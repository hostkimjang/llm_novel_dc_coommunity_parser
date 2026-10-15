"""실제 source consumer의 성립 근거를 native와 같은 사건 ID로 진단에 저장한다."""
import hashlib
import json
from pathlib import Path

# ROOT가 source44 후보의 정확한 test/fixture/product를 같은 격리 tree에 공급한다.
# 실제 consumer·외부 호출 금지 fixture를 재사용하며 native 성공값을 대체하지 않는다.
import test_source44_compound_speaker as source44
from test_source44_compound_speaker import offline  # noqa: F401: pytest autouse fixture
from llm_batch.grounding.source_context_diagnostics import MAX_BYTES


def _bound_packet(path, expected_sha, *, index):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha
    data = json.loads(raw)
    packet = data['packet'] if 'packet' in data else next(p for p in data['rows'] if p['index1'] == index)
    assert packet['index1'] == index and type(packet['post_id']) is int
    assert hashlib.sha256(source44.canonical({'post': packet['source_post'],
        'comments': packet['source_comments']})).hexdigest() == packet['source_canonical_sha256']
    assert hashlib.sha256(source44.canonical(packet['checkpoint_result'])).hexdigest() == packet['result_canonical_sha256']
    return packet, raw


def _assert_native_export_same(ctx, diagnostic, verify, *, expected_status='STORED',
                               expected_reason_codes=(), expected_omitted_counts=None):
    native = ctx._final_source_projection_native
    ledgers = [native.author_ledger, *native.comment_ledgers]
    events = {(ledger.source_id, event.event_id): event for ledger in ledgers for event in ledger.evaluations}
    stored = {(ledger['source_id'], event['event_id']): event
        for ledger in diagnostic['ledgers'] for event in ledger['evaluations']}
    assert events and set(stored) == set(events)
    assert diagnostic['status'] == expected_status
    assert diagnostic['reason_codes'] == list(expected_reason_codes)
    assert diagnostic['omitted_counts'] == ({} if expected_omitted_counts is None else expected_omitted_counts)
    assert diagnostic['publication_authority'] is False
    assert diagnostic['native_verification_status'] == 'NATIVE_CALLBACK_TRUE'
    assert len(source44.canonical(diagnostic)) <= MAX_BYTES
    for key, event in events.items():
        row = stored[key]
        assert row['realization_source'] == event.realization_source
        assert row['realization'] == event.realization
        assert row['evaluation_polarity'] == event.evaluation_polarity
        assert row['final_support'] is event.final_support
        assert row['predicate'] == event.predicate
        assert row['predicate_span'] == list(event.predicate_span)
        assert row['evidence_text'] == event.evidence_text
    assert verify()
    return events, stored


def test_saved44_consumer_native_and_export_keep_negative_judgment_source(tmp_path):
    packet, raw = _bound_packet(source44.FIXTURE, source44.FIXTURE_SHA, index=44)
    candidates = packet['checkpoint_result']['analysis_result']['identity']['title_candidates']
    ctx, identity, notes, diagnostic, verify = source44.consume(tmp_path, post=packet['source_post'],
        comments=packet['source_comments'], candidates=candidates)
    events, stored = _assert_native_export_same(ctx, diagnostic, verify)
    matching = [(key, event) for key, event in events.items()
        if event.evidence_text == source44.ORIGINAL and event.predicate == '좋은']
    assert len(matching) == 1
    key, event = matching[0]
    assert event.realization_source == stored[key]['realization_source'] == 'nominal_judgment_content'
    assert event.realization == 'embedded' and event.final_support is False
    assert event.actor == event.grammatical_subject.actor == 'self'
    assert source44.ORIGINAL in identity.reason + notes
    assert identity.novel_identity is None
    assert identity.model_dump()['title_candidates'] == candidates
    assert source44.FIXTURE.read_bytes() == raw


def test_explicit_positive_source_consumer_keeps_positive_event_source(tmp_path):
    # 실제 원형의 재생이라고 주장하지 않는 독립 긍정 기능 입력이다.
    text = '이 작품은 좋다.'
    ctx, identity, notes, diagnostic, verify = source44.consume(tmp_path, body=[text])
    events, stored = _assert_native_export_same(ctx, diagnostic, verify)
    matching = [(key, event) for key, event in events.items()
        if event.evidence_kind == 'cue' and event.predicate.startswith('좋다')]
    assert matching
    for key, event in matching:
        assert event.realization == 'actual' and event.final_support is True
        assert event.realization_source == stored[key]['realization_source'] == 'cue_token_construction'
        assert event.evaluation_polarity == 'pos' and event.polarity == 'positive'
    assert identity.novel_identity is None and verify()


def test_saved74_nominal_cue_source_consumer_keeps_observation_source(tmp_path):
    path = Path(__file__).parent / 'fixtures/nominal_cue13_74_saved.json'
    packet, raw = _bound_packet(path, 'a8598914e12514f2ba93988841f8fde63f48d3cbf10bb292ac623295cdbaf0af', index=74)
    candidates = packet['checkpoint_result']['analysis_result']['identity']['title_candidates']
    ctx, identity, notes, diagnostic, verify = source44.consume(tmp_path, post=packet['source_post'],
        comments=packet['source_comments'], candidates=candidates)
    events, stored = _assert_native_export_same(ctx, diagnostic, verify,
        expected_status='TRUNCATED', expected_reason_codes=('FIELD_LIMIT',),
        expected_omitted_counts={'ledgers.graph_edges.items': 1})
    matching = [(key, event) for key, event in events.items() if event.predicate == '학창시절첫사랑꼬시기']
    assert len(matching) == 1
    key, event = matching[0]
    assert event.realization_source == stored[key]['realization_source'] == 'nominal_cue_observation'
    assert event.realization == 'embedded' and event.final_support is False
    assert event.evaluation_polarity == 'pos' and event.polarity == 'positive'
    assert event.evidence_text == '동창회나가서 학창시절첫사랑꼬시기'
    assert event.evidence_text in identity.reason + notes
    assert identity.novel_identity is None
    assert identity.model_dump()['title_candidates'] == candidates
    assert path.read_bytes() == raw
