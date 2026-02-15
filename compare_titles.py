#!/usr/bin/env python3
"""
30개 포스트 원본 제목 vs 식별된 제목 비교
"""
import json
from pathlib import Path

# 결과 파일 로드
result_file = Path("out/expert_result_20260205_164507.json")
with open(result_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

# 테이블 헤더
print("=" * 180)
print(f"{'No':<4} {'Post ID':<10} {'R':<3} {'원본 제목':<60} {'식별된 작품명':<60}")
print("=" * 180)

# 각 포스트 출력
for idx, post in enumerate(results, 1):
    post_id = post['post_id']
    original_title = post.get('title', 'N/A')
    identity = post['analysis_result']['identity']
    
    is_relevant = identity.get('is_relevant', False)
    novel_identity = identity.get('novel_identity')
    
    # 제목 추출
    if novel_identity and novel_identity.get('official_title'):
        identified_title = novel_identity.get('official_title', '')
        confidence = novel_identity.get('confidence', '')
        identified_title = f"{identified_title} [{confidence}]"
    else:
        identified_title = '-'
    
    # 제목이 너무 길면 자르기
    if len(original_title) > 58:
        original_title = original_title[:55] + "..."
    if len(identified_title) > 58:
        identified_title = identified_title[:55] + "..."
    
    # Relevant 마크
    rel_mark = "✓" if is_relevant else "✗"
    
    # 강조 표시 (Relevant인데 제목 없는 케이스)
    if is_relevant and identified_title == '-':
        rel_mark = "⚠"  # 경고 표시
    
    # 출력
    print(f"{idx:<4} {post_id:<10} {rel_mark:<3} {original_title:<60} {identified_title:<60}")

print("=" * 180)

# 요약 통계
relevant_count = sum(1 for p in results if p['analysis_result']['identity'].get('is_relevant'))
identified_count = 0
relevant_no_title = []

for p in results:
    identity = p['analysis_result']['identity']
    if identity.get('is_relevant'):
        ni = identity.get('novel_identity')
        if ni and ni.get('official_title'):
            identified_count += 1
        else:
            relevant_no_title.append({
                'post_id': p['post_id'],
                'title': p['title'],
                'type': identity.get('discussion_type', 'Unknown')
            })

print(f"\n📊 Legend:")
print(f"  ✓ = Relevant (작품 관련)")
print(f"  ✗ = Irrelevant (잡담/추천/메타 등)")
print(f"  ⚠ = Relevant but No Title (작품 관련인데 제목 식별 실패)")

print(f"\n📈 통계:")
print(f"  - 총 포스트: {len(results)}")
print(f"  - Relevant: {relevant_count} ({relevant_count/len(results)*100:.1f}%)")
print(f"  - Identified (제목 있음): {identified_count} ({identified_count/relevant_count*100:.1f}% of relevant)")
print(f"  - ⚠ Relevant but No Title: {len(relevant_no_title)}")

if relevant_no_title:
    print(f"\n⚠️  Relevant인데 제목 없는 케이스:")
    for case in relevant_no_title:
        print(f"  - Post {case['post_id']}: {case['title'][:70]} ({case['type']})")

# 축약어 해독 성공 케이스 찾기
print(f"\n🎯 축약어 해독 성공 케이스:")
abbreviation_cases = []
for p in results:
    original = p.get('title', '')
    identity = p['analysis_result']['identity']
    ni = identity.get('novel_identity')
    
    if ni and ni.get('official_title'):
        identified = ni.get('official_title')
        # 원본에 식별된 제목이 포함되지 않으면 축약어로 판단
        if identified not in original and len(original) < len(identified):
            abbreviation_cases.append({
                'post_id': p['post_id'],
                'original': original,
                'identified': identified
            })

for case in abbreviation_cases[:5]:  # 상위 5개만
    print(f"  - '{case['original'][:40]}' → '{case['identified']}'")
