#!/usr/bin/env python3
"""
30개 포스트 결과를 테이블 형태로 출력
"""
import json
from pathlib import Path

# 결과 파일 로드
result_file = Path("out/expert_result_20260205_164507.json")
with open(result_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

# 테이블 헤더
print("=" * 160)
print(f"{'No':<4} {'Post ID':<10} {'Relevant':<10} {'Official Title':<50} {'Conf':<8} {'Type':<15}")
print("=" * 160)

# 각 포스트 출력
for idx, post in enumerate(results, 1):
    post_id = post['post_id']
    identity = post['analysis_result']['identity']
    
    is_relevant = identity.get('is_relevant', False)
    novel_identity = identity.get('novel_identity')
    discussion_type = identity.get('discussion_type', 'N/A')
    
    # 제목과 신뢰도 추출
    if novel_identity and novel_identity.get('official_title'):
        official_title = novel_identity.get('official_title', 'N/A')
        confidence = novel_identity.get('confidence', 'N/A')
    else:
        official_title = '-'
        confidence = '-'
    
    # 제목이 너무 길면 자르기
    if len(official_title) > 48:
        official_title = official_title[:45] + "..."
    
    # Relevant 색상 표시 (✓/✗)
    rel_mark = "✓ TRUE " if is_relevant else "✗ FALSE"
    
    # 출력
    print(f"{idx:<4} {post_id:<10} {rel_mark:<10} {official_title:<50} {confidence:<8} {discussion_type:<15}")

print("=" * 160)

# 요약 통계
relevant_count = sum(1 for p in results if p['analysis_result']['identity'].get('is_relevant'))
identified_count = 0
for p in results:
    identity = p['analysis_result']['identity']
    if identity.get('is_relevant'):
        ni = identity.get('novel_identity')
        if ni and ni.get('official_title'):
            identified_count += 1

print(f"\n📊 요약:")
print(f"  - 총 포스트: {len(results)}")
print(f"  - Relevant: {relevant_count} ({relevant_count/len(results)*100:.1f}%)")
print(f"  - Identified (제목 있음): {identified_count} ({identified_count/relevant_count*100:.1f}% of relevant)")
print(f"  - Relevant but No Title: {relevant_count - identified_count}")

# 신뢰도별 집계
from collections import Counter
confidences = []
for p in results:
    ni = p['analysis_result']['identity'].get('novel_identity')
    if ni and ni.get('official_title'):
        confidences.append(ni.get('confidence', 'Unknown'))

conf_dist = Counter(confidences)
print(f"\n📈 신뢰도 분포:")
for conf, count in sorted(conf_dist.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {conf}: {count}")
