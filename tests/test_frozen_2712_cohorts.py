from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.build_frozen_2712_cohorts import (
    DEFAULT_ARBITRATION_DIR,
    DEFAULT_CROSS_REVIEW,
    DEFAULT_LEDGER,
    DEFAULT_RAW_RESULT,
    PROFILE_COUNTS,
    build_cohorts,
)
from tools.compare_frozen_2712_pair import build_transition_report


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOL = REPO_ROOT / "tools/build_frozen_2712_cohorts.py"
COMPARE_TOOL = REPO_ROOT / "tools/compare_frozen_2712_pair.py"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def ledger_row(
    post_id: int,
    verdict: str,
    action: str,
    *,
    published: bool = False,
    recommended: str | None = None,
    ocr: bool = False,
    image_count: int = 0,
    comments_count: int = 0,
) -> dict:
    return {
        "post_id": str(post_id),
        "pipeline": {
            "publish_allowed": published,
            "official_title": recommended if published else None,
        },
        "source_evidence": {
            "image_count": image_count,
            "comments_count": comments_count,
            "explicit_ocr_titles": ["direct"] if ocr else [],
            "title_candidates": [],
        },
        "independent_semantic_verdict": {
            "review_verdict": verdict,
            "dashboard_action": action,
            "recommended_title": recommended,
            "dashboard_title_expected": recommended,
        },
    }


def raw_row(post_id: int) -> dict:
    return {
        "post_id": post_id,
        "title": f"source-{post_id}",
        "content_blocks": [{"type": "text", "text": "body"}],
        "analysis_result": {"identity": {"identity_state": "resolved_title"}},
        "run_meta": {"run_id": "baseline"},
    }


def runtime_row(
    post_id: int,
    *,
    publish: bool,
    title: str | None,
    system_state: str = "clean",
    review: bool | None = None,
    search_status: str = "HEALTHY",
    calls: int | None = 2,
) -> dict:
    identity = {
        "system_state": system_state,
        "identity_state": "resolved_title" if publish else "unresolved_title",
        "promotion_decision": {
            "publish_allowed": publish,
            "official_title": title,
        },
        "search_health": {
            "status": search_status,
            "queries_issued": 3,
            "degraded": 0,
            "unrecovered_degraded": 0,
        },
    }
    if review is not None:
        identity["semantic_review_required"] = review
    return {
        "post_id": post_id,
        "analysis_result": {"identity": identity},
        "run_meta": {
            "decision_cost_trace": {
                "expert_calls": calls,
                "search_calls": 3,
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "wall_ms": 100,
            }
        },
    }


