const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../src/llm_batch/monitor/static/index.html'), 'utf8');
// 실제 HTML의 함수 본문을 사용한다. 별도 복제 renderer로 성공을 만들지 않는다.
const code = html.slice(html.indexOf('function batchStatePresentation(s) {'), html.indexOf('function updatePipeline('));
assert.ok(code.includes('function updateStatus(s) {'));
function harness() {
  const nodes = new Map();
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, {textContent: '', innerHTML: '', hidden: true, style: {}, dataset: {},
      classList: {toggle(){},remove(){},add(){}}, setAttribute(){}, querySelector(){return null;}});
    return nodes.get(id);
  }
  const sandbox = { document: {getElementById: node, querySelector: node, querySelectorAll: () => [1,2]},
    lastKnownStatus: {}, activeWorkers: new Map([[9, {title: 'ghost'}]]),
    liveTotalResults: 1, parallelCount: 12, sseRestorePending: false, lastEventTime: Date.now(),
    workerLogs: new Map(), flowLog: [], renderNativeProgress(){},setLlmSuspendState(){},resetPipelineSteps(){},
    renderWorkerCards(){}, liveFilterActive(){return false;}, updateLivePager(){}, toggleParallelUI(){},
    updateLogTabStyles(){},addFlowEntry(){},updatePipeline(){},fmtTime: n=>String(n),fmtNum: n=>String(n),
    WORKER_TAB_COLORS: [], Date, Map, Set };
  vm.createContext(sandbox); vm.runInContext(code, sandbox);
  return {s:sandbox,node};
}
function failureStatus() {
  return {batch_status: 'FAILED', batch_running: false, run_id:'r5-test', output_file:'before.json',
    total_posts:24,done_count:1,progress_pct:4.2,parallel_count:12,active_posts:{99:{title:'stale'}},
    elapsed_sec:324,eta_sec:0,avg_sec_per_post:324,
    batch_failure:{schema_version:'dashboard_run_failure_v1',run_id:'r5-test',reason_code:'CHILD_EXIT_NONZERO',
      message:'child exit 1 <img src=x>',manifest_counts:{input_post_count:24,flushed_count:0}}};
}
test('실패는 완료로 표시하지 않고 저장 분모와 실측 미완료를 보여 준다',()=>{
  const {s,node}=harness();s.updateStatus(failureStatus());
  assert.equal(node('.progress-card').dataset.state,'failed');
  assert.equal(node('batch-status-text').textContent,'배치 실패 · 실측 미완료');
  assert.equal(node('progress-text').textContent,'1 / 24');
  assert.match(node('batch-failure-detail').textContent,/저장 0 \/ 24/);
  assert.match(node('batch-failure-detail').textContent,/child exit 1 <img src=x>/);
  assert.equal(node('batch-failure-detail').innerHTML,'');
  assert.equal(node('batch-failure-detail').hidden,false);
  assert.equal(node('elapsed-text').textContent,'경과: 324');
  assert.equal(node('eta-text').textContent,'ETA: -');
  const inferred=failureStatus();inferred.batch_start_time_source='LEGACY_INFERRED_OR_ATTACH_TIME';
  s.updateStatus(inferred);assert.match(node('elapsed-text').textContent,/시각 추정/);
});
test('SSE 활동이 최근이어도 실패 폴링은 ghost를 지우고 stale active_posts를 복원하지 않는다',()=>{
  const {s,node}=harness();s.updateStatus(failureStatus());
  assert.equal(s.activeWorkers.size,0);
  assert.equal(node('current-post-label').textContent,'실행 중단 · 최종 저장 미완료');
  s.updateStatus(failureStatus());assert.equal(s.activeWorkers.size,0);
});
test('실패 뒤 새 정상 상태는 배너를 숨기고 기존 성공·실행·대기를 유지한다',()=>{
  const {s,node}=harness();s.updateStatus(failureStatus());
  for(const [status,running,done,label] of [
    ['RUNNING',true,0,'배치 실행 중'],['COMPLETED',false,24,'배치 완료'],
    ['INCOMPLETE',false,1,'배치 미완료'],['IDLE',false,0,'배치 대기 중']]){
    s.updateStatus({batch_status:status,batch_running:running,done_count:done,total_posts:24,parallel_count:1});
    assert.equal(node('batch-status-text').textContent,label);
    assert.equal(node('batch-failure-detail').hidden,true);
  }
  assert.equal(s.batchStatePresentation({batch_running:false,done_count:2}).state,'complete');
  assert.equal(s.batchStatePresentation({batch_running:true,llm_suspended:true}).state,'suspended');
});
test('실패 이벤트는 batch_complete를 위조하지 않고 실제 상태를 다시 읽는다',()=>{
  const section=html.slice(html.indexOf("    case 'batch_failed':"),html.indexOf("    case 'batch_complete':"));
  assert.ok(section.includes("fetch('/api/status')"));
  assert.ok(section.includes('activeWorkers.clear()'));
  assert.ok(!section.includes('배치 완료'));
});

test('core의 drain 완료는 실제 프로세스 exit 관측으로 표시하지 않는다',()=>{
  const {s,node}=harness();const status=failureStatus();
  Object.assign(status.batch_failure,{failure_origin:'CORE_EXCEPTION',reason_code:'CORE_EXCEPTION',
    exit_code:null,process_exited:false,shutdown_status:'DRAINED',message:'원래 실패'});
  s.updateStatus(status);
  assert.equal(node('batch-status-text').textContent,'배치 중단 · 프로세스 종료 미확인 · 실측 미완료');
  assert.ok(!node('batch-failure-detail').textContent.includes('exit 0'));
  assert.equal(s.activeWorkers.size,0);
});
