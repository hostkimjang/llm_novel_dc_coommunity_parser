"""역할 설명 후보 회귀 초안. 고정 저장 경계와 실제 native 봉인을 구분한다. 외부 호출 없음."""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PickvelAnalysis, PickvelIdentity, PickvelOutputItemV2, PostInput, SlangInsight
from llm_batch.experts.orchestrator import ConversationContext, ExpertType

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/actual80_slang_role8_saved_experts.json'
TITLE = '은빛 기록'
NAME = '서린'
BAD = '작품명(은빛 기록)과 주인공 이름(서린)을 결합한 표현이다.'


class NoExternalIO:
    def fetch(self, *args, **kwargs):
        raise AssertionError('EXTERNAL_FETCH_FORBIDDEN')

    def search(self, *args, **kwargs):
        raise AssertionError('EXTERNAL_SEARCH_FORBIDDEN')


def make_context(*, title='은빛 기록서린 반응', body=('벌써 움직이네',), comments=(), record=None):
    raw = dict(record['post'], comments=record['comments']) if record else {
        'post_id': 81008, 'title': title,
        'content_blocks': [{'type': 'text', 'text': line} for line in body], 'comments': list(comments),
    }
    post = PostInput(**deepcopy(raw))
    pipe = AgenticPipeline(llm=object(), mcp=NoExternalIO(), max_iterations=1)
    pipe._use_session_knowledge = False
    pipe.enable_url_fetch_disk_cache = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    if record:
        for name, value in record['experts'].items():
            ctx.set_expert_output(ExpertType(name), deepcopy(value))
    return pipe, ctx


def make_identity(**overrides):
    insight = dict(detected_term=TITLE + NAME, decoded_term=TITLE, decode_verified=True,
        canonical_work_alias=TITLE, cultural_context=BAD, alias_scope='pure_work_alias',
        attached_entity_text=None, attached_entity_type=None, store_in_slang_db=False,
        store_reason='character_attached_composite')
    insight.update(overrides)
    return PickvelIdentity(is_relevant=False, discussion_type='general', title_resolution_allowed=False,
        title_resolution_state='context_only', reason='이 설명은 역할 수리 대상이 아니다.',
        slang_insight=SlangInsight(**insight))


def apply_and_assert_only_context_changed(pipe, ctx, identity):
    before = identity.model_dump(mode='json')
    original = deepcopy(ctx.post_data)
    pipe._hold_unbound_slang_character_role_context(ctx, identity)
    after = identity.model_dump(mode='json')
    expected = deepcopy(before)
    expected['slang_insight']['cultural_context'] = after['slang_insight']['cultural_context']
    assert after == expected
    assert ctx.post_data == original
    return after['slang_insight']['cultural_context']


def test_actual8_saved_model_boundary_keeps_every_other_field_and_serialized_bytes(tmp_path):
    before_fixture = FIXTURE.read_bytes()
    record = json.loads(before_fixture)
    pipe, ctx = make_context(record=record)
    saved = record['saved_result']['analysis_result']
    output = PickvelOutputItemV2.model_validate(saved)
    before = output.model_dump(mode='json')
    vf_slang = record['experts']['verifier']['verification_result']['slang_insight']
    assert vf_slang['attached_entity_type'] == 'other'
    assert pipe._source_bound_character_decode(ctx, vf_slang, output.identity.novel_identity.official_title) is True
    assert output.identity.slang_insight.alias_scope == 'pure_work_alias'
    assert output.identity.slang_insight.attached_entity_type is None
    assert output.identity.slang_insight.store_reason == 'character_attached_composite'
    assert apply_and_assert_only_context_changed(pipe, ctx, output.identity) is None
    after = output.model_dump(mode='json')
    expected = deepcopy(before)
    expected['identity']['slang_insight']['cultural_context'] = None
    assert after == expected
    assert after['identity']['novel_identity'] == saved['identity']['novel_identity']
    assert after['identity']['reason'] == saved['identity']['reason']
    assert after['analysis']['notes'] == saved['analysis']['notes']
    assert after['identity']['slang_insight']['store_in_slang_db'] is False
    # 기존 공개 쌍을 새로 승인하지 않는다. 실제 저장 모델 경계의 불변성과 필드 봉인만 검사한다.
    seal = pipe._final_source_serialization_seal(after)
    path = tmp_path / 'actual8_boundary_only.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(after, stream, ensure_ascii=False, allow_nan=False)
    readback = json.loads(path.read_text(encoding='utf-8'))
    assert readback == after
    assert pipe._final_source_serialization_seal(readback) == seal
    changed = deepcopy(readback)
    changed['identity']['slang_insight']['cultural_context'] = vf_slang['cultural_context']
    assert pipe._final_source_serialization_seal(changed) != seal
    assert FIXTURE.read_bytes() == before_fixture


