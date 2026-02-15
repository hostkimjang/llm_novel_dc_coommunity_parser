#!/usr/bin/env python3
"""
파이프라인 결과 전수 리뷰 HTML 대시보드 생성기
- 결과 JSON + 로그 파일 → 인터랙티브 HTML 리뷰 페이지
"""
import json
import sys
import re
import html as html_mod
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

RESULT_FILE = 'out/expert_result_20260210_011453.json'
LOG_FILE = 'logs/expert_run_20260210_011453.log'
OUTPUT_HTML = 'out/review_dashboard.html'


def load_results(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_log_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.readlines()


def parse_log_boundaries(lines):
    """post_id별 로그 시작/끝 라인 인덱스"""
    boundaries = []
    for i, line in enumerate(lines):
        m = re.search(r'Orchestrator 시작: post_id=(\d+)', line)
        if m:
            boundaries.append((int(m.group(1)), i))
    # 각 post의 끝 인덱스 계산
    post_ranges = {}
    for j, (pid, start) in enumerate(boundaries):
        end = boundaries[j + 1][1] if j + 1 < len(boundaries) else len(lines)
        post_ranges[pid] = (start, end)
    return post_ranges


def extract_log_summary(lines, start, end):
    """post 로그에서 주요 판단 요약 추출"""
    chunk = lines[start:end]
    summary = {
        'gatekeeper': [],
        'decoder': [],
        'verifier': [],
        'critic': [],
        'arbiter': [],
        'search': [],
        'key_decisions': [],
        'full_log': ''
    }

    full_lines = []
    for line in chunk:
        stripped = line.rstrip()
        if not stripped:
            continue
        full_lines.append(stripped)

        # 검색 쿼리
        if '🔎 검색:' in line:
            summary['search'].append(stripped)
        # Gatekeeper
        elif 'Gatekeeper' in line and ('완료' in line or 'is_noise' in line):
            summary['gatekeeper'].append(stripped)
        # Decoder
        elif '🔤' in line or 'Decoder' in line:
            if any(kw in line for kw in ['완료', 'best_match', '약어스코어', '약어 매칭', '스코어 극단', 'morpheme', 'guard', 'rescue', 'possible_titles']):
                summary['decoder'].append(stripped)
        # Verifier
        elif '🔍' in line or 'Verifier' in line:
            if any(kw in line for kw in ['완료', 'is_relevant', '본문증거', 'confidence', 'grounding']):
                summary['verifier'].append(stripped)
        # Critic
        elif '📚' in line or 'Critic' in line:
            if '완료' in line:
                summary['critic'].append(stripped)
        # Arbiter
        elif '⚖️' in line or 'Arbiter' in line:
            if any(kw in line for kw in ['완료', 'is_relevant', 'agreeing', 'dissenting', 'arbiter_decision']):
                summary['arbiter'].append(stripped)
        # Key decisions
        if any(kw in line for kw in ['confidence:', 'is_relevant:', '→ confidence', '할루시네이션', '본문증거']):
            if '🛡️' in line or 'is_relevant' in line.lower():
                summary['key_decisions'].append(stripped)

    summary['full_log'] = '\n'.join(full_lines)
    return summary


def generate_agent_opinion(item, log_summary):
    """AI 에이전트 의견 자동 생성"""
    ar = item.get('analysis_result', {})
    identity = ar.get('identity', {})
    is_relevant = identity.get('is_relevant', False)
    ni = identity.get('novel_identity') or {}
    title = ni.get('official_title', '')
    confidence = ni.get('confidence', 'N/A')
    disc_type = identity.get('discussion_type', '')
    reason = identity.get('reason', '')
    post_title = item.get('title', '')
    content = item.get('content', '')

    opinions = []

    if is_relevant:
        # is_relevant=True 검토
        if confidence == 'High':
            opinions.append('✅ High confidence 식별 — 정상 판정으로 보임')
        elif confidence == 'Medium':
            opinions.append('⚠️ Medium confidence — 추가 검증 필요 가능성')
        elif confidence == 'Low':
            opinions.append('🔴 Low confidence인데 is_relevant=True — FP 위험')

        # Decoder guard 관련
        decoder_lines = log_summary.get('decoder', [])
        for dl in decoder_lines:
            if '할루시네이션' in dl or '스코어 극단' in dl:
                opinions.append(f'⚠️ Decoder guard 발동 이력: {dl[-80:]}')
            if '약어 매칭 낮음' in dl:
                opinions.append(f'⚠️ 약어 매칭 이슈: {dl[-80:]}')

        # 본문증거
        verifier_lines = log_summary.get('verifier', [])
        for vl in verifier_lines:
            if '본문증거' in vl and '실패' in vl:
                opinions.append(f'⚠️ 본문증거 실패: {vl[-80:]}')

        if not title:
            opinions.append('🔴 is_relevant=True인데 official_title 없음 — 확인 필요')

    else:
        # is_relevant=False 검토
        # 제목에 알려진 약어 패턴 체크
        known_patterns = ['즉사무림', '망겜', '마좋', '죽깨수', '헌터상담', '괴담텔',
                          '김괴라리', '고향무림', '컵라면', '성좌안무', '흑백소설',
                          '개돌', '로판']
        found_patterns = [p for p in known_patterns if p in post_title]
        if found_patterns:
            opinions.append(f'⚠️ 제목에 작품 약어 패턴 감지: {found_patterns} → FN 가능성 검토')

        # 작품 관련 키워드
        novel_keywords = ['작가', '연재', '회차', '스포', '결말', '완결', '주인공',
                          '히로인', '빌런', '전개', '복선', '설정', '떡밥']
        found_kw = [k for k in novel_keywords if k in post_title or k in (content or '')]
        if found_kw:
            opinions.append(f'ℹ️ 작품 관련 키워드 발견: {found_kw}')

        # Arbiter에서 dissenting이 있었는지
        arbiter_lines = log_summary.get('arbiter', [])
        for al in arbiter_lines:
            if 'dissenting' in al:
                opinions.append(f'⚠️ 전문가 의견 불일치: {al[-100:]}')

    if not opinions:
        opinions.append('ℹ️ 특이사항 없음')

    return '\n'.join(opinions)


def build_html(results, log_ranges, log_lines):
    """HTML 대시보드 생성"""
    total = len(results)
    relevant = sum(1 for r in results if r.get('analysis_result', {}).get('identity', {}).get('is_relevant'))
    not_relevant = total - relevant

    # 통계
    conf_counts = {}
    type_counts = {}
    for r in results:
        ni = r.get('analysis_result', {}).get('identity', {}).get('novel_identity') or {}
        c = ni.get('confidence', 'N/A') if ni else 'N/A'
        conf_counts[c] = conf_counts.get(c, 0) + 1
        t = r.get('analysis_result', {}).get('identity', {}).get('discussion_type', 'N/A')
        type_counts[t] = type_counts.get(t, 0) + 1

    rows_html = []
    for idx, item in enumerate(results):
        post_id = item['post_id']
        post_title = html_mod.escape(str(item.get('title', '') or ''))
        post_url = html_mod.escape(str(item.get('url', '') or ''))
        raw_content = item.get('content', '') or ''
        if isinstance(raw_content, list):
            raw_content = '\n'.join(str(c) for c in raw_content)
        post_content = html_mod.escape(str(raw_content))[:200]
        post_author = html_mod.escape(str(item.get('author', '') or ''))
        comments = item.get('comments', [])
        comment_count = len(comments) if isinstance(comments, list) else 0
        comment_preview = ''
        if isinstance(comments, list) and comments:
            for c in comments[:3]:
                if isinstance(c, dict):
                    ctext = c.get('content', '') or c.get('text', '') or ''
                    cauthor = c.get('author', '') or ''
                    comment_preview += f'[{html_mod.escape(cauthor)}] {html_mod.escape(ctext[:50])}\n'
                elif isinstance(c, str):
                    comment_preview += html_mod.escape(c[:50]) + '\n'

        ar = item.get('analysis_result', {})
        identity = ar.get('identity', {})
        is_relevant = identity.get('is_relevant', False)
        ni = identity.get('novel_identity') or {}
        official_title = html_mod.escape(ni.get('official_title', '') or '')
        confidence = ni.get('confidence', 'N/A') if ni else 'N/A'
        heretic_url = html_mod.escape(ni.get('heretic_url', '') or '')
        disc_type = html_mod.escape(identity.get('discussion_type', ''))
        reason = html_mod.escape(identity.get('reason', '') or '')

        # 로그 요약
        log_summary = {'gatekeeper': [], 'decoder': [], 'verifier': [], 'critic': [],
                       'arbiter': [], 'search': [], 'key_decisions': [], 'full_log': ''}
        if post_id in log_ranges:
            s, e = log_ranges[post_id]
            log_summary = extract_log_summary(log_lines, s, e)

        # 에이전트 의견
        agent_opinion = html_mod.escape(generate_agent_opinion(item, log_summary))

        # 로그 요약 텍스트
        log_text_parts = []
        if log_summary['gatekeeper']:
            log_text_parts.append('📋 Gatekeeper:\n' + '\n'.join(l[:150] for l in log_summary['gatekeeper'][:3]))
        if log_summary['decoder']:
            log_text_parts.append('🔤 Decoder:\n' + '\n'.join(l[:150] for l in log_summary['decoder'][:5]))
        if log_summary['search']:
            log_text_parts.append(f'🔎 검색 ({len(log_summary["search"])}건):\n' + '\n'.join(l[:120] for l in log_summary['search'][:5]))
        if log_summary['verifier']:
            log_text_parts.append('🔍 Verifier:\n' + '\n'.join(l[:150] for l in log_summary['verifier'][:3]))
        if log_summary['arbiter']:
            log_text_parts.append('⚖️ Arbiter:\n' + '\n'.join(l[:150] for l in log_summary['arbiter'][:3]))
        if log_summary['key_decisions']:
            log_text_parts.append('🎯 핵심 판단:\n' + '\n'.join(l[:150] for l in log_summary['key_decisions'][:5]))
        log_summary_text = html_mod.escape('\n\n'.join(log_text_parts))
        full_log_escaped = html_mod.escape(log_summary['full_log'][:8000])

        # CSS 클래스
        rel_class = 'relevant' if is_relevant else 'not-relevant'
        conf_class = confidence.lower() if confidence in ('High', 'Medium', 'Low') else 'na'

        row = f'''
        <tr class="result-row {rel_class}" data-post-id="{post_id}" data-relevant="{str(is_relevant).lower()}" data-confidence="{confidence}" data-type="{disc_type}">
            <td class="col-idx">{idx + 1}</td>
            <td class="col-check">
                <select class="status-select" data-post-id="{post_id}">
                    <option value="">미검토</option>
                    <option value="correct">✅ 정확</option>
                    <option value="fp">❌ FP</option>
                    <option value="fn">❌ FN</option>
                    <option value="partial">⚠️ 부분정확</option>
                    <option value="unclear">❓ 불명확</option>
                </select>
            </td>
            <td class="col-postid">
                <a href="{post_url}" target="_blank">{post_id}</a>
            </td>
            <td class="col-title" title="{post_title}">{post_title}</td>
            <td class="col-content">
                <div class="content-preview" title="{post_content}">{post_content[:80]}{'...' if len(post_content) > 80 else ''}</div>
                <div class="comment-info">💬 {comment_count}개</div>
                {f'<div class="comment-preview">{comment_preview}</div>' if comment_preview else ''}
            </td>
            <td class="col-result">
                <span class="badge badge-{rel_class}">{'✅ 관련' if is_relevant else '❌ 무관'}</span>
                <span class="badge badge-conf-{conf_class}">{confidence}</span>
                <div class="result-title">{official_title or '-'}</div>
                <div class="result-type">{disc_type}</div>
            </td>
            <td class="col-reason">
                <div class="reason-text">{reason[:200]}{'...' if len(reason) > 200 else ''}</div>
                <button class="btn-expand" onclick="toggleDetail(this, 'reason')">상세보기</button>
                <div class="detail-full" style="display:none">{reason}</div>
            </td>
            <td class="col-log">
                <div class="log-summary">{log_summary_text[:300]}{'...' if len(log_summary_text) > 300 else ''}</div>
                <button class="btn-expand" onclick="toggleDetail(this, 'log')">로그 보기</button>
                <div class="detail-full" style="display:none"><pre>{log_summary_text}</pre></div>
                <button class="btn-expand" onclick="toggleDetail(this, 'fulllog')">전체 로그</button>
                <div class="detail-full" style="display:none"><pre class="full-log">{full_log_escaped}</pre></div>
            </td>
            <td class="col-agent-opinion">
                <div class="opinion-text">{agent_opinion}</div>
            </td>
            <td class="col-user-opinion">
                <textarea class="user-opinion-input" data-post-id="{post_id}" placeholder="의견 입력..."></textarea>
            </td>
            <td class="col-feedback">
                <textarea class="feedback-input" data-post-id="{post_id}" placeholder="개선 제안..."></textarea>
            </td>
        </tr>'''
        rows_html.append(row)

    # 타입별 통계 HTML
    type_stats_html = ''.join(
        f'<span class="stat-tag">{t}: {c}</span>' for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    )
    conf_stats_html = ''.join(
        f'<span class="stat-tag conf-{c.lower() if c in ("High","Medium","Low") else "na"}">{c}: {v}</span>'
        for c, v in sorted(conf_counts.items(), key=lambda x: -x[1])
    )

    html_content = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>파이프라인 결과 전수 리뷰 대시보드</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; background: #0d1117; color: #c9d1d9; font-size: 13px; }}

.dashboard-header {{
    background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
    padding: 20px 30px;
    border-bottom: 1px solid #30363d;
    position: sticky; top: 0; z-index: 100;
}}
.dashboard-header h1 {{ color: #58a6ff; font-size: 20px; margin-bottom: 10px; }}
.stats-bar {{ display: flex; gap: 20px; flex-wrap: wrap; align-items: center; }}
.stat-box {{
    background: #21262d; border: 1px solid #30363d; border-radius: 8px;
    padding: 8px 16px; display: flex; flex-direction: column; align-items: center;
}}
.stat-box .stat-value {{ font-size: 22px; font-weight: bold; }}
.stat-box .stat-label {{ font-size: 11px; color: #8b949e; }}
.stat-box.relevant .stat-value {{ color: #3fb950; }}
.stat-box.not-relevant .stat-value {{ color: #f85149; }}

.filter-bar {{
    background: #161b22; padding: 10px 30px; border-bottom: 1px solid #30363d;
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
    position: sticky; top: 90px; z-index: 99;
}}
.filter-bar label {{ color: #8b949e; font-size: 12px; }}
.filter-bar select, .filter-bar input {{
    background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
    border-radius: 4px; padding: 4px 8px; font-size: 12px;
}}
.filter-bar button {{
    background: #238636; color: white; border: none; border-radius: 4px;
    padding: 4px 12px; cursor: pointer; font-size: 12px;
}}
.filter-bar button:hover {{ background: #2ea043; }}
.filter-bar button.btn-danger {{ background: #da3633; }}
.filter-bar button.btn-danger:hover {{ background: #f85149; }}

.type-stats {{ padding: 8px 30px; background: #161b22; border-bottom: 1px solid #30363d; }}
.stat-tag {{ display: inline-block; background: #21262d; border: 1px solid #30363d; border-radius: 4px; padding: 2px 8px; margin: 2px; font-size: 11px; }}
.stat-tag.conf-high {{ border-color: #3fb950; color: #3fb950; }}
.stat-tag.conf-medium {{ border-color: #d29922; color: #d29922; }}
.stat-tag.conf-low {{ border-color: #f85149; color: #f85149; }}

.table-container {{ overflow-x: auto; padding: 10px; }}

table {{
    width: 100%; border-collapse: collapse; font-size: 12px;
    table-layout: fixed;
}}
thead {{ position: sticky; top: 130px; z-index: 50; }}
th {{
    background: #21262d; color: #58a6ff; padding: 8px 6px;
    border: 1px solid #30363d; font-weight: 600; text-align: left;
    white-space: nowrap; font-size: 11px;
}}
td {{
    padding: 6px; border: 1px solid #21262d; vertical-align: top;
    word-break: break-all;
}}
tr:hover {{ background: #161b22; }}
tr.relevant {{ border-left: 3px solid #3fb950; }}
tr.not-relevant {{ border-left: 3px solid #484f58; }}
tr.highlight {{ background: #1c2333 !important; }}

.col-idx {{ width: 35px; text-align: center; }}
.col-check {{ width: 90px; }}
.col-postid {{ width: 75px; }}
.col-title {{ width: 180px; }}
.col-content {{ width: 180px; }}
.col-result {{ width: 150px; }}
.col-reason {{ width: 200px; }}
.col-log {{ width: 250px; }}
.col-agent-opinion {{ width: 200px; }}
.col-user-opinion {{ width: 150px; }}
.col-feedback {{ width: 150px; }}

.badge {{
    display: inline-block; padding: 2px 6px; border-radius: 4px;
    font-size: 10px; font-weight: 600; margin: 1px;
}}
.badge-relevant {{ background: #0d3321; color: #3fb950; }}
.badge-not-relevant {{ background: #3d1a1a; color: #f85149; }}
.badge-conf-high {{ background: #0d3321; color: #3fb950; }}
.badge-conf-medium {{ background: #3d2e00; color: #d29922; }}
.badge-conf-low {{ background: #3d1a1a; color: #f85149; }}
.badge-conf-na {{ background: #21262d; color: #8b949e; }}

.result-title {{ color: #79c0ff; font-weight: 600; margin-top: 4px; font-size: 12px; }}
.result-type {{ color: #8b949e; font-size: 11px; }}

.reason-text, .log-summary, .opinion-text {{
    font-size: 11px; line-height: 1.4; max-height: 80px; overflow: hidden;
    color: #8b949e;
}}
.opinion-text {{ color: #d2a8ff; }}

.content-preview {{ font-size: 11px; color: #8b949e; }}
.comment-info {{ font-size: 10px; color: #484f58; }}
.comment-preview {{ font-size: 10px; color: #6e7681; max-height: 40px; overflow: hidden; white-space: pre-line; }}

.btn-expand {{
    background: #30363d; color: #8b949e; border: none; border-radius: 3px;
    padding: 2px 6px; cursor: pointer; font-size: 10px; margin-top: 4px;
}}
.btn-expand:hover {{ background: #484f58; color: #c9d1d9; }}

.detail-full {{
    margin-top: 4px; padding: 6px; background: #0d1117; border: 1px solid #30363d;
    border-radius: 4px; font-size: 11px; max-height: 400px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-all;
}}
.detail-full pre {{ font-size: 10px; line-height: 1.3; white-space: pre-wrap; word-break: break-all; }}
.full-log {{ max-height: 600px; overflow-y: auto; }}

.status-select {{
    background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
    border-radius: 4px; padding: 2px 4px; font-size: 11px; width: 100%;
}}
.status-select option[value="correct"] {{ color: #3fb950; }}
.status-select option[value="fp"] {{ color: #f85149; }}
.status-select option[value="fn"] {{ color: #f85149; }}
.status-select option[value="partial"] {{ color: #d29922; }}

.user-opinion-input, .feedback-input {{
    width: 100%; min-height: 60px; background: #0d1117; border: 1px solid #30363d;
    color: #c9d1d9; border-radius: 4px; padding: 4px; font-size: 11px;
    font-family: inherit; resize: vertical;
}}

a {{ color: #58a6ff; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.export-section {{
    padding: 10px 30px; background: #161b22; border-top: 1px solid #30363d;
    position: sticky; bottom: 0;
}}

/* 검토 상태 색상 */
tr[data-status="correct"] {{ background: #0d33210a; }}
tr[data-status="fp"] {{ background: #3d1a1a0a; }}
tr[data-status="fn"] {{ background: #3d1a1a0a; }}
tr[data-status="partial"] {{ background: #3d2e000a; }}

.summary-panel {{
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 15px; margin: 10px 30px;
}}
.summary-panel h3 {{ color: #79c0ff; margin-bottom: 8px; }}

@media print {{
    .filter-bar, .export-section, .btn-expand, .dashboard-header {{ position: static; }}
    .detail-full {{ display: block !important; }}
}}
</style>
</head>
<body>

<div class="dashboard-header">
    <h1>🔍 파이프라인 결과 전수 리뷰 대시보드</h1>
    <div class="stats-bar">
        <div class="stat-box"><span class="stat-value">{total}</span><span class="stat-label">전체</span></div>
        <div class="stat-box relevant"><span class="stat-value">{relevant}</span><span class="stat-label">is_relevant=True</span></div>
        <div class="stat-box not-relevant"><span class="stat-value">{not_relevant}</span><span class="stat-label">is_relevant=False</span></div>
        <div class="stat-box"><span class="stat-value" id="reviewed-count">0</span><span class="stat-label">검토 완료</span></div>
        <div class="stat-box"><span class="stat-value" id="fp-count">0</span><span class="stat-label">FP</span></div>
        <div class="stat-box"><span class="stat-value" id="fn-count">0</span><span class="stat-label">FN</span></div>
    </div>
</div>

<div class="filter-bar">
    <label>필터:</label>
    <select id="filter-relevant" onchange="applyFilters()">
        <option value="">전체</option>
        <option value="true">✅ 관련만</option>
        <option value="false">❌ 무관만</option>
    </select>
    <select id="filter-confidence" onchange="applyFilters()">
        <option value="">모든 Confidence</option>
        <option value="High">High</option>
        <option value="Medium">Medium</option>
        <option value="Low">Low</option>
        <option value="N/A">N/A</option>
    </select>
    <select id="filter-status" onchange="applyFilters()">
        <option value="">모든 검토상태</option>
        <option value="">미검토</option>
        <option value="correct">✅ 정확</option>
        <option value="fp">❌ FP</option>
        <option value="fn">❌ FN</option>
        <option value="partial">⚠️ 부분정확</option>
        <option value="unclear">❓ 불명확</option>
    </select>
    <select id="filter-type" onchange="applyFilters()">
        <option value="">모든 Type</option>
        {''.join(f'<option value="{t}">{t} ({c})</option>' for t, c in sorted(type_counts.items(), key=lambda x: -x[1]))}
    </select>
    <input type="text" id="filter-search" placeholder="제목/내용 검색..." onkeyup="applyFilters()">
    <button onclick="applyFilters()">🔍 필터</button>
    <button onclick="resetFilters()">초기화</button>
    <button onclick="exportReview()" class="btn-danger">📥 리뷰 내보내기 (JSON)</button>
    <button onclick="saveToLocal()">💾 임시 저장</button>
    <button onclick="loadFromLocal()">📂 불러오기</button>
</div>

<div class="type-stats">
    <strong>Discussion Types:</strong> {type_stats_html}
    <br><strong>Confidence:</strong> {conf_stats_html}
</div>

<div class="table-container">
<table id="review-table">
<thead>
<tr>
    <th class="col-idx">#</th>
    <th class="col-check">검토</th>
    <th class="col-postid">Post ID</th>
    <th class="col-title">제목</th>
    <th class="col-content">내용/댓글</th>
    <th class="col-result">판정 결과</th>
    <th class="col-reason">판정 사유</th>
    <th class="col-log">로그 분석</th>
    <th class="col-agent-opinion">🤖 에이전트 의견</th>
    <th class="col-user-opinion">👤 사용자 의견</th>
    <th class="col-feedback">개선 제안</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>

<div class="export-section">
    <span id="filter-info">전체 {total}건 표시중</span>
    &nbsp;|&nbsp;
    <span>생성: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
</div>

<script>
// 상태 변경 추적
document.querySelectorAll('.status-select').forEach(sel => {{
    sel.addEventListener('change', function() {{
        const row = this.closest('tr');
        row.setAttribute('data-status', this.value);
        updateCounts();
    }});
}});

function updateCounts() {{
    let reviewed = 0, fp = 0, fn = 0;
    document.querySelectorAll('.status-select').forEach(sel => {{
        if (sel.value) reviewed++;
        if (sel.value === 'fp') fp++;
        if (sel.value === 'fn') fn++;
    }});
    document.getElementById('reviewed-count').textContent = reviewed;
    document.getElementById('fp-count').textContent = fp;
    document.getElementById('fn-count').textContent = fn;
}}

function toggleDetail(btn, type) {{
    const detail = btn.nextElementSibling;
    if (detail.style.display === 'none') {{
        detail.style.display = 'block';
        btn.textContent = '접기';
    }} else {{
        detail.style.display = 'none';
        btn.textContent = type === 'fulllog' ? '전체 로그' : (type === 'log' ? '로그 보기' : '상세보기');
    }}
}}

function applyFilters() {{
    const relFilter = document.getElementById('filter-relevant').value;
    const confFilter = document.getElementById('filter-confidence').value;
    const statusFilter = document.getElementById('filter-status').value;
    const typeFilter = document.getElementById('filter-type').value;
    const searchFilter = document.getElementById('filter-search').value.toLowerCase();

    let shown = 0;
    document.querySelectorAll('.result-row').forEach(row => {{
        let show = true;
        if (relFilter && row.dataset.relevant !== relFilter) show = false;
        if (confFilter && row.dataset.confidence !== confFilter) show = false;
        if (typeFilter && row.dataset.type !== typeFilter) show = false;
        if (statusFilter) {{
            const sel = row.querySelector('.status-select');
            if (sel.value !== statusFilter) show = false;
        }}
        if (searchFilter) {{
            const text = row.textContent.toLowerCase();
            if (!text.includes(searchFilter)) show = false;
        }}
        row.style.display = show ? '' : 'none';
        if (show) shown++;
    }});
    document.getElementById('filter-info').textContent = `${{shown}} / {total}건 표시중`;
}}

function resetFilters() {{
    document.getElementById('filter-relevant').value = '';
    document.getElementById('filter-confidence').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-type').value = '';
    document.getElementById('filter-search').value = '';
    applyFilters();
}}

function exportReview() {{
    const reviews = [];
    document.querySelectorAll('.result-row').forEach(row => {{
        const postId = row.dataset.postId;
        const status = row.querySelector('.status-select').value;
        const userOpinion = row.querySelector('.user-opinion-input').value;
        const feedback = row.querySelector('.feedback-input').value;
        if (status || userOpinion || feedback) {{
            reviews.push({{ post_id: postId, status, user_opinion: userOpinion, feedback }});
        }}
    }});
    const blob = new Blob([JSON.stringify(reviews, null, 2)], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'review_feedback_' + new Date().toISOString().slice(0,10) + '.json';
    a.click();
    URL.revokeObjectURL(url);
}}

function saveToLocal() {{
    const data = {{}};
    document.querySelectorAll('.result-row').forEach(row => {{
        const postId = row.dataset.postId;
        data[postId] = {{
            status: row.querySelector('.status-select').value,
            userOpinion: row.querySelector('.user-opinion-input').value,
            feedback: row.querySelector('.feedback-input').value
        }};
    }});
    localStorage.setItem('pipeline_review_data', JSON.stringify(data));
    alert('💾 임시 저장 완료! (' + Object.keys(data).length + '건)');
}}

function loadFromLocal() {{
    const saved = localStorage.getItem('pipeline_review_data');
    if (!saved) {{ alert('저장된 데이터가 없습니다.'); return; }}
    const data = JSON.parse(saved);
    document.querySelectorAll('.result-row').forEach(row => {{
        const postId = row.dataset.postId;
        if (data[postId]) {{
            row.querySelector('.status-select').value = data[postId].status || '';
            row.querySelector('.user-opinion-input').value = data[postId].userOpinion || '';
            row.querySelector('.feedback-input').value = data[postId].feedback || '';
            row.setAttribute('data-status', data[postId].status || '');
        }}
    }});
    updateCounts();
    alert('📂 불러오기 완료!');
}}

// 키보드 단축키
document.addEventListener('keydown', e => {{
    if (e.ctrlKey && e.key === 's') {{
        e.preventDefault();
        saveToLocal();
    }}
}});
</script>
</body>
</html>'''
    return html_content


def main():
    print('📂 결과 파일 로딩...')
    results = load_results(RESULT_FILE)
    print(f'   → {len(results)}건 로드')

    print('📂 로그 파일 로딩...')
    log_lines = load_log_lines(LOG_FILE)
    print(f'   → {len(log_lines)}줄 로드')

    print('🔍 로그 경계 파싱...')
    log_ranges = parse_log_boundaries(log_lines)
    print(f'   → {len(log_ranges)}개 post 로그 발견')

    print('🏗️ HTML 대시보드 생성 중...')
    html = build_html(results, log_ranges, log_lines)

    Path(OUTPUT_HTML).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'✅ HTML 대시보드 생성 완료: {OUTPUT_HTML}')
    print(f'   파일 크기: {Path(OUTPUT_HTML).stat().st_size / 1024:.1f} KB')


if __name__ == '__main__':
    main()
