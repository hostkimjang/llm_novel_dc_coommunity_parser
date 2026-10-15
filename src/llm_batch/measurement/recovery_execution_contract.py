from __future__ import annotations

"""Bound, read-only inputs for a local synthetic recovery simulation.

An activation signature authenticates an AUDIT_ONLY proposal, never an external
execution permit. No registry, provider, subprocess, or mutable source writer is
created here. The only I/O API reads explicitly named, bounded regular files.
"""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

from ..ledger.publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA,
    PublicationDecisionCommit,
    validate_publication_result_commit,
)
from ..ledger.recovery_activation import (
    RecoveryActivationEvent,
    extract_direct_ocr_review_proposals,
)
from .semantic_recovery_plan import validate_semantic_recovery_plan_receipt
from .semantic_review_router import validate_semantic_review_router_receipt


PLAN_SCHEMA = "recovery_execution_plan_v1"
EXECUTION_MODE = "LOCAL_SIMULATION_ONLY"
DATA_KIND = "SYNTHETIC_CONTRACT_ONLY"
MAX_PLAN_BYTES = 65536
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_EVENTS = 10000
_HEX = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ROLES = frozenset({"input", "result", "manifest", "publication_wal", "activation_journal",
                    "router", "recovery_plan", "source_payload", "fixture"})
_TOP = frozenset({"schema_version", "execution_mode", "data_kind", "public_apply",
                  "publication_authority", "central_db_write", "actual_external_call_budget",
                  "base", "review", "activation", "source_binding", "actions", "policy",
                  "fixture_sha256", "artifacts", "selectors", "output_dir", "plan_sha256",
                  "binding_sha256"})
_BASE = frozenset({"publication_scope_id", "input_index", "post_id", "base_attempt_run_id",
                   "publication_decision_id", "commit_sha256", "result_sha256",
                   "stable_result_sha256", "public_projection_sha256", "contract_input_fingerprint",
                   "input_count", "input_order_sha256", "input_raw_sha256"})
_SOURCE = frozenset({"source_locator", "source_item_sha256", "field_pointer", "span_start",
                     "span_end", "span_unit", "query", "query_sha256", "relation_role"})
_ACTION = frozenset({"action_id", "kind", "purpose", "query", "query_sha256",
                     "source_item_sha256", "relation_role"})
_POLICY_LIMITS = {"max_actions": 16, "max_simulated_dispatches": 64,
                  "max_retries_per_action": 15, "max_elapsed_ms": 60000,
                  "per_action_timeout_ms": 60000, "cancel_grace_ms": 60000,
                  "max_output_bytes": 65536, "actual_external_call_budget": 0}
_KINDS = {"REVALIDATE_SAVED_EVIDENCE": "REVALIDATE_SAVED_EVIDENCE",
          "SIMULATED_EXPERT_REVIEW": "REVIEW_SAVED_EVIDENCE"}
_OUTCOMES = frozenset({"SUCCESS", "TRANSIENT_FAILURE", "PERMANENT_FAILURE",
                       "CANCEL_CONFIRMED", "NO_RESPONSE", "CALLBACK_ERROR"})
_RELATION_ROLES = frozenset({"primary", "previous", "mentioned", "comparison", "candidate", "ambiguous"})


