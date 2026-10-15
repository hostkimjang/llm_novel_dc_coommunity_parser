"""기록된 원문·expert 관측의 국소 serializer 회귀. 인간 정답이나 새 추론이 아니다."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.ledger.publication_commit import compute_publication_decision_commit

# 고정 packet 원문과 완료된 worker log 구간만 복사했다. 원래 메모리 context의 복원은 아니다.
# 각 raw log 구간 SHA 및 packet SHA는 아래 fixture에 함께 남긴다. 실행 중 결과 파일을 읽지 않는다.
RECORDED = json.loads('{"10":{"scope":"LOG_DERIVED_RECONSTRUCTED_CONTEXT","post":{"gallery_id":"genrenovel","post_id":11718086,"title":"난 찐친 5명이나 있네 ㅋㅋ 친구없는 찐따로 안 살아서 다행","author":"ㅇㅇ","created_at":"2026-01-28 18:40:26","url":"https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11718086","content_blocks":[{"type":"text","text":"118.235"},{"type":"text","text":"39.7"},{"type":"text","text":"ㅇㅇ"},{"type":"text","text":"노벨쨩"},{"type":"text","text":"피아쨩"},{"type":"text","text":"너희 내 친구쟈나"}],"page_no":30,"comments":["내친구 ㅇㅇ - dc App","","통피는 단수가 아니다",""]},"experts":{"gatekeeper":{"is_noise":true,"noise_reason":"본문이 특정 소설 작품에 대한 논의가 아닌, 작성자의 개인적인 일상(친구 관계)을 언급하며 커뮤니티 은어(노벨쨩, 피아쨩 등)를 사용한 잡담/밈 형태의 게시글임. 본문에 등장하는 \'노벨쨩\', \'피아쨩\'은 플랫폼(노벨피아)이나 특정 캐릭터를 지칭할 가능성이 있으나, 전체 담론이 작품의 서사나 내용을 다루지 않고 작성자의 상태를 과시하는 일상적 발화임.","post_type":"community_banter","detected_entities":{"possible_titles":["노벨쨩","피아쨩"],"possible_authors":[],"possible_characters":[],"platforms_mentioned":["노벨피아"]},"key_terms":["찐친","노벨쨩","피아쨩"],"context_clues":{"has_url_in_comments":false,"has_specific_names":false,"is_asking_recommendation":false,"is_spoiler_discussion":false,"has_comment_title_answer":true,"comment_title_candidates":["통피는 단수가 아니다"],"comment_title_merge_candidates":[],"comment_title_candidate_details":[{"text":"통피는 단수가 아니다","comment_index":1,"line_index":0,"speech_act":"explanation","has_at_mention":false,"reply_level":0,"reply_to_comment_id":null,"author":"ㅇㅇ","title_assertion_basis":null}]},"search_requests":[],"confidence":"high","notes":"제목과 본문의 맥락이 \'친구 관계\'라는 현실 세계의 일상을 다루고 있으며, 본문의 \'노벨쨩\', \'피아쨩\'은 노벨피아 플랫폼 이용자나 특정 밈을 지칭하는 것으로 보이나 실제 작품 토론으로 보기 어려움. 댓글 또한 원문에 적힌 IP(통피)를 언급하는 커뮤니티 내부의 농담임."},"discourse":{"discourse_analysis":{"primary_domain":"memes_humor","domain_confidence":"high","domain_evidence":["찐친","찐따","노벨쨩","피아쨩","통피는 단수가 아니다"],"secondary_domains":["novel_literature"],"intent":"make_joke","intent_confidence":"medium","speech_act":"banter","target_kind":"community","is_coherent":true,"coherence_reason":"제목에서 언급한 \'친구\'가 본문의 IP 주소와 특정 캐릭터(노벨쨩, 피아쨩)를 지칭하는 유머임을 댓글을 통해 확인할 수 있음.","title_novel_terms":[],"title_body_consistency":false,"consistency_note":"제목은 실제 친구 관계를 언급하는 듯하나, 본문은 IP 주소와 커뮤니티 밈(캐릭터 이름)을 나열하며 반전 유머를 제공함.","is_association_not_discussion":true,"association_evidence":"본문의 \'노벨쨩\', \'피아쨩\'은 특정 작품의 캐릭터라기보다 커뮤니티 내에서 사용되는 밈적 표현으로 보임.","search_suggestions":[],"real_subject":"작성자가 자신의 IP 주소와 커뮤니티 밈을 \'친구\'라고 부르며 자학적으로 유머를 던지는 글","author_question_span":null,"author_question_target":null,"author_recommendation_span":null,"author_recommendation_is_direct":false,"reasoning":"작성자는 제목에서 친구가 많다고 허세를 부리지만, 본문에는 IP 주소(118.235.39.7)와 \'노벨쨩\', \'피아쨩\'이라는 밈적 명칭만 나열하고 있다. 이는 혼자 커뮤니티를 이용하는 상황을 희화화한 전형적인 커뮤니티 유머(shitposting)이다.","source_bound_recommendation_request":false,"image_topic_relation":{"state":"no_image","source":"author_spans"},"semantic_seed_review":{"post_intent":"작성자가 자신의 IP 주소와 커뮤니티 밈을 친구라고 지칭하며 자학적인 유머를 던지는 글","content_interpretation":"표현 오타/축약 패턴(범용)으로만 처리하며, 특정 인명이나 작품명을 지시하는 직접적인 앵커가 부족함","is_specific_work_discussion":false,"recommended_intent":"make_joke","recommended_target_kind":"community","warnings":["작품명 후보가 실제 작품이 아닌 작성자의 유머적 대상(인명/밈)일 가능성이 높음"]},"warnings":["semantic_seed_review_search_suggestions_removed","semantic_seed_review_specific_work_denied"]}}},"source_packet":{"path":"C:\\\\Users\\\\kimjang\\\\Documents\\\\GitHub\\\\llm_novel_dc_coommunity_parser\\\\out\\\\development_plan_20261010\\\\p4_reapproval_v1\\\\final80_parallel12_v1\\\\progress_review_v1\\\\review_packets.jsonl","sha256":"aad28693a619e4e314ba21f76a0244df1a200574a450f119b89e94f228f0089d","jsonl_line1":10},"expert_log":{"path":"C:\\\\Users\\\\kimjang\\\\Documents\\\\GitHub\\\\llm_novel_dc_coommunity_parser\\\\logs\\\\expert_run_20261012_145104_574531_W9.log","raw_byte_offset":187,"raw_byte_length":39771,"raw_block_sha256":"fa8eda9d666dd8a04656432534ca5a8f30cddd377989c051c451066661fe0c87"},"source_canonical_sha256":"60e264737a533d838a2620b00e4c8bd8b1ad6589e8a90a4376211c3e5ace7f43","source_comments_canonical_sha256":"70b3cb8f2136102f5fd7d707258932b548440c69a3c7a1dbb29734fba5dcc67f","pre_fix":{"discussion_type":"undecodable_reference","subtype":"unresolved_work","promotion_decision":{"status":"reject","publish_allowed":false,"official_title":null,"official_url":null,"candidate_preserved":false,"reason_codes":["no_candidate_title","row_discussion_missing","title_resolution_state_not_publishable","context_only","work_resolution_not_publishable","scope_unknown","scope_not_current_work","serializer_candidate_removed"],"bypassed_gate":false,"scope":{"scope_kind":"unknown","confidence":"low","direct_bridge_sources":[],"competing_candidates":[],"conflict_reason_codes":["serializer_candidate_removed"]},"input_fingerprint":"b8932cd48e04da3b376b02bd3a86d03be6d10ba627f8396d0f105f2f9e993856","contract_version":"promotion_contract_v2"},"publish_contract_input_fingerprint":"b8932cd48e04da3b376b02bd3a86d03be6d10ba627f8396d0f105f2f9e993856"}},"61":{"scope":"LOG_DERIVED_RECONSTRUCTED_CONTEXT","post":{"gallery_id":"genrenovel","post_id":9140648,"title":"장갤<< 의외로 분탕은 많은데","author":"ㅇㅇ","created_at":"2024-08-16 03:36:13","url":"https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=9140648","content_blocks":[{"type":"text","text":"병신이 더많음"}],"page_no":46440,"comments":[]},"experts":{"gatekeeper":{"is_noise":true,"noise_reason":"semantic_seed_review가 제목/검색 seed를 작품명 후보가 아닌 자연어 문맥으로 낮췄고, 이미지/OCR/VLM 또는 강한 작품 앵커가 없어 Decoder 검색·해독으로 재승격하지 않음","post_type":"short_reaction","detected_entities":{"possible_titles":["장갤<< 의외로 분탕은 많은데"],"possible_authors":[],"possible_characters":[],"platforms_mentioned":[]},"key_terms":["장갤<< 의외로 분탕은 많은데"],"context_clues":{"short_post_fast_path":true,"body_length":7,"body_text":"병신이 더많음","short_post_title_surface":"장갤<< 의외로 분탕은 많은데"},"search_requests":[],"confidence":"medium","notes":"Short-post Fast-Path: body=7자, 제목 기반 판정 위임"},"discourse":{"discourse_analysis":{"primary_domain":"meta_platform","domain_confidence":"high","domain_evidence":["장갤","분탕","병신"],"secondary_domains":[],"intent":"express_opinion","intent_confidence":"medium","speech_act":"other","target_kind":"community","is_coherent":true,"coherence_reason":"제목에서 제기한 커뮤니티(장갤) 내 이용자 성향에 대한 화제가 본문에서 비속어를 사용해 강조하며 일관되게 이어짐","title_novel_terms":[],"title_body_consistency":true,"consistency_note":null,"is_association_not_discussion":false,"association_evidence":null,"search_suggestions":[],"real_subject":"장르소설 갤러리 이용자들의 수준에 대한 작성자의 부정적인 견해","author_question_span":null,"author_question_target":null,"author_recommendation_span":null,"author_recommendation_is_direct":false,"reasoning":"작성자는 \'장갤(장르소설 갤러리)\'이라는 특정 커뮤니티를 지칭하며, 해당 커뮤니티의 이용자들이 분탕(트롤)보다 더 심각한 수준(비속어 사용)이라고 비난하는 의견을 표출하고 있다. 이는 작품에 대한 논의가 아닌 커뮤니티 자체의 분위기에 대한 불만이다.","source_bound_recommendation_request":false,"image_topic_relation":{"state":"no_image","source":"author_spans"},"semantic_seed_review":{"post_intent":"장르소설 갤러리 이용자들의 수준에 대한 작성자의 부정적인 견해 표출","content_interpretation":"표현 오타/축약 패턴(범용)을 포함한 커뮤니티 내 이용자 비하성 발언","is_specific_work_discussion":false,"recommended_intent":"express_opinion","recommended_target_kind":"community","warnings":[]},"warnings":["semantic_seed_review_non_title_terms_removed","semantic_seed_review_search_suggestions_removed","semantic_seed_review_specific_work_denied"],"semantic_seed_review_context_terms":["장갤"]}}},"source_packet":{"path":"C:\\\\Users\\\\kimjang\\\\Documents\\\\GitHub\\\\llm_novel_dc_coommunity_parser\\\\out\\\\development_plan_20261010\\\\p4_reapproval_v1\\\\final80_parallel12_v1\\\\progress_review_v7\\\\review_packets.jsonl","sha256":"99b6a805fae245dc2b1967822564c940c2719a40941c7415f10dee77f5e1f448","jsonl_line1":59},"expert_log":{"path":"C:\\\\Users\\\\kimjang\\\\Documents\\\\GitHub\\\\llm_novel_dc_coommunity_parser\\\\logs\\\\expert_run_20261012_145104_574531_W3.log","raw_byte_offset":539864,"raw_byte_length":27182,"raw_block_sha256":"112b15603b188b0740e10d589f36e1a9e971cb0f6f7887ca5ec1c722eb227a20"},"source_canonical_sha256":"cb330d98c28ea6b6dde92303b2de03df6ee43b7723ac1f5f29da6d2d4655d590","source_comments_canonical_sha256":"4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945","pre_fix":{"discussion_type":"undecodable_reference","subtype":"unresolved_work","promotion_decision":{"status":"reject","publish_allowed":false,"official_title":null,"official_url":null,"candidate_preserved":false,"reason_codes":["no_candidate_title","row_discussion_missing","title_resolution_state_not_publishable","context_only","work_resolution_not_publishable","scope_unknown","scope_not_current_work","serializer_candidate_removed"],"bypassed_gate":false,"scope":{"scope_kind":"unknown","confidence":"low","direct_bridge_sources":[],"competing_candidates":[],"conflict_reason_codes":["serializer_candidate_removed"]},"input_fingerprint":"5715c3735ada9856433e30e6eac3aa16b36d78c2454307dca787fdbb40616b9d","contract_version":"promotion_contract_v2"},"publish_contract_input_fingerprint":"5715c3735ada9856433e30e6eac3aa16b36d78c2454307dca787fdbb40616b9d"}},"10_old":{"scope":"OLD_EXPERTS_ON_CURRENT_SOURCE_COMPARISON","post":{"gallery_id":"genrenovel","post_id":11718086,"title":"난 찐친 5명이나 있네 ㅋㅋ 친구없는 찐따로 안 살아서 다행","author":"ㅇㅇ","created_at":"2026-01-28 18:40:26","url":"https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11718086","content_blocks":[{"type":"text","text":"118.235"},{"type":"text","text":"39.7"},{"type":"text","text":"ㅇㅇ"},{"type":"text","text":"노벨쨩"},{"type":"text","text":"피아쨩"},{"type":"text","text":"너희 내 친구쟈나"}],"page_no":30,"comments":["내친구 ㅇㅇ - dc App","","통피는 단수가 아니다",""]},"experts":{"gatekeeper":{"is_noise":true,"noise_reason":"본문 내용이 특정 웹소설 작품에 대한 논의가 아니라, 플랫폼(노벨피아, 피아 등)을 의인화하여 \'친구\'라고 부르는 커뮤니티식 드립/잡담임. 제목 또한 일상적인 자학적 유머이며, 본문의 \'노벨쨩\', \'피아쨩\'은 웹소설 플랫폼인 노벨피아(Novelpia)와 피아(Pia)를 지칭하는 것으로 판단됨. 이는 작품 토론이 아닌 플랫폼 관련 밈/잡담 영역에 해당함.","post_type":"community_banter","detected_entities":{"possible_titles":["5명이나","명이나","5명이","찐따로","다행","찐따","친구"],"possible_authors":[],"possible_characters":[],"platforms_mentioned":["노벨피아","피아"]},"key_terms":["노벨쨩","피아쨩","찐친"],"context_clues":{"has_url_in_comments":false,"has_specific_names":false,"is_asking_recommendation":false,"is_spoiler_discussion":false,"has_comment_title_answer":true,"comment_title_candidates":["통피는 단수가 아니다"],"comment_title_merge_candidates":[],"comment_title_candidate_details":[{"text":"통피는 단수가 아니다","comment_index":1,"line_index":0,"speech_act":"explanation","has_at_mention":false,"reply_level":0,"reply_to_comment_id":null,"author":"ㅇㅇ","title_assertion_basis":null}]},"search_requests":[],"confidence":"high","notes":"본문은 118.235, 39.7, ㅇㅇ, 노벨쨩, 피아쨩을 각각 친구로 부르는 커뮤니티 농담이며, 특정 작품을 논하는 글은 아닙니다."},"discourse":{"discourse_analysis":{"primary_domain":"memes_humor","domain_confidence":"high","domain_evidence":["찐친","찐따","노벨쨩","피아쨩","너희 내 친구쟈나"],"secondary_domains":["novel_literature"],"intent":"make_joke","intent_confidence":"medium","speech_act":"banter","target_kind":"community","is_coherent":true,"coherence_reason":"제목에서 \'친구 5명\'을 언급하고, 본문에서 IP 주소(118.235.39.7)와 특정 명칭(노벨쨩, 피아쨩 등)을 나열하며 혼자 떠드는 유머를 구사함. 댓글 또한 작성자의 IP(통피)를 지적하며 커뮤니티 내부의 농담으로 이어짐.","title_novel_terms":[],"title_body_consistency":false,"consistency_note":"제목은 친구 관계에 대한 자학적 유머이나, 본문은 IP 주소와 특정 캐릭터/명칭을 나열하는 형태임.","is_association_not_discussion":true,"association_evidence":"본문의 \'노벨쨩\', \'피아쨩\' 등의 표현이 특정 작품의 캐릭터가 아닌, IP 주소 조각이나 커뮤니티 내부의 밈(Meme) 혹은 단순 장난으로 보임.","search_suggestions":[],"real_subject":"작성자가 자신의 IP 주소를 친구라고 부르며 혼자 즐거워하는 커뮤니티식 유머(뻘글)","author_question_span":null,"author_question_target":null,"author_recommendation_span":null,"author_recommendation_is_direct":false,"reasoning":"작성자는 제목에서 친구가 많다고 허세를 부린 뒤, 본문에서 IP 주소의 일부와 \'노벨쨩\', \'피아쨩\' 같은 정체불명의 명칭을 나열하며 스스로 친구라고 주장하고 있다. 이는 전형적인 커뮤니티의 \'혼잣말/뻘글\' 형태이며, 댓글 역시 작성자의 IP(통신사 IP)를 언급하며 놀리는 맥락이다.","source_bound_recommendation_request":false,"image_topic_relation":{"state":"no_image","source":"author_spans"},"semantic_seed_review":{"post_intent":"작성자가 자신의 IP 주소 일부를 인명처럼 부르며 친구라고 지칭하는 커뮤니티식 유머","content_interpretation":"표현 오타/축약 패턴(범용)에 따라 특정 고유명사로 단정할 수 없는 인명/캐릭터명 형태의 표면어임","is_specific_work_discussion":false,"recommended_intent":"make_joke","recommended_target_kind":"community","warnings":["작품 관련 앵커가 전혀 없는 단순 유머 게시글임"]},"warnings":["semantic_seed_review_search_suggestions_removed","semantic_seed_review_specific_work_denied"]}}},"source_packet":{"path":"C:\\\\Users\\\\kimjang\\\\Documents\\\\GitHub\\\\llm_novel_dc_coommunity_parser\\\\out\\\\development_plan_20261010\\\\p4_reapproval_v1\\\\final80_parallel12_v1\\\\progress_review_v1\\\\review_packets.jsonl","sha256":"aad28693a619e4e314ba21f76a0244df1a200574a450f119b89e94f228f0089d","jsonl_line1":10},"expert_log":{"path":"C:\\\\Users\\\\kimjang\\\\Documents\\\\GitHub\\\\llm_novel_dc_coommunity_parser\\\\logs\\\\expert_run_20261010_210300_688879.log","raw_byte_offset":1280214,"raw_byte_length":54503,"raw_block_sha256":"9acc2d1da1f51f6783af18a0eab1b2a4e54fa1f606452a6b223c9a22ead4e3ad"},"source_canonical_sha256":"60e264737a533d838a2620b00e4c8bd8b1ad6589e8a90a4376211c3e5ace7f43","source_comments_canonical_sha256":"70b3cb8f2136102f5fd7d707258932b548440c69a3c7a1dbb29734fba5dcc67f","pre_fix":{"discussion_type":"community_banter","subtype":"pure_meme","promotion_decision":{"status":"reject","publish_allowed":false,"official_title":null,"official_url":null,"candidate_preserved":false,"reason_codes":["no_candidate_title","row_discussion_missing","title_resolution_state_not_publishable","context_only","work_resolution_not_publishable","community_banter","scope_unknown","scope_not_current_work","serializer_candidate_removed"],"bypassed_gate":false,"scope":{"scope_kind":"unknown","confidence":"low","direct_bridge_sources":[],"competing_candidates":[],"conflict_reason_codes":["serializer_candidate_removed"]},"input_fingerprint":"23d5ac8f787d7c1fa4ddf6f354baf2814ccc94df7f99fda4be5f742e531297a0","contract_version":"promotion_contract_v2"},"publish_contract_input_fingerprint":"23d5ac8f787d7c1fa4ddf6f354baf2814ccc94df7f99fda4be5f742e531297a0"}}}')


class NoExternal:
    def __getattr__(self, name):
        def forbidden(*args, **kwargs):
            raise AssertionError('NEW_MODEL_SEARCH_FETCH_FORBIDDEN:' + name)
        return forbidden


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def serialize(tmp_path, row):
    raw = copy.deepcopy(row['post'])
    post = PostInput(**raw)
    pipeline = AgenticPipeline(llm=NoExternal(), mcp=NoExternal(),
        output_dir=tmp_path, max_iterations=1, native_recovery=True)
    ctx = ConversationContext(post_id=post.post_id,
        post_data=pipeline._post_to_dict(post), comments=post.comments)
    ctx._final_source_original_inputs = pipeline._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    if 'image_enrichment' in row:
        # 합성 이미지 관측만 공급한다. 이미지 읽기나 실제 OCR 정확도 검증은 아니다.
        ctx.post_data['image_enrichment'] = copy.deepcopy(row['image_enrichment'])
    for name, value in row['experts'].items():
        ctx.set_expert_output(ExpertType(name), copy.deepcopy(value))
    discourse = row['experts']['discourse']['discourse_analysis']
    ctx.primary_domain = discourse.get('primary_domain')
    ctx.discourse_intent = discourse.get('intent')
    original = canonical(ctx.post_data)
    output = pipeline._context_to_output(ctx)
    payload = output.model_dump(mode='json')
    checked = pipeline.verify_final_source_context_serialization(
        output, payload, stage='community_state_regression_saved_experts')
    assert isinstance(checked, dict)
    assert canonical(ctx.post_data) == original and raw == row['post']
    commit = compute_publication_decision_commit(payload,
        publication_scope_id=hashlib.sha256(b'community-state-regression').hexdigest(),
        attempt_run_id='saved-experts', input_index=1, post_id=post.post_id)
    return pipeline, ctx, output, payload, commit


@pytest.mark.parametrize('case,subtype', [('10','pure_meme'), ('61','realworld_social_talk')])
def test_actual_saved_experts_source_explanation_owns_final_community_state(tmp_path, case, subtype):
    row = RECORDED[case]
    pipeline, ctx, output, payload, commit = serialize(tmp_path, row)
    identity = payload['identity']
    assert identity['discussion_type'] == 'community_banter'
    assert identity['subtype'] == subtype
    assert '- 글 분류: community_banter' in identity['reason']
    assert identity['novel_identity'] is None and not identity['title_resolution_allowed']
    assert identity['work_resolution'] == 'none' and identity['title_resolution_state'] == 'context_only'
    assert commit.outcome == 'HOLD' and commit.publish_allowed is False
    # 분류만 연결한다. 기존 공식 쌍·공개 gate의 권한을 다시 만드는 수정은 허용하지 않는다.
    assert identity['promotion_decision'] == row['pre_fix']['promotion_decision']
    assert identity['publish_contract_input_fingerprint'] == row['pre_fix']['publish_contract_input_fingerprint']
    observed = ctx._final_source_discussion_observations['classification']
    assert observed['basis'] == 'verified_current_author_community_state'
    binding = observed['label_evidence_binding']
    assert binding['mode'] == 'verified_current_author_community_state'
    assert binding['counts_as_core'] is False and binding['publication_authority'] is False
    assert binding['native_label_location_claimed'] is False
    assert ctx._final_source_projection_consumption['source_explanation_used']
    for proof in binding['proofs']:
        assert proof.claim_kind == 'own' and proof.claimant == 'self'
        assert proof.comment_object is None and proof.ledger_object is ctx._final_source_projection_native.author_ledger
        assert proof.origin_object.raw_text[slice(*proof.raw_span)] == proof.sourcequote
        assert proof.source_sha256 == hashlib.sha256(proof.sourcequote.encode()).hexdigest()
    # 실제 최종 serialization seal이 새 분류를 소유하며 사후 변경은 거절해야 한다.
    changed = copy.deepcopy(payload)
    changed['identity']['discussion_type'] = 'noise'
    with pytest.raises(ValueError, match='serialized fields changed'):
        pipeline.verify_final_source_context_serialization(output, changed, stage='tampered_community_state')
    assert isinstance(pipeline.verify_final_source_context_serialization(
        output, payload, stage='unchanged_after_rejected_community_tamper'), dict)


def test_previous_recorded_joke_experts_keep_existing_classification_and_guard(tmp_path):
    _, ctx, _, payload, commit = serialize(tmp_path, RECORDED['10_old'])
    identity = payload['identity']
    assert (identity['discussion_type'], identity['subtype']) == ('community_banter','pure_meme')
    assert identity['promotion_decision'] == RECORDED['10_old']['pre_fix']['promotion_decision']
    assert ctx._final_source_discussion_observations['classification']['basis'] != 'verified_current_author_community_state'
    assert commit.publish_allowed is False


NEGATIVES = [
    ('short_work_review', '전지적 독자 시점 감상', ['이번 화 전개 좋았음'], []),
    ('aseng_alias_competing', '아생갤 이번 화 감상',
        ['아카데미 생존 갤러리를 아생갤이라 부른다.', '전개 좋았음'], []),
    ('quoted_community', '아생갤 이번 화 감상',
        ['민수: 장갤은 분탕이 많다.', '작성자: 아카데미 생존 갤러리의 전개가 좋았다.'], []),
    ('comment_community', '아생갤 이번 화 감상',
        ['아카데미 생존 갤러리의 전개가 좋았다.'], [{'author':'타인','content':'장갤은 분탕이 많다.'}]),
]


def synthetic_work(name, title, body, comments):
    aseng = '아생갤' in title
    return {'post': {'post_id':90001 + [r[0] for r in NEGATIVES].index(name),
        'title':title, 'author':'작성자', 'content_blocks':[{'type':'text','text':line} for line in body],
        'comments':copy.deepcopy(comments)},
        'experts': {'gatekeeper': {'is_noise':False, 'post_type':'short_reaction',
            'detected_entities':{'possible_titles':['아카데미 생존 갤러리' if aseng else '전지적 독자 시점']},
            'context_clues':{'short_post_fast_path':True}},
            'discourse': {'discourse_analysis': {'primary_domain':'novel_literature',
                'domain_confidence':'high', 'intent':'express_opinion', 'target_kind':'work',
                'semantic_seed_review':{'is_specific_work_discussion':True}}}}}


@pytest.mark.parametrize('name,title,body,comments', NEGATIVES, ids=[r[0] for r in NEGATIVES])
def test_seven_case_boundary_preserves_work_alias_and_author_scope(tmp_path, name, title, body, comments):
    _, ctx, _, payload, commit = serialize(tmp_path, synthetic_work(name, title, body, comments))
    identity = payload['identity']
    assert identity['discussion_type'] not in {'community_banter','noise'}
    assert ctx._final_source_discussion_observations['classification']['basis'] != 'verified_current_author_community_state'
    assert identity['promotion_decision']['bypassed_gate'] is False
    if name == 'short_work_review':
        assert identity['work_resolution'] == 'unresolved'
        assert identity['title_resolution_state'] == 'unresolved_matchable'
        assert identity['discussion_type'] == 'general'
        assert identity['novel_identity'] is None and commit.publish_allowed is False
    else:
        # 현재 내장 별칭+실제 guard의 기존 title-only 허용을 제거하지 않는다.
        assert identity['novel_identity']['official_title'] == '아카데미 생존 갤러리'
        assert identity['novel_identity']['heretic_url'] is None and commit.publish_allowed is True
        assert 'batch_alias_public_title_bridge' in identity['promotion_decision']['reason_codes']
        assert '아카데미 생존 갤러리' in identity['primary_subject_text']


@pytest.fixture
def bound_case(tmp_path):
    pipeline, ctx, output, _, _ = serialize(tmp_path, RECORDED['61'])
    return pipeline, ctx, output


@pytest.mark.parametrize('change', ['no_explanation','not_eligible','not_source_eligible',
    'proof_hash','proof_span','foreign_ledger','comment_proof','named_work','title_term'])
def test_community_route_requires_same_call_owned_source_proof(bound_case, change):
    pipeline, ctx, output = bound_case
    observations = ctx._final_source_discussion_observations
    native = ctx._final_source_projection_native
    identity = output.identity.model_copy(deep=True)
    for name, value in observations['classification']['before']:
        setattr(identity, name, value)
    explanation = ctx._final_source_context_explanation
    eligible = source_eligible = True
    if change == 'no_explanation':
        explanation = None
    elif change == 'not_eligible':
        eligible = False
    elif change == 'not_source_eligible':
        source_eligible = False
    elif change in {'named_work','title_term'}:
        key = 'named_work_surfaces' if change == 'named_work' else 'title_term_surfaces'
        native = replace(native, signals=replace(native.signals, **{key:('아카데미 생존 갤러리',)}))
    else:
        proof = explanation.proofs[0]
        changed = {'proof_hash':{'source_sha256':'0'*64},
            'proof_span':{'raw_span':(1,len(proof.sourcequote))},
            'foreign_ledger':{'ledger_object':copy.deepcopy(native.author_ledger)},
            'comment_proof':{'comment_object':{'content':proof.sourcequote}}}[change]
        explanation = replace(explanation, proofs=(replace(proof, **changed), *explanation.proofs[1:]))
    classification = pipeline._final_source_discussion_classification(identity, native,
        observations['records'], eligible=eligible, source_eligible=source_eligible,
        verified_source_explanation=explanation)
    assert classification['basis'] != 'verified_current_author_community_state'
    assert identity.discussion_type == 'undecodable_reference' and identity.novel_identity is None


@pytest.mark.parametrize('title,body,comments', [
    ('타인 발화', ['민수: 장갤<< 의외로 분탕은 많은데', '병신이 더많음'], []),
    ('타인 발화', ['“장갤<< 의외로 분탕은 많은데', '병신이 더많음”'], []),
    ('작성자 일상', ['오늘은 그냥 쉬었음'],
        [{'author':'타인','content':'장갤<< 의외로 분탕은 많은데 병신이 더많음'}]),
    ('이 음식은 의외로 단맛이 많은데', ['짠맛이 더많음'], []),
], ids=['speaker_label_carry','carried_quote','comment_only','noncommunity_comparison'])
def test_community_expert_signal_cannot_replace_owned_source(tmp_path, title, body, comments):
    row = copy.deepcopy(RECORDED['61'])
    row['post'].update(title=title, content_blocks=[{'type':'text','text':line} for line in body], comments=comments)
    _, ctx, _, payload, commit = serialize(tmp_path, row)
    assert ctx._final_source_discussion_observations['classification']['basis'] != 'verified_current_author_community_state'
    assert payload['identity']['novel_identity'] is None and commit.publish_allowed is False


@pytest.mark.parametrize('kind', ['image_not_observed', 'untitled_scene', 'unverified_work_ocr'])
def test_image_competition_keeps_existing_guard_and_does_not_use_text_only_community_fallback(tmp_path, kind):
    row = copy.deepcopy(RECORDED['61'])
    image_url = 'https://fixture.invalid/community-competition.png'
    image_index = len(row['post']['content_blocks'])
    row['post']['content_blocks'].append({'type':'image', 'url':image_url})
    if kind != 'image_not_observed':
        item = {'block_index':image_index, 'source_url':image_url,
            'evidence_type':'character_visual_only', 'title_role':'unknown',
            'promotion_eligible':False, 'visual_summary':'작품명이 확인되지 않은 인물 장면'}
        if kind == 'unverified_work_ocr':
            item.update(evidence_type='explicit_text', ocr_text='가상의 장면 기록집',
                explicit_work_title='가상의 장면 기록집', work_cues=['가상의 장면 기록집'])
        row['image_enrichment'] = [item]
    pipeline, ctx, output, payload, commit = serialize(tmp_path, row)
    identity = payload['identity']
    observation = ctx._final_source_discussion_observations['classification']
    assert any(line.reason == 'dropped_non_text_block'
        and line.raw_path == f'/content_blocks/{image_index}/text'
        for line in ctx._final_source_projection_native.manifest.dropped)
    assert ctx._final_source_context_explanation.supported
    assert observation['basis'] != 'verified_current_author_community_state'
    assert dict(observation['before']) == dict(observation['after'])
    assert identity['novel_identity'] is None and identity['title_resolution_allowed'] is False
    assert commit.outcome == 'HOLD' and commit.publish_allowed is False
    assert identity['promotion_decision']['bypassed_gate'] is False
    if kind == 'image_not_observed':
        assert not identity['image_evidence_catalog']
    else:
        catalog = identity['image_evidence_catalog']
        assert len(catalog) == 1 and catalog[0]['source_url'] == image_url
        assert catalog[0]['block_index'] == image_index
        assert catalog[0]['promotion_eligible'] is False and catalog[0]['title_role'] == 'unknown'
        assert ctx.post_data['image_enrichment'] == row['image_enrichment']
        if kind == 'unverified_work_ocr':
            assert catalog[0]['explicit_work_title'] == '가상의 장면 기록집'
            assert catalog[0]['ocr_text'] == '가상의 장면 기록집'
            assert '가상의 장면 기록집' in identity['reason']
    assert isinstance(pipeline.verify_final_source_context_serialization(
        output, payload, stage='image_community_boundary_preserved'), dict)
