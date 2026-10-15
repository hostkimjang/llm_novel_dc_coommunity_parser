"""선택 전 실제 R2·재정렬 입력을 보존한다. 학습 라벨이나 출처 권한을 만들지 않는다."""
from __future__ import annotations

import hashlib
import base64
import json
from typing import Any

SCHEMA = "candidate_reranker_capture_v1"
SCHEMA_V2 = "candidate_reranker_capture_v2"
MAX_CAPTURE_BYTES = 256 * 1024
MAX_CAPTURE_V2_BYTES = 12 * 1024 * 1024
SCOPE = "PRE_SELECTION_PARSED_SOURCE_SNAPSHOT"


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ValueError("CAPTURE_JSON_INVALID") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _copy(value):
    raw = canonical_bytes(value)
    limit = MAX_CAPTURE_V2_BYTES if type(value) is dict and value.get("schema_version") == SCHEMA_V2 else MAX_CAPTURE_BYTES
    if len(raw) > limit:
        raise ValueError("CAPTURE_BYTE_LIMIT")
    return json.loads(raw)


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _projection(frozen_view, raw_receipt, retrieval_receipt, scorer_summary, *, semantic_input=None, evidence_payloads=None):
    from .candidate_reranker_shadow import _validate_view, build_frozen_view
    from ..runtime.candidate_reranker import _valid_receipt
    view = _validate_view(_copy(frozen_view))
    receipt, retrieval, summary = map(_copy, (raw_receipt, retrieval_receipt, scorer_summary))
    _require(type(receipt) is dict and type(retrieval) is dict and type(summary) is dict,
             "CAPTURE_OBJECT_REQUIRED")
    post_id = view["post_id"]
    _require(type(view["source_view"]["post_id"]) is type(post_id)
             and view["source_view"]["post_id"] == post_id, "CAPTURE_TYPED_POST_ID_MISMATCH")
    _require(_valid_receipt(receipt, summary, post_id, require_roles="preselection_role_producer" in receipt),
             "CAPTURE_RAW_RECEIPT_INVALID")
    _require(receipt.get("input_sha256") == canonical_sha256(view)
             and receipt.get("query_sha256") == canonical_sha256(view["source_view"])
             and receipt.get("candidate_view_sha256") == canonical_sha256(view["candidates"])
             and receipt.get("generation_sha256") == view["generation_sha256"], "CAPTURE_SCORE_INPUT_MISMATCH")
    _require(all(receipt.get(key) == view[key] for key in (
        "candidate_namespace", "generation_status", "candidate_set_fingerprint")),
        "CAPTURE_GENERATION_BINDING_MISMATCH")
    expected_ids = [candidate["candidate_id"] for candidate in view["candidates"]]
    expected_observations = [{"candidate_id": candidate["candidate_id"],
                              "role_observations": candidate["role_observations"]}
                             for candidate in view["candidates"]]
    _require(receipt.get("frozen_candidate_ids") == expected_ids, "CAPTURE_CANDIDATE_IDS_MISMATCH")
    # scorer의 명시적 크기 제한 terminal만 상세 배열 생략을 허용한다.
    # 입력 후보 ID·순서·generation 결속은 이 경우에도 그대로 검산한다.
    omitted = (receipt.get("status") == "LIMIT_EXCEEDED"
               and receipt.get("reason_codes") == ["RECEIPT_BYTE_LIMIT"]
               and receipt.get("details_available") is False
               and receipt.get("ranked_candidates") == []
               and receipt.get("candidate_observations") == [])
    _require(omitted or receipt.get("candidate_observations") == expected_observations,
             "CAPTURE_CANDIDATE_ROLES_MISMATCH")
    if receipt.get("status") in {"SCORED_SYNTHETIC", "SCORED_LEARNED"}:
        _require(sorted(row["candidate_id"] for row in receipt["ranked_candidates"])
                 == sorted(expected_ids), "CAPTURE_RANKED_CANDIDATES_MISMATCH")
    unobserved = build_frozen_view(view["source_view"], retrieval)
    semantic = summary.get("semantic_input_required") is True
    payloads = {}
    if semantic:
        from .candidate_reranker_semantic_input import validate_semantic_input
        semantic_input = validate_semantic_input(semantic_input, evidence_payloads=evidence_payloads, expected_view=view)
        _require(semantic_input["original_view"] == unobserved, "CAPTURE_RETRIEVAL_VIEW_MISMATCH")
        consumed = receipt["semantic_consumption"]
        _require(consumed["input_validated"] is True
            and consumed["semantic_input_sha256"] == semantic_input["input_sha256"]
            and consumed["semantic_observation_sha256"] == canonical_sha256(semantic_input["observation"])
            and consumed["semantic_contract_sha256"] == semantic_input["contract_sha256"],
            "CAPTURE_SEMANTIC_CONSUMPTION_MISMATCH")
        payloads = {key: base64.b64encode(evidence_payloads[key]).decode("ascii")
                    for key in semantic_input["alias_payload_sha256"]}
    else:
        _require(semantic_input is None and evidence_payloads is None, "CAPTURE_LEGACY_SEMANTIC_INPUT_FORBIDDEN")
        restored = _copy(view)
        for candidate in restored["candidates"]:
            candidate["role_observations"] = []
        _require(restored == unobserved, "CAPTURE_RETRIEVAL_VIEW_MISMATCH")
    fragments = view["source_view"]["fragments"]
    by_path = {fragment["raw_path"]: fragment["text"] for fragment in fragments}
    source_bytes = [{"raw_path": f["raw_path"], "kind": f["kind"],
                     "utf8_byte_length": len(f["text"].encode("utf-8")),
                     "utf8_sha256": hashlib.sha256(f["text"].encode("utf-8")).hexdigest()}
                    for f in fragments]
    roles = []
    for candidate in view["candidates"]:
        for role in candidate["role_observations"]:
            text = by_path[role["raw_path"]]
            start, end = role["start"], role["end"]
            roles.append({"candidate_id": candidate["candidate_id"], "role": role["role"],
                "raw_path": role["raw_path"], "char_start": start, "char_end": end,
                "utf8_byte_start": len(text[:start].encode("utf-8")),
                "utf8_byte_end": len(text[:end].encode("utf-8")), "text_sha256": role["text_sha256"]})
    result = {"schema_version": SCHEMA_V2 if semantic else SCHEMA, "status": "CAPTURED", "scope": SCOPE, "post_id": post_id,
        "frozen_view": view, "frozen_view_sha256": canonical_sha256(view),
        "raw_receipt": receipt, "raw_receipt_sha256": receipt["receipt_sha256"],
        "scorer_summary": summary, "scorer_summary_sha256": canonical_sha256(summary),
        "retrieval_receipt": retrieval, "retrieval_receipt_sha256": canonical_sha256(retrieval),
        "source_fragments": source_bytes, "role_byte_spans": roles,
        "training_readiness": "NOT_ASSIGNED_OR_ADJUDICATED",
        "provenance_status": "SOURCE_RIGHTS_AND_LINEAGE_NOT_BOUND",
        "publication_authority": False, "public_apply": False, "central_db_write": False}
    if semantic:
        result.update(semantic_input=semantic_input, semantic_payloads_base64=payloads)
    return result


