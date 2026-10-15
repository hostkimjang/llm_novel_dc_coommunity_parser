"""의미 특징의 공통 원문 재생 계약. IO·정답·최종 선택을 사용하지 않는다."""
from __future__ import annotations

import hashlib
import json
import unicodedata

from . import candidate_reranker_alias_evidence as aliases
from . import candidate_reranker_semantics as semantics
from .candidate_reranker_shadow import build_frozen_view, canonical_sha256

SCHEMA_VERSION = "candidate_semantic_feature_input_v1"
CAPTURE_SCHEMA = "reranker_preselection_capture_v2"
MAX_INPUT_BYTES = 512 * 1024
FEATURE_CONTRACT = {
    "schema_version": "candidate_semantic_feature_contract_v1",
    "producer_schema": semantics.SCHEMA_VERSION,
    "producer_policy_sha256": semantics.POLICY_SHA256,
    "parser_contract_sha256": semantics.PARSER_CONTRACT_SHA256,
    "alias_policy_sha256": aliases.POLICY_SHA256,
    "aggregation": "CANDIDATE_ROLE_SET_V1",
    "input_roles": "MUST_BE_EMPTY",
    "alias_features": "VALIDATED_EXPLICIT_EVIDENCE_ONLY",
    "alias_family": "NFKC_CASEFOLD_SURFACE_SHA256_V1",
    "unicode_version": unicodedata.unidata_version,
    "alias_exposure": "DEFINITION_AND_REVIEW_RAW_SOURCE_WITH_SAME_LINEAGE_V1",
    "corpus_exposure": "EXPLICIT_CANDIDATE_WORK_EDITION_MEDIA_AND_TEXT_BINDING",
    "r2_exposure_binding": "EXACT_KNOWN_WORK_EDITION_MEDIA_AND_DATA_KIND_V1",
    "failures": "REJECT_NO_LEGACY_FALLBACK",
    "executable_observation_statuses": ["OBSERVED", "NO_MATCH", "AMBIGUOUS"],
    "publication_authority": False,
}
FEATURE_CONTRACT_SHA256 = canonical_sha256(FEATURE_CONTRACT)
_FIELDS = {"schema_version", "contract_sha256", "original_view", "enriched_view",
    "observation", "retrieval_receipt", "alias_evidence", "alias_payload_sha256", "input_sha256"}


class SemanticInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(value, code):
    if not value:
        raise SemanticInputError(code)


def _raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _copy(value):
    # 기존 bounded JSON 검사를 재사용하며 import cycle은 호출 시점으로 제한한다.
    from .candidate_reranker_learned import _copy_json
    return _copy_json(value, MAX_INPUT_BYTES)


def _hash(value):
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
             "SEMANTIC_SHA_INVALID")
    return value


def _payload_refs(evidence):
    if evidence is None:
        return []
    _require(type(evidence) is dict and set(evidence) == aliases.CALL_FIELDS, "SEMANTIC_ALIAS_SCHEMA_INVALID")
    paths = evidence["snapshot_files"]
    _require(type(paths) is dict and len(paths) <= aliases.MAX_FILES, "SEMANTIC_ALIAS_FILES_INVALID")
    return sorted({_hash(evidence["snapshot_manifest_sha256"]), _hash(evidence["corpus_sha256"]),
                   *(_hash(value) for value in paths.values())})


def _payloads(refs, values):
    _require(type(refs) is list and len(refs) <= aliases.MAX_FILES + 2,
             "SEMANTIC_ALIAS_FILES_INVALID")
    _require(refs == sorted(set(_hash(value) for value in refs)), "SEMANTIC_ALIAS_FILES_INVALID")
    if not refs:
        return {}
    _require(type(values) is dict, "SEMANTIC_EVIDENCE_MISSING")
    result, size = {}, 0
    for digest in refs:
        raw = values.get(digest)
        _require(type(raw) is bytes, "SEMANTIC_EVIDENCE_MISSING")
        size += len(raw)
        _require(size <= aliases.MAX_INPUT_BYTES, "SEMANTIC_EVIDENCE_BYTE_LIMIT")
        _require(hashlib.sha256(raw).hexdigest() == digest, "SEMANTIC_EVIDENCE_SHA_MISMATCH")
        result[digest] = raw
    return result


