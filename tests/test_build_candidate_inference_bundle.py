"""기존 학습 근거를 새 bundle로 묶을 때 원본·출력 보존과 잘못된 참조 거절."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools import build_candidate_inference_bundle as builder
from src.llm_batch.runtime import candidate_inference as runtime
from tests.candidate_inference_fixtures import build_candidate_inference_fixture, raw, sha


@pytest.fixture(scope="module")
def fixture(tmp_path_factory):
    return build_candidate_inference_fixture(tmp_path_factory.mktemp("inference-bundle"))


def test_builder_reuses_fitted_artifact_without_training_or_modifying_inputs(fixture, tmp_path, monkeypatch):
    from src.llm_batch.grounding import candidate_reranker_calibration as cal
    from src.llm_batch.grounding import candidate_reranker_nil_learned as nil
    monkeypatch.setattr(cal, "fit_temperature", lambda *a, **k: pytest.fail("builder fit"))
    monkeypatch.setattr(nil, "train_model", lambda *a, **k: pytest.fail("builder train"))
    monkeypatch.setattr(type(fixture["scorer"]), "score", lambda *a, **k: pytest.fail("builder score"))
    before = {p: Path(p).read_bytes() for p in fixture["input_paths"]}
    receipt = builder.build_bundle(**fixture["spec"], output_dir=tmp_path / "new")
    assert receipt["status"] == "PASS" and receipt["new_temperature_fit_calls"] == receipt["score_calls"] == 0
    assert receipt["calibration_numeric_replay_performed"] is True
    values = runtime.read_inference_bundle(receipt["bundle_path"], expected_sha256=receipt["bundle_sha256"])
    assert values["artifact"] == fixture["artifact"].to_dict()
    assert values["corpus_snapshot"] == fixture["corpus_snapshot"] and values["source_payloads"] == fixture["source_payloads"]
    assert {p: Path(p).read_bytes() for p in before} == before
    with pytest.raises(FileExistsError):
        builder.build_bundle(**fixture["spec"], output_dir=tmp_path / "new")
    assert json.loads((tmp_path / "new" / "build_receipt.json").read_bytes()) == receipt


@pytest.mark.parametrize("fault", ["artifact_sha", "missing_source", "source_key", "model_summary"])
def test_invalid_inputs_fail_before_creating_success_output(fixture, tmp_path, fault):
    spec = deepcopy(fixture["spec"])
    if fault == "artifact_sha": spec["artifact"]["sha256"] = "0" * 64
    elif fault == "missing_source": spec["source_files"] = {}
    elif fault == "source_key": spec["source_files"] = {"0" * 64: next(iter(spec["source_files"].values()))}
    else:
        summary = deepcopy(fixture["scorer_summary"]); summary["model_sha256"] = "0" * 64
        payload = raw(summary); path = tmp_path / "foreign-summary.json"; path.write_bytes(payload)
        spec["scorer_summary"] = {"path": str(path), "sha256": sha(payload), "bytes": len(payload)}
    with pytest.raises(ValueError):
        builder.build_bundle(**spec, output_dir=tmp_path / "new")
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("fault", ["escape", "absolute", "wrong_size", "duplicate_json"])
def test_runtime_loader_strict_pinned_relative_references(fixture, tmp_path, fault):
    folder = Path(fixture["settings"]["bundle_path"]).parent
    for source in folder.iterdir():
        if source.is_file():
            (tmp_path / source.name).write_bytes(source.read_bytes())
    bundle = json.loads((tmp_path / "bundle.json").read_bytes())
    if fault == "escape": bundle["artifact"]["path"] = "../artifact.json"
    elif fault == "absolute": bundle["artifact"]["path"] = str(folder / "artifact.json")
    elif fault == "wrong_size": bundle["artifact"]["bytes"] -= 1
    payload = raw(bundle)
    if fault == "duplicate_json": payload = payload[:-1] + b',"schema_version":"candidate_inference_runtime_bundle_v1"}'
    path = tmp_path / "mutated.json"; path.write_bytes(payload)
    with pytest.raises(ValueError):
        runtime.read_inference_bundle(path, expected_sha256=sha(payload))


def test_cli_spec_is_pinned_and_build_failure_has_no_success_receipt(fixture, tmp_path, monkeypatch):
    spec = tmp_path / "spec.json"; payload = raw(fixture["spec"]); spec.write_bytes(payload)
    with pytest.raises(ValueError, match="spec SHA"):
        builder.main(["--spec", str(spec), "--spec-sha256", "0" * 64, "--output-dir", str(tmp_path / "new")])
    from tools import run_candidate_reranker_training as local
    original = local._write
    def broken(path, value):
        if path.name == "bundle.json": raise OSError("simulated write failure")
        return original(path, value)
    monkeypatch.setattr(local, "_write", broken)
    with pytest.raises(OSError):
        builder.main(["--spec", str(spec), "--spec-sha256", sha(payload), "--output-dir", str(tmp_path / "new")])
    assert not (tmp_path / "new" / "build_receipt.json").exists()