@pytest.mark.parametrize('body', [
    ['서린은 은빛 기록의 주인공이다.'],
    ['은빛 기록의 주인공은 서린이다.'],
    ['은빛 기록의 주인공 이름은 서린입니다.'],
])
def test_explicit_same_source_work_name_role_declaration_keeps_description(body):
    pipe, ctx = make_context(body=body)
    identity = make_identity()
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) == BAD


@pytest.mark.parametrize('body', [
    ['서린은 은빛 기록의 주인공이 아니다.'],
    ['서린은 은빛 기록의 주인공인가?'],
    ['서린은 은빛 기록의 주인공이라고 친구가 말했다.'],
    ['> 서린은 은빛 기록의 주인공이다.'],
    ['"서린은 은빛 기록의 주인공이다."'],
    ['「서린은 은빛 기록의 주인공이다.」'],
    ['친구가 말했다. "', '서린은 은빛 기록의 주인공이다.', '"'],
    ['친구:', '서린은 은빛 기록의 주인공이다.'],
    ['만약 서린은 은빛 기록의 주인공이다.'],
    ['서린은 황금 정원의 주인공이다.'],
    ['서린은 은빛 기록의 등장인물이다.'],
    ['주인공이라는 단어만 보았다.'],
])
def test_other_work_negation_question_quotation_or_generic_character_cannot_prove_role(body):
    pipe, ctx = make_context(body=body)
    identity = make_identity()
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None


@pytest.mark.parametrize('channel', ['comment', 'search', 'image', 'generated_body'])
def test_only_author_original_may_preserve_role(channel):
    sentence = '서린은 은빛 기록의 주인공이다.'
    pipe, ctx = make_context(comments=[sentence] if channel == 'comment' else [])
    if channel == 'search':
        ctx.search_results = [{'snippet': sentence, 'url': 'https://example.invalid/source'}]
    elif channel == 'image':
        ctx.post_data['image_enrichment'] = [{'ocr_text': sentence, 'visual_description': sentence}]
    elif channel == 'generated_body':
        ctx.post_data['content_blocks'].append({'type': 'text', 'text': sentence, 'from_ocr': True})
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity()) is None


def test_typed_character_to_work_link_is_not_role_proof():
    pipe, ctx = make_context()
    ctx.verified_character_work_links = [{'character': NAME, 'title': TITLE,
        'url': 'https://series.naver.com/novel/detail.series?productNo=999991', '_weak_match': False}]
    identity = make_identity(alias_scope='work_plus_character', attached_entity_text=NAME,
        attached_entity_type='character')
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None


def test_pure_work_explanation_and_non_role_sentences_survive():
    pipe, ctx = make_context()
    pure = make_identity(cultural_context='작품 제목을 줄인 말이다.', store_reason='pure_work_alias')
    assert apply_and_assert_only_context_changed(pipe, ctx, pure) == '작품 제목을 줄인 말이다.'
    mixed = make_identity(cultural_context=BAD + ' 원제목과 함께 쓰이는 표현이다.')
    assert apply_and_assert_only_context_changed(pipe, ctx, mixed) == '원제목과 함께 쓰이는 표현이다.'
    assert len(ctx._slang_character_role_hold['held']) == 1


@pytest.mark.parametrize('text', [
    '주인공 이름(서린)이라는 주장은 확인되지 않았다.',
    '주인공 이름(서린)이 맞는가?',
    '주인공 이름(서린)이 아니다.',
])
def test_nonaffirmative_model_sentence_is_not_rewritten_as_positive_claim(text):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=text)) == text


@pytest.mark.parametrize('mutation', ['missing_capture', 'original_changed'])
def test_missing_or_changed_original_cannot_release_hold(mutation):
    pipe, ctx = make_context(body=['서린은 은빛 기록의 주인공이다.'])
    if mutation == 'missing_capture':
        del ctx._final_source_original_inputs
    else:
        ctx.post_data['content_blocks'][0]['text'] = '나중에 생성된 문장'
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity()) is None


