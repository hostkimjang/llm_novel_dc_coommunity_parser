import json
import sys
import glob
import os

# 가장 최신 결과 파일 찾기
result_files = glob.glob(r"C:\Users\kimjang\Documents\GitHub\llm_novel_dc_coommunity_parser\out\expert_result_*.json")
latest_file = max(result_files, key=os.path.getmtime) if result_files else None

if not latest_file:
    print("결과 파일을 찾을 수 없습니다.")
    sys.exit(1)

print(f"📂 분석 파일: {os.path.basename(latest_file)}")

# UTF-8로 읽기
with open(latest_file, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"총 처리된 포스트: {len(data)}개")
print("="*60)

# 각 포스트 요약
for i, item in enumerate(data, 1):
    print(f"\n[{i}] Post {item['post_id']}: {item['title']}")
    result = item.get('analysis_result', {})
    identity = result.get('identity', {})
    
    is_relevant = identity.get('is_relevant', False)
    status = "✅ 웹소설 관련" if is_relevant else "❌ 노이즈"
    
    print(f"    {status}")
    
    if is_relevant:
        novel = identity.get('novel_identity')
        if novel:
            title = novel.get('official_title', 'Unknown')
            confidence = novel.get('confidence', 'Unknown')
            print(f"    📖 작품: {title}")
            print(f"    🎯 신뢰도: {confidence}")
        else:
            print(f"    📖 작품: (식별 실패)")
        
        # discussion_type 표시 (새 필드)
        disc_type = identity.get('discussion_type')
        if disc_type:
            type_labels = {
                "review": "📝 리뷰/평가",
                "spoiler": "⚠️ 스포일러",
                "anticipation": "🙏 기대/응원",
                "meme": "😂 밈/드립",
                "author_talk": "✍️ 작가 토론",
                "character_talk": "👤 캐릭터 감상",
                "general": "💬 일반 토론",
                "trope_discussion": "🏷️ 장르/트로프 토론",
            }
            print(f"    📊 유형: {type_labels.get(disc_type, disc_type)}")
        
        # Discourse 분석 확인 (있으면)
        if 'discourse_analysis' in result:
            disc = result['discourse_analysis']
            print(f"    🌐 도메인: {disc.get('primary_domain', 'N/A')}")
            print(f"    💬 의도: {disc.get('intent', 'N/A')}")
    else:
        print(f"    사유: {identity.get('reason', 'N/A')[:80]}...")

print("\n" + "="*60)
print(f"✅ 관련 포스트: {sum(1 for x in data if x.get('analysis_result', {}).get('identity', {}).get('is_relevant'))}")
print(f"❌ 노이즈: {sum(1 for x in data if not x.get('analysis_result', {}).get('identity', {}).get('is_relevant'))}")
