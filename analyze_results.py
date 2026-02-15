import json
import sys

# Load results
with open('out/expert_result_20260204_044051.json', encoding='utf-8') as f:
    data = json.load(f)

print("="*120)
print("📊 심층 분석 결과")
print("="*120)

# Summary
total = len(data)
relevant = sum(1 for x in data if x['analysis_result']['identity']['is_relevant'])
with_title = sum(1 for x in data if x['analysis_result']['identity']['novel_identity'] and x['analysis_result']['identity']['novel_identity'].get('official_title'))

print(f"\n총 포스트: {total}개")
print(f"관련 포스트: {relevant}개 ({relevant/total*100:.1f}%)")
print(f"작품 식별: {with_title}개 ({with_title/total*100:.1f}%)")

# Detailed table
print("\n" + "="*120)
print(f"{'ID':8} | {'관련':5} | {'작품명':45} | {'신뢰도':8} | {'제목':40}")
print("="*120)

for x in data:
    post_id = x['post_id']
    is_rel = "TRUE" if x['analysis_result']['identity']['is_relevant'] else "FALSE"
    
    novel_id = x['analysis_result']['identity'].get('novel_identity')
    if novel_id and novel_id.get('official_title'):
        title = novel_id['official_title'][:45]
        conf = novel_id.get('confidence', 'N/A')
    else:
        title = "N/A"
        conf = "N/A"
    
    post_title = x['title'][:40]
    
    print(f"{post_id:8} | {is_rel:5} | {title:45} | {conf:8} | {post_title}")

# Category analysis
print("\n" + "="*120)
print("📋 카테고리별 분석")
print("="*120)

discussion_types = {}
for x in data:
    if x['analysis_result']['identity']['is_relevant']:
        dtype = x['analysis_result']['identity'].get('discussion_type', 'unknown')
        discussion_types[dtype] = discussion_types.get(dtype, 0) + 1

print("\n토론 유형:")
for dtype, count in sorted(discussion_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {dtype:20}: {count:2}개")

# Confidence distribution
print("\n신뢰도 분포:")
conf_dist = {}
for x in data:
    novel_id = x['analysis_result']['identity'].get('novel_identity')
    if novel_id:
        conf = novel_id.get('confidence', 'None')
        conf_dist[conf] = conf_dist.get(conf, 0) + 1

for conf, count in sorted(conf_dist.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {conf:10}: {count:2}개")

# Problem cases check
print("\n" + "="*120)
print("⚠️  Problem Cases 검증")
print("="*120)

problem_ids = [11718070, 11718067, 11718085]
for pid in problem_ids:
    post = next((x for x in data if x['post_id'] == pid), None)
    if post:
        is_rel = post['analysis_result']['identity']['is_relevant']
        novel_id = post['analysis_result']['identity'].get('novel_identity')
        title = novel_id.get('official_title', 'N/A') if novel_id else 'N/A'
        
        result = "✅ PASS" if not is_rel else "❌ FAIL"
        print(f"{pid} | {result} | is_relevant={is_rel} | title={title}")
        print(f"  제목: {post['title']}")
        print(f"  이유: {post['analysis_result']['identity'].get('reason', 'N/A')[:100]}...")
        print()
