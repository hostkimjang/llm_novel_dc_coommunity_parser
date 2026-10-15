"""고정 로컬 NIL/CAL 양쪽 관측을 재생하고 기존 actual 파일 게이트로 연결한다."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_candidate_reranker_evaluation as descriptive
from tools import run_candidate_reranker_calibration as saved
from tools import run_candidate_reranker_training as local

BUNDLE_SCHEMA = "candidate_reranker_actual_evaluation_bundle_v1"
REPORT_SCHEMA = "candidate_reranker_actual_evaluation_workflow_v1"
ACTUAL_NAMES = ("p1_run_spec", "p1_comparison", "label_ledger", "actual_evaluation_policy",
                "split_manifest", "source_manifest", "expected_universe")
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = 24 * 1024 * 1024


def _require(condition, message):
    local._require(condition, message)


def _jsonl(raw):
    _require(bool(raw) and len(raw) <= local.MAX_BUNDLE_BYTES, "JSONL_BYTES_LIMIT")
    lines = raw.splitlines()
    _require(0 < len(lines) <= descriptive.MAX_ROWS and all(line.strip() for line in lines), "JSONL_ROW_LIMIT")
    return [local._strict_json(line) for line in lines]


def read_actual_bundle(bundle_path, *, expected_sha256):
    path = local._local_path(bundle_path)
    _require(local._hex(expected_sha256), "BUNDLE_PIN_REQUIRED")
    raw = local._read(path, local.MAX_BUNDLE_BYTES)
    _require(local._sha(raw) == expected_sha256, "BUNDLE_PIN_MISMATCH")
    value = local._strict_json(raw)
    _require(set(value) == {"schema_version", "after_bundle", "baseline_bundle", "actual_inputs", "bootstrap"}
        and value["schema_version"] == BUNDLE_SCHEMA, "ACTUAL_BUNDLE_SCHEMA")
    _require(type(value["actual_inputs"]) is dict and set(value["actual_inputs"]) == set(ACTUAL_NAMES), "ACTUAL_INPUT_REFS")
    bootstrap = value["bootstrap"]
    _require(type(bootstrap) is dict and set(bootstrap) == {"seed", "replicates"}
        and type(bootstrap["seed"]) is int and bootstrap["seed"] >= 0
        and type(bootstrap["replicates"]) is int and 2000 <= bootstrap["replicates"] <= 10000,
        "BOOTSTRAP_BOUND_REQUIRED")
    snapshots, arms, actual, paths = {str(path): raw}, {}, {}, {}
    def reference(ref):
        return descriptive._reference(ref, bundle_path=path, limit=local.MAX_BUNDLE_BYTES, snapshots=snapshots)
    for name in ("after", "baseline"):
        arm_path, _ = reference(value[name + "_bundle"])
        arm = descriptive.read_evaluation_bundle(arm_path, expected_sha256=value[name + "_bundle"]["sha256"])
        for key, content in arm["snapshots"].items():
            _require(Path(key).resolve().is_relative_to(path.parent.resolve()), "ARM_INPUT_OUTSIDE_ROOT")
            _require(key not in snapshots or snapshots[key] == content, "INPUT_CHANGED")
            snapshots[key] = content
        arms[name] = arm
    for name in ACTUAL_NAMES:
        target, content = reference(value["actual_inputs"][name])
        paths[name] = target
        actual[name] = _jsonl(content) if name == "expected_universe" else local._strict_json(content)
    source_payloads = {value["actual_inputs"]["source_manifest"]["sha256"]: snapshots[str(paths["source_manifest"]) ]}
    manifest = actual["source_manifest"]
    _require(type(manifest.get("rows")) is list and len(manifest["rows"]) <= descriptive.MAX_ROWS, "SOURCE_MANIFEST_ROWS")
    for row in manifest["rows"]:
        ref = row["source_artifact"]
        _, content = reference({"path": ref["relative_path"], "sha256": ref["sha256"], "bytes": ref["bytes"]})
        source_payloads[ref["sha256"]] = content
    _require(sum(map(len, snapshots.values())) <= MAX_TOTAL_BYTES and len(snapshots) <= local.MAX_FILES,
             "ACTUAL_INPUT_TOTAL_LIMIT")
    return {"path": path, "bundle": value, "snapshots": snapshots, "arms": arms,
        "actual": actual, "actual_paths": paths, "actual_source_payloads": source_payloads}


def _load_arm(loaded):
    from src.llm_batch.measurement.candidate_reranker_actual_bridge import FrozenArmInput
    from src.llm_batch.grounding.candidate_set_calibration_shadow import calibration_artifact_from_dict
    from src.llm_batch.grounding.candidate_reranker_shadow import load_scorer
    value = loaded["bundle"]
    manifest, policy = saved._typed_context(value)
    artifact = calibration_artifact_from_dict(loaded["artifact_payload"])
    artifact.validate_against(manifest, policy)
    scorer = load_scorer(loaded["model_path"], expected_sha256=value["model_manifest"]["sha256"])
    summary = scorer.summary()
    _require(local._sha(local._json_bytes(summary)) == value["expected_scorer_summary_sha256"], "SCORER_SUMMARY_MISMATCH")
    _require(summary.get("status") == "AVAILABLE_LEARNED" and summary.get("backend") == "NIL_AUGMENTED_LINEAR_V1"
        and summary.get("nil_head_available") is True, "PINNED_NIL_MODEL_REQUIRED")
    replayed = descriptive._replay_rows(scorer, value["expected_rows"], value["observations"],
        training_manifest=value["training_manifest"], source_payloads=loaded["source_payloads"],
        evidence_payloads=loaded["evidence_payloads"])
    arm = FrozenArmInput(training_manifest=value["training_manifest"],
        expected_training_manifest_sha256=value["expected_training_manifest_sha256"], calibration_manifest=manifest,
        expected_calibration_manifest_sha256=value["expected_calibration_manifest_sha256"], scorer_summary=summary,
        expected_scorer_summary_sha256=value["expected_scorer_summary_sha256"], policy=policy,
        calibration_artifact=artifact, expected_rows=value["expected_rows"], observations=value["observations"],
        frozen_rows=saved._typed_rows(value["frozen_rows"]), source_payloads=loaded["source_payloads"],
        evidence_payloads=loaded["evidence_payloads"])
    return arm, replayed


def _pin_legacy_closure(value, *, artifact_root, snapshots):
    """P1/P0에서 실제 읽는 refs를 기존 ROOT 해석 그대로, 지정 root 안에 고정한다."""
    visited = set()
    def walk(item):
        if type(item) is list:
            for child in item:
                walk(child)
        elif type(item) is dict:
            if all(k in item for k in ("path", "sha256", "bytes")):
                _require(type(item["path"]) is str and local._hex(item["sha256"])
                    and type(item["bytes"]) is int and 0 <= item["bytes"] <= local.MAX_BUNDLE_BYTES, "LEGACY_REF_SHAPE")
                candidate = Path(item["path"])
                target = local._local_path(candidate if candidate.is_absolute() else ROOT / candidate)
                _require(target.resolve().is_relative_to(artifact_root), "LEGACY_REF_OUTSIDE_ARTIFACT_ROOT")
                content = local._read(target, item["bytes"])
                _require(len(content) == item["bytes"] and local._sha(content) == item["sha256"], "LEGACY_REF_PIN_MISMATCH")
                _require(str(target) not in snapshots or snapshots[str(target)] == content, "LEGACY_REF_CHANGED")
                snapshots[str(target)] = content
                _require(len(snapshots) <= local.MAX_FILES and sum(map(len, snapshots.values())) <= MAX_TOTAL_BYTES,
                         "LEGACY_CLOSURE_LIMIT")
                if target.suffix.lower() == ".json" and str(target) not in visited:
                    visited.add(str(target))
                    # 전이 참조의 root는 배열일 수 있다. 기존 strict parser의 중복 키/
                    # NaN 거절을 내부에도 적용하되 원본 bytes는 변경하지 않는다.
                    parsed = local._strict_json(b'{"value":' + content + b'}')["value"]
                    walk(parsed)
            else:
                for key, child in item.items():
                    if key != "implementation_contract":  # 기존 runner도 verify_implementation=False
                        walk(child)
    walk(value)


def _save_json(path, value, *, limit=local.MAX_BUNDLE_BYTES):
    _require(len(local._json_bytes(value)) <= limit, "SAVED_JSON_BYTE_LIMIT")
    pending = path.with_name(".pending_" + path.name)
    ref = local._write(pending, value)
    _require(local._json_bytes(saved._read_saved(ref)) == local._json_bytes(value), "SAVED_OBJECT_MISMATCH")
    saved._rename_noreplace(pending, path)
    return {**ref, "path": str(path)}


def _save_jsonl(path, rows):
    content = b"".join(local._json_bytes(row) + b"\n" for row in rows)
    _require(len(content) <= local.MAX_BUNDLE_BYTES, "SAVED_JSONL_BYTE_LIMIT")
    pending = path.with_name(".pending_" + path.name)
    with pending.open("xb") as stream:
        stream.write(content); stream.flush(); os.fsync(stream.fileno())
    _require(local._read(pending, max(local.MAX_BUNDLE_BYTES, len(content))) == content, "SAVED_JSONL_BYTES_MISMATCH")
    _require(local._json_bytes(_jsonl(content)) == local._json_bytes(rows), "SAVED_JSONL_OBJECT_MISMATCH")
    saved._rename_noreplace(pending, path)
    return {"path": str(path), "sha256": local._sha(content), "bytes": len(content)}


def _archive_inputs(*, root, output, snapshots, used_paths):
    """기존 reader의 JSON 계약 안에 일반 원문 bytes도 손실 없이 보존한다.

    기존 reader는 .bin/text를 직접 artifact로 받지 않는다. 원본을 변환하지 않고
    새 JSON wrapper에 base64를 넣고 SHA·길이·decode를 검산한다. 최종 영수증 전
    원래 경로의 raw bytes도 _check_inputs로 다시 확인한다.
    """
    refs = []
    for index, name in enumerate(sorted(snapshots)):
        path = Path(name).resolve()
        if str(path) in used_paths:
            continue
        content = snapshots[name]
        payload = {"schema_version": "candidate_reranker_actual_input_archive_v1",
            "original_relative_path": path.relative_to(root).as_posix(),
            "raw_sha256": local._sha(content), "raw_bytes": len(content),
            "encoding": "BASE64", "payload_base64": base64.b64encode(content).decode("ascii")}
        payload["archive_sha256"] = local._sha(local._json_bytes(payload))
        target = output / ("bridge_input_archive_" + str(index) + ".json")
        ref = _save_json(target, payload, limit=MAX_ARCHIVE_BYTES)
        recovered = saved._read_saved(ref)
        decoded = base64.b64decode(recovered["payload_base64"], validate=True)
        _require(decoded == content and len(decoded) == recovered["raw_bytes"]
            and local._sha(decoded) == recovered["raw_sha256"], "INPUT_ARCHIVE_RAW_MISMATCH")
        refs.append(("bridge_input_" + str(index), target.relative_to(root).as_posix()))
        used_paths.add(str(path))
    return refs


def _bound_actual(loaded, pair, output):
    from tools import run_candidate_set_calibration_shadow_harness as actual
    root = loaded["path"].parent.resolve()
    _pin_legacy_closure(loaded["actual"]["p1_run_spec"], artifact_root=root, snapshots=loaded["snapshots"])
    for key in ("p1_comparison", "label_ledger"):
        _pin_legacy_closure(loaded["actual"][key], artifact_root=root, snapshots=loaded["snapshots"])
    refs = {}
    for name, payload in pair["artifact_payloads"].items():
        target = output / (name + (".jsonl" if type(payload) is list else ".json"))
        (_save_jsonl if type(payload) is list else _save_json)(target, payload)
        refs[name] = target.relative_to(root).as_posix()
    additional = [(name, refs[name]) for name in sorted(actual.ACTUAL_REPLAY_ARTIFACT_NAMES)]
    used = {str(p.resolve()) for p in loaded["actual_paths"].values()}
    used.update(str((root / row["source_artifact"]["relative_path"]).resolve())
        for row in loaded["actual"]["source_manifest"]["rows"])
    additional.extend(_archive_inputs(root=root, output=output, snapshots=loaded["snapshots"], used_paths=used))
    names = {k + ("_jsonl" if k == "expected_universe" else "_json"):
        p.relative_to(root).as_posix() for k, p in loaded["actual_paths"].items()}
    _, run_spec, readiness, manifest = actual.build_bound_actual_readback_from_files(artifact_root=root,
        **names, producer_jsonl=refs["producer"], prediction_jsonl=refs["prediction"],
        baseline_prediction_jsonl=refs["baseline_prediction"], additional_artifacts=additional,
        **loaded["bundle"]["bootstrap"])
    directory = output / "readback"
    directory.mkdir(exist_ok=False)
    # 기존 writer는 root의 직접 자식만 허용한다. 새 CLI의 단일 출력 폴더 안에
    # 똑같은 세 객체를 atomic no-replace로 저장하고 기존 독립 reader를 호출한다.
    for name, value in (("run_spec", run_spec), ("readiness", readiness), ("readback", manifest)):
        _save_json(directory / (name + ".json"), value)
    _, result, receipt, readback = actual.evaluate_bound_actual_readback_bundle(
        artifact_root=root, readback_bundle_dir=directory.relative_to(root).as_posix())
    _require(result["conversion_allowed"] is False, "ACTUAL_PUBLIC_AUTHORITY_FORBIDDEN")
    return {"evaluation": result, "evidence_receipt": receipt.to_dict(), "readback_manifest": readback}


def evaluate_actual_bundle(*, bundle_path, expected_sha256, output_dir):
    output = local._local_path(output_dir)
    _require(not os.path.lexists(output), "OUTPUT_MUST_BE_NEW")
    from src.llm_batch.runtime.execution_config import apply_profile_resources, observe_process_resources
    start = apply_profile_resources("low-load-validation", os.environ)
    local._resources(start)
    loaded = read_actual_bundle(bundle_path, expected_sha256=expected_sha256)
    _require(output.resolve().is_relative_to(loaded["path"].parent.resolve())
        and output.resolve() != loaded["path"].parent.resolve(), "OUTPUT_MUST_BE_NEW_CHILD")
    after, a_count = _load_arm(loaded["arms"]["after"])
    baseline, b_count = _load_arm(loaded["arms"]["baseline"])
    _require(local._json_bytes(loaded["actual"]["split_manifest"]) == local._json_bytes(after.calibration_manifest.to_dict())
        and local._json_bytes(loaded["actual"]["actual_evaluation_policy"]) == local._json_bytes(after.policy.to_dict()),
        "ACTUAL_CONTEXT_MISMATCH")
    from src.llm_batch.measurement.candidate_reranker_actual_bridge import prepare_actual_pair
    pair = prepare_actual_pair(after=after, baseline=baseline, expected_universe=loaded["actual"]["expected_universe"],
        source_manifest=loaded["actual"]["source_manifest"],
        source_manifest_raw_sha256=loaded["bundle"]["actual_inputs"]["source_manifest"]["sha256"],
        actual_source_payloads=loaded["actual_source_payloads"])
    local._check_inputs(loaded["snapshots"])
    output.mkdir(parents=True, exist_ok=False)
    pair_ref = _save_json(output / "pair_report.json", pair)
    reasons = sorted(set(pair["reason_codes"] + pair["actual_admission_reasons"]))
    result = None
    if not reasons:
        result = _bound_actual(loaded, pair, output)
    local._check_inputs(loaded["snapshots"])
    end = observe_process_resources(os.environ)
    local._resources(end)
    _require(all(start[k] == end[k] for k in ("pid", "priority_class", "affinity_mask", "logical_cpu_count", "numeric_threads")),
             "RESOURCE_DRIFT")
    report = {"schema_version": REPORT_SCHEMA, "status": "BOUND_ACTUAL_READBACK_COMPLETE" if result is not None else "NOT_EVALUABLE",
        "bundle_sha256": expected_sha256, "pair_report": pair_ref, "pair_sha256": pair["pair_sha256"],
        "expected_count": pair["expected_count"], "reason_codes": reasons, "actual_readback": result,
        "actual_gate_status": result["evaluation"]["evaluation"]["status"] if result else None,
        "actual_inputs_validation": "EXISTING_BOUND_RUNNER_REPLAYED" if result else "NOT_EXECUTED_ADMISSION_BLOCKED",
        "local_score_replay_counts": {"after": a_count, "baseline": b_count},
        "inputs": [{"path": p, "sha256": local._sha(raw), "bytes": len(raw)} for p, raw in sorted(loaded["snapshots"].items())],
        "resources_start": start, "resources_end": end,
        "model_training_executed": False, "calibration_fit_executed": False, "thresholds_reselected": False,
        "source_truth_independently_verified": False, "quality_acceptance_claimed": False,
        "formal_kpi_status": "NOT_ESTIMABLE", "publication_authority": False, "public_apply": False, "central_db_write": False,
        "limitations": ["LOCAL_SAVED_OBSERVATION_REPLAY_NOT_NEW_PROVIDER_EXECUTION",
                        "SOURCE_AND_HUMAN_RIGHTS_DECLARATIONS_NOT_INDEPENDENTLY_AUTHENTICATED",
                        "LEGACY_ACTUAL_GATE_IS_SHADOW_ONLY_NOT_PRODUCT_ACCEPTANCE"]}
    report["report_sha256"] = local._sha(local._json_bytes(report))
    report_ref = _save_json(output / "evaluation_report.json", report)
    local._check_inputs(loaded["snapshots"])
    if result is not None:
        from src.llm_batch.grounding.calibration_actual_readback import validate_actual_readback_artifacts
        validate_actual_readback_artifacts(loaded["path"].parent, result["readback_manifest"])
    receipt = {"schema_version": REPORT_SCHEMA, "status": "SAVED_AND_READBACK_VERIFIED", "report_status": report["status"],
        "evaluation_report": report_ref, "report_sha256": report["report_sha256"], "actual_gate_status": report["actual_gate_status"],
        "publication_authority": False, "public_apply": False, "central_db_write": False, "formal_kpi_status": "NOT_ESTIMABLE"}
    receipt["receipt_sha256"] = local._sha(local._json_bytes(receipt))
    ref = saved._publish_workflow_receipt(output, receipt)
    return {**receipt, "workflow_receipt": ref}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_actual_bundle(bundle_path=args.bundle, expected_sha256=args.bundle_sha256, output_dir=args.output_dir)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("고정 NIL actual 연결 실패: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
