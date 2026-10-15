const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const ui = require('../src/llm_batch/monitor/static/presentation.js');

function nativeViewFixture(guard = 'PUBLISH') {
  const sha = 'a'.repeat(64), scope = 'b'.repeat(64);
  const flags = {public_apply: false, publication_authority: false, central_db_write: false,
    actual_quality_evaluated: false, formal_kpi_status: 'NOT_ESTIMABLE'};
  const provider = {execution_status: 'PROVIDER_EVIDENCE_STORED', guard_status: 'GUARD_NOT_EVALUATED',
    client_http_invocations: 1, actual_external_call_count: 0, data_kind: 'TEST_SYNTHETIC', report_sha256: sha};
  const native = {...flags, status: 'COMPLETED_NATIVE_IO', guard_status: guard, publication_scope_id: scope,
    data_kind: 'TEST_SYNTHETIC', transport_mode: 'TEST_DOUBLE', client_http_invocations: 5,
    actual_external_call_count: 0, remote_dispatch_count: null, remote_dispatch_status: 'UNKNOWN',
    receipt_sha256: sha, native_counts_complete: true, price: null,
    time_scope: 'THROUGH_TERMINAL_DURABLE_READBACK', finalization_write_in_time_scope: false};
  const states = ['COMPLETED_NATIVE_IO', 'PROVIDER_EVIDENCE_STORED', 'NOT_EXECUTED', 'SKIPPED', 'INCOMPLETE'];
  const rows = states.map((state, i) => ({...flags, input_index: i + 1, post_id: i === 1 ? '101' : 101 + i,
    execution_status: state, capture_status: i < 2 ? 'CAPTURED' : 'NOT_ADMITTED', reason_codes: [],
    result_sha256: sha, provider: i < 2 ? {...provider} : null, native: i === 0 ? native : null,
    provider_report_ref: i < 2 ? {path: 'provider.json', sha256: sha, bytes: 128} : null,
    native_receipt_ref: i === 0 ? {path: 'native.json', sha256: sha, bytes: 256} : null}));
  const counts = Object.fromEntries([...states, 'NOT_AVAILABLE', 'ERROR'].map(state => [state, states.includes(state) ? 1 : 0]));
  const aggregate = {...flags, schema_version: 'recovery_native_dashboard_aggregate_v1', aggregate_sha256: sha,
    batch: null, batch_report_ref: null,
    base_run: {run_id: 'native-current', publication_scope_id: sha, policy_sha256: sha, input_count: rows.length},
    rows, counts: {input_count: rows.length, states: counts, client_http_invocations: null,
      actual_external_call_count: null, remote_dispatch_count: null, remote_dispatch_status: 'UNKNOWN'}};
  return {view: {binding_status: 'BOUND', verification_scope: 'FILE_AND_BASE_BINDING_ONLY', reason_codes: [],
    aggregate, row: rows[0]}, context: {post_id: 101, recovery_native_export_manifest: {binding_status: 'BOUND',
      summary: {run_id: 'native-current', publication_scope_id: sha, input_post_count: rows.length}}, run_manifest: {binding_status: 'BOUND',
      summary: {run_id: 'native-current', publication_scope_id: sha}}}};
}

test('native 별도 guard는 원래 provider 미평가와 전체 입력 분모를 함께 표시한다', () => {
  for (const guard of ['PUBLISH', 'HOLD']) {
    const {view, context} = nativeViewFixture(guard), before = JSON.stringify(view);
    const html = ui.renderRunContext({...context, recovery_native_execution: view});
    for (const text of ['R6 native 복구', 'GUARD_NOT_EVALUATED', 'FILE_AND_BASE_BINDING_ONLY',
      'TEST_DOUBLE', 'TEST_SYNTHETIC', 'NOT_EXECUTED', 'SKIPPED', 'INCOMPLETE', 'NOT_ESTIMABLE',
      '원래 공개 결과를 변경하지 않습니다', '합성 HTTP mock 기록']) assert.ok(html.includes(text), text);
    assert.match(html, new RegExp('별도 native guard 판정</div><div class="value">' + guard + '<'));
    assert.match(html, /전체 입력 수<\/div><div class="value">5</);
    assert.match(html, /native 포함 client 호출 수<\/div><div class="value">5</);
    assert.match(html, /native 포함 실제 외부 호출 수<\/div><div class="value">0</);
    assert.match(html, /client HTTP 누적 호출 수<\/div><div class="value">null · 산정값 없음/);
    assert.match(html, /최종 저장 시간 포함<\/div><div class="value">false</);
    assert.match(html, /공개 권한<\/div><div class="value">false</);
    assert.equal(JSON.stringify(view), before);
  }
});

test('native 미실행·provider only·부분 manifest는 정직하게 표시하고 완료로 승격하지 않는다', () => {
  const {view, context} = nativeViewFixture();
  context.run_manifest.binding_status = 'PARTIAL';
  for (const i of [1, 2, 3, 4]) {
    view.row = view.aggregate.rows[i]; context.post_id = view.row.post_id;
    const html = ui.renderRecoveryNative(view, context);
    assert.ok(html.includes(view.row.execution_status));
    assert.match(html, /별도 native guard 판정<\/div><div class="value">null · 산정값 없음/);
    assert.match(html, /기존 행의 run 메타데이터 일부는 미기록/);
    assert.doesNotMatch(html, /별도 native guard 판정<\/div><div class="value">PUBLISH</);
  }
  for (const binding_status of ['MISSING', 'INVALID', 'NO_PLAN_PROVIDED']) {
    const html = ui.renderRecoveryNative({binding_status, verification_scope: 'FILE_AND_BASE_BINDING_ONLY'}, context);
    assert.ok(html.includes(binding_status)); assert.doesNotMatch(html, /별도 native guard 판정<\/div>/);
  }
});

test('native foreign run·typed ID·scope·카운터·권한 모순은 guard 표시를 막는다', () => {
  const edits = [x => {x.context.post_id = '101';}, x => {x.context.recovery_native_export_manifest.binding_status = 'MISMATCH';},
    x => {x.context.recovery_native_export_manifest.summary.run_id = 'foreign';}, x => {x.view.aggregate.base_run.publication_scope_id = 'bad';},
    x => {x.view.aggregate.rows[0].native.publication_scope_id = x.view.aggregate.base_run.publication_scope_id;},
    x => {x.view.aggregate.public_apply = true;}, x => {x.view.aggregate.rows[0].native.actual_external_call_count = 1;},
    x => {x.view.aggregate.rows[0].provider.guard_status = 'PUBLISH';}, x => {x.view.aggregate.rows[0].native.receipt_sha256 = null;},
    x => {x.view.aggregate.rows[0].input_index = true;}, x => {x.view.aggregate.counts.input_count = 4;},
    x => {x.view.aggregate.counts.client_http_invocations = 0;}, x => {x.view.aggregate.counts.states.SKIPPED = 0;},
    x => {x.view.aggregate.rows[2].native = x.view.aggregate.rows[0].native;}];
  for (const edit of edits) {
    const x = nativeViewFixture(); edit(x);
    const html = ui.renderRecoveryNative(x.view, x.context);
    assert.match(html, /결속이 맞지 않아 판정을 표시하지 않습니다/);
    assert.doesNotMatch(html, /별도 native guard 판정<\/div>/);
  }
});

test('native 참조·객체 사유의 HTML은 escape하고 임의 파일 링크를 만들지 않는다', () => {
  const {view, context} = nativeViewFixture();
  view.row.reason_codes = [{message: '<script>bad()</script>'}];
  view.row.native_receipt_ref.path = '<img src=x onerror=bad()>';
  const html = ui.renderRecoveryNative(view, context);
  assert.match(html, /&lt;script&gt;/); assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<script>|<img|<a\s|href=/);
});

test('WAL 재생 owner와 새 export 불일치는 유지하면서 native 전체 분모와 새 판정을 표시한다', () => {
  const {view, context} = nativeViewFixture();
  const newRow = view.aggregate.rows[0], replayRow = {...view.aggregate.rows[2], input_index: 1,
    reason_codes: ['BASE_PUBLICATION_REPLAY_NO_CAPTURE']};
  newRow.input_index = 2;
  view.aggregate.rows = [replayRow, newRow]; view.aggregate.base_run.input_count = 2;
  view.aggregate.counts = {...view.aggregate.counts, input_count: 2, client_http_invocations: 5,
    actual_external_call_count: 0, states: Object.fromEntries(Object.keys(view.aggregate.counts.states).map(s =>
      [s, ['COMPLETED_NATIVE_IO', 'NOT_EXECUTED'].includes(s) ? 1 : 0]))};
  context.recovery_native_export_manifest.summary.input_post_count = 2;
  context.run_manifest = {binding_status: 'MISMATCH', reason_codes: ['RUN_ID_MISMATCH'], summary: {}};
  const runContext = {...context}; delete runContext.post_id;
  const whole = ui.renderRecoveryNative(view, runContext);
  assert.match(whole, /전체 입력 수<\/div><div class="value">2</);
  assert.match(whole, /BASE_PUBLICATION_REPLAY_NO_CAPTURE/);
  assert.match(whole, /별도 native guard 판정<\/div><div class="value">PUBLISH</);
  assert.match(whole, /기본 manifest 결속<\/div><div class="value">MISMATCH</);
  assert.match(whole, /현재 export 파일 결속<\/div><div class="value">BOUND</);
  view.row = replayRow; context.post_id = replayRow.post_id; context.run_meta = {run_id: 'prior-wal-owner'};
  const replay = ui.renderRecoveryNative(view, context);
  assert.match(replay, /prior-wal-owner/); assert.match(replay, /native-current/);
  assert.match(replay, /별도 native guard 판정<\/div><div class="value">null · 산정값 없음/);
  assert.doesNotMatch(replay, /별도 native guard 판정<\/div><div class="value">PUBLISH</);
  context.recovery_native_export_manifest.summary.publication_scope_id = 'c'.repeat(64);
  assert.match(ui.renderRecoveryNative(view, context), /결속이 맞지 않아 판정을 표시하지 않습니다/);
});

test('불완전 native 영수증이 없으면 알려진 provider 호출을 전체 합계로 대체하지 않는다', () => {
  const {view, context} = nativeViewFixture();
  const row = view.aggregate.rows[4]; row.provider = {...view.aggregate.rows[1].provider};
  view.row = row; context.post_id = row.post_id;
  const html = ui.renderRecoveryNative(view, context);
  assert.match(html, /provider만의 client 호출 수<\/div><div class="value">1</);
  assert.match(html, /client HTTP 누적 호출 수<\/div><div class="value">null · 산정값 없음/);
  assert.match(html, /실제 외부 누적 호출 수<\/div><div class="value">null · 산정값 없음/);
  view.aggregate.counts.client_http_invocations = 7;
  assert.match(ui.renderRecoveryNative(view, context), /결속이 맞지 않아 판정을 표시하지 않습니다/);
});

test('native 행 성공과 마지막 batch 제어 실패를 별도로 표시하고 보고서 결속을 확인한다', () => {
  const {view, context} = nativeViewFixture(), a = view.aggregate, row = a.rows[0];
  a.rows = [row]; a.base_run.input_count = 1; context.recovery_native_export_manifest.summary.input_post_count = 1;
  a.counts = {...a.counts, input_count: 1, client_http_invocations: 5, actual_external_call_count: 0,
    states: Object.fromEntries(Object.keys(a.counts.states).map(s => [s, s === 'COMPLETED_NATIVE_IO' ? 1 : 0]))};
  a.batch_report_ref = {path: '<img src=x onerror=bad()>/batch.json', sha256: 'c'.repeat(64), bytes: 2048};
  a.batch = {schema_version: 'recovery_native_batch_summary_v1', status: 'INCOMPLETE',
    reason_codes: ['BATCH_TIME_EXHAUSTED'], data_kind: 'TEST_SYNTHETIC', receipt_sha256: 'd'.repeat(64),
    policy_sha256: a.base_run.policy_sha256, counts: {input_count: 1, NOT_EXECUTED: 0, RUNNING: 0,
      COMPLETED_NATIVE_IO: 1, INCOMPLETE: 0, client_http_invocations: 5, actual_external_calls: 0},
    budget: {reserved_rows: 1, reserved_calls: 10, reserved_response_bytes: 4096, reserved_elapsed_ms: 100,
      observed_elapsed_ms: 101, refunds: 0, time_scope: 'THROUGH_FINAL_DRAIN_CONTROL_OBSERVATION',
      report_publication_io_in_time_scope: false, total_ram_bytes: null},
    public_apply: false, publication_authority: false, central_db_write: false,
    actual_quality_evaluated: false, formal_kpi_status: 'NOT_ESTIMABLE'};
  const before = JSON.stringify(view), html = ui.renderRecoveryNative(view, context);
  assert.match(html, /batch 최종 제어 상태<\/div><div class="value">INCOMPLETE</);
  assert.match(html, /BATCH_TIME_EXHAUSTED/);
  assert.match(html, /별도 native guard 판정<\/div><div class="value">PUBLISH</);
  assert.match(html, /마지막 제어 검사까지 관측한 시간 ms<\/div><div class="value">101</);
  assert.match(html, /보고서 발행 시간 포함<\/div><div class="value">false</);
  assert.match(html, /예약량은 실제 사용량이 아닙니다/); assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img|href=/); assert.equal(JSON.stringify(view), before);
  for (const edit of [x => {x.batch_report_ref = null;}, x => {x.batch.policy_sha256 = 'b'.repeat(64);},
    x => {x.batch.status = 'COMPLETED';}, x => {x.batch.counts.input_count = 2;},
    x => {x.batch.budget.report_publication_io_in_time_scope = true;}]) {
    const copy = JSON.parse(before); edit(copy.aggregate);
    assert.match(ui.renderRecoveryNative(copy, context), /결속이 맞지 않아 판정을 표시하지 않습니다/);
  }
});

test('live native 상세가 비면 요약에 남은 이전 성공을 삭제한다', () => {
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  const script = html.match(/function mergeLiveDetail\(summary, detail\) \{[\s\S]*?\n\}/)[0];
  const context = vm.createContext({summary: {post_id: 101, recovery_native_execution: nativeViewFixture().view,
    recovery_native_export_manifest: nativeViewFixture().context.recovery_native_export_manifest}});
  vm.runInContext(script, context);
  vm.runInContext('absent = mergeLiveDetail(summary, {post_id: 101}); missing = mergeLiveDetail(summary, {post_id: 101, recovery_native_execution: {binding_status: "MISSING"}})', context);
  assert.equal(Object.hasOwn(context.absent, 'recovery_native_execution'), false);
  assert.equal(Object.hasOwn(context.absent, 'recovery_native_export_manifest'), false);
  assert.equal(context.missing.recovery_native_execution.binding_status, 'MISSING');
});

test('native 진행은 재접속·중복·역순을 처리하고 기본 분석 카운터를 건드리지 않는다', () => {
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  const panel = {textContent: ''}, context = vm.createContext({document: {getElementById: () => panel}});
  vm.runInContext(html.slice(html.indexOf('let lastNativeProgress = null;'), html.indexOf('// ─── Event Handlers')), context);
  const event = {schema_version: 'native_recovery_progress_v1', run_id: 'run', publication_scope_id: 'a'.repeat(64),
    policy_sha256: 'b'.repeat(64), sequence: 1, status: 'RUNNING', total: 3, processed: 1,
    completed: 0, not_executed: 1, incomplete: 0, aggregate_ref: null};
  context.value = event; assert.equal(vm.runInContext('renderNativeProgress(value)', context), true);
  const first = panel.textContent;
  for (const update of [{sequence: 0}, {sequence: 2, run_id: 'other'}, {sequence: 2, processed: 0},
    {sequence: 2, status: 'COMPLETED'}, {sequence: 2, policy_sha256: 'bad'}]) {
    context.value = {...event, ...update}; assert.equal(vm.runInContext('renderNativeProgress(value)', context), false);
    assert.equal(panel.textContent, first);
  }
  context.value = {...event, sequence: 2, status: 'COMPLETED', processed: 3, completed: 1, incomplete: 1,
    aggregate_ref: {path: 'view.json', sha256: 'c'.repeat(64), bytes: 100}};
  assert.equal(vm.runInContext('renderNativeProgress(value)', context), true);
  assert.match(panel.textContent, /3\/3 · COMPLETED/);
  context.value = {...event, sequence: 3}; assert.equal(vm.runInContext('renderNativeProgress(value)', context), false);
  vm.runInContext('renderNativeProgress(null, true)', context); assert.equal(panel.textContent, '');
  context.value = event; assert.equal(vm.runInContext('renderNativeProgress(value)', context), true);
});

test('실제 native HTTP mock→저장→live/history API 자료를 같은 renderer로 표시한다',
  {skip: !process.env.NATIVE_UI_READBACK}, () => {
    const payload = JSON.parse(fs.readFileSync(process.env.NATIVE_UI_READBACK, 'utf8'));
    const before = JSON.stringify(payload);
    assert.deepEqual(payload.live.recovery_native_execution, payload.history.recovery_native_execution);
    for (const context of [payload.live, payload.history]) {
      const view = context.recovery_native_execution;
      assert.equal(view.binding_status, 'BOUND');
      const rendered = ui.renderRecoveryNative(view, context);
      assert.match(rendered, /별도 native guard 판정<\/div><div class="value">(?:PUBLISH|HOLD)</);
      assert.match(rendered, /GUARD_NOT_EVALUATED/); assert.match(rendered, /TEST_DOUBLE/);
      assert.match(rendered, /native 포함 실제 외부 호출 수<\/div><div class="value">0</);
      assert.match(rendered, /원격 관측<\/div><div class="value">UNKNOWN</);
    }
    assert.equal(JSON.stringify(payload), before);
  });

