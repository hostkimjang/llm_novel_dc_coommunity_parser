from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.llm_batch.grounding.candidate_set_shadow import NIL_LABEL
from src.llm_batch.promotion_gate import (
    can_publish_title,
    evidence_records_from_payload,
    grounding_state_from_dict,
)
from tools.run_candidate_set_nil_shadow_harness import (
    EXPECTED_RECALL_STATUS,
    _canonical_hash,
    _sha256_file,
    build_saved_artifact_comparison,
    create_run_spec,
    validate_run_spec,
    write_comparison,
    write_run_spec,
)


def fixture_row(post_id: int, title: str | None) -> dict:
    state = {"post_id": post_id, "candidate_title": title or "", "candidate_url": f"https://example.test/{post_id}" if title else "", "source": "test", "official_title_exists": bool(title), "row_discusses_work_as_work": bool(title), "title_resolution_state": "resolved" if title else "unresolved_matchable", "work_resolution": "resolved" if title else "unresolved", "scope": {"scope_kind": "current_work" if title else "unknown", "confidence": "high", "direct_bridge_sources": ["explicit_alias_relation"] if title else [], "competing_candidates": [], "conflict_reason_codes": []}}
    evidence = [{"candidate_title": title, "candidate_url": f"https://example.test/{post_id}", "supports_publish": True}] if title else []
    decision = can_publish_title(
        grounding_state_from_dict(state), evidence_records_from_payload(evidence)
    ).to_dict()
    identity = {
        "novel_identity": {"official_title": decision["official_title"], "official_url": decision["official_url"]} if decision["publish_allowed"] else None,
        "promotion_decision": decision,
        "publish_contract_input_fingerprint": "a" * 64,
        "promotion_gate_state": state,
        "promotion_gate_evidence": evidence,
    }
    return {"post_id": post_id, "analysis_result": {"identity": identity}}


class CandidateSetNilShadowHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.baseline = self.root / "baseline.json"
        self.parent = self.root / "p0.json"
        self.audit = self.root / "audit.json"
        self.ledger = self.root / "ledger.json"
        self.p0_validation = patch(
            "tools.run_pipeline_improvement_harness.validate_run_spec",
            return_value=({}, [], {}),
        )
        self.p0_validation.start()
        self.rows = [fixture_row(1, "작품 하나"), fixture_row(2, None)]
        self.baseline.write_text(json.dumps(self.rows, ensure_ascii=False), encoding="utf-8")
        ids = ["1", "2"]
        contract = {"row_count": 2, "post_id_order_sha256": _canonical_hash(ids), "post_id_set_sha256": _canonical_hash(sorted(ids))}
        baseline_ref = {"path": str(self.baseline), "sha256": _sha256_file(self.baseline)}
        parent = {"schema_version": "pipeline-improvement-runspec-v2", "artifacts": {"baseline_result": baseline_ref}, "post_contract": contract}
        parent["run_spec_sha256"] = _canonical_hash(parent)
        self.parent.write_text(json.dumps(parent), encoding="utf-8")
        audit = {"report_type": "golden18_bound_audit", "semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False, "row_count": 2, "after_result_sha256": baseline_ref["sha256"], "after_post_id_order_sha256": contract["post_id_order_sha256"], "after_post_id_set_sha256": contract["post_id_set_sha256"], "rows": [{"post_id": 1, "passed": True, "golden_role": "positive_expected_work", "expected_title_or_hypothesis": "작품 하나"}, {"post_id": 2, "passed": True, "golden_role": "negative_no_public_work", "expected_no_public_title": True, "status": "expected_null_respected"}]}
        self.audit.write_text(json.dumps(audit), encoding="utf-8")
        ledger = {"schema_version": "candidate-set-nil-label-ledger-v1", "source_expected_audit": {"path": str(self.audit), "sha256": _sha256_file(self.audit)}, "source_baseline_result": baseline_ref, "label_policy": {"abstain_is_not_truth_label": True, "candidate_set_recall_requires_complete_generation_status": True}, "semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False, "counts": {"rows": 2, "candidate_truth": 1, "nil_truth": 1, "unjudged": 0}, "rows": [{"post_id": 1, "truth_kind": "CANDIDATE", "expected_title": "작품 하나"}, {"post_id": 2, "truth_kind": "NIL", "expected_title": None}]}
        self.ledger.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.p0_validation.stop()
        self.tmp.cleanup()

    def spec_path(self) -> Path:
        path = self.root / "out" / "run_spec.json"
        write_run_spec(create_run_spec(parent_p0_run_spec_path=self.parent, expected_audit_path=self.audit, label_ledger_path=self.ledger), path)
        return path

    def test_frozen_saved_artifact_shadow_is_publicly_noninterfering(self) -> None:
        report = build_saved_artifact_comparison(self.spec_path())
        self.assertEqual("GO_SAVED_ARTIFACT_SHADOW_ONLY", report["gates"]["overall"])
        self.assertEqual("NOT_RUN", report["gates"]["runtime_validation"])
        self.assertFalse(report["gates"]["full_scan_approval"])
        for row in report["rows"]:
            self.assertIn(NIL_LABEL, row["candidate_nil_event"]["labels"])
            self.assertTrue(row["candidate_nil_event"]["probabilities_all_null"])
            self.assertEqual(EXPECTED_RECALL_STATUS, row["candidate_set"]["candidate_set_recall_status"])
            self.assertTrue(row["public_noninterference"]["unchanged"])
            self.assertEqual(row["public_noninterference"]["before_sha256"], row["public_noninterference"]["after_sha256"])

    def test_tampered_parent_and_implementation_are_rejected(self) -> None:
        path = self.spec_path()
        parent = json.loads(self.parent.read_text(encoding="utf-8"))
        parent["post_contract"]["row_count"] = 3
        self.parent.write_text(json.dumps(parent), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "artifact sha256 mismatch"):
            validate_run_spec(path)

    def test_frozen_parent_validation_accepts_historical_source_drift_but_not_malformed_record(self) -> None:
        historical = Path(__file__).resolve().parents[1] / "out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json"
        with self.assertRaisesRegex(ValueError, "artifact sha256 mismatch"):
            validate_run_spec(historical)
        frozen, rows, _ = validate_run_spec(historical, verify_implementation=False)
        self.assertEqual(18, len(rows))
        self.assertEqual("5b36fe5de439eb37d358b5a0e8185cdd61f610760676623086d92207abac16a9", frozen["run_spec_sha256"])

        path = self.spec_path()
        spec = json.loads(path.read_text(encoding="utf-8"))
        implementation = spec["implementation_contract"]
        implementation["artifacts"]["agentic_pipeline"]["bytes"] = 0
        implementation["sha256"] = _canonical_hash(
            {
                name: ref["sha256"]
                for name, ref in sorted(implementation["artifacts"].items())
            }
        )
        spec["run_spec_sha256"] = _canonical_hash(
            {key: value for key, value in spec.items() if key != "run_spec_sha256"}
        )
        path.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "frozen implementation bytes invalid"):
            validate_run_spec(path, verify_implementation=False)

    def test_self_hash_ledger_and_overwrite_are_rejected(self) -> None:
        path = self.spec_path()
        spec = json.loads(path.read_text(encoding="utf-8"))
        spec["approval_boundary"]["runtime_validation"] = "GO"
        path.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "self hash mismatch"):
            validate_run_spec(path)
        fresh_path = self.root / "out" / "fresh_run_spec.json"
        write_run_spec(
            create_run_spec(
                parent_p0_run_spec_path=self.parent,
                expected_audit_path=self.audit,
                label_ledger_path=self.ledger,
            ),
            fresh_path,
        )
        report = build_saved_artifact_comparison(fresh_path)
        out_json, out_md = self.root / "out" / "report.json", self.root / "out" / "report.md"
        _, markdown = write_comparison(report, output_json=out_json, output_md=out_md)
        self.assertIn("저장 산출물", markdown.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            write_comparison(report, output_json=out_json, output_md=self.root / "out" / "second.md")

    def test_label_ledger_source_binding_is_required(self) -> None:
        ledger = json.loads(self.ledger.read_text(encoding="utf-8"))
        ledger["counts"]["candidate_truth"] = 0
        self.ledger.write_text(json.dumps(ledger), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "label ledger counts mismatch"):
            create_run_spec(parent_p0_run_spec_path=self.parent, expected_audit_path=self.audit, label_ledger_path=self.ledger)

    def test_candidate_truth_missing_from_event_space_is_rejected(self) -> None:
        audit = json.loads(self.audit.read_text(encoding="utf-8"))
        audit["rows"][0]["expected_title_or_hypothesis"] = "후보에 없는 작품"
        self.audit.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")
        ledger = json.loads(self.ledger.read_text(encoding="utf-8"))
        ledger["source_expected_audit"]["sha256"] = _sha256_file(self.audit)
        ledger["rows"][0]["expected_title"] = "후보에 없는 작품"
        self.ledger.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        spec_path = self.root / "out" / "missing_truth_run_spec.json"
        write_run_spec(
            create_run_spec(
                parent_p0_run_spec_path=self.parent,
                expected_audit_path=self.audit,
                label_ledger_path=self.ledger,
            ),
            spec_path,
        )
        with self.assertRaisesRegex(ValueError, "exact candidate truth missing"):
            build_saved_artifact_comparison(spec_path)


if __name__ == "__main__":
    unittest.main()
