import json
import tempfile
import unittest
from pathlib import Path

from tools.build_goal_next_seed_package import build_package


class GoalNextSeedPackageTest(unittest.TestCase):
    def test_builds_rerun_and_browser_targets_from_audit_issue_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_path = root / "audit.json"
            source_path = root / "source.jsonl"
            out_dir = root / "out"
            audit_path.write_text(
                json.dumps(
                    {
                        "issues": [
                            {
                                "code": "image_evidence_catalog_missing",
                                "severity": "REVIEW-LOCKED",
                                "sample_post_ids": [11718082],
                            },
                            {
                                "code": "blocked_intent_resolved_title",
                                "severity": "REVIEW-LOCKED",
                                "sample_post_ids": [11718080],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            rows = [
                {
                    "post_id": 11718082,
                    "title": "이미지 글",
                    "url": "https://example.test/post/11718082",
                    "content_blocks": [
                        {"type": "image", "image_url": "https://dcimg.example/a.jpg"},
                        {"type": "text", "text": "본문"},
                    ],
                },
                {
                    "comment_id": "c1",
                    "post_id": 11718082,
                    "author": "ㅇㅇ",
                    "content": "댓글",
                },
                {
                    "comment_id": "c1",
                    "post_id": 11718082,
                    "author": "ㅇㅇ",
                    "content": "댓글",
                },
                {
                    "post_id": 11718080,
                    "title": "잡담 글",
                    "url": "https://example.test/post/11718080",
                    "content_blocks": [{"type": "text", "text": "특정 작품이 아닌 한탄"}],
                },
            ]
            source_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )

            manifest = build_package(
                audit_path=audit_path,
                out_dir=out_dir,
                prefix="seed",
                source_globs=[source_path.as_posix()],
                result_paths=[],
                run_id="run1",
            )

            self.assertEqual(manifest["target_post_count"], 2)
            self.assertEqual(manifest["rerun_post_count"], 2)
            self.assertEqual(manifest["browser_visual_required_count"], 1)
            self.assertEqual(manifest["recommended_parallel"], 2)
            self.assertIn("--parallel 2", manifest["recommended_commands"]["rerun"])
            self.assertEqual(manifest["fallback_without_image_url_post_ids"], [])

            rerun_rows = [
                json.loads(line)
                for line in (out_dir / "seed_rerun_input.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rerun_rows), 3)
            image_post = next(row for row in rerun_rows if row.get("post_id") == 11718082)
            self.assertEqual(image_post["_goal_seed_source_quality"], "raw_input_with_image_url")
            self.assertEqual(image_post["content_blocks"][0]["image_url"], "https://dcimg.example/a.jpg")

            summary = (out_dir / "seed_summary_ko.md").read_text(encoding="utf-8")
            self.assertIn("v504 다음 실행 seed 패키지", summary)
            self.assertIn("REVIEW-LOCKED", summary)
            self.assertIn("권장 명령", summary)


if __name__ == "__main__":
    unittest.main()
