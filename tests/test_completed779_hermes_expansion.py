from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "build_completed779_hermes_expansion.py"
    spec = importlib.util.spec_from_file_location("build_completed779_hermes_expansion", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def source_row(post_id: int, *, image: bool = False) -> dict:
    return {
        "post_id": post_id,
        "title": f"source {post_id}",
        "url": f"https://example.test/{post_id}",
        "image_count": 1 if image else 0,
        "analysis_result": {
            "identity": {
                "is_novel_related": True,
                "is_resolved_work_discussion": False,
                "title_resolution_state": "unresolved_matchable",
                "title_resolution_allowed": False,
                "candidate_ledger_status": "hold_unresolved",
                "novel_identity": {"official_title": None, "heretic_url": None},
            }
        },
    }


def action_row(post_id: int, disagreement: str, *, title: str | None = None) -> dict:
    return {
        "post_id": post_id,
        "title": f"source {post_id}",
        "url": f"https://example.test/{post_id}",
        "resolution_label": "REPROCESS",
        "disagreement_type": disagreement,
        "severity": "high",
        "recommended_action": "re_search",
        "search_evidence_grade": "Strong",
        "independent_official_title": title or f"work {post_id}",
        "independent_url": f"https://official.test/{post_id}",
        "pipeline_official_title": None,
        "pipeline_url": None,
        "korean_reason": f"{disagreement} reason",
        "source_urls": [f"https://official.test/{post_id}"],
    }


def compare_row(post_id: int, status: str, disagreement: str) -> dict:
    return {
        "post_id": post_id,
        "seed_bucket": "precision_wrong_work_control" if status == "review" else "source_url_hygiene",
        "disagreement_type": disagreement,
        "recommended_action": "re_search",
        "expected_independent_title": f"expected {post_id}",
        "expected_independent_url": f"https://official.test/{post_id}",
        "baseline_pipeline_title": f"bad {post_id}",
        "baseline_pipeline_url": None,
        "before_identity": {"official_title": f"bad {post_id}", "heretic_url": None},
        "after_identity": {
            "official_title": None,
            "heretic_url": None,
            "title_resolution_state": "unresolved_matchable",
            "candidate_count": 1,
        },
        "movement_status": status,
        "observed_problem": f"residual {status}",
        "source_queue_observed_problem": f"residual {status}",
    }


class Completed779HermesExpansionTest(unittest.TestCase):
    def test_parse_main_targets_supports_custom_lane(self):
        mod = load_module()

        self.assertIsNone(mod.parse_main_targets([], clear_defaults=False))
        self.assertEqual(
            mod.parse_main_targets(
                ["comment_explicit_title_missed=4", "candidate_preservation_missing=6"],
                clear_defaults=True,
            ),
            {"candidate_preservation_missing": 6, "comment_explicit_title_missed": 4},
        )
        merged = mod.parse_main_targets(["wrong_relevance=1"], clear_defaults=False)
        self.assertEqual(merged["wrong_relevance"], 1)
        self.assertIn("under_resolved", merged)

    def test_builds_main_expansion_and_residual_controls(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_path = root / "action_queue.json"
            source_path = root / "source.json"
            balanced_path = root / "balanced.jsonl"
            source_refresh_compare = root / "source_refresh_compare.json"
            loop4_compare = root / "loop4_compare.json"
            extra_exclude = root / "consumed_loop_compare.json"
            out_dir = root / "out"

            source_rows = [source_row(pid, image=pid in {8}) for pid in range(1, 11)]
            write_json(source_path, source_rows)
            write_jsonl(balanced_path, [{"post_id": 1}])
            write_json(loop4_compare, {"rows": [{"post_id": 7}]})
            write_json(
                extra_exclude,
                {
                    "rows": [
                        {"post_id": 2, "movement_status": "resolved_expected_title"},
                        {"post_id": 9, "movement_status": "url_lint_preserved"},
                    ]
                },
            )
            write_json(
                source_refresh_compare,
                {
                    "rows": [
                        compare_row(8, "review", "wrong_work"),
                        compare_row(9, "url_lint_preserved", "heretic_url_null"),
                    ]
                },
            )
            write_json(
                action_path,
                {
                    str(pid): row
                    for pid, row in [
                        (1, action_row(1, "under_resolved_false_negative", title="consumed")),
                        (2, action_row(2, "under_resolved_false_negative", title="repeat")),
                        (3, action_row(3, "wrong_relevance", title="repeat")),
                        (4, action_row(4, "under_resolved", title="unique-a")),
                        (5, action_row(5, "wrong_relevance", title="unique-b")),
                        (6, action_row(6, "under_resolved_false_negative", title="unique-c")),
                        (10, action_row(10, "under_resolved_false_negative", title="unique-d")),
                    ]
                },
            )

            manifest = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=out_dir,
                prefix="fixture_loop",
                main_targets={
                    "under_resolved_false_negative": 1,
                    "wrong_relevance": 1,
                    "under_resolved": 1,
                    "source_url_or_evidence_hygiene": 1,
                },
                residual_review_controls=1,
                residual_url_controls=1,
                per_work_cap=2,
                extra_exclude_paths=[extra_exclude],
                control_compare_path=source_refresh_compare,
                control_bucket_prefix="fixture_control",
            )

            self.assertEqual(manifest["semantic_quality"], "REVIEW-LOCKED")
            self.assertFalse(manifest["full_scan_approval"])
            self.assertEqual(manifest["selection"]["queue_rows"], 5)
            self.assertEqual(manifest["selection"]["role_counts"], {"control": 1, "main": 4})
            self.assertEqual(manifest["selection"]["duplicate_post_ids"], [])
            self.assertEqual(manifest["selection"]["extra_excluded_id_count"], 2)
            self.assertTrue(manifest["selection"]["exclude_consumed_controls"])
            self.assertEqual(manifest["selection"]["main_consumed_overlap"], [])
            self.assertEqual(manifest["selection"]["control_consumed_overlap"], [])
            self.assertEqual(manifest["selection"]["selected_consumed_overlap"], [])
            self.assertEqual(Path(manifest["source"]["control_compare_path"]), source_refresh_compare)
            self.assertIn("fallback_unseen_high_risk", manifest["selection"]["selection_bucket_counts"])
            self.assertIn("fixture_control_review_residual", manifest["selection"]["selection_bucket_counts"])

            queue = json.loads((out_dir / "fixture_loop_queue.json").read_text(encoding="utf-8"))
            main_ids = {row["post_id"] for row in queue["rows"] if row["queue_role"] == "main"}
            control_ids = {row["post_id"] for row in queue["rows"] if row["queue_role"] == "control"}
            self.assertNotIn(1, main_ids)
            self.assertNotIn(2, main_ids)
            self.assertNotIn(7, main_ids)
            self.assertEqual(control_ids, {8})
            self.assertTrue(all(row["required_test"] for row in queue["rows"]))
            self.assertTrue(all(row["suspected_code_hook"] for row in queue["rows"]))

            seed_rows = [
                json.loads(line)
                for line in (out_dir / "inputs" / "fixture_loop_seed.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(seed_rows), 5)
            self.assertTrue(all(row["full_scan_approval"] is False for row in seed_rows))
            self.assertEqual(manifest["split"]["image_ocr_post_ids"], [8])

            manifest_with_consumed_controls = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=root / "out2",
                prefix="fixture_loop_controls",
                main_targets={
                    "under_resolved_false_negative": 1,
                    "wrong_relevance": 1,
                    "under_resolved": 1,
                    "source_url_or_evidence_hygiene": 1,
                },
                residual_review_controls=1,
                residual_url_controls=1,
                per_work_cap=2,
                extra_exclude_paths=[extra_exclude],
                control_compare_path=source_refresh_compare,
                control_bucket_prefix="fixture_control",
                exclude_consumed_controls=False,
            )
            self.assertFalse(manifest_with_consumed_controls["selection"]["exclude_consumed_controls"])
            self.assertEqual(manifest_with_consumed_controls["selection"]["main_consumed_overlap"], [])
            self.assertEqual(manifest_with_consumed_controls["selection"]["control_consumed_overlap"], [9])
            self.assertEqual(manifest_with_consumed_controls["selection"]["selected_consumed_overlap"], [])
            self.assertEqual(manifest_with_consumed_controls["selection"]["role_counts"], {"control": 2, "main": 4})

    def test_custom_control_bucket_prefix_respects_url_target(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_path = root / "action_queue.json"
            source_path = root / "source.json"
            balanced_path = root / "balanced.jsonl"
            source_refresh_compare = root / "source_refresh_compare.json"
            loop4_compare = root / "loop4_compare.json"
            out_dir = root / "out"

            source_rows = [source_row(pid) for pid in range(1, 8)]
            write_json(source_path, source_rows)
            write_jsonl(balanced_path, [])
            write_json(loop4_compare, {"rows": []})
            write_json(
                action_path,
                {str(pid): action_row(pid, "under_resolved_false_negative") for pid in range(1, 5)},
            )
            write_json(
                source_refresh_compare,
                {
                    "rows": [
                        compare_row(5, "url_lint_preserved", "heretic_url_null"),
                        compare_row(6, "url_lint_preserved", "url_mismatch"),
                        compare_row(7, "url_lint_preserved", "reason_evidence_mismatch"),
                    ]
                },
            )

            manifest = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=out_dir,
                prefix="custom_prefix",
                main_targets={"under_resolved_false_negative": 1},
                residual_review_controls=0,
                residual_url_controls=1,
                control_compare_path=source_refresh_compare,
                control_bucket_prefix="loop10_regression",
            )

            self.assertEqual(
                manifest["selection"]["selection_bucket_counts"],
                {"loop10_regression_url_lint_residual": 1, "under_resolved_false_negative": 1},
            )
            queue = json.loads((out_dir / "custom_prefix_queue.json").read_text(encoding="utf-8"))
            control_rows = [row for row in queue["rows"] if row["queue_role"] == "control"]
            self.assertEqual(len(control_rows), 1)
            self.assertEqual(control_rows[0]["selection_bucket"], "loop10_regression_url_lint_residual")

    def test_explicit_consumed_post_ids_can_be_regression_controls(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_path = root / "action_queue.json"
            source_path = root / "source.json"
            balanced_path = root / "balanced.jsonl"
            source_refresh_compare = root / "source_refresh_compare.json"
            loop4_compare = root / "loop4_compare.json"
            consumed = root / "consumed_queue.json"
            out_dir = root / "out"

            write_json(source_path, [source_row(1), source_row(2)])
            write_jsonl(balanced_path, [])
            write_json(loop4_compare, {"rows": []})
            write_json(source_refresh_compare, {"rows": []})
            write_json(consumed, {"rows": [{"post_id": 2}]})
            write_json(
                action_path,
                {
                    "1": action_row(1, "under_resolved"),
                    "2": action_row(2, "wrong_work"),
                },
            )

            manifest = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=out_dir,
                prefix="explicit_controls",
                main_targets={"under_resolved": 1},
                residual_review_controls=0,
                residual_url_controls=0,
                extra_exclude_paths=[consumed],
                explicit_control_post_ids=[2],
            )

            self.assertEqual(manifest["selection"]["queue_rows"], 2)
            self.assertEqual(manifest["selection"]["role_counts"], {"control": 1, "main": 1})
            self.assertEqual(manifest["selection"]["explicit_control_post_ids"], [2])
            self.assertEqual(manifest["selection"]["control_consumed_overlap"], [2])
            self.assertEqual(manifest["selection"]["selected_consumed_overlap"], [])
            queue = json.loads((out_dir / "explicit_controls_queue.json").read_text(encoding="utf-8"))
            control_rows = [row for row in queue["rows"] if row["queue_role"] == "control"]
            self.assertEqual(len(control_rows), 1)
            self.assertEqual(control_rows[0]["post_id"], 2)
            self.assertEqual(control_rows[0]["selection_bucket"], "explicit_regression_control")
            self.assertEqual(control_rows[0]["movement_status"], "explicit_regression_control")
            self.assertIn("control must not regress", control_rows[0]["required_test"])

    def test_empty_main_targets_do_not_fall_back_to_defaults(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_path = root / "action_queue.json"
            source_path = root / "source.json"
            balanced_path = root / "balanced.jsonl"
            source_refresh_compare = root / "source_refresh_compare.json"
            loop4_compare = root / "loop4_compare.json"
            out_dir = root / "out"

            write_json(source_path, [source_row(1), source_row(2)])
            write_jsonl(balanced_path, [])
            write_json(loop4_compare, {"rows": []})
            write_json(source_refresh_compare, {"rows": []})
            write_json(
                action_path,
                {
                    "1": action_row(1, "under_resolved"),
                    "2": action_row(2, "wrong_work"),
                },
            )

            manifest = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=out_dir,
                prefix="controls_only",
                main_targets={},
                residual_review_controls=0,
                residual_url_controls=0,
                explicit_control_post_ids=[2],
            )

            self.assertEqual(manifest["selection"]["main_targets"], {})
            self.assertEqual(manifest["selection"]["role_counts"], {"control": 1})
            self.assertEqual(manifest["selection"]["queue_rows"], 1)
            queue = json.loads((out_dir / "controls_only_queue.json").read_text(encoding="utf-8"))
            self.assertEqual([row["post_id"] for row in queue["rows"]], [2])

    def test_default_targets_include_candidate_comment_and_multi_buckets(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_path = root / "action_queue.json"
            source_path = root / "source.json"
            balanced_path = root / "balanced.jsonl"
            source_refresh_compare = root / "source_refresh_compare.json"
            loop4_compare = root / "loop4_compare.json"
            out_dir = root / "out"

            source_rows = [source_row(pid) for pid in range(1, 4)]
            write_json(source_path, source_rows)
            write_jsonl(balanced_path, [])
            write_json(loop4_compare, {"rows": []})
            write_json(source_refresh_compare, {"rows": []})
            write_json(
                action_path,
                {
                    "1": action_row(1, "comment_explicit_title_missed"),
                    "2": action_row(2, "candidate_preservation_missing"),
                    "3": action_row(3, "conflicting_or_multi_candidate"),
                },
            )

            manifest = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=out_dir,
                prefix="candidate_comment_defaults",
                residual_review_controls=0,
                residual_url_controls=0,
            )

            self.assertEqual(
                manifest["selection"]["selection_bucket_counts"],
                {
                    "candidate_preservation_missing": 1,
                    "comment_explicit_title_missed": 1,
                    "conflicting_or_multi_candidate": 1,
                },
            )

    def test_balanced_main_rows_require_explicit_allowance(self):
        mod = load_module()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            action_path = root / "action_queue.json"
            source_path = root / "source.json"
            balanced_path = root / "balanced.jsonl"
            source_refresh_compare = root / "source_refresh_compare.json"
            loop4_compare = root / "loop4_compare.json"

            write_json(source_path, [source_row(1)])
            write_jsonl(balanced_path, [{"post_id": 1}])
            write_json(loop4_compare, {"rows": []})
            write_json(source_refresh_compare, {"rows": []})
            write_json(action_path, {"1": action_row(1, "comment_explicit_title_missed")})

            blocked = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=root / "blocked",
                prefix="blocked",
                main_targets={"comment_explicit_title_missed": 1},
                residual_review_controls=0,
                residual_url_controls=0,
            )
            allowed = mod.build_queue(
                action_queue_path=action_path,
                source_path=source_path,
                balanced_seed_path=balanced_path,
                source_refresh_compare_path=source_refresh_compare,
                loop4_compare_path=loop4_compare,
                out_dir=root / "allowed",
                prefix="allowed",
                main_targets={"comment_explicit_title_missed": 1},
                residual_review_controls=0,
                residual_url_controls=0,
                exclude_balanced_main=False,
            )

            self.assertEqual(blocked["selection"]["queue_rows"], 0)
            self.assertTrue(blocked["selection"]["exclude_balanced_main"])
            self.assertEqual(allowed["selection"]["queue_rows"], 1)
            self.assertFalse(allowed["selection"]["exclude_balanced_main"])


if __name__ == "__main__":
    unittest.main()
