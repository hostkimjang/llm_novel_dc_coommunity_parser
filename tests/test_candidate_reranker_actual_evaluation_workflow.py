"""고정 모델 양쪽 재생·전체 분모·새 출력·actual 진입 거절을 실제 저장 경로로 검증한다."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import run_candidate_reranker_actual_evaluation as workflow
from tests.test_candidate_reranker_actual_bridge import (
    semantic_bundle, paired_semantic_bundle, plain_bundle, arm_for, source_inputs, terminal_pair, pair,
)
from tests.test_candidate_reranker_evaluation_workflow import write_bundle


def raw(value):
    return workflow.local._json_bytes(value)


def ref(path, root):
    content = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "sha256": workflow.local._sha(content), "bytes": len(content)}


def write_actual_bundle(root, fixture, artifact, *, baseline_fixture=None, baseline_artifact=None, existing_root=False):
    """합성 두 arm을 명시한다. P1 자료는 actual 적격 자료가 아니므로 실행에 쓰지 않는다."""
    root.mkdir(exist_ok=existing_root)
    arm_refs = {}
    for name in ("after", "baseline"):
        f = baseline_fixture if name == "baseline" and baseline_fixture is not None else fixture
        a = baseline_artifact if name == "baseline" and baseline_artifact is not None else artifact
        path, _, _ = write_bundle(root / name, f, a)
        arm_refs[name + "_bundle"] = ref(path, root)
    source = source_inputs(arm_for(fixture, artifact))
    (root / "source").mkdir(exist_ok=existing_root)
    for item in source["source_manifest"]["rows"]:
        r = item["source_artifact"]
        (root / r["relative_path"]).write_bytes(source["actual_source_payloads"][r["sha256"]])
    payloads = {"p1_run_spec": {"schema_version": "synthetic_not_actual_p1"},
        "p1_comparison": {"schema_version": "synthetic_not_actual_comparison"},
        "label_ledger": {"schema_version": "synthetic_not_human_labels"},
        "actual_evaluation_policy": fixture["policy"].to_dict(),
        "split_manifest": fixture["calibration_manifest"].to_dict(),
        "source_manifest": source["source_manifest"], "expected_universe": source["expected_universe"]}
    refs = {}
    for name, value in payloads.items():
        rows = name == "expected_universe"
        target = root / (name + (".jsonl" if rows else ".json"))
        target.write_bytes(b"".join(raw(r) + b"\n" for r in value) if rows else raw(value))
        refs[name] = ref(target, root)
    value = {"schema_version": workflow.BUNDLE_SCHEMA, **arm_refs, "actual_inputs": refs,
        "bootstrap": {"seed": 7, "replicates": 2000}}
    path = root / "actual_bundle.json"
    path.write_bytes(raw(value))
    return path, workflow.local._sha(path.read_bytes()), value


@pytest.fixture
def bundle(paired_semantic_bundle, tmp_path, monkeypatch):
    import socket
    from src.llm_batch.grounding import candidate_reranker_calibration as calibration
    from src.llm_batch.grounding import candidate_reranker_learned as learned
    from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
    fixture, artifact, baseline_fixture, baseline_artifact = paired_semantic_bundle
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("평가 중 외부 연결 금지"))
    for module, function in ((calibration, "fit_temperature"), (learned, "train_model"), (nil, "train_model")):
        monkeypatch.setattr(module, function, lambda *a, **k: pytest.fail("평가 중 FROZEN 재학습 금지"))
    return (*write_actual_bundle(tmp_path / "inputs", fixture, artifact,
        baseline_fixture=baseline_fixture, baseline_artifact=baseline_artifact), baseline_fixture)


def test_direct_cli_help_imports_from_its_own_repository():
    result = subprocess.run([sys.executable, str(Path(workflow.__file__).resolve()), "--help"],
        cwd=Path(workflow.__file__).resolve().parent.parent, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "--bundle-sha256" in result.stdout and "--output-dir" in result.stdout


def repin(path, value):
    path.write_bytes(raw(value))
    return workflow.local._sha(path.read_bytes())


def replace_arm(path, outer, arm, value):
    target = path.parent / outer[arm + "_bundle"]["path"]
    target.write_bytes(raw(value))
    outer[arm + "_bundle"] = ref(target, path.parent)
    return repin(path, outer)


def read_report(receipt):
    path = Path(receipt["evaluation_report"]["path"])
    return json.loads(path.read_bytes())


def test_cli_replays_both_semantic_alias_models_without_claiming_actual_gate(bundle, monkeypatch, capsys):
    path, pin, _, _ = bundle
    before = {p: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}
    monkeypatch.setattr(workflow, "_bound_actual", lambda *a, **k: pytest.fail("합성 자료의 actual 진입 금지"))
    output = path.parent / "evaluated"
    assert workflow.main(["--bundle", str(path), "--bundle-sha256", pin, "--output-dir", str(output)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    report = read_report(receipt)
    assert receipt["status"] == "SAVED_AND_READBACK_VERIFIED"
    assert receipt["report_status"] == report["status"] == "NOT_EVALUABLE"
    assert report["actual_readback"] is report["actual_gate_status"] is None
    assert report["actual_inputs_validation"] == "NOT_EXECUTED_ADMISSION_BLOCKED"
    assert report["local_score_replay_counts"] == {"after": 2, "baseline": 2}
    paired = json.loads(Path(report["pair_report"]["path"]).read_bytes())
    payloads = paired["artifact_payloads"]
    assert payloads["after_calibration_artifact"] != payloads["baseline_calibration_artifact"]
    assert payloads["after_score_vectors"] != payloads["baseline_score_vectors"]
    for name in ("after", "baseline"):
        artifact = json.loads((path.parent / name / "artifact.json").read_bytes())
        assert payloads[name + "_calibration_artifact"] == artifact
        assert all(v["scorer_fingerprint"] == artifact["scorer_fingerprint"]
            for v in payloads[name + "_score_vectors"])
    assert report["expected_count"] == 2
    assert {"AFTER_SYNTHETIC_NOT_ACTUAL", "BASELINE_SYNTHETIC_NOT_ACTUAL",
        "AFTER_HUMAN_LABELS_NOT_COMPLETE", "ACTUAL_POLICY_V4_NOT_PREREGISTERED"} <= set(report["reason_codes"])
    assert report["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert all(report[k] is False for k in ("quality_acceptance_claimed", "publication_authority", "public_apply",
        "central_db_write", "model_training_executed", "calibration_fit_executed", "thresholds_reselected"))
    for field in ("evaluation_report", "workflow_receipt"):
        r = receipt[field]; content = Path(r["path"]).read_bytes()
        assert len(content) == r["bytes"] and workflow.local._sha(content) == r["sha256"]
    assert report["report_sha256"] == workflow.local._sha(raw({k: v for k, v in report.items() if k != "report_sha256"}))
    assert not (output / ".pending_receipt.json").exists()
    assert not (output / "readback").exists()
    for p, content in before.items(): assert p.read_bytes() == content
    for key in ("pid", "priority_class", "affinity_mask", "logical_cpu_count", "numeric_threads"):
        assert report["resources_start"][key] == report["resources_end"][key]


def test_real_unexecuted_baseline_is_not_replaced_by_replayed_success(bundle):
    from src.llm_batch.runtime.candidate_reranker import export_candidate_reranker_fields
    path, _, outer, fixture = bundle
    arm = json.loads((path.parent / outer["baseline_bundle"]["path"]).read_bytes())
    binding = arm["observations"][0]["receipt"]["binding"]
    receipt = export_candidate_reranker_fields(None, fixture["scorer"], binding=binding)["candidate_reranker_shadow"]
    arm["observations"][0]["receipt"] = receipt
    arm["frozen_rows"] = arm["frozen_rows"][1:]
    pin = replace_arm(path, outer, "baseline", arm)
    stored = workflow.evaluate_actual_bundle(bundle_path=path, expected_sha256=pin, output_dir=path.parent / "out")
    report = read_report(stored)
    pair = json.loads(Path(report["pair_report"]["path"]).read_bytes())
    assert report["local_score_replay_counts"] == {"after": 2, "baseline": 1}
    assert report["expected_count"] == pair["expected_count"] == len(pair["per_row"]) == 2
    assert pair["per_row"][0]["baseline_terminal"] == "NOT_AVAILABLE"
    assert pair["artifact_payloads"] is None and report["actual_readback"] is None


@pytest.mark.parametrize("arm_name", ["after", "baseline"])
def test_resealed_scores_must_replay_same_pinned_model(bundle, arm_name):
    from src.llm_batch.grounding.candidate_reranker_shadow import canonical_sha256
    path, _, outer, _ = bundle
    arm = json.loads((path.parent / outer[arm_name + "_bundle"]["path"]).read_bytes())
    receipt = arm["observations"][0]["receipt"]
    receipt["event_logits"][0]["score"] += 0.125
    receipt["receipt_sha256"] = canonical_sha256({k: v for k, v in receipt.items()
        if k not in {"receipt_sha256", "latency_ms", "binding"}})
    pin = replace_arm(path, outer, arm_name, arm)
    output = path.parent / "out"
    with pytest.raises(ValueError):
        workflow.evaluate_actual_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize("fault", ["pin", "path", "absolute", "bool_seed", "small_bootstrap", "large_bootstrap",
    "missing_baseline", "duplicate_json", "nonfinite", "missing_middle_observation", "reordered_universe"])
def test_invalid_pins_paths_scope_or_denominator_fail_before_output(bundle, fault):
    path, pin, outer, _ = bundle
    if fault == "pin": pin = "0" * 64
    elif fault == "path": outer["after_bundle"]["path"] = "../outside.json"
    elif fault == "absolute": outer["after_bundle"]["path"] = str(path.parent / "after/bundle.json")
    elif fault == "bool_seed": outer["bootstrap"]["seed"] = True
    elif fault == "small_bootstrap": outer["bootstrap"]["replicates"] = 1999
    elif fault == "large_bootstrap": outer["bootstrap"]["replicates"] = 10001
    elif fault == "missing_baseline": del outer["baseline_bundle"]
    elif fault in ("duplicate_json", "nonfinite"):
        content = raw(outer)[:-1] + (b',"schema_version":"duplicate"}' if fault == "duplicate_json" else b',"extra":NaN}')
        path.write_bytes(content); pin = workflow.local._sha(content)
    elif fault == "missing_middle_observation":
        arm = json.loads((path.parent / outer["baseline_bundle"]["path"]).read_bytes())
        arm["observations"].pop(0); pin = replace_arm(path, outer, "baseline", arm)
    else:
        target = path.parent / outer["actual_inputs"]["expected_universe"]["path"]
        rows = [json.loads(line) for line in target.read_bytes().splitlines()]
        target.write_bytes(b"".join(raw(r) + b"\n" for r in reversed(rows)))
        outer["actual_inputs"]["expected_universe"] = ref(target, path.parent)
    if fault not in ("pin", "duplicate_json", "nonfinite", "missing_middle_observation"):
        pin = repin(path, outer)
    output = path.parent / "out"
    with pytest.raises((ValueError, KeyError)):
        workflow.evaluate_actual_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert not output.exists()


def test_existing_output_is_not_overwritten_or_scored(bundle, monkeypatch):
    path, pin, _, _ = bundle
    output = path.parent / "out"; output.mkdir(); sentinel = output / "keep.bin"; sentinel.write_bytes(b"keep")
    monkeypatch.setattr(workflow, "_load_arm", lambda *a, **k: pytest.fail("기존 출력 검사 뒤 모델 실행 금지"))
    with pytest.raises(ValueError, match="OUTPUT_MUST_BE_NEW"):
        workflow.evaluate_actual_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert list(output.iterdir()) == [sentinel] and sentinel.read_bytes() == b"keep"


def test_final_receipt_readback_failure_leaves_no_success_marker(bundle, monkeypatch):
    path, pin, _, _ = bundle
    original = workflow.local._write
    def fail_final(path, value):
        result = original(path, value)
        if path.name == ".pending_receipt.json":
            raise OSError("injected final raw readback failure")
        return result
    monkeypatch.setattr(workflow.local, "_write", fail_final)
    output = path.parent / "out"
    with pytest.raises(OSError, match="final raw readback failure"):
        workflow.evaluate_actual_bundle(bundle_path=path, expected_sha256=pin, output_dir=output)
    assert not (output / "workflow_receipt.json").exists()
    assert (output / ".pending_receipt.json").is_file()
    report = json.loads((output / "evaluation_report.json").read_bytes())
    assert report["status"] == "NOT_EVALUABLE"


def test_pinned_transitive_legacy_references_are_read_only_and_reject_escape(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    data = root / "data.json"; data.write_bytes(raw({"value": 1}))
    snapshots = {}
    pinned = {"path": str(data), "sha256": workflow.local._sha(data.read_bytes()), "bytes": data.stat().st_size}
    workflow._pin_legacy_closure({"ref": pinned}, artifact_root=root, snapshots=snapshots)
    assert snapshots[str(data)] == data.read_bytes()
    data.write_bytes(raw({"value": 2}))
    with pytest.raises(ValueError, match="LEGACY_REF_PIN_MISMATCH"):
        workflow._pin_legacy_closure({"ref": pinned}, artifact_root=root, snapshots={})
    outside = tmp_path / "outside.json"; outside.write_bytes(b"{}")
    pinned = {"path": str(outside), "sha256": workflow.local._sha(b"{}"), "bytes": 2}
    with pytest.raises(ValueError, match="LEGACY_REF_OUTSIDE_ARTIFACT_ROOT"):
        workflow._pin_legacy_closure({"ref": pinned}, artifact_root=root, snapshots={})


@pytest.mark.parametrize("content", [b'{"a":1,"a":2}', b'[NaN]'])
def test_transitive_json_does_not_accept_duplicate_keys_or_nonfinite(tmp_path, content):
    path = tmp_path / "bad.json"; path.write_bytes(content)
    value = {"path": str(path), "sha256": workflow.local._sha(content), "bytes": len(content)}
    with pytest.raises(ValueError):
        workflow._pin_legacy_closure(value, artifact_root=tmp_path, snapshots={})


def test_literal_source_bytes_are_archived_for_json_only_actual_reader(tmp_path):
    import base64
    from src.llm_batch.grounding import calibration_actual_readback as readback
    source = tmp_path / "원문.bin"
    content = "나는 합성소설을 읽었다.\n원본 바이트 보존".encode("utf-8")
    source.write_bytes(content)
    output = tmp_path / "new"; output.mkdir()
    refs = workflow._archive_inputs(root=tmp_path, output=output,
        snapshots={str(source): content}, used_paths=set())
    assert len(refs) == 1
    name, path = refs[0]
    stored = readback.snapshot_artifact(tmp_path, name, path)
    value = json.loads((tmp_path / stored.relative_path).read_bytes())
    assert base64.b64decode(value["payload_base64"], validate=True) == source.read_bytes() == content
    assert value["raw_sha256"] == workflow.local._sha(content) and value["raw_bytes"] == len(content)
    assert value["original_relative_path"] == source.name
    assert value["archive_sha256"] == workflow.local._sha(raw({k: v for k, v in value.items() if k != "archive_sha256"}))
    with pytest.raises(FileExistsError):
        workflow._archive_inputs(root=tmp_path, output=output, snapshots={str(source): content}, used_paths=set())


@pytest.mark.parametrize("terminal", ["EMPTY", "TRUNCATED", "GOLD_MISS"])
def test_cli_terminal_baseline_retains_whole_pair_without_inventing_nil(plain_bundle, tmp_path, terminal):
    fixture, artifact = plain_bundle
    path, _, outer = write_actual_bundle(tmp_path / "terminal-inputs", fixture, artifact)
    arms = terminal_pair(plain_bundle, terminal, "baseline")
    arm = arms["baseline"]
    target = path.parent / outer["baseline_bundle"]["path"]
    stored = json.loads(target.read_bytes())
    stored.update(expected_rows=arm.expected_rows, observations=arm.observations,
        frozen_rows=[pair.nil_eval._graph_payload(g) for g in arm.frozen_rows])
    for digest, content in arm.evidence_payloads.items():
        if digest in stored["evidence_files"]:
            continue
        evidence_path = target.parent / "evidence" / (digest + ".bin")
        with evidence_path.open("xb") as stream: stream.write(content)
        stored["evidence_files"][digest] = ref(evidence_path, target.parent)
    pin = replace_arm(path, outer, "baseline", stored)
    receipt = workflow.evaluate_actual_bundle(bundle_path=path, expected_sha256=pin, output_dir=path.parent / "out")
    report = read_report(receipt)
    paired = json.loads(Path(report["pair_report"]["path"]).read_bytes())
    assert report["expected_count"] == paired["expected_count"] == len(paired["per_row"]) == 2
    assert report["local_score_replay_counts"] == {"after": 2, "baseline": 2 if terminal == "GOLD_MISS" else 1}
    assert report["actual_readback"] is paired["artifact_payloads"] is None
    assert report["actual_inputs_validation"] == "NOT_EXECUTED_ADMISSION_BLOCKED"
    row = paired["baseline_report"]["rows"][0]
    assert row["calibration_shadow"] is None and row["truth_kind"] == "CANDIDATE"
    assert row["action"] != "ASSERT_NIL"
    if terminal == "GOLD_MISS":
        assert row["gold_present"] is False
        assert "GOLD_CANDIDATE_NOT_RETRIEVED" in row["calibration_reason_codes"]
    else:
        assert stored["observations"][0]["receipt"]["nil_score"] is None
        assert stored["observations"][0]["receipt"]["event_logits"] == []


def test_bound_actual_reaches_real_p1_readiness_rejection_and_preserves_saved_graph(paired_semantic_bundle):
    """합성 P1은 준비도 0/18에서 거절된다. actual 성공을 mock하거나 등급을 바꾸지 않는다."""
    import base64
    from tests.candidate_shadow_graph_fixture import new_graph_directory, build_current_shadow_graph
    from tests.test_calibration_dataset_readiness import CalibrationDatasetReadinessTests
    from tools.run_calibration_dataset_readiness import build_current_readiness
    from tools import run_candidate_set_calibration_shadow_harness as legacy_runner
    from src.llm_batch.grounding import calibration_actual_readback as readback
    af, aa, bf, ba = paired_semantic_bundle
    with new_graph_directory() as temporary:
        root = Path(temporary)
        graph = build_current_shadow_graph(root, include_calibration=False)
        # 기존 readiness 음성시험의 사전등록 형식 policy다. 합성 모델/fit/라벨은 변경하지 않는다.
        negative_policy = CalibrationDatasetReadinessTests._actual_policy()
        policy_path = root / "negative_actual_policy.json"
        policy_path.write_bytes(raw(negative_policy.to_dict()))
        readiness = build_current_readiness(p1_run_spec_path=graph.p1,
            p1_comparison_path=graph.p1_comparison, label_ledger_path=graph.ledger,
            actual_evaluation_policy_path=policy_path)
        assert readiness["ready_for_split_manifest"] is False
        assert readiness["counts"]["source_rows"] == 18 and readiness["counts"]["ready_rows"] == 0
        assert readiness["counts"]["unjudged"] == 3
        path, _, outer = write_actual_bundle(root, af, aa,
            baseline_fixture=bf, baseline_artifact=ba, existing_root=True)
        for name, file in (("p1_run_spec", graph.p1), ("p1_comparison", graph.p1_comparison),
                ("label_ledger", graph.ledger), ("actual_evaluation_policy", policy_path)):
            outer["actual_inputs"][name] = ref(file, root)
        pin = repin(path, outer)
        loaded = workflow.read_actual_bundle(path, expected_sha256=pin)
        a = arm_for(af, aa)
        paired = pair.prepare_actual_pair(after=a, baseline=arm_for(bf, ba), **source_inputs(a))
        assert paired["actual_admission_reasons"]  # 상위 CLI는 이 자료의 actual 진입을 허용하지 않는다.
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        output = root / "negative-bound-output"; output.mkdir()
        with pytest.raises(ValueError, match=r"NO_GO_ACTUAL_DATASET_NOT_READY: ready_rows=0/18"):
            workflow._bound_actual(loaded, paired, output)
        refs = {}
        for name, payload in paired["artifact_payloads"].items():
            is_rows = type(payload) is list
            stored_path = output / (name + (".jsonl" if is_rows else ".json"))
            content = stored_path.read_bytes()
            recovered = [json.loads(line) for line in content.splitlines()] if is_rows else json.loads(content)
            assert recovered == payload
            refs[name] = readback.snapshot_artifact(root, name, stored_path.relative_to(root).as_posix(), jsonl=is_rows)
        # 거절 경로에서 저장한 아홉 artifact를 기존 parser로 검산한다. actual 수용과 구분한다.
        legacy_runner._validate_actual_replay_bundle(root=root, refs=refs,
            frozen=[v for v in a.calibration_manifest.assignments if v.split == "FROZEN_HOLDOUT"],
            split_manifest=a.calibration_manifest, policy=a.policy,
            prediction_rows=paired["artifact_payloads"]["prediction"],
            baseline_rows=paired["artifact_payloads"]["baseline_prediction"])
        archives = list(output.glob("bridge_input_archive_*.json"))
        assert archives
        for archive in archives:
            value = json.loads(archive.read_bytes())
            original = root / value["original_relative_path"]
            content = base64.b64decode(value["payload_base64"], validate=True)
            assert content == before[original] == original.read_bytes()
            assert len(content) == value["raw_bytes"] and workflow.local._sha(content) == value["raw_sha256"]
        assert not (output / "readback").exists()
        assert not (output / "workflow_receipt.json").exists()
        for file, content in before.items(): assert file.read_bytes() == content
