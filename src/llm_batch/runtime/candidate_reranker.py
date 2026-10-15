"""선택 전 R2 후보의 재정렬 관측 설정·연결·행별 저장 경계."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

MAX_RECEIPT_BYTES = 64 * 1024
_HASH = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINTS = ("model_manifest_sha256", "scorer_sha256", "feature_schema_sha256", "config_sha256")
_BINDING_KEYS = ("run_id", "input_index", "post_id", "attempt_id", "publication_scope_id")
_DIGEST_SCOPE = "CANONICAL_EXCLUDING_LATENCY_SELF_AND_STORAGE_BINDING"
_ROLE_KEY = "preselection_role_producer"
_ROLE_EXECUTED = {"OBSERVED", "NO_MATCH", "AMBIGUOUS"}
_NIL_BACKEND = "NIL_AUGMENTED_LINEAR_V1"
_MODEL_METADATA = ("model_sha256", "model_kind", "model_quality_status", "training_split_manifest_sha256",
                   "nil_head_available", "candidate_ranker_model_sha256", "semantic_input_required",
                   "semantic_contract_sha256", "semantic_policy_sha256", "feature_schema")
_TERMINALS = {"SCORED_SYNTHETIC", "SCORED_LEARNED", "NOT_SCORED_GENERATION_UNKNOWN", "NOT_SCORED_GENERATION_TRUNCATED",
              "NOT_SCORED_EMPTY_CORPUS", "EMPTY_CANDIDATE_SET", "EMPTY_QUERY", "UNAVAILABLE_MODEL",
              "INVALID_INPUT", "LIMIT_EXCEEDED", "ERROR", "NOT_AVAILABLE"}
_SETTINGS = {
    "mode": ("candidate_reranker", "EXPERT_CANDIDATE_RERANKER", "OFF"),
    "manifest_path": ("reranker_manifest", "EXPERT_RERANKER_MANIFEST", None),
    "manifest_sha256": ("reranker_manifest_sha256", "EXPERT_RERANKER_MANIFEST_SHA256", None),
}


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _summary(scorer):
    try:
        value = scorer.summary()
        return json.loads(_bytes(value)) if isinstance(value, dict) else {}
    except Exception:
        return {}


def resolve_candidate_reranker_settings(args: Any, environment: Mapping[str, str]) -> dict:
    values, sources = {}, {}
    for key, (attribute, env_key, default) in _SETTINGS.items():
        value = getattr(args, attribute, None)
        if value is not None:
            source = "CLI"
        elif env_key in environment:
            value, source = environment[env_key], "ENVIRONMENT"
        else:
            value, source = default, "DEFAULT"
        values[key], sources[key] = value, source
    if values["mode"] not in {"OFF", "SHADOW"}:
        raise ValueError("재정렬 모드는 OFF 또는 SHADOW여야 합니다")
    if values["mode"] == "SHADOW":
        if getattr(args, "candidate_retrieval", "OFF") != "SHADOW":
            raise ValueError("재정렬 SHADOW에는 --candidate-retrieval SHADOW가 필요합니다")
        if not values["manifest_path"] or not isinstance(values["manifest_sha256"], str) or not _HASH.fullmatch(values["manifest_sha256"]):
            raise ValueError("재정렬 SHADOW에는 manifest 경로와 사전 고정 소문자 SHA-256이 필요합니다")
    return {**values, "sources": sources}


def prepare_candidate_reranker(settings: Mapping[str, Any]):
    if settings["mode"] == "OFF":
        return None
    from ..grounding.candidate_reranker_shadow import load_scorer, unavailable_scorer
    try:
        return load_scorer(settings["manifest_path"], expected_sha256=settings["manifest_sha256"])
    except Exception as exc:
        code = getattr(exc, "code", "MODEL_LOAD_ERROR")
        return unavailable_scorer(code if isinstance(code, str) and len(code) <= 96 else "MODEL_LOAD_ERROR",
                                  expected_sha256=settings["manifest_sha256"])


def candidate_reranker_policy_fields(scorer, settings=None) -> dict:
    if scorer is None:
        return {}
    policy = copy.deepcopy(scorer.summary())
    if policy.get("semantic_input_required") is True:
        from ..grounding.candidate_reranker_semantics import POLICY, POLICY_SHA256
        policy["semantic_role_producer_policy"] = {"policy_sha256": POLICY_SHA256, "policy": copy.deepcopy(POLICY)}
    else:
        from ..grounding.candidate_reranker_roles import POLICY, POLICY_SHA256
        policy["preselection_role_producer_policy"] = {"policy_sha256": POLICY_SHA256, "policy": copy.deepcopy(POLICY)}
    policy.update(mode="SHADOW", model_input_may_change=policy.get("semantic_input_required") is True, public_apply=False,
                  publication_authority=False, central_db_write=False,
                  candidate_source="R2_PRE_EXPERT_FROZEN_CANDIDATES")
    if settings is not None:
        policy.update(manifest_path=str(Path(settings["manifest_path"]).absolute()), setting_sources=dict(settings["sources"]))
    return {"candidate_reranker_policy": policy}


def _seal(receipt):
    receipt["receipt_digest_scope"] = _DIGEST_SCOPE
    receipt["receipt_sha256"] = _sha({key: value for key, value in receipt.items()
                                    if key not in {"latency_ms", "receipt_sha256", "binding"}})
    return receipt


def _unavailable(reason, post_id, summary, *, status="NOT_AVAILABLE", query_sha256=None):
    value = {"schema_version": "candidate_reranker_shadow_v1", "mode": "SHADOW", "post_id": post_id,
        "status": status, "reason_codes": [reason], **{key: summary.get(key) for key in _FINGERPRINTS},
        "backend": summary.get("backend"),
        **{key: summary[key] for key in _MODEL_METADATA if key in summary},
        **({"nil_score": None, "event_logits": []} if summary.get("backend") == _NIL_BACKEND else {}),
        "data_kind": summary.get("data_kind"), "actual_model_available": summary.get("actual_model_available", False),
        "training_status": summary.get("training_status"), "query_sha256": query_sha256,
        "input_sha256": None, "candidate_view_sha256": None, "generation_sha256": None,
        "generation_status": "UNKNOWN", "candidate_namespace": "CORPUS_CANDIDATE",
        "candidate_option_bridge_status": "MISSING", "candidate_set_fingerprint": None,
        "frozen_candidate_ids": [], "ranked_candidates": [], "candidate_observations": [],
        "probability_status": "NOT_AVAILABLE_UNCALIBRATED", "nil_probability": None, "selected_candidate_id": None,
        "publication_authority": False, "public_apply": False, "central_db_write": False,
        "operational_effect": "NONE_SHADOW_ONLY", "latency_ms": 0.0,
        _ROLE_KEY: _role_not_executed(reason)}
    if summary.get("semantic_input_required") is True:
        value.pop(_ROLE_KEY)
        value["semantic_input_sha256"] = None
        value["semantic_consumption"] = {
            "schema_version": "candidate_reranker_semantic_consumption_v1", "status": "NOT_CONSUMED",
            "reason_codes": [reason], "input_validated": False, "backend_invoked": False, "score_produced": False,
            "semantic_input_sha256": None, "semantic_contract_sha256": summary.get("semantic_contract_sha256"),
            "semantic_observation_sha256": None, "semantic_policy_sha256": summary.get("semantic_policy_sha256"),
            "scorer_input_sha256": None}
    return _seal(value)


def requires_semantic_input(scorer):
    return scorer is not None and _summary(scorer).get("semantic_input_required") is True


def _valid_semantic_consumption(receipt, summary):
    value = receipt.get("semantic_consumption")
    if summary.get("semantic_input_required") is not True:
        return not any(key in receipt for key in ("semantic_consumption", "semantic_input_required",
            "semantic_contract_sha256", "semantic_policy_sha256", "semantic_input_sha256", "feature_schema"))
    fields = {"schema_version", "status", "reason_codes", "input_validated", "backend_invoked", "score_produced",
        "semantic_input_sha256", "semantic_contract_sha256", "semantic_observation_sha256",
        "semantic_policy_sha256", "scorer_input_sha256"}
    if (type(value) is not dict or set(value) != fields or _ROLE_KEY in receipt
            or receipt.get("semantic_input_required") is not True
            or value["schema_version"] != "candidate_reranker_semantic_consumption_v1"
            or value["status"] not in {"SCORED", "BACKEND_FAILED", "INPUT_BOUND_NOT_SCORED", "NOT_CONSUMED", "OUTPUT_LIMIT_EXCEEDED"}
            or type(value["reason_codes"]) is not list
            or any(type(c) is not str or not re.fullmatch(r"[A-Z0-9_]{1,96}", c) for c in value["reason_codes"])
            or any(type(value[k]) is not bool for k in ("input_validated", "backend_invoked", "score_produced"))):
        return False
    if value["reason_codes"] != receipt.get("reason_codes"):
        return False
    for key in ("semantic_contract_sha256", "semantic_policy_sha256"):
        if value[key] != summary.get(key) or type(value[key]) is not str or not _HASH.fullmatch(value[key]):
            return False
    if value["input_validated"]:
        if (any(type(value[k]) is not str or not _HASH.fullmatch(value[k]) for k in
                ("semantic_input_sha256", "semantic_observation_sha256", "scorer_input_sha256"))
                or value["scorer_input_sha256"] != receipt.get("input_sha256")
                or value["semantic_input_sha256"] != receipt.get("semantic_input_sha256")
                or receipt.get("generation_status") != "COMPLETE"):
            return False
    elif receipt.get("semantic_input_sha256") is not None or any(value[k] is not None for k in ("semantic_input_sha256", "semantic_observation_sha256", "scorer_input_sha256")):
        return False
    if value["backend_invoked"] and not value["input_validated"]:
        return False
    produced = receipt.get("status") == "SCORED_LEARNED"
    if value["score_produced"] != produced or produced and not (value["backend_invoked"] and value["status"] == "SCORED"):
        return False
    expected = ("SCORED" if produced else "OUTPUT_LIMIT_EXCEEDED" if receipt.get("reason_codes") == ["RECEIPT_BYTE_LIMIT"]
        else "BACKEND_FAILED" if value["backend_invoked"] else "INPUT_BOUND_NOT_SCORED" if value["input_validated"] else "NOT_CONSUMED")
    return value["status"] == expected


def _role_not_executed(reason, *, status="NOT_EXECUTED"):
    from ..grounding.candidate_reranker_roles import not_executed_metadata
    return not_executed_metadata(reason, status=status)


def _attach_roles(receipt, metadata, view=None):
    # 관측 뒤 scorer 오류가 나도 완료된 producer 관측을 미실행으로 바꾸지 않는다.
    if metadata["status"] in _ROLE_EXECUTED and receipt.get("input_sha256") is None and view is not None:
        receipt.update(input_sha256=_sha(view), candidate_view_sha256=_sha(view["candidates"]),
            generation_sha256=view["generation_sha256"], generation_status=view["generation_status"],
            candidate_namespace=view["candidate_namespace"], candidate_set_fingerprint=view["candidate_set_fingerprint"],
            frozen_candidate_ids=[row["candidate_id"] for row in view["candidates"]],
            candidate_observations=[{"candidate_id": row["candidate_id"], "role_observations": row["role_observations"]}
                                    for row in view["candidates"]])
    receipt[_ROLE_KEY] = copy.deepcopy(metadata)
    return _seal(receipt)


def _valid_role_metadata(receipt):
    from ..grounding.candidate_reranker_roles import validate_metadata
    metadata = validate_metadata(receipt.get(_ROLE_KEY))
    state = metadata["status"]
    if state in _ROLE_EXECUTED:
        if (metadata["frozen_view_sha256"] != receipt.get("input_sha256")
                or receipt.get("generation_status") != "COMPLETE"):
            return False
        observations = receipt.get("candidate_observations")
        ids = receipt.get("frozen_candidate_ids")
        if (receipt.get("status") == "LIMIT_EXCEEDED"
                and receipt.get("reason_codes") == ["RECEIPT_BYTE_LIMIT"]
                and receipt.get("details_available") is False
                and observations == [] and receipt.get("ranked_candidates") == []):
            # scorer가 크기 한도로 상세를 생략했어도 완료된 producer의 집계·입력
            # 결속과 LIMIT terminal은 보존한다. 큰 관측 배열을 다시 붙이지 않는다.
            return type(ids) is list and metadata["counts"]["candidates"] == len(ids)
        if (type(observations) is not list or type(ids) is not list
                or [row.get("candidate_id") if type(row) is dict else None for row in observations] != ids):
            return False
        roles = []
        for row in observations:
            if (set(row) != {"candidate_id", "role_observations"} or type(row["role_observations"]) is not list
                    or len(row["role_observations"]) > 32):
                return False
            for role in row["role_observations"]:
                if (type(role) is not dict or set(role) != {"role", "raw_path", "start", "end", "text_sha256"}
                        or role["role"] != "MENTIONED" or type(role["raw_path"]) is not str
                        or type(role["start"]) is not int or type(role["end"]) is not int
                        or not 0 <= role["start"] < role["end"]
                        or type(role["text_sha256"]) is not str or not _HASH.fullmatch(role["text_sha256"])):
                    return False
                roles.append(role)
        counts = metadata["counts"]
        if (counts["candidates"] != len(ids) or counts["observations"] != len(roles)
                or counts["observed_candidates"] != sum(bool(row["role_observations"]) for row in observations)):
            return False
    elif state in {"ERROR", "LIMIT_EXCEEDED", "INVALID_INPUT"}:
        if receipt.get("status") != state or receipt.get("ranked_candidates"):
            return False
    elif receipt.get("status") in {"SCORED_SYNTHETIC", "SCORED_LEARNED"}:
        if metadata["reason_codes"] != ["EXPLICIT_FROZEN_VIEW_PROVIDED"]:
            return False
    return True


def _source_view(post):
    fragments = [{"raw_path": "/title", "kind": "TITLE", "text": post.title}]
    for index, block in enumerate(post.content_blocks or []):
        kind = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
        raw = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
        if kind == "text" and isinstance(raw, str):
            fragments.append({"raw_path": f"/content_blocks/{index}/text", "kind": "BODY", "text": raw})
    for index, comment in enumerate(post.comments or []):
        if isinstance(comment, dict):
            key = "content" if isinstance(comment.get("content"), str) else "text"
            raw, path = comment.get(key), f"/comments/{index}/{key}"
        elif isinstance(comment, str):
            raw, path = comment, f"/comments/{index}"
        else:
            raw, path = getattr(comment, "content", None), f"/comments/{index}/content"
        if isinstance(raw, str):
            fragments.append({"raw_path": path, "kind": "COMMENT", "text": raw})
    return {"schema_version": "candidate_retrieval_source_view_v1", "post_id": post.post_id, "fragments": fragments}


def _observe_roles(frozen):
    from ..grounding.candidate_reranker_roles import observe_preselection_roles
    return observe_preselection_roles(frozen)


def _validate_role_enrichment(original, enriched):
    """원문·고정 후보는 그대로 두고 정확한 제목 언급 관측만 허용한다."""
    from ..grounding.candidate_reranker_shadow import _validate_view
    view = _validate_view(enriched)
    restored = copy.deepcopy(view)
    if len(view["candidates"]) != len(original["candidates"]):
        raise ValueError("role producer changed candidate count")
    fragments = {part["raw_path"]: part["text"] for part in original["source_view"]["fragments"]}
    for before, after, restore in zip(original["candidates"], view["candidates"], restored["candidates"]):
        restore["role_observations"] = copy.deepcopy(before["role_observations"])
        for role in after["role_observations"]:
            if (role["role"] != "MENTIONED"
                    or fragments[role["raw_path"]][role["start"]:role["end"]] not in before["titles"]):
                raise ValueError("role producer exceeded exact title mention scope")
    if restored != original:
        raise ValueError("role producer changed frozen input")
    return view


def _valid_nil_scores(receipt, summary):
    if summary.get("backend") != _NIL_BACKEND:
        return "nil_score" not in receipt and "event_logits" not in receipt
    if receipt.get("nil_head_available") is not True or "nil_score" not in receipt or "event_logits" not in receipt:
        return False
    if receipt.get("status") != "SCORED_LEARNED":
        return receipt.get("nil_score") is None and receipt.get("event_logits") == []
    nil_score, events = receipt.get("nil_score"), receipt.get("event_logits")
    if type(nil_score) not in (float, int) or not math.isfinite(nil_score) or type(events) is not list:
        return False
    labels = receipt["frozen_candidate_ids"] + ["__NIL__"]
    if len(events) != len(labels):
        return False
    expected = {row["candidate_id"]: row["score"] for row in receipt["ranked_candidates"]}
    expected["__NIL__"] = nil_score
    for event, label in zip(events, labels):
        if (type(event) is not dict or set(event) != {"label", "score"} or event["label"] != label
                or type(event["score"]) not in (float, int) or not math.isfinite(event["score"])
                or event["score"] != expected[label]):
            return False
    return True


def _valid_receipt(receipt, summary, post_id, *, require_roles=False):
    if not isinstance(receipt, dict) or len(_bytes(receipt)) > MAX_RECEIPT_BYTES - 4096:
        return False
    if receipt.get("schema_version") != "candidate_reranker_shadow_v1" or receipt.get("mode") != "SHADOW":
        return False
    if receipt.get("receipt_digest_scope") != _DIGEST_SCOPE or receipt.get("status") not in _TERMINALS:
        return False
    if type(receipt.get("post_id")) is not type(post_id) or receipt.get("post_id") != post_id or any(receipt.get(key) != summary.get(key) for key in _FINGERPRINTS):
        return False
    if any(receipt.get(key) is not False for key in ("publication_authority", "public_apply", "central_db_write")):
        return False
    if (receipt.get("probability_status") != "NOT_AVAILABLE_UNCALIBRATED" or receipt.get("nil_probability") is not None
            or receipt.get("selected_candidate_id") is not None or receipt.get("operational_effect") != "NONE_SHADOW_ONLY"):
        return False
    if (type(receipt.get("actual_model_available")) is not bool
            or receipt.get("actual_model_available") is not summary.get("actual_model_available", False)
            or any(receipt.get(key) != summary.get(key) for key in ("backend", "data_kind", "training_status"))):
        return False
    if any(receipt.get(key) != summary.get(key) for key in _MODEL_METADATA):
        return False
    ids, ranked, observations = (receipt.get(key) for key in ("frozen_candidate_ids", "ranked_candidates", "candidate_observations"))
    if (type(ids) is not list or len(ids) > 20 or any(type(key) is not str or not key or key == "__NIL__" or len(key) > 160 for key in ids)
            or len(set(ids)) != len(ids) or type(ranked) is not list or type(observations) is not list):
        return False
    if receipt["status"] in {"SCORED_SYNTHETIC", "SCORED_LEARNED"}:
        learned = receipt["status"] == "SCORED_LEARNED"
        if learned:
            training = {_NIL_BACKEND: "TRAINED_PAIRWISE_PLUS_NIL_HEAD", "PAIRWISE_LINEAR_V1": "TRAINED_PAIRWISE_LINEAR"}
            if (receipt.get("backend") not in training or receipt.get("actual_model_available") is not True
                    or receipt.get("training_status") != training[receipt["backend"]]
                    or receipt.get("data_kind") not in {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}
                    or not isinstance(receipt.get("model_sha256"), str)
                    or not _HASH.fullmatch(receipt["model_sha256"])
                    or not isinstance(receipt.get("training_split_manifest_sha256"), str)
                    or not _HASH.fullmatch(receipt["training_split_manifest_sha256"])
                    or any(receipt.get(key) != summary.get(key) for key in ("model_sha256", "model_kind", "model_quality_status"))):
                return False
        elif receipt.get("data_kind") != "SYNTHETIC_FIXTURE" or receipt.get("actual_model_available") is not False:
            return False
        if (receipt.get("generation_status") != "COMPLETE"
                or not ids or len(ranked) != len(ids)):
            return False
        for row in ranked:
            if (type(row) is not dict or set(row) != {"candidate_id", "score"} or type(row["candidate_id"]) is not str
                    or type(row["score"]) not in {int, float} or not math.isfinite(row["score"])):
                return False
        if sorted(row["candidate_id"] for row in ranked) != sorted(ids):
            return False
        if ranked != sorted(ranked, key=lambda row: (-row["score"], row["candidate_id"])):
            return False
        if [row.get("candidate_id") if type(row) is dict else None for row in observations] != ids:
            return False
    elif ranked:
        return False
    if not _valid_nil_scores(receipt, summary):
        return False
    if not _valid_semantic_consumption(receipt, summary):
        return False
    if receipt.get("receipt_sha256") != _sha({key: value for key, value in receipt.items()
                                           if key not in {"latency_ms", "receipt_sha256", "binding"}}):
        return False
    if summary.get("semantic_input_required") is True:
        return _ROLE_KEY not in receipt
    if require_roles:
        return _valid_role_metadata(receipt)
    return _ROLE_KEY not in receipt


def _observe_candidate_reranker(scorer, post, retrieval_receipt, retrieval_observer, *, capture_sink=None,
                               semantic_package=None, semantic_observer=None):
    """사후 출력 없이 같은 원문의 R2 후보만 한 번 점수화한다. 오류는 기존 분석에 전파하지 않는다."""
    if scorer is None:
        return None
    summary = _summary(scorer)
    query_sha = None
    frozen = None
    role_metadata = None
    semantic_input = None
    semantic_payloads = None
    semantic_required = summary.get("semantic_input_required") is True
    producing_roles = False
    try:
        source = _source_view(post)
        query_sha = _sha(source)
        if retrieval_observer is None or retrieval_receipt is None:
            return _unavailable("RETRIEVAL_NOT_EXECUTED", post.post_id, summary, query_sha256=query_sha)
        receipt = json.loads(_bytes(retrieval_receipt))
        expected = retrieval_observer.summary()
        if (receipt.get("schema_version") != "candidate_retrieval_shadow_v1" or receipt.get("mode") != "SHADOW"
                or str(receipt.get("post_id")) != str(post.post_id) or receipt.get("query_sha256") != query_sha
                or any(receipt.get(key) is not False for key in ("publication_authority", "public_apply", "central_db_write"))):
            raise ValueError("R2 receipt binding")
        # 실패 영수증에 없는 값은 만들지 않되 알려진 지문 모순은 실패 원인과 구별한다.
        for key in ("corpus_sha256", "scorer_sha256", "config_sha256"):
            if key in receipt and receipt[key] is not None and receipt[key] != expected.get(key):
                raise ValueError("R2 policy binding")
        if receipt.get("observation_sha256") is not None:
            actual_digest = _sha({key: value for key, value in receipt.items()
                                 if key not in {"latency_ms", "observation_sha256", "binding"}})
            if receipt["observation_sha256"] != actual_digest:
                raise ValueError("R2 receipt digest")
        if receipt.get("status") not in {"OK", "NO_MATCH"}:
            terminal = {"EMPTY_QUERY": "EMPTY_QUERY", "EMPTY_CORPUS": "NOT_SCORED_EMPTY_CORPUS"}.get(receipt.get("status"), "NOT_SCORED_GENERATION_UNKNOWN")
            return _unavailable("RETRIEVAL_" + str(receipt.get("status", "UNKNOWN"))[:64], post.post_id, summary,
                                status=terminal, query_sha256=query_sha)
        if any(receipt.get(key) != expected.get(key) for key in ("corpus_sha256", "scorer_sha256", "config_sha256")):
            raise ValueError("R2 policy binding")
        from ..grounding.candidate_reranker_shadow import build_frozen_view
        frozen = build_frozen_view(source, receipt)
        if semantic_required:
            if frozen["generation_status"] == "COMPLETE" and frozen["candidates"] and any(
                    part["text"].strip() for part in frozen["source_view"]["fragments"]):
                from .candidate_semantics import bind_current_semantic_input
                semantic_input, semantic_payloads = bind_current_semantic_input(
                    semantic_package, semantic_observer, post, retrieval_observer)
                if semantic_input["original_view"] != frozen:
                    raise ValueError("SEMANTIC_CURRENT_RETRIEVAL_MISMATCH")
                frozen = copy.deepcopy(semantic_input["enriched_view"])
        elif frozen["generation_status"] != "COMPLETE":
            role_metadata = _role_not_executed("GENERATION_" + frozen["generation_status"])
        elif not frozen["candidates"]:
            role_metadata = _role_not_executed("EMPTY_CANDIDATE_SET")
        elif not any(part["text"].strip() for part in frozen["source_view"]["fragments"]):
            role_metadata = _role_not_executed("EMPTY_QUERY")
        else:
            producing_roles = True
            enriched, metadata = _observe_roles(copy.deepcopy(frozen))
            enriched = _validate_role_enrichment(frozen, enriched)
            from ..grounding.candidate_reranker_roles import validate_metadata
            metadata = validate_metadata(metadata)
            if metadata["status"] not in _ROLE_EXECUTED or metadata["frozen_view_sha256"] != _sha(enriched):
                raise ValueError("role producer metadata binding")
            counts = metadata["counts"]
            if (counts["candidates"] != len(enriched["candidates"])
                    or counts["unique_titles"] != len({title for row in enriched["candidates"] for title in row["titles"]})
                    or counts["observations"] != sum(len(row["role_observations"]) for row in enriched["candidates"])
                    or counts["observed_candidates"] != sum(bool(row["role_observations"]) for row in enriched["candidates"])):
                raise ValueError("role producer count binding")
            frozen, role_metadata = enriched, metadata
            producing_roles = False
        generation_sha = frozen["generation_sha256"]
        input_sha, candidate_sha = _sha(frozen), _sha(frozen["candidates"])
        if semantic_required:
            raw = scorer.score(copy.deepcopy(frozen), semantic_input=semantic_input, evidence_payloads=semantic_payloads)
        else:
            raw = scorer.score(copy.deepcopy(frozen))
        output = json.loads(_bytes(raw))
        if not _valid_receipt(output, summary, post.post_id):
            raise ValueError("R4 receipt binding")
        # 입력 검사 전 거절은 입력 지문이 없을 수 있다. 성공한 관측에는 예외를 적용하지 않는다.
        if output.get("status") not in {"INVALID_INPUT", "LIMIT_EXCEEDED"}:
            if any(output.get(key) != value for key, value in {"query_sha256": query_sha, "input_sha256": input_sha,
                    "candidate_view_sha256": candidate_sha, "generation_sha256": generation_sha}.items()):
                raise ValueError("R4 source fingerprints")
        if output.get("status") in {"SCORED_SYNTHETIC", "SCORED_LEARNED"}:
            frozen_ids = [row["candidate_id"] for row in frozen["candidates"]]
            expected_ids = sorted(frozen_ids)
            actual_ids = [row["candidate_id"] for row in output["ranked_candidates"]]
            expected_observations = [{"candidate_id": row["candidate_id"], "role_observations": row["role_observations"]}
                                     for row in frozen["candidates"]]
            if (sorted(actual_ids) != expected_ids or len(set(actual_ids)) != len(actual_ids)
                    or output.get("frozen_candidate_ids") != frozen_ids or output.get("candidate_observations") != expected_observations):
                raise ValueError("R4 candidate set mismatch")
        if not semantic_required:
            output = _attach_roles(output, role_metadata, frozen)
        if not _valid_receipt(output, summary, post.post_id, require_roles=True):
            raise ValueError("role producer receipt binding")
        if capture_sink is not None:
            # capture 실패는 기존 점수나 전문가 분석 결과에 전파하지 않는다.
            try:
                if semantic_required and semantic_input is not None:
                    capture_sink(copy.deepcopy(frozen), copy.deepcopy(output), copy.deepcopy(receipt), copy.deepcopy(summary),
                        semantic_input=copy.deepcopy(semantic_input), evidence_payloads=semantic_payloads)
                elif not semantic_required:
                    capture_sink(copy.deepcopy(frozen), copy.deepcopy(output), copy.deepcopy(receipt), copy.deepcopy(summary))
            except Exception:
                pass
        return output
    except Exception as exc:
        code = getattr(exc, "code", "INVALID_OR_FAILED_OBSERVATION")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9_]{1,96}", code):
            code = "INVALID_OR_FAILED_OBSERVATION"
        status = "LIMIT_EXCEEDED" if code.endswith("LIMIT") else "ERROR"
        output = _unavailable(code, post.post_id, summary, status=status, query_sha256=query_sha)
        if producing_roles:
            role_metadata = _role_not_executed(code, status=status)
        if role_metadata is not None:
            output = _attach_roles(output, role_metadata, frozen)
        return output


def observe_candidate_reranker(scorer, post, retrieval_receipt, retrieval_observer, *,
                              semantic_package=None, semantic_observer=None):
    """기존 receipt 전용 API. capture I/O나 새 교정 의존성을 실행하지 않는다."""
    return _observe_candidate_reranker(scorer, post, retrieval_receipt, retrieval_observer,
        semantic_package=semantic_package, semantic_observer=semantic_observer)


def observe_candidate_reranker_with_capture(scorer, post, retrieval_receipt, retrieval_observer, *,
                                           semantic_package=None, semantic_observer=None):
    """같은 실제 scorer 호출의 입력과 출력만 호출별 지역 변수로 돌려준다."""
    captured = []
    def sink(view, receipt, retrieval, summary, **kwargs):
        from ..grounding.candidate_reranker_capture import build_capture
        captured.append(build_capture(view, receipt, retrieval, summary, **kwargs))
    receipt = _observe_candidate_reranker(scorer, post, retrieval_receipt, retrieval_observer, capture_sink=sink,
        semantic_package=semantic_package, semantic_observer=semantic_observer)
    return {"receipt": receipt, "capture": captured[0] if captured else None}


def export_candidate_reranker_fields(result, scorer, *, binding: Mapping[str, Any]):
    if scorer is None:
        return {}
    summary = _summary(scorer)
    post_id = binding.get("post_id")
    storage_binding = {**{key: binding.get(key) for key in _BINDING_KEYS}, "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    raw = getattr(result, "_candidate_reranker_shadow", None) if result is not None else None
    if raw is None:
        receipt = _unavailable("PIPELINE_NOT_EXECUTED" if result is None else "RECEIPT_NOT_AVAILABLE", post_id, summary)
    else:
        try:
            receipt = json.loads(_bytes(raw))
            has_metadata = _ROLE_KEY in receipt
            if not _valid_receipt(receipt, summary, post_id, require_roles=has_metadata) or ("binding" in receipt and receipt["binding"] != storage_binding):
                raise ValueError("stale or invalid receipt")
            if not has_metadata and summary.get("semantic_input_required") is not True:
                # 이전 명시 frozen-view API는 보존하되 producer 실행으로 승격하지 않는다.
                receipt = _attach_roles(receipt, _role_not_executed("EXPLICIT_FROZEN_VIEW_PROVIDED"))
                if not _valid_receipt(receipt, summary, post_id, require_roles=True):
                    raise ValueError("manual frozen view receipt binding")
        except (ValueError, TypeError, AttributeError, RecursionError, OverflowError, UnicodeError):
            receipt = _unavailable("INVALID_OR_OVERSIZED_RECEIPT", post_id, summary)
    receipt["binding"] = storage_binding
    if len(_bytes(receipt)) > MAX_RECEIPT_BYTES:
        receipt = _unavailable("BINDING_BYTE_LIMIT", None, summary)
    return {"candidate_reranker_shadow": receipt}
