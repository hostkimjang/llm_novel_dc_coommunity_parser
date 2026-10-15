"""R2 후보 회수의 명시적 실행 설정과 비공개 관측 저장 경계."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from typing import Any, Mapping


MAX_RECEIPT_BYTES = 64 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def prepare_candidate_retrieval(args: Any):
    """OFF에서는 경로를 읽거나 adapter를 import하지 않는다."""
    mode = getattr(args, "candidate_retrieval", "OFF")
    if mode == "OFF":
        return None
    if mode != "SHADOW":
        raise ValueError("후보 회수 모드는 OFF 또는 SHADOW여야 합니다")
    path = getattr(args, "candidate_corpus", None)
    sha = getattr(args, "candidate_corpus_sha256", None)
    top_k = getattr(args, "candidate_retrieval_top_k", 20)
    if not path or not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise ValueError("SHADOW에는 corpus 경로와 소문자 SHA-256을 명시해야 합니다")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
        raise ValueError("후보 회수 top-k는 1~100이어야 합니다")
    from ..grounding.candidate_retrieval_shadow import load_candidate_retrieval_shadow, unavailable_observer
    try:
        return load_candidate_retrieval_shadow(Path(path), expected_sha256=sha, top_k=top_k)
    except Exception as exc:
        reason = str(getattr(exc, "code", "CORPUS_LOAD_ERROR"))[:96]
        return unavailable_observer(reason, expected_sha256=sha, top_k=top_k)


def candidate_retrieval_policy_fields(observer: Any, *, corpus_path: str | None = None) -> dict:
    if observer is None:
        return {}
    policy = copy.deepcopy(observer.summary())
    if corpus_path is not None:
        policy["corpus_path"] = str(Path(corpus_path).absolute())
    return {"candidate_retrieval_policy": policy}


def _unavailable(reason: str, binding: Mapping[str, Any]) -> dict:
    return {"schema_version": "candidate_retrieval_shadow_v1", "mode": "SHADOW",
            "status": "NOT_AVAILABLE", "reason_codes": [reason],
            "post_id": binding.get("post_id"), "ranked_candidates": [],
            "publication_authority": False, "central_db_write": False, "public_apply": False}


def export_candidate_retrieval_fields(result: Any, observer: Any, *, binding: Mapping[str, Any]) -> dict:
    """같은 게시글·attempt의 관측만 run_meta에 넣고 공개 payload에는 넣지 않는다."""
    if observer is None:
        return {}
    raw = getattr(result, "_candidate_retrieval_shadow", None) if result is not None else None
    if raw is None:
        receipt = _unavailable("PIPELINE_NOT_EXECUTED" if result is None else "RECEIPT_NOT_AVAILABLE", binding)
    else:
        try:
            encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if len(encoded.encode("utf-8")) > MAX_RECEIPT_BYTES - 4096:
                raise ValueError("receipt exceeds byte limit")
            receipt = json.loads(encoded)
            if not isinstance(receipt, dict) or str(receipt.get("post_id")) != str(binding.get("post_id")):
                raise ValueError("post binding mismatch")
            if receipt.get("schema_version") != "candidate_retrieval_shadow_v1" or receipt.get("mode") != "SHADOW":
                raise ValueError("unknown receipt schema")
            if (receipt.get("publication_authority") is not False or receipt.get("central_db_write") is not False
                    or receipt.get("public_apply") is not False):
                raise ValueError("shadow authority mismatch")
        except (ValueError, TypeError, RecursionError, OverflowError):
            receipt = _unavailable("INVALID_OR_OVERSIZED_RECEIPT", binding)
    receipt["binding"] = {key: binding.get(key) for key in
                          ("run_id", "input_index", "post_id", "attempt_id", "publication_scope_id")}
    receipt["binding"]["scope"] = "ATTEMPT_LOCAL_OBSERVATION"
    receipt["publication_authority"] = False
    receipt["central_db_write"] = False
    receipt["mode"] = "SHADOW"
    encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_RECEIPT_BYTES:
        receipt = _unavailable("BINDING_BYTE_LIMIT", {"post_id": None})
    return {"candidate_retrieval_shadow": receipt}
