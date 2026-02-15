import json

data = json.load(open('out/expert_result_20260203_235912.json', 'r', encoding='utf-8'))

# 문제 케이스 추출
problem_cases = {
    '11718067': '백합난입 (장르 토론)',
    '11718070': 'ect (의학 토론)',
    '11718085': '로판닼판 (삭제된 소설)'
}

print("=" * 80)
print("문제 케이스 분석")
print("=" * 80)

for post in data:
    if str(post['post_id']) in problem_cases:
        print(f"\n{'='*80}")
        print(f"Post {post['post_id']}: {post['title']}")
        print(f"문제 유형: {problem_cases[str(post['post_id'])]}")
        print(f"{'='*80}")
        
        identity = post['analysis_result']['identity']
        
        print(f"\n현재 판정: is_relevant={identity['is_relevant']}")
        
        if identity['novel_identity']:
            print(f"작품: {identity['novel_identity']['official_title']}")
            print(f"신뢰도: {identity['novel_identity']['confidence']}")
        
        print(f"\n판정 이유:")
        print(identity['reason'][:500])
        
        print(f"\n원본 포스트:")
        print(f"제목: {post['title']}")
        print(f"본문: {' / '.join(post['content'])}")
        print(f"댓글: {post['comments'][:3] if post['comments'] else '없음'}")

print("\n" + "="*80)
print("전체 통계")
print("="*80)

total = len(data)
relevant = sum(1 for p in data if p['analysis_result']['identity']['is_relevant'])
false_positive = 3  # 문제 케이스 3개

print(f"Total: {total}")
print(f"Relevant (현재): {relevant}")
print(f"False Positive (의심): {false_positive}")
print(f"수정 후 Relevant: {relevant - false_positive}")
print(f"정확도 (수정 전): {(relevant / total * 100):.1f}%")
print(f"정확도 (수정 후): {((relevant - false_positive) / total * 100):.1f}%")
