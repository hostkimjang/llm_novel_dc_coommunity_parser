from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    can_publish_title,
)
from tools.run_candidate_generation_completeness_harness import (
    _canonical_hash,
    _sha256_file,
    build_comparison,
    create_run_spec,
    validate_run_spec,
    write_comparison,
    write_run_spec,
)


def fixture_row(post_id: int) -> dict:
    title = "합성 기준 작품"
    url = f"https://example.test/{post_id}"
    state = GroundingState(
        post_id=post_id,
        candidate_title=title,
        candidate_url=url,
        official_title_exists=True,
        row_discusses_work_as_work=True,
        title_resolution_state="resolved",
        work_resolution="resolved",
        scope=ScopeState(scope_kind="current_work", confidence="high"),
    )
    evidence = [
        EvidenceRecord(
            kind="official_detail",
            strength="strong",
            supports_publish=True,
            candidate_title=title,
            candidate_url=url,
            title_url_match=True,
            reason_code="official_detail_display_title_exact",
        )
    ]
    decision = can_publish_title(state, evidence)
    identity = {
        "novel_identity": {
            "official_title": decision.official_title,
            "official_url": decision.official_url,
        },
        "candidate_preservation_sources": [
            {
                "official_title": title,
                "heretic_url": url,
                "preservation_role": "title_candidate",
            }
        ],
        "candidate_ledger": {},
        "promotion_gate_state": state.to_dict(),
        "promotion_gate_evidence": [item.to_dict() for item in evidence],
        "promotion_decision": decision.to_dict(),
        "publish_contract_input_fingerprint": "a" * 64,
        "publish_contract_version": "promotion_contract_v2",
    }
    return {"post_id": post_id, "analysis_result": {"identity": identity}}


class CandidateGenerationCompletenessHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.baseline = self.root / "baseline.json"
        self.parent = self.root / "p1.json"
        self.rows = [fixture_row(1), fixture_row(2)]
        self.baseline.write_text(
            json.dumps(self.rows, ensure_ascii=False),
            encoding="utf-8",
        )
        ids = ["1", "2"]
        contract = {
            "row_count": 2,
            "post_id_order_sha256": _canonical_hash(ids),
            "post_id_set_sha256": _canonical_hash(sorted(ids)),
        }
        baseline_ref = {
            "path": str(self.baseline),
            "sha256": _sha256_file(self.baseline),
            "bytes": self.baseline.stat().st_size,
        }
        parent = {
            "schema_version": "candidate-set-nil-shadow-runspec-v1",
            "mode": "SAVED_ARTIFACT_SHADOW_NO_RUNTIME",
            "artifacts": {"baseline_result": baseline_ref},
            "post_contract": contract,
        }
        parent["run_spec_sha256"] = _canonical_hash(parent)
        self.parent.write_text(json.dumps(parent), encoding="utf-8")
        self.parent_payload = parent
        self.parent_validation = patch(
            "tools.run_candidate_set_nil_shadow_harness.validate_run_spec",
            return_value=(parent, self.rows, {}),
        )
        self.parent_validation.start()

    def tearDown(self) -> None:
        self.parent_validation.stop()
        self.tmp.cleanup()

    def spec_path(self) -> Path:
        path = self.root / "out" / "run_spec.json"
        write_run_spec(
            create_run_spec(parent_p1_run_spec_path=self.parent),
            path,
        )
        return path

    def test_saved_rows_and_synthetic_boundary_cases_are_separated(self) -> None:
        report = build_comparison(self.spec_path())

        self.assertEqual(
            "GO_SAVED_ARTIFACT_AND_SYNTHETIC_SHADOW_ONLY",
            report["gates"]["overall"],
        )
        self.assertEqual("NOT_RUN", report["gates"]["runtime_validation"])
        self.assertFalse(report["gates"]["full_scan_approval"])
        self.assertEqual(2, report["summary"]["actual_public_contract_unchanged_rows"])
        self.assertEqual(
            "TRUNCATED",
            report["synthetic_cases"]["unique_25"]["after"]["status"],
        )
        self.assertEqual(
            "UNKNOWN",
            report["synthetic_cases"]["exact_24"]["after"]["status"],
        )
        self.assertEqual(
            24,
            report["synthetic_cases"]["raw_25_unique_24"]["after"][
                "unique_valid_source_count"
            ],
        )
        self.assertEqual(
            "TRUNCATED",
            report["synthetic_cases"]["title_unique_7"]["after"]["status"],
        )
        self.assertEqual(
            "UNKNOWN",
            report["synthetic_cases"]["title_exact_6"]["after"]["status"],
        )
        self.assertEqual(
            6,
            report["synthetic_cases"]["title_raw_7_unique_6"]["after"][
                "unique_valid_source_count"
            ],
        )
        self.assertEqual(
            1,
            report["synthetic_cases"]["title_same_name_different_url"]["after"][
                "unique_valid_source_count"
            ],
        )
        self.assertEqual(2, report["summary"]["synthetic_truncation_detected_after"])
        self.assertEqual(
            7,
            report["summary"]["synthetic_stage_truncation_detected_after"],
        )
        self.assertEqual(
            "GO_DIAGNOSTIC_ONLY",
            report["gates"]["stage_local_receipt_detection"],
        )
        self.assertEqual(
            "GO_SYNTHETIC_CONTRACT_ONLY",
            report["gates"]["producer_completion_proof"],
        )
        self.assertEqual(
            "IMPLEMENTED_NOT_RUNTIME_VALIDATED",
            report["gates"]["producer_runtime_wiring"],
        )
        self.assertEqual(1, report["summary"]["synthetic_producer_complete_after"])
        self.assertEqual(4, report["summary"]["synthetic_producer_unknown_after"])
        self.assertEqual(1, report["summary"]["synthetic_producer_truncated_after"])
        self.assertEqual(
            "COMPLETE",
            report["producer_synthetic_cases"]["clean_search_fetch"]["after"][
                "producer_proof"
            ]["status"],
        )
        self.assertEqual(
            "UNKNOWN",
            report["producer_synthetic_cases"]["clean_cache_replay"]["after"][
                "producer_proof"
            ]["status"],
        )
        self.assertEqual(
            "UNKNOWN",
            report["producer_synthetic_cases"]["missing_fetch_receipt"]["after"][
                "producer_proof"
            ]["status"],
        )
        self.assertEqual(
            "TRUNCATED",
            report["producer_synthetic_cases"]["search_top_k_loss"]["after"][
                "producer_proof"
            ]["status"],
        )
        self.assertTrue(
            all(
                case["retained_sources_unchanged"]
                for case in report["synthetic_cases"].values()
            )
        )
        self.assertTrue(
            all(
                case["retained_sources_unchanged"]
                and case["candidate_set_status_effect"] == "NONE_DIAGNOSTIC_ONLY"
                and case["public_decision_effect"] == "NONE"
                for case in report["stage_synthetic_cases"].values()
            )
        )
        self.assertEqual(
            "UNKNOWN",
            report["stage_synthetic_cases"][
                "gatekeeper.comment_title_candidates.duplicate_beyond_cap"
            ]["after"]["status"],
        )

    def test_self_hash_and_implementation_artifact_tamper_are_rejected(self) -> None:
        path = self.spec_path()
        spec = json.loads(path.read_text(encoding="utf-8"))
        spec["approval_boundary"]["runtime_validation"] = "GO"
        path.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "self hash mismatch"):
            validate_run_spec(path)

        fresh = self.root / "out" / "fresh.json"
        fresh_spec = create_run_spec(parent_p1_run_spec_path=self.parent)
        fresh_spec["implementation_contract"]["artifacts"]["candidate_generation"][
            "sha256"
        ] = "0" * 64
        fresh_spec["run_spec_sha256"] = _canonical_hash(
            {key: value for key, value in fresh_spec.items() if key != "run_spec_sha256"}
        )
        write_run_spec(fresh_spec, fresh)
        with self.assertRaisesRegex(ValueError, "artifact sha256 mismatch"):
            validate_run_spec(fresh)

    def test_outputs_are_korean_and_write_once(self) -> None:
        report = build_comparison(self.spec_path())
        json_path = self.root / "out" / "comparison.json"
        md_path = self.root / "out" / "comparison.md"
        write_comparison(report, output_json=json_path, output_md=md_path)
        markdown = md_path.read_text(encoding="utf-8")
        self.assertIn("후보 생성 완전성 증명 개선 보고서", markdown)
        self.assertIn("정확도로 읽으면 안 되는 이유", markdown)
        self.assertIn("단계별 진단 영수증은 무슨 기능인가", markdown)
        self.assertIn("CandidateSet 상태에는 합성하지 않는다", markdown)
        self.assertIn("상류 producer 완료 증명은 무슨 기능인가", markdown)
        self.assertIn("정상 search+fetch", markdown)
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            write_comparison(report, output_json=json_path, output_md=self.root / "out" / "second.md")


if __name__ == "__main__":
    unittest.main()
