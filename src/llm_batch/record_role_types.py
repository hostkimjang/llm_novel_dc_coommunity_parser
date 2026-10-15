"""미래 버전 typed 선언 초안. 제품 클래스/실제 생산값이 아니다."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class SourceLiteralSpanDraft:
    source_id: Optional[str]
    source_index: Optional[int]
    source_role: Optional[str]
    source_raw_bytes_sha256: Optional[str]
    raw_span: Optional[Tuple[int, int]]
    raw_text: Optional[str]
    used_span: Optional[Tuple[int, int]]
    used_text: Optional[str]
    boundary_map_sha256: Optional[str]
    coordinate_system: str
    raw_coordinate_system: str
    status: str
    reason: str


@dataclass(frozen=True)
class NativeNPDraft:
    full_np: SourceLiteralSpanDraft
    head: SourceLiteralSpanDraft
    governed_predicate_ids: Tuple[str, ...]
    status: str
    reason: str


@dataclass(frozen=True)
class LiteralObservationDraft:
    literal: Optional[SourceLiteralSpanDraft]
    status: str
    reason: str


@dataclass(frozen=True)
class NPObservationDraft:
    np: Optional[NativeNPDraft]
    status: str
    reason: str


@dataclass(frozen=True)
class NativeRecordReferenceDraft:
    record_object_id: Optional[str]
    predicate_id: Optional[str]
    event_id: Optional[str]
    native_work_reference_ids: Tuple[str, ...]
    status: str
    proofs: Tuple[SourceLiteralSpanDraft, ...]
    reason: str


@dataclass(frozen=True)
class RecordRoleBindingDraft:
    role: str
    entity_literal: Optional[str]
    subject_np: Optional[NativeNPDraft]
    record_object_id: Optional[str]
    governing_predicate_id: Optional[str]
    status: str
    proofs: Tuple[SourceLiteralSpanDraft, ...]
    cross_source_record_reference_edge_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class FutureApplicabilityDraft:
    field: str
    event_class: str
    state: str
    rule_version: str
    rule_id: str
    native_record_relation: str
    source_proofs: Tuple[SourceLiteralSpanDraft, ...]
    reason: str


@dataclass(frozen=True)
class SameRecordTransmissionDraft:
    record_object_id: Optional[str]
    predicate_id: Optional[str]
    event_id: Optional[str]
    ledger_pointer: Optional[str]
    actual_consumed_ledger_pointer: Optional[str]
    actual_returned_relation_pointer: Optional[str]
    serialized_attribute_pointer: Optional[str]
    defining_class_module: Optional[str]
    defining_class_source_sha256: Optional[str]
    class_identity_status: str
    full_annotation_value_status: str
    status: str
    reason: str


@dataclass(frozen=True)
class RecordRoleProvenanceDraft:
    schema_version: str
    record_reference: NativeRecordReferenceDraft
    record_assertion_source: LiteralObservationDraft
    reported_reading_content_source: LiteralObservationDraft
    record_owner_np: NPObservationDraft
    record_writer: RecordRoleBindingDraft
    content_reader: RecordRoleBindingDraft
    record_reader: RecordRoleBindingDraft
    verifier: RecordRoleBindingDraft
    annotation_envelope_reference: LiteralObservationDraft
    applicability: Tuple[FutureApplicabilityDraft, ...]
    same_record_transmission: SameRecordTransmissionDraft
