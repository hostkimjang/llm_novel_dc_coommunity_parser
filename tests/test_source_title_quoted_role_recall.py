"""표제 후보와 독서 사실의 범위를 구분한다. 기존 baseline 기대는 변경하지 않는다."""
from copy import deepcopy
import hashlib

import pytest
from llm_batch.domain.models import DetectedTitle
from llm_batch.grounding.source_title_hypothesis import title_hypothesis_source_support
from test_source_surface_hypothesis_candidates import context, interpretation, seed, candidate_titles


def producer_candidate_input(alias, title):
    """기존 Decoder의 best_match/candidates 진입 조건을 만족시키는 합성 입력.

    별책과 임의 표제는 약어 점수가0이라 interpretations-only로는 후보가 안 생긴다.
    후보 입력만 명시하며 원문 역할·제외·공개 guard는 실제 제품이 판단한다.
    저장된34/35 전문가나 원문 fixture를 변경하는 함수가 아니다.
    """
    value=interpretation(alias,title)
    term=value['decoded_terms'][0]
    term['best_match']={'title':title,'confidence':'medium'}
    term['candidates']=[{'official_title':title,'morphological_score':0.8}]
    return value


@pytest.mark.parametrize('title,body', [
    ('여러 장르 등의 약자 추정', "소설 '여러 장르 등의 약자 추정'을 읽었다"),
    ('여러 장르 등의 약자 추정', '나는 「여러 장르 등의 약자 추정」를 읽었다'),
    ('주무시기 전에 무엇을 하셨나요?(추정)', '나는 “주무시기 전에 무엇을 하셨나요?(추정)”를 읽었다'),
    ('그는 다시 돌아온다.(추정)', '소설 『그는 다시 돌아온다.(추정)』를 읽었다'),
])
def test_exact_quoted_work_name_with_object_particle_keeps_original_reading_role(tmp_path,title,body):
    pipe,ctx,_=context(tmp_path,title='다른 작품을 읽었다',body=[body])
    # 기존 실제 실패의 소비 경로를 먼저 확인한다. 새 공식검색/모델 해석으로 보충하지 않는다.
    assert pipe._has_literal_author_title_occurrence(ctx,title) is True
    assert pipe._is_unbound_title_meta_explanation(ctx,title) is False
    proof=title_hypothesis_source_support(ctx,'별책',title)
    assert proof['kind']=='author_work_name'
    assert proof['raw_text'][slice(*proof['raw_span'])]==title
    assert proof['publication_authority'] is False and proof['supports_publish'] is False
    value=interpretation('별책',title)
    value['decoded_terms'][0]['best_match']={'title':title,'confidence':'medium'}
    value['decoded_terms'][0]['candidates']=[{'official_title':title,'morphological_score':0.8}]
    seed(ctx,value)
    assert title in candidate_titles(ctx)


@pytest.mark.parametrize('body', [
    ["친구가 '여러 장르 등의 약자 추정'이라고 말했다"],
    ['나는 「여러 장르 등의 약자 추정」를 읽었다면'],
    ["'여러 장르 등의 약자 추정'이라는 풀이일 뿐 작품명은 아니다"],
    ['“', '나는 「여러 장르 등의 약자 추정」를 읽었다.', '”라는 말은 틀렸다.'],
    ["소설 '여러 장르 등의 약자 추정'을 읽었다. 정정, 아니다."],
    ["'여러 장르 등의 약자 추정'이라는 설명을 읽었다"],
])
def test_delimited_surface_does_not_bypass_speech_negation_hypothesis_or_meta_scope(tmp_path,body):
    title='여러 장르 등의 약자 추정'
    pipe,ctx,_=context(tmp_path,title='단어 뜻이 궁금하다',body=body)
    assert title_hypothesis_source_support(ctx,'별책',title) is None
    assert pipe._is_unbound_title_meta_explanation(ctx,title) is True


