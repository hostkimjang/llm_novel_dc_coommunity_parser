"""미래 explicit producer carrier 전달 후보. lexical 추론·gold 소비는 없다."""
from dataclasses import dataclass, fields, is_dataclass, replace
import hashlib
import json
import re
from pathlib import Path
import types
import typing
from . import record_role_types as T

VERSION = 'RECORD_ROLE_VNEXT_DRAFT1'
FIELDS = ('record_assertion_source', 'reported_reading_content_source', 'record_owner_np',
          'record_writer', 'content_reader', 'record_reader', 'verifier', 'annotation_envelope_reference')
ROLES = dict(zip(FIELDS[3:7], ('RECORD_WRITER', 'CONTENT_READER', 'RECORD_READER', 'VERIFIER')))
STATUSES = {'OBSERVED', 'NOT_OBSERVED', 'CONFLICT', 'PROVENANCE_FAILURE'}
CLASSES = ('SourceLiteralSpanDraft', 'NativeNPDraft', 'LiteralObservationDraft', 'NPObservationDraft',
           'NativeRecordReferenceDraft', 'RecordRoleBindingDraft', 'FutureApplicabilityDraft',
           'SameRecordTransmissionDraft', 'RecordRoleProvenanceDraft')
NATIVE_CLASSES = ('EditionSourceLedger', 'EditionSourceObject', 'EditionSourcePredicate',
                  'EditionSourceEvent', 'EditionNativeSource', 'EditionNativeSpan', 'EditionNativeNP',
                  'EditionCurrentRelation')

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')

def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()

@dataclass(frozen=True)
class ClassBinding:
    module: types.ModuleType
    path: str
    sha256: str

@dataclass(frozen=True)
class LiteralEvidence:
    draft: T.SourceLiteralSpanDraft
    native_span: typing.Any
    native_source: typing.Any

@dataclass(frozen=True)
class NPEvidence:
    draft: T.NativeNPDraft
    native_np: typing.Any

@dataclass(frozen=True)
class FieldEvidence:
    field: str
    record_object: typing.Any
    predicate: typing.Any
    event: typing.Any
    subject_np: typing.Any
    entity_literal: typing.Optional[str]
    proofs: tuple
    relation: str
    cross_source_edge: typing.Any

@dataclass(frozen=True)
class CrossSourceEdge:
    edge_id: str
    record_object: typing.Any
    predicate: typing.Any
    event: typing.Any
    anchor_source: typing.Any
    evidence_sources: tuple
    proofs: tuple

@dataclass(frozen=True)
class ProducerPacket:
    carrier: T.RecordRoleProvenanceDraft
    record_object: typing.Any
    predicate: typing.Any
    event: typing.Any
    literal_evidence: tuple
    np_evidence: tuple
    field_evidence: tuple

@dataclass
class RolePass:
    ledger: typing.Any
    packets: tuple
    producer_binding: ClassBinding
    typed_binding: ClassBinding
    diagnostics: tuple
    consumed_ledger: typing.Any = None
    returned_relation: typing.Any = None

@dataclass(frozen=True)
class CandidateRoleResult:
    relation: typing.Any
    session: RolePass

def verify_module(binding, names):
    module = binding.module
    if type(module) is not types.ModuleType or Path(getattr(module, '__file__', '')).resolve() != Path(binding.path).resolve():
        raise ValueError('actual defining module/file binding missing')
    if file_sha(binding.path) != binding.sha256:
        raise ValueError('defining source SHA changed')
    spec = getattr(module, '__spec__', None)
    if spec is None or Path(spec.origin).resolve() != Path(binding.path).resolve():
        raise ValueError('actual defining spec origin missing')
    for name in names:
        cls = getattr(module, name, None)
        if not isinstance(cls, type) or cls.__module__ != module.__name__:
            raise ValueError('actual class existence/defining module ' + name)

def exact_native(value, name, binding):
    cls = getattr(binding.module, name, None)
    if not isinstance(cls, type) or type(value) is not cls:
        raise ValueError('native class identity ' + name)

