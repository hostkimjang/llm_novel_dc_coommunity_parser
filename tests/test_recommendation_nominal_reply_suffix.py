"""ROOT 격리 시험용. 원형71의 누락과 명사 말미/장르/반응 발화를 구분한다."""
from importlib import import_module
import json

import pytest

from test_source_recommendation_reply_repair import (
    sut, facts, context, collect, comment, canonical,
)


def test_current71_source_boundary_and_native_tokens_are_observed(sut, facts, tmp_path):
    pipe, ctx, external = context(sut, tmp_path, facts.p71)
    before = canonical([ctx.post_data, ctx.comments, facts.p71])
    raw = facts.p71['source_comments'][0]['content']
    helper = import_module('llm_batch.grounding.comment_request_scope')
    gate = import_module('llm_batch.promotion_gate')
    kiwi = gate._edition_kiwi()
    assert kiwi is not None
    tokens = [{'form': token.form, 'tag': token.tag, 'start': token.start, 'len': token.len}
              for token in kiwi.tokenize('우주괴물')]
    # 공개 제목 판정에 쓰는 원래 보수적 기본값은 바꾸지 않는다.
    assert pipe._is_generic_topic_title('우주괴물') is True
    assert pipe._is_structural_nonwork_title('우주괴물') is True
    assert helper.nominal_mul_ending_is_lexical('우주괴물') is True
    parts = pipe._comment_named_response_parts(raw)
    assert len(parts) == 1 and parts[0]['surface'] == '우주괴물'
    assert parts[0]['answer_raw_span'] == [0, len('우주괴물')]
    assert parts[0]['explicit_title_span'] is False
    observations = pipe._bound_comment_answer_observations(ctx)
    found = next(item for item in observations if item['surface'] == '우주괴물')
    assert found['relation'] == 'direct_post_work_request'
    assert found['post_request']['kind'] == 'source_novel_existence_request'
    assert found['original_index'] == 0 and found['raw_text'] == raw
    rows = collect(pipe, ctx)
    assert {row.official_title for row in rows} == {'우주괴물', '메카네크'}
    assert all(row.heretic_url is None and pipe._local_hold_has_work_role(ctx, row) for row in rows)
    assert before == canonical([ctx.post_data, ctx.comments, facts.p71]) and external.attempts == []
    (tmp_path / 'recommendation71_boundary.json').write_text(json.dumps({
        'scope': 'SOURCE_ONLY_COLLECTOR_NOT_FULL71_REPLAY',
        'source_canonical_sha256': facts.p71['source_canonical_sha256'],
        'raw_first_comment': raw, 'native_tokens': tokens, 'parts': parts,
        'observations': observations, 'candidates': [row.model_dump(mode='json') for row in rows],
        'source_unchanged': True, 'external_attempts': external.attempts,
    }, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.parametrize('name', ['도시괴물', '고대보물', '전설인물', '별빛선물', '행성생물'])
def test_unregistered_nominal_endings_preserve_only_low_reply(sut, tmp_path, name):
    pipe, ctx, external = context(sut, tmp_path, title='이런 소설 없냐', comments=[comment(name + '...')])
    before = canonical([ctx.post_data, ctx.comments])
    rows = collect(pipe, ctx)
    assert len(rows) == 1 and rows[0].official_title == name and rows[0].heretic_url is None
    assert pipe._local_hold_has_work_role(ctx, rows[0])
    preserved = pipe._build_candidate_preservation_sources(title_candidates=[], mentioned_works=[],
        comparison_target=None, recommendation_candidates=rows, secondary_reference_works=None)
    assert all(item['promotion_policy'] == 'hold_without_promotion' for item in preserved)
    assert before == canonical([ctx.post_data, ctx.comments]) and external.attempts == []


@pytest.mark.parametrize('answer', ['괴수물', '이세계물', '아카데미물', '하렘물',
    '회귀헌터물', '장르소설', '목차', '작가후기'])
def test_genre_labels_and_structural_topics_stay_excluded(sut, tmp_path, answer):
    pipe, ctx, external = context(sut, tmp_path, title='이런 소설 없냐', comments=[comment(answer)])
    assert collect(pipe, ctx) == [] and external.attempts == []


@pytest.mark.parametrize('answer', ['우주괴물 같다', '우주괴물 같은데', '읽어보니 별로임',
    '이거 꽤 재밌음', '진짜 고맙다', '물 좀 마셔'])
def test_reactions_and_predication_do_not_become_nominal_replies(sut, tmp_path, answer):
    pipe, ctx, external = context(sut, tmp_path, title='이런 소설 없냐', comments=[comment(answer)])
    assert collect(pipe, ctx) == [] and external.attempts == []


@pytest.mark.parametrize('request_text', ['영화 추천해줘', '게임 추천해줘', '웹툰 추천해줘',
    '산책할 곳 추천해줘', '오늘 날씨 좋다', '“이런 소설 없냐”라고 말했다.'])
def test_nominal_shape_does_not_create_a_novel_request(sut, tmp_path, request_text):
    pipe, ctx, external = context(sut, tmp_path, title=request_text, comments=[comment('우주괴물...')])
    assert collect(pipe, ctx) == [] and external.attempts == []


@pytest.mark.parametrize('answer', ['제목: 회귀물', '제목: 나는 물이 된다.', '「이세계물」',
    '[도시괴물](https://novelpia.com/novel/998811)'])
def test_explicit_name_and_link_paths_remain_low(sut, tmp_path, answer):
    pipe, ctx, external = context(sut, tmp_path, title='이런 소설 없냐', comments=[comment(answer)])
    rows = collect(pipe, ctx)
    assert len(rows) == 1 and pipe._local_hold_has_work_role(ctx, rows[0])
    assert external.attempts == []


def test_nominal_reply_deduplication_and_low_limit_are_unchanged(sut, tmp_path):
    answers = [comment('우주괴물...', cid='a'), comment('우주괴물...', cid='b'),
               comment('고대보물...', cid='c'), comment('메카네크', cid='d')]
    pipe, ctx, external = context(sut, tmp_path, title='이런 소설 없냐', comments=answers)
    rows = pipe._collect_comment_answer_preservation_candidates(ctx, discussion_type='recommendation', max_items=2)
    assert [row.official_title for row in rows] == ['우주괴물', '고대보물']
    assert all(row.confidence == 'Low' and row.reference_role == 'candidate'
               and row.negative_evidence == ['comment_answer_preservation_only'] for row in rows)
    assert external.attempts == []


def test_native_analyzer_unavailable_does_not_grant_suffix_exception(sut, monkeypatch):
    helper = import_module('llm_batch.grounding.comment_request_scope')
    gate = import_module('llm_batch.promotion_gate')
    monkeypatch.setattr(gate, '_edition_kiwi', lambda: None)
    assert helper.nominal_mul_ending_is_lexical('우주괴물') is False


@pytest.mark.parametrize('surface', ['우주괴물', '로판닼판', '전차', '줄다리기', '포스트 아포칼립스'])
def test_public_generic_defaults_and_nonboolean_flags_remain_conservative(sut, tmp_path, surface):
    pipe, _, _ = context(sut, tmp_path, title='일반 문맥')
    assert pipe._is_generic_topic_title(surface) is True
    assert pipe._is_generic_topic_title(surface, ignore_genre_suffix=False) is True
    assert pipe._is_generic_topic_title(surface, ignore_genre_suffix='true') is True


@pytest.mark.parametrize('surface', ['판타지 소설', '프롤로그', '에필로그', '202화', '제 202 화',
    '표지변경', '소신 발언', '장르보물'])
def test_non_suffix_structural_and_low_specificity_rules_are_not_bypassed(sut, tmp_path, surface):
    pipe, _, _ = context(sut, tmp_path, title='일반 문맥')
    assert pipe._is_structural_nonwork_title(surface) is True
    # Low 전용 옵션도 사전·구조·담화·메타 규칙을 지우지 않는다.
    assert pipe._is_structural_nonwork_title(surface, ignore_genre_suffix=True) is True