function providerViewFixture() {
  const sha = 'a'.repeat(64), context = {post_id: 101, run_manifest: {binding_status: 'BOUND',
    summary: {run_id: 'provider-export', publication_scope_id: 'source-scope'}}};
  const view = {binding_status: 'BOUND', verification_scope: 'FILE_AND_BASE_BINDING_ONLY', reason_codes: [], report: {
    schema_version: 'recovery_provider_report_v1', verification_scope: 'SOURCE_JOURNAL_AND_RESPONSE_READBACK',
    execution_status: 'PROVIDER_EVIDENCE_STORED', guard_status: 'GUARD_NOT_EVALUATED',
    data_kind: 'TEST_SYNTHETIC', transport_mode: 'TEST_DOUBLE', actual_external_call_count: 0,
    client_http_invocations: 1, remote_provider_dispatch_count: null, remote_provider_dispatch_status: 'UNKNOWN',
    public_apply: false, publication_authority: false, central_db_write: false, formal_kpi_status: 'NOT_ESTIMABLE',
    plan_sha256: sha, report_sha256: sha, base: {post_id: 101, input_index: 1, export_run_id: 'provider-export',
      base_attempt_run_id: 'original-wal-owner', publication_scope_id: 'source-scope', input_count: 2},
    budget: {reservations_consumed: 1}, input_count: 2,
    input_rows: [{input_index: 1, post_id: 101, state: 'PROVIDER_EVIDENCE_STORED'},
      {input_index: 2, post_id: '202', state: 'NO_PLAN_PROVIDED'}],
    request_receipts: [{request_id: 'targeted-search-1', reservation_id: 'reservation-1', request_sha256: sha, status: 'SUCCESS',
      finalization_recorded: true, actual_external_call_count: 0, client_http_invocations: 1, observed_response_bytes: 90,
      response_ref: {path: 'responses/' + sha + '.bin', sha256: sha, bytes: 90},
      transport_ref: {path: 'responses/' + sha + '.json', sha256: sha, bytes: 1000}, transport_receipt_sha256: sha}],
  }};
  return {view, context};
}

test('provider 근거 수집과 공개 guard 미평가·원격 횟수 미확정을 구분한다', () => {
  const {view, context} = providerViewFixture(), before = JSON.stringify(view);
  const html = ui.renderRunContext({...context, recovery_provider_execution: view});
  for (const value of ['provider 응답 근거 저장', 'GUARD_NOT_EVALUATED', 'FILE_AND_BASE_BINDING_ONLY',
    'TEST_SYNTHETIC', 'TEST_DOUBLE', '합성 자료 또는 시험 전송 기록', 'UNKNOWN', 'NO_PLAN_PROVIDED',
    'original-wal-owner', 'provider-export', 'NOT_ESTIMABLE']) assert.ok(html.includes(value), value);
  assert.match(html, /client HTTP 호출 수<\/div><div class="value">1</);
  assert.match(html, /원격 내부 provider 호출 수<\/div><div class="value">null · 산정값 없음/);
  assert.match(html, /실제 외부 호출 수<\/div><div class="value">0</);
  assert.match(html, /공개 권한<\/div><div class="value">false</);
  assert.equal(JSON.stringify(view), before);
});

test('provider 미확정 발송의 null을 0회로 바꾸지 않는다', () => {
  const {view, context} = providerViewFixture(), report = view.report;
  report.transport_mode = 'HTTPX_SINGLE_REQUEST'; report.data_kind = 'SOURCE_BACKED';
  report.execution_status = 'INCOMPLETE_DISPATCH'; report.input_rows[0].state = 'INCOMPLETE_DISPATCH';
  report.actual_external_call_count = null; report.client_http_invocations = null;
  report.request_receipts[0] = {...report.request_receipts[0], status: 'INCOMPLETE_DISPATCH',
    finalization_recorded: false, response_ref: null, transport_ref: null, transport_receipt_sha256: null,
    observed_response_bytes: null, actual_external_call_count: null, client_http_invocations: null};
  const html = ui.renderRecoveryProvider(view, context);
  assert.match(html, /발송 여부·종결 미확정/);
  assert.match(html, /실제 외부 호출 수<\/div><div class="value">null · 산정값 없음/);
  assert.match(html, /client HTTP 호출 수<\/div><div class="value">null · 산정값 없음/);
  assert.doesNotMatch(html, /provider 응답 근거 저장/);
});

test('provider 현재 행·manifest·schema·권한 모순은 성공 표시를 만들지 않는다', () => {
  const edits = [x => {x.context.post_id = '101';}, x => {x.context.run_manifest.binding_status = 'MISMATCH';},
    x => {x.context.run_manifest.summary.run_id = 'original-wal-owner';},
    x => {x.context.run_manifest.summary.publication_scope_id = 'foreign';},
    x => {x.view.report.guard_status = 'APPROVED';}, x => {x.view.report.public_apply = true;},
    x => {x.view.report.publication_authority = true;}, x => {x.view.report.central_db_write = true;},
    x => {x.view.report.actual_external_call_count = false;}, x => {x.view.report.remote_provider_dispatch_count = 0;},
    x => {x.view.report.actual_external_call_count = 1;}, x => {x.view.report.report_sha256 = null;},
    x => {x.view.report.schema_version = 'recovery_execution_readback_v1';},
    x => {x.view.report.input_rows[0].state = 'NO_PLAN_PROVIDED';},
    x => {x.view.report.request_receipts[0].response_ref = null;},
    x => {x.view.report.request_receipts[0].finalization_recorded = false;}];
  for (const edit of edits) {
    const x = providerViewFixture(); edit(x);
    const html = ui.renderRecoveryProvider(x.view, x.context);
    assert.match(html, /실행 상태를 표시할 수 없습니다/);
    assert.doesNotMatch(html, /provider 응답 근거 저장|original-wal-owner/);
  }
  for (const binding_status of ['MISSING', 'INVALID', 'NO_PLAN_PROVIDED']) {
    const {view, context} = providerViewFixture(); view.binding_status = binding_status;
    const html = ui.renderRecoveryProvider(view, context);
    assert.doesNotMatch(html, /PROVIDER_EVIDENCE_STORED|targeted-search-1/);
  }
  assert.match(ui.renderRecoveryProvider(undefined), /provider 기록 미기록/);
});

test('provider 원시 응답을 표시하지 않고 유효한 요청 ID 문자열을 escape한다', () => {
  const {view, context} = providerViewFixture();
  view.report.request_receipts[0].request_id = '<img src=x onerror=bad()>';
  view.report.request_receipts[0].payload = {secret: 'RAW_RESPONSE_DO_NOT_RENDER'};
  const html = ui.renderRecoveryProvider(view, context);
  assert.match(html, /&lt;img/); assert.doesNotMatch(html, /<img |RAW_RESPONSE_DO_NOT_RENDER/);
});

test('provider 요청별 호출·bytes·참조와 상위 합계 모순을 거절한다', () => {
  const changes = [
    r => {r.client_http_invocations = 0;}, r => {r.actual_external_call_count = 1;},
    r => {r.transport_mode = 'NOT_STARTED';}, r => {r.input_count = 1;},
    r => {r.request_receipts[0].client_http_invocations = 0; r.client_http_invocations = 0;},
    r => {r.request_receipts[0].client_http_invocations = true;},
    r => {r.request_receipts[0].actual_external_call_count = 1;},
    r => {r.request_receipts[0].observed_response_bytes = 91;},
    r => {r.request_receipts[0].response_ref.bytes = 89;},
    r => {r.request_receipts[0].response_ref.path = 'responses/foreign.bin';},
    r => {r.request_receipts[0].response_ref.sha256 = 'bad';},
    r => {r.request_receipts[0].response_ref.extra = true;},
    r => {r.request_receipts[0].transport_ref = null;},
    r => {r.request_receipts[0].transport_ref.path = 'responses/' + 'b'.repeat(64) + '.json';},
    r => {r.request_receipts[0].transport_ref.bytes = false;},
    r => {r.request_receipts[0].transport_receipt_sha256 = null;},
    r => {r.request_receipts[0].request_sha256 = null;},
    r => {r.request_receipts[0].reservation_id = '';},
    r => {r.request_receipts[0].status = 'FAILED';},
    r => {r.request_receipts.push({...r.request_receipts[0]});},
  ];
  for (const change of changes) {
    const {view, context} = providerViewFixture(); change(view.report);
    const html = ui.renderRecoveryProvider(view, context);
    assert.match(html, /실행 상태를 표시할 수 없습니다/);
    assert.doesNotMatch(html, /provider 응답 근거 저장|targeted-search-1/);
  }
  const {view, context} = providerViewFixture();
  view.report.transport_mode = 'HTTPX_SINGLE_REQUEST'; view.report.data_kind = 'SOURCE_BACKED';
  view.report.actual_external_call_count = 1; view.report.request_receipts[0].actual_external_call_count = 1;
  assert.match(ui.renderRecoveryProvider(view, context), /provider 응답 근거 저장/);
  view.report.request_receipts[0].actual_external_call_count = 0;
  assert.doesNotMatch(ui.renderRecoveryProvider(view, context), /provider 응답 근거 저장/);
});

test('provider 미시작·실패·terminal 저장 후 미최종화 상태의 분모와 합계를 보존한다', () => {
  const make = status => {
    const x = providerViewFixture(); x.view.report.execution_status = status;
    x.view.report.input_rows[0].state = status; return x;
  };
  const waiting = make('NOT_STARTED');
  waiting.view.report.transport_mode = 'NOT_STARTED'; waiting.view.report.request_receipts = [];
  waiting.view.report.client_http_invocations = 0;
  assert.match(ui.renderRecoveryProvider(waiting.view, waiting.context), /NOT_STARTED · 미시작/);
  const failed = make('PROVIDER_REQUEST_FAILED');
  failed.view.report.request_receipts[0].status = 'HTTP_ERROR';
  assert.match(ui.renderRecoveryProvider(failed.view, failed.context), /provider 요청 실패/);
  const incomplete = make('INCOMPLETE_DISPATCH');
  incomplete.view.report.request_receipts[0].status = 'INCOMPLETE_DISPATCH';
  incomplete.view.report.request_receipts[0].finalization_recorded = false;
  const html = ui.renderRecoveryProvider(incomplete.view, incomplete.context);
  assert.match(html, /발송 여부·종결 미확정/); assert.match(html, /client HTTP 호출 수<\/div><div class="value">1</);
});

test('실제 provider workflow의 저장·판독 자료를 현재 행에 결속해 표시한다',
  {skip: !process.env.PROVIDER_UI_READBACK}, () => {
    const payload = JSON.parse(fs.readFileSync(process.env.PROVIDER_UI_READBACK, 'utf8'));
    const view = payload.bound, row = payload.row, base = view.report.base;
    assert.equal(view.binding_status, 'BOUND');
    assert.equal(view.report.execution_status, 'PROVIDER_EVIDENCE_STORED');
    const context = {...row, run_manifest: {binding_status: 'BOUND', summary: {
      run_id: base.export_run_id, publication_scope_id: base.publication_scope_id}}};
    const before = JSON.stringify(payload);
    const html = ui.renderRecoveryProvider(view, context);
    assert.match(html, /provider 응답 근거 저장/);
    assert.match(html, /GUARD_NOT_EVALUATED/); assert.match(html, /NO_PLAN_PROVIDED/);
    assert.match(html, /TEST_DOUBLE/); assert.match(html, /원격 내부 호출 관측<\/div><div class="value">UNKNOWN</);
    assert.match(html, /client HTTP 호출 수<\/div><div class="value">1</);
    assert.match(html, /실제 외부 호출 수<\/div><div class="value">0</);
    assert.match(ui.renderRunContext({...context, recovery_provider_execution: view}), /provider 응답 근거 저장/);
    assert.equal(JSON.stringify(payload), before);
  });

test('live 상세 응답에 provider 기록이 없으면 이전 요약의 성공을 재사용하지 않는다', () => {
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  const match = html.match(/function mergeLiveDetail\(summary, detail\) \{[\s\S]*?\n\}/);
  assert.ok(match);
  const context = vm.createContext({});
  vm.runInContext(match[0], context);
  const old = providerViewFixture().view;
  context.summary = {post_id: 101, recovery_provider_execution: old};
  vm.runInContext('absent = mergeLiveDetail(summary, {post_id: 101}); missing = mergeLiveDetail(summary, {post_id: 101, recovery_provider_execution: {binding_status: "MISSING"}})', context);
  assert.equal(Object.hasOwn(context.absent, 'recovery_provider_execution'), false);
  assert.equal(context.missing.recovery_provider_execution.binding_status, 'MISSING');
});

function generalInferenceFixture() {
  const digest = 'a'.repeat(64), flags = {publication_authority: false, public_apply: false, central_db_write: false, action_applied: false};
  const shared = {mode: 'SHADOW', post_id: 99001, graph_sha256: digest, capture_sha256: digest,
    bundle_sha256: digest, input_snapshot_sha256: digest, ...flags,
    binding: {run_id: 'run-new', input_index: 2, post_id: 99001, attempt_id: 'attempt-new', publication_scope_id: 'scope-new', scope: 'ATTEMPT_LOCAL_OBSERVATION'}};
  const pair = {value: {schema_version: 'candidate_reranker_inference_runtime_v1', ...shared,
    status: 'TEMPERATURE_APPLIED_BOUND_INFERENCE', score_replay_verified: true,
    verification_scope: 'CURRENT_SOURCE_R2_MODEL_REPLAY_AND_FITTED_TEMPERATURE',
    inference: {schema_version: 'candidate_inference_temperature_receipt_v1', mode: 'SHADOW', scope: 'GENERAL_INPUT_SHADOW',
      status: 'TEMPERATURE_APPLIED_BOUND_INFERENCE', post_id: 99001, probability_scope: 'BOUNDED_PINNED_R2_CORPUS',
      evaluation_split: null, truth_status: 'UNJUDGED_NOT_ASSIGNED', actual_quality_evaluated: false,
      graph_sha256: digest, capture_sha256: digest, model_sha256: digest, base_model_sha256: digest, scorer_sha256: digest,
      calibration_artifact_sha256: digest, raw_receipt_sha256: digest, policy_sha256: digest, ...flags,
      calibration_manifest_sha256: digest, training_split_manifest_sha256: digest,
      scorer_summary_sha256: digest, corpus_sha256: digest, temperature: 2,
      event_probabilities: [{label: 'r2-a', probability_mass: 0, probability_scale: 1000, probability: 0},
        {label: '__NIL__', probability_mass: 1000, probability_scale: 1000, probability: 1}],
      selected_label: '__NIL__', selected_error_probability: 0, nil_probability: 1, action: 'ASSERT_NIL'}},
    capture: {schema_version: 'candidate_inference_capture_ref_v1', ...shared, status: 'SAVED',
      artifact: {path: 'candidate_inference_captures/example.json', sha256: digest, bytes: 100}}};
  pair.context = {post_id: 99001, run_manifest: {binding_status: 'BOUND', summary: {
    run_id: 'run-new', publication_scope_id: 'scope-new', candidate_inference_policy: {
      schema_version: 'candidate_inference_policy_v1', mode: 'SHADOW', status: 'AVAILABLE',
      bundle_sha256: digest, corpus_sha256: digest, model_sha256: digest,
      calibration: JSON.parse(JSON.stringify(pair.value.inference))}}}};
  return pair;
}

test('실제 pipeline·저장·live/history API 판독 자료의 일반 입력 확률을 표시한다',
  {skip: !process.env.INFERENCE_UI_READBACK}, () => {
    const payload = JSON.parse(fs.readFileSync(process.env.INFERENCE_UI_READBACK, 'utf8'));
    for (const detail of [payload.live, payload.history]) {
      assert.equal(detail.run_manifest.binding_status, 'BOUND');
      const html = ui.renderCandidateInference(detail.run_meta.candidate_reranker_inference, detail.run_meta.candidate_inference_capture, detail);
      assert.match(html, /결속된 일반 입력 사건 확률/);
      assert.match(ui.renderRunContext(detail), /일반 입력 교정 정책/);
      assert.match(html, /UNJUDGED_NOT_ASSIGNED/);
    }
  });

test('일반 입력의 저장·모델 검산·행 결속을 함께 만족할 때만 확률을 표시한다', () => {
  const {value, capture, context} = generalInferenceFixture();
  const html = ui.renderCandidateInference(value, capture, context);
  assert.match(html, /결속된 일반 입력 사건 확률/);
  assert.match(html, /UNJUDGED_NOT_ASSIGNED/);
  assert.match(html, /FROZEN 평가 배정이나 실제 정확도 보증이 아닙니다/);
  assert.match(html, /SHADOW 선택 오류확률<\/div><div class="value">0</);
  assert.match(html, /공개 권한<\/div><div class="value">false</);
});

test('미실행·저장 실패·다른 행·부분 확률은 일반 입력 성공 표를 만들지 않는다', () => {
  const changes = [
    x => {x.value.status = 'NOT_EXECUTED';}, x => {x.capture.status = 'NOT_AVAILABLE';},
    x => {x.value.score_replay_verified = 'true';}, x => {x.capture.binding = {...x.capture.binding, attempt_id: 'stale'};},
    x => {x.capture.post_id = '99001';}, x => {x.value.inference.event_probabilities[0].probability_mass = 2;},
    x => {x.value.inference.event_probabilities = null;}, x => {x.value.inference.public_apply = true;},
    x => {x.value.inference.selected_error_probability = .5;}, x => {x.value.inference.model_sha256 = null;},
    x => {x.value.inference.evaluation_split = 'FROZEN_HOLDOUT';}, x => {x.capture.artifact = null;},
    x => {x.context.post_id = '99001';}, x => {x.context.run_manifest.summary.run_id = 'foreign';},
    x => {x.context.run_manifest.binding_status = 'MISMATCH';}, x => {x.value.inference.calibration_manifest_sha256 = null;},
    x => {x.value.inference.training_split_manifest_sha256 = null;}, x => {x.value.inference.scorer_summary_sha256 = null;},
    x => {x.value.inference.corpus_sha256 = null;}, x => {x.value.inference.temperature = 0;},
  ];
  for (const change of changes) {
    const x = generalInferenceFixture(); change(x);
    const html = ui.renderCandidateInference(x.value, x.capture, x.context);
    assert.doesNotMatch(html, /결속된 일반 입력 사건 확률/);
    assert.match(html, /확률 표시 조건을 충족하지 못했습니다/);
  }
  assert.match(ui.renderCandidateInference(null, null), /교정 관측이 저장되지 않았습니다/);
});

test('일반 입력 정책과 capture 경로는 HTML로 실행하지 않고 live·history 공용 표시를 사용한다', () => {
  const {value, capture, context} = generalInferenceFixture(); capture.artifact.path = '<img src=x onerror=alert(1)>';
  const html = ui.renderCandidateInference(value, capture, context);
  assert.doesNotMatch(html, /<img src=x/); assert.match(html, /&lt;img src=x/);
  const policy = ui.renderRunContext({run_manifest: {binding_status: 'BOUND', summary: {
    candidate_inference_policy: {mode: 'SHADOW', status: 'AVAILABLE', calibration: {temperature: 2}, actual_quality_evaluated: false}}}});
  assert.match(policy, /일반 입력 교정 정책/); assert.match(policy, /temperature/);
  const index = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  assert.match(index, /renderCandidateInference\(d\.run_meta\?\.candidate_reranker_inference, d\.run_meta\?\.candidate_inference_capture, d\)/);
});

