"""같은 이미지의 직접 대사 기능: 기존32 + 현재49 좁은1 + 합성 main/WAL2.

현재49 원래 full replay2는 diagnostic_current49_comic_partial_replay.py에
기대와 함수 AST 그대로 보존한 미완료 진단이다. 이 파일의 성공으로 대체하지 않는다.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from llm_batch.experts.orchestrator import ExpertType
from llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result,
)
from test_source_image_nsfw_assessment import prepared, canonical, digest
from test_source_bound_nsfw import context_for
from test_source_bound_nsfw_desire import actual_main_sync_and_wrapper
from test_nsfw_assessment_status import image_record, serialize_record


FIXTURE = Path(__file__).parent / "fixtures/current49_comic_dialogue_projection.json"
FIXTURE_SHA = "7b68c123bf3495cfe584344dda8ed0b3fac5fadc71855c41949a8ad498a24a65"
NEUTRAL = "흑백 만화 스타일의 이미지로 인물의 얼굴과 대사가 있다."
OCR = "성관계를 하자"


class ExternalAttemptBlocked(BaseException):
    pass


class NoExternal:
    def __init__(self):
        self.attempts = []

    def __getattr__(self, name):
        def denied(*args, **kwargs):
            self.attempts.append(name)
            raise ExternalAttemptBlocked("COMIC_DIALOGUE_EXTERNAL_ATTEMPT:" + name)
        return denied


@pytest.fixture(scope="module")
def current49():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    value = json.loads(raw)
    assert value["scope"] == "SAVED_EXPERTS_PARTIAL_CONTEXT_NOT_RUNTIME_ARGUMENT_CAPTURE"
    assert value["image_bytes_identity_at_run"] == "UNKNOWN" and value["human_gold"] is False
    row = value["records"]["49"]; packet = row["packet"]
    assert type(packet["post_id"]) is int and packet["index1"] == 49
    assert packet["run_id"] == value["run_id"]
    assert packet["publication_scope_id"] == value["publication_scope_id"]
    assert digest({"post": packet["source_post"], "comments": packet["source_comments"]}) == packet["source_canonical_sha256"]
    assert digest(packet["checkpoint_result"]) == packet["result_canonical_sha256"]
    assert row["expert_sha256"] == {k: digest(v) for k, v in row["experts"].items()}
    assert set(row["experts"]) == {"gatekeeper", "discourse"}
    assert row["image_projection"] == packet["checkpoint_result"]["analysis_result"]["identity"]["image_evidence_catalog"]
    for item in row["image_projection"]:
        assert type(item["block_index"]) is int
        block = packet["source_post"]["content_blocks"][item["block_index"]]
        assert block["type"] == "image" and block["url"] == item["source_url"]
    before = canonical(value)
    yield value
    assert canonical(value) == before and FIXTURE.read_bytes() == raw


def prepare(current49, *, inject=True, ocr=None, visual=None):
    pipe, ctx, record = prepared(current49, 49, inject=False)
    external = NoExternal(); pipe.llm = external; pipe.mcp = external
    image = ctx.post_data["image_enrichment"][0]
    if ocr is not None: image["ocr_text"] = ocr
    if visual is not None: image["visual_summary"] = visual
    if inject: pipe._inject_image_enrichment_blocks(ctx.post_data)
    return pipe, ctx, record, external


def assess(current49, ocr=OCR, visual=NEUTRAL):
    pipe, ctx, record, external = prepare(current49, ocr=ocr, visual=visual)
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, record])
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result["binding_status"] == "BOUND" and result["pixels_verified"] is False
    assert result["publication_authority"] is False
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, record]) == before
    assert external.attempts == []
    return result


@pytest.mark.parametrize("visual", [
    NEUTRAL,
    "만화의 한 장면이며 말풍선이 있다.",
    "동인지 장면과 인물의 대사를 보여 준다.",
    "망가 한 컷에 말풍선이 있다.",
    "코믹스 형식의 그림으로 대사가 보인다.",
    "의학 교재에서 발췌한 안내문을 배경에 둔 만화 장면과 말풍선이 있다.",
])
def test_neutral_visual_paraphrases_keep_same_image_explicit_dialogue(current49, visual):
    result = assess(current49, visual=visual)
    assert result["status"] == "SOURCE_IMAGE_RULE_POSITIVE"
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["rule"] == "SAME_IMAGE_EXPLICIT_OCR_AND_CONTENT_CONTEXT"


@pytest.mark.parametrize("visual,rule,prefix", [
    ("교육 교재에서 발췌한 성인용 만화 장면과 대사가 있다.", "DOCUMENT_SOURCE_ADNOMINAL", "성인용"),
    ("의학 자료에 수록된 만화 스타일의 이미지에 말풍선이 있다.", "DOCUMENT_SOURCE_ADNOMINAL", "만화"),
    ("의학 자료에 수록된 흑백 만화 스타일의 이미지에 말풍선이 있다.", "DOCUMENT_SOURCE_ADNOMINAL", "흑백"),
    ("재활 목적으로 사용되는 성인용 동인지 장면과 대사가 있다.", "MEDICAL_USE_ADNOMINAL", "성인용"),
    ("의료용 만화 장면의 말풍선이다.", "MEDICAL_OR_NONSEXUAL_MODIFIER", "만화"),
    ("소설 제목: 성인용 만화 장면과 대사.", "NAMING_SOURCE", "성인용"),
])
def test_classified_target_includes_optional_adult_prefix(current49, visual, rule, prefix):
    result = assess(current49, visual=visual)
    assert result["status"] == "NO_POSITIVE_IMAGE_RULE" and result["evidence"] == []
    proofs = result["item_outcomes"][0]["excluded_relations"]
    full = [p for p in proofs if p["rule"] == rule and p["source_field"] == "visual_summary"
            and visual[slice(*p["target_span"])].startswith(prefix)
            and any(x in visual[slice(*p["target_span"])] for x in ("장면", "이미지"))]
    assert full
    for p in full:
        lo, hi = p["context_span"]; start, end = p["target_span"]
        assert 0 <= lo < hi == start < end <= len(visual)
        assert p["text_sha256"] == hashlib.sha256(visual.encode()).hexdigest()


@pytest.mark.parametrize("visual", [
    "만화 장면이 아니라 교육 교재다. 말풍선 설명.",
    "만화 장면과 대사가 없다.",
    "만화 장면의 대사는 소설 제목이다.",
    "만화 장면. 말풍선이라는 용어 설명이다.",
    "만화 장면이 아닌 안내문이며 대사가 있다.",
])
def test_negation_and_naming_apply_to_scene_or_dialogue(current49, visual):
    result = assess(current49, visual=visual)
    assert result["status"] == "NO_POSITIVE_IMAGE_RULE" and result["evidence"] == []


@pytest.mark.parametrize("ocr", [
    "성교육 교재", "소설 제목: 성관계하는", "성관계하는 장면이 아니다", "정자에서 물을 마셔",
])
def test_ocr_document_naming_negation_and_locative_homonym_do_not_form_direct_act(current49, ocr):
    result = assess(current49, ocr=ocr)
    assert result["status"] == "NO_POSITIVE_IMAGE_RULE" and result["evidence"] == []


@pytest.mark.parametrize("visual", [
    "장면에 대사가 있다.", "만화책에 대사 글자가 있다.", "만화의 한 장면이다.", "자극적인 대사가 있다.",
])
def test_one_visual_keyword_cannot_replace_comic_scene_and_dialogue_relation(current49, visual):
    result = assess(current49, visual=visual)
    assert result["status"] == "NO_POSITIVE_IMAGE_RULE" and result["evidence"] == []


@pytest.mark.parametrize("external_kind", ["other_image", "search_only"])
def test_other_image_and_search_cannot_complete_same_image_relation(external_kind):
    record = image_record(); url = record["post"]["content_blocks"][0]["url"]
    first = {"block_index": 0, "source_url": url, "ocr_text": OCR, "visual_summary": "풍경 사진이다."}
    second = {"block_index": 1, "source_url": "https://fixture.invalid/second.png", "ocr_text": "", "visual_summary": NEUTRAL}
    if external_kind == "other_image": record["post"]["content_blocks"].append({"type": "image", "url": second["source_url"]})
    pipe, ctx, _ = context_for(record_override=record)
    ctx.post_data["image_enrichment"] = [first, second] if external_kind == "other_image" else [first]
    ctx.search_results = [{"title": "외부 대사", "content": OCR + " " + NEUTRAL, "url": url}]
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result["binding_status"] == "BOUND" and result["evidence"] == []


@pytest.mark.parametrize("value", [False, True])
def test_strict_model_boolean_still_precedes_neutral_comic_rule(value):
    record = image_record(value)
    image = {"block_index": 0, "source_url": record["post"]["content_blocks"][0]["url"],
             "ocr_text": OCR, "visual_summary": NEUTRAL}
    _, _, _, payload, observation = serialize_record(record, images=[image])
    assert payload["analysis"]["is_nsfw"] is value
    assert payload["analysis"]["nsfw_assessment_status"] == "MODEL_REPORTED"
    assert payload["analysis"]["nsfw_assessment_reason"] == "MODEL_BOOLEAN_REPORTED"
    assert observation["nsfw_content_observation"]["image_assessment"]["fallback_executed"] is False


def test_current49_original_catalog_rule_only_keeps_exact_source_binding(current49):
    # 실제 저장 원문/전문가/catalog 투영의 좁은 규칙 대조다. 전체 serializer 재생이 아니다.
    pipe, ctx, record, external = prepare(current49, inject=True)
    before = canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, record])
    capture = ctx._source_bound_nsfw_original_carrier
    image = current49["records"]["49"]["image_projection"][0]
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result["binding_status"] == "BOUND"
    assert result["status"] == "SOURCE_IMAGE_RULE_POSITIVE"
    assert result["fallback_executed"] is True
    assert result["pixels_verified"] is False and result["publication_authority"] is False
    assert len(result["evidence"]) == 1
    ev = result["evidence"][0]
    assert ev["block_index"] == image["block_index"]
    assert ev["ocr_sha256"] == hashlib.sha256(image["ocr_text"].encode()).hexdigest()
    assert ev["visual_summary_sha256"] == hashlib.sha256(image["visual_summary"].encode()).hexdigest()
    assert canonical([ctx.post_data, ctx.comments, ctx.expert_outputs, record]) == before
    assert ctx._source_bound_nsfw_original_carrier == capture and external.attempts == []


@pytest.mark.parametrize("inject", [False, True])
def test_synthetic_neutral_comic_source_serializer_main_and_wal(inject, tmp_path):
    # 기존의 명시 합성 image_record control을 사용한다. 현재49의 원문/전문가 재생이 아니다.
    # 모델 NSFW bool을 새로 만들지 않고 MISSING 상태를 유지한다.
    record = image_record()
    # 명시 합성 입력: 작품 식별 질문이 없는 이미지 게시다. 실제49를 재구성하지 않는다.
    # capture 전에 제목만 정하며 OCR/요약/저장 전문가/모든 판정 기대는 유지한다.
    record["post"]["title"] = "만화 한 컷"
    original = canonical(record)
    pipe, ctx, _ = context_for(record_override=record)
    external = NoExternal(); pipe.llm = external; pipe.mcp = external
    image = {"block_index": 0, "source_url": record["post"]["content_blocks"][0]["url"],
             "ocr_text": OCR, "visual_summary": NEUTRAL}
    ctx.post_data["image_enrichment"] = [deepcopy(image)]
    if inject:
        pipe._inject_image_enrichment_blocks(ctx.post_data)
    source_before = canonical([ctx.post_data, ctx.comments])
    capture = ctx._source_bound_nsfw_original_carrier
    arbiter = ctx.get_expert_output(ExpertType.ARBITER)
    assert isinstance(arbiter, dict) and "is_nsfw" not in arbiter["metadata_synthesis"]
    assert Path(sys.modules[type(pipe).__module__].__file__).resolve() == (
        Path(__file__).resolve().parents[1] / "src/llm_batch/agentic_pipeline.py").resolve()
    output = pipe._context_to_output(ctx); payload = output.model_dump(mode="json")
    proof = pipe.verify_final_source_context_serialization(output, payload, stage="synthetic_comic_native")["nsfw_content_observation"]
    assert payload["analysis"]["is_nsfw"] is True
    assert payload["analysis"]["nsfw_assessment_status"] == "SOURCE_RULE_POSITIVE"
    assert payload["analysis"]["nsfw_assessment_reason"] == "SOURCE_IMAGE_RULE_POSITIVE"
    assert proof["arbiter_status"] == "MISSING" and proof["arbiter_value"] is None
    assert proof["image_assessment"]["binding_status"] == "BOUND"
    assert proof["image_assessment"]["pixels_verified"] is False
    assert proof["image_assessment"]["fallback_executed"] is True
    assert ctx._final_source_projection_call_count == 1
    assert payload["identity"]["novel_identity"] is None
    assert payload["identity"]["promotion_decision"]["publish_allowed"] is False
    ev = proof["image_assessment"]["evidence"][0]
    assert ev["ocr_sha256"] == hashlib.sha256(image["ocr_text"].encode()).hexdigest()
    assert ev["visual_summary_sha256"] == hashlib.sha256(image["visual_summary"].encode()).hexdigest()
    wrapper = actual_main_sync_and_wrapper(payload, ctx.post_data)
    pipe.verify_final_source_context_serialization(output, payload, stage="synthetic_comic_actual_main")
    row = dict(record["post"], comments=deepcopy(record["comments"]), analysis_result=payload)
    wrapped = wrapper(row, output=output, verifier=pipe.verify_final_source_context_serialization)
    scope = build_publication_scope_descriptor(input_file_sha256=digest(record["post"]), post_ids=[ctx.post_id],
        config_hash="synthetic-comic-functional", release_fingerprint="candidate-only")
    path = tmp_path / "commits.jsonl"; registry = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=True)
    commit, created = commit_publication_result(wrapped, registry=registry, attempt_run_id="synthetic-comic-control",
        input_index=1, post_id=ctx.post_id)
    assert created and commit.outcome == "HOLD" and commit.publish_allowed is False
    stored = PublicationCommitRegistry(path, scope_descriptor=scope, create_new=False).result(ctx.post_id)
    assert wrapped.verify_stored_payload(stored, stage="synthetic_comic_wal_readback")["nsfw_content_observation"] == proof
    assert stored["analysis_result"] == payload
    assert canonical(record) == original and canonical([ctx.post_data, ctx.comments]) == source_before
    assert ctx._source_bound_nsfw_original_carrier == capture and external.attempts == []
    before_wal = path.read_bytes(); changed = deepcopy(stored)
    changed["analysis_result"]["analysis"]["nsfw_assessment_reason"] = "MODEL_BOOLEAN_REPORTED"
    with pytest.raises(ValueError): wrapped.verify_stored_payload(changed, stage="synthetic_comic_reason_tamper")
    assert path.read_bytes() == before_wal


@pytest.mark.parametrize("mutation", ["url", "source_title", "carrier_missing"])
def test_new_rule_does_not_relax_source_binding(current49, mutation):
    pipe, ctx, _, _ = prepare(current49)
    if mutation == "url": ctx.post_data["image_enrichment"][0]["source_url"] += "?other"
    elif mutation == "source_title": ctx.post_data["title"] += " changed"
    else: del ctx._source_bound_nsfw_original_carrier
    result = pipe._source_bound_image_nsfw_assessment(ctx)
    assert result["status"] != "SOURCE_IMAGE_RULE_POSITIVE" and result["evidence"] == []
