import json
import tempfile
import unittest
from pathlib import Path

from tools.build_judge_seed_registry import build_registry, compare_canary


class JudgeSeedRegistryTest(unittest.TestCase):
    def test_builds_seed_registry_shadow_and_canary_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviews = root / "reviews.jsonl"
            source = root / "source.json"
            out_dir = root / "out"
            reviews.write_text(
                "\n".join(
                    json.dumps(row, ensure_ascii=False)
                    for row in [
                        {
                            "post_id": 1,
                            "agree": False,
                            "disagreement_type": "under_resolved_false_negative",
                            "likely_correct": "claude",
                            "severity": "high",
                            "note": "후보를 놓침",
                        },
                        {
                            "post_id": 2,
                            "agree": False,
                            "disagreement_type": "wrong_work",
                            "likely_correct": "claude",
                            "severity": "high",
                            "note": "다른 작품으로 확정",
                        },
                        {
                            "post_id": 3,
                            "agree": False,
                            "disagreement_type": "wrong_discussion_type",
                            "likely_correct": "claude",
                            "severity": "low",
                            "note": "taxonomy drift",
                        },
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            source.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 1,
                            "title": "후보 없음",
                            "content": ["본문"],
                            "analysis_result": {
                                "identity": {
                                    "is_novel_related": False,
                                    "title_resolution_state": "none",
                                    "work_resolution": "none",
                                    "novel_identity": None,
                                }
                            },
                            "run_meta": {"worker_id": 1},
                        },
                        {
                            "post_id": 2,
                            "title": "과확정",
                            "content": ["본문"],
                            "analysis_result": {
                                "identity": {
                                    "is_resolved_work_discussion": False,
                                    "title_resolution_allowed": False,
                                    "title_resolution_state": "context_only",
                                    "work_resolution": "none",
                                    "novel_identity": {"official_title": "잘못된 작품", "confidence": "High"},
                                }
                            },
                        },
                        {
                            "post_id": 3,
                            "title": "분류 오류",
                            "content": ["본문"],
                            "analysis_result": {
                                "identity": {
                                    "discussion_type": "trope_discussion",
                                    "title_resolution_state": "adjacent",
                                    "work_resolution": "none",
                                    "novel_identity": None,
                                }
                            },
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = build_registry(
                reviews_path=reviews,
                source_patterns=[source.as_posix()],
                out_dir=out_dir,
                prefix="seed",
                canary_per_group=2,
            )

            self.assertEqual(manifest["seed_count"], 3)
            self.assertEqual(manifest["counts"]["by_group"], {"recall": 1, "precision": 1, "hygiene": 1})
            self.assertEqual(manifest["canary_post_count"], 3)
            self.assertEqual(manifest["recommended_parallel"], 16)
            self.assertEqual(manifest["expected_effective_parallel"], 3)
            self.assertIn("--parallel 16", manifest["recommended_commands"]["expert_main_canary"])
            self.assertNotIn("--no-dashboard", manifest["recommended_commands"]["expert_main_canary"])
            self.assertEqual(
                manifest["execution_contract"]["dashboard_contract"]["dashboard_policy"],
                "WEB_DASHBOARD_REQUIRED_FOR_TEST_RUNS",
            )

            registry = json.loads((out_dir / "seed_seed_registry.json").read_text(encoding="utf-8"))
            labels = {row["post_id"]: row["shadow_label"] for row in registry["seeds"]}
            self.assertEqual(labels[1], "candidate_generation_miss")
            self.assertEqual(labels[2], "official_title_lint")
            self.assertEqual(labels[3], "output_consistency_lint")

            canary_rows = [
                json.loads(line)
                for line in (out_dir / "seed_expert_main_canary_input.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(canary_rows), 3)
            self.assertNotIn("analysis_result", canary_rows[0])
            self.assertIn("_judge_seed", canary_rows[0])

    def test_compare_canary_result_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.json"
            result = root / "result.json"
            manifest = root / "manifest.json"
            out_json = root / "compare.json"
            out_md = root / "compare.md"
            registry.write_text(
                json.dumps(
                    {
                        "seeds": [
                            {
                                "post_id": 1,
                                "seed_group": "recall",
                                "disagreement_type": "under_resolved_false_negative",
                                "severity": "high",
                                "shadow_label": "candidate_generation_miss",
                                "likely_correct": "claude",
                                "candidate_ledger": {"pipeline_official_title": None, "candidate_count": 0},
                                "judge": {"note": "놓침"},
                            },
                            {
                                "post_id": 2,
                                "seed_group": "precision",
                                "disagreement_type": "wrong_work",
                                "severity": "high",
                                "shadow_label": "identity_consistency_lint",
                                "likely_correct": "claude",
                                "candidate_ledger": {"pipeline_official_title": "오답", "candidate_count": 0},
                                "judge": {"note": "scope 밖 seed"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            manifest.write_text(json.dumps({"canary_post_ids": [1]}, ensure_ascii=False), encoding="utf-8")
            result.write_text(
                json.dumps(
                    [
                        {
                            "post_id": 1,
                            "analysis_result": {
                                "identity": {
                                    "title_resolution_state": "unresolved_matchable",
                                    "work_resolution": "unresolved",
                                    "title_candidates": [{"title": "후보작"}],
                                    "novel_identity": None,
                                }
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = compare_canary(
                registry_path=registry,
                canary_result_path=result,
                output_json=out_json,
                output_md=out_md,
                manifest_path=manifest,
            )

            self.assertEqual(summary["compared_post_count"], 1)
            self.assertEqual(summary["registry_seed_count"], 2)
            self.assertEqual(summary["compare_scope_seed_count"], 1)
            self.assertEqual(summary["missing_result_post_ids"], [])
            self.assertEqual(summary["gate"]["run_integrity"], "GO")
            self.assertEqual(summary["rows"][0]["shadow_label_after"], "promotion_blocked")
            self.assertTrue(out_json.exists())
            self.assertTrue(out_md.exists())


if __name__ == "__main__":
    unittest.main()
