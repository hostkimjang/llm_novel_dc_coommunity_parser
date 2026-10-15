/* 저장 결과를 바꾸지 않고 판정 사유와 로그의 표시만 정리한다. */
(function (root) {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const FIELDS = {
    discussion_type: '토론 유형', work_resolution: '작품 식별', grounding_anchor: '작품 단서',
    evidence_type: '근거 유형', title_in_post: '원문에 제목 등장', evidence_bucket: '수집한 근거',
    official_title_evidence: '공식 제목 근거', image_ocr_title_evidence: '이미지 OCR 제목 근거',
    image_ocr_variant: 'OCR 제목 표기 차이', official_search_resolution: '공식 검색으로 확인',
    candidate_count: '후보 수', interpreted_topic: '해석한 주제', total: '합계',
    heretic_url_platform: '플랫폼 작품 URL', decoder_confidence: '해독 신뢰도',
    executed_queries: '실행한 검색', effective_executed_queries: '보정한 검색 횟수',
    degraded_queries: '검색 장애·저하', planned_unique_queries: '계획한 검색', evidence_diversity: '근거 다양성',
    title_resolution: '제목 식별', decision_alignment: '판정 일치',
    is_novel_related: '웹소설 관련 여부', is_resolved_work_discussion: '확정 작품 토론 여부',
    is_relevant: '기존 관련 플래그 (is_relevant)',
    title_resolution_state: '제목 식별 상태', title_resolution_allowed: '제목 확정 허용',
    primary_subject_type: '주요 화제 유형', primary_subject_text: '주요 화제',
    identity_state: '판정 상태', system_state: '시스템 상태',
    promotion_blocked: '제목 확정 차단', hold_unresolved: '미확정 유지',
    hold_without_candidates: '후보 없이 보류', safe_resolved: '안전 확정 상태',
    candidate_ledger_status: '후보 기록 상태', candidate_generation_miss: '후보 생성 누락',
    queries_issued: '검색 요청', accepted: '채택한 결과', raw: '수집한 결과',
    filtered: '제외한 결과', retried: '재시도', cache_hits: '캐시 사용',
    status: '상태', degraded: '검색 저하', upstream_zero: '검색 결과 없음',
    degraded_zero: '검색 저하 중 결과 없음', fallback_recovered: '대체 검색으로 복구',
    unrecovered_degraded: '복구하지 못한 검색 저하',
  };
  const SECTION_TITLES = [
    '판정 요약', '원문 해석', '전문가별 판단', '미확정 사유', '후보 제목', '최종 종합',
    '근거 스코어', '근거 요약', '정합성 교정', '범위 분리', 'LLM 검토',
  ];
  const STAGES = {
    general: '처리 기록', input: '게시글 입력', vlm: '이미지·OCR', orchestrator: '실행 조정',
    fast_path: '빠른 판정', gatekeeper: '입력 분류', discourse: '문맥 해석', search: '검색',
    decoder: '별칭 해독', verifier: '근거 검증', critic: '반론 검토',
    deliberation: '추가 검토', synthesizer: '분석 종합', arbiter: '최종 판정', result: '완료 결과',
  };
  const CATEGORIES = { stage: '진행', llm: 'LLM', search: '검색', json: 'JSON', warning: '주의·오류', result: '결과' };

  function parseReason(text) {
    // 알려진 제목만 인라인에서 분리한다. [이미지 OCR], [E001] 등 본문 인용은 유지한다.
    let value = String(text ?? '').replace(/\r\n?/g, '\n').trim();
    value = value.replace(new RegExp(`\\s*\\[(${SECTION_TITLES.join('|')})\\]\\s*`, 'g'), '\n[$1]\n');
    value = value.replace(/[^\S\n]+(?=-\s+(?:[A-Za-z_][\w]*|[가-힣][가-힣\w ()/·]{0,24})\s*[:=])/g, '\n');
    const sections = [];
    let current;
    for (const raw of value.split('\n')) {
      const line = raw.trim();
      if (!line) continue;
      const heading = line.match(/^\[([^\]\n]{2,60})\]$/);
      if (heading && !/^(?:E\d+|IMG\d+|이미지(?:\s|$))/.test(heading[1])) {
        current = { title: heading[1], lines: [] };
        sections.push(current);
      } else {
        if (!current) { current = { title: '판정 설명', lines: [] }; sections.push(current); }
        current.lines.push(line);
      }
    }
    return sections;
  }

  function renderReasonLine(line) {
    const match = line.match(/^-\s+([^:=]{1,60})\s*[:=]\s*(.*)$/);
    if (!match) return `<p class="reason-line">${esc(line)}</p>`;
    const key = match[1].trim();
    return `<div class="reason-field"><dt title="${esc(key)}">${esc(FIELDS[key] || key)}</dt><dd>${esc(match[2])}</dd></div>`;
  }

  function renderReason(text, { raw = true } = {}) {
    const sections = parseReason(text);
    if (!sections.length) return '<p class="presentation-empty">저장된 판정 사유가 없습니다.</p>';
    const cards = sections.map(section => {
      const important = ['판정 요약', '최종 종합', '미확정 사유'].includes(section.title);
      const content = `<dl class="reason-fields">${section.lines.map(renderReasonLine).join('')}</dl>`;
      const long = section.lines.join('').length > 1000 || section.lines.length > 12;
      return `<section class="reason-card${important ? ' reason-important' : ''}"><h4>${esc(section.title)}</h4>${long
        ? `<details class="reason-more"><summary>상세 내용 펼치기 · ${section.lines.length}개 항목</summary>${content}</details>`
        : content}</section>`;
    }).join('');
    return `<div class="reason-cards">${cards}</div>${raw ? `<details class="raw-record"><summary>판정 사유 원문 보기</summary><pre>${esc(text)}</pre></details>` : ''}`;
  }

  function safeLink(url, label) {
    const value = String(url ?? '');
    return /^https?:\/\//i.test(value)
      ? `<a href="${esc(value)}" target="_blank" rel="noopener noreferrer">${esc(label || value)}</a>`
      : esc(label || value);
  }

  function renderIdentity(identity) {
    const publish = identity.publish_ledger;
    const candidateUrl = publish?.candidate_preservation?.official_url;
    const publicUrl = publish?.public_publish?.official_url;
    const heldCandidateUrl = candidateUrl && candidateUrl !== publicUrl ? candidateUrl : null;
    const groups = [
      ['판정 범위와 확정 상태', ['is_novel_related', 'is_resolved_work_discussion', 'title_resolution_state', 'title_resolution_allowed', 'identity_state', 'primary_subject_type', 'primary_subject_text', 'is_relevant']],
      ['후보 검토 상태', ['candidate_ledger_status', 'candidate_generation_miss', 'promotion_blocked', 'hold_unresolved', 'hold_without_candidates', 'safe_resolved', 'system_state']],
    ];
    let html = groups.map(([title, keys]) => {
      const rows = keys.filter(key => identity[key] !== undefined && identity[key] !== null).map(key =>
        `<div class="detail-kv"><div class="label" title="${key}">${FIELDS[key]}</div><div class="value">${esc(typeof identity[key] === 'object' ? JSON.stringify(identity[key]) : identity[key])}</div></div>`);
      return rows.length ? `<section class="detail-section"><h3 class="detail-section-title">${title}</h3><div class="detail-grid">${rows.join('')}</div></section>` : '';
    }).join('');
    const health = identity.search_health;
    if (health && typeof health === 'object') {
      html += `<section class="detail-section"><h3 class="detail-section-title">검색 상태</h3><div class="detail-grid">${Object.entries(health).map(([key, value]) => `<div class="detail-kv"><div class="label" title="${esc(key)}">${esc(FIELDS[key] || key)}</div><div class="value">${esc(value)}</div></div>`).join('')}</div></section>`;
    }
    for (const [key, title] of [['search_evidence_catalog', '검색 근거'], ['image_evidence_catalog', '이미지·OCR 근거']]) {
      const items = identity[key];
      if (!Array.isArray(items) || !items.length) continue;
      html += `<details class="evidence-list detail-section"><summary>${title} · ${items.length}건</summary>${items.map(item => {
        const url = item.url || item.source_url;
        const label = item.title || item.explicit_work_title || '출처 보기';
        const source = safeLink(url, label);
        const candidateNote = url && url === heldCandidateUrl
          ? '<p class="section-note">검토 출처 · 공식 작품 URL 미확정</p>' : '';
        return `<article class="evidence-card"><h4>${esc(item.eid || '')} ${source}</h4>${candidateNote}<p>${esc(item.snippet || item.ocr_text || item.visual_summary || '저장된 설명이 없습니다.')}</p>${item.query ? `<p class="section-note">검색어: ${esc(item.query)}</p>` : ''}</article>`;
      }).join('')}</details>`;
    }
    const diagnostics = [
      ['후보 검토 기록', ['candidate_ledger', 'candidate_preservation_sources', 'candidate_audit_lint']],
      ['제목 확정 검토', ['promotion_decision', 'promotion_gate_state', 'promotion_gate_evidence']],
      ['출력 점검 기록', ['publish_contract_trace', 'publish_ledger', 'official_title_lint', 'identity_consistency_lint', 'output_consistency_lint']],
    ].map(([title, keys]) => {
      const values = Object.fromEntries(keys.filter(key => identity[key] != null).map(key => [key, identity[key]]));
      return Object.keys(values).length ? `<details class="raw-record"><summary>${title} · JSON</summary><pre>${esc(JSON.stringify(values, null, 2))}</pre></details>` : '';
    }).join('');
    if (diagnostics) html += `<details class="evidence-list detail-section"><summary>상세 진단 기록</summary>${diagnostics}</details>`;
    return html;
  }

  const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const displayValue = value => value === undefined ? '미기록' : value === null ? 'null · 산정값 없음'
    : typeof value === 'object' ? JSON.stringify(value) : String(value);
  const kv = (label, value) => '<div class="detail-kv"><div class="label">' + esc(label)
    + '</div><div class="value">' + esc(displayValue(value)) + '</div></div>';
  const section = (title, content) => '<section class="detail-section"><h3 class="detail-section-title">'
    + esc(title) + '</h3>' + content + '</section>';
  const rawRecord = (title, value) => '<details class="raw-record"><summary>' + esc(title)
    + '</summary><pre>' + esc(JSON.stringify(value, null, 2)) + '</pre></details>';

  function renderExplanation(identity = {}, analysis = {}, fallbackNotes) {
    const reason = typeof identity.reason === 'string' && identity.reason.trim()
      ? identity.reason : Array.isArray(identity.reason_lines)
        ? identity.reason_lines.filter(line => typeof line === 'string').join('\n') : '';
    const notes = analysis.notes ?? fallbackNotes;
    const notesText = typeof notes === 'string' ? notes.trim() : '';
    const notesBody = notesText
      ? '<div class="detail-block" style="white-space:pre-wrap;overflow-wrap:anywhere">' + esc(notesText) + '</div>'
      : '<p class="presentation-empty">저장된 분석 메모가 없습니다.</p>';
    return section('판정 사유', renderReason(reason))
      + section('분석 메모', notesText.length > 1000
        ? '<details class="reason-more"><summary>분석 메모 펼치기</summary>' + notesBody + '</details>' : notesBody);
  }

  function nsfwLabel(value, assessmentStatus) {
    // 새 상태는 생산자가 봉인한 평가 출처다. UI가 OCR/설명/기본 false로 추론하지 않는다.
    if (assessmentStatus !== undefined && assessmentStatus !== null) {
      if (!['MODEL_REPORTED', 'SOURCE_RULE_POSITIVE', 'NOT_EVALUATED'].includes(assessmentStatus))
        return '상태 미확인 · NSFW 여부 미확인';
      if (typeof value !== 'boolean') return '형식 불일치 · NSFW 여부 미확인';
      if (assessmentStatus === 'NOT_EVALUATED') return value === false
        ? '미평가 · NSFW 여부 미확인' : '상태 불일치 · NSFW 여부 미확인';
      if (assessmentStatus === 'SOURCE_RULE_POSITIVE') return value === true
        ? 'true · NSFW 해당 · 규칙 양성' : '상태 불일치 · NSFW 여부 미확인';
      return (value ? 'true · NSFW 해당' : 'false · NSFW 해당 없음') + ' · 모델 보고값';
    }
    // 과거 absent/null 상태는 기존 저장값 표시를 유지하며 평가 완료를 새로 주장하지 않는다.
    if (value === true) return 'true · NSFW 해당';
    if (value === false) return 'false · NSFW 해당 없음';
    return value === undefined || value === null ? '미기록 · 판정 미확인' : '형식 불일치 · 판정 미확인';
  }

  function nsfwReasonLabel(value, assessmentStatus, reason) {
    if (reason === undefined || reason === null) return '평가 사유 미기록';
    const labels = {
      MODEL_BOOLEAN_REPORTED: '모델이 NSFW 여부를 보고했습니다.',
      SOURCE_TEXT_RULE_POSITIVE: '원문 텍스트가 NSFW 규칙에 해당합니다.',
      SOURCE_IMAGE_RULE_POSITIVE: '원문 이미지의 관측 정보가 NSFW 규칙에 해당합니다.',
      NOISE_EARLY_RETURN_NO_MODEL_ASSESSMENT: '작품 분석이 조기 종료되어 모델의 NSFW 평가는 수행되지 않았습니다.',
      NOISE_OUTPUT_WITHOUT_MODEL_ASSESSMENT: '작품 분석에서 제외됐으며 모델의 NSFW 평가값은 없습니다.',
      MODEL_ASSESSMENT_MISSING_OR_INVALID: '모델의 NSFW 평가값이 없거나 형식이 올바르지 않습니다.',
    };
    if (typeof reason !== 'string' || !Object.hasOwn(labels, reason)) return '평가 사유 미확인';
    const expectedStatus = reason === 'MODEL_BOOLEAN_REPORTED' ? 'MODEL_REPORTED'
      : reason.startsWith('SOURCE_') ? 'SOURCE_RULE_POSITIVE' : 'NOT_EVALUATED';
    if (typeof value !== 'boolean' || assessmentStatus !== expectedStatus
      || (expectedStatus === 'SOURCE_RULE_POSITIVE' && value !== true)
      || (expectedStatus === 'NOT_EVALUATED' && value !== false))
      return '평가 사유와 저장 상태가 일치하지 않습니다.';
    return labels[reason];
  }

  function executionSummary(config) {
    const c = object(config), s = object(c.settings);
    if (!Object.keys(c).length) return '실행 설정 미기록';
    return [
      '프로필 ' + displayValue(c.profile),
      'VLM ' + displayValue(object(s.vlm).value),
      'OCR ' + displayValue(object(s.ocr).value),
      '장부 ' + displayValue(object(s.ledger_mode).value),
      '병렬 ' + displayValue(c.requested_parallel) + '/' + displayValue(c.effective_parallel),
    ].join(' · ');
  }

  function runCompletionSummary(summary, artifactKind) {
    const m = object(summary), keys = ['input_post_count', 'completed_count', 'pending_count', 'failed_count', 'flushed_count'];
    const recorded = value => value !== undefined && value !== null;
    const count = value => Number.isSafeInteger(value) && value >= 0;
    const finalized = m.terminal_artifacts_finalized;
    const invalid = keys.some(key => recorded(m[key]) && !count(m[key]))
      || (recorded(finalized) && typeof finalized !== 'boolean')
      || (recorded(m.completed_subset_only) && typeof m.completed_subset_only !== 'boolean');
    if (invalid) return {state: 'UNKNOWN', label: '형식 불일치 · 처리 상태 미확인'};
    // 실패 기록은 종료 여부와 독립이다. 실패가 있어도 처리는 계속될 수 있다.
    if (count(m.failed_count) && m.failed_count > 0)
      return {state: 'FAILURES_RECORDED', label: '실패 기록 있음 · ' + (finalized === true ? '종료 확정' : '종료 미확정')};
    if (artifactKind === 'COMPLETED_SUBSET' || m.completed_subset_only === true)
      return {state: 'PARTIAL', label: '부분 결과 · 전체 실행 완료 아님'};
    if (finalized === false)
      return {state: 'IN_PROGRESS_RECORDED', label: '진행 중으로 기록됨 · 종료 미확정'};
    if (finalized === true) {
      const completeCounts = keys.slice(0, 4).every(key => count(m[key]));
      if (!completeCounts) return {state: 'UNKNOWN', label: '종료 산출물 확정 · 처리 상태 미확인'};
      const done = m.completed_count === m.input_post_count && m.pending_count === 0 && m.failed_count === 0
        && (!recorded(m.flushed_count) || m.flushed_count === m.completed_count);
      return done ? {state: 'COMPLETED', label: '처리 완료'}
        : {state: 'INCOMPLETE', label: '미완료 · 종료 산출물 확정'};
    }
    return {state: 'UNKNOWN', label: '미기록 · 처리 상태 미확인'};
  }

  function historyRunSummary(run) {
    const r = object(run), m = object(r.manifest_summary);
    const completion = { FINAL: '최종 저장', PARTIAL: '부분 저장', UNKNOWN: '완료 상태 미확인', INVALID: '잘못된 기록' };
    return {
      key: r.run_key || r.filename || '',
      title: r.run_id || r.timestamp || r.filename || '실행 ID 미기록',
      path: r.relative_path || r.filename || '경로 미기록',
      completion: (completion[r.completion_status] || '완료 상태 미확인')
        + (Object.keys(m).length ? ' · ' + runCompletionSummary(m, r.artifact_kind).label : ''),
      mode: r.execution_mode && r.execution_mode !== 'UNKNOWN' ? r.execution_mode : 'UNKNOWN · 실행 모드 미확인',
      settings: executionSummary(m.execution_config || r.execution_config),
      artifactKind: r.artifact_kind || 'UNKNOWN',
    };
  }

  function renderHistoryRun(run) {
    const r = object(run), view = historyRunSummary(r);
    const countLabel = r.post_count_source === 'manifest' ? '처리 결과'
      : r.post_count_source === 'result' ? '저장된 결과' : '결과 수';
    return '<button type="button" class="history-run-card w-full text-left p-3 rounded-lg bg-slate-800/50 hover:bg-slate-700/50" data-run-key="'
      + esc(view.key) + '"><span class="block text-sm font-medium">' + esc(view.title)
      + '</span><span class="block text-xs text-slate-400">' + esc(view.path)
      + '</span><span class="block text-xs mt-1">' + esc(view.completion) + ' · ' + esc(view.mode)
      + ' · ' + esc(view.artifactKind === 'COMPLETED_SUBSET' ? '완료 행 부분집합' : view.artifactKind)
      + ' · ' + countLabel + ' ' + esc(displayValue(r.post_count)) + '건 · ' + esc(displayValue(r.size_kb)) + 'KB</span>'
      + '<span class="block text-xs text-slate-400 mt-1">' + esc(view.settings) + '</span></button>';
  }

  function renderExecutionConfig(config, title = '실행 유효 설정') {
    const c = object(config), s = object(c.settings), source = object(c.source);
    if (!Object.keys(c).length) return section(title, '<p class="presentation-empty">이 실행에는 유효 설정 기록이 없습니다.</p>');
    const labels = { vlm: 'VLM', ocr: 'OCR', ledger_mode: '호출 장부', context_diagnostics: '문맥 진단', requested_parallel: '요청 병렬도' };
    let rows = kv('프로필', c.profile) + kv('프로필 출처', c.profile_source);
    for (const [key, label] of Object.entries(labels)) {
      rows += kv(label, object(s[key]).value) + kv(label + ' 설정 출처', object(s[key]).source);
    }
    rows += kv('요청 / 실효 병렬도', displayValue(c.requested_parallel) + ' / ' + displayValue(c.effective_parallel))
      + kv('실행 코드', source.entry_point) + kv('진입점 SHA-256', source.entry_sha256)
      + kv('런타임 소스 SHA-256', source.runtime_source_sha256)
      + kv('대시보드', c.dashboard) + kv('출력 위치', c.output_file)
      + kv('이미지 검토 준비', c.image_review) + kv('프로세스 자원', c.resources)
      + kv('압축 설정', c.compression) + kv('측정 정책', c.measurement);
    if (c.candidate_retrieval_policy) rows += kv('후보 회수 SHADOW 설정', c.candidate_retrieval_policy);
    if (c.candidate_reranker_policy) rows += kv('후보 재정렬 SHADOW 설정', c.candidate_reranker_policy);
    if (c.community_knowledge_policy) rows += kv('커뮤니티 지식 READ_ONLY 설정', c.community_knowledge_policy);
    return section(title, '<p class="section-note">저장된 최종 유효값과 설정 출처입니다.</p><div class="detail-grid">'
      + rows + '</div>' + rawRecord('실행 설정 원본 · JSON', c));
  }

  function renderMetrics(metrics, title) {
    const m = object(metrics);
    return '<h4>' + esc(title) + '</h4><div class="detail-grid">'
      + kv('호출 수', m.expert_calls) + kv('입력 토큰', m.prompt_tokens)
      + kv('출력 토큰', m.completion_tokens) + kv('전체 토큰', m.total_tokens) + '</div>';
  }

  function renderPairedExecution(meta, title = '저부하 비교 실행 · 저장 관측') {
    const m = object(meta), bundle = object(m.paired_execution_observation);
    if (!Object.keys(bundle).length) return '';
    const start = object(bundle.start), end = object(bundle.end);
    const recorded = Object.keys(start).length && Object.keys(end).length;
    let html = '<p class="section-note">' + (recorded ? '시작·종료 관측 저장' : '관측 미완료 · 시작 또는 종료 기록 없음')
      + '. 저장값을 표시하며 정책 검산 통과를 판정하지 않습니다. 실행 중 자원의 연속 유지, 원격 모델 가중치 불변, 비용·품질 개선은 이 화면으로 증명되지 않습니다.</p>';
    for (const [label, observation] of [['START', start], ['END', end]]) {
      const binding = object(observation.binding), resources = object(observation.resources), health = object(observation.health);
      const threads = object(resources.numeric_threads);
      html += '<h4>' + label + '</h4><div class="detail-grid">'
        + kv('관측 시각', observation.observed_at) + kv('비교 구간', binding.arm)
        + kv('실행 ID', binding.run_id) + kv('시도 ID', binding.attempt_id)
        + kv('실제 프로세스 PID', resources.pid) + kv('우선순위 코드', resources.priority_class)
        + kv('CPU 수 / affinity mask', displayValue(resources.logical_cpu_count) + ' / ' + displayValue(resources.affinity_mask))
        + kv('수치 연산 스레드', Object.keys(threads).length === 5 && Object.values(threads).every(value => value === '1') ? '5종 모두 1' : resources.numeric_threads)
        + kv('검색 health 정상 / 실패', displayValue(health.ok_count) + ' / ' + displayValue(health.failure_count))
        + kv('health 관측 시각', health.observed_at) + '</div>';
    }
    html += '<div class="detail-grid">' + kv('결속 정책 SHA-256', start.policy_sha256) + '</div>';
    html += '<p class="section-note">정식 KPI: 별도 paired reader 검산과 실측 자료 필요. REFERENCE_COPY_COST_ONLY는 production 절감률로 사용할 수 없습니다.</p>';
    return section(title, html + rawRecord('저부하 비교 실행 원본 · JSON', {
      paired_execution_observation: bundle, paired_execution_runtime_fields: m.paired_execution_runtime_fields,
    }));
  }

  function storedState(value, labels) {
    return typeof value === 'string' && Object.prototype.hasOwnProperty.call(labels, value)
      ? value + ' · ' + labels[value] : displayValue(value);
  }

  function renderReviewBinding(receipt) {
    return '<div class="detail-grid">' + kv('수령증 모드', receipt.mode)
      + kv('공개 적용', receipt.public_apply) + kv('기록 출처', receipt.authority)
      + kv('실행 시도 ID', receipt.attempt_run_id) + kv('공개 범위 ID', receipt.publication_scope_id)
      + kv('입력 순서', receipt.input_index) + kv('post ID', receipt.post_id)
      + kv('공개 decision ID', receipt.publication_decision_id) + kv('수령증 SHA-256', receipt.receipt_sha256) + '</div>';
  }

  function renderSemanticReview(meta) {
    const m = object(meta), review = object(m.semantic_review_router_receipt);
    const receipt = object(m.semantic_recovery_plan_receipt), plan = object(receipt.plan), query = object(plan.query_plan);
    const note = '<p class="section-note">행에 저장된 검토·계획 수령증입니다. 화면 표시는 독립 검산 통과, 실제 복구 실행 또는 공개 승인을 뜻하지 않습니다.</p>';
    let html = section('행 저장 시점 · 의미 검토', Object.keys(review).length
      ? note + '<div class="detail-grid">' + kv('검토 상태', storedState(review.state, {
        REVIEW_REQUIRED: '검토 필요', NO_REVIEW: '추가 검토 신호 없음',
        NOT_APPLICABLE: '해당 없음', UNKNOWN: '판정 미확인',
      })) + kv('검토 사유', review.trigger_codes) + kv('미확인 사유', review.unknown_reason_codes)
      + '</div>' + renderReviewBinding(review) + rawRecord('의미 검토 원본 · JSON', review)
      : '<p class="presentation-empty">의미 검토 수령증 미기록 · 검토 필요 여부를 추정하지 않습니다.</p>');
    html += section('행 저장 시점 · 복구 계획', Object.keys(receipt).length
      ? note + '<div class="detail-grid">' + kv('계획 상태', storedState(plan.state, {
        HOLD: '보류 · 계획만 기록', NOT_APPLICABLE: '해당 없음', UNKNOWN: '계획 미확인',
      })) + kv('보류 사유', plan.blocker_codes) + kv('작품 역할별 후보 수', plan.relationship_counts)
      + kv('주 대상 식별자 수', plan.primary_identity_count) + kv('매체 처리 계획', plan.media_action)
      + kv('OCR 원문 근거 수', plan.raw_ocr_evidence_count) + kv('검색 목적', query.purposes)
      + kv('계획상 query 실행 허용', query.query_execution_allowed)
      + kv('계획상 query 상한', query.max_queries) + kv('계획에 기록된 검색 상태', query.search_health)
      + kv('계획 수령증의 검색 호출 수', plan.search_calls_executed)
      + kv('계획 수령증의 네트워크 호출 수', plan.network_calls_executed) + '</div>'
      + '<p class="section-note">query_execution_allowed는 PLAN_ONLY 안의 계획 조건입니다. true여도 실제 query 생성·검색·모델 실행을 뜻하지 않습니다.</p>'
      + renderReviewBinding(receipt) + rawRecord('복구 계획 원본 · JSON', receipt)
      : '<p class="presentation-empty">복구 계획 수령증 미기록 · 실행 여부를 추정하지 않습니다.</p>');
    return html;
  }

  function renderRecoveryActivation(manifest) {
    const run = object(manifest);
    const keys = ['schema', 'requested_mode', 'mode', 'public_apply', 'status', 'journal', 'event_count',
      'proposals_observed', 'events_created', 'events_replayed', 'append_errors', 'tail_repair_count', 'error_samples'];
    const saved = Object.fromEntries(keys.map(key => 'recovery_activation_' + key)
      .filter(key => Object.prototype.hasOwnProperty.call(run, key)).map(key => [key, run[key]]));
    if (!Object.keys(saved).length) return section('실행 manifest · 복구 제안 감사 기록',
      '<p class="presentation-empty">복구 제안 감사 기록 미기록 · OFF 또는 실행 완료로 추정하지 않습니다.</p>');
    return section('실행 manifest · 복구 제안 감사 기록',
      '<p class="section-note">선택한 실행의 종료·중간 manifest 기록입니다. AUDIT_ONLY는 제안 기록용이며 실제 복구 실행 권한이 아닙니다. READY는 제안 기록 준비를 뜻합니다.</p>'
      + '<div class="detail-grid">' + kv('요청 모드', run.recovery_activation_requested_mode)
      + kv('기록된 모드', run.recovery_activation_mode)
      + kv('감사 기록 상태', storedState(run.recovery_activation_status, {
        READY: '제안 기록 준비', DISABLED: '비활성',
        SKIPPED_FRESH_MEASUREMENT: 'fresh 측정으로 감사 기록 생략', NO_GO: '제안 기록 불가·오류 확인',
      })) + kv('공개 적용', run.recovery_activation_public_apply)
      + kv('감사 사건 수', run.recovery_activation_event_count)
      + kv('관측 제안 수', run.recovery_activation_proposals_observed)
      + kv('새 기록 수', run.recovery_activation_events_created)
      + kv('기존 기록 재사용 수', run.recovery_activation_events_replayed)
      + kv('기록 오류 수', run.recovery_activation_append_errors)
      + kv('원장 끝부분 수리 수', run.recovery_activation_tail_repair_count)
      + kv('저장된 오류', run.recovery_activation_error_samples) + '</div>'
      + '<p class="section-note">사건·제안 수는 실제 provider 호출 수가 아닙니다. 이 기록만으로 로컬 합성 실행이나 실제 복구 완료를 판정하지 않습니다.</p>'
      + rawRecord('복구 제안 감사 원본 · JSON', saved));
  }

  function recoveryExecutionState(value) {
    return storedState(value, {
      NOT_STARTED: '미시작', COMPLETED_SIMULATION: '로컬 합성 시뮬레이션 완료',
      INCOMPLETE: '미완료', FAILED: '합성 시도 실패', BUDGET_EXHAUSTED: '예산 소진',
      CANCELLED: '취소', NO_PLAN_PROVIDED: '명시 계획 없음 · 실패 아님',
    });
  }

  function renderRecoveryExecution(value) {
    const view = object(value), report = object(view.report);
    const title = '선택 행 · R6 로컬 복구 판독';
    const binding = Object.keys(view).length ? view.binding_status : 'MISSING';
    let html = '<p class="section-note">이 합성 경로의 실제 provider 실행은 미연결입니다. 별도 provider 기록은 전용 구역에서 표시합니다. 로컬 합성 기록은 실제 복구 품질·비용 측정이나 R6 전체 개발 완료를 뜻하지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('파일·대상 결속', storedState(binding, {
        BOUND: '파일·base 결속 확인', MISSING: '판독 기록 미기록',
        NO_PLAN_PROVIDED: '이 행의 명시 계획 없음 · 실패 아님', INVALID: '판독 기록 결속 오류',
      })) + kv('대시보드 확인 범위', view.verification_scope) + kv('결속 사유', view.reason_codes) + '</div>';
    // 결속되지 않은 다른 행/이전 보고서의 상태를 현재 행의 실행 결과로 표시하지 않는다.
    if (binding !== 'BOUND') return section(title, html);
    if (view.verification_scope !== 'FILE_AND_BASE_BINDING_ONLY'
        || report.schema_version !== 'recovery_execution_readback_v1') {
      return section(title, html + '<p class="presentation-empty">판독 스키마 또는 확인 범위 미확인 · 실행 상태를 표시할 수 없습니다.</p>');
    }
    const base = object(report.base), journal = object(report.journal);
    html += '<p class="section-note">BOUND는 파일·base 결속 확인입니다. 아래 검증 상태는 저장 판독자가 남긴 주장입니다. 대시보드가 원장·출력을 독립 재검산하거나 복구를 실행한 결과가 아닙니다.</p>'
      + '<div class="detail-grid">' + kv('저장 판독자의 검증 상태', report.verification_status)
      + kv('저장된 실행 상태', recoveryExecutionState(report.execution_status))
      + kv('실행 모드', report.execution_mode) + kv('자료 종류', report.data_kind)
      + kv('실제 외부 호출 수', report.actual_external_call_count)
      + kv('토큰', report.tokens) + kv('가격', report.price) + kv('정식 KPI', report.formal_kpi_status)
      + kv('공개 적용', report.public_apply) + kv('공개 권한', report.publication_authority)
      + kv('중앙 DB 쓰기', report.central_db_write)
      + kv('전체 입력 수', report.input_count) + kv('명시 계획 대상 수', report.selected_base_count)
      + kv('복구 시도 수', report.attempt_count) + kv('합성 예약 수', report.consumed_simulated_dispatches)
      + kv('소비한 action 수', report.consumed_action_count) + kv('미종결 호출 수', report.open_call_count)
      + kv('최종화 대기 수', report.pending_finalization_count)
      + kv('누적 관측 시간(ms)', report.consumed_elapsed_ms)
      + kv('시간 예산 관측 범위', report.budget_observation_scope)
      + kv('최종화 기록 저장 I/O의 예산 포함', report.finalization_persistence_in_budget) + '</div>';
    if (report.budget_observation_scope === 'THROUGH_ATTEMPT_TERMINAL_DURABLE_READBACK'
        && report.finalization_persistence_in_budget === false) {
      html += '<p class="section-note">시간 예산은 종결 후보의 저장·재판독까지 관측합니다. 마지막 최종화 기록 저장 I/O는 예산에서 제외됩니다.</p>';
    }
    html += '<details class="raw-record"><summary>시도별 종결 후보·최종화</summary>'
      + '<p class="section-note">종결 후보만 저장되고 최종화되지 않은 시도는 미완료입니다. 후보 출력과 최종 출력은 구분합니다.</p>';
    const attempts = Array.isArray(report.attempts) ? report.attempts : [];
    if (!attempts.length) html += '<p class="presentation-empty">저장된 시도 항목이 없습니다.</p>';
    for (const item of attempts) {
      const attempt = object(item);
      html += '<div class="detail-grid">' + kv('복구 시도 ID', attempt.recovery_attempt_id)
        + kv('복구 세션 ID', attempt.recovery_session_id) + kv('시도 상태', recoveryExecutionState(attempt.status))
        + kv('종결 후보 저장', attempt.terminal_recorded)
        + kv('종결 후보 상태', recoveryExecutionState(attempt.terminal_candidate_status))
        + kv('최종화 저장', attempt.finalization_recorded) + kv('시도 사유', attempt.reason_codes)
        + kv('예약 수', attempt.reserved_dispatches) + kv('마지막 관측 시간(ms)', attempt.last_elapsed_ms)
        + kv('후보 출력 참조', attempt.candidate_output) + kv('최종 출력 참조', attempt.output) + '</div>';
    }
    html += '</details><details class="raw-record"><summary>전체 입력의 명시 계획·상태</summary>'
      + '<p class="section-note">NO_PLAN_PROVIDED는 계획이 제공되지 않은 입력입니다. 검토 결과나 실패 판정으로 계산하지 않습니다.</p>';
    for (const item of (Array.isArray(report.input_rows) ? report.input_rows : [])) {
      const row = object(item);
      html += '<div class="detail-grid">' + kv('입력 순서', row.input_index) + kv('post ID', row.post_id)
        + kv('명시 계획 제공', row.plan_provided) + kv('입력 상태', recoveryExecutionState(row.state))
        + kv('입력의 시도 수', row.attempt_count) + '</div>';
    }
    html += '</details><div class="detail-grid">' + kv('base 입력 순서', base.input_index)
      + kv('base post ID', base.post_id) + kv('base 실행 시도 ID', base.base_attempt_run_id)
      + kv('base 공개 범위 ID', base.publication_scope_id)
      + kv('계획 SHA-256', report.plan_sha256) + kv('결속 SHA-256', report.binding_sha256)
      + kv('원장 SHA-256', journal.sha256) + kv('원장 사건 수', journal.event_count)
      + kv('판독 보고서 SHA-256', report.report_sha256) + kv('판독 한계', report.limitations) + '</div>';
    return section(title, html + rawRecord('저장된 R6 판독 보고서 · JSON', report));
  }

  function renderRecoveryProvider(value, context) {
    const view = object(value), report = object(view.report), d = object(context);
    const title = '선택 행 · R6 provider 근거 수집';
    const binding = Object.keys(view).length ? view.binding_status : 'MISSING';
    let html = '<p class="section-note">명시 provider 명령의 저장 기록입니다. 원래 공개 결과는 바꾸지 않으며, 검색 응답만으로 공식 상세 근거나 주역 관계를 확정하지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('파일·대상 결속', storedState(binding, {
        BOUND: '파일·base 결속 확인', MISSING: 'provider 기록 미기록',
        INVALID: 'provider 기록 결속 오류', NO_PLAN_PROVIDED: '이 행의 명시 계획 없음 · 실패 아님',
      })) + kv('대시보드 확인 범위', view.verification_scope) + kv('결속 사유', view.reason_codes) + '</div>';
    if (binding !== 'BOUND') return section(title, html);
    const base = object(report.base), manifest = object(d.run_manifest), run = object(manifest.summary);
    const sha = x => typeof x === 'string' && /^[0-9a-f]{64}$/.test(x);
    const count = x => x === null || (Number.isSafeInteger(x) && x >= 0);
    const receipts = report.request_receipts, rows = report.input_rows;
    const states = ['PROVIDER_EVIDENCE_STORED', 'INCOMPLETE_DISPATCH', 'PROVIDER_REQUEST_FAILED', 'NOT_STARTED'];
    const identifier = x => typeof x === 'string' && x.length > 0 && x.length <= 128 && x.trim() === x
      && !/[\u0000-\u001f]/.test(x);
    const reference = (value, digest, suffix) => Object.keys(object(value)).length === 3
      && Object.keys(value).every(key => ['path', 'sha256', 'bytes'].includes(key))
      && value.path === 'responses/' + digest + suffix && sha(value.sha256)
      && Number.isSafeInteger(value.bytes) && value.bytes >= 0;
    // 성공 문구보다 먼저 요청별 근거·전송 모드·상위 합계를 함께 확인한다.
    const requestsValid = Array.isArray(receipts) && receipts.length <= 1 && receipts.every(value => {
      const row = object(value), calls = row.client_http_invocations, actual = row.actual_external_call_count;
      if (!identifier(row.request_id) || !identifier(row.reservation_id) || !identifier(row.status)
          || !sha(row.request_sha256) || typeof row.finalization_recorded !== 'boolean'
          || !count(calls) || (calls !== null && calls > 1) || !count(actual) || !count(row.observed_response_bytes)) return false;
      if (row.transport_ref === null) {
        if (row.transport_receipt_sha256 !== null || calls !== null || actual !== null
            || row.observed_response_bytes !== null || row.response_ref !== null || row.finalization_recorded) return false;
      } else {
        if (!reference(row.transport_ref, row.request_sha256, '.json') || !sha(row.transport_receipt_sha256)
            || calls === null || row.observed_response_bytes === null
            || actual !== (report.transport_mode === 'TEST_DOUBLE' ? 0 : calls)) return false;
      }
      if (row.response_ref !== null && (!reference(row.response_ref, row.request_sha256, '.bin')
          || row.response_ref.bytes !== row.observed_response_bytes)) return false;
      if (!row.finalization_recorded && row.status !== 'INCOMPLETE_DISPATCH') return false;
      if (row.status === 'SUCCESS' && (!row.finalization_recorded || calls !== 1 || row.response_ref === null)) return false;
      return true;
    });
    const callsTotal = requestsValid && !receipts.some(row => row.client_http_invocations === null)
      ? receipts.reduce((sum, row) => sum + row.client_http_invocations, 0) : null;
    const actualTotal = ['TEST_DOUBLE', 'NOT_STARTED'].includes(report.transport_mode) ? 0 : callsTotal;
    const derivedStatus = !requestsValid ? null : receipts.some(row => !row.finalization_recorded)
      ? 'INCOMPLETE_DISPATCH' : !receipts.length ? 'NOT_STARTED'
      : receipts.every(row => row.status === 'SUCCESS') ? 'PROVIDER_EVIDENCE_STORED' : 'PROVIDER_REQUEST_FAILED';
    const valid = view.verification_scope === 'FILE_AND_BASE_BINDING_ONLY'
      && report.schema_version === 'recovery_provider_report_v1'
      && report.verification_scope === 'SOURCE_JOURNAL_AND_RESPONSE_READBACK'
      && report.guard_status === 'GUARD_NOT_EVALUATED'
      && report.public_apply === false && report.publication_authority === false && report.central_db_write === false
      && report.formal_kpi_status === 'NOT_ESTIMABLE' && report.remote_provider_dispatch_count === null
      && report.remote_provider_dispatch_status === 'UNKNOWN'
      && ['SOURCE_BACKED', 'TEST_SYNTHETIC', 'UNKNOWN'].includes(report.data_kind)
      && ['HTTPX_SINGLE_REQUEST', 'TEST_DOUBLE', 'NOT_STARTED'].includes(report.transport_mode)
      && states.includes(report.execution_status) && sha(report.plan_sha256) && sha(report.report_sha256)
      && count(report.actual_external_call_count) && count(report.client_http_invocations)
      && requestsValid && report.client_http_invocations === callsTotal && report.actual_external_call_count === actualTotal
      && report.execution_status === derivedStatus && (report.transport_mode !== 'NOT_STARTED' || receipts.length === 0)
      && (Number.isSafeInteger(base.post_id) || (typeof base.post_id === 'string' && base.post_id.length > 0))
      && typeof base.publication_scope_id === 'string' && base.publication_scope_id.length > 0
      && manifest.binding_status === 'BOUND' && d.post_id === base.post_id
      && typeof d.post_id === typeof base.post_id
      && typeof base.export_run_id === 'string' && base.export_run_id.length > 0
      && run.run_id === base.export_run_id && run.publication_scope_id === base.publication_scope_id
      && Number.isSafeInteger(base.input_index) && base.input_index > 0
      && Array.isArray(rows) && Number.isSafeInteger(report.input_count) && report.input_count > 0
      && rows.length === report.input_count && base.input_count === report.input_count
      && rows.every((row, i) => object(row).input_index === i + 1
        && row.state === (i + 1 === base.input_index && row.post_id === base.post_id
          ? report.execution_status : 'NO_PLAN_PROVIDED'))
      && rows.some(row => row.input_index === base.input_index && row.post_id === base.post_id)
      && (report.execution_status !== 'PROVIDER_EVIDENCE_STORED' || (receipts.length > 0
        && receipts.every(row => object(row).status === 'SUCCESS' && row.finalization_recorded === true
          && Object.keys(object(row.response_ref)).length > 0)));
    if (!valid) return section(title, html + '<p class="presentation-empty">provider 스키마·현재 행·미평가 조건이 맞지 않아 실행 상태를 표시할 수 없습니다.</p>');
    html += '<p class="section-note">BOUND는 파일·base 결속 확인입니다. 저장 판독자가 원장과 응답을 검산했으며, 이 화면은 HMAC·원장·원시 응답을 재판독하거나 요청을 실행하지 않습니다. 공개 guard 재판정과 실제 복구 품질은 미평가입니다.</p>';
    if (report.transport_mode === 'TEST_DOUBLE' || report.data_kind === 'TEST_SYNTHETIC') {
      html += '<p class="section-note">합성 자료 또는 시험 전송 기록입니다. 실제 자료의 provider 복구 성과가 아닙니다.</p>';
    }
    html += '<div class="detail-grid">' + kv('근거 수집 상태', storedState(report.execution_status, {
      PROVIDER_EVIDENCE_STORED: 'provider 응답 근거 저장', INCOMPLETE_DISPATCH: '발송 여부·종결 미확정',
      PROVIDER_REQUEST_FAILED: 'provider 요청 실패', NOT_STARTED: '미시작',
    })) + kv('공개 guard 상태', report.guard_status) + kv('자료 종류', report.data_kind)
      + kv('전송 모드', report.transport_mode) + kv('실제 외부 호출 수', report.actual_external_call_count)
      + kv('client HTTP 호출 수', report.client_http_invocations)
      + kv('원격 내부 provider 호출 수', report.remote_provider_dispatch_count)
      + kv('원격 내부 호출 관측', report.remote_provider_dispatch_status)
      + kv('공개 적용', report.public_apply) + kv('공개 권한', report.publication_authority)
      + kv('중앙 DB 쓰기', report.central_db_write) + kv('정식 KPI', report.formal_kpi_status)
      + kv('전체 입력 수', report.input_count) + kv('예산 관측', report.budget) + '</div>'
      + '<p class="section-note">MCP HTTP 요청 1회와 원격 bridge 내부 검색 횟수는 다릅니다. null/UNKNOWN은 관측하지 못한 값이며 0회로 계산하지 않습니다.</p>'
      + '<details class="raw-record"><summary>요청별 저장 근거 참조</summary>';
    for (const receipt of receipts) {
      html += '<div class="detail-grid">' + kv('요청 ID', receipt.request_id) + kv('요청 상태', receipt.status)
        + kv('최종화 저장', receipt.finalization_recorded) + kv('client HTTP 호출 수', receipt.client_http_invocations)
        + kv('실제 외부 호출 수', receipt.actual_external_call_count) + kv('응답 bytes', receipt.observed_response_bytes)
        + kv('요청 SHA-256', receipt.request_sha256) + kv('응답 파일 참조', receipt.response_ref)
        + kv('전송 수령증 참조', receipt.transport_ref) + '</div>';
    }
    html += '</details><details class="raw-record"><summary>전체 입력의 명시 계획·상태</summary>';
    for (const row of rows) {
      html += '<div class="detail-grid">' + kv('입력 순서', row.input_index) + kv('post ID', row.post_id)
        + kv('입력 상태', row.state) + '</div>';
    }
    html += '</details><div class="detail-grid">' + kv('원본 export 실행 ID', base.export_run_id)
      + kv('원본 WAL 시도 ID', base.base_attempt_run_id) + kv('계획 SHA-256', report.plan_sha256)
      + kv('보고서 SHA-256', report.report_sha256) + '</div>';
    return section(title, html);
  }

  function renderRecoveryNative(value, data) {
    const view = object(value), d = object(data), manifest = object(d.run_manifest);
    const exported = object(d.recovery_native_export_manifest), run = object(exported.summary);
    const a = object(view.aggregate), base = object(a.base_run);
    const title = 'R6 native 복구 · 별도 판정';
    let html = '<div class="detail-grid">' + kv('저장 집계 연결', view.binding_status || 'MISSING')
      + kv('검산 범위', view.verification_scope) + kv('사유', view.reason_codes) + '</div>';
    if (view.binding_status !== 'BOUND') return section(title, html + '<p class="presentation-empty">'
      + (view.binding_status === 'INVALID' ? '파일·원본 행 결속이 맞지 않아 성공 판정을 표시하지 않습니다.'
        : '현재 실행에 연결된 native 복구 집계가 없습니다. 미기록은 실행 성공이나 실패를 뜻하지 않습니다.') + '</p>');
    const sha = x => typeof x === 'string' && /^[a-f0-9]{64}$/.test(x);
    const count = x => x === null || (Number.isSafeInteger(x) && x >= 0);
    const flags = x => x.public_apply === false && x.publication_authority === false && x.central_db_write === false
      && x.actual_quality_evaluated === false && x.formal_kpi_status === 'NOT_ESTIMABLE';
    const states = ['COMPLETED_NATIVE_IO', 'PROVIDER_EVIDENCE_STORED', 'NOT_EXECUTED', 'SKIPPED', 'INCOMPLETE', 'NOT_AVAILABLE', 'ERROR'];
    const rows = a.rows, totals = object(a.counts);
    const rowsValid = Array.isArray(rows) && rows.length === base.input_count && rows.every((r, i) => {
      if (!r || typeof r !== 'object' || r.input_index !== i + 1 || !flags(r) || !states.includes(r.execution_status)
        || !sha(r.result_sha256) || !((Number.isSafeInteger(r.post_id)) || (typeof r.post_id === 'string' && r.post_id.length))) return false;
      const n = object(r.native), provider = object(r.provider);
      if (r.provider !== null && (provider.guard_status !== 'GUARD_NOT_EVALUATED'
        || !count(provider.client_http_invocations) || !count(provider.actual_external_call_count))) return false;
      if (r.native !== null && (!flags(n) || !sha(n.receipt_sha256) || n.remote_dispatch_count !== null
        || n.remote_dispatch_status !== 'UNKNOWN' || !count(n.client_http_invocations) || !count(n.actual_external_call_count)
        || !['TEST_DOUBLE', 'HTTPX_SINGLE_REQUEST'].includes(n.transport_mode)
        || (n.transport_mode === 'TEST_DOUBLE' ? n.actual_external_call_count !== 0 : n.actual_external_call_count !== n.client_http_invocations))) return false;
      if (['SKIPPED', 'NOT_EXECUTED'].includes(r.execution_status) && (r.provider !== null || r.native !== null)) return false;
      if (r.execution_status === 'PROVIDER_EVIDENCE_STORED' && (provider.execution_status !== 'PROVIDER_EVIDENCE_STORED' || r.native !== null)) return false;
      return r.execution_status === 'COMPLETED_NATIVE_IO'
        ? n.status === 'COMPLETED_NATIVE_IO' && ['PUBLISH', 'HOLD'].includes(n.guard_status)
          && sha(n.publication_scope_id) && n.publication_scope_id !== base.publication_scope_id
        : r.native === null || (n.status !== 'COMPLETED_NATIVE_IO' && n.guard_status === null);
    });
    const selected = rowsValid && Object.prototype.hasOwnProperty.call(d, 'post_id')
      ? rows.filter(r => r.post_id === d.post_id && typeof r.post_id === typeof d.post_id) : null;
    const sumKnown = key => {
      const values = rows.map(r => {
        const record = r.native || (r.execution_status === 'PROVIDER_EVIDENCE_STORED' ? r.provider : null);
        return record ? record[key] : ['SKIPPED', 'NOT_EXECUTED'].includes(r.execution_status) ? 0 : null;
      });
      return values.includes(null) ? null : values.reduce((sum, n) => sum + n, 0);
    };
    const batch = object(a.batch), batchCounts = object(batch.counts), budget = object(batch.budget);
    const batchValid = a.batch === null && a.batch_report_ref === null || (
      a.batch !== null && batch.schema_version === 'recovery_native_batch_summary_v1' && flags(batch)
      && ['COMPLETED', 'INCOMPLETE', 'NOT_EXECUTED'].includes(batch.status)
      && ['TEST_SYNTHETIC', 'SOURCE_BACKED'].includes(batch.data_kind)
      && sha(batch.receipt_sha256) && batch.policy_sha256 === base.policy_sha256
      && Array.isArray(batch.reason_codes) && batch.reason_codes.every(x => typeof x === 'string' && /^[A-Z][A-Z0-9_]{0,127}$/.test(x))
      && (batch.status === 'COMPLETED' ? batch.reason_codes.length === 0 : batch.reason_codes.length > 0)
      && typeof object(a.batch_report_ref).path === 'string' && sha(object(a.batch_report_ref).sha256)
      && Number.isSafeInteger(object(a.batch_report_ref).bytes) && a.batch_report_ref.bytes > 0
      && batchCounts.input_count === base.input_count && batchCounts.RUNNING === 0
      && rowsValid && ['NOT_EXECUTED', 'COMPLETED_NATIVE_IO', 'INCOMPLETE'].every(state =>
        batchCounts[state] === rows.filter(r => r.execution_status === state).length)
      && count(batchCounts.client_http_invocations) && count(batchCounts.actual_external_calls)
      && ['reserved_rows', 'reserved_calls', 'reserved_response_bytes', 'reserved_elapsed_ms'].every(k =>
        Number.isSafeInteger(budget[k]) && budget[k] >= 0)
      && (budget.observed_elapsed_ms === null || typeof budget.observed_elapsed_ms === 'number'
        && Number.isFinite(budget.observed_elapsed_ms) && budget.observed_elapsed_ms >= 0)
      && budget.refunds === 0 && budget.time_scope === 'THROUGH_FINAL_DRAIN_CONTROL_OBSERVATION'
      && budget.report_publication_io_in_time_scope === false && budget.total_ram_bytes === null);
    const bound = rowsValid && flags(a) && a.schema_version === 'recovery_native_dashboard_aggregate_v1'
      && batchValid
      && view.verification_scope === 'FILE_AND_BASE_BINDING_ONLY' && sha(a.aggregate_sha256)
      && sha(base.policy_sha256) && sha(base.publication_scope_id) && exported.binding_status === 'BOUND'
      && run.run_id === base.run_id && run.publication_scope_id === base.publication_scope_id
      && run.input_post_count === base.input_count
      && Number.isSafeInteger(base.input_count) && base.input_count > 0 && totals.input_count === base.input_count
      && states.every(state => object(totals.states)[state] === rows.filter(r => r.execution_status === state).length)
      && count(totals.client_http_invocations) && count(totals.actual_external_call_count)
      && totals.client_http_invocations === sumKnown('client_http_invocations')
      && totals.actual_external_call_count === sumKnown('actual_external_call_count')
      && totals.remote_dispatch_count === null && totals.remote_dispatch_status === 'UNKNOWN'
      && (!selected || (selected.length === 1 && object(view.row).input_index === selected[0].input_index
        && view.row.post_id === selected[0].post_id && view.row.result_sha256 === selected[0].result_sha256));
    if (!bound) return section(title, html + '<p class="presentation-empty">native 스키마·전체 분모·현재 실행/행 결속이 맞지 않아 판정을 표시하지 않습니다.</p>');
    html += '<p class="section-note">BOUND는 파일·원본 판정 결속입니다. GET은 HMAC 키나 실행기를 호출하지 않습니다. native 판정은 별도 scope에 저장된 guard 결과이며 원래 공개 결과를 변경하지 않습니다. provider의 GUARD_NOT_EVALUATED와 구분합니다.</p>'
      + '<div class="detail-grid">' + kv('기본 manifest 결속', manifest.binding_status)
      + kv('현재 export 파일 결속', exported.binding_status) + kv('현재 export 실행 ID', run.run_id)
      + kv('행에 남은 실행 ID', object(d.run_meta).run_id)
      + kv('전체 입력 수', totals.input_count) + kv('상태별 입력 수', totals.states)
      + kv('client HTTP 누적 호출 수', totals.client_http_invocations) + kv('실제 외부 누적 호출 수', totals.actual_external_call_count)
      + kv('원격 내부 호출 수', totals.remote_dispatch_count) + kv('원격 관측', totals.remote_dispatch_status)
      + kv('공개 적용', a.public_apply) + kv('공개 권한', a.publication_authority)
      + kv('실제 품질 평가', a.actual_quality_evaluated) + kv('정식 KPI', a.formal_kpi_status) + '</div>';
    if (a.batch !== null) {
      html += '<div class="detail-grid">' + kv('batch 최종 제어 상태', batch.status)
        + kv('batch 최종 사유', batch.reason_codes) + kv('batch 보고서 원래 계수', batch.counts)
        + kv('예약된 행 수', budget.reserved_rows) + kv('예약된 호출 수', budget.reserved_calls)
        + kv('예약된 응답 바이트', budget.reserved_response_bytes) + kv('예약된 시간 ms', budget.reserved_elapsed_ms)
        + kv('마지막 제어 검사까지 관측한 시간 ms', budget.observed_elapsed_ms)
        + kv('batch 시간 관측 범위', budget.time_scope)
        + kv('보고서 발행 시간 포함', budget.report_publication_io_in_time_scope)
        + kv('batch 보고서 참조', a.batch_report_ref) + '</div>'
        + '<p class="section-note">행별 guard와 batch 최종 제어 상태는 별도입니다. 완료 행이 있어도 마지막 취소·시간 초과는 INCOMPLETE로 남습니다. 예약량은 실제 사용량이 아닙니다.</p>';
    } else html += '<p class="section-note">batch 최종 제어 보고서는 미기록입니다. 행 성공만으로 batch 전체 완료를 추론하지 않습니다.</p>';
    const shown = selected || rows;
    if (manifest.binding_status === 'PARTIAL') html += '<p class="section-note">기존 행의 run 메타데이터 일부는 미기록입니다. 별도 집계가 원본 result·manifest 파일과 typed 행을 다시 결속한 범위로 표시합니다.</p>';
    if (manifest.binding_status === 'MISMATCH') html += '<p class="section-note">기존 행 메타데이터와 현재 export의 불일치는 그대로 유지합니다. WAL 재생 행의 원래 실행 ID를 바꾸지 않으며 native 표시는 별도 검산한 현재 export 파일과 전체 typed 행 결속을 사용합니다.</p>';
    for (const row of shown) {
      const n = object(row.native), p = object(row.provider);
      html += '<div class="detail-grid">' + kv('입력 순서', row.input_index) + kv('post ID', row.post_id)
        + kv('capture 상태', row.capture_status) + kv('복구 실행 상태', row.execution_status) + kv('사유', row.reason_codes)
        + kv('provider 수집 상태', p.execution_status) + kv('provider guard 상태', p.guard_status)
        + kv('provider만의 client 호출 수', p.client_http_invocations) + kv('provider만의 실제 외부 호출 수', p.actual_external_call_count)
        + kv('별도 native guard 판정', row.execution_status === 'COMPLETED_NATIVE_IO' ? n.guard_status : null)
        + kv('별도 publication scope', n.publication_scope_id) + kv('자료 종류', n.data_kind || p.data_kind)
        + kv('전송 모드', n.transport_mode) + kv('native 포함 client 호출 수', n.client_http_invocations)
        + kv('native 포함 실제 외부 호출 수', n.actual_external_call_count) + kv('가격', n.price)
        + kv('시간 관측 범위', n.time_scope) + kv('최종 저장 시간 포함', n.finalization_write_in_time_scope)
        + kv('provider 보고서 참조', row.provider_report_ref) + kv('native 보고서 참조', row.native_receipt_ref) + '</div>';
      if (n.transport_mode === 'TEST_DOUBLE' || n.data_kind === 'TEST_SYNTHETIC' || p.data_kind === 'TEST_SYNTHETIC') {
        html += '<p class="section-note">합성 HTTP mock 기록입니다. 실제 모델·검색·복구 품질 검증이 아닙니다.</p>';
      }
    }
    html += '<p class="section-note">미배정·미실행·불완전 행도 전체 분모에 남습니다. null/UNKNOWN은 미확정이며 0회로 합산하지 않습니다. 모든 R6 기능이나 실제 품질의 완료를 뜻하지 않습니다.</p>';
    return section(title, html);
  }

  function renderRunContext(data) {
    const d = object(data), meta = object(d.run_meta), manifest = object(d.run_manifest);
    const run = object(manifest.summary), rowSummary = object(meta.decision_call_ledger_summary);
    const runSummary = object(run.decision_call_ledger_summary);
    const attempt = object(meta.decision_call_attempt_receipt), measurement = object(meta.decision_call_measurement);
    const trace = object(meta.decision_cost_trace);
    let html = section('호출·측정 기록',
      '<p class="section-note">행 저장 시점과 실행 종료 기록을 따로 표시합니다. 관측 토큰과 정식 비교 KPI는 같은 값이 아닙니다.</p>');
    if (Object.keys(rowSummary).length || Object.keys(attempt).length || Object.keys(measurement).length || Object.keys(trace).length) {
      html += section('행 저장 시점 · 호출 장부',
        '<div class="detail-grid">' + kv('행 연결 상태', attempt.publication_link_status)
        + kv('사용량 출처·상태', rowSummary.usage_status) + kv('측정 모드', measurement.mode)
        + kv('측정 결속', measurement.binding_status) + kv('정식 KPI 상태', rowSummary.actual_kpi_status)
        + kv('정식 KPI 대상 여부', measurement.actual_kpi_eligible) + '</div>'
        + renderMetrics(rowSummary.derived_observation, '행 장부의 관측 사용량')
        + renderMetrics(rowSummary.actual_metrics, '행 장부의 정식 KPI')
        + (Object.keys(trace).length ? '<p class="section-note">별도 비용 trace · '
          + esc(displayValue(trace.measurement_status)) + ' · 행 장부와 집계 범위가 다를 수 있습니다.</p>'
          + renderMetrics(trace, '비용 trace에 기록된 부분 사용량') : '')
        + rawRecord('행 호출·측정 원본 · JSON', {
          decision_call_attempt_receipt: meta.decision_call_attempt_receipt,
          decision_call_ledger: meta.decision_call_ledger,
          decision_call_ledger_summary: meta.decision_call_ledger_summary,
          decision_call_measurement: meta.decision_call_measurement,
          decision_cost_trace: meta.decision_cost_trace,
        }));
    } else html += section('행 저장 시점 · 호출 장부', '<p class="presentation-empty">이 행에는 호출·측정 기록이 없습니다.</p>');
    html += section('실행 manifest · 종료 계측',
      '<div class="detail-grid">' + kv('결과와 manifest 결속', manifest.binding_status)
      + kv('결속 사유', manifest.reason_codes) + kv('실행 ID', run.run_id)
      + kv('완료 상태', runCompletionSummary(run, manifest.artifact_kind).label)
      + kv('종료 산출물 확정', run.terminal_artifacts_finalized) + kv('입력 수', run.input_post_count)
      + kv('처리 결과 수', run.completed_count) + kv('저장된 결과 수', run.flushed_count)
      + kv('저장 대기 수', run.pending_count) + kv('실패 기록 수', run.failed_count)
      + kv('계측 상태', runSummary.instrumentation_status)
      + kv('측정 결속', runSummary.measurement_binding_status) + kv('정식 KPI 상태', runSummary.actual_kpi_status)
      + kv('봉인 행', runSummary.sealed_row_attempt_count) + kv('연결 행', runSummary.linked_row_attempt_count)
      + kv('미종결 호출', runSummary.open_call_count) + '</div>'
      + '<p class="section-note">출처: 선택한 실행의 manifest. 행 저장 당시의 연결 상태를 이 값으로 덮어쓰지 않습니다. '
      + '진행 표시는 마지막 저장 시점이며 현재 프로세스 생존을 확인한 값이 아닙니다. '
      + '저장 대기는 처리 후 순서대로 저장하기를 기다리는 결과 수입니다. 처리 완료는 의미 판정·품질·KPI 승인을 뜻하지 않습니다.</p>'
      + renderMetrics(runSummary.derived_observation, 'manifest의 관측 사용량')
      + renderMetrics(runSummary.actual_metrics, 'manifest의 정식 KPI')
      + (Object.keys(manifest).length ? rawRecord('실행 manifest 요약 · JSON', manifest)
        : '<p class="presentation-empty">이 실행의 manifest 기록을 찾지 못했습니다.</p>'));
    const rowConfig = object(meta.execution_config), runConfig = object(run.execution_config);
    if (Object.keys(rowConfig).length) html += renderExecutionConfig(rowConfig, '행 저장 시점 · 실행 유효 설정');
    if (Object.keys(runConfig).length) html += renderExecutionConfig(runConfig, '실행 manifest · 유효 설정');
    if (!Object.keys(rowConfig).length && !Object.keys(runConfig).length) html += renderExecutionConfig(null);
    html += renderPairedExecution(meta, '행 저장 시점 · 저부하 비교 관측');
    html += renderPairedExecution(run, '실행 manifest · 저부하 비교 관측');
    if (Object.prototype.hasOwnProperty.call(run, 'candidate_calibration_policy')) {
      html += renderCandidateCalibrationPolicy(run.candidate_calibration_policy);
    }
    if (Object.prototype.hasOwnProperty.call(run, 'candidate_inference_policy')) {
      html += renderCandidateInferencePolicy(run.candidate_inference_policy);
    }
    if (Object.prototype.hasOwnProperty.call(run, 'candidate_reranker_semantics_policy')) {
      html += renderCandidateSemanticsPolicy(run.candidate_reranker_semantics_policy, manifest);
    }
    html += renderSemanticReview(meta);
    html += renderRecoveryActivation(run);
    html += renderRecoveryExecution(d.recovery_execution);
    html += renderRecoveryProvider(d.recovery_provider_execution, d);
    html += renderRecoveryNative(d.recovery_native_execution, d);
    return html;
  }

  function renderContextDiagnostics(value) {
    const d = object(value);
    if (!Object.keys(d).length) return section('구조화 문맥·발화 진단',
      '<p class="presentation-empty">이 실행에는 구조화 진단이 저장되지 않았습니다.</p>');
    const projection = object(d.projection);
    let html = '<div class="detail-grid">' + kv('저장 상태', d.status) + kv('스키마', d.schema_version)
      + kv('공개 권한', d.publication_authority) + kv('생략 사유', d.reason_codes)
      + kv('생략 건수', d.omitted_counts) + kv('저장 상한(bytes)', d.max_bytes) + '</div>';
    html += '<p class="section-note">생산 단계에서 저장한 진단입니다. 이 진단은 작품 제목·공식 URL 공개 권한을 부여하지 않습니다.</p>';
    const guards = Array.isArray(d.scope_state_guards) ? d.scope_state_guards : [];
    const gateLabels = {surface_title_anchor: '표면 제목 상태 검사', propriety_question_scope: '질문 발화 범위 검사',
      propriety_callback: '같은 문맥의 상태 반영 검사'};
    const statusLabels = {STARTED: '진입 기록', REJECTED: '조건 거절', ELIGIBLE: '조건 충족',
      APPLIED: '적용 기록', NOT_APPLIED: '적용되지 않음', SKIPPED: '건너뜀'};
    const recordedLabel = (labels, value) => typeof value === 'string' && Object.prototype.hasOwnProperty.call(labels, value)
      ? labels[value] + ' · ' + value : value;
    html += '<div class="scope-state-guards"><h4>상태 보정 guard · 저장 기록</h4>'
      + '<p class="section-note">저장 시점의 진단입니다. 적용 기록은 이전 호출을 포함할 수 있으며 마지막 기록 상태와 별개입니다. '
      + '저장 이후 callback의 전체 호출 집계나 최종 품질 승인을 뜻하지 않습니다.</p>';
    if (!guards.length) html += '<p class="presentation-empty">저장된 guard 항목이 없습니다. 미기록만으로 미실행이나 적용 실패를 판단하지 않습니다.</p>';
    if (d.scope_state_guards != null && !Array.isArray(d.scope_state_guards)) {
      html += '<p class="section-note">guard 목록 형식이 맞지 않습니다. 원본 JSON을 확인하세요.</p>';
    }
    for (const value of guards.slice(0, 24)) {
      const guard = object(value);
      if (!Object.keys(guard).length) {
        html += '<p class="presentation-empty">읽을 수 있는 guard 필드가 없는 항목입니다. 원본 JSON을 확인하세요.</p>';
        continue;
      }
      html += '<article class="evidence-card"><div class="detail-grid">'
        + kv('검사 단계', recordedLabel(gateLabels, guard.gate))
        + kv('마지막 기록 상태', recordedLabel(statusLabels, guard.status)) + kv('마지막 사유 코드', guard.code)
        + kv('기록된 진입 수', guard.calls) + kv('첫 거절 코드', guard.first_rejection)
        + kv('적용 기록 있음', guard.applied) + kv('기록된 공개 권한', guard.publication_authority) + '</div></article>';
    }
    if (guards.length > 24) html += '<p class="section-note">앞 24개 guard 항목만 표시합니다. 나머지는 원본 JSON을 확인하세요.</p>';
    html += '</div>';
    if (Object.keys(projection).length) html += '<div class="detail-grid">'
      + kv('발화 행위', projection.speech_act) + kv('대상 종류', projection.target_kind)
      + kv('대상 표현', projection.target_surface) + kv('대상 원문 위치', projection.target_span)
      + kv('대상 매체', projection.target_media) + kv('요구 조건', projection.request_conditions)
      + kv('작품 역할', projection.work_roles) + kv('관계 근거', projection.work_relation_evidence) + '</div>';
    for (const channel of (Array.isArray(d.channels) ? d.channels : []).map(object)) {
      html += '<details class="raw-record"><summary>저장 필드 · ' + esc(displayValue(channel.field)) + '</summary>'
        + '<div class="detail-block" style="white-space:pre-wrap;overflow-wrap:anywhere">' + esc(displayValue(channel.value))
        + '</div><div class="detail-grid">' + kv('값 종류', channel.value_kind)
        + kv('적용 규칙', channel.rule) + kv('원문 근거 위치', channel.locations) + '</div></details>';
    }
    for (const ledger of (Array.isArray(d.ledgers) ? d.ledgers : []).map(object)) {
      html += '<details class="raw-record"><summary>발화 구조 · ' + esc(displayValue(ledger.source_id))
        + '</summary><div class="detail-grid">' + kv('출처 역할', ledger.source_role) + '</div>';
      for (const event of (Array.isArray(ledger.evaluations) ? ledger.evaluations : []).map(object)) {
        html += '<article class="evidence-card"><div class="detail-grid">'
          + kv('사건 ID', event.event_id) + kv('발화자', event.speaker) + kv('행위자', event.actor)
          + kv('문법상 주어', event.grammatical_subject) + kv('대상과 관계', event.objects)
          + kv('서술어', event.predicate) + kv('극성', event.polarity)
          + kv('성립 상태', event.realization) + kv('성립 근거', event.realization_source)
          + kv('평가 방향', event.evaluation_polarity) + kv('최종 근거 채택', event.final_support)
          + kv('시간 범위', event.temporal_scope)
          + kv('원문 근거', event.evidence_text) + kv('근거 범위', event.assertion_span) + '</div></article>';
      }
      html += rawRecord('주장·출처·관계 그래프 · JSON', {
        sources: ledger.sources, claims: ledger.claims, graph_edges: ledger.graph_edges,
      }) + '</details>';
    }
    const explanation = object(d.explanation);
    if (Object.keys(explanation).length) {
      html += '<div class="detail-grid">' + kv('설명 근거 확인', explanation.supported)
        + kv('미해결', explanation.unresolved) + '</div>';
      for (const proof of (Array.isArray(explanation.proofs) ? explanation.proofs : []).map(object)) {
        html += '<details class="raw-record"><summary>발화 근거 · ' + esc(displayValue(proof.claim_kind))
          + '</summary><div class="detail-grid">' + kv('발화자·주장 주체', proof.claimant)
          + kv('출처', proof.source_id) + kv('원문 위치', proof.raw_path)
          + kv('원문 범위', proof.raw_span) + kv('원문 인용', proof.sourcequote)
          + kv('적용 규칙', proof.rule) + '</div></details>';
      }
    }
    return section('구조화 문맥·발화 진단', html + rawRecord('구조화 진단 원본 · JSON', d));
  }

  function renderCandidateRetrieval(value) {
    const d = object(value);
    if (!Object.keys(d).length) return '';
    let html = '<p class="section-note">고정 작품 자료의 후보 회수 관측입니다. 기존 제목 판정과 공개 권한에는 반영하지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('관측 모드', d.mode) + kv('상태', d.status)
      + kv('사유', d.reason_codes) + kv('게시글 ID', d.post_id)
      + kv('자료 구분', object(d.policy).data_kind) + kv('출처 독립 검증', object(d.policy).source_refs_independently_verified)
      + kv('corpus SHA-256', d.corpus_sha256) + kv('원문 query SHA-256', d.query_sha256)
      + kv('처리 시간(ms)', d.latency_ms) + kv('공개 권한', d.publication_authority)
      + kv('실행·행 결속', d.binding) + '</div>';
    const candidates = Array.isArray(d.ranked_candidates) ? d.ranked_candidates : [];
    if (!candidates.length) html += '<p class="presentation-empty">저장된 양수 점수 후보가 없습니다. 작품 없음(NIL) 판정을 뜻하지 않습니다.</p>';
    for (const [index, value] of candidates.slice(0, 100).entries()) {
      const hit = object(value);
      html += '<details class="raw-record"><summary>' + esc(index + 1) + ' · '
        + esc(displayValue(hit.title)) + '</summary><div class="detail-grid">'
        + kv('고정 후보 ID', hit.corpus_candidate_id) + kv('회수 점수', hit.score)
        + kv('작품 ID', hit.work_id) + kv('판본 ID', hit.edition_id) + kv('매체', hit.media_type)
        + kv('출처', hit.source_refs) + '</div></details>';
    }
    return section('작품 후보 회수 · SHADOW', html + rawRecord('후보 관측 원본 · JSON', d));
  }

  function renderCandidateReranker(value) {
    const d = object(value);
    if (!Object.keys(d).length) return '';
    let html = '<p class="section-note">고정 후보의 점수와 순서만 관측합니다. 학습 파라미터가 있어도 실제 자료의 성능 검증을 뜻하지 않습니다. 점수는 교정된 확률이나 작품 없음(NIL) 판정이 아닙니다.</p>'
      + '<div class="detail-grid">' + kv('관측 모드', d.mode) + kv('상태', d.status) + kv('사유', d.reason_codes)
      + kv('자료 구분', d.data_kind) + kv('학습 상태', d.training_status) + kv('학습 파라미터 사용 가능', d.actual_model_available)
      + kv('점수화 방식', d.backend) + kv('모델 종류', d.model_kind) + kv('모델 품질 검증', d.model_quality_status)
      + kv('학습 모델 SHA-256', d.model_sha256)
      + kv('후보 생성 상태', d.generation_status) + kv('후보 ID 종류', d.candidate_namespace)
      + kv('CandidateOption 대응', d.candidate_option_bridge_status) + kv('확률 상태', d.probability_status)
      + kv('공개 권한', d.publication_authority) + kv('판정 반영', d.public_apply)
      + kv('scorer SHA-256', d.scorer_sha256) + kv('manifest SHA-256', d.model_manifest_sha256)
      + kv('원문 query SHA-256', d.query_sha256) + kv('고정 입력 SHA-256', d.input_sha256)
      + kv('후보 생성 SHA-256', d.generation_sha256) + kv('실행·행 결속', d.binding) + '</div>';
    if (d.backend === 'NIL_AUGMENTED_LINEAR_V1') {
      html += '<p class="section-note">NIL 학습 점수도 미교정 원시 점수입니다. 작품 없음의 확률이나 최종 판정으로 사용하지 않습니다.</p>'
        + '<div class="detail-grid">' + kv('NIL 학습 파라미터 사용 가능', d.nil_head_available)
        + kv('NIL 원시 점수', d.nil_score) + kv('고정 사건 순서·원시 점수', d.event_logits)
        + kv('기존 후보 모델 SHA-256', d.candidate_ranker_model_sha256) + '</div>';
    }
    if (Object.prototype.hasOwnProperty.call(d, 'semantic_input_required')) {
      html += '<div class="detail-grid">' + kv('의미 입력 필수', d.semantic_input_required)
        + kv('학습 특징 스키마', d.feature_schema) + kv('의미 특징 계약 SHA-256', d.semantic_contract_sha256)
        + kv('의미 정책 SHA-256', d.semantic_policy_sha256) + kv('의미 입력 SHA-256', d.semantic_input_sha256)
        + kv('점수기의 의미 입력 소비 기록', d.semantic_consumption) + '</div>';
    }
    const roles = object(d.preselection_role_producer);
    if (Object.keys(roles).length) {
      html += '<p class="section-note">이 scorer 입력의 v1 제목 출현 관측은 MENTIONED만 기록합니다. 별도 의미 역할 관측은 이 점수·교정 입력에 반영하지 않습니다.</p>'
        + '<div class="detail-grid">' + kv('선택 전 역할 관측 상태', roles.status)
        + kv('역할 관측 사유', roles.reason_codes) + kv('역할 관측 집계', roles.counts)
        + kv('역할 관측 정책 SHA-256', roles.policy_sha256)
        + kv('역할 관측 입력 SHA-256', roles.frozen_view_sha256) + '</div>';
    }
    const ranked = Array.isArray(d.ranked_candidates) ? d.ranked_candidates : [];
    if (!ranked.length) html += '<p class="presentation-empty">저장된 재정렬 점수가 없습니다. 위 상태와 사유를 확인하세요.</p>';
    for (const [index, item] of ranked.slice(0, 20).entries()) {
      const candidate = object(item);
      html += '<article class="evidence-card"><div class="detail-grid">' + kv('관측 순위', index + 1)
        + kv('고정 후보 ID', candidate.candidate_id) + kv('원시 점수', candidate.score) + '</div></article>';
    }
    const observed = Array.isArray(d.candidate_observations) ? d.candidate_observations : [];
    for (const value of observed.slice(0, 20)) {
      const candidate = object(value);
      if (Array.isArray(candidate.role_observations) && candidate.role_observations.length) {
        html += '<details class="raw-record"><summary>원문 역할 관측 · ' + esc(displayValue(candidate.candidate_id))
          + '</summary><div class="detail-grid">' + kv('역할·원문 위치', candidate.role_observations) + '</div></details>';
      }
    }
    return section('고정 후보 재정렬 · SHADOW', html + rawRecord('재정렬 관측 원본 · JSON', d));
  }

  function renderCandidateSemanticsPolicy(value, manifestValue) {
    const title = '실행 manifest · 선행 의미 역할 정책', d = object(value), manifest = object(manifestValue);
    const policy = object(d.policy);
    if (manifest.binding_status !== 'BOUND' && manifest.binding_status !== 'PARTIAL') {
      return section(title, '<p class="presentation-empty">manifest 결속이 확인되지 않아 의미 역할 정책을 행에 연결하지 않습니다.</p>'
        + '<div class="detail-grid">' + kv('manifest 결속', manifest.binding_status)
        + kv('결속 사유', manifest.reason_codes) + '</div>');
    }
    return section(title,
      '<p class="section-note">실행에 저장된 정책입니다. 행별 관측 성공이나 모델·교정 입력 소비를 뜻하지 않습니다. PARTIAL은 실행·공개 범위 좌표가 일부 미기록인 상태입니다.</p>'
      + '<div class="detail-grid">' + kv('manifest 결속', manifest.binding_status)
      + kv('결속 사유', manifest.reason_codes) + kv('관측 모드', d.mode)
      + kv('정책 스키마', d.schema_version) + kv('producer 스키마', d.producer_schema)
      + kv('적용 범위', policy.semantic_scope) + kv('관측 권한의 범위', policy.authority)
      + kv('관측 정책 SHA-256', d.policy_sha256) + kv('원문 parser 계약 SHA-256', policy.parser_contract_sha256)
      + kv('별칭 근거 bundle SHA-256', d.alias_bundle_sha256)
      + kv('정적 별칭 설정 SHA-256 · 행 관측과 별도', d.alias_evidence_sha256)
      + kv('점수 소비 상태', d.score_consumption_status) + kv('실제 품질 평가', d.actual_quality_evaluated)
      + kv('설정 출처', d.setting_sources)
      + kv('공개 권한', d.publication_authority) + kv('판정 반영', d.public_apply)
      + kv('중앙 DB 쓰기', d.central_db_write) + '</div>' + rawRecord('저장된 의미 역할 정책 · JSON', value));
  }

  function renderCandidateSemantics(value, manifestValue) {
    const title = '선택 전 의미 역할 · 별도 SHADOW', d = object(value), manifest = object(manifestValue);
    if (!Object.keys(d).length) return section(title,
      '<p class="presentation-empty">이 행에는 선행 의미 역할 관측이 저장되지 않았습니다.</p>');
    const observation = object(d.observation), consumption = object(d.consumption);
    let html = '<p class="section-note">원문과 고정 후보에 연결된 역할 관측입니다. PRIMARY는 원문의 논의 대상, PREVIOUS는 작가의 전작이며 독자의 과거 독서 이력이 아닙니다. 관측은 정답·최종 작품 선택·공개 권한을 부여하지 않습니다. 이 화면은 저장값을 표시하며 producer를 재실행하지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('관측 모드', d.mode) + kv('실행 관측 상태', d.status)
      + kv('사유', d.reason_codes) + kv('게시글 ID', d.post_id) + kv('스키마', d.schema_version)
      + kv('실행·행 결속', d.binding) + kv('공개 권한', d.publication_authority)
      + kv('판정 반영', d.public_apply) + kv('중앙 DB 쓰기', d.central_db_write)
      + kv('runtime receipt SHA-256', d.receipt_sha256) + '</div>';
    if (manifest.binding_status === 'MISMATCH') {
      html += '<p class="section-note">manifest 실행·공개 범위 결속 불일치입니다. 아래 행 저장 관측은 보존하되 manifest 정책과 같은 실행의 기록으로 연결하지 않습니다.</p>';
    }
    const notConsumed = ['OBSERVED_NOT_CONSUMED', 'NOT_CONSUMED_OBSERVATION_FAILED', 'NOT_EXECUTED', 'NOT_AVAILABLE'].includes(consumption.status)
      && consumption.scorer_input_applied === false && consumption.calibration_input_applied === false;
    const isSha = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
    const semanticConsumer = d.schema_version === 'candidate_reranker_semantics_runtime_v2'
      && d.mode === 'SHADOW'
      && consumption.schema_version === 'candidate_reranker_semantic_consumption_v1'
      && ['SCORED', 'BACKEND_FAILED', 'INPUT_BOUND_NOT_SCORED', 'NOT_CONSUMED', 'OUTPUT_LIMIT_EXCEEDED'].includes(consumption.status)
      && typeof consumption.input_validated === 'boolean' && typeof consumption.backend_invoked === 'boolean'
      && typeof consumption.score_produced === 'boolean' && typeof consumption.calibration_input_applied === 'boolean'
      && consumption.scorer_input_applied === consumption.backend_invoked
      && (!consumption.backend_invoked || consumption.input_validated)
      && (!consumption.input_validated || (['OBSERVED', 'NO_MATCH', 'AMBIGUOUS'].includes(d.status)
        && observation.schema_version === 'candidate_preselection_semantics_v2' && observation.status === d.status))
      && (consumption.score_produced === (consumption.status === 'SCORED'))
      && (!consumption.score_produced || consumption.backend_invoked)
      && (!consumption.calibration_input_applied || consumption.score_produced)
      && (consumption.status !== 'BACKEND_FAILED' || consumption.backend_invoked)
      && (consumption.status !== 'INPUT_BOUND_NOT_SCORED' || (consumption.input_validated && !consumption.backend_invoked))
      && (consumption.status !== 'NOT_CONSUMED' || (!consumption.input_validated && !consumption.backend_invoked))
      && ['semantic_contract_sha256', 'semantic_policy_sha256', 'score_receipt_sha256', 'model_sha256', 'scorer_sha256'].every(k => isSha(consumption[k]))
      && (consumption.input_validated
        ? ['semantic_input_sha256', 'semantic_observation_sha256', 'scorer_input_sha256'].every(k => isSha(consumption[k]))
        : ['semantic_input_sha256', 'semantic_observation_sha256', 'scorer_input_sha256'].every(k => consumption[k] === null));
    html += '<p class="section-note">' + (semanticConsumer
      ? (consumption.score_produced
        ? '의미 특징을 실제 점수 입력에 사용했습니다. 교정 입력 적용은 별도 저장값을 확인하세요. 실제 자료 품질 수용을 뜻하지 않습니다.'
        : consumption.backend_invoked
          ? '의미 특징을 점수기에 전달했으나 점수 생성은 완료되지 않았습니다.'
          : '의미 특징의 점수기 호출은 실행되지 않았습니다. 입력 검산과 미실행 사유를 확인하세요.')
      : notConsumed
      ? '점수·교정 입력 미사용 · 역할 정책과 학습 모델의 결속이 아직 연결되지 않았습니다. 관측 실행 상태는 위 기록을 따로 확인하세요.'
      : '점수·교정 입력 소비 계약 미확인 · 미기록이나 다른 값을 미사용 또는 사용 완료로 보충하지 않습니다.') + '</p>'
      + '<div class="detail-grid">' + kv('소비 상태', consumption.status)
      + kv('scorer 입력 적용', consumption.scorer_input_applied)
      + kv('교정 입력 적용', consumption.calibration_input_applied) + kv('소비 사유', consumption.reason_codes)
      + kv(semanticConsumer ? '실제 scorer 입력 SHA-256' : '기존 scorer 입력 SHA-256', consumption.scorer_input_sha256) + '</div>';
    if (d.schema_version === 'candidate_reranker_semantics_runtime_v2') {
      html += '<div class="detail-grid">' + kv('입력 검산', consumption.input_validated)
        + kv('점수기 호출', consumption.backend_invoked) + kv('점수 생성', consumption.score_produced)
        + kv('의미 입력 SHA-256', consumption.semantic_input_sha256)
        + kv('의미 특징 계약 SHA-256', consumption.semantic_contract_sha256)
        + kv('소비한 관측 SHA-256', consumption.semantic_observation_sha256)
        + kv('소비 정책 SHA-256', consumption.semantic_policy_sha256)
        + kv('점수 receipt SHA-256', consumption.score_receipt_sha256)
        + kv('학습 모델 SHA-256', consumption.model_sha256) + kv('점수기 SHA-256', consumption.scorer_sha256) + '</div>';
    }
    const observed = ['candidate_reranker_semantics_runtime_v1', 'candidate_reranker_semantics_runtime_v2'].includes(d.schema_version) && d.mode === 'SHADOW'
      && ['OBSERVED', 'NO_MATCH', 'AMBIGUOUS'].includes(d.status)
      && observation.schema_version === 'candidate_preselection_semantics_v2' && observation.status === d.status;
    if (observed) {
      const counts = object(observation.counts), aliases = object(observation.alias_validation);
      html += '<div class="detail-grid">' + kv('producer 관측 상태', observation.status)
        + kv('producer 사유', observation.reason_codes)
        + kv('주요 논의 대상 · PRIMARY', counts.primary) + kv('작가의 전작 · PREVIOUS', counts.previous)
        + kv('비교 기준작 · COMPARISON', counts.comparison) + kv('제목·검증 별칭 출현 · MENTIONED', counts.mentioned)
        + kv('미결합 관측 수', counts.unresolved) + kv('검증 별칭 출현 수', counts.alias_observations)
        + kv('관측 집계 원본', observation.counts) + kv('관측 정책 SHA-256', observation.policy_sha256)
        + kv('원문 parser 계약 SHA-256', observation.parser_contract_sha256)
        + kv('파싱된 source-view SHA-256 · 원본 파일 SHA 아님', observation.source_view_sha256)
        + kv('query SHA-256', observation.query_sha256) + kv('관측 전 view SHA-256', observation.input_frozen_view_sha256)
        + kv(d.schema_version === 'candidate_reranker_semantics_runtime_v1'
          ? '관측 후 view SHA-256 · 모델 입력 아님' : '관측 후 view SHA-256 · 실제 소비는 별도 기록', observation.frozen_view_sha256)
        + kv('고정 후보 ID·순서 SHA-256', observation.candidate_ids_sha256)
        + kv('producer 점수 소비 상태', observation.score_consumption_status)
        + kv('별칭 근거 SHA-256', observation.alias_evidence_sha256)
        + kv('관측 receipt SHA-256', observation.receipt_sha256) + '</div>'
        + '<p class="section-note">별칭 근거가 null이면 검증된 별칭 사용을 뜻하지 않습니다. 합성 근거와 source-backed 근거를 구분하며, 갤·갤러리라는 표면만으로 현실 커뮤니티나 작품을 단정하지 않습니다.</p>';
      if (Object.keys(aliases).length) {
        html += '<details class="raw-record"><summary>별칭 검산 · 출처 권한과 자료 구분</summary>'
          + '<p class="section-note">검토 권한은 원문 선언입니다. 관계의 진실·검토자 신원을 이 화면에서 인증하지 않습니다.</p>'
          + '<div class="detail-grid">' + kv('별칭 결속 상태', aliases.status) + kv('별칭 결속 사유', aliases.reason_codes)
          + kv('별칭 자료 구분', aliases.data_kind) + kv('별칭 관측 집계', aliases.counts)
          + kv('별칭 정책 SHA-256', aliases.policy_sha256) + kv('snapshot SHA-256', aliases.snapshot_sha256)
          + kv('corpus SHA-256', aliases.corpus_sha256) + kv('별칭 receipt SHA-256', aliases.receipt_sha256)
          + kv('별칭 결속·검토 권한·관계 근거', aliases.bindings) + kv('별칭 미결합 사유', aliases.unresolved)
          + '</div></details>';
      } else html += '<div class="detail-grid">' + kv('별칭 검산·출처 권한·자료 구분', observation.alias_validation) + '</div>';
      const rows = Array.isArray(observation.observations) ? observation.observations : [];
      for (const value of rows.slice(0, 32)) {
        const row = object(value);
        html += '<details class="raw-record"><summary>원문 역할 · ' + esc(displayValue(row.role)) + ' · '
          + esc(displayValue(row.candidate_id)) + '</summary><div class="detail-grid">'
          + kv('고정 후보 ID', row.candidate_id) + kv('원문 역할', row.role) + kv('출현 종류', row.mention_kind)
          + kv('제목·별칭 원문 위치', row.mention) + kv('관계 단서 원문 위치', row.relation_cues)
          + kv('관계 상대 원문 위치', row.related_mentions) + kv('화자', row.speaker)
          + kv('단언 상태', row.assertion) + kv('적용 규칙', row.rule_id)
          + kv('별칭 근거 ID', row.alias_evidence_ids) + '</div></details>';
      }
      if (rows.length > 32) html += '<p class="section-note">상세 카드 표시 상한 32개를 넘었습니다. 전체 관측은 아래 저장 원본에서 확인하세요.</p>';
      html += '<details class="raw-record"><summary>모호성·부정·전언 등 미결합 근거</summary><div class="detail-grid">'
        + kv('미결합 목록', observation.unresolved) + '</div></details>';
    } else {
      html += '<p class="presentation-empty">구조화 역할 표시 대상이 아닙니다. 미실행·오류·상한 초과·미기록과 알 수 없는 스키마를 관측 성공이나 역할 0건으로 바꾸지 않습니다.</p>'
        + '<div class="detail-grid">' + kv('저장된 producer payload', d.observation) + '</div>';
    }
    return section(title, html + rawRecord('저장된 의미 역할 관측 원본 · JSON', d));
  }

  function renderCandidateSemanticsCapture(value) {
    const title = '의미 역할 capture · 저장 참조', d = object(value), artifact = object(d.artifact);
    if (!Object.keys(d).length) return section(title,
      '<p class="presentation-empty">이 행에는 의미 역할 capture 참조가 저장되지 않았습니다.</p>');
    return section(title,
      '<p class="section-note">별도 의미 관측의 재생용 저장 참조입니다. 저장 성공은 모델 입력 적용이나 학습·정답 배정을 뜻하지 않습니다. 파일 경로는 정보만 표시하며 화면에서 파일을 읽지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('스키마', d.schema_version) + kv('관측 모드', d.mode) + kv('capture 상태', d.status)
      + kv('사유', d.reason_codes) + kv('게시글 ID', d.post_id) + kv('파일 참조', d.artifact)
      + kv('학습 준비 상태', d.training_readiness)
      + kv('저장 경로 · 정보만 표시', artifact.path) + kv('파일 SHA-256', artifact.sha256)
      + kv('파일 바이트 수', artifact.bytes) + kv('관측 객체 전체 SHA-256 · receipt self SHA와 별도', d.observation_sha256)
      + kv('결속된 capture SHA-256', d.capture_sha256) + kv('입력 snapshot SHA-256', d.input_snapshot_sha256)
      + kv('실행·행 결속', d.binding) + kv('공개 권한', d.publication_authority)
      + kv('판정 반영', d.public_apply) + kv('중앙 DB 쓰기', d.central_db_write)
      + kv('capture receipt SHA-256', d.receipt_sha256) + '</div>'
      + rawRecord('저장된 의미 역할 capture 참조 · JSON', d));
  }

  function renderCandidateInferencePolicy(value) {
    const d = object(value);
    return section('실행 manifest · 일반 입력 교정 정책',
      '<p class="section-note">고정 R2 corpus와 학습 모델에 연결한 일반 입력 SHADOW 정책입니다. 정책 로드는 실행·정답 검토·실제 품질 평가 완료를 뜻하지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('관측 모드', d.mode) + kv('정책 상태', d.status)
      + kv('적용 범위', d.scope) + kv('사유', d.reason_codes) + kv('자료 구분', d.data_kind)
      + kv('bundle SHA-256', d.bundle_sha256) + kv('corpus SHA-256', d.corpus_sha256)
      + kv('고정 교정 정책', d.calibration) + kv('공개 권한', d.publication_authority)
      + kv('실제 품질 평가', d.actual_quality_evaluated) + '</div>'
      + rawRecord('저장된 일반 입력 교정 정책 · JSON', d));
  }

  function renderCandidateInference(value, capture, context) {
    const d = object(value), ref = object(capture), receipt = object(d.inference), artifact = object(ref.artifact);
    const current = object(context), manifest = object(current.run_manifest), run = object(manifest.summary);
    const runPolicy = object(run.candidate_inference_policy), calibration = object(runPolicy.calibration);
    const title = '일반 입력 후보·NIL · 고정 교정 SHADOW';
    if (!Object.keys(d).length && !Object.keys(ref).length) return section(title,
      '<p class="presentation-empty">이 행에는 일반 입력 교정 관측이 저장되지 않았습니다.</p>');
    let html = '<p class="section-note">현재 원문에서 회수한 고정 corpus 후보와 NIL의 관측입니다. FROZEN 평가 배정이나 실제 정확도 보증이 아닙니다. NIL 제안으로 작품 없음의 최종 판정을 추론하지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('관측 상태', d.status) + kv('사유', d.reason_codes)
      + kv('고정 모델 수치 재생 검산', d.score_replay_verified) + kv('검산 범위', d.verification_scope)
      + kv('자료 구분', receipt.data_kind) + kv('확률 범위', receipt.probability_scope)
      + kv('원문 게시글 ID', d.post_id) + kv('정답 상태', receipt.truth_status)
      + kv('실제 품질 평가', receipt.actual_quality_evaluated) + kv('capture 저장 상태', ref.status)
      + kv('저장 경로 · 정보만 표시', artifact.path) + kv('파일 SHA-256', artifact.sha256)
      + kv('파일 바이트 수', artifact.bytes) + kv('입력 snapshot SHA-256', d.input_snapshot_sha256)
      + kv('R2 graph SHA-256', d.graph_sha256) + kv('capture SHA-256', d.capture_sha256)
      + kv('bundle SHA-256', d.bundle_sha256) + kv('교정 artifact SHA-256', receipt.calibration_artifact_sha256)
      + kv('모델 SHA-256', receipt.model_sha256) + kv('고정 온도', receipt.temperature)
      + kv('실행·행 결속', d.binding) + kv('공개 권한', d.publication_authority)
      + kv('판정 반영', d.public_apply) + kv('동작 적용', d.action_applied) + '</div>';
    const hash = x => typeof x === 'string' && /^[0-9a-f]{64}$/.test(x);
    const flags = x => ['publication_authority', 'public_apply', 'central_db_write', 'action_applied'].every(k => x[k] === false);
    const probabilities = receipt.event_probabilities;
    const binding = object(d.binding), refBinding = object(ref.binding);
    const bindingKeys = ['run_id', 'input_index', 'post_id', 'attempt_id', 'publication_scope_id', 'scope'];
    const bound = d.schema_version === 'candidate_reranker_inference_runtime_v1' && d.mode === 'SHADOW'
      && d.status === 'TEMPERATURE_APPLIED_BOUND_INFERENCE' && d.score_replay_verified === true
      && d.verification_scope === 'CURRENT_SOURCE_R2_MODEL_REPLAY_AND_FITTED_TEMPERATURE'
      && receipt.schema_version === 'candidate_inference_temperature_receipt_v1' && receipt.mode === 'SHADOW'
      && receipt.status === d.status && receipt.scope === 'GENERAL_INPUT_SHADOW'
      && receipt.probability_scope === 'BOUNDED_PINNED_R2_CORPUS' && receipt.post_id === d.post_id
      && receipt.evaluation_split === null && receipt.actual_quality_evaluated === false
      && Number.isFinite(receipt.temperature) && receipt.temperature > 0
      && manifest.binding_status === 'BOUND' && current.post_id === d.post_id
      && run.run_id === binding.run_id && run.publication_scope_id === binding.publication_scope_id
      && runPolicy.schema_version === 'candidate_inference_policy_v1' && runPolicy.status === 'AVAILABLE'
      && runPolicy.mode === 'SHADOW' && runPolicy.bundle_sha256 === d.bundle_sha256
      && runPolicy.corpus_sha256 === receipt.corpus_sha256 && runPolicy.model_sha256 === receipt.model_sha256
      && ['calibration_artifact_sha256', 'calibration_manifest_sha256', 'training_split_manifest_sha256',
          'scorer_summary_sha256', 'model_sha256', 'base_model_sha256', 'scorer_sha256', 'policy_sha256', 'temperature']
        .every(k => calibration[k] === receipt[k])
      && ref.schema_version === 'candidate_inference_capture_ref_v1' && ref.mode === 'SHADOW' && ref.status === 'SAVED'
      && flags(d) && flags(ref) && flags(receipt) && ref.post_id === d.post_id
      && binding.scope === 'ATTEMPT_LOCAL_OBSERVATION' && Number.isSafeInteger(binding.input_index) && binding.input_index > 0
      && binding.post_id === d.post_id && ['run_id', 'attempt_id', 'publication_scope_id'].every(k => typeof binding[k] === 'string' && binding[k].trim())
      && bindingKeys.every(k => refBinding[k] === binding[k])
      && ['graph_sha256', 'capture_sha256', 'bundle_sha256', 'input_snapshot_sha256'].every(k => hash(d[k]) && ref[k] === d[k])
      && receipt.graph_sha256 === d.graph_sha256 && receipt.capture_sha256 === d.capture_sha256
      && ['model_sha256', 'base_model_sha256', 'scorer_sha256', 'calibration_artifact_sha256', 'raw_receipt_sha256', 'policy_sha256',
          'calibration_manifest_sha256', 'training_split_manifest_sha256', 'scorer_summary_sha256', 'corpus_sha256'].every(k => hash(receipt[k]))
      && hash(artifact.sha256) && typeof artifact.path === 'string' && artifact.path.length > 0
      && Number.isSafeInteger(artifact.bytes) && artifact.bytes > 0
      && Array.isArray(probabilities) && probabilities.length >= 2 && probabilities.length <= 21
      && probabilities.every(p => p && typeof p.label === 'string' && p.label.length > 0
        && Number.isSafeInteger(p.probability_mass) && p.probability_mass >= 0
        && Number.isSafeInteger(p.probability_scale) && p.probability_scale > 0
        && p.probability_scale === probabilities[0].probability_scale && p.probability_mass <= p.probability_scale
        && p.probability === p.probability_mass / p.probability_scale)
      && new Set(probabilities.map(p => p.label)).size === probabilities.length
      && probabilities.at(-1).label === '__NIL__' && probabilities.at(-1).probability === receipt.nil_probability
      && probabilities.reduce((sum, p) => sum + p.probability_mass, 0) === probabilities[0].probability_scale
      && probabilities.some(p => p.label === receipt.selected_label
        && p.probability_mass === Math.max(...probabilities.map(x => x.probability_mass))
        && receipt.selected_error_probability === (p.probability_scale - p.probability_mass) / p.probability_scale);
    if (bound) {
      html += '<div class="detail-grid">' + kv('SHADOW 제안 label · 공개 선택 아님', receipt.selected_label)
        + kv('SHADOW 제안 동작 · 적용 아님', receipt.action)
        + kv('SHADOW 선택 오류확률', receipt.selected_error_probability) + '</div>'
        + '<div class="detail-grid">' + kv('결속된 일반 입력 사건 확률', probabilities) + '</div>';
    } else html += '<p class="presentation-empty">확률 표시 조건을 충족하지 못했습니다. 실행·저장·수치 검산 상태를 확인하세요.</p>';
    return section(title, html + rawRecord('일반 입력 관측 원본 · JSON', d) + rawRecord('저장 capture 참조 · JSON', ref));
  }

  function renderCandidateCalibrationPolicy(value) {
    const d = object(value);
    return section('실행 manifest · 후보 확률 교정 정책',
      '<p class="section-note">FROZEN 재관측 전용 정책입니다. 정책 저장은 해당 행의 교정 실행이나 실제 자료 품질 평가 완료를 뜻하지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('관측 모드', d.mode) + kv('정책 상태', d.status)
      + kv('적용 범위', d.scope) + kv('자료 구분', d.data_kind)
      + kv('bundle SHA-256', d.bundle_sha256) + kv('교정 artifact SHA-256', d.calibration_artifact_sha256)
      + kv('모델 SHA-256', d.model_sha256) + kv('scorer SHA-256', d.scorer_sha256)
      + kv('실제 품질 평가', d.actual_quality_evaluated) + kv('공개 권한', d.publication_authority)
      + kv('판정 반영', d.public_apply) + '</div>' + rawRecord('저장된 교정 정책 · JSON', value));
  }

  function renderCandidateCalibration(value) {
    const title = '후보 확률 교정 · FROZEN SHADOW', d = object(value);
    if (!Object.keys(d).length) return section(title,
      '<p class="presentation-empty">이 행에는 교정 관측이 저장되지 않았습니다.</p>');
    const shadow = object(d.calibration_shadow);
    let html = '<p class="section-note">FROZEN 재관측 전용입니다. 저장된 확률은 SHADOW 관측이며 실제 자료의 교정 품질이나 최종 공개 판정을 뜻하지 않습니다. __NIL__ 확률로 작품 없음의 최종 판정을 추론하지 않습니다. 기존 재정렬 원시 점수는 별도 기록입니다.</p>'
      + '<div class="detail-grid">' + kv('관측 모드', d.mode) + kv('관측 상태', d.status)
      + kv('사유', d.reason_codes) + kv('자료 구분', d.data_kind) + kv('실행 게시글 ID', d.post_id)
      + kv('자료 example ID', d.dataset_example_id) + kv('자료 게시글 ID', d.dataset_post_id)
      + kv('ID 대응 SHA-256', d.mapping_sha256) + kv('실행 capture SHA-256', d.runtime_capture_sha256)
      + kv('실행 원시 receipt SHA-256', d.runtime_raw_receipt_sha256)
      + kv('자료 원시 receipt SHA-256', d.dataset_raw_receipt_sha256)
      + kv('교정 artifact SHA-256', d.calibration_artifact_sha256) + kv('bundle SHA-256', d.bundle_sha256)
      + kv('모델 SHA-256', d.model_sha256) + kv('scorer SHA-256', d.scorer_sha256)
      + kv('공개 권한', d.publication_authority) + kv('판정 반영', d.public_apply)
      + kv('동작 적용', d.action_applied) + kv('중앙 DB 쓰기', d.central_db_write)
      + kv('운영 영향', d.operational_effect) + kv('실행·행 결속', d.binding)
      + kv('교정 receipt SHA-256', d.receipt_sha256) + '</div>';
    const bound = d.schema_version === 'candidate_calibration_shadow_v1' && d.mode === 'SHADOW'
      && d.status === 'CALIBRATED_SHADOW_BOUND' && shadow.probability_status === 'CALIBRATED_SHADOW_BOUND';
    if (bound) {
      html += '<div class="detail-grid">' + kv('저장된 확률 상태', shadow.probability_status)
        + kv('SHADOW 선택 label · 공개 선택 아님', shadow.selected_label)
        + kv('SHADOW 제안 동작 · 적용 아님', shadow.action) + kv('SHADOW 동작 적용', shadow.action_applied)
        + kv('정책 SHA-256', shadow.policy_sha256) + kv('분할 manifest SHA-256', shadow.split_manifest_sha256)
        + kv('고정 사건 score vector SHA-256', shadow.score_vector_sha256) + '</div>';
      const probabilities = Array.isArray(shadow.event_probabilities) ? shadow.event_probabilities : [];
      html += '<p class="section-note">확률은 저장된 정수 질량과 기준값으로 표시합니다. 계약 기준값은 1000000이며, 누락된 값은 보충하지 않습니다.</p>';
      if (!probabilities.length) html += '<p class="presentation-empty">저장된 사건 확률이 없습니다.</p>';
      for (const item of probabilities.slice(0, 21)) {
        const event = object(item);
        html += '<article class="evidence-card"><div class="detail-grid">' + kv('고정 사건 label', event.label)
          + kv('확률 정수 질량', event.probability_mass) + kv('확률 기준값', event.probability_scale) + '</div></article>';
      }
      if (probabilities.length > 21) html += '<p class="section-note">사건 표시 상한 21개를 넘었습니다. 전체 저장값은 아래 원본에서 확인하세요.</p>';
    } else {
      html += '<p class="presentation-empty">결속된 교정 확률 표시 대상이 아닙니다. 미실행·미사용·오류·미기록을 확률 0으로 바꾸지 않습니다.</p>'
        + '<div class="detail-grid">' + kv('저장된 교정 payload', d.calibration_shadow) + '</div>';
    }
    return section(title, html + rawRecord('저장된 교정 관측 원본 · JSON', d));
  }

  function renderCandidateCapture(value) {
    const title = '선택 전 원문 capture · 저장 참조', d = object(value);
    if (!Object.keys(d).length) return section(title,
      '<p class="presentation-empty">이 행에는 선택 전 원문 capture 참조가 저장되지 않았습니다.</p>');
    const artifact = object(d.artifact);
    const html = '<p class="section-note">선택 전 파싱된 원문 snapshot의 참조 정보입니다. 저장 성공은 학습 분할 배정이나 정답 판정을 뜻하지 않습니다. 파일 경로는 표시만 하며 이 화면에서 파일을 열거나 읽지 않습니다.</p>'
      + '<div class="detail-grid">' + kv('관측 모드', d.mode) + kv('capture 상태', d.status)
      + kv('사유', d.reason_codes) + kv('게시글 ID', d.post_id) + kv('snapshot 범위', d.scope)
      + kv('학습 준비 상태', d.training_readiness) + kv('원문 fragment 수', d.fragment_count)
      + kv('후보 수', d.candidate_count) + kv('원본 관측 SHA-256', d.observation_sha256)
      + kv('결속된 capture SHA-256', d.capture_sha256) + kv('고정 입력 view SHA-256', d.frozen_view_sha256)
      + kv('입력 snapshot SHA-256', d.input_snapshot_sha256) + kv('파일 참조', d.artifact)
      + kv('저장 경로 · 정보만 표시', artifact.path) + kv('파일 SHA-256', artifact.sha256)
      + kv('파일 바이트 수', artifact.bytes) + kv('공개 권한', d.publication_authority)
      + kv('판정 반영', d.public_apply) + kv('중앙 DB 쓰기', d.central_db_write)
      + kv('실행·행 결속', d.binding) + kv('capture receipt SHA-256', d.receipt_sha256) + '</div>';
    return section(title, html + rawRecord('저장된 capture 참조 원본 · JSON', d));
  }

  function renderCommunityKnowledge(value) {
    const d = object(value);
    if (!Object.keys(d).length) return '';
    let html = '<p class="section-note">후보 정의와 경쟁 의미를 읽어 문맥에 제공합니다. 조회·prompt 포함은 올바른 해석의 증거가 아니며, 후보 자체에는 작품 제목·공식 URL 공개 권한이 없습니다.</p>'
      + '<div class="detail-grid">' + kv('실행 모드', d.mode) + kv('조회 상태', d.status)
      + kv('사유', d.reason_codes) + kv('실제 소비 기록', d.consumption)
      + kv('게시글 ID', d.post_id) + kv('자료 구분', object(d.policy).data_kind || d.data_kind)
      + kv('snapshot SHA-256', d.snapshot_sha256) + kv('원문 query SHA-256', d.query_sha256)
      + kv('공개 권한', d.public_authority) + kv('중앙 DB 쓰기', d.central_db_write)
      + kv('원문 출현 위치', d.occurrences) + kv('실행·행 결속', d.binding) + '</div>';
    const candidates = Array.isArray(d.candidates) ? d.candidates : [];
    if (!candidates.length) html += '<p class="presentation-empty">전달할 후보가 없습니다. 작품 없음(NIL)이나 용어에 의미가 없다는 판정은 아닙니다.</p>';
    for (const value of candidates.slice(0, 16)) {
      const candidate = object(value);
      html += '<details class="raw-record"><summary>' + esc(displayValue(candidate.surface_raw || candidate.surface))
        + ' · ' + esc(displayValue(candidate.sense_candidate_id || candidate.sense_id))
        + '</summary><div class="detail-grid">' + kv('후보 ID', candidate.candidate_id)
        + kv('구분', candidate.namespace) + kv('후보 정의', candidate.definition_text || candidate.definition)
        + kv('적용 커뮤니티', candidate.community_scope) + kv('의미 유효기간', candidate.temporal_scope)
        + kv('검토 상태', candidate.review_status) + kv('검토 출처', candidate.review)
        + kv('작품 별칭 후보', candidate.work_alias_entries) + kv('일반 의미 분류', candidate.lexicon_entries)
        + kv('선언된 lineage', candidate.declared_lineage_roots) + kv('출처', candidate.source_refs)
        + '</div>' + rawRecord('후보 상세 · JSON', candidate) + '</details>';
    }
    return section('커뮤니티 지식 · READ_ONLY', html + rawRecord('조회·소비 원본 · JSON', d));
  }

  function logPrefix(line) {
    let message = String(line ?? '');
    const time = message.match(/^\[(\d{2}:\d{2}:\d{2}(?:\.\d+)?)(?:\|(W\d+))?\]\s*/);
    let worker = time?.[2] || '';
    if (time) message = message.slice(time[0].length);
    const workerTag = message.match(/^\[(W\d+)\]\s*/);
    if (workerTag) { worker = workerTag[1]; message = message.slice(workerTag[0].length); }
    return { time: time?.[1] || '', worker, message };
  }

  function stageOf(message) {
    if (/✅\s*Post.*완료|📊\s*Post.*token usage/.test(message)) return 'result';
    if (/VLM|\bOCR\b|🖼/.test(message)) return 'vlm';
    if (/📌 Post ID:|📝 제목:|🤖 \[W/.test(message)) return 'input';
    for (const stage of Object.keys(STAGES).filter(key => !['general', 'input', 'vlm', 'result'].includes(key))) {
      if (new RegExp(`\\b${stage.replace('_', '[_ -]?')}\\b`, 'i').test(message)) return stage;
    }
    return '';
  }

  function categoryOf(message) {
    if (/⚠|❌|\b(?:error|exception|failed|traceback)\b|오류|실패/i.test(message)) return 'warning';
    if (/✅\s*Post.*완료|token usage|^\s*(?:is_relevant|official_title|confidence|reason):/.test(message)) return 'result';
    if (/\[llm-(?:debug|stream|usage|context)\]/.test(message)) return 'llm';
    if (/검색|\bsearch\b|\bfetch\b/i.test(message)) return 'search';
    return 'stage';
  }

  // JSON 검증 후 토큰 사이 공백만 바꾼다. 큰 정수와 소수의 원래 표기를 보존한다.
  function prettyJson(source) {
    try { JSON.parse(source); } catch { return null; }
    const tokens = source.match(/"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|[{}\[\],:]/g) || [];
    let depth = 0, result = '';
    const newline = () => '\n' + '  '.repeat(Math.max(0, depth));
    tokens.forEach((token, index) => {
      const previous = tokens[index - 1], next = tokens[index + 1];
      if (token === '{' || token === '[') { result += token; depth++; if (next !== '}' && next !== ']') result += newline(); }
      else if (token === '}' || token === ']') { depth--; if (previous !== '{' && previous !== '[') result += newline(); result += token; }
      else if (token === ',') result += ',' + newline();
      else if (token === ':') result += ': ';
      else result += token;
    });
    return result;
  }

  function parseLogs(lines) {
    const records = [];
    const stages = new Map();
    let pending = null, lastWorker = '', reasonRecord = null;
    function finishJson() {
      const record = pending.record;
      record.pretty = prettyJson(pending.parts.join('\n'));
      record.category = record.pretty === null ? pending.fallbackCategory : 'json';
      records.push(record);
      pending = null;
    }
    function scanJson(text) {
      for (const char of text) {
        if (pending.escaped) { pending.escaped = false; continue; }
        if (pending.inString && char === '\\') { pending.escaped = true; continue; }
        if (char === '"') pending.inString = !pending.inString;
        else if (!pending.inString) {
          if (char === '{' || char === '[') pending.depth++;
          if (char === '}' || char === ']') pending.depth--;
        }
      }
    }
    lines.forEach((raw, index) => {
      raw = String(raw ?? '');
      const prefix = logPrefix(raw);
      if (reasonRecord && /^\[[^\]]+\](?:\[W\d+\])? {8,}/.test(raw)
          && (!prefix.worker || prefix.worker === reasonRecord.worker)) {
        reasonRecord.lines.push(raw);
        reasonRecord.reason += '\n' + prefix.message;
        reasonRecord.end = index + 1;
        return;
      }
      reasonRecord = null;
      // 중간에 끊긴 JSON 다음의 타임스탬프 로그를 JSON에 삼키지 않는다.
      if (pending && (prefix.time || prefix.worker) && !(prefix.time === pending.record.time && prefix.worker === pending.record.worker)) finishJson();
      if (pending) {
        pending.record.lines.push(raw); pending.record.end = index + 1;
        pending.parts.push(prefix.message); scanJson(prefix.message);
        if (pending.depth <= 0) finishJson();
        return;
      }
      const worker = prefix.worker || (prefix.time ? '' : lastWorker);
      if (prefix.time || prefix.worker) lastWorker = prefix.worker;
      const detected = stageOf(prefix.message);
      if (detected) stages.set(worker, detected);
      const stage = stages.get(worker) || 'general';
      const category = categoryOf(prefix.message);
      const record = { ...prefix, worker, stage, category, lines: [raw], start: index + 1, end: index + 1 };
      if (/^reason:\s*/.test(prefix.message)) {
        record.reason = prefix.message.replace(/^reason:\s*/, '');
        record.stage = 'result'; record.category = 'result';
        reasonRecord = record;
        records.push(record);
        return;
      }
      if (/^\s*(?:\{|\[(?:\s*$|\s*[\{"\d\]truefalsn-]))/.test(prefix.message)) {
        pending = { record, parts: [prefix.message], depth: 0, inString: false, escaped: false, fallbackCategory: category };
        scanJson(prefix.message);
        if (pending.depth <= 0) finishJson();
      } else records.push(record);
    });
    if (pending) finishJson();
    return records;
  }

  function renderLogRecord(record, raw = false) {
    const text = raw ? record.lines.join('\n') : record.pretty ?? record.lines.map(line => logPrefix(line).message).join('\n');
    const metadata = `<span class="log-meta">${esc(record.time)}${record.worker ? ` <b>${esc(record.worker)}</b>` : ''}<span class="log-kind">${CATEGORIES[record.category]}</span></span>`;
    let key = 2166136261;
    for (const char of record.lines.join('\n')) key = Math.imul(key ^ char.charCodeAt(0), 16777619);
    const recordKey = (key >>> 0).toString(36);
    const tone = record.category === 'stage' ? 'progress' : record.category;
    const content = `<pre>${esc(text)}</pre>`;
    if (!raw && record.reason) {
      return `<details class="log-record log-result" data-log-key="${recordKey}"><summary>${metadata}<span>판정 사유 · ${record.lines.length}줄 펼치기</span></summary>${renderReason(record.reason, { raw: false })}</details>`;
    }
    if (!raw && (record.category === 'json' || text.length > 900 || record.lines.length > 12)) {
      return `<details class="log-record log-${tone}" data-log-key="${recordKey}"><summary>${metadata}<span>${record.category === 'json' ? 'JSON 응답' : '긴 기록'} · ${record.end - record.start + 1}줄 펼치기</span></summary>${content}</details>`;
    }
    return `<div class="log-record log-${tone}">${raw ? '' : metadata}${content}</div>`;
  }

  function renderLogs(records, { grouped = true, raw = false } = {}) {
    if (!records.length) return '<p class="presentation-empty">조건에 맞는 로그가 없습니다.</p>';
    if (raw || !grouped) return records.map(record => renderLogRecord(record, raw)).join('');
    const groups = [];
    for (const record of records) {
      let group = groups.at(-1);
      if (!group || group.stage !== record.stage || group.worker !== record.worker) {
        group = { stage: record.stage, worker: record.worker, records: [] }; groups.push(group);
      }
      group.records.push(record);
    }
    return groups.map(group => `<details class="log-stage" open><summary><span>${esc(STAGES[group.stage] || group.stage)}</span><span class="log-stage-meta">${esc(group.worker)} · ${group.records[0].start}–${group.records.at(-1).end}줄</span></summary><div>${group.records.map(record => renderLogRecord(record)).join('')}</div></details>`).join('');
  }

  const api = { parseReason, renderReason, renderIdentity, parseLogs, renderLogs, prettyJson, safeLink,
    renderExplanation, nsfwLabel, nsfwReasonLabel, executionSummary, runCompletionSummary, historyRunSummary, renderHistoryRun,
    renderExecutionConfig, renderPairedExecution, renderSemanticReview, renderRecoveryActivation, renderRecoveryExecution, renderRecoveryProvider,
    renderRecoveryNative, renderRunContext, renderContextDiagnostics, renderCandidateRetrieval, renderCandidateReranker,
    renderCandidateCalibrationPolicy, renderCandidateCalibration, renderCandidateCapture,
    renderCandidateInferencePolicy, renderCandidateInference,
    renderCandidateSemantics, renderCandidateSemanticsCapture, renderCandidateSemanticsPolicy, renderCommunityKnowledge };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.DashboardPresentation = api;
})(typeof window === 'undefined' ? globalThis : window);
