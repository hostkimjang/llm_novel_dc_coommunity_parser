"""실제 Arbiter 메시지 조립만 확인한다. 모델 판정·당시 messages 재생 시험이 아니다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_batch.experts.arbiter import ArbiterExpert  # noqa: E402
from llm_batch.experts.orchestrator import ConversationContext, ExpertType  # noqa: E402


FIXTURE = Path(__file__).parent / "fixtures/nsfw_prompt_scope_saved58.json"
FIXTURE_SHA = "2fa09165e5aec84818deb261850ad7768df5ca422a800aaf46a7f348ea822632"
EXTERNAL_TITLE = "합성 외부 자료: 19세 성인 등급과 성적 묘사"
EXPERT_INFERENCE = "합성 전문가 추정: 약어를 외부 성인 작품으로 풀이했다."
IMAGE_A = "https://source.invalid/original-a.png"
IMAGE_B = "https://source.invalid/original-b.png"
FOREIGN_IMAGE = "https://external.invalid/unrelated.png"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class CapturedRequest(BaseException):
    """첫 전송 경계에서 종료해 응답·모델 성공을 만들어 내지 않는다."""


class CaptureOnlyTransport:
    def __init__(self):
        self.calls = []

    def _stream_chat_http(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        raise CapturedRequest()


def context_for(post, comments):
    ctx = ConversationContext(post_id=post.get("post_id", 81001), post_data=deepcopy(post), comments=deepcopy(comments))
    # 아래 검색·전문가 정보는 모두 합성이다. 당시 58번의 입력이라고 주장하지 않는다.
    ctx.search_results = [{
        "title": EXTERNAL_TITLE, "url": "https://external.invalid/work/1",
        "content": "합성 외부 검색 본문의 성인 작품 소개", "query": "합성 검색",
        "_evidence_id": "E001", "_evidence_rank": 1,
    }]
    ctx.set_expert_output(ExpertType.DECODER, {
        "decoded_terms": [{"original": "합성약어", "best_match": {"title": "합성 성인 작품", "confidence": "Low"}}],
        "overall_confidence": "Low",
    })
    ctx.set_expert_output(ExpertType.SYNTHESIZER, {"synthesis_summary": EXPERT_INFERENCE})
    return ctx


def capture_actual_messages(ctx):
    source_before = canonical({"post": ctx.post_data, "comments": ctx.comments})
    transport = CaptureOnlyTransport()
    # analyze, _call_llm, prompt router, catalog와 전문가 요약 조립은 실제 구현을 사용한다.
    # 교체한 것은 외부 전송 객체 하나이며 정상 응답을 반환하지 않는다.
    with pytest.raises(CapturedRequest):
        ArbiterExpert(transport).analyze(ctx)
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["tag"] == "arbiter" and call["use_grammar"] is True
    assert [m["role"] for m in call["messages"]] == ["system", "user"]
    assert canonical({"post": ctx.post_data, "comments": ctx.comments}) == source_before
    return tuple(m["content"] for m in call["messages"])


def assert_scope_contract(system, user):
    for clause in (
        "NSFW 원문 범위 (INPUT CONTENT ONLY)",
        "원문 제목·본문·댓글", "같은 원문 이미지에 출처가 결속된 OCR",
        "다른 이미지·외부 페이지의 글자를 합치지 마세요",
        "결속 검증의 증명은 아닙니다", "단독 NSFW 양성 근거가 아닙니다",
        "욕설·욕설처럼 보이는 작품명/약어·성인 장르의 단순 언급",
        "의학·교육·비성적 설명인지", "다른 성적 내용을 지우지 마세요",
        "원문 인용문이나 댓글 속 명시적 성적 내용도 판독 대상",
        "인용·부정·거절이라는 이유만으로 내용을 없애거나",
        "해당 원문 구절과 출처", "판독 불가·잘린 입력·미확인 이미지",
        "작품 식별 confidence나 장르·관련성 판정",
    ):
        assert clause in system
    assert "NSFW 판독 범위" in user
    assert "외부 검색의 성적 문구·작품 등급·약어 추정만으로" in user
    assert "is_nsfw는 위 POST의 원문 제목·본문·댓글" in user
    assert user.index("NSFW 판독 범위") < user.index("=== EXPERT CONSENSUS ===")
    source_area = user.split("=== 작성자 발화와 근거 출처 ===", 1)[0]
    assert EXTERNAL_TITLE not in source_area and EXPERT_INFERENCE not in source_area
    catalog = user.split("=== SEARCH EVIDENCE CATALOG (CANONICAL EID) ===", 1)[1]
    assert EXTERNAL_TITLE in catalog
    assert EXPERT_INFERENCE in user.split("=== 🔬 SYNTHESIZER", 1)[1]
    # 외부 근거를 삭제하거나 원문으로 이동해 통과시키지 않는다.
    assert '"is_nsfw": boolean' in user
    return source_area


@pytest.fixture(scope="module")
def saved58():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    saved = json.loads(raw)
    assert saved["scope"] == "SAVED_SOURCE_AND_RESULT_NOT_EXACT_MESSAGES_REPLAY"
    row = saved["packet"]
    assert row["index1"] == 58 and type(row["post_id"]) is int
    assert hashlib.sha256(canonical({"post": row["source_post"], "comments": row["source_comments"]})).hexdigest() == row["source_canonical_sha256"]
    assert hashlib.sha256(canonical(row["checkpoint_result"])).hexdigest() == row["result_canonical_sha256"]
    before = canonical(saved)
    yield saved
    assert canonical(saved) == before and FIXTURE.read_bytes() == raw


def test_saved58_source_with_explicitly_synthetic_external_context(saved58):
    row = saved58["packet"]
    system, user = capture_actual_messages(context_for(row["source_post"], row["source_comments"]))
    source_area = assert_scope_contract(system, user)
    assert row["source_post"]["title"] in source_area
    for block in row["source_post"]["content_blocks"]:
        assert block["text"] in source_area
    for comment in row["source_comments"]:
        assert comment["content"] in source_area
    # 저장된 true를 사람 정답 또는 수리 성공 false로 바꾸지 않는다.
    assert row["checkpoint_result"]["analysis_result"]["analysis"]["is_nsfw"] is True


@pytest.mark.parametrize("title,body,comment", [
    ("일상 기록", "오늘은 산책하고 일기를 썼다.", "푹 쉬세요."),
    ("욕설로 쓴 불만", "망할 일정 때문에 화가 난다.", "일정에 대한 불평이다."),
    ("성인 장르 분류", "성인 장르라는 분류명만 언급했다.", "장르 이름을 설명했다."),
    ("작품 이름 질문", "소설 『성인 장르를 쓰지 않겠습니다』라는 제목을 찾는다.", "제목은 문장형이다."),
    ("의학 교육 자료", "성관계 후 감염 예방을 설명하는 보건 교육 문서다.", "비성적 의료 설명이다."),
    ("본문 장면 설명", "등장인물의 노골적인 성행위를 자세히 묘사한 장면이다.", "본문 장면을 지칭했다."),
    ("인용과 거절", "인용된 요구에 동의하지 않는다고 적었다.", '인용문에는 "성관계를 하자"라는 말이 있었다.'),
    ("댓글 범위", "본문에는 연재 일정만 적혀 있다.", "댓글에는 노골적인 성행위 묘사가 적혀 있다."),
    ("비성적 부정 설명", "의학 용어 설명이며 성적 행위 장면은 없다.", "단어만으로 장면을 추정하지 말자."),
], ids=["neutral", "profanity", "genre_mention", "sentence_title", "medical", "explicit_body", "quoted_refused", "explicit_comment", "negated_context"])
def test_source_content_is_preserved_with_external_inference_separated(title, body, comment):
    post = {"post_id": 81001, "title": title, "content_blocks": [{"type": "text", "text": body}]}
    system, user = capture_actual_messages(context_for(post, [{"content": comment}]))
    source_area = assert_scope_contract(system, user)
    assert title in source_area and body in source_area and comment in source_area
    # 이 조합은 프롬프트 회수 대조다. 어떤 bool이 정답인지 모델 없이 판정하지 않는다.


@pytest.mark.parametrize("source_url,second_image", [
    (IMAGE_A, False), (FOREIGN_IMAGE, False), (None, False), (IMAGE_B, True),
], ids=["same_url", "foreign_url", "missing_url", "second_image"])
def test_ocr_source_metadata_reaches_real_prompt_without_binding_authority(source_url, second_image):
    blocks = [{"type": "image", "url": IMAGE_A, "text": "원문 이미지 A"}]
    if second_image:
        blocks.append({"type": "image", "url": IMAGE_B, "text": "원문 이미지 B"})
    raw_ocr = "[이미지 OCR] 합성 대사: 성관계를 요구하는 내용."
    blocks.append({"type": "ocr_text", "url": source_url, "text": raw_ocr})
    post = {"post_id": 81002, "title": "그림 속 문장", "content_blocks": blocks}
    system, user = capture_actual_messages(context_for(post, []))
    source_area = assert_scope_contract(system, user)
    assert raw_ocr in source_area
    metadata = user.split("=== 이미지 출처 메타데이터 (본문 예산 밖) ===", 1)[1]
    origins = [json.loads(raw) for raw in re.findall(r"\[이미지 출처\] (\{[^\n]*?\})", metadata)]
    assert "[이미지 출처] {" not in source_area
    assert origins == [{"type": block["type"], "url": block.get("url")} for block in blocks]
    assert "미확인 출처·다른 이미지·잘린 OCR" in user
    # 동일/다름/누락을 전달하는 시험이다. URL 일치만으로 OCR 정확성·성적 판정을 승인하지 않는다.


def test_literal_ocr_marker_in_original_text_is_not_forged_image_metadata():
    text = "[이미지 OCR]이라는 표식을 텍스트로 설명할 뿐이다."
    post = {"post_id": 81003, "title": "표식 설명", "content_blocks": [{"type": "text", "text": text}]}
    system, user = capture_actual_messages(context_for(post, []))
    source_area = assert_scope_contract(system, user)
    assert text in source_area and "[이미지 출처] {" not in source_area


@pytest.mark.parametrize("metadata", [{"is_nsfw": True}, {"is_nsfw": False}, {"is_nsfw": None}, {}], ids=["true", "false", "null", "missing"])
def test_prompt_contract_does_not_rewrite_synthetic_response_values(metadata):
    payload = {"final_decision": {}, "metadata_synthesis": deepcopy(metadata)}

    class FixedResponseTransport:
        def __init__(self):
            self.calls = []

        def _stream_chat_http(self, **kwargs):
            self.calls.append(deepcopy(kwargs))
            return json.dumps(payload, ensure_ascii=False)

    transport = FixedResponseTransport()
    actual = ArbiterExpert(transport)._call_llm("합성 응답 운반 확인")
    assert len(transport.calls) == 1
    assert actual == payload and actual["metadata_synthesis"] == metadata
    assert "NSFW 원문 범위 (INPUT CONTENT ONLY)" in transport.calls[0]["messages"][0]["content"]
    # 고정 응답은 parser 경계 대조다. 모델 개선·main/WAL 재생 성공을 뜻하지 않는다.


def displayed_body(user):
    return user.split("\nBody: ", 1)[1].split("\nComments (", 1)[0]


@pytest.mark.parametrize("multiple_ocr", [False, True], ids=["one_ocr", "two_ocr"])
def test_long_url_without_image_text_keeps_the_preexisting_ocr_body(multiple_ocr):
    prefix = "https://source.invalid/"
    long_url = prefix + "u" * (400 - len(prefix))
    blocks = [
        {"type": "image", "url": long_url},
        {"type": "ocr_text", "url": long_url, "text": "첫 OCR 구절"},
    ]
    expected_body = "{'type': 'image', 'url': '" + long_url + "'} / 첫 OCR 구절"
    if multiple_ocr:
        blocks.append({"type": "ocr_text", "url": long_url, "text": "둘째 OCR 구절"})
        expected_body += " / 둘째 OCR 구절"
    assert len(long_url) == 400 and len(expected_body) < 800
    ctx = context_for({"post_id": 81004, "title": "", "content_blocks": blocks}, [])
    system, user = capture_actual_messages(ctx)
    assert_scope_contract(system, user)
    assert displayed_body(user).encode() == expected_body.encode()
    assert "첫 OCR 구절" in displayed_body(user)
    if multiple_ocr:
        assert "둘째 OCR 구절" in displayed_body(user)
    metadata = user.split("=== 이미지 출처 메타데이터 (본문 예산 밖) ===", 1)[1]
    origins = [json.loads(raw) for raw in re.findall(r"\[이미지 출처\] (\{[^\n]*?\})", metadata)]
    assert origins == [{"type": block["type"], "url": long_url} for block in blocks]
    assert "첫 OCR 구절" not in metadata and "둘째 OCR 구절" not in metadata


@pytest.mark.parametrize("original_length", [799, 800, 801])
def test_original_800_character_body_boundary_is_unchanged(original_length):
    long_url = "https://source.invalid/" + "u" * 400
    ocr = "O" * (original_length - 6) + "끝"
    original_body = "그림 / " + ocr
    assert len(original_body) == original_length
    # 기존 body_preview 경계의 기대값. URL 메타데이터 길이는 여기에 들어가지 않는다.
    visible = original_body if original_length <= 800 else original_body[:800] + "..."
    expected_body = visible + f"\n[TEXT_CONTENT: {original_length - 3}자 텍스트 존재 — 이미지 전용 포스트 아님]"
    post = {"post_id": 81005, "title": "경계", "content_blocks": [
        {"type": "image", "url": long_url, "text": "그림"},
        {"type": "ocr_text", "url": long_url, "text": ocr},
    ]}
    system, user = capture_actual_messages(context_for(post, []))
    assert_scope_contract(system, user)
    assert displayed_body(user).encode() == expected_body.encode()
    assert ("끝" in displayed_body(user)) is (original_length <= 800)
    assert "[이미지 출처] {" not in displayed_body(user)
    metadata = user.split("=== 이미지 출처 메타데이터 (본문 예산 밖) ===", 1)[1]
    assert long_url in metadata and ocr not in metadata


def test_source_metadata_does_not_reintroduce_ninth_block_text_or_url():
    first_eight = [{"type": "text", "text": f"원문{i}"} for i in range(8)]
    hidden = {"type": "ocr_text", "url": FOREIGN_IMAGE, "text": "미리보기 밖 OCR_TEST_NINTH"}
    text_count = 24 + len(hidden["text"])
    expected_body = " / ".join(f"원문{i}" for i in range(8))
    expected_body += f"\n[TEXT_CONTENT: {text_count}자 텍스트 존재 — 이미지 전용 포스트 아님]"
    post = {"post_id": 81006, "title": "원래 8블록 범위", "content_blocks": first_eight + [hidden]}
    system, user = capture_actual_messages(context_for(post, []))
    assert_scope_contract(system, user)
    assert displayed_body(user).encode() == expected_body.encode()
    assert hidden["text"] not in user and FOREIGN_IMAGE not in user
    assert "=== 이미지 출처 메타데이터 (본문 예산 밖) ===" not in user
