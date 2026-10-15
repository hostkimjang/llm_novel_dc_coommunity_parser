"""댓글 원문·명명 철회·ASCII 인용 경계. 원형 v2는 보존하고 합성 분기 입력만 정정한다."""
from copy import deepcopy
import socket
import subprocess

import pytest

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.alias_learning import capture_alias_source, eligible_alias_confidence
from llm_batch.domain.models import PostInput
from llm_batch.experts.decoder import DecoderExpert, abbreviation_match_score
from llm_batch.experts.orchestrator import ConversationContext
from llm_batch.grounding.candidate_alias_relation import candidate_alias_relation
from tests.test_source_alias_candidate_preservation import TITLE, ALIAS, URL, NoExternal, context


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("별칭 경계 기능 시험의 새 모델/검색/child 호출 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


def comment_context(tmp_path, *, captured=True, comments=None, declaration=None, alias=ALIAS):
    comments = ([{"comment_id": 701, "author": "댓글 작성자", "content": alias + " 추천"}]
                if comments is None else comments)
    post = PostInput(post_id=130113, title="작품 추천 좀", content_blocks=[], comments=comments)
    pipe = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path,
                          max_iterations=1, native_recovery=True)
    pipe.enable_heretic_live_fetch = False
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post),
                              comments=pipe._extract_comments(post))
    if captured:
        ctx._batch_alias_original_source = capture_alias_source(post)
        ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx.search_results = [{"url": URL, "title": "서평",
        "content": declaration or f"{TITLE}의 약칭은 {alias}이다."}]
    return ctx, post


@pytest.mark.parametrize("comment_id", [701, "701"])
def test_comment_only_witness_keeps_role_original_index_raw_span_and_typed_id(tmp_path, comment_id):
    raw = "  " + ALIAS + " 추천  "
    ctx, post = comment_context(tmp_path, comments=[
        {"comment_id": 700, "content": ""},
        {"comment_id": comment_id, "author": "다른 독자", "content": raw}])
    original_post, comments, rows = deepcopy(ctx.post_data), list(ctx.comments), deepcopy(ctx.search_results)
    capture = deepcopy(ctx._batch_alias_original_source)
    assert "comments" not in capture  # 기존 작성자 전용 학습 capture는 확대하지 않는다.
    witness = candidate_alias_relation(ctx, TITLE, ALIAS)
    assert witness and witness["schema_version"] == "source_candidate_alias_relation_v2"
    assert len(witness["source_hit_details"]) == 1
    hit = witness["source_hit_details"][0]
    assert hit["source"] == "comment" and hit["speaker"] == "comment_author"
    assert hit["position"] == 0 and hit["original_index"] == 1
    assert type(hit["comment_id"]) is type(comment_id) and hit["comment_id"] == comment_id
    assert hit["raw_path"] == "/comments/1/content" and hit["binding"] == "original_comment_capture"
    assert raw[slice(*hit["raw_alias_span"])] == ALIAS
    assert ctx.comments[0][slice(*hit["alias_span"])] == ALIAS
    assert witness["publication_authority"] is witness["learning_authority"] is False
    term = {"original": ALIAS, "source_role": "work_alias",
            "best_match": {"title": TITLE, "confidence": "high"}, "learning_evidence": witness}
    assert eligible_alias_confidence(post.model_dump(), term, TITLE, registries={}) == 0
    assert ctx.post_data == original_post and ctx.comments == comments and ctx.search_results == rows
    assert ctx._batch_alias_original_source == capture


@pytest.mark.parametrize("method", ["_validate_morpheme_in_title", "_guard_no_body_evidence"])
@pytest.mark.parametrize("captured", [False, True])
@pytest.mark.parametrize("exact", [True, False])
def test_actual_decoder_guards_reach_comment_alias_relation_without_borrowing_other_work(
        tmp_path, capsys, method, captured, exact):
    # 이 시험은 합성 댓글의 witness 분기용이다. 정상 0.95 조기 통과는 저장13 시험이 보존한다.
    alias = "달콩별"
    declared_title = TITLE if exact else "푸른 별의 기록자"
    ctx, _ = comment_context(tmp_path, captured=captured, alias=alias,
                            declaration=f"{declared_title}의 약칭은 {alias}이다.")
    before = deepcopy(ctx.post_data), list(ctx.comments), deepcopy(ctx.search_results)
    raw = {"decoded_terms": [{"original": alias, "morphemes": ["완결", "후기"],
        "best_match": {"title": TITLE, "confidence": "high"}, "candidates": [], "interpretations": []}]}
    raw_before = deepcopy(raw)
    assert abbreviation_match_score(alias, TITLE) < 0.5
    assert all(part not in TITLE.replace(" ", "") for part in raw["decoded_terms"][0]["morphemes"])
    decoder = DecoderExpert(NoExternal())
    if method == "_guard_no_body_evidence":
        result = decoder._guard_no_body_evidence(deepcopy(raw), {}, ctx)
        marker = "검색 결과에 명시적 약칭 증거 있음"
    else:
        result = decoder._validate_morpheme_in_title(deepcopy(raw), ctx)
        marker = "명시적 약칭 증거 발견"
    log = capsys.readouterr().err
    assert (marker in log) is exact
    if method == "_validate_morpheme_in_title":
        assert "morpheme_ok=False" in log
    if exact:
        best = result["decoded_terms"][0]["best_match"]
        assert best["title"] == TITLE and best["confidence"].lower() == "high"
        assert not best.get("url")
        witness = candidate_alias_relation(ctx, TITLE, alias)
        assert witness["source_hit_details"][0]["binding"] == (
            "original_comment_capture" if captured else "live_context_comment")
    assert (ctx.post_data, ctx.comments, ctx.search_results) == before and raw == raw_before