def annotation_ok(value, annotation):
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is typing.Union:
        return any(annotation_ok(value, option) for option in args)
    if origin is tuple:
        if type(value) is not tuple:
            return False
        if len(args) == 2 and args[1] is Ellipsis:
            return all(annotation_ok(item, args[0]) for item in value)
        return len(value) == len(args) and all(annotation_ok(item, kind) for item, kind in zip(value, args))
    if annotation is type(None):
        return value is None
    if isinstance(annotation, type):
        if type(value) is not annotation:
            return False
        if is_dataclass(value):
            hints = typing.get_type_hints(annotation)
            return tuple(hints) == tuple(f.name for f in fields(annotation)) and all(annotation_ok(getattr(value, f.name), hints[f.name]) for f in fields(annotation))
        return True
    return False

def walk(value):
    if is_dataclass(value):
        yield value
        for field in fields(value):
            yield from walk(getattr(value, field.name))
    elif type(value) is tuple:
        for item in value:
            yield from walk(item)

def validate_declared_shape(carrier):
    """9개 typed class 전용 guard다. 일반 JSON Schema validator를 대신하지 않는다."""
    if not annotation_ok(carrier, T.RecordRoleProvenanceDraft):
        raise ValueError('full annotation including nested nullable/field order')
    if carrier.schema_version != VERSION or any(getattr(carrier, field).role != role for field, role in ROLES.items()):
        raise ValueError('schema/root role const')
    for item in walk(carrier):
        for field in fields(item):
            value = getattr(item, field.name)
            if isinstance(value, str) and len(value) > 4096 or type(value) is tuple and len(value) > 256:
                raise ValueError('declared field size cap')
        if hasattr(item, 'status') and item.status not in STATUSES:
            raise ValueError('typed status enum')
        if type(item) is T.SourceLiteralSpanDraft:
            if item.coordinate_system != 'NFKC_unicode_code_points' or item.raw_coordinate_system != 'raw_unicode_code_points':
                raise ValueError('declared coordinate const')
            if item.status == 'OBSERVED' and (not item.source_id or type(item.source_index) is not int or item.source_index < 0 or item.source_role not in {'post_title', 'post_body', 'comment'} or any(v is None for v in (item.raw_text, item.used_text, item.raw_span, item.used_span, item.source_raw_bytes_sha256, item.boundary_map_sha256))):
                raise ValueError('OBSERVED source children missing/null')
        elif type(item) is T.LiteralObservationDraft and item.status == 'OBSERVED':
            if item.literal is None or item.literal.status != 'OBSERVED':
                raise ValueError('OBSERVED literal wrapper child missing/null')
        elif type(item) is T.NPObservationDraft and item.status == 'OBSERVED':
            if item.np is None or item.np.status != 'OBSERVED':
                raise ValueError('OBSERVED NP wrapper child missing/null')
        elif type(item) is T.NativeNPDraft and item.status == 'OBSERVED':
            if item.full_np.status != 'OBSERVED' or item.head.status != 'OBSERVED' or not item.governed_predicate_ids:
                raise ValueError('OBSERVED NP nested proof missing')
        elif type(item) is T.NativeRecordReferenceDraft and item.status == 'OBSERVED':
            if not item.record_object_id or not item.predicate_id or not item.event_id or not item.proofs or any(p.status != 'OBSERVED' for p in item.proofs):
                raise ValueError('OBSERVED record anchor/proofs missing')
        elif type(item) is T.RecordRoleBindingDraft:
            if item.role not in ROLES.values():
                raise ValueError('role enum')
            if item.status == 'OBSERVED' and (not item.entity_literal or not item.record_object_id or not item.governing_predicate_id or item.subject_np is None or item.subject_np.status != 'OBSERVED' or not item.proofs or any(p.status != 'OBSERVED' for p in item.proofs)):
                raise ValueError('OBSERVED role children missing/null')
        elif type(item) is T.SameRecordTransmissionDraft:
            if item.class_identity_status not in {'PASS', 'FAIL', 'NOT_OBSERVED'} or item.full_annotation_value_status not in {'PASS', 'FAIL', 'NOT_OBSERVED'}:
                raise ValueError('transmission independent check enum')
            if item.status == 'OBSERVED' and (any(not getattr(item, key) for key in ('record_object_id', 'predicate_id', 'event_id', 'ledger_pointer', 'actual_consumed_ledger_pointer', 'actual_returned_relation_pointer', 'serialized_attribute_pointer', 'defining_class_module', 'defining_class_source_sha256')) or item.class_identity_status == 'NOT_OBSERVED' or item.full_annotation_value_status == 'NOT_OBSERVED'):
                raise ValueError('OBSERVED transmission proof children missing/null')
            if item.status == 'OBSERVED':
                if not re.fullmatch('[a-f0-9]{64}', item.defining_class_source_sha256) or any(not re.fullmatch(r'/(?:[^~/]|~[01])*(?:/(?:[^~/]|~[01])*)*', getattr(item, key)) for key in ('ledger_pointer', 'actual_consumed_ledger_pointer', 'actual_returned_relation_pointer', 'serialized_attribute_pointer')):
                    raise ValueError('OBSERVED transmission SHA/pointer form')

