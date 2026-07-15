from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_interrupted_run_residual import build_residual, main


class BuildInterruptedRunResidualTest(unittest.TestCase):
    def test_preserves_source_order_and_builds_exact_partition(self) -> None:
        source = [
            {"post_id": 30, "title": "thirty"},
            {"post_id": 10, "title": "ten"},
            {"post_id": 20, "title": "twenty"},
        ]
        recovered = [{"post_id": 10, "title": "ten"}]

        residual, manifest = build_residual(
            source,
            recovered,
            expected_source_count=3,
            expected_recovered_count=1,
            expected_residual_count=2,
        )

        self.assertEqual([row["post_id"] for row in residual], [30, 20])
        self.assertEqual(manifest["gate"], "GO")
        self.assertTrue(manifest["integrity"]["original_order_preserved"])
        self.assertEqual(manifest["integrity"]["partition_missing_post_ids"], [])
        self.assertEqual(manifest["integrity"]["recovered_residual_overlap_post_ids"], [])
        self.assertEqual(manifest["residual_post_ids_in_source_order"], ["30", "20"])

    def test_rejects_duplicate_and_missing_recovered_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate post_id"):
            build_residual([{"post_id": 1}, {"post_id": 1}], [])
        with self.assertRaisesRegex(ValueError, "absent from source"):
            build_residual([{"post_id": 1}], [{"post_id": 2}])

    def test_cli_outputs_are_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            recovered = root / "recovered.json"
            output = root / "residual.jsonl"
            manifest = root / "manifest.json"
            source.write_text('{"post_id": 1}\n{"post_id": 2}\n', encoding="utf-8")
            recovered.write_text(json.dumps([{"post_id": 1}]), encoding="utf-8")

            import sys

            original_argv = sys.argv
            try:
                sys.argv = [
                    "build_interrupted_run_residual.py",
                    "--source-jsonl",
                    str(source),
                    "--recovered-json",
                    str(recovered),
                    "--output-jsonl",
                    str(output),
                    "--manifest-json",
                    str(manifest),
                    "--expected-source-count",
                    "2",
                    "--expected-recovered-count",
                    "1",
                    "--expected-residual-count",
                    "1",
                ]
                self.assertEqual(main(), 0)
                with self.assertRaises(FileExistsError):
                    main()
            finally:
                sys.argv = original_argv


if __name__ == "__main__":
    unittest.main()
