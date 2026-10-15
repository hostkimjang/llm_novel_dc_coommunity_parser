from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import run_publication_exact_once_harness as harness
from tests.candidate_shadow_graph_fixture import build_current_shadow_graph, new_graph_directory

from tools.run_publication_exact_once_harness import (
    ROOT,
    build_comparison,
    create_run_spec,
    render_markdown,
    validate_run_spec,
)


class PublicationExactOnceHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        directory = new_graph_directory()
        cls.addClassCleanup(directory.cleanup)
        cls.graph = build_current_shadow_graph(Path(directory.name), include_calibration=False)

    def _write_spec(self, root: Path) -> Path:
        spec = create_run_spec(
            parent_p1_run_spec_path=self.graph.p1,
            parent_producer_run_spec_path=self.graph.producer,
        )
        path = root / "run_spec.json"
        path.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def test_synthetic18_saved_artifact_and_attack_gate(self) -> None:
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


class PublicationImplementationContractTests(unittest.TestCase):
    def test_new_runspec_source_binding_and_writer_with_synthetic_parent_boundary(self) -> None:
        # 부모 의미 재생은 기존 시험이 담당한다. 여기서는 새 지문/저장 경계만 분리한다.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, parent, producer = (root / name for name in ("baseline.json", "parent.json", "producer.json"))
            rows = [{"post_id": 1}]
            baseline.write_text(json.dumps(rows), encoding="utf-8")
            parent.write_text("{}", encoding="utf-8")
            producer.write_text("{}", encoding="utf-8")
            p1 = {"artifacts": {"baseline_result": harness._artifact_ref(baseline)}, "run_spec_sha256": "1" * 64}
            chain = (p1, {"run_spec_sha256": "2" * 64}, rows, harness._post_contract(rows))
            output_root = root / "new-output"
            with patch.object(harness, "_parent_chain", return_value=chain), patch.object(harness, "OUTPUT_ROOT", output_root):
                spec = create_run_spec(parent_p1_run_spec_path=parent, parent_producer_run_spec_path=producer)
                path = harness.write_run_spec(spec, output_root / "run_spec.json")
                saved, saved_rows = validate_run_spec(path)
                self.assertEqual(spec, saved)
                self.assertEqual(rows, saved_rows)
                self.assertIs(True, inspect.signature(validate_run_spec).parameters["verify_implementation"].default)
                artifacts = saved["implementation_contract"]["artifacts"]
                expected = {"publication_commit": "src/llm_batch/ledger/publication_commit.py",
                            "decision_call_independent_reader": "src/llm_batch/ledger/decision_call_readback.py",
                            "promotion_gate": "src/llm_batch/promotion_gate.py"}
                for name, relative in expected.items():
                    raw = (ROOT / relative).read_bytes()
                    self.assertEqual(relative, artifacts[name]["path"])
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), artifacts[name]["sha256"])
                    self.assertEqual(len(raw), artifacts[name]["bytes"])
                with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                    harness.write_run_spec(spec, path)
                with self.assertRaisesRegex(ValueError, "output must stay under"):
                    harness.write_run_spec(spec, root / "outside.json")
                forged = copy.deepcopy(spec)
                forged["implementation_contract"]["artifacts"]["publication_commit"]["sha256"] = "0" * 64
                forged["implementation_contract"]["sha256"] = harness._canonical_hash(
                    {name: ref["sha256"] for name, ref in sorted(forged["implementation_contract"]["artifacts"].items())}
                )
                forged["run_spec_sha256"] = harness._run_spec_self_hash(forged)
                forged_path = harness.write_run_spec(forged, output_root / "forged.json")
                with self.assertRaisesRegex(ValueError, "implementation contract mismatch"):
                    validate_run_spec(forged_path)
                # frozen 모드는 현재 지문 검증을 생략해도 잘못된 구조는 허용하지 않는다.
                forged["implementation_contract"]["artifacts"]["publication_commit"]["bytes"] = 0
                forged["run_spec_sha256"] = harness._run_spec_self_hash(forged)
                malformed_path = harness.write_run_spec(forged, output_root / "malformed.json")
                with self.assertRaisesRegex(ValueError, "frozen implementation bytes invalid"):
                    validate_run_spec(malformed_path, verify_implementation=False)


if __name__ == "__main__":
    unittest.main()