def build_capture(frozen_view, raw_receipt, retrieval_receipt, scorer_summary, *, semantic_input=None, evidence_payloads=None) -> dict:
    """같은 호출에서 만든 원문·R2·역할 관측·score 입력만 깊은 복사로 봉인한다."""
    payload = _projection(frozen_view, raw_receipt, retrieval_receipt, scorer_summary,
        semantic_input=semantic_input, evidence_payloads=evidence_payloads)
    payload["capture_sha256"] = canonical_sha256(payload)
    return _copy(payload)


def validate_capture(value) -> dict:
    """자체 해시만 신뢰하지 않고 원문/후보/점수 및 UTF-8 좌표를 재검산한다."""
    value = _copy(value)
    _require(type(value) is dict, "CAPTURE_OBJECT_REQUIRED")
    try:
        kwargs = {}
        if value.get("schema_version") == SCHEMA_V2:
            kwargs = {"semantic_input": value["semantic_input"], "evidence_payloads": capture_semantic_payloads(value)}
        expected = build_capture(value["frozen_view"], value["raw_receipt"],
                                 value["retrieval_receipt"], value["scorer_summary"], **kwargs)
    except KeyError as exc:
        raise ValueError("CAPTURE_FIELDS_MISSING") from exc
    _require(canonical_bytes(value) == canonical_bytes(expected), "CAPTURE_PROJECTION_MISMATCH")
    return value


def capture_semantic_payloads(value):
    """보존된 원시 별칭 증거만 복원한다. 파일이나 외부 주소를 읽지 않는다."""
    value = _copy(value)
    _require(value.get("schema_version") == SCHEMA_V2, "CAPTURE_SEMANTIC_SCHEMA_REQUIRED")
    refs = value.get("semantic_payloads_base64")
    _require(type(refs) is dict and len(refs) <= 4098, "CAPTURE_SEMANTIC_PAYLOADS_INVALID")
    result, total = {}, 0
    for key, encoded in refs.items():
        _require(type(key) is str and len(key) == 64 and type(encoded) is str, "CAPTURE_SEMANTIC_PAYLOAD_INVALID")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("CAPTURE_SEMANTIC_BASE64_INVALID") from exc
        total += len(raw)
        _require(total <= 8 * 1024 * 1024, "CAPTURE_SEMANTIC_PAYLOAD_BYTE_LIMIT")
        _require(hashlib.sha256(raw).hexdigest() == key, "CAPTURE_SEMANTIC_PAYLOAD_SHA_MISMATCH")
        result[key] = raw
    _require(sorted(result) == value["semantic_input"]["alias_payload_sha256"], "CAPTURE_SEMANTIC_PAYLOAD_SET_MISMATCH")
    return result
