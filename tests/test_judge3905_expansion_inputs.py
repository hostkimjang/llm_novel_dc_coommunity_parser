import json
import tempfile
import unittest
from pathlib import Path

from tools.build_judge3905_expansion_inputs import build_high_risk_expansion


class Judge3905ExpansionInputTest(unittest.TestCase):
    def test_builds_non_overlapping_high_risk_expansion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.json"
            source = root / "source.json"
            exclude = root / "exclude.json"
            out_dir = root / "out"
            registry.write_text(
                json.dumps(
                    {
                        "seeds": [
                            {
                                "post_id": 1,
                                "seed_group": "recall",
                                "disagreement_type": "under_resolved_false_negative",
                                "severity": "high",
                                "shadow_label": "hold_unresolved",
                                "source": {"title": "old", "image_count": 0},
                            },
                            {
                                "post_id": 2,
                                "seed_group": "recall",
                                "disagreement_type": "under_resolved_false_negative",
                                "severity": "high",
                                "shadow_label": "candidate_generation_miss",
                                "source": {"title": "recall", "image_count": 1},
                            },
                            {
                                "post_id": 3,
                                "seed_group": "precision",
                                "disagreement_type": "wrong_work",
                                "severity": "high",
                                "shadow_label": "identity_consistency_lint",
                                "source": {"title": "precision", "image_count": 0},
                            },
                            {
                                "post_id": 4,
                                "seed_group": "hygiene",
                                "disagreement_type": "title_noisy_ocr",
                                "severity": "high",
                                "shadow_label": "output_consistency_lint",
                                "source": {"title": "ocr", "image_count": 0},
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            source.write_text(
                json.dumps(
                    [
                        {"post_id": 2, "title": "recall", "content_blocks": [{"type": "image", "url": "https://dcimg.example/2.jpg"}]},
                        {"post_id": 3, "title": "precision", "content_blocks": [{"type": "text", "text": "body"}]},
                        {"post_id": 4, "title": "ocr", "content_blocks": [{"type": "text", "text": "body"}]},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            exclude.write_text(json.dumps({"canary_post_ids": [1]}, ensure_ascii=False), encoding="utf-8")

            manifest = build_high_risk_expansion(
                registry_path=registry,
                source_patterns=[source.as_posix()],
                exclude_paths=[exclude],
                out_dir=out_dir,
                prefix="seed",
                total=3,
                quotas={"recall": 1, "precision": 1, "hygiene": 1},
            )

            self.assertEqual(manifest["selected_count"], 3)
            self.assertEqual(manifest["excluded_post_count"], 1)
            self.assertEqual(manifest["counts"]["by_group"], {"recall": 1, "precision": 1, "hygiene": 1})
            self.assertEqual(manifest["recommended_parallel"], 16)
            self.assertEqual(manifest["expected_effective_parallel"], 3)
            self.assertIn("--parallel 16", manifest["recommended_commands"]["expert_main"])
            self.assertNotIn("--no-dashboard", manifest["recommended_commands"]["expert_main"])
            self.assertEqual(
                manifest["execution_contract"]["dashboard_contract"]["dashboard_policy"],
                "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
            )
            rows = [
                json.loads(line)
                for line in (out_dir / "seed_highrisk_expansion_input.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([row["post_id"] for row in rows], [2, 3, 4])
            self.assertEqual(rows[0]["image_urls"], ["https://dcimg.example/2.jpg"])
            self.assertEqual(rows[0]["_judge_seed"]["expansion_kind"], "high_risk")


if __name__ == "__main__":
    unittest.main()
