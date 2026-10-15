"""선택 전 의미 관측과 원문 보존. 새 모델 계약에 결속된 입력 소비만 별도 검산한다."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import uuid

SCHEMA = "candidate_reranker_semantics_runtime_v1"
CAPTURE_SCHEMA = "candidate_reranker_semantics_capture_ref_v1"
BUNDLE_SCHEMA = "candidate_semantics_alias_bundle_v1"
MAX_BYTES = 8 * 1024 * 1024
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_EXECUTED = {"OBSERVED", "NO_MATCH", "AMBIGUOUS"}
_FAILED = {"NOT_EXECUTED", "NOT_AVAILABLE", "ERROR", "LIMIT_EXCEEDED", "INVALID_INPUT"}


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _copy(value):
    raw = _bytes(value)
    _require(len(raw) <= MAX_CAPTURE_BYTES, "SEMANTICS_BYTE_LIMIT")
    return json.loads(raw)


def _seal(value):
    return {**value, "receipt_sha256": _sha(value)}


def _reason(exc):
    code = getattr(exc, "code", str(exc))
    return code if type(code) is str and re.fullmatch(r"[A-Z0-9_]{1,96}", code) else "SEMANTICS_OBSERVATION_FAILED"


def resolve_candidate_semantics_settings(args, environment):
    settings, sources = {}, {}
    for key, attr, env, default in (
        ("mode", "candidate_semantics", "EXPERT_CANDIDATE_SEMANTICS", "OFF"),
        ("bundle_path", "semantic_alias_bundle", "EXPERT_SEMANTIC_ALIAS_BUNDLE", None),
        ("bundle_sha256", "semantic_alias_bundle_sha256", "EXPERT_SEMANTIC_ALIAS_BUNDLE_SHA256", None),
    ):
        value = getattr(args, attr, None)
        source = "CLI" if value is not None else "ENVIRONMENT" if env in environment else "DEFAULT"
        settings[key] = value if value is not None else environment.get(env, default)
        sources[key] = source
    _require(settings["mode"] in {"OFF", "SHADOW"}, "SEMANTICS_MODE_INVALID")
    if settings["mode"] == "SHADOW":
        _require(getattr(args, "candidate_retrieval", "OFF") == "SHADOW", "SEMANTICS_RETRIEVAL_SHADOW_REQUIRED")
        path, digest = settings["bundle_path"], settings["bundle_sha256"]
        _require((path is None and digest is None) or (type(path) is str and bool(path)
            and type(digest) is str and _HASH.fullmatch(digest)), "SEMANTICS_ALIAS_BUNDLE_PIN_REQUIRED")
    return {**settings, "sources": sources}


def _read_bundle(path, pin):
    from tools import run_candidate_reranker_training as local
    target = local._local_path(path)
    raw = local._read(target, MAX_BYTES)
    _require(hashlib.sha256(raw).hexdigest() == pin, "SEMANTICS_BUNDLE_SHA_MISMATCH")
    bundle = local._strict_json(raw)
    _require(set(bundle) == {"schema_version", "alias_evidence", "evidence_files"}
        and bundle["schema_version"] == BUNDLE_SCHEMA and type(bundle["alias_evidence"]) is dict
        and type(bundle["evidence_files"]) is dict, "SEMANTICS_BUNDLE_SCHEMA")
    _require(not {"retrieval_receipt", "community_source_view"}.intersection(bundle["alias_evidence"]),
        "SEMANTICS_BUNDLE_PER_POST_CONTEXT_FORBIDDEN")
    _require(len(bundle["evidence_files"]) <= 8000, "SEMANTICS_FILE_COUNT_LIMIT")
    payloads, snapshots, total = {}, {str(target): raw}, 0
    for key, ref in bundle["evidence_files"].items():
        _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "SEMANTICS_FILE_REF_SCHEMA")
        name = ref["path"]
        _require(type(name) is str and bool(name) and not Path(name).is_absolute()
            and not PureWindowsPath(name).drive and "\\" not in name and "://" not in name
            and all(p not in ("", ".", "..") for p in name.split("/")), "SEMANTICS_FILE_PATH_INVALID")
        _require(type(key) is str and _HASH.fullmatch(key) and key == ref["sha256"]
            and type(ref["bytes"]) is int and 0 <= ref["bytes"] <= MAX_BYTES, "SEMANTICS_FILE_PIN_INVALID")
        file = local._local_path(target.parent / name)
        _require(file.resolve().is_relative_to(target.parent.resolve()) and file != target, "SEMANTICS_FILE_OUTSIDE_BUNDLE")
        data = local._read(file, ref["bytes"])
        _require(len(data) == ref["bytes"] and hashlib.sha256(data).hexdigest() == key, "SEMANTICS_FILE_SHA_MISMATCH")
        payloads[key] = data
        snapshots[str(file)] = data
        total += len(data)
        _require(total <= MAX_BYTES, "SEMANTICS_PAYLOAD_BYTE_LIMIT")
    local._check_inputs(snapshots)
    from ..grounding.candidate_reranker_alias_evidence import prepare_alias_evidence
    prepare_alias_evidence(alias_evidence=bundle["alias_evidence"], evidence_payloads=payloads)
    return bundle["alias_evidence"], payloads, raw


@dataclass(frozen=True)
class CandidateSemanticsObserver:
    alias_json: bytes = b"null"
    payloads: tuple = ()
    bundle_sha256: str | None = None
    bundle_raw: bytes | None = None

    def summary(self):
        from ..grounding.candidate_reranker_semantics import POLICY, POLICY_SHA256, SCHEMA_VERSION
        return _copy({"schema_version": "candidate_reranker_semantics_policy_v1", "mode": "SHADOW",
            "producer_schema": SCHEMA_VERSION, "policy": POLICY, "policy_sha256": POLICY_SHA256,
            "alias_bundle_sha256": self.bundle_sha256, "alias_evidence_sha256": _sha(json.loads(self.alias_json)),
            "score_consumption_status": "NOT_CONSUMED_MODEL_POLICY_UNBOUND",
            "actual_quality_evaluated": False,
            "publication_authority": False, "public_apply": False, "central_db_write": False})


def prepare_candidate_semantics(settings):
    if settings["mode"] == "OFF":
        return None
    alias, payloads, raw = None, {}, None
    if settings["bundle_path"] is not None:
        alias, payloads, raw = _read_bundle(settings["bundle_path"], settings["bundle_sha256"])
    return CandidateSemanticsObserver(_bytes(alias), tuple(sorted(payloads.items())), settings["bundle_sha256"], raw)


def candidate_semantics_policy_fields(observer, settings=None):
    if observer is None:
        return {}
    summary = observer.summary()
    if settings is not None:
        summary.update(setting_sources=dict(settings["sources"]), alias_bundle_path=settings["bundle_path"])
    return {"candidate_reranker_semantics_policy": summary}


def _community_view(post, source):
    gallery = getattr(post, "gallery_id", None)
    community = gallery if ("gallery_id" in getattr(post, "model_fields_set", set()) and type(gallery) is str
        and gallery.strip() and gallery.lower() not in {"test", "unknown"}) else None
    as_of, raw_time = None, getattr(post, "created_at", None)
    if type(raw_time) is str and raw_time.strip():
        try:
            parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if parsed.utcoffset() is not None:
                as_of = parsed.isoformat()
        except ValueError:
            pass
    return {"schema_version": "community_knowledge_source_view_v1", "post_id": source["post_id"],
        "fragments": _copy(source["fragments"]),
        "community": {"value": community, "source_path": "/gallery_id", "status": "EXPLICIT" if community else "UNKNOWN"},
        "as_of": {"value": as_of, "source_path": "/created_at", "status": "EXPLICIT" if as_of else "UNKNOWN"}}


def _retrieval_view(source, receipt, summary):
    from ..grounding.candidate_reranker_shadow import build_frozen_view
    _require(type(receipt) is dict and receipt.get("schema_version") == "candidate_retrieval_shadow_v1"
        and receipt.get("mode") == "SHADOW" and type(receipt.get("post_id")) is type(source["post_id"])
        and receipt["post_id"] == source["post_id"] and receipt.get("query_sha256") == _sha(source), "SEMANTICS_RETRIEVAL_SOURCE_MISMATCH")
    _require(all(receipt.get(k) is False for k in ("publication_authority", "public_apply", "central_db_write")),
        "SEMANTICS_RETRIEVAL_AUTHORITY")
    _require(receipt.get("status") in {"OK", "NO_MATCH"}, "SEMANTICS_RETRIEVAL_NOT_COMPLETE")
    _require(all(receipt.get(k) == summary.get(k) and receipt.get(k) is not None
        for k in ("corpus_sha256", "scorer_sha256", "config_sha256")), "SEMANTICS_RETRIEVAL_POLICY_MISMATCH")
    _require(receipt.get("observation_sha256") == _sha({k: v for k, v in receipt.items()
        if k not in {"observation_sha256", "latency_ms", "binding"}}), "SEMANTICS_RETRIEVAL_DIGEST_MISMATCH")
    view = build_frozen_view(source, receipt)
    _require(view["generation_status"] == "COMPLETE", "SEMANTICS_GENERATION_NOT_COMPLETE")
    return view


def observe_candidate_semantics(observer, post, retrieval_receipt, retrieval_observer):
    if observer is None:
        return None
    package = {"status": "NOT_AVAILABLE", "reason_codes": ["RETRIEVAL_NOT_EXECUTED"], "post_id": post.post_id,
        "observer_sha256": _sha(observer.summary()), "original_view": None, "enriched_view": None,
        "observation": None, "retrieval_receipt": None, "retrieval_summary": None, "alias_evidence": None}
    try:
        if retrieval_observer is None or retrieval_receipt is None:
            return package
        from .candidate_reranker import _source_view
        source, receipt, summary = _source_view(post), _copy(retrieval_receipt), _copy(retrieval_observer.summary())
        view = _retrieval_view(source, receipt, summary)
        alias = json.loads(observer.alias_json)
        if alias is not None:
            alias.update(retrieval_receipt=receipt, community_source_view=_community_view(post, source))
        from ..grounding.candidate_reranker_semantics import observe_preselection_semantics, validate_semantic_observation
        enriched, observation = observe_preselection_semantics(view, alias_evidence=alias, evidence_payloads=dict(observer.payloads))
        validate_semantic_observation(view, enriched, observation, alias_evidence=alias, evidence_payloads=dict(observer.payloads))
        _require(observation["status"] in _EXECUTED, "SEMANTICS_PRODUCER_STATUS_INVALID")
        package.update(status=observation["status"], reason_codes=observation["reason_codes"], original_view=view,
            enriched_view=enriched, observation=observation, retrieval_receipt=receipt, retrieval_summary=summary, alias_evidence=alias)
    except Exception as exc:
        code = _reason(exc)
        package.update(status="LIMIT_EXCEEDED" if code.endswith("LIMIT") else "ERROR", reason_codes=[code])
    return _copy(package)


def _validate_package(package, observer, post_id):
    value = _copy(package)
    _require(type(value) is dict and set(value) == {"status", "reason_codes", "post_id", "observer_sha256",
        "original_view", "enriched_view", "observation", "retrieval_receipt", "retrieval_summary", "alias_evidence"},
        "SEMANTICS_PACKAGE_SCHEMA")
    _require(type(value["post_id"]) is type(post_id) and value["post_id"] == post_id
        and value["observer_sha256"] == _sha(observer.summary()), "SEMANTICS_PACKAGE_BINDING_MISMATCH")
    _require(type(value["status"]) is str and value["status"] in _EXECUTED | _FAILED
        and type(value["reason_codes"]) is list and len(value["reason_codes"]) <= 128
        and all(type(c) is str and re.fullmatch(r"[A-Z0-9_]{1,96}", c) for c in value["reason_codes"]), "SEMANTICS_PACKAGE_STATUS")
    if value["status"] not in _EXECUTED:
        _require(all(value[k] is None for k in ("original_view", "enriched_view", "observation",
            "retrieval_receipt", "retrieval_summary", "alias_evidence")), "SEMANTICS_FAILURE_WITH_OBSERVATION")
        return value
    original = value["original_view"]
    _require(type(original["post_id"]) is type(post_id) and original["post_id"] == post_id, "SEMANTICS_VIEW_POST_MISMATCH")
    _require(_bytes(original) == _bytes(_retrieval_view(original["source_view"], value["retrieval_receipt"],
        value["retrieval_summary"])), "SEMANTICS_RETRIEVAL_VIEW_MISMATCH")
    alias = json.loads(observer.alias_json)
    if alias is not None:
        supplied = value["alias_evidence"]
        _require(type(supplied) is dict and _bytes({k:v for k,v in supplied.items()
            if k not in {"retrieval_receipt", "community_source_view"}}) == _bytes(alias), "SEMANTICS_ALIAS_STATIC_MISMATCH")
        _require(_bytes(supplied["retrieval_receipt"]) == _bytes(value["retrieval_receipt"]), "SEMANTICS_ALIAS_RETRIEVAL_MISMATCH")
    else:
        _require(value["alias_evidence"] is None, "SEMANTICS_UNCONFIGURED_ALIAS")
    from ..grounding.candidate_reranker_semantics import validate_semantic_observation
    observed = validate_semantic_observation(original, value["enriched_view"], value["observation"],
        alias_evidence=value["alias_evidence"], evidence_payloads=dict(observer.payloads))
    _require(value["status"] == observed["status"] and value["reason_codes"] == observed["reason_codes"],
        "SEMANTICS_OBSERVATION_STATUS_MISMATCH")
    return value


def bind_current_semantic_input(package, observer, post, retrieval_observer):
    """현재 원문/R2와 독립 대조한 producer만 점수 입력으로 결속한다. IO 없음."""
    from .candidate_reranker import _source_view
    from ..grounding.candidate_reranker_semantic_input import build_semantic_input
    _require(observer is not None and post is not None and retrieval_observer is not None,
             "SEMANTICS_CURRENT_CONTEXT_REQUIRED")
    package = _validate_package(package, observer, post.post_id)
    _require(package["status"] in _EXECUTED, "SEMANTICS_NOT_EXECUTED")
    source = _source_view(post)
    summary = _copy(retrieval_observer.summary())
    fresh = retrieval_observer.observe(source)
    _require(_bytes(package["original_view"]) == _bytes(_retrieval_view(source, fresh, summary))
        and _bytes(package["retrieval_summary"]) == _bytes(summary), "SEMANTICS_CURRENT_CONTEXT_MISMATCH")
    if package["alias_evidence"] is not None:
        _require(_bytes(package["alias_evidence"]["community_source_view"]) == _bytes(_community_view(post, source)),
                 "SEMANTICS_CURRENT_COMMUNITY_MISMATCH")
    payloads = dict(observer.payloads)
    artifact = build_semantic_input(package["original_view"], retrieval_receipt=package["retrieval_receipt"],
        alias_evidence=package["alias_evidence"], evidence_payloads=payloads)
    _require(_bytes(artifact["enriched_view"]) == _bytes(package["enriched_view"])
        and _bytes(artifact["observation"]) == _bytes(package["observation"]), "SEMANTICS_SCORE_INPUT_MISMATCH")
    return artifact, {key: payloads[key] for key in artifact["alias_payload_sha256"]}


def _publish(root, folder_name, payload):
    from tools import run_candidate_reranker_training as local
    from tools.run_candidate_reranker_calibration import _rename_noreplace
    root = local._local_path(root)
    folder = local._local_path(root / folder_name)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (_sha(payload) + ".json")
    expected = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    _require(len(expected) <= MAX_CAPTURE_BYTES, "SEMANTICS_CAPTURE_BYTE_LIMIT")
    pending = folder / ("." + path.stem + "." + uuid.uuid4().hex + ".pending")
    local._write(pending, payload)
    _require(local._read(pending, MAX_CAPTURE_BYTES) == expected, "SEMANTICS_CAPTURE_PENDING_MISMATCH")
    try:
        _rename_noreplace(pending, path)
    except FileExistsError:
        _require(local._read(path, MAX_CAPTURE_BYTES) == expected, "SEMANTICS_CAPTURE_EXISTING_MISMATCH")
    raw = local._read(path, MAX_CAPTURE_BYTES)
    _require(raw == expected, "SEMANTICS_CAPTURE_READBACK_MISMATCH")
    return {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def export_candidate_semantics_fields(result, observer, *, binding, output_dir, input_snapshot_sha256,
                                     current_post=None, retrieval_observer=None, scorer=None, calibration_observer=None):
    if observer is None:
        return {}
    from .candidate_capture import _binding
    row = {"schema_version": SCHEMA, "mode": "SHADOW", "status": "NOT_AVAILABLE", "reason_codes": ["SEMANTICS_NOT_AVAILABLE"],
        "post_id": binding.get("post_id"), "binding": {}, "observation": None,
        "consumption": {"status": "NOT_AVAILABLE", "scorer_input_applied": False, "calibration_input_applied": False,
            "reason_codes": ["ROLE_POLICY_TRAINING_BINDING_PENDING"], "scorer_input_sha256": None},
        "publication_authority": False, "public_apply": False, "central_db_write": False}
    capture = {"schema_version": CAPTURE_SCHEMA, "mode": "SHADOW", "status": "NOT_AVAILABLE", "reason_codes": ["SEMANTICS_CAPTURE_NOT_AVAILABLE"],
        "post_id": row["post_id"], "binding": {}, "artifact": None, "observation_sha256": None,
        "capture_sha256": None, "input_snapshot_sha256": None,
        "training_readiness": "NOT_ASSIGNED_OR_ADJUDICATED", "publication_authority": False, "public_apply": False, "central_db_write": False}
    def exported():
        return {"candidate_reranker_semantics": _seal(row), "candidate_reranker_semantics_capture": _seal(capture)}
    try:
        stored = _binding(binding)
        row["binding"] = capture["binding"] = stored
        if result is None:
            row["consumption"]["status"] = "NOT_EXECUTED"
            for value in (row, capture):
                value.update(status="NOT_EXECUTED", reason_codes=["PIPELINE_NOT_EXECUTED"])
            return exported()
        package = getattr(result, "_candidate_reranker_semantics", None)
        if package is None:
            return exported()
        package = _validate_package(package, observer, binding["post_id"])
        if package["status"] in _EXECUTED:
            # 패키지 자체 SHA 외에 현재 입력과 현재 고정 R2를 독립적으로 재관측한다.
            from .candidate_reranker import _source_view
            _require(current_post is not None and retrieval_observer is not None,
                "SEMANTICS_CURRENT_CONTEXT_REQUIRED")
            source = _source_view(current_post)
            current_summary = _copy(retrieval_observer.summary())
            current_receipt = retrieval_observer.observe(source)
            _require(_bytes(package["original_view"]) == _bytes(_retrieval_view(source, current_receipt, current_summary))
                and _bytes(package["retrieval_summary"]) == _bytes(current_summary), "SEMANTICS_CURRENT_CONTEXT_MISMATCH")
            if package["alias_evidence"] is not None:
                _require(_bytes(package["alias_evidence"]["community_source_view"]) == _bytes(_community_view(current_post, source)),
                    "SEMANTICS_CURRENT_COMMUNITY_MISMATCH")
        row.update(status=package["status"], reason_codes=package["reason_codes"], observation=package["observation"])
        row["consumption"]["status"] = "OBSERVED_NOT_CONSUMED" if package["status"] in _EXECUTED else "NOT_CONSUMED_OBSERVATION_FAILED"
        score_receipt = getattr(result, "_candidate_reranker_shadow", None)
        if type(score_receipt) is dict and score_receipt.get("semantic_input_required") is True:
            row["schema_version"] = "candidate_reranker_semantics_runtime_v2"
            try:
                from .candidate_reranker import _valid_receipt
                _require(scorer is not None, "SEMANTIC_SCORER_CONTEXT_REQUIRED")
                _require("binding" not in score_receipt or score_receipt["binding"] == stored,
                    "SEMANTIC_SCORE_ATTEMPT_MISMATCH")
                _require(_valid_receipt(score_receipt, scorer.summary(), binding["post_id"]),
                    "SEMANTIC_SCORE_RECEIPT_INVALID")
                consumed = score_receipt["semantic_consumption"]
                if consumed["input_validated"]:
                    semantic_input, _ = bind_current_semantic_input(package, observer, current_post, retrieval_observer)
                    _require(consumed["semantic_input_sha256"] == semantic_input["input_sha256"]
                        and consumed["semantic_observation_sha256"] == _sha(package["observation"])
                        and consumed["scorer_input_sha256"] == _sha(package["enriched_view"]),
                        "SEMANTIC_SCORE_INPUT_MISMATCH")
                calibrated = False
                calibration = getattr(result, "_candidate_calibration_shadow", None)
                raw_capture = getattr(result, "_candidate_reranker_capture", None)
                if (calibration_observer is not None and type(calibration) is dict
                        and calibration.get("status") == "CALIBRATED_SHADOW_BOUND"):
                    replay = calibration_observer.observe(current_post, raw_capture, score_receipt)
                    _require(_bytes(replay) == _bytes(calibration), "SEMANTIC_CALIBRATION_CONSUMPTION_MISMATCH")
                    calibrated = replay.get("status") == "CALIBRATED_SHADOW_BOUND"
                row["consumption"] = {**_copy(consumed), "scorer_input_applied": consumed["backend_invoked"],
                    "calibration_input_applied": calibrated, "score_receipt_sha256": score_receipt["receipt_sha256"],
                    "model_sha256": score_receipt.get("model_sha256"), "scorer_sha256": score_receipt.get("scorer_sha256")}
            except Exception as exc:
                row["consumption"] = {"status": "NOT_AVAILABLE", "scorer_input_applied": None,
                    "calibration_input_applied": None, "reason_codes": [_reason(exc)], "scorer_input_sha256": None}
        elif type(score_receipt) is dict and type(score_receipt.get("post_id")) is type(binding["post_id"]) and score_receipt["post_id"] == binding["post_id"]:
            digest = score_receipt.get("input_sha256")
            if package["status"] in _EXECUTED and type(digest) is str and _HASH.fullmatch(digest):
                try:
                    from ..grounding.candidate_reranker_roles import observe_preselection_roles
                    legacy, _ = observe_preselection_roles(package["original_view"])
                    if digest == _sha(legacy) and score_receipt.get("receipt_sha256") == _sha({k:v for k,v in score_receipt.items()
                        if k not in {"receipt_sha256", "latency_ms", "binding"}}):
                        row["consumption"]["scorer_input_sha256"] = digest
                except Exception:
                    # 선택적인 구형 점수 지문은 신규 관측의 저장 가능성을 바꾸지 않는다.
                    pass
        if package["status"] not in _EXECUTED:
            return exported()
    except Exception as exc:
        row.update(status="NOT_AVAILABLE", reason_codes=[_reason(exc)], observation=None)
        row["consumption"]["status"] = "NOT_AVAILABLE"
        return exported()
    try:
        _require(type(input_snapshot_sha256) is str and _HASH.fullmatch(input_snapshot_sha256), "SEMANTICS_INPUT_SNAPSHOT_REQUIRED")
        evidence_ref = None
        if observer.payloads:
            evidence_ref = _publish(output_dir, "candidate_semantics_evidence", {
                "schema_version": "candidate_semantics_evidence_archive_v1", "alias_static": json.loads(observer.alias_json),
                "bundle_raw_base64": base64.b64encode(observer.bundle_raw).decode("ascii") if observer.bundle_raw is not None else None,
                "payloads_base64": {key: base64.b64encode(raw).decode("ascii") for key,raw in observer.payloads}})
        artifact = {"schema_version": "candidate_reranker_semantics_capture_artifact_v1", "package": package,
            "binding": stored, "input_snapshot_sha256": input_snapshot_sha256, "evidence_archive": evidence_ref,
            "observer_summary": observer.summary(), "scope": "PRE_SELECTION_PARSED_SOURCE_SNAPSHOT"}
        artifact["capture_sha256"] = _sha(artifact)
        ref = _publish(output_dir, "candidate_semantics_captures/" + _sha(binding["run_id"])[:16], artifact)
        capture.update(status="SAVED", reason_codes=[], artifact=ref,
            observation_sha256=_sha(package["observation"]), capture_sha256=artifact["capture_sha256"], input_snapshot_sha256=input_snapshot_sha256)
    except Exception as exc:
        capture.update(reason_codes=[_reason(exc)])
    return exported()


def read_candidate_semantics_capture(output_dir, reference):
    """저장 참조·공통 별칭 원문을 읽고 producer를 재생한다. 원본 실행·정답을 새로 주장하지 않는다."""
    from tools import run_candidate_reranker_training as local
    from .candidate_capture import _binding
    root = local._local_path(output_dir)
    def read_ref(ref):
        _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "SEMANTICS_CAPTURE_REF_SCHEMA")
        name = ref["path"]
        _require(type(name) is str and bool(name) and not Path(name).is_absolute() and not PureWindowsPath(name).drive
            and "\\" not in name and "://" not in name and all(p not in ("", ".", "..") for p in name.split("/")),
            "SEMANTICS_CAPTURE_REF_PATH")
        _require(type(ref["sha256"]) is str and _HASH.fullmatch(ref["sha256"])
            and type(ref["bytes"]) is int and 0 < ref["bytes"] <= MAX_CAPTURE_BYTES, "SEMANTICS_CAPTURE_REF_PIN")
        path = local._local_path(root / name)
        _require(path.resolve().is_relative_to(root.resolve()), "SEMANTICS_CAPTURE_OUTSIDE_ROOT")
        raw = local._read(path, ref["bytes"])
        _require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], "SEMANTICS_CAPTURE_REF_SHA")
        return local._strict_json(raw)
    artifact = read_ref(reference)
    _require(set(artifact) == {"schema_version", "package", "binding", "input_snapshot_sha256", "evidence_archive",
        "observer_summary", "scope", "capture_sha256"}
        and artifact["schema_version"] == "candidate_reranker_semantics_capture_artifact_v1"
        and artifact["scope"] == "PRE_SELECTION_PARSED_SOURCE_SNAPSHOT", "SEMANTICS_CAPTURE_ARTIFACT_SCHEMA")
    _require(artifact["capture_sha256"] == _sha({k:v for k,v in artifact.items() if k != "capture_sha256"}), "SEMANTICS_CAPTURE_SELF_SHA")
    stored = artifact["binding"]
    _require(type(stored) is dict and _binding({k:v for k,v in stored.items() if k != "scope"}) == stored,
        "SEMANTICS_CAPTURE_BINDING")
    _require(type(artifact["input_snapshot_sha256"]) is str and _HASH.fullmatch(artifact["input_snapshot_sha256"]),
        "SEMANTICS_CAPTURE_INPUT_PIN")
    summary = artifact["observer_summary"]
    _require(type(summary) is dict, "SEMANTICS_CAPTURE_SUMMARY")
    alias, payloads, bundle_raw = None, {}, None
    if artifact["evidence_archive"] is not None:
        archive = read_ref(artifact["evidence_archive"])
        _require(set(archive) == {"schema_version", "alias_static", "bundle_raw_base64", "payloads_base64"}
            and archive["schema_version"] == "candidate_semantics_evidence_archive_v1"
            and type(archive["payloads_base64"]) is dict and len(archive["payloads_base64"]) <= 4096, "SEMANTICS_ARCHIVE_SCHEMA")
        alias = archive["alias_static"]
        total = 0
        for key, encoded in archive["payloads_base64"].items():
            _require(type(key) is str and _HASH.fullmatch(key) and type(encoded) is str, "SEMANTICS_ARCHIVE_PAYLOAD_SCHEMA")
            data = base64.b64decode(encoded, validate=True)
            _require(hashlib.sha256(data).hexdigest() == key, "SEMANTICS_ARCHIVE_PAYLOAD_SHA")
            total += len(data)
            _require(total <= MAX_BYTES, "SEMANTICS_ARCHIVE_BYTE_LIMIT")
            payloads[key] = data
        if archive["bundle_raw_base64"] is not None:
            bundle_raw = base64.b64decode(archive["bundle_raw_base64"], validate=True)
            _require(hashlib.sha256(bundle_raw).hexdigest() == summary.get("alias_bundle_sha256"), "SEMANTICS_ARCHIVE_BUNDLE_SHA")
            bundle = local._strict_json(bundle_raw)
            _require(set(bundle) == {"schema_version", "alias_evidence", "evidence_files"}
                and bundle["schema_version"] == BUNDLE_SCHEMA and _bytes(bundle["alias_evidence"]) == _bytes(alias)
                and type(bundle["evidence_files"]) is dict and set(bundle["evidence_files"]) == set(payloads), "SEMANTICS_ARCHIVE_BUNDLE_SCHEMA")
            for key, ref in bundle["evidence_files"].items():
                _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}
                    and ref["sha256"] == key and type(ref["bytes"]) is int and ref["bytes"] == len(payloads[key]),
                    "SEMANTICS_ARCHIVE_BUNDLE_PAYLOAD_BINDING")
        from ..grounding.candidate_reranker_alias_evidence import prepare_alias_evidence
        prepare_alias_evidence(alias_evidence=alias, evidence_payloads=payloads)
    _require((bundle_raw is not None) == (summary.get("alias_bundle_sha256") is not None), "SEMANTICS_ARCHIVE_BUNDLE_PIN_MISSING")
    observer = CandidateSemanticsObserver(_bytes(alias), tuple(sorted(payloads.items())), summary.get("alias_bundle_sha256"), bundle_raw)
    _require(_bytes(observer.summary()) == _bytes(summary), "SEMANTICS_CAPTURE_POLICY_MISMATCH")
    package = _validate_package(artifact["package"], observer, stored["post_id"])
    _require(package["status"] in _EXECUTED, "SEMANTICS_CAPTURE_NOT_OBSERVED")
    return artifact
