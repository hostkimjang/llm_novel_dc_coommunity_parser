import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_regression_safe_golden import (
    expected_evidence_preserved_unresolved,
    expected_hypothesis_preserved_unresolved,
    expected_hypothesis_resolved_by_direct_image,
    positive_image_boundary_preserved_unresolved,
)
from tools.bootstrap_regression_safe_grounding import bootstrap, compare_collateral
from tools.compare_projection_collateral import build_compare, write_markdown


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def result_row(post_id: int, title: str, official_title=None, url=None) -> dict:
    identity = {
        "novel_identity": {
            "official_title": official_title,
            "heretic_url": url,
        },
        "title_resolution_state": "resolved" if official_title else "unresolved_matchable",
        "title_resolution_allowed": bool(official_title),
        "candidate_ledger_status": "safe_resolved" if official_title else "hold_unresolved",
    }
    return {
        "post_id": post_id,
        "gallery_id": "genrenovel",
        "title": title,
        "content": [f"body {post_id}"],
        "analysis_result": {"identity": identity},
        "run_meta": {"worker": 1},
    }


class RegressionSafeGroundingBootstrapTest(unittest.TestCase):
    def test_bootstrap_freezes_panel_and_clean_golden_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / "out" / "expert_result_20260626_000008_928006.json"
            rows = [
                result_row(1, "로파민 완결", "wrong before"),
                result_row(2, "짜장면 잡담", "짜장면"),
                result_row(3, "accepted resolved", "정상 작품"),
                result_row(4, "accepted unresolved"),
                result_row(11694064, "sentinel", None),
            ]
            write_json(result, rows)
            write_json(
                result.with_name(result.stem + "_manifest.json"),
                {"completed_count": 5, "flushed_count": 5, "pending_count": 0, "large_run_complete": False},
            )
            phase1 = root / "phase1"
            write_json(
                phase1 / "phase2_initial_queue.json",
                {"rows": [{"post_id": 1, "fix_axis": "wrong_work_disambiguation", "severity": "high"}]},
            )
            write_json(
                phase1 / "_verdicts_final.json",
                {
                    "verdicts": [
                        {"post_id": 3, "resolution_label": "ACCEPT", "severity": "low"},
                        {"post_id": 4, "resolution_label": "ACCEPT", "severity": "low"},
                    ]
                },
            )
            survey = root / "survey.json"
            write_json(
                survey,
                {
                    "errors": [
                        {
                            "post_id": 1,
                            "failure_class": "wrong_work_among_aliases",
                            "disagreement_type": "wrong_work",
                            "severity": "high",
                            "fix_axis": "wrong_work_disambiguation",
                            "correct_hypothesis": "로판에 도파민을 풀었다",
                        },
                        {
                            "post_id": 2,
                            "failure_class": "over_resolved_nonwork",
                            "disagreement_type": "over_resolved",
                            "severity": "high",
                            "fix_axis": "resolution_promotion_gate",
                            "correct_hypothesis": "",
                        },
                    ]
                },
            )

            summary = bootstrap(
                result_path=result,
                phase1_root=phase1,
                survey_errors_path=survey,
                out_dir=root / "fix0",
                accept_sample_size=2,
                golden_per_bucket=2,
            )

            self.assertEqual(summary["panel"]["survey_errors_in_panel"], 2)
            self.assertEqual(summary["panel"]["phase2_queue_in_panel"], 1)
            self.assertEqual(summary["collateral_selfcheck"]["collateral_regression_count"], 0)
            golden_rows = [
                json.loads(line)
                for line in (root / "fix0" / "golden" / "golden_set.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(golden_rows), 2)
            self.assertTrue(all("analysis_result" not in row for row in golden_rows))
            self.assertTrue(all("_judge_seed" not in row for row in golden_rows))
            self.assertTrue(all("_golden_role" in row for row in golden_rows))
            panel_inputs = (root / "fix0" / "panel" / "regression_panel_input.jsonl").read_text(encoding="utf-8")
            self.assertIn("_judge_seed", panel_inputs)
            self.assertIn("11694064", panel_inputs)

    def test_collateral_counts_regressions_and_exempts_expected_recall(self):
        before = [
            result_row(1, "resolved changed", "A"),
            result_row(2, "recall improved", None),
            result_row(3, "resolved dropped", "C"),
        ]
        after = [
            result_row(1, "resolved changed", "B"),
            result_row(2, "recall improved", "주서연(정답작)"),
            result_row(3, "resolved dropped", None),
        ]
        report = compare_collateral(
            before,
            after,
            expected_rows=[
                {"post_id": 1, "expected_title_or_hypothesis": "B"},
                {"post_id": 2, "expected_title_or_hypothesis": "정답작"},
            ],
        )

        self.assertEqual(report["shared_post_count"], 3)
        self.assertEqual(report["changed_post_count"], 3)
        self.assertEqual(report["collateral_regression_count"], 1)
        changed = [row for row in report["rows"] if row["post_id"] == 1][0]
        self.assertTrue(changed["exempted_by_expected_answer"])
        self.assertFalse(changed["is_regression"])
        exempted = [row for row in report["rows"] if row["post_id"] == 2][0]
        self.assertTrue(exempted["exempted_by_expected_answer"])
        self.assertFalse(exempted["is_regression"])

    def test_projection_compare_without_runtime_manifest_keeps_missing_runtime_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            after = root / "after.json"
            manifest = root / "golden_manifest.json"
            write_json(baseline, [result_row(1, "same", "A"), result_row(2, "hold")])
            write_json(after, [result_row(1, "same", "A"), result_row(2, "hold")])
            write_json(manifest, {"rows": []})

            report = build_compare(
                baseline_path=baseline,
                after_path=after,
                golden_manifest=manifest,
                compare_id="unit_projection",
                expected_shared_posts=2,
            )

            self.assertEqual(report["report_type"], "full375_projection_collateral_compare")
            self.assertFalse(report["runtime_complete"])
            self.assertIn("collateral_runtime_counts_missing", report["blockers"])
            self.assertIsNone(report["runtime_completed_count"])

    def test_projection_compare_markdown_uses_generic_projection_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            after = root / "after.json"
            manifest = root / "golden_manifest.json"
            output_md = root / "compare.md"
            write_json(baseline, [result_row(1, "same", "A")])
            write_json(after, [result_row(1, "same", "A")])
            write_json(manifest, {"rows": []})

            report = build_compare(
                baseline_path=baseline,
                after_path=after,
                golden_manifest=manifest,
                compare_id="unit_projection",
                expected_shared_posts=1,
            )
            write_markdown(output_md, report)

            text = output_md.read_text(encoding="utf-8")
            self.assertIn("projection 결과를 baseline full375와 비교한 정적 collateral diff", text)
            self.assertNotIn("Loop580 projection", text)

    def test_projection_compare_runtime_manifest_marks_full_replay_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            after = root / "after.json"
            manifest = root / "golden_manifest.json"
            runtime_manifest = root / "after_manifest.json"
            write_json(baseline, [result_row(1, "same", "A"), result_row(2, "hold")])
            write_json(after, [result_row(1, "same", "A"), result_row(2, "hold")])
            write_json(manifest, {"rows": []})
            write_json(runtime_manifest, {"completed_count": 2, "pending_count": 0, "failed_count": 0})

            report = build_compare(
                baseline_path=baseline,
                after_path=after,
                golden_manifest=manifest,
                compare_id="unit_runtime",
                expected_shared_posts=2,
                runtime_manifest=runtime_manifest,
            )

            self.assertEqual(report["report_type"], "full375_runtime_collateral_compare")
            self.assertTrue(report["runtime_complete"])
            self.assertEqual(report["runtime_collateral_gate"], "GO")
            self.assertEqual(report["runtime_completed_count"], 2)
            self.assertEqual(report["blockers"], [])

    def test_bootstrap_includes_explicit_extra_golden_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / "out" / "expert_result_20260626_000008_928006.json"
            rows = [
                result_row(1, "로파민 완결", "wrong before"),
                result_row(2, "짜장면 잡담", "짜장면"),
                result_row(11660237, "테라포밍 볼만함?", "테라포밍", "https://novelpia.com/novel/61947"),
            ]
            write_json(result, rows)
            write_json(
                result.with_name(result.stem + "_manifest.json"),
                {"completed_count": 3, "flushed_count": 3, "pending_count": 0, "large_run_complete": False},
            )
            phase1 = root / "phase1"
            write_json(phase1 / "phase2_initial_queue.json", {"rows": []})
            write_json(phase1 / "_verdicts_final.json", {"verdicts": []})
            survey = root / "survey.json"
            write_json(
                survey,
                {
                    "errors": [
                        {
                            "post_id": 1,
                            "failure_class": "wrong_work_among_aliases",
                            "disagreement_type": "wrong_work",
                            "severity": "high",
                            "fix_axis": "wrong_work_disambiguation",
                            "correct_hypothesis": "로판에 도파민을 풀었다",
                        },
                        {
                            "post_id": 2,
                            "failure_class": "over_resolved_nonwork",
                            "disagreement_type": "over_resolved",
                            "severity": "high",
                            "fix_axis": "resolution_promotion_gate",
                            "correct_hypothesis": "",
                        },
                    ]
                },
            )
            extra = root / "extra_golden.json"
            write_json(
                extra,
                {
                    "rows": [
                        {
                            "post_id": 11660237,
                            "golden_role": "safe_loss_blind_judge_expected_work",
                            "failure_class": "safe_loss_flip_probe",
                            "disagreement_type": "nondeterminism",
                            "severity": "high",
                            "expected_title_or_hypothesis": "테라포밍",
                            "expected_no_public_title": False,
                            "expected_url": "https://novelpia.com/novel/61947",
                            "expected_status": "safe_resolved",
                        }
                    ]
                },
            )

            summary = bootstrap(
                result_path=result,
                phase1_root=phase1,
                survey_errors_path=survey,
                out_dir=root / "fix0",
                accept_sample_size=0,
                golden_per_bucket=1,
                extra_golden_rows_path=extra,
            )

            self.assertEqual(summary["golden"]["golden_rows"], 3)
            self.assertEqual(summary["golden"]["extra_golden_rows_included"], 1)
            manifest = json.loads(
                (root / "fix0" / "golden" / "golden_manifest.json").read_text(encoding="utf-8")
            )
            extra_rows = [row for row in manifest["rows"] if row["post_id"] == 11660237]
            self.assertEqual(len(extra_rows), 1)
            self.assertEqual(extra_rows[0]["golden_role"], "safe_loss_blind_judge_expected_work")
            self.assertEqual(extra_rows[0]["expected_status"], "safe_resolved")
            golden_inputs = [
                json.loads(line)
                for line in (root / "fix0" / "golden" / "golden_set.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(any(row.get("post_id") == 11660237 for row in golden_inputs))
            self.assertTrue(all("_judge_seed" not in row for row in golden_inputs))

    def test_golden_audit_accepts_direct_image_resolution_for_hypothesis_label(self):
        identity = {
            "consistency_flags": ["direct_image_explicit_title_rescued"],
        }

        self.assertTrue(
            expected_hypothesis_resolved_by_direct_image(
                "교황님(아파하세요) 계열 표지 작품(미상)",
                "교황님 아 하세요 마왕 들어 가요",
                identity,
            )
        )
        self.assertFalse(
            expected_hypothesis_resolved_by_direct_image(
                "교황님(아파하세요) 계열 표지 작품(미상)",
                "무한을 이해한 나는 외신의 사제가 되었습니다",
                identity,
            )
        )

    def test_golden_audit_accepts_preserved_expected_evidence_hold(self):
        identity = {
            "is_relevant": True,
            "title_resolution_state": "unresolved_matchable",
            "search_evidence_catalog": [
                {"title": "어떤 마술의 금서목록 - 나무위키", "snippet": "카미조 토우마"}
            ],
        }

        self.assertTrue(
            expected_evidence_preserved_unresolved(
                "어떤 마술의 금서목록 / 어떤 과학의 초전자포",
                identity,
            )
        )

    def test_golden_audit_accepts_candidate_ledger_hold_for_novel_related_row(self):
        identity = {
            "is_relevant": False,
            "is_novel_related": True,
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "candidate_ledger": {
                "title_candidates": [
                    "전 버튜버가 하고 싶은데요",
                    "주서연",
                ],
            },
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "전 버튜버가 하고 싶은데요",
                    "evidence_type": "cover_title",
                }
            ],
        }

        self.assertTrue(
            expected_evidence_preserved_unresolved(
                "전 버튜버가 하고 싶은데요",
                identity,
            )
        )

    def test_golden_audit_accepts_preserved_hypothesis_hold(self):
        identity = {
            "is_relevant": True,
            "title_resolution_state": "ocr_explicit_title_unresolved",
            "consistency_flags": [
                "direct_image_explicit_title_rescued",
                "local_candidate_hold_preserved",
            ],
            "image_evidence_catalog": [
                {
                    "explicit_work_title": "교황님 아 하세요 마왕 들어가요",
                    "evidence_type": "cover_title",
                }
            ],
            "candidate_ledger": {
                "title_candidates": [
                    "교황님 아 하세요 마왕 들어가요",
                ],
            },
        }

        self.assertTrue(
            expected_hypothesis_preserved_unresolved(
                "교황님(아파하세요) 계열 표지 작품(미상)",
                identity,
            )
        )

    def test_golden_audit_accepts_image_boundary_hold_only_when_unresolved(self):
        identity = {
            "is_relevant": True,
            "title_resolution_state": "unresolved_matchable",
            "consistency_flags": ["vlm_ocr_title_conflict_with_final_title"],
        }
        resolved_identity = dict(identity)
        resolved_identity["title_resolution_state"] = "resolved"

        self.assertTrue(positive_image_boundary_preserved_unresolved(identity))
        self.assertFalse(positive_image_boundary_preserved_unresolved(resolved_identity))


if __name__ == "__main__":
    unittest.main()
