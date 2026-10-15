"""저장65 부분 입력과 명시 합성 대조. 원형 전체 재생/공개 정답 주입이 아니다."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from urllib.parse import quote

import pytest

import llm_batch.agentic_pipeline as pipeline_module
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import DetectedTitle, NovelIdentity, PickvelIdentity, PickvelOutputItemV2
from llm_batch.domain.alias_learning import capture_alias_source
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.grounding.character_work_candidate import (
    CHARACTER_WORK_CANDIDATE_HOLD, character_work_candidates,
)


FIXTURE = Path(__file__).parent / "fixtures/current65_partial_context.json"
FIXTURE_SHA = "8fa2b6d601669bbb170e352a344ed7ac8ab9a8807b96839879a60a39db9fd6cd"


class ExternalForbidden(BaseException):
    pass


def forbidden(*args, **kwargs):
    raise ExternalForbidden("NO_EXTERNAL_IN_PARTIAL_SOURCE65_TEST")


class NoExternal:
    def __getattr__(self, name):
        return forbidden


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    # 실제 PageAnalyzer 생성자의 캐시 폴더도 새 tmp 안에 생성한다. 생성자를 stub하지 않는다.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    p = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(), output_dir=tmp_path / "output",
        native_recovery=True, max_iterations=1)
    p.enable_heretic_live_fetch = False
    p.enable_url_fetch_disk_cache = False
    p._use_session_knowledge = False
    assert Path(pipeline_module.__file__).resolve() == (
        Path(__file__).resolve().parents[1] / "src/llm_batch/agentic_pipeline.py").resolve()
    return p


def saved_context():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    f = json.loads(raw)
    assert canonical({"post": f["source_post"], "comments": f["source_comments"]}) == f["source_canonical_sha256"]
    post = deepcopy(f["source_post"])
    post["image_enrichment"] = deepcopy(f["image_evidence_catalog"])
    ctx = ConversationContext(post_id=f["post_id"], post_data=post, comments=deepcopy(f["source_comments"]))
    for entry in f["saved_expert_outputs_in_order"]:
        assert canonical(entry["value"]) == entry["parsed_json_canonical_sha256"]
        ctx.set_expert_output(ExpertType(entry["expert"]), deepcopy(entry["value"]))
    ctx.search_results = [deepcopy(f["e001"])]
    ctx.suspected_titles = deepcopy(ctx.get_expert_output(ExpertType.ARBITER)["final_decision"]["suspected_titles"])
    discourse = ctx.get_expert_output(ExpertType.DISCOURSE)["discourse_analysis"]
    ctx.discourse_intent = discourse["intent"]
    ctx.discourse_warning = "discuss_genre(medium)"
    ctx.primary_domain = discourse["primary_domain"]
    return ctx


def synthetic_context(title="은월전", character="서하진"):
    source = f"{character} 눈 멀게 할 인물이 누가 있나"
    url = "https://namu.wiki/w/" + quote(title + "/등장인물", safe="/")
    ctx = ConversationContext(post_id=650065,
        post_data={"post_id": 650065, "title": source, "content_blocks": []}, comments=[])
    ctx.search_results = [{"eid": "E001", "title": title + "/등장인물 - 나무위키", "url": url,
        "snippet": f"개요 웹소설 {title}의 등장인물을 정리한 문서. {character}과 마주쳤다."}]
    ctx.set_expert_output(ExpertType.DECODER, {"decoded_terms": [{"original": character,
        "is_author_name": False, "interpretations": [{"type": "character_name", "value": character, "context_fit": "high"}],
        "grounding": {"is_grounded": True, "anchor_type": "character_mention", "anchor_evidence": source},
        "candidates": [{"official_novel_title": title, "url": url, "morphological_score": 1.0}],
        "best_match": {"title": title, "confidence": "low"}}]})
    return ctx


def build(pipeline, ctx, relevant=False):
    vf = deepcopy((ctx.get_expert_output(ExpertType.VERIFIER) or {}).get("verification_result") or {})
    return pipeline._build_title_candidates_with_snapshot(ctx=ctx, is_relevant=relevant,
        official_title=None, heretic_url=None, confidence="None", vf_result=vf, max_items=6)


def input_copy(ctx):
    return deepcopy((ctx.post_data, ctx.comments, ctx.expert_outputs, ctx.search_results, ctx.suspected_titles))


def assert_low_hold(candidate, title):
    assert candidate.official_title == title
    assert candidate.confidence == "Low" and candidate.reference_role == "candidate"
    assert candidate.heretic_url is None and candidate.alias_or_mention is None
    assert candidate.locked is False and candidate.source_tier == "llm_only"
    assert CHARACTER_WORK_CANDIDATE_HOLD in candidate.negative_evidence
    assert any(item.startswith("source_character_work_proof:") for item in candidate.negative_evidence)


@pytest.mark.parametrize("relevant", [False, True])
def test_saved65_real_builder_retains_low_only_after_both_observed_returns(pipeline, relevant):
    ctx = saved_context()
    before = input_copy(ctx)
    candidates, snapshot = build(pipeline, ctx, relevant)
    matching = [c for c in candidates if c.official_title == "당문전"]
    assert len(matching) == 1
    assert_low_hold(matching[0], "당문전")
    assert any(x["official_title"] == "당문전" for x in snapshot.retained_sources)
    assert snapshot.to_ledger_dict()["upstream_completeness"] == "UNKNOWN"
    assert input_copy(ctx) == before
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA


def test_legacy_mention_boolean_uses_character_original_not_literal_title(pipeline):
    ctx = saved_context()
    raw = " ".join([ctx.post_data["title"], *(b.get("text", "") for b in ctx.post_data["content_blocks"])])
    assert "당문전" not in raw and "유진광" in raw
    assert pipeline._title_mentioned_in_post_main_context(ctx, "당문전") is True
    assert pipeline._title_mentioned_in_post_context(ctx, "당문전") is True
    assert pipeline._full_title_mentioned_in_raw_post_context(ctx, "당문전") is False
    proof = character_work_candidates(ctx)[0]
    assert proof["character"] == "유진광" and proof["alias_authority"] is False


@pytest.mark.parametrize("title,character", [("은월전", "서하진"), ("긴 항로의 기록", "백도윤"), ("별빛 문답", "청연")])
def test_relation_is_not_bound_to_one_name_or_title(pipeline, title, character):
    ctx = synthetic_context(title, character)
    proof = character_work_candidates(ctx)
    assert len(proof) == 1 and proof[0]["title"] == title
    candidates, _ = pipeline._finalize_title_candidate_generation(scored=[], final_norm="", max_items=6, ctx=ctx)
    assert len(candidates) == 1
    assert_low_hold(candidates[0], title)


@pytest.mark.parametrize("mutation", [
    "source_person_absent", "source_person_only_comment", "source_person_quoted", "source_derived_body",
    "anchor_drift", "not_character", "author_role", "competing_work_role", "not_grounded",
    "wrong_row_url", "different_url_owner", "different_headline_owner", "missing_owned_header",
    "unrelated_header", "header_negated", "person_absent_from_document", "person_other_work",
    "person_negated", "diagnostic", "catalog_diagnostic", "non_novel_media", "other_domain", "typed_post_id_mismatch",
])
def test_missing_or_competing_relationship_never_creates_new_hold(mutation):
    ctx = synthetic_context()
    term = ctx.expert_outputs["decoder"]["decoded_terms"][0]
    row = ctx.search_results[0]
    if mutation == "source_person_absent": ctx.post_data["title"] = "다른 인물을 묻는다"
    elif mutation == "source_person_only_comment":
        ctx.comments = [ctx.post_data["title"]]; ctx.post_data["title"] = "질문"
    elif mutation == "source_person_quoted": ctx.post_data["title"] = '친구가 "' + ctx.post_data["title"] + '"라고 물었다'
    elif mutation == "source_derived_body":
        ctx.post_data["content_blocks"] = [{"type": "text", "text": ctx.post_data["title"], "from_ocr": True}]; ctx.post_data["title"] = "이미지"
    elif mutation == "anchor_drift": term["grounding"]["anchor_evidence"] = "없는 이전 원문"
    elif mutation == "not_character": term["interpretations"][0]["type"] = "general_noun"
    elif mutation == "author_role": term["is_author_name"] = True
    elif mutation == "competing_work_role": term["interpretations"].append({"type": "work_alias", "value": "은월전"})
    elif mutation == "not_grounded": term["grounding"]["is_grounded"] = "true"
    elif mutation == "wrong_row_url": term["candidates"][0]["url"] += "?from=another"
    elif mutation == "different_url_owner": row["url"] = "https://namu.wiki/w/다른작품/등장인물"
    elif mutation == "different_headline_owner": row["title"] = "다른작품/등장인물 - 나무위키"
    elif mutation == "missing_owned_header": row["snippet"] = "서하진과 은월전을 비교한 문서."
    elif mutation == "unrelated_header": row["snippet"] = "개요 웹소설 다른작품의 등장인물을 정리한 문서. 서하진과 마주쳤다."
    elif mutation == "header_negated": row["snippet"] = "개요 웹소설 은월전의 등장인물을 정리한 문서가 아니다. 서하진 언급."
    elif mutation == "person_absent_from_document": row["snippet"] = "개요 웹소설 은월전의 등장인물을 정리한 문서. 백도윤과 마주쳤다."
    elif mutation == "person_other_work": row["snippet"] = "개요 웹소설 은월전의 등장인물을 정리한 문서. 서하진은 다른 작품의 인물이다."
    elif mutation == "person_negated": row["snippet"] = "개요 웹소설 은월전의 등장인물을 정리한 문서. 서하진은 이 작품의 등장인물이 아니다."
    elif mutation == "diagnostic": row["_ocr_diagnostic_only"] = True
    elif mutation == "catalog_diagnostic": row["purpose"] = "image_ocr_diagnostic_probe"
    elif mutation == "non_novel_media": row["media_type"] = "webtoon"
    elif mutation == "other_domain": row["url"] = row["url"].replace("namu.wiki", "namu.wiki.example.com")
    elif mutation == "typed_post_id_mismatch": ctx.post_data["post_id"] = str(ctx.post_id)
    before = input_copy(ctx)
    assert character_work_candidates(ctx) == []
    assert input_copy(ctx) == before


def test_same_person_competing_owner_documents_do_not_select_one():
    ctx = synthetic_context()
    row = deepcopy(ctx.search_results[0])
    row.update(title="다른작품/등장인물 - 나무위키", url="https://namu.wiki/w/다른작품/등장인물",
        snippet="개요 웹소설 다른작품의 등장인물을 정리한 문서. 서하진과 마주쳤다.")
    ctx.search_results.append(row)
    assert character_work_candidates(ctx) == []


@pytest.mark.parametrize("field", ["title", "body", "comment"])
def test_preserved_source_capture_drift_does_not_reuse_proof(field):
    ctx = synthetic_context()
    ctx._final_source_original_inputs = (
        {"origin": "post_title", "original_index": 0, "caller_disposition": "passed_to_source", "raw_text": ctx.post_data["title"]},
    )
    if field == "title":
        ctx._final_source_original_inputs[0]["raw_text"] = "과거 원문"
    elif field == "body": ctx.post_data["content_blocks"] = [{"type": "text", "text": "추가 본문"}]
    else: ctx.comments = ["보존되지 않은 댓글"]
    assert character_work_candidates(ctx) == []


def test_existing_ranked_candidate_is_not_downgraded_or_given_new_authority(pipeline):
    ctx = synthetic_context()
    rows = [(7, False, {"title": "은월전", "confidence": "Medium", "url": None, "alias": None, "locked": False})]
    original = deepcopy(rows)
    candidates, _ = pipeline._finalize_title_candidate_generation(scored=rows, final_norm="", max_items=6, ctx=ctx)
    assert len(candidates) == 1 and candidates[0].confidence == "Medium"
    assert CHARACTER_WORK_CANDIDATE_HOLD not in (candidates[0].negative_evidence or [])
    assert rows == original


def test_existing_final_title_and_cap_are_not_displaced(pipeline):
    ctx = synthetic_context()
    rows = [(5, True, {"title": "정상 확정 제목", "confidence": "High", "locked": True})]
    candidates, _ = pipeline._finalize_title_candidate_generation(scored=rows,
        final_norm=pipeline._normalize_match_text("정상 확정 제목"), max_items=1, ctx=ctx)
    assert len(candidates) == 1 and candidates[0].official_title == "정상 확정 제목"
    assert candidates[0].reference_role == "primary"
    candidates, snapshot = pipeline._finalize_title_candidate_generation(scored=rows, final_norm="", max_items=1, ctx=ctx)
    assert candidates[0].official_title == "정상 확정 제목" and len(candidates) == 1
    assert snapshot.to_ledger_dict()["unique_valid_source_count"] == 2


def test_saved65_real_reference_consumers_keep_hold_out_of_public_roles(pipeline):
    ctx = saved_context()
    before = input_copy(ctx)
    candidates, _ = build(pipeline, ctx)
    vf = deepcopy(ctx.get_expert_output(ExpertType.VERIFIER)["verification_result"])
    annotated, primary, mentioned, future = pipeline._annotate_work_references(
        ctx=ctx, title_candidates=candidates, official_title=None, vf_result=vf)
    held = [c for c in annotated if c.official_title == "당문전"]
    assert len(held) == 1
    assert_low_hold(held[0], "당문전")
    assert primary is None and mentioned == [] and future is None
    assert pipeline._collect_secondary_reference_works(ctx=ctx, official_title=None,
        primary_work=None, mentioned_works=held, comparison_target=held[0], recommendation_candidates=held) == []
    assert input_copy(ctx) == before


def test_real_primary_interpretation_and_typed_export_do_not_promote_the_hold(pipeline):
    ctx = saved_context()
    ctx._batch_alias_original_source = capture_alias_source(ctx.post_data)
    candidates, snapshot = build(pipeline, ctx)
    held = next(c for c in candidates if c.official_title == "당문전")
    vf = deepcopy(ctx.get_expert_output(ExpertType.VERIFIER)["verification_result"])
    # 일부 caller가 후보를 primary 위치에 넘겨도 adjacent→secondary 우회를 허용하지 않는다.
    subject = pipeline._derive_primary_subject_interpretation(ctx=ctx,
        topicality="adjacent_relevant", subtype="genre_trope_discussion",
        discussion_type="trope_discussion", official_title=None, primary_work=held,
        mentioned_works=[], comparison_target=None, recommendation_candidates=[],
        metadata={}, verification_result=vf)
    assert subject["secondary_reference_works"] == []
    annotated, primary, mentioned, future = pipeline._annotate_work_references(
        ctx=ctx, title_candidates=candidates, official_title=None, vf_result=vf)
    # Builder/소비자의 실제 반환을 typed 모델로 투영한다. _context_to_output 전체 재생은 아니다.
    identity = PickvelIdentity(is_relevant=False, is_novel_related=True,
        is_resolved_work_discussion=False, title_resolution_state="adjacent",
        title_resolution_allowed=False, work_resolution="none", discussion_type="trope_discussion",
        novel_identity=NovelIdentity(official_title=None, heretic_url=None, confidence="None"),
        title_candidates=annotated, primary_work=primary, mentioned_works=mentioned,
        future_watch_target=future, secondary_reference_works=subject["secondary_reference_works"])
    envelope = pipeline._build_final_batch_context_learning_envelope(ctx, identity)
    typed = PickvelOutputItemV2(post_id=ctx.post_id, identity=identity,
        batch_context_learning_envelope=envelope)
    reopened = PickvelOutputItemV2.model_validate_json(typed.model_dump_json())
    assert reopened.identity.novel_identity.official_title is None
    assert reopened.identity.novel_identity.heretic_url is None
    assert_low_hold(next(c for c in reopened.identity.title_candidates if c.official_title == "당문전"), "당문전")
    assert reopened.identity.primary_work is None
    assert reopened.identity.mentioned_works == [] and reopened.identity.secondary_reference_works == []
    assert envelope["decoded_terms"] == [] and envelope["identified_author"] is None
    assert envelope["identified_characters"] == []
    assert snapshot.to_ledger_dict()["upstream_completeness"] == "UNKNOWN"


@pytest.mark.parametrize("tamper", ["fingerprint", "url", "alias", "confidence", "lock"])
def test_hold_marker_cannot_inject_reference_authority(pipeline, tamper):
    ctx = saved_context()
    candidates, _ = build(pipeline, ctx)
    held = next(c for c in candidates if c.official_title == "당문전")
    if tamper == "fingerprint": held.negative_evidence = [CHARACTER_WORK_CANDIDATE_HOLD, "source_character_work_proof:forged"]
    elif tamper == "url": held.heretic_url = ctx.search_results[0]["url"]
    elif tamper == "alias": held.alias_or_mention = "유진광"
    elif tamper == "confidence": held.confidence = "High"
    elif tamper == "lock": held.locked = True
    annotated, primary, mentioned, future = pipeline._annotate_work_references(
        ctx=ctx, title_candidates=[held], official_title=None,
        vf_result=ctx.get_expert_output(ExpertType.VERIFIER)["verification_result"])
    assert not any(CHARACTER_WORK_CANDIDATE_HOLD in (c.negative_evidence or []) for c in annotated)
    assert primary is None and mentioned == [] and future is None
