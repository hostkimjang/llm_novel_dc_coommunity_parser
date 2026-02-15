#!/usr/bin/env python3
"""4개 특정 케이스 심도있는 분석 스크립트"""
import json
import re
from pathlib import Path

def load_result_file(file_path):
    """결과 파일 로드"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_log_file(log_path):
    """로그 파일 로드"""
    with open(log_path, 'r', encoding='utf-8') as f:
        return f.read()

def extract_post_log(log_content, post_id):
    """특정 포스트의 로그 추출"""
    pattern = f"Post {post_id}.*?(?=Post \\d{{8}}|$)"
    match = re.search(pattern, log_content, re.DOTALL)
    return match.group(0) if match else ""

def analyze_case(result, log_section):
    """케이스 분석"""
    post_id = result['post_id']
    title = result['title']
    content = '\n'.join(result['content'])
    
    identity = result['analysis_result']['identity']
    is_relevant = identity['is_relevant']
    official_title = identity.get('novel_identity', {}).get('official_title') if identity.get('novel_identity') else None
    confidence = identity.get('novel_identity', {}).get('confidence', 'Unknown') if identity.get('novel_identity') else 'Unknown'
    discussion_type = identity.get('discussion_type')
    reason = identity.get('reason', '')
    
    # 전문가 판단 추출
    decoder_matches = re.findall(r'\[🔤\].*?(?=\n\[|$)', log_section, re.DOTALL)
    verifier_matches = re.findall(r'\[🔍\].*?(?=\n\[|$)', log_section, re.DOTALL)
    arbiter_matches = re.findall(r'\[⚖️\].*?(?=\n\[|$)', log_section, re.DOTALL)
    
    return {
        'post_id': post_id,
        'title': title,
        'content': content,
        'is_relevant': is_relevant,
        'official_title': official_title,
        'confidence': confidence,
        'discussion_type': discussion_type,
        'reason': reason,
        'decoder_count': len(decoder_matches),
        'verifier_count': len(verifier_matches),
        'arbiter_count': len(arbiter_matches),
        'log_length': len(log_section)
    }

def main():
    # 파일 로드
    result_file = Path("out/expert_result_20260205_192258.json")
    log_file = Path("logs/expert_run_20260205_192258.log")
    
    results = load_result_file(result_file)
    log_content = load_log_file(log_file)
    
    # 분석할 케이스
    target_ids = [11718069, 11718064, 11718089, 11718098]
    
    print("="*100)
    print("4개 특정 케이스 심도있는 분석")
    print("="*100)
    
    for i, target_id in enumerate(target_ids, 1):
        # 결과 찾기
        result = next((r for r in results if r['post_id'] == target_id), None)
        if not result:
            print(f"\n❌ Post {target_id} 결과를 찾을 수 없습니다.")
            continue
        
        # 로그 추출
        log_section = extract_post_log(log_content, target_id)
        
        # 분석
        analysis = analyze_case(result, log_section)
        
        # 출력
        print(f"\n{'='*100}")
        print(f"【케이스 {i}】 Post {analysis['post_id']}")
        print("="*100)
        
        print(f"\n📝 제목: {analysis['title']}")
        print(f"\n📄 본문:")
        for line in analysis['content'].split('\n')[:5]:
            print(f"   {line}")
        if len(analysis['content'].split('\n')) > 5:
            print(f"   ... ({len(analysis['content'].split('\n'))-5}줄 더)")
        
        print(f"\n🎯 분석 결과:")
        print(f"   is_relevant: {analysis['is_relevant']}")
        print(f"   official_title: {analysis['official_title']}")
        print(f"   confidence: {analysis['confidence']}")
        print(f"   discussion_type: {analysis['discussion_type']}")
        
        print(f"\n💡 판정 사유 (요약):")
        reason_lines = analysis['reason'].split('.')[:3]
        for line in reason_lines:
            if line.strip():
                print(f"   • {line.strip()}")
        
        print(f"\n📊 전문가 활동:")
        print(f"   Decoder 호출: {analysis['decoder_count']}회")
        print(f"   Verifier 호출: {analysis['verifier_count']}회")
        print(f"   Arbiter 호출: {analysis['arbiter_count']}회")
        print(f"   로그 크기: {analysis['log_length']:,} chars")
        
        # 케이스별 문제점 분석
        print(f"\n⚠️ 문제점 분석:")
        
        if target_id == 11718069:
            print("   [문제] 작가 품평회인데 is_relevant=true + official_title 있음")
            print("   [원인 추정]")
            print("      • 제목이 '목마는 그냥 현판이나 써야댐' → 작품명으로 오인")
            print("      • '개돌도 후반 말아먹긴했지만' → 특정 작품 리뷰로 오인")
            print("      • 실제로는 '작가 개돌이 목마라는 작품을 이렇게 써야 한다'는 작가 비평")
            print("   [필요한 개선]")
            print("      • '~써야댐', '~해야지' 패턴 = 작가에게 하는 제안/비평 감지")
            print("      • 작가명(개돌) + '후반 망했다' = 작가 경력 평가 패턴 인식")
            print("      • P0-2 작가 필터링 강화: 작가 비평 vs 작품 리뷰 구분")
            
        elif target_id == 11718064:
            print("   [문제] official_title에 '즉사무림이유백' (축약어+캐릭터명)")
            print("   [원인 추정]")
            print("      • '즉사무림' (축약어) + '이유백' (캐릭터명)이 제목에 붙어있음")
            print("      • 실제 작품명: '즉사기 들고 무림에 떨어지다'")
            print("      • 제목 전체를 하나의 작품명으로 잘못 인식")
            print("   [필요한 개선]")
            print("      • 형태소 분석: '즉사무림'과 '이유백' 분리 감지")
            print("      • suspected_titles 검증: 검색 결과와 비교")
            print("      • 축약어 뒤에 일반명사/캐릭터명이 붙은 패턴 분리")
            
        elif target_id == 11718089:
            print("   [문제] 작가 '개돌' 작품 많아서 혼란, 날짜 기반 추론 필요")
            print("   [원인 추정]")
            print("      • '개돌 신작' → 작가의 여러 작품 중 어떤 신작인지 불명확")
            print("      • 본문에 구체적인 작품 정보 (초대남, 좆돼지 청소부)")
            print("      • 날짜(2026-01-28)와 '신작' 키워드로 시기 추론 가능했음")
            print("   [필요한 개선]")
            print("      • 작가 이름 + '신작' → 작가 최근 작품 검색")
            print("      • 날짜 정보 활용: '2026년 1월 개돌 신작' 검색")
            print("      • 본문 키워드(좆돼지 청소부, 초대남, NTR) 집중 검색")
            print("      • 검색 결과를 날짜로 필터링")
            
        elif target_id == 11718098:
            print("   [문제] '마좋좋좋' → '마법 좋아'로만 인식 (불완전)")
            print("   [원인 추정]")
            print("      • 축약어 '마좋좋좋' = '마법' + '좋아' x3")
            print("      • '마법 좋아'만 매칭, 나머지 '좋좋' 무시")
            print("      • 실제 작품명: '마법 좋아 좋아 좋아' (좋아 3번 반복)")
            print("   [필요한 개선]")
            print("      • 형태소 매칭 후 검증: '좋좋' 남았는데 의미 있나?")
            print("      • 축약어 패턴: 같은 음절 반복 감지 (좋+좋+좋)")
            print("      • suspected_titles 검증: '마법 좋아' vs '마법 좋아 좋아 좋아'")
            print("      • 제목 길이 비교: 축약어 길이와 원제목 길이의 일치성")
        
        # 로그에서 핵심 정보 추출
        if log_section:
            # Decoder의 판단
            decoder_section = re.search(r'Decoder 분석 시작.*?(?=Verifier|Critic|Arbiter|$)', log_section, re.DOTALL)
            if decoder_section:
                suspected_titles = re.findall(r'"official_novel_title":\s*"([^"]+)"', decoder_section.group(0))
                if suspected_titles:
                    print(f"\n   📚 Decoder가 식별한 제목들:")
                    for st in suspected_titles[:3]:
                        print(f"      • {st}")
            
            # Verifier의 판단
            verifier_section = re.search(r'Verifier 검증 시작.*?(?=Decoder|Critic|Arbiter|$)', log_section, re.DOTALL)
            if verifier_section:
                is_relevant_match = re.search(r'"is_relevant":\s*(true|false)', verifier_section.group(0))
                if is_relevant_match:
                    print(f"\n   🔍 Verifier 판단: is_relevant={is_relevant_match.group(1)}")

    print("\n" + "="*100)
    print("종합 개선 권장사항")
    print("="*100)
    
    print("\n【P0 우선순위】 즉시 수정 필요")
    print("  1. 작가 비평 vs 작품 리뷰 구분 강화")
    print("     • '~써야댐', '~해야지' 패턴 → 작가에게 하는 조언")
    print("     • 작가명 + 작품명이 함께 나오면 → 작가 경력/스타일 평가 가능성 높음")
    print("     • P0-2 작가 필터링 로직에 패턴 추가")
    
    print("\n  2. 축약어 + 추가 텍스트 분리")
    print("     • '즉사무림' + '이유백' → 축약어와 캐릭터명 분리")
    print("     • 형태소 분석으로 경계 감지")
    print("     • suspected_titles에서 검색 결과와 비교")
    
    print("\n【P1 우선순위】 성능 향상")
    print("  3. 날짜 기반 신작 추론")
    print("     • 작가명 + '신작' → 포스트 날짜 기준 최근 작품 검색")
    print("     • 검색 쿼리에 날짜 범위 추가")
    print("     • '2026년 1월 [작가명] 신작' 형태로 검색")
    
    print("\n  4. 축약어 반복 패턴 감지")
    print("     • '마좋좋좋' → '마' + '좋'x3 분해")
    print("     • 형태소 매칭 후 남은 부분 검증")
    print("     • '좋좋' 남았으면 → '좋아 좋아 좋아' 전체 검색")
    
    print("\n【P2 우선순위】 정교화")
    print("  5. 다중 검색 전략")
    print("     • 본문 키워드 우선순위 검색")
    print("     • 검색 결과 날짜 필터링")
    print("     • 여러 검색 결과의 교차 검증")
    
    print("\n" + "="*100)

if __name__ == "__main__":
    main()
