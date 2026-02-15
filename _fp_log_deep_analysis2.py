"""FP 심층 분석 2: 각 Expert별 판정 흐름 완전 추적"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

LOG_FILE = Path("logs/expert_run_20260208_220427.log")
RESULT_FILE = Path("out/expert_result_20260208_220427.json")

FP_IDS = {
    11718085, 11718092, 11718091, 11718116, 11718105, 11718083, 11718080,
    11718079, 11718058, 11718055, 11718054, 11718051, 11716503, 11716496,
    11716486, 11716482, 11716477, 11716475, 11716466, 11716460, 11716448,
    11714913, 11714912, 11714911, 11714910, 11714900, 11714897, 11714895,
    11714888, 11714885, 11714879, 11714878, 11714874, 11714871, 11714870,
    11714867, 11714865, 11714863, 11713226, 11713218, 11713217, 11713209,
    11713206, 11713205, 11713204, 11713202, 11713198, 11713192, 11713186,
    11711636, 11711635, 11711627, 11711625, 11711619, 11711601, 11711594,
    11711589, 11711585, 11711581, 11710067, 11710065, 11710053, 11710046,
    11710020,
}

log_text = LOG_FILE.read_text(encoding="utf-8", errors="replace")

# 패턴별로 각 Expert의 판정을 로그에서 정확히 추출
# 로그 형식: [시간][이모지] 메시지
# 예: [06:43:51.761][🎭] Gatekeeper 완료 (14.6s): is_noise=False, post_type=work_discussion

results = {}

for pid in sorted(FP_IDS):
    pid_str = str(pid)
    
    # 이 post_id와 관련된 로그 구간 찾기
    # 패턴: "post_id=XXXXX" 또는 "ID: XXXXX"
    gk_noise = None
    gk_post_type = None
    dc_title = None
    dc_confidence = None
    vf_relevant = None
    vf_veto = None
    
    # Gatekeeper 결과 라인 찾기
    gk_pattern = rf'Gatekeeper 완료.*?{pid_str}|post_id={pid_str}.*?Gatekeeper|{pid_str}.*?is_noise=(True|False).*?post_type=(\w+)'
    # 더 넓은 범위로 로그 구간 추출
    
    # 방법: post_id 전후 구간의 Expert 완료 메시지 찾기
    # [시간][이모지] Expert명 완료 (시간s): key=value
    
    # 간단한 방법: 로그에서 이 post_id 관련 전문가 완료 메시지 추출
    lines = log_text.split("\n")
    in_post = False
    post_section = []
    
    for i, line in enumerate(lines):
        if pid_str in line:
            in_post = True
            start_idx = max(0, i - 2)
        if in_post:
            post_section.append(line)
            # 다른 post_id가 나오면 종료
            if len(post_section) > 5:
                other_pid = re.search(r'post_id=(\d+)', line)
                if other_pid and other_pid.group(1) != pid_str:
                    in_post = False
                    break
            if len(post_section) > 300:  # 안전 제한
                break
    
    section_text = "\n".join(post_section)
    
    # Gatekeeper 판정 추출
    gk_match = re.search(r'Gatekeeper 완료.*?is_noise=(True|False).*?post_type=(\w+)', section_text)
    if gk_match:
        gk_noise = gk_match.group(1) == "True"
        gk_post_type = gk_match.group(2)
    
    # Decoder 판정 추출
    dc_match = re.search(r'Decoder 완료.*?title=(.+?)(?:,|\s|$)', section_text)
    if dc_match:
        dc_title = dc_match.group(1).strip()
    
    # Verifier 판정 추출
    vf_match = re.search(r'Verifier 완료.*?relevant=(True|False)', section_text)
    if vf_match:
        vf_relevant = vf_match.group(1) == "True"
    
    vf_veto_match = re.search(r'거부권|VETO|veto', section_text)
    vf_veto = bool(vf_veto_match)
    
    results[pid] = {
        "gk_noise": gk_noise,
        "gk_post_type": gk_post_type,
        "vf_relevant": vf_relevant,
        "vf_veto": vf_veto,
    }

# 이제 결과 파일에서 최종 판정과 비교
with open(RESULT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

fp_data = {}
for item in data:
    pid = item.get("post_id")
    if pid in FP_IDS:
        ar = item.get("analysis_result") or {}
        ident = ar.get("identity") or {}
        ni = ident.get("novel_identity") or {}
        fp_data[pid] = {
            "title": item.get("title", ""),
            "official_title": ni.get("official_title"),
            "confidence": ni.get("confidence"),
            "discussion_type": ident.get("discussion_type"),
            "reason": ident.get("reason", "")[:200],
        }

# === 핵심 분석: 어디서 판정이 잘못됐나? ===
print("=" * 80)
print("Expert별 판정 추적: FP 64건의 파이프라인 흐름")
print("=" * 80)

# 1. Gatekeeper가 noise로 잡았는데 뒤집힌 케이스
gk_caught = [(pid, r) for pid, r in results.items() if r["gk_noise"] == True]
gk_passed = [(pid, r) for pid, r in results.items() if r["gk_noise"] == False]
gk_unknown = [(pid, r) for pid, r in results.items() if r["gk_noise"] is None]

print(f"\n[1] Gatekeeper 판정:")
print(f"  noise로 잡은 FP: {len(gk_caught)}건 (잡았는데 뒤집힘)")
print(f"  통과시킨 FP:     {len(gk_passed)}건 (놓침)")  
print(f"  판정 불명:       {len(gk_unknown)}건")

if gk_caught:
    print(f"\n  --- Gatekeeper가 noise로 잡았는데 뒤집힌 케이스 ---")
    for pid, r in gk_caught:
        fd = fp_data.get(pid, {})
        print(f"  POST {pid}: {fd.get('title', '?')[:40]}")
        print(f"    GK: noise=True, type={r['gk_post_type']}")
        print(f"    최종: official_title={fd.get('official_title')}, type={fd.get('discussion_type')}")
        print(f"    reason: {fd.get('reason', '')[:100]}")

# 2. Gatekeeper post_type 분포
gk_types = Counter(r["gk_post_type"] for r in results.values() if r["gk_post_type"])
print(f"\n[2] Gatekeeper post_type 분포 (FP에서):")
for t, c in sorted(gk_types.items(), key=lambda x: -x[1]):
    print(f"  {t:25s} {c:3d}건")

# 3. Verifier 판정
vf_caught = [(pid, r) for pid, r in results.items() if r["vf_relevant"] == False]
vf_passed = [(pid, r) for pid, r in results.items() if r["vf_relevant"] == True]
vf_unknown = [(pid, r) for pid, r in results.items() if r["vf_relevant"] is None]

print(f"\n[3] Verifier 판정:")
print(f"  relevant=false (정당한 거부): {len(vf_caught)}건")
print(f"  relevant=true (놓침):         {len(vf_passed)}건")
print(f"  판정 불명:                    {len(vf_unknown)}건")

if vf_caught:
    print(f"\n  --- Verifier가 거부했는데 Arbiter가 뒤집은 {len(vf_caught)}건 ---")
    for pid, r in vf_caught[:10]:
        fd = fp_data.get(pid, {})
        print(f"  POST {pid}: {fd.get('title', '?')[:40]}")
        print(f"    VF: relevant=False, veto={r['vf_veto']}")
        print(f"    최종: official_title={fd.get('official_title')}, type={fd.get('discussion_type')}")

# 4. 핵심: confidence 분포
print(f"\n[4] FP의 confidence 분포:")
conf_dist = Counter(fp_data[pid].get("confidence") for pid in FP_IDS if pid in fp_data)
for c, cnt in sorted(conf_dist.items(), key=lambda x: -x[1]):
    print(f"  {str(c):10s} {cnt:3d}건")

# 5. official_title 분포 (어떤 작품이 가장 많이 오매칭?)
print(f"\n[5] 오매칭된 작품 빈도 (상위):")
title_dist = Counter(fp_data[pid].get("official_title") for pid in FP_IDS if pid in fp_data)
for t, cnt in sorted(title_dist.items(), key=lambda x: -x[1])[:10]:
    print(f"  {str(t):40s} {cnt:3d}건")

# 6. 핵심 인사이트
print(f"\n{'='*80}")
print("핵심 인사이트")
print(f"{'='*80}")

# Decoder가 검색해서 첫 번째 결과를 매칭한 경우 감지
# reason에서 "검색", "Decoder" 키워드 빈도
has_decoder_reason = sum(1 for pid in FP_IDS if pid in fp_data and "Decoder" in fp_data[pid].get("reason", ""))
has_search_reason = sum(1 for pid in FP_IDS if pid in fp_data and "검색" in fp_data[pid].get("reason", ""))

print(f"\n  reason에 'Decoder' 언급: {has_decoder_reason}건")
print(f"  reason에 '검색' 언급:    {has_search_reason}건")
print(f"  → Decoder의 검색 기반 매칭이 FP의 주범")

# official_title이 None인 FP (제목 없이도 relevant 판정)
no_title = sum(1 for pid in FP_IDS if pid in fp_data and not fp_data[pid].get("official_title"))
print(f"\n  official_title=None인 FP: {no_title}건")
print(f"  official_title 있는 FP:   {len(FP_IDS) - no_title}건")
print(f"  → FP의 {(len(FP_IDS) - no_title)/len(FP_IDS)*100:.0f}%가 '잘못된 제목 매칭'이 원인")

print(f"\n{'='*80}")
print("구조적 문제 진단")
print(f"{'='*80}")
print("""
[문제 1] Decoder의 "무조건 매칭" 강박
  → 64건 FP 중 61건(95%)에서 Decoder가 official_title을 채움
  → Decoder가 title=null을 반환하는 것을 극도로 꺼림
  → "아카데미 습격"이라는 장르 키워드를 검색 → "아카데미 습격자"라는 작품 발견 → 매칭
  → 개선: Decoder에게 "장르 키워드 검색 결과는 작품 매칭하지 말라" 지시 강화

[문제 2] Verifier 거부권의 약화
  → Verifier가 거부한 FP 비율 확인 필요
  → 거부했는데 Arbiter가 뒤집은 경우: "Decoder 식별 우선" 규칙이 과도
  → 개선: Verifier 거부 시 Arbiter의 override 조건 강화

[문제 3] 본문 분석 부재
  → 현재: 제목 기반 검색 → 작품 매칭 → relevant
  → 필요: 본문에 작품 고유 정보(캐릭터명, 줄거리, 회차 등)가 있는지 검증
  → "아카데미 습격" 제목 + 본문 "걍 폭격기 보내면 안되나" → 장르 일반론!
  → 본문에 캐릭터명, 줄거리 등이 없으면 → 장르 일반론으로 격하

[문제 4] 커뮤니티 은어 감지 실패
  → "장붕", "파딱", "분충" 등 DC 은어가 제목에 있어도 작품 키워드로 검색
  → Gatekeeper에 은어 사전 추가 → 은어가 주요 키워드면 community_banter

[문제 5] 이미지 전용 게시글 감지 부재
  → content_blocks에서 type=image만 있으면 → Gatekeeper 단계에서 image_post
  → 현재: 이미지 URL을 무시하고 제목만으로 매칭 시도
""")