@pytest.mark.parametrize('tamper', ['restore', 'remove_key', 'remove_insight'])
def test_actual_native_source_consumption_and_existing_seal_reject_role_restore(tmp_path, tamper):
    pipe, ctx = make_context()
    identity = make_identity(alias_scope='work_plus_character', attached_entity_type='character', attached_entity_text=NAME)
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None
    # 저장8의 새 공개 판정을 만드는 시험이 아니다. 합성 HOLD 모델의 실제 native 소비·봉인이다.
    notes, native = pipe._consume_final_source_context(ctx, identity, None)
    analysis = PickvelAnalysis(notes=notes)
    pipe._apply_ocr_reader_provenance_before_source_seal(ctx, identity, analysis)
    output = PickvelOutputItemV2(post_id=ctx.post_id, identity=identity, analysis=analysis)
    object.__setattr__(output, '_final_source_context_owner', ctx)
    object.__setattr__(output, '_final_source_context_native', ctx._final_source_projection_native)
    object.__setattr__(output, '_final_source_context_original_entities', ctx._final_source_original_entities)
    object.__setattr__(output, '_final_source_context_consumption', ctx._final_source_projection_consumption)
    def verify_used_fields():
        return bool(native() and pipe._verify_final_source_reader_fields(ctx, identity, analysis))
    pipe._attach_final_source_serialization_receipt(output, native_verifier=verify_used_fields)
    payload = output.model_dump(mode='json')
    pipe.verify_final_source_context_serialization(output, payload, stage='slang_role_native_model_dump')
    path = tmp_path / 'synthetic_native_slang.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
    stored = json.loads(path.read_text(encoding='utf-8'))
    pipe.verify_final_source_context_serialization(output, stored, stage='slang_role_native_readback')
    assert stored['identity']['novel_identity'] is None
    assert stored['identity']['slang_insight']['cultural_context'] is None
    if tamper == 'restore':
        stored['identity']['slang_insight']['cultural_context'] = BAD
    elif tamper == 'remove_key':
        del stored['identity']['slang_insight']['cultural_context']
    else:
        stored['identity']['slang_insight'] = None
    with pytest.raises(ValueError, match='serialized fields changed'):
        pipe.verify_final_source_context_serialization(output, stored, stage='slang_role_tampered_payload')


def test_actual_serializer_calls_narrow_guard_before_source_projection_and_legacy_seal_is_unchanged():
    tree = ast.parse((ROOT / 'src/llm_batch/agentic_pipeline.py').read_text(encoding='utf-8'))
    klass = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == 'AgenticPipeline')
    function = next(item for item in klass.body if isinstance(item, ast.FunctionDef) and item.name == '_context_to_output')
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    hold = [node.lineno for node in calls if node.func.attr == '_hold_unbound_slang_character_role_context']
    consume = [node.lineno for node in calls if node.func.attr == '_consume_final_source_context']
    assert len(hold) == len(consume) == 1 and hold[0] < consume[0]
    # 과거 payload seal에 새 필드나 버전을 소급 넣지 않는다.
    payload = PickvelOutputItemV2(post_id=81008, identity=make_identity(), analysis=None).model_dump(mode='json')
    fields = AgenticPipeline._final_source_serialization_fields(payload)
    assert fields['slang_cultural_context'] == {'present': True, 'value': BAD}



@pytest.mark.parametrize('body', [
    ['친구가 말했다. "', '서린은 은빛 기록의 주인공이다.', '"'],
    ['친구가 말했다. "\n서린은 은빛 기록의 주인공이다.\n"'],
    ['친구가 말했다. "', '서린은 은빛 기록의 주인공이다.'],
])
def test_ascii_multiline_or_unclosed_quote_is_not_author_role_proof(body):
    # 원문의 실제 줄바꿈으로 단일 block과 여러 block을 모두 확인한다.
    body = [line.replace('\\n', '\n') for line in body]
    pipe, ctx = make_context(body=body)
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity()) is None


@pytest.mark.parametrize('body', [
    ['친구가 말했다. "', '서린은 은빛 기록의 주인공이다.', '"', '서린은 은빛 기록의 주인공이다.'],
    ['친구가 말했다. "', '친구:', '서린은 은빛 기록의 주인공이다.', '"', '은빛 기록의 주인공은 서린이다.'],
])
def test_closed_ascii_quote_does_not_hide_later_independent_author_declaration(body):
    pipe, ctx = make_context(body=body)
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity()) == BAD


