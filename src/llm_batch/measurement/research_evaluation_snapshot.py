"""저장된 실행·원문을 읽기 전용 평가 snapshot으로 묶는다.

순수 builder는 파일을 읽지 않으며, exporter가 명시한 원본 해시와
새 출력 경계를 검증한다. 모델 호출과 공개 판정 권위는 없다.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid


REQUEST_SCHEMA = "research_snapshot_request_v1"
SNAPSHOT_SCHEMA = "research_evaluation_snapshot_v1"
REFERENCE_SCHEMA = "research_snapshot_reference_v1"
POLICY_VERSION = "saved_artifact_readback_v1"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_FIELDS = (
    "post_id", "title", "content", "comments", "content_blocks", "comment_metadata",
    "comment_context_lines", "comment_dialogue_context_lines", "image_urls",
    "image_count", "url", "gallery_id", "created_at", "author", "post_author",
)
MANIFEST_FIELDS = (
    "run_id", "output_file", "input_file", "input_post_count", "completed_count",
    "flushed_count", "failed_count", "pending_count", "status", "large_run_complete",
    "execution_mode", "publication_execution_mode", "execution_config",
    "publication_input_snapshot_sha256", "publication_scope_descriptor", "publication_scope_id",
    "publication_scope_descriptor_sha256", "publication_decision_environment_sha256",
    "source_sha256", "runtime_source_sha256", "config_sha256",
    "publication_config_sha256", "publication_scope_config_sha256",
    "publication_scope_config", "publication_release_fingerprint",
    "publication_release_fingerprint_source", "publication_slang_db_input_sha256",
    "decision_call_measurement", "decision_call_ledger_summary",
)
REFERENCE_KINDS = frozenset({"MODEL_REFERENCE", "GOLD_LITE", "HUMAN_GOLD", "UNJUDGED"})
DATA_KINDS = frozenset({"SAVED_ARTIFACT", "SYNTHETIC_FIXTURE"})


class SnapshotError(ValueError):
    """Malformed request, changed source or unsafe output destination."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def semantic_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def present(mapping: dict, key: str) -> dict:
    """Keep missing, explicit null, false and zero different."""
    return {"present": key in mapping, "value": deepcopy(mapping.get(key))}


