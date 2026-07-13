from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.llm_batch.calibration_actual_readback import snapshot_artifact
from src.llm_batch.calibration_dataset_readiness import (
    sha256_payload,
    validate_dataset_readiness_manifest,
)
from src.llm_batch.candidate_set_calibration_shadow import CalibrationEvaluationPolicy
from tools.run_candidate_set_calibration_shadow_harness import (
    ACTUAL_SOURCE_PAYLOAD_SCHEMA,
    ACTUAL_SOURCE_MANIFEST_SCHEMA,
    _build_synthetic_bundle,
    _base_shadow_map,
    _calibration_artifact_from_dict,
    _calibration_shadow_map,
    _canonical_hash,
    _implementation_contract,
    _policy,
    _run_spec_self_hash,
    _build_actual_readback_manifest_from_files,
    _validate_actual_source_manifest,
    _validate_actual_replay_bundle,
    _validate_split_against_readiness,
    _score_vector_map,
    build_actual_readback_manifest_from_files,
    build_actual_preflight_report,
    build_bound_actual_readback_from_files,
    build_comparison,
    create_run_spec,
    render_markdown,
    validate_run_spec,
    write_comparison,
    write_run_spec,
)


ROOT = Path(__file__).resolve().parents[1]
P1_RUN_SPEC = ROOT / "out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json"
P1_COMPARISON = ROOT / "out/candidate_set_nil_shadow_harness_20260711/v8/comparison.json"
P2_RUN_SPEC = ROOT / "out/publication_exact_once_harness_20260711/v8/run_spec.json"
P2_COMPARISON = ROOT / "out/publication_exact_once_harness_20260711/v8/comparison.json"
LABEL_LEDGER = ROOT / "docs/devs/p1_candidate_set_nil_golden18_label_ledger_20260711.json"
DATASET_READINESS = ROOT / "out/candidate_set_calibration_dataset_readiness_20260712/v2/readiness.json"


class CandidateSetCalibrationShadowHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = create_run_spec(
            parent_p1_run_spec_path=P1_RUN_SPEC,
            parent_p1_comparison_path=P1_COMPARISON,
            parent_p2_run_spec_path=P2_RUN_SPEC,
            parent_p2_comparison_path=P2_COMPARISON,
            label_ledger_path=LABEL_LEDGER,
        )

    def test_implementation_contract_binds_actual_readback_foundation(self):
        artifacts = _implementation_contract()["artifacts"]
        self.assertIn("actual_artifact_readback", artifacts)
        self.assertIn("actual_artifact_readback_tests", artifacts)
        self.assertIn("dataset_readiness_contract", artifacts)
        self.assertIn("dataset_readiness_tool", artifacts)
        self.assertIn("dataset_readiness_tests", artifacts)
        self.assertEqual(
            "READ_ONLY_NO_WRITE_NO_RUNTIME",
            self.spec["p3_contract"]["actual_preflight_mode"],
        )
        with TemporaryDirectory() as directory:
            path = write_run_spec(self.spec, Path(directory) / "run_spec.json")
            comparison = build_comparison(path)
            markdown = render_markdown(comparison)
        self.assertEqual(
            "IMPLEMENTED_V2_BOUND_RUNNER_NO_ACTUAL_ARTIFACT",
            comparison["gates"]["actual_artifact_readback"],
        )
        self.assertEqual(
            "IMPLEMENTED_POLICY_BOUND_NO_ACTUAL_OUTPUT",
            comparison["gates"]["full_interval_protocol"],
        )
        self.assertFalse(any("아직 구현되지 않았다" in item for item in comparison["limits"]))
        self.assertIn("실제 데이터 준비도", markdown)
        self.assertIn("실제 분할 가능 행 | 0", markdown)
        self.assertIn("actual-readback v2", markdown)

    def test_actual_readback_v2_uses_external_universe_and_validates_baseline(self):
        def write_jsonl(path: Path, rows: list[dict]) -> None:
            path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )

        sha = lambda ch: ch * 64
        expected = [
            {"example_id": f"e{i}", "post_id": f"p{i}"}
            for i in range(3)
        ]
        producer = [
            {
                **row,
                "generation_status": "COMPLETE",
                "candidate_set_fingerprint": sha("a"),
                "generation_proof_fingerprint": sha("b"),
                "source_digest_sha256": sha("c"),
            }
            for row in expected[:2]
        ]
        prediction = [
            {
                **row,
                "probabilities": {"work": 1_000_000},
                "shadow_fingerprint": sha("d"),
                "score_vector_sha256": sha("e"),
                "candidate_set_fingerprint": sha("a"),
                "generation_proof_fingerprint": sha("b"),
                "source_digest_sha256": sha("c"),
            }
            for row in expected[:2]
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_jsonl(root / "expected.jsonl", expected)
            write_jsonl(root / "producer.jsonl", producer)
            write_jsonl(root / "prediction.jsonl", prediction)
            write_jsonl(root / "baseline.jsonl", prediction)
            with self.assertRaisesRegex(ValueError, "coverage order/set mismatch"):
                _build_actual_readback_manifest_from_files(
                    artifact_root=root,
                    expected_universe_jsonl="expected.jsonl",
                    producer_jsonl="producer.jsonl",
                    prediction_jsonl="prediction.jsonl",
                    baseline_prediction_jsonl="baseline.jsonl",
                    run_spec_sha256=sha("f"),
                    source_digest_sha256=sha("c"),
                    metric_protocol_sha256=sha("f"),
                    seed=7,
                    replicates=100,
                )
            write_jsonl(root / "expected.jsonl", expected[:2])
            bad_baseline = json.loads(json.dumps(prediction))
            bad_baseline[0]["probabilities"] = {"work": 999_999}
            write_jsonl(root / "baseline.jsonl", bad_baseline)
            with self.assertRaisesRegex(ValueError, "probability mass"):
                _build_actual_readback_manifest_from_files(
                    artifact_root=root,
                    expected_universe_jsonl="expected.jsonl",
                    producer_jsonl="producer.jsonl",
                    prediction_jsonl="prediction.jsonl",
                    baseline_prediction_jsonl="baseline.jsonl",
                    run_spec_sha256=sha("f"),
                    source_digest_sha256=sha("c"),
                    metric_protocol_sha256=sha("f"),
                    seed=7,
                    replicates=100,
                )

    def test_raw_sha_actual_readback_api_is_fail_closed(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "raw SHA assertions are forbidden"):
                build_actual_readback_manifest_from_files(
                    artifact_root=directory,
                    expected_universe_jsonl="missing-expected.jsonl",
                    producer_jsonl="missing-producer.jsonl",
                    prediction_jsonl="missing-after.jsonl",
                    baseline_prediction_jsonl="missing-before.jsonl",
                    run_spec_sha256="a" * 64,
                    source_digest_sha256="b" * 64,
                    metric_protocol_sha256="c" * 64,
                    seed=7,
                    replicates=100,
                )

    def test_bound_actual_readback_derives_policy_then_stops_at_current_readiness(self):
        policy = CalibrationEvaluationPolicy.create(
            fixed_bin_edges=(0.0, 0.5, 1.0),
            selector_max_error_probability=0.2,
            nil_min_probability=0.8,
            alpha=0.05,
            min_dev_rows=2,
            min_dev_per_truth_class=1,
            min_calibration_rows=2,
            min_calibration_per_truth_class=1,
            min_frozen_rows=2,
            min_per_truth_class=1,
            min_occupied_bin_rows=1,
            target_coverage=0.5,
            max_selective_risk_upper_bound=0.5,
            baseline_noninferiority_margin=0.1,
            min_candidate_recall_lower_bound=0.1,
            min_nil_prediction_count=1,
            min_nil_precision_lower_bound=0.1,
            min_nil_recall_lower_bound=0.1,
            paired_delta_ci_bounds={
                "top_label_accuracy": -0.1,
                "brier": 0.1,
                "log_loss": 0.1,
                "ece": 0.1,
                "selective_risk": 0.1,
                "aurc": 0.1,
            },
            policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
            policy_origin="PRE_REGISTERED_DEV_CALIBRATION",
        )
        with TemporaryDirectory(dir=ROOT / "out") as directory:
            policy_path = Path(directory) / "actual-policy.json"
            policy_path.write_text(
                json.dumps(policy.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            relative_policy = policy_path.relative_to(ROOT).as_posix()
            with self.assertRaisesRegex(
                ValueError,
                "NO_GO_ACTUAL_DATASET_NOT_READY: ready_rows=0/18",
            ):
                build_bound_actual_readback_from_files(
                    artifact_root=ROOT,
                    p1_run_spec_json=P1_RUN_SPEC.relative_to(ROOT).as_posix(),
                    p1_comparison_json=P1_COMPARISON.relative_to(ROOT).as_posix(),
                    label_ledger_json=LABEL_LEDGER.relative_to(ROOT).as_posix(),
                    actual_evaluation_policy_json=relative_policy,
                    split_manifest_json="not-read-before-readiness.json",
                    source_manifest_json="not-read-before-readiness.json",
                    expected_universe_jsonl="not-read-before-readiness.jsonl",
                    producer_jsonl="not-read-before-readiness.jsonl",
                    prediction_jsonl="not-read-before-readiness.jsonl",
                    baseline_prediction_jsonl="not-read-before-readiness.jsonl",
                    seed=7,
                    replicates=100,
                )

    def test_actual_preflight_lists_missing_inputs_without_writes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            report = build_actual_preflight_report(
                artifact_root=root,
                p1_run_spec_json="p1/run_spec.json",
                p1_comparison_json="p1/comparison.json",
                label_ledger_json="labels/ledger.json",
                actual_evaluation_policy_json="policy/actual.json",
                split_manifest_json="dataset/split.json",
                source_manifest_json="dataset/source.json",
                expected_universe_jsonl="dataset/expected.jsonl",
                producer_jsonl="predictions/producer.jsonl",
                prediction_jsonl="predictions/after.jsonl",
                baseline_prediction_jsonl="predictions/before.jsonl",
                seed=20260712,
                replicates=2000,
            )
            self.assertEqual("NO_GO_ACTUAL_PREFLIGHT", report["gate"])
            self.assertFalse(report["writes_performed"])
            self.assertFalse(report["runtime_started"])
            self.assertFalse(report["bound_readback"]["attempted"])
            self.assertIn("MISSING_FILE::p1_run_spec", report["blockers"])
            self.assertEqual(
                6,
                sum(
                    blocker.startswith("MISSING_REPLAY_ARTIFACT::")
                    for blocker in report["blockers"]
                ),
            )
            self.assertEqual([], list(root.iterdir()))

    def test_actual_preflight_replays_readiness_before_downstream_files_exist(self):
        policy = _policy(
            policy_scope="FROZEN_ACTUAL_PRE_REGISTERED",
            min_candidate_recall_lower_bound=0.1,
            min_nil_precision_lower_bound=0.1,
            min_nil_recall_lower_bound=0.1,
        )
        with TemporaryDirectory(dir=ROOT / "out") as directory:
            policy_path = Path(directory) / "actual-policy.json"
            policy_path.write_text(
                json.dumps(policy.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )
            missing_prefix = "out/preflight-missing-fixture"
            replay = [
                (name, f"{missing_prefix}/{name}.jsonl")
                for name in (
                    "after_base_shadows",
                    "after_score_vectors",
                    "baseline_base_shadows",
                    "baseline_score_vectors",
                )
            ] + [
                (name, f"{missing_prefix}/{name}.json")
                for name in (
                    "after_calibration_artifact",
                    "baseline_calibration_artifact",
                )
            ]
            report = build_actual_preflight_report(
                artifact_root=ROOT,
                p1_run_spec_json=P1_RUN_SPEC.relative_to(ROOT).as_posix(),
                p1_comparison_json=P1_COMPARISON.relative_to(ROOT).as_posix(),
                label_ledger_json=LABEL_LEDGER.relative_to(ROOT).as_posix(),
                actual_evaluation_policy_json=policy_path.relative_to(ROOT).as_posix(),
                split_manifest_json=f"{missing_prefix}/split.json",
                source_manifest_json=f"{missing_prefix}/source.json",
                expected_universe_jsonl=f"{missing_prefix}/expected.jsonl",
                producer_jsonl=f"{missing_prefix}/producer.jsonl",
                prediction_jsonl=f"{missing_prefix}/after.jsonl",
                baseline_prediction_jsonl=f"{missing_prefix}/before.jsonl",
                additional_artifacts=replay,
                seed=20260712,
                replicates=2000,
            )
            self.assertTrue(report["readiness"]["evaluated"])
            self.assertEqual(
                "NO_GO_ACTUAL_DATASET_NOT_READY",
                report["readiness"]["gate"],
            )
            self.assertEqual(0, report["readiness"]["counts"]["ready_rows"])
            self.assertIn("NO_GO_ACTUAL_DATASET_NOT_READY", report["blockers"])
            self.assertFalse(report["bound_readback"]["attempted"])

    def test_actual_preflight_go_is_read_only_and_lists_source_payloads(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            base_paths = {
                "p1_run_spec_json": "p1/run_spec.json",
                "p1_comparison_json": "p1/comparison.json",
                "label_ledger_json": "labels/ledger.json",
                "actual_evaluation_policy_json": "policy/actual.json",
                "split_manifest_json": "dataset/split.json",
                "source_manifest_json": "dataset/source.json",
                "expected_universe_jsonl": "dataset/expected.jsonl",
                "producer_jsonl": "predictions/producer.jsonl",
                "prediction_jsonl": "predictions/after.jsonl",
                "baseline_prediction_jsonl": "predictions/before.jsonl",
            }
            replay = [
                ("after_base_shadows", "replay/after_base_shadows.jsonl"),
                ("after_score_vectors", "replay/after_score_vectors.jsonl"),
                ("after_calibration_artifact", "replay/after_calibration_artifact.json"),
                ("baseline_base_shadows", "replay/baseline_base_shadows.jsonl"),
                ("baseline_score_vectors", "replay/baseline_score_vectors.jsonl"),
                (
                    "baseline_calibration_artifact",
                    "replay/baseline_calibration_artifact.json",
                ),
            ]
            for relative_path in list(base_paths.values()) + [path for _, path in replay]:
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "{}\n" if path.suffix == ".jsonl" else "{}",
                    encoding="utf-8",
                )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            readiness = {
                "ready_for_split_manifest": True,
                "gate": "GO_ACTUAL_DATASET_READY",
                "counts": {"ready_rows": 6, "source_rows": 6},
                "manifest_sha256": "a" * 64,
            }
            actual_run_spec = {
                "run_spec_sha256": "b" * 64,
                "artifacts": {
                    "source_payload::example-1": {
                        "relative_path": "source/example-1.json",
                        "bytes": 123,
                        "sha256": "c" * 64,
                    }
                },
            }
            manifest = {"manifest_sha256": "d" * 64}
            with patch(
                "tools.run_calibration_dataset_readiness.build_current_readiness",
                return_value=readiness,
            ), patch(
                "tools.run_candidate_set_calibration_shadow_harness.build_bound_actual_readback_from_files",
                return_value=(root, actual_run_spec, readiness, manifest),
            ):
                report = build_actual_preflight_report(
                    artifact_root=root,
                    additional_artifacts=replay,
                    seed=20260712,
                    replicates=2000,
                    **base_paths,
                )
            self.assertEqual(
                "GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED",
                report["gate"],
            )
            self.assertTrue(report["bound_readback"]["attempted"])
            self.assertTrue(report["bound_readback"]["eligible"])
            self.assertEqual(
                "source_payload::example-1",
                report["bound_readback"]["discovered_source_payloads"][0][
                    "logical_name"
                ],
            )
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_actual_split_replays_full_readiness_row_semantics(self):
        bundle = _build_synthetic_bundle()
        split_manifest = bundle["manifest"]
        readiness_rows = []
        for assignment in split_manifest.assignments:
            readiness_rows.append(
                {
                    "post_id": assignment.post_id,
                    "truth_kind": assignment.truth_kind,
                    "truth_candidate_id": (
                        assignment.truth_label
                        if assignment.truth_kind == "CANDIDATE"
                        else None
                    ),
                    "candidate_set_fingerprint": assignment.candidate_set_fingerprint,
                    "split_group_id": assignment.split_group_id,
                    "content_fingerprint": assignment.content_fingerprint,
                    "source_group_fingerprint": assignment.source_group_fingerprint,
                    "label_provenance_sha256": assignment.label_provenance_sha256,
                    "gold_work_fingerprint": assignment.gold_work_fingerprint,
                    "binding_status": assignment.binding_status,
                }
            )
        frozen = _validate_split_against_readiness(
            split_manifest,
            {"rows": readiness_rows},
            bundle["policy"],
        )
        self.assertTrue(frozen)
        tampered = copy.deepcopy(readiness_rows)
        tampered[0]["content_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "content_fingerprint"):
            _validate_split_against_readiness(
                split_manifest,
                {"rows": tampered},
                bundle["policy"],
            )

    def test_actual_source_manifest_binds_frozen_order_and_self_hash(self):
        bundle = _build_synthetic_bundle()
        frozen = [
            item
            for item in bundle["manifest"].assignments
            if item.split == "FROZEN_HOLDOUT"
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for item in frozen:
                relative_path = f"source/{item.example_id}.json"
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": ACTUAL_SOURCE_PAYLOAD_SCHEMA,
                            "source_run_id": "fixture-run",
                            "example_id": item.example_id,
                            "post_id": item.post_id,
                            "payload": {"body": f"fixture::{item.example_id}"},
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                rows.append(
                    {
                        "example_id": item.example_id,
                        "post_id": item.post_id,
                        "source_artifact": snapshot_artifact(
                            root,
                            f"source_payload::{item.example_id}",
                            relative_path,
                        ).to_dict(),
                    }
                )
            source = {
                "schema_version": ACTUAL_SOURCE_MANIFEST_SCHEMA,
                "source_run_id": "fixture-run",
                "rows": rows,
            }
            source["manifest_sha256"] = _canonical_hash(source)
            _validate_actual_source_manifest(source, frozen, artifact_root=root)

            swapped = copy.deepcopy(source)
            swapped["rows"] = list(reversed(swapped["rows"]))
            swapped["manifest_sha256"] = _canonical_hash(
                {key: value for key, value in swapped.items() if key != "manifest_sha256"}
            )
            with self.assertRaisesRegex(ValueError, "frozen order"):
                _validate_actual_source_manifest(swapped, frozen, artifact_root=root)

            first_ref = source["rows"][0]["source_artifact"]
            (root / first_ref["relative_path"]).write_text(
                json.dumps({"tampered": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "source payload snapshot mismatch"):
                _validate_actual_source_manifest(source, frozen, artifact_root=root)

    def test_actual_source_payload_identity_is_bound(self):
        bundle = _build_synthetic_bundle()
        frozen = [
            item
            for item in bundle["manifest"].assignments
            if item.split == "FROZEN_HOLDOUT"
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for index, item in enumerate(frozen):
                relative_path = f"source/{item.example_id}.json"
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": ACTUAL_SOURCE_PAYLOAD_SCHEMA,
                            "source_run_id": "fixture-run",
                            "example_id": (
                                "wrong-example" if index == 0 else item.example_id
                            ),
                            "post_id": item.post_id,
                            "payload": {"body": "fixture"},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                rows.append(
                    {
                        "example_id": item.example_id,
                        "post_id": item.post_id,
                        "source_artifact": snapshot_artifact(
                            root,
                            f"source_payload::{item.example_id}",
                            relative_path,
                        ).to_dict(),
                    }
                )
            source = {
                "schema_version": ACTUAL_SOURCE_MANIFEST_SCHEMA,
                "source_run_id": "fixture-run",
                "rows": rows,
            }
            source["manifest_sha256"] = _canonical_hash(source)
            with self.assertRaisesRegex(ValueError, "source payload identity mismatch"):
                _validate_actual_source_manifest(source, frozen, artifact_root=root)

    def test_actual_evaluator_replay_object_parsers_roundtrip(self):
        bundle = _build_synthetic_bundle()
        artifact = _calibration_artifact_from_dict(bundle["artifact"].to_dict())
        self.assertEqual(bundle["artifact"].to_dict(), artifact.to_dict())
        score_rows = [score.to_dict() for score in bundle["after_scores"].values()]
        self.assertEqual(
            set(bundle["after_scores"]),
            set(_score_vector_map(score_rows)),
        )
        base_rows = [
            {
                "example_id": example_id,
                "post_id": bundle["after_scores"][example_id].post_id,
                "shadow": shadow.to_dict(),
            }
            for example_id, shadow in bundle["base_shadows"].items()
        ]
        self.assertEqual(set(bundle["base_shadows"]), set(_base_shadow_map(base_rows)))
        def prediction_payloads(shadows):
            rows = []
            for example_id, shadow in shadows.items():
                assignment = next(
                    item
                    for item in bundle["manifest"].assignments
                    if item.example_id == example_id
                )
                rows.append(
                    {
                        "example_id": example_id,
                        "post_id": shadow.post_id,
                        "group": assignment.split_group_id,
                        "probabilities": {
                            item.label: item.probability_mass
                            for item in shadow.event_probabilities
                        },
                        "shadow_fingerprint": shadow.shadow_fingerprint,
                        "score_vector_sha256": shadow.score_vector_sha256,
                        "candidate_set_fingerprint": shadow.candidate_set_fingerprint,
                        "generation_proof_fingerprint": shadow.generation_proof_fingerprint,
                        "source_digest_sha256": "8" * 64,
                        "calibration_shadow": shadow.to_dict(),
                    }
                )
            return rows

        prediction_rows = prediction_payloads(bundle["after"])
        baseline_rows = prediction_payloads(bundle["before"])
        parsed = _calibration_shadow_map(prediction_rows)
        self.assertEqual(set(bundle["after"]), set(parsed))
        tampered = copy.deepcopy(prediction_rows)
        tampered[0]["shadow_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            _calibration_shadow_map(tampered)

        frozen = [
            item
            for item in bundle["manifest"].assignments
            if item.split == "FROZEN_HOLDOUT"
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def write_jsonl(relative_path, rows):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "\n".join(
                        json.dumps(row, ensure_ascii=False, sort_keys=True)
                        for row in rows
                    )
                    + "\n",
                    encoding="utf-8",
                )

            replay_paths = {
                "after_base_shadows": "replay/after_base_shadows.jsonl",
                "after_score_vectors": "replay/after_score_vectors.jsonl",
                "after_calibration_artifact": "replay/after_calibration_artifact.json",
                "baseline_base_shadows": "replay/baseline_base_shadows.jsonl",
                "baseline_score_vectors": "replay/baseline_score_vectors.jsonl",
                "baseline_calibration_artifact": "replay/baseline_calibration_artifact.json",
            }
            write_jsonl(replay_paths["after_base_shadows"], base_rows)
            write_jsonl(replay_paths["baseline_base_shadows"], base_rows)
            write_jsonl(
                replay_paths["after_score_vectors"],
                [score.to_dict() for score in bundle["after_scores"].values()],
            )
            write_jsonl(
                replay_paths["baseline_score_vectors"],
                [score.to_dict() for score in bundle["before_scores"].values()],
            )
            for name, payload in (
                ("after_calibration_artifact", bundle["artifact"].to_dict()),
                (
                    "baseline_calibration_artifact",
                    bundle["baseline_artifact"].to_dict(),
                ),
            ):
                path = root / replay_paths[name]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8",
                )
            refs = {
                name: snapshot_artifact(
                    root,
                    name,
                    relative_path,
                    jsonl=relative_path.endswith(".jsonl"),
                )
                for name, relative_path in replay_paths.items()
            }
            _validate_actual_replay_bundle(
                root=root,
                refs=refs,
                frozen=frozen,
                split_manifest=bundle["manifest"],
                policy=bundle["policy"],
                prediction_rows=prediction_rows,
                baseline_rows=baseline_rows,
            )

            bad_name = "after_calibration_artifact"
            (root / replay_paths[bad_name]).write_text("{}", encoding="utf-8")
            refs[bad_name] = snapshot_artifact(
                root,
                bad_name,
                replay_paths[bad_name],
            )
            with self.assertRaisesRegex(ValueError, "fit receipt missing"):
                _validate_actual_replay_bundle(
                    root=root,
                    refs=refs,
                    frozen=frozen,
                    split_manifest=bundle["manifest"],
                    policy=bundle["policy"],
                    prediction_rows=prediction_rows,
                    baseline_rows=baseline_rows,
                )
    def test_p3_rejects_self_rehashed_readiness_not_replayed_from_sources(self):
        forged = json.loads(DATASET_READINESS.read_text(encoding="utf-8"))
        candidate = next(row for row in forged["rows"] if row["truth_kind"] == "CANDIDATE")
        candidate["expected_title"] = "출처와 다른 조작 제목"
        candidate["row_sha256"] = sha256_payload(
            {key: value for key, value in candidate.items() if key != "row_sha256"}
        )
        forged["manifest_sha256"] = sha256_payload(
            {key: value for key, value in forged.items() if key != "manifest_sha256"}
        )
        validate_dataset_readiness_manifest(forged)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "forged-readiness.json"
            path.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source replay mismatch"):
                create_run_spec(
                    parent_p1_run_spec_path=P1_RUN_SPEC,
                    parent_p1_comparison_path=P1_COMPARISON,
                    parent_p2_run_spec_path=P2_RUN_SPEC,
                    parent_p2_comparison_path=P2_COMPARISON,
                    label_ledger_path=LABEL_LEDGER,
                    dataset_readiness_path=path,
                )

    def test_p3_rejects_label_ledger_not_bound_by_p1(self):
        forged = json.loads(LABEL_LEDGER.read_text(encoding="utf-8"))
        candidate = next(row for row in forged["rows"] if row["truth_kind"] == "CANDIDATE")
        candidate["expected_title"] = "P1과 다른 라벨"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "forged-ledger.json"
            path.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact P1-bound artifact"):
                create_run_spec(
                    parent_p1_run_spec_path=P1_RUN_SPEC,
                    parent_p1_comparison_path=P1_COMPARISON,
                    parent_p2_run_spec_path=P2_RUN_SPEC,
                    parent_p2_comparison_path=P2_COMPARISON,
                    label_ledger_path=path,
                    dataset_readiness_path=DATASET_READINESS,
                )

    def test_status_validator_replays_readiness_and_p1_label_lineage(self):
        def artifact_ref(path: Path) -> dict:
            raw = path.read_bytes()
            try:
                stored = path.resolve().relative_to(ROOT).as_posix()
            except ValueError:
                stored = str(path.resolve())
            return {
                "path": stored,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }

        with TemporaryDirectory() as directory:
            root = Path(directory)
            forged_readiness = json.loads(DATASET_READINESS.read_text(encoding="utf-8"))
            candidate = next(
                row for row in forged_readiness["rows"] if row["truth_kind"] == "CANDIDATE"
            )
            candidate["expected_title"] = "status validator 조작 제목"
            candidate["row_sha256"] = sha256_payload(
                {key: value for key, value in candidate.items() if key != "row_sha256"}
            )
            forged_readiness["manifest_sha256"] = sha256_payload(
                {
                    key: value
                    for key, value in forged_readiness.items()
                    if key != "manifest_sha256"
                }
            )
            readiness_path = root / "forged-readiness.json"
            readiness_path.write_text(
                json.dumps(forged_readiness, ensure_ascii=False),
                encoding="utf-8",
            )
            forged_spec = copy.deepcopy(self.spec)
            forged_spec["artifacts"]["dataset_readiness"] = artifact_ref(readiness_path)
            forged_spec["dataset_readiness"]["manifest_sha256"] = forged_readiness[
                "manifest_sha256"
            ]
            forged_spec["run_spec_sha256"] = _run_spec_self_hash(forged_spec)
            spec_path = root / "forged-readiness-spec.json"
            spec_path.write_text(json.dumps(forged_spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source replay mismatch"):
                validate_run_spec(spec_path)

            forged_ledger = json.loads(LABEL_LEDGER.read_text(encoding="utf-8"))
            forged_ledger["rows"][1]["expected_title"] = "status ledger 조작"
            ledger_path = root / "forged-ledger.json"
            ledger_path.write_text(
                json.dumps(forged_ledger, ensure_ascii=False),
                encoding="utf-8",
            )
            forged_spec = copy.deepcopy(self.spec)
            forged_spec["artifacts"]["label_ledger"] = artifact_ref(ledger_path)
            forged_spec["run_spec_sha256"] = _run_spec_self_hash(forged_spec)
            spec_path = root / "forged-ledger-spec.json"
            spec_path.write_text(json.dumps(forged_spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact P1-bound artifact"):
                validate_run_spec(spec_path)

    def test_saved_golden18_stays_no_number_and_not_evaluable(self):
        with TemporaryDirectory() as directory:
            path = write_run_spec(self.spec, Path(directory) / "run_spec.json")
            report = build_comparison(path)

        golden = report["golden18_readiness"]
        self.assertEqual(18, golden["row_count"])
        self.assertEqual("UNKNOWN", golden["generation_status"])
        self.assertEqual("NOT_EVALUABLE", golden["candidate_set_recall"])
        self.assertTrue(golden["all_probability_null"])
        self.assertTrue(all(value is None for value in golden["headline_metrics"].values()))
        self.assertFalse(golden["conversion_allowed"])
        self.assertEqual("REVIEW-LOCKED", report["gates"]["semantic_quality"])
        self.assertFalse(report["gates"]["full_scan_approval"])

    def test_before_unbound_numeric_claim_is_closed_by_authoritative_p3_wrapper(self):
        with TemporaryDirectory() as directory:
            path = write_run_spec(self.spec, Path(directory) / "run_spec.json")
            report = build_comparison(path)

        comparison = report["before_after"]
        self.assertEqual(1, comparison["before"]["unbound_numeric_claim_accepted"])
        self.assertEqual(0, comparison["after"]["unbound_numeric_claim_accepted"])
        self.assertEqual("NOT_AVAILABLE_UNCALIBRATED", comparison["after"]["missing_artifact_status"])

    def test_synthetic_metric_math_improves_but_never_becomes_deployment_evidence(self):
        with TemporaryDirectory() as directory:
            path = write_run_spec(self.spec, Path(directory) / "run_spec.json")
            report = build_comparison(path)

        synthetic = report["synthetic_metric_contract"]
        before = synthetic["before_metrics"]
        after = synthetic["after_metrics"]
        self.assertLess(before["top_label_accuracy"], after["top_label_accuracy"])
        self.assertGreater(before["multiclass_brier"], after["multiclass_brier"])
        self.assertGreater(before["log_loss"], after["log_loss"])
        self.assertFalse(synthetic["conversion_allowed"])
        self.assertEqual("SYNTHETIC_EVIDENCE_NEVER_DEPLOYMENT", synthetic["conversion_reason"])

    def test_all_adversarial_contract_cases_pass_without_false_go(self):
        with TemporaryDirectory() as directory:
            path = write_run_spec(self.spec, Path(directory) / "run_spec.json")
            report = build_comparison(path)

        attacks = report["adversarial_contract"]
        self.assertGreaterEqual(attacks["case_count"], 12)
        self.assertEqual(attacks["case_count"], attacks["passed_count"])
        self.assertEqual(0, attacks["false_go_count"])

    def test_run_spec_and_outputs_roundtrip_and_tamper_fail_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            run_spec_path = write_run_spec(self.spec, root / "run_spec.json")
            validated = validate_run_spec(run_spec_path)
            self.assertEqual(self.spec["run_spec_sha256"], validated[0]["run_spec_sha256"])
            report = build_comparison(run_spec_path)
            json_path, markdown_path = write_comparison(
                report,
                output_json=root / "comparison.json",
                output_md=root / "comparison.md",
            )
            self.assertTrue(json_path.is_file())
            self.assertTrue(markdown_path.is_file())
            self.assertIn("정확도 퍼센트", markdown_path.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                write_run_spec(self.spec, run_spec_path)
            with self.assertRaisesRegex(ValueError, "distinct new files"):
                write_comparison(
                    report,
                    output_json=json_path,
                    output_md=markdown_path,
                )

            approval_forged = copy.deepcopy(report)
            approval_forged["gates"]["full_scan_approval"] = True
            with self.assertRaisesRegex(ValueError, "approval boundary"):
                write_comparison(
                    approval_forged,
                    output_json=root / "forged.json",
                    output_md=root / "forged.md",
                )
            self.assertFalse((root / "forged.json").exists())
            self.assertFalse((root / "forged.md").exists())

            tampered = json.loads(run_spec_path.read_text(encoding="utf-8"))
            tampered["mode"] = "tampered"
            tampered_path = root / "tampered.json"
            tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "self hash|mode"):
                validate_run_spec(tampered_path)

            policy_tampered = json.loads(run_spec_path.read_text(encoding="utf-8"))
            policy_tampered["metric_protocol"]["policy"]["alpha"] = 0.10
            policy_tampered["run_spec_sha256"] = _run_spec_self_hash(policy_tampered)
            policy_tampered_path = root / "policy_tampered.json"
            policy_tampered_path.write_text(
                json.dumps(policy_tampered),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "metric protocol|policy binding"):
                validate_run_spec(policy_tampered_path)


if __name__ == "__main__":
    unittest.main()