def build_semantic_input(original_view, *, retrieval_receipt, alias_evidence=None, evidence_payloads=None):
    """같은 R2 관측으로 원본을 검산한 뒤 producer를 실행하고 새 입력을 봉인한다."""
    original = _copy(original_view)
    retrieval = _copy(retrieval_receipt)
    _require(_raw(build_frozen_view(original["source_view"], retrieval)) == _raw(original),
             "SEMANTIC_R2_ORIGINAL_MISMATCH")
    evidence = _copy(alias_evidence)
    if evidence is not None:
        _require(_raw(evidence.get("retrieval_receipt")) == _raw(retrieval), "SEMANTIC_ALIAS_R2_MISMATCH")
    refs = _payload_refs(evidence)
    payloads = _payloads(refs, evidence_payloads)
    enriched, observation = semantics.observe_preselection_semantics(original,
        alias_evidence=evidence, evidence_payloads=payloads)
    _require(observation["status"] in FEATURE_CONTRACT["executable_observation_statuses"],
             "SEMANTIC_OBSERVATION_NOT_EXECUTABLE")
    value = {"schema_version": SCHEMA_VERSION, "contract_sha256": FEATURE_CONTRACT_SHA256,
        "original_view": original, "enriched_view": enriched, "observation": observation,
        "retrieval_receipt": retrieval, "alias_evidence": evidence, "alias_payload_sha256": refs}
    value["input_sha256"] = canonical_sha256(value)
    return _copy(value)


def validate_semantic_input(value, *, evidence_payloads=None, expected_view=None):
    """자체 지문뿐 아니라 R2와 producer 전체를 재생한다. 원본 인수는 바꾸지 않는다."""
    value = _copy(value)
    _require(type(value) is dict and set(value) == _FIELDS, "SEMANTIC_INPUT_SCHEMA_INVALID")
    _require(value["schema_version"] == SCHEMA_VERSION and value["contract_sha256"] == FEATURE_CONTRACT_SHA256,
             "SEMANTIC_FEATURE_CONTRACT_MISMATCH")
    _require(_hash(value["input_sha256"]) == canonical_sha256({k: v for k, v in value.items() if k != "input_sha256"}),
             "SEMANTIC_INPUT_SHA_MISMATCH")
    _require(value["alias_payload_sha256"] == _payload_refs(value["alias_evidence"]),
             "SEMANTIC_ALIAS_PAYLOAD_SET_MISMATCH")
    expected = build_semantic_input(value["original_view"], retrieval_receipt=value["retrieval_receipt"],
        alias_evidence=value["alias_evidence"], evidence_payloads=evidence_payloads)
    _require(_raw(value) == _raw(expected), "SEMANTIC_INPUT_REPLAY_MISMATCH")
    if expected_view is not None:
        _require(_raw(_copy(expected_view)) == _raw(expected["enriched_view"]), "SEMANTIC_SCORE_VIEW_MISMATCH")
    return expected


