const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const html = fs.readFileSync(process.env.DASHBOARD_HTML || path.join(__dirname, '../src/llm_batch/monitor/static/index.html'), 'utf8');
function actual(name) {
  const marker = html.includes(`async function ${name}(`) ? `async function ${name}(` : `function ${name}(`;
  const start = html.indexOf(marker);
  assert.ok(start >= 0, name);
  const end = html.indexOf('\n}', start);
  assert.ok(end > start, name);
  return html.slice(start, end + 2);
}
function harness(fetchImpl) {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {textContent:'',innerHTML:'',classList:{remove(){},add(){},toggle(){}}});
    return nodes.get(id);
  };
  const s = {document:{getElementById:node}, parallelCount:1, activeWorkers:new Map([[50,{}]]),
    doneSteps:new Set(['old']),recallCounts:{old:1},workerLogs:new Map([[-1,['old']]]),currentLogWorker:-1,
    liveResultPage:[{post_id:50}],liveCurrentPage:0,liveTotalResults:1,livePageLoading:false,
    liveResultGeneration:0,_livePendingReloadPage:null,liveInitialPageLoaded:true,livePendingRestoreItems:[{post_id:50}],
    liveCachedSnapshot:{items:[{post_id:50}],total:1,page:0},_cacheSaveResultsLastTs:Date.now(),
    liveSearchQuery:'',liveRelevanceFilter:'all',LIVE_PAGE_SIZE:100,slangDbLoaded:true,WORKER_TAB_COLORS:['blue'],
    currentTab:'live',rendered:[],cacheWrites:[],statuses:[],
    renderNativeProgress(){},setLlmSuspendState(){},resetPipelineSteps(){},clearFlowLog(){},toggleParallelUI(){},
    renderWorkerCards(){},renderLiveResults(){s.rendered.push(s.liveResultPage.map(r=>r.post_id));},
    _cacheSaveResults(){s.cacheWrites.push(s.liveResultPage.map(r=>r.post_id));},
    updateStatus(status){s.statuses.push(status);},Date,Map,Set,URLSearchParams,console,
    fetch:fetchImpl || (()=>Promise.resolve({json:()=>Promise.resolve({batch_status:'FAILED',done_count:0})}))};
  vm.createContext(s);
  vm.runInContext(['handleEvent','loadLiveResults','_restoreLiveResultsFromCache'].map(actual).join('\n'),s);
  return s;
}
function prepare(s) {s.handleEvent({type:'batch_prepare',data:{run_id:'new-failed',parallel_count:1,total:1}});}
test('old50 → prepare → failed에서 결과 행·복원 캐시·누계를 지운다',async()=>{
  const s=harness();prepare(s);
  assert.equal(s.liveResultPage.length,0);assert.equal(s.liveTotalResults,0);
  assert.equal(s.livePendingRestoreItems.length,0);assert.equal(s.liveCachedSnapshot.items.length,0);
  assert.equal(s._cacheSaveResultsLastTs,0);assert.equal(s.activeWorkers.size,0);
  assert.equal(s.rendered.at(-1).length,0);assert.equal(s.cacheWrites.at(-1).length,0);
  assert.equal(s._restoreLiveResultsFromCache(),false);
  s.handleEvent({type:'batch_failed',data:{run_id:'new-failed'}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(s.statuses.at(-1).batch_status,'FAILED');assert.equal(s.liveResultPage.length,0);
});
test('이전 실행의 지연 results 응답은 새 실패 표에 다시 삽입하지 않는다',async()=>{
  let resolve;const s=harness(()=>new Promise(r=>{resolve=r;}));
  const pending=s.loadLiveResults(0);prepare(s);
  resolve({json:async()=>({items:[{post_id:50}],total:1})});await pending;
  assert.equal(s.liveResultPage.length,0);assert.equal(s.liveTotalResults,0);
  assert.equal(s.livePageLoading,false);assert.equal(s.liveInitialPageLoaded,false);
});
test('이전 요청의 실패도 과거 캐시를 재복원하지 않는다',async()=>{
  let reject;const s=harness(()=>new Promise((_,r)=>{reject=r;}));
  const pending=s.loadLiveResults(0);prepare(s);reject(new Error('old request'));await pending;
  assert.equal(s.liveResultPage.length,0);assert.equal(s.liveTotalResults,0);
  assert.equal(s._restoreLiveResultsFromCache(),false);
});
test('새 실행 응답과 기존 batch_start 초기화는 유지한다',async()=>{
  const s=harness(()=>Promise.resolve({json:async()=>({items:[{post_id:51}],total:1})}));
  prepare(s);await s.loadLiveResults(0);
  assert.equal(s.liveResultPage[0].post_id,51);assert.equal(s.liveTotalResults,1);
  s.handleEvent({type:'batch_start',data:{parallel_count:1}});
  assert.equal(s.liveResultPage.length,0);assert.equal(s.liveTotalResults,0);
});

