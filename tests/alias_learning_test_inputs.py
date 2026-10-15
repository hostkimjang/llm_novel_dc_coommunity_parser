"""구형 시험의 명시 원문·개별 검증 fixture. 합성 입력이며 실제 검색/사람 정답이 아니다."""
from copy import deepcopy
from types import SimpleNamespace


def source_and_experts(title, alias, *, post_id=601, decoder_confidence='high', verifier_confidence='high'):
    # confidence는 공개 identity에서 읽지 않는 독립적인 시험 입력이다.
    source = {'post_id': post_id, 'title': alias + ' 회차 이야기',
        'content_blocks': [{'type': 'text', 'text': title + '의 약칭은 ' + alias + '이다.'}], 'comments': []}
    decoder = {'needs_verification': False, 'decoded_terms': [{'original': alias, 'is_author_name': False,
        'interpretations': [{'type': 'novel_title', 'value': title, 'context_fit': 'high'}],
        'best_match': {'title': title, 'confidence': decoder_confidence}}]}
    verification = {'is_relevant': True, 'novel_identity': {'official_title': title},
        'slang_insight': {'detected_term': alias, 'canonical_work_alias': alias, 'decoded_term': title,
            'decode_verified': True, 'alias_scope': 'pure_work_alias', 'store_in_slang_db': False},
        'relation_judgment': {'relation_type': 'explicit_alias', 'discussion_target': 'specific_work',
            'promotion_decision': 'allow', 'confidence': verifier_confidence}}
    return source, decoder, verification


def qualified_learning_input(result, original_terms, *, decoder_confidence='high', verifier_confidence='high'):
    from llm_batch.agentic_pipeline import AgenticPipeline
    from llm_batch.domain.alias_learning import capture_alias_source
    identity = result['identity']
    title = identity['novel_identity']['official_title']
    slang = identity['slang_insight']
    alias = slang.get('canonical_work_alias') or slang['detected_term']
    source, decoder, verification = source_and_experts(title, alias,
        decoder_confidence=decoder_confidence, verifier_confidence=verifier_confidence)
    roots = {'decoder': decoder, 'verifier': {'verification_result': verification}}
    ctx = SimpleNamespace(post_id=source['post_id'], post_data=deepcopy(source), search_results=[],
        _batch_alias_original_source=capture_alias_source(source),
        get_expert_output=lambda kind: roots.get(getattr(kind, 'value', kind), {}))
    before = deepcopy((result, original_terms, source, roots))
    pipe = object.__new__(AgenticPipeline)
    envelope = pipe._build_batch_context_learning_envelope(ctx)
    assert (result, original_terms, source, roots) == before
    assert len(envelope['decoded_terms']) == 1
    assert envelope['decoded_terms'][0]['original'] == alias
    assert 'learning_evidence' in envelope['decoded_terms'][0]
    qualified = deepcopy(result)
    qualified.update(deepcopy(source))
    # 기존 문장/인물 결합 표면은 그대로 남겨 계속 학습되지 않는지 대조한다.
    return qualified, deepcopy(original_terms) + envelope['decoded_terms']
