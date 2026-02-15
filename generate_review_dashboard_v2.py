#!/usr/bin/env python3
"""
파이프라인 결과 전수 리뷰 HTML 대시보드 v2 생성기
- 결과 JSON + 로그 파일 → 심도있는 인터랙티브 HTML 리뷰 페이지
- v2: 파이프라인 스테이지 흐름 시각화, 자동 이상 탐지, 향상된 에이전트 검토
"""
import json
import sys
import re
import html as html_mod
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

RESULT_FILE = 'out/expert_result_20260210_123650.json'
LOG_FILE = 'logs/expert_run_20260210_123650.log'
OUTPUT_HTML = 'out/review_dashboard_v2.html'


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
    post_ranges = {}
    for j, (pid, start) in enumerate(boundaries):
        end = boundaries[j + 1][1] if j + 1 < len(boundaries) else len(lines)
        post_ranges[pid] = (start, end)
    return post_ranges


def extract_log_details(lines, start, end):
    """post 로그에서 심층 정보 추출"""
    chunk = lines[start:end]
    info = {
        'gatekeeper': {'lines': [], 'is_noise': None, 'possible_titles': [], 'possible_authors': [], 'confidence': None},
        'decoder': {'lines': [], 'calls': 0, 'best_matches': [], 'scores': [], 'guards': [], 'rescues': [], 'morphemes': [], 'code_hints': []},
        'verifier': {'lines': [], 'is_relevant': None, 'confidence': None, 'body_evidence': None},
        'critic': {'lines': []},
        'arbiter': {'lines': [], 'is_relevant': None, 'confidence': None, 'agreeing': 0, 'dissenting': 0, 'reversal': False},
        'search': {'queries': [], 'total_results': 0},
        'warnings': [],
        'errors': [],
        'timings': {},
        'full_log': '',
    }

    full_lines = []
    for line in chunk:
        s = line.rstrip()
        if not s:
            continue
        full_lines.append(s)

        # Gatekeeper
        if '🎭' in s or ('Gatekeeper' in s and ('분석' in s or '완료' in s)):
            info['gatekeeper']['lines'].append(s)
        if 'is_noise' in s:
            m = re.search(r'is_noise["\s:=]+(\w+)', s)
            if m:
                info['gatekeeper']['is_noise'] = m.group(1).lower() == 'true'
        if 'possible_titles' in s:
            m = re.search(r'possible_titles.*?\[([^\]]*)\]', s)
            if m:
                titles = re.findall(r'"([^"]+)"', m.group(1))
                info['gatekeeper']['possible_titles'] = titles
        if 'possible_authors' in s:
            m = re.search(r'possible_authors.*?\[([^\]]*)\]', s)
            if m:
                authors = re.findall(r'"([^"]+)"', m.group(1))
                info['gatekeeper']['possible_authors'] = authors

        # Search
        if '🔎 검색:' in s:
            info['search']['queries'].append(s)
        if '🔎 결과:' in s:
            m = re.search(r'(\d+)건', s)
            if m:
                info['search']['total_results'] += int(m.group(1))

        # Decoder
        if '🔤' in s or 'Decoder' in s:
            info['decoder']['lines'].append(s)
        if 'Decoder 분석 시작' in s or 'Decoder.*호출' in s:
            info['decoder']['calls'] += 1
        if '약어스코어' in s or '약어 매칭' in s or 'abbreviation' in s.lower():
            m = re.search(r'score[=:]\s*([\d.]+)', s)
            if m:
                info['decoder']['scores'].append(float(m.group(1)))
        if 'best_match' in s or '최종 선택' in s:
            info['decoder']['best_matches'].append(s)
        if 'guard' in s.lower() or '할루시네이션' in s:
            info['decoder']['guards'].append(s)
        if 'rescue' in s.lower() or 'Rescue' in s:
            info['decoder']['rescues'].append(s)
        if 'morpheme' in s.lower() or '형태소' in s:
            info['decoder']['morphemes'].append(s)
        if 'code_level_hint' in s or 'CODE-LEVEL' in s:
            info['decoder']['code_hints'].append(s)

        # Verifier
        if '🔍' in s or ('Verifier' in s and ('완료' in s or 'is_relevant' in s)):
            info['verifier']['lines'].append(s)
        if 'Verifier' in s and 'is_relevant' in s:
            m = re.search(r'is_relevant["\s:=]+(\w+)', s)
            if m:
                info['verifier']['is_relevant'] = m.group(1).lower() == 'true'
        if '본문증거' in s:
            info['verifier']['body_evidence'] = s

        # Critic
        if '📚' in s or 'Critic' in s:
            info['critic']['lines'].append(s)

        # Arbiter
        if '⚖️' in s or 'Arbiter' in s:
            info['arbiter']['lines'].append(s)
        if 'Arbiter' in s and 'is_relevant' in s:
            m = re.search(r'is_relevant["\s:=]+(\w+)', s)
            if m:
                info['arbiter']['is_relevant'] = m.group(1).lower() == 'true'
        if 'agreeing' in s:
            m = re.search(r'agreeing[:\s]+(\d+)', s)
            if m:
                info['arbiter']['agreeing'] = int(m.group(1))
        if 'dissenting' in s:
            m = re.search(r'dissenting[:\s]+(\d+)', s)
            if m:
                info['arbiter']['dissenting'] = int(m.group(1))
        if '역전' in s or 'reversal' in s.lower():
            info['arbiter']['reversal'] = True

        # Warnings/Errors
        if '⚠️' in s:
            info['warnings'].append(s)
        if 'error' in s.lower() or 'Error' in s:
            info['errors'].append(s)

        # Timings
        m_time = re.search(r'완료\s*\(([\d.]+)s\)', s)
        if m_time:
            for stage in ['gatekeeper', 'decoder', 'verifier', 'critic', 'arbiter']:
                if stage in s.lower():
                    info['timings'][stage] = float(m_time.group(1))
                    break

    info['full_log'] = '\n'.join(full_lines)
    return info


def generate_stage_flow(log_info):
    """파이프라인 스테이지 흐름을 시각적 HTML로 생성"""
    stages = []

    # GK
    gk = log_info['gatekeeper']
    gk_status = '🟢' if not gk['is_noise'] else '🔴'
    gk_label = f"GK {gk_status}"
    gk_detail = f"noise={gk['is_noise']}"
    if gk['possible_titles']:
        gk_detail += f"<br>titles: {', '.join(gk['possible_titles'][:3])}"
    stages.append(('gatekeeper', gk_label, gk_detail, gk['is_noise'] is False))

    # Search
    sq = log_info['search']
    s_label = f"🔎 Search ({len(sq['queries'])}q)"
    s_detail = f"{sq['total_results']}건"
    stages.append(('search', s_label, s_detail, sq['total_results'] > 0))

    # Decoder
    dec = log_info['decoder']
    d_label = f"🔤 Decoder ({dec['calls']}회)"
    d_parts = []
    if dec['scores']:
        d_parts.append(f"scores: {', '.join(f'{s:.2f}' for s in dec['scores'][:3])}")
    if dec['guards']:
        d_parts.append(f"⚠guard: {len(dec['guards'])}")
    if dec['rescues']:
        d_parts.append(f"🆘rescue: {len(dec['rescues'])}")
    if dec['code_hints']:
        d_parts.append(f"💡hints: {len(dec['code_hints'])}")
    d_detail = '<br>'.join(d_parts) if d_parts else '-'
    stages.append(('decoder', d_label, d_detail, bool(dec['best_matches'])))

    # Verifier
    ver = log_info['verifier']
    v_status = '🟢' if ver['is_relevant'] else ('🔴' if ver['is_relevant'] is False else '⚪')
    v_label = f"🔍 Verifier {v_status}"
    v_detail = f"relevant={ver['is_relevant']}"
    if ver['body_evidence']:
        short_ev = ver['body_evidence'][-60:]
        v_detail += f"<br>{short_ev}"
    stages.append(('verifier', v_label, v_detail, ver['is_relevant']))

    # Arbiter
    arb = log_info['arbiter']
    a_status = '🟢' if arb['is_relevant'] else ('🔴' if arb['is_relevant'] is False else '⚪')
    a_label = f"⚖️ Arbiter {a_status}"
    a_parts = [f"relevant={arb['is_relevant']}"]
    if arb['agreeing'] or arb['dissenting']:
        a_parts.append(f"agree={arb['agreeing']} dissent={arb['dissenting']}")
    if arb['reversal']:
        a_parts.append("⚠️ REVERSAL")
    a_detail = '<br>'.join(a_parts)
    stages.append(('arbiter', a_label, a_detail, arb['is_relevant']))

    return stages


