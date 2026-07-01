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
            write_json(out / "clean_short.json", [{"post_id": 10}, {"post_id": 11}])
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
        self.assertEqual(report["summary"]["partial_vlm_ocr_population_ge_random_target_count"], 1)
        self.assertIn("no_completed_vlm_ocr_source_with_random_target_rows", report["gate"]["blockers"])

    def test_completed_candidate_is_found_but_not_semantic_approval(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            write_json(out / "complete.json", [{"post_id": 1}, {"post_id": 2}, {"post_id": 3}])
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


if __name__ == "__main__":
    unittest.main()
