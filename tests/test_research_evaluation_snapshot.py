from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
from llm_batch.measurement import research_evaluation_snapshot as snapshot


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _dump(path, value):
    raw = snapshot.canonical_bytes(value) + b"\n"
    path.write_bytes(raw)
    return {"path": str(path), "sha256": _sha(raw)}


def _row(post=11, index=1, run="run-a"):
    coordinate = {"post_id": post, "input_index": index, "attempt_run_id": run,
                  "row_attempt_id": f"{run}-{post}", "publication_scope_id": "a" * 64}
    return {
        "post_id": post, "title": "원문 작품명", "content": "본문", "comments": [],
        "analysis_result": {
            "identity": {"official_title": None, "official_url": None},
            "analysis": {"is_nsfw": False, "score": 0, "reason": None,
                         "candidate_set_shadow": {"generation_status": "TRUNCATED",
                                                  "probability": None}},
        },
        "run_meta": {
            "run_id": run,
            "decision_call_attempt_receipt": {"row": coordinate,
                                            "publication_link_status": "PENDING_EXTERNAL_LEDGER_LINK"},
            "decision_call_ledger": {"publication_scope_id": "a" * 64, "row": deepcopy(coordinate)},
            "decision_call_ledger_summary": {"actual_kpi_status": "PENDING_INDEPENDENT_READBACK",
                                             "actual_metrics": None, "calls": 0},
        },
    }


def _dataset(tmp_path, *, did="one", posts=(11,), run="run-a", kind="SAVED_ARTIFACT"):
    result = [_row(post, index, run) for index, post in enumerate(posts, 1)]
    inputs = [{"post_id": post, "title": "원문 작품명"} for post in posts]
    result_path = tmp_path / f"{did}_result.json"
    manifest_path = tmp_path / f"{did}_manifest.json"
    input_path = tmp_path / f"{did}_input.json"
    input_raw = snapshot.canonical_bytes(inputs) + b"\n"
    manifest = {"run_id": run, "output_file": str(result_path), "input_file": str(input_path),
                "publication_input_snapshot_sha256": _sha(input_raw),
                "publication_scope_id": "a" * 64, "input_post_count": len(posts),
                "flushed_count": len(posts), "completed_count": len(posts),
                "failed_count": 0, "pending_count": 0,
                "publication_release_fingerprint": "b" * 64,
                "decision_call_ledger_summary": {"actual_kpi_status": "NOT_ESTIMABLE",
                                                "linked_row_attempt_count": len(posts)}}
    values = {"result": result, "manifest": manifest, "input": inputs}
    paths = {"result": result_path, "manifest": manifest_path, "input": input_path}
    refs = {}
    for key in values:
        raw = snapshot.canonical_bytes(values[key]) + b"\n"
        refs[key] = {"path": str(paths[key]), "sha256": _sha(raw), "bytes": len(raw)}
    return {"dataset_id": did, "sample_namespace": "dc-fixture", "data_kind": kind,
            "source_refs": refs, **values}


def _write_request(tmp_path, dataset=None):
    dataset = deepcopy(dataset or _dataset(tmp_path))
    record = {key: dataset[key] for key in ("dataset_id", "sample_namespace", "data_kind")}
    for kind in ("result", "manifest", "input", "reference"):
        if kind in dataset:
            ref = dataset["source_refs"][kind]
            record[kind] = _dump(Path(ref["path"]), dataset[kind])
    request = {"schema_version": snapshot.REQUEST_SCHEMA, "datasets": [record]}
    path = tmp_path / "request.json"
    _dump(path, request)
    return path, request


def _codes(built):
    return {issue["code"] for issue in built["issues"]}


def test_valid_snapshot_preserves_original_and_separates_measurement(tmp_path):
    dataset = _dataset(tmp_path, posts=(11, 12))
    before = deepcopy(dataset)
    built = snapshot.build_evaluation_snapshot([dataset])
    assert dataset == before
    assert built["binding_status"] == "COMPLETE_WITH_LIMITS"
    assert built["rows"][0]["saved_row"] == dataset["result"][0]
    assert built["rows"][0]["row_measurement"]["decision_call_ledger_summary"]["value"]["actual_kpi_status"] == "PENDING_INDEPENDENT_READBACK"
    assert built["datasets"][0]["manifest_observation"]["decision_call_ledger_summary"]["value"]["actual_kpi_status"] == "NOT_ESTIMABLE"
    assert built["formal_kpi_status"] == "NOT_ESTIMABLE"
    assert built["publication_authority"] is False
    assert built["rows"][0]["candidate_recall"]["value"] is None


