"""명시 provider 계획→실제 파일 예약→HTTP mock→독립 판독·대시보드 연결 회귀."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from src.llm_batch.ledger.private_file import create_private_file
from src.llm_batch.measurement.recovery_provider_readback import build_provider_report, validate_provider_report
from src.llm_batch.ledger.recovery_provider_journal import canonical_sha256
from src.llm_batch.runtime import recovery_provider_transport as transport
from tests.recovery_provider_fixtures import build_recovery_provider_fixture
from tests.recovery_execution_fixtures import json_bytes
from tools import run_recovery_provider as workflow


class Clock:
    def __init__(self): self.value = 1000
    def __call__(self): return self.value


class Body(httpx.SyncByteStream):
    def __iter__(self): yield b'{ "results" : [ {"title":"fixture only"} ] }'


def make_workflow_fixture(root):
    with patch("tests.recovery_provider_fixtures.HMAC_KEY", b"k" * 32):
        bundle = build_recovery_provider_fixture(root)
    root = Path(root).resolve()
    plan_path, key_path = root/"explicit_plan.json", root/"existing_private.hex"
    plan_path.write_bytes(json_bytes(bundle["plan"]))
    with os.fdopen(create_private_file(key_path), "wb") as stream:
        stream.write((bundle["hmac_key"].hex() + "\n").encode())
    return {**bundle, "plan_path":plan_path, "key_path":key_path, "root":root,
            "plan_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest()}


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("PIPELINE_MEASUREMENT_", "PIPELINE_PAIRED_EXECUTION_")):
            monkeypatch.delenv(key)
    monkeypatch.delenv("EXPERT_EXECUTION_PROFILE", raising=False)
    import socket
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("external socket forbidden"))


@pytest.fixture
def dashboard(monkeypatch):
    calls=[]
    def health(url):
        calls.append(url)
        return {"url":url, "pid":42, "service":"expert-pipeline-monitor", "standalone":True}
    monkeypatch.setattr(workflow, "_dashboard_health", health)
    return calls


def invoke(bundle, calls, **overrides):
    def send(request):
        snapshot = transport.RecoveryProviderJournal(bundle["bound"].journal_path,
            binding=bundle["bound"].binding, policy=bundle["bound"].policy,
            requests=bundle["bound"].requests).snapshot()
        assert snapshot["open_request_id"] == bundle["bound"].requests[0]["request_id"]
        calls.append(request)
        return httpx.Response(200, stream=Body())
    args = dict(plan_path=bundle["plan_path"], plan_sha256=bundle["plan_sha256"],
        hmac_key_path=bundle["key_path"], attempt_id="recovery-provider-1", session_id="provider-session-1",
        root=bundle["root"], dashboard_url="http://127.0.0.1:8080", clock=Clock(),
        test_transport=httpx.MockTransport(send))
    args.update(overrides)
    return workflow.run_recovery_provider(**args)


def originals(bundle):
    return {str(path):path.read_bytes() for path in [bundle["plan_path"], bundle["key_path"],
        *(Path(ref["path"]) for ref in bundle["source_refs"].values())]}


def test_pipeline_files_report_api_and_zero_dispatch_replay(tmp_path, dashboard):
    bundle = make_workflow_fixture(tmp_path)
    before, calls = originals(bundle), []
    first = invoke(bundle, calls)
    assert first['publish_view'] is True and first['dashboard_reference'] is not None
    assert first["execution_status"] == "PROVIDER_EVIDENCE_STORED"
    assert first["guard_status"] == "GUARD_NOT_EVALUATED"
    assert first["client_http_invocations_this_invocation"] == len(calls) == 1
    assert first["actual_external_calls_this_invocation"] == 0
    assert first["remote_provider_dispatch_count"] is None
    assert first["dashboard"]["visibility_verified"] is False and len(dashboard)==2
    assert not any(first[k] for k in ("public_apply", "central_db_write", "publication_authority"))
    report = json.loads(Path(first["reports"][0]["path"]).read_bytes())
    assert report == build_provider_report(bundle["bound"])
    assert report["input_count"] == 2
    assert [r["state"] for r in report["input_rows"]] == ["PROVIDER_EVIDENCE_STORED", "NO_PLAN_PROVIDED"]
    assert report["client_http_invocations"] == 1 and report["actual_external_call_count"] == 0
    from src.llm_batch.monitor.recovery_provider_view import read_recovery_provider_view
    view = read_recovery_provider_view(bundle["source_refs"]["result"]["path"], tmp_path, item=bundle["result"])
    assert view["binding_status"] == "BOUND" and view["report"] == report
    immutable_paths = [bundle["bound"].journal_path, *(Path(r["path"]) for r in first["reports"]), Path(first["dashboard_reference"]["path"])]
    immutable = {str(p):p.read_bytes() for p in immutable_paths}
    second = invoke(bundle, calls, attempt_id="recovery-provider-2", session_id="provider-session-2")
    assert second["replayed"] and second["client_http_invocations_this_invocation"] == 0 and len(calls)==1
    assert first["reports"] == second["reports"]
    assert {p:Path(p).read_bytes() for p in immutable} == immutable
    assert originals(bundle) == before
    # Node가 소비할 실제 workflow→API payload를 시험 temp에 보존한다.
    (tmp_path/"provider_ui_readback.json").write_bytes(json_bytes({"bound":view, "row":bundle["result"]}))


def test_existing_cli_keeps_companion_publication(tmp_path, dashboard, monkeypatch, capsys):
    bundle = make_workflow_fixture(tmp_path / 'out')
    original = workflow.run_recovery_provider
    calls = []
    def send(request):
        calls.append(request)
        return httpx.Response(200, stream=Body())
    def local_workflow(**kwargs):
        assert 'publish_view' not in kwargs  # 기존 CLI에는 새 생략 옵션을 노출하지 않는다.
        return original(**kwargs, dashboard_url='http://127.0.0.1:8080', clock=Clock(),
                        test_transport=httpx.MockTransport(send))
    monkeypatch.setattr(workflow, 'ROOT', tmp_path)
    monkeypatch.setattr(workflow, 'run_recovery_provider', local_workflow)
    assert workflow.main(['--plan', str(bundle['plan_path']), '--plan-sha256', bundle['plan_sha256'],
        '--hmac-key-file', str(bundle['key_path']), '--attempt-id', 'cli-attempt', '--session-id', 'cli-session']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['publish_view'] is True and result['execution_status'] == 'PROVIDER_EVIDENCE_STORED'
    assert Path(result['dashboard_reference']['path']).is_file() and len(calls) == 1


def make_two_row_workflow_fixture(root):
    """동일 원본 array의 1·2행에 실제 계약으로 별도 provider 계획을 만든다."""
    from src.llm_batch.ledger.recovery_activation import _create_event, extract_direct_ocr_review_proposals
    from src.llm_batch.measurement.semantic_review_router import build_semantic_review_router_receipt
    from src.llm_batch.measurement.semantic_recovery_plan import build_semantic_recovery_plan_receipt
    from src.llm_batch.measurement.recovery_provider_contract import build_recovery_provider_plan, bind_recovery_provider_plan
    first = make_workflow_fixture(root)
    second_result, second_receipt = first['results'][1], first['receipts'][1]
    second_proposal = extract_direct_ocr_review_proposals(second_result)[0]
    second_event = _create_event(receipt=second_receipt, proposal=second_proposal,
        raw_capability='fixture-second-row-only', hmac_key=first['hmac_key'], sequence=2,
        prev_event_sha256=first['event'].event_sha256)
    journal = first['source_bytes']['activation_journal'] + json_bytes(second_event.to_dict()) + b'\n'
    path = Path(first['source_refs']['activation_journal']['path'])
    path.write_bytes(journal)
    first['source_bytes']['activation_journal'] = journal
    first['source_refs']['activation_journal'] = {'path': str(path), 'sha256': hashlib.sha256(journal).hexdigest(), 'bytes': len(journal)}
    first_kwargs = deepcopy(first['build_kwargs'])
    first_kwargs.update(source_refs=deepcopy(first['source_refs']), source_bytes=deepcopy(first['source_bytes']))
    first['plan'] = build_recovery_provider_plan(**first_kwargs)
    first['bound'] = bind_recovery_provider_plan(first['plan'], hmac_key=first['hmac_key'])
    first['plan_path'].write_bytes(json_bytes(first['plan']))
    first['plan_sha256'] = hashlib.sha256(first['plan_path'].read_bytes()).hexdigest()

    second_kwargs = deepcopy(first_kwargs)
    item = second_result['analysis_result']['identity']['image_evidence_catalog'][0]
    capture = deepcopy(first['source_capture'])
    capture.update(input_index=2, post_id=second_result['post_id'],
                   source_locator=second_proposal.source_locator, item=deepcopy(item))
    values = {
        'router': build_semantic_review_router_receipt(second_result, second_receipt, attempt_run_id=second_receipt.attempt_run_id),
        'recovery_plan': build_semantic_recovery_plan_receipt(second_result, second_receipt, attempt_run_id=second_receipt.attempt_run_id),
        'source_capture': capture,
    }
    for role, value in values.items():
        raw = json_bytes(value)
        path = first['root'] / 'source' / ('second_' + role + '.json')
        path.write_bytes(raw)
        second_kwargs['source_bytes'][role] = raw
        second_kwargs['source_refs'][role] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    query = second_proposal.raw_candidate_title
    binding = deepcopy(first['source_binding'])
    binding.update(source_locator=second_proposal.source_locator,
        source_item_sha256=hashlib.sha256(json_bytes(item)).hexdigest(), query=query,
        query_sha256=hashlib.sha256(query.encode()).hexdigest(), span_end=len(query.encode()),
        relation_role=second_proposal.relation_role)
    second_kwargs.update(result_pointer='/1', publication_decision_id=second_receipt.decision_id,
        activation_event_sha256=second_event.event_sha256, source_binding=binding,
        payload={'query': query, 'num_results': 2, 'purpose': values['recovery_plan']['plan']['query_plan']['purposes'][0]},
        output_dir=str(first['root'] / 'second_output'))
    plan = build_recovery_provider_plan(**second_kwargs)
    path = first['root'] / 'second_plan.json'
    path.write_bytes(json_bytes(plan))
    second = {**first, 'plan': plan, 'bound': bind_recovery_provider_plan(plan, hmac_key=first['hmac_key']),
        'plan_path': path, 'plan_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_refs': second_kwargs['source_refs'], 'source_bytes': second_kwargs['source_bytes'], 'result': second_result}
    return first, second


def test_two_rows_share_base_output_without_provider_companion_publish(tmp_path, dashboard):
    first, second = make_two_row_workflow_fixture(tmp_path)
    output = Path(first['source_refs']['result']['path'])
    assert second['source_refs']['result'] == first['source_refs']['result']
    companion = output.with_name(output.stem + '_recovery_provider_view.json')
    # main의 별도 aggregate 경로에서는 기존 companion의 내용까지 손대지 않는다.
    companion.write_bytes(b'original companion remains untouched')
    before = {**originals(first), **originals(second), str(companion): companion.read_bytes()}
    report_refs = []
    for index, bundle in enumerate((first, second), 1):
        calls = []
        value = invoke(bundle, calls, publish_view=False, attempt_id=f'row-{index}-attempt', session_id=f'row-{index}-session')
        assert value['execution_status'] == 'PROVIDER_EVIDENCE_STORED'
        assert value['publish_view'] is False and value['dashboard_reference'] is None
        assert value['client_http_invocations_this_invocation'] == len(calls) == 1
        assert value['actual_external_calls_this_invocation'] == 0
        assert value['resources_start']['numeric_threads'] == value['resources_end']['numeric_threads']
        report = json.loads(Path(value['reports'][0]['path']).read_bytes())
        assert report == build_provider_report(bundle['bound'])
        assert [row['state'] for row in report['input_rows']] == (
            ['PROVIDER_EVIDENCE_STORED', 'NO_PLAN_PROVIDED'] if index == 1
            else ['NO_PLAN_PROVIDED', 'PROVIDER_EVIDENCE_STORED'])
        assert json.loads(json.dumps(value, allow_nan=False)) == value  # namespace 밖으로 JSON/ref만 반환
        replay = invoke(bundle, calls, publish_view=False)
        assert replay['replayed'] and replay['client_http_invocations_this_invocation'] == 0 and len(calls) == 1
        assert replay['reports'] == value['reports']
        report_refs.append(value['reports'][0])
    assert len(dashboard) == 8 and report_refs[0]['path'] != report_refs[1]['path']
    assert {path: Path(path).read_bytes() for path in before} == before


@pytest.mark.parametrize('failure', ['plan_sha', 'key', 'dashboard', 'source', 'mode', 'option_type'])
def test_publish_disabled_keeps_preflight_and_original_bytes(tmp_path, dashboard, monkeypatch, failure):
    bundle = make_workflow_fixture(tmp_path)
    options = {'publish_view': False}
    if failure == 'plan_sha': options['plan_sha256'] = '0' * 64
    elif failure == 'key': options['hmac_key_path'] = tmp_path / 'missing.hex'
    elif failure == 'dashboard':
        monkeypatch.setattr(workflow, '_dashboard_health', lambda *_: (_ for _ in ()).throw(OSError('offline')))
    elif failure == 'source': Path(bundle['source_refs']['manifest']['path']).write_bytes(b'{}')
    elif failure == 'mode': monkeypatch.setenv('PIPELINE_MEASUREMENT_EXECUTION_MODE', 'AFTER')
    else: options['publish_view'] = 0
    before, calls = originals(bundle), []
    with pytest.raises((ValueError, OSError)):
        invoke(bundle, calls, **options)
    assert calls == [] and not bundle['bound'].journal_path.exists()
    assert originals(bundle) == before


@pytest.mark.parametrize("failure", ["plan_sha", "missing_key", "synthetic_real", "same_attempt", "no_dashboard", "source_changed", "foreign_companion", "mixed_measurement"])
def test_preflight_failure_does_not_create_journal_or_send(tmp_path, dashboard, monkeypatch, failure):
    bundle=make_workflow_fixture(tmp_path); calls=[]; args={}
    if failure=="plan_sha": args["plan_sha256"]="0"*64
    elif failure=="missing_key": args["hmac_key_path"]=tmp_path/"missing.hex"
    elif failure=="synthetic_real": args["test_transport"]=None
    elif failure=="same_attempt": args["attempt_id"]=bundle["bound"].base["base_attempt_run_id"]
    elif failure=="no_dashboard": monkeypatch.setattr(workflow,"_dashboard_health",lambda *_:(_ for _ in ()).throw(OSError("offline")))
    elif failure=="source_changed": Path(bundle["source_refs"]["manifest"]["path"]).write_bytes(b"{}")
    elif failure=="foreign_companion":
        result=Path(bundle["source_refs"]["result"]["path"])
        result.with_name(result.stem+"_recovery_provider_view.json").write_bytes(b"{}")
    else: monkeypatch.setenv("PIPELINE_MEASUREMENT_EXECUTION_MODE","AFTER")
    before=originals(bundle)
    with pytest.raises((ValueError,OSError)): invoke(bundle,calls,**args)
    assert not calls and not bundle["bound"].journal_path.exists()
    assert originals(bundle)==before


@pytest.mark.parametrize("failure", ["timeout", "http", "invalid_json"])
def test_failure_is_saved_and_restart_does_not_retry(tmp_path, dashboard, failure):
    bundle=make_workflow_fixture(tmp_path); calls=[]
    def send(req):
        calls.append(req)
        if failure=="timeout": raise httpx.ReadTimeout("private endpoint")
        class Raw(httpx.SyncByteStream):
            def __iter__(self): yield b'{"broken":}' if failure=="invalid_json" else b'{}'
        return httpx.Response(503 if failure=="http" else 200,stream=Raw())
    result=invoke(bundle,calls,test_transport=httpx.MockTransport(send))
    assert result["execution_status"]=="PROVIDER_REQUEST_FAILED"
    assert result["guard_status"]=="GUARD_NOT_EVALUATED" and len(calls)==1
    report=build_provider_report(bundle["bound"])
    assert report["client_http_invocations"]==1
    retry=invoke(bundle,calls)
    assert retry["replayed"] and len(calls)==1


def test_terminal_storage_crash_is_unknown_and_new_attempt_cannot_resend(tmp_path,dashboard,monkeypatch):
    bundle=make_workflow_fixture(tmp_path);calls=[]
    from src.llm_batch.ledger import recovery_provider_journal as journal
    original=journal._Transaction.append
    def append(self,*,expected_head_sha256,event):
        if event["event_type"]=="REQUEST_TERMINAL": raise OSError("private path")
        return original(self,expected_head_sha256=expected_head_sha256,event=event)
    monkeypatch.setattr(journal._Transaction,"append",append)
    result=invoke(bundle,calls)
    assert result["execution_status"]=="INCOMPLETE_DISPATCH" and len(calls)==1
    report=build_provider_report(bundle["bound"])
    assert report["client_http_invocations"] is None and report["actual_external_call_count"]==0
    monkeypatch.setattr(journal._Transaction,"append",original)
    result=invoke(bundle,calls,attempt_id="different-attempt")
    assert result["client_http_invocations_this_invocation"]==0 and len(calls)==1
    assert result["execution_status"]=="INCOMPLETE_DISPATCH"


@pytest.mark.parametrize("target", ["raw", "transport", "anchor", "report", "markdown"])
def test_saved_artifact_corruption_is_not_repaired_or_resent(tmp_path,dashboard,target):
    bundle=make_workflow_fixture(tmp_path);calls=[];first=invoke(bundle,calls)
    report=build_provider_report(bundle["bound"])
    if target=="raw": path=bundle["bound"].output_dir/report["request_receipts"][0]["response_ref"]["path"]
    elif target=="transport": path=bundle["bound"].output_dir/report["request_receipts"][0]["transport_ref"]["path"]
    elif target=="anchor": path=bundle["bound"].journal_path.with_name("provider_journal.jsonl.anchor.json")
    else: path=Path(first["reports"][0 if target=="report" else 1]["path"])
    path.write_bytes(b"changed")
    with pytest.raises((ValueError,OSError)): invoke(bundle,calls)
    assert len(calls)==1 and path.read_bytes()==b"changed"


@pytest.mark.parametrize("change",["authority","guard","count","status","row","ref",
    "request_actual","success_zero_calls","response_bytes","transport_sha"])
def test_resealed_report_cannot_invent_guard_or_counts(tmp_path,dashboard,change):
    bundle=make_workflow_fixture(tmp_path); invoke(bundle,[])
    report=build_provider_report(bundle["bound"])
    if change=="authority": report["public_apply"]=True
    elif change=="guard": report["guard_status"]="PASSED"
    elif change=="count": report["actual_external_call_count"]=1
    elif change=="status": report["execution_status"]="INCOMPLETE_DISPATCH"
    elif change=="row": report["input_rows"][1]["state"]="PROVIDER_EVIDENCE_STORED"
    elif change=="request_actual": report["request_receipts"][0]["actual_external_call_count"]=1
    elif change=="success_zero_calls":
        report["request_receipts"][0]["client_http_invocations"]=0
        report["client_http_invocations"]=0
    elif change=="response_bytes": report["request_receipts"][0]["observed_response_bytes"]+=1
    elif change=="transport_sha": report["request_receipts"][0]["transport_receipt_sha256"]=None
    else: report["request_receipts"][0]["response_ref"]["path"]="responses/"+"0"*64+".bin"
    report["report_sha256"]=canonical_sha256({k:v for k,v in report.items() if k!="report_sha256"})
    with pytest.raises(ValueError):validate_provider_report(report)


def test_same_job_moved_output_cannot_reset_budget(tmp_path,dashboard):
    bundle=make_workflow_fixture(tmp_path);calls=[]
    first=invoke(bundle,calls)
    from src.llm_batch.measurement.recovery_provider_contract import build_recovery_provider_plan, bind_recovery_provider_plan
    moved=build_recovery_provider_plan(**{**bundle["build_kwargs"],"output_dir":str(tmp_path/"moved_output")})
    assert moved["job_id"]==bundle["plan"]["job_id"]
    moved_path=tmp_path/"moved_plan.json";moved_path.write_bytes(json_bytes(moved))
    with pytest.raises(ValueError,match="다른 provider 보고서가 이미 연결"):
        invoke(bundle,calls,plan_path=moved_path,plan_sha256=hashlib.sha256(moved_path.read_bytes()).hexdigest())
    with pytest.raises(ValueError,match="동일 provider job"):
        invoke(bundle,calls,plan_path=moved_path,plan_sha256=hashlib.sha256(moved_path.read_bytes()).hexdigest(),publish_view=False)
    moved_bound=bind_recovery_provider_plan(moved,hmac_key=bundle["hmac_key"])
    with pytest.raises(ValueError,match="동일 provider job"):
        workflow._claim_job(moved_bound,bundle["root"])
    assert len(calls)==1 and not (tmp_path/"moved_output/provider_journal.jsonl").exists()
    assert json.loads(Path(first["job_reference"]["path"]).read_bytes())["output_dir"]==str(bundle["bound"].output_dir)


def test_reader_does_not_count_zero_after_journal_loss(tmp_path,dashboard):
    bundle=make_workflow_fixture(tmp_path);calls=[];invoke(bundle,calls)
    bundle["bound"].journal_path.write_bytes(b"")
    with pytest.raises(ValueError,match="JOURNAL_MISSING_AFTER_ANCHOR"):
        build_provider_report(bundle["bound"])
    with pytest.raises(ValueError):invoke(bundle,calls)
    assert len(calls)==1


@pytest.mark.parametrize("changed_key", ["reservation_consumed", "observed_response_sha256"])
def test_reader_rejects_resealed_transport_receipt_semantic_drift(tmp_path,dashboard,changed_key):
    bundle=make_workflow_fixture(tmp_path);invoke(bundle,[])
    bound=bundle["bound"]
    events=[json.loads(line) for line in bound.journal_path.read_bytes().splitlines()]
    terminal=next(e for e in events if e["event_type"]=="REQUEST_TERMINAL")
    saved=terminal["payload"]
    path=bound.output_dir/saved["transport_ref"]["path"]
    payload=json.loads(path.read_bytes())
    payload[changed_key]=False if changed_key=="reservation_consumed" else "0"*64
    payload["receipt_sha256"]=canonical_sha256({k:v for k,v in payload.items() if k!="receipt_sha256"})
    raw=json_bytes(payload);path.write_bytes(raw)
    saved["transport_ref"].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    saved["transport_receipt_sha256"]=payload["receipt_sha256"]
    previous="GENESIS"
    for event in events:
        event["prev_event_sha256"]=previous
        if event["event_type"]=="REQUEST_FINALIZED":event["payload"]["terminal_sha256"]=terminal["event_sha256"]
        event["event_sha256"]=canonical_sha256({k:v for k,v in event.items() if k!="event_sha256"})
        previous=event["event_sha256"]
    bound.journal_path.write_bytes(b"".join(json_bytes(e)+b"\n" for e in events))
    with pytest.raises(ValueError):build_provider_report(bound)
