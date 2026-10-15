"""Shared synthetic-only R6 evidence, generated through existing validators.

No historical input or result is read. Every original file is created exclusively
under the caller's fresh temporary directory; output remains absent until the
journal/runtime tests create it. The returned HMAC key is synthetic test data.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from src.llm_batch.ledger.publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA,
    build_publication_scope_descriptor,
    compute_publication_decision_commit,
)
from src.llm_batch.ledger.recovery_activation import _create_event, extract_direct_ocr_review_proposals
from src.llm_batch.measurement.recovery_execution_contract import (
    bind_recovery_execution_plan,
    build_recovery_execution_plan,
    canonical_sha256,
)
from src.llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt
from src.llm_batch.measurement.semantic_review_router import build_semantic_review_router_receipt
from src.llm_batch.promotion_gate import (
    EvidenceRecord, GroundingState, ScopeState, apply_publish_contract, evaluate_publish_contract,
)


HMAC_KEY = b"R6-local-synthetic-audit-key-20261010-only"


def json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def reseal_plan(plan: dict) -> dict:
    """Test-only resealing: semantic contradictions must still fail full binding."""
    result = deepcopy(plan)
    semantic = {key: deepcopy(value) for key, value in result.items()
                if key not in {"plan_sha256", "binding_sha256", "output_dir"}}
    semantic["artifacts"] = {role: {key: ref[key] for key in ("sha256", "bytes")}
                              for role, ref in result["artifacts"].items()}
    result["plan_sha256"] = canonical_sha256(semantic)
    result["binding_sha256"] = canonical_sha256({key: value for key, value in result.items()
                                                if key != "binding_sha256"})
    return result


def _hold_result(post_id, relation_role: str, *, ocr_review_required: bool = True) -> dict:
    title = "합성 달별갤 작품"
    state = GroundingState(
        post_id=post_id, candidate_title=title, candidate_url="", source="r6_synthetic_contract",
        official_title_exists=False, row_discusses_work_as_work=False,
        title_resolution_state="unresolved_matchable", work_resolution="unresolved",
        discussion_type="unknown", scope=ScopeState(scope_kind="unknown", confidence="low",
            conflict_reason_codes=("review_only_recovery",)),
    )
    evidence = EvidenceRecord(kind="direct_ocr_review_candidate", strength="medium",
        source_path_or_snippet="image:0", supports_publish=False, reason_code="review_only_recovery",
        candidate_title=title, candidate_url="")
    identity = {"is_relevant": True, "novel_identity": None}
    apply_publish_contract(identity, evaluate_publish_contract(state, [evidence]))
    identity.update({
        # The original router requires an explicit trigger, not merely raw OCR.
        # This is synthetic unresolved OCR evidence, never a forced router state.
        "work_resolution": "unresolved",
        "consistency_flags": ["ocr_explicit_title_unresolved"] if ocr_review_required else [],
        "output_consistency_lint": [],
        "title_candidates": [{"official_title": title, "heretic_url": None,
            "reference_role": relation_role, "source_tier": "raw_ocr", "page_type": "unknown"}],
        "search_health": {"status": "SEARCH_OK"},
        "image_evidence_catalog": [{"eid": "R6_SYNTHETIC_IMG001", "block_index": 0,
            "ocr_text": title + " · 합성 1화", "explicit_work_title": title,
            "evidence_type": "explicit_text", "title_role": "work_title", "promotion_eligible": True}],
    })
    if relation_role == "ambiguous":
        identity["title_candidates"][0]["reference_role"] = "primary"
        other = deepcopy(identity["title_candidates"][0])
        other["reference_role"] = "mentioned"
        identity["title_candidates"].append(other)
    return {"gallery_id": "synthetic_r6", "post_id": post_id, "title": "합성 복구 계약",
            "content": ["실제 작품이나 운영 입력이 아닌 합성 시험 원문"], "comments": [],
            "image_count": 1, "analysis_result": {"identity": identity}, "run_meta": {}}


def make_recovery_fixture(root: Path, *, action_kinds=None, responses=None,
                          policy_overrides=None, post_id=101, relation_role="primary",
                          post_ids=None, input_format="JSON_ARRAY_V1", jsonl_comment_rows=None,
                          embedded_comments=None, result_comments_override=None,
                          comment_metadata=None, ocr_review_required=True,
                          router_rule_version=None) -> dict:
    root = Path(root).resolve()
    source_dir = root / "source"
    source_dir.mkdir(parents=True, exist_ok=False)
    ids = list(post_ids) if post_ids is not None else [post_id, 102]
    if not ids:
        raise ValueError("fixture requires an input post")
    post_id = ids[0]
    result = _hold_result(post_id, relation_role, ocr_review_required=ocr_review_required)
    embedded = deepcopy(embedded_comments or [])
    separate = deepcopy(jsonl_comment_rows or [])
    if separate and input_format != "JSONL_POST_COMMENT_V1":
        raise ValueError("separate comment rows require explicit JSONL format")
    expected_comments = []
    for comment in separate:
        if type(comment["post_id"]) is type(post_id) and comment["post_id"] == post_id:
            expected_comments.append(comment.get("content", comment.get("text")))
    for comment in embedded:
        if isinstance(comment, dict):
            expected_comments.append(comment.get("content", comment.get("text")))
        elif comment.strip():
            expected_comments.append(comment.strip())
    result["comments"] = deepcopy(expected_comments if result_comments_override is None else result_comments_override)
    first_input = {key: deepcopy(result[key]) for key in ("gallery_id", "post_id", "title", "content", "comments")}
    first_input["comments"] = embedded
    if comment_metadata is not None:
        first_input["comment_metadata"] = deepcopy(comment_metadata)
    inputs = [first_input] + [{**deepcopy(first_input), "post_id": identifier, "comments": [],
                              "title": f"미실행 합성 입력 {index}"}
                             for index, identifier in enumerate(ids[1:], 2)]
    input_records = inputs + separate
    input_raw = (json_bytes(inputs) if input_format == "JSON_ARRAY_V1" else
                 b"".join(json_bytes(row) + b"\n" for row in input_records))
    input_sha = hashlib.sha256(input_raw).hexdigest()
    scope = build_publication_scope_descriptor(input_file_sha256=input_sha, post_ids=ids,
        config_hash="r6-synthetic-config", release_fingerprint="r6-synthetic-only")
    receipt = compute_publication_decision_commit(result, publication_scope_id=scope.publication_scope_id,
        attempt_run_id="r6-base-synthetic-attempt", input_index=1, post_id=post_id)
    router = build_semantic_review_router_receipt(result, receipt, attempt_run_id=receipt.attempt_run_id,
        **({"rule_version": router_rule_version} if router_rule_version is not None else {}))
    recovery = build_semantic_recovery_plan_receipt(result, receipt, attempt_run_id=receipt.attempt_run_id)
    proposals = extract_direct_ocr_review_proposals(result)
    if len(proposals) != 1:
        raise AssertionError("synthetic fixture must produce exactly one original OCR proposal")
    proposal = proposals[0]
    event = _create_event(receipt=receipt, proposal=proposal, raw_capability="synthetic-audit-only-token",
        hmac_key=HMAC_KEY, sequence=1, prev_event_sha256="GENESIS")
    item = result["analysis_result"]["identity"]["image_evidence_catalog"][0]
    query = proposal.raw_candidate_title
    source_binding = {"source_locator": proposal.source_locator, "source_item_sha256": canonical_sha256(item),
        "field_pointer": "/ocr_text", "span_start": 0, "span_end": len(query.encode("utf-8")),
        "span_unit": "UTF8_FIELD_VALUE", "query": query,
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(), "relation_role": proposal.relation_role}
    kinds = list(action_kinds) if action_kinds is not None else ["REVALIDATE_SAVED_EVIDENCE"]
    search_purposes = iter(recovery["plan"]["query_plan"]["purposes"])
    actions = []
    for index, kind in enumerate(kinds, 1):
        purpose = (next(search_purposes) if kind == "SIMULATED_TARGETED_SEARCH" else
                   "REVIEW_SAVED_EVIDENCE" if kind == "SIMULATED_EXPERT_REVIEW" else "REVALIDATE_SAVED_EVIDENCE")
        actions.append({"action_id": f"action-{index}", "kind": kind, "purpose": purpose,
            **{key: source_binding[key] for key in ("query", "query_sha256", "source_item_sha256", "relation_role")}})
    default_response = {"outcome": "SUCCESS", "delay_ms": 0, "retry_delay_ms": 0,
                        "response": {"status": "SYNTHETIC_OBSERVATION", "publication_authority": False}}
    fixture = {"schema_version": "recovery_simulation_fixture_v1", "data_kind": "SYNTHETIC_CONTRACT_ONLY",
        "actions": [{"action_id": action["action_id"],
            "responses": deepcopy(responses.get(action["action_id"], [default_response]) if isinstance(responses, dict)
                                  else responses if responses is not None else [default_response])}
                    for action in actions]}
    policy = {"max_actions": 16, "max_simulated_dispatches": 16, "max_retries_per_action": 2,
              "max_elapsed_ms": 1000, "per_action_timeout_ms": 100, "cancel_grace_ms": 10,
              "max_output_bytes": 65536, "actual_external_call_budget": 0}
    policy.update(policy_overrides or {})
    manifest = {"run_id": receipt.attempt_run_id, "publication_scope_id": scope.publication_scope_id,
                "input_sha256": input_sha, "data_kind": "SYNTHETIC_CONTRACT_ONLY"}
    payload = {"schema_version": "recovery_source_capture_v1", "data_kind": "SYNTHETIC_CONTRACT_ONLY",
               "input_raw_sha256": input_sha, "input_index": 1, "post_id": post_id,
               "source_locator": proposal.source_locator, "item": item}
    raw = {"input": input_raw, "result": json_bytes(result), "manifest": json_bytes(manifest),
           "publication_wal": json_bytes({"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
                                         "receipt": receipt.to_dict(), "result": result}) + b"\n",
           "activation_journal": json_bytes(event.to_dict()) + b"\n", "router": json_bytes(router),
           "recovery_plan": json_bytes(recovery), "source_payload": json_bytes(payload),
           "fixture": json_bytes(fixture)}
    refs = {}
    for role, data in raw.items():
        path = source_dir / (role + (".jsonl" if role.endswith("wal") or role.endswith("journal") else ".json"))
        with path.open("xb") as handle:
            handle.write(data)
        refs[role] = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    kwargs = {"artifact_refs": refs, "artifact_bytes": raw, "input_format": input_format,
              "result_pointer": "", "router_pointer": "", "recovery_plan_pointer": "",
              "publication_decision_id": receipt.decision_id, "activation_event_sha256": event.event_sha256,
              "source_binding": source_binding, "actions": actions, "policy": policy,
              "output_dir": str(root / "output"), "hmac_key": HMAC_KEY}
    plan = build_recovery_execution_plan(**kwargs)
    bound = bind_recovery_execution_plan(plan, hmac_key=HMAC_KEY)
    return {"plan": plan, "bound": bound, "hmac_key": HMAC_KEY, "artifact_bytes": raw,
            "artifact_refs": refs, "build_kwargs": kwargs, "result": result, "receipt": receipt,
            "event": event, "fixture": fixture, "input_posts": inputs, "router": router,
            "recovery_plan": recovery, "source_binding": source_binding, "source_payload": payload,
            "manifest": manifest, "scope": scope, "input_records": input_records}


def build_bound_fixture(root: Path, *, responses=None, policy_overrides=None, post_ids=None, **kwargs) -> dict:
    return make_recovery_fixture(root, responses=responses, policy_overrides=policy_overrides,
                                 post_ids=post_ids, **kwargs)