def generate_auto_review(item, log_info):
    """자동 심층 검토 (에이전트 의견 v3 — 깊은 교차검증)"""
    ar = item.get('analysis_result', {})
    identity = ar.get('identity', {})
    is_relevant = identity.get('is_relevant', False)
    ni = identity.get('novel_identity') or {}
    title = ni.get('official_title', '')
    confidence = ni.get('confidence', 'N/A') if ni else 'N/A'
    disc_type = identity.get('discussion_type', '')
    reason = identity.get('reason', '') or ''
    evidence = identity.get('evidence', '') or ''
    slang_insight = identity.get('slang_insight', '') or ''
    post_title = item.get('title', '') or ''
    raw_content = item.get('content', '') or ''
    if isinstance(raw_content, list):
        raw_content = '\n'.join(str(c) for c in raw_content)
    comments = item.get('comments', [])
    comment_text = ''
    comment_count = 0
    if isinstance(comments, list):
        comment_count = len(comments)
        for c in comments:
            if isinstance(c, dict):
                comment_text += ' ' + (c.get('content', '') or c.get('text', '') or '')
            elif isinstance(c, str):
                comment_text += ' ' + c
    all_text = post_title + ' ' + raw_content + ' ' + comment_text
    all_text_lower = all_text.lower()

    # detected_titles 분석
    analysis = ar.get('analysis') or {}
    detected_titles = analysis.get('detected_titles') or []
    micro_tags = analysis.get('micro_tags') or []
    sentiment = analysis.get('sentiment_profile') or {}
    is_nsfw = analysis.get('is_nsfw', False)

    # GK 정보
    gk = log_info['gatekeeper']
    gk_titles = gk.get('possible_titles', [])
    gk_authors = gk.get('possible_authors', [])
    gk_is_noise = gk.get('is_noise')

    # Decoder 정보
    dec = log_info['decoder']
    dec_scores = dec.get('scores', [])
    dec_guards = dec.get('guards', [])
    dec_rescues = dec.get('rescues', [])
    dec_code_hints = dec.get('code_hints', [])
    dec_best = dec.get('best_matches', [])

    # Verifier / Arbiter
    ver = log_info['verifier']
    arb = log_info['arbiter']
    search_info = log_info['search']
    warnings = log_info.get('warnings', [])
    errors = log_info.get('errors', [])
    timings = log_info.get('timings', {})
    body_len = len(raw_content.strip())

    flags = []  # (severity, icon, message)
    risk_score = 0

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [A] 공통 분석 — 스테이지간 일관성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # A1. GK vs 최종 판정 불일치
    if gk_is_noise is True and is_relevant:
        flags.append(('warn', '⚠️', 'GK: noise 판정 → 최종: 관련 (GK 뒤집힘, 검증 필요)'))
        risk_score += 2
    elif gk_is_noise is False and not is_relevant and gk_titles:
        flags.append(('info', '🔍', f'GK: not_noise + 후보 {gk_titles[:2]} → 최종: 무관 (FN?)'))
        risk_score += 1

    # A2. Verifier vs Arbiter 불일치
    if ver.get('is_relevant') is not None and arb.get('is_relevant') is not None:
        if ver['is_relevant'] != arb['is_relevant']:
            flags.append(('warn', '⚠️', f"Verifier({ver['is_relevant']}) ≠ Arbiter({arb['is_relevant']}) — 판단 분열"))
            risk_score += 2

    # A3. Arbiter reversal (역전)
    if arb.get('reversal'):
        flags.append(('error', '🔴', 'Arbiter 역전 발생 — 소수 의견이 최종 판정 뒤집음'))
        risk_score += 3

    # A4. 전문가 합의도 분석
    agree = arb.get('agreeing', 0)
    dissent = arb.get('dissenting', 0)
    if agree + dissent > 0:
        agree_ratio = agree / (agree + dissent)
        if agree_ratio < 0.5:
            flags.append(('warn', '⚠️', f'전문가 합의 부족: 찬성{agree} vs 반대{dissent} ({agree_ratio:.0%})'))
            risk_score += 2
        elif agree_ratio < 0.7:
            flags.append(('info', 'ℹ️', f'전문가 의견 분산: 찬성{agree} vs 반대{dissent}'))
            risk_score += 1

    # A5. 처리 시간 이상
    total_time = sum(timings.values()) if timings else 0
    if total_time > 120:
        flags.append(('warn', '⚠️', f'처리 시간 과다: {total_time:.0f}초 — 반복/재시도 가능성'))
        risk_score += 1

    # A6. 에러/경고 발생
    if errors:
        flags.append(('error', '🔴', f'파이프라인 에러 {len(errors)}건 발생'))
        risk_score += 2
    if len(warnings) >= 3:
        flags.append(('warn', '⚠️', f'파이프라인 경고 {len(warnings)}건 — 불안정 처리'))
        risk_score += 1

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [B] True 판정 심층 검증 (FP 탐지)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if is_relevant:
        # B1. Confidence 수준별
        if confidence == 'High':
            flags.append(('info', '✅', 'High confidence 식별'))
        elif confidence == 'Medium':
            flags.append(('warn', '⚠️', 'Medium confidence — 추가 검증 필요'))
            risk_score += 1
        elif confidence == 'Low':
            flags.append(('error', '🔴', 'Low confidence + is_relevant=True — FP 고위험'))
            risk_score += 3

        # B2. 제목 없는 관련 판정
        if not title:
            flags.append(('error', '🔴', '관련 판정인데 official_title 없음'))
            risk_score += 3

        # B3. 제목-본문 교차검증 — 식별된 작품이 본문/제목에 전혀 안 나타남
        if title:
            title_words = [w for w in re.split(r'[\s\-·:]+', title) if len(w) >= 2]
            title_in_post = any(tw in post_title for tw in title_words)
            title_in_body = any(tw in raw_content for tw in title_words)
            title_in_comments = any(tw in comment_text for tw in title_words) if comment_text else False

            # 포스트 제목에서 약어/축약 흔적 확인
            abbr_trace = False
            if len(title) >= 4:
                # 작품 제목의 초성/앞글자가 포스트 제목에 있는지
                first_chars = ''.join(w[0] for w in title.split() if w)
                if len(first_chars) >= 2 and first_chars[:3] in post_title:
                    abbr_trace = True
                # 작품명에서 핵심어 2글자 이상 매칭
                for i in range(len(title) - 1):
                    chunk = title[i:i+2]
                    if chunk in post_title:
                        abbr_trace = True
                        break

            if not title_in_post and not title_in_body and not abbr_trace:
                if not title_in_comments:
                    flags.append(('error', '🔴', f'작품명 "{title[:20]}" — 포스트 어디에도 흔적 없음 (FP 위험)'))
                    risk_score += 3
                else:
                    flags.append(('warn', '⚠️', f'작품명이 댓글에만 등장 — 본문 근거 약함'))
                    risk_score += 1
            elif title_in_post or abbr_trace:
                flags.append(('info', '✅', f'작품명 "{title[:20]}" — 포스트 제목에서 확인'))

        # B4. Decoder guard (할루시네이션 방어) 발동
        if dec_guards:
            flags.append(('warn', '⚠️', f'Decoder guard 발동 {len(dec_guards)}회 — 할루시네이션 의심 있었음'))
            risk_score += 1

        # B5. 약어 매칭 스코어 분석
        if dec_scores:
            max_s = max(dec_scores)
            avg_s = sum(dec_scores) / len(dec_scores)
            if max_s < 0.3:
                flags.append(('error', '🔴', f'약어 스코어 매우 낮음 (max={max_s:.2f}) — 매칭 근거 없음'))
                risk_score += 3
            elif max_s < 0.5:
                flags.append(('warn', '⚠️', f'약어 스코어 낮음 (max={max_s:.2f}, avg={avg_s:.2f})'))
                risk_score += 2
            elif max_s < 0.7:
                flags.append(('info', 'ℹ️', f'약어 스코어 보통 (max={max_s:.2f})'))
            else:
                flags.append(('info', '✅', f'약어 스코어 양호 (max={max_s:.2f})'))

        # B6. 검색 결과 없음 + 관련 판정
        if search_info['total_results'] == 0:
            flags.append(('error', '🔴', '검색 결과 0건인데 관련 판정 — 근거 완전 부재'))
            risk_score += 3
        elif search_info['total_results'] < 3:
            flags.append(('warn', '⚠️', f'검색 결과 {search_info["total_results"]}건 — 근거 빈약'))
            risk_score += 1

        # B7. rescue로만 식별 (정규 디코딩 실패)
        if dec_rescues and not dec_best:
            flags.append(('warn', '⚠️', 'Rescue 메커니즘으로만 식별 — 정규 경로 실패'))
            risk_score += 1

        # B8. 본문이 극히 짧은데 관련 판정
        if body_len < 10:
            flags.append(('warn', '⚠️', f'본문 {body_len}자로 매우 짧음 — 판단 근거 부족'))
            risk_score += 1
        elif body_len < 30:
            flags.append(('info', 'ℹ️', f'본문 짧음 ({body_len}자)'))

        # B9. noise 타입인데 관련 판정 (모순)
        if disc_type == 'noise':
            flags.append(('error', '🔴', 'discussion_type=noise인데 is_relevant=True — 모순'))
            risk_score += 3

        # B10. image_post인데 관련 판정 (이미지 포스트는 텍스트 근거 부족)
        if disc_type == 'image_post' and body_len < 30:
            flags.append(('warn', '⚠️', '이미지 포스트 + 본문 짧음 — 텍스트 근거 부족'))
            risk_score += 1

        # B11. detected_titles 교차 확인
        if detected_titles:
            dt_titles = [dt.get('official_title', '') for dt in detected_titles if dt.get('official_title')]
            dt_confs = [dt.get('confidence', 'N/A') for dt in detected_titles]
            if title and title not in dt_titles:
                flags.append(('warn', '⚠️', f'최종 제목이 detected_titles에 없음'))
                risk_score += 1
            low_conf_dts = [c for c in dt_confs if c == 'Low']
            if low_conf_dts and len(low_conf_dts) == len(dt_confs):
                flags.append(('warn', '⚠️', '모든 detected_titles가 Low confidence'))
                risk_score += 1
        else:
            if is_relevant:
                flags.append(('warn', '⚠️', 'detected_titles가 비어있음'))
                risk_score += 1

        # B12. code_level_hints 활용 여부
        if dec_code_hints:
            flags.append(('info', '💡', f'Code-level hints {len(dec_code_hints)}건 활용'))

        # B13. 본문증거 검증 결과
        if ver.get('body_evidence'):
            be = ver['body_evidence']
            if '실패' in be or 'fail' in be.lower():
                flags.append(('warn', '⚠️', '본문증거 검증 실패'))
                risk_score += 2
            elif '성공' in be or 'pass' in be.lower():
                flags.append(('info', '✅', '본문증거 검증 통과'))

        # B14. reason에서 "추정", "가능성", "불확실" 같은 약한 어조
        weak_words = ['추정', '가능성', '불확실', '명확하지', '확인 불가', '불분명', '약한 근거', '추측']
        found_weak = [w for w in weak_words if w in reason]
        if found_weak:
            flags.append(('info', 'ℹ️', f'판정 사유에 불확실 어조: {found_weak}'))
            risk_score += 1

        # B15. heretic_url 도메인 이상 (팀블라인드, 나무위키 등 비정상 소스)
        h_url = ni.get('heretic_url', '') or ''
        if h_url:
            suspicious_domains = ['teamblind.com', 'namu.wiki', 'wikipedia.org', 'namuwiki']
            for sd in suspicious_domains:
                if sd in h_url:
                    flags.append(('warn', '⚠️', f'heretic_url이 {sd} — 비공식 소스'))
                    risk_score += 1
                    break

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [C] False 판정 심층 검증 (FN 탐지)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    else:
        # C1. 제목에 알려진 작품 약어 패턴
        known_abbr = [
            '즉사무림', '망겜', '마좋', '죽깨수', '헌터상담', '괴담텔',
            '김괴라리', '고향무림', '컵라면', '성좌안무', '흑백소설',
            '개돌', '로판', '갓겜', '빌환', '사펑', '담텔기', '망겜성',
            '즉사기', '마검', '천마', '환생', '나홀로', '솔플', '사펑드래곤',
            '즉무', '괴텔', '고무', '흑소', '무린이', '전직', '이판사',
        ]
        found_abbr = [p for p in known_abbr if p in post_title]
        if found_abbr:
            flags.append(('error', '🔴', f'제목에 작품 약어 감지: {found_abbr} → FN 고위험'))
            risk_score += 3

        # C2. 본문에 작품 약어
        found_abbr_body = [p for p in known_abbr if p in raw_content]
        if found_abbr_body and not found_abbr:
            flags.append(('warn', '⚠️', f'본문에 작품 약어: {found_abbr_body[:3]} → FN 가능'))
            risk_score += 2

        # C3. 소설 토론 키워드 밀도 분석
        novel_kw_strong = ['스포', '스포)', '전개', '결말', '완결', '주인공', '히로인', '빌런',
                           '복선', '떡밥', '클리셰', '연재', '작가', '원작', '후기', '리뷰']
        novel_kw_weak = ['웹소설', '소설', '화', '편', '권', '스토리', '설정', '독자',
                         '캐릭터', '세계관', '장르', '판타지', '무협', '로맨스', '헌터']
        found_strong = [k for k in novel_kw_strong if k in all_text]
        found_weak = [k for k in novel_kw_weak if k in all_text]
        kw_density = len(found_strong) * 2 + len(found_weak)
        if kw_density >= 6:
            flags.append(('error', '🔴', f'소설 키워드 고밀도 ({kw_density}점): 강={found_strong}, 약={found_weak[:3]} → FN 고위험'))
            risk_score += 3
        elif kw_density >= 3:
            flags.append(('warn', '⚠️', f'소설 키워드 감지 ({kw_density}점): {found_strong + found_weak[:3]}'))
            risk_score += 1
        elif found_strong:
            flags.append(('info', 'ℹ️', f'소설 키워드 일부: {found_strong}'))

        # C4. 플랫폼 명시적 언급 + 작품 토론 구조
        platforms = ['문피아', '노벨피아', '카카오페이지', '네이버시리즈', '시리즈',
                     '리디', '리디북스', '조아라', '먼피아', 'munpia', 'novelpia']
        found_plat = [p for p in platforms if p in all_text_lower]
        if found_plat:
            if found_strong:
                flags.append(('warn', '⚠️', f'플랫폼({found_plat}) + 소설키워드({found_strong}) — FN 가능성 높음'))
                risk_score += 2
            else:
                flags.append(('info', 'ℹ️', f'플랫폼 언급: {found_plat}'))

        # C5. GK가 후보 제목을 잡았는데 최종 무관
        if gk_is_noise is False and gk_titles:
            if len(gk_titles) >= 2:
                flags.append(('warn', '⚠️', f'GK가 후보 {len(gk_titles)}개 감지했으나 무관 판정: {gk_titles[:3]}'))
                risk_score += 2
            else:
                flags.append(('info', '🔍', f'GK 후보: {gk_titles[:2]}'))

        # C6. Decoder가 스코어 있는 매칭을 찾았으나 최종 무관
        if dec_scores:
            max_s = max(dec_scores)
            if max_s >= 0.7:
                flags.append(('error', '🔴', f'Decoder 약어매칭 {max_s:.2f}인데 무관 판정 — FN 고위험'))
                risk_score += 3
            elif max_s >= 0.4:
                flags.append(('warn', '⚠️', f'Decoder 약어매칭 {max_s:.2f}인데 무관 — 검토 필요'))
                risk_score += 2

        # C7. 댓글에 작품명 직접 언급
        if comment_text:
            novel_mention_in_comments = False
            # 댓글에서 "~~ 재밌", "~~봤", "~~읽" 패턴
            comment_novel_patterns = [
                r'재밌', r'재미[있없]', r'읽[고었]', r'봤[는어]', r'추천',
                r'완결', r'연재', r'ㅋㅋ', r'작가', r'스포'
            ]
            comment_kw = [p for p in comment_novel_patterns if re.search(p, comment_text)]
            if len(comment_kw) >= 2 and found_strong:
                flags.append(('warn', '⚠️', f'댓글에 소설 토론 패턴: {comment_kw[:3]} + 키워드: {found_strong[:2]}'))
                risk_score += 1

        # C8. discussion_type이 작품 관련인데 무관 판정 (모순)
        related_types = ['review', 'character_talk', 'anticipation', 'recommendation']
        if disc_type in related_types:
            flags.append(('error', '🔴', f'discussion_type={disc_type}인데 is_relevant=False — 모순'))
            risk_score += 3

        # C9. 포스트 제목 구조 분석 — "작품명) 내용" 패턴
        title_patterns = [
            (r'스포\)', 'prefix_spo'),
            (r'^[가-힣]{2,8}\)', 'abbr_paren'),      # "즉무)" 같은 패턴
            (r'[가-힣]{2,6}\s+(ㄹㅇ|솔직히|진짜|마지막|최신)', 'abbr_opinion'),
            (r'(읽|봤|추천|평가|리뷰|후기)', 'review_verb'),
        ]
        for pat, name in title_patterns:
            if re.search(pat, post_title):
                if name == 'prefix_spo':
                    flags.append(('warn', '⚠️', '제목에 "스포)" 접두사 — 작품 스포일러 토론 가능'))
                    risk_score += 2
                elif name == 'abbr_paren' and not found_abbr:
                    flags.append(('info', 'ℹ️', '제목에 "약어)" 패턴 감지'))
                elif name == 'review_verb':
                    flags.append(('info', 'ℹ️', '제목에 리뷰/평가 동사 감지'))
                break

        # C10. 검색 결과가 많았는데 무관 판정
        if search_info['total_results'] >= 10 and gk_titles:
            flags.append(('info', '🔍', f'검색 결과 {search_info["total_results"]}건 + GK 후보 있음 — Decoder/Verifier 단계에서 탈락'))

        # C11. 본문 길이 + 소설 토론 가능성
        if body_len > 100 and found_strong:
            flags.append(('info', 'ℹ️', f'본문 {body_len}자 + 소설 키워드 — 실질 토론 가능성'))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # [D] 특수 케이스 탐지
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # D1. 전체 텍스트가 일본어/영어 — 장르갤 한국어 기대
    han_ratio = sum(1 for c in all_text if '가' <= c <= '힣') / max(len(all_text), 1)
    if han_ratio < 0.2 and len(all_text) > 20:
        flags.append(('info', 'ℹ️', f'한국어 비율 낮음 ({han_ratio:.0%}) — 일어/영문 포스트'))

    # D2. 극단적으로 짧은 포스트 (제목만)
    if body_len == 0 or raw_content.strip() == '':
        flags.append(('info', 'ℹ️', '본문 없음 (제목만 있는 포스트)'))

    # D3. 다중 작품 언급 — detected_titles 2개 이상
    if len(detected_titles) >= 2:
        dt_names = [dt.get('official_title','')[:15] for dt in detected_titles[:3]]
        flags.append(('info', '📚', f'다중 작품 감지: {dt_names}'))

    # D4. NSFW 콘텐츠
    if is_nsfw:
        flags.append(('info', '🔞', 'NSFW 콘텐츠'))

    # 최종: 플래그 없으면 정상
    if not flags:
        flags.append(('info', '✅', '특이사항 없음 — 판정 정상'))

    return flags, risk_score