class FrozenCohortBuilderTest(unittest.TestCase):
    def synthetic_fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        ledger = root / "ledger.jsonl"
        raw = root / "raw.json"
        cross = root / "cross.jsonl"
        arbitration_dir = root / "arbitration"
        rows = [
            ledger_row(1, "FP_NONNOVEL", "REMOVE", published=True),
            ledger_row(2, "FN_TITLE_MISSING", "CORRECT", recommended="Recovered", ocr=True, image_count=1),
            ledger_row(3, "FN_TITLE_MISSING", "CORRECT", recommended="Candidate"),
            ledger_row(4, "WRONG_WORK", "CORRECT", recommended="Right"),
            ledger_row(5, "MULTIWORK_HOLD_CORRECT", "HOLD"),
            ledger_row(6, "DASHBOARD_TITLE_MISMATCH", "CORRECT", recommended="Canonical"),
            ledger_row(7, "PASS", "KEEP", published=True, recommended="Kept"),
            ledger_row(8, "NOISE_CORRECT", "NOT_APPLICABLE"),
            ledger_row(9, "CONTEXT_ONLY_CORRECT", "NOT_APPLICABLE", comments_count=1),
            ledger_row(10, "EVIDENCE_CONFLICT", "HOLD"),
        ]
        write_jsonl(ledger, rows)
        write_json(raw, [raw_row(index) for index in range(1, 11)] + [raw_row(99)])
        write_jsonl(
            cross,
            [
                {"post_id": "4", "cross_review_status": "REQUIRES_ARBITRATION"},
                {"post_id": "5", "cross_review_status": "AGREE"},
            ],
        )
        write_jsonl(arbitration_dir / "part.jsonl", [{"post_id": "4", "adjudicated_verdict": "WRONG_WORK"}])
        return ledger, raw, cross, arbitration_dir

    def test_cli_builds_deterministic_cohorts_and_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger, raw, cross, arbitration_dir = self.synthetic_fixture(root)
            output = root / "output"
            command = [
                sys.executable,
                str(BUILD_TOOL),
                "--ledger",
                str(ledger),
                "--raw-result",
                str(raw),
                "--cross-review-ledger",
                str(cross),
                "--arbitration-verdict-dir",
                str(arbitration_dir),
                "--output-dir",
                str(output),
                "--profile",
                "none",
                "--family-cap",
                "3",
                "--cross-family-cap",
                "4",
            ]
            subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
            first_manifest = (output / "manifest.json").read_bytes()
            subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
            self.assertEqual(first_manifest, (output / "manifest.json").read_bytes())

            manifest = json.loads(first_manifest)
            self.assertEqual("GO", manifest["gate"])
            self.assertEqual(2, manifest["cohorts"]["fn_title_missing"]["count"])
            self.assertEqual(1, manifest["cohorts"]["fn_direct_ocr"]["count"])
            self.assertEqual(2, manifest["cohorts"]["safe_no_title"]["count"])
            self.assertEqual(1, manifest["cohorts"]["ultra_safe_no_title"]["count"])
            self.assertEqual(1, manifest["reconciliation"]["raw_extra_to_ledger"])
            self.assertEqual(16, manifest["parallel"]["requested_parallel"])
            self.assertLessEqual(manifest["bundles"]["cross_family"]["count"], 4)
            source = json.loads((output / "cohorts/fp_non_novel.jsonl").read_text())
            self.assertNotIn("analysis_result", source)
            self.assertNotIn("run_meta", source)

    def test_duplicate_and_missing_raw_rows_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger, raw, cross, arbitration_dir = self.synthetic_fixture(root)
            rows = json.loads(raw.read_text())
            write_json(raw, rows + [rows[0]])
            with self.assertRaisesRegex(ValueError, "duplicate post_id"):
                build_cohorts(
                    ledger_path=ledger,
                    raw_result_path=raw,
                    cross_review_path=cross,
                    arbitration_verdict_paths=[arbitration_dir / "part.jsonl"],
                    output_dir=root / "duplicate-output",
                    profile="none",
                )
            write_json(raw, rows[1:])
            with self.assertRaisesRegex(ValueError, "missing ledger post_id"):
                build_cohorts(
                    ledger_path=ledger,
                    raw_result_path=raw,
                    cross_review_path=cross,
                    arbitration_verdict_paths=[arbitration_dir / "part.jsonl"],
                    output_dir=root / "missing-output",
                    profile="none",
                )

    def test_arbitration_coverage_must_be_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger, raw, cross, arbitration_dir = self.synthetic_fixture(root)
            write_jsonl(arbitration_dir / "part.jsonl", [{"post_id": "5"}])
            with self.assertRaisesRegex(ValueError, "arbitration coverage mismatch"):
                build_cohorts(
                    ledger_path=ledger,
                    raw_result_path=raw,
                    cross_review_path=cross,
                    arbitration_verdict_paths=[arbitration_dir / "part.jsonl"],
                    output_dir=root / "output",
                    profile="none",
                )

    @unittest.skipUnless(
        DEFAULT_LEDGER.exists()
        and DEFAULT_RAW_RESULT.exists()
        and DEFAULT_CROSS_REVIEW.exists()
        and DEFAULT_ARBITRATION_DIR.exists(),
        "current frozen 2712 artifacts are not available",
    )
    def test_current_frozen_data_matches_registered_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = build_cohorts(
                ledger_path=DEFAULT_LEDGER,
                raw_result_path=DEFAULT_RAW_RESULT,
                cross_review_path=DEFAULT_CROSS_REVIEW,
                arbitration_verdict_paths=sorted(DEFAULT_ARBITRATION_DIR.glob("*.jsonl")),
                output_dir=Path(directory) / "current",
                profile="frozen2712",
            )
        self.assertEqual(
            PROFILE_COUNTS,
            {name: value["count"] for name, value in manifest["cohorts"].items()},
        )
        self.assertEqual("EXACT", manifest["reconciliation"]["arbitration"]["coverage"])


class FrozenPairComparatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = [
            ledger_row(1, "FP_NONNOVEL", "REMOVE"),
            ledger_row(2, "FN_TITLE_MISSING", "CORRECT", recommended="Recovered", ocr=True),
            ledger_row(3, "WRONG_WORK", "HOLD"),
            ledger_row(4, "PASS", "KEEP", recommended="Keep"),
        ]
        self.before = [
            runtime_row(1, publish=True, title="False", review=False),
            runtime_row(2, publish=False, title=None, review=False),
            runtime_row(3, publish=True, title="Wrong", review=False),
            runtime_row(4, publish=True, title="Keep", review=False),
        ]
        self.after = [
            runtime_row(1, publish=False, title=None, review=True),
            runtime_row(2, publish=True, title="Recovered", review=True),
            runtime_row(3, publish=False, title=None, review=True),
            runtime_row(4, publish=True, title="Keep", review=False),
        ]

    def test_transition_metrics_cover_semantics_router_search_and_cost(self) -> None:
        transitions, report = build_transition_report(self.ledger, self.before, self.after)
        self.assertEqual(4, len(transitions))
        metrics = report["metrics"]
        self.assertEqual({"before": 2, "after": 0}, metrics["unsafe_publish"])
        self.assertEqual(1, metrics["correct_title_recovery"]["after"])
        self.assertEqual(1, metrics["false_positive"]["before"])
        self.assertEqual(0, metrics["wrong_work_error"]["after"])
        self.assertEqual(1, metrics["hold_integrity"]["after"])
        self.assertEqual(1, metrics["pass_retention"]["after"])
        self.assertEqual(0, metrics["normal_to_abnormal_regression"])
        self.assertEqual(0, metrics["runtime_normal_to_abnormal_regression"])
        self.assertEqual(4, metrics["adjudication_compliant"]["after"]["compliant"])
        self.assertEqual(0, metrics["adjudication_compliant"]["after"]["noncompliant"])
        self.assertEqual(0, metrics["adjudication_compliant"]["after"]["not_estimable"])
        self.assertEqual(3, metrics["review_router"]["after"]["routed"])
        self.assertEqual(3, metrics["review_router"]["after"]["high_risk_recall"]["numerator"])
        self.assertEqual(3, metrics["review_router"]["after"]["high_risk_recall"]["denominator"])
        self.assertEqual(0, metrics["review_router"]["after"]["normal_control_false_review_rate"]["numerator"])
        self.assertEqual(1, metrics["review_router"]["after"]["normal_control_false_review_rate"]["denominator"])
        self.assertEqual({"HEALTHY": 4}, metrics["search_health"]["after_status_counts"])
        self.assertEqual(48, metrics["calls_tokens_wall"]["after"]["total_tokens"]["value"])
        self.assertEqual(400, metrics["calls_tokens_wall"]["after"]["wall_ms"]["value"])

    def test_semantic_regression_is_distinct_from_runtime_error(self) -> None:
        ledger = [ledger_row(11, "PASS", "KEEP", recommended="Expected")]
        before = [runtime_row(11, publish=True, title="Expected", system_state="clean")]
        after = [runtime_row(11, publish=True, title="Wrong", system_state="clean")]
        transitions, report = build_transition_report(ledger, before, after)
        self.assertTrue(transitions[0]["transition"]["normal_to_abnormal_regression"])
        self.assertFalse(transitions[0]["transition"]["runtime_normal_to_abnormal_regression"])
        self.assertEqual(1, report["metrics"]["normal_to_abnormal_regression"])
        self.assertEqual(0, report["metrics"]["runtime_normal_to_abnormal_regression"])

        runtime_error_after = [runtime_row(11, publish=True, title="Expected", system_state="error")]
        error_transitions, error_report = build_transition_report(ledger, before, runtime_error_after)
        self.assertFalse(error_transitions[0]["transition"]["normal_to_abnormal_regression"])
        self.assertTrue(error_transitions[0]["transition"]["runtime_normal_to_abnormal_regression"])
        self.assertEqual(0, error_report["metrics"]["normal_to_abnormal_regression"])
        self.assertEqual(1, error_report["metrics"]["runtime_normal_to_abnormal_regression"])

    def test_unknown_action_is_not_silently_compliant_or_false(self) -> None:
        ledger = [ledger_row(12, "UNSPECIFIED", "UNSUPPORTED")]
        before = [runtime_row(12, publish=False, title=None)]
        after = [runtime_row(12, publish=True, title="Anything")]
        transitions, report = build_transition_report(ledger, before, after)
        self.assertIsNone(transitions[0]["before"]["quality"]["adjudication_compliant"])
        self.assertEqual("NOT_ESTIMABLE", transitions[0]["after"]["quality"]["adjudication_compliance_status"])
        self.assertFalse(transitions[0]["transition"]["normal_to_abnormal_regression"])
        observability = report["metrics"]["normal_to_abnormal_regression_observability"]
        self.assertEqual(1, observability["unknown_rows"])
        self.assertEqual("NOT_ESTIMABLE", observability["status"])

    def test_pairing_is_post_id_exact_and_cli_writes_table(self) -> None:
        with self.assertRaisesRegex(ValueError, "post_id set mismatch"):
            build_transition_report(self.ledger, self.before, self.after[:-1])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger_path = root / "ledger.jsonl"
            before_path = root / "before.json"
            after_path = root / "after.json"
            table_path = root / "transitions.jsonl"
            summary_path = root / "summary.json"
            write_jsonl(ledger_path, self.ledger)
            write_json(before_path, self.before)
            write_json(after_path, self.after)
            subprocess.run(
                [
                    sys.executable,
                    str(COMPARE_TOOL),
                    "--ledger",
                    str(ledger_path),
                    "--before",
                    str(before_path),
                    "--after",
                    str(after_path),
                    "--transition-jsonl",
                    str(table_path),
                    "--summary-json",
                    str(summary_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(4, len(table_path.read_text().splitlines()))
            self.assertEqual("EXACT", json.loads(summary_path.read_text())["pairing"]["status"])


if __name__ == "__main__":
    unittest.main()
