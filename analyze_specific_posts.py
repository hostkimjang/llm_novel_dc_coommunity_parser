"""특정 포스트 상세 분석"""
import json

# JSON 파일 읽기
with open("out/expert_result_20260205_122914.json", "r", encoding="utf-8") as f:
    results = json.load(f)

target_posts = [11718087, 11718103, 11718102]

print("=" * 80)
print("🔍 문제 포스트 상세 분석")
print("=" * 80)

for post_id in target_posts:
    # 해당 포스트 찾기
    post = next((p for p in results if p['post_id'] == post_id), None)
    
    if not post:
        print(f"\n❌ Post {post_id}: 찾을 수 없음")
        continue
    
    print(f"\n{'='*80}")
    print(f"📄 Post {post_id}")
    print(f"{'='*80}")
    
    # 기본 정보
    print(f"\n📌 원본 데이터:")
    print(f"   제목: {post.get('title', 'N/A')}")
    print(f"   본문: {' '.join(post.get('content', []))[:100]}")
    print(f"   댓글 수: {len(post.get('comments', []))}")
    if post.get('comments'):
        print(f"   댓글 샘플: {post['comments'][0][:80]}")
    
    # 분석 결과
    ar = post.get('analysis_result', {})
    identity = ar.get('identity', {})
    analysis = ar.get('analysis', {})
    
    print(f"\n🎯 분석 결과:")
    print(f"   is_relevant: {identity.get('is_relevant')}")
    print(f"   discussion_type: {identity.get('discussion_type')}")
    
    # novel_identity 상세
    novel_id = identity.get('novel_identity')
    if novel_id:
        print(f"\n📚 Novel Identity:")
        print(f"   official_title: {novel_id.get('official_title') or novel_id.get('official_novel_title')}")
        print(f"   confidence: {novel_id.get('confidence')}")
        print(f"   heretic_url: {novel_id.get('heretic_url')}")
    else:
        print(f"\n📚 Novel Identity: None")
    
    # Arbiter reason (중요!)
    reason = identity.get('reason', '')
    print(f"\n💡 Arbiter Reason (처음 200자):")
    print(f"   {reason[:200]}")
    if len(reason) > 200:
        print(f"   ... (총 {len(reason)}자)")
    
    # 감지된 타이틀
    detected = analysis.get('detected_titles', [])
    if detected:
        print(f"\n🔎 Detected Titles ({len(detected)}개):")
        for dt in detected:
            print(f"   - {dt.get('official_title')}")
            print(f"     confidence: {dt.get('confidence')}")
            print(f"     url: {dt.get('heretic_url')}")
    
    # 문제점 분석
    print(f"\n⚠️  문제점 분석:")
    
    # 1. 추천 요청 글인가?
    title = post.get('title', '')
    content = ' '.join(post.get('content', []))
    
    is_recommendation_request = any(kw in title for kw in ['추천', '추천좀', '추천해'])
    if is_recommendation_request:
        print(f"   ✓ 제목에 '추천' 키워드 있음 → 추천 요청 글")
    
    # 2. 본문이 짧은가?
    if len(content) < 50:
        print(f"   ✓ 본문이 짧음 ({len(content)}자)")
    
    # 3. 이미지 기반 판단인가?
    if 'image' in reason.lower() or '이미지' in reason:
        print(f"   ✓ 이미지 기반 판단")
    
    # 4. URL 타입 확인
    url_type = "Unknown"
    for c in post.get('content', []):
        if isinstance(c, dict):
            url_type = c.get('type', 'Unknown')
            break
    print(f"   URL Type: {url_type}")
    
    # 5. 결론
    print(f"\n🎯 결론:")
    if is_recommendation_request and identity.get('is_relevant'):
        print(f"   ❌ False Positive 가능성 높음")
        print(f"      → 추천 요청 글을 특정 작품으로 오인")
    elif identity.get('is_relevant') and novel_id:
        if len(content) < 50 and 'image' in reason.lower():
            print(f"   ⚠️  이미지만으로 판단 (텍스트 컨텍스트 부족)")
        else:
            print(f"   ✅ 정상 식별")
    else:
        print(f"   ℹ️  추가 확인 필요")

print("\n" + "=" * 80)
print("\n📊 종합 분석")
print("=" * 80)

# 공통 패턴 찾기
for post_id in target_posts:
    post = next((p for p in results if p['post_id'] == post_id), None)
    if not post:
        continue
    
    title = post.get('title', '')
    content = ' '.join(post.get('content', []))
    ar = post.get('analysis_result', {})
    identity = ar.get('identity', {})
    novel_id = identity.get('novel_identity')
    
    print(f"\nPost {post_id}:")
    print(f"  제목: {title[:50]}")
    print(f"  본문 길이: {len(content)}자")
    print(f"  작품명: {novel_id.get('official_title') if novel_id else 'N/A'}")
    print(f"  추천 요청? {'예' if '추천' in title else '아니오'}")
    print(f"  이미지 기반? {'예' if 'image' in identity.get('reason', '').lower() else '아니오'}")

print("\n" + "=" * 80)