@pytest.mark.parametrize('title,body,mode,negative', [
    ('여러 장르 등의 약자 추정', "소설 '여러 장르 등의 약자 추정'을 읽지 않았다", 'negative', True),
    ('여러 장르 등의 약자 추정', "소설 '여러 장르 등의 약자 추정'을 읽었나?", 'question', False),
    ('여러 장르 등의 약자 추정', '나는 웹소설 「여러 장르 등의 약자 추정」를 읽지 않음.', 'negative', True),
    ('여러 장르 등의 약자 추정', '작품 여러 장르 등의 약자 추정을 안 읽었다.', 'negative', True),
    ('여러 장르 등의 약자 추정', '저는 소설 《여러 장르 등의 약자 추정》을 못 읽었습니다.', 'negative', True),
    ('여러 장르 등의 약자 추정', '소설 “여러 장르 등의 약자 추정”을 읽을까?', 'question', False),
    ('여러 장르 등의 약자 추정', '웹소설 「여러 장르 등의 약자 추정」를 읽었나요', 'question', False),
    ('여러 장르 등의 약자 추정', '소설 「여러 장르 등의 약자 추정」를 읽지 않았다?', 'question', True),
    ('여러 장르 등의 약자 추정', '소설 「여러 장르 등의 약자 추정」를 읽을 예정이다.', 'planned', False),
    ('여러 장르 등의 약자 추정', '내가 작품 ‘여러 장르 등의 약자 추정’을 읽을 계획임.', 'planned', False),
    ('주무시기 전에 무엇을 하셨나요?(추정)', '소설 “주무시기 전에 무엇을 하셨나요?(추정)”를 읽지 않았다.', 'negative', True),
    ('그는 다시 돌아온다.(추정)', '소설 『그는 다시 돌아온다.(추정)』를 읽을 예정이다.', 'planned', False),
])
def test_explicit_work_object_preserves_candidate_without_asserting_reading_or_publication(tmp_path,title,body,mode,negative):
    pipe,ctx,_=context(tmp_path,title='이런 히로인 나오는 소설 추천 좀',body=[body])
    source_before=deepcopy(ctx.post_data)
    captured_before=deepcopy(ctx._final_source_original_inputs)
    proof=title_hypothesis_source_support(ctx,'별책',title)
    assert proof['kind']=='author_work_name'
    assert proof['basis']=='explicit_work_object_name_without_reading_assertion'
    assert proof['origin']=='body_line'
    assert proof['raw_text']==body
    assert proof['raw_text'][slice(*proof['raw_span'])]==title
    assert proof['source_sha256']==hashlib.sha256(body.encode()).hexdigest()
    assert any(row['origin']==proof['origin'] and row['original_index']==proof['original_index']
               and row['raw_text']==body and row['caller_disposition']=='passed_to_source'
               for row in captured_before)
    role=proof['role_evidence']
    assert role['kind']=='explicit_work_object_name'
    assert role['scope']=='candidate_name_only'
    assert role['reading_action_mode']==mode
    assert role['reading_predicate_negative'] is negative
    assert role['reading_action_asserted'] is False
    assert role['supports_current_work'] is False and role['counts_as_core'] is False
    for item in (proof,role):
        assert item['publication_authority'] is False and item['supports_publish'] is False
    for field,span in role['raw_spans'].items():
        assert body[slice(*span)]==role['raw_evidence'][field]
    assert role['raw_evidence']['work_marker'] in {'소설','웹소설','작품'}
    assert role['raw_evidence']['object_particle'] in {'을','를'}
    a,b=role['raw_spans']['named_object']
    assert a<=proof['raw_span'][0]<proof['raw_span'][1]<=b
    assert pipe._has_literal_author_title_occurrence(ctx,title) is True
    assert pipe._is_unbound_title_meta_explanation(ctx,title) is False
    value=producer_candidate_input('별책',title)
    seed(ctx,value)
    assert title in candidate_titles(ctx)
    # 실제 공개 예외는 원문 행위 parser를 그대로 호출한다. 새 helper가 성공을 대신하지 않는다.
    assert pipe._has_source_bound_image_recommendation_exception(ctx,DetectedTitle(official_title=title)) is False
    assert ctx.post_data==source_before
    assert ctx._final_source_original_inputs==captured_before


@pytest.mark.parametrize('body', [
    ["소설 '여러 장르 등의 약자 추정'이라는 풀이일 뿐 작품명은 아니다"],
    ["소설 '여러 장르 등의 약자 추정'을 읽지 않았다는 말은 거짓이다"],
    ["친구가 소설 '여러 장르 등의 약자 추정'을 읽지 않았다고 말했다"],
    ["소설 '여러 장르 등의 약자 추정'을 읽을 예정이라고 했다"],
    ["소설 '여러 장르 등의 약자 추정'을 읽었나? 라고 물었다"],
    ['“소설 「여러 장르 등의 약자 추정」를 읽지 않았다.”'],
    ['“', '소설 「여러 장르 등의 약자 추정」를 읽을 예정이다.', '”라고 했다.'],
    ["만약 소설 '여러 장르 등의 약자 추정'을 읽지 않았다면"],
    ["가령 소설 '여러 장르 등의 약자 추정'을 읽을 예정이라면"],
    ["소설 '여러 장르 등의 약자 추정'을 읽지 않았다면"],
    ["소설 '여러 장르 등의 약자 추정'을 읽지 않았다. 정정, 아니다."],
    ["소설 '여러 장르 등의 약자 추정'을 읽었나? 정정, 아니다."],
    ["소설 '여러 장르 등의 약자 추정'을 읽을 예정이다. 정정, 아니다."],
    ["소설 '여러 장르 등의 약자 추정'을 읽지 않았다. 그건 작품명이 아니다."],
    ["소설 '여러 장르 등의 약자 추정'을 읽지 않았다. 여러 장르 등의 약자 추정은 작품명이 아님."],
    ['소설 「여러 장르 등의 약자 추정』를 읽지 않았다'],
    ["'여러 장르 등의 약자 추정'이라는 설명을 읽지 않았다"],
    ['소설 목록에서', '여러 장르 등의 약자 추정을 읽지 않았다'],
    ["나는 '여러 장르 등의 약자 추정'을 읽지 않았다"],
])
def test_candidate_name_exception_keeps_name_denial_speech_hypothesis_and_cross_field_boundaries(tmp_path,body):
    title='여러 장르 등의 약자 추정'
    pipe,ctx,_=context(tmp_path,title='단어 뜻이 궁금하다',body=body)
    source_before=deepcopy(ctx.post_data)
    assert title_hypothesis_source_support(ctx,'별책',title) is None
    assert pipe._is_unbound_title_meta_explanation(ctx,title) is True
    seed(ctx,producer_candidate_input('별책',title))
    assert title not in candidate_titles(ctx)
    assert any(row['text']==title for row in ctx._title_meta_explanation_observations)
    assert ctx.post_data==source_before