def _mapping(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise SnapshotError(f"{field}: expected object")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SnapshotError(f"{field}: expected non-empty text")
    return value


def _integer(value: Any, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _post_key(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if type(value) is int and value >= 0:
        return str(value)
    return None


def _rows(value: Any, field: str) -> list[dict]:
    if isinstance(value, dict):
        keys = [key for key in ("posts", "results") if key in value]
        if len(keys) != 1:
            raise SnapshotError(f"{field}: expected array or exactly one posts/results array")
        value = value[keys[0]]
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise SnapshotError(f"{field}: expected array of objects")
    return value


def _path_key(path: str, base: str | None = None) -> str:
    item = Path(path)
    if not item.is_absolute():
        item = Path(base or ".") / item
    return os.path.normcase(os.path.abspath(item))


def _issue(issues: list, dataset_id: str, code: str, *, severity="LIMIT",
           ordinal: int | None = None, details: Any = None) -> None:
    value = {"dataset_id": dataset_id, "code": code, "severity": severity}
    if ordinal is not None:
        value["result_ordinal"] = ordinal
    if details is not None:
        value["details"] = details
    issues.append(value)


def _source_ref(value: Any, field: str) -> dict:
    ref = _mapping(value, field)
    _text(ref.get("path"), f"{field}.path")
    if not Path(ref["path"]).is_absolute():
        raise SnapshotError(f"{field}.path: absolute path required in pure builder")
    if not isinstance(ref.get("sha256"), str) or not SHA256_RE.fullmatch(ref["sha256"]):
        raise SnapshotError(f"{field}.sha256: required lowercase byte SHA256")
    if not _integer(ref.get("bytes")):
        raise SnapshotError(f"{field}.bytes: expected nonnegative integer")
    return deepcopy(ref)


def _reference_map(dataset: dict, run_id: Any, issues: list) -> tuple[dict, str]:
    value = dataset.get("reference")
    if value is None:
        return {}, "REFERENCE_NOT_BOUND"
    reference = _mapping(value, "reference")
    did = dataset["dataset_id"]
    valid = True
    expected = {
        "schema_version": REFERENCE_SCHEMA,
        "result_sha256": dataset["source_refs"]["result"]["sha256"],
        "run_id": run_id,
    }
    for key, expected_value in expected.items():
        if reference.get(key) != expected_value or (key == "run_id" and not run_id):
            _issue(issues, did, "REFERENCE_BINDING_MISMATCH", severity="ERROR",
                   details={"field": key})
            valid = False
    mapped = {}
    for number, row in enumerate(_rows(reference.get("rows"), "reference.rows"), 1):
        index = row.get("input_index")
        post = _post_key(row.get("post_id"))
        kind = row.get("reference_kind")
        if not _integer(index, 1) or post is None or kind not in REFERENCE_KINDS:
            _issue(issues, did, "REFERENCE_ROW_INVALID", severity="ERROR",
                   details={"reference_ordinal": number})
            valid = False
            continue
        coordinate = (index, post)
        if coordinate in mapped:
            _issue(issues, did, "DUPLICATE_REFERENCE_COORDINATE", severity="ERROR",
                   details={"input_index": index, "post_id": post})
            valid = False
        mapped[coordinate] = deepcopy(row)
    return mapped, "BOUND_CALLER_SUPPLIED" if valid else "INVALID_BINDING"


def build_evaluation_snapshot(datasets: list[dict]) -> dict:
    """Build deterministic content from parsed, explicitly bound datasets.

    This function verifies internal bindings, not file bytes. Only the IO wrapper
    may attest byte readback. Candidate/publication payloads are retained verbatim;
    this module never validates or upgrades their authority.
    """
    if not isinstance(datasets, list) or not datasets:
        raise SnapshotError("datasets: at least one explicitly named dataset required")
    output_rows, output_datasets, issues = [], [], []
    seen_ids, artifact_owners = set(), {}
    unique_posts, unique_material = defaultdict(set), defaultdict(set)
    post_fingerprints = defaultdict(set)
    for dataset in datasets:
        _mapping(dataset, "dataset")
        did = _text(dataset.get("dataset_id"), "dataset_id")
        namespace = _text(dataset.get("sample_namespace"), "sample_namespace")
        if did in seen_ids:
            raise SnapshotError(f"duplicate dataset_id: {did}")
        seen_ids.add(did)
        data_kind = dataset.get("data_kind")
        if data_kind not in DATA_KINDS:
            raise SnapshotError(f"{did}: explicit data_kind required")
        refs = _mapping(dataset.get("source_refs"), "source_refs")
        for kind in ("result", "manifest"):
            _source_ref(refs.get(kind), f"{did}.{kind}")
        for kind in ("input", "reference"):
            if kind in dataset:
                if dataset[kind] is None:
                    raise SnapshotError(f"{did}.{kind}: omit absent artifacts; null is not an artifact")
                _source_ref(refs.get(kind), f"{did}.{kind}")
            elif kind in refs:
                raise SnapshotError(f"{did}.{kind}: source ref without payload")
        result = _rows(dataset.get("result"), f"{did}.result")
        manifest = _mapping(dataset.get("manifest"), f"{did}.manifest")
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            _issue(issues, did, "MANIFEST_RUN_ID_MISSING")
        artifact_id = refs["result"]["sha256"]
        if artifact_id in artifact_owners:
            _issue(issues, did, "DUPLICATE_RESULT_ARTIFACT", severity="ERROR",
                   details={"other_dataset_id": artifact_owners[artifact_id]})
        artifact_owners[artifact_id] = did
        declared_output = manifest.get("output_file")
        if isinstance(declared_output, str) and declared_output:
            if _path_key(declared_output, str(Path(refs["manifest"]["path"]).parent)) != _path_key(refs["result"]["path"]):
                _issue(issues, did, "MANIFEST_OUTPUT_PATH_MISMATCH", severity="ERROR")
        else:
            _issue(issues, did, "MANIFEST_OUTPUT_PATH_MISSING")
        inputs = _rows(dataset["input"], f"{did}.input") if "input" in dataset else None
        if inputs is None:
            _issue(issues, did, "FIXED_INPUT_NOT_BOUND")
        else:
            expected_input_hash = manifest.get("publication_input_snapshot_sha256")
            if expected_input_hash is not None:
                if expected_input_hash != refs["input"]["sha256"]:
                    _issue(issues, did, "MANIFEST_INPUT_SHA256_MISMATCH", severity="ERROR")
            else:
                _issue(issues, did, "MANIFEST_INPUT_SHA256_MISSING_CALLER_BINDING_ONLY")
            declared_input = manifest.get("input_file")
            if isinstance(declared_input, str) and declared_input:
                if _path_key(declared_input, str(Path(refs["manifest"]["path"]).parent)) != _path_key(refs["input"]["path"]):
                    _issue(issues, did, "MANIFEST_INPUT_PATH_MISMATCH", severity="ERROR")
            else:
                _issue(issues, did, "MANIFEST_INPUT_PATH_MISSING_CALLER_BINDING_ONLY")
        input_count = manifest.get("input_post_count")
        if not _integer(input_count):
            _issue(issues, did, "INPUT_DENOMINATOR_UNKNOWN")
            input_count = len(inputs) if inputs is not None else None
        if inputs is not None and input_count != len(inputs):
            _issue(issues, did, "INPUT_COUNT_MISMATCH", severity="ERROR")
        if inputs is not None:
            input_posts = [_post_key(row.get("post_id")) for row in inputs]
            if None in input_posts:
                _issue(issues, did, "FIXED_INPUT_POST_ID_INVALID", severity="ERROR")
            if len(set(input_posts)) != len(input_posts):
                _issue(issues, did, "DUPLICATE_FIXED_INPUT_POST_ID", severity="ERROR")
        for field in ("flushed_count", "completed_count", "failed_count", "pending_count"):
            if field in manifest and not _integer(manifest[field]):
                _issue(issues, did, "MANIFEST_COUNT_INVALID", severity="ERROR", details={"field": field})
        if _integer(manifest.get("flushed_count")) and manifest["flushed_count"] != len(result):
            _issue(issues, did, "FLUSHED_COUNT_MISMATCH", severity="ERROR")
        if input_count is not None and len(result) > input_count:
            _issue(issues, did, "RESULT_EXCEEDS_INPUT_COUNT", severity="ERROR")
        reference_rows, reference_status = _reference_map(dataset, run_id, issues)
        used_references, seen_indexes, seen_posts, seen_attempts = set(), set(), set(), set()
        prior_index = 0
        for ordinal, row in enumerate(result, 1):
            post_id = row.get("post_id")
            post = _post_key(post_id)
            if post is None:
                _issue(issues, did, "POST_ID_INVALID", severity="ERROR", ordinal=ordinal)
            elif post in seen_posts:
                _issue(issues, did, "DUPLICATE_POST_ID", severity="ERROR", ordinal=ordinal)
            seen_posts.add(post)
            run_meta = row.get("run_meta")
            if not isinstance(run_meta, dict):
                run_meta = {}
            receipt = run_meta.get("decision_call_attempt_receipt")
            receipt = receipt if isinstance(receipt, dict) else {}
            coordinate = receipt.get("row")
            coordinate = coordinate if isinstance(coordinate, dict) else {}
            scope = manifest.get("publication_scope_id")
            if scope is None:
                _issue(issues, did, "MANIFEST_PUBLICATION_SCOPE_MISSING", ordinal=ordinal)
            elif not isinstance(scope, str) or not SHA256_RE.fullmatch(scope):
                _issue(issues, did, "MANIFEST_PUBLICATION_SCOPE_INVALID", severity="ERROR", ordinal=ordinal)
            ledger = run_meta.get("decision_call_ledger")
            ledger = ledger if isinstance(ledger, dict) else {}
            ledger_row = ledger.get("row")
            ledger_row = ledger_row if isinstance(ledger_row, dict) else {}
            # Each known carrier must agree with the source independently. A
            # missing receipt field must not hide a contradictory ledger field.
            if "attempt_run_id" in ledger_row and run_id is not None and ledger_row["attempt_run_id"] != run_id:
                _issue(issues, did, "LEDGER_RUN_ID_MISMATCH", severity="ERROR", ordinal=ordinal)
            if "post_id" in ledger_row and _post_key(ledger_row["post_id"]) != post:
                _issue(issues, did, "LEDGER_POST_ID_MISMATCH", severity="ERROR", ordinal=ordinal)
            if "input_index" in ledger_row:
                ledger_index = ledger_row["input_index"]
                if not _integer(ledger_index, 1):
                    _issue(issues, did, "LEDGER_INPUT_INDEX_INVALID", severity="ERROR", ordinal=ordinal)
                elif input_count is not None and ledger_index > input_count:
                    _issue(issues, did, "LEDGER_INPUT_INDEX_OUT_OF_RANGE", severity="ERROR", ordinal=ordinal)
                elif inputs is not None and ledger_index <= len(inputs) and _post_key(inputs[ledger_index - 1].get("post_id")) != post:
                    _issue(issues, did, "LEDGER_FIXED_INPUT_POST_ID_MISMATCH", severity="ERROR", ordinal=ordinal)
            for name, carrier in (("attempt_receipt", coordinate), ("ledger", ledger), ("ledger.row", ledger_row)):
                if "publication_scope_id" in carrier and scope is not None and carrier["publication_scope_id"] != scope:
                    _issue(issues, did, "ROW_PUBLICATION_SCOPE_MISMATCH", severity="ERROR",
                           ordinal=ordinal, details={"field": name})
            if "publication_scope_id" not in coordinate:
                _issue(issues, did, "ROW_PUBLICATION_SCOPE_MISSING", ordinal=ordinal)
            for field in ("input_index", "post_id", "attempt_run_id", "row_attempt_id", "publication_scope_id"):
                if field in coordinate and field in ledger_row:
                    left, right = coordinate[field], ledger_row[field]
                    if field == "post_id":
                        left, right = _post_key(left), _post_key(right)
                    if left != right or (field == "input_index" and type(coordinate[field]) is not type(ledger_row[field])):
                        _issue(issues, did, "LEDGER_RECEIPT_COORDINATE_MISMATCH", severity="ERROR",
                               ordinal=ordinal, details={"field": field})
            for name, declared_run in (("run_meta.run_id", run_meta.get("run_id")),
                                       ("receipt.attempt_run_id", coordinate.get("attempt_run_id"))):
                if declared_run is None:
                    _issue(issues, did, "ROW_RUN_ID_MISSING", ordinal=ordinal, details={"field": name})
                elif declared_run != run_id:
                    _issue(issues, did, "ROW_RUN_ID_MISMATCH", severity="ERROR",
                           ordinal=ordinal, details={"field": name})
            if not coordinate or "input_index" not in coordinate:
                _issue(issues, did, "ROW_ATTEMPT_COORDINATE_MISSING", ordinal=ordinal)
            if "post_id" in coordinate and _post_key(coordinate["post_id"]) != post:
                _issue(issues, did, "RECEIPT_POST_ID_MISMATCH", severity="ERROR", ordinal=ordinal)
            if "post_id" not in coordinate:
                _issue(issues, did, "RECEIPT_POST_ID_MISSING", ordinal=ordinal)
            index = coordinate.get("input_index")
            if index is not None and not _integer(index, 1):
                _issue(issues, did, "INPUT_INDEX_INVALID", severity="ERROR", ordinal=ordinal)
                index = None
            if index is not None:
                if index in seen_indexes:
                    _issue(issues, did, "DUPLICATE_INPUT_INDEX", severity="ERROR", ordinal=ordinal)
                if index <= prior_index:
                    _issue(issues, did, "RESULT_INPUT_ORDER_MISMATCH", severity="ERROR", ordinal=ordinal)
                seen_indexes.add(index)
                prior_index = index
                if input_count is not None and index > input_count:
                    _issue(issues, did, "INPUT_INDEX_OUT_OF_RANGE", severity="ERROR", ordinal=ordinal)
                if inputs is not None and index <= len(inputs):
                    if _post_key(inputs[index - 1].get("post_id")) != post:
                        _issue(issues, did, "FIXED_INPUT_POST_ID_MISMATCH", severity="ERROR", ordinal=ordinal)
            attempt = coordinate.get("row_attempt_id")
            if attempt is None:
                _issue(issues, did, "ROW_ATTEMPT_ID_MISSING", ordinal=ordinal)
            else:
                if not isinstance(attempt, str) or not attempt:
                    _issue(issues, did, "ROW_ATTEMPT_ID_INVALID", severity="ERROR", ordinal=ordinal)
                elif attempt in seen_attempts:
                    _issue(issues, did, "DUPLICATE_ROW_ATTEMPT_ID", severity="ERROR", ordinal=ordinal)
                seen_attempts.add(str(attempt))
            source_material = {key: present(row, key) for key in SOURCE_FIELDS}
            source_hash = semantic_hash(source_material)
            if post is not None:
                unique_posts[data_kind].add((namespace, post))
                unique_material[data_kind].add((namespace, post, source_hash))
                post_fingerprints[(data_kind, namespace, post)].add(source_hash)
            ref_coordinate = (index, post)
            reference = reference_rows.get(ref_coordinate)
            if reference is not None:
                used_references.add(ref_coordinate)
            bound_reference = reference is not None and reference_status == "BOUND_CALLER_SUPPLIED"
            if reference is not None and not bound_reference:
                reference_row_status = "INVALID_BINDING"
            else:
                reference_row_status = "BOUND_CALLER_SUPPLIED" if bound_reference else "REFERENCE_NOT_BOUND"
            fixed_row = inputs[index - 1] if inputs is not None and index is not None and index <= len(inputs) else None
            output_rows.append({
                "schema_version": "research_evaluation_row_v1", "dataset_id": did,
                "sample_namespace": namespace, "data_kind": data_kind,
                "coordinate": {"run_id": run_id, "result_sha256": artifact_id,
                               "result_ordinal": ordinal, "input_index": index,
                               "post_id": deepcopy(post_id), "row_attempt_id": deepcopy(attempt)},
                "saved_row_sha256": semantic_hash(row), "saved_row": deepcopy(row),
                "source_material": source_material, "source_material_sha256": source_hash,
                "fixed_input_row": {"present": fixed_row is not None, "value": deepcopy(fixed_row),
                                    "sha256": semantic_hash(fixed_row) if fixed_row is not None else None},
                "fixed_input_raw_records": deepcopy(dataset.get("input_readback", {}).get("post_bindings", {}).get(str(index))),
                "row_measurement": {key: present(run_meta, key) for key in (
                    "decision_call_attempt_receipt", "decision_call_ledger", "decision_call_ledger_summary",
                    "decision_call_measurement", "decision_cost_trace", "execution_config",
                    "source_context_diagnostics")},
                "reference": {"binding_status": reference_row_status, "payload": deepcopy(reference),
                              "reference_kind": reference.get("reference_kind") if bound_reference else "UNJUDGED",
                              "authority_status": "CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED",
                              "artifact_ref": deepcopy(refs.get("reference"))},
                "candidate_recall": {"value": None, "status": "NOT_ESTIMABLE",
                                     "reason": "INDEPENDENT_CORPUS_REFERENCE_MAPPING_NOT_EVALUATED"},
                "publication_authority": False,
            })
        unused = set(reference_rows) - used_references
        if unused:
            _issue(issues, did, "REFERENCE_ROWS_NOT_IN_SAVED_RESULT", details={"count": len(unused)})
        missing_indexes = None
        if inputs is not None:
            missing_indexes = sorted(set(range(1, len(inputs) + 1)) - seen_indexes)
            if missing_indexes:
                _issue(issues, did, "INPUT_ROWS_WITHOUT_BOUND_SAVED_RESULT", details={"input_indexes": missing_indexes})
        output_datasets.append({
            "dataset_id": did, "sample_namespace": namespace, "data_kind": data_kind,
            "parent_dataset_id": present(dataset, "parent_dataset_id"),
            "parent_relation_status": "CALLER_DECLARED_NOT_INDEPENDENT_SAMPLING_PROOF",
            "source_refs": deepcopy(refs),
            "input_readback": deepcopy(dataset.get("input_readback")),
            "manifest_observation": {key: present(manifest, key) for key in MANIFEST_FIELDS},
            "reference_binding_status": reference_status,
            "denominators": {"input_count": input_count,
                             "input_count_source": "MANIFEST" if _integer(manifest.get("input_post_count")) else ("FIXED_INPUT" if inputs is not None else "UNKNOWN"),
                             "saved_observation_count": len(result),
                             "bound_input_index_count": len(seen_indexes),
                             "missing_saved_row_count": max(0, input_count - len(result)) if input_count is not None else None,
                             "fixed_input_indexes_without_bound_result": missing_indexes,
                             "failed_count": present(manifest, "failed_count"),
                             "pending_count": present(manifest, "pending_count")},
        })
    for dataset in output_datasets:
        parent = dataset["parent_dataset_id"]
        if parent["present"] and (parent["value"] not in seen_ids or parent["value"] == dataset["dataset_id"]):
            _issue(issues, dataset["dataset_id"], "PARENT_DATASET_NOT_BOUND", severity="ERROR")
    per_kind = {}
    for kind in sorted(DATA_KINDS):
        selected = [row for row in output_rows if row["data_kind"] == kind]
        per_kind[kind] = {
            "saved_observation_count": len(selected),
            "unique_post_count": len(unique_posts[kind]),
            "unique_source_material_count": len(unique_material[kind]),
            "posts_with_multiple_source_fingerprints": sum(
                len(values) > 1 for key, values in post_fingerprints.items() if key[0] == kind),
            "independent_sample_count": None,
            "denominator_status": "OBSERVATIONAL_COUNTS_NOT_INDEPENDENCE_PROOF",
        }
    core = {
        "schema_version": SNAPSHOT_SCHEMA, "policy_version": POLICY_VERSION,
        "execution_mode": "SAVED_ARTIFACT_READBACK", "publication_authority": False,
        "central_db_write": False, "model_calls": 0, "network_calls": 0,
        "formal_kpi_status": "NOT_ESTIMABLE",
        "binding_status": "INVALID_BINDING" if any(i["severity"] == "ERROR" for i in issues) else "COMPLETE_WITH_LIMITS",
        "byte_readback_status": "CALLER_METADATA_ONLY",
        "datasets": output_datasets, "rows": output_rows, "issues": issues,
        "denominators_by_data_kind": per_kind,
        "limitations": [
            "과거 실행의 코드·설정·후보·원장 누락을 현재 실행 정보로 보충하지 않는다.",
            "원본 판정과 공개 권위는 재검증하거나 승격하지 않는다.",
            "참조 등급은 호출자 제공 값이며 독립 gold 또는 corpus 결속을 증명하지 않는다.",
            "unique post/source 수는 독립 표본 수와 다르다. 합성 자료는 별도 분모다.",
        ],
    }
    return {**core, "semantic_sha256": semantic_hash(core)}


def _strict_json(raw: bytes, field: str) -> Any:
    def no_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise SnapshotError(f"{field}: duplicate JSON key {key}")
            value[key] = item
        return value

    def no_constant(value):
        raise SnapshotError(f"{field}: non-finite JSON number {value}")
    try:
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=no_duplicates,
                          parse_constant=no_constant)
    except (ValueError, UnicodeError) as exc:
        raise SnapshotError(f"{field}: invalid JSON: {exc}") from exc


def _read_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise SnapshotError(f"source is not a regular file: {path}")
    with path.open("rb") as source:
        raw = source.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise SnapshotError(f"source exceeds {MAX_SOURCE_BYTES} bytes: {path}")
    return raw


def _parse_jsonl_input(raw: bytes, field: str) -> tuple[list[dict], dict]:
    """Preserve raw post/comment records and file order; do not emulate runtime normalization."""
    records, posts, bindings = [], [], {}
    comments = defaultdict(list)
    seen_posts, seen_comments = set(), set()
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        value = _mapping(_strict_json(line, f"{field}:{line_number}"), "input record")
        post = _post_key(value.get("post_id"))
        if post is None:
            raise SnapshotError(f"{field}:{line_number}: missing post_id")
        record = {"line_number": line_number, "raw_line_sha256": hashlib.sha256(line).hexdigest(),
                  "payload": value}
        records.append(record)
        if "comment_id" in value:
            comment_id = _post_key(value["comment_id"])
            if comment_id is None or (post, comment_id) in seen_comments:
                raise SnapshotError(f"{field}:{line_number}: invalid or duplicate comment_id")
            seen_comments.add((post, comment_id))
            comments[post].append(record)
        else:
            if post in seen_posts:
                raise SnapshotError(f"{field}:{line_number}: duplicate input post_id")
            seen_posts.add(post)
            posts.append(value)
            bindings[str(len(posts))] = {"post": record, "comments": []}
    for index, post in enumerate(posts, 1):
        bindings[str(index)]["comments"] = deepcopy(comments.get(_post_key(post["post_id"]), []))
    orphan_comments = [item for key, items in comments.items() if key not in seen_posts for item in items]
    if orphan_comments:
        raise SnapshotError(f"{field}: comment post_id does not bind to any input post")
    return posts, {"format": "JSONL_POST_COMMENT_V1", "records": records, "post_bindings": bindings,
                   "raw_line_hash_scope": "EXACT_LINE_BYTES_EXCLUDING_LINE_ENDING", "post_count": len(posts)}


def load_request(spec_path: str | Path) -> tuple[list[dict], list[dict]]:
    """Read exact pinned files; no glob, network, model or mutable source writes."""
    path = Path(spec_path).resolve(strict=True)
    spec_bytes = _read_bytes(path)
    spec = _mapping(_strict_json(spec_bytes, str(path)), "request")
    if spec.get("schema_version") != REQUEST_SCHEMA:
        raise SnapshotError("unsupported request schema")
    if set(spec) - {"schema_version", "datasets"}:
        raise SnapshotError("unknown request fields")
    records = spec.get("datasets")
    if not isinstance(records, list) or not records:
        raise SnapshotError("request.datasets: non-empty list required")
    sources = [{"path": str(path), "sha256": hashlib.sha256(spec_bytes).hexdigest(),
                "bytes": len(spec_bytes), "role": "request"}]
    datasets = []
    for record in records:
        _mapping(record, "request.dataset")
        if set(record) - {"dataset_id", "sample_namespace", "data_kind", "parent_dataset_id",
                           "result", "manifest", "input", "reference"}:
            raise SnapshotError("unknown dataset fields")
        dataset = {key: deepcopy(record[key]) for key in (
            "dataset_id", "sample_namespace", "data_kind", "parent_dataset_id") if key in record}
        dataset["source_refs"] = {}
        for kind in ("result", "manifest", "input", "reference"):
            if kind not in record:
                if kind in ("result", "manifest"):
                    raise SnapshotError(f"required source: {kind}")
                continue
            ref = _mapping(record[kind], f"request.{kind}")
            allowed = {"path", "sha256", "format"} if kind == "input" else {"path", "sha256"}
            if set(ref) - allowed or not {"path", "sha256"}.issubset(ref):
                raise SnapshotError(f"request.{kind}: path and sha256 required; only input accepts format")
            raw_path = Path(_text(ref["path"], f"request.{kind}.path"))
            source_path = (path.parent / raw_path).resolve(strict=True) if not raw_path.is_absolute() else raw_path.resolve(strict=True)
            expected = ref["sha256"]
            if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
                raise SnapshotError(f"request.{kind}: required lowercase byte SHA256")
            raw = _read_bytes(source_path)
            actual = hashlib.sha256(raw).hexdigest()
            if actual != expected:
                raise SnapshotError(f"source SHA256 mismatch: {source_path}")
            format_name = ref.get("format", "JSON")
            if format_name == "JSONL_POST_COMMENT_V1" and kind == "input":
                payload, input_readback = _parse_jsonl_input(raw, str(source_path))
                dataset["input_readback"] = input_readback
            elif format_name == "JSON":
                payload = _strict_json(raw, str(source_path))
            else:
                raise SnapshotError(f"unsupported input format: {format_name}")
            bound_ref = {"path": str(source_path), "sha256": actual, "bytes": len(raw)}
            if kind == "input":
                bound_ref["format"] = format_name
            dataset[kind] = payload
            dataset["source_refs"][kind] = bound_ref
            sources.append({**bound_ref, "role": kind, "dataset_id": dataset.get("dataset_id")})
        datasets.append(dataset)
    return datasets, sources


def _verify_sources(sources: list[dict]) -> list[dict]:
    verified = []
    for source in sources:
        raw = _read_bytes(Path(source["path"]))
        after = hashlib.sha256(raw).hexdigest()
        if after != source["sha256"] or len(raw) != source["bytes"]:
            raise SnapshotError(f"source changed during export: {source['path']}")
        verified.append({"path": source["path"], "sha256_start": source["sha256"],
                         "sha256_end": after, "unchanged": True})
    return verified


def _write_new(path: Path, data: bytes) -> dict:
    if len(data) > MAX_SOURCE_BYTES:
        raise SnapshotError(f"generated artifact exceeds {MAX_SOURCE_BYTES} bytes: {path.name}")
    with path.open("xb") as output:
        output.write(data)
    return {"filename": path.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _report_ko(snapshot: dict) -> str:
    lines = [
        "# 저장 자료 평가 snapshot", "",
        f"결속 상태: {snapshot['binding_status']}. 실행 방식은 SAVED_ARTIFACT_READBACK이다.",
        "모델·검색 호출은 0이며 공개 권위와 중앙 DB 쓰기는 없다. 정식 KPI는 NOT_ESTIMABLE이다.", "",
        "| 자료 | 입력 분모 | 저장 행 | 저장 누락 |", "|---|---:|---:|---:|",
    ]
    for dataset in snapshot["datasets"]:
        count = dataset["denominators"]
        label = dataset["dataset_id"].replace("|", "/").replace("\n", " ")
        lines.append(f"| {label} | {count['input_count']} | {count['saved_observation_count']} | {count['missing_saved_row_count']} |")
    lines += ["", "실행별 분모와 중복 제거 분모는 별개다. 독립 표본 수는 확정하지 않는다.", ""]
    for kind, value in snapshot["denominators_by_data_kind"].items():
        lines.append(f"- {kind}: 저장 {value['saved_observation_count']}행, unique post {value['unique_post_count']}개, unique source {value['unique_source_material_count']}개.")
    lines += ["", "## 제한과 결속 문제", ""]
    lines += ["- " + line for line in snapshot["limitations"]]
    for issue in snapshot["issues"]:
        lines.append(f"- {issue['severity']} / {issue['dataset_id']} / {issue['code']}")
    lines += ["", "행의 원본 후보·판정·측정값은 rows.jsonl, 종료 manifest 관측은 snapshot_manifest.json에 별도로 보존했다.",
              "source_refs.json은 원본 byte hash를 기록한다. 생성 시간과 snapshot ID는 semantic SHA 계산에서 제외했다.", ""]
    return "\n".join(lines)


def export_snapshot(spec_path: str | Path, output_dir: str | Path, *,
                    research_root: str | Path, snapshot_id: str | None = None,
                    created_at: str | None = None) -> dict:
    """Write only a new child directory; existing sources/output are never replaced."""
    root = Path(research_root).resolve(strict=True)
    if not root.is_dir():
        raise SnapshotError("research_root must be an existing directory")
    output = Path(output_dir).resolve()
    if output == root or not output.is_relative_to(root):
        raise SnapshotError("output_dir must be a strict child of research_root")
    if output.exists():
        raise SnapshotError("output_dir already exists; overwrite forbidden")
    datasets, sources = load_request(spec_path)
    for source in sources:
        if Path(source["path"]).is_relative_to(output):
            raise SnapshotError("output directory overlaps an input artifact")
    snapshot = build_evaluation_snapshot(datasets)
    _verify_sources(sources)
    # No parents=True: the caller must explicitly prepare the output parent.
    output.mkdir()
    files = []
    files.append(_write_new(output / "source_refs.json", canonical_bytes(sources) + b"\n"))
    rows_bytes = b"".join(canonical_bytes(row) + b"\n" for row in snapshot["rows"])
    files.append(_write_new(output / "rows.jsonl", rows_bytes))
    files.append(_write_new(output / "report_ko.md", _report_ko(snapshot).encode("utf-8")))
    verified = _verify_sources(sources)
    manifest = {key: deepcopy(value) for key, value in snapshot.items() if key != "rows"}
    manifest.update({
        "snapshot_id": snapshot_id or uuid.uuid4().hex,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "exporter_source_sha256": hashlib.sha256(_read_bytes(Path(__file__))).hexdigest(),
        "byte_readback_status": "VERIFIED_START_END",
        "byte_readback_scope": "EXPLICIT_INPUTS_ONLY_NO_GLOBAL_FILESYSTEM_ATTESTATION",
        "source_integrity": verified, "output_files": files,
        "semantic_hash_scope": "PURE_BUILDER_CONTENT_EXCLUDES_CREATION_AND_EXPORT_RECEIPT",
        "semantic_byte_readback_status": snapshot["byte_readback_status"],
        "source_refs": sources,
    })
    manifest["manifest_sha256"] = semantic_hash(manifest)
    _write_new(output / "snapshot_manifest.json", canonical_bytes(manifest) + b"\n")
    return manifest


def verify_exported_snapshot(output_dir: str | Path) -> dict:
    """Verify exported checksums and deterministic payload, without source writes.

    This checks integrity of a saved export, not independent provenance or truth.
    It deliberately does not require the original source files to remain mounted.
    """
    output = Path(output_dir).resolve(strict=True)
    manifest = _mapping(_strict_json(_read_bytes(output / "snapshot_manifest.json"),
                                    "snapshot_manifest"), "snapshot_manifest")
    actual_self = manifest.get("manifest_sha256")
    material = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if manifest.get("schema_version") != SNAPSHOT_SCHEMA or semantic_hash(material) != actual_self:
        raise SnapshotError("snapshot manifest self hash mismatch")
    listed = manifest.get("output_files")
    expected_names = {"source_refs.json", "rows.jsonl", "report_ko.md"}
    if not isinstance(listed, list) or len(listed) != 3:
        raise SnapshotError("snapshot output file inventory mismatch")
    observed, raw_files = set(), {}
    for ref in listed:
        name = ref.get("filename") if isinstance(ref, dict) else None
        if name not in expected_names or name in observed:
            raise SnapshotError("snapshot output file inventory mismatch")
        observed.add(name)
        raw = _read_bytes(output / name)
        if len(raw) != ref.get("bytes") or hashlib.sha256(raw).hexdigest() != ref.get("sha256"):
            raise SnapshotError(f"snapshot output hash mismatch: {name}")
        raw_files[name] = raw
    rows = [_strict_json(line, "rows.jsonl") for line in raw_files["rows.jsonl"].splitlines()]
    core_fields = (
        "schema_version", "policy_version", "execution_mode", "publication_authority",
        "central_db_write", "model_calls", "network_calls", "formal_kpi_status",
        "binding_status", "datasets", "issues", "denominators_by_data_kind", "limitations",
    )
    core = {key: manifest[key] for key in core_fields}
    core["rows"] = rows
    core["byte_readback_status"] = manifest.get("semantic_byte_readback_status")
    if semantic_hash(core) != manifest.get("semantic_sha256"):
        raise SnapshotError("snapshot semantic hash mismatch")
    if _strict_json(raw_files["source_refs.json"], "source_refs") != manifest.get("source_refs"):
        raise SnapshotError("snapshot source inventory mismatch")
    return {"status": "VERIFIED", "binding_status": manifest["binding_status"],
            "semantic_sha256": manifest["semantic_sha256"], "saved_row_count": len(rows),
            "publication_authority": False, "independent_provenance_verified": False}