def test_missing_false_zero_null_and_old_source_are_not_filled(tmp_path):
    dataset = _dataset(tmp_path)
    dataset["result"][0].pop("run_meta")
    built = snapshot.build_evaluation_snapshot([dataset])
    row = built["rows"][0]
    assert row["saved_row"]["analysis_result"]["analysis"] == dataset["result"][0]["analysis_result"]["analysis"]
    assert row["row_measurement"]["source_context_diagnostics"] == {"present": False, "value": None}
    assert snapshot.present({"value": False}, "value") == {"present": True, "value": False}
    assert snapshot.present({"value": 0}, "value") == {"present": True, "value": 0}
    assert snapshot.present({"value": None}, "value") == {"present": True, "value": None}
    assert "ROW_RUN_ID_MISSING" in _codes(built)
    assert "ROW_ATTEMPT_ID_MISSING" in _codes(built)
    observation = built["datasets"][0]["manifest_observation"]
    assert observation["runtime_source_sha256"] == {"present": False, "value": None}
    assert observation["publication_release_fingerprint"]["value"] == "b" * 64


@pytest.mark.parametrize("mutation,code", [
    ("run", "ROW_RUN_ID_MISMATCH"),
    ("attempt", "LEDGER_RECEIPT_COORDINATE_MISMATCH"),
    ("scope", "ROW_PUBLICATION_SCOPE_MISMATCH"),
    ("input_sha", "MANIFEST_INPUT_SHA256_MISMATCH"),
    ("path", "MANIFEST_OUTPUT_PATH_MISMATCH"),
    ("order", "RESULT_INPUT_ORDER_MISMATCH"),
    ("post", "FIXED_INPUT_POST_ID_MISMATCH"),
    ("index_bool", "INPUT_INDEX_INVALID"),
])
def test_cross_bindings_are_invalid(tmp_path, mutation, code):
    dataset = _dataset(tmp_path, posts=(11, 12))
    row = dataset["result"][0]
    if mutation == "run":
        row["run_meta"]["run_id"] = "foreign"
    elif mutation == "attempt":
        row["run_meta"]["decision_call_ledger"]["row"]["row_attempt_id"] = "foreign"
    elif mutation == "scope":
        row["run_meta"]["decision_call_attempt_receipt"]["row"]["publication_scope_id"] = "c" * 64
    elif mutation == "input_sha":
        dataset["manifest"]["publication_input_snapshot_sha256"] = "0" * 64
    elif mutation == "path":
        dataset["manifest"]["output_file"] = str(tmp_path / "foreign.json")
    elif mutation == "order":
        dataset["result"].reverse()
    elif mutation == "post":
        dataset["input"][0]["post_id"] = 99
    else:
        row["run_meta"]["decision_call_attempt_receipt"]["row"]["input_index"] = True
    built = snapshot.build_evaluation_snapshot([dataset])
    assert built["binding_status"] == "INVALID_BINDING"
    assert code in _codes(built)


def test_duplicates_and_missing_rows_remain_visible(tmp_path):
    dataset = _dataset(tmp_path, posts=(11, 12, 13))
    dataset["result"] = [dataset["result"][0], deepcopy(dataset["result"][0])]
    dataset["manifest"]["flushed_count"] = 2
    built = snapshot.build_evaluation_snapshot([dataset])
    assert {"DUPLICATE_POST_ID", "DUPLICATE_INPUT_INDEX", "DUPLICATE_ROW_ATTEMPT_ID"} <= _codes(built)
    counts = built["datasets"][0]["denominators"]
    assert counts["saved_observation_count"] == 2
    assert counts["missing_saved_row_count"] == 1
    assert counts["fixed_input_indexes_without_bound_result"] == [2, 3]
    assert counts["failed_count"] == {"present": True, "value": 0}


@pytest.mark.parametrize("field,foreign,code", [
    ("attempt_run_id", "foreign-run", "LEDGER_RUN_ID_MISMATCH"),
    ("post_id", 999, "LEDGER_POST_ID_MISMATCH"),
    ("input_index", 999, "LEDGER_INPUT_INDEX_OUT_OF_RANGE"),
])
def test_missing_receipt_field_cannot_hide_ledger_contradiction(tmp_path, field, foreign, code):
    dataset = _dataset(tmp_path)
    meta = dataset["result"][0]["run_meta"]
    del meta["decision_call_attempt_receipt"]["row"][field]
    meta["decision_call_ledger"]["row"][field] = foreign
    built = snapshot.build_evaluation_snapshot([dataset])
    assert built["binding_status"] == "INVALID_BINDING"
    assert code in _codes(built)