def object_present(value, records):
    return any(value is item for item in records)

def validate_packet(packet, ledger, binding):
    """V01–V07의 관계 검산. producer 의미 authority는 별도 미래 검수다."""
    if type(packet) is not ProducerPacket or type(packet.carrier) is not T.RecordRoleProvenanceDraft:
        raise ValueError('producer packet/pinned typed carrier required')
    carrier = packet.carrier
    validate_declared_shape(carrier)
    if carrier.schema_version != VERSION:
        raise ValueError('candidate schema version')
    for value in walk(carrier):
        if hasattr(value, 'status') and value.status not in STATUSES:
            raise ValueError('typed status enum')
    for native, name, records in ((packet.record_object, 'EditionSourceObject', ledger.objects),
            (packet.predicate, 'EditionSourcePredicate', ledger.predicates), (packet.event, 'EditionSourceEvent', ledger.events)):
        exact_native(native, name, binding)
        if not object_present(native, records):
            raise ValueError('producer anchor is outside this actual ledger')
    ref = carrier.record_reference
    if ref.record_object_id != packet.record_object.object_id or ref.predicate_id != packet.predicate.predicate_id or ref.event_id != packet.event.event_id:
        raise ValueError('V03 record/predicate/event exact anchor IDs')
    if packet.event.predicate_id != packet.predicate.predicate_id or packet.event.object_id != packet.record_object.object_id:
        raise ValueError('V03 actual event/predicate/object edge')
    if packet.record_object.object_id not in packet.predicate.object_ids:
        raise ValueError('V03 anchor predicate does not govern record')
    if len(ref.native_work_reference_ids) != len(set(ref.native_work_reference_ids)):
        raise ValueError('V03 duplicate work reference')
    for work_id in ref.native_work_reference_ids:
        matches = [m for m in ledger.work_mentions if m.mention_id == work_id]
        if len(matches) != 1 or work_id != packet.event.object_mention_id:
            raise ValueError('V03 actual same event work reference')
    literal_links = packet.literal_evidence
    for literal in (v for v in walk(carrier) if type(v) is T.SourceLiteralSpanDraft and v.status == 'OBSERVED'):
        links = [link for link in literal_links if type(link) is LiteralEvidence and link.draft is literal]
        if len(links) != 1:
            raise ValueError('V01 missing/duplicate actual literal evidence reference')
        link = links[0]
        span, source = link.native_span, link.native_source
        exact_native(span, 'EditionNativeSpan', binding)
        exact_native(source, 'EditionNativeSource', binding)
        if not object_present(source, ledger.native_sources):
            raise ValueError('V01 source object outside ledger')
        if literal.source_id != source.source_id or literal.source_index != source.source_index or literal.source_role != source.source_role or source.source_role not in {'post_title', 'post_body', 'comment'}:
            raise ValueError('V01 source identity/index/role')
        if span.status != 'OBSERVED' or span.source_id != source.source_id or span.source_index != source.source_index:
            raise ValueError('V01 native span not observed on same source')
        if literal.source_raw_bytes_sha256 != source.raw_text_sha256 or hashlib.sha256(source.raw_text.encode('utf8')).hexdigest() != source.raw_text_sha256:
            raise ValueError('V01 actual source bytes SHA')
        if literal.boundary_map_sha256 != hashlib.sha256(canonical(source.boundary_map)).hexdigest():
            raise ValueError('V01 actual source boundary map SHA')
        if (literal.coordinate_system != span.coordinate_system or span.coordinate_system != source.coordinate_system
            or literal.raw_coordinate_system != span.raw_coordinate_system or span.raw_coordinate_system != source.raw_coordinate_system):
            raise ValueError('V01 coordinate systems')
        for points, text, native_points, native_text, whole in ((literal.raw_span, literal.raw_text, span.raw_span, span.raw_text, source.raw_text),
                (literal.used_span, literal.used_text, span.used_span, span.used_text, source.used_text)):
            if points != native_points or text != native_text or points is None or not 0 <= points[0] <= points[1] <= len(whole) or whole[slice(*points)] != text:
                raise ValueError('V01 exact native span/source slice')
        boundary = dict(source.boundary_map)
        if boundary.get(literal.used_span[0]) != literal.raw_span[0] or boundary.get(literal.used_span[1]) != literal.raw_span[1]:
            raise ValueError('V01 raw/used exact boundary linkage')
    for np in (v for v in walk(carrier) if type(v) is T.NativeNPDraft and v.status == 'OBSERVED'):
        links = [link for link in packet.np_evidence if type(link) is NPEvidence and link.draft is np]
        if len(links) != 1:
            raise ValueError('V02 actual NP evidence reference')
        native = links[0].native_np
        exact_native(native, 'EditionNativeNP', binding)
        if native.status != 'OBSERVED' or np.governed_predicate_ids != native.governed_predicate_ids or not np.governed_predicate_ids or len(np.governed_predicate_ids) != len(set(np.governed_predicate_ids)):
            raise ValueError('V02 exact observed NP governance')
        full, head = np.full_np, np.head
        source_keys = ('source_id', 'source_index', 'source_role', 'source_raw_bytes_sha256', 'boundary_map_sha256', 'coordinate_system', 'raw_coordinate_system')
        if full.status != 'OBSERVED' or head.status != 'OBSERVED' or any(getattr(full, k) != getattr(head, k) for k in source_keys):
            raise ValueError('V02 full NP/head same source')
        if not full.raw_span[0] <= head.raw_span[0] <= head.raw_span[1] <= full.raw_span[1] or not full.used_span[0] <= head.used_span[0] <= head.used_span[1] <= full.used_span[1]:
            raise ValueError('V02 full NP/head containment')
        for draft, actual in ((full, native.full_np), (head, native.head)):
            if not any(link.draft is draft and link.native_span is actual for link in literal_links):
                raise ValueError('V02 actual native NP children identity')
        if any(len([p for p in ledger.predicates if p.predicate_id == pid]) != 1 for pid in np.governed_predicate_ids):
            raise ValueError('V02 native predicate ID resolution')
    expected_relations = {'record_assertion_source': 'RECORD_ASSERTION', 'reported_reading_content_source': 'EMBEDDED_READING_CONTENT',
        'record_owner_np': 'EXPLICIT_POSSESSIVE_OWNER', **ROLES}
    for field in FIELDS[:7]:
        observation = getattr(carrier, field)
        if field in ROLES and observation.role != ROLES[field]:
            raise ValueError('V04 root role const ' + field)
        if observation.status != 'OBSERVED':
            continue
        links = [e for e in packet.field_evidence if type(e) is FieldEvidence and e.field == field]
        if len(links) != 1 or links[0].record_object is not packet.record_object or links[0].relation != expected_relations[field]:
            raise ValueError('V04/V06 explicit same-record role relation evidence ' + field)
        evidence = links[0]
        exact_native(evidence.predicate, 'EditionSourcePredicate', binding)
        exact_native(evidence.event, 'EditionSourceEvent', binding)
        if not object_present(evidence.predicate, ledger.predicates) or not object_present(evidence.event, ledger.events) or evidence.event.predicate_id != evidence.predicate.predicate_id:
            raise ValueError('V04 actual role predicate/event relation')
        if not evidence.proofs or any(not object_present(p, tuple(link.native_span for link in literal_links)) for p in evidence.proofs):
            raise ValueError('V04/V06 role direct native proofs')
        if field in FIELDS[:2]:
            if not any(link.draft is observation.literal and object_present(link.native_span, evidence.proofs) for link in literal_links):
                raise ValueError('V06 literal field is not the declared producer field evidence')
        elif field == 'record_owner_np':
            if evidence.subject_np is None or not any(e.draft is observation.np and e.native_np is evidence.subject_np for e in packet.np_evidence):
                raise ValueError('V06 explicit possessive NP identity, generic record NP is insufficient')
        # Embedded relation may use a different predicate; require the actual object ancestry.
        objects = {o.object_id: o for o in ledger.objects}
        oid, visited = evidence.event.object_id, set()
        while oid and oid != packet.record_object.object_id and oid not in visited:
            visited.add(oid)
            obj = objects.get(oid)
            oid = obj.parent_object_id if obj is not None else ''
        if oid != packet.record_object.object_id:
            raise ValueError('V04 embedded/role event is not on this record or its actual child object')
        if field in ROLES:
            if observation.record_object_id != ref.record_object_id or observation.governing_predicate_id != evidence.predicate.predicate_id:
                raise ValueError('V04 role same record/predicate')
            if observation.subject_np is None or evidence.subject_np is None or observation.subject_np.status != 'OBSERVED' or evidence.predicate.predicate_id not in observation.subject_np.governed_predicate_ids:
                raise ValueError('V02 role subject NP governance not observed')
            if not any(e.draft is observation.subject_np and e.native_np is evidence.subject_np for e in packet.np_evidence):
                raise ValueError('V04 actual subject NP identity')
            if observation.entity_literal != evidence.entity_literal or not observation.entity_literal:
                raise ValueError('V04 explicit producer entity relation; no text/name inference')
            if any(not any(link.draft is p and object_present(link.native_span, evidence.proofs) for link in literal_links) for p in observation.proofs):
                raise ValueError('V04 role proofs not attached to same producer field')
        subject_children = ((observation.subject_np.full_np, observation.subject_np.head) if field in ROLES
                            else (observation.np.full_np, observation.np.head) if field == 'record_owner_np' else ())
        sources = tuple(link.native_source for link in literal_links if any(link.native_span is p for p in evidence.proofs) or any(link.draft is p for p in subject_children))
        needs_edge = any(s.source_role == 'comment' or s.source_id != packet.record_object.source_id for s in sources)
        if needs_edge:
            edge = evidence.cross_source_edge
            if type(edge) is not CrossSourceEdge or edge.record_object is not packet.record_object or edge.predicate is not evidence.predicate or edge.event is not evidence.event or not edge.edge_id or not edge.proofs:
                raise ValueError('V05 actual directed same-record cross-source edge missing')
            if not object_present(edge.anchor_source, ledger.native_sources) or edge.anchor_source.source_id != packet.record_object.source_id or any(not object_present(s, edge.evidence_sources) for s in sources):
                raise ValueError('V05 edge endpoints/source identity')
            if any(not object_present(s, ledger.native_sources) for s in edge.evidence_sources) or any(not object_present(p, tuple(link.native_span for link in literal_links)) for p in edge.proofs):
                raise ValueError('V05 edge endpoint/proofs outside actual source bindings')
            if field in ROLES and observation.cross_source_record_reference_edge_id != edge.edge_id:
                raise ValueError('V05 role edge ID exact reference')
    applicability = carrier.applicability
    if len(applicability) != 8 or len({a.field for a in applicability}) != 8 or {a.field for a in applicability} != set(FIELDS):
        raise ValueError('V07 exact field coverage; original array order preserved')
    diagnostics = []
    for rule in applicability:
        if rule.rule_version != VERSION or rule.rule_id != 'R' + str(FIELDS.index(rule.field) + 1):
            raise ValueError('V07 field/rule version binding')
        if rule.event_class not in {'RECORD_ASSERTION', 'REPORTED_READING_CONTENT', 'RECORD_READING', 'RECORD_COPY', 'CONFIRMATION', 'DIRECT_READING', 'IDENTITY_OR_REVISION', 'UNRESOLVED'} or rule.native_record_relation not in {'PRESENT_SAME_RECORD_PROVED', 'NO_RECORD_RELATION_DECLARED_WITH_SCOPE_PROOF', 'UNKNOWN'}:
            raise ValueError('V07 declared enum')
        if rule.state in {'REQUIRED', 'OUTSIDE_DECLARED_EVENT_SCOPE'} and (rule.event_class == 'UNRESOLVED' or not rule.source_proofs or any(p.status != 'OBSERVED' for p in rule.source_proofs)):
            raise ValueError('V07 known event and observed scope proof form')
        if rule.state == 'REQUIRED' and rule.field != 'annotation_envelope_reference' and rule.native_record_relation != 'PRESENT_SAME_RECORD_PROVED':
            raise ValueError('V07 required R1-R7 relation form')
        if rule.state == 'OUTSIDE_DECLARED_EVENT_SCOPE' and (rule.native_record_relation != 'NO_RECORD_RELATION_DECLARED_WITH_SCOPE_PROOF' or not rule.reason):
            raise ValueError('V07 outside scope declaration form')
        if rule.state == 'UNRESOLVED' and not rule.reason:
            raise ValueError('V07 unresolved reason absent')
        if rule.state == 'OUTSIDE_DECLARED_EVENT_SCOPE':
            if rule.field != 'annotation_envelope_reference' and getattr(carrier, rule.field).status == 'OBSERVED':
                diagnostics.append({'check': 'V07', 'field': rule.field, 'status': 'PROVENANCE_FAILURE', 'reason': 'NO_RECORD_RELATION declaration contradicts observed same-record field; original declaration retained'})
            else:
                diagnostics.append({'check': 'V07', 'field': rule.field, 'status': 'UNSUPPORTED', 'reason': 'approved applicability matrix absent; outside never authorized'})
        elif rule.state == 'UNRESOLVED' or rule.native_record_relation == 'UNKNOWN':
            diagnostics.append({'check': 'V07', 'field': rule.field, 'status': 'NOT_OBSERVED', 'reason': rule.reason})
        elif rule.state == 'REQUIRED':
            diagnostics.append({'check': 'V07', 'field': rule.field, 'status': 'NOT_OBSERVED', 'reason': 'future semantic applicability adoption pending; source form alone insufficient'})
        else:
            raise ValueError('V07 applicability enum')
    diagnostics.append({'check': 'V08', 'status': 'NOT_OBSERVED', 'reason': 'carrier transmission assertions preserved; actual session evidence reported separately'})
    diagnostics.append({'check': 'V04_V06_SEMANTIC_AUTHORITY', 'status': 'NOT_OBSERVED', 'reason': 'explicit future producer relation declaration is transported; parser semantic adoption and independent role judgment pending'})
    return tuple(diagnostics)

