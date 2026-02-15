#!/usr/bin/env python3
"""
30개 포스트 종합 결과 차트 (Relevant, Confidence, Type, 제목 모두 통합)
"""
import json
from pathlib import Path

# 결과 파일 로드
result_file = Path("out/expert_result_20260205_164507.json")
with open(result_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

# 테이블 헤더
print("=" * 190)
print(f"{'No':<4} {'Post ID':<10} {'Rel':<4} {'Conf':<6} {'Type':<15} {'원본 제목':<55} {'→ 식별된 작품명':<55}")
print("=" * 190)

# 각 포스트 출력
for idx, post in enumerate(results, 1):
    post_id = post['post_id']
    original_title = post.get('title', 'N/A')
    identity = post['analysis_result']['identity']
    
    is_relevant = identity.get('is_relevant', False)
    novel_identity = identity.get('novel_identity')
    discussion_type = identity.get('discussion_type', 'N/A')
    
    # 제목과 신뢰도 추출
    if novel_identity and novel_identity.get('official_title'):
        identified_title = novel_identity.get('official_title', '')
        confidence = novel_identity.get('confidence', '-')
    else:
        identified_title = '-'
        confidence = '-'
    
    # 제목이 너무 길면 자르기
    if len(original_title) > 53:
        original_title = original_title[:50] + "..."
    if len(identified_title) > 53:
        identified_title = identified_title[:50] + "..."
    
    # Relevant 마크
    rel_mark = "✓" if is_relevant else "✗"
    
    # 색상 구분을 위한 이모지 추가
    if is_relevant and identified_title != '-':
        prefix = "🟢"  # 성공
    elif is_relevant and identified_title == '-':
        prefix = "🟡"  # 경고
    else:
        prefix = "⚫"  # Irrelevant
    
    # 출력
    print(f"{idx:<4} {post_id:<10} {rel_mark:<4} {confidence:<6} {discussion_type:<15} {original_title:<55} {identified_title:<55}")

print("=" * 190)

# 요약 통계
from collections import Counter

relevant_count = 0
identified_count = 0
relevant_no_title = []
conf_dist = Counter()
type_dist = Counter()

for p in results:
    identity = p['analysis_result']['identity']
    dtype = identity.get('discussion_type', 'Unknown')
    type_dist[dtype] += 1
    
    if identity.get('is_relevant'):
        relevant_count += 1
        ni = identity.get('novel_identity')
        if ni and ni.get('official_title'):
            identified_count += 1
            conf = ni.get('confidence', 'Unknown')
            conf_dist[conf] += 1
        else:
            relevant_no_title.append(p['post_id'])

print(f"\n📊 Legend:")
print(f"  🟢 = Relevant + Title 식별 성공 (완전 성공)")
print(f"  🟡 = Relevant but No Title (작품 관련이나 특정 작품 미식별)")
print(f"  ⚫ = Irrelevant (잡담/추천/메타 등)")
print(f"  ✓ = Relevant  |  ✗ = Irrelevant")

print(f"\n📈 전체 통계:")
print(f"  총 포스트: {len(results)}")
print(f"  🟢 성공 (Relevant + Title): {identified_count} ({identified_count/len(results)*100:.1f}%)")
print(f"  🟡 부분 성공 (Relevant, No Title): {len(relevant_no_title)} ({len(relevant_no_title)/len(results)*100:.1f}%)")
print(f"  ⚫ Irrelevant: {len(results) - relevant_count} ({(len(results)-relevant_count)/len(results)*100:.1f}%)")

print(f"\n🎯 신뢰도 분포 (Identified {identified_count}건):")
for conf, count in sorted(conf_dist.items(), key=lambda x: x[1], reverse=True):
    bar = '█' * int(count * 30 / identified_count)
    print(f"  {conf:8} [{bar:<30}] {count:2} ({count/identified_count*100:.1f}%)")

print(f"\n📝 Discussion Type 분포 (전체 {len(results)}건):")
for dtype, count in type_dist.most_common(10):
    bar = '█' * int(count * 30 / len(results))
    print(f"  {dtype:15} [{bar:<30}] {count:2} ({count/len(results)*100:.1f}%)")

print(f"\n🔍 상세 분석:")
print(f"  • Relevant 비율: {relevant_count}/{len(results)} = {relevant_count/len(results)*100:.1f}%")
print(f"  • Identification 성공률 (relevant 중): {identified_count}/{relevant_count} = {identified_count/relevant_count*100:.1f}%")
print(f"  • High Confidence 비율: {conf_dist.get('High', 0)}/{identified_count} = {conf_dist.get('High', 0)/identified_count*100:.1f}%")
print(f"  • Relevant but No Title 케이스: {len(relevant_no_title)}건 → Post IDs: {', '.join(map(str, relevant_no_title))}")

# 축약어 해독 성공 케이스
print(f"\n✨ 축약어 해독 성공 사례:")
abbr_cases = []
for p in results:
    original = p.get('title', '')
    identity = p['analysis_result']['identity']
    ni = identity.get('novel_identity')
    
    if ni and ni.get('official_title'):
        identified = ni.get('official_title')
        # 축약어 판단: 원본 제목에 식별된 정식 제목의 일부만 포함되어 있거나, 완전히 다른 경우
        # 예: "즉사무림" in "즉사기 들고 무림에 떨어지다"의 부분이 아님
        original_clean = original.replace('스포)', '').replace('(', '').replace(')', '').strip()
        
        # 정식 제목이 원본에 완전히 포함되어 있지 않으면 축약어로 판단
        if identified not in original and original_clean not in identified:
            abbr_cases.append({
                'original': original,
                'identified': identified
            })

for idx, case in enumerate(abbr_cases[:8], 1):  # 상위 8개만 출력
    orig = case['original'][:40] + '...' if len(case['original']) > 40 else case['original']
    print(f"  {idx}. '{orig}' → '{case['identified']}'")

if len(abbr_cases) > 8:
    print(f"  ... 외 {len(abbr_cases) - 8}건 더")

print(f"\n✅ 총 {len(abbr_cases)}건의 축약어/부분정보 해독 성공!")