def test_overlap_runs_keep_run_and_unique_denominators(tmp_path):
    parent = _dataset(tmp_path, did="original80_like", posts=(11, 12), run="run-parent")
    child = _dataset(tmp_path, did="followup32_like", posts=(11,), run="run-child")
    child["parent_dataset_id"] = parent["dataset_id"]
    synthetic = _dataset(tmp_path, did="synthetic", posts=(11,), run="run-synthetic", kind="SYNTHETIC_FIXTURE")
    built = snapshot.build_evaluation_snapshot([parent, child, synthetic])
    counts = built["denominators_by_data_kind"]["SAVED_ARTIFACT"]
    assert counts["saved_observation_count"] == 3
    assert counts["unique_post_count"] == 2
    assert counts["unique_source_material_count"] == 2
    assert counts["independent_sample_count"] is None
    assert built["denominators_by_data_kind"]["SYNTHETIC_FIXTURE"]["saved_observation_count"] == 1
    assert [item["denominators"]["input_count"] for item in built["datasets"]] == [2, 1, 1]


def test_duplicate_artifact_not_disguised_as_second_dataset(tmp_path):
    first = _dataset(tmp_path)
    second = deepcopy(first)
    second["dataset_id"] = "second"
    assert "DUPLICATE_RESULT_ARTIFACT" in _codes(snapshot.build_evaluation_snapshot([first, second]))
    second["dataset_id"] = "one"
    with pytest.raises(snapshot.SnapshotError, match="duplicate dataset"):
        snapshot.build_evaluation_snapshot([first, second])


def test_reference_binding_does_not_create_gold_or_recall(tmp_path):
    dataset = _dataset(tmp_path)
    reference = {"schema_version": snapshot.REFERENCE_SCHEMA, "result_sha256": dataset["source_refs"]["result"]["sha256"],
                 "run_id": "run-a", "rows": [{"input_index": 1, "post_id": 11, "reference_kind": "MODEL_REFERENCE",
                                             "truth_kind": "WORK", "truth_candidate_id": "work-one"}]}
    dataset["reference"] = reference
    raw = snapshot.canonical_bytes(reference)
    dataset["source_refs"]["reference"] = {"path": str(tmp_path / "reference.json"), "sha256": _sha(raw), "bytes": len(raw)}
    built = snapshot.build_evaluation_snapshot([dataset])
    assert built["rows"][0]["reference"]["reference_kind"] == "MODEL_REFERENCE"
    assert built["rows"][0]["reference"]["authority_status"] == "CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED"
    assert built["rows"][0]["candidate_recall"]["value"] is None
    dataset["reference"]["run_id"] = "foreign"
    broken = snapshot.build_evaluation_snapshot([dataset])
    assert broken["binding_status"] == "INVALID_BINDING"
    assert broken["rows"][0]["reference"]["reference_kind"] == "UNJUDGED"


def test_export_new_output_sources_unchanged_and_semantic_deterministic(tmp_path, monkeypatch):
    def forbid_network(*args, **kwargs):
        raise AssertionError("network forbidden")
    monkeypatch.setattr(socket, "socket", forbid_network)
    spec_path, request = _write_request(tmp_path)
    inputs = [spec_path] + [Path(ref["path"]) for ref in request["datasets"][0].values() if isinstance(ref, dict)]
    before = {path: path.read_bytes() for path in inputs}
    one = snapshot.export_snapshot(spec_path, tmp_path / "one", research_root=tmp_path,
                                   snapshot_id="one", created_at="first")
    two = snapshot.export_snapshot(spec_path, tmp_path / "two", research_root=tmp_path,
                                   snapshot_id="two", created_at="second")
    assert one["semantic_sha256"] == two["semantic_sha256"]
    assert one["manifest_sha256"] != two["manifest_sha256"]
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert one["byte_readback_status"] == "VERIFIED_START_END"
    assert snapshot.verify_exported_snapshot(tmp_path / "one")["status"] == "VERIFIED"
    with pytest.raises(snapshot.SnapshotError, match="already exists"):
        snapshot.export_snapshot(spec_path, tmp_path / "one", research_root=tmp_path)


def test_hash_drift_and_output_escape_rejected_before_write(tmp_path):
    spec_path, request = _write_request(tmp_path)
    source = Path(request["datasets"][0]["result"]["path"])
    source.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(snapshot.SnapshotError, match="SHA256 mismatch"):
        snapshot.export_snapshot(spec_path, tmp_path / "refused", research_root=tmp_path)
    assert not (tmp_path / "refused").exists()
    with pytest.raises(snapshot.SnapshotError, match="strict child"):
        snapshot.export_snapshot(spec_path, tmp_path.parent / "escape", research_root=tmp_path)


