"""커뮤니티 지식 READ_ONLY 설정·판정 범위·행별 소비 기록 경계."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

MAX_RECEIPT_BYTES = 64 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SETTINGS = {
    "mode": ("community_knowledge", "EXPERT_COMMUNITY_KNOWLEDGE", "OFF"),
    "snapshot_path": ("community_snapshot", "EXPERT_COMMUNITY_SNAPSHOT", None),
    "snapshot_sha256": ("community_snapshot_sha256", "EXPERT_COMMUNITY_SNAPSHOT_SHA256", None),
}


def resolve_community_knowledge_settings(args: Any, environment: Mapping[str, str]) -> dict:
    """CLI > 환경변수 > 기본 OFF. 실행 프로필은 이 기능을 자동 활성화하지 않는다."""
    values, sources = {}, {}
    for key, (attribute, env_key, default) in _SETTINGS.items():
        value = getattr(args, attribute, None)
        if value is not None:
            sources[key] = "CLI"
        elif env_key in environment:
            value, sources[key] = environment[env_key], "ENVIRONMENT"
        else:
            value, sources[key] = default, "DEFAULT"
        values[key] = value
    if values["mode"] not in {"OFF", "READ_ONLY"}:
        raise ValueError("커뮤니티 지식 모드는 OFF 또는 READ_ONLY여야 합니다")
    if values["mode"] == "READ_ONLY":
        if not values["snapshot_path"] or not isinstance(values["snapshot_sha256"], str) or not _SHA256.fullmatch(values["snapshot_sha256"]):
            raise ValueError("READ_ONLY에는 snapshot manifest 경로와 소문자 SHA-256을 명시해야 합니다")
    return {**values, "sources": sources}


def prepare_community_knowledge(settings: Mapping[str, Any]):
    """OFF는 저장소 모듈을 import하거나 파일을 읽지 않는다. 손상 snapshot은 명시적 미가용이다."""
    if settings["mode"] == "OFF":
        return None
    if settings["mode"] != "READ_ONLY":
        raise ValueError("지원하지 않는 커뮤니티 지식 모드")
    from ..grounding.community_knowledge import load_snapshot, unavailable_snapshot
    try:
        return load_snapshot(Path(settings["snapshot_path"]), expected_sha256=settings["snapshot_sha256"])
    except Exception as exc:
        reason = str(getattr(exc, "code", "SNAPSHOT_LOAD_ERROR"))[:96]
        return unavailable_snapshot(reason, expected_sha256=settings["snapshot_sha256"])


def community_knowledge_policy_fields(snapshot: Any, settings: Mapping[str, Any] | None = None) -> dict:
    if snapshot is None:
        return {}
    policy = copy.deepcopy(snapshot.summary())
    policy.update(mode="READ_ONLY", slang_db_enabled=False, batch_context_learning_enabled=False,
                  central_db_write=False, public_authority=False, model_input_may_change=True)
    if settings is not None:
        policy["snapshot_path"] = str(Path(settings["snapshot_path"]).absolute())
        policy["setting_sources"] = dict(settings["sources"])
    return {"community_knowledge_policy": policy}


def community_knowledge_decision_fields(snapshot: Any) -> dict:
    """모델 입력을 바꾸는 snapshot/config를 WAL 판정 범위에 결속한다. OFF의 기존 지문은 유지한다."""
    if snapshot is None:
        return {}
    summary = copy.deepcopy(snapshot.summary())
    # 준비 실패 상태도 정상 snapshot과 같은 캐시/판정 범위로 취급하지 않는다.
    policy = {key: summary.get(key) for key in ("snapshot_sha256", "config_sha256", "status", "reason_codes")}
    policy.update(schema_version="community_knowledge_decision_config_v1", mode="READ_ONLY",
                  slang_db_enabled=False, batch_context_learning_enabled=False,
                  policy_sha256=hashlib.sha256(json.dumps(summary, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest())
    return {"community_knowledge": policy}


def _unavailable(reason: str, post_id: Any, summary: Mapping[str, Any]) -> dict:
    return {"schema_version": "community_knowledge_readback_v1", "mode": "READ_ONLY",
            "status": "NOT_AVAILABLE", "reason_codes": [reason], "post_id": post_id,
            "snapshot_sha256": summary.get("snapshot_sha256"), "config_sha256": summary.get("config_sha256"),
            "data_kind": summary.get("data_kind"), "query_sha256": None,
            "candidates": [], "occurrences": [], "consumption": {"status": "NOT_CONSUMED_ERROR"},
            "public_authority": False, "central_db_write": False, "public_apply": False}


def _seal_receipt(receipt: dict) -> dict:
    receipt["receipt_digest_scope"] = "CANONICAL_EXCLUDING_ELAPSED_SELF_AND_STORAGE_BINDING"
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(
        {key: value for key, value in receipt.items() if key not in {"elapsed_ms", "latency_ms", "receipt_sha256", "binding"}},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return receipt


def export_community_knowledge_fields(result: Any, snapshot: Any, *, binding: Mapping[str, Any]) -> dict:
    """이번 게시글·snapshot의 크기가 제한된 private receipt만 저장한다."""
    if snapshot is None:
        return {}
    summary = snapshot.summary()
    raw = getattr(result, "_community_knowledge_readback", None) if result is not None else None
    if raw is None:
        receipt = _unavailable("PIPELINE_NOT_EXECUTED" if result is None else "RECEIPT_NOT_AVAILABLE", binding.get("post_id"), summary)
        if result is None:
            receipt["consumption"]["status"] = "NOT_CONSUMED_FAST_PATH"
    else:
        try:
            encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if len(encoded.encode("utf-8")) > MAX_RECEIPT_BYTES - 4096:
                raise ValueError("receipt byte limit")
            receipt = json.loads(encoded)
            if not isinstance(receipt, dict) or str(receipt.get("post_id")) != str(binding.get("post_id")):
                raise ValueError("post binding mismatch")
            if receipt.get("schema_version") != "community_knowledge_readback_v1" or receipt.get("mode") != "READ_ONLY":
                raise ValueError("unknown receipt schema")
            if any(receipt.get(key) is not False for key in ("public_authority", "central_db_write", "public_apply")):
                raise ValueError("candidate authority mismatch")
            expected = summary
            if any(receipt.get(key) != expected.get(key) for key in ("snapshot_sha256", "config_sha256")):
                raise ValueError("snapshot/config binding mismatch")
            body = {key: value for key, value in receipt.items()
                    if key not in {"elapsed_ms", "latency_ms", "receipt_sha256", "binding"}}
            digest = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
            if receipt.get("receipt_sha256") != digest:
                raise ValueError("receipt digest mismatch")
            if "binding" in receipt and receipt["binding"] != {**dict(binding), "scope": "ATTEMPT_LOCAL_CONSUMPTION"}:
                raise ValueError("stale attempt binding")
        except (ValueError, TypeError, RecursionError, OverflowError, AttributeError, UnicodeError):
            receipt = _unavailable("INVALID_OR_OVERSIZED_RECEIPT", binding.get("post_id"), summary)
    receipt["binding"] = {key: binding.get(key) for key in ("run_id", "input_index", "post_id", "attempt_id", "publication_scope_id")}
    receipt["binding"]["scope"] = "ATTEMPT_LOCAL_CONSUMPTION"
    _seal_receipt(receipt)
    if len(json.dumps(receipt, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_RECEIPT_BYTES:
        receipt = _seal_receipt(_unavailable("BINDING_BYTE_LIMIT", None, summary))
    return {"community_knowledge_readback": receipt}
