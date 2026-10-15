"""저장 28번 두 전문가의 부분 context→main→WAL 및 계약 변조 회귀."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.grounding.candidate_set_shadow import selective_shadow_from_identity
from llm_batch.grounding.candidate_audit import apply_candidate_audit_fields
from llm_batch.ledger.publication_commit import PublicationCommitRegistry, build_publication_scope_descriptor, commit_publication_result
from test_source_bound_nsfw_desire import actual_main_sync_and_wrapper

FIXTURE = Path(__file__).parent/'fixtures/shadow_contract_repair_v1.json'
FIXTURE_SHA256 = '6b6ed252615e76e66db77fcef818a09256e6e62f83c26dd4202a87b4b7239307'
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA256
DATA = json.loads(FIXTURE.read_bytes())
CONTRACT_KEYS = ('promotion_gate_state','promotion_gate_evidence','promotion_decision',
                 'publish_contract_input_fingerprint','publish_contract_version','publish_contract_trace','publish_ledger')


class ExternalAttempt(BaseException):
    """제품의 일반 예외 처리로 외부 호출 시도를 숨기지 않는다."""


class NoExternal:
    def __init__(self): self.attempts=[]
    def __getattr__(self,name):
        def denied(*args,**kwargs):
            self.attempts.append(name)
            raise ExternalAttempt('EXTERNAL_CALL_FORBIDDEN:'+name)
        return denied


def check_mirrors(identity):
    assert isinstance(identity.get('candidate_ledger'),dict)
    for key in CONTRACT_KEYS:
        assert key in identity and key in identity['candidate_ledger'], key
        assert identity[key]==identity['candidate_ledger'][key], key
    shadow=selective_shadow_from_identity(identity).to_dict()
    assert shadow['schema_version']=='candidate_set_nil_shadow_v1'
    assert shadow['action_applied'] is False
    return copy.deepcopy({key:identity.get(key) for key in CONTRACT_KEYS})


def test_saved28_veto_transports_one_contract_through_typed_main_and_wal(tmp_path):
    original_fixture=FIXTURE.read_bytes()
    record=copy.deepcopy(DATA['records']['28'])
    packet=record['packet']
    assert type(packet['post_id']) is int and packet['post_id']==11172535
    assert set(record['experts'])=={'gatekeeper','discourse'}
    canonical=lambda value: json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    assert hashlib.sha256(canonical({'post':packet['source_post'],'comments':packet['source_comments']})).hexdigest()==packet['source_canonical_sha256']
    assert hashlib.sha256(canonical(packet['checkpoint_result'])).hexdigest()==packet['result_canonical_sha256']
    raw=dict(copy.deepcopy(packet['source_post']),comments=copy.deepcopy(packet['source_comments']))
    post=PostInput(**raw)
    external=NoExternal()
    pipe=AgenticPipeline(llm=external,mcp=external,output_dir=tmp_path,max_iterations=1,
                        parallel_count=12,worker_id=0,native_recovery=True)
    pipe.enable_url_fetch_disk_cache=False
    pipe._use_session_knowledge=False
    ctx=ConversationContext(post_id=post.post_id,post_data=pipe._post_to_dict(post),comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs=pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs=tuple(post.comments)
    ctx._source_bound_nsfw_original_carrier=pipe._capture_source_bound_nsfw_carrier(post)
    for name,value in record['experts'].items():ctx.set_expert_output(ExpertType(name),copy.deepcopy(value))
    disc=record['experts']['discourse']['discourse_analysis']
    ctx.primary_domain,ctx.discourse_intent=disc['primary_domain'],disc['intent']
    ctx.discourse_warning=record['discourse_warning_observations'][-1]['value']
    source_before=copy.deepcopy([ctx.post_data,ctx.comments,ctx._final_source_original_inputs])
    output=pipe._context_to_output(ctx)
    payload=output.model_dump(mode='json')
    assert payload['identity']['promotion_gate_state']['source']=='final_source_bound_community_nonwork_veto'
    contract=check_mirrors(payload['identity'])
    assert payload['identity']['novel_identity'] is None
    assert payload['identity']['promotion_decision']['publish_allowed'] is False
    wrapper=actual_main_sync_and_wrapper(payload,ctx.post_data)
    assert check_mirrors(payload['identity'])==contract
    assert 'candidate_set_shadow_contract_invalid' not in (payload['identity'].get('candidate_audit_lint') or [])
    pipe.verify_final_source_context_serialization(output,payload,stage='shadow_repair_actual_main')
    wrapped=wrapper(dict(raw,analysis_result=payload),output=output,verifier=pipe.verify_final_source_context_serialization)
    scope=build_publication_scope_descriptor(input_file_sha256=packet['source_canonical_sha256'],post_ids=[post.post_id],
        config_hash='shadow-repair-saved28-partial',release_fingerprint='candidate-only')
    wal=tmp_path/'publication.jsonl'
    registry=PublicationCommitRegistry(wal,scope_descriptor=scope,create_new=True)
    commit,created=commit_publication_result(wrapped,registry=registry,attempt_run_id='shadow-repair',input_index=1,post_id=post.post_id)
    saved=PublicationCommitRegistry(wal,scope_descriptor=scope,create_new=False).result(post.post_id)
    assert created and commit.outcome=='HOLD' and commit.publish_allowed is False
    assert check_mirrors(saved['analysis_result']['identity'])==contract
    wrapped.verify_stored_payload(saved,stage='shadow_repair_wal')
    assert source_before==[ctx.post_data,ctx.comments,ctx._final_source_original_inputs]
    assert external.attempts==[] and FIXTURE.read_bytes()==original_fixture


@pytest.mark.parametrize('mutation',['root_ledger_state_mismatch','same_mutated_decision'])
def test_contract_tampering_remains_unavailable_without_publication(mutation):
    original_fixture=FIXTURE.read_bytes()
    identity=copy.deepcopy(DATA['records']['51']['packet']['checkpoint_result']['analysis_result']['identity'])
    # 정상 51번이 먼저 유효해야 변조 거절을 정상 대조로 읽을 수 있다.
    check_mirrors(identity)
    assert identity['promotion_decision']['publish_allowed'] is False
    novel=copy.deepcopy(identity['novel_identity'])
    if mutation=='root_ledger_state_mismatch':identity['promotion_gate_state']['source']='deliberate-tamper'
    else:
        identity['promotion_decision']['status']='deliberate-tamper'
        identity['candidate_ledger']['promotion_decision']['status']='deliberate-tamper'
    with pytest.raises(ValueError):selective_shadow_from_identity(identity)
    apply_candidate_audit_fields(identity)
    assert identity['candidate_ledger']['candidate_set_shadow']['schema_version']=='candidate_set_nil_shadow_unavailable_v1'
    assert identity['novel_identity']==novel
    assert identity['promotion_decision']['publish_allowed'] is False
    assert FIXTURE.read_bytes()==original_fixture
