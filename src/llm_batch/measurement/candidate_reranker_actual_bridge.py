"""고정 NIL/CAL 관측을 기존 actual readback 형식으로 연결하는 순수 변환.

이 모듈은 모델 점수의 실제 생성, 사람 판정과 권리의 진실을 인증하지 않는다.
CLI가 고정 모델을 재생하며 기존 actual runner가 파일·정책·분모를 재검산한다.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
from pathlib import PurePosixPath, PureWindowsPath
from typing import Mapping

from . import candidate_reranker_nil_evaluation as nil_eval
from ..grounding import candidate_reranker_event_bridge as event
from ..grounding import candidate_set_calibration_shadow as cal
from ..grounding.candidate_reranker_learned import _strict_capture

SCHEMA = "candidate_reranker_actual_pair_v1"
SOURCE_SCHEMA = "candidate-set-calibration-actual-source-manifest-v1"
PAYLOAD_SCHEMA = "candidate-set-calibration-actual-source-payload-v1"
ALIGNMENT_SCHEMA = "candidate_reranker_actual_source_alignment_v1"
MAX_BYTES = nil_eval.MAX_BYTES
MAX_ROWS = nil_eval.MAX_ROWS
_REF_KEYS = {"logical_name", "relative_path", "bytes", "sha256", "canonical_payload_sha256", "row_count"}


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _raw(value):
    return nil_eval.raw_evaluation._bytes(value)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _equal(left, right):
    return _raw(left) == _raw(right)


@dataclass(frozen=True)
class FrozenArmInput:
    training_manifest: dict
    expected_training_manifest_sha256: str
    calibration_manifest: cal.CalibrationSplitManifest
    expected_calibration_manifest_sha256: str
    scorer_summary: dict
    expected_scorer_summary_sha256: str
    policy: cal.CalibrationEvaluationPolicy
    calibration_artifact: cal.CalibrationArtifact
    expected_rows: list[dict]
    observations: list[dict]
    frozen_rows: list[dict]
    source_payloads: Mapping[str, bytes]
    evidence_payloads: Mapping[str, bytes]


def _snapshot_arm(arm):
    _require(type(arm) is FrozenArmInput, "TYPED_ARM_REQUIRED")
    # frozen dataclass 자체는 내부 dict를 고정하지 않는다. 공유 입력을 모두 분리한다.
    graphs = nil_eval._copy([nil_eval._graph_payload(g) for g in arm.frozen_rows])
    graphs = [{**g, "base_shadow": nil_eval.selective_shadow_from_dict(g["base_shadow"]),
        "generation_proof": nil_eval.candidate_generation_proof_from_dict(g["generation_proof"]),
        "retrieval_state": nil_eval.RetrievalState(**g["retrieval_state"])} for g in graphs]
    manifest = nil_eval._copy(arm.calibration_manifest.to_dict())
    manifest["assignments"] = tuple(cal.CalibrationSplitAssignment(**a) for a in manifest["assignments"])
    sources, evidence = event._payloads(arm.source_payloads, arm.evidence_payloads)
    return FrozenArmInput(training_manifest=nil_eval._copy(arm.training_manifest),
        expected_training_manifest_sha256=arm.expected_training_manifest_sha256,
        calibration_manifest=cal.CalibrationSplitManifest(**manifest),
        expected_calibration_manifest_sha256=arm.expected_calibration_manifest_sha256,
        scorer_summary=nil_eval._copy(arm.scorer_summary),
        expected_scorer_summary_sha256=arm.expected_scorer_summary_sha256,
        policy=cal.CalibrationEvaluationPolicy(**arm.policy.to_dict()),
        calibration_artifact=cal.calibration_artifact_from_dict(arm.calibration_artifact.to_dict()),
        expected_rows=nil_eval._copy(arm.expected_rows), observations=nil_eval._copy(arm.observations),
        frozen_rows=graphs, source_payloads=sources, evidence_payloads=evidence)


def _kwargs(arm):
    return {f.name: getattr(arm, f.name) for f in fields(FrozenArmInput)}


def _rows(arm):
    return [r for r in arm.training_manifest["rows"] if r["assignment"]["split"] == "FROZEN_HOLDOUT"]


def _source_alignment(after, baseline, expected, manifest, manifest_sha, payloads):
    _require(event._hash(manifest_sha), "ACTUAL_SOURCE_MANIFEST_PIN_REQUIRED")
    _require(type(payloads) is dict and len(payloads) <= MAX_ROWS + 1, "ACTUAL_SOURCE_MAP_LIMIT")
    _require(all(event._hash(k) and type(v) is bytes and _sha(v) == k for k, v in payloads.items())
             and sum(map(len, payloads.values())) <= MAX_BYTES, "ACTUAL_SOURCE_BYTES_INVALID")
    _require(manifest_sha in payloads and _equal(_strict_capture(payloads[manifest_sha], maximum=MAX_BYTES), manifest),
             "ACTUAL_SOURCE_MANIFEST_RAW_BINDING")
    _require(type(manifest) is dict and set(manifest) == {"schema_version", "source_run_id", "rows", "manifest_sha256"}
             and manifest["schema_version"] == SOURCE_SCHEMA
             and type(manifest["source_run_id"]) is str and bool(manifest["source_run_id"].strip()),
             "ACTUAL_SOURCE_MANIFEST_SCHEMA")
    _require(manifest["manifest_sha256"] == event.canonical_sha256({k: v for k, v in manifest.items()
        if k != "manifest_sha256"}), "ACTUAL_SOURCE_MANIFEST_SELF_SHA")
    records = manifest["rows"]
    _require(type(records) is list and len(records) == len(expected), "ACTUAL_SOURCE_COVERAGE")
    used, paths = {manifest_sha}, set()
    for exp, record, left, right in zip(expected, records, _rows(after), _rows(baseline)):
        _require(type(record) is dict and set(record) == {"example_id", "post_id", "source_artifact"}
            and _equal([record["example_id"], record["post_id"]], [exp["example_id"], exp["post_id"]]),
            "ACTUAL_SOURCE_ORDER_ID")
        ref = record["source_artifact"]
        path = ref.get("relative_path") if type(ref) is dict else None
        _require(type(ref) is dict and set(ref) == _REF_KEYS and ref["logical_name"] == "source_payload::" + exp["example_id"]
            and type(path) is str and bool(path) and path not in paths
            and not PurePosixPath(path).is_absolute() and not PureWindowsPath(path).drive
            and "://" not in path and "\\" not in path and all(p not in ("", ".", "..") for p in path.split("/"))
            and PurePosixPath(path).suffix == ".json" and event._hash(ref["sha256"])
            and event._hash(ref["canonical_payload_sha256"])
            and type(ref["bytes"]) is int and 0 <= ref["bytes"] <= MAX_BYTES and ref["row_count"] is None,
            "ACTUAL_SOURCE_REF_SHAPE")
        paths.add(ref["relative_path"])
        raw = payloads.get(ref["sha256"])
        _require(type(raw) is bytes and len(raw) == ref["bytes"], "ACTUAL_SOURCE_REF_BYTES")
        value = _strict_capture(raw, maximum=MAX_BYTES)
        _require(event.canonical_sha256(value) == ref["canonical_payload_sha256"], "ACTUAL_SOURCE_CANONICAL_SHA")
        _require(set(value) == {"schema_version", "source_run_id", "example_id", "post_id", "payload"}
            and value["schema_version"] == PAYLOAD_SCHEMA and value["source_run_id"] == manifest["source_run_id"]
            and _equal([value["example_id"], value["post_id"]], [exp["example_id"], exp["post_id"]]),
            "ACTUAL_SOURCE_PAYLOAD_ID")
        aligned = value["payload"]
        _require(type(aligned) is dict and set(aligned) == {"schema_version", "source_spans", "source_refs"}
            and aligned["schema_version"] == ALIGNMENT_SCHEMA, "ACTUAL_SOURCE_ALIGNMENT_UNSUPPORTED")
        _require(_equal(left["source_spans"], right["source_spans"])
            and _equal(aligned["source_spans"], left["source_spans"]), "ACTUAL_SOURCE_SPANS_MISMATCH")
        source_refs = {}
        for arm, row in ((after, left), (baseline, right)):
            for sid in row["source_ids"]:
                raw_source = arm.source_payloads[sid]
                current = {"source_id": sid, "payload_sha256": _sha(raw_source), "bytes": len(raw_source)}
                _require(sid not in source_refs or _equal(source_refs[sid], current), "PAIR_SOURCE_ID_COLLISION")
                source_refs[sid] = current
            for span in row["source_spans"]:
                raw_source = arm.source_payloads[span["source_id"]]
                start, end = span["utf8_byte_span_start"], span["utf8_byte_span_end"]
                _require(type(start) is int and type(end) is int and 0 <= start < end <= len(raw_source), "SOURCE_SPAN_RANGE")
                sliced = raw_source[start:end]
                _require(sliced.decode("utf-8") == span["text"] and _sha(sliced) == span["span_sha256"], "SOURCE_SPAN_BYTES")
        _require(_equal(aligned["source_refs"], [source_refs[k] for k in sorted(source_refs)]), "ACTUAL_SOURCE_REFS_MISMATCH")
        used.add(ref["sha256"])
    _require(set(payloads) == used, "UNUSED_ACTUAL_SOURCE_PAYLOAD")


def _arm_artifacts(arm, report, source_sha):
    common = {k: getattr(arm, k) for k in ("training_manifest", "expected_training_manifest_sha256",
        "calibration_manifest", "expected_calibration_manifest_sha256", "scorer_summary",
        "expected_scorer_summary_sha256", "source_payloads", "evidence_payloads")}
    bases, scores, predictions, producer = [], [], [], []
    for graph, row, observed in zip(arm.frozen_rows, _rows(arm), report["rows"]):
        score = event.build_frozen_event_score(**common, **graph)
        assignment = next(a for a in arm.calibration_manifest.assignments if a.example_id == score.example_id)
        shadow = cal.build_calibration_shadow(base_shadow=graph["base_shadow"], score_vector=score,
            artifact=arm.calibration_artifact, split_manifest=arm.calibration_manifest, policy=arm.policy,
            assignment=assignment)
        _require(_equal(shadow.to_dict(), observed["calibration_shadow"]), "SHADOW_REBUILD_MISMATCH")
        binding = {"example_id": score.example_id, "post_id": score.post_id,
            "candidate_set_fingerprint": shadow.candidate_set_fingerprint,
            "generation_proof_fingerprint": shadow.generation_proof_fingerprint, "source_digest_sha256": source_sha}
        producer.append({**binding, "generation_status": "COMPLETE"})
        predictions.append({**binding, "group": assignment.split_group_id,
            "probabilities": {p.label: p.probability_mass for p in shadow.event_probabilities},
            "shadow_fingerprint": shadow.shadow_fingerprint, "score_vector_sha256": score.score_vector_sha256,
            "calibration_shadow": shadow.to_dict()})
        bases.append({"example_id": score.example_id, "post_id": score.post_id, "shadow": graph["base_shadow"].to_dict()})
        scores.append(score.to_dict())
    return {"producer": producer, "prediction": predictions, "base_shadows": bases,
        "score_vectors": scores, "calibration_artifact": arm.calibration_artifact.to_dict()}


def prepare_actual_pair(*, after: FrozenArmInput, baseline: FrozenArmInput, expected_universe: list[dict],
        source_manifest: dict, source_manifest_raw_sha256: str, actual_source_payloads: Mapping[str, bytes]) -> dict:
    after, baseline = _snapshot_arm(after), _snapshot_arm(baseline)
    expected = nil_eval._copy(expected_universe)
    _require(type(expected) is list and 0 < len(expected) <= MAX_ROWS, "EXPECTED_UNIVERSE_LIMIT")
    for row in expected:
        _require(type(row) is dict and all(type(row.get(k)) is str and row[k].strip() for k in ("example_id", "post_id")),
                 "ACTUAL_TYPED_STRING_ID_REQUIRED")
    _require(_equal(after.calibration_manifest.to_dict(), baseline.calibration_manifest.to_dict())
        and _equal(after.policy.to_dict(), baseline.policy.to_dict()), "PAIR_SPLIT_POLICY_MISMATCH")
    frozen = [a.to_dict() for a in after.calibration_manifest.assignments if a.split == "FROZEN_HOLDOUT"]
    _require(_equal(expected, frozen), "EXPECTED_UNIVERSE_SPLIT_MISMATCH")
    for arm in (after, baseline):
        _require(_equal(expected, [row["assignment"] for row in _rows(arm)]), "PAIR_FULL_FROZEN_ORDER_MISMATCH")
    reports = {name: nil_eval.evaluate_frozen_nil_scores(**_kwargs(arm)) for name, arm in (("after", after), ("baseline", baseline))}
    for left, right in zip(_rows(after), _rows(baseline)):
        _require(_equal(left["assignment"], right["assignment"]), "PAIR_ASSIGNMENT_MISMATCH")
    manifest = nil_eval._copy(source_manifest)
    _source_alignment(after, baseline, expected, manifest, source_manifest_raw_sha256, dict(actual_source_payloads))
    reasons, rows = [], []
    for left, right in zip(reports["after"]["rows"], reports["baseline"]["rows"]):
        per_row = {"example_id": left["example_id"], "after_terminal": left["source_terminal"],
            "baseline_terminal": right["source_terminal"], "after_calibration": left["calibration_status"],
            "baseline_calibration": right["calibration_status"], "truth_kind": left["truth_kind"],
            "after_reasons": left["calibration_reason_codes"], "baseline_reasons": right["calibration_reason_codes"]}
        if left["calibration_status"] != "BOUND" or right["calibration_status"] != "BOUND":
            reasons.append("INCOMPLETE_PAIRED_FROZEN_UNIVERSE")
        rows.append(per_row)
    artifacts = None
    if not reasons:
        a = _arm_artifacts(after, reports["after"], source_manifest_raw_sha256)
        b = _arm_artifacts(baseline, reports["baseline"], source_manifest_raw_sha256)
        _require(_equal(a["producer"], b["producer"]), "PAIR_CANDIDATE_GENERATION_MISMATCH")
        artifacts = {"producer": a["producer"], "prediction": a["prediction"], "baseline_prediction": b["prediction"]}
        for name, values in (("after", a), ("baseline", b)):
            for kind in ("base_shadows", "score_vectors", "calibration_artifact"):
                artifacts[name + "_" + kind] = values[kind]
    admission = []
    for name, arm in (("after", after), ("baseline", baseline)):
        if arm.scorer_summary["data_kind"] != "SOURCE_BACKED":
            admission.append(name.upper() + "_SYNTHETIC_NOT_ACTUAL")
        if any(r["label_provenance"]["grade"] != "HUMAN_GOLD" for r in arm.training_manifest["rows"]):
            admission.append(name.upper() + "_HUMAN_LABELS_NOT_COMPLETE")
        if any(s["rights_status"] != "REUSE_PERMITTED" for s in arm.training_manifest["sources"]):
            admission.append(name.upper() + "_RIGHTS_NOT_PERMITTED")
    if after.policy.policy_scope != "FROZEN_ACTUAL_PRE_REGISTERED" or after.policy.schema_version != cal.CALIBRATION_POLICY_SCHEMA_V4:
        admission.append("ACTUAL_POLICY_V4_NOT_PREREGISTERED")
    report = {"schema_version": SCHEMA, "status": "NOT_EVALUABLE" if reasons else "READY_FOR_BOUND_READBACK",
        "expected_count": len(expected), "after_report": reports["after"], "baseline_report": reports["baseline"],
        "per_row": rows, "reason_codes": sorted(set(reasons)), "actual_admission_reasons": sorted(set(admission)),
        "bindings": {"expected_universe_sha256": event.canonical_sha256(expected),
            "source_manifest_raw_sha256": source_manifest_raw_sha256,
            "calibration_manifest_sha256": after.calibration_manifest.manifest_sha256,
            "policy_sha256": after.policy.policy_sha256,
            "after_summary_sha256": after.expected_scorer_summary_sha256,
            "baseline_summary_sha256": baseline.expected_scorer_summary_sha256},
        "artifact_payloads": artifacts, "score_verification_scope": "STRUCTURAL_BINDING_REQUIRES_CALLER_MODEL_REPLAY",
        "source_truth_independently_verified": False, "quality_acceptance_claimed": False,
        "formal_kpi_status": "NOT_ESTIMABLE", "publication_authority": False, "public_apply": False, "central_db_write": False}
    report["pair_sha256"] = event.canonical_sha256(report)
    _require(len(_raw(report)) <= MAX_BYTES, "PAIR_REPORT_BYTE_LIMIT")
    return report
