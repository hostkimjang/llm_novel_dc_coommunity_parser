"""CAL 전용 raw-event 자료형. 출처 검산은 bridge, temperature 학습은 solver가 맡는다.

공개 API: CalibrationFitEvent.create(**kwargs), .validate(), .to_dict(),
.from_dict(dict); validate_calibration_fit_events(events, *, expected_example_ids=None)
-> tuple[CalibrationFitEvent, ...]; calibration_event_set_sha256(events) -> str.
자료형의 자체 SHA는 바이트 결속이며 정답·출처 선언의 진실을 인증하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping


SCHEMA_VERSION = "candidate_reranker_calibration_fit_event_v1"
MAX_EVENTS = 256
MAX_LABELS = 21
MAX_EVENT_BYTES = 64 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CANDIDATE = re.compile(r"cand_[0-9a-f]{64}\Z")
_PROVENANCE_FIELDS = {"grade", "artifact_sha256", "reviewer", "scope"}
_HASH_FIELDS = ("training_split_manifest_sha256", "calibration_manifest_sha256",
    "scorer_fingerprint", "scorer_summary_sha256", "model_sha256", "base_model_sha256",
    "source_binding_sha256", "raw_receipt_sha256", "candidate_set_fingerprint",
    "publication_input_fingerprint", "generation_proof_fingerprint",
    "retrieval_state_fingerprint", "feature_fingerprint")
_SHARED_FIELDS = ("training_split_manifest_sha256", "calibration_manifest_sha256",
    "scorer_fingerprint", "scorer_summary_sha256", "model_sha256", "base_model_sha256", "data_kind")


class CalibrationDataError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CalibrationDataError(code)


def _bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise CalibrationDataError("EVENT_JSON_INVALID") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _text(value: Any) -> bool:
    return type(value) is str and 0 < len(value.strip()) <= 512 and "\x00" not in value


def _hash(value: Any) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value))


def _score(value: Any) -> float:
    _require(type(value) in (int, float), "FINITE_RAW_SCORE_REQUIRED")
    try:
        number = float(value)
    except OverflowError as exc:
        raise CalibrationDataError("FINITE_RAW_SCORE_REQUIRED") from exc
    _require(math.isfinite(number), "FINITE_RAW_SCORE_REQUIRED")
    return number


@dataclass(frozen=True, slots=True)
class CalibrationFitEvent:
    example_id: str
    post_id: str
    labels: tuple[str, ...]
    raw_scores: tuple[float, ...]
    truth_kind: str
    truth_label: str
    label_provenance: Mapping[str, str]
    training_split_manifest_sha256: str
    calibration_manifest_sha256: str
    scorer_fingerprint: str
    scorer_summary_sha256: str
    model_sha256: str
    base_model_sha256: str
    data_kind: str
    source_binding_sha256: str
    raw_receipt_sha256: str
    candidate_set_fingerprint: str
    publication_input_fingerprint: str
    generation_proof_fingerprint: str
    retrieval_state_fingerprint: str
    feature_fingerprint: str
    event_sha256: str
    split: str = "CALIBRATION"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require(type(self.labels) in (list, tuple) and type(self.raw_scores) in (list, tuple),
                 "EVENT_ARRAY_REQUIRED")
        _require(isinstance(self.label_provenance, Mapping), "LABEL_PROVENANCE_REQUIRED")
        object.__setattr__(self, "labels", tuple(self.labels))
        object.__setattr__(self, "raw_scores", tuple(_score(x) for x in self.raw_scores))
        object.__setattr__(self, "label_provenance", MappingProxyType(dict(self.label_provenance)))
        self.validate()

    @classmethod
    def create(cls, **kwargs) -> "CalibrationFitEvent":
        """현재 CAL event 계약을 정규화해 봉인한다. raw 점수에서 정답을 추측하지 않는다."""
        payload = dict(kwargs)
        _require("event_sha256" not in payload, "EVENT_SHA_MUST_BE_COMPUTED")
        payload.setdefault("split", "CALIBRATION")
        payload.setdefault("schema_version", SCHEMA_VERSION)
        _require(set(payload) == {item.name for item in fields(cls)} - {"event_sha256"}, "EVENT_FIELDS_INVALID")
        _require(type(payload["labels"]) in (list, tuple) and type(payload["raw_scores"]) in (list, tuple),
                 "EVENT_ARRAY_REQUIRED")
        _require(isinstance(payload["label_provenance"], Mapping), "LABEL_PROVENANCE_REQUIRED")
        payload["labels"] = list(payload["labels"])
        payload["raw_scores"] = [_score(value) for value in payload["raw_scores"]]
        payload["label_provenance"] = dict(payload["label_provenance"])
        payload["event_sha256"] = canonical_sha256(payload)
        return cls(**payload)

    @classmethod
    def from_dict(cls, value: dict) -> "CalibrationFitEvent":
        """추가 필드와 낡거나 변경된 자체 SHA를 거절한다."""
        _require(type(value) is dict and set(value) == {item.name for item in fields(cls)}, "EVENT_FIELDS_INVALID")
        encoded = _bytes(value)
        _require(len(encoded) <= MAX_EVENT_BYTES, "EVENT_BYTE_LIMIT")
        return cls(**json.loads(encoded))

    def _payload(self) -> dict:
        result = {item.name: getattr(self, item.name) for item in fields(self) if item.name != "event_sha256"}
        result.update(labels=list(self.labels), raw_scores=list(self.raw_scores), label_provenance=dict(self.label_provenance))
        return result

    def validate(self) -> None:
        _require(self.schema_version == SCHEMA_VERSION and self.split == "CALIBRATION", "CALIBRATION_EVENT_ONLY")
        _require(_text(self.example_id) and _text(self.post_id), "EVENT_ID_INVALID")
        _require(2 <= len(self.labels) <= MAX_LABELS and len(self.raw_scores) == len(self.labels), "EVENT_LABEL_COUNT")
        _require(all(type(label) is str for label in self.labels) and len(set(self.labels)) == len(self.labels)
                 and self.labels[-1] == "__NIL__" and all(_CANDIDATE.fullmatch(label) for label in self.labels[:-1]),
                 "CANDIDATE_OPTION_LABELS_REQUIRED")
        for value in self.raw_scores:
            _score(value)
        _require(type(self.truth_kind) is str and self.truth_kind in {"CANDIDATE", "NIL"}, "RESOLVED_TRUTH_REQUIRED")
        _require(type(self.truth_label) is str and self.truth_label in self.labels
                 and (self.truth_label == "__NIL__") == (self.truth_kind == "NIL"), "TRUTH_EVENT_MISMATCH")
        _require(all(_hash(getattr(self, name)) for name in _HASH_FIELDS) and _hash(self.event_sha256), "EVENT_HASH_INVALID")
        _require(type(self.data_kind) is str and self.data_kind in {"SOURCE_BACKED", "SYNTHETIC_FIXTURE"}, "EVENT_DATA_KIND_INVALID")
        provenance = self.label_provenance
        _require(set(provenance) == _PROVENANCE_FIELDS, "LABEL_PROVENANCE_FIELDS_INVALID")
        _require(type(provenance["grade"]) is str and provenance["grade"] in {"MODEL_REFERENCE", "GOLD_LITE", "HUMAN_GOLD", "SYNTHETIC_FIXTURE"},
                 "RESOLVED_PROVENANCE_GRADE_REQUIRED")
        _require(provenance["scope"] == "WORK_IDENTITY" and _text(provenance["reviewer"])
                 and _hash(provenance["artifact_sha256"]), "LABEL_PROVENANCE_INVALID")
        _require(not (self.data_kind == "SOURCE_BACKED" and provenance["grade"] == "SYNTHETIC_FIXTURE"), "SYNTHETIC_PROVENANCE_MIXED")
        payload = self._payload()
        _require(len(_bytes({**payload, "event_sha256": self.event_sha256})) <= MAX_EVENT_BYTES, "EVENT_BYTE_LIMIT")
        _require(self.event_sha256 == canonical_sha256(payload), "EVENT_SHA_MISMATCH")

    def to_dict(self) -> dict:
        return {**self._payload(), "event_sha256": self.event_sha256}

    def __deepcopy__(self, memo):
        # 모든 필드와 provenance가 불변이다. MappingProxyType의 pickle을 피한다.
        return self


def validate_calibration_fit_events(events, *, expected_example_ids=None) -> tuple[CalibrationFitEvent, ...]:
    """CAL 전체 집합 검산용 공통 helper. 순서·중복·동일 고정 모델을 보존한다."""
    _require(type(events) in (list, tuple) and 1 <= len(events) <= MAX_EVENTS, "CAL_EVENT_COUNT_LIMIT")
    result = tuple(events)
    _require(all(isinstance(event, CalibrationFitEvent) for event in result), "TYPED_CAL_EVENT_REQUIRED")
    for event in result:
        event.validate()
    ids, posts = [e.example_id for e in result], [e.post_id for e in result]
    _require(len(set(ids)) == len(ids) and len(set(posts)) == len(posts), "DUPLICATE_CAL_EVENT")
    _require(all(all(getattr(e, key) == getattr(result[0], key) for key in _SHARED_FIELDS) for e in result),
             "MIXED_CAL_EVENT_BINDING")
    if expected_example_ids is not None:
        _require(type(expected_example_ids) in (list, tuple) and all(_text(x) for x in expected_example_ids),
                 "EXPECTED_CAL_IDS_REQUIRED")
        _require(ids == list(expected_example_ids), "CAL_EVENT_UNIVERSE_MISMATCH")
    return result


def calibration_event_set_sha256(events) -> str:
    return canonical_sha256([event.to_dict() for event in validate_calibration_fit_events(events)])
