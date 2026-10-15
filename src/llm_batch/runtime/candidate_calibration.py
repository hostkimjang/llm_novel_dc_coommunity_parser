"""명시적으로 배정된 FROZEN 행의 재관측만 교정 shadow에 연결한다.

새 추론 자료에 대한 확률 계약이 아니다. 원래 runtime/corpus 좌표와 dataset
좌표를 별도로 보존하며 기존 bridge·교정 검산을 완화하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
from typing import Mapping

BUNDLE_SCHEMA = "candidate_calibration_runtime_bundle_v1"
SCHEMA = "candidate_calibration_shadow_v1"
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_OBSERVATION_BYTES = 48 * 1024
MAX_STORED_BYTES = 64 * 1024
MAX_ROWS = 256
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z0-9_]{1,96}\Z")
_BINDING = ("run_id", "input_index", "post_id", "attempt_id", "publication_scope_id")
_ROW = {"example", "raw_receipt", "base_shadow", "generation_proof", "retrieval_state",
        "publication_scope_id", "source_binding_sha256"}
_BUNDLE = {"schema_version", "artifact", "training_manifest", "expected_training_manifest_sha256",
           "calibration_manifest", "expected_calibration_manifest_sha256", "policy",
           "expected_scorer_summary_sha256", "source_files", "evidence_files", "frozen_rows"}
_SCORES = ("ranked_candidates", "event_logits", "nil_score", "frozen_candidate_ids", "candidate_observations",
           "model_sha256", "candidate_ranker_model_sha256", "training_split_manifest_sha256", "scorer_sha256", "data_kind")
_SETTINGS = {"mode": ("candidate_calibration", "EXPERT_CANDIDATE_CALIBRATION", "OFF"),
             "bundle_path": ("calibration_bundle", "EXPERT_CALIBRATION_BUNDLE", None),
             "bundle_sha256": ("calibration_bundle_sha256", "EXPERT_CALIBRATION_BUNDLE_SHA256", None)}


class CandidateCalibrationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise CandidateCalibrationError(code)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _copy(value, limit=MAX_BUNDLE_BYTES):
    raw = _bytes(value)
    _require(len(raw) <= limit, "BYTE_LIMIT")
    return json.loads(raw)


def _hash(value):
    return type(value) is str and bool(_SHA.fullmatch(value))


def _post_id(value):
    return ((type(value) is int and 0 <= value <= 2**63 - 1)
            or (type(value) is str and 0 < len(value.strip()) <= 128))


def _equal(left, right):
    return _bytes(left) == _bytes(right)


def _semantic_binding(value):
    """runtime/dataset의 명시 post 매핑 외 별칭 정책·원시 근거는 그대로 결속한다."""
    alias = value["alias_evidence"]
    return {"contract_sha256": value["contract_sha256"],
        "policy_sha256": value["observation"]["policy_sha256"],
        "alias_payload_sha256": value["alias_payload_sha256"],
        "alias_community_context": {k: alias["community_source_view"][k] for k in ("community", "as_of")}
            if alias is not None else None,
        "alias_static_sha256": _sha({k:v for k,v in alias.items()
            if k not in {"retrieval_receipt", "community_source_view"}}) if alias is not None else None}


def _require_frozen_semantic_binding(capture, scorer_summary, record):
    """관측과 저장 양쪽에서 같은 고정 별칭 문맥을 요구한다."""
    if scorer_summary.get("semantic_input_required") is True:
        _require(capture.get("schema_version") == "candidate_reranker_capture_v2"
            and _equal(_semantic_binding(capture["semantic_input"]), record["semantic_binding"]),
            "FROZEN_SEMANTIC_BINDING_MISMATCH")


def _code(exc, default):
    code = getattr(exc, "code", str(exc))
    return code if type(code) is str and _CODE.fullmatch(code) else default


def resolve_candidate_calibration_settings(args, environment: Mapping[str, str]) -> dict:
    values, sources = {}, {}
    for key, (attribute, env, default) in _SETTINGS.items():
        value = getattr(args, attribute, None)
        if value is not None:
            source = "CLI"
        elif env in environment:
            value, source = environment[env], "ENVIRONMENT"
        else:
            value, source = default, "DEFAULT"
        values[key], sources[key] = value, source
    _require(type(values["mode"]) is str and values["mode"] in {"OFF", "SHADOW"}, "MODE_INVALID")
    if values["mode"] == "SHADOW":
        reranker_mode = getattr(args, "candidate_reranker", None)
        if reranker_mode is None:
            reranker_mode = environment.get("EXPERT_CANDIDATE_RERANKER", "OFF")
        _require(getattr(args, "candidate_retrieval", "OFF") == "SHADOW" and reranker_mode == "SHADOW",
                 "RETRIEVAL_AND_RERANKER_SHADOW_REQUIRED")
        _require(isinstance(values["bundle_path"], (str, Path)) and bool(str(values["bundle_path"]).strip())
                 and _hash(values["bundle_sha256"]), "PINNED_BUNDLE_REQUIRED")
    return {**values, "sources": sources}


def _summary(bundle_sha, scorer_summary, *, reason=None, artifact=None, mappings=None):
    scorer_summary = scorer_summary if type(scorer_summary) is dict else {}
    result = {"schema_version": "candidate_calibration_policy_v1", "mode": "SHADOW",
        "scope": "FROZEN_REOBSERVATION_ONLY", "status": "UNAVAILABLE" if reason else "AVAILABLE",
        "reason_codes": [reason] if reason else [], "bundle_sha256": bundle_sha if _hash(bundle_sha) else None,
        "model_sha256": scorer_summary.get("model_sha256") if _hash(scorer_summary.get("model_sha256")) else None,
        "scorer_sha256": scorer_summary.get("scorer_sha256") if _hash(scorer_summary.get("scorer_sha256")) else None,
        "data_kind": scorer_summary.get("data_kind") if scorer_summary.get("data_kind") in ("SOURCE_BACKED", "SYNTHETIC_FIXTURE") else None,
        "calibration_artifact_sha256": artifact,
        "mapping_set_sha256": _sha(mappings) if mappings is not None else None,
        "frozen_rows": len(mappings) if mappings is not None else 0,
        "actual_quality_evaluated": False, "publication_authority": False, "public_apply": False,
        "central_db_write": False, "action_applied": False, "operational_effect": "NONE_SHADOW_ONLY"}
    result["policy_sha256"] = _sha(result)
    return result


def _seal(value):
    value["receipt_sha256"] = _sha({k: v for k, v in value.items() if k not in {"receipt_sha256", "binding"}})
    return value


def _envelope(summary, post_id, status, reasons, record=None, *, capture_sha=None, raw_sha=None):
    record = record or {}
    return _seal({"schema_version": SCHEMA, "mode": "SHADOW", "status": status, "reason_codes": list(reasons),
        "post_id": post_id, "dataset_example_id": record.get("example_id"), "dataset_post_id": record.get("dataset_post_id"),
        "mapping_sha256": record.get("mapping_sha256"), "runtime_capture_sha256": capture_sha,
        "runtime_raw_receipt_sha256": raw_sha, "dataset_raw_receipt_sha256": record.get("dataset_raw_receipt_sha256"),
        **{key: summary.get(key) for key in ("calibration_artifact_sha256", "bundle_sha256", "model_sha256", "scorer_sha256", "data_kind")},
        "calibration_shadow": record.get("calibration_shadow") if status == "CALIBRATED_SHADOW_BOUND" else None,
        "publication_authority": False, "public_apply": False, "central_db_write": False, "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY"})


@dataclass(frozen=True, slots=True)
class FrozenCandidateCalibration:
    _summary_json: bytes
    _scorer_summary_json: bytes
    _rows: tuple[tuple[bytes, bytes], ...] = ()

    def summary(self):
        return json.loads(self._summary_json)

    def _record(self, post_id):
        if not _post_id(post_id):
            return None
        key = _bytes(post_id)
        return next((json.loads(raw) for stored, raw in self._rows if stored == key), None)

    def observe(self, post, capture, reranker_receipt):
        summary, post_id = self.summary(), getattr(post, "post_id", None)
        if summary["status"] != "AVAILABLE":
            return _envelope(summary, post_id, "UNAVAILABLE", summary["reason_codes"])
        record = self._record(post_id)
        if record is None:
            return _envelope(summary, post_id, "NOT_AVAILABLE", ["FROZEN_ROW_NOT_ASSIGNED"])
        try:
            from ..grounding.candidate_reranker_capture import validate_capture
            from ..grounding.candidate_reranker_event_bridge import _scores
            from .candidate_reranker import _source_view, _valid_receipt
            _require(capture is not None, "CAPTURE_NOT_AVAILABLE")
            capture = validate_capture(capture)
            _require(capture.get("status") == "CAPTURED" and _equal(capture.get("post_id"), post_id), "CAPTURE_POST_MISMATCH")
            scorer_summary = json.loads(self._scorer_summary_json)
            _require(_equal(capture["scorer_summary"], scorer_summary), "CAPTURE_SCORER_MISMATCH")
            view = capture["frozen_view"]
            _require(_equal(view["source_view"], _source_view(post)), "RUNTIME_SOURCE_MISMATCH")
            comparison = _copy(view)
            comparison["post_id"] = comparison["source_view"]["post_id"] = record["dataset_post_id"]
            _require(_equal(comparison, record["dataset_view"]), "FROZEN_VIEW_MISMATCH")
            _require_frozen_semantic_binding(capture, scorer_summary, record)
            raw = _copy(reranker_receipt, MAX_STORED_BYTES)
            _require(_valid_receipt(raw, scorer_summary, post_id, require_roles="preselection_role_producer" in raw), "RUNTIME_RECEIPT_INVALID")
            _require(raw.get("receipt_sha256") == capture["raw_receipt_sha256"], "CAPTURE_RAW_RECEIPT_MISMATCH")
            _scores(raw, view, scorer_summary)
            _require(all(_equal(raw.get(key), record["scores"][key]) for key in _SCORES), "RUNTIME_DATASET_SCORE_MISMATCH")
            result = _envelope(summary, post_id, "CALIBRATED_SHADOW_BOUND", ["EXPLICIT_FROZEN_REOBSERVATION"], record,
                capture_sha=capture["capture_sha256"], raw_sha=raw["receipt_sha256"])
            _require(len(_bytes(result)) <= MAX_OBSERVATION_BYTES, "OBSERVATION_BYTE_LIMIT")
            return result
        except Exception as exc:
            return _envelope(summary, post_id, "NOT_AVAILABLE", [_code(exc, "INVALID_CALIBRATION_OBSERVATION")], record)


def _load(settings, scorer):
    # OFF 경로는 이 import와 파일 판독에도 도달하지 않는다.
    from tools import run_candidate_reranker_training as local
    from ..grounding import candidate_reranker_event_bridge as bridge
    from ..grounding import candidate_set_calibration_shadow as legacy
    from ..grounding.candidate_set_shadow import selective_shadow_from_dict
    from ..grounding.candidate_generation import candidate_generation_proof_from_dict
    from ..promotion_gate import RetrievalState
    _require(scorer is not None, "NIL_SCORER_REQUIRED")
    summary = _copy(scorer.summary())
    _require(type(summary) is dict and summary.get("status") == "AVAILABLE_LEARNED"
             and summary.get("backend") == "NIL_AUGMENTED_LINEAR_V1", "NIL_SCORER_REQUIRED")
    path = local._local_path(settings["bundle_path"])
    raw = local._read(path, MAX_BUNDLE_BYTES)
    _require(_hash(settings["bundle_sha256"]) and hashlib.sha256(raw).hexdigest() == settings["bundle_sha256"], "BUNDLE_SHA_MISMATCH")
    data = local._strict_json(raw)
    _require(set(data) == _BUNDLE and data["schema_version"] == BUNDLE_SCHEMA, "BUNDLE_SCHEMA_INVALID")
    snapshots = {str(path): raw}
    def read_ref(ref, limit):
        _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "REFERENCE_SCHEMA_INVALID")
        name = ref["path"]
        _require(type(name) is str and name and not Path(name).is_absolute() and not PureWindowsPath(name).drive
            and "://" not in name and "\\" not in name and all(p not in {"", ".", ".."} for p in name.split("/")), "REFERENCE_PATH_INVALID")
        _require(_hash(ref["sha256"]) and type(ref["bytes"]) is int and 0 <= ref["bytes"] <= limit, "REFERENCE_SIZE_OR_SHA_INVALID")
        target = local._local_path(path.parent / name)
        _require(target.resolve().is_relative_to(path.parent.resolve()) and target != path, "REFERENCE_OUTSIDE_BUNDLE")
        payload = local._read(target, ref["bytes"])
        _require(len(payload) == ref["bytes"] and hashlib.sha256(payload).hexdigest() == ref["sha256"], "REFERENCE_BYTES_MISMATCH")
        _require(str(target) not in snapshots or snapshots[str(target)] == payload, "INPUT_CHANGED_DURING_LOAD")
        snapshots[str(target)] = payload
        return payload
    artifact = legacy.calibration_artifact_from_dict(local._strict_json(read_ref(data["artifact"], MAX_PAYLOAD_BYTES)))
    _require(artifact.schema_version == "candidate_set_calibration_artifact_v2", "LEARNED_CALIBRATION_V2_REQUIRED")
    manifests = data["calibration_manifest"]
    calibration = legacy.CalibrationSplitManifest(**{**manifests, "assignments": tuple(
        legacy.CalibrationSplitAssignment(**item) for item in manifests["assignments"])})
    policy = legacy.CalibrationEvaluationPolicy(**data["policy"])
    artifact.validate_against(calibration, policy)
    expected_binding = {"training_split_manifest_sha256": data["expected_training_manifest_sha256"],
        "calibration_manifest_sha256": calibration.manifest_sha256, "scorer_fingerprint": summary["scorer_sha256"],
        "scorer_summary_sha256": _sha(summary), "model_sha256": summary["model_sha256"],
        "base_model_sha256": summary["candidate_ranker_model_sha256"], "data_kind": summary["data_kind"]}
    _require(_equal(artifact.fit_receipt.to_dict()["learning_evidence"]["binding"], expected_binding), "ARTIFACT_MODEL_BINDING_MISMATCH")
    maps, total, files = {}, 0, 0
    for key in ("source_files", "evidence_files"):
        refs = data[key]
        _require(type(refs) is dict, "PAYLOAD_MAP_REQUIRED")
        files += len(refs)
        _require(files <= 8000, "PAYLOAD_FILE_LIMIT")
        values = {}
        for identifier, ref in refs.items():
            _require(type(identifier) is str and identifier, "PAYLOAD_KEY_INVALID")
            payload = read_ref(ref, MAX_PAYLOAD_BYTES)
            total += len(payload)
            _require(total <= MAX_PAYLOAD_BYTES, "PAYLOAD_BYTE_LIMIT")
            _require(key != "evidence_files" or identifier == ref["sha256"], "EVIDENCE_KEY_SHA_MISMATCH")
            values[identifier] = payload
        maps[key] = values
    rows = data["frozen_rows"]
    _require(type(rows) is list and 1 <= len(rows) <= MAX_ROWS
             and all(type(row) is dict and set(row) == _ROW | {"runtime_post_id", "dataset_post_id"} for row in rows), "FROZEN_ROWS_INVALID")
    assignments = {a.example_id: a for a in calibration.assignments if a.split == "FROZEN_HOLDOUT"}
    _require([r["example"].get("example_id") for r in rows] == sorted(assignments), "FULL_FROZEN_UNIVERSE_REQUIRED")
    records, mappings, runtime_ids = [], [], set()
    for row in rows:
        runtime_id, dataset_id, example = row["runtime_post_id"], row["dataset_post_id"], row["example"]
        _require(_post_id(runtime_id) and type(dataset_id) is str and dataset_id == assignments[example["example_id"]].post_id,
                 "EXPLICIT_POST_MAPPING_INVALID")
        runtime_key = _bytes(runtime_id)
        _require(runtime_key not in runtime_ids, "DUPLICATE_RUNTIME_POST_MAPPING")
        runtime_ids.add(runtime_key)
        semantic_input = None
        if summary.get("semantic_input_required") is True:
            training_row = next(r for r in data["training_manifest"]["rows"]
                                if r["assignment"]["example_id"] == example["example_id"])
            semantic_input = bridge.resolve_example_semantic_input(example, training_row,
                maps["source_files"], maps["evidence_files"], split_manifest=data["training_manifest"])
            _require(semantic_input is not None, "SEMANTIC_DATASET_INPUT_REQUIRED")
            replay = scorer.score(_copy(example["frozen_view"]), semantic_input=semantic_input,
                                  evidence_payloads=maps["evidence_files"])
            _require(replay.get("semantic_input_sha256") == semantic_input["input_sha256"]
                and row["raw_receipt"].get("semantic_input_sha256") == semantic_input["input_sha256"],
                "DATASET_SEMANTIC_INPUT_MISMATCH")
        else:
            replay = scorer.score(_copy(example["frozen_view"]))
        _require(replay.get("status") == "SCORED_LEARNED" and all(_equal(replay.get(k), row["raw_receipt"].get(k)) for k in _SCORES), "DATASET_MODEL_REPLAY_MISMATCH")
        args = {**{k: row[k] for k in _ROW}, "base_shadow": selective_shadow_from_dict(row["base_shadow"]),
            "generation_proof": candidate_generation_proof_from_dict(row["generation_proof"]),
            "retrieval_state": RetrievalState(**row["retrieval_state"]), "scorer_summary": summary,
            "expected_scorer_summary_sha256": data["expected_scorer_summary_sha256"],
            "training_manifest": data["training_manifest"], "expected_training_manifest_sha256": data["expected_training_manifest_sha256"],
            "calibration_manifest": calibration, "expected_calibration_manifest_sha256": data["expected_calibration_manifest_sha256"],
            "source_payloads": maps["source_files"], "evidence_payloads": maps["evidence_files"]}
        vector = bridge.build_frozen_event_score(**args)
        shadow = legacy.build_calibration_shadow(args["base_shadow"], vector, artifact, policy,
            split_manifest=calibration, assignment=assignments[example["example_id"]])
        _require(shadow.probability_status == legacy.CALIBRATED_BOUND_STATUS and shadow.action_applied is False, "FROZEN_CALIBRATION_NOT_BOUND")
        mapping = {"schema_version": "candidate_calibration_post_mapping_v1", "runtime_post_id": runtime_id,
            "dataset_post_id": dataset_id, "dataset_example_id": example["example_id"],
            "training_split_manifest_sha256": data["expected_training_manifest_sha256"], "calibration_manifest_sha256": calibration.manifest_sha256}
        mappings.append(mapping)
        record = {"example_id": example["example_id"], "dataset_post_id": dataset_id, "mapping_sha256": _sha(mapping),
            "dataset_raw_receipt_sha256": row["raw_receipt"]["receipt_sha256"], "dataset_view": example["frozen_view"],
            "scores": {key: row["raw_receipt"][key] for key in _SCORES}, "calibration_shadow": shadow.to_dict()}
        if semantic_input is not None:
            record["semantic_binding"] = _semantic_binding(semantic_input)
        records.append((runtime_key, _bytes(record)))
    local._check_inputs(snapshots)
    return FrozenCandidateCalibration(_bytes(_summary(settings["bundle_sha256"], summary,
        artifact=artifact.artifact_sha256, mappings=mappings)), _bytes(summary), tuple(records))


def prepare_candidate_calibration(settings, scorer):
    if settings["mode"] == "OFF":
        return None
    try:
        _require(settings["mode"] == "SHADOW", "MODE_INVALID")
        return _load(settings, scorer)
    except Exception as exc:
        try:
            summary = _copy(scorer.summary()) if scorer is not None else {}
        except Exception:
            summary = {}
        return FrozenCandidateCalibration(_bytes(_summary(settings.get("bundle_sha256"), summary,
            reason=_code(exc, "BUNDLE_LOAD_ERROR"))), _bytes(summary))


def candidate_calibration_policy_fields(observer, settings=None):
    if observer is None:
        return {}
    summary = observer.summary()
    if settings is not None:
        summary["setting_sources"] = dict(settings["sources"])
        summary["policy_sha256"] = _sha({k: v for k, v in summary.items() if k != "policy_sha256"})
    return {"candidate_calibration_policy": summary}


def observe_candidate_calibration(observer, post, capture, reranker_receipt):
    if observer is None:
        return None
    return observer.observe(post, capture, reranker_receipt)


def export_candidate_calibration_fields(result, observer, *, binding, capture_receipt=None):
    if observer is None:
        return {}
    summary, post_id, storage_binding = observer.summary(), None, {}
    try:
        _require(isinstance(binding, Mapping), "STORAGE_BINDING_INVALID")
        post_id = binding.get("post_id")
        storage_binding = {**{k: binding.get(k) for k in _BINDING}, "scope": "ATTEMPT_LOCAL_OBSERVATION"}
        _require(_post_id(post_id) and type(storage_binding["input_index"]) is int and storage_binding["input_index"] >= 1
            and all(type(storage_binding[k]) is str and 0 < len(storage_binding[k].strip()) <= 512
                    for k in ("run_id", "attempt_id", "publication_scope_id")), "STORAGE_BINDING_INVALID")
        raw = getattr(result, "_candidate_calibration_shadow", None) if result is not None else None
        if raw is None:
            receipt = (_envelope(summary, post_id, "NOT_EXECUTED", ["PIPELINE_NOT_EXECUTED"])
                if result is None else _envelope(summary, post_id, "NOT_AVAILABLE", ["CALIBRATION_OBSERVATION_MISSING"]))
        else:
            raw = _copy(raw, MAX_OBSERVATION_BYTES)
            _require(_equal(raw.get("post_id"), post_id), "STORAGE_POST_MISMATCH")
            _require("binding" not in raw or _equal(raw["binding"], storage_binding), "STORAGE_ATTEMPT_MISMATCH")
            _require(raw.get("status") in {"CALIBRATED_SHADOW_BOUND", "NOT_AVAILABLE", "NOT_EXECUTED", "UNAVAILABLE"}, "OBSERVATION_STATUS_INVALID")
            reasons = raw.get("reason_codes")
            _require(type(reasons) is list and 1 <= len(reasons) <= 8
                and all(type(x) is str and _CODE.fullmatch(x) for x in reasons), "OBSERVATION_REASONS_INVALID")
            record = observer._record(post_id) if raw.get("dataset_example_id") is not None else None
            receipt = _envelope(summary, post_id, raw["status"], reasons, record,
                capture_sha=raw.get("runtime_capture_sha256"), raw_sha=raw.get("runtime_raw_receipt_sha256"))
            _require(_equal({k: v for k, v in raw.items() if k != "binding"}, receipt), "OBSERVATION_RECEIPT_INVALID")
            if receipt["status"] == "CALIBRATED_SHADOW_BOUND":
                _require(summary["status"] == "AVAILABLE" and record is not None
                    and _hash(receipt["runtime_capture_sha256"]) and _hash(receipt["runtime_raw_receipt_sha256"]), "BOUND_OBSERVATION_INVALID")
                from ..grounding.candidate_reranker_capture import validate_capture
                from ..grounding.candidate_reranker_event_bridge import _scores
                capture = validate_capture(getattr(result, "_candidate_reranker_capture", None))
                current_raw = _copy(getattr(result, "_candidate_reranker_shadow", None), MAX_STORED_BYTES)
                scorer_summary = json.loads(observer._scorer_summary_json)
                _require(_equal(capture["post_id"], post_id), "CAPTURE_POST_MISMATCH")
                _require(_equal(capture["scorer_summary"], scorer_summary), "CAPTURE_SCORER_MISMATCH")
                _require(_equal(current_raw, capture["raw_receipt"]), "PRIVATE_RAW_CAPTURE_MISMATCH")
                _require(capture["capture_sha256"] == receipt["runtime_capture_sha256"]
                    and capture["raw_receipt_sha256"] == current_raw["receipt_sha256"]
                    == receipt["runtime_raw_receipt_sha256"], "STORED_OBSERVATION_DIGEST_MISMATCH")
                comparison = _copy(capture["frozen_view"])
                comparison["post_id"] = comparison["source_view"]["post_id"] = record["dataset_post_id"]
                _require(_equal(comparison, record["dataset_view"]), "FROZEN_VIEW_MISMATCH")
                _require_frozen_semantic_binding(capture, scorer_summary, record)
                _scores(current_raw, capture["frozen_view"], scorer_summary)
                _require(all(_equal(current_raw.get(key), record["scores"][key]) for key in _SCORES),
                         "RUNTIME_DATASET_SCORE_MISMATCH")
                _require(type(capture_receipt) is dict and capture_receipt.get("status") == "SAVED"
                    and capture_receipt.get("observation_sha256") == receipt["runtime_capture_sha256"]
                    and _equal(capture_receipt.get("binding"), storage_binding), "CAPTURE_STORAGE_NOT_BOUND")
        receipt["binding"] = storage_binding
        _require(len(_bytes(receipt)) <= MAX_STORED_BYTES, "STORAGE_BYTE_LIMIT")
    except Exception as exc:
        receipt = _envelope(summary, post_id if _post_id(post_id) else None, "NOT_AVAILABLE", [_code(exc, "INVALID_STORED_OBSERVATION")])
        try:
            if len(_bytes(storage_binding)) <= 4096:
                receipt["binding"] = _copy(storage_binding, 4096)
        except (ValueError, TypeError, RecursionError, OverflowError, UnicodeError):
            pass
    return {"candidate_calibration_shadow": receipt}
