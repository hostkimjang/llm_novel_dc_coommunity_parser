/* 저장된 사건 상태를 실제 카드로 표시한다. 제품·모델 의미 판정을 재실행하지 않는다. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const test = require('node:test');
const ui = require('../src/llm_batch/monitor/static/presentation.js');

function fixture(name, expectedSha) {
  const bytes = fs.readFileSync(path.join(__dirname, 'fixtures', name));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), expectedSha);
  return JSON.parse(bytes);
}
const current = fixture('source44_native_ui.json', '4172feb7a4fd4846e84094619e5ef6adf24361479bb5968f05763be93edb048a');
const recorded = fixture('source44_recorded_ui_diagnostics.json', 'ea149187515a66acdabb64fddcc944552443bad1620eafbf1653bc6cf1eb193f');
const labels = ['성립 상태', '성립 근거', '평가 방향', '최종 근거 채택'];
const fields = ['realization', 'realization_source', 'evaluation_polarity', 'final_support'];

function cards(diagnostic) {
  // 마지막 원본 JSON의 텍스트로 카드 표시 검사를 대신할 수 없게 article만 읽는다.
  return [...ui.renderContextDiagnostics(diagnostic).matchAll(/<article class="evidence-card">[\s\S]*?<\/article>/g)]
    .map(match => match[0]).filter(card => card.includes('사건 ID</div>'));
}
function value(card, label) {
  const match = card.match(new RegExp('<div class="label">' + label + '</div><div class="value">([\\s\\S]*?)</div>'));
  assert.ok(match, label + ' 카드 필드 누락');
  return match[1];
}
function synthetic(events) {
  return {status: 'STORED', publication_authority: false,
    ledgers: [{source_id: 'author', source_role: 'author', evaluations: events}]};
}
function frozen(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach(frozen);
  }
  return value;
}

test('실제 44 부분 소비·native 검산·export 결과를 카드에서 어휘 극성과 구분한다', () => {
  assert.equal(current.scope, 'ROOT_REAL_FUNCTION_PARTIAL_SOURCE_CONSUMER_NOT_MODEL_RUN');
  assert.equal(current.native_verify, true);
  assert.equal(current.source_canonical_sha256, '60ab6de7e4b07bce90299a45f1ddddb59a1e733e87669630e26a84f984948b51');
  assert.equal(current.product_module_sha256, 'a71a6d26fe072bf866c4f59aa325675b58bf8bcda634643a7a173ee73ace1877');
  assert.equal(current.root_test_receipt_sha256, '8fcb614968db02a38e1e724620d42336ff3b391694d201719dc2ac227203e8ef');
  const event = current.diagnostic.ledgers.find(ledger => ledger.source_id === 'author').evaluations[0];
  assert.equal(event.actor, 'self');
  assert.equal(event.grammatical_subject.actor, 'self');
  assert.equal(Object.hasOwn(event, 'realization_source'), false);
  const [card] = cards(frozen(current.diagnostic));
  assert.equal(value(card, '서술어'), '좋은');
  assert.equal(value(card, '극성'), 'positive');
  assert.equal(value(card, '성립 상태'), 'embedded');
  assert.equal(value(card, '성립 근거'), '미기록');
  assert.equal(value(card, '평가 방향'), 'pos');
  assert.equal(value(card, '최종 근거 채택'), 'false');
  assert.equal(value(card, '원문 근거'), '다 좋은 마무리는 아니라고 생각해요');
  assert.match(current.identity.reason, /비교 우위와 최종 평가를 구분한다/);
  assert.match(current.notes, /다 좋은 마무리는 아니라고 생각해요/);
});

test('기존 44 저장 진단은 actual과 false를 그대로 표시하고 새 판정으로 덮지 않는다', () => {
  const [card] = cards(frozen(recorded));
  assert.equal(value(card, '발화자'), '마무리');
  assert.equal(value(card, '극성'), 'positive');
  assert.equal(value(card, '성립 상태'), 'actual');
  assert.equal(value(card, '성립 근거'), '미기록');
  assert.equal(value(card, '평가 방향'), 'pos');
  assert.equal(value(card, '최종 근거 채택'), 'false');
});

test('네 필드의 false·null·미기록·빈 문자열·알 수 없는 값은 서로 구분한다', () => {
  for (const [input, expected] of [[false, 'false'], [true, 'true'], [null, 'null · 산정값 없음'],
    [undefined, '미기록'], ['', ''], ['UNKNOWN_FUTURE', 'UNKNOWN_FUTURE']]) {
    const event = {event_id: 'synthetic-value'};
    for (const field of fields) if (input !== undefined) event[field] = input;
    const [card] = cards(synthetic([event]));
    for (const label of labels) assert.equal(value(card, label), expected, label);
  }
});

test('네 필드의 문자열·구조화 값은 기존 escaping을 거쳐 표시한다', () => {
  const unsafe = '<img src=x onerror="alert(1)">&\'test\'';
  const expected = '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#39;test&#39;';
  const event = {event_id: 'synthetic-escaping'};
  for (const field of fields) event[field] = unsafe;
  const [card] = cards(synthetic([event]));
  for (const label of labels) assert.equal(value(card, label), expected);
  assert.doesNotMatch(card, /<img|<script/);
  const [structured] = cards(synthetic([{event_id: 'synthetic-structured', realization_source: {note: '<script>'}}]));
  assert.equal(value(structured, '성립 근거'), '{&quot;note&quot;:&quot;&lt;script&gt;&quot;}');
});

test('같은 화면의 작성자·댓글 사건별 저장 값만 표시하고 지원 여부를 추론하지 않는다', () => {
  // 13·74 실자료의 재생이 아니라 상태 조합 표시만 검사하는 명시 합성 대조다.
  const diagnostic = synthetic([{event_id: 'a', polarity: 'positive', realization: 'embedded',
    realization_source: 'nominal_cue_modifier', evaluation_polarity: 'pos', final_support: false}]);
  diagnostic.ledgers.push({source_id: 'comment:0', source_role: 'comment', evaluations: [
    {event_id: 'b', polarity: 'negative', realization: 'actual', realization_source: 'saved_source',
      evaluation_polarity: 'neg', final_support: true},
    {event_id: 'legacy', polarity: 'positive'},
  ]});
  const result = cards(frozen(diagnostic));
  assert.equal(result.length, 3);
  assert.deepEqual(result.map(card => fields.map((_, i) => value(card, labels[i]))), [
    ['embedded', 'nominal_cue_modifier', 'pos', 'false'], ['actual', 'saved_source', 'neg', 'true'],
    ['미기록', '미기록', '미기록', '미기록'],
  ]);
});

test('이력 반복 렌더링·빈 진단이 이전 행 상태를 물려받거나 원본을 바꾸지 않는다', () => {
  const newBefore = JSON.stringify(current), oldBefore = JSON.stringify(recorded);
  for (let i = 0; i < 2; i++) {
    assert.equal(value(cards(current.diagnostic)[0], '성립 상태'), 'embedded');
    assert.equal(value(cards(recorded)[0], '성립 상태'), 'actual');
    assert.equal(value(cards(synthetic([{event_id: 'missing'}]))[0], '최종 근거 채택'), '미기록');
    assert.match(ui.renderContextDiagnostics(undefined), /구조화 진단이 저장되지 않았습니다/);
    assert.equal(cards({status: 'OFF', ledgers: []}).length, 0);
  }
  assert.equal(JSON.stringify(current), newBefore);
  assert.equal(JSON.stringify(recorded), oldBefore);
});
