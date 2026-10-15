"""명시적 완료 원본에 묶인 단일 provider 검색 계획. 실행·공개 권한은 부여하지 않는다.

기존 합성 계약의 파일/JSON/입력/WAL 검산 helper만 재사용한다. 합성 source
schema를 바꾸거나 실제 자료에 합성 표식을 채우지 않는다. provider 응답과
native 공개 guard 재판정은 이 모듈의 범위 밖이다.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
from typing import Any

from . import recovery_execution_contract as legacy
from .recovery_input_projection import validate_main_input_projection
from ..ledger.publication_commit import PublicationScopeDescriptor
from ..ledger.recovery_activation import extract_direct_ocr_review_proposals
from ..runtime.recovery_transport import RecoveryTransportPolicy, _endpoint, _payload
from .semantic_review_router import validate_semantic_review_router_receipt
from .semantic_recovery_plan import validate_semantic_recovery_plan_receipt

SCHEMA = "recovery_provider_plan_v1"
SOURCE_SCHEMA = "recovery_provider_source_capture_v1"
MODE = "EXPLICIT_PROVIDER_EVIDENCE_ONLY"
MAX_PLAN_BYTES = 65536
_ROLES = frozenset({"input", "result", "manifest", "publication_wal", "activation_journal",
                    "router", "recovery_plan", "source_capture", "scope_descriptor"})
_BASE = frozenset({"publication_scope_id", "input_index", "post_id", "base_attempt_run_id",
    "export_run_id", "publication_decision_id", "commit_sha256", "result_sha256",
    "stable_result_sha256", "public_projection_sha256", "contract_input_fingerprint",
    "input_count", "input_order_sha256", "input_raw_sha256"})
_SELECTORS = frozenset({"input_format", "result_pointer", "router_pointer", "recovery_plan_pointer",
                       "publication_decision_id", "activation_event_sha256"})
_TOP = frozenset({"schema_version", "execution_mode", "data_kind", "source_refs", "artifacts", "selectors", "request",
    "base", "review", "activation", "source_binding", "endpoint", "payload", "policy", "requests",
    "job_id", "output_dir", "guard_status", "publication_authority", "public_apply",
    "central_db_write", "actual_quality_evaluated", "plan_sha256", "binding_sha256"})
_POLICY = frozenset({"max_calls", "max_elapsed_ms", "request_timeout_ms", "max_response_bytes",
                     "max_total_response_bytes"})
_KINDS = frozenset({"SOURCE_BACKED", "TEST_SYNTHETIC", "UNKNOWN"})
_TOKEN = object()


class RecoveryProviderContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RecoveryProviderContractError(code)


def _exact(value: Any, keys, code: str) -> dict:
    _require(type(value) is dict and set(value) == set(keys), code)
    return value


def _same(left: Any, right: Any, code: str) -> None:
    _require(legacy._canonical_bytes(left) == legacy._canonical_bytes(right), code)


def _sha(value: Any) -> str:
    return legacy.canonical_sha256(value)


def _refs(value: Any) -> dict:
    _require(type(value) is dict and set(value) == _ROLES, "SOURCE_NOT_CAPTURED" if
             type(value) is dict and "source_capture" not in value else "SOURCE_REFS_INVALID")
    paths, total = set(), 0
    for role, ref in value.items():
        _exact(ref, {"path", "sha256", "bytes"}, "SOURCE_REF_FIELDS")
        path = legacy._absolute_path(ref["path"])
        normalized = os.path.normcase(os.path.abspath(path))
        _require(normalized not in paths, "SOURCE_PATH_DUPLICATE")
        paths.add(normalized)
        legacy._hex(ref["sha256"], role)
        total += legacy._integer(ref["bytes"], role, 1, legacy.MAX_FILE_BYTES)
    _require(total <= legacy.MAX_TOTAL_BYTES, "SOURCE_TOTAL_BYTES_LIMIT")
    return deepcopy(value)


def _policy(value: Any) -> dict:
    _exact(value, _POLICY, "POLICY_FIELDS")
    checked = RecoveryTransportPolicy(**value)
    _require(checked.max_calls in (0, 1), "SINGLE_SEARCH_NO_RETRY")
    _require(checked.request_timeout_ms <= checked.max_elapsed_ms, "REQUEST_EXCEEDS_DEADLINE")
    return asdict(checked)


def _requests(endpoint: str, payload: dict) -> list[dict]:
    raw = _payload("MCP_SEARCH", payload)
    return [{"request_id": "targeted-search-1", "kind": "MCP_SEARCH",
             "body_sha256": hashlib.sha256(raw).hexdigest(),
             "endpoint_sha256": hashlib.sha256(endpoint.encode("utf-8")).hexdigest()}]


def _source_digest(plan: dict) -> str:
    return _sha({"source_refs": {role: {key: ref[key] for key in ("sha256", "bytes")}
                 for role, ref in plan["source_refs"].items()}, "source_binding": plan["source_binding"]})


def _config_digest(plan: dict) -> str:
    return _sha({"schema_version": SCHEMA, "execution_mode": MODE, "endpoint": plan["endpoint"],
                 "payload": plan["payload"], "requests": plan["requests"]})


def _job(plan: dict) -> str:
    return _sha({"base_sha256": _sha(plan["base"]), "source_sha256": _source_digest(plan),
                 "config_sha256": _config_digest(plan), "policy_sha256": _sha(plan["policy"])})


def _material(plan: dict) -> dict:
    result = {key: deepcopy(value) for key, value in plan.items()
              if key not in {"plan_sha256", "binding_sha256", "output_dir"}}
    result["source_refs"] = {role: {key: ref[key] for key in ("sha256", "bytes")}
                             for role, ref in result["source_refs"].items()}
    result["artifacts"] = deepcopy(result["source_refs"])
    return result


def _seal(plan: dict) -> dict:
    result = deepcopy(plan)
    result["job_id"] = _job(result)
    result["plan_sha256"] = _sha(_material(result))
    result["binding_sha256"] = _sha({k: v for k, v in result.items() if k != "binding_sha256"})
    return result


def validate_recovery_provider_plan(plan: Any) -> dict:
    """저장 계획의 구조 검산. 원본 결속에는 bind_recovery_provider_plan이 필요하다."""
    _exact(plan, _TOP, "PLAN_FIELDS")
    _require(len(legacy._canonical_bytes(plan)) <= MAX_PLAN_BYTES, "PLAN_BYTE_LIMIT")
    _require(plan["schema_version"] == SCHEMA and plan["execution_mode"] == MODE, "PLAN_SCHEMA_MODE")
    _require(plan["data_kind"] in _KINDS, "DATA_KIND")
    _require(plan["guard_status"] == "GUARD_NOT_EVALUATED", "GUARD_NOT_EVALUATED_REQUIRED")
    for key in ("publication_authority", "public_apply", "central_db_write", "actual_quality_evaluated"):
        _require(plan[key] is False, "NO_PUBLIC_OR_QUALITY_AUTHORITY")
    _refs(plan["source_refs"])
    _same(plan["artifacts"], plan["source_refs"], "ARTIFACT_ALIAS_MISMATCH")
    selectors = _exact(plan["selectors"], _SELECTORS, "SELECTOR_FIELDS")
    _require(selectors["input_format"] in {"JSON_ARRAY_V1", "JSONL_POST_COMMENT_V1"}, "INPUT_FORMAT")
    for key in ("result_pointer", "router_pointer", "recovery_plan_pointer"):
        _require(type(selectors[key]) is str and (not selectors[key] or selectors[key].startswith("/")), "SELECTOR_POINTER")
    for key in ("publication_decision_id", "activation_event_sha256"):
        legacy._hex(selectors[key], key)
    base = _exact(plan["base"], _BASE, "BASE_FIELDS")
    legacy._post(base["post_id"])
    legacy._integer(base["input_count"], "input count", 1)
    legacy._integer(base["input_index"], "input index", 1, base["input_count"])
    for key in ("export_run_id", "base_attempt_run_id"):
        legacy._text(base[key], key)
    for key in _BASE - {"post_id", "input_index", "input_count", "export_run_id", "base_attempt_run_id"}:
        legacy._hex(base[key], key)
    _same(selectors["publication_decision_id"], base["publication_decision_id"], "BASE_DECISION_MISMATCH")
    legacy._validate_source(plan["source_binding"])
    review = _exact(plan["review"], {"router_receipt_sha256", "recovery_plan_receipt_sha256", "query_purposes", "max_queries"}, "REVIEW_FIELDS")
    for key in ("router_receipt_sha256", "recovery_plan_receipt_sha256"):
        legacy._hex(review[key], key)
    _require(type(review["query_purposes"]) is list and all(type(x) is str for x in review["query_purposes"]), "QUERY_PURPOSES")
    legacy._integer(review["max_queries"], "max queries", 1)
    activation = _exact(plan["activation"], {"event_sha256", "sequence", "proposal_id", "proposal_sha256", "mode", "capability_scope"}, "ACTIVATION_FIELDS")
    for key in ("event_sha256", "proposal_sha256", "proposal_id"):
        legacy._hex(activation[key], key)
    legacy._integer(activation["sequence"], "activation sequence", 1)
    _same(activation["event_sha256"], selectors["activation_event_sha256"], "ACTIVATION_SELECTOR_MISMATCH")
    _require(activation["mode"] == "AUDIT_ONLY" and activation["capability_scope"] == "proposal_authorization_only", "AUDIT_ONLY_REQUIRED")
    _same(plan["endpoint"], _endpoint(plan["endpoint"]), "ENDPOINT_NOT_CANONICAL")
    _same(plan["requests"], _requests(plan["endpoint"], plan["payload"]), "REQUEST_DIGEST_MISMATCH")
    _same(plan["request"], {**plan["requests"][0], "endpoint": plan["endpoint"],
                           "payload": plan["payload"]}, "REQUEST_ALIAS_MISMATCH")
    _same(plan["payload"]["query"], plan["source_binding"]["query"], "QUERY_SOURCE_MISMATCH")
    _require(plan["payload"]["purpose"] in review["query_purposes"], "QUERY_PURPOSE_NOT_ALLOWED")
    _policy(plan["policy"])
    legacy._absolute_path(plan["output_dir"])
    _same(plan, _seal(plan), "PLAN_SEAL_MISMATCH")
    return deepcopy(plan)


def provider_journal_arguments(plan: Any) -> dict:
    plan = validate_recovery_provider_plan(plan)
    base = plan["base"]
    binding = {"plan_sha256": plan["plan_sha256"], "base_sha256": _sha(base),
               "source_sha256": _source_digest(plan), "config_sha256": _config_digest(plan),
               "policy_sha256": _sha(plan["policy"]),
               **{key: base[key] for key in ("publication_scope_id", "input_index", "post_id", "base_attempt_run_id")}}
    return {"binding": binding, "policy": deepcopy(plan["policy"]), "requests": deepcopy(plan["requests"])}


def _source_bound(source: dict, capture: Any, result: dict, event: dict, base: dict) -> str:
    _exact(capture, {"schema_version", "data_kind", "input_raw_sha256", "input_index", "post_id", "source_locator", "item"}, "SOURCE_CAPTURE_FIELDS")
    _require(capture["schema_version"] == SOURCE_SCHEMA and capture["data_kind"] in _KINDS, "SOURCE_CAPTURE_SCHEMA")
    for key in ("input_raw_sha256", "input_index", "post_id"):
        _same(capture[key], base[key], "SOURCE_PARENT_MISMATCH")
    _same(capture["source_locator"], source["source_locator"], "SOURCE_LOCATOR_MISMATCH")
    item = capture["item"]
    _require(type(item) is dict, "SOURCE_ITEM_OBJECT")
    _same(_sha(item), source["source_item_sha256"], "SOURCE_ITEM_CANONICAL_SHA_MISMATCH")
    catalog = result["analysis_result"]["identity"].get("image_evidence_catalog")
    _require(type(catalog) is list and sum(legacy._canonical_bytes(x) == legacy._canonical_bytes(item)
                                         for x in catalog) == 1, "SOURCE_ITEM_NOT_UNIQUE_IN_RESULT")
    proposals = [p.to_dict() for p in extract_direct_ocr_review_proposals(result)]
    proposal = event["proposal"]
    _require(any(legacy._canonical_bytes(p) == legacy._canonical_bytes(proposal) for p in proposals), "PROPOSAL_NOT_BOUND")
    _require(proposal["source_payload_sha256"] is not None, "SOURCE_NOT_CAPTURED")
    _same(proposal["source_payload_sha256"], source["source_item_sha256"], "PROPOSAL_SOURCE_SHA_MISMATCH")
    for pkey, skey in (("source_locator", "source_locator"), ("relation_role", "relation_role"), ("raw_candidate_title", "query")):
        _same(proposal[pkey], source[skey], "PROPOSAL_SOURCE_MISMATCH")
    field = legacy._pointer(item, source["field_pointer"])
    _require(type(field) is str, "SOURCE_FIELD_TEXT")
    raw = field.encode("utf-8")
    _require(source["span_end"] <= len(raw), "SOURCE_SPAN_OUTSIDE")
    try:
        query = raw[source["span_start"]:source["span_end"]].decode("utf-8")
    except UnicodeError as exc:
        raise RecoveryProviderContractError("SOURCE_SPAN_UTF8") from exc
    _same(query, source["query"], "SOURCE_SPAN_QUERY_MISMATCH")
    return capture["data_kind"]


def build_recovery_provider_plan(*, source_refs: dict, source_bytes: dict, input_format: str,
    result_pointer: str, router_pointer: str, recovery_plan_pointer: str,
    publication_decision_id: str, activation_event_sha256: str, source_binding: dict,
    endpoint: str, payload: dict, policy: dict, output_dir: str, hmac_key: bytes) -> dict:
    """명시 bytes만 검산한다. 파일·key·원장·provider를 생성하지 않는다."""
    refs = _refs(source_refs)
    _require(type(source_bytes) is dict and set(source_bytes) == _ROLES, "SOURCE_BYTES_FIELDS")
    for role, ref in refs.items():
        raw = source_bytes[role]
        _require(type(raw) is bytes and len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], "SOURCE_RAW_SHA_OR_BYTES_MISMATCH")
    legacy._validate_source(source_binding)
    posts, input_bindings = legacy._input_snapshot(source_bytes["input"], input_format)
    wal_result, receipt = legacy._publication_event(source_bytes["publication_wal"], publication_decision_id, posts)
    result_document = legacy._load_json(source_bytes["result"])
    _require(type(result_document) is list and len(result_document) == len(posts), "FINAL_RESULT_FULL_INPUT_REQUIRED")
    for row, post in zip(result_document, posts):
        _require(type(row) is dict, "FINAL_RESULT_ROW_OBJECT")
        _same(row.get("post_id"), post["post_id"], "FINAL_RESULT_TYPED_INPUT_ORDER")
        validate_main_input_projection(post, row)
    wal_events = legacy._json_lines(source_bytes["publication_wal"], "publication WAL")
    _require(len(wal_events) == len(posts), "FINAL_WAL_FULL_INPUT_REQUIRED")
    for event_row in wal_events:
        # _publication_event already verified every full commit and unique index.
        index = event_row["receipt"]["input_index"]
        _same(result_document[index - 1], event_row["result"], "FINAL_RESULT_WAL_ROW_MISMATCH")
    result = legacy._pointer(result_document, result_pointer)
    _same(result, wal_result, "ORIGINAL_RESULT_WAL_MISMATCH")
    _require(receipt.outcome == "HOLD" and receipt.publish_allowed is False, "ORIGINAL_HOLD_REQUIRED")
    _same(input_bindings["post_bindings"][receipt.input_index - 1]["result_comments"], result.get("comments"), "ORIGINAL_COMMENTS_MISMATCH")
    manifest = legacy._load_json(source_bytes["manifest"])
    _require(type(manifest) is dict and manifest.get("terminal_artifacts_finalized") is True, "FINALIZED_MANIFEST_REQUIRED")
    for key in ("completed_count", "flushed_count"):
        _require(type(manifest.get(key)) is int and manifest[key] == len(posts), "INCOMPLETE_MANIFEST")
    _require(type(manifest.get("pending_count")) is int and manifest["pending_count"] == 0
             and manifest.get("partial_flush_gap") is False, "INCOMPLETE_MANIFEST")
    legacy._text(manifest.get("run_id"), "export run id")
    _same(manifest.get("publication_input_snapshot_sha256"), refs["input"]["sha256"], "MANIFEST_INPUT_SNAPSHOT_MISMATCH")
    _same(manifest.get("publication_scope_id"), receipt.publication_scope_id, "MANIFEST_SCOPE_MISMATCH")
    _same(str(legacy._absolute_path(manifest.get("output_file"))), str(legacy._absolute_path(refs["result"]["path"])), "MANIFEST_OUTPUT_MISMATCH")
    descriptor = PublicationScopeDescriptor.from_dict(legacy._load_json(source_bytes["scope_descriptor"]))
    _same(descriptor.publication_scope_id, receipt.publication_scope_id, "SCOPE_DESCRIPTOR_SCOPE_MISMATCH")
    _same(descriptor.input_file_sha256, refs["input"]["sha256"], "SCOPE_INPUT_SHA_MISMATCH")
    _same(list(descriptor.post_ids), [p["post_id"] for p in posts], "SCOPE_TYPED_INPUT_ORDER_MISMATCH")
    _same(manifest.get("publication_scope_descriptor_sha256"), descriptor.descriptor_sha256, "MANIFEST_SCOPE_DESCRIPTOR_MISMATCH")
    base = {"publication_scope_id": receipt.publication_scope_id, "input_index": receipt.input_index,
        "post_id": receipt.post_id, "base_attempt_run_id": receipt.attempt_run_id,
        "export_run_id": manifest["run_id"], "publication_decision_id": receipt.decision_id,
        "commit_sha256": receipt.commit_sha256, "result_sha256": receipt.result_sha256,
        "stable_result_sha256": receipt.stable_result_sha256, "public_projection_sha256": receipt.public_projection_sha256,
        "contract_input_fingerprint": receipt.contract_input_fingerprint,
        "input_count": len(posts), "input_order_sha256": _sha([p["post_id"] for p in posts]), "input_raw_sha256": refs["input"]["sha256"]}
    router = legacy._pointer(legacy._load_json(source_bytes["router"]), router_pointer)
    recovery = legacy._pointer(legacy._load_json(source_bytes["recovery_plan"]), recovery_plan_pointer)
    for value, validator in ((router, validate_semantic_review_router_receipt), (recovery, validate_semantic_recovery_plan_receipt)):
        _same(value.get("post_id"), receipt.post_id, "REVIEW_POST_TYPE_MISMATCH")
        validator(value, result=result, expected_publication_receipt=receipt,
            expected_scope_id=receipt.publication_scope_id, expected_input_index=receipt.input_index,
            expected_post_id=receipt.post_id, expected_attempt_run_id=receipt.attempt_run_id)
    _require(router["state"] == "REVIEW_REQUIRED" and recovery["plan"]["state"] == "HOLD", "PROPOSAL_NOT_ELIGIBLE")
    events = legacy.read_recovery_activation_snapshot(source_bytes["activation_journal"],
        expected_sha256=refs["activation_journal"]["sha256"], hmac_key=hmac_key, expected_scope_id=receipt.publication_scope_id)
    chosen = [event for event in events if event["event_sha256"] == activation_event_sha256]
    _require(len(chosen) == 1, "ACTIVATION_NOT_FOUND")
    event = chosen[0]
    event_base = {"publication_scope_id": receipt.publication_scope_id, "input_index": receipt.input_index,
        "post_id": receipt.post_id, "base_decision_id": receipt.decision_id, "base_commit_sha256": receipt.commit_sha256,
        "base_result_sha256": receipt.result_sha256, "base_stable_result_sha256": receipt.stable_result_sha256,
        "base_public_projection_sha256": receipt.public_projection_sha256,
        "base_contract_input_fingerprint": receipt.contract_input_fingerprint}
    for key, value in event_base.items():
        _same(event[key], value, "ACTIVATION_BASE_MISMATCH")
    kind = _source_bound(source_binding, legacy._load_json(source_bytes["source_capture"]), result, event, base)
    if "data_kind" in manifest:
        _same(manifest["data_kind"], kind, "DECLARED_DATA_KIND_MISMATCH")
    query = recovery["plan"]["query_plan"]
    _require(query["query_execution_allowed"] is True and type(query["max_queries"]) is int and query["max_queries"] >= 1, "SEMANTIC_QUERY_NOT_ALLOWED")
    endpoint = _endpoint(endpoint)
    requests = _requests(endpoint, payload)
    plan = {"schema_version": SCHEMA, "execution_mode": MODE, "data_kind": kind,
        "source_refs": refs, "artifacts": deepcopy(refs), "selectors": {"input_format": input_format, "result_pointer": result_pointer,
            "router_pointer": router_pointer, "recovery_plan_pointer": recovery_plan_pointer,
            "publication_decision_id": publication_decision_id, "activation_event_sha256": activation_event_sha256},
        "base": base, "review": {"router_receipt_sha256": router["receipt_sha256"],
            "recovery_plan_receipt_sha256": recovery["receipt_sha256"], "query_purposes": query["purposes"], "max_queries": query["max_queries"]},
        "activation": {"event_sha256": event["event_sha256"], "sequence": event["sequence"],
            "proposal_id": event["proposal_id"], "proposal_sha256": _sha(event["proposal"]),
            "mode": event["mode"], "capability_scope": event["capability_scope"]},
        "source_binding": deepcopy(source_binding), "endpoint": endpoint, "payload": deepcopy(payload),
        "policy": _policy(policy), "requests": requests,
        "request": {**requests[0], "endpoint": endpoint, "payload": deepcopy(payload)}, "output_dir": output_dir,
        "guard_status": "GUARD_NOT_EVALUATED", "publication_authority": False, "public_apply": False,
        "central_db_write": False, "actual_quality_evaluated": False}
    return validate_recovery_provider_plan(_seal(plan))


@dataclass(frozen=True, init=False)
class BoundRecoveryProviderPlan:
    _serialized: bytes
    _posts: bytes
    _inputs: bytes
    _identities: tuple

    def __init__(self, token=None, *, plan=None, posts=None, inputs=None, identities=()):
        _require(token is _TOKEN, "VERIFIED_FACTORY_REQUIRED")
        object.__setattr__(self, "_serialized", legacy._canonical_bytes(plan))
        object.__setattr__(self, "_posts", legacy._canonical_bytes(posts))
        object.__setattr__(self, "_inputs", legacy._canonical_bytes(inputs))
        object.__setattr__(self, "_identities", tuple(identities))

    @property
    def plan(self): return legacy._load_json(self._serialized)
    def to_dict(self): return self.plan
    @property
    def base(self): return self.plan["base"]
    @property
    def binding(self): return provider_journal_arguments(self.plan)["binding"]
    @property
    def policy(self): return self.plan["policy"]
    @property
    def requests(self): return self.plan["requests"]
    @property
    def endpoints(self): return {"MCP_SEARCH": self.plan["endpoint"]}
    @property
    def payload(self): return self.plan["payload"]
    @property
    def output_dir(self): return Path(self.plan["output_dir"])
    @property
    def journal_path(self): return self.output_dir / "provider_journal.jsonl"
    @property
    def job_id(self): return self.plan["job_id"]
    @property
    def data_kind(self): return self.plan["data_kind"]
    @property
    def input_rows(self): return legacy._load_json(self._posts)
    @property
    def input_bindings(self): return legacy._load_json(self._inputs)

    def assert_output_path(self, path: str | Path) -> Path:
        output = legacy._safe_path(self.output_dir)
        target = legacy._safe_path(Path(path))
        _require(target != output and output in target.parents, "OUTPUT_OUTSIDE_NAMESPACE")
        _require(not output.exists() or output.is_dir(), "OUTPUT_NOT_DIRECTORY")
        for ref in self.plan["source_refs"].values():
            source = legacy._safe_path(Path(ref["path"]), file_required=True)
            _require(source != target and source != output and output not in source.parents and source not in output.parents, "OUTPUT_OVERLAPS_SOURCE")
            if target.exists():
                _require(target.is_file() and target.stat().st_nlink == 1 and not os.path.samefile(target, source), "OUTPUT_ALIASES_SOURCE")
        return target

    def verify_protected_sources(self) -> bool:
        expected = dict(self._identities)
        for role, ref in self.plan["source_refs"].items():
            _, identity = legacy._read_protected(ref)
            _require(identity == expected[role], "SOURCE_FILE_IDENTITY_DRIFT")
        self.assert_output_path(self.journal_path)
        return True

    def protected_sources(self) -> list[dict]:
        self.verify_protected_sources()
        return [{"role": role, **ref} for role, ref in self.plan["source_refs"].items()]


def bind_recovery_provider_plan(plan: Any, *, hmac_key: bytes) -> BoundRecoveryProviderPlan:
    checked = validate_recovery_provider_plan(plan)
    raw, identities, seen = {}, {}, set()
    for role, ref in checked["source_refs"].items():
        raw[role], identities[role] = legacy._read_protected(ref)
        _require(identities[role] not in seen, "SOURCE_FILE_ALIAS")
        seen.add(identities[role])
    rebuilt = build_recovery_provider_plan(source_refs=checked["source_refs"], source_bytes=raw,
        **checked["selectors"], source_binding=checked["source_binding"], endpoint=checked["endpoint"],
        payload=checked["payload"], policy=checked["policy"], output_dir=checked["output_dir"], hmac_key=hmac_key)
    _same(rebuilt, checked, "PLAN_ORIGINAL_REBUILD_MISMATCH")
    posts, inputs = legacy._input_snapshot(raw["input"], checked["selectors"]["input_format"])
    bound = BoundRecoveryProviderPlan(_TOKEN, plan=checked, posts=posts, inputs=inputs, identities=tuple(identities.items()))
    bound.verify_protected_sources()
    return bound
