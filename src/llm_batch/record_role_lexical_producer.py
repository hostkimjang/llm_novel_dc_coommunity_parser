"""Actual native parser evidence -> immutable typed packet. No text semantic reparse."""
from . import record_role_types as T
from . import record_role_transport as R


def packets_from_native_ledger(ledger):
    """Only consume native evidence constructed in the same lexical ledger build."""
    packets = []
    for index, item in enumerate(ledger.record_role_lexical_evidence):
        if item['status'] != 'OBSERVED':
            continue
        record, predicate, event = item['record_object'], item['predicate'], item['event']
        if not any(record is o for o in ledger.objects) or not any(predicate is p for p in ledger.predicates) or not any(event is e for e in ledger.events):
            raise ValueError('lexical evidence anchor outside same actual ledger')
        literals, nps, field_evidence = [], [], []
        literal_cache, np_cache = {}, {}

        def literal(span):
            if span is None or span.status != 'OBSERVED':
                return None
            if id(span) in literal_cache:
                return literal_cache[id(span)]
            sources = [s for s in ledger.native_sources if s.source_id == span.source_id and s.source_index == span.source_index]
            if len(sources) != 1:
                raise ValueError('native literal source identity ambiguous')
            source = sources[0]
            value = T.SourceLiteralSpanDraft(source.source_id, source.source_index, source.source_role,
                source.raw_text_sha256, span.raw_span, span.raw_text, span.used_span, span.used_text,
                R.hashlib.sha256(R.canonical(source.boundary_map)).hexdigest(),
                span.coordinate_system, span.raw_coordinate_system, span.status, span.reason)
            literals.append(R.LiteralEvidence(value, span, source)); literal_cache[id(span)] = value
            return value

        def native_np(np):
            if np is None or np.status != 'OBSERVED':
                return None
            if id(np) in np_cache:
                return np_cache[id(np)]
            full, head = literal(np.full_np), literal(np.head)
            if full is None or head is None:
                return None
            value = T.NativeNPDraft(full, head, np.governed_predicate_ids, np.status, np.reason)
            nps.append(R.NPEvidence(value, np)); np_cache[id(np)] = value
            return value

        source = next(s for s in ledger.native_sources if s.source_id == record.source_id)
        field_support = source.source_role != 'comment'
        reason = 'direct_native_parser_evidence; independent_semantic_adoption_NOT_OBSERVED'
        unsupported = 'actual_directed_comment_record_reference_edge_NOT_OBSERVED' if not field_support else 'native_parser_did_not_prove_this_role'
        unknown_literal = T.LiteralObservationDraft(None, 'NOT_OBSERVED', unsupported)
        statement = literal(item['statement']) if field_support else None
        content = literal(item['content_span']) if field_support and item['content_event'] is not None else None
        owner = native_np(item['owner_np']) if field_support else None
        reference_proofs = tuple(v for v in (literal(predicate.native_full_predicate), literal(record.native_span)) if v is not None)
        reference = T.NativeRecordReferenceDraft(record.object_id, predicate.predicate_id, event.event_id,
            (event.object_mention_id,) if event.object_mention_id else (),
            'OBSERVED' if reference_proofs else 'NOT_OBSERVED', reference_proofs,
            'actual_unique_record_predicate_historical_anchor; no_publication_authority')
        r1 = T.LiteralObservationDraft(statement, 'OBSERVED', reason) if statement else unknown_literal
        r2 = T.LiteralObservationDraft(content, 'OBSERVED', reason) if content else unknown_literal
        own = T.NPObservationDraft(owner, 'OBSERVED', reason) if owner else T.NPObservationDraft(None, 'NOT_OBSERVED', unsupported)
        if statement:
            field_evidence.append(R.FieldEvidence('record_assertion_source', record, predicate, event, None, None,
                (item['statement'],), 'RECORD_ASSERTION', None))
        if content:
            field_evidence.append(R.FieldEvidence('reported_reading_content_source', record, item['content_predicate'],
                item['content_event'], None, None, (item['content_span'],), 'EMBEDDED_READING_CONTENT', None))
        if owner:
            field_evidence.append(R.FieldEvidence('record_owner_np', record, predicate, event, item['owner_np'], None,
                (item['owner_np'].full_np, item['owner_np'].head), 'EXPLICIT_POSSESSIVE_OWNER', None))

        roles = {}
        for field, role in R.ROLES.items():
            native = item['writer_np'] if field == 'record_writer' else item['content_np'] if field == 'content_reader' else None
            governing = predicate if field == 'record_writer' else item['content_predicate']
            role_event = event if field == 'record_writer' else item['content_event']
            np = native_np(native) if field_support and governing is not None and role_event is not None else None
            if np is None:
                roles[field] = T.RecordRoleBindingDraft(role, None, None, record.object_id, None,
                    'NOT_OBSERVED', (), None, unsupported)
                continue
            # Entity literal is the actual NP head; no owner->actor, reader->writer, or identity alias.
            entity = native.head.raw_text
            roles[field] = T.RecordRoleBindingDraft(role, entity, np, record.object_id, governing.predicate_id,
                'OBSERVED', (np.full_np, np.head), None, reason)
            field_evidence.append(R.FieldEvidence(field, record, governing, role_event, native, entity,
                (native.full_np, native.head), role, None))
        rules = tuple(T.FutureApplicabilityDraft(field, 'RECORD_ASSERTION', 'UNRESOLVED', R.VERSION,
            'R' + str(i + 1), 'UNKNOWN', (), 'semantic applicability matrix/adoption not approved; no old203 N/A')
            for i, field in enumerate(R.FIELDS))
        transmission = T.SameRecordTransmissionDraft(record.object_id, predicate.predicate_id, event.event_id,
            '/ledger/record_role_lexical_evidence/' + str(index), None, None, None, None, None,
            'NOT_OBSERVED', 'NOT_OBSERVED', 'NOT_OBSERVED',
            'actual session and serialization proof lives separately; no prefilled samepass PASS')
        carrier = T.RecordRoleProvenanceDraft(R.VERSION, reference, r1, r2, own, roles['record_writer'],
            roles['content_reader'], roles['record_reader'], roles['verifier'], unknown_literal, rules, transmission)
        packets.append(R.ProducerPacket(carrier, record, predicate, event, tuple(literals), tuple(nps), tuple(field_evidence)))
    return tuple(packets)