function recoveryViewFixture() {
  return {binding_status: 'BOUND', verification_scope: 'FILE_AND_BASE_BINDING_ONLY', reason_codes: [], report: {
    schema_version: 'recovery_execution_readback_v1', verification_status: 'VERIFIED_LOCAL_CONTRACT',
    execution_status: 'COMPLETED_SIMULATION', execution_mode: 'LOCAL_SIMULATION_ONLY', data_kind: 'SYNTHETIC_CONTRACT_ONLY',
    actual_external_call_count: 0, tokens: null, price: null, formal_kpi_status: 'NOT_ESTIMABLE',
    public_apply: false, publication_authority: false, central_db_write: false,
    base: {input_index: 1, post_id: 42, base_attempt_run_id: 'base-attempt', publication_scope_id: 'base-scope'},
    plan_sha256: 'plan-fingerprint', binding_sha256: 'binding-fingerprint', report_sha256: 'report-fingerprint',
    journal: {event_count: 6, sha256: 'journal-fingerprint'}, input_count: 2, selected_base_count: 1, attempt_count: 1,
    consumed_simulated_dispatches: 1, consumed_action_count: 1, consumed_elapsed_ms: 12,
    pending_finalization_count: 0, open_call_count: 0,
    budget_observation_scope: 'THROUGH_ATTEMPT_TERMINAL_DURABLE_READBACK', finalization_persistence_in_budget: false,
    attempts: [{recovery_attempt_id: 'synthetic-attempt', recovery_session_id: 'synthetic-session',
      status: 'COMPLETED_SIMULATION', terminal_recorded: true, terminal_candidate_status: 'COMPLETED_SIMULATION',
      finalization_recorded: true, reason_codes: [], reserved_dispatches: 1, last_elapsed_ms: 12,
      candidate_output: {sha256: 'candidate-fingerprint'}, output: {sha256: 'output-fingerprint'}}],
    input_rows: [{input_index: 1, post_id: 42, plan_provided: true, state: 'COMPLETED_SIMULATION', attempt_count: 1},
      {input_index: 2, post_id: 43, plan_provided: false, state: 'NO_PLAN_PROVIDED', attempt_count: 0}],
    limitations: ['SYNTHETIC_CONTRACT_ONLY', 'ONE_EXPLICIT_PLAN', 'NO_ACTUAL_RECOVERY_QUALITY', 'NO_ACTUAL_PRICE_MEASUREMENT'],
  }};
}

test('현재 한 줄 사유를 구역과 항목으로 나누고 OCR·검색 참조를 보존한다', () => {
  const reason = "[판정 요약] - 판정: 관련 - discussion_type: review - 검색 요약: 2건 [엔진경고 1건] [원문 해석] - 제목: 작품 - 특별편 - 본문 요약: [이미지 OCR] 제목 [E001] [전문가별 판단] - Verifier: anchor=title_mention [미확정 사유] - 근거 부족 [후보 제목] - 후보 A [최종 종합] - 미확정 유지 [범위 분리] - is_novel_related=true - title_resolution_allowed=false";
  const sections = ui.parseReason(reason);
  assert.deepEqual(sections.map(s => s.title), ['판정 요약', '원문 해석', '전문가별 판단', '미확정 사유', '후보 제목', '최종 종합', '범위 분리']);
  assert.equal(sections[0].lines.length, 3);
  assert.equal(sections[1].lines[0], '- 제목: 작품 - 특별편');
  assert.ok(sections[1].lines[1].includes('[이미지 OCR] 제목 [E001]'));
  assert.equal(sections.at(-1).lines.length, 2);
  const html = ui.renderReason(reason);
  assert.match(html, /웹소설 관련 여부/);
  assert.match(html, />false</);
  assert.match(html, /판정 사유 원문 보기/);
});

test('알 수 없는 독립 구역과 구형 자유 서술 사유를 누락하지 않는다', () => {
  assert.deepEqual(ui.parseReason('자유 서술\r\n[새로운 점검]\r\n추가 근거').map(s => s.title), ['판정 설명', '새로운 점검']);
  assert.match(ui.renderReason('오래된 단일 문장 사유'), /오래된 단일 문장 사유/);
  assert.match(ui.renderReason(''), /저장된 판정 사유가 없습니다/);
});

test('현재 identity의 false·0·미확정 상태와 출처를 화면에 보존한다', () => {
  const data = { is_novel_related: true, title_resolution_allowed: false, search_health: { accepted: 0 }, search_evidence_catalog: [{ eid: 'E001', title: '작품', url: 'https://example.com/work', snippet: '<img src=x onerror=alert(1)>' }] };
  const original = JSON.stringify(data);
  const html = ui.renderIdentity(data);
  assert.match(html, /제목 확정 허용/);
  assert.match(html, />false</);
  assert.match(html, />0</);
  assert.match(html, /검색 근거 · 1건/);
  assert.ok(!html.includes('<img'));
  assert.equal(JSON.stringify(data), original);
  assert.equal(ui.safeLink('javascript:alert(1)', '출처'), '출처');
});

test('공식 URL 보류와 독립 검색 출처 링크를 순서에 관계없이 구분한다', () => {
  const heldUrl = 'https://example.com/novel/123';
  const unrelatedUrl = 'https://example.net/review';
  const evidence = [
    { eid: 'E001', title: '별칭 근거', purpose: 'alias_bridge_search', url: heldUrl },
    { eid: 'E002', title: '공식 후보 검토', purpose: 'official_title_verify', url: heldUrl },
    { eid: 'E003', title: '독립 감상', purpose: 'review', url: unrelatedUrl },
  ];
  for (const items of [evidence, [...evidence].reverse()]) {
    const identity = {
      search_evidence_catalog: items,
      publish_ledger: {
        candidate_preservation: { official_url: heldUrl },
        public_publish: { official_url: null },
      },
    };
    const before = JSON.stringify(identity);
    const html = ui.renderIdentity(identity);
    assert.equal((html.match(/href="https:\/\/example\.com\/novel\/123"/g) || []).length, 2);
    assert.equal((html.match(/검토 출처 · 공식 작품 URL 미확정/g) || []).length, 2);
    assert.match(html, /href="https:\/\/example\.net\/review"/);
    assert.equal(JSON.stringify(identity), before);

    identity.publish_ledger.public_publish.official_url = heldUrl;
    const published = ui.renderIdentity(identity);
    assert.equal((published.match(/href="https:\/\/example\.com\/novel\/123"/g) || []).length, 2);
    assert.doesNotMatch(published, /검토 출처 · 공식 작품 URL 미확정/);
  }
});

test('서로 다른 시간·워커 접두사와 새 단계를 인식한다', () => {
  const rows = ui.parseLogs([
    '[12:00:00.100|W0][🎭] Gatekeeper 분석 시작',
    '[12:00:01.100][W1] Critic 분석 시작',
    '[12:00:02.100|W0] [llm-stream] 토큰 생성',
    '[12:00:03.100|W1] ⚠️ 검색 실패',
    '[12:00:04.100|W0] VLM 이미지 처리',
    '[12:00:05.100|W0] ✅ Post 7 완료',
  ]);
  assert.equal(rows[2].stage, 'gatekeeper');
  assert.equal(rows[3].stage, 'critic');
  assert.equal(rows[3].category, 'warning');
  assert.equal(rows[4].stage, 'vlm');
  assert.equal(rows[5].category, 'result');
  assert.match(ui.renderLogs(rows), /반론 검토/);
});

test('여러 줄 JSON은 한 묶음으로 접고 문자열·큰 정수·원문은 보존한다', () => {
  const lines = ['[12:00:00|W0] Decoder 시작', '{', '  "id": 9007199254740993,', '  "value": ["괄호 } 와 \\"따옴표\\"", false, 1.00]', '}', '[12:00:01|W0] 완료'];
  // 유효한 이스케이프 문자열을 실제 JSON으로 구성한다.
  lines[3] = '  "value": ["괄호 } 와 \\"따옴표\\"", false, 1.00]'.replaceAll('\\\\', '\\');
  const records = ui.parseLogs(lines);
  assert.equal(records.length, 3);
  assert.equal(records[1].category, 'json');
  assert.equal(records[1].start, 2);
  assert.equal(records[1].end, 5);
  assert.match(records[1].pretty, /9007199254740993/);
  assert.match(records[1].pretty, /1\.00/);
  assert.deepEqual(records.flatMap(record => record.lines), lines);
  assert.match(ui.renderLogs(records), /JSON 응답/);
});

test('잘리거나 깨진 JSON 다음의 일반 로그와 원문 줄을 잃지 않는다', () => {
  for (const lines of [
    ['{', '  "incomplete": [', '[12:00:01|W1] ⚠️ 연결 실패'],
    ['{', 'invalid json', '}', '[12:00:01] 다음 단계'],
    ['[', '  1,', '  2'],
  ]) {
    const records = ui.parseLogs(lines);
    assert.deepEqual(records.flatMap(record => record.lines), lines);
    const rendered = ui.renderLogs(records);
    for (const line of lines) assert.ok(rendered.includes(line.replaceAll('"', '&quot;').replace(/^\[12:00:01(?:\|W1)?\] /, '')), line);
  }
});

test('접두사가 있는 JSON과 배열도 표시하고 HTML을 실행하지 않는다', () => {
  const records = ui.parseLogs(['[12:00:00|W0] {"text":"<script>evil()</script>","v":[0,false]}', '[1,2,3]']);
  assert.equal(records[0].category, 'json');
  assert.equal(records[1].category, 'json');
  assert.ok(!ui.renderLogs(records).includes('<script>'));
  assert.ok(!ui.renderReason('[판정 요약] - 제목: <script>evil()</script>').includes('<script>'));
});

test('완료 로그에 기록한 판정 사유는 구역별로 묶고 다음 결과 필드는 분리한다', () => {
  const lines = ['[12:00:00|W0]    reason: [판정 요약]', '[12:00:00|W0]            - 판정: 관련', '[12:00:00|W0]            [범위 분리]', '[12:00:00|W0]            - title_resolution_allowed=false', '[12:00:00|W0]    unanimous: True'];
  const records = ui.parseLogs(lines);
  assert.equal(records.length, 2);
  assert.equal(records[0].category, 'result');
  assert.equal(records[0].lines.length, 4);
  assert.deepEqual(records.flatMap(record => record.lines), lines);
  assert.match(ui.renderLogs(records), /판정 사유 · 4줄/);
  assert.match(ui.renderLogs(records), /제목 확정 허용/);
});

function logView(lines) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, { value: id === 'log-view-mode' ? 'pretty' : '', textContent: '', innerHTML: '', scrollTop: 0 });
    return elements.get(id);
  };
  const document = { getElementById: get, querySelectorAll: () => [] };
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  const start = html.indexOf('function renderLogLines()');
  const end = html.indexOf('function closeLogModal()', start);
  const context = vm.createContext({ document, DashboardPresentation: ui, _logRawLines: lines, _logRecords: [], _logParsedSource: null, _logFilter: 'all', _logPage: 0, LOG_PAGE_SIZE: 200 });
  vm.runInContext(html.slice(start, end), context);
  return { context, get, render: () => vm.runInContext('renderLogLines()', context) };
}

test('로그 종류 필터와 검색을 함께 적용하고 페이지·원문 전환도 유지한다', () => {
  const lines = Array.from({ length: 450 }, (_, i) => `[12:00:00|W0] ${i % 2 ? '[llm-stream]' : '검색'} 항목 ${i}`);
  const view = logView(lines);
  view.render();
  assert.equal(view.get('log-page-label').textContent, '1 / 3쪽');
  vm.runInContext('changeLogPage(1)', view.context);
  assert.equal(view.get('log-page-label').textContent, '2 / 3쪽');
  view.context._logFilter = 'llm';
  view.get('log-search').value = '항목 101';
  vm.runInContext('resetLogPage()', view.context);
  assert.equal(view.get('log-modal-count').textContent, '1 / 450줄');
  assert.ok(!view.get('log-modal-body').innerHTML.includes('항목 100'));
  view.get('log-view-mode').value = 'raw';
  view.render();
  assert.match(view.get('log-modal-body').innerHTML, /\[12:00:00\|W0\] \[llm-stream\] 항목 101/);
});

