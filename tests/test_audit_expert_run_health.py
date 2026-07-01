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

    def test_explicit_paths_override_default_expert_result_locations(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            sampling = repo / "out" / "sampling"
            logs = repo / "logs"
            sampling.mkdir(parents=True)
            logs.mkdir()
            manifest = sampling / "custom_manifest.json"
            checkpoint = sampling / "custom_checkpoint.jsonl"
            pending = sampling / "custom_pending.json"
            worker_log = logs / "custom_W0.log"
            manifest.write_text(json.dumps({"run_id": "sample-run"}), encoding="utf-8")
            checkpoint.write_text("", encoding="utf-8")
            pending.write_text("[]", encoding="utf-8")
            worker_log.write_text("worker log", encoding="utf-8")

            artifacts = _resolve_run_artifacts(
                "sample-run",
                repo=repo,
                manifest_path=str(manifest),
                checkpoint_path=str(checkpoint),
                pending_snapshot_path=str(pending),
                log_glob=str(logs / "custom_*.log"),
            )

            self.assertEqual(artifacts["resolution"], "explicit_paths")
            self.assertEqual(artifacts["explicit_overrides"], ["manifest", "checkpoint", "pending_snapshot", "log_glob"])
            self.assertEqual(artifacts["manifest"], manifest)
            self.assertEqual(artifacts["checkpoint"], checkpoint)
            self.assertEqual(artifacts["pending"], pending)
            self.assertEqual(artifacts["log_files"], [worker_log])

    def test_missing_explicit_manifest_does_not_fallback_to_run_id_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            out = repo / "out"
            logs = repo / "logs"
            out.mkdir()
            logs.mkdir()
            fallback_manifest = out / "expert_result_fallback_manifest.json"
            missing_manifest = out / "sampling" / "missing_manifest.json"
            fallback_manifest.write_text(json.dumps({"run_id": "sample-run"}), encoding="utf-8")

            artifacts = _resolve_run_artifacts(
                "sample-run",
                repo=repo,
                manifest_path=str(missing_manifest),
            )

            self.assertEqual(artifacts["resolution"], "explicit_paths")
            self.assertEqual(artifacts["manifest"], missing_manifest)
            self.assertNotEqual(artifacts["manifest"], fallback_manifest)


if __name__ == "__main__":
    unittest.main()
