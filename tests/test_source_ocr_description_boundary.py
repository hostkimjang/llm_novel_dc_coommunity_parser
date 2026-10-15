"""OCR 변형의 비권한 설명과 최종 봉인 경계를 검산하는 미실행 회귀 초안."""
from copy import deepcopy

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from test_source_bound_propriety_question_state import NoExternal


OFFICIAL = '재벌가 차녀의 2회차 걸그룹'
OCR = '제벨가 차녀의 2회차 결그룹'
BAD = '게시글 제목에 사용된 축약어/오타로 보임'


def context(tmp_path, *, flag=True, raw_title='이거 제목 뭐였지', body='', captured=False):
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path, max_iterations=1)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    post = PostInput(post_id=11718082, title=raw_title,
                     content_blocks=[{'type':'text', 'text':body}] if body else [], comments=[])
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=[])
    if captured:
        ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx.post_data['content_blocks'].append({'type':'ocr_text', 'text':OCR})
    ctx.post_data['vlm_enrichment_used'] = True
    ctx.post_data['image_enrichment'] = [{'evidence_type':'explicit_text', 'explicit_work_title':OCR,
        'title_role':'work_title', 'promotion_eligible':flag}]
    ctx.search_results = [{'title':OFFICIAL + ' - 웹소설 - 카카오페이지',
        'url':'https://page.kakao.com/content/66692543', 'content':'유은우. ' + OFFICIAL + ' 267화.'}]
    ctx.set_expert_output(ExpertType.DECODER, {'decoded_terms':[
        {'original':OCR, 'best_match':{'title':OFFICIAL}}]})
    return pipe, ctx


@pytest.mark.parametrize('flag', [True, False, None])
def test_ocr_variant_reader_cleanup_does_not_change_promotion_eligibility_or_raw_inputs(tmp_path,flag):
    pipe,ctx=context(tmp_path,flag=flag)
    post_before,experts_before=deepcopy(ctx.post_data),deepcopy(ctx.expert_outputs)
    search_before=deepcopy(ctx.search_results)
    item=ctx.post_data['image_enrichment'][0]
    # role39와 함께 통합하는 설명 수리다. 허용값을 덮어쓰지 않고 실제 guard를 전후 대조한다.
    before_allowed=pipe._source_image_title_recall_allowed(ctx,item)
    assert before_allowed is (flag is not False)
    cleaned=pipe._sanitize_slang_cultural_context_for_image_conflict(BAD,ctx=ctx,official_title=OFFICIAL)
    assert '게시글 제목에 사용된' not in cleaned
    assert '이미지 OCR/표지에서 감지된' in cleaned
    assert pipe._source_image_title_recall_allowed(ctx,item) is before_allowed
    assert ctx.post_data==post_before and ctx.expert_outputs==experts_before
    assert ctx.search_results==search_before


@pytest.mark.parametrize('mode', ['different_title','mixed_diagnostics','no_official','exact_title'])
def test_nonvariant_or_mixed_ocr_still_defers_to_final_source_seal(tmp_path,mode):
    pipe,ctx=context(tmp_path)
    official=OFFICIAL
    if mode=='different_title':
        ctx.post_data['image_enrichment'][0]['explicit_work_title']='심연을 걷는 마법사'
    elif mode=='mixed_diagnostics':
        ctx.post_data['image_enrichment'].append({'evidence_type':'cover_title',
            'explicit_work_title':'심연을 걷는 마법사','promotion_eligible':False})
    elif mode=='no_official':
        official=None
    else:
        ctx.post_data['image_enrichment'][0]['explicit_work_title']=OFFICIAL
    assert pipe._sanitize_slang_cultural_context_for_image_conflict(BAD,ctx=ctx,official_title=official)==BAD


@pytest.mark.parametrize('raw_title', [OFFICIAL, OCR])
def test_actual_authored_title_is_not_relabelled_as_ocr(tmp_path,raw_title):
    pipe,ctx=context(tmp_path,raw_title=raw_title,captured=True)
    assert pipe._sanitize_slang_cultural_context_for_image_conflict(BAD,ctx=ctx,official_title=OFFICIAL)==BAD


@pytest.mark.parametrize('captured', [True, False])
def test_original_author_clause_remains_verbatim_until_final_source_seal(tmp_path,captured):
    raw='게시글 제목에 사용된 축약어/오타로 보임.'
    pipe,ctx=context(tmp_path,body='작가가 직접 쓴 문장이다. ' + raw,captured=captured)
    mixed='[원문] ' + raw + ' 작품의 고유 명칭으로 추정된다.'
    assert pipe._sanitize_slang_cultural_context_for_image_conflict(mixed,ctx=ctx,official_title=OFFICIAL)==mixed


def test_independent_official_title_sentence_is_not_deleted_by_variant_display_cleanup(tmp_path):
    pipe,ctx=context(tmp_path)
    official_fact='공식 페이지의 표제는 ' + OFFICIAL + '이다.'
    cleaned=pipe._sanitize_slang_cultural_context_for_image_conflict(
        official_fact + ' ' + BAD,ctx=ctx,official_title=OFFICIAL)
    assert official_fact in cleaned
    assert '게시글 제목에 사용된' not in cleaned
    assert ctx.search_results[0]['content']=='유은우. ' + OFFICIAL + ' 267화.'