@pytest.mark.parametrize('description', [
    '다른 뜻은 없고 ' + BAD,
    '이견은 아니지만 ' + BAD,
    BAD[:-1] + ', 다른 뜻은 없다.',
    '다른 주장은 확인되지 않았고 ' + BAD,
    '작품명(은빛 기록)과 주인공 이름(아니카)을 결합한 표현이다.',
    '서린은 주인공이다, 다른 뜻은 없다.',
])
def test_unrelated_negation_or_name_substring_cannot_bypass_role_proof(description):
    pipe, ctx = make_context()
    person = '아니카' if '아니카' in description else NAME
    identity = make_identity(detected_term=TITLE + person, cultural_context=description)
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None
    assert len(ctx._slang_character_role_hold['held']) == 1


@pytest.mark.parametrize('description', [
    '주인공 이름(서린)이 아니다.',
    '주인공 이름(서린)이라는 주장은 확인되지 않았다.',
    '주인공 이름(서린)은 확인되지 않았다.',
    '주인공 이름(서린)이 맞는가?',
    '주인공 이름(서린)이라면 가능한 설명이다.',
    '만약 주인공 이름(서린)을 결합한 표현이다.',
    '주인공 이름(서린)이라고 가정한 설명이다.',
])
def test_claim_bound_negation_question_or_hypothesis_is_preserved(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description


def test_held_role_sentence_does_not_remove_independent_nonrole_negation():
    pipe, ctx = make_context()
    description = '다른 뜻은 없고 ' + BAD + ' 별도 뜻은 확인되지 않았다.'
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == '별도 뜻은 확인되지 않았다.'



# 19:11 실제 런의 완료행 원형이다. 이전 fixture나 실제 결과를 바꾸지 않는다.
LATEST_PACKET_FIXTURE = Path(__file__).parent / 'fixtures/actual80_run191128_slang_role8_packet.json'
LATEST_RESULT_SHA = '7f7fd4d29e4e9f03a47fcee1d5d383c66dc932479dc16a9934cee0848d0288f2'
LATEST_SOURCE_SHA = '7cde871fab3fdff2c8f9a9cd101093dc8ff4b68a011d0831339bad17529418fa'
NEW_NAMING = "작품명(은빛 기록)과 주인공의 성함('서린')을 결합한 표현이다."


def test_actual191128_row8_full_saved_boundary_keeps_public_pair_and_original_packet(tmp_path):
    import hashlib
    original_bytes = LATEST_PACKET_FIXTURE.read_bytes()
    packet = json.loads(original_bytes)
    def fingerprint(value):
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()
    assert packet['run_id'] == '20261012_191128_106718'
    assert type(packet['post_id']) is int and packet['post_id'] == 11718064 and packet['index1'] == 8
    assert fingerprint(packet['checkpoint_result']) == packet['result_canonical_sha256'] == LATEST_RESULT_SHA
    assert fingerprint({'post': packet['source_post'], 'comments': packet['source_comments']}) == packet['source_canonical_sha256'] == LATEST_SOURCE_SHA
    pipe, ctx = make_context(record={'post': packet['source_post'], 'comments': packet['source_comments'], 'experts': {}})
    output = PickvelOutputItemV2.model_validate(packet['checkpoint_result']['analysis_result'])
    before = output.model_dump(mode='json')
    assert before['identity']['slang_insight']['cultural_context'] == "작품 제목의 앞부분('즉사' + '무림')과 주인공의 성함('이유백')을 하나로 합친 커뮤니티식 축약어"
    assert before['identity']['slang_insight']['alias_scope'] == 'pure_work_alias'
    assert before['identity']['slang_insight']['attached_entity_type'] is None
    assert before['identity']['slang_insight']['attached_entity_text'] is None
    assert before['identity']['slang_insight']['store_reason'] == 'character_attached_composite'
    assert apply_and_assert_only_context_changed(pipe, ctx, output.identity) is None
    after = output.model_dump(mode='json')
    expected = deepcopy(before)
    expected['identity']['slang_insight']['cultural_context'] = None
    assert after == expected
    assert after['identity']['novel_identity'] == packet['checkpoint_result']['analysis_result']['identity']['novel_identity']
    assert after['identity']['slang_insight']['store_in_slang_db'] is False
    held = ctx._slang_character_role_hold
    assert held['publication_authority'] is False and held['human_gold'] is False
    claim = held['held'][0]['claims'][0]
    assert (claim['name'], claim['role']) == ('이유백', '주인공')
    source_description = before['identity']['slang_insight']['cultural_context']
    assert source_description[slice(*claim['name_span'])] == "'이유백'"
    assert source_description[slice(*claim['relation_span'])] == "주인공의 성함('이유백')"
    # 실제 저장 모델 경계만 재생한다. 이전 actual PUBLISH의 in-memory context를 합성하지 않는다.
    seal = pipe._final_source_serialization_seal(after)
    target = tmp_path / 'latest_actual8_saved_boundary.json'
    with target.open('x', encoding='utf8') as stream:
        json.dump(after, stream, ensure_ascii=False, allow_nan=False)
    readback = json.loads(target.read_text(encoding='utf8'))
    assert readback == after and pipe._final_source_serialization_seal(readback) == seal
    restored = deepcopy(readback)
    restored['identity']['slang_insight']['cultural_context'] = source_description
    assert pipe._final_source_serialization_seal(restored) != seal
    assert LATEST_PACKET_FIXTURE.read_bytes() == original_bytes
    assert fingerprint(packet['checkpoint_result']) == LATEST_RESULT_SHA


@pytest.mark.parametrize('description', [
    '주인공의 이름(서린)을 합친 표현이다.',
    '주인공 성함(서린)을 합친 표현이다.',
    "주인공 이름('서린')을 합친 표현이다.",
    NEW_NAMING,
    '남주인공의 성명（“서린”）을 합친 표현이다.',
    '여주 이름(‘서린’)을 합친 표현이다.',
    '여주인공의 성함(「서린」)을 합친 표현이다.',
    '남주 성명(『서린』)을 합친 표현이다.',
    "주인공의 이름은 '서린'이다.",
    '주인공 성명은 서린입니다.',
    '주인공의 성함이 “서린”임',
], ids=['genitive', 'honorific', 'single_quotes', 'actual_shape', 'fullwidth_double',
        'female_single', 'female_corner', 'male_double_corner', 'subject_quoted', 'subject_plain', 'subject_copula'])
def test_narrow_naming_forms_are_held_without_inventing_author_role(description):
    pipe, ctx = make_context()
    identity = make_identity(cultural_context=description)
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None
    for item in ctx._slang_character_role_hold['held']:
        for claim in item['claims']:
            assert claim['name'] == NAME
            assert description[slice(*claim['name_span'])].strip().strip("'\"‘’“”「」『』") == NAME
    assert ctx._slang_character_role_hold['publication_authority'] is False


@pytest.mark.parametrize('description', [NEW_NAMING, "주인공의 성함은 '서린'이다."])
def test_existing_exact_author_declaration_releases_new_naming_forms(description):
    pipe, ctx = make_context(body=['서린은 은빛 기록의 주인공이다.'])
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description
    assert '_slang_character_role_hold' not in ctx.__dict__


@pytest.mark.parametrize('description', [
    "주인공의 성함('서린')이 아니다.",
    "주인공의 성함('서린')이 맞는가?",
    "주인공의 성함('서린')이라는 주장은 확인되지 않았다.",
    "주인공의 성함('서린')이라면 가능한 설명이다.",
    "만약 주인공의 성함('서린')을 합친 표현이다.",
    "주인공의 성함('서린')이라고 가정한 설명이다.",
    "주인공의 성함('서린')이라고 친구가 말했다.",
    "주인공의 이름은 '서린'이 아니다.",
    "주인공의 이름은 '서린'이다?",
    "주인공의 이름은 '서린'이라면 가능한 설명이다.",
    "만약 주인공의 이름은 '서린'이다.",
    '“주인공의 성함(서린)을 합친 표현”이라는 댓글이 있다.',
    "친구가 '주인공의 성함(서린)'이라고 말했다.",
    '친구의 설명: “\n주인공의 이름은 서린이다.\n”',
    '친구의 설명: “\n주인공의 성함(서린)을 합친 표현이다.',
], ids=['negative', 'question', 'unsupported_report', 'conditional', 'if_prefix', 'assumption',
        'reported', 'subject_negative', 'subject_question', 'subject_conditional', 'subject_if',
        'whole_curly_quote', 'whole_ascii_quote', 'multiline_quote', 'unclosed_quote'])
def test_new_naming_nonaffirmative_or_outer_quote_is_preserved(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description


@pytest.mark.parametrize('description', [
    '다른 뜻은 없고 ' + NEW_NAMING,
    "이견은 아니지만 주인공의 성함은 '서린'이다.",
    "주인공의 성함('아니카')을 합친 표현이다.",
])
def test_new_naming_unrelated_negation_does_not_exempt_its_positive_claim(description):
    pipe, ctx = make_context()
    person = '아니카' if '아니카' in description else NAME
    assert apply_and_assert_only_context_changed(pipe, ctx,
        make_identity(cultural_context=description, detected_term=TITLE + person)) is None


@pytest.mark.parametrize('description', [
    "주인공 성함('서린\")을 합친 표현이다.",
    '주인공 성함(서린）을 합친 표현이다.',
    '주인공 성함（서린)을 합친 표현이다.',
    "주인공 성함('서린)을 합친 표현이다.",
    '주인공 이름이라는 작품 제목이다.',
    '주인공의 성격이 서늘하다.',
    '작품 제목을 줄인 말이다.',
])
def test_malformed_naming_or_unrelated_prose_is_not_silently_normalized(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description


@pytest.mark.parametrize('mode', ['missing_capture', 'changed_body', 'comment', 'search', 'image',
    'wrong_work', 'generic_character', 'source_quote', 'source_report', 'source_speaker',
    'ascii_carried_source', 'new_source_grammar_not_enabled'])
def test_new_naming_does_not_expand_the_existing_author_proof(mode):
    declaration = '서린은 은빛 기록의 주인공이다.'
    body = {
        'missing_capture': [declaration], 'changed_body': [declaration],
        'wrong_work': ['서린은 황금 정원의 주인공이다.'],
        'generic_character': ['서린은 은빛 기록의 등장인물이다.'],
        'source_quote': ['“' + declaration + '”'],
        'source_report': ['서린은 은빛 기록의 주인공이라고 친구가 말했다.'],
        'source_speaker': ['친구:', declaration],
        'ascii_carried_source': ['친구가 말했다. "', declaration, '"'],
        'new_source_grammar_not_enabled': ["은빛 기록의 주인공의 성함은 '서린'이다."],
    }.get(mode, ['벌써 움직이네'])
    pipe, ctx = make_context(body=body, comments=[declaration] if mode == 'comment' else [])
    if mode == 'missing_capture':
        del ctx._final_source_original_inputs
    elif mode == 'changed_body':
        ctx.post_data['content_blocks'][0]['text'] = '후행 생성문'
    elif mode == 'search':
        ctx.search_results = [{'snippet': declaration, 'url': 'https://example.invalid/source'}]
    elif mode == 'image':
        ctx.post_data['image_enrichment'] = [{'ocr_text': declaration}]
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=NEW_NAMING)) is None


def test_new_naming_keeps_independent_prose_and_later_direct_author_declaration():
    pipe, ctx = make_context()
    remainder = '서로 부를 때 쓰는 표현이다.'
    assert apply_and_assert_only_context_changed(pipe, ctx,
        make_identity(cultural_context=NEW_NAMING + ' ' + remainder)) == remainder
    pipe, ctx = make_context(body=['친구가 말했다. "', '서린은 은빛 기록의 주인공이다.', '"',
        '서린은 은빛 기록의 주인공이다.'])
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=NEW_NAMING)) == NEW_NAMING


