#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

with open('out/expert_result_20260204_181541.json', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("is_relevant=true이지만 novel_identity가 없는 케이스")
print("=" * 80)

true_cases = [p for p in data if p['analysis_result']['identity']['is_relevant']]
no_novel_cases = [p for p in true_cases if not p['analysis_result']['identity'].get('novel_identity')]

if no_novel_cases:
    print(f"\n발견됨: {len(no_novel_cases)}개")
    for i, p in enumerate(no_novel_cases, 1):
        print(f"\n{i}. Post {p['post_id']}: {p['title']}")
        print(f"   discussion_type: {p['analysis_result']['identity'].get('discussion_type')}")
        reason = p['analysis_result']['identity'].get('reason', '')
        print(f"   reason: {reason[:200]}...")
else:
    print("\n없음 - 모든 is_relevant=true 케이스에 novel_identity 존재")

print("\n" + "=" * 80)
print("모든 is_relevant=true 케이스 상세")
print("=" * 80)

for i, p in enumerate(true_cases, 1):
    novel_id = p['analysis_result']['identity'].get('novel_identity')
    if novel_id:
        title = novel_id.get('official_title', 'NO TITLE')
        conf = novel_id.get('confidence', 'N/A')
    else:
        title = 'NO NOVEL_IDENTITY'
        conf = 'N/A'
    dtype = p['analysis_result']['identity'].get('discussion_type', 'unknown')
    
    print(f"\n{i}. Post {p['post_id']}: {p['title'][:50]}")
    print(f"   official_title: {title}")
    print(f"   confidence: {conf}")
    print(f"   discussion_type: {dtype}")

print("\n" + "=" * 80)
print("특이 케이스 체크")
print("=" * 80)

# 제목이 null이거나 짧은 케이스
short_title_cases = [p for p in true_cases 
                     if p['analysis_result']['identity'].get('novel_identity', {}).get('official_title') 
                     and len(p['analysis_result']['identity']['novel_identity']['official_title']) < 6]

if short_title_cases:
    print(f"\n제목이 짧은 케이스 ({len(short_title_cases)}개):")
    for p in short_title_cases:
        title = p['analysis_result']['identity']['novel_identity']['official_title']
        print(f"  Post {p['post_id']}: '{p['title'][:40]}' → '{title}'")

# 축약어 그대로 사용한 케이스 (Critical 11718064)
print(f"\n축약어 그대로 사용 케이스:")
print(f"  Post 11718064: '즉사무림이유백' → '즉사무림' ❌")

# 작가명 오인 케이스 (Critical 11718089)
print(f"\n작가명 오인 케이스:")
print(f"  Post 11718089: '개돌 신작 초대남' → '개구리 와자' ❌")

print("\n" + "=" * 80)
