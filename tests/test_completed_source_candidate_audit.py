from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_completed_source_candidate_audit.py"
    spec = importlib.util.spec_from_file_location("build_completed_source_candidate_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def neutral_identity_row(post_id: int) -> dict:
    return {
        "post_id": post_id,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
            }
        },
    }


class CompletedSourceCandidateAuditTest(unittest.TestCase):
    def test_missing_completed_source_candidate_stays_review_locked(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            write_json(out / "partial.json", [{"post_id": 1}, {"post_id": 2}, {"post_id": 3}, {"post_id": 4}])
            write_json(
                out / "partial_manifest.json",
                {
                    "run_id": "partial",
                    "input_post_count": 100,
                    "completed_count": 4,
                    "flushed_count": 4,
                    "pending_count": 96,
                    "failed_count": 0,
                    "large_run_complete": False,
                    "vlm_enabled": True,
                    "ocr_enabled": True,
                },
            )
            write_json(out / "clean_short.json", [neutral_identity_row(10), neutral_identity_row(11)])
            write_json(
                out / "clean_short_manifest.json",
                {
                    "run_id": "clean-short",
                    "input_post_count": 2,
                    "completed_count": 2,
                    "flushed_count": 2,
                    "pending_count": 0,
                    "failed_count": 0,
                    "large_run_complete": True,
                    "vlm_ocr_semantic_review_ready": True,
                    "mcp_health_include_search": True,
                    "mcp_health_light_mode": False,
                    "mcp_health_failure_count": 0,
                },
            )
            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                report = mod.build_audit(out, random_target=3)
            finally:
                os.chdir(old_cwd)

        self.assertEqual(report["gate"]["overall"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["approval_source_candidate_count"], 0)
        self.assertEqual(report["summary"]["clean_vlm_ocr_random_shortfall_count"], 1)
        self.assertEqual(report["summary"]["clean_vlm_ocr_search_health_not_ready_count"], 0)
        self.assertEqual(report["summary"]["partial_vlm_ocr_population_ge_random_target_count"], 1)
        self.assertIn("no_completed_vlm_ocr_source_with_random_target_rows", report["gate"]["blockers"])

    def test_completed_candidate_is_found_but_not_semantic_approval(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            write_json(
                out / "complete.json",
                [neutral_identity_row(1), neutral_identity_row(2), neutral_identity_row(3)],
            )
            write_json(
                out / "complete_manifest.json",
                {
                    "run_id": "complete",
                    "input_post_count": 3,
                    "completed_count": 3,
                    "flushed_count": 3,
                    "pending_count": 0,
                    "failed_count": 0,
                    "large_run_complete": True,
                    "vlm_enabled": True,
                    "ocr_enabled": True,
                    "mcp_health_include_search": True,
                    "mcp_health_light_mode": False,
                    "mcp_health_failure_count": 0,
                },
            )
            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                report = mod.build_audit(out, random_target=3)
            finally:
                os.chdir(old_cwd)

        self.assertEqual(report["gate"]["overall"], "REVIEW")
        self.assertFalse(report["gate"]["full_scan_approval"])
        self.assertEqual(report["gate"]["semantic_quality"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["approval_source_candidate_count"], 1)
        self.assertEqual(report["approval_source_candidates"][0]["run_id"], "complete")
        self.assertTrue(report["approval_source_candidates"][0]["search_health_ready"])
        self.assertTrue(report["approval_source_candidates"][0]["publication_contract_ready"])
        self.assertEqual(
            report["approval_source_candidates"][0]["publication_contract_convergence_gate"],
            "GO",
        )

    def test_clean_candidate_without_direct_search_health_is_blocked(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            write_json(out / "complete.json", [{"post_id": 1}, {"post_id": 2}, {"post_id": 3}])
            write_json(
                out / "complete_manifest.json",
                {
                    "run_id": "complete-light-health",
                    "input_post_count": 3,
                    "completed_count": 3,
                    "flushed_count": 3,
                    "pending_count": 0,
                    "failed_count": 0,
                    "large_run_complete": True,
                    "vlm_enabled": True,
                    "ocr_enabled": True,
                    "mcp_health_include_search": False,
                    "mcp_health_light_mode": True,
                    "mcp_health_failure_count": 0,
                },
            )
            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                report = mod.build_audit(out, random_target=3)
            finally:
                os.chdir(old_cwd)

        self.assertEqual(report["gate"]["overall"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["approval_source_candidate_count"], 0)
        self.assertEqual(report["summary"]["clean_vlm_ocr_search_health_not_ready_count"], 1)
        self.assertEqual(report["summary"]["clean_vlm_ocr_search_health_blocked_count"], 1)
        self.assertIn("clean_sources_exist_but_search_health_not_ready", report["gate"]["blockers"])
        blocked = report["clean_vlm_ocr_search_health_blocked_candidates"][0]
        self.assertEqual(report["clean_vlm_ocr_search_health_not_ready_candidates"][0]["run_id"], "complete-light-health")
        self.assertFalse(blocked["search_health_ready"])
        self.assertFalse(blocked["search_health_included"])
        self.assertTrue(blocked["search_health_light_mode"])

    def test_clean_candidate_without_publication_contract_convergence_is_blocked(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            write_json(
                out / "complete.json",
                [
                    {
                        "post_id": 1,
                        "analysis_result": {
                            "identity": {
                                "novel_identity": {
                                    "official_title": "테라포밍",
                                    "heretic_url": "https://novel.munpia.com/416826",
                                }
                            }
                        },
                    },
                    neutral_identity_row(2),
                    neutral_identity_row(3),
                ],
            )
            write_json(
                out / "complete_manifest.json",
                {
                    "run_id": "complete-publication-contract-leak",
                    "input_post_count": 3,
                    "completed_count": 3,
                    "flushed_count": 3,
                    "pending_count": 0,
                    "failed_count": 0,
                    "large_run_complete": True,
                    "vlm_enabled": True,
                    "ocr_enabled": True,
                    "mcp_health_include_search": True,
                    "mcp_health_light_mode": False,
                    "mcp_health_failure_count": 0,
                },
            )
            old_cwd = Path.cwd()
            try:
                import os

                os.chdir(root)
                report = mod.build_audit(out, random_target=3)
            finally:
                os.chdir(old_cwd)

        self.assertEqual(report["gate"]["overall"], "REVIEW-LOCKED")
        self.assertEqual(report["summary"]["approval_source_candidate_count"], 0)
        self.assertEqual(
            report["summary"]["clean_vlm_ocr_publication_contract_not_ready_count"],
            1,
        )
        self.assertIn(
            "clean_sources_exist_but_publication_contract_not_ready",
            report["gate"]["blockers"],
        )
        blocked = report["clean_vlm_ocr_publication_contract_not_ready_candidates"][0]
        self.assertEqual(blocked["run_id"], "complete-publication-contract-leak")
        self.assertFalse(blocked["publication_contract_ready"])
        self.assertEqual(blocked["publication_contract_convergence_gate"], "NO-GO")


if __name__ == "__main__":
    unittest.main()
