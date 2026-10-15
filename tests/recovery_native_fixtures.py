"""실제 native 최종화 시험에 쓸 합성 원문과 외부 HTTP 응답.

수동 HOLD는 이전 publication의 적격 복구 계약에만 사용한다. 후속 판정은
실제 전문가·pipeline·guard가 생성해야 하며 이 helper는 출력 모델을 만들지 않는다.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import httpx

from src.llm_batch.ledger.publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA, build_publication_scope_descriptor,
    compute_publication_decision_commit,
)
from src.llm_batch.ledger.recovery_activation import _create_event, extract_direct_ocr_review_proposals
from src.llm_batch.measurement.recovery_provider_contract import (
    SOURCE_SCHEMA, bind_recovery_provider_plan, build_recovery_provider_plan,
)
from src.llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt
from src.llm_batch.measurement.semantic_review_router import build_semantic_review_router_receipt
from tests.recovery_execution_fixtures import HMAC_KEY, _hold_result, json_bytes


TITLE = "합성 달별갤 작품"
DETAIL_URL = "https://novelpia.com/novel/987654321"
ENDPOINTS = {
    "MCP_SEARCH": "http://127.0.0.1:9/mcp/search",
    "MCP_FETCH": "http://127.0.0.1:9/mcp/fetch",
    "OPENAI_CHAT": "http://127.0.0.1:9/v1/chat/completions",
}


def native_case(case: str = "positive") -> dict:
    """원문과 선언형 HTTP 자료만 반환한다. 정답·실측 자료가 아니다."""
    if case not in {"positive", "hold", "previous", "comparison"}:
        raise ValueError("unknown native synthetic case")
    positive = case == "positive"
    titles = {
        "positive": TITLE + " 소설 후기",
        "hold": "제목을 모르는 소설을 찾는다",
        "previous": "합성 작가의 신작을 기다린다",
        "comparison": "새로 읽을 소설을 추천해 줘",
    }
    bodies = {
        "positive": ["합성작가의 웹소설 " + TITLE + "을 읽었다.",
                     TITLE + "의 주인공이 적을 물리치는 전개가 좋았다.", "작품 링크: " + DETAIL_URL],
        "hold": ["주인공이 적을 물리치는 소설을 찾는다. 작품 제목은 기억나지 않는다."],
        "previous": [TITLE + "은 합성작가의 전작이다.", "이번 신작의 제목은 아직 모른다. 신작을 기다린다."],
        "comparison": [TITLE + "처럼 주인공이 강한 다른 소설을 추천해 줘.", "비교 기준일 뿐 지금 읽는 작품은 아니다."],
    }
    role = {"positive": "primary", "hold": "mentioned", "previous": "previous", "comparison": "comparison"}[case]
    post = {
        "gallery_id": "synthetic_r6", "post_id": 101, "title": titles[case],
        "author": "합성작성자", "created_at": "2026-10-10T09:00:00+09:00",
        "url": "https://example.invalid/synthetic/posts/101",
        "content": deepcopy(bodies[case]),
        "comments": [{"comment_id": "native-comment-1", "post_id": 101,
                      "author": "합성독자", "content": "작성자 글을 읽었다.",
                      "reply_level": 0, "reply_to_comment_id": None}],
    }
    reason = ("작성자 제목과 본문이 같은 소설의 독서 감상을 직접 설명한다." if positive
              else "검색된 작품은 현재 글의 특정 작품으로 확인되지 않아 공식 제목을 보류한다.")
    relation = {"relation_type": "exact_title" if positive else "thematic_overlap_only",
                "discussion_target": "specific_work" if positive else "mixed_or_uncertain",
                "promotion_decision": "allow" if positive else "hold",
                "confidence": "high", "reason": reason}
    identity = {"official_novel_title": TITLE if positive else None,
                "official_title": TITLE if positive else None,
                "heretic_url": DETAIL_URL if positive else None,
                "confidence": "High" if positive else "Low", "evidence_type": "search_platform_url"}
    gatekeeper = {"is_novel_related": True, "post_type": "work_discussion" if positive else "question",
                  "detected_entities": {"possible_titles": [TITLE] if case != "hold" else [],
                                        "possible_characters": [], "possible_authors": []},
                  "key_terms": [TITLE] if case != "hold" else [], "context_clues": {}}
    discourse = {"discourse_analysis": {
        "primary_domain": "novel_literature", "domain_confidence": "high",
        "intent": "discuss_work" if positive else "ask_question", "target_kind": "work",
        "title_novel_terms": [TITLE] if positive else [], "is_coherent": True,
        "title_body_consistency": True, "is_association_not_discussion": False,
        "semantic_seed_review": {"is_specific_work_discussion": positive,
                                 "content_interpretation": reason, "post_intent": reason},
    }}
    decoded = {"original": TITLE, "source_role": "work_title",
               "best_match": {"title": TITLE, "url": DETAIL_URL, "confidence": "High"},
               "candidates": [{"official_novel_title": TITLE, "title": TITLE,
                               "url": DETAIL_URL, "platform": "novelpia", "confidence": "High"}],
               "grounding": {"anchor_type": "title_mention", "anchor_text": TITLE},
               "reference_role": role, "supporting_evidence": [{"url": DETAIL_URL, "title": TITLE}]}
    verification = {"verification_result": {
        "is_relevant": True, "is_novel_discussion": True, "novel_identity": identity,
        "grounding_check": {"anchor_found": "title_mention" if positive else "none",
                            "anchor_text": TITLE if positive else None,
                            "matched_alias": TITLE if positive else None},
        "relation_judgment": relation, "reason": reason,
        "inference": {"type": "work_discussion"}, "counter_arguments": [],
        "evidence_chain": [{"source": DETAIL_URL, "content": TITLE + " 소설 상세"}],
    }, "final_confidence": "high" if positive else "low"}
    synthesis = {
        "reinterpretation": {"post_intent": reason, "actual_meaning": reason,
                             "is_about_identified_work": positive},
        "confidence_assessment": {"is_about_identified_work": positive,
                                  "confidence": "high" if positive else "low",
                                  "requires_further_investigation": False},
        "synthesis_summary": reason, "key_evidence": [TITLE] if positive else [],
        "consistency_check": {"is_consistent": True, "contradictions": []},
        "evidence_alignment": {"decoder_match": "strong" if positive else "weak",
            "verifier_match": "strong" if positive else "weak", "overall_coherence": "high",
            "decoder_reason": reason, "verifier_reason": reason},
        "hidden_references": [],
    }
    decision = {"is_relevant": True, "official_title": TITLE if positive else None,
                "official_novel_title": TITLE if positive else None,
                "heretic_url": DETAIL_URL if positive else None,
                "confidence": "High" if positive else "Low", "discussion_type": "review" if positive else "work_discussion",
                "reason": reason, "final_reasoning": reason}
    if not positive:
        decision.update({"_title_deliberately_null": True,
                         "_title_null_block_reasons": ["temporal_reference_guard" if case == "previous" else "no_direct_anchor"]})
    expert_responses = {
        "gatekeeper": gatekeeper, "discourse": discourse,
        # 실제 snippet_analyzer prompt의 JSON 필드만 반환한다.
        # 원문/검색 snippet과 최종 guard 결과는 변경하지 않는다.
        "snippet_analyzer": {
            "post_intent": "work_discussion",
            "post_intent_reason": ("원문 제목·본문과 [E001]의 작품 제목이 같다." if positive
                                   else "[E001]의 작품을 현재 글의 대상으로 확정하지 않는다."),
            "identified_title": TITLE if positive else None,
            "identified_author": "합성작가" if positive else None,
            "identified_category": "web_novel",
            "relevant_authors": ["합성작가"] if positive else [],
            "irrelevant_authors": [], "abbreviation_mappings": [],
            "relevant_characters": [], "entity_role_hints": [],
        },
        "decoder": {"decoded_terms": [decoded], "overall_confidence": "high"},
        "verifier": verification, "verifier_relation_judge": relation,
        "synthesizer": synthesis, "arbiter": {"final_decision": decision, "metadata_synthesis": {}},
        "final_semantic_reread": {"decision": "ACCEPT" if positive else "HOLD",
            "is_specific_work_discussion": positive, "evidence_strength": "Strong" if positive else "Missing",
            "recommended_discussion_type": "review" if positive else "general", "reason": reason},
        "page_alive_check": {"content_status": "active", "novel_title": TITLE,
            "page_type": "novel_page", "reason": "합성 응답의 제목과 소설 소개가 표시된다."},
        "reason_review": {"selected_ids": [], "primary_reason": reason,
            "merged_reason": reason, "llm_review_note": "합성 HTTP 응답", "review_confidence": "high"},
    }
    content = TITLE + "\n작가: 합성작가\n웹소설 작품 상세\n주인공이 적을 물리치는 이야기.\n1화 읽기"
    hit = {"title": TITLE, "url": DETAIL_URL, "content": content, "snippet": content}
    return {"data_kind": "TEST_SYNTHETIC", "case": case, "post": post,
            "candidate_title": TITLE, "candidate_url": DETAIL_URL, "relation_role": role,
            "search_response": {"results": [hit], "raw_total": 1, "degraded": False},
            "detail_response": {"url": DETAIL_URL, "final_url": DETAIL_URL,
                "title": TITLE, "page_title": TITLE,
                "content": content, "text": content, "description": "합성 웹소설 상세",
                "author": "합성작가", "site_name": "노벨피아", "status_code": 200,
                "structured_info": {"title": TITLE, "page_title": TITLE, "author": "합성작가",
                    "page_type": "novel_page", "content_status": "active", "description": content,
                    "fetch_method": "httpx"},
                "fetch_transport_provenance": {"requested_url": DETAIL_URL, "final_url": DETAIL_URL,
                    "method": "httpx", "status_code": 200, "redirected": False},
                "official_detail_transport_provenance": {"requested_url": DETAIL_URL,
                    "final_url": DETAIL_URL, "method": "httpx", "status_code": 200}},
            "expert_responses": expert_responses, "expected_outcome": "PUBLISH" if positive else "HOLD"}


def build_native_base_fixture(root: Path, *, case="positive") -> dict:
    """동일 합성 원문으로 새 base/HMAC/provider 계약을 처음부터 생성한다."""
    root = Path(root).resolve()
    source_dir = root / "source"
    source_dir.mkdir(parents=True, exist_ok=False)
    data = native_case(case)
    post = deepcopy(data["post"])
    result = _hold_result(post["post_id"], data["relation_role"])
    result.update({"gallery_id": post["gallery_id"], "title": post["title"], "post_author": post["author"],
                   "created_at": post["created_at"], "url": post["url"],
                   "content": deepcopy(post["content"]),
                   "content_blocks": [{"type": "text", "text": text} for text in post["content"]],
                   "image_count": 0,
                   "comments": [item["content"] for item in post["comments"]],
                   "comment_metadata": deepcopy(post["comments"])})
    assert post["content"] == [block["text"] for block in result["content_blocks"]]
    for field in ("gallery_id", "post_id", "title", "content"):
        assert result[field] == post[field] and type(result[field]) is type(post[field])
    # 외부 run_id를 원래 owner attempt와 같게 꾸미지 않는다.
    inputs, results = [post], [result]
    raw_input = json_bytes(post) + b"\n"
    input_sha = hashlib.sha256(raw_input).hexdigest()
    scope = build_publication_scope_descriptor(input_file_sha256=input_sha, post_ids=[101],
        config_hash="r6-native-synthetic-base", release_fingerprint="TEST_SYNTHETIC")
    receipt = compute_publication_decision_commit(result, publication_scope_id=scope.publication_scope_id,
        attempt_run_id="native-base-owner", input_index=1, post_id=101)
    router = build_semantic_review_router_receipt(result, receipt, attempt_run_id=receipt.attempt_run_id)
    recovery = build_semantic_recovery_plan_receipt(result, receipt, attempt_run_id=receipt.attempt_run_id)
    proposals = extract_direct_ocr_review_proposals(result)
    assert len(proposals) == 1
    proposal = proposals[0]
    event = _create_event(receipt=receipt, proposal=proposal, raw_capability="native-fixture-audit-only",
        hmac_key=HMAC_KEY, sequence=1, prev_event_sha256="GENESIS")
    item = result["analysis_result"]["identity"]["image_evidence_catalog"][0]
    query = proposal.raw_candidate_title
    capture = {"schema_version": SOURCE_SCHEMA, "data_kind": "TEST_SYNTHETIC",
        "input_raw_sha256": input_sha, "input_index": 1, "post_id": 101,
        "source_locator": proposal.source_locator, "item": deepcopy(item)}
    source_binding = {"source_locator": proposal.source_locator,
        "source_item_sha256": hashlib.sha256(json_bytes(item)).hexdigest(), "field_pointer": "/ocr_text",
        "span_start": 0, "span_end": len(query.encode()), "span_unit": "UTF8_FIELD_VALUE",
        "query": query, "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
        "relation_role": proposal.relation_role}
    manifest = {"run_id": "native-base-export", "output_file": str(source_dir / "result.json"),
        "publication_scope_id": scope.publication_scope_id,
        "publication_input_snapshot_sha256": input_sha,
        "publication_scope_descriptor_sha256": scope.descriptor_sha256,
        "terminal_artifacts_finalized": True, "completed_count": 1, "flushed_count": 1,
        "pending_count": 0, "partial_flush_gap": False, "data_kind": "TEST_SYNTHETIC"}
    raw = {"input": raw_input, "result": json_bytes(results), "manifest": json_bytes(manifest),
        "publication_wal": json_bytes({"schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
            "receipt": receipt.to_dict(), "result": result}) + b"\n",
        "activation_journal": json_bytes(event.to_dict()) + b"\n", "router": json_bytes(router),
        "recovery_plan": json_bytes(recovery), "source_capture": json_bytes(capture),
        "scope_descriptor": json_bytes(scope.to_dict())}
    refs = {}
    for role, payload in raw.items():
        path = source_dir / (role + (".jsonl" if role in {"input", "publication_wal", "activation_journal"} else ".json"))
        with path.open("xb") as stream:
            stream.write(payload)
        refs[role] = {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    kwargs = {"source_refs": refs, "source_bytes": raw, "input_format": "JSONL_POST_COMMENT_V1",
        "result_pointer": "/0", "router_pointer": "", "recovery_plan_pointer": "",
        "publication_decision_id": receipt.decision_id, "activation_event_sha256": event.event_sha256,
        "source_binding": source_binding, "endpoint": ENDPOINTS["MCP_SEARCH"],
        "payload": {"query": query, "num_results": 2, "purpose": recovery["plan"]["query_plan"]["purposes"][0]},
        "policy": {"max_calls": 1, "max_elapsed_ms": 1000, "request_timeout_ms": 100,
                   "max_response_bytes": 32768, "max_total_response_bytes": 32768},
        "output_dir": str(root / "provider_output"), "hmac_key": HMAC_KEY}
    plan = build_recovery_provider_plan(**kwargs)
    bound = bind_recovery_provider_plan(plan, hmac_key=HMAC_KEY)
    return {"native_case": data, "root": root, "plan": plan, "bound": bound, "build_kwargs": kwargs,
            "hmac_key": HMAC_KEY, "source_refs": refs, "source_bytes": raw, "result": result,
            "results": results, "receipt": receipt, "receipts": [receipt], "event": event,
            "manifest": manifest, "router": router, "recovery_plan": recovery,
            "source_binding": source_binding, "source_capture": capture, "scope": scope,
            "input_posts": inputs, "input_records": inputs}


def build_native_capture(pipeline, bundle):
    """실제 main loader 결과를 src 모델로 재생성해 pre-final carrier를 만든다."""
    from expert_main import load_jsonl_posts
    from src.llm_batch.domain.models import PostInput
    from src.llm_batch.experts.orchestrator import ConversationContext, ExpertType
    from src.llm_batch.runtime.recovery_native_context import capture_pre_final

    ref = bundle["source_refs"]["input"]
    loaded = load_jsonl_posts(Path(ref["path"]), snapshot_bytes=bundle["source_bytes"]["input"])
    assert len(loaded) == 1 and loaded[0].post_id == 101
    post = PostInput(**loaded[0].model_dump(mode="json"))
    object.__setattr__(post, "_input_truncated", getattr(loaded[0], "_input_truncated", None))
    object.__setattr__(post, "_parse_errors", tuple(getattr(loaded[0], "_parse_errors", ())))
    ctx = ConversationContext(post_id=post.post_id, post_data=pipeline._post_to_dict(post),
                              comments=pipeline._extract_comments(post))
    ctx._final_source_original_inputs = pipeline._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    ctx._input_truncated = post._input_truncated
    ctx._parse_errors = post._parse_errors
    responses = bundle["native_case"]["expert_responses"]
    ctx.set_expert_output(ExpertType.GATEKEEPER, deepcopy(responses["gatekeeper"]))
    ctx.set_expert_output(ExpertType.DISCOURSE, deepcopy(responses["discourse"]))
    # 이전 실패를 지우는 주체가 continuation인지 검사할 수 있도록 남긴다.
    ctx.set_expert_output(ExpertType.VERIFIER, {"verification_result": {
        "is_relevant": False, "reason": "STALE_PRE_RECOVERY_VERIFIER", "novel_identity": {}}})
    ctx.set_expert_output(ExpertType.ARBITER, {"final_decision": {
        "is_relevant": False, "_title_deliberately_null": True,
        "reason": "STALE_PRE_RECOVERY_ARBITER"}, "metadata_synthesis": {}})
    return {"post": post, "context": ctx, "capture": capture_pre_final(post, ctx)}


class _FixtureStream(httpx.SyncByteStream):
    def __init__(self, payload):
        self.raw = json_bytes(payload)

    def __iter__(self):
        yield self.raw


def _http_response(status, payload):
    # json= 생성자는 미리 읽힌 응답이다. 제품 iter_raw()가 관측할 스트림을 공급한다.
    return httpx.Response(status, stream=_FixtureStream(payload))


class NativeHTTPFixture:
    """물리 HTTP 경계에서만 선언형 응답을 반환하고 모든 요청을 기록한다."""
    def __init__(self, case_data):
        self.data = deepcopy(case_data)
        self.requests = []
        self.tags = []
        self.unexpected = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append({"url": str(request.url), "body": deepcopy(body)})
        if str(request.url) == ENDPOINTS["MCP_SEARCH"]:
            assert body.get("query"), "검색 query가 없는 HTTP 요청"
            payload = deepcopy(self.data["search_response"])
            if "source_receipt" in body:
                from src.llm_batch.ledger.recovery_provider_journal import canonical_sha256
                payload.update(direct_search_binding_verified=True,
                    direct_search_source_receipt_sha256=canonical_sha256(body["source_receipt"]))
            return _http_response(200, payload)
        if str(request.url) == ENDPOINTS["MCP_FETCH"]:
            if body.get("url") != DETAIL_URL:
                self.unexpected.append(deepcopy(body))
                return _http_response(422, {"error": "UNSCRIPTED_DETAIL_URL"})
            return _http_response(200, deepcopy(self.data["detail_response"]))
        if str(request.url) != ENDPOINTS["OPENAI_CHAT"]:
            self.unexpected.append(deepcopy(body))
            return _http_response(422, {"error": "UNSCRIPTED_HTTP_ENDPOINT"})
        assert body.get("stream") is False
        tag = self._tag(request, body)
        self.tags.append(tag)
        if tag not in self.data["expert_responses"]:
            self.unexpected.append({"tag": tag, "body": deepcopy(body)})
            return _http_response(422, {"error": "UNSCRIPTED_EXPERT_TAG"})
        text = json.dumps(self.data["expert_responses"][tag], ensure_ascii=False)
        return _http_response(200, {"id": "synthetic-native-response", "object": "chat.completion",
            "model": "synthetic-native-model", "choices": [{"index": 0,
                "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 13, "total_tokens": 24}})

    @staticmethod
    def _tag(request, body):
        metadata = body.get("metadata") or {}
        for value in (metadata.get("tag"), metadata.get("recovery_tag"), body.get("tag"),
                      request.headers.get("x-recovery-tag")):
            if isinstance(value, str) and value:
                return value
        systems = [message.get("content", "") for message in body.get("messages", [])
                   if type(message) is dict and message.get("role") == "system"]
        first = " ".join(str(systems[0]).strip().split()) if systems else ""
        prefixes = {
            "You are GATEKEEPER,": "gatekeeper", "You are DECODER,": "decoder",
            "You are VERIFIER,": "verifier", "You are FINAL ARBITER,": "arbiter",
            "You are 📖 DISCOURSE ANALYZER,": "discourse",
            "당신은 「증거 기반 재해석 전문가」입니다.": "synthesizer",
            "당신은 웹소설 커뮤니티의 축약어/장르어/플랫폼 메타를 구분하는 판정기입니다.": "verifier_relation_judge",
            "당신은 웹소설 커뮤니티 스캔 결과의 최종 자연어 정합성 검토자입니다.": "final_semantic_reread",
            "당신은 웹 페이지 상태 판별 전문가입니다.": "page_alive_check",
            "You are a REASON MERGE REVIEWER": "reason_review",
            "당신은 소설형 커뮤니티 검색 결과 분석 전문가입니다.": "snippet_analyzer",
        }
        for prefix, tag in prefixes.items():
            if first.startswith(prefix):
                return tag
        # 호출 순서나 후보 제목만으로 미상 전문가를 성공 처리하지 않는다.
        return "UNKNOWN"


def source_bytes(bundle):
    return {role: Path(ref["path"]).read_bytes() for role, ref in bundle["source_refs"].items()}


def store_native_provider_evidence(bundle, handler):
    """실제 예약/HTTP mock/원문 저장/독립 판독을 거쳐 provider carrier를 만든다."""
    from src.llm_batch.measurement.recovery_native_source import read_native_provider_evidence
    from src.llm_batch.runtime.recovery_provider_transport import RecoveryProviderRunner

    bound = bundle["bound"]
    runner = RecoveryProviderRunner(binding=bound.binding, policy=bound.policy,
        requests=bound.requests, journal_path=bound.journal_path, endpoints=bound.endpoints,
        source_check=bound.verify_protected_sources, cancelled=lambda: False,
        test_transport=httpx.MockTransport(handler), clock_ms=lambda: 1000)
    receipt = runner.request("MCP_SEARCH", bound.payload, request_id=bound.requests[0]["request_id"])
    assert receipt["status"] == "SUCCESS", receipt
    return {"provider_receipt": receipt, "evidence": read_native_provider_evidence(bound)}
