#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

with open('out/expert_result_20260204_181541.json', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("분석 결과 요약")
print("=" * 80)

# is_relevant=false 케이스
false_cases = [p for p in data if not p['analysis_result']['identity']['is_relevant']]
print(f"\n✗ is_relevant=false: {len(false_cases)}개")
for i, p in enumerate(false_cases, 1):
    title = p['title'][:60]
    dtype = p['analysis_result']['identity'].get('discussion_type', 'unknown')
    print(f"  {i}. Post {p['post_id']}: {title} [{dtype}]")

# is_relevant=true 케이스
true_cases = [p for p in data if p['analysis_result']['identity']['is_relevant']]
print(f"\n✓ is_relevant=true: {len(true_cases)}개")

# 신뢰도별 분류
confidence_map = {}
for p in true_cases:
    novel_id = p['analysis_result']['identity'].get('novel_identity')
    if novel_id:
        conf = novel_id.get('confidence', 'Unknown')
        confidence_map.setdefault(conf, []).append(p)

print("\n신뢰도별 분류:")
for conf in ['High', 'Medium', 'Low']:
    cases = confidence_map.get(conf, [])
    print(f"  {conf}: {len(cases)}개")

# Medium/Low 케이스 상세
print("\n=" * 80)
print("Medium/Low 신뢰도 케이스 (확인 필요)")
print("=" * 80)
for conf in ['Medium', 'Low']:
    cases = confidence_map.get(conf, [])
    if cases:
        print(f"\n[{conf} 신뢰도]")
        for i, p in enumerate(cases, 1):
            title = p['title'][:50]
            novel_id = p['analysis_result']['identity'].get('novel_identity', {})
            official = novel_id.get('official_title', 'N/A')
            print(f"  {i}. Post {p['post_id']}: {title}")
            print(f"     → {official}")

# Critical 케이스 (이미 분석한 것)
print("\n=" * 80)
print("Critical 문제 케이스 (이미 분석 완료)")
print("=" * 80)
critical = [
    (11718064, "즉사무림이유백", "즉사무림", "축약어를 정식 제목으로 착각"),
    (11718089, "개돌 신작 초대남", "개구리 와자", "작가명을 작품명으로 오인")
]
for post_id, title, result, issue in critical:
    print(f"  Post {post_id}: {title}")
    print(f"     결과: {result}")
    print(f"     문제: {issue}")

print("\n" + "=" * 80)