test('큰 JSON의 원문 페이지는 200줄로 제한하며 검색 결과가 없으면 빈 상태를 표시한다', () => {
  const lines = ['[', ...Array.from({ length: 800 }, (_, i) => `  ${i}${i < 799 ? ',' : ''}`), ']'];
  const view = logView(lines);
  view.get('log-view-mode').value = 'raw';
  view.render();
  assert.equal(view.get('log-page-label').textContent, '1 / 5쪽');
  assert.equal((view.get('log-modal-body').innerHTML.match(/class="log-record/g) || []).length, 200);
  view.get('log-search').value = '없는 문자열';
  view.render();
  assert.match(view.get('log-modal-body').innerHTML, /조건에 맞는 로그가 없습니다/);
  assert.equal(view.get('log-page-prev').disabled, true);
  assert.equal(view.get('log-page-next').disabled, true);
});

test('HTML 안의 전체 스크립트가 파싱된다', () => {
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  for (const [, script] of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(script);
});

test('사유와 메모를 동시에 보존하고 구형 notes-only·긴 메모도 분리한다', () => {
  const identity = { reason: '작품을 질문한다.', reason_lines: ['대체 사유는 선택하지 않음'] };
  const analysis = { notes: '작가의 반응을 분석한다. <script>bad()</script>' };
  const before = JSON.stringify({ identity, analysis });
  const html = ui.renderExplanation(identity, analysis);
  assert.match(html, /작품을 질문한다/);
  assert.match(html, /작가의 반응을 분석한다/);
  assert.match(html, /판정 사유/);
  assert.match(html, /분석 메모/);
  assert.doesNotMatch(html, /대체 사유는 선택하지 않음|<script>/);
  assert.equal(JSON.stringify({ identity, analysis }), before);
  const old = ui.renderExplanation({}, {}, '과거 메모');
  assert.match(old, /저장된 판정 사유가 없습니다/);
  assert.match(old, /과거 메모/);
  assert.match(ui.renderExplanation({ reason_lines: ['첫 줄', '다음 줄'] }, { notes: '가'.repeat(1001) }), /분석 메모 펼치기/);
});

test('NSFW false와 결측·문자열 false를 혼동하지 않는다', () => {
  assert.equal(ui.nsfwLabel(true), 'true · NSFW 해당');
  assert.equal(ui.nsfwLabel(false), 'false · NSFW 해당 없음');
  for (const value of [undefined, null]) assert.match(ui.nsfwLabel(value), /미기록/);
  for (const value of ['false', 'true', 0, 1, {}, []]) {
    assert.match(ui.nsfwLabel(value), /형식 불일치/);
    assert.doesNotMatch(ui.nsfwLabel(value), /해당 없음/);
  }
});

test('NSFW 평가 출처가 없는 구형 payload는 기존 저장값 표시를 유지한다', () => {
  for (const value of [undefined, null, true, false, 'false', 'true', 0, 1, {}, []]) {
    assert.equal(ui.nsfwLabel(value, undefined), ui.nsfwLabel(value));
    assert.equal(ui.nsfwLabel(value, null), ui.nsfwLabel(value));
  }
});

test('NSFW 미평가와 모델 보고·규칙 양성을 구분하고 저장값을 바꾸지 않는다', () => {
  const cases = [
    {is_nsfw: false, nsfw_assessment_status: 'NOT_EVALUATED', expected: '미평가 · NSFW 여부 미확인'},
    {is_nsfw: false, nsfw_assessment_status: 'MODEL_REPORTED', expected: 'false · NSFW 해당 없음 · 모델 보고값'},
    {is_nsfw: true, nsfw_assessment_status: 'MODEL_REPORTED', expected: 'true · NSFW 해당 · 모델 보고값'},
    {is_nsfw: true, nsfw_assessment_status: 'SOURCE_RULE_POSITIVE', expected: 'true · NSFW 해당 · 규칙 양성'},
  ];
  const before = JSON.stringify(cases);
  for (const row of cases) assert.equal(ui.nsfwLabel(row.is_nsfw, row.nsfw_assessment_status), row.expected);
  assert.equal(JSON.stringify(cases), before);
  assert.doesNotMatch(ui.nsfwLabel(false, 'NOT_EVALUATED'), /해당 없음/);
});

test('알 수 없거나 모순된 NSFW 평가 상태와 boolean 문자열은 미확인으로 남긴다', () => {
  for (const status of ['', 'model_reported', 'MODEL_REPORTED ', true, false, 0, 1, [], {}, '<img src=x onerror=bad()>']) {
    assert.equal(ui.nsfwLabel(false, status), '상태 미확인 · NSFW 여부 미확인');
    assert.doesNotMatch(ui.nsfwLabel(true, status), /NSFW 해당|<img/);
  }
  for (const status of ['NOT_EVALUATED', 'MODEL_REPORTED', 'SOURCE_RULE_POSITIVE']) {
    for (const value of [undefined, null, 'false', 'true', 0, 1, [], {}, '<script>bad()</script>']) {
      assert.equal(ui.nsfwLabel(value, status), '형식 불일치 · NSFW 여부 미확인');
      assert.doesNotMatch(ui.nsfwLabel(value, status), /NSFW 해당|<script>/);
    }
  }
  assert.equal(ui.nsfwLabel(true, 'NOT_EVALUATED'), '상태 불일치 · NSFW 여부 미확인');
  assert.equal(ui.nsfwLabel(false, 'SOURCE_RULE_POSITIVE'), '상태 불일치 · NSFW 여부 미확인');
  assert.equal(ui.nsfwLabel(false, {toString() { throw new Error('DO_NOT_COERCE_STATUS'); }}),
    '상태 미확인 · NSFW 여부 미확인');
});

function nsfwReasonDisplayCases() {
  return [
    [false, 'MODEL_REPORTED', 'MODEL_BOOLEAN_REPORTED', '모델이 NSFW 여부를 보고했습니다.'],
    [true, 'MODEL_REPORTED', 'MODEL_BOOLEAN_REPORTED', '모델이 NSFW 여부를 보고했습니다.'],
    [true, 'SOURCE_RULE_POSITIVE', 'SOURCE_TEXT_RULE_POSITIVE', '원문 텍스트가 NSFW 규칙에 해당합니다.'],
    [true, 'SOURCE_RULE_POSITIVE', 'SOURCE_IMAGE_RULE_POSITIVE', '원문 이미지의 관측 정보가 NSFW 규칙에 해당합니다.'],
    [false, 'NOT_EVALUATED', 'NOISE_EARLY_RETURN_NO_MODEL_ASSESSMENT', '작품 분석이 조기 종료되어 모델의 NSFW 평가는 수행되지 않았습니다.'],
    [false, 'NOT_EVALUATED', 'NOISE_OUTPUT_WITHOUT_MODEL_ASSESSMENT', '작품 분석에서 제외됐으며 모델의 NSFW 평가값은 없습니다.'],
    [false, 'NOT_EVALUATED', 'MODEL_ASSESSMENT_MISSING_OR_INVALID', '모델의 NSFW 평가값이 없거나 형식이 올바르지 않습니다.'],
  ];
}

test('NSFW 평가 이유 여섯 값은 bool·상태와 맞을 때 한국어로 표시한다', () => {
  const cases = nsfwReasonDisplayCases(), before = JSON.stringify(cases);
  for (const [value, status, reason, expected] of cases) {
    assert.equal(ui.nsfwReasonLabel(value, status, reason), expected);
    assert.doesNotMatch(expected, /픽셀 확인|정답|KPI|안전 확인/);
  }
  assert.equal(JSON.stringify(cases), before);
});

test('NSFW 이유의 구형 누락·unknown·HTML·객체를 성공이나 원문 코드로 표시하지 않는다', () => {
  for (const reason of [undefined, null]) assert.equal(ui.nsfwReasonLabel(false, undefined, reason), '평가 사유 미기록');
  for (const reason of ['', 'FUTURE_REASON', 'SOURCE_IMAGE_RULE_POSITIVE ', 'constructor', 'toString',
    '<img src=x onerror=bad()>', true, false, 0, 1, [], {},
    {toString() {throw new Error('DO_NOT_COERCE_REASON');}}]) {
    assert.equal(ui.nsfwReasonLabel(true, 'SOURCE_RULE_POSITIVE', reason), '평가 사유 미확인');
  }
});

test('NSFW 이유는 누락·잘못된 bool·서로 다른 상태를 조합해 평가 성공을 만들지 않는다', () => {
  for (const [value, status, reason] of nsfwReasonDisplayCases()) {
    for (const wrongValue of [undefined, null, 'true', 'false', 0, 1, {}, []]) {
      assert.equal(ui.nsfwReasonLabel(wrongValue, status, reason), '평가 사유와 저장 상태가 일치하지 않습니다.');
    }
    for (const wrongStatus of [undefined, null, '', 'FUTURE_STATUS', ...['MODEL_REPORTED', 'SOURCE_RULE_POSITIVE', 'NOT_EVALUATED'].filter(x => x !== status)]) {
      assert.equal(ui.nsfwReasonLabel(value, wrongStatus, reason), '평가 사유와 저장 상태가 일치하지 않습니다.');
    }
    if (status !== 'MODEL_REPORTED') assert.equal(ui.nsfwReasonLabel(!value, status, reason), '평가 사유와 저장 상태가 일치하지 않습니다.');
  }
});

test('이력은 opaque key와 명시 모드만 사용하며 경로 이름으로 actual을 추론하지 않는다', () => {
  const a = { run_key: 'run-a', filename: 'result.json', relative_path: 'actual/a/result.json', completion_status: 'PARTIAL', post_count: 3 };
  const b = { ...a, run_key: 'run-b', relative_path: 'replay/b/result.json', completion_status: 'FINAL', execution_mode: 'REPLAY' };
  assert.equal(ui.historyRunSummary(a).key, 'run-a');
  assert.match(ui.historyRunSummary(a).mode, /UNKNOWN/);
  assert.equal(ui.historyRunSummary(b).mode, 'REPLAY');
  assert.match(ui.renderHistoryRun(a), /부분 저장/);
  assert.match(ui.renderHistoryRun(b), /최종 저장/);
  assert.match(ui.renderHistoryRun({ ...a, artifact_kind: 'COMPLETED_SUBSET' }), /완료 행 부분집합/);
  const escaped = ui.renderHistoryRun({ ...a, run_key: "'><script>bad()</script>", relative_path: '<img src=x>' });
  assert.doesNotMatch(escaped, /<script>|<img|onclick=/);
});

test('완료 표시는 산출물 마감과 전체 행 성공을 함께 확인하고 0행도 보존한다', () => {
  const complete = {terminal_artifacts_finalized: true, input_post_count: 2, completed_count: 2,
    flushed_count: 2, pending_count: 0, failed_count: 0};
  const before = JSON.stringify(complete);
  assert.deepEqual(ui.runCompletionSummary(complete, 'RESULT'), {state: 'COMPLETED', label: '처리 완료'});
  const html = ui.renderRunContext({run_manifest: {binding_status: 'BOUND', artifact_kind: 'RESULT', summary: complete}});
  assert.match(html, /완료 상태<\/div><div class="value">처리 완료</);
  assert.match(html, /종료 산출물 확정<\/div><div class="value">true</);
  assert.match(html, /실패 기록 수<\/div><div class="value">0</);
  assert.match(html, /처리 완료는 의미 판정·품질·KPI 승인을 뜻하지 않습니다/);
  assert.equal(ui.runCompletionSummary({...complete, input_post_count: 0, completed_count: 0, flushed_count: 0}).state, 'COMPLETED');
  assert.equal(JSON.stringify(complete), before);
});

test('종료 확정이 있어도 실패·대기·누락 행·저장 수 불일치는 성공으로 표시하지 않는다', () => {
  const complete = {terminal_artifacts_finalized: true, input_post_count: 2, completed_count: 2,
    flushed_count: 2, pending_count: 0, failed_count: 0};
  for (const [change, state] of [[{failed_count: 1}, 'FAILURES_RECORDED'], [{pending_count: 1}, 'INCOMPLETE'],
      [{completed_count: 1, flushed_count: 1}, 'INCOMPLETE'], [{flushed_count: 1}, 'INCOMPLETE']]) {
    const summary = {...complete, ...change};
    assert.equal(ui.runCompletionSummary(summary).state, state);
    const html = ui.renderRunContext({run_manifest: {binding_status: 'BOUND', summary}});
    assert.doesNotMatch(html, /완료 상태<\/div><div class="value">처리 완료</);
  }
  assert.match(ui.runCompletionSummary({...complete, failed_count: 1, terminal_artifacts_finalized: false}).label, /실패 기록 있음.*종료 미확정/);
});

test('미기록·잘못된 타입·진행 기록은 실제 완료나 현재 프로세스 생존으로 승격하지 않는다', () => {
  const complete = {terminal_artifacts_finalized: true, input_post_count: 2, completed_count: 2, pending_count: 0, failed_count: 0};
  assert.match(ui.runCompletionSummary({}).label, /미기록/);
  assert.equal(ui.runCompletionSummary({terminal_artifacts_finalized: true}).state, 'UNKNOWN');
  assert.equal(ui.runCompletionSummary({...complete, failed_count: null}).state, 'UNKNOWN');
  assert.equal(ui.runCompletionSummary({...complete, terminal_artifacts_finalized: null}).state, 'UNKNOWN');
  for (const value of [true, false, '0', -1, {}, [], 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.match(ui.runCompletionSummary({...complete, failed_count: value}).label, /형식 불일치/);
  }
  for (const value of ['true', 1, {}, []])
    assert.match(ui.runCompletionSummary({...complete, terminal_artifacts_finalized: value}).label, /형식 불일치/);
  const progress = {...complete, terminal_artifacts_finalized: false, completed_count: 1};
  assert.equal(ui.runCompletionSummary(progress).state, 'IN_PROGRESS_RECORDED');
  const html = ui.renderRunContext({run_manifest: {binding_status: 'PARTIAL', summary: progress}});
  assert.match(html, /현재 프로세스 생존을 확인한 값이 아닙니다/);
  assert.doesNotMatch(ui.renderRunContext({run_manifest: {binding_status: 'MISMATCH', summary: {}}}), /완료 상태<\/div><div class="value">처리 완료</);
});

test('완료 행 부분집합은 전체 완료로 표시하지 않으며 원본의 과거 subset 생성과 구분한다', () => {
  const complete = {terminal_artifacts_finalized: true, input_post_count: 1, completed_count: 1,
    pending_count: 0, failed_count: 0, completed_subset_written: true, completed_subset_count: 1};
  assert.equal(ui.runCompletionSummary(complete, 'COMPLETED_SUBSET').state, 'PARTIAL');
  assert.equal(ui.runCompletionSummary({...complete, completed_subset_only: true}, 'RESULT').state, 'PARTIAL');
  assert.equal(ui.runCompletionSummary(complete, 'RESULT').state, 'COMPLETED');
  const html = ui.renderRunContext({run_manifest: {binding_status: 'BOUND', artifact_kind: 'COMPLETED_SUBSET', summary: complete}});
  assert.match(html, /부분 결과 · 전체 실행 완료 아님/);
});

test('이력 목록은 최종 저장과 실패 기록을 분리하고 상세와 같은 상태 해석을 사용한다', () => {
  const summary = {terminal_artifacts_finalized: true, input_post_count: 2, completed_count: 2, pending_count: 0, failed_count: 1};
  const run = {run_key: 'selected', completion_status: 'FINAL', artifact_kind: 'RESULT', manifest_summary: summary};
  assert.match(ui.renderHistoryRun(run), /최종 저장 · 실패 기록 있음 · 종료 확정/);
  const detail = {run_manifest: {binding_status: 'BOUND', artifact_kind: 'RESULT', summary}};
  assert.match(ui.renderRunContext(detail), /완료 상태<\/div><div class="value">실패 기록 있음 · 종료 확정</);
  assert.match(ui.renderHistoryRun({...run, manifest_summary: {}}), /최종 저장/);
});

test('원문 완료 상태는 임의 문자열을 신뢰하지 않고 대기 값을 남은 실행 행으로 부르지 않는다', () => {
  const summary = {terminal_artifacts_finalized: false, completed_count: 2, flushed_count: 1,
    input_post_count: 3, pending_count: 1, failed_count: 0, status: '<script>DONE</script>', completion_status: 'FINAL'};
  const before = JSON.stringify(summary);
  const html = ui.renderRunContext({run_manifest: {binding_status: 'BOUND', summary}});
  assert.match(html, /진행 중으로 기록됨/);
  assert.match(html, /저장 대기 수<\/div><div class="value">1</);
  assert.match(html, /처리 후 순서대로 저장하기를 기다리는 결과 수/);
  assert.doesNotMatch(html, /<script>/);
  assert.equal(JSON.stringify(summary), before);
});

test('이력 건수는 manifest 처리 결과와 실제 파일의 저장 결과를 구별한다', () => {
  const summary = {terminal_artifacts_finalized: false, input_post_count: 3, completed_count: 2,
    flushed_count: 1, pending_count: 1, failed_count: 0};
  const run = {run_key: 'progress', completion_status: 'PARTIAL', artifact_kind: 'RESULT',
    post_count_source: 'manifest', post_count: 2, manifest_summary: summary};
  const before = JSON.stringify(run);
  const list = ui.renderHistoryRun(run);
  assert.match(list, /처리 결과 2건/);
  assert.doesNotMatch(list, /저장(?:된 결과)? 2건/);
  const detail = ui.renderRunContext({run_manifest: {binding_status: 'BOUND', artifact_kind: 'RESULT', summary}});
  assert.match(detail, /처리 결과 수<\/div><div class="value">2</);
  assert.match(detail, /저장된 결과 수<\/div><div class="value">1</);
  assert.match(detail, /저장 대기 수<\/div><div class="value">1</);
  assert.match(ui.renderHistoryRun({...run, artifact_kind: 'COMPLETED_SUBSET'}), /완료 행 부분집합.*처리 결과 2건/);
  assert.match(ui.renderHistoryRun({run_key: 'legacy', post_count_source: 'result', post_count: 2}), /저장된 결과 2건/);
  assert.equal(JSON.stringify(run), before);
});

test('이력 건수의 출처·값 미기록과 null을 저장 0건으로 바꾸지 않는다', () => {
  for (const [source, label] of [['manifest', '처리 결과'], ['result', '저장된 결과'], ['unknown', '결과 수'], [null, '결과 수'], [undefined, '결과 수']]) {
    for (const [value, shown] of [[undefined, '미기록'], [null, 'null · 산정값 없음'], [0, '0']]) {
      const run = {run_key: 'count-only'};
      if (source !== undefined) run.post_count_source = source;
      if (value !== undefined) run.post_count = value;
      const before = JSON.stringify(run), html = ui.renderHistoryRun(run);
      assert.ok(html.includes(label + ' ' + shown + '건'), source + ':' + shown);
      if (value !== 0) assert.doesNotMatch(html, /(?:처리 결과|저장된 결과|결과 수) 0건/);
      assert.equal(JSON.stringify(run), before);
    }
  }
  assert.match(ui.renderHistoryRun({post_count: 2}), /결과 수 2건/);
});

test('행 PENDING·부분 trace와 manifest 연결32·NOT_ESTIMABLE을 따로 표시한다', () => {
  const data = {
    run_meta: {
      decision_call_attempt_receipt: { publication_link_status: 'PENDING_EXTERNAL_LEDGER_LINK' },
      decision_call_measurement: { mode: 'SHADOW', binding_status: 'UNBOUND', actual_kpi_eligible: false },
      decision_call_ledger_summary: {
        actual_kpi_status: 'PENDING_INDEPENDENT_READBACK', usage_status: 'COMPLETE_PROVIDER_REPORTED',
        derived_observation: { expert_calls: 16, prompt_tokens: 215335, completion_tokens: 11273, total_tokens: 226608 },
        actual_metrics: { expert_calls: null, total_tokens: null },
      },
      decision_cost_trace: { measurement_status: 'PARTIAL_AGGREGATE_NO_CALL_EVENTS', total_tokens: 111676 },
    },
    run_manifest: { binding_status: 'BOUND', summary: { run_id: 'r32', decision_call_ledger_summary: {
      actual_kpi_status: 'NOT_ESTIMABLE', measurement_binding_status: 'UNBOUND_PARTIAL',
      linked_row_attempt_count: 32, sealed_row_attempt_count: 32, open_call_count: 0,
      derived_observation: { total_tokens: 4328129 }, actual_metrics: { total_tokens: null },
    } } },
  };
  const before = JSON.stringify(data);
  const html = ui.renderRunContext(data);
  for (const text of ['행 저장 시점', '실행 manifest', 'PENDING_EXTERNAL_LEDGER_LINK', 'NOT_ESTIMABLE', 'UNBOUND_PARTIAL',
    '226608', '111676', '4328129', 'null · 산정값 없음', '연결 행', '>32<', '>0<']) assert.ok(html.includes(text), text);
  assert.equal(JSON.stringify(data), before);
  assert.match(ui.renderRunContext({}), /이 행에는 호출·측정 기록이 없습니다/);
});

test('유효 설정은 OFF·false·출처·실효 병렬을 보존한다', () => {
  const config = {
    schema_version: 'expert_execution_config_v1', profile: 'low-load', profile_source: 'CLI',
    settings: { vlm: { value: false, source: 'CLI' }, ocr: { value: true, source: 'ENV' },
      ledger_mode: { value: 'OFF', source: 'DEFAULT' }, context_diagnostics: { value: 'OFF', source: 'DEFAULT' } },
    requested_parallel: 1, effective_parallel: 1,
    source: { entry_point: 'C:/project/expert_main.py', entry_sha256: 'abc', runtime_source_sha256: 'def' },
    image_review: { ready: false, skip_reason_codes: ['VLM_DISABLED'] },
  };
  const html = ui.renderExecutionConfig(config);
  assert.match(html, /설정 출처/);
  assert.match(html, />false</);
  assert.match(html, />OFF</);
  assert.match(html, /1 \/ 1/);
  assert.match(html, /VLM_DISABLED/);
  assert.match(ui.executionSummary(config), /VLM false/);
  assert.match(ui.renderExecutionConfig(null), /유효 설정 기록이 없습니다/);
});

test('문맥 진단은 생산 필드와 원문 위치를 표시하고 미저장·OFF·TRUNCATED를 구분한다', () => {
  assert.match(ui.renderContextDiagnostics(undefined), /구조화 진단이 저장되지 않았습니다/);
  for (const status of ['OFF', 'NOT_AVAILABLE', 'TRUNCATED']) {
    assert.match(ui.renderContextDiagnostics({ status, publication_authority: false, reason_codes: ['LIMIT'] }), new RegExp(status));
  }
  const diagnostics = {
    status: 'STORED', publication_authority: false, max_bytes: 65536,
    projection: { speech_act: 'QUESTION', target_surface: '작품', work_roles: { primary: '후보A' } },
    channels: [{ field: 'analysis.notes', value: '<script>위험</script>', value_kind: 'SOURCE_BOUND', locations: [{ raw_path: 'comments[5]', raw_text_span: [0, 9] }] }],
    explanation: { supported: true, proofs: [{ claimant: '검미성', claim_kind: 'THIRD_PERSON', raw_path: 'comments[5]', sourcequote: '검미성이...' }] },
    ledgers: [{ source_id: 'comment:5', source_role: 'comment',
      evaluations: [{ event_id: 'e5', speaker: '댓글 화자', actor: '검미성', grammatical_subject: { text: '검미성이', explicit: true },
        objects: [{ text: 'ts녀', relation: 'OBJECT' }], evidence_text: '검미성이 ts녀를 사랑해서...' }],
      graph_edges: [{ source_id: 'e5', relation: 'ABOUT', target_id: 'ts녀' }] }],
  };
  const before = JSON.stringify(diagnostics);
  const html = ui.renderContextDiagnostics(diagnostics);
  assert.match(html, /검미성/);
  assert.match(html, /comments\[5\]/);
  assert.match(html, /문법상 주어/);
  assert.match(html, /댓글 화자/);
  assert.match(html, /대상과 관계/);
  assert.match(html, /공개 권한을 부여하지 않습니다/);
  assert.doesNotMatch(html, /<script>/);
  assert.equal(JSON.stringify(diagnostics), before);
});

function historyView(fetch) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, { textContent: '', innerHTML: '', classList: { add() {}, remove() {} } });
    return elements.get(id);
  };
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  const start = html.indexOf('async function loadHistoryDetail(');
  const end = html.indexOf('// ─── Helpers', start);
  const context = vm.createContext({
    document: { getElementById: get }, fetch, DashboardPresentation: ui, encodeURIComponent,
    historySelectionVersion: 0, historyModalVersion: 0, historyFileName: '', historyLogFileName: '',
    historyCurrentPage: 0, historyPageData: [], historyTotalResults: 0, historyRunItems: new Map(),
    HISTORY_PAGE_SIZE: 50, renderHistoryResults() {}, updateHistoryPager() {}, tailLogLinesForRender: x => x,
  });
  vm.runInContext(html.slice(start, end), context);
  return { context, get };
}

test('중첩 이력 선택은 opaque key를 인코딩하고 로그도 같은 key로 조회한다', async () => {
  const paths = [];
  const view = historyView(async url => {
    paths.push(url);
    return { ok: true, json: async () => url.includes('/log?')
      ? { lines: ['해당 실행 로그'], source: 'bound' }
      : { items: [{ post_id: 7 }], total: 1, stats: { relevant: 1, identified: 0, noise: 0 },
        run: { run_key: 'opaque key', filename: 'result.json', relative_path: 'nested/result.json', completion_status: 'FINAL' },
        run_manifest: { binding_status: 'BOUND', summary: {} } } };
  });
  await vm.runInContext("loadHistoryDetail('opaque key', 'unrelated.log')", view.context);
  assert.equal(paths[0], '/api/runs/opaque%20key?summary=1&offset=0&limit=50');
  assert.equal(paths[1], '/api/runs/opaque%20key/log?tail=500');
  assert.equal(view.get('history-detail-title').textContent, 'nested/result.json');
  assert.match(view.get('history-run-summary').textContent, /최종 저장.*UNKNOWN/);
  assert.match(view.get('history-log-area').innerHTML, /해당 실행 로그/);
});

test('늦게 도착한 이전 실행 응답이 새 실행이나 닫힌 이력을 덮어쓰지 않는다', async () => {
  let resolveOld;
  const old = new Promise(resolve => { resolveOld = resolve; });
  const response = id => ({ ok: true, json: async () => ({ items: [{ post_id: id }], total: 1, run: { filename: 'run' + id }, stats: {} }) });
  const view = historyView(url => url.includes('/old?') ? old
    : Promise.resolve(url.includes('/log?') ? { ok: false, json: async () => ({ error: 'missing' }) } : response(2)));
  const pending = vm.runInContext("loadHistoryDetail('old', '')", view.context);
  await vm.runInContext("loadHistoryDetail('new', '')", view.context);
  resolveOld(response(1));
  await pending;
  assert.equal(view.context.historyPageData[0].post_id, 2);
  assert.equal(view.get('history-detail-title').textContent, 'run2');
  vm.runInContext('closeHistoryDetail()', view.context);
  assert.equal(view.context.historyFileName, '');
});

test('실제 상세 모달은 live와 history 모두 메모·NSFW·실행 기록을 표시한다', () => {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '', style: {} });
    return elements.get(id);
  };
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  const start = html.indexOf('function showModal(d, mode)');
  const end = html.indexOf('function closeModal()', start);
  const context = vm.createContext({
    document: { getElementById: get, body: { style: {} } }, DashboardPresentation: ui,
    historyFileName: 'opaque-run', modalHistoryRunKey: '', _modalCurrentData: null, _updateModalNavButtons() {},
    escHtml: value => ui.safeLink('', String(value ?? '')), dkv: (label, value) => '<div>' + label + ': ' + value + '</div>',
    TOPICALITY_LABELS: {core_relevant: '핵심 관련', adjacent_relevant: '주변 관련', unrelated: '무관'},
    pickDisplayWorkTitle: () => '미확정',
    enumLabel: value => value || '미기록', confBadge: () => '', fmtNum: value => String(value),
    SUBTYPE_LABELS: {}, WORK_RESOLUTION_LABELS: {}, ANCHOR_TYPE_LABELS: {}, ANCHOR_STRENGTH_LABELS: {},
  });
  vm.runInContext(html.slice(html.indexOf('function topicalityMeta('), html.indexOf('function compactStructureText(')), context);
  vm.runInContext(html.slice(start, end), context);
  vm.runInContext(html.slice(html.indexOf('function mergeLiveDetail('), html.indexOf('function titleLabel(')), context);
  const identity = { reason: '원문 판정', is_relevant: true };
  const analysis = { notes: '별도 분석 메모', is_nsfw: false };
  const base = { post_id: 42, title: '제목', recovery_execution: recoveryViewFixture(), run_meta: {
    execution_config: { profile: 'low-load', settings: {}, requested_parallel: 1, effective_parallel: 1 },
    candidate_retrieval_shadow: {mode: 'SHADOW', status: 'NOT_AVAILABLE', post_id: 42,
      publication_authority: false, ranked_candidates: [], reason_codes: ['PIPELINE_NOT_EXECUTED']},
    candidate_calibration_shadow: {schema_version: 'candidate_calibration_shadow_v1', mode: 'SHADOW',
      status: 'NOT_EXECUTED', reason_codes: ['CALIBRATION_NOT_EXECUTED'], calibration_shadow: null},
    candidate_reranker_capture: {schema_version: 'candidate_reranker_capture_ref_v1', mode: 'SHADOW',
      status: 'SAVED', capture_sha256: 'modal-capture-fixed', artifact: {path: 'capture/display-only.json', bytes: 7}},
    candidate_reranker_semantics: semanticsViewFixture(),
    candidate_reranker_semantics_capture: {schema_version: 'candidate_reranker_semantics_capture_ref_v1',
      status: 'SAVED', observation_sha256: 'modal-semantics-fixed', artifact: {path: 'semantics/display-only.json', bytes: 9}},
    community_knowledge_readback: {mode: 'READ_ONLY', status: 'AMBIGUOUS', post_id: 42,
      public_authority: false, central_db_write: false, candidates: [], consumption: {status: 'PROMPT_SECTION_INCLUDED'}},
  } };
  context.liveDetail = { ...base, ...identity, analysis };
  // live는 요약+상세 병합, history는 원본 상세 payload를 공통 모달에 전달한다.
  vm.runInContext('live = mergeLiveDetail({post_id: 42, recovery_execution: {binding_status: "MISSING"}}, liveDetail)', context);
  context.history = { ...base, analysis_result: { identity, analysis } };
  for (const mode of ['live', 'history']) {
    vm.runInContext("showModal(" + mode + ", '" + mode + "')", context);
    const body = get('modal-body').innerHTML;
    for (const text of ['원문 판정', '별도 분석 메모', 'false · NSFW 해당 없음', 'low-load', '구조화 진단이 저장되지 않았습니다', '작품 후보 회수 · SHADOW', 'PIPELINE_NOT_EXECUTED', '커뮤니티 지식 · READ_ONLY', 'PROMPT_SECTION_INCLUDED', '선택 행 · R6 로컬 복구 판독', '파일·base 결속 확인', 'report-fingerprint']) {
      assert.ok(body.includes(text), mode + ': ' + text);
    }
    for (const text of ['후보 확률 교정 · FROZEN SHADOW', 'CALIBRATION_NOT_EXECUTED',
      '선택 전 원문 capture · 저장 참조', 'modal-capture-fixed', 'capture/display-only.json',
      '선택 전 의미 역할 · 별도 SHADOW', 'ROLE_POLICY_TRAINING_BINDING_PENDING', '점수·교정 입력 미사용',
      '의미 역할 capture · 저장 참조', 'modal-semantics-fixed', 'semantics/display-only.json']) {
      assert.ok(body.includes(text), mode + ': ' + text);
    }
  }
  assert.match(get('modal-body').innerHTML, /openHistoryRunLog/);
  assert.doesNotMatch(get('modal-body').innerHTML, /onclick="openPostLog/);
  assert.equal(context.modalHistoryRunKey, 'opaque-run');
  // 생산자가 저장한 optional 상태만 공통 NSFW 표시기에 전달한다.
  // live 상세의 새 analysis가 이전 요약 상태를 대체하며 history와 같은 문구를 낸다.
  const assessmentCases = [
    [{is_nsfw: false, nsfw_assessment_status: 'NOT_EVALUATED'}, '미평가 · NSFW 여부 미확인'],
    [{is_nsfw: false, nsfw_assessment_status: 'MODEL_REPORTED'}, 'false · NSFW 해당 없음 · 모델 보고값'],
    [{is_nsfw: true, nsfw_assessment_status: 'MODEL_REPORTED'}, 'true · NSFW 해당 · 모델 보고값'],
    [{is_nsfw: true, nsfw_assessment_status: 'SOURCE_RULE_POSITIVE'}, 'true · NSFW 해당 · 규칙 양성'],
    [{is_nsfw: true, nsfw_assessment_status: 'NOT_EVALUATED'}, '상태 불일치 · NSFW 여부 미확인'],
    [{is_nsfw: false, nsfw_assessment_status: 'SOURCE_RULE_POSITIVE'}, '상태 불일치 · NSFW 여부 미확인'],
    [{is_nsfw: 'false', nsfw_assessment_status: 'MODEL_REPORTED'}, '형식 불일치 · NSFW 여부 미확인'],
    [{is_nsfw: null, nsfw_assessment_status: 'NOT_EVALUATED'}, '형식 불일치 · NSFW 여부 미확인'],
    [{nsfw_assessment_status: 'MODEL_REPORTED'}, '형식 불일치 · NSFW 여부 미확인'],
    [{is_nsfw: false, nsfw_assessment_status: '<img src=x onerror=bad()>'}, '상태 미확인 · NSFW 여부 미확인'],
    [{is_nsfw: false, nsfw_assessment_status: {message: '<script>bad()</script>'}}, '상태 미확인 · NSFW 여부 미확인'],
    [{is_nsfw: false}, 'false · NSFW 해당 없음'],
    [{is_nsfw: false, nsfw_assessment_status: null}, 'false · NSFW 해당 없음'],
    [{is_nsfw: true}, 'true · NSFW 해당'],
    [{}, '미기록 · 판정 미확인'],
  ];
  for (const [fields, expected] of assessmentCases) {
    const sampleAnalysis = {...analysis, ...fields};
    if (!Object.hasOwn(fields, 'is_nsfw')) delete sampleAnalysis.is_nsfw;
    const before = JSON.stringify(sampleAnalysis);
    context.assessmentDetail = {...base, ...identity, analysis: sampleAnalysis};
    vm.runInContext('assessmentLive = mergeLiveDetail({post_id: 42, analysis: {is_nsfw: true, nsfw_assessment_status: "SOURCE_RULE_POSITIVE"}}, assessmentDetail)', context);
    context.assessmentHistory = {...base, analysis_result: {identity, analysis: sampleAnalysis}};
    for (const mode of ['live', 'history']) {
      vm.runInContext("showModal(" + (mode === 'live' ? 'assessmentLive' : 'assessmentHistory') + ", '" + mode + "')", context);
      const body = get('modal-body').innerHTML;
      assert.ok(body.includes('<div>NSFW: ' + expected + '</div>'), mode + ': ' + expected);
      if (expected.includes('미확인')) assert.doesNotMatch(body, /<div>NSFW: [^<]*NSFW 해당/);
      assert.doesNotMatch(body, /<img|<script>|onerror=/);
    }
    assert.equal(JSON.stringify(sampleAnalysis), before);
  }
  // 같은 행의 상세 analysis만 사용한다. 이전 요약·다른 행·다른 이력의 이유를 빌리지 않는다.
  const reasonCases = [...nsfwReasonDisplayCases(),
    [false, undefined, undefined, '평가 사유 미기록'],
    [false, 'NOT_EVALUATED', null, '평가 사유 미기록'],
    [false, 'NOT_EVALUATED', '<img src=x onerror=bad()>', '평가 사유 미확인'],
    [false, 'NOT_EVALUATED', 'SOURCE_IMAGE_RULE_POSITIVE', '평가 사유와 저장 상태가 일치하지 않습니다.']];
  for (const [position, [value, status, reason, expected]] of reasonCases.entries()) {
    const postId = position % 2 ? 43 : 42;
    const sampleAnalysis = {notes: '현재 행 메모', is_nsfw: value};
    if (status !== undefined) sampleAnalysis.nsfw_assessment_status = status;
    if (reason !== undefined) sampleAnalysis.nsfw_assessment_reason = reason;
    const before = JSON.stringify(sampleAnalysis);
    context.reasonDetail = {...base, post_id: postId, title: '현재 선택 행 ' + postId, ...identity, analysis: sampleAnalysis};
    context.reasonSummary = {post_id: postId, analysis: {is_nsfw: true,
      nsfw_assessment_status: 'SOURCE_RULE_POSITIVE', nsfw_assessment_reason: 'SOURCE_TEXT_RULE_POSITIVE'}};
    vm.runInContext('reasonLive = mergeLiveDetail(reasonSummary, reasonDetail)', context);
    context.reasonHistory = {...base, post_id: postId, title: '현재 선택 행 ' + postId, analysis_result: {identity, analysis: sampleAnalysis}};
    context.historyFileName = 'reason-run-' + position;
    for (const mode of ['live', 'history']) {
      vm.runInContext("showModal(" + (mode === 'live' ? 'reasonLive' : 'reasonHistory') + ", '" + mode + "')", context);
      const body = get('modal-body').innerHTML;
      assert.ok(body.includes('<div>NSFW 평가 사유: ' + expected + '</div>'), mode + ': ' + expected);
      assert.ok(body.includes('<div>NSFW: ' + ui.nsfwLabel(value, status) + '</div>'));
      assert.equal(context._modalCurrentData.post_id, postId);
      assert.equal(context.modalHistoryRunKey, mode === 'history' ? 'reason-run-' + position : '');
      assert.doesNotMatch(body, /<img|onerror=/);
    }
    assert.equal(JSON.stringify(sampleAnalysis), before);
  }
  // analysis 자체가 없을 때도 이전 요약의 NSFW 세 필드를 빌리지 않는다.
  // 다른 행/이력을 먼저 보여 준 뒤 같은 행과 다른 행의 상세를 반복해 검산한다.
  const missingAnalyses = [['null', null], ['empty', {}], ['missing', undefined]];
  const rowTransitions = [[42, 42], [42, 43], [43, 42], [42, 43]];
  const nsfwFields = ['is_nsfw', 'nsfw_assessment_status', 'nsfw_assessment_reason'];
  for (const [transition, [previousId, postId]] of rowTransitions.entries()) {
    for (const [variant, absentAnalysis] of missingAnalyses) {
      const oldAnalysis = {notes: '기존 메모 유지', user_segment: '기존 독자 분류', is_nsfw: true,
        nsfw_assessment_status: 'SOURCE_RULE_POSITIVE', nsfw_assessment_reason: 'SOURCE_TEXT_RULE_POSITIVE'};
      context.missingSummary = {...base, post_id: previousId, analysis: oldAnalysis};
      context.previousHistory = {...base, post_id: previousId, analysis_result: {identity, analysis: oldAnalysis}};
      context.historyFileName = 'previous-reason-run-' + transition;
      vm.runInContext("showModal(previousHistory, 'history')", context);
      assert.ok(get('modal-body').innerHTML.includes('<div>NSFW 평가 사유: 원문 텍스트가 NSFW 규칙에 해당합니다.</div>'));
      context.missingDetail = {...base, ...identity, post_id: postId, title: '현재 행 ' + postId, is_relevant: false};
      context.missingHistory = {...base, post_id: postId, analysis_result: {identity}};
      if (absentAnalysis !== undefined) {
        context.missingDetail.analysis = absentAnalysis;
        context.missingHistory.analysis_result.analysis = absentAnalysis;
      }
      const before = JSON.stringify([context.missingSummary, context.missingDetail, context.missingHistory]);
      vm.runInContext('missingLive = mergeLiveDetail(missingSummary, missingDetail)', context);
      assert.equal(context.missingLive.analysis.notes, oldAnalysis.notes);
      assert.equal(context.missingLive.analysis.user_segment, oldAnalysis.user_segment);
      for (const field of nsfwFields) assert.equal(Object.hasOwn(context.missingLive.analysis, field), false);
      context.historyFileName = 'current-reason-run-' + transition + '-' + variant;
      for (const mode of ['live', 'history']) {
        vm.runInContext("showModal(" + (mode === 'live' ? 'missingLive' : 'missingHistory') + ", '" + mode + "')", context);
        const body = get('modal-body').innerHTML;
        assert.ok(body.includes('<div>NSFW: 미기록 · 판정 미확인</div>'), mode + ': ' + variant);
        assert.ok(body.includes('<div>NSFW 평가 사유: 평가 사유 미기록</div>'), mode + ': ' + variant);
        assert.doesNotMatch(body, /<div>NSFW: [^<]*NSFW 해당/);
        assert.doesNotMatch(body, /<div>NSFW 평가 사유: 원문 텍스트가/);
        assert.equal(context._modalCurrentData.post_id, postId);
        assert.equal(context.modalHistoryRunKey, mode === 'history' ? context.historyFileName : '');
      }
      assert.equal(JSON.stringify([context.missingSummary, context.missingDetail, context.missingHistory]), before);
    }
  }
  // 행 ID도 없는 부분 상세의 NSFW 값은 현재 요약 행으로 옮기지 않는다.
  context.unboundNsfwSummary = {post_id: 42, analysis: {notes: '요약 메모'}};
  context.unboundNsfwDetail = {analysis: {notes: '상세 메모', is_nsfw: true,
    nsfw_assessment_status: 'SOURCE_RULE_POSITIVE', nsfw_assessment_reason: 'SOURCE_IMAGE_RULE_POSITIVE'}};
  const unboundBefore = JSON.stringify([context.unboundNsfwSummary, context.unboundNsfwDetail]);
  vm.runInContext('unboundNsfwLive = mergeLiveDetail(unboundNsfwSummary, unboundNsfwDetail)', context);
  assert.equal(context.unboundNsfwLive.post_id, 42);
  assert.equal(context.unboundNsfwLive.analysis.notes, '상세 메모');
  for (const field of nsfwFields) assert.equal(Object.hasOwn(context.unboundNsfwLive.analysis, field), false);
  assert.equal(JSON.stringify([context.unboundNsfwSummary, context.unboundNsfwDetail]), unboundBefore);
  context.historyFileName = 'opaque-run';
  // guard 진단도 같은 상세 payload 경로를 지나 live/history 공통 모달에 표시된다.
  const scopeDiagnostics = scopeGuardDisplayFixture(), scopeBefore = JSON.stringify(scopeDiagnostics);
  const scopeMeta = {...base.run_meta, source_context_diagnostics: scopeDiagnostics};
  context.scopeLiveDetail = {...base, ...identity, analysis, run_meta: scopeMeta};
  vm.runInContext('scopeLive = mergeLiveDetail({post_id: 42}, scopeLiveDetail)', context);
  context.scopeHistory = {...base, run_meta: scopeMeta, analysis_result: {identity, analysis}};
  for (const mode of ['live', 'history']) {
    vm.runInContext("showModal(" + (mode === 'live' ? 'scopeLive' : 'scopeHistory') + ", '" + mode + "')", context);
    const body = get('modal-body').innerHTML;
    const structured = body.split('<details class="raw-record"><summary>구조화 진단 원본 · JSON')[0];
    for (const text of ['상태 보정 guard · 저장 기록', '표면 제목 상태 검사', '질문 발화 범위 검사',
      '같은 문맥의 상태 반영 검사', 'DECODER_GENERAL_NOUN_HIGH_MISSING', 'LITERAL_TITLE_QUESTION_PROOF_BOUND',
      'CONTEXT_ONLY_SAME_NATIVE']) assert.ok(structured.includes(text), mode + ': ' + text);
    assert.match(structured, /기록된 공개 권한<\/div><div class="value">false</);
    assert.match(body, /구조화 진단 원본 · JSON/);
  }
  assert.equal(JSON.stringify(scopeDiagnostics), scopeBefore);
  // 주변 관련은 legacy is_relevant=false와 공존한다. 별도 '무관' 배지를 붙이지 않는다.
  for (const mode of ['live', 'history']) {
    for (const [topicality, relevant, expected] of [
      ['adjacent_relevant', false, '주변 관련'], ['unrelated', false, '무관'],
      ['core_relevant', true, '핵심 관련'], [undefined, false, '무관'],
      [undefined, undefined, '미확인'],
    ]) {
      const state = {topicality, is_relevant: relevant, reason: '표시 대조'};
      context.sample = mode === 'history' ? {post_id: 1, analysis_result: {identity: state}} : {post_id: 1, ...state};
      vm.runInContext("showModal(sample, '" + mode + "')", context);
      const body = get('modal-body').innerHTML;
      assert.ok(body.includes('>' + expected + '</span>'), mode + ': ' + expected);
      assert.doesNotMatch(body, /<div>관련 여부:/);
      if (topicality === 'adjacent_relevant') assert.doesNotMatch(body, />무관<\/span>/);
      if (typeof relevant === 'boolean') {
        assert.match(body, /기존 관련 플래그 \(is_relevant\)/);
        assert.ok(body.includes('>' + relevant + '</div>'));
      }
    }
  }
});

