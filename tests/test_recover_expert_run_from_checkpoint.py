import json
import tempfile
import unittest
from pathlib import Path

from tools.recover_expert_run_from_checkpoint import recover


class RecoverExpertRunFromCheckpointTest(unittest.TestCase):
    def test_recovers_completed_rows_and_classifies_pending_flush_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            checkpoint_path = root / "checkpoint.jsonl"
            pending_path = root / "pending.json"
            manifest_path = root / "manifest.json"
            recovered_path = root / "recovered.json"
            summary_path = root / "summary.json"

            result_path.write_text(
                json.dumps([{"post_id": 1, "title": "first"}], ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint_rows = [
                {"global_idx": 1, "post_id": 1, "status": "completed", "result": {"post_id": 1, "title": "first"}},
                {"global_idx": 2, "post_id": 2, "status": "completed", "result": {"post_id": 2, "title": "second"}},
            ]
            checkpoint_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in checkpoint_rows) + "\n",
                encoding="utf-8",
            )
            pending_path.write_text(
                json.dumps([{"global_idx": 2, "post_id": 2, "result": {"post_id": 2, "title": "second"}}], ensure_ascii=False),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "test",
                        "input_post_count": 10,
                        "completed_count": 2,
                        "flushed_count": 1,
                        "pending_count": 1,
                        "failed_count": 0,
                        "next_save_idx": 2,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=summary_path,
            )

            recovered = json.loads(recovered_path.read_text(encoding="utf-8"))
            self.assertEqual([row["post_id"] for row in recovered], [1, 2])
            self.assertEqual(summary["missing_from_final_post_ids"], [2])
            self.assertEqual(summary["pending_not_in_final_post_ids"], [2])
            self.assertEqual(summary["integrity_classification"], "recoverable_pending_flush_gap")
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertFalse(summary["large_run_complete"])

    def test_classifies_complete_final_and_checkpoint_match_as_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            checkpoint_path = root / "checkpoint.jsonl"
            pending_path = root / "pending.json"
            manifest_path = root / "manifest.json"
            recovered_path = root / "recovered.json"
            summary_path = root / "summary.json"

            row = {"post_id": 1, "title": "first"}
            result_path.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
            checkpoint_path.write_text(
                json.dumps({"global_idx": 1, "post_id": 1, "status": "completed", "result": row}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            pending_path.write_text("[]", encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "test",
                        "input_post_count": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "next_save_idx": 2,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=summary_path,
            )

            self.assertEqual(summary["integrity_classification"], "clean_completed_run")
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertTrue(summary["large_run_complete"])


if __name__ == "__main__":
    unittest.main()