def test_new_naming_pure_work_and_quoted_clause_do_not_hide_later_assertion():
    pipe, ctx = make_context()
    # composite 근거가 없는 순수 작품 계약의 검사 범위를 늘리지 않는다.
    assert apply_and_assert_only_context_changed(pipe, ctx,
        make_identity(store_reason='pure_work_alias', cultural_context=NEW_NAMING)) == NEW_NAMING
    quoted = '“주인공의 성함(서린)”이라고 친구가 말했다.'
    assert apply_and_assert_only_context_changed(pipe, ctx,
        make_identity(cultural_context=quoted + ' ' + NEW_NAMING)) == quoted



@pytest.mark.parametrize('description', [
    "작품명과 '주인공 이름(서린)'을 결합한 표현이다.",
    '작품명과 “주인공의 성함(서린)”을 합친 표현이다.',
    "작품명과 '주인공의 이름은 서린이다'라는 구절을 결합했다.",
    "설명: '주인공 이름(서린)'을 결합한 표현이다.",
], ids=['legacy_phrase_quote', 'new_phrase_quote', 'subject_phrase_quote', 'label_not_speech'])
def test_role_expr01_metalinguistic_quote_does_not_exempt_role_claim(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) is None
    assert ctx._slang_character_role_hold['publication_authority'] is False