@pytest.mark.parametrize("mutation", ["live_text", "capture_text", "capture_path", "capture_index_bool",
                                      "live_order", "author_text"])
def test_comment_and_original_capture_mismatch_cannot_reuse_success(tmp_path, mutation):
    ctx, _ = comment_context(tmp_path, comments=[
        {"comment_id": 701, "content": ALIAS + " 추천"}, {"comment_id": 702, "content": "다른 이야기"}])
    before = candidate_alias_relation(ctx, TITLE, ALIAS)
    assert before
    record = next(x for x in ctx._final_source_original_inputs if x["origin"] == "comment")
    if mutation == "live_text": ctx.comments[0] += " 수정"
    elif mutation == "capture_text": record["raw_text"] += " 변조"
    elif mutation == "capture_path": record["raw_path"] = "/comments/99/content"
    elif mutation == "capture_index_bool": record["original_index"] = True
    elif mutation == "live_order": ctx.comments.reverse()
    else: ctx.post_data["title"] += " 수정"
    assert candidate_alias_relation(ctx, TITLE, ALIAS) is None


def test_comment_alias_absent_does_not_use_external_declaration_as_source(tmp_path):
    ctx, _ = comment_context(tmp_path, comments=[{"comment_id": 1, "content": "다른 작품 추천"}])
    assert candidate_alias_relation(ctx, TITLE, ALIAS) is None


@pytest.mark.parametrize("tail", ["그 명명은 철회한다.", "이 선언은 철회한다.",
                                  "그 명명은 취소한다.", "이 선언은 잘못됐다.",
                                  "이 선언은 취소한다."])
@pytest.mark.parametrize("wiki", [False, True])
def test_same_field_next_sentence_naming_withdrawal_is_not_a_witness(tail, wiki):
    text = f"{TITLE}의 약칭은 {ALIAS}이다. {tail}"
    ctx = context(text)
    if wiki:
        ctx.search_results = [{"url": "https://namu.wiki/w/" + TITLE, "title": TITLE,
                               "content": "한국의 웹소설이다. " + text}]
    assert candidate_alias_relation(ctx, TITLE, ALIAS) is None


@pytest.mark.parametrize("tail", ["그 명명은 철회하지 않았다.", "이 선언은 취소하지 않는다."])
@pytest.mark.parametrize("wiki", [False, True])
def test_denied_naming_withdrawal_preserves_candidate_only_relation(tail, wiki):
    text = f"{TITLE}의 약칭은 {ALIAS}이다. {tail}"
    ctx = context(text)
    if wiki:
        ctx.search_results = [{"url": "https://namu.wiki/w/" + TITLE, "title": TITLE,
                               "content": "한국의 웹소설이다. " + text}]
    before = deepcopy(ctx.post_data), deepcopy(ctx.search_results)
    witness = candidate_alias_relation(ctx, TITLE, ALIAS)
    assert witness and witness["title"] == TITLE and witness["alias"] == ALIAS
    assert witness["publication_authority"] is witness["learning_authority"] is False
    assert (ctx.post_data, ctx.search_results) == before


@pytest.mark.parametrize("tail", ["그 결말은 잘못됐다.", "나는 아직 읽지 않았다.",
                                  "나는 이 소설의 결말에 동의하지 않는다."])
def test_unrelated_reading_or_ending_negation_does_not_retract_naming(tail):
    witness = candidate_alias_relation(context(f"{TITLE}의 약칭은 {ALIAS}이다. {tail}"), TITLE, ALIAS)
    assert witness and witness["publication_authority"] is witness["learning_authority"] is False


@pytest.mark.parametrize("title,alias,text", [
    (TITLE, ALIAS, f"소설 '{TITLE}'의 약칭은 {ALIAS}이다."),
    (TITLE, ALIAS, f"'{ALIAS}'은 {TITLE}의 약칭이다."),
    (TITLE, ALIAS, f"Don't panic. 소설 '{TITLE}'의 약칭은 '{ALIAS}'이다."),
    ("Don't Stop", "돈스탑", "소설 'Don't Stop'의 약칭은 돈스탑이다."),
    ("나는 가끔 춤을 춘다.", "가끔춤", "소설 '나는 가끔 춤을 춘다.'의 약칭은 가끔춤이다."),
])
def test_ascii_title_quotes_close_before_korean_particles_and_keep_english_apostrophe(title, alias, text):
    witness = candidate_alias_relation(context(text, title=title, alias=alias), title, alias)
    assert witness and witness["title"] == title and witness["alias"] == alias
    assert text[slice(*witness["title_span"])] == title
    assert witness["publication_authority"] is witness["learning_authority"] is False


@pytest.mark.parametrize("text", [
    f"'{TITLE}의 약칭은 {ALIAS}이다.'라고 친구가 말했다.",
    f"'{TITLE}의 약칭은 {ALIAS}이다.",
    f"Don't say '{TITLE}의 약칭은 {ALIAS}이다.'라고 누군가 말했다.",
])
def test_full_relation_quote_or_unclosed_speech_is_not_a_declaration(text):
    assert candidate_alias_relation(context(text), TITLE, ALIAS) is None