test('저부하 paired 관측은 저장과 검증을 구분하고 행·종료 기록을 함께 표시한다', () => {
  assert.equal(ui.renderPairedExecution(null), '');
  const start = {observed_at: '2026-10-10T00:00:00Z', binding: {arm: 'BEFORE', attempt_id: '<script>bad</script>'},
    policy_sha256: 'policy-fixed', resources: {pid: 123, priority_class: 16384, affinity_mask: 2},
    health: {ok_count: 1, failure_count: 0}};
  const meta = {paired_execution_observation: {start, end: {...start, observed_at: '2026-10-10T00:01:00Z'}}};
  const html = ui.renderRunContext({run_meta: meta, run_manifest: {summary: meta}});
  for (const text of ['행 저장 시점 · 저부하 비교 관측', '실행 manifest · 저부하 비교 관측', '시작·종료 관측 저장',
    '16384', 'policy-fixed', '정책 검산 통과를 판정하지 않습니다', 'REFERENCE_COPY_COST_ONLY']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(ui.renderPairedExecution({paired_execution_observation: {start}}), /관측 미완료/);
  assert.doesNotMatch(ui.renderPairedExecution({paired_execution_observation: {start}}), /시작·종료 관측 저장/);
});

test('semantic 검토·계획은 모드와 결속을 표시하고 query 허용을 실행으로 승격하지 않는다', () => {
  const binding = {attempt_run_id: 'row-run', publication_scope_id: 'scope-row', input_index: 1,
    post_id: 7, publication_decision_id: 'decision-row', public_apply: false, receipt_sha256: 'receipt-sha'};
  const meta = {semantic_review_router_receipt: {...binding, mode: 'REVIEW_ONLY', state: 'REVIEW_REQUIRED',
    trigger_codes: ['OCR_TITLE_UNRESOLVED'], unknown_reason_codes: []},
    semantic_recovery_plan_receipt: {...binding, mode: 'PLAN_ONLY', plan: {state: 'HOLD',
      blocker_codes: ['MISSING_PRIMARY'], relationship_counts: {mentioned: 1}, primary_identity_count: 0,
      query_plan: {purposes: ['VERIFY_OFFICIAL_DETAIL_ID'], query_execution_allowed: true, max_queries: 2},
      search_calls_executed: 0, network_calls_executed: 0}}};
  const before = JSON.stringify(meta);
  const html = ui.renderSemanticReview(meta);
  for (const value of ['REVIEW_ONLY', 'PLAN_ONLY', 'REVIEW_REQUIRED', 'HOLD', 'OCR_TITLE_UNRESOLVED',
    'MISSING_PRIMARY', 'row-run', 'scope-row', 'decision-row', 'receipt-sha', '>false<', '>0<',
    '계획상 query 실행 허용', '>true<', '실제 query 생성·검색·모델 실행을 뜻하지 않습니다']) {
    assert.ok(html.includes(value), value);
  }
  assert.equal(JSON.stringify(meta), before);
  const missing = ui.renderSemanticReview({});
  assert.match(missing, /의미 검토 수령증 미기록/);
  assert.match(missing, /복구 계획 수령증 미기록/);
  assert.doesNotMatch(missing, /NO_REVIEW|>false<|>0</);
  for (const state of ['NO_REVIEW', 'NOT_APPLICABLE', 'UNKNOWN']) {
    assert.ok(ui.renderSemanticReview({semantic_review_router_receipt: {state}}).includes(state));
  }
  const blocked = ui.renderSemanticReview({semantic_recovery_plan_receipt: {mode: 'PLAN_ONLY',
    public_apply: false, plan: {state: 'UNKNOWN', query_plan: {query_execution_allowed: false, max_queries: 0}}}});
  assert.match(blocked, /UNKNOWN · 계획 미확인/);
  assert.match(blocked, />false</);
  assert.match(blocked, /계획 수령증의 검색 호출 수<\/div><div class="value">미기록/);
});

test('activation manifest는 READY·OFF·NO_GO·fresh 생략과 미기록을 구분한다', () => {
  for (const [status, expected] of [['READY', '제안 기록 준비'], ['DISABLED', '비활성'],
    ['NO_GO', '제안 기록 불가·오류 확인'], ['SKIPPED_FRESH_MEASUREMENT', 'fresh 측정으로 감사 기록 생략']]) {
    const run = {recovery_activation_requested_mode: 'AUDIT_ONLY',
      recovery_activation_mode: status === 'DISABLED' ? 'OFF' : 'AUDIT_ONLY',
      recovery_activation_status: status, recovery_activation_public_apply: false,
      recovery_activation_event_count: 0, recovery_activation_append_errors: 0};
    const before = JSON.stringify(run), html = ui.renderRecoveryActivation(run);
    for (const value of [status, expected, 'AUDIT_ONLY', '>false<', '>0<', '실제 복구 실행 권한이 아닙니다']) {
      assert.ok(html.includes(value), value);
    }
    assert.equal(JSON.stringify(run), before);
    assert.doesNotMatch(html, /R6 전체 완료|복구 실행 완료|실제 provider 호출 수<\/div>/);
  }
  assert.match(ui.renderRecoveryActivation({}), /감사 기록 미기록/);
  const unknown = ui.renderRecoveryActivation({recovery_activation_mode: 'AUDIT_ONLY'});
  assert.match(unknown, /감사 기록 상태<\/div><div class="value">미기록/);
  assert.doesNotMatch(unknown, />0<|>false</);
});

test('공통 live·history 복구 표시는 행과 manifest 출처를 유지하며 저장 문자열을 escape한다', () => {
  const data = {run_meta: {semantic_review_router_receipt: {mode: 'REVIEW_ONLY', state: 'REVIEW_REQUIRED',
    attempt_run_id: 'row-attempt', trigger_codes: ['<script>bad()</script>'], public_apply: false}},
    run_manifest: {binding_status: 'BOUND', summary: {run_id: 'manifest-run',
      recovery_activation_mode: 'AUDIT_ONLY', recovery_activation_status: 'NO_GO',
      recovery_activation_error_samples: ['<img src=x onerror=bad()>']}}};
  const before = JSON.stringify(data), html = ui.renderRunContext(data);
  for (const value of ['행 저장 시점 · 의미 검토', '실행 manifest · 복구 제안 감사 기록',
    'row-attempt', 'manifest-run', 'REVIEW_ONLY', 'NO_GO', '&lt;script&gt;', '&lt;img']) assert.ok(html.includes(value), value);
  assert.doesNotMatch(html, /<script>|<img /);
  assert.equal(JSON.stringify(data), before);
});

test('R6 판독은 파일 결속과 저장자의 검증을 구분하고 합성·미산정·전체 분모를 보존한다', () => {
  const view = recoveryViewFixture(), before = JSON.stringify(view);
  const html = ui.renderRunContext({recovery_execution: view});
  for (const text of ['BOUND · 파일·base 결속 확인', 'FILE_AND_BASE_BINDING_ONLY', '저장 판독자의 검증 상태',
    'VERIFIED_LOCAL_CONTRACT', 'COMPLETED_SIMULATION · 로컬 합성 시뮬레이션 완료', 'LOCAL_SIMULATION_ONLY',
    'SYNTHETIC_CONTRACT_ONLY', 'NOT_ESTIMABLE', 'null · 산정값 없음', '실제 provider 실행은 미연결',
    '마지막 최종화 기록 저장 I/O는 예산에서 제외', '종결 후보 저장', '최종화 저장',
    'NO_PLAN_PROVIDED · 명시 계획 없음 · 실패 아님', 'base-attempt', 'plan-fingerprint', 'journal-fingerprint']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /실제 외부 호출 수<\/div><div class="value">0</);
  assert.match(html, /공개 적용<\/div><div class="value">false</);
  assert.match(html, /전체 입력 수<\/div><div class="value">2</);
  assert.match(html, /명시 계획 대상 수<\/div><div class="value">1</);
  assert.equal(JSON.stringify(view), before);
});

test('R6 미기록·미계획·결속 오류는 성공 보고서를 재사용하지 않으며 오류 문자열을 escape한다', () => {
  const report = recoveryViewFixture().report;
  const labels = {MISSING: '판독 기록 미기록', NO_PLAN_PROVIDED: '이 행의 명시 계획 없음 · 실패 아님', INVALID: '판독 기록 결속 오류'};
  for (const [binding_status, label] of Object.entries(labels)) {
    const html = ui.renderRecoveryExecution({binding_status, verification_scope: 'FILE_AND_BASE_BINDING_ONLY',
      reason_codes: ['<img src=x onerror=bad()>'], report});
    assert.ok(html.includes(label), binding_status);
    assert.match(html, /&lt;img/);
    assert.doesNotMatch(html, /<img |COMPLETED_SIMULATION|VERIFIED_LOCAL_CONTRACT|report-fingerprint/);
  }
  const absent = ui.renderRecoveryExecution(undefined);
  assert.match(absent, /판독 기록 미기록/);
  assert.doesNotMatch(absent, /NOT_STARTED|>0<|>false</);
  for (const view of [{binding_status: 'BOUND'}, {...recoveryViewFixture(), verification_scope: 'UNRECOGNIZED'},
    {...recoveryViewFixture(), report: {...report, schema_version: 'future_schema'}}]) {
    assert.match(ui.renderRecoveryExecution(view), /스키마 또는 확인 범위 미확인/);
    assert.doesNotMatch(ui.renderRecoveryExecution(view), /COMPLETED_SIMULATION|VERIFIED_LOCAL_CONTRACT/);
  }
});

test('R6 종결 후보만 있는 시도는 최종화 미완료와 후보 출력을 따로 표시한다', () => {
  const view = recoveryViewFixture(), report = view.report;
  report.execution_status = 'INCOMPLETE'; report.pending_finalization_count = 1;
  const attempt = report.attempts[0];
  attempt.status = 'INCOMPLETE'; attempt.finalization_recorded = false; attempt.output = null;
  attempt.reason_codes = ['ATTEMPT_NOT_FINALIZED']; report.input_rows[0].state = 'INCOMPLETE';
  const html = ui.renderRecoveryExecution(view);
  assert.match(html, /저장된 실행 상태<\/div><div class="value">INCOMPLETE · 미완료</);
  assert.match(html, /종결 후보 상태<\/div><div class="value">COMPLETED_SIMULATION/);
  assert.match(html, /최종화 저장<\/div><div class="value">false</);
  assert.match(html, /최종 출력 참조<\/div><div class="value">null · 산정값 없음/);
  assert.match(html, /ATTEMPT_NOT_FINALIZED/);
  assert.match(html, /최종화 대기 수<\/div><div class="value">1</);
});

test('R6 저장 상태와 알 수 없는 값은 바꾸지 않고 원문·참조를 안전하게 표시한다', () => {
  const view = recoveryViewFixture(), report = view.report;
  for (const status of ['NOT_STARTED', 'FAILED', 'BUDGET_EXHAUSTED', 'CANCELLED', 'UNKNOWN_FUTURE']) {
    report.execution_status = status;
    const html = ui.renderRecoveryExecution(view);
    assert.ok(html.includes('저장된 실행 상태</div><div class="value">' + status), status);
  }
  report.base.post_id = '<script>bad()</script>';
  report.attempts[0].candidate_output = {path: '<img src=x onerror=bad()>'};
  report.actual_external_call_count = undefined; report.tokens = undefined;
  report.budget_observation_scope = undefined; report.finalization_persistence_in_budget = undefined;
  const html = ui.renderRecoveryExecution(view);
  assert.match(html, /&lt;script&gt;/); assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<script>|<img |마지막 최종화 기록 저장 I\/O는 예산에서 제외/);
  assert.match(html, /실제 외부 호출 수<\/div><div class="value">미기록</);
  assert.match(html, /토큰<\/div><div class="value">미기록</);
});

