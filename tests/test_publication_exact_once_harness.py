from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.run_publication_exact_once_harness import (
    ROOT,
    build_comparison,
    create_run_spec,
    render_markdown,
    validate_run_spec,
)


P1_RUN_SPEC = ROOT / "out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json"
PRODUCER_RUN_SPEC = (
    ROOT / "out/candidate_generation_completeness_harness_20260711/v6/run_spec.json"
)


class PublicationExactOnceHarnessTest(unittest.TestCase):
    def _write_spec(self, root: Path) -> Path:
        spec = create_run_spec(
            parent_p1_run_spec_path=P1_RUN_SPEC,
            parent_producer_run_spec_path=PRODUCER_RUN_SPEC,
        )
        path = root / "run_spec.json"
        path.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def test_golden18_saved_artifact_and_attack_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_spec(Path(tmp))
            report = build_comparison(path)

        self.assertEqual(report["source"]["row_count"], 18)
        self.assertEqual(report["before"]["valid_commit_count"], 0)
        self.assertEqual(report["after"]["valid_commit_count"], 18)
        self.assertEqual(report["after"]["new_commit_count"], 18)
        self.assertEqual(report["after"]["restart_replay_noop_count"], 18)
        self.assertEqual(report["after"]["outcomes"], {"HOLD": 15, "PUBLISH": 3})
        self.assertEqual(report["noninterference"]["public_projection_unchanged_count"], 18)
        self.assertEqual(report["noninterference"]["full_result_row_unchanged_count"], 18)
        self.assertEqual(report["synthetic_attacks"]["false_go_count"], 0)
        self.assertEqual(report["gates"]["saved_artifact_and_synthetic"], "GO")
        self.assertEqual(report["gates"]["production_runtime"], "NOT_RUN")

    def test_receipts_are_hash_only_and_result_json_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_spec(Path(tmp))
            report = build_comparison(path)

        for receipt in report["after"]["receipts"]:
            self.assertFalse(any("title" in key.lower() for key in receipt))
            self.assertFalse(any("url" in key.lower() for key in receipt))
        self.assertFalse(report["noninterference"]["result_json_receipt_embedded"])
        self.assertEqual(report["after"]["receipt_raw_public_copy_count"], 0)

    def test_runspec_rejects_scope_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_spec(Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["publication_commit_contract"]["publication_scope_id"] = "0" * 64
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "self hash mismatch"):
                validate_run_spec(path)

    def test_markdown_explains_function_and_approval_boundary_in_korean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_spec(Path(tmp))
            markdown = render_markdown(build_comparison(path))

        self.assertIn("이 기능이 하는 일", markdown)
        self.assertIn("개선 전과 개선 후", markdown)
        self.assertIn("실제 새 runtime: `NOT_RUN`", markdown)
        self.assertIn("전체 스캔 승인: `false`", markdown)


if __name__ == "__main__":
    unittest.main()