class RecoveryExecutionContractError(ValueError):
    """A plan or its original evidence is incomplete, inconsistent, or unsafe."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RecoveryExecutionContractError(message)


def _json_value(value: Any, depth: int = 0) -> None:
    _require(depth <= 64, "JSON nesting exceeds limit")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        _require(math.isfinite(value), "JSON number must be finite")
    elif type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
    elif type(value) is dict:
        _require(all(type(key) is str for key in value), "JSON keys must be strings")
        for item in value.values():
            _json_value(item, depth + 1)
    else:
        raise RecoveryExecutionContractError("only strict JSON values are supported")


def _canonical_bytes(value: Any) -> bytes:
    _json_value(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise RecoveryExecutionContractError("invalid canonical JSON") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact(value: Any, fields: set | frozenset, name: str) -> dict:
    _require(type(value) is dict and set(value) == fields, f"{name} fields mismatch")
    return value


def _text(value: Any, name: str) -> str:
    _require(type(value) is str and bool(value.strip()), f"{name} must be nonempty text")
    return value


def _integer(value: Any, name: str, minimum: int = 0, maximum: int = MAX_EVENTS) -> int:
    _require(type(value) is int and minimum <= value <= maximum, f"{name} integer out of bounds")
    return value


def _hex(value: Any, name: str) -> str:
    _require(type(value) is str and _HEX.fullmatch(value) is not None, f"{name} invalid SHA256")
    return value


def _post(value: Any) -> int | str:
    _require((type(value) is int and value > 0) or
             (type(value) is str and bool(value.strip())), "post_id must retain strict int/string type")
    return value


def _equal(left: Any, right: Any, name: str) -> None:
    _require(_canonical_bytes(left) == _canonical_bytes(right), f"{name} mismatch")


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _load_json(raw: bytes) -> Any:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               RecoveryExecutionContractError("nonfinite JSON number")))
        _json_value(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise RecoveryExecutionContractError("invalid strict UTF-8 JSON") from exc


def _json_lines(raw: bytes, name: str) -> list:
    _require(type(raw) is bytes and len(raw) <= MAX_FILE_BYTES, f"{name} byte limit")
    _require(not raw or raw.endswith(b"\n"), f"INCOMPLETE_JOURNAL: {name}")
    lines = raw.splitlines()
    _require(len(lines) <= MAX_EVENTS, f"{name} event limit")
    _require(all(line.strip() for line in lines), f"{name} blank frame")
    return [_load_json(line) for line in lines]


def _pointer(value: Any, pointer: str) -> Any:
    _require(type(pointer) is str and (pointer == "" or pointer.startswith("/")),
             "invalid JSON pointer")
    if pointer == "":
        return value
    current = value
    for token in pointer[1:].split("/"):
        _require(re.search(r"~(?![01])", token) is None, "invalid JSON pointer escape")
        token = token.replace("~1", "/").replace("~0", "~")
        if type(current) is dict:
            _require(token in current, "JSON pointer missing field")
            current = current[token]
        elif type(current) is list:
            _require(re.fullmatch(r"0|[1-9][0-9]*", token) is not None, "invalid array pointer")
            _require(int(token) < len(current), "array pointer out of bounds")
            current = current[int(token)]
        else:
            raise RecoveryExecutionContractError("JSON pointer crosses scalar")
    return current


def read_recovery_activation_snapshot(raw_bytes: bytes, *, expected_sha256: str,
                                      hmac_key: bytes, expected_scope_id: str | None = None) -> tuple[dict, ...]:
    """Verify a frozen audit chain without locks, repair, or capability elevation."""
    _hex(expected_sha256, "activation raw")
    _require(type(raw_bytes) is bytes, "activation snapshot must be bytes")
    _require(hashlib.sha256(raw_bytes).hexdigest() == expected_sha256, "activation raw SHA mismatch")
    _require(type(hmac_key) is bytes and len(hmac_key) >= 32, "HMAC key must be explicit bytes >=32")
    previous = "GENESIS"
    scope = expected_scope_id
    seen_proposals, seen_activations = set(), set()
    output = []
    for ordinal, value in enumerate(_json_lines(raw_bytes, "activation"), 1):
        try:
            event = RecoveryActivationEvent.from_dict(value)
            event.verify_authorization(hmac_key)
        except (ValueError, TypeError) as exc:
            raise RecoveryExecutionContractError("activation event/signature invalid") from exc
        _post(event.post_id)
        _integer(event.input_index, "activation input index", 1)
        if scope is None:
            scope = event.publication_scope_id
        _require(event.publication_scope_id == scope, "activation mixed scope")
        _require(event.sequence == ordinal and event.prev_event_sha256 == previous,
                 "activation chain mismatch")
        activation_key = canonical_sha256({"publication_scope_id": scope,
            "input_index": event.input_index, "post_id": event.post_id,
            "proposal_kind": event.proposal_kind, "overlay_schema": event.overlay_schema,
            "proposal": event.proposal.to_dict()})
        _require(event.proposal_id not in seen_proposals and activation_key not in seen_activations,
                 "duplicate activation proposal")
        seen_proposals.add(event.proposal_id)
        seen_activations.add(activation_key)
        previous = event.event_sha256
        output.append(event.to_dict())
    return tuple(output)


def _absolute_path(value: Any) -> Path:
    value = _text(value, "artifact path")
    path = Path(value)
    _require(path.is_absolute() and ".." not in path.parts, "path must be explicit absolute without traversal")
    # UNC, device, and ADS paths could perform remote I/O or address alternate data.
    _require(not value.startswith(("\\\\", "//")), "remote/device path forbidden")
    tail = value[2:] if re.match(r"^[A-Za-z]:", value) else value
    _require(":" not in tail and "\x00" not in value, "alternate data/device path forbidden")
    return path


def _refs(refs: Any) -> dict:
    _require(type(refs) is dict and _ROLES <= set(refs) <= (_ROLES | {"db"}), "artifact roles mismatch")
    paths, total = set(), 0
    for role, ref in refs.items():
        _exact(ref, {"path", "sha256", "bytes"}, f"{role} ref")
        path = _absolute_path(ref["path"])
        normalized = os.path.normcase(os.path.abspath(path))
        _require(normalized not in paths, "duplicate artifact path")
        paths.add(normalized)
        _hex(ref["sha256"], f"{role} raw")
        total += _integer(ref["bytes"], f"{role} bytes", 0, MAX_FILE_BYTES)
    _require(total <= MAX_TOTAL_BYTES, "total artifact byte limit")
    return refs


def _comment_text(comment: dict) -> str:
    value = comment.get("content", comment.get("text"))
    _require(type(value) is str, "comment original content/text must be a string")
    if comment.get("content") not in (None, "") and comment.get("text") not in (None, ""):
        _equal(comment["content"], comment["text"], "comment content/text aliases")
    return value


def _input_snapshot(raw: bytes, input_format: str) -> tuple[list[dict], dict]:
    """Keep exact records; bind the loader's separate-first comment projection.

