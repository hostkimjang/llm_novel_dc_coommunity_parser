"""ROOT 실행 전용. 기존 native 한 번의 원문 소비 뒤 현재 입력 변경을 검산한다."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_source_speaker_attribution_repair import consume


def fresh():
    return consume({'post_id':90801, 'title':'관계 이야기', 'content_blocks':[
        {'type':'text', 'text':'친구를 위해 내가 먼저 연락했다.'},
        {'type':'text', 'text':'나는 내일 다시 만나기로 했다.'}]},
        [{'comment_id':'c1', 'author':'별도 화자', 'content':'나는 먼저 연락하지 않았다.'}])


@pytest.mark.parametrize('mode', ['body_text', 'body_space', 'body_order', 'body_drop',
    'body_append', 'body_type', 'post_title', 'captured_text', 'captured_path', 'comment'])
def test_native_current_inputs_and_original_carrier_tamper_fail_without_rebinding(mode):
    _, ctx, _, _, verify, _ = fresh()
    native = ctx._final_source_projection_native
    assert verify() and ctx._final_source_projection_call_count == 1
    if mode == 'body_text': ctx.post_data['content_blocks'][0]['text'] = '변경된 본문'
    elif mode == 'body_space': ctx.post_data['content_blocks'][0]['text'] += ' '
    elif mode == 'body_order': ctx.post_data['content_blocks'].reverse()
    elif mode == 'body_drop': ctx.post_data['content_blocks'].pop()
    elif mode == 'body_append': ctx.post_data['content_blocks'].append({'type':'text', 'text':'새 본문'})
    elif mode == 'body_type': ctx.post_data['content_blocks'][0]['type'] = 'image'
    elif mode == 'post_title': ctx.post_data['title'] = '다른 제목'
    elif mode == 'captured_text': ctx._final_source_original_inputs[1]['raw_text'] = '원 carrier 변경'
    elif mode == 'captured_path': ctx._final_source_original_inputs[1]['raw_path'] = '/content_blocks/1/text'
    elif mode == 'comment': ctx.comments[0]['content'] = '다른 댓글'
    assert not verify()
    assert ctx._final_source_projection_native is native and ctx._final_source_projection_call_count == 1


@pytest.mark.parametrize('field', ['normalized_body', 'normalized_title', 'surface_paraphrase_notes'])
def test_unconsumed_working_metadata_does_not_invalidate_raw_source_binding(field):
    _, ctx, _, _, verify, _ = fresh()
    ctx.post_data[field] = '실제 원문 소비에 쓰이지 않는 보조값'
    assert verify() and ctx._final_source_projection_call_count == 1


def test_body_same_exact_values_and_repeated_readback_keep_single_native_pass():
    _, ctx, _, _, verify, _ = fresh()
    native = ctx._final_source_projection_native
    ctx.post_data['content_blocks'] = copy.deepcopy(ctx.post_data['content_blocks'])
    assert verify() and verify()
    assert ctx._final_source_projection_native is native and ctx._final_source_projection_call_count == 1