def prepare_pass(ledger, producer, product_binding, typed_binding):
    verify_module(product_binding, NATIVE_CLASSES)
    verify_module(typed_binding, CLASSES)
    if typed_binding.module is not T:
        raise ValueError('exact imported nine-class module binding')
    exact_native(ledger, 'EditionSourceLedger', product_binding)
    for records, name, id_field in ((ledger.objects, 'EditionSourceObject', 'object_id'),
            (ledger.predicates, 'EditionSourcePredicate', 'predicate_id'), (ledger.events, 'EditionSourceEvent', 'event_id'),
            (ledger.native_sources, 'EditionNativeSource', 'source_id')):
        identifiers = []
        for value in records:
            exact_native(value, name, product_binding)
            identifiers.append(getattr(value, id_field))
        if len(identifiers) != len(set(identifiers)):
            raise ValueError('native duplicate ID at ' + id_field)
    packets = producer(ledger)
    if type(packets) is not tuple:
        raise ValueError('producer explicit tuple required; None is unsupported, not empty success')
    diagnostics = tuple(check for packet in packets for check in validate_packet(packet, ledger, product_binding))
    keys = [(p.carrier.record_reference.record_object_id, p.carrier.record_reference.predicate_id, p.carrier.record_reference.event_id) for p in packets]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate producer record/predicate/event binding')
    carriers = tuple(packet.carrier for packet in packets)
    augmented = replace(ledger, record_role_provenance=carriers, native_provenance={**ledger.native_provenance,
        'record_role_transport_candidate': {'schema': VERSION, 'producer_source_sha256': product_binding.sha256,
            'typed_source_sha256': typed_binding.sha256,
            'carrier_record_hashes': tuple({'pointer': '/record_role_provenance/' + str(i),
                'sha256': hashlib.sha256(canonical(encode(value))).hexdigest()} for i, value in enumerate(carriers)),
            'original_hash_groups_unmodified': True, 'meaning_GO': False}})
    return RolePass(augmented, packets, product_binding, typed_binding, diagnostics)