def build_html(results, log_ranges, log_lines):
    """v2 HTML 대시보드 생성"""
    total = len(results)
    relevant_items = [r for r in results if r.get('analysis_result', {}).get('identity', {}).get('is_relevant')]
    not_relevant_items = [r for r in results if not r.get('analysis_result', {}).get('identity', {}).get('is_relevant')]
    relevant = len(relevant_items)
    not_relevant = len(not_relevant_items)

    # 통계
    conf_counts = Counter()
    type_counts = Counter()
    title_counts = Counter()
    for r in results:
        ni = r.get('analysis_result', {}).get('identity', {}).get('novel_identity') or {}
        c = ni.get('confidence', 'N/A') if ni else 'N/A'
        conf_counts[c] += 1
        t = r.get('analysis_result', {}).get('identity', {}).get('discussion_type') or 'N/A'
        type_counts[t] += 1
        tit = ni.get('official_title', '')
        if tit:
            title_counts[tit] += 1

    # 식별된 작품 목록 HTML
    title_list_html = ''
    for tit, cnt in title_counts.most_common(30):
        title_list_html += f'<div class="title-item"><span class="title-name">{html_mod.escape(tit)}</span> <span class="title-cnt">×{cnt}</span></div>\n'

    # 각 행 생성
    rows_html = []
    risk_items = []  # (risk_score, idx, post_id, post_title)

    for idx, item in enumerate(results):
        post_id = item['post_id']
        post_title = html_mod.escape(str(item.get('title', '') or ''))
        post_url = html_mod.escape(str(item.get('url', '') or ''))
        raw_content = item.get('content', '') or ''
        if isinstance(raw_content, list):
            raw_content = '\n'.join(str(c) for c in raw_content)
        post_content_full = html_mod.escape(str(raw_content))
        post_content = post_content_full[:300]
        post_author = html_mod.escape(str(item.get('author', '') or ''))
        comments = item.get('comments', [])
        comment_count = len(comments) if isinstance(comments, list) else 0
        comment_preview = ''
        if isinstance(comments, list) and comments:
            for c in comments[:5]:
                if isinstance(c, dict):
                    ctext = c.get('content', '') or c.get('text', '') or ''
                    cauthor = c.get('author', '') or ''
                    comment_preview += f'[{html_mod.escape(str(cauthor))}] {html_mod.escape(str(ctext)[:80])}\n'
                elif isinstance(c, str):
                    comment_preview += html_mod.escape(str(c)[:80]) + '\n'

        ar = item.get('analysis_result', {})
        identity = ar.get('identity', {})
        is_relevant = identity.get('is_relevant', False)
        ni = identity.get('novel_identity') or {}
        official_title = html_mod.escape(ni.get('official_title', '') or '')
        confidence = ni.get('confidence', 'N/A') if ni else 'N/A'
        heretic_url = html_mod.escape(ni.get('heretic_url', '') or '')
        disc_type = html_mod.escape(str(identity.get('discussion_type', '') or ''))
        reason = html_mod.escape(str(identity.get('reason', '') or ''))
        slang_insight = html_mod.escape(str(identity.get('slang_insight', '') or ''))
        evidence = html_mod.escape(str(identity.get('evidence', '') or ''))

        # analysis 섹션
        analysis = ar.get('analysis') or {}
        detected_titles = analysis.get('detected_titles') or []
        dt_html = ''
        for dt in detected_titles:
            dt_title = html_mod.escape(str(dt.get('official_title', '') or ''))
            dt_conf = dt.get('confidence', '?')
            dt_alias = html_mod.escape(str(dt.get('alias_or_mention', '') or ''))
            dt_html += f'<div class="dt-item"><span class="dt-title">{dt_title}</span> <span class="badge badge-conf-{dt_conf.lower() if dt_conf in ("High","Medium","Low") else "na"}">{dt_conf}</span>'
            if dt_alias:
                dt_html += f' <span class="dt-alias">({dt_alias})</span>'
            dt_html += '</div>\n'

        micro_tags = analysis.get('micro_tags', [])
        tags_html = ' '.join(f'<span class="micro-tag">{html_mod.escape(str(t))}</span>' for t in (micro_tags or []))

        sentiment = analysis.get('sentiment_profile', {})
        sentiment_str = sentiment.get('sentiment', 'N/A') if sentiment else 'N/A'
        is_nsfw = analysis.get('is_nsfw', False)

        # 로그 정보
        log_info = extract_log_details(log_lines, *log_ranges[post_id]) if post_id in log_ranges else {
            'gatekeeper': {'lines': [], 'is_noise': None, 'possible_titles': [], 'possible_authors': [], 'confidence': None},
            'decoder': {'lines': [], 'calls': 0, 'best_matches': [], 'scores': [], 'guards': [], 'rescues': [], 'morphemes': [], 'code_hints': []},
            'verifier': {'lines': [], 'is_relevant': None, 'confidence': None, 'body_evidence': None},
            'critic': {'lines': []},
            'arbiter': {'lines': [], 'is_relevant': None, 'confidence': None, 'agreeing': 0, 'dissenting': 0, 'reversal': False},
            'search': {'queries': [], 'total_results': 0},
            'warnings': [], 'errors': [], 'timings': {}, 'full_log': ''
        }

        # 자동 검토
        review_flags, risk_score = generate_auto_review(item, log_info)
        risk_items.append((risk_score, idx, post_id, item.get('title', '')))

        # 플래그 HTML
        flags_html = ''
        for sev, icon, msg in review_flags:
            css = 'flag-error' if sev == 'error' else ('flag-warn' if sev == 'warn' else 'flag-info')
            flags_html += f'<div class="flag {css}">{icon} {html_mod.escape(msg)}</div>\n'

        # 스테이지 흐름
        stage_flow = generate_stage_flow(log_info)
        flow_html = '<div class="stage-flow">'
        for i, (stage_id, label, detail, ok) in enumerate(stage_flow):
            css = 'stage-ok' if ok else ('stage-fail' if ok is False else 'stage-skip')
            flow_html += f'<div class="stage-box {css}"><div class="stage-label">{label}</div><div class="stage-detail">{detail}</div></div>'
            if i < len(stage_flow) - 1:
                flow_html += '<div class="stage-arrow">→</div>'
        flow_html += '</div>'

        # 로그 요약 (주요 라인들)
        log_sections = []
        if log_info['gatekeeper']['lines']:
            log_sections.append('📋 Gatekeeper:\n' + '\n'.join(l[:180] for l in log_info['gatekeeper']['lines'][:5]))
        if log_info['decoder']['lines']:
            log_sections.append('🔤 Decoder:\n' + '\n'.join(l[:180] for l in log_info['decoder']['lines'][:8]))
        if log_info['search']['queries']:
            log_sections.append(f'🔎 Search ({len(log_info["search"]["queries"])}건):\n' + '\n'.join(l[:150] for l in log_info['search']['queries'][:6]))
        if log_info['verifier']['lines']:
            log_sections.append('🔍 Verifier:\n' + '\n'.join(l[:180] for l in log_info['verifier']['lines'][:5]))
        if log_info['arbiter']['lines']:
            log_sections.append('⚖️ Arbiter:\n' + '\n'.join(l[:180] for l in log_info['arbiter']['lines'][:5]))
        if log_info['warnings']:
            log_sections.append(f'⚠️ Warnings ({len(log_info["warnings"])}):\n' + '\n'.join(l[:180] for l in log_info['warnings'][:5]))
        log_summary_text = html_mod.escape('\n\n'.join(log_sections))
        full_log_escaped = html_mod.escape(log_info['full_log'][:15000])

        # 타이밍
        timing_html = ''
        if log_info['timings']:
            timing_parts = [f'{k}: {v:.1f}s' for k, v in log_info['timings'].items()]
            timing_html = f'<div class="timing-info">⏱ {" | ".join(timing_parts)}</div>'

        # CSS 클래스
        rel_class = 'relevant' if is_relevant else 'not-relevant'
        conf_class = confidence.lower() if confidence in ('High', 'Medium', 'Low') else 'na'
        risk_class = 'risk-high' if risk_score >= 3 else ('risk-med' if risk_score >= 1 else 'risk-low')

        row = f'''
        <tr class="result-row {rel_class} {risk_class}" data-post-id="{post_id}" data-relevant="{str(is_relevant).lower()}" data-confidence="{confidence}" data-type="{disc_type}" data-risk="{risk_score}" data-idx="{idx}">
            <td class="col-idx">{idx + 1}</td>
            <td class="col-check">
                <div class="row-status-group" data-post-id="{post_id}">
                    <button class="rs-btn active" data-val="" onclick="setRowStatus(this)">미검토</button>
                    <button class="rs-btn" data-val="correct" onclick="setRowStatus(this)">✅정확</button>
                    <button class="rs-btn" data-val="fp" onclick="setRowStatus(this)">❌오탐</button>
                    <button class="rs-btn" data-val="fn" onclick="setRowStatus(this)">❌미탐</button>
                    <button class="rs-btn" data-val="partial" onclick="setRowStatus(this)">⚠부분</button>
                    <button class="rs-btn" data-val="unclear" onclick="setRowStatus(this)">❓</button>
                </div>
                <div class="risk-badge risk-{risk_class}">risk:{risk_score}</div>
            </td>
            <td class="col-postid">
                <a href="{post_url}" target="_blank" title="{post_url}">{post_id}</a>
            </td>
            <td class="col-post">
                <div class="post-title-text" title="{post_title}">📌 {post_title}</div>
                <div class="post-author">👤 {post_author}</div>
                <div class="post-content-preview">{post_content[:120]}{'…' if len(post_content) > 120 else ''}</div>
                <button class="btn-expand" onclick="toggleEl(this)">내용 더보기</button>
                <div class="detail-full" style="display:none">
                    <div class="full-content">{post_content_full}</div>
                    {f'<div class="comments-section"><strong>💬 댓글 ({comment_count}개):</strong><pre>{comment_preview}</pre></div>' if comment_preview else f'<div class="comment-info">💬 댓글 {comment_count}개</div>'}
                </div>
            </td>
            <td class="col-result">
                <span class="badge badge-{rel_class}">{'✅ 관련' if is_relevant else '❌ 무관'}</span>
                <span class="badge badge-conf-{conf_class}">{confidence}</span>
                {f'<span class="badge badge-nsfw">🔞 NSFW</span>' if is_nsfw else ''}
                <div class="result-title">{official_title or '<span class="no-title">-</span>'}</div>
                <div class="result-type-badge">{disc_type}</div>
                {dt_html}
                <div class="tags-row">{tags_html}</div>
                {timing_html}
            </td>
            <td class="col-pipeline">
                {flow_html}
                <button class="btn-expand" onclick="toggleEl(this)">로그 상세</button>
                <div class="detail-full" style="display:none"><pre class="log-pre">{log_summary_text}</pre></div>
                <button class="btn-expand btn-fulllog" onclick="toggleFullLog(this)" data-pid="{post_id}">전체 로그</button>
                <div class="detail-full fulllog-container" style="display:none" data-pid="{post_id}"></div>
            </td>
            <td class="col-reason">
                <div class="reason-text">{reason[:250]}{'…' if len(reason) > 250 else ''}</div>
                <button class="btn-expand" onclick="toggleEl(this)">전체 사유</button>
                <div class="detail-full" style="display:none">{reason}</div>
                {f'<div class="evidence-text">📎 {evidence[:150]}</div>' if evidence else ''}
                {f'<div class="slang-text">🗣 {slang_insight[:150]}</div>' if slang_insight else ''}
            </td>
            <td class="col-review">
                <div class="auto-review">{flags_html}</div>
            </td>
            <td class="col-user">
                <textarea class="user-opinion-input" data-post-id="{post_id}" placeholder="의견 입력..."></textarea>
                <select class="ground-truth-select" data-post-id="{post_id}">
                    <option value="">정답 선택</option>
                    <option value="relevant">관련 포스트</option>
                    <option value="not-relevant">무관 포스트</option>
                </select>
                <input class="gt-title-input" data-post-id="{post_id}" placeholder="정답 작품명 (옵션)">
            </td>
        </tr>'''
        rows_html.append(row)

    # 로그 데이터 (lazy-load용, JS에서 필요 시 로드)
    log_data_map = {}
    for item in results:
        pid = item['post_id']
        if pid in log_ranges:
            li = extract_log_details(log_lines, *log_ranges[pid])
            log_data_map[str(pid)] = li['full_log'][:15000]

    # 위험도 상위 항목
    risk_items.sort(key=lambda x: -x[0])
    top_risk_html = ''
    for score, idx, pid, ptitle in risk_items[:20]:
        if score > 0:
            top_risk_html += f'<div class="risk-item" onclick="scrollToRow({idx})"><span class="risk-score">⚠{score}</span> #{idx+1} [{pid}] {html_mod.escape(str(ptitle or "")[:50])}</div>\n'

    # 타입별 통계 HTML
    type_stats_html = ''.join(
        f'<span class="stat-tag">{t}: {c}</span>' for t, c in type_counts.most_common()
    )
    conf_stats_html = ''.join(
        f'<span class="stat-tag conf-{c.lower() if c in ("High","Medium","Low") else "na"}">{c}: {v}</span>'
        for c, v in conf_counts.most_common()
    )

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>파이프라인 리뷰 대시보드 v2</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; background: #0d1117; color: #c9d1d9; font-size: 13px; }}

