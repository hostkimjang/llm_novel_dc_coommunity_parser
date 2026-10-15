"""고정 R2 corpus와 학습 모델의 일반 입력 교정 관측. 공개 결과에는 개입하지 않는다."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
from typing import Mapping
import uuid

BUNDLE_SCHEMA = "candidate_inference_runtime_bundle_v1"
SCHEMA = "candidate_reranker_inference_runtime_v1"
CAPTURE_REF_SCHEMA = "candidate_inference_capture_ref_v1"
ARTIFACT_SCHEMA = "candidate_inference_capture_artifact_v1"
PACKAGE_SCHEMA = "candidate_inference_observation_v1"
MAX_BUNDLE_BYTES = 1024 * 1024
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 40 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z0-9_]{1,96}\Z")
_BUNDLE_KEYS = {"schema_version", "expected_scorer_summary_sha256", "artifact",
                "calibration_manifest", "policy", "corpus_snapshot", "source_files"}
_SETTINGS = {"mode": ("candidate_inference", "EXPERT_CANDIDATE_INFERENCE", "OFF"),
    "bundle_path": ("inference_bundle", "EXPERT_INFERENCE_BUNDLE", None),
    "bundle_sha256": ("inference_bundle_sha256", "EXPERT_INFERENCE_BUNDLE_SHA256", None)}
_FLAGS = {"publication_authority": False, "public_apply": False, "central_db_write": False,
          "action_applied": False, "operational_effect": "NONE_SHADOW_ONLY"}
_SCORE_IGNORED = {"latency_ms", "receipt_sha256", "preselection_role_producer"}


class CandidateInferenceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise CandidateInferenceError(code)


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _copy(value, limit=MAX_ARTIFACT_BYTES):
    raw = _bytes(value)
    _require(len(raw) <= limit, "INFERENCE_BYTE_LIMIT")
    return json.loads(raw)


def _equal(left, right):
    return _bytes(left) == _bytes(right)


def _hash(value):
    return type(value) is str and bool(_HASH.fullmatch(value))


def _code(exc, fallback="INFERENCE_VALIDATION_FAILED"):
    # 파일·provider 예외의 문자열은 경로나 임의 내용을 담을 수 있다.
    value = getattr(exc, "code", None)
    return value if type(value) is str and _CODE.fullmatch(value) else fallback


def _seal(value):
    return {**value, "receipt_sha256": _sha(value)}


def resolve_candidate_inference_settings(args, environment: Mapping[str, str]) -> dict:
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
        reranker = getattr(args, "candidate_reranker", None)
        if reranker is None:
            reranker = environment.get("EXPERT_CANDIDATE_RERANKER", "OFF")
        _require(getattr(args, "candidate_retrieval", "OFF") == "SHADOW" and reranker == "SHADOW",
                 "RETRIEVAL_AND_RERANKER_SHADOW_REQUIRED")
        _require(isinstance(values["bundle_path"], (str, Path)) and bool(str(values["bundle_path"]).strip())
                 and _hash(values["bundle_sha256"]), "PINNED_BUNDLE_REQUIRED")
    return {**values, "sources": sources}


def read_inference_bundle(path, *, expected_sha256):
    """참조 파일의 raw bytes를 읽는다. 학습/fit/검색/모델 호출은 하지 않는다."""
    from tools import run_candidate_reranker_training as local
    path = local._local_path(path)
    raw = local._read(path, MAX_BUNDLE_BYTES)
    _require(_hash(expected_sha256) and hashlib.sha256(raw).hexdigest() == expected_sha256, "BUNDLE_SHA_MISMATCH")
    data = local._strict_json(raw)
    _require(set(data) == _BUNDLE_KEYS and data["schema_version"] == BUNDLE_SCHEMA, "BUNDLE_SCHEMA_INVALID")
    _require(_hash(data["expected_scorer_summary_sha256"]), "SCORER_SUMMARY_SHA_INVALID")
    snapshots = {str(path): raw}

    def read_ref(ref, limit):
        _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "REFERENCE_SCHEMA_INVALID")
        name = ref["path"]
        _require(type(name) is str and name and not Path(name).is_absolute() and not PureWindowsPath(name).drive
            and "://" not in name and "\\" not in name and all(p not in {"", ".", ".."} for p in name.split("/")),
            "REFERENCE_PATH_INVALID")
        _require(_hash(ref["sha256"]) and type(ref["bytes"]) is int and 0 <= ref["bytes"] <= limit,
                 "REFERENCE_SIZE_OR_SHA_INVALID")
        target = local._local_path(path.parent / name)
        _require(target.resolve().is_relative_to(path.parent.resolve()) and target != path, "REFERENCE_OUTSIDE_BUNDLE")
        payload = local._read(target, ref["bytes"])
        _require(len(payload) == ref["bytes"] and hashlib.sha256(payload).hexdigest() == ref["sha256"], "REFERENCE_BYTES_MISMATCH")
        _require(str(target) not in snapshots or snapshots[str(target)] == payload, "INPUT_CHANGED_DURING_LOAD")
        snapshots[str(target)] = payload
        return payload

    values = {key: local._strict_json(read_ref(data[key], MAX_JSON_BYTES))
              for key in ("artifact", "calibration_manifest", "policy")}
    from ..grounding.candidate_retrieval_shadow import MAX_CORPUS_BYTES
    values["corpus_snapshot"] = read_ref(data["corpus_snapshot"], MAX_CORPUS_BYTES)
    refs = data["source_files"]
    _require(type(refs) is dict and len(refs) <= 4096, "SOURCE_PAYLOAD_MAP_INVALID")
    payloads, total = {}, 0
    for digest, ref in refs.items():
        _require(_hash(digest) and type(ref) is dict and ref.get("sha256") == digest, "SOURCE_KEY_SHA_MISMATCH")
        payload = read_ref(ref, MAX_PAYLOAD_BYTES)
        total += len(payload)
        _require(total <= MAX_PAYLOAD_BYTES, "SOURCE_PAYLOAD_BYTE_LIMIT")
        payloads[digest] = payload
    local._check_inputs(snapshots)
    return {**values, "source_payloads": payloads, "bundle": data, "snapshots": snapshots}


def _summary(bundle_sha, scorer_summary, *, core=None, corpus_sha=None, reason=None):
    value = {"schema_version": "candidate_inference_policy_v1", "mode": "SHADOW",
        "scope": "BOUNDED_PINNED_R2_CORPUS", "status": "UNAVAILABLE" if reason else "AVAILABLE",
        "reason_codes": [reason] if reason else [], "bundle_sha256": bundle_sha if _hash(bundle_sha) else None,
        "corpus_sha256": corpus_sha, "expected_scorer_summary_sha256": _sha(scorer_summary),
        **{key: scorer_summary.get(key) for key in ("model_sha256", "scorer_sha256", "data_kind")},
        "calibration": core, "actual_quality_evaluated": False,
        "truth_status": "UNJUDGED_NOT_ASSIGNED", "quality_status": "NOT_EVALUATED_UNSEEN_INPUT", **_FLAGS}
    value["policy_sha256"] = _sha(value)
    return value


def _package(summary, post_id, status, reasons, *, graph=None, receipt=None, capture_sha=None):
    value = {"schema_version": PACKAGE_SCHEMA, "post_id": post_id, "status": status,
        "reason_codes": list(reasons), "bundle_sha256": summary["bundle_sha256"],
        "graph": graph, "inference": receipt, "capture_sha256": capture_sha}
    value["package_sha256"] = _sha(value)
    return value


@dataclass(frozen=True, slots=True)
class FrozenCandidateInference:
    _summary_json: bytes
    _scorer_summary_json: bytes
    _core: object = None
    _scorer: object = None
    _corpus_snapshot: bytes = b""
    _source_payloads: tuple = ()

    def summary(self):
        return json.loads(self._summary_json)

    def _validated_capture(self, post, capture, reranker_receipt):
        from ..grounding.candidate_reranker_capture import validate_capture, capture_semantic_payloads
        from .candidate_reranker import _source_view, _valid_receipt
        _require(capture is not None and post is not None, "CAPTURE_NOT_AVAILABLE")
        capture = validate_capture(capture)
        summary = json.loads(self._scorer_summary_json)
        _require(_equal(summary, self._scorer.summary()) and _equal(capture["scorer_summary"], summary), "CAPTURE_SCORER_MISMATCH")
        _require(_equal(capture["post_id"], post.post_id), "CAPTURE_POST_MISMATCH")
        _require(_equal(capture["frozen_view"]["source_view"], _source_view(post)), "CURRENT_SOURCE_MISMATCH")
        _require(_equal(reranker_receipt, capture["raw_receipt"]), "CAPTURE_RAW_RECEIPT_MISMATCH")
        _require(_valid_receipt(reranker_receipt, summary, post.post_id,
            require_roles="preselection_role_producer" in reranker_receipt), "RUNTIME_RECEIPT_INVALID")
        kwargs = {}
        if summary.get("semantic_input_required") is True:
            _require(capture["schema_version"] == "candidate_reranker_capture_v2", "SEMANTIC_CAPTURE_REQUIRED")
            kwargs = {"semantic_input": capture["semantic_input"], "evidence_payloads": capture_semantic_payloads(capture)}
        replay = self._scorer.score(_copy(capture["frozen_view"]), **kwargs)
        _require(_valid_receipt(replay, summary, post.post_id), "SCORE_REPLAY_INVALID")
        _require(_equal({k:v for k,v in replay.items() if k not in _SCORE_IGNORED},
                        {k:v for k,v in reranker_receipt.items() if k not in _SCORE_IGNORED}), "ACTUAL_SCORE_REPLAY_MISMATCH")
        return capture

    def observe(self, post, capture, reranker_receipt):
        summary, post_id = self.summary(), getattr(post, "post_id", None)
        if summary["status"] != "AVAILABLE":
            return _package(summary, post_id, "UNAVAILABLE", summary["reason_codes"])
        try:
            capture = self._validated_capture(post, capture, reranker_receipt)
            from ..grounding.candidate_reranker_inference_graph import build_inference_graph
            graph = build_inference_graph(capture, corpus_snapshot=self._corpus_snapshot, source_payloads=dict(self._source_payloads))
            receipt = self._core.apply(graph, capture=capture, corpus_snapshot=self._corpus_snapshot,
                                       source_payloads=dict(self._source_payloads))
            _require(type(receipt) is dict and type(receipt.get("status")) is str, "CORE_RECEIPT_INVALID")
            return _copy(_package(summary, post_id, receipt["status"], receipt.get("reason_codes", []),
                graph=graph, receipt=receipt, capture_sha=capture["capture_sha256"]))
        except Exception as exc:
            return _package(summary, post_id, "NOT_AVAILABLE", [_code(exc)])


def prepare_candidate_inference(settings, scorer):
    if settings["mode"] == "OFF":
        return None
    summary = {}
    try:
        _require(settings["mode"] == "SHADOW" and scorer is not None, "NIL_SCORER_REQUIRED")
        summary = _copy(scorer.summary())
        _require(type(summary) is dict, "SCORER_SUMMARY_INVALID")
        values = read_inference_bundle(settings["bundle_path"], expected_sha256=settings["bundle_sha256"])
        _require(values["bundle"]["expected_scorer_summary_sha256"] == _sha(summary), "BUNDLE_SCORER_MISMATCH")
        from ..grounding.candidate_reranker_calibration_inference import prepare_inference_calibration
        core = prepare_inference_calibration(scorer_summary=summary, artifact=values["artifact"],
            calibration_manifest=values["calibration_manifest"], policy=values["policy"])
        policy = _summary(settings["bundle_sha256"], summary, core=core.summary(),
            corpus_sha=hashlib.sha256(values["corpus_snapshot"]).hexdigest())
        return FrozenCandidateInference(_bytes(policy), _bytes(summary), core, scorer, values["corpus_snapshot"],
            tuple(sorted(values["source_payloads"].items())))
    except Exception as exc:
        if type(summary) is not dict:
            summary = {}
        return FrozenCandidateInference(_bytes(_summary(settings.get("bundle_sha256"), summary,
            reason=_code(exc, "BUNDLE_LOAD_ERROR"))), _bytes(summary))


def candidate_inference_policy_fields(observer, settings=None):
    if observer is None:
        return {}
    value = observer.summary()
    if settings is not None:
        value["setting_sources"] = dict(settings["sources"])
        value["policy_sha256"] = _sha({k:v for k,v in value.items() if k != "policy_sha256"})
    return {"candidate_inference_policy": value}


def observe_candidate_inference(observer, post, capture, reranker_receipt):
    return None if observer is None else observer.observe(post, capture, reranker_receipt)


def _store_artifact(payload, output_dir):
    from tools import run_candidate_reranker_training as local
    from tools.run_candidate_reranker_calibration import _rename_noreplace
    root = local._local_path(output_dir)
    folder = root / "candidate_inference_captures" / _sha(payload["binding"]["run_id"])[:16]
    local._local_path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (_sha(payload) + ".json")
    expected = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    _require(len(expected) <= MAX_ARTIFACT_BYTES, "INFERENCE_ARTIFACT_BYTE_LIMIT")
    pending = folder / f".{target.stem}.{uuid.uuid4().hex}.pending"
    local._write(pending, payload)
    _require(local._read(pending, MAX_ARTIFACT_BYTES) == expected, "PENDING_READBACK_MISMATCH")
    try:
        _rename_noreplace(pending, target)
    except FileExistsError:
        _require(local._read(target, MAX_ARTIFACT_BYTES) == expected, "EXISTING_ARTIFACT_MISMATCH")
    raw = local._read(target, MAX_ARTIFACT_BYTES)
    _require(raw == expected and _equal(local._strict_json(raw), payload), "SAVED_READBACK_MISMATCH")
    return {"path": target.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def export_candidate_inference_fields(result, observer, *, binding, output_dir, input_snapshot_sha256,
                                      current_post, retrieval_observer, semantic_observer=None):
    if observer is None:
        return {}
    summary = observer.summary()
    storage_binding, post_id = {}, None
    status, reasons, graph, inference, capture, artifact = "NOT_AVAILABLE", ["INVALID_STORAGE_BINDING"], None, None, None, None
    verified = False
    try:
        from .candidate_capture import _binding
        storage_binding = _binding(binding)
        post_id = storage_binding["post_id"]
        _require(_hash(input_snapshot_sha256), "INPUT_SNAPSHOT_REQUIRED")
        if result is None:
            status, reasons = "NOT_EXECUTED", ["PIPELINE_NOT_EXECUTED"]
        elif summary["status"] != "AVAILABLE":
            status, reasons = "UNAVAILABLE", summary["reason_codes"]
        else:
            _require(current_post is not None and _equal(current_post.post_id, post_id), "CURRENT_POST_MISMATCH")
            package = getattr(result, "_candidate_inference", None)
            _require(type(package) is dict, "INFERENCE_OBSERVATION_MISSING")
            capture = observer._validated_capture(current_post, getattr(result, "_candidate_reranker_capture", None),
                                                   getattr(result, "_candidate_reranker_shadow", None))
            _require(retrieval_observer is not None, "CURRENT_RETRIEVAL_REQUIRED")
            from .candidate_reranker import _source_view
            current_r2 = retrieval_observer.observe(_source_view(current_post))
            project = lambda value: {k:v for k,v in value.items() if k not in {"latency_ms", "binding"}}
            _require(_equal(project(current_r2), project(capture["retrieval_receipt"])), "CURRENT_R2_REPLAY_MISMATCH")
            _require(_equal(retrieval_observer.summary(), capture["retrieval_receipt"]["policy"]), "CURRENT_R2_POLICY_MISMATCH")
            if capture["schema_version"] == "candidate_reranker_capture_v2":
                from .candidate_semantics import bind_current_semantic_input
                semantic, _ = bind_current_semantic_input(getattr(result, "_candidate_reranker_semantics", None),
                    semantic_observer, current_post, retrieval_observer)
                _require(_equal(semantic, capture["semantic_input"]), "CURRENT_SEMANTIC_INPUT_MISMATCH")
            replay = observer.observe(current_post, capture, capture["raw_receipt"])
            _require(_equal(package, replay), "INFERENCE_PACKAGE_REPLAY_MISMATCH")
            status, reasons = replay["status"], replay["reason_codes"]
            graph, inference = replay["graph"], replay["inference"]
            verified = graph is not None and inference is not None
            if verified:
                payload = {"schema_version": ARTIFACT_SCHEMA, "binding": storage_binding,
                    "input_snapshot_sha256": input_snapshot_sha256, "bundle_sha256": summary["bundle_sha256"],
                    "graph": graph, "capture": capture, "inference": inference, "score_replay_verified": True,
                    "verification_scope": "CURRENT_SOURCE_R2_MODEL_REPLAY_AND_FITTED_TEMPERATURE", **_FLAGS}
                artifact = _store_artifact(payload, output_dir)
    except Exception as exc:
        status, reasons, graph, inference, capture, artifact = "NOT_AVAILABLE", [_code(exc)], None, None, None, None
        verified = False
    ref_status = "SAVED" if artifact else "NOT_EXECUTED" if status == "NOT_EXECUTED" else "NOT_AVAILABLE"
    shared = {"mode": "SHADOW", "post_id": post_id, "binding": storage_binding,
        "bundle_sha256": summary["bundle_sha256"], "input_snapshot_sha256": input_snapshot_sha256 if _hash(input_snapshot_sha256) else None,
        "graph_sha256": graph["graph_sha256"] if graph else None,
        "capture_sha256": capture["capture_sha256"] if capture else None, **_FLAGS}
    return {"candidate_reranker_inference": _seal({"schema_version": SCHEMA, **shared,
        "status": status, "reason_codes": reasons, "inference": inference,
        "score_replay_verified": verified,
        "verification_scope": "CURRENT_SOURCE_R2_MODEL_REPLAY_AND_FITTED_TEMPERATURE" if verified else "NOT_VERIFIED"}),
        "candidate_inference_capture": _seal({"schema_version": CAPTURE_REF_SCHEMA, **shared,
            "status": ref_status, "reason_codes": [] if artifact else reasons, "artifact": artifact})}