def observe_consumed(session, ledger):
    if type(session) is not RolePass or session.ledger is not ledger or session.consumed_ledger is not None:
        raise ValueError('same-pass reducer actual consumed ledger identity')
    session.consumed_ledger = ledger

def bind_return(session, relation):
    exact_native(relation, 'EditionCurrentRelation', session.producer_binding)
    if session.consumed_ledger is not session.ledger or session.returned_relation is not None:
        raise ValueError('actual reducer consumption/return binding missing or repeated')
    if relation.record_role_provenance is not session.ledger.record_role_provenance:
        raise ValueError('actual returned relation carrier tuple identity changed')
    if any(c is not p.carrier for c, p in zip(relation.record_role_provenance, session.packets)) or len(relation.record_role_provenance) != len(session.packets):
        raise ValueError('actual per-record carrier identity changed')
    session.returned_relation = relation
    return CandidateRoleResult(relation, session)

def encode(value):
    if is_dataclass(value):
        return {f.name: encode(getattr(value, f.name)) for f in fields(value)}
    if type(value) is tuple:
        return [encode(v) for v in value]
    if type(value) is dict:
        return {k: encode(v) for k, v in value.items()}
    if value is None or type(value) in (str, int, bool, float):
        return value
    raise TypeError('unsupported serialization type; no fallback string/default')

