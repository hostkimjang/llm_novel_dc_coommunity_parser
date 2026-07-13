import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.llm_batch.calibration_actual_readback import (
    PROBABILITY_SCALE,
    build_readback_manifest,
    canonical_bytes,
    cluster_bootstrap,
    expected_universe_readback,
    prediction_payload_readback,
    producer_coverage_receipt,
    snapshot_artifact,
    snapshot_json_object,
    validate_actual_readback_artifacts,
    validate_artifact_snapshots,
)


def h(ch):
    return ch * 64


def expected(n=2):
    return [{"example_id": f"e{i}", "post_id": f"p{i}"} for i in range(n)]


def producer(n=2, status="COMPLETE"):
    return [{**r, "generation_status": status, "candidate_set_fingerprint": h("a"), "generation_proof_fingerprint": h("b"), "source_digest_sha256": h("c")} for r in expected(n)]


def prediction(n=2):
    return [{**r, "probabilities": {"work": PROBABILITY_SCALE}, "shadow_fingerprint": h("d"), "score_vector_sha256": h("e"), "candidate_set_fingerprint": h("a"), "generation_proof_fingerprint": h("b"), "source_digest_sha256": h("c")} for r in expected(n)]


def write_jsonl(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def actual_parts(root, *, expected_rows=None, producer_rows=None, prediction_rows=None, baseline_rows=None, extra_refs=None):
    expected_rows = expected() if expected_rows is None else expected_rows
    producer_rows = producer() if producer_rows is None else producer_rows
    prediction_rows = prediction() if prediction_rows is None else prediction_rows
    baseline_rows = prediction() if baseline_rows is None else baseline_rows
    files = {
        "expected_universe": ("expected.jsonl", expected_rows),
        "producer": ("producer.jsonl", producer_rows),
        "prediction": ("prediction.jsonl", prediction_rows),
        "baseline_prediction": ("baseline.jsonl", baseline_rows),
    }
    refs = {}
    for name, (relative_path, rows) in files.items():
        write_jsonl(root / relative_path, rows)
        refs[name] = snapshot_artifact(root, name, relative_path, jsonl=True)
    refs.update(extra_refs or {})
    universe = expected_universe_readback(expected_rows)
    coverage = producer_coverage_receipt(expected_rows, producer_rows)
    after = prediction_payload_readback(expected_rows, prediction_rows)
    baseline = prediction_payload_readback(expected_rows, baseline_rows)
    manifest = build_readback_manifest(
        run_spec_sha256=h("f"),
        artifacts=refs,
        expected_universe=universe,
        producer_coverage=coverage,
        prediction=after,
        baseline_prediction=baseline,
        source_digest_sha256=h("c"),
        metric_protocol_sha256=h("f"),
        bootstrap_seed=7,
        bootstrap_replicates=100,
    )
    return refs, universe, coverage, after, baseline, manifest


class CalibrationActualReadbackTests(unittest.TestCase):
    def test_snapshot_and_manifest_are_canonical_and_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.json").write_bytes(canonical_bytes({"z": 1, "a": 2}))
            ref = snapshot_artifact(root, "a", "a.json")
            self.assertIsNone(ref.row_count)
            _, _, _, _, _, manifest = actual_parts(root, extra_refs={"a": ref})
            self.assertEqual(64, manifest["manifest_sha256"].__len__())
            validate_artifact_snapshots(root, manifest)
            validate_actual_readback_artifacts(root, manifest)
            (root / "a.json").write_text("[1]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
                validate_artifact_snapshots(root, manifest)
            with self.assertRaises(ValueError):
                snapshot_artifact(root, "x", "../outside.json")

    def test_producer_coverage_fail_closed(self):
        receipt = producer_coverage_receipt(expected(), producer())
        self.assertEqual(2, receipt["complete_count"])
        with self.assertRaises(ValueError):
            producer_coverage_receipt(expected(), producer(status="UNKNOWN"))
        with self.assertRaises(ValueError):
            producer_coverage_receipt(expected(), producer()[:1])

    def test_prediction_mass_and_binding(self):
        self.assertEqual(2, prediction_payload_readback(expected(), prediction())["row_count"])
        bad = prediction(); bad[0]["probabilities"] = {"work": PROBABILITY_SCALE - 1}
        with self.assertRaises(ValueError):
            prediction_payload_readback(expected(), bad)

    def test_cluster_bootstrap_is_deterministic_and_paired(self):
        rows = [
            {"example_id": "e1", "group": "g1", "correct": True, "abstain": False, "brier": .1, "log_loss": .2, "confidence": .9, "risk_score": .1},
            {"example_id": "e2", "group": "g2", "correct": False, "abstain": False, "brier": .8, "log_loss": .9, "confidence": .8, "risk_score": .2},
            {"example_id": "e3", "group": "g3", "correct": True, "abstain": False, "brier": .2, "log_loss": .3, "confidence": .7, "risk_score": .3},
        ]
        before = [dict(row, correct=True) for row in rows]
        one = cluster_bootstrap(rows, seed=7, replicates=100, baseline_rows=before)
        two = cluster_bootstrap(rows, seed=7, replicates=100, baseline_rows=before)
        self.assertEqual(one, two)
        self.assertTrue(one["estimable"])
        self.assertIn("paired_deltas", one)
        self.assertEqual(one["point_estimate"]["top_label_accuracy"], one["intervals"]["top_label_accuracy"]["value"])
        self.assertIn("bootstrap_mean", one["intervals"]["top_label_accuracy"])
        self.assertEqual(
            one["paired_point_estimate"]["top_label_accuracy"],
            one["paired_deltas"]["top_label_accuracy"]["value"],
        )
        self.assertFalse(cluster_bootstrap(rows[:1], seed=1, replicates=100)["estimable"])

    def test_cluster_bootstrap_binds_top_label_accuracy_denominator(self):
        rows = [
            {"example_id": "e1", "group": "g1", "correct": True, "abstain": False, "brier": .1, "log_loss": .2, "confidence": .9, "risk_score": .1},
            {"example_id": "e2", "group": "g2", "correct": False, "abstain": True, "brier": .8, "log_loss": .9, "confidence": .8, "risk_score": .2},
        ]
        all_rows = cluster_bootstrap(rows, seed=7, replicates=100)
        covered_rows = cluster_bootstrap(
            rows,
            seed=7,
            replicates=100,
            top_label_accuracy_denominator="NON_ABSTAIN_ROWS",
        )
        self.assertEqual("ALL_FROZEN_ROWS", all_rows["top_label_accuracy_denominator"])
        self.assertEqual("NON_ABSTAIN_ROWS", covered_rows["top_label_accuracy_denominator"])
        self.assertEqual(0.5, all_rows["point_estimate"]["top_label_accuracy"])
        self.assertEqual(1.0, covered_rows["point_estimate"]["top_label_accuracy"])
        with self.assertRaisesRegex(ValueError, "top_label_accuracy_denominator"):
            cluster_bootstrap(rows, seed=7, replicates=100, top_label_accuracy_denominator="AUTO")

    def test_duplicate_and_baseline_mismatch_rejected(self):
        dup = producer(); dup[1]["example_id"] = dup[0]["example_id"]
        with self.assertRaises(ValueError):
            producer_coverage_receipt(expected(), dup)
        rows = [{"example_id": "e1", "group": "g1", "correct": True, "abstain": False, "brier": .1, "log_loss": .2, "confidence": .9, "risk_score": .1}, {"example_id": "e2", "group": "g2", "correct": True, "abstain": False, "brier": .1, "log_loss": .2, "confidence": .9, "risk_score": .1}]
        self.assertEqual("BASELINE_ROW_MISMATCH", cluster_bootstrap(rows, seed=1, replicates=100, baseline_rows=rows[:1])["reason"])

    def test_raw_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "duplicate.jsonl").write_text(
                '{"example_id":"e1","example_id":"e2","post_id":"p1"}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                snapshot_artifact(root, "duplicate", "duplicate.jsonl", jsonl=True)
            (root / "nested.json").write_text(
                '{"outer":{"value":1,"value":2}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                snapshot_artifact(root, "nested", "nested.json")

    def test_snapshot_json_object_returns_strict_payload_and_ref(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "policy.json").write_text('{"scope":"actual"}', encoding="utf-8")
            ref, payload = snapshot_json_object(root, "policy", "policy.json")
            self.assertEqual({"scope": "actual"}, payload)
            self.assertEqual("policy", ref.logical_name)
            self.assertIsNone(ref.row_count)
            (root / "array.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be an object"):
                snapshot_json_object(root, "array", "array.json")

    def test_strict_types_and_manifest_cross_binding(self):
        with self.assertRaises(ValueError):
            canonical_bytes({1: "collision", "1": "collision"})
        bad = expected(); bad[0]["example_id"] = None
        with self.assertRaises(ValueError):
            prediction_payload_readback(bad, prediction())
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root / "a.json").write_bytes(b"[]")
            ref = snapshot_artifact(root, "a", "a.json")
            refs, universe, c, p, baseline, manifest = actual_parts(
                root,
                extra_refs={"a": ref},
            )
            p["per_row"][0]["source_digest_sha256"] = h("z")
            with self.assertRaises(ValueError):
                build_readback_manifest(
                    run_spec_sha256=h("f"), artifacts=refs,
                    expected_universe=universe, producer_coverage=c,
                    prediction=p, baseline_prediction=baseline,
                    source_digest_sha256=h("c"), metric_protocol_sha256=h("f"),
                    bootstrap_seed=7, bootstrap_replicates=100,
                )
            manifest["producer_coverage"]["complete_count"] = 1
            manifest["manifest_sha256"] = h("0")
            with self.assertRaises(ValueError):
                from src.llm_batch.calibration_actual_readback import validate_readback_manifest
                validate_readback_manifest(manifest)

    def test_semantic_artifact_receipts_reject_self_rehashed_divergence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            refs, universe, coverage, after, baseline, manifest = actual_parts(root)
            changed = producer()
            changed[0]["generation_proof_fingerprint"] = h("9")
            write_jsonl(root / "producer.jsonl", changed)
            with self.assertRaisesRegex(ValueError, "snapshot mismatch"):
                validate_actual_readback_artifacts(root, manifest)
            forged_refs = dict(refs)
            forged_refs["producer"] = snapshot_artifact(
                root,
                "producer",
                "producer.jsonl",
                jsonl=True,
            )
            forged = build_readback_manifest(
                run_spec_sha256=h("f"), artifacts=forged_refs,
                expected_universe=universe, producer_coverage=coverage,
                prediction=after, baseline_prediction=baseline,
                source_digest_sha256=h("c"), metric_protocol_sha256=h("f"),
                bootstrap_seed=7, bootstrap_replicates=100,
            )
            with self.assertRaisesRegex(ValueError, "producer semantic receipt mismatch"):
                validate_actual_readback_artifacts(root, forged)

    def test_evaluation_plan_and_baseline_receipt_are_bound(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, _, _, _, _, manifest = actual_parts(root)
            forged = json.loads(json.dumps(manifest))
            forged["bootstrap_replicates"] = 101
            forged["manifest_sha256"] = hashlib.sha256(
                canonical_bytes({key: value for key, value in forged.items() if key != "manifest_sha256"})
            ).hexdigest()
            from src.llm_batch.calibration_actual_readback import validate_readback_manifest
            with self.assertRaisesRegex(ValueError, "evaluation plan hash mismatch"):
                validate_readback_manifest(forged)
            self.assertEqual(
                2,
                manifest["baseline_prediction"]["row_count"],
            )

    def test_top_level_source_digest_must_match_every_producer_row(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            refs, universe, coverage, after, baseline, _ = actual_parts(root)
            with self.assertRaisesRegex(ValueError, "top-level source digest"):
                build_readback_manifest(
                    run_spec_sha256=h("f"),
                    artifacts=refs,
                    expected_universe=universe,
                    producer_coverage=coverage,
                    prediction=after,
                    baseline_prediction=baseline,
                    source_digest_sha256=h("9"),
                    metric_protocol_sha256=h("f"),
                    bootstrap_seed=7,
                    bootstrap_replicates=100,
                )

    def test_ece_uses_fixed_bins_and_strict_boolean_metrics(self):
        rows = [{"example_id": "e1", "group": "g1", "correct": True, "abstain": False, "brier": .1, "log_loss": .2, "confidence": .9, "risk_score": .1}, {"example_id": "e2", "group": "g2", "correct": False, "abstain": False, "brier": .8, "log_loss": .9, "confidence": .4, "risk_score": .2}]
        result = cluster_bootstrap(rows, seed=3, replicates=100, ece_bin_edges=(0.0, .5, 1.0))
        self.assertTrue(result["estimable"])
        bad = [dict(r, correct=1) for r in rows]
        with self.assertRaises(ValueError):
            cluster_bootstrap(bad, seed=3, replicates=100)


if __name__ == "__main__":
    unittest.main()