test('이력 로그는 post ID 캐시와 현재 실행 로그를 사용하지 않는다', async () => {
  const html = fs.readFileSync(require.resolve('../src/llm_batch/monitor/static/index.html'), 'utf8');
  const start = html.indexOf('async function openPostLog(');
  const end = html.indexOf('function renderLogLines()', start);
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '', value: '', style: {} });
    return elements.get(id);
  };
  const paths = [];
  const context = vm.createContext({
    document: { getElementById: get, body: { style: {} }, querySelectorAll: () => [] },
    clearTimeout() {}, _logSearchTimer: null, _logRequestId: 0, _logRawLines: [],
    _logParsedSource: null, _logRecords: [], _logFilter: 'all', _logPage: 0, encodeURIComponent,
    _cacheGetPostLog() { throw new Error('history must not read post cache'); },
    _cacheSavePostLog() { throw new Error('history must not write post cache'); },
    renderLogLines() {}, escHtml: value => String(value),
    fetch: async url => { paths.push(url); return { ok: true, headers: { get: () => 'application/json' },
      json: async () => ({ lines: ['선택 실행 원문 로그'], source: 'bound-run' }) }; },
  });
  vm.runInContext(html.slice(start, end), context);
  await vm.runInContext("openPostLog(42, false, 'run opaque')", context);
  assert.deepEqual(paths, ['/api/runs/run%20opaque/log?tail=500']);
  assert.equal(context._logRawLines[0], '선택 실행 원문 로그');
  assert.match(get('log-modal-title').textContent, /선택 실행 로그/);
});

test('후보 회수는 SHADOW 상태·출처·행 결속을 표시하고 문자열을 escape한다', () => {
  assert.equal(ui.renderCandidateRetrieval(null), '');
  const html = ui.renderCandidateRetrieval({schema_version: 'candidate_retrieval_shadow_v1', mode: 'SHADOW',
    status: 'COMPLETE', post_id: 42, corpus_sha256: 'fixed-corpus', query_sha256: 'original-query',
    publication_authority: false, latency_ms: 0, binding: { run_id: 'run-42' },
    ranked_candidates: [{ corpus_candidate_id: 'immutable-1', title: '<script>alert(1)</script>', score: 0.5,
      work_id: 'work-1', edition_id: 'edition-1', media_type: 'WEB_NOVEL',
      source_refs: [{ source_ref: 'fixture://source' }] }]});
  for (const text of ['SHADOW', 'COMPLETE', 'fixed-corpus', 'original-query', 'immutable-1', 'fixture://source', 'run-42', 'work-1', 'edition-1', 'WEB_NOVEL']) {
    assert.ok(html.includes(text), text);
  }
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(ui.renderCandidateRetrieval({status: 'NOT_AVAILABLE', ranked_candidates: []}), /NIL.*뜻하지 않습니다/);
});

test('재정렬 관측은 합성 점수·미교정 확률·생성 상태·행 결속을 구분한다', () => {
  assert.equal(ui.renderCandidateReranker(null), '');
  const html = ui.renderCandidateReranker({mode: 'SHADOW', status: 'SCORED_SYNTHETIC',
    data_kind: 'SYNTHETIC_FIXTURE', training_status: 'NOT_TRAINED_SYNTHETIC_FIXTURE', actual_model_available: false,
    generation_status: 'COMPLETE', candidate_namespace: 'CORPUS_CANDIDATE', candidate_option_bridge_status: 'MISSING',
    probability_status: 'NOT_AVAILABLE_UNCALIBRATED', publication_authority: false, public_apply: false,
    model_manifest_sha256: 'model-fixed', query_sha256: 'query-fixed', generation_sha256: 'generation-fixed',
    ranked_candidates: [{candidate_id: '<script>alert(1)</script>', score: 0.75}],
    candidate_observations: [{candidate_id: 'candidate-A', role_observations: [{role: 'PREVIOUS', raw_path: '/title'}]}],
    binding: {attempt_id: 'attempt-fixed'}});
  for (const value of ['SCORED_SYNTHETIC', 'SYNTHETIC_FIXTURE', 'NOT_AVAILABLE_UNCALIBRATED',
    'model-fixed', 'query-fixed', 'generation-fixed', 'attempt-fixed', 'PREVIOUS', '/title', '0.75']) {
    assert.ok(html.includes(value), value);
  }
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /학습 파라미터가 있어도 실제 자료의 성능 검증을 뜻하지 않습니다/);
  assert.match(ui.renderCandidateReranker({status: 'NOT_SCORED_GENERATION_TRUNCATED'}), /저장된 재정렬 점수가 없습니다/);
});

test('학습 재정렬은 모델 존재와 자료 종류·품질 검증을 함께 표시한다', () => {
  const html = ui.renderCandidateReranker({mode: 'SHADOW', status: 'SCORED_LEARNED',
    backend: 'PAIRWISE_LINEAR_V1', model_kind: 'LEARNED_LINEAR_BASELINE',
    data_kind: 'SYNTHETIC_FIXTURE', training_status: 'TRAINED_PAIRWISE_LINEAR',
    actual_model_available: true, model_quality_status: 'NOT_EVALUATED_BY_ADAPTER',
    model_sha256: 'learned-weights-sha', probability_status: 'NOT_AVAILABLE_UNCALIBRATED',
    ranked_candidates: [{candidate_id: 'new-id', score: 0}]});
  for (const value of ['SCORED_LEARNED', 'PAIRWISE_LINEAR_V1', 'SYNTHETIC_FIXTURE',
    'TRAINED_PAIRWISE_LINEAR', 'NOT_EVALUATED_BY_ADAPTER', 'learned-weights-sha', 'new-id']) {
    assert.ok(html.includes(value), value);
  }
  assert.match(html, /학습 파라미터 사용 가능/);
  assert.match(html, /교정된 확률이나 작품 없음/);
});

