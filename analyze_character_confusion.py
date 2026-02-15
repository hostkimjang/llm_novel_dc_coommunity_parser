import json

# 결과 파일 로드
with open('out/expert_result_20260204_044051.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 캐릭터명 검색 패턴 분석
character_cases = []

for post in data:
    content_str = ' '.join(post.get('content', []))
    title = post.get('title', '')
    
    # 특정 캐릭터가 언급된 케이스 찾기
    chars = ['서무량', '흑도애', '은영', '알베도', '아인즈']
    
    for char in chars:
        if char in content_str or char in title:
            result = post.get('analysis_result', {}).get('identity', {})
            novel_title = result.get('novel_identity', {}).get('official_title') if result.get('novel_identity') else None
            
            character_cases.append({
                'post_id': post['post_id'],
                'title': title[:50],
                'character': char,
                'novel_identified': novel_title,
                'confidence': result.get('novel_identity', {}).get('confidence') if result.get('novel_identity') else None,
                'reason_snippet': result.get('reason', '')[:150] if result.get('reason') else ''
            })

# 결과 출력
print("="*80)
print("캐릭터명 검색으로 인한 작품 매칭 분석")
print("="*80)
print()

for case in character_cases:
    print(f"Post {case['post_id']}: {case['title']}")
    print(f"  캐릭터: {case['character']}")
    print(f"  식별 작품: {case['novel_identified']}")
    print(f"  신뢰도: {case['confidence']}")
    print(f"  판단 근거: {case['reason_snippet']}")
    print()

# 같은 캐릭터가 다른 작품으로 매칭된 케이스 찾기
print("="*80)
print("동일 캐릭터명의 작품 혼동 케이스")
print("="*80)
print()

char_to_works = {}
for case in character_cases:
    char = case['character']
    work = case['novel_identified']
    
    if char not in char_to_works:
        char_to_works[char] = set()
    if work:
        char_to_works[char].add(work)

for char, works in char_to_works.items():
    if len(works) > 1:
        print(f"⚠️ 캐릭터 '{char}'가 여러 작품에서 검색됨:")
        for work in works:
            print(f"   - {work}")
        print()
