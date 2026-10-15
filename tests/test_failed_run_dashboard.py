"""실패 수령증→기존 ingest→상태/표시 계약. 네트워크는 mock이며 원문은 불변이다."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import attach_manifest_dashboard as attach
from tools import run_independent_plan as runner
from llm_batch.monitor.event_bus import MonitorState
from llm_batch.monitor.forwarder import DashboardForwarder
from llm_batch.monitor import server


def put(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def failure_files(tmp_path):
    output = tmp_path / "before.json"
    manifest = put(tmp_path / "before_manifest.json", {
        "run_id": "20261013_125737_380361", "output_file": str(output),
        "publication_scope_id": "a" * 64, "input_post_count": 24,
        "completed_count": 0, "flushed_count": 0, "pending_count": 0, "failed_count": 0,
        "parallel_count": 12, "effective_parallel": 12, "terminal_artifacts_finalized": False,
        "large_run_complete": False,
        "paired_execution_observation": {"start": {"observed_at": "2026-10-13T12:59:44+00:00"}},
    })
    claim = put(tmp_path / "claim.json", {"run_id": "20261013_125737_380361", "output_file": str(output)})
    plan = put(tmp_path / "plan.json", {"planned_runs": [{"output_json": str(output),
        "manifest_json": str(manifest), "output_attempt_claim_json": str(claim)}]})
    receipt = put(tmp_path / "execution.receipt.json", {
        "receipt_type": "independent_plan_execution_receipt", "gate": "FAILED", "exit_code": 1,
        "plan": str(plan), "plan_sha256": digest(plan), "failed_run_index": 1,
        "completed_at": "2026-10-13T22:05:08+09:00", "completed_runs": 0,
    })
    return manifest, receipt, plan, claim


def item_for(files):
    return attach._failure_item(files[0], files[1], expected_run_id="20261013_125737_380361")


def ready_monitor(files):
    m = MonitorState()
    manifest = json.loads(files[0].read_text("utf-8"))
    m.ingest_event("batch_start", {"total": 24, "parallel_count": 12, "output_file": manifest["output_file"]})
    m.load_status_snapshot(attach._snapshot(manifest, started_at=1791896384.0, summary_limit=5))
    m.ingest_event("post_start", {"post_id": 7, "worker_id": 1, "index": 4, "title": "아직 처리 중"})
    m.ingest_event("post_complete", {"post_id": 4, "worker_id": 0, "is_relevant": False})
    return m


def test_receipt_to_ingest_clears_ghost_without_manufacturing_result_or_terminal(failure_files):
    before = [p.read_bytes() for p in failure_files]
    m = ready_monitor(failure_files)
    assert m.get_status()["active_posts"]
    with patch.object(server, "monitor", m), patch.object(server, "_is_standalone_mode", return_value=True), patch.object(server, "_ingest_token_ok", return_value=True):
        response = server.api_ingest(SimpleNamespace(headers={}), {"items": [item_for(failure_files)]})
    assert json.loads(response.body)["accepted"] == 1
    status = m.get_status()
    assert status["batch_status"] == "FAILED" and status["batch_running"] is False
    assert status["active_posts"] == {} and status["current_post_id"] is None
    assert status["done_count"] == 1 and status["total_posts"] == 24
    assert status["batch_failure"]["manifest_counts"]["flushed_count"] == 0
    assert status["elapsed_sec"] == 324.0 and status["eta_sec"] == 0
    assert [p.read_bytes() for p in failure_files] == before
    assert not (failure_files[0].parent / "before.json").exists()
    assert json.loads(failure_files[0].read_bytes())["terminal_artifacts_finalized"] is False


@pytest.mark.parametrize("change", ["run", "output", "total"])
def test_cross_run_or_denominator_mismatch_is_not_an_ack(failure_files, change):
    m = ready_monitor(failure_files); item = item_for(failure_files)
    if change == "run": item["data"]["run_id"] = "other"
    elif change == "output": item["data"]["output_file"] += ".other"
    else: item["data"]["manifest_counts"]["input_post_count"] = 25
    before = m.get_status()
    with patch.object(server, "monitor", m), patch.object(server, "_is_standalone_mode", return_value=True), patch.object(server, "_ingest_token_ok", return_value=True):
        reply = server.api_ingest(SimpleNamespace(headers={}), {"items": [item]})
    assert json.loads(reply.body)["accepted"] == 0
    assert m.batch_running and m.batch_failure is None
    assert m.get_status()["active_posts"] == before["active_posts"]


def test_same_output_without_run_binding_is_rejected_but_empty_restart_can_restore_failure(failure_files):
    data = item_for(failure_files)["data"]
    m = MonitorState(); m.ingest_event("batch_start", {"total": 24, "output_file": data["output_file"]})
    assert m.ingest_event("batch_failed", data) is False
    empty = MonitorState()
    assert empty.ingest_event("batch_failed", data) is True
    assert empty.get_status()["parallel_count"] == 12
    assert empty.get_status()["total_posts"] == 24 and empty.get_status()["done_count"] == 0


def test_failure_latch_rejects_late_snapshots_events_and_replay_after_new_run(failure_files):
    m = ready_monitor(failure_files); data = item_for(failure_files)["data"]
    assert m.ingest_event("batch_failed", data) is True
    assert m.ingest_event("batch_failed", deepcopy(data)) is True
    for event in ("post_start", "expert_phase", "batch_complete", "llm_suspend"):
        assert m.ingest_event(event, {"post_id": 99}) is False
    for run in (data["run_id"], None):
        assert m.load_status_snapshot({"output_file": data["output_file"], "run_id": run,
            "batch_running": True, "active_posts": {"99": {}}, "batch_start_time": 1}) is False
    assert m.ingest_event("batch_start", {"output_file": data["output_file"]}) is False
    assert m.get_status()["batch_status"] == "FAILED" and not m.active_posts
    m.ingest_event("batch_start", {"run_id": "new", "output_file": data["output_file"] + ".new", "total": 2})
    assert m.batch_running and m.batch_failure is None
    assert m.ingest_event("batch_failed", data) is False
    assert m.load_status_snapshot({"output_file": data["output_file"], "run_id": data["run_id"], "batch_running": True}) is False
    assert m.get_status()["run_id"] == "new"


@pytest.mark.parametrize("field,value", [("exit_code", False), ("parallel_count", 0),
    ("started_at_epoch", float("nan")), ("ended_at_epoch", 1),
    ("reason_code", "COMPLETE"), ("schema_version", "future")])
def test_invalid_failure_transport_does_not_change_state(failure_files, field, value):
    m = ready_monitor(failure_files); data = item_for(failure_files)["data"];data[field] = value
    assert m.ingest_event("batch_failed", data) is False
    assert m.batch_running


@pytest.mark.parametrize("fault", ["plan_sha", "gate", "index_bool", "exit_zero", "run", "output", "claim", "counts", "time"])
def test_receipt_binding_rejects_mismatch_before_delivery(failure_files, fault):
    manifest, receipt, plan, claim = failure_files
    r = json.loads(receipt.read_bytes());m = json.loads(manifest.read_bytes())
    if fault == "plan_sha": r["plan_sha256"] = "0" * 64
    elif fault == "gate": r["gate"] = "PASS"
    elif fault == "index_bool": r["failed_run_index"] = True
    elif fault == "exit_zero": r["exit_code"] = 0
    elif fault == "run": m["run_id"] = "foreign"
    elif fault == "output": m["output_file"] += ".other"
    elif fault == "claim": put(claim, {"run_id": "foreign", "output_file": m["output_file"]})
    elif fault == "counts": m["completed_count"] = True
    elif fault == "time": r["completed_at"] = "2026-10-12T00:00:00+00:00"
    put(receipt, r);put(manifest,m)
    with pytest.raises(ValueError): item_for(failure_files)


def test_zero_child_exit_with_explicit_artifact_failure_keeps_terminal_evidence(failure_files):
    manifest, receipt, *_ = failure_files
    r=json.loads(receipt.read_bytes());r.update(gate="FAILED_RUNTIME_ARTIFACT_VALIDATION",error="ValueError: incomplete artifacts")
    put(receipt,r);m=json.loads(manifest.read_bytes());m["terminal_artifacts_finalized"]=True;put(manifest,m)
    data=item_for(failure_files)["data"]
    assert data["reason_code"] == "ARTIFACT_VALIDATION_FAILED"
    assert data["exit_code"] == 0 and data["invocation_exit_code"] == 1
    assert data["terminal_artifacts_finalized"] is True
    assert json.loads(manifest.read_bytes())["terminal_artifacts_finalized"] is True


def test_explicit_epoch_and_aware_observation_do_not_parse_utc_plan_id_as_local(failure_files):
    m=json.loads(failure_files[0].read_bytes())
    expected=datetime(2026,10,13,12,59,44,tzinfo=timezone.utc).timestamp()
    with patch.object(attach.time,"mktime",side_effect=AssertionError("run ID timezone guessing")):
        assert attach._started_at_from_manifest(m) == expected
        assert attach._start_time_source(m) == "PAIRED_START_OBSERVATION"
        assert attach._start_time_source({},expected) == "RUNNER_EPOCH"
        assert attach._start_time_source({}) == "LEGACY_INFERRED_OR_ATTACH_TIME"
        assert attach._started_at_from_manifest(m,expected-5) == expected-5
    with pytest.raises(ValueError): attach._started_at_from_manifest(m,float("inf"))


def test_success_running_and_legacy_incomplete_stay_distinct():
    m=MonitorState();m.ingest_event("batch_start",{"total":2,"output_file":"ok.json"})
    assert m.batch_status == "RUNNING"
    m.load_status_snapshot({"batch_running":False,"total_posts":2,"done_count":1})
    assert m.batch_status == "INCOMPLETE"
    m.ingest_event("batch_complete",{})
    assert m.get_status()["batch_status"] == "COMPLETED" and m.batch_failure is None


def test_forwarder_snapshot_preserves_failure_without_new_publication_authority(failure_files):
    m=ready_monitor(failure_files);m.ingest_event("batch_failed",item_for(failure_files)["data"])
    # Snapshot serialization only: no forwarder thread or HTTP client initialization.
    forwarder=DashboardForwarder.__new__(DashboardForwarder);forwarder._monitor=m
    snap=forwarder._make_snapshot_item()["data"]
    assert snap["batch_status"] == "FAILED" and snap["active_posts"] == {}
    assert snap["batch_failure"]["receipt_ref"]["sha256"] == digest(failure_files[1])
    restored=MonitorState();assert restored.load_status_snapshot(snap) is True
    assert restored.batch_status=="FAILED" and not restored.active_posts
    mixed=deepcopy(snap);mixed["output_file"] += ".other"
    assert restored.load_status_snapshot(mixed) is False


@pytest.mark.parametrize("accepted,expected",[(1,0),(0,2)])
def test_failure_cli_posts_only_scoped_event_not_snapshot_or_complete(failure_files,accepted,expected):
    args=["attach", "--manifest", str(failure_files[0]), "--failure-receipt", str(failure_files[1]),
          "--expected-run-id","20261013_125737_380361","--dashboard-url","http://unused"]
    with patch.object(sys,"argv",args),patch.object(attach,"_post_items",return_value={"accepted":accepted}) as post:
        assert attach.main() == expected
    sent=post.call_args.args[1]
    assert len(sent)==1 and sent[0]["type"]=="batch_failed"


def test_runner_notifier_preserves_failure_and_reports_delivery_error(failure_files):
    m=ready_monitor(failure_files)
    def deliver(url,items,**kwargs):
        return {"accepted":int(m.ingest_event(items[0]["type"],items[0]["data"]) is True)}
    start=attach._started_at_from_manifest(json.loads(failure_files[0].read_bytes()))
    before=failure_files[1].read_bytes()
    with patch.object(attach,"_post_items",side_effect=deliver):
        result=runner._notify_dashboard_failure(manifest_path=failure_files[0],receipt_path=failure_files[1],dashboard_url="http://unused",started_at_epoch=start)
    assert result["status"] == "ACKNOWLEDGED" and m.batch_status == "FAILED"
    with patch.object(attach,"_post_items",side_effect=OSError("offline")):
        result=runner._notify_dashboard_failure(manifest_path=failure_files[0],receipt_path=failure_files[1],dashboard_url="http://unused",started_at_epoch=start)
    assert result["status"] == "NOT_DELIVERED" and failure_files[1].read_bytes()==before


def test_runner_attacher_passes_known_epoch_as_argv(tmp_path):
    fake=SimpleNamespace(pid=123)
    with patch.object(runner.subprocess,"Popen",return_value=fake) as popen:
        runner._start_manifest_attach(manifest_path=tmp_path/"m.json",dashboard_url="http://unused",
            log_path=tmp_path/"attach.log",python_executable="python",started_at_epoch=1791896384.125)
    argv=popen.call_args.args[0]
    assert argv[argv.index("--started-at-epoch")+1] == "1791896384.125"


@pytest.mark.parametrize("mode",["success","artifact_failure","child_failure"])
def test_actual_runner_branches_mock_popen_write_receipt_then_deliver(tmp_path,mode):
    child_rc=7 if mode=="child_failure" else 0
    # 실제 runner 제어 흐름을 사용하되 child와 HTTP는 생성하지 않는다.
    output=tmp_path/"before.json";manifest=tmp_path/"before_manifest.json";checkpoint=tmp_path/"before_checkpoint.jsonl"
    argv=[sys.executable,"-c","raise SystemExit('fixture never executed')"]
    run={"post_id":"1","repeat_index":1,"output_json":str(output),"manifest_json":str(manifest),
         "checkpoint_jsonl":str(checkpoint),"command_argv":argv}
    plan=put(tmp_path/"plan.json",{"planned_runs":[run]})
    m=MonitorState();captures=[]
    def fake_popen(actual_argv,**kwargs):
        assert actual_argv==argv
        put(manifest,{"run_id":"runner-failed","output_file":str(output),"input_post_count":1,
            "completed_count":0,"flushed_count":0,"pending_count":0,"failed_count":0,"large_run_complete":False})
        if mode=="success":
            put(output,[{"post_id":"1","run_meta":{"run_id":"runner-failed"}}])
            checkpoint.write_text(json.dumps({"post_id":"1","status":"completed"})+"\n",encoding="utf-8")
            put(manifest,{"run_id":"runner-failed","output_file":str(output),"checkpoint_jsonl":str(checkpoint),
                "input_post_count":1,"completed_count":1,"flushed_count":1,"pending_count":0,"failed_count":0})
        return SimpleNamespace(pid=54321,stdout=io.StringIO("fixture log\n"),wait=lambda **kw:child_rc)
    def deliver(url,items,**kwargs):
        captures.extend(items)
        return {"accepted":int(m.ingest_event(items[0]["type"],items[0]["data"]) is True)}
    with patch.object(runner,"_ensure_dashboard",return_value={"ok":True,"standalone":True}), \
         patch.object(runner,"_start_manifest_attach",return_value=(SimpleNamespace(pid=999),{"pid":999})), \
         patch.object(runner,"_finish_manifest_attach",return_value=0), \
         patch.object(runner.subprocess,"Popen",side_effect=fake_popen) as popen, \
         patch.object(runner,"_process_creation_token",return_value="fixture-process-creation"), \
         patch.object(attach,"_post_items",side_effect=deliver):
        kwargs=dict(plan_path=plan,log_dir=tmp_path/"logs",env_updates={},skip_existing=False,
                    limit=None,dashboard_url="http://unused",dashboard_python=sys.executable)
        if mode=="success":
            assert runner.run_plan(**kwargs)==0
        elif child_rc:
            assert runner.run_plan(**kwargs)==child_rc
        else:
            with pytest.raises(ValueError):runner.run_plan(**kwargs)
        assert popen.call_count==1
    if mode=="success":
        assert not captures
        assert not list((tmp_path/"logs"/"attempts").glob("*/*.dashboard_failure.json"))
        return
    assert len(captures)==1 and captures[0]["type"]=="batch_failed"
    assert m.batch_status=="FAILED" and not m.batch_running
    receipt=next((tmp_path/"logs"/"attempts").glob("*/execution.receipt.json"))
    r=json.loads(receipt.read_bytes())
    assert r["exit_code"] == (child_rc or 1)
    assert datetime.fromisoformat(r["completed_at"]).tzinfo is not None
    delivery=json.loads(next((tmp_path/"logs"/"attempts").glob("*/run_001_before.dashboard_failure.json")).read_bytes())
    assert delivery["status"]=="ACKNOWLEDGED" and not output.exists()


def core_notice(files, scope="a" * 64):
    data=deepcopy(item_for(files)["data"])
    for key in ("manifest_ref","invocation_exit_code","terminal_artifacts_finalized"):
        data.pop(key,None)
    data.update(failure_origin="CORE_EXCEPTION",reason_code="CORE_EXCEPTION",exit_code=None,
        process_exited=False,publication_scope_id=scope,shutdown_status="DRAINING",
        receipt_ref=None,rejected_row_ref=None,message="PublicationCommitError: original rejection")
    data["manifest_counts"]["failed_count"]=1
    return data


def test_core_draining_drained_are_not_exit_then_runner_observation_completes_failure(failure_files):
    m=ready_monitor(failure_files); core=core_notice(failure_files)
    assert m.ingest_failure(core) is True
    assert m.batch_failure["exit_code"] is None and m.batch_failure["process_exited"] is False
    drained={**core,"shutdown_status":"DRAINED"}
    assert m.ingest_failure(drained) is True
    assert m.ingest_failure(core) is False
    assert m.ingest_failure(item_for(failure_files)["data"]) is True
    assert m.batch_failure["process_exited"] is True and m.batch_failure["exit_code"]==1
    assert m.ingest_failure(drained) is False


@pytest.mark.parametrize("scope",[None,"b"*64,""])
def test_known_scope_cannot_be_bypassed_by_null_other_or_empty(failure_files,scope):
    m=ready_monitor(failure_files)
    assert m.publication_scope_id=="a"*64
    assert m.ingest_failure(core_notice(failure_files,scope)) is False
    assert m.batch_running


def test_scope_not_created_allows_only_matching_null_and_actual_start_epoch(failure_files):
    output=json.loads(failure_files[0].read_bytes())["output_file"]
    m=MonitorState();m.ingest_event("batch_start",{"run_id":"20261013_125737_380361",
        "publication_scope_id":None,"output_file":output,"total":24,"started_at_epoch":1234.5})
    assert m.batch_start_time==1234.5
    assert m.ingest_failure(core_notice(failure_files,None)) is True
    assert m.batch_failure["process_exited"] is False


def test_verified_receipt_can_bind_legacy_output_only_but_scope_conflict_still_rejects(failure_files):
    data=item_for(failure_files)["data"]
    for existing_scope,accepted in [(None,1),("b"*64,0)]:
        m=MonitorState();m.ingest_event("batch_start",{"output_file":data["output_file"],"total":24,
            "publication_scope_id":existing_scope})
        assert not m.run_id
        with patch.object(server,"monitor",m),patch.object(server,"_is_standalone_mode",return_value=True),patch.object(server,"_ingest_token_ok",return_value=True):
            response=server.api_ingest(SimpleNamespace(headers={}),{"items":[{"kind":"event","type":"batch_failed","data":data}]})
        assert json.loads(response.body)["accepted"]==accepted
        assert (m.batch_failure is not None)==bool(accepted)
    # A copied hash or path is insufficient: the server reconstructs the actual producer binding.
    tampered=deepcopy(data);tampered["manifest_ref"]["sha256"]="0"*64
    assert server._verified_failed_runner_binding(tampered) is False


def test_core_ingest_is_accepted_without_fabricating_exit_receipt(failure_files):
    m=ready_monitor(failure_files);data=core_notice(failure_files)
    with patch.object(server,"monitor",m),patch.object(server,"_is_standalone_mode",return_value=True),patch.object(server,"_ingest_token_ok",return_value=True):
        response=server.api_ingest(SimpleNamespace(headers={}),{"items":[{"kind":"event","type":"batch_failed","data":data}]})
    assert json.loads(response.body)["accepted"]==1
    assert m.batch_failure["receipt_ref"] is None and m.batch_failure["process_exited"] is False


def test_paired_planned_run_id_rejects_consistent_foreign_manifest_claim_and_argument(failure_files):
    manifest,receipt,plan,claim=failure_files
    run_id=json.loads(manifest.read_bytes())["run_id"]
    planned=json.loads(plan.read_bytes())
    planned["planned_runs"][0]["batch_completion_contract"]={"planned_run_id":run_id}
    put(plan,planned);r=json.loads(receipt.read_bytes());r["plan_sha256"]=digest(plan);put(receipt,r)
    assert item_for(failure_files)["data"]["run_id"]==run_id
    foreign="foreign-consistent-run"
    for path in (manifest,claim):
        row=json.loads(path.read_bytes());row["run_id"]=foreign;put(path,row)
    with pytest.raises(ValueError,match="planned run ID"):
        attach._failure_item(manifest,receipt,expected_run_id=foreign)


def stored_core_manifest(files):
    data=core_notice(files);manifest=json.loads(files[0].read_bytes())
    manifest.update(data["manifest_counts"])
    manifest.update(batch_status="FAILED",terminal_status="FAILED",large_run_complete=False,
                    terminal_artifacts_finalized=False,batch_failure=data)
    return manifest


def test_stored_core_failure_snapshot_restores_same_run_scope_counts_and_time(failure_files):
    value=stored_core_manifest(failure_files);before=deepcopy(value)
    snap=attach._snapshot(value,started_at=1.0,summary_limit=5,start_time_source="LEGACY_INFERRED_OR_ATTACH_TIME")
    assert snap["batch_status"]=="FAILED" and snap["batch_running"] is False
    assert snap["batch_start_time"]==value["batch_failure"]["started_at_epoch"]
    assert snap["batch_start_time_source"]=="CORE_EPOCH"
    assert snap["done_count"]==value["completed_count"]==0 and snap["total_posts"]==24
    restored=MonitorState();assert restored.load_status_snapshot(snap) is True
    assert restored.publication_scope_id==value["publication_scope_id"]
    assert restored.batch_failure["process_exited"] is False and not restored.active_posts
    # The normal --manifest --once route sends only this snapshot and requires its ACK.
    put(failure_files[0],value)
    args=["attach","--manifest",str(failure_files[0]),"--once"]
    for accepted,expected in [(1,0),(0,2)]:
        with patch.object(sys,"argv",args),patch.object(attach,"_post_items",return_value={"accepted":accepted}) as post:
            assert attach.main()==expected
        assert len(post.call_args.args[1])==1
        assert post.call_args.args[1][0]["kind"]=="status_snapshot"
        assert post.call_args.args[1][0]["data"]["batch_failure"]["process_exited"] is False
    with patch.object(sys,"argv",args),patch.object(attach,"_post_items",side_effect=OSError("offline")):
        assert attach.main()==2
    assert value==before


def test_stored_failure_mismatch_or_bare_failed_marker_never_projects_running(failure_files):
    original=stored_core_manifest(failure_files)
    for fault in ("run","output","scope_null","scope_other","count","time","complete","missing_payload"):
        value=deepcopy(original);failure=value["batch_failure"]
        if fault=="run":failure["run_id"]="other"
        elif fault=="output":failure["output_file"]+=".other"
        elif fault=="scope_null":failure["publication_scope_id"]=None
        elif fault=="scope_other":failure["publication_scope_id"]="b"*64
        elif fault=="count":failure["manifest_counts"]["flushed_count"]=1
        elif fault=="time":failure["ended_at_epoch"]=1
        elif fault=="complete":value["large_run_complete"]=True
        elif fault=="missing_payload":value.pop("batch_failure")
        with pytest.raises(ValueError):attach._snapshot(value,started_at=1,summary_limit=5)
        put(failure_files[0],value)
        with patch.object(sys,"argv",["attach","--manifest",str(failure_files[0]),"--once"]),patch.object(attach,"_post_items") as post:
            assert attach.main()==2
        post.assert_not_called()
