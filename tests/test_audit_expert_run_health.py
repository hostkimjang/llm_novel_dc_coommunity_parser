import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_expert_run_health import _resolve_run_artifacts


class AuditExpertRunHealthTest(unittest.TestCase):
    def test_resolves_launcher_prefix_from_manifest_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            out = repo / "out"
            logs = repo / "logs"
            out.mkdir()
            logs.mkdir()
            manifest = out / "expert_result_20260702_065632_479765_manifest.json"
            manifest.write_text(
                json.dumps({"run_id": "20260702_065642_030743"}, ensure_ascii=False),
                encoding="utf-8",
            )

            artifacts = _resolve_run_artifacts("20260702_065642_030743", repo=repo)

            self.assertEqual(artifacts["resolution"], "manifest_run_id_lookup")
            self.assertEqual(artifacts["artifact_prefix"], "20260702_065632_479765")
            self.assertEqual(artifacts["manifest"], manifest)
            self.assertEqual(
                artifacts["checkpoint"],
                out / "expert_result_20260702_065632_479765_checkpoint.jsonl",
            )
            self.assertEqual(
                artifacts["pending"],
                out / "expert_result_20260702_065632_479765_pending_snapshot.json",
            )

    def test_prefers_direct_prefix_when_manifest_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            out = repo / "out"
            logs = repo / "logs"
            out.mkdir()
            logs.mkdir()
            manifest = out / "expert_result_run123_manifest.json"
            manifest.write_text(json.dumps({"run_id": "run123"}), encoding="utf-8")

            artifacts = _resolve_run_artifacts("run123", repo=repo)

            self.assertEqual(artifacts["resolution"], "direct_prefix")
            self.assertEqual(artifacts["artifact_prefix"], "run123")
            self.assertEqual(artifacts["manifest"], manifest)


if __name__ == "__main__":
    unittest.main()