@pytest.mark.parametrize('description', [
    "친구가 '주인공 이름(서린)'이라고 말했다.",
    '“주인공의 성함(서린)”이라는 댓글이 있다.',
    '친구가 말했다. "\n주인공의 이름은 서린이다.\n"',
    '친구의 설명: “\n주인공의 성함(서린)을 합친 표현이다.',
], ids=['direct_speech', 'comment_report', 'carried_closed', 'carried_unclosed'])
def test_role_expr01_direct_report_and_carried_speech_are_preserved(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description


def test_role_expr01_reported_quote_cannot_hide_later_independent_naming():
    pipe, ctx = make_context()
    report = "친구가 '주인공 이름(서린)'이라고 말했다."
    own_claim = "작품명과 '주인공 이름(서린)'을 결합한 표현이다."
    assert apply_and_assert_only_context_changed(pipe, ctx,
        make_identity(cultural_context=report + ' ' + own_claim)) == report
    # 동일 표현도 실제 작성자의 작품·이름·역할 선언이 있으면 기존 proof로 보존한다.
    pipe, ctx = make_context(body=['서린은 은빛 기록의 주인공이다.'])
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=own_claim)) == own_claim


@pytest.mark.parametrize('description', [
    '주인공의 이름은 중요한 단서입니다.',
    '주인공의 성함은 중요한 단서이다.',
    '주인공의 이름은 반전의 중요한 단서입니다.',
    "주인공의 이름은 '중요한 단서'입니다.",
], ids=['general_noun_phrase', 'honorific_general', 'long_description', 'quoted_general_phrase'])
def test_role_expr02_unobserved_general_description_is_not_an_invented_name(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description


@pytest.mark.parametrize('description,overrides,person', [
    ('주인공의 이름은 서린이다.', {}, '서린'),
    ('주인공의 성함은 김서린입니다.', {'attached_entity_text': '김서린'}, '김서린'),
    ("주인공의 이름은 '김서린'이다.", {}, '김서린'),
    ('주인공의 성명은 “김서린”입니다.', {}, '김서린'),
], ids=['detected_surface', 'attached_surface', 'new_explicit_ascii_name', 'new_explicit_curly_name'])
def test_role_expr02_observed_or_explicit_new_name_still_needs_role_proof(description, overrides, person):
    pipe, ctx = make_context()
    identity = make_identity(cultural_context=description, **overrides)
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None
    assert ctx._slang_character_role_hold['held'][0]['claims'][0]['name'] == person
    assert ctx._slang_character_role_hold['publication_authority'] is False


def test_role_expr02_surface_binding_is_not_source_authority_but_old_exact_proof_is():
    description = '주인공의 성함은 김서린입니다.'
    pipe, ctx = make_context()
    identity = make_identity(cultural_context=description, attached_entity_text='김서린')
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None
    pipe, ctx = make_context(body=['김서린은 은빛 기록의 주인공이다.'])
    identity = make_identity(cultural_context=description, attached_entity_text='김서린')
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) == description