test('NIL 학습 점수는 파라미터 존재와 미교정 상태를 구분해 표시한다', () => {
  const html = ui.renderCandidateReranker({status: 'SCORED_LEARNED', backend: 'NIL_AUGMENTED_LINEAR_V1',
    nil_head_available: true, nil_score: -0.25, candidate_ranker_model_sha256: 'base-model-sha',
    nil_probability: null, selected_candidate_id: null,
    event_logits: [{label: '<img>', score: 0.1}, {label: '__NIL__', score: -0.25}]});
  for (const value of ['NIL 학습 파라미터 사용 가능', 'NIL 원시 점수', '-0.25', '__NIL__', 'base-model-sha']) {
    assert.ok(html.includes(value), value);
  }
  assert.match(html, /작품 없음의 확률이나 최종 판정으로 사용하지 않습니다/);
  assert.doesNotMatch(html, /<img>/);
  const unscored = ui.renderCandidateReranker({status: 'UNAVAILABLE_MODEL', backend: 'NIL_AUGMENTED_LINEAR_V1',
    nil_head_available: true, nil_score: null, event_logits: []});
  assert.match(unscored, /UNAVAILABLE_MODEL/);
  assert.match(unscored, /저장된 재정렬 점수가 없습니다/);
  assert.doesNotMatch(ui.renderCandidateReranker({backend: 'PAIRWISE_LINEAR_V1'}), /NIL 원시 점수/);
});

test('기존 scorer의 v1 제목 관측과 별도 의미 관측의 미소비를 구분한다', () => {
  for (const status of ['OBSERVED', 'NO_MATCH', 'AMBIGUOUS', 'NOT_EXECUTED', 'LIMIT_EXCEEDED']) {
    const html = ui.renderCandidateReranker({status: 'SCORED_LEARNED',
      preselection_role_producer: {status, reason_codes: ['AMBIGUOUS_TITLE'], counts: {observations: 2},
        policy_sha256: 'policy-roles-fixed', frozen_view_sha256: 'view-roles-fixed'},
      candidate_observations: [{candidate_id: '<img onerror=alert(1)>',
        role_observations: [{role: 'MENTIONED', raw_path: '/comments/0', start: 2, end: 5}]}]});
    for (const value of [status, 'AMBIGUOUS_TITLE', 'policy-roles-fixed', 'view-roles-fixed', 'MENTIONED', '/comments/0']) {
      assert.ok(html.includes(value), value);
    }
    assert.match(html, /이 scorer 입력의 v1 제목 출현 관측은 MENTIONED만 기록합니다/);
    assert.match(html, /별도 의미 역할 관측은 이 점수·교정 입력에 반영하지 않습니다/);
    assert.doesNotMatch(html, /<img/);
  }
  assert.doesNotMatch(ui.renderCandidateReranker({status: 'SCORED_SYNTHETIC'}), /선택 전 역할 관측 상태/);
});

test('커뮤니티 지식은 조회와 실제 소비를 구분하고 후보 권한과 출처를 표시한다', () => {
  assert.equal(ui.renderCommunityKnowledge(null), '');
  const html = ui.renderCommunityKnowledge({schema_version: 'community_knowledge_readback_v1', mode: 'READ_ONLY',
    status: 'AMBIGUOUS', post_id: 42, snapshot_sha256: 'snapshot-fixed', query_sha256: 'query-fixed',
    public_authority: false, central_db_write: false, consumption: {status: 'PROMPT_SECTION_INCLUDED'},
    candidates: [{candidate_id: 'candidate-1', sense_candidate_id: 'sense-1', namespace: 'COMMUNITY_LEXICON',
      surface_raw: '아생갤', definition_text: '<script>alert(1)</script>', source_refs: [{source_ref: 'fixture://source'}],
      community_scope: ['fixture-community'], temporal_scope: {valid_from: '2026-10-01T00:00:00Z'},
      review_status: 'UNREVIEWED', work_alias_entries: [], lexicon_entries: [{term_kind: 'MEME'}]}],
    binding: {attempt_id: 'attempt-1'}});
  for (const text of ['READ_ONLY', 'AMBIGUOUS', 'PROMPT_SECTION_INCLUDED', 'snapshot-fixed', 'query-fixed', 'candidate-1', 'sense-1', 'fixture://source', 'attempt-1', 'fixture-community', '2026-10-01T00:00:00Z', 'UNREVIEWED', 'MEME']) {
    assert.ok(html.includes(text), text);
  }
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /올바른 해석의 증거가 아니며/);
  assert.match(ui.renderCommunityKnowledge({status: 'UNAVAILABLE', candidates: []}), /NIL.*판정은 아닙니다/);
});

function calibrationViewFixture() {
  return {schema_version: 'candidate_calibration_shadow_v1', mode: 'SHADOW', status: 'CALIBRATED_SHADOW_BOUND',
    post_id: 42, dataset_post_id: 'dataset-42', dataset_example_id: 'frozen-42', data_kind: 'SYNTHETIC_FIXTURE',
    mapping_sha256: 'mapping-fixed', runtime_capture_sha256: 'capture-fixed',
    runtime_raw_receipt_sha256: 'runtime-raw-fixed', dataset_raw_receipt_sha256: 'dataset-raw-fixed',
    calibration_artifact_sha256: 'artifact-fixed', bundle_sha256: 'bundle-fixed', model_sha256: 'model-fixed',
    scorer_sha256: 'scorer-fixed', publication_authority: false, public_apply: false, central_db_write: false,
    action_applied: false, operational_effect: 'NONE_SHADOW_ONLY', receipt_sha256: 'calibration-receipt-fixed',
    binding: {run_id: 'run-fixed', publication_scope_id: 'scope-fixed', attempt_id: 'attempt-fixed', input_index: 1,
      post_id: 42, scope: 'FROZEN_REOBSERVATION_ONLY'},
    calibration_shadow: {probability_status: 'CALIBRATED_SHADOW_BOUND', action_applied: false,
      selected_label: '__NIL__', action: 'ASSERT_NIL', policy_sha256: 'policy-fixed',
      split_manifest_sha256: 'split-fixed', score_vector_sha256: 'vector-fixed', event_probabilities: [
        {label: 'candidate-A', probability_mass: 0, probability_scale: 1000000},
        {label: '__NIL__', probability_mass: 1000000, probability_scale: 1000000}]}};
}

function semanticsViewFixture() {
  const mention = {raw_path: '/title', start: 0, end: 3, byte_start: 0, byte_end: 9,
    text: '합성작', text_sha256: 'mention-fixed'};
  return {schema_version: 'candidate_reranker_semantics_runtime_v1', mode: 'SHADOW', status: 'OBSERVED',
    reason_codes: [], post_id: 42, publication_authority: false, public_apply: false, central_db_write: false,
    binding: {run_id: 'semantics-run', publication_scope_id: 'semantics-scope', input_index: 1,
      post_id: 42, attempt_id: 'semantics-attempt'}, receipt_sha256: 'runtime-semantics-fixed',
    consumption: {status: 'OBSERVED_NOT_CONSUMED', scorer_input_applied: false, calibration_input_applied: false,
      reason_codes: ['ROLE_POLICY_TRAINING_BINDING_PENDING'], scorer_input_sha256: 'old-scorer-view-fixed'},
    observation: {schema_version: 'candidate_preselection_semantics_v2', status: 'OBSERVED', reason_codes: [],
      policy_sha256: 'semantics-policy-fixed', parser_contract_sha256: 'parser-fixed',
      score_consumption_status: 'NOT_CONSUMED_MODEL_POLICY_UNBOUND', source_view_sha256: 'source-view-fixed',
      query_sha256: 'source-view-fixed', input_frozen_view_sha256: 'before-view-fixed',
      frozen_view_sha256: 'after-view-fixed', candidate_ids_sha256: 'ids-fixed', receipt_sha256: 'observation-fixed',
      alias_evidence_sha256: null, alias_validation: null, counts: {candidates: 1, primary: 1, previous: 0,
        comparison: 0, mentioned: 0, unresolved: 1, alias_observations: 0, observations: 1},
      observations: [{candidate_id: 'candidate-fixed', role: 'PRIMARY', mention_kind: 'EXACT_TITLE', mention,
        relation_cues: [{...mention, text: '후기', text_sha256: 'cue-fixed'}], related_mentions: [],
        speaker: 'AUTHOR', assertion: 'ASSERTED', rule_id: 'rule-fixed', alias_evidence_ids: []}],
      unresolved: [{candidate_ids: ['candidate-other'], mention, reason_codes: ['AUTHOR_STATE_UNRESOLVED']}]}};
}

test('의미 역할은 원문 근거와 미결합을 표시하고 scorer·교정 입력과 분리한다', () => {
  const value = semanticsViewFixture(), before = JSON.stringify(value);
  const html = ui.renderCandidateSemantics(value, {binding_status: 'BOUND'});
  for (const text of ['선택 전 의미 역할 · 별도 SHADOW', 'PRIMARY', 'PREVIOUS', 'COMPARISON', 'MENTIONED',
    '작가의 전작이며 독자의 과거 독서 이력이 아닙니다', '점수·교정 입력 미사용',
    'ROLE_POLICY_TRAINING_BINDING_PENDING', 'NOT_CONSUMED_MODEL_POLICY_UNBOUND',
    'semantics-policy-fixed', 'parser-fixed', 'source-view-fixed', 'before-view-fixed', 'after-view-fixed',
    'old-scorer-view-fixed', 'ids-fixed', 'observation-fixed', 'runtime-semantics-fixed',
    'semantics-run', 'semantics-scope', 'semantics-attempt', 'AUTHOR_STATE_UNRESOLVED',
    'candidate-fixed', '/title', 'mention-fixed', 'cue-fixed', 'AUTHOR', 'ASSERTED', 'rule-fixed']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /작가의 전작 · PREVIOUS<\/div><div class="value">0</);
  assert.match(html, /scorer 입력 적용<\/div><div class="value">false</);
  assert.match(html, /별칭 검산·출처 권한·자료 구분<\/div><div class="value">null · 산정값 없음</);
  assert.match(html, /관측 후 view SHA-256 · 모델 입력 아님/);
  assert.equal(JSON.stringify(value), before);
});

test('의미 관측 terminal·미기록·스키마 불일치는 성공이나 0건으로 보충하지 않는다', () => {
  for (const value of [undefined, null, [], false]) {
    assert.match(ui.renderCandidateSemantics(value), /관측이 저장되지 않았습니다/);
  }
  for (const status of ['NOT_EXECUTED', 'NOT_AVAILABLE', 'ERROR', 'LIMIT_EXCEEDED', 'INVALID_INPUT', 'FUTURE_STATUS']) {
    const value = semanticsViewFixture(); value.status = status;
    const html = ui.renderCandidateSemantics(value);
    assert.ok(html.includes(status));
    assert.match(html, /구조화 역할 표시 대상이 아닙니다/);
    assert.doesNotMatch(html, /주요 논의 대상 · PRIMARY<\/div>/);
  }
  for (const change of [v => { v.schema_version = 'future'; },
    v => { v.observation.schema_version = 'future'; }, v => { v.observation.status = 'NO_MATCH'; },
    v => { v.observation = null; }, v => { v.mode = 'OFF'; }]) {
    const value = semanticsViewFixture(); change(value);
    assert.doesNotMatch(ui.renderCandidateSemantics(value), /주요 논의 대상 · PRIMARY<\/div>/);
  }
  for (const status of ['NO_MATCH', 'AMBIGUOUS']) {
    const value = semanticsViewFixture(); value.status = value.observation.status = status;
    value.observation.counts = {primary: null}; value.observation.observations = [];
    const html = ui.renderCandidateSemantics(value);
    assert.match(html, /주요 논의 대상 · PRIMARY<\/div><div class="value">null · 산정값 없음</);
    assert.match(html, /작가의 전작 · PREVIOUS<\/div><div class="value">미기록</);
  }
});

test('소비 필드가 없거나 모순이면 미사용을 단정하지 않는다', () => {
  for (const consumption of [null, {}, {status: 'FUTURE_STATUS', scorer_input_applied: false, calibration_input_applied: false},
    {status: 'OBSERVED_NOT_CONSUMED', scorer_input_applied: true, calibration_input_applied: false},
    {status: 'OBSERVED_NOT_CONSUMED', scorer_input_applied: false, calibration_input_applied: true}]) {
    const html = ui.renderCandidateSemantics({...semanticsViewFixture(), consumption});
    assert.match(html, /점수·교정 입력 소비 계약 미확인/);
    assert.doesNotMatch(html, /점수·교정 입력 미사용 ·/);
  }
  for (const status of ['NOT_CONSUMED_OBSERVATION_FAILED', 'NOT_EXECUTED', 'NOT_AVAILABLE']) {
    const value = semanticsViewFixture(); value.status = 'NOT_EXECUTED'; value.observation = null;
    value.consumption.status = status;
    const html = ui.renderCandidateSemantics(value);
    assert.match(html, /점수·교정 입력 미사용 ·/);
    assert.ok(html.includes(status));
    assert.doesNotMatch(html, /주요 논의 대상 · PRIMARY<\/div>/);
  }
});

function semanticConsumerFixture() {
  const value = semanticsViewFixture();
  value.schema_version = 'candidate_reranker_semantics_runtime_v2';
  value.consumption = {schema_version: 'candidate_reranker_semantic_consumption_v1', status: 'SCORED',
    input_validated: true, backend_invoked: true, score_produced: true,
    scorer_input_applied: true, calibration_input_applied: false, reason_codes: []};
  for (const key of ['semantic_contract_sha256', 'semantic_policy_sha256', 'score_receipt_sha256',
    'model_sha256', 'scorer_sha256', 'semantic_input_sha256', 'semantic_observation_sha256', 'scorer_input_sha256']) {
    value.consumption[key] = 'a'.repeat(64);
  }
  return value;
}

test('의미 특징 실제 점수 소비와 별도 CAL 적용을 저장값대로 표시한다', () => {
  for (const calibration of [false, true]) {
    const value = semanticConsumerFixture(); value.consumption.calibration_input_applied = calibration;
    const before = JSON.stringify(value), html = ui.renderCandidateSemantics(value);
    assert.match(html, /의미 특징을 실제 점수 입력에 사용했습니다/);
    assert.match(html, /실제 자료 품질 수용을 뜻하지 않습니다/);
    assert.match(html, /실제 scorer 입력 SHA-256/);
    assert.match(html, /의미 특징 계약 SHA-256/);
    assert.match(html, /주요 논의 대상 · PRIMARY/);
    assert.doesNotMatch(html, /점수·교정 입력 미사용 ·/);
    assert.equal(JSON.stringify(value), before);
  }
});

test('의미 특징 호출 실패와 입력 검산만 된 상태를 점수 생성 성공과 구분한다', () => {
  const value = semanticConsumerFixture();
  value.consumption.status = 'BACKEND_FAILED'; value.consumption.score_produced = false;
  let html = ui.renderCandidateSemantics(value);
  assert.match(html, /점수 생성은 완료되지 않았습니다/);
  assert.doesNotMatch(html, /실제 점수 입력에 사용했습니다/);
  value.consumption.status = 'INPUT_BOUND_NOT_SCORED';
  value.consumption.backend_invoked = value.consumption.scorer_input_applied = false;
  html = ui.renderCandidateSemantics(value);
  assert.match(html, /점수기 호출은 실행되지 않았습니다/);
  assert.doesNotMatch(html, /실제 점수 입력에 사용했습니다/);
});

test('새 소비 기록도 필수 지문 누락과 모순이면 성공 표시를 보류한다', () => {
  for (const change of [v => delete v.consumption.semantic_contract_sha256,
    v => v.mode = 'OFF', v => v.status = 'NOT_EXECUTED',
    v => v.observation.status = 'NOT_EXECUTED', v => v.observation.schema_version = 'FUTURE',
    v => v.consumption.schema_version = 'FUTURE', v => v.consumption.backend_invoked = false,
    v => v.consumption.input_validated = false, v => v.consumption.score_produced = false,
    v => v.consumption.semantic_input_sha256 = '<script>오염</script>',
    v => {v.consumption = {status: 'NOT_AVAILABLE', scorer_input_applied: null, calibration_input_applied: null};}]) {
    const value = semanticConsumerFixture(); change(value);
    const html = ui.renderCandidateSemantics(value);
    assert.match(html, /점수·교정 입력 소비 계약 미확인/);
    assert.doesNotMatch(html, /의미 특징을 실제 점수 입력에 사용했습니다/);
    assert.doesNotMatch(html, /<script>/);
  }
});

test('별칭 근거·화자·모호성 객체를 escape하고 상세 표시 상한을 명시한다', () => {
  const value = semanticsViewFixture();
  value.observation.alias_evidence_sha256 = 'alias-fixed';
  value.observation.alias_validation = {schema_version: 'candidate_reranker_alias_evidence_v1',
    status: 'BOUND', data_kind: 'SYNTHETIC_FIXTURE', reason_codes: [{text: '<img src=x onerror=bad()>'}],
    bindings: [{candidate_id: 'candidate-0', alias: '합성별칭', evidence_grade: 'SYNTHETIC_FIXTURE_BOUND',
      review_authority: 'SYNTHETIC_FIXTURE', relation: {predicate: '뜻한다'}}], unresolved: []};
  value.observation.observations = Array.from({length: 33}, (_, i) => ({...value.observation.observations[0],
    candidate_id: 'candidate-' + i, mention_kind: 'VERIFIED_ALIAS', alias_evidence_ids: ['alias-1']}));
  value.observation.observations[0].relation_cues = [{text: '<script>bad()</script>'}];
  const html = ui.renderCandidateSemantics(value);
  for (const text of ['alias-fixed', 'VERIFIED_ALIAS', 'alias-1', 'SYNTHETIC_FIXTURE', 'SYNTHETIC_FIXTURE_BOUND',
    'review_authority', '뜻한다', '관계의 진실·검토자 신원을 이 화면에서 인증하지 않습니다',
    '갤·갤러리라는 표면만으로', '상세 카드 표시 상한 32개', 'candidate-32']) assert.ok(html.includes(text), text);
  assert.equal((html.match(/<summary>원문 역할 ·/g) || []).length, 32);
  assert.match(html, /&lt;script&gt;/); assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<script>|<img/);
});

