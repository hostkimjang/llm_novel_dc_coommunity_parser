import json
import tempfile
import unittest
from pathlib import Path

from tools.build_completed779_issue_index import build_issue_index


class Completed779IssueIndexTest(unittest.TestCase):
    def test_build_issue_index_dedupes_sentinel_and_balances_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "completed_subset.json"
            judge_root = root / "judge"
            verdict_dir = judge_root / "verdicts"
            out_dir = root / "out"
            verdict_dir.mkdir(parents=True)

            source_rows = [
                {"post_id": idx, "title": f"post {idx}", "analysis_result": {"identity": {}}}
                for idx in range(1, 6)
            ]
            result_path.write_text(json.dumps(source_rows, ensure_ascii=False), encoding="utf-8")
            (verdict_dir / "verdict_sentinel_001.json").write_text(
                json.dumps(
                    {
                        "post_id": 1,
                        "resolution_label": "REPROCESS",
                        "disagreement_type": "wrong_work",
                        "severity": "high",
                        "recommended_action": "re_judge",
                        "search_evidence_grade": "Strong",
                        "independent_official_title": "sentinel stale",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (verdict_dir / "verdict_001.json").write_text(
                json.dumps(
                    {
                        "verdicts": [
                            {
                                "post_id": 1,
                                "resolution_label": "REPROCESS",
                                "disagreement_type": "wrong_work",
                                "severity": "high",
                                "recommended_action": "re_judge",
                                "search_evidence_grade": "Strong",
                                "independent_official_title": "canonical batch",
                            },
                            {
                                "post_id": 2,
                                "resolution_label": "HOLD",
                                "disagreement_type": "comment_explicit_title_missed",
                                "severity": "high",
                                "recommended_action": "re_search",
                                "search_evidence_grade": "Strong",
                            },
                            {
                                "post_id": 3,
                                "resolution_label": "REPROCESS",
                                "disagreement_type": "under_resolved",
                                "severity": "med",
                                "recommended_action": "re_search",
                                "search_evidence_grade": "Medium",
                            },
                            {
                                "post_id": 4,
                                "resolution_label": "REPROCESS",
                                "disagreement_type": "heretic_url_null",
                                "severity": "med",
                                "recommended_action": "source_upgrade",
                                "search_evidence_grade": "Medium",
                            },
                            {
                                "post_id": 5,
                                "resolution_label": "ACCEPT",
                                "disagreement_type": "none",
                                "severity": "low",
                                "recommended_action": "no_action",
                                "search_evidence_grade": "Strong",
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = build_issue_index(
                result_path,
                judge_root,
                out_dir,
                expected_total=None,
                expected_non_accept=None,
                seed_targets={
                    "precision_identity_high": 1,
                    "candidate_comment_multi": 1,
                    "recall_relevance_representative": 1,
                    "source_url_hygiene": 1,
                },
            )

            self.assertEqual(summary["coverage"]["source_unique_post_ids"], 5)
            self.assertEqual(summary["coverage"]["verdict_unique_post_ids"], 5)
            self.assertEqual(summary["coverage"]["deduped_duplicates_removed"], 1)
            self.assertEqual(summary["coverage"]["duplicate_post_ids_removed"], [1])
            self.assertEqual(summary["native_web_aggregate"]["non_accept"], 4)
            self.assertEqual(
                summary["seed_packet"]["actual_counts"],
                {
                    "candidate_comment_multi": 1,
                    "precision_identity_high": 1,
                    "recall_relevance_representative": 1,
                    "source_url_hygiene": 1,
                },
            )
            self.assertTrue(summary["seed_packet"]["wrong_work_all_seeded"])


if __name__ == "__main__":
    unittest.main()
