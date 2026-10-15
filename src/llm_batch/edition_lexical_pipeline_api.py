"""One actual lexical ledger build -> same consumed relation -> exact serialization."""
from dataclasses import dataclass, replace, fields, is_dataclass
import hashlib
import json
from . import promotion_gate as P
from . import record_role_transport as R
from . import record_role_normalizer as N
from .record_role_lexical_producer import packets_from_native_ledger


def encode_actual_value(value):
    """Serialize actual JSON arrays and typed records without semantic fallback."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: encode_actual_value(getattr(value, f.name)) for f in fields(value)}
    if type(value) in (tuple, list):
        return [encode_actual_value(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError('actual serialization requires string mapping keys')
        return {key: encode_actual_value(item) for key, item in value.items()}
    if value is None or type(value) in (str, int, bool, float):
        return value
    raise TypeError('unsupported actual serialization type; no string/default fallback')


@dataclass(frozen=True)
class LexicalPublicationBundle:
    state: object
    result: object
    actual_base_ledger: object
    source_origins: tuple
    serialized_payload: dict
    serialized_bytes: bytes
    serialized_sha256: str
    normalized: dict
    support_diagnostics: tuple


def verify_captured_bundle(bundle):
    """Pure exact transmission checks; no parser/role/authority reconstruction."""
    if type(bundle.serialized_bytes) is not bytes:
        raise TypeError('native bundle captured bytes type')
    actual_sha = hashlib.sha256(bundle.serialized_bytes).hexdigest()
    if type(bundle.serialized_sha256) is not str or actual_sha != bundle.serialized_sha256:
        raise ValueError('native bundle captured bytes SHA mismatch')
    if R.canonical(bundle.serialized_payload) != bundle.serialized_bytes:
        raise ValueError('native bundle whole payload changed')
    captured = json.loads(bundle.serialized_bytes)
    expected_keys = {'publication_state','record_relation','native_ledger','source_origins','meaning_GO'}
    if type(captured) is not dict or set(captured) != expected_keys:
        raise ValueError('native bundle captured outer fields differ')
    # This existing transport checks actual consumed/returned ledger and carrier object identities.
    fresh_relation = R.serialize_relation(bundle.result)
    if R.canonical(fresh_relation) != R.canonical(captured['record_relation']):
        raise ValueError('native bundle serialized relation changed')
    if R.canonical(encode_actual_value(bundle.state.to_dict())) != R.canonical(captured['publication_state']):
        raise ValueError('native bundle captured state differs from actual state')
    if R.canonical(encode_actual_value(bundle.result.session.ledger)) != R.canonical(captured['native_ledger']):
        raise ValueError('native bundle captured ledger differs from actual consumed ledger')
    if R.canonical(encode_actual_value(bundle.source_origins)) != R.canonical(captured['source_origins']):
        raise ValueError('native bundle captured origins differ from actual origins')
    if captured['meaning_GO'] is not False:
        raise ValueError('native bundle preparation meaning flag changed')
    fresh_normalized = N.normalize_record_roles(captured['record_relation']['relation'], actual_sha,
                                                prefix='/record_relation/relation')
    if (R.canonical(encode_actual_value(fresh_normalized)) !=
        R.canonical(encode_actual_value(bundle.normalized))):
        raise ValueError('native bundle normalized value differs from captured bytes recomputation')
    return captured, fresh_normalized


def publication_from_lexical_sources(sources, candidate_title, competing_variant_titles, source_checked,
                                     source_origins, product_binding, typed_binding):
    chunks = tuple(sources)
    selected = tuple(row for row in source_origins if row['selected'])
    if len(chunks) != len(selected) or any(row['selected_index'] != i or
        (row['source_role'], row['selected_text']) != chunks[i] for i, row in enumerate(selected)):
        raise ValueError('source origin recipe and actual chunks differ')
    base = P._edition_source_ledger(chunks)  # The sole lexical ledger build.
    if len(base.native_sources) != len(selected) or any(s.raw_text != selected[i]['selected_text'] or s.source_role != selected[i]['source_role']
           or s.source_index != i for i, s in enumerate(base.native_sources)):
        raise ValueError('actual native source/raw origin binding differs')
    base = replace(base, native_provenance={**base.native_provenance, 'original_input_origin_inventory': source_origins})
    session = R.prepare_pass(base, packets_from_native_ledger, product_binding, typed_binding)
    # prepare_pass adds carriers by replace; this same augmented object is actually consumed once.
    relation = P._edition_current_relation_from_ledger(session.ledger, chunks, candidate_title, record_role_session=session)
    result = R.bind_return(session, relation)
    markers = relation.markers if relation.status == 'affirmed' else ()
    state = P.EditionPublicationState(source_checked, markers, tuple(competing_variant_titles), relation)
    if state.current_relation is not result.relation:
        raise ValueError('publication state did not return actual relation object')
    packet_payload = R.serialize_relation(result)
    payload = {'publication_state': state.to_dict(), 'record_relation': packet_payload,
               'native_ledger': encode_actual_value(session.ledger),
               'source_origins': encode_actual_value(source_origins), 'meaning_GO': False}
    raw = R.canonical(payload); artifact_sha = hashlib.sha256(raw).hexdigest()
    # Normalize the exact captured serializer bytes; no hidden enum/leaf/source derivation.
    parsed = json.loads(raw)
    normalized = N.normalize_record_roles(parsed['record_relation']['relation'], artifact_sha,
                                          prefix='/record_relation/relation')
    diagnostics = []
    for row in base.record_role_lexical_evidence:
        if row['status'] != 'OBSERVED':
            diagnostics.append({'status': 'NOT_OBSERVED', 'reason': row['reason']})
    if not session.packets:
        diagnostics.append({'status': 'NOT_OBSERVED', 'reason': 'no_supported_actual_record_anchor; empty_is_not_PASS'})
    return LexicalPublicationBundle(state, result, base, source_origins, payload, raw, artifact_sha,
        normalized, tuple(diagnostics) + session.diagnostics)