test('의미 capture는 저장·미실행·null을 보존하고 참조 파일을 링크로 열지 않는다', () => {
  assert.match(ui.renderCandidateSemanticsCapture(null), /capture 참조가 저장되지 않았습니다/);
  const value = {schema_version: 'candidate_reranker_semantics_capture_ref_v1', status: 'SAVED',
    observation_sha256: 'observation-fixed', capture_sha256: 'capture-fixed', input_snapshot_sha256: 'input-fixed',
    binding: {run_id: 'run-fixed', publication_scope_id: 'scope-fixed'}, publication_authority: false,
    public_apply: false, central_db_write: false, receipt_sha256: 'ref-fixed',
    artifact: {path: 'https://example.invalid/<img onerror=bad()>.json', sha256: 'file-fixed', bytes: 0}};
  const before = JSON.stringify(value), html = ui.renderCandidateSemanticsCapture(value);
  for (const text of ['SAVED', 'observation-fixed', 'capture-fixed', 'input-fixed', 'run-fixed', 'scope-fixed',
    'ref-fixed', 'file-fixed', '저장 성공은 모델 입력 적용이나 학습·정답 배정을 뜻하지 않습니다']) assert.ok(html.includes(text), text);
  assert.match(html, /파일 바이트 수<\/div><div class="value">0</);
  assert.match(html, /공개 권한<\/div><div class="value">false</);
  assert.match(html, /관측 객체 전체 SHA-256 · receipt self SHA와 별도/);
  assert.match(html, /&lt;img/); assert.doesNotMatch(html, /<img|<a\s|href=/);
  assert.equal(JSON.stringify(value), before);
  for (const status of ['NOT_EXECUTED', 'NOT_AVAILABLE', 'FUTURE_STATUS']) {
    const absent = ui.renderCandidateSemanticsCapture({status, artifact: null});
    assert.ok(absent.includes(status));
    assert.match(absent, /파일 참조<\/div><div class="value">null · 산정값 없음</);
    assert.match(absent, /파일 바이트 수<\/div><div class="value">미기록</);
  }
});

test('manifest 의미 정책은 행 관측을 대신하지 않고 stale scope 정책을 차단한다', () => {
  const policy = {schema_version: 'candidate_reranker_semantics_policy_v1', mode: 'SHADOW',
    producer_schema: 'candidate_preselection_semantics_v2', policy: {semantic_scope: 'PER_OCCURRENCE_AUTHOR_ASSERTION',
      authority: 'SOURCE_OBSERVATION_NOT_GOLD', parser_contract_sha256: 'manifest-parser-fixed'},
    score_consumption_status: 'NOT_CONSUMED_MODEL_POLICY_UNBOUND', alias_bundle_sha256: null,
    policy_sha256: 'manifest-semantics-fixed',
    publication_authority: false, public_apply: false, central_db_write: false};
  for (const binding_status of ['BOUND', 'PARTIAL']) {
    const html = ui.renderRunContext({run_manifest: {binding_status,
      summary: {candidate_reranker_semantics_policy: policy}}});
    assert.match(html, /실행 manifest · 선행 의미 역할 정책/);
    assert.match(html, /manifest-semantics-fixed/);
    assert.match(html, /행별 관측 성공이나 모델·교정 입력 소비를 뜻하지 않습니다/);
    assert.match(html, /실제 품질 평가<\/div><div class="value">미기록</);
    assert.match(html, /PER_OCCURRENCE_AUTHOR_ASSERTION/);
    assert.match(html, /manifest-parser-fixed/);
    assert.match(html, /SOURCE_OBSERVATION_NOT_GOLD/);
    assert.doesNotMatch(html, /선택 전 의미 역할 · 별도 SHADOW/);
  }
  for (const binding_status of ['MISMATCH', 'MISSING', undefined]) {
    const html = ui.renderRunContext({run_manifest: {binding_status, reason_codes: ['PUBLICATION_SCOPE_MISMATCH'],
      summary: {candidate_reranker_semantics_policy: policy}}});
    // The untrusted complete manifest stays in its existing raw-record section; the policy card must not adopt it.
    const policyCard = html.slice(html.indexOf('<h3 class="detail-section-title">실행 manifest · 선행 의미 역할 정책'));
    assert.match(policyCard, /manifest 결속이 확인되지 않아/);
    assert.doesNotMatch(policyCard, /manifest-semantics-fixed/);
  }
  const row = ui.renderCandidateSemantics(semanticsViewFixture(), {binding_status: 'MISMATCH'});
  assert.match(row, /manifest 실행·공개 범위 결속 불일치/);
  assert.match(row, /runtime-semantics-fixed/);
});

test('교정 카드는 저장된 FROZEN 확률 질량을 raw 점수·공개 판정과 구분한다', () => {
  const value = calibrationViewFixture(), before = JSON.stringify(value);
  const html = ui.renderCandidateCalibration(value);
  for (const text of ['FROZEN 재관측 전용', 'SYNTHETIC_FIXTURE', 'mapping-fixed', 'capture-fixed',
    'runtime-raw-fixed', 'dataset-raw-fixed', 'artifact-fixed', 'bundle-fixed', 'model-fixed', 'scorer-fixed',
    'calibration-receipt-fixed', 'run-fixed', 'attempt-fixed', 'scope-fixed', 'dataset-42', 'frozen-42',
    '__NIL__', 'candidate-A', '1000000', 'NONE_SHADOW_ONLY', 'policy-fixed', 'split-fixed', 'vector-fixed']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /확률 정수 질량<\/div><div class="value">0</);
  assert.match(html, /공개 권한<\/div><div class="value">false</);
  assert.match(html, /동작 적용<\/div><div class="value">false</);
  assert.match(html, /SHADOW 선택 label · 공개 선택 아님/);
  assert.match(html, /실제 자료의 교정 품질이나 최종 공개 판정을 뜻하지 않습니다/);
  assert.equal(JSON.stringify(value), before);
  assert.match(ui.renderCandidateReranker({backend: 'NIL_AUGMENTED_LINEAR_V1', nil_score: 0,
    probability_status: 'NOT_AVAILABLE_UNCALIBRATED', nil_probability: null}), /NIL 학습 점수도 미교정 원시 점수/);
});

test('교정 미기록·비결속·null은 확률 0으로 대체하지 않는다', () => {
  for (const value of [null, undefined, [], false]) {
    assert.match(ui.renderCandidateCalibration(value), /교정 관측이 저장되지 않았습니다/);
  }
  for (const status of ['NOT_AVAILABLE', 'NOT_EXECUTED', 'UNAVAILABLE', 'OFF', 'FUTURE_STATUS']) {
    const value = {...calibrationViewFixture(), status, calibration_shadow: null};
    const html = ui.renderCandidateCalibration(value);
    assert.ok(html.includes(status));
    assert.match(html, /저장된 교정 payload<\/div><div class="value">null · 산정값 없음</);
    assert.doesNotMatch(html, /고정 사건 label<\/div>/);
  }
  const stale = calibrationViewFixture(); stale.status = 'UNAVAILABLE';
  assert.doesNotMatch(ui.renderCandidateCalibration(stale), /고정 사건 label<\/div>/);
  const missing = calibrationViewFixture(); missing.calibration_shadow.event_probabilities = [{label: '__NIL__'}];
  assert.match(ui.renderCandidateCalibration(missing), /확률 정수 질량<\/div><div class="value">미기록</);
  assert.match(ui.renderCandidateCalibration(missing), /확률 기준값<\/div><div class="value">미기록</);
});

test('교정·capture의 객체 및 문자열은 escape하고 파일 링크를 만들지 않는다', () => {
  const value = calibrationViewFixture();
  value.reason_codes = [{message: '<script>bad()</script>'}];
  value.calibration_shadow.event_probabilities[0].label = {text: '<img src=x onerror=bad()>'};
  const capture = {status: 'SAVED', scope: 'PRE_SELECTION_PARSED_SOURCE_SNAPSHOT',
    training_readiness: 'NOT_ASSIGNED_OR_ADJUDICATED', fragment_count: 0, candidate_count: 0,
    observation_sha256: 'observation-fixed', capture_sha256: 'capture-fixed', frozen_view_sha256: 'view-fixed',
    input_snapshot_sha256: 'input-fixed', receipt_sha256: 'ref-fixed', publication_authority: false,
    public_apply: false, central_db_write: false, artifact: {path: '<img src=x onerror=bad()>', sha256: 'file-fixed', bytes: 0},
    binding: {run_id: 'run-fixed'}};
  const html = ui.renderCandidateCalibration(value) + ui.renderCandidateCapture(capture);
  assert.match(html, /&lt;script&gt;/); assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<script>|<img|<a\s|href=/);
  for (const text of ['NOT_ASSIGNED_OR_ADJUDICATED', 'PRE_SELECTION_PARSED_SOURCE_SNAPSHOT',
    'observation-fixed', 'capture-fixed', 'view-fixed', 'input-fixed', 'ref-fixed', 'file-fixed', 'run-fixed']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /파일 바이트 수<\/div><div class="value">0</);
  assert.match(html, /저장 성공은 학습 분할 배정이나 정답 판정을 뜻하지 않습니다/);
  capture.artifact.path = 'https://example.invalid/capture.json';
  assert.doesNotMatch(ui.renderCandidateCapture(capture), /<a\s|href=/);
});

test('capture 미기록·미실행과 null 파일 참조를 보존한다', () => {
  assert.match(ui.renderCandidateCapture(null), /capture 참조가 저장되지 않았습니다/);
  for (const status of ['NOT_AVAILABLE', 'NOT_EXECUTED', 'UNKNOWN_FUTURE']) {
    const html = ui.renderCandidateCapture({status, artifact: null, publication_authority: false});
    assert.ok(html.includes(status));
    assert.match(html, /파일 참조<\/div><div class="value">null · 산정값 없음</);
    assert.match(html, /파일 바이트 수<\/div><div class="value">미기록</);
  }
});

test('manifest 교정 정책은 행 성공으로 승격하지 않고 저장 정책만 표시한다', () => {
  const policy = {mode: 'SHADOW', status: 'AVAILABLE', scope: 'FROZEN_REOBSERVATION_ONLY',
    data_kind: 'SYNTHETIC_FIXTURE', bundle_sha256: 'policy-bundle-fixed', calibration_artifact_sha256: 'policy-artifact-fixed',
    model_sha256: 'policy-model-fixed', scorer_sha256: 'policy-scorer-fixed', actual_quality_evaluated: false,
    publication_authority: false, public_apply: false};
  const html = ui.renderRunContext({run_manifest: {binding_status: 'BOUND', summary: {candidate_calibration_policy: policy}}});
  for (const text of ['실행 manifest · 후보 확률 교정 정책', 'FROZEN_REOBSERVATION_ONLY',
    'policy-bundle-fixed', 'policy-artifact-fixed', 'policy-model-fixed', 'policy-scorer-fixed']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /실제 품질 평가<\/div><div class="value">false</);
  assert.match(html, /정책 저장은 해당 행의 교정 실행이나 실제 자료 품질 평가 완료를 뜻하지 않습니다/);
  assert.doesNotMatch(ui.renderRunContext({run_manifest: {binding_status: 'MISMATCH', summary: {}}}),
    /실행 manifest · 후보 확률 교정 정책/);
});

// producer의 허용 필드·코드를 사용한 합성 표시 자료다. 실제 저장 관측이나 사람 정답이 아니다.
function scopeGuardDisplayFixture() {
  return {schema_version: 'source_context_diagnostics_v1', status: 'STORED', publication_authority: false,
    reason_codes: [], omitted_counts: {}, max_bytes: 65536, scope_state_guards: [
      {gate: 'surface_title_anchor', status: 'REJECTED', code: 'DECODER_GENERAL_NOUN_HIGH_MISSING', calls: 2,
        first_rejection: 'DECODER_GENERAL_NOUN_HIGH_MISSING', applied: false, publication_authority: false},
      {gate: 'propriety_question_scope', status: 'ELIGIBLE', code: 'LITERAL_TITLE_QUESTION_PROOF_BOUND', calls: 1,
        first_rejection: null, applied: false, publication_authority: false},
      {gate: 'propriety_callback', status: 'APPLIED', code: 'CONTEXT_ONLY_SAME_NATIVE', calls: 1,
        first_rejection: null, applied: true, publication_authority: false},
    ]};
}

function scopeGuardStructured(value) {
  return ui.renderContextDiagnostics(value).split('<details class="raw-record"><summary>구조화 진단 원본 · JSON')[0];
}

test('상태 guard 세 단계와 적용·거절 근거를 원본 JSON 밖에서 읽을 수 있다', () => {
  const value = scopeGuardDisplayFixture(), before = JSON.stringify(value);
  const html = scopeGuardStructured(value);
  for (const text of ['표면 제목 상태 검사 · surface_title_anchor', '질문 발화 범위 검사 · propriety_question_scope',
    '같은 문맥의 상태 반영 검사 · propriety_callback', '조건 거절 · REJECTED', '조건 충족 · ELIGIBLE',
    '적용 기록 · APPLIED', 'DECODER_GENERAL_NOUN_HIGH_MISSING', 'LITERAL_TITLE_QUESTION_PROOF_BOUND',
    'CONTEXT_ONLY_SAME_NATIVE']) assert.ok(html.includes(text), text);
  assert.match(html, /기록된 진입 수<\/div><div class="value">2</);
  assert.match(html, /첫 거절 코드<\/div><div class="value">DECODER_GENERAL_NOUN_HIGH_MISSING</);
  assert.match(html, /적용 기록 있음<\/div><div class="value">false</);
  assert.match(html, /적용 기록 있음<\/div><div class="value">true</);
  assert.match(html, /기록된 공개 권한<\/div><div class="value">false</);
  assert.match(html, /공개 권한을 부여하지 않습니다/);
  assert.match(html, /최종 품질 승인을 뜻하지 않습니다/);
  assert.equal(JSON.stringify(value), before);
});

test('guard의 마지막 상태와 이전 적용·첫 거절 기록은 서로 덮어쓰지 않는다', () => {
  const labels = {STARTED: '진입 기록', REJECTED: '조건 거절', ELIGIBLE: '조건 충족',
    APPLIED: '적용 기록', NOT_APPLIED: '적용되지 않음', SKIPPED: '건너뜀'};
  for (const [status, label] of Object.entries(labels)) {
    const value = scopeGuardDisplayFixture();
    value.scope_state_guards = [{...value.scope_state_guards[0], status, code: 'LATEST_CODE',
      applied: true, first_rejection: 'EARLIER_REJECTION', calls: 0}];
    const html = scopeGuardStructured(value);
    assert.ok(html.includes(label + ' · ' + status));
    assert.match(html, /마지막 사유 코드<\/div><div class="value">LATEST_CODE</);
    assert.match(html, /첫 거절 코드<\/div><div class="value">EARLIER_REJECTION</);
    assert.match(html, /기록된 진입 수<\/div><div class="value">0</);
    assert.match(html, /적용 기록 있음<\/div><div class="value">true</);
    assert.match(html, /마지막 기록 상태와 별개/);
  }
});

test('guard 미기록·빈 목록·OFF·NOT_AVAILABLE과 TRUNCATED를 적용 성공으로 바꾸지 않는다', () => {
  assert.match(ui.renderContextDiagnostics(undefined), /구조화 진단이 저장되지 않았습니다/);
  for (const status of ['OFF', 'NOT_AVAILABLE', 'TRUNCATED', 'STORED']) {
    for (const guards of [undefined, null, []]) {
      const html = scopeGuardStructured({status, publication_authority: false, scope_state_guards: guards});
      assert.ok(html.includes(status));
      assert.match(html, /저장된 guard 항목이 없습니다/);
      assert.match(html, /미기록만으로 미실행이나 적용 실패를 판단하지 않습니다/);
      assert.doesNotMatch(html, /적용 기록 · APPLIED|조건 충족 · ELIGIBLE/);
    }
  }
  // exporter는 최종 native receipt가 없어도 따로 저장한 guard를 내보낼 수 있다.
  const value = scopeGuardDisplayFixture(); value.status = 'NOT_AVAILABLE';
  value.reason_codes = ['NO_FINAL_NATIVE_RECEIPT'];
  assert.match(scopeGuardStructured(value), /DECODER_GENERAL_NOUN_HIGH_MISSING/);
  value.status = 'TRUNCATED'; value.omitted_counts = {'scope_state_guards.items': 1};
  assert.match(scopeGuardStructured(value), /scope_state_guards.items/);
});

test('guard 알 수 없는 값·잘못된 형식·null·미기록은 원래 차이를 유지한다', () => {
  const value = scopeGuardDisplayFixture();
  value.scope_state_guards = [{gate: 'future_guard', status: 'FUTURE_STATUS', first_rejection: null},
    {gate: 'constructor', status: 'toString', calls: null, applied: null, publication_authority: null}];
  const html = scopeGuardStructured(value);
  for (const text of ['future_guard', 'FUTURE_STATUS', 'constructor', 'toString']) assert.ok(html.includes(text));
  assert.match(html, /기록된 진입 수<\/div><div class="value">미기록</);
  assert.match(html, /적용 기록 있음<\/div><div class="value">null · 산정값 없음</);
  assert.match(html, /기록된 공개 권한<\/div><div class="value">미기록</);
  assert.doesNotMatch(html, /적용 기록 · APPLIED|function Object|function toString/);
  for (const guards of [{status: 'APPLIED'}, 'APPLIED', false]) {
    const bad = scopeGuardStructured({status: 'STORED', scope_state_guards: guards});
    assert.match(bad, /guard 목록 형식이 맞지 않습니다/);
    assert.doesNotMatch(bad, /적용 기록 · APPLIED/);
  }
  assert.match(scopeGuardStructured({status: 'STORED', scope_state_guards: [null, 'APPLIED', [], {}]}),
    /읽을 수 있는 guard 필드가 없는 항목/);
});

test('guard 문자열·객체를 escape하고 표시 상한과 원본 보존을 유지한다', () => {
  const value = scopeGuardDisplayFixture();
  value.scope_state_guards = [{gate: '<img src=x onerror=bad()>', status: '<script>bad()</script>',
    code: {text: '<svg onload=bad()>'}, first_rejection: 'https://example.invalid/<b>',
    calls: 0, applied: false, publication_authority: false}];
  const before = JSON.stringify(value), html = ui.renderContextDiagnostics(value);
  for (const text of ['&lt;img', '&lt;script&gt;', '&lt;svg', '&lt;b&gt;']) assert.ok(html.includes(text));
  assert.doesNotMatch(html, /<img|<script>|<svg|<a\s|href=/);
  assert.equal(JSON.stringify(value), before);
  const many = {status: 'STORED', scope_state_guards: Array.from({length: 25}, (_, i) => ({
    gate: 'synthetic_' + i, status: 'REJECTED', code: 'DISPLAY_CODE_' + i}))};
  const all = ui.renderContextDiagnostics(many), structured = scopeGuardStructured(many);
  assert.match(structured, /앞 24개 guard 항목만 표시/);
  assert.ok(structured.includes('DISPLAY_CODE_23'));
  assert.ok(!structured.includes('DISPLAY_CODE_24'));
  assert.ok(all.includes('DISPLAY_CODE_24'));
});