@pytest.mark.parametrize('description', [
    '주인공 이름(서린)이라고 부르는 표현이며, 다른 리뷰를 친구가 썼다.',
    '주인공의 성함(서린)이라며 부르는 표현이며; 다른 이야기를 친구가 말했다.',
    '주인공 이름(서린)이라고 다른 리뷰를 친구가 썼다.',
    '주인공 이름(서린)이라고 부르는 표현이고 다른 이야기를 친구가 말했다.',
], ids=['review_finding', 'semicolon_clause', 'other_object', 'unpunctuated_other_clause'])
def test_role_expr03_report_verb_in_a_different_clause_does_not_exempt_naming(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) is None


@pytest.mark.parametrize('description', [
    '주인공 이름(서린)이라고 친구가 말했다.',
    '주인공의 성함(서린)이라며 말했다.',
    '주인공의 성함(서린)이라고 다른 독자가 썼다.',
], ids=['direct_subject', 'direct_no_subject', 'direct_determiner'])
def test_role_expr03_only_direct_attached_report_is_preserved(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description


@pytest.mark.parametrize('description', [
    "'주인공 이름(서린)'이 아니다.",
    '“주인공의 성함(서린)”이 맞는가?',
    "만약 '주인공의 성함(서린)'이라면 가능한 설명이다.",
    "'주인공의 이름은 서린이다'라는 주장은 확인되지 않았다.",
])
def test_meta_quoted_claim_keeps_its_own_negation_question_and_condition(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description



@pytest.mark.parametrize('description', [
    '“주인공 이름(서린)\n”이 아니다.',
    '“\n주인공 이름(서린)\n”이 아니다.',
    '“\n주인공의 성함(서린)\n”이 맞는가?',
    "'\n주인공의 이름은 서린이다\n'라는 주장은 확인되지 않았다.",
    '만약 “\n주인공 이름(서린)\n”이라면 가능한 설명이다.',
    '“\n주인공의 성함(서린)\n”이라는 가정 아래의 설명이다.',
    '「\n주인공 이름(서린)\n」이 아닌 표현이다.',
    '“\n‘주인공 이름(서린)’\n”이 아니다.',
], ids=['closing_next_line_negative', 'opening_previous_line_negative',
    'opening_previous_line_question', 'subject_claim_negative', 'if_prefix',
    'direct_assumption', 'corner_quote', 'nested_exact_quotes'])
def test_role_expr04_multiline_exact_quote_keeps_its_attached_qualifier(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description
    assert '_slang_character_role_hold' not in ctx.__dict__


@pytest.mark.parametrize('qualified', [
    '“주인공 이름(서린)\n”이 아니다.',
    '“\n주인공의 성함(서린)\n”이 맞는가?',
    '만약 “\n주인공 이름(서린)\n”이라면 가능한 설명이다.',
], ids=['negative', 'question', 'conditional'])
def test_role_expr04_multiline_qualification_cannot_exempt_later_own_claim(qualified):
    pipe, ctx = make_context()
    proposed = qualified + ' ' + NEW_NAMING
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=proposed)) == qualified
    assert len(ctx._slang_character_role_hold['held']) == 1
    held = ctx._slang_character_role_hold['held'][0]
    lo, hi = held['model_span']
    assert proposed[lo:hi] == held['model_quote']
    assert qualified not in held['model_quote'] and NEW_NAMING in held['model_quote']


@pytest.mark.parametrize('description', [
    '“주인공 이름(서린)\n”을 결합한 표현이다.',
    '작품명과 “\n주인공 이름(서린)\n”을 결합한 표현이다.',
    "작품명과 '\n주인공의 성함은 서린이다\n'라는 구절을 합쳤다.",
    '“\n‘주인공 이름(서린)’\n”을 결합한 표현이다.',
], ids=['closing_next_line', 'opening_previous_line', 'subject_claim', 'nested_exact_quotes'])
def test_role_expr04_multiline_positive_quote_is_held_without_dangling_punctuation(description):
    pipe, ctx = make_context()
    identity = make_identity(cultural_context=description)
    assert apply_and_assert_only_context_changed(pipe, ctx, identity) is None
    held = ctx._slang_character_role_hold['held'][0]
    assert held['model_span'] == [0, len(description)]
    assert held['model_quote'] == description
    for claim in held['claims']:
        start, end = claim['relation_span']
        assert '주인공' in description[start:end]
        start, end = claim['name_span']
        assert '서린' in description[start:end]
    # 기존 원문 proof의 양성은 같은 여러 줄 모델 표현에도 유지한다.
    pipe, ctx = make_context(body=['서린은 은빛 기록의 주인공이다.'])
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description


@pytest.mark.parametrize('suffix,remaining', [
    ('을 합친 표현이다. 다른 주장은 확인되지 않았다.', '다른 주장은 확인되지 않았다.'),
    ('을 합친 표현이며, 다른 주장은 사실이 아니다.', None),
    ('을 합친 표현이며; 다른 설명이 맞는지 물었다.', None),
    ('을 합친 표현이다. 다른 설명이라고 친구가 말했다.', '다른 설명이라고 친구가 말했다.'),
], ids=['later_sentence_negative', 'other_clause_negative', 'other_clause_question', 'later_report'])
def test_role_expr04_qualifier_does_not_jump_to_an_unrelated_clause(suffix, remaining):
    pipe, ctx = make_context()
    proposed = '“\n주인공 이름(서린)\n”' + suffix
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=proposed)) == remaining


def test_role_expr04_removal_keeps_neighboring_prose_and_overlapping_hold_ranges_once():
    prefix, suffix = '먼저 남길 설명이다.', '나중에 남길 설명이다.'
    wrapped = '“\n주인공 이름(서린)\n”을 합친 표현이고 주인공의 성함은 서린이다.'
    proposed = prefix + ' ' + wrapped + ' ' + suffix
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=proposed)) == prefix + ' ' + suffix
    for held in ctx._slang_character_role_hold['held']:
        start, end = held['model_span']
        assert held['model_quote'] == proposed[start:end]
        assert prefix not in held['model_quote'] and suffix not in held['model_quote']


@pytest.mark.parametrize('description', [
    '“\n주인공 이름(서린)\n”이라고 친구가 말했다.',
    '친구의 설명: “\n주인공 이름(서린)\n”.',
], ids=['closing_direct_report', 'opening_speech_prefix'])
def test_role_expr04_multiline_actual_speech_is_preserved(description):
    pipe, ctx = make_context()
    assert apply_and_assert_only_context_changed(pipe, ctx, make_identity(cultural_context=description)) == description