The strict subset does not silently deduplicate conflicting raw records. String
embedded comments are stripped as in expert_main.load_jsonl_posts; dict comments
use content (or text only when content is absent), without title inference.
JSONL posts may omit comments when comments are separate records. An absent
field uses the loader's comments_raw list fallback without changing raw posts;
explicit non-list comments remain outside this strict execution subset.
"""
    _require(input_format in {"JSON_ARRAY_V1", "JSONL_POST_COMMENT_V1"}, "unsupported input format")
    values = _load_json(raw) if input_format == "JSON_ARRAY_V1" else _json_lines(raw, "input")
    _require(type(values) is list and 0 < len(values) <= MAX_EVENTS, "input record count invalid")
    lines = raw.splitlines() if input_format == "JSONL_POST_COMMENT_V1" else None
    posts, comments, seen, records, post_records = [], [], set(), [], []
    for ordinal, value in enumerate(values, 1):
        _require(type(value) is dict, "input record must be object")
        post = _post(value.get("post_id"))
        record = {"record_index": ordinal, "payload": deepcopy(value),
                  "raw_line_sha256": hashlib.sha256(lines[ordinal - 1]).hexdigest() if lines is not None else None}
        records.append(record)
        if input_format == "JSONL_POST_COMMENT_V1" and "comment_id" in value:
            _post(value["comment_id"])
            _comment_text(value)
            comments.append(record)
            continue
        key = canonical_sha256(post)
        _require(key not in seen, "duplicate input post_id")
        seen.add(key)
        posts.append(deepcopy(value))
        post_records.append(record)
    _require(bool(posts), "input has no posts")
    comment_ids = set()
    by_parent = {}
    for record in comments:
        value = record["payload"]
        _require(canonical_sha256(value["post_id"]) in seen, "orphan input comment")
        key = canonical_sha256([value["post_id"], value["comment_id"]])
        _require(key not in comment_ids, "duplicate input comment")
        comment_ids.add(key)
        by_parent.setdefault(canonical_sha256(value["post_id"]), []).append(record)
    bindings = []
    for index, (post, post_record) in enumerate(zip(posts, post_records), 1):
        separate = by_parent.get(canonical_sha256(post["post_id"]), [])
        embedded = (post.get("comments_raw", [])
                    if input_format == "JSONL_POST_COMMENT_V1" and "comments" not in post
                    else post.get("comments"))
        _require(type(embedded) is list, "post comments must be explicit list")
        projected, loader_ids = [], set()
        if input_format == "JSON_ARRAY_V1":
            projected = deepcopy(embedded)
        else:
            for record in separate:
                comment = record["payload"]
                key = str(comment["comment_id"]).strip()
                _require(key not in loader_ids, "duplicate normalized comment_id")
                loader_ids.add(key)
                projected.append(_comment_text(comment))
            metadata = post.get("comment_metadata", [])
            _require(type(metadata) is list, "comment_metadata must be a list")
            for ordinal, value in enumerate(embedded):
                if type(value) is str:
                    text = value.strip()
                    if not text:
                        continue
                    comment = {"content": text}
                else:
                    _require(type(value) is dict, "embedded comment must be string/object")
                    comment = deepcopy(value)
                    text = _comment_text(comment)
                if "post_id" in comment:
                    _equal(comment["post_id"], post["post_id"], "embedded comment parent")
                # The loader fills metadata first, then uses setdefault: an
                # explicitly empty ID must never become a fresh ordinal ID.
                meta = metadata[ordinal] if ordinal < len(metadata) and type(metadata[ordinal]) is dict else {}
                if comment.get("comment_id") in (None, "") and meta.get("comment_id") not in (None, ""):
                    comment["comment_id"] = meta["comment_id"]
                comment.setdefault("comment_id", f"{post['post_id']}:embedded:{ordinal}")
                identifier = comment["comment_id"]
                # Empty IDs use author/IP/time/body deduplication in the loader.
                # This strict execution subset rejects them rather than inventing
                # a unique identity or silently dropping raw comments.
                _require(bool(str(identifier or "").strip()), "explicit empty comment_id is not eligible")
                _post(identifier)
                key = str(identifier).strip()
                _require(key not in loader_ids, "duplicate separate/embedded comment_id")
                loader_ids.add(key)
                projected.append(text)
        bindings.append({"input_index": index, "post_id": post["post_id"],
                         "post_record": deepcopy(post_record), "separate_comment_records": deepcopy(separate),
                         "result_comments": projected})
    return posts, {"input_format": input_format, "records": records, "post_bindings": bindings,
                   "comment_projection_schema": "expert_main_separate_then_embedded_text_v1",
                   "raw_line_hash_scope": "EXACT_LINE_BYTES_EXCLUDING_LINE_ENDING" if lines is not None else None}


def _input_posts(raw: bytes, input_format: str) -> list[dict]:
    return _input_snapshot(raw, input_format)[0]


def _validate_policy(policy: Any) -> None:
    _exact(policy, set(_POLICY_LIMITS), "policy")
    for key, limit in _POLICY_LIMITS.items():
        _integer(policy[key], key, 0, limit)
    for key in ("per_action_timeout_ms", "cancel_grace_ms"):
        _require(policy[key] <= policy["max_elapsed_ms"], f"{key} exceeds elapsed budget")


def _validate_source(source: Any) -> None:
    _exact(source, _SOURCE, "source_binding")
    for field in ("source_locator", "relation_role", "query"):
        _text(source[field], field)
    _require(source["relation_role"] in _RELATION_ROLES, "SOURCE_ROLE_NOT_ELIGIBLE: unknown or undefined relation role")
    _hex(source["source_item_sha256"], "source item")
    _hex(source["query_sha256"], "query")
    _require(hashlib.sha256(source["query"].encode("utf-8")).hexdigest() == source["query_sha256"],
             "query raw SHA mismatch")
    _require(type(source["field_pointer"]) is str and source["field_pointer"].startswith("/"),
             "source field pointer required")
    _require(source["span_unit"] == "UTF8_FIELD_VALUE", "span unit mismatch")
    start = _integer(source["span_start"], "span start", 0, MAX_FILE_BYTES)
    end = _integer(source["span_end"], "span end", 1, MAX_FILE_BYTES)
    _require(end > start and end - start == len(source["query"].encode("utf-8")), "span size mismatch")


def _validate_actions(actions: Any, source: dict, review: dict, policy: dict) -> None:
    _require(type(actions) is list and 0 < len(actions) <= 16, "action count out of bounds")
    _require(len(actions) <= policy["max_actions"], "actions exceed policy")
    ids, purposes, search_count = set(), set(), 0
    for action in actions:
        _exact(action, _ACTION, "action")
        action_id = _text(action["action_id"], "action_id")
        _require(_ID.fullmatch(action_id) is not None and action_id not in ids, "invalid/duplicate action_id")
        ids.add(action_id)
        for key in ("query", "query_sha256", "source_item_sha256", "relation_role"):
            _equal(action[key], source[key], f"action {key}")
        kind, purpose = action["kind"], action["purpose"]
        _text(kind, "action kind")
        _text(purpose, "action purpose")
        if kind == "SIMULATED_TARGETED_SEARCH":
            _require(purpose in review["query_purposes"] and purpose not in purposes,
                     "search purpose missing/duplicate")
            purposes.add(purpose)
            search_count += 1
        else:
            _require(kind in _KINDS and purpose == _KINDS[kind], "action kind/purpose forbidden")
    _require(search_count <= review["max_queries"], "search actions exceed semantic query limit")


def validate_fixture(fixture: Any, *, actions: list[dict]) -> dict:
    """Validate fixed JSON response scripts, not callable backend registrations."""
    _require(len(_canonical_bytes(fixture)) <= MAX_PLAN_BYTES, "fixture byte limit")
    _exact(fixture, {"schema_version", "data_kind", "actions"}, "fixture")
    _require(fixture["schema_version"] == "recovery_simulation_fixture_v1" and
             fixture["data_kind"] == DATA_KIND, "fixture mode mismatch")
    entries = fixture["actions"]
    _require(type(entries) is list and 0 < len(entries) <= 16, "fixture action count")
    ids = []
    for entry in entries:
        _exact(entry, {"action_id", "responses"}, "fixture action")
        ids.append(entry["action_id"])
        responses = entry["responses"]
        _require(type(responses) is list and 0 < len(responses) <= 16, "fixture response count")
        for response in responses:
            _exact(response, {"outcome", "delay_ms", "retry_delay_ms", "response"}, "fixture response")
            _require(type(response["outcome"]) is str and response["outcome"] in _OUTCOMES,
                     "fixture outcome invalid")
            _integer(response["delay_ms"], "fixture delay_ms", 0, 60000)
            _integer(response["retry_delay_ms"], "fixture retry_delay_ms", 0, 60000)
            _require(response["response"] is None or type(response["response"]) is dict,
                     "fixture response must be object/null")
    _equal(ids, [action["action_id"] for action in actions], "fixture action order")
    return deepcopy(fixture)


def _semantic_material(plan: dict) -> dict:
    material = {key: deepcopy(value) for key, value in plan.items()
                if key not in {"plan_sha256", "binding_sha256", "output_dir"}}
    material["artifacts"] = {role: {"sha256": ref["sha256"], "bytes": ref["bytes"]}
                             for role, ref in plan["artifacts"].items()}
    return material


def _seal(plan: dict) -> dict:
    material = deepcopy(plan)
    material["plan_sha256"] = canonical_sha256(_semantic_material(material))
    material["binding_sha256"] = canonical_sha256({key: value for key, value in material.items()
                                                   if key != "binding_sha256"})
    return material


def validate_plan(plan: Any) -> dict:
    _require(len(_canonical_bytes(plan)) <= MAX_PLAN_BYTES, "plan byte limit")
    _exact(plan, _TOP, "plan")
    _require(plan["schema_version"] == PLAN_SCHEMA and plan["execution_mode"] == EXECUTION_MODE
             and plan["data_kind"] == DATA_KIND, "plan mode/schema mismatch")
    for key in ("public_apply", "publication_authority", "central_db_write"):
        _require(plan[key] is False, f"{key} must remain false")
    _integer(plan["actual_external_call_budget"], "external budget", 0, 0)
    base = _exact(plan["base"], _BASE, "base")
    _integer(base["input_index"], "base input index", 1)
    _integer(base["input_count"], "base input count", 1)
    _require(base["input_index"] <= base["input_count"], "base outside input denominator")
    _post(base["post_id"])
    _text(base["base_attempt_run_id"], "base attempt")
    for key in _BASE - {"post_id", "input_index", "input_count", "base_attempt_run_id", "contract_input_fingerprint"}:
        _hex(base[key], key)
    if base["contract_input_fingerprint"] is not None:
        _hex(base["contract_input_fingerprint"], "contract input fingerprint")
    review = _exact(plan["review"], {"router_receipt_sha256", "recovery_plan_receipt_sha256",
                                     "query_purposes", "max_queries"}, "review")
    for key in ("router_receipt_sha256", "recovery_plan_receipt_sha256"):
        _hex(review[key], key)
    purposes = review["query_purposes"]
    _require(type(purposes) is list and all(type(item) is str and item for item in purposes),
             "query purposes invalid")
    _require(purposes == sorted(set(purposes)), "query purposes must be sorted unique")
    _integer(review["max_queries"], "max queries", 0, 2)
    _require(review["max_queries"] <= len(purposes), "query count without purposes")
    activation = _exact(plan["activation"], {"event_sha256", "sequence", "proposal_id",
                                             "proposal_sha256", "mode", "capability_scope"}, "activation")
    for key in ("event_sha256", "proposal_id", "proposal_sha256"):
        _hex(activation[key], key)
    _integer(activation["sequence"], "activation sequence", 1)
    _require(activation["mode"] == "AUDIT_ONLY" and
             activation["capability_scope"] == "proposal_authorization_only", "audit authority elevated")
    _validate_source(plan["source_binding"])
    _validate_policy(plan["policy"])
    _validate_actions(plan["actions"], plan["source_binding"], review, plan["policy"])
    _hex(plan["fixture_sha256"], "fixture")
    refs = _refs(plan["artifacts"])
    _require(refs["fixture"]["bytes"] <= MAX_PLAN_BYTES, "fixture raw byte limit")
    _equal(base["input_raw_sha256"], refs["input"]["sha256"], "input raw binding")
    selectors = _exact(plan["selectors"], {"input_format", "result_pointer", "router_pointer",
                                           "recovery_plan_pointer"}, "selectors")
    _require(selectors["input_format"] in {"JSON_ARRAY_V1", "JSONL_POST_COMMENT_V1"}, "input format invalid")
    for key in ("result_pointer", "router_pointer", "recovery_plan_pointer"):
        _require(type(selectors[key]) is str and
                 (selectors[key] == "" or selectors[key].startswith("/")), "selector pointer invalid")
    output = _absolute_path(plan["output_dir"])
    for ref in refs.values():
        source = _absolute_path(ref["path"])
        _require(output != source and output not in source.parents and source not in output.parents,
                 "output overlaps protected source")
    expected = _seal(plan)
    for key in ("plan_sha256", "binding_sha256"):
        _hex(plan[key], key)
        _require(plan[key] == expected[key], f"{key} mismatch")
    return deepcopy(plan)


validate_recovery_execution_plan = validate_plan


def execution_journal_arguments(plan: Any) -> dict:
    """One shared projection binds the journal to semantic and file coordinates."""
    checked = validate_plan(plan)
    base = checked["base"]
    return {"binding": {
        "plan_sha256": checked["plan_sha256"], "base_sha256": canonical_sha256(base),
        "policy_sha256": canonical_sha256(checked["policy"]), "config_sha256": checked["binding_sha256"],
        "source_sha256": canonical_sha256({"source_binding": checked["source_binding"],
                                           "artifacts": checked["artifacts"]}),
        "fixture_sha256": checked["fixture_sha256"],
        **{key: base[key] for key in ("publication_scope_id", "input_index", "post_id", "base_attempt_run_id")}},
        "policy": deepcopy(checked["policy"]),
        "actions": [{"action_id": action["action_id"], "action_kind": action["kind"],
                     "query_sha256": action["query_sha256"]} for action in checked["actions"]]}


def _publication_event(raw: bytes, decision_id: str, posts: list[dict]) -> tuple[dict, PublicationDecisionCommit]:
    selected = None
    scope = None
    seen = set()
    for event in _json_lines(raw, "publication WAL"):
        _exact(event, {"schema_version", "receipt", "result"}, "publication event")
        _require(event["schema_version"] == PUBLICATION_COMMIT_EVENT_SCHEMA, "publication event schema")
        try:
            receipt = PublicationDecisionCommit.from_dict(event["receipt"])
            validate_publication_result_commit(event["result"], receipt)
        except (ValueError, TypeError, KeyError) as exc:
            raise RecoveryExecutionContractError("publication full commit invalid") from exc
        _post(receipt.post_id)
        index = _integer(receipt.input_index, "publication index", 1, len(posts))
        _equal(receipt.post_id, posts[index - 1]["post_id"], "publication/input post type")
        _equal(event["result"].get("post_id"), receipt.post_id, "publication result post type")
        if scope is None:
            scope = receipt.publication_scope_id
        _require(receipt.publication_scope_id == scope, "publication mixed scope")
        _require(index not in seen, "duplicate publication input index")
        seen.add(index)
        if receipt.decision_id == decision_id:
            _require(selected is None, "duplicate publication decision")
            selected = (event["result"], receipt)
    _require(selected is not None, "publication decision not found")
    return selected


def _source_bound(source: dict, payload: Any, result: dict, event: dict, base: dict) -> None:
    _validate_source(source)
    _exact(payload, {"schema_version", "data_kind", "input_raw_sha256", "input_index", "post_id",
                     "source_locator", "item"}, "source payload")
    _require(payload["schema_version"] == "recovery_source_capture_v1" and
             payload["data_kind"] == DATA_KIND, "source payload schema/mode")
    for key in ("input_raw_sha256", "input_index", "post_id"):
        _equal(payload[key], base[key], f"source parent {key}")
    _equal(payload["source_locator"], source["source_locator"], "source locator")
    item = payload["item"]
    _require(type(item) is dict, "source catalog item invalid")
    _equal(canonical_sha256(item), source["source_item_sha256"], "source item canonical SHA")
    identity = result["analysis_result"]["identity"]
    catalog = identity.get("image_evidence_catalog")
    _require(type(catalog) is list and sum(_canonical_bytes(other) == _canonical_bytes(item)
                                         for other in catalog) == 1, "source item not uniquely in result")
    proposals = [proposal.to_dict() for proposal in extract_direct_ocr_review_proposals(result)]
    _require(any(_canonical_bytes(proposal) == _canonical_bytes(event["proposal"])
                 for proposal in proposals), "PROPOSAL_NOT_BOUND to original extractor")
    proposal = event["proposal"]
    _require(proposal["source_payload_sha256"] is not None, "SOURCE_NOT_BOUND: missing catalog SHA")
    _equal(proposal["source_payload_sha256"], source["source_item_sha256"], "proposal catalog SHA")
    for proposal_key, source_key in (("source_locator", "source_locator"),
                                     ("relation_role", "relation_role"), ("raw_candidate_title", "query")):
        _equal(proposal[proposal_key], source[source_key], f"proposal {proposal_key}")
    field = _pointer(item, source["field_pointer"])
    _require(type(field) is str, "source field must be text")
    encoded = field.encode("utf-8")
    _require(source["span_end"] <= len(encoded), "span outside original field")
    try:
        query = encoded[source["span_start"]:source["span_end"]].decode("utf-8")
    except UnicodeError as exc:
        raise RecoveryExecutionContractError("span splits UTF-8 codepoint") from exc
    _equal(query, source["query"], "original source span query")


def build_recovery_execution_plan(*, artifact_refs: dict, artifact_bytes: dict,
        input_format: str, result_pointer: str, router_pointer: str, recovery_plan_pointer: str,
        publication_decision_id: str, activation_event_sha256: str, source_binding: dict,
        actions: list[dict], policy: dict, output_dir: str, hmac_key: bytes) -> dict:
    """Build only from explicit original bytes; no file reads/writes or dispatch."""
    refs = deepcopy(_refs(artifact_refs))
    _validate_source(source_binding)
    _require(type(artifact_bytes) is dict and set(artifact_bytes) == set(refs), "artifact bytes roles mismatch")
    for role, ref in refs.items():
        raw = artifact_bytes[role]
        _require(type(raw) is bytes and len(raw) == ref["bytes"] and
                 hashlib.sha256(raw).hexdigest() == ref["sha256"], f"{role} raw binding mismatch")
    _hex(publication_decision_id, "requested publication decision")
    _hex(activation_event_sha256, "requested activation event")
    posts, input_bindings = _input_snapshot(artifact_bytes["input"], input_format)
    wal_result, receipt = _publication_event(artifact_bytes["publication_wal"], publication_decision_id, posts)
    result = _pointer(_load_json(artifact_bytes["result"]), result_pointer)
    _equal(result, wal_result, "original result/WAL")
    _require(receipt.outcome == "HOLD" and receipt.publish_allowed is False,
             "base must be typed HOLD without publication authority")
    parent = posts[receipt.input_index - 1]
    for key in ("gallery_id", "post_id", "title", "content"):
        _require(key in parent and key in result, f"original input/result missing {key}")
        _equal(parent[key], result[key], f"original input/result {key}")
    _require("comments" in result, "original result missing comments")
    _equal(input_bindings["post_bindings"][receipt.input_index - 1]["result_comments"],
           result["comments"], "original input/result comments projection")
    base = {"publication_scope_id": receipt.publication_scope_id,
            "input_index": receipt.input_index, "post_id": receipt.post_id,
            "base_attempt_run_id": receipt.attempt_run_id, "publication_decision_id": receipt.decision_id,
            "commit_sha256": receipt.commit_sha256, "result_sha256": receipt.result_sha256,
            "stable_result_sha256": receipt.stable_result_sha256,
            "public_projection_sha256": receipt.public_projection_sha256,
            "contract_input_fingerprint": receipt.contract_input_fingerprint,
            "input_count": len(posts), "input_order_sha256": canonical_sha256([post["post_id"] for post in posts]),
            "input_raw_sha256": refs["input"]["sha256"]}
    manifest = _load_json(artifact_bytes["manifest"])
    _require(type(manifest) is dict, "manifest must be object")
    for key, expected in {"run_id": receipt.attempt_run_id, "publication_scope_id": receipt.publication_scope_id,
                          "input_sha256": refs["input"]["sha256"], "data_kind": DATA_KIND}.items():
        _equal(manifest.get(key), expected, f"manifest {key}")
    router = _pointer(_load_json(artifact_bytes["router"]), router_pointer)
    recovery = _pointer(_load_json(artifact_bytes["recovery_plan"]), recovery_plan_pointer)
    try:
        for value, validator in ((router, validate_semantic_review_router_receipt),
                                 (recovery, validate_semantic_recovery_plan_receipt)):
            _equal(value.get("post_id"), receipt.post_id, "review post type")
            validator(value, result=result, expected_publication_receipt=receipt,
                      expected_scope_id=receipt.publication_scope_id, expected_input_index=receipt.input_index,
                      expected_post_id=receipt.post_id, expected_attempt_run_id=receipt.attempt_run_id)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise RecoveryExecutionContractError("original semantic receipt binding invalid") from exc
    _require(router["state"] == "REVIEW_REQUIRED" and recovery["plan"]["state"] == "HOLD",
             f"PROPOSAL_NOT_BOUND: review/plan not eligible (router={router['state']}, "
             f"plan={recovery['plan']['state']})")
    events = read_recovery_activation_snapshot(artifact_bytes["activation_journal"],
        expected_sha256=refs["activation_journal"]["sha256"], hmac_key=hmac_key,
        expected_scope_id=receipt.publication_scope_id)
    chosen = [event for event in events if event["event_sha256"] == activation_event_sha256]
    _require(len(chosen) == 1, "activation event not found")
    event = chosen[0]
    event_base = {"publication_scope_id": receipt.publication_scope_id, "input_index": receipt.input_index,
                  "post_id": receipt.post_id, "base_decision_id": receipt.decision_id,
                  "base_commit_sha256": receipt.commit_sha256, "base_result_sha256": receipt.result_sha256,
                  "base_stable_result_sha256": receipt.stable_result_sha256,
                  "base_public_projection_sha256": receipt.public_projection_sha256,
                  "base_contract_input_fingerprint": receipt.contract_input_fingerprint}
    for key, expected in event_base.items():
        _equal(event[key], expected, f"activation base {key}")
    _source_bound(source_binding, _load_json(artifact_bytes["source_payload"]), result, event, base)
    query_plan = recovery["plan"]["query_plan"]
    review = {"router_receipt_sha256": router["receipt_sha256"],
              "recovery_plan_receipt_sha256": recovery["receipt_sha256"],
              "query_purposes": query_plan["purposes"],
              "max_queries": query_plan["max_queries"] if query_plan["query_execution_allowed"] else 0}
    _validate_policy(policy)
    _validate_actions(actions, source_binding, review, policy)
    _require(len(artifact_bytes["fixture"]) <= MAX_PLAN_BYTES, "fixture raw byte limit")
    fixture = validate_fixture(_load_json(artifact_bytes["fixture"]), actions=actions)
    material = {"schema_version": PLAN_SCHEMA, "execution_mode": EXECUTION_MODE, "data_kind": DATA_KIND,
        "public_apply": False, "publication_authority": False, "central_db_write": False,
        "actual_external_call_budget": 0, "base": base, "review": review,
        "activation": {"event_sha256": event["event_sha256"], "sequence": event["sequence"],
            "proposal_id": event["proposal_id"], "proposal_sha256": canonical_sha256(event["proposal"]),
            "mode": event["mode"], "capability_scope": event["capability_scope"]},
        "source_binding": source_binding, "actions": actions, "policy": policy,
        "fixture_sha256": canonical_sha256(fixture), "artifacts": refs,
        "selectors": {"input_format": input_format, "result_pointer": result_pointer,
                      "router_pointer": router_pointer, "recovery_plan_pointer": recovery_plan_pointer},
        "output_dir": output_dir}
    return validate_plan(_seal(material))


def _safe_path(path: Path, *, file_required: bool = False) -> Path:
    path = _absolute_path(str(path))
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        _require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
                 "symlink/reparse path forbidden")
        if component != path:
            _require(stat.S_ISDIR(info.st_mode), "path parent is not directory")
    if file_required:
        _require(path.is_file(), "protected source file unavailable")
    resolved = path.resolve(strict=file_required)
    _require(os.path.normcase(str(resolved)) == os.path.normcase(os.path.abspath(path)),
             "path resolution changed")
    return resolved


def _read_protected(ref: dict) -> tuple[bytes, tuple[int, int]]:
    path = _safe_path(Path(ref["path"]), file_required=True)
    before = path.stat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "protected source must have a single regular link")
    _require(before.st_size == ref["bytes"] <= MAX_FILE_BYTES, "protected source size drift")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            _require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino) and opened.st_nlink == 1,
                     "protected source changed while opening")
            raw = handle.read(MAX_FILE_BYTES + 1)
            after = os.fstat(handle.fileno())
    except OSError as exc:
        raise RecoveryExecutionContractError("protected source read failed") from exc
    current_path = _safe_path(path, file_required=True)
    current = current_path.stat()
    for info in (after, current):
        _require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink) ==
                 (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, 1),
                 "protected source changed during read")
    _require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"],
             "protected source raw SHA drift")
    return raw, (current.st_dev, current.st_ino)


_BOUND_TOKEN = object()


@dataclass(frozen=True, init=False)
class BoundRecoveryPlan:
    """Opaque factory product; accessors never expose mutable internal state."""

    _serialized: bytes
    _fixture_serialized: bytes
    _posts_serialized: bytes
    _input_bindings_serialized: bytes
    _file_identities: tuple

    def __init__(self, token: object = None, *, plan: dict | None = None,
                 fixture: dict | None = None, posts: list | None = None,
                 input_bindings: dict | None = None, identities: tuple = ()):
        _require(token is _BOUND_TOKEN, "BoundRecoveryPlan requires verified binding factory")
        object.__setattr__(self, "_serialized", _canonical_bytes(plan))
        object.__setattr__(self, "_fixture_serialized", _canonical_bytes(fixture))
        object.__setattr__(self, "_posts_serialized", _canonical_bytes(posts))
        object.__setattr__(self, "_input_bindings_serialized", _canonical_bytes(input_bindings))
        object.__setattr__(self, "_file_identities", identities)

    @property
    def plan(self) -> dict:
        return _load_json(self._serialized)

    def to_dict(self) -> dict:
        return self.plan

    @property
    def plan_sha256(self) -> str:
        return self.plan["plan_sha256"]

    @property
    def fixture(self) -> dict:
        return _load_json(self._fixture_serialized)

    @property
    def output_dir(self) -> Path:
        return Path(self.plan["output_dir"])

    @property
    def journal_path(self) -> Path:
        return self.output_dir / "recovery_execution.jsonl"

    def input_rows(self) -> list[dict]:
        return [{"input_index": index, "post_id": post["post_id"]}
                for index, post in enumerate(_load_json(self._posts_serialized), 1)]

    def input_bindings(self) -> dict:
        """Original JSONL post/comment records, parent/order, and result projection."""
        return _load_json(self._input_bindings_serialized)

    def verify_protected_sources(self) -> list[dict]:
        plan = validate_plan(self.plan)
        expected_ids = dict(self._file_identities)
        output = []
        for role, ref in plan["artifacts"].items():
            _, identity = _read_protected(ref)
            _require(identity == expected_ids[role], "protected source file identity drift")
            output.append({"role": role, **deepcopy(ref)})
        self.assert_output_path(self.journal_path)
        return output

    def assert_output_path(self, path: str | Path) -> Path:
        output = _safe_path(self.output_dir)
        target = _safe_path(Path(path))
        _require(target != output and output in target.parents, "output path outside fixed namespace")
        if output.exists():
            _require(output.is_dir(), "output namespace must be directory")
        if target.exists():
            info = target.stat()
            _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "output must have single regular link")
        for ref in self.plan["artifacts"].values():
            source = _safe_path(Path(ref["path"]), file_required=True)
            _require(source != target and source != output and output not in source.parents and
                     source not in output.parents, "output overlaps protected source")
            if target.exists():
                _require(not os.path.samefile(target, source), "output aliases protected source")
        return target


def read_bound_input_posts(bound_plan: BoundRecoveryPlan) -> list[dict]:
    _require(type(bound_plan) is BoundRecoveryPlan, "verified bound plan required")
    bound_plan.verify_protected_sources()
    return _load_json(bound_plan._posts_serialized)


def read_bound_input_bindings(bound_plan: BoundRecoveryPlan) -> dict:
    _require(type(bound_plan) is BoundRecoveryPlan, "verified bound plan required")
    bound_plan.verify_protected_sources()
    return bound_plan.input_bindings()


def bind_recovery_execution_plan(plan: Any, *, hmac_key: bytes) -> BoundRecoveryPlan:
    """Rebuild from current protected bytes and audit HMAC; never create files."""
    checked = validate_plan(plan)
    raw, identities, seen_ids = {}, {}, set()
    for role, ref in checked["artifacts"].items():
        raw[role], identities[role] = _read_protected(ref)
        _require(identities[role] not in seen_ids, "artifact identity aliases another source")
        seen_ids.add(identities[role])
    rebuilt = build_recovery_execution_plan(artifact_refs=checked["artifacts"], artifact_bytes=raw,
        **checked["selectors"], publication_decision_id=checked["base"]["publication_decision_id"],
        activation_event_sha256=checked["activation"]["event_sha256"], source_binding=checked["source_binding"],
        actions=checked["actions"], policy=checked["policy"], output_dir=checked["output_dir"], hmac_key=hmac_key)
    _equal(rebuilt, checked, "saved plan/current source rebuild")
    posts, input_bindings = _input_snapshot(raw["input"], checked["selectors"]["input_format"])
    bound = BoundRecoveryPlan(_BOUND_TOKEN, plan=checked, fixture=_load_json(raw["fixture"]),
        posts=posts, input_bindings=input_bindings,
        identities=tuple(identities.items()))
    bound.verify_protected_sources()
    return bound