/* ── 상단 고정 영역 ── */
.top-fixed {{
    position: fixed; top: 0; left: 0; right: 0; z-index: 200;
    background: #0d1117;
}}
#top-spacer {{ height: 0; }}

/* ── 헤더 ── */
.header {{
    background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
    padding: 12px 24px;
    border-bottom: 1px solid #30363d;
}}
.header h1 {{ color: #58a6ff; font-size: 18px; margin-bottom: 6px; }}
.header .subtitle {{ color: #8b949e; font-size: 12px; margin-bottom: 8px; }}

.stats-bar {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
.stat-box {{
    background: #21262d; border: 1px solid #30363d; border-radius: 6px;
    padding: 4px 12px; display: flex; flex-direction: column; align-items: center;
    min-width: 60px;
}}
.stat-box .sv {{ font-size: 18px; font-weight: 700; }}
.stat-box .sl {{ font-size: 10px; color: #8b949e; }}
.stat-box.s-rel .sv {{ color: #3fb950; }}
.stat-box.s-nrel .sv {{ color: #f85149; }}
.stat-box.s-fp .sv {{ color: #f85149; }}
.stat-box.s-fn .sv {{ color: #d29922; }}
.stat-box.s-review .sv {{ color: #58a6ff; }}

/* ── 필터 ── */
.filter-bar {{
    background: #161b22; padding: 6px 24px; border-bottom: 1px solid #30363d;
    display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}}
.filter-bar label {{ color: #8b949e; font-size: 11px; }}
.filter-bar select, .filter-bar input {{
    background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
    border-radius: 4px; padding: 3px 6px; font-size: 11px;
}}
.filter-bar button {{
    background: #238636; color: white; border: none; border-radius: 4px;
    padding: 3px 10px; cursor: pointer; font-size: 11px;
}}
.filter-bar button:hover {{ background: #2ea043; }}
.filter-bar .btn-export {{ background: #8957e5; }}
.filter-bar .btn-export:hover {{ background: #a371f7; }}
.filter-bar .btn-save {{ background: #1f6feb; }}
.filter-bar .btn-load {{ background: #388bfd; }}
.filter-bar .btn-reset {{ background: #484f58; }}

/* ── 검토상태 버튼 그룹 ── */
.status-btn-group {{
    display: flex; gap: 2px; margin-left: 8px;
}}
.status-btn {{
    background: #21262d; border: 1px solid #30363d; color: #8b949e;
    border-radius: 4px; padding: 3px 10px; cursor: pointer; font-size: 11px;
    transition: all 0.15s;
}}
.status-btn:hover {{ border-color: #58a6ff; color: #c9d1d9; }}
.status-btn.active {{ background: #1f6feb; border-color: #58a6ff; color: #fff; font-weight: 600; }}
.status-btn.active[data-val="correct"] {{ background: #238636; border-color: #3fb950; }}
.status-btn.active[data-val="fp"] {{ background: #9b1c1c; border-color: #f85149; }}
.status-btn.active[data-val="fn"] {{ background: #7c5c00; border-color: #d29922; }}
.status-btn.active[data-val="partial"] {{ background: #5a4000; border-color: #d29922; }}
.status-btn.active[data-val="unclear"] {{ background: #30363d; border-color: #8b949e; }}

/* ── 사이드패널 (탭) ── */
.tabs-bar {{
    background: #161b22; padding: 0 24px; border-bottom: 1px solid #30363d;
    display: flex; gap: 0;
}}
.tab-btn {{
    background: none; border: none; color: #8b949e; padding: 6px 14px;
    cursor: pointer; font-size: 12px; border-bottom: 2px solid transparent;
}}
.tab-btn:hover {{ color: #c9d1d9; }}
.tab-btn.active {{ color: #58a6ff; border-bottom-color: #58a6ff; }}
.tab-panel {{ display: none; padding: 8px 24px; background: #0d1117; border-bottom: 1px solid #30363d; max-height: 200px; overflow-y: auto; }}
.tab-panel.active {{ display: block; }}

.stat-tag {{ display: inline-block; background: #21262d; border: 1px solid #30363d; border-radius: 4px; padding: 2px 8px; margin: 2px; font-size: 11px; }}
.stat-tag.conf-high {{ border-color: #3fb950; color: #3fb950; }}
.stat-tag.conf-medium {{ border-color: #d29922; color: #d29922; }}
.stat-tag.conf-low {{ border-color: #f85149; color: #f85149; }}

.title-item {{ display: inline-flex; align-items: center; gap: 4px; background: #21262d; border: 1px solid #30363d; border-radius: 4px; padding: 2px 8px; margin: 2px; font-size: 11px; }}
.title-name {{ color: #79c0ff; }}
.title-cnt {{ color: #8b949e; font-size: 10px; }}

.risk-item {{ cursor: pointer; padding: 3px 6px; margin: 2px 0; border-radius: 4px; font-size: 11px; }}
.risk-item:hover {{ background: #21262d; }}
.risk-score {{ color: #f85149; font-weight: bold; margin-right: 6px; }}

/* ── 테이블 ── */
.table-wrap {{ padding: 0 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; table-layout: fixed; }}
thead {{ position: sticky; top: 0; z-index: 100; }}
th {{
    background: #21262d; color: #58a6ff; padding: 7px 5px;
    border: 1px solid #30363d; font-weight: 600; text-align: left;
    white-space: nowrap; font-size: 11px;
}}
td {{
    padding: 5px; border: 1px solid #1c2128; vertical-align: top;
    word-break: break-word;
}}
tr:hover {{ background: #161b22; }}
tr.relevant {{ border-left: 3px solid #3fb950; }}
tr.not-relevant {{ border-left: 3px solid #484f58; }}
tr.risk-high {{ background: #2d1616 !important; }}

.col-idx {{ width: 30px; text-align: center; }}
.col-check {{ width: 115px; }}
.col-postid {{ width: 65px; }}
.col-post {{ width: 220px; }}
.col-result {{ width: 180px; }}
.col-pipeline {{ width: 280px; }}
.col-reason {{ width: 200px; }}
.col-review {{ width: 180px; }}
.col-user {{ width: 160px; }}

/* ── 뱃지 ── */
.badge {{
    display: inline-block; padding: 1px 5px; border-radius: 3px;
    font-size: 10px; font-weight: 600; margin: 1px;
}}
.badge-relevant {{ background: #0d3321; color: #3fb950; }}
.badge-not-relevant {{ background: #3d1a1a; color: #f85149; }}
.badge-conf-high {{ background: #0d3321; color: #3fb950; }}
.badge-conf-medium {{ background: #3d2e00; color: #d29922; }}
.badge-conf-low {{ background: #3d1a1a; color: #f85149; }}
.badge-conf-na {{ background: #21262d; color: #8b949e; }}
.badge-conf-n\\/a {{ background: #21262d; color: #8b949e; }}
.badge-nsfw {{ background: #3d1a1a; color: #f85149; }}

.result-title {{ color: #79c0ff; font-weight: 600; margin-top: 3px; font-size: 12px; }}
.result-type-badge {{ display: inline-block; background: #21262d; border: 1px solid #30363d; border-radius: 3px; padding: 1px 5px; font-size: 10px; color: #d2a8ff; margin-top: 3px; }}
.no-title {{ color: #484f58; }}

.dt-item {{ font-size: 11px; margin: 2px 0; padding: 2px 4px; background: #161b22; border-radius: 3px; }}
.dt-title {{ color: #79c0ff; }}
.dt-alias {{ color: #8b949e; font-size: 10px; }}

.micro-tag {{ display: inline-block; background: #1c2333; border: 1px solid #30363d; border-radius: 3px; padding: 0 4px; font-size: 9px; color: #8b949e; margin: 1px; }}

.tags-row {{ margin-top: 3px; }}
.timing-info {{ font-size: 10px; color: #484f58; margin-top: 3px; }}

/* ── 포스트 ── */
.post-title-text {{ color: #c9d1d9; font-weight: 600; font-size: 12px; line-height: 1.3; }}
.post-author {{ color: #484f58; font-size: 10px; }}
.post-content-preview {{ font-size: 11px; color: #8b949e; margin-top: 3px; line-height: 1.3; }}
.comment-info {{ font-size: 10px; color: #484f58; margin-top: 2px; }}
.comments-section {{ margin-top: 6px; }}
.comments-section pre {{ font-size: 10px; color: #8b949e; white-space: pre-wrap; }}

/* ── 스테이지 흐름 ── */
.stage-flow {{ display: flex; align-items: center; gap: 2px; flex-wrap: wrap; margin-bottom: 6px; }}
.stage-box {{
    background: #21262d; border: 1px solid #30363d; border-radius: 4px;
    padding: 3px 6px; min-width: 50px; font-size: 10px;
}}
.stage-ok {{ border-color: #238636; }}
.stage-fail {{ border-color: #f85149; background: #2d1616; }}
.stage-skip {{ border-color: #484f58; opacity: 0.6; }}
.stage-label {{ font-weight: 600; font-size: 10px; white-space: nowrap; }}
.stage-detail {{ font-size: 9px; color: #8b949e; line-height: 1.2; }}
.stage-arrow {{ color: #484f58; font-size: 12px; }}

/* ── 사유/로그 ── */
.reason-text {{ font-size: 11px; line-height: 1.3; color: #8b949e; max-height: 80px; overflow: hidden; }}
.evidence-text {{ font-size: 10px; color: #7ee787; margin-top: 3px; }}
.slang-text {{ font-size: 10px; color: #d2a8ff; margin-top: 2px; }}

.btn-expand {{
    background: #30363d; color: #8b949e; border: none; border-radius: 3px;
    padding: 1px 5px; cursor: pointer; font-size: 9px; margin-top: 3px;
}}
.btn-expand:hover {{ background: #484f58; color: #c9d1d9; }}
.detail-full {{
    margin-top: 4px; padding: 5px; background: #0d1117; border: 1px solid #30363d;
    border-radius: 4px; font-size: 11px; max-height: 400px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-word; line-height: 1.3;
}}
.log-pre {{ font-size: 10px; white-space: pre-wrap; word-break: break-word; }}
.full-log {{ max-height: 500px; overflow-y: auto; font-size: 10px; contain: content; }}
.full-content {{ white-space: pre-wrap; }}

/* ── 자동 검토 플래그 ── */
.flag {{ font-size: 11px; padding: 2px 4px; margin: 1px 0; border-radius: 3px; line-height: 1.3; }}
.flag-error {{ background: #3d1a1a; color: #f85149; }}
.flag-warn {{ background: #3d2e00; color: #d29922; }}
.flag-info {{ color: #8b949e; }}

.risk-badge {{ font-size: 9px; text-align: center; margin-top: 3px; padding: 1px 4px; border-radius: 3px; }}
.risk-risk-high {{ background: #3d1a1a; color: #f85149; }}
.risk-risk-med {{ background: #3d2e00; color: #d29922; }}
.risk-risk-low {{ color: #484f58; }}

/* ── 사용자 입력 ── */
.ground-truth-select {{
    background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
    border-radius: 3px; padding: 2px 3px; font-size: 10px; width: 100%;
    margin-bottom: 3px;
}}

/* ── 행별 검토 버튼 그룹 ── */
.row-status-group {{
    display: flex; flex-wrap: wrap; gap: 2px;
}}
.rs-btn {{
    background: #161b22; border: 1px solid #30363d; color: #6e7681;
    border-radius: 3px; padding: 2px 5px; cursor: pointer; font-size: 9px;
    transition: all 0.12s; white-space: nowrap; line-height: 1.2;
}}
.rs-btn:hover {{ border-color: #58a6ff; color: #c9d1d9; }}
.rs-btn.active {{ font-weight: 700; }}
.rs-btn.active[data-val=""] {{ background: #21262d; border-color: #484f58; color: #8b949e; }}
.rs-btn.active[data-val="correct"] {{ background: #0d3321; border-color: #3fb950; color: #3fb950; }}
.rs-btn.active[data-val="fp"] {{ background: #3d1a1a; border-color: #f85149; color: #f85149; }}
.rs-btn.active[data-val="fn"] {{ background: #3d2e00; border-color: #d29922; color: #d29922; }}
.rs-btn.active[data-val="partial"] {{ background: #2d2600; border-color: #d29922; color: #d29922; }}
.rs-btn.active[data-val="unclear"] {{ background: #1c1c2e; border-color: #8b8be0; color: #8b8be0; }}
.user-opinion-input {{
    width: 100%; min-height: 45px; background: #0d1117; border: 1px solid #30363d;
    color: #c9d1d9; border-radius: 3px; padding: 3px; font-size: 10px;
    font-family: inherit; resize: vertical; margin-bottom: 3px;
}}
.gt-title-input {{
    width: 100%; background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
    border-radius: 3px; padding: 2px 4px; font-size: 10px; margin-top: 3px;
}}

a {{ color: #58a6ff; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.footer {{
    padding: 8px 24px; background: #161b22; border-top: 1px solid #30363d;
    font-size: 11px; color: #8b949e; display: flex; justify-content: space-between;
    position: sticky; bottom: 0; z-index: 100;
}}

/* 검토상태 하이라이트 */
tr[data-status="correct"] {{ background: rgba(56,139,253,0.04); }}
tr[data-status="fp"] {{ background: rgba(248,81,73,0.06); }}
tr[data-status="fn"] {{ background: rgba(210,153,34,0.06); }}
tr[data-status="partial"] {{ background: rgba(210,153,34,0.04); }}

@media print {{
    .filter-bar, .header, .tabs-bar, .footer {{ position: static; }}
    .detail-full {{ display: block !important; max-height: none; }}
    tr.risk-high {{ background: #fff0f0 !important; }}
}}
</style>
</head>
<body>

<!-- 상단 고정 영역 -->
<div class="top-fixed" id="top-fixed">
<!-- 헤더 -->
<div class="header">
    <h1>🔍 파이프라인 결과 리뷰 대시보드 v2</h1>
    <div class="subtitle">결과: {Path(RESULT_FILE).name} | 로그: {Path(LOG_FILE).name} | 생성: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
    <div class="stats-bar">
        <div class="stat-box"><span class="sv">{total}</span><span class="sl">전체</span></div>
        <div class="stat-box s-rel"><span class="sv">{relevant}</span><span class="sl">관련(T)</span></div>
        <div class="stat-box s-nrel"><span class="sv">{not_relevant}</span><span class="sl">무관(F)</span></div>
        <div class="stat-box"><span class="sv">{len(title_counts)}</span><span class="sl">식별 작품수</span></div>
        <div class="stat-box s-review"><span class="sv" id="cnt-reviewed">0</span><span class="sl">검토완료</span></div>
        <div class="stat-box s-rel"><span class="sv" id="cnt-correct">0</span><span class="sl">정확</span></div>
        <div class="stat-box s-fp"><span class="sv" id="cnt-fp">0</span><span class="sl">FP</span></div>
        <div class="stat-box s-fn"><span class="sv" id="cnt-fn">0</span><span class="sl">FN</span></div>
        <div class="stat-box"><span class="sv" id="cnt-partial">0</span><span class="sl">부분</span></div>
    </div>
</div>

<!-- 필터 -->
<div class="filter-bar">
    <label>필터:</label>
    <select id="f-rel" onchange="applyFilters()">
        <option value="">전체</option>
        <option value="true">✅ 관련</option>
        <option value="false">❌ 무관</option>
    </select>
    <select id="f-conf" onchange="applyFilters()">
        <option value="">Confidence</option>
        <option value="High">High</option>
        <option value="Medium">Medium</option>
        <option value="Low">Low</option>
        <option value="N/A">N/A</option>
    </select>
    <div class="status-btn-group">
        <button class="status-btn active" data-val="unreviewed" onclick="toggleStatusFilter(this)">미검토</button>
        <button class="status-btn" data-val="correct" onclick="toggleStatusFilter(this)">✅ 정확</button>
        <button class="status-btn" data-val="fp" onclick="toggleStatusFilter(this)">❌ 오탐</button>
        <button class="status-btn" data-val="fn" onclick="toggleStatusFilter(this)">❌ 미탐</button>
        <button class="status-btn" data-val="partial" onclick="toggleStatusFilter(this)">⚠️ 부분</button>
        <button class="status-btn" data-val="unclear" onclick="toggleStatusFilter(this)">❓ 불명확</button>
        <button class="status-btn" data-val="" onclick="toggleStatusFilter(this)">전체</button>
    </div>
    <select id="f-type" onchange="applyFilters()">
        <option value="">Type</option>
        {''.join(f'<option value="{t}">{t} ({c})</option>' for t, c in type_counts.most_common())}
    </select>
    <select id="f-risk" onchange="applyFilters()">
        <option value="">Risk</option>
        <option value="high">🔴 High (≥3)</option>
        <option value="med">🟡 Med (1-2)</option>
        <option value="low">🟢 Low (0)</option>
    </select>
    <input type="text" id="f-search" placeholder="검색..." onkeyup="applyFilters()" style="width:120px">
    <button onclick="applyFilters()">🔍</button>
    <button class="btn-reset" onclick="resetFilters()">초기화</button>
    <button class="btn-export" onclick="exportReview()">📥 내보내기</button>
    <button class="btn-save" onclick="saveLocal()">💾 저장</button>
    <button class="btn-load" onclick="loadLocal()">📂 불러오기</button>
</div>

<!-- 탭 패널 (top-fixed 내부) -->
<div class="tabs-bar">
    <button class="tab-btn active" onclick="switchTab(this,'tab-stats')">📊 통계</button>
    <button class="tab-btn" onclick="switchTab(this,'tab-titles')">📚 식별 작품</button>
    <button class="tab-btn" onclick="switchTab(this,'tab-risk')">⚠️ 위험 항목</button>
</div>
<div id="tab-stats" class="tab-panel active">
    <strong>Discussion Types:</strong> {type_stats_html}<br>
    <strong>Confidence:</strong> {conf_stats_html}
</div>
<div id="tab-titles" class="tab-panel">
    <strong>식별된 작품 ({len(title_counts)}종):</strong><br>
    {title_list_html}
</div>
<div id="tab-risk" class="tab-panel">
    <strong>자동 검토 위험도 상위 항목 (검토 우선):</strong><br>
    {top_risk_html}
</div>
</div><!-- /top-fixed -->
<div id="top-spacer"></div>

<!-- 테이블 -->
<div class="table-wrap">
<table id="review-table">
<thead>
<tr>
    <th class="col-idx">#</th>
    <th class="col-check">검토</th>
    <th class="col-postid">ID</th>
    <th class="col-post">포스트</th>
    <th class="col-result">판정 결과</th>
    <th class="col-pipeline">파이프라인 흐름</th>
    <th class="col-reason">판정 사유</th>
    <th class="col-review">🤖 자동 검토</th>
    <th class="col-user">👤 사용자 검토</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>

<div class="footer">
    <span id="filter-info">전체 {total}건 표시</span>
    <span>Pipeline Review Dashboard v2 | {datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
</div>

<script id="log-data-json" type="application/json">
''' + json.dumps(log_data_map, ensure_ascii=False).replace('</script>', '<\\/script>') + f'''
</script>

<script>
const STORAGE_KEY = 'pipeline_review_v2_{Path(RESULT_FILE).stem}';
let _currentStatusFilter = 'unreviewed';  // 기본 필터: 미검토

// ── thead sticky top + spacer 동적 계산 ──
function updateStickyTop() {{
    const topFixed = document.getElementById('top-fixed');
    const spacer = document.getElementById('top-spacer');
    if (topFixed) {{
        const h = topFixed.offsetHeight;
        if (spacer) spacer.style.height = h + 'px';
        document.querySelector('thead').style.top = h + 'px';
    }}
}}
window.addEventListener('resize', updateStickyTop);
window.addEventListener('load', updateStickyTop);
setTimeout(updateStickyTop, 0);
setTimeout(updateStickyTop, 100);
setTimeout(updateStickyTop, 500);
// ResizeObserver로 top-fixed 높이 변경 자동 추적
(function() {{
    const tf = document.getElementById('top-fixed');
    if (tf && typeof ResizeObserver !== 'undefined') {{
        new ResizeObserver(updateStickyTop).observe(tf);
    }}
}})();

// ── 탭 전환 ──
function switchTab(btn, tabId) {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(tabId).classList.add('active');
    // 탭 변경 시 높이 재계산
    requestAnimationFrame(updateStickyTop);
}}

// ── 검토상태 버튼 그룹 토글 ──
function toggleStatusFilter(btn) {{
    document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    _currentStatusFilter = btn.dataset.val;
    applyFilters();
}}

// ── 상세 토글 ──
function toggleEl(btn) {{
    const d = btn.nextElementSibling;
    if (d.style.display === 'none') {{
        d.style.display = 'block';
        btn.textContent = '접기';
    }} else {{
        d.style.display = 'none';
        btn.textContent = btn.dataset.origLabel || '더보기';
    }}
}}

// ── 전체 로그 lazy 로딩 ──
function toggleFullLog(btn) {{
    const container = btn.nextElementSibling;
    if (container.style.display !== 'none') {{
        container.style.display = 'none';
        btn.textContent = '전체 로그';
        return;
    }}
    // 이미 로드됐으면 보이기만
    if (container.dataset.loaded) {{
        container.style.display = 'block';
        btn.textContent = '접기';
        return;
    }}
    // lazy 로드: _logDataMap에서 가져옴
    const pid = btn.dataset.pid;
    const logText = _logDataMap[pid] || '(로그 없음)';
    const pre = document.createElement('pre');
    pre.className = 'full-log';
    pre.textContent = logText;  // textContent로 안전하게 삽입
    container.appendChild(pre);
    container.dataset.loaded = '1';
    container.style.display = 'block';
    btn.textContent = '접기';
}}

// 버튼 원본 라벨 저장
document.querySelectorAll('.btn-expand').forEach(b => {{ b.dataset.origLabel = b.textContent; }});

// ── 행별 검토 상태 변경 ──
function setRowStatus(btn) {{
    const grp = btn.closest('.row-status-group');
    grp.querySelectorAll('.rs-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const row = btn.closest('tr');
    row.setAttribute('data-status', btn.dataset.val);
    updateCounts();
}}

function getRowStatus(row) {{
    const active = row.querySelector('.rs-btn.active');
    return active ? active.dataset.val : '';
}}

function setRowStatusValue(row, val) {{
    const grp = row.querySelector('.row-status-group');
    if (!grp) return;
    grp.querySelectorAll('.rs-btn').forEach(b => {{
        b.classList.toggle('active', b.dataset.val === val);
    }});
    row.setAttribute('data-status', val);
}}

function updateCounts() {{
    let reviewed=0, correct=0, fp=0, fn=0, partial=0;
    document.querySelectorAll('.row-status-group').forEach(grp => {{
        const active = grp.querySelector('.rs-btn.active');
        const v = active ? active.dataset.val : '';
        if(v) reviewed++;
        if(v==='correct') correct++;
        if(v==='fp') fp++;
        if(v==='fn') fn++;
        if(v==='partial') partial++;
    }});
    document.getElementById('cnt-reviewed').textContent = reviewed;
    document.getElementById('cnt-correct').textContent = correct;
    document.getElementById('cnt-fp').textContent = fp;
    document.getElementById('cnt-fn').textContent = fn;
    document.getElementById('cnt-partial').textContent = partial;
}}

// ── 필터 ──
function applyFilters() {{
    const fRel = document.getElementById('f-rel').value;
    const fConf = document.getElementById('f-conf').value;
    const fStatus = _currentStatusFilter;
    const fType = document.getElementById('f-type').value;
    const fRisk = document.getElementById('f-risk').value;
    const fSearch = document.getElementById('f-search').value.toLowerCase();
    let shown = 0;
    document.querySelectorAll('.result-row').forEach(row => {{
        let show = true;
        if (fRel && row.dataset.relevant !== fRel) show = false;
        if (fConf && row.dataset.confidence !== fConf) show = false;
        if (fType && row.dataset.type !== fType) show = false;
        if (fRisk) {{
            const r = parseInt(row.dataset.risk);
            if (fRisk === 'high' && r < 3) show = false;
            if (fRisk === 'med' && (r < 1 || r >= 3)) show = false;
            if (fRisk === 'low' && r > 0) show = false;
        }}
        if (fStatus) {{
            const sv = getRowStatus(row);
            if (fStatus === 'unreviewed') {{ if (sv) show = false; }}
            else {{ if (sv !== fStatus) show = false; }}
        }}
        if (fSearch) {{
            if (!row.textContent.toLowerCase().includes(fSearch)) show = false;
        }}
        row.style.display = show ? '' : 'none';
        if (show) shown++;
    }});
    document.getElementById('filter-info').textContent = shown + ' / {total}건 표시';
}}

function resetFilters() {{
    ['f-rel','f-conf','f-type','f-risk'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('f-search').value = '';
    _currentStatusFilter = '';
    document.querySelectorAll('.status-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.status-btn[data-val=""]').classList.add('active');
    applyFilters();
}}

// ── 행 스크롤 ──
function scrollToRow(idx) {{
    const row = document.querySelector(`tr[data-idx="${{idx}}"]`);
    if (row) {{ row.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); row.style.outline = '2px solid #58a6ff'; setTimeout(() => row.style.outline = '', 2000); }}
}}

// ── 저장/불러오기 ──
function saveLocal() {{
    const data = {{}};
    document.querySelectorAll('.result-row').forEach(row => {{
        const pid = row.dataset.postId;
        data[pid] = {{
            status: getRowStatus(row),
            opinion: row.querySelector('.user-opinion-input').value,
            gt: row.querySelector('.ground-truth-select').value,
            gtTitle: row.querySelector('.gt-title-input').value,
        }};
    }});
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    alert('💾 저장 완료 (' + Object.values(data).filter(d => d.status || d.opinion).length + '건 입력)');
}}

function loadLocal() {{
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) {{ alert('저장된 데이터 없음'); return; }}
    const data = JSON.parse(saved);
    let loaded = 0;
    document.querySelectorAll('.result-row').forEach(row => {{
        const pid = row.dataset.postId;
        if (data[pid]) {{
            setRowStatusValue(row, data[pid].status || '');
            row.querySelector('.user-opinion-input').value = data[pid].opinion || '';
            row.querySelector('.ground-truth-select').value = data[pid].gt || '';
            row.querySelector('.gt-title-input').value = data[pid].gtTitle || '';
            if (data[pid].status) loaded++;
        }}
    }});
    updateCounts();
    alert('📂 불러오기 완료 (' + loaded + '건 검토 복원)');
}}

// ── 내보내기 ──
function exportReview() {{
    const reviews = [];
    document.querySelectorAll('.result-row').forEach(row => {{
        const pid = row.dataset.postId;
        const status = getRowStatus(row);
        const opinion = row.querySelector('.user-opinion-input').value;
        const gt = row.querySelector('.ground-truth-select').value;
        const gtTitle = row.querySelector('.gt-title-input').value;
        reviews.push({{
            post_id: parseInt(pid),
            is_relevant: row.dataset.relevant === 'true',
            confidence: row.dataset.confidence,
            type: row.dataset.type,
            risk: parseInt(row.dataset.risk),
            review_status: status || 'unreviewed',
            user_opinion: opinion,
            ground_truth: gt,
            ground_truth_title: gtTitle,
        }});
    }});
    const blob = new Blob([JSON.stringify(reviews, null, 2)], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'review_v2_' + new Date().toISOString().slice(0,10) + '.json';
    a.click();
    URL.revokeObjectURL(url);
}}

// ── 키보드 단축키 ──
document.addEventListener('keydown', e => {{
    if (e.ctrlKey && e.key === 's') {{ e.preventDefault(); saveLocal(); }}
}});

// ── 자동 불러오기 ──
(function() {{
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {{
        try {{
            const data = JSON.parse(saved);
            let cnt = 0;
            document.querySelectorAll('.result-row').forEach(row => {{
                const pid = row.dataset.postId;
                if (data[pid] && (data[pid].status || data[pid].opinion)) {{
                    setRowStatusValue(row, data[pid].status || '');
                    row.querySelector('.user-opinion-input').value = data[pid].opinion || '';
                    row.querySelector('.ground-truth-select').value = data[pid].gt || '';
                    row.querySelector('.gt-title-input').value = data[pid].gtTitle || '';
                    cnt++;
                }}
            }});
            if (cnt > 0) {{ updateCounts(); console.log('Auto-loaded ' + cnt + ' reviews'); }}
        }} catch(e) {{}}
    }}
}})();

// ── 로그 데이터 맵 (lazy-load용) ──
let _logDataMap = {{}};
try {{
    const _logEl = document.getElementById('log-data-json');
    if (_logEl) _logDataMap = JSON.parse(_logEl.textContent);
}} catch(e) {{ console.error('Failed to parse log data:', e); }}

// 초기 필터 적용 (미검토 기본 선택)
setTimeout(() => {{ applyFilters(); }}, 100);
</script>
</body>
</html>'''
    return html


def main():
    print('📂 결과 파일 로딩...')
    results = load_results(RESULT_FILE)
    print(f'   → {len(results)}건 로드')

    print('📂 로그 파일 로딩...')
    log_lines = load_log_lines(LOG_FILE)
    print(f'   → {len(log_lines):,}줄 로드')

    print('🔍 로그 경계 파싱...')
    log_ranges = parse_log_boundaries(log_lines)
    print(f'   → {len(log_ranges)}개 post 로그 발견')

    print('🏗️ HTML 대시보드 v2 생성 중...')
    html = build_html(results, log_ranges, log_lines)

    Path(OUTPUT_HTML).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = Path(OUTPUT_HTML).stat().st_size / 1024
    print(f'✅ v2 대시보드 생성 완료: {OUTPUT_HTML}')
    print(f'   파일 크기: {size_kb:.1f} KB ({size_kb/1024:.1f} MB)')


if __name__ == '__main__':
    main()
