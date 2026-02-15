#!/usr/bin/env python3
"""
Expert 테스트 결과 상세 분석 스크립트
30개 포스트 처리 결과에서 패턴, 성공률, 실패 원인 등을 추출
"""
import json
from collections import defaultdict, Counter
from pathlib import Path

# 결과 파일 로드
result_file = Path("out/expert_result_20260205_164507.json")
with open(result_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

print(f"총 포스트 개수: {len(results)}")

# 메트릭 추출
metrics = {
    'total': len(results),
    'relevant': 0,
    'irrelevant': 0,
    'identified': 0,  # relevant이면서 official_title이 있는 경우
    'relevant_no_title': [],  # relevant인데 title 없는 케이스
    'confidence_dist': Counter(),
    'discussion_types': Counter(),
    'uncertainty_factors': [],  # 전체 불확실성 요인 리스트
    'false_positives': [],  # relevant=false인데 제목 있는 경우
    'by_confidence': defaultdict(list),  # 신뢰도별 포스트 ID
}

for post in results:
    post_id = post['post_id']
    identity = post['analysis_result']['identity']
    is_relevant = identity.get('is_relevant', False)
    novel_identity = identity.get('novel_identity')
    
    if is_relevant:
        metrics['relevant'] += 1
        
        if novel_identity and novel_identity.get('official_title'):
            metrics['identified'] += 1
            confidence = novel_identity.get('confidence', 'Unknown')
            metrics['confidence_dist'][confidence] += 1
            metrics['by_confidence'][confidence].append(post_id)
        else:
            # relevant인데 제목 없는 케이스
            metrics['relevant_no_title'].append({
                'post_id': post_id,
                'title': post['title'],
                'reason': identity.get('reason', 'No reason'),
                'discussion_type': identity.get('discussion_type', 'Unknown')
            })
    else:
        metrics['irrelevant'] += 1
        
        # false positive 체크 (irrelevant인데 제목 있는 경우)
        if novel_identity and novel_identity.get('official_title'):
            metrics['false_positives'].append({
                'post_id': post_id,
                'title': post['title'],
                'official_title': novel_identity.get('official_title'),
                'reason': identity.get('reason', 'No reason')
            })
    
    # discussion_type 수집
    dtype = identity.get('discussion_type', 'Unknown')
    metrics['discussion_types'][dtype] += 1

# 통계 출력
print("\n=== 기본 통계 ===")
print(f"Relevant: {metrics['relevant']} ({metrics['relevant']/metrics['total']*100:.1f}%)")
print(f"Irrelevant: {metrics['irrelevant']} ({metrics['irrelevant']/metrics['total']*100:.1f}%)")
print(f"Identified (제목 있음): {metrics['identified']} ({metrics['identified']/metrics['relevant']*100:.1f}% of relevant)")
print(f"Relevant but No Title: {len(metrics['relevant_no_title'])} ({len(metrics['relevant_no_title'])/metrics['relevant']*100:.1f}% of relevant)")

print("\n=== 신뢰도 분포 (Identified 포스트) ===")
for conf, count in metrics['confidence_dist'].most_common():
    print(f"{conf}: {count} ({count/metrics['identified']*100:.1f}%)")

print("\n=== Discussion Type 분포 ===")
for dtype, count in metrics['discussion_types'].most_common():
    print(f"{dtype}: {count} ({count/metrics['total']*100:.1f}%)")

print("\n=== Relevant인데 제목 없는 케이스 ({}) ===".format(len(metrics['relevant_no_title'])))
for case in metrics['relevant_no_title']:
    print(f"\nPost {case['post_id']}: {case['title']}")
    print(f"  Type: {case['discussion_type']}")
    print(f"  Reason: {case['reason'][:200]}...")

if metrics['false_positives']:
    print("\n=== ⚠️  False Positive 의심 케이스 ({}) ===".format(len(metrics['false_positives'])))
    for case in metrics['false_positives']:
        print(f"\nPost {case['post_id']}: {case['title']}")
        print(f"  Detected Title: {case['official_title']}")
        print(f"  Reason: {case['reason'][:200]}...")

# ASCII 차트 생성 (텍스트 기반)
print("\n\n=== 📊 시각화 (ASCII Charts) ===")

# 1. Relevant vs Irrelevant
print("\n[1] Relevant vs Irrelevant 분포:")
rel_bar = '█' * int(metrics['relevant'] * 40 / metrics['total'])
irrel_bar = '█' * int(metrics['irrelevant'] * 40 / metrics['total'])
print(f"  Relevant   [{rel_bar:<40}] {metrics['relevant']} ({metrics['relevant']/metrics['total']*100:.1f}%)")
print(f"  Irrelevant [{irrel_bar:<40}] {metrics['irrelevant']} ({metrics['irrelevant']/metrics['total']*100:.1f}%)")

# 2. 신뢰도 분포
print("\n[2] 신뢰도 분포 (Identified Posts):")
for conf, count in sorted(metrics['confidence_dist'].items(), key=lambda x: x[1], reverse=True):
    bar = '█' * int(count * 40 / metrics['identified'])
    print(f"  {conf:8} [{bar:<40}] {count} ({count/metrics['identified']*100:.1f}%)")

# 3. Discussion Type 분포
print("\n[3] Discussion Type 분포 (Top 10):")
for dtype, count in metrics['discussion_types'].most_common(10):
    bar = '█' * int(count * 40 / metrics['total'])
    print(f"  {dtype:15} [{bar:<40}] {count} ({count/metrics['total']*100:.1f}%)")

# 상세 리포트 생성
report_file = Path("out/expert_analysis_report.md")
with open(report_file, 'w', encoding='utf-8') as f:
    f.write("# Expert 시스템 테스트 결과 상세 분석\n\n")
    f.write(f"**테스트 일시**: 2026-02-05 16:45\n")
    f.write(f"**총 포스트 수**: {metrics['total']}\n\n")
    
    f.write("## 1. 전체 성능 요약\n\n")
    f.write(f"- **Relevant**: {metrics['relevant']} ({metrics['relevant']/metrics['total']*100:.1f}%)\n")
    f.write(f"- **Irrelevant**: {metrics['irrelevant']} ({metrics['irrelevant']/metrics['total']*100:.1f}%)\n")
    f.write(f"- **Identified (제목 추출 성공)**: {metrics['identified']} (relevant의 {metrics['identified']/metrics['relevant']*100:.1f}%)\n")
    f.write(f"- **Relevant but No Title**: {len(metrics['relevant_no_title'])} (relevant의 {len(metrics['relevant_no_title'])/metrics['relevant']*100:.1f}%)\n\n")
    
    f.write("## 2. 신뢰도 분포\n\n")
    for conf, count in metrics['confidence_dist'].most_common():
        f.write(f"- **{conf}**: {count} ({count/metrics['identified']*100:.1f}%)\n")
    
    f.write("\n## 3. Discussion Type 분포\n\n")
    for dtype, count in metrics['discussion_types'].most_common():
        f.write(f"- **{dtype}**: {count} ({count/metrics['total']*100:.1f}%)\n")
    
    f.write("\n## 4. 실패 케이스 분석\n\n")
    f.write(f"### 4.1 Relevant인데 제목 없는 케이스 ({len(metrics['relevant_no_title'])}건)\n\n")
    for case in metrics['relevant_no_title']:
        f.write(f"#### Post {case['post_id']}: {case['title']}\n")
        f.write(f"- **Type**: {case['discussion_type']}\n")
        f.write(f"- **Reason**: {case['reason']}\n\n")
    
    if metrics['false_positives']:
        f.write(f"\n### 4.2 ⚠️ False Positive 의심 케이스 ({len(metrics['false_positives'])}건)\n\n")
        for case in metrics['false_positives']:
            f.write(f"#### Post {case['post_id']}: {case['title']}\n")
            f.write(f"- **Detected Title**: {case['official_title']}\n")
            f.write(f"- **Reason**: {case['reason']}\n\n")
    
    f.write("\n## 5. 신뢰도별 포스트 ID\n\n")
    for conf in ['High', 'Medium', 'Low']:
        if conf in metrics['by_confidence']:
            ids = metrics['by_confidence'][conf]
            f.write(f"### {conf} Confidence ({len(ids)}건)\n")
            f.write(f"{', '.join(map(str, ids))}\n\n")

print(f"\n📄 상세 리포트 저장: {report_file}")

# 주요 인사이트 출력
print("\n\n=== 🔍 주요 인사이트 ===")
print(f"1. Identification 성공률: {metrics['identified']}/{metrics['relevant']} = {metrics['identified']/metrics['relevant']*100:.1f}%")
print(f"2. High Confidence 비율: {metrics['confidence_dist']['High']}/{metrics['identified']} = {metrics['confidence_dist']['High']/metrics['identified']*100:.1f}%")
print(f"3. 가장 많은 Discussion Type: {metrics['discussion_types'].most_common(1)[0][0]} ({metrics['discussion_types'].most_common(1)[0][1]}건)")
print(f"4. Relevant but No Title 케이스: {len(metrics['relevant_no_title'])}건 - 추가 조사 필요")

if metrics['false_positives']:
    print(f"⚠️  5. False Positive 의심: {len(metrics['false_positives'])}건 - 검증 필요")

print("\n✅ 분석 완료!")
