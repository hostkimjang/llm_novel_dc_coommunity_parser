"""추가 페이지를 새 source proof로 만들지 않고 고정된 delta로 검산하는 회귀."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import pytest
import test_source_bound_general_comparison_question as replay
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.experts.orchestrator import ExpertType

HERE=Path(__file__).resolve().parent

@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("NETWORK_FORBIDDEN_IN_GENERAL_CONTEXT_DELTA_REPLAY")
    monkeypatch.setattr(socket.socket, "connect", forbidden)

TITLE="충왕전/결과/ 장수풍뎅이, 사슴벌레 시리즈"
PAGES=[
 ("https://novelpia.com/novel/451543","(포켓몬스터) 세계챔피언하고 칼로스퀸의 아이로 살아간다는 것","unavailable"),
 ("https://novelpia.com/novel/381781","[슬라임 300년X벤 10] 옴니트릭스를 얻고 벤이 되었습니다.","deleted"),
 ("https://novelpia.com/novel/337354","이무기가 떨어진 곳은 이세계였습니다.","deleted"),
]

def context(tmp_path,*,mutate=None,empty_fetch=False):
    previous=replay.FIXTURE
    try:
        replay.FIXTURE=HERE/"fixtures/row55_closure2_general_context.json"
        pipe,ctx,row=replay.context(tmp_path,"closure2",9426461,mutate)
    finally:replay.FIXTURE=previous
    # Scalar fields are reconstructed from actual W0 and source extraction;
    # unlogged mutable runtime fields are not claimed to have been recovered.
    ctx.suspected_titles=[{"title":TITLE,"confidence":0.9,"source_term":ctx.post_data["title"],"source_expert":"arbiter"}]
    if empty_fetch:ctx.fetched_page_info=[]
    return pipe,ctx,row

def entry(index=0):
    url,title,status=PAGES[index]
    return {"url":url,"structured_info":{"title":title,"content_status":status,"content_status_source":"llm"},
            "_content_deleted":True,"_title_mismatch":True,"_fetched_title":title}

def attach(ctx, item):
    if not hasattr(ctx,"fetched_page_info") or ctx.fetched_page_info is None:ctx.fetched_page_info=[]
    ctx.fetched_page_info.append(item)

@pytest.mark.parametrize("empty_fetch",[False,True])
def test_fixed_raw_capture_accepts_only_first_negative_fetch_tail_then_seals(tmp_path,empty_fetch):
    pipe,ctx,row=context(tmp_path,empty_fetch=empty_fetch)
    proof=pipe._source_bound_general_context_state(ctx,"nonwork_comparison")
    assert proof is not None
    base=proof["inputs"]["facts"]; base_hash=proof["input_sha256"]
    for i in range(3):attach(ctx,entry(i))
    assert proof["verify"]() is True
    assert proof["inputs"]["facts"]==base and proof["input_sha256"]==base_hash
    assert proof["extension"]["appended_fetch_count"]==3
    assert proof["extension"]["status"]=="SEALED"
    assert proof["verify"]() is True
    ctx.fetched_page_info.append(entry())
    assert proof["verify"]() is False

@pytest.mark.parametrize("kind",["source","expert","search","suspect","owner","prefix_edit","prefix_delete","prefix_reorder","list_replaced","active","missing_deleted","missing_mismatch","exact_title","nested_alias","root_alias","post_bridge","character","different_edition","invalid_status","after_seal_change"])
def test_late_extension_fails_closed_on_real_work_or_original_changes(tmp_path,kind):
    pipe,ctx,row=context(tmp_path,empty_fetch=True)
    ctx.fetched_page_info.extend([entry(0),entry(1)])
    proof=pipe._source_bound_general_context_state(ctx,"nonwork_comparison")
    assert proof is not None
    extra=entry(2)
    if kind=="source":ctx.post_data["title"]+=" 변경"
    elif kind=="expert":ctx.get_expert_output(ExpertType.DISCOURSE)["discourse_analysis"]["intent"]="discuss_work"
    elif kind=="search":ctx.search_results.append({"title":"새 관측","url":"https://fixture.invalid/x"})
    elif kind=="suspect":ctx.suspected_titles[0]["title"]="사슴벌레"
    elif kind=="owner":ctx.search_results=deepcopy(ctx.search_results)
    elif kind=="prefix_edit":ctx.fetched_page_info[0]["_fetched_title"]="변경"
    elif kind=="prefix_delete":ctx.fetched_page_info.pop(0)
    elif kind=="prefix_reorder":ctx.fetched_page_info.reverse()
    elif kind=="list_replaced":ctx.fetched_page_info=deepcopy(ctx.fetched_page_info)
    elif kind=="active":extra["structured_info"]["content_status"]="active"
    elif kind=="missing_deleted":extra.pop("_content_deleted")
    elif kind=="missing_mismatch":extra.pop("_title_mismatch")
    elif kind=="exact_title":extra["structured_info"]["title"]=ctx.post_data["title"]
    elif kind=="nested_alias":extra["structured_info"]["explicit_alias_bridge"]=True
    elif kind=="root_alias":extra["explicit_alias_bridge"]=True
    elif kind=="post_bridge":extra["post_direct_grounding"]=True
    elif kind=="character":extra["verified_character_work_link"]=True
    elif kind=="different_edition":
        extra["structured_info"].update(title=ctx.post_data["title"],edition="다른 판본")
    elif kind=="invalid_status":extra["structured_info"]["content_status"]="unknown"
    elif kind=="after_seal_change":
        assert proof["verify"]() is True
    attach(ctx,extra)
    assert proof["verify"]() is False

@pytest.mark.parametrize("kind",["string_high","missing_source","different_score","not_final_low","positive_verifier","known_alias"])
def test_numeric_proposal_is_not_generic_high_confidence_permission(tmp_path,kind):
    pipe,ctx,row=context(tmp_path)
    if kind=="string_high":ctx.suspected_titles[0]["confidence"]="High"
    elif kind=="missing_source":ctx.suspected_titles[0].pop("source_term")
    elif kind=="different_score":ctx.suspected_titles[0]["confidence"]=0.8
    elif kind=="not_final_low":ctx.get_expert_output(ExpertType.ARBITER)["final_decision"]["suspected_titles"][0]["confidence"]="High"
    elif kind=="positive_verifier":ctx.get_expert_output(ExpertType.VERIFIER)["verification_result"]["is_novel_discussion"]=True
    elif kind=="known_alias":
        ctx.post_data["title"]="아생갤vs회귀수선전"
    assert pipe._source_bound_general_context_state(ctx,"nonwork_comparison") is None

def test_full_context_to_output_with_recorded_negative_fetch_shape_and_actual_proposal(tmp_path,monkeypatch):
    pipe,ctx,row=context(tmp_path)
    attempts=[]
    # This replaces only the transport boundary with logged negative shapes.
    # The real _context_to_output, native, contract and main/WAL code run.
    def recorded_fetch(runtime,url,*args,**kwargs):
        if url not in {p[0] for p in PAGES}:return None
        index=next(i for i,p in enumerate(PAGES) if p[0]==url)
        if url not in attempts:
            attempts.append(url);attach(runtime,entry(index))
        return next(item for item in runtime.fetched_page_info if item["url"]==url)
    monkeypatch.setattr(pipe,"_fetch_and_attach_page_info",recorded_fetch)
    source_before=replay.canonical({"post":ctx.post_data,"comments":ctx.comments,
        "experts":{k.value:ctx.get_expert_output(k) for k in ExpertType},"search":ctx.search_results,"suspected":ctx.suspected_titles})
    output=pipe._context_to_output(ctx);payload=output.model_dump(mode="json")
    pipe.verify_final_source_context_serialization(output,payload,stage="closure2_full_replay")
    identity=payload["identity"]
    assert identity["is_novel_related"] is False and identity["title_resolution_state"]=="context_only"
    assert identity["is_relevant"] is False and identity["work_resolution"]=="none"
    assert identity["promotion_decision"]["publish_allowed"] is False and identity["novel_identity"] is None
    assert len(attempts)==3
    assert replay.canonical({"post":ctx.post_data,"comments":ctx.comments,
        "experts":{k.value:ctx.get_expert_output(k) for k in ExpertType},"search":ctx.search_results,"suspected":ctx.suspected_titles})==source_before
    proof=ctx._general_context_state_evidence
    assert proof["extension"]["appended_fetch_count"]==3 and proof["verify"]() is True
    assert ctx._final_source_projection_call_count==1
    replay.synchronize_like_actual_main(payload,ctx.post_data)
    pipe.verify_final_source_context_serialization(output,payload,stage="closure2_main")
    # Reuse actual wrapper/WAL APIs while retaining this replay's exact result.
    from llm_batch.ledger.publication_commit import PublicationCommitRegistry,build_publication_scope_descriptor,commit_publication_result
    import hashlib
    scope=build_publication_scope_descriptor(input_file_sha256=hashlib.sha256(replay.canonical(row["post"])).hexdigest(),post_ids=[ctx.post_id],config_hash="closure2-local",release_fingerprint="candidate-replay")
    registry=PublicationCommitRegistry(tmp_path/"wal.jsonl",scope_descriptor=scope,create_new=True)
    wrapped=replay.wrapper_class()(dict(row["post"],comments=row["comments"],analysis_result=payload,run_meta={"local_replay":True}),output=output,verifier=pipe.verify_final_source_context_serialization)
    commit,created=commit_publication_result(wrapped,registry=registry,attempt_run_id="closure2-local",input_index=1,post_id=ctx.post_id)
    assert created and commit.outcome=="HOLD"
    wrapped.verify_stored_payload(registry.result(ctx.post_id),stage="closure2_wal")
    from llm_batch.grounding.source_context_diagnostics import export_source_context_diagnostics
    diagnostics=export_source_context_diagnostics(output,enabled=True)
    by_gate={r["gate"]:r for r in diagnostics["scope_state_guards"]}
    assert by_gate["general_context_capture"]["status"]=="ELIGIBLE"
    assert by_gate["general_context_adoption"]["applied"] is True
    summary={"scope":"LOG_SCALAR_CONTEXT_AND_NEGATIVE_TRANSPORT_SHAPES_NOT_ORIGINAL_FULL_MEMORY",
        "fetch_attempts":attempts,"extension":proof["extension"],"state":{k:identity[k] for k in ["is_relevant","is_novel_related","title_resolution_state","work_resolution"]},
        "native_calls":ctx._final_source_projection_call_count,"commit":commit.to_dict(),"diagnostics":diagnostics["scope_state_guards"]}
    (tmp_path/"fullpath_receipt.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    ctx.fetched_page_info[0]["_fetched_title"]="변조"
    with pytest.raises(ValueError):pipe.verify_final_source_context_serialization(output,payload,stage="post_seal_tamper")

