"""fixture 이행이 무근거 허용이나 공개 confidence 전용으로 흐르지 않는지 확인한다."""
from copy import deepcopy
import pytest
from llm_batch.domain.batch_context import BatchContextMemory
from alias_learning_test_inputs import qualified_learning_input


def result():
    return {'identity': {'is_relevant': True,
        'novel_identity': {'official_title': '새로운 달의 항해', 'confidence': 'Max'},
        'slang_insight': {'detected_term': '검증별칭', 'decoded_term': '새로운 달의 항해',
            'canonical_work_alias': '검증별칭', 'alias_scope': 'pure_work_alias', 'store_in_slang_db': False}}}


@pytest.mark.parametrize('decoder_confidence,verifier_confidence', [('medium', 'high'), ('high', 'medium')])
def test_qualified_fixture_keeps_individual_medium_despite_public_max(decoder_confidence, verifier_confidence):
    original = result()
    before = deepcopy(original)
    row, terms = qualified_learning_input(original, [], decoder_confidence=decoder_confidence,
                                         verifier_confidence=verifier_confidence)
    assert original == before and row['identity']['novel_identity']['confidence'] == 'Max'
    assert terms[0]['best_match']['confidence'] == 'medium'
    memory = BatchContextMemory(enabled=True)
    for _ in range(3):
        memory.learn_from_result(row, decoded_terms=terms)
    key = memory._normalize('검증별칭')
    assert memory.get_abbreviation('검증별칭') is None
    assert memory.pending_abbreviations[key]['confidence'] == 2
    assert memory.pending_abbreviations[key]['allow_pending_promotion'] is False


def test_original_unqualified_shape_is_still_rejected():
    memory = BatchContextMemory(enabled=True)
    row = result()
    before = deepcopy(row)
    memory.learn_from_result(row, decoded_terms=[{'original': '검증별칭', 'best_match': {'title': '새로운 달의 항해', 'confidence': 'high'}}])
    assert memory.resolved_abbreviations == memory.pending_abbreviations == {}
    assert memory.stats['abbreviation_learning_evidence_rejected'] == 1
    assert row == before
