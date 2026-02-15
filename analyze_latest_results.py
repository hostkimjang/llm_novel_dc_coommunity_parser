"""
최신 테스트 결과 분석 스크립트
"""
import json
from pathlib import Path
from typing import Dict, List

def analyze_results(result_file: str):
    """결과 파일 분석"""
    
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=" * 80)
    print("📊 테스트 결과 상세 분석")
    print("=" * 80)
    print()
    
    # 기본 통계
    total = len(data)
    relevant = sum(1 for item in data if item['analysis_result']['identity']['is_relevant'])
    identified = sum(1 for item in data if item['analysis_result']['identity'].get('novel_identity', {}) and 
                     item['analysis_result']['identity']['novel_identity'].get('official_title'))
    
    print(f"📈 전체 통계:")
    print(f"   총 포스트: {total}")
    print(f"   관련성 있음 (is_relevant=true): {relevant} ({relevant/total*100:.1f}%)")
    print(f"   작품 식별됨 (title 있음): {identified} ({identified/total*100:.1f}%)")
    print(f"   작품 없음 (is_relevant=false): {total-relevant} ({(total-relevant)/total*100:.1f}%)")
    print()
    
    # 문제 케이스 분석
    print("=" * 80)
    print("🔍 핵심 문제 케이스 분석")
    print("=" * 80)
    print()
    
    problem_cases = {
        11718077: {
            "title": "스포) 즉사무림 예상된 전개긴하지만",
            "expected": "즉사기 들고 무림에 떨어지다",
            "issue": "캐릭터 검증이 형태소 불일치를 덮어쓰지 않는지 확인"
        },
        11718085: {
            "title": "로판닼판 뒤졌네",
            "expected": "FALSE (메타 토론)",
            "issue": "플랫폼 메타 토론 감지"
        },
        11718070: {
            "title": "ect 개무섭네",
            "expected": "FALSE (현실 세계)",
            "issue": "담론 영역 분석"
        },
        11718067: {
            "title": "백합난입은 공을 따먹는 게 맛있긴 한듯",
            "expected": "FALSE (장르 일반론)",
            "issue": "장르 토론 vs 작품 토론 구분"
        }
    }
    
    for post_id, expected in problem_cases.items():
        result = next((item for item in data if item['post_id'] == post_id), None)
        if not result:
            print(f"⚠️ Post {post_id}: 결과 없음")
            continue
        
        identity = result['analysis_result']['identity']
        is_relevant = identity['is_relevant']
        novel_identity = identity.get('novel_identity')
        official_title = novel_identity.get('official_title') if novel_identity else None
        confidence = novel_identity.get('confidence') if novel_identity else None
        reason = identity.get('reason', '')
        
        print(f"📌 Post {post_id}: {expected['title']}")
        print(f"   예상: {expected['expected']}")
        print(f"   이슈: {expected['issue']}")
        print(f"   결과: is_relevant={is_relevant}")
        if official_title:
            print(f"   작품명: {official_title} ({confidence})")
        print(f"   판단 근거: {reason[:200]}...")
        
        # 성공 여부 판단
        if post_id == 11718077:
            # 축약어가 아닌 정식 제목이어야 함
            if official_title and "즉사기 들고 무림에 떨어지다" in official_title:
                print(f"   ✅ PASS: 올바른 정식 제목 식별")
            elif official_title == "즉사무림":
                print(f"   ❌ FAIL: 축약어를 그대로 반환 (정식 제목 필요)")
            else:
                print(f"   ❌ FAIL: 잘못된 작품명")
        elif post_id in [11718085, 11718070, 11718067]:
            # FALSE여야 함
            if not is_relevant:
                print(f"   ✅ PASS: 올바르게 is_relevant=false 판단")
            else:
                print(f"   ❌ FAIL: 잘못된 작품 식별")
        
        print()
    
    # 신뢰도 분포
    print("=" * 80)
    print("📊 신뢰도 분포")
    print("=" * 80)
    print()
    
    confidence_dist = {"Max": 0, "High": 0, "Medium": 0, "Low": 0, "None": 0}
    for item in data:
        identity = item['analysis_result']['identity']
        if identity['is_relevant'] and identity.get('novel_identity'):
            conf = identity['novel_identity'].get('confidence', 'None')
            confidence_dist[conf] = confidence_dist.get(conf, 0) + 1
    
    for conf, count in confidence_dist.items():
        if count > 0:
            print(f"   {conf}: {count}")
    print()
    
    # 토론 타입 분포
    print("=" * 80)
    print("📊 토론 타입 분포")
    print("=" * 80)
    print()
    
    discussion_types = {}
    for item in data:
        dtype = item['analysis_result']['identity'].get('discussion_type', 'unknown')
        discussion_types[dtype] = discussion_types.get(dtype, 0) + 1
    
    for dtype, count in sorted(discussion_types.items(), key=lambda x: -x[1]):
        print(f"   {dtype}: {count}")
    print()
    
    # 축약어 식별 케이스
    print("=" * 80)
    print("🔤 축약어 식별 케이스")
    print("=" * 80)
    print()
    
    for item in data[:10]:  # 처음 10개만
        title = item['title']
        identity = item['analysis_result']['identity']
        if identity['is_relevant'] and identity.get('novel_identity'):
            official = identity['novel_identity'].get('official_title', '')
            conf = identity['novel_identity'].get('confidence', '')
            print(f"   {title[:30]:30s} → {official[:40]:40s} ({conf})")
    
    print()
    print("=" * 80)
    print("✅ 분석 완료!")
    print("=" * 80)

if __name__ == "__main__":
    result_file = "out/expert_result_20260204_121956.json"
    analyze_results(result_file)
