"""후보 정답 부재를 원문 작품담론 부재로 확대하지 않는 실제50·반례 검증."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from llm_batch.experts.orchestrator import ExpertType
from llm_batch.grounding.source_work_discussion_hold import marked_work_reading_hold
from test_source_surface_hypothesis_candidates import context

FIXTURE = Path(__file__).parent / 'fixtures/source50_saved_experts_20261014.json'


def discourse(surface='은빛항로'):
    return dict(primary_domain='novel_literature', target_kind='work',
                title_body_consistency=True, is_association_not_discussion=False,
                title_novel_terms=[surface])


def source(title='은빛항로<< 볼만함?', body='난 이거 중도하차함'):
    return {'title': title, 'content_blocks': [{'type': 'text', 'text': body}]}


@pytest.mark.parametrize('body', ['난 이거 중도하차함', '나는 이 작품을 읽었다.',
                                 '저는 이 소설을 중도 하차했습니다'])
def test_source_witness_retains_exact_spans_without_title_or_learning_authority(body):
    post = source(body=body)
    proof = marked_work_reading_hold(post, discourse())
    assert proof and post['title'][slice(*proof['title_span'])] == '은빛항로'
    assert body[slice(*proof['reading_span'])]
    assert proof['publication_authority'] is proof['learning_authority'] is False


@pytest.mark.parametrize('title,body', [
    ('은빛항로 좋음?', '난 이거 중도하차함'),
    ('은빛항로<< 다른책<< 비교', '난 이거 중도하차함'),
    ('은빛항로<<< 비교', '난 이거 중도하차함'),
    ('은빛항로<< 볼만함?', '친구가 이거 중도하차함'),
    ('은빛항로<< 볼만함?', '난 이거 읽지 않았다'),
    ('은빛항로<< 볼만함?', '난 이거 읽었다면'),
    ('은빛항로<< 볼만함?', '난 이거 읽을 예정이다'),
    ('은빛항로<< 볼만함?', '난 이거 읽었나?'),
    ('은빛항로<< 볼만함?', '난 이거 중도하차했다고 들었다'),
    ('은빛항로<< 볼만함?', '난 이거 중도하차함. 정정, 아니다.'),
    ('은빛항로<< 볼만함?', '“난 이거 중도하차함”이라고 했다'),
    ('친구가 "은빛항로<< 볼만함?"이라고 물었다', '난 이거 중도하차함'),
    ('은빛항로<< 볼만함?', '다른 소설을 읽었다'),
])
def test_quoted_speculative_negative_other_speaker_or_competing_targets_do_not_hold(title, body):
    assert marked_work_reading_hold(source(title, body), discourse()) is None


@pytest.mark.parametrize('field,value', [('primary_domain','game'), ('target_kind','topic'),
    ('title_body_consistency',False), ('is_association_not_discussion',True),
    ('title_novel_terms',['다른책']), ('title_novel_terms',['은빛항로','다른책'])])
def test_model_hypothesis_must_agree_with_original_source(field, value):
    model = discourse(); model[field] = value
    assert marked_work_reading_hold(source(), model) is None


@pytest.mark.parametrize('extra', [{'is_quote': True}, {'from_ocr': True}, {'speaker':'comment'}, {'source':'vlm'}])
def test_generated_or_non_author_reading_does_not_count(extra):
    post = source(); post['content_blocks'][0].update(extra)
    post['comments'] = [{'content':'난 이거 중도하차함'}]
    assert marked_work_reading_hold(post, discourse()) is None


def saved_context(tmp_path):
    f = json.loads(FIXTURE.read_text(encoding='utf-8'))
    pipe, ctx, _ = context(tmp_path, title=f['source_post']['title'],
        body=[x['text'] for x in f['source_post']['content_blocks'] if x.get('type') == 'text'])
    for name, value in f['experts'].items():
        ctx.set_expert_output(ExpertType(name), deepcopy(value))
    d = f['experts']['discourse']['discourse_analysis']
    ctx.primary_domain = d['primary_domain']; ctx.discourse_intent = d['intent']
    return pipe, ctx, f


def test_saved50_original_experts_keep_work_discussion_and_raw_candidate_only(tmp_path):
    pipe, ctx, f = saved_context(tmp_path)
    old_experts = deepcopy(ctx.get_expert_output(ExpertType.VERIFIER))
    output = pipe._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    identity = payload['identity']
    assert identity['topicality'] == 'core_relevant'
    assert identity['work_resolution'] == 'unresolved'
    assert identity['discussion_type'] != 'noise'
    assert identity['title_resolution_state'] == 'unresolved_matchable'
    assert not (identity.get('novel_identity') or {}).get('official_title')
    assert not (identity.get('novel_identity') or {}).get('heretic_url')
    preserved = identity['candidate_preservation_sources']
    candidate = next(x for x in preserved if x['official_title'] == '마왕의게임')
    assert candidate['confidence'] == 'Low' and candidate.get('heretic_url') is None
    assert 'source_marked_reading_hold_without_promotion' in candidate['negative_evidence']
    assert 'forced_unrelated_absent_grounding' not in identity['consistency_flags']
    assert ctx.get_expert_output(ExpertType.VERIFIER) == old_experts
    assert not (identity.get('slang_insight') or {}).get('store_in_slang_db')
    pipe.verify_final_source_context_serialization(output, payload, stage='source50_saved_partial_context')


def test_explicit_other_medium_disclaimer_keeps_original_veto(tmp_path):
    pipe, ctx, _ = context(tmp_path, title='은빛항로<< 볼만함?',
        body=['소설 얘기 아닌데', '난 이거 중도하차함'])
    ctx.set_expert_output(ExpertType.DISCOURSE, {'discourse_analysis': discourse()})
    assert pipe._source_marked_work_reading_hold(ctx) is None
