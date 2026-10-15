"""제외 관계의 기능 대조. 원형 83사례는 별도 파일에 그대로 보존한다."""
import hashlib
import json
from pathlib import Path

import pytest

from test_source_image_nsfw_assessment import saved, prepared, canonical


COUNTERS = Path(__file__).parent / 'fixtures/image_nsfw_context_scope_v2.json'
COUNTERS_SHA = 'aa9d38692e5d91daf65c0675c0fd81ac05159e5050e7cb63a0e0b75af53fe72b'


def assess(saved, ocr, visual):
    pipe, ctx, _ = prepared(saved, 49, inject=False)
    ctx.post_data['image_enrichment'][0].update(ocr_text=ocr, visual_summary=visual)
    pipe._inject_image_enrichment_blocks(ctx.post_data)
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs])
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result['binding_status'] == 'BOUND'
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs]) == before
    return result


@pytest.mark.parametrize('index', [0, 1])
def test_independent_review_counterexamples_keep_existing_positive_relation(saved, index):
    raw = COUNTERS.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == COUNTERS_SHA
    fixture = json.loads(raw)
    assert fixture['scope'] == 'STATIC_REVIEW_COUNTEREXAMPLES_NOT_EXECUTED'
    case = fixture['cases'][index]
    assert case['baseline_helper_expected_by_static_trace'] is True
    assert case['candidate_helper_expected_by_static_trace'] is False
    result = assess(saved, case['ocr_text'], case['visual_summary'])
    assert result['status'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    assert len(result['evidence']) == 1
    assert COUNTERS.read_bytes() == raw


@pytest.mark.parametrize('ocr,visual', [
    ('정자 잔뜩 마셔', '배경에 신발이 놓여 있고 성적 장면을 묘사한 이미지다.'),
    ('', '성인용 기구이며 성기 모양인 제품 이미지이고 가격 표시는 없다.'),
    ('정자 잔뜩 마셔', '배경에 교육 교재가 놓여 있다. 성적 장면을 묘사한 이미지다.'),
    ('제품 표기', '성인용 기구의 제품 이미지다. 배경에 의료용 신발이 놓여 있다.'),
    ('제품 표기', '성인용 기구의 제품 이미지다. 이 제품은 신발과 같은 색상이다.'),
    ('제품 표기', '성인용 기구의 제품 이미지다. 이 제품은 의료용 모형 옆에 놓여 있다.'),
])
def test_unrelated_background_negation_and_comparison_do_not_cancel_positive(saved, ocr, visual):
    result = assess(saved, ocr, visual)
    assert result['status'] == 'SOURCE_IMAGE_RULE_POSITIVE'
    assert len(result['evidence']) == 1


@pytest.mark.parametrize('ocr,visual', [
    ('정자 잔뜩 마셔', '성적 장면이 아니다.'),
    ('정자 잔뜩 마셔', '성인용 만화 장면이 없으며 설명용 교재다.'),
    ('제품 표기', '성인용 기구가 아니라 신발이다. 제품 이미지다.'),
    ('PRODUCT', 'Medical dildo 제품 이미지다.'),
    ('성교육 교재', '성인용 기구의 제품 이미지다.'),
    ('', '성인용 기구이며 성기 모양인 제품 이미지다. 이 제품은 의료용 모형이다.'),
    ('', '성인용 기구이며 성기 모양인 제품 이미지다. 이 제품은 신발이다.'),
])
def test_exclusion_stays_bound_to_the_content_or_product_identity(saved, ocr, visual):
    result = assess(saved, ocr, visual)
    assert result['status'] == 'NO_POSITIVE_IMAGE_RULE'
    assert result['requires_image_review'] is True
    assert result['evidence'] == []
    exclusions = result['item_outcomes'][0]['excluded_relations']
    assert exclusions
    sources = {'ocr_text': ocr, 'visual_summary': visual}
    for proof in exclusions:
        text = sources[proof['source_field']]
        lo, hi = proof['context_span']
        assert 0 <= lo < hi <= len(text)
        assert hashlib.sha256(text.encode()).hexdigest() == proof['text_sha256']
        if proof['target_span'] is None:
            assert proof['rule'] == 'WHOLE_OCR_DOCUMENT_LABEL'
            assert proof['source_field'] == 'ocr_text'
        else:
            start, end = proof['target_span']
            assert 0 <= start < end <= len(text)
