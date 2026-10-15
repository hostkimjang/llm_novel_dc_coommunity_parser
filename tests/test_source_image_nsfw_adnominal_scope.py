"""F2의 직접 관형 관계와 배경 대상을 구분한다. 원형 98사례는 그대로다."""
import hashlib
import json
from pathlib import Path

import pytest

from test_source_image_nsfw_assessment import saved
from test_source_image_nsfw_context_scope import assess


COUNTERS = Path(__file__).parent / 'fixtures/image_nsfw_adnominal_scope_v3.json'
COUNTERS_SHA = 'f2812016eca58836e9cc05d3c426a734ab37a422f4a3eea643463ce046aa45ee'


@pytest.mark.parametrize('index', [0, 1])
def test_reviewer_medical_adnominal_relations_preserve_unevaluated_scope(saved, index):
    raw = COUNTERS.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == COUNTERS_SHA
    fixed = json.loads(raw)
    assert fixed['scope'] == 'STATIC_REVIEW_F2_COUNTEREXAMPLES_NOT_EXECUTED'
    case = fixed['cases'][index]
    assert case['v1_expected_by_static_trace'] == 'NO_POSITIVE_IMAGE_RULE'
    assert case['v2_expected_by_static_trace'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    result = assess(saved, case['ocr_text'], case['visual_summary'])
    assert result['status'] == 'NO_POSITIVE_IMAGE_RULE'
    assert result['evidence'] == [] and result['requires_image_review'] is True
    proofs = result['item_outcomes'][0]['excluded_relations']
    target = next(proof for proof in proofs if proof['rule'] == case['missed_relation'])
    assert target['source_field'] == 'visual_summary'
    lo, hi = target['context_span']
    start, end = target['target_span']
    assert 0 <= lo < hi == start < end <= len(case['visual_summary'])
    assert hashlib.sha256(case['visual_summary'].encode()).hexdigest() == target['text_sha256']
    assert COUNTERS.read_bytes() == raw


@pytest.mark.parametrize('ocr,visual,expected_rule', [
    ('정자 잔뜩 마셔', '교육 교재에 수록된 성인용 만화 장면이다.', 'DOCUMENT_SOURCE_ADNOMINAL'),
    ('제품 표기', '재활 목적으로 사용되는 성인용 기구의 제품 이미지다.', 'MEDICAL_USE_ADNOMINAL'),
])
def test_document_source_and_passive_use_remain_attached_to_target(saved, ocr, visual, expected_rule):
    result = assess(saved, ocr, visual)
    assert result['status'] == 'NO_POSITIVE_IMAGE_RULE'
    assert result['evidence'] == []
    assert any(proof['rule'] == expected_rule
        for proof in result['item_outcomes'][0]['excluded_relations'])


@pytest.mark.parametrize('ocr,visual', [
    ('정자 잔뜩 마셔', '의학 교재에서 발췌한 안내문을 배경에 둔 성적 장면 이미지다.'),
    ('제품 표기', '의료용으로 사용하는 장갑 옆에 성인용 기구의 제품 이미지가 있다.'),
])
def test_adnominal_relation_of_background_object_does_not_veto_foreground(saved, ocr, visual):
    result = assess(saved, ocr, visual)
    assert result['status'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    assert len(result['evidence']) == 1