def serialize_relation(result):
    if type(result) is not CandidateRoleResult or result.session.returned_relation is not result.relation or result.session.consumed_ledger is not result.session.ledger:
        raise ValueError('actual returned object/session identity missing')
    session = result.session
    exact_native(session.ledger, 'EditionSourceLedger', session.producer_binding)
    exact_native(result.relation, 'EditionCurrentRelation', session.producer_binding)
    carriers = result.relation.record_role_provenance
    if (carriers is not session.ledger.record_role_provenance
        or type(carriers) is not tuple or type(session.packets) is not tuple
        or len(carriers) != len(session.packets)
        or any(type(packet) is not ProducerPacket or carrier is not packet.carrier
               for carrier, packet in zip(carriers, session.packets))):
        raise ValueError('serialization current carrier tuple/packet identity changed')
    payload = encode(result.relation)
    if payload.get('record_role_provenance') != [encode(p.carrier) for p in result.session.packets]:
        raise ValueError('all annotation fields changed in serialization')
    return {'schema': 'RECORD_ROLE_TRANSPORT_CANDIDATE1', 'relation': payload,
        'transmission_evidence': {'actual_same_ledger_object': True, 'actual_returned_relation_object': True,
            'carrier_objects_preserved': True, 'all_serialized_fields_preserved': True,
            'producer_module_source_sha256': result.session.producer_binding.sha256,
            'typed_module_source_sha256': result.session.typed_binding.sha256},
        'crossfield_diagnostics': list(result.session.diagnostics), 'meaning_GO': False}
