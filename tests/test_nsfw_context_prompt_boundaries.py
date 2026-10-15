"""실제 요청 조립의 원문·문맥 지시 결속. 모델 정답률 시험과 구분한다."""
import hashlib
import json
from pathlib import Path

import pytest

from test_arbiter_nsfw_prompt_scope import (
    assert_scope_contract, capture_actual_messages, context_for,
)


FIXTURE = Path(__file__).parent / 'fixtures/nsfw_context33_50_saved.json'
FIXTURE_SHA = '1ccb55e1cdc197a20b94ac57825848d3702bf6792c9559dc37c6da68c2120cb6'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def assert_context_boundaries(system, user):
    source_area = assert_scope_contract(system, user)
    for clause in (
        '독자층·취향을 낮춰 부르는 합성 은어',
        '신체 부위처럼 보이는 일부 글자만 잘라 성행위나 작품 속 히로인 선택을 만들어 내지',
        '성적 행위가 생략된 완곡 표현은 제목·본문이 지시하는 대상과 해당 댓글을 함께',
        '명시적인 행위 명사가 없다는 이유만으로 누락하지',
        '활동 대상이 운동·게임·업무라면 성적 의미를 보충하지',
        '개인 의견인지 작품 관련인지와 성적 내용인지는 별개',
        '판독한 댓글을 글쓴이의 의사나 실제 행위로 귀속하지',
    ):
        assert clause in system
    instructions = user.split('=== NSFW 판독 범위 ===', 1)[1].split('=== EXPERT CONSENSUS ===', 1)[0]
    assert '전체 표현의 역할과 원문에 있는 대상·행위를 구분' in instructions
    assert '댓글 화자와 글쓴이를 합치지' in instructions
    # 기존 실제 요청·원문/외부 경계와 JSON 출력 계약을 함께 보존한다.
    assert '"is_nsfw": boolean' in user
    return source_area


@pytest.mark.parametrize('index,stored_bool', [(33, False), (50, True)])
def test_saved_source_reaches_real_request_with_context_rules_without_changing_old_bool(index, stored_bool):
    before = FIXTURE.read_bytes()
    assert hashlib.sha256(before).hexdigest() == FIXTURE_SHA
    fixture = json.loads(before)
    assert fixture['scope'] == 'SAVED_SOURCE_FULL_RESULT_NOT_ORIGINAL_REQUEST_CONTEXT'
    row = next(x for x in fixture['rows'] if x['index1'] == index)
    assert hashlib.sha256(canonical({'post': row['source_post'], 'comments': row['source_comments']})).hexdigest() == row['source_canonical_sha256']
    assert hashlib.sha256(canonical(row['checkpoint_result'])).hexdigest() == row['result_canonical_sha256']
    comments = [x['content'].strip() for x in row['source_comments'] if x.get('content', '').strip()][:15]
    system, user = capture_actual_messages(context_for(row['source_post'], comments))
    source_area = assert_context_boundaries(system, user)
    assert row['source_post']['title'] in source_area
    for block in row['source_post']['content_blocks']:
        if block.get('type') == 'text':
            assert block['text'] in source_area
    assert all(comment in source_area for comment in comments)
    # 수정된 프롬프트의 회수 확인이며 모델 응답·당시 private context 재현은 아니다.
    assert row['checkpoint_result']['analysis_result']['analysis']['is_nsfw'] is stored_bool
    assert FIXTURE.read_bytes() == before


@pytest.mark.parametrize('title,body,comment', [
    ('독자층에 대한 질문', '이 작품을 여성 독자가 주로 고른다는 뜻의 속어를 썼다.', '장르 취향 이야기다.'),
    ('연애와 성적 경험에 관한 질문', '경험 유무에 따른 성적 파트너 선호를 묻는다.', '경험 없는 사람이랑 하고 싶긴 해.'),
    ('게임 동료에 관한 질문', '이 게임 경험이 없는 친구를 모집한다.', '경험 없는 사람이랑 하고 싶긴 해.'),
    ('운동 모임에 관한 질문', '초보자끼리 배드민턴을 하려 한다.', '경험 없는 사람이랑 하고 싶긴 해.'),
    ('업무 체험 안내', '새로 입사한 사람과 프로젝트를 진행한다.', '경험 없는 사람이랑 하고 싶긴 해.'),
    ('인용한 제안에 반대한다', '댓글의 성관계 제안을 거절한다.', '성관계를 하자는 제안이었다.'),
])
def test_contrastive_context_and_speaker_survive_actual_prompt_assembly(title, body, comment):
    post = {'post_id': 82001, 'title': title, 'content_blocks': [{'type': 'text', 'text': body}]}
    system, user = capture_actual_messages(context_for(post, [comment]))
    source_area = assert_context_boundaries(system, user)
    assert title in source_area and body in source_area and comment in source_area
    assert source_area.index(title) < source_area.index(body) < source_area.index(comment)
    # 같은 댓글의 문맥별 전달 검산이다. 참/거짓 정답을 응답 stub으로 주입하지 않는다.
