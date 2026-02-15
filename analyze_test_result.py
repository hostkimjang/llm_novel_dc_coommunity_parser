"""테스트 결과 분석 스크립트 v2"""
import json
from collections import Counter

# JSON 파일 읽기
with open("out/expert_result_20260205_122914.json", "r", encoding="utf-8") as f:
    results = json.load(f)

print("=" * 70)
print("📊 테스트 결과 분석 (올바른 구조)")
print("=" * 70)

# 데이터 구조 확인
print(f"\n🔍 데이터 구조 확인:")
print(f"   Type: {type(results)}")
print(f"   Length: {len(results)}")
if results:
    print(f"   첫 번째 항목 키: {list(results[0].keys())}")
    print(f"   analysis_result 구조: {results[0].get('analysis_result', {}).keys()}")

# 전체 통계
total = len(results)
relevant_count = 0
noise_count = 0
identified_count = 0
error_count = 0

for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    
    # is_relevant 체크
    if identity.get("is_relevant"):
        relevant_count += 1
    
    # is_noise 체크 (Gatekeeper 레벨)
    if r.get("is_noise"):  # 최상위 필드
        noise_count += 1
    
    # official_title 체크
    novel_id = identity.get("novel_identity")
    if novel_id and (novel_id.get("official_title") or novel_id.get("official_novel_title")):
        identified_count += 1
    
    # 오류 체크
    reason = identity.get("reason", "")
    if "처리 오류" in reason or "validation error" in reason:
        error_count += 1

print(f"\n✅ 전체 통계:")
print(f"   총 포스트: {total}")
print(f"   Relevant: {relevant_count} ({relevant_count/total*100:.1f}%)")
print(f"   Noise (Gatekeeper): {noise_count} ({noise_count/total*100:.1f}%)")
print(f"   Identified (title 있음): {identified_count} ({identified_count/total*100:.1f}%)")
print(f"   오류 발생: {error_count}건")

# Confidence 분포
confidence_dist = Counter()
for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    novel_id = identity.get("novel_identity")
    if novel_id:
        conf = novel_id.get("confidence", "Unknown")
        confidence_dist[conf] += 1

print(f"\n📈 Confidence 분포:")
for conf, count in sorted(confidence_dist.items(), key=lambda x: -x[1]):
    print(f"   {conf}: {count}건 ({count/identified_count*100:.1f}%)")

# Relevant이지만 title 없는 케이스
print(f"\n⚠️  Relevant이지만 title 없는 케이스:")
untitled_count = 0
for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    novel_id = identity.get("novel_identity")
    
    if identity.get("is_relevant") and not novel_id:
        untitled_count += 1
        print(f"   Post {r['post_id']}: {r.get('title', '')[:50]}")
        print(f"      Discussion: {identity.get('discussion_type', 'Unknown')}")
        print(f"      Reason: {identity.get('reason', '')[:120]}...")
        print()

if untitled_count == 0:
    print("   없음")

# 오류 케이스 상세
print(f"\n❌ 오류 발생 케이스 상세:")
for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    reason = identity.get("reason", "")
    
    if "처리 오류" in reason or "validation error" in reason:
        print(f"   Post {r['post_id']}: {r.get('title', '')[:50]}")
        print(f"      Error: {reason[:200]}")
        print()

# Discussion type 분포
discussion_types = Counter()
for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    if identity.get("is_relevant"):
        dtype = identity.get("discussion_type", "Unknown")
        discussion_types[dtype] += 1

print(f"\n📝 Discussion Type 분포 (Relevant 케이스만):")
for dtype, count in sorted(discussion_types.items(), key=lambda x: -x[1]):
    print(f"   {dtype}: {count}건 ({count/relevant_count*100:.1f}%)")

# 특이 케이스 분석
print(f"\n🔍 특이 케이스 분석:")

# 1. confidence=Low 케이스
print(f"\n   1) Confidence=Low 케이스:")
low_conf_count = 0
for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    novel_id = identity.get("novel_identity")
    
    if novel_id and novel_id.get("confidence") == "Low":
        low_conf_count += 1
        title_val = novel_id.get("official_title") or novel_id.get("official_novel_title")
        print(f"      Post {r['post_id']}: {title_val}")
        print(f"         원본: {r.get('title', '')[:50]}")

if low_conf_count == 0:
    print("      없음")

# 2. 이미지 기반 판단 케이스
print(f"\n   2) 이미지 기반 판단 케이스:")
img_based = 0
for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    reason = identity.get("reason", "")
    
    if identity.get("is_relevant") and ("이미지" in reason or "image" in reason.lower() or "type=image" in reason):
        img_based += 1
        novel_id = identity.get("novel_identity")
        title_val = "N/A"
        if novel_id:
            title_val = novel_id.get("official_title") or novel_id.get("official_novel_title") or "N/A"
        
        print(f"      Post {r['post_id']}: {title_val}")
        print(f"         원본: {r.get('title', '')[:50]}")

if img_based == 0:
    print("      없음")

# 3. False Negative 후보 (noise인데 제목에 작품 관련 키워드)
print(f"\n   3) False Negative 후보:")
fn_count = 0
for r in results:
    ar = r.get("analysis_result", {})
    identity = ar.get("identity", {})
    
    if not identity.get("is_relevant"):
        title = r.get("title", "")
        # 작품 관련 키워드
        if any(kw in title for kw in ["작품", "소설", "웹소설", "추천", "재밌", "재미있"]):
            fn_count += 1
            print(f"      Post {r['post_id']}: {title[:60]}")
            print(f"         Reason: {identity.get('reason', '')[:100]}...")

if fn_count == 0:
    print("      없음")

print("\n" + "=" * 70)