def test_source_change_during_write_never_produces_final_manifest(tmp_path, monkeypatch):
    spec_path, request = _write_request(tmp_path)
    source = Path(request["datasets"][0]["result"]["path"])
    original_write = snapshot._write_new
    def tampering_write(path, data):
        receipt = original_write(path, data)
        if path.name == "report_ko.md":
            source.write_bytes(source.read_bytes() + b" ")
        return receipt
    monkeypatch.setattr(snapshot, "_write_new", tampering_write)
    with pytest.raises(snapshot.SnapshotError, match="source changed"):
        snapshot.export_snapshot(spec_path, tmp_path / "interrupted", research_root=tmp_path)
    assert not (tmp_path / "interrupted" / "snapshot_manifest.json").exists()


@pytest.mark.parametrize("target", ["rows.jsonl", "snapshot_manifest.json"])
def test_verifier_rejects_tampering(tmp_path, target):
    spec_path, _ = _write_request(tmp_path)
    output = tmp_path / "output"
    snapshot.export_snapshot(spec_path, output, research_root=tmp_path)
    path = output / target
    if target == "rows.jsonl":
        path.write_bytes(path.read_bytes() + b" ")
    else:
        value = json.loads(path.read_bytes())
        value["publication_authority"] = True
        path.write_bytes(snapshot.canonical_bytes(value))
    with pytest.raises(snapshot.SnapshotError, match="hash mismatch"):
        snapshot.verify_exported_snapshot(output)


def test_strict_json_rejects_duplicates_nonfinite(tmp_path):
    for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
        with pytest.raises(snapshot.SnapshotError):
            snapshot._strict_json(raw, "fixture")


def test_jsonl_post_comment_order_raw_sha_and_scope_binding(tmp_path):
    dataset = _dataset(tmp_path, posts=(11, 12))
    spec_path, request = _write_request(tmp_path, dataset)
    comment_first = {"post_id": 12, "comment_id": "c2", "content": "먼저 기록된 댓글"}
    values = [comment_first, {"post_id": 11, "title": "첫 게시글"},
              {"post_id": 11, "comment_id": "c1", "content": "댓글"},
              {"post_id": 12, "title": "둘째 게시글"}]
    raw_lines = [json.dumps(value, ensure_ascii=False).encode("utf-8") for value in values]
    raw = b"\r\n".join(raw_lines) + b"\r\n"
    input_path = tmp_path / "original.jsonl"
    input_path.write_bytes(raw)
    request["datasets"][0]["input"] = {"path": str(input_path), "sha256": _sha(raw), "format": "JSONL_POST_COMMENT_V1"}
    manifest_path = Path(request["datasets"][0]["manifest"]["path"])
    manifest = dataset["manifest"]
    manifest["input_file"] = str(input_path)
    manifest["publication_input_snapshot_sha256"] = _sha(raw)
    request["datasets"][0]["manifest"] = _dump(manifest_path, manifest)
    _dump(spec_path, request)
    prepared, _ = snapshot.load_request(spec_path)
    built = snapshot.build_evaluation_snapshot(prepared)
    assert built["binding_status"] == "COMPLETE_WITH_LIMITS"
    assert [row["post_id"] for row in prepared[0]["input"]] == [11, 12]
    raw_binding = built["rows"][1]["fixed_input_raw_records"]
    assert raw_binding["post"]["line_number"] == 4
    assert raw_binding["comments"][0]["payload"] == comment_first
    assert raw_binding["comments"][0]["raw_line_sha256"] == _sha(raw_lines[0])


@pytest.mark.parametrize("lines", [
    [{"post_id": 1}, {"post_id": 1}],
    [{"post_id": 1}, {"post_id": 1, "comment_id": 2}, {"post_id": 1, "comment_id": 2}],
    [{"post_id": 1}, {"post_id": 999, "comment_id": 2}],
])
def test_jsonl_duplicate_or_orphan_records_rejected(lines):
    raw = b"\n".join(snapshot.canonical_bytes(line) for line in lines)
    with pytest.raises(snapshot.SnapshotError):
        snapshot._parse_jsonl_input(raw, "fixture")


def test_cli_export_and_verify_exit_codes(tmp_path, capsys, monkeypatch):
    # Import the adjacent CLI in-process; no external service or pipeline import.
    monkeypatch.syspath_prepend(str(REPO_ROOT / "src"))
    cli_spec = importlib.util.spec_from_file_location("r1_snapshot_cli", REPO_ROOT / "tools" / "build_research_evaluation_snapshot.py")
    cli = importlib.util.module_from_spec(cli_spec)
    cli_spec.loader.exec_module(cli)
    request, _ = _write_request(tmp_path)
    output = tmp_path / "cli"
    assert cli.main(["--spec", str(request), "--output-dir", str(output), "--research-root", str(tmp_path)]) == 0
    assert cli.main(["--verify-dir", str(output)]) == 0
    assert "VERIFIED" in capsys.readouterr().out
    assert cli.main(["--spec", str(request), "--output-dir", str(output), "--research-root", str(tmp_path)]) == 1