def read_semantic_input(raw, *, expected_sha256, evidence_payloads=None, expected_view=None):
    """파일 접근 없이 외부 raw SHA와 중복 키를 검사한다."""
    _require(type(raw) is bytes and len(raw) <= MAX_INPUT_BYTES, "SEMANTIC_INPUT_BYTE_LIMIT")
    _require(hashlib.sha256(raw).hexdigest() == _hash(expected_sha256), "SEMANTIC_INPUT_RAW_SHA_MISMATCH")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "SEMANTIC_INPUT_DUPLICATE_KEY")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(SemanticInputError("SEMANTIC_NONFINITE_NUMBER")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SemanticInputError("SEMANTIC_INPUT_JSON_INVALID") from exc
    return validate_semantic_input(value, evidence_payloads=evidence_payloads, expected_view=expected_view)


def semantic_exposure_requirements(value):
    """이미 재생한 관측에서 실제 채택한 별칭의 노출 요건을 결정적으로 얻는다."""
    validation = value["observation"]["alias_validation"]
    result = []
    for bound in validation["bindings"] if validation is not None else []:
        surface = unicodedata.normalize("NFKC", bound["alias"]).casefold()
        result.append({"candidate_id": bound["candidate_id"], "registry_entry_id": bound["registry_entry_id"],
            "alias": bound["alias"], "alias_family_id": "semantic-alias:" + hashlib.sha256(surface.encode("utf-8")).hexdigest(),
            "source_id": bound["source_id"], "payload_sha256": bound["payload_sha256"],
            "review_source_id": "semantic-review:" + bound["review_receipt_sha256"],
            "review_payload_sha256": bound["review_receipt_sha256"],
            "lineage_root_id": bound["lineage_root_id"],
            **{key: bound[key] for key in ("work_id", "edition_id", "media_type")}})
    return result


def resolve_training_semantic_input(capture, view, row, payloads, evidence, *, split_manifest=None):
    """TRAIN/CAL/FROZEN 공용 결속. 전체 분할 검사는 호출자의 기존 gate가 수행한다."""
    _require(type(capture) is dict and capture.get("schema_version") == CAPTURE_SCHEMA,
             "SEMANTIC_TRAINING_CAPTURE_REQUIRED")
    digest = _hash(capture.get("semantic_input_sha256"))
    _require(type(evidence) is dict and digest in evidence, "SEMANTIC_INPUT_EVIDENCE_MISSING")
    value = read_semantic_input(evidence[digest], expected_sha256=digest,
        evidence_payloads=evidence, expected_view=view)
    label_shas = {row["label_provenance"]["artifact_sha256"],
                  *(item["provenance"]["artifact_sha256"] for item in row["role_mentions"])}
    _require(digest not in label_shas and not label_shas.intersection(value["alias_payload_sha256"]),
             "SEMANTIC_LABEL_AS_FEATURE_EVIDENCE")
    _require(type(split_manifest) is dict, "SEMANTIC_EXPOSURE_MANIFEST_REQUIRED")
    key = "corpus_candidate_id" if view["candidate_namespace"] == "CORPUS_CANDIDATE" else "candidate_id"
    exposures = {item[key]: item for item in row["exposures"]}
    retrieved = value["retrieval_receipt"]["ranked_candidates"]
    _require(len(exposures) == len(row["exposures"]) == len(retrieved)
             and set(exposures) == {item["corpus_candidate_id"] for item in retrieved},
             "SEMANTIC_R2_EXPOSURE_SET_MISMATCH")
    retrieval_policy = value["retrieval_receipt"].get("policy")
    _require(type(retrieval_policy) is dict and retrieval_policy.get("data_kind") == split_manifest["data_kind"],
             "SEMANTIC_R2_DATA_KIND_MISMATCH")
    for candidate in retrieved:
        bound = exposures[candidate["corpus_candidate_id"]]
        _require(all(type(candidate.get(field)) is str and candidate[field] == bound[field]
                     for field in ("work_id", "edition_id", "media_type")), "SEMANTIC_R2_IDENTITY_MISMATCH")
    alias_validation = value["observation"]["alias_validation"]
    _require(alias_validation is None or alias_validation["data_kind"] == split_manifest["data_kind"],
             "SEMANTIC_ALIAS_DATA_KIND_MISMATCH")
    requirements = semantic_exposure_requirements(value)
    if not requirements:
        return value
    sources = {item["source_id"]: item for item in split_manifest["sources"]}
    for item in requirements:
        bound = exposures.get(item["candidate_id"])
        _require(bound is not None, "SEMANTIC_ALIAS_CANDIDATE_NOT_EXPOSED")
        _require(all(bound[field] == item[field] for field in ("work_id", "edition_id", "media_type")),
                 "SEMANTIC_ALIAS_IDENTITY_MISMATCH")
        _require(type(bound["alias_family_ids"]) is list and item["alias_family_id"] in bound["alias_family_ids"],
                 "SEMANTIC_ALIAS_FAMILY_NOT_EXPOSED")
        for sid, raw_sha in ((item["source_id"], item["payload_sha256"]),
                             (item["review_source_id"], item["review_payload_sha256"])):
            _require(sid in row["source_ids"] and sid in bound["source_ids"] and sid in sources,
                     "SEMANTIC_ALIAS_SOURCE_NOT_EXPOSED")
            source = sources[sid]
            _require(source["payload_sha256"] == raw_sha and source["lineage_root_id"] == item["lineage_root_id"],
                     "SEMANTIC_ALIAS_SOURCE_LINEAGE_MISMATCH")
            _require(source["rights_status"] == ("SYNTHETIC_FIXTURE" if split_manifest["data_kind"] == "SYNTHETIC_FIXTURE"
                     else "REUSE_PERMITTED"), "SEMANTIC_ALIAS_SOURCE_RIGHTS_INVALID")
            raw = payloads.get(sid)
            _require(type(raw) is bytes and raw == evidence.get(raw_sha)
                     and hashlib.sha256(raw).hexdigest() == raw_sha, "SEMANTIC_ALIAS_SOURCE_BYTES_MISMATCH")
    return value
