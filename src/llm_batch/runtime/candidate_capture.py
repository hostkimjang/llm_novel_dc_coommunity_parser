"""선택 전 capture를 실행별 새 파일에 보존하고 작은 참조만 행에 저장한다."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from ..grounding.candidate_reranker_capture import (
    SCOPE, MAX_CAPTURE_BYTES, MAX_CAPTURE_V2_BYTES, SCHEMA_V2 as CAPTURE_V2,
    canonical_bytes, canonical_sha256, validate_capture,
)

SCHEMA = "candidate_reranker_capture_ref_v1"
ARTIFACT_SCHEMA = "candidate_reranker_capture_artifact_v1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_BINDING_KEYS = ("run_id", "input_index", "post_id", "attempt_id", "publication_scope_id")


def _seal(value):
    return {**value, "receipt_sha256": canonical_sha256(value)}


def _binding(value):
    if type(value) is not dict or set(value) != set(_BINDING_KEYS):
        raise ValueError("CAPTURE_BINDING_FIELDS")
    if type(value["input_index"]) is not int or value["input_index"] < 1:
        raise ValueError("CAPTURE_INPUT_INDEX")
    if not all(type(value[k]) is str and 0 < len(value[k].strip()) <= 512
               for k in ("run_id", "attempt_id", "publication_scope_id")):
        raise ValueError("CAPTURE_BINDING_TEXT")
    if not ((type(value["post_id"]) is int and 0 <= value["post_id"] <= 2**63 - 1)
            or (type(value["post_id"]) is str and 0 < len(value["post_id"].strip()) <= 128)):
        raise ValueError("CAPTURE_POST_ID")
    return {**value, "scope": "ATTEMPT_LOCAL_OBSERVATION"}


def _base(binding, reason):
    return {"schema_version": SCHEMA, "mode": "SHADOW", "status": "NOT_AVAILABLE",
        "reason_codes": [reason], "post_id": binding.get("post_id"), "binding": dict(binding),
        "observation_sha256": None, "capture_sha256": None, "frozen_view_sha256": None,
        "input_snapshot_sha256": None, "fragment_count": None, "candidate_count": None,
        "artifact": None, "scope": SCOPE, "training_readiness": "NOT_ASSIGNED_OR_ADJUDICATED",
        "publication_authority": False, "public_apply": False, "central_db_write": False}


def export_candidate_capture_fields(result, observer, *, binding, output_dir, input_snapshot_sha256,
                                    current_post=None, retrieval_observer=None, semantic_observer=None):
    """실제 관측·현재 행 결속·입력 파일 SHA를 검산한 뒤 파일을 배타 저장한다.

    동일 내용의 파일만 재사용한다. 실패한 파일은 성공 참조로 노출하지 않으며,
    원본 입력 JSONL의 byte 위치나 학습용 권리/정답을 새로 추론하지 않는다.
    """
    if observer is None:
        return {}
    fallback = _base({}, "INVALID_CAPTURE_BINDING")
    try:
        stored_binding = _binding(binding)
        fallback = _base(stored_binding, "CAPTURE_NOT_AVAILABLE")
        if result is None:
            fallback.update(status="NOT_EXECUTED", reason_codes=["PIPELINE_NOT_EXECUTED"])
            return {"candidate_reranker_capture": _seal(fallback)}
        raw = getattr(result, "_candidate_reranker_capture", None)
        if raw is None:
            return {"candidate_reranker_capture": _seal(fallback)}
        capture = validate_capture(raw)
        semantic = capture["schema_version"] == CAPTURE_V2
        artifact_limit = MAX_CAPTURE_V2_BYTES if semantic else MAX_CAPTURE_BYTES * 2
        if semantic:
            fallback["schema_version"] = "candidate_reranker_capture_ref_v2"
            from .candidate_semantics import bind_current_semantic_input
            verified, _ = bind_current_semantic_input(getattr(result, "_candidate_reranker_semantics", None),
                semantic_observer, current_post, retrieval_observer)
            if (canonical_bytes(verified) != canonical_bytes(capture["semantic_input"])
                    or canonical_bytes(observer.summary()) != canonical_bytes(capture["scorer_summary"])):
                raise ValueError("CAPTURE_CURRENT_SEMANTIC_CONTEXT_MISMATCH")
        if type(capture["post_id"]) is not type(binding["post_id"]) or capture["post_id"] != binding["post_id"]:
            raise ValueError("CAPTURE_POST_BINDING_MISMATCH")
        reranker = getattr(result, "_candidate_reranker_shadow", None)
        if canonical_bytes(reranker) != canonical_bytes(capture["raw_receipt"]):
            raise ValueError("CAPTURE_RAW_RECEIPT_MISMATCH")
        if type(input_snapshot_sha256) is not str or not _HASH.fullmatch(input_snapshot_sha256):
            raise ValueError("CAPTURE_INPUT_SNAPSHOT_REQUIRED")
        payload = {"schema_version": "candidate_reranker_capture_artifact_v2" if semantic else ARTIFACT_SCHEMA, "observation": capture,
            "binding": stored_binding, "input_snapshot_sha256": input_snapshot_sha256}
        payload["capture_sha256"] = canonical_sha256(payload)
        # 기존 학습/CAL CLI와 같은 로컬 파일 경계를 재사용한다. 학습 함수는 호출하지 않는다.
        from tools import run_candidate_reranker_training as local
        from tools.run_candidate_reranker_calibration import _rename_noreplace
        root = local._local_path(output_dir)
        folder = root / "candidate_reranker_captures" / canonical_sha256(binding["run_id"])[:16]
        local._local_path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (payload["capture_sha256"] + ".json")
        expected = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(expected) > artifact_limit:
            raise ValueError("CAPTURE_ARTIFACT_BYTE_LIMIT")
        pending = folder / f".{target.stem}.{uuid.uuid4().hex}.pending"
        local._write(pending, payload)
        if local._read(pending, artifact_limit) != expected:
            raise ValueError("CAPTURE_PENDING_READBACK_MISMATCH")
        # 완전한 파일만 최종 이름으로 공개한다. 실패한 임시 파일은 진단용으로
        # 보존하며 기존 최종 파일은 동일 bytes일 때만 재사용한다.
        try:
            _rename_noreplace(pending, target)
        except FileExistsError:
            if local._read(target, artifact_limit) != expected:
                raise ValueError("CAPTURE_EXISTING_ARTIFACT_MISMATCH")
        raw = local._read(target, artifact_limit)
        if raw != expected:
            raise ValueError("CAPTURE_SAVED_READBACK_MISMATCH")
        ref = {"path": target.relative_to(root).as_posix(),
               "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        fallback.update(status="SAVED", reason_codes=[], observation_sha256=capture["capture_sha256"],
            capture_sha256=payload["capture_sha256"], frozen_view_sha256=capture["frozen_view_sha256"],
            input_snapshot_sha256=input_snapshot_sha256,
            fragment_count=len(capture["source_fragments"]), candidate_count=len(capture["frozen_view"]["candidates"]),
            artifact=ref)
        return {"candidate_reranker_capture": _seal(fallback)}
    except Exception as exc:
        reason = str(exc)
        if not re.fullmatch(r"[A-Z0-9_]{1,96}", reason):
            reason = "CAPTURE_SAVE_OR_VALIDATION_FAILED"
        fallback.update(status="NOT_AVAILABLE", reason_codes=[reason], artifact=None)
        return {"candidate_reranker_capture": _seal(fallback)}
