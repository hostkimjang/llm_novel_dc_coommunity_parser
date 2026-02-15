"""FP 64건의 로그를 파이프라인 단계별로 추적 분석"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

LOG_FILE = Path("logs/expert_run_20260208_220427.log")
RESULT_FILE = Path("out/expert_result_20260208_220427.json")

# 사용자가 체크한 FP post_ids
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

# 결과 파일에서 FP 케이스 정보 로드
with open(RESULT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

fp_cases = {}
for item in data:
    pid = item.get("post_id")
    if pid in FP_IDS:
        ar = item.get("analysis_result") or {}
        ident = ar.get("identity") or {}
        analysis = ar.get("analysis") or {}
        fp_cases[pid] = {
            "title": item.get("title", ""),
            "content": item.get("content", []),
            "comments": item.get("comments", []),
            "official_title": (ident.get("novel_identity") or {}).get("official_title"),
            "confidence": (ident.get("novel_identity") or {}).get("confidence"),
            "discussion_type": ident.get("discussion_type"),
            "reason": ident.get("reason", ""),
            "detected_titles": analysis.get("detected_titles", []),
        }

print(f"FP 케이스: {len(fp_cases)}건 로드\n")

# 로그 파일 읽기 및 post_id별로 분리
print("로그 파일 파싱 중...")
log_lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").split("\n")

# 각 post_id에 대한 로그 라인 수집
post_logs = defaultdict(list)
current_pid = None

for line in log_lines:
    # post_id 감지 패턴들
    pid_match = re.search(r'post[_\s]*(?:id)?[=:]\s*(\d+)', line, re.IGNORECASE)
    if pid_match:
        found_pid = int(pid_match.group(1))
        if found_pid in FP_IDS:
            current_pid = found_pid
    
    # 현재 추적 중인 pid가 있으면 로그 수집
    if current_pid and current_pid in FP_IDS:
        post_logs[current_pid].append(line)
        
    # 다른 pid 감지되면 전환
    if pid_match:
        found_pid = int(pid_match.group(1))
        if found_pid not in FP_IDS:
            current_pid = None

print(f"로그 수집 완료: {len(post_logs)}개 FP 포스트에 대한 로그 발견\n")

# === 분석 1: 각 Expert의 판정 추출 ===
expert_patterns = {
    "gatekeeper": re.compile(r'(?:🎭|GATEKEEPER|GK).*?(is_noise|post_type|noise)\s*[=:]\s*(\S+)', re.IGNORECASE),
    "decoder": re.compile(r'(?:🔤|DECODER|DC).*?(title|best_match|confidence|식별|매칭)\s*[=:]*\s*(.{1,80})', re.IGNORECASE),
    "verifier": re.compile(r'(?:🔍|VERIFIER|VF).*?(relevant|veto|거부|noise)\s*[=:]*\s*(.{1,80})', re.IGNORECASE),
    "critic": re.compile(r'(?:📚|CRITIC|CR).*?(archetype|verdict|판정)\s*[=:]*\s*(.{1,80})', re.IGNORECASE),
    "arbiter": re.compile(r'(?:⚖️|ARBITER|AB).*?(is_relevant|discussion_type|official)\s*[=:]*\s*(.{1,80})', re.IGNORECASE),
}

# FP 패턴 분석
failure_patterns = Counter()
expert_disagreements = Counter()
pipeline_flow = defaultdict(dict)

for pid in sorted(FP_IDS):
    if pid not in post_logs:
        continue
    
    logs = post_logs[pid]
    log_text = "\n".join(logs)
    
    flow = {}
    
    # Gatekeeper 판정 추출
    if "is_noise=true" in log_text.lower() or "is_noise=True" in log_text:
        flow["gatekeeper"] = "noise"
    elif "is_noise=false" in log_text.lower() or "is_noise=False" in log_text:
        flow["gatekeeper"] = "pass"
    
    # Verifier 거부권 추출
    if "거부권 발동" in log_text or "veto" in log_text.lower() or "VETO" in log_text:
        flow["verifier_veto"] = True
    else:
        flow["verifier_veto"] = False
    
    # Decoder 제목 식별
    title_match = re.search(r'best_match.*?title["\s:=]+([^"}\n,]+)', log_text)
    if title_match:
        flow["decoder_title"] = title_match.group(1).strip()[:50]
    
    # Decoder confidence
    conf_match = re.search(r'confidence["\s:=]+(Max|High|Medium|Low|None)', log_text)
    if conf_match:
        flow["decoder_confidence"] = conf_match.group(1)
    
    # 최종 Arbiter 판정에서 왜 relevant가 됐는지 분석
    arbiter_reason = fp_cases.get(pid, {}).get("reason", "")
    
    # 패턴 분류
    content = fp_cases.get(pid, {}).get("content", [])
    content_text = " ".join(content) if isinstance(content, list) else str(content)
    
    is_image_only = all(
        "type=image" in str(c) or "url=" in str(c) 
        for c in content if c
    ) if content else False
    
    has_search_mention = "검색" in arbiter_reason or "Decoder" in arbiter_reason
    has_verifier_override = "Verifier" in arbiter_reason and ("거부" in arbiter_reason or "veto" in arbiter_reason)
    
    flow["official_title"] = fp_cases.get(pid, {}).get("official_title")
    flow["discussion_type"] = fp_cases.get(pid, {}).get("discussion_type")
    flow["is_image_only"] = is_image_only
    
    pipeline_flow[pid] = flow

# === 분석 2: FP 실패 패턴 분류 ===
print("=" * 80)
print("📊 FP 64건 파이프라인 실패 패턴 분석")
print("=" * 80)

# 패턴 1: Verifier가 거부했는데 Arbiter가 뒤집은 경우
veto_overridden = []
# 패턴 2: Decoder가 잘못된 제목을 매칭한 경우  
wrong_title = []
# 패턴 3: 이미지만 있는 글인데 relevant 판정
image_fps = []
# 패턴 4: 장르 일반론인데 작품 매칭
genre_opinion_fps = []
# 패턴 5: 커뮤니티 은어/잡담인데 작품 매칭
community_fps = []
# 패턴 6: 작가 토론인데 작품 매칭
author_fps = []

# 사용자의 의견 데이터 (이전 FP 패턴 분석에서)
user_opinions = {
    # D: 장르일반론
    11718091: "D", 11718085: "D", 11716503: "D", 11716486: "D", 11716482: "D",
    11716477: "D", 11716475: "D", 11716460: "D", 11714912: "D", 11714911: "D",
    11714910: "D", 11714879: "D", 11713226: "D", 11713218: "D", 11713217: "D",
    # E: 커뮤니티은어
    11718116: "E", 11718105: "E", 11718083: "E", 11718079: "E", 11714900: "E",
    11714874: "E", 11714871: "E", 11714863: "E", 11713209: "E", 11713204: "E",
    11713198: "E", 11713192: "E",
    # B: 이미지해독불가
    11718092: "B", 11714895: "B", 11714885: "B", 11714878: "B", 11713205: "B",
    11711636: "B", 11711635: "B", 11711581: "B",
    # F: 제목오매칭
    11718058: "F", 11714888: "F", 11713206: "F", 11711627: "F", 11714870: "F",
    11714913: "F", 11710046: "F", 11710020: "F",
    # G: 일반글
    11718080: "G", 11718055: "G", 11718054: "G", 11718051: "G", 11716496: "G",
    11716466: "G", 11714897: "G", 11711625: "G", 11711619: "G",
    # A: 플랫폼슬로건
    11711601: "A", 11711594: "A", 11711589: "A",
    # C: 작가명한계
    11714867: "C", 11714865: "C", 11711585: "C", 11710067: "C", 11710065: "C",
    # H: 시스템한계
    11713186: "H", 11710053: "H",
    # I: DC갤러리명오인
    11716448: "I", 11713202: "I",
}

for pid in sorted(FP_IDS):
    flow = pipeline_flow.get(pid, {})
    case = fp_cases.get(pid, {})
    pattern = user_opinions.get(pid, "?")
    
    if pattern == "B":
        image_fps.append(pid)
    elif pattern == "D":
        genre_opinion_fps.append(pid)
    elif pattern == "E":
        community_fps.append(pid)
    elif pattern == "C":
        author_fps.append(pid)
    elif pattern == "F":
        wrong_title.append(pid)

# === 분석 3: 각 패턴별 로그 심층 분석 ===
def print_case_detail(pid, case, flow, logs_subset):
    """케이스 상세 출력"""
    print(f"\n  POST {pid}: {case.get('title', '?')[:50]}")
    print(f"    결과: official_title={flow.get('official_title')}, "
          f"type={flow.get('discussion_type')}, verifier_veto={flow.get('verifier_veto')}")
    
    # 로그에서 핵심 이벤트 추출
    logs = post_logs.get(pid, [])
    key_events = []
    for line in logs:
        if any(kw in line for kw in [
            "식별", "매칭", "veto", "거부", "강제", "교정", "차단",
            "is_relevant", "official", "discussion_type", "confidence",
            "best_match", "title=", "작가", "author", "noise",
            "image", "은어", "장르", "트로프", "플랫폼",
        ]):
            # 타임스탬프 제거하고 핵심만
            cleaned = re.sub(r'^\[?\d{4}.*?\]?\s*', '', line.strip())
            if cleaned and len(cleaned) > 10:
                key_events.append(cleaned[:120])
    
    if key_events:
        print(f"    핵심 로그 ({len(key_events)}건 중 상위):")
        for evt in key_events[:5]:
            print(f"      → {evt}")
    else:
        print(f"    ⚠️ 핵심 로그 없음 (로그 라인: {len(logs)})")

print(f"\n{'='*80}")
print(f"패턴 B: 이미지 해독 불가 ({len(image_fps)}건)")
print(f"{'='*80}")
print("문제: 본문이 이미지만 있는데 텍스트 없이 작품 매칭 시도")
for pid in image_fps[:4]:
    case = fp_cases.get(pid, {})
    flow = pipeline_flow.get(pid, {})
    print_case_detail(pid, case, flow, [])
    # 본문 내용 확인
    content = case.get("content", [])
    text_parts = [c for c in content if isinstance(c, str) and "type=image" not in c and "url=" not in c and len(c.strip()) > 3]
    img_parts = [c for c in content if isinstance(c, str) and ("type=image" in c or "url=" in c)]
    print(f"    본문: 텍스트={len(text_parts)}건, 이미지={len(img_parts)}건")
    if text_parts:
        print(f"    텍스트 내용: {' '.join(text_parts)[:100]}")

print(f"\n{'='*80}")
print(f"패턴 D: 장르 일반론 → 작품 오매칭 ({len(genre_opinion_fps)}건)")
print(f"{'='*80}")
print("문제: 장르/소재 범용 의견인데 Decoder가 강제로 작품 매칭")
for pid in genre_opinion_fps[:5]:
    case = fp_cases.get(pid, {})
    flow = pipeline_flow.get(pid, {})
    print_case_detail(pid, case, flow, [])

print(f"\n{'='*80}")
print(f"패턴 E: 커뮤니티 은어 오인 ({len(community_fps)}건)")
print(f"{'='*80}")
print("문제: DC 갤러리 은어/잡담을 소설 토론으로 오인")
for pid in community_fps[:5]:
    case = fp_cases.get(pid, {})
    flow = pipeline_flow.get(pid, {})
    print_case_detail(pid, case, flow, [])

print(f"\n{'='*80}")
print(f"패턴 F: 잘못된 제목 매칭 ({len(wrong_title)}건)")
print(f"{'='*80}")
print("문제: Decoder가 틀린 작품을 매칭")
for pid in wrong_title[:5]:
    case = fp_cases.get(pid, {})
    flow = pipeline_flow.get(pid, {})
    print_case_detail(pid, case, flow, [])

print(f"\n{'='*80}")
print(f"패턴 C: 작가명 한계 ({len(author_fps)}건)")
print(f"{'='*80}")
for pid in author_fps[:3]:
    case = fp_cases.get(pid, {})
    flow = pipeline_flow.get(pid, {})
    print_case_detail(pid, case, flow, [])

# === 분석 4: 종합 통계 ===
print(f"\n{'='*80}")
print("📊 종합: 어느 Expert가 FP를 만들었나?")
print(f"{'='*80}")

verifier_veto_count = sum(1 for f in pipeline_flow.values() if f.get("verifier_veto"))
has_official_title = sum(1 for f in pipeline_flow.values() if f.get("official_title"))
dt_counts = Counter(f.get("discussion_type", "?") for f in pipeline_flow.values())

print(f"\n  Verifier가 거부권 발동: {verifier_veto_count}건 / {len(FP_IDS)}건")
print(f"  → Verifier가 거부했는데 Arbiter가 뒤집은 비율: {verifier_veto_count}/{len(FP_IDS)} = {verifier_veto_count/len(FP_IDS)*100:.0f}%")
print(f"\n  official_title이 있는 FP: {has_official_title}건")
print(f"  → Decoder가 제목을 매칭해서 FP가 된 비율: {has_official_title}/{len(FP_IDS)} = {has_official_title/len(FP_IDS)*100:.0f}%")

print(f"\n  FP의 discussion_type 분포:")
for dt, cnt in sorted(dt_counts.items(), key=lambda x: -x[1]):
    print(f"    {dt:20s} {cnt:3d}건")

# === 분석 5: 핵심 질문 ===
print(f"\n{'='*80}")
print("🔍 핵심 질문: 파이프라인 어디서 막았어야 했나?")
print(f"{'='*80}")

print("""
[질문 1] Gatekeeper가 더 일찍 noise로 걸렀어야 하는 케이스?
  → 이미지만 있는 글(B), 커뮤니티 잡담(E), 완전 무관 주제(G)는 
    Gatekeeper 단계에서 이미 걸러야 했음

[질문 2] Decoder가 제목 매칭을 하지 말았어야 하는 케이스?
  → 장르 일반론(D)의 핵심: Decoder가 "하렘", "아카데미" 같은 장르 키워드를
    검색해서 첫 번째 나온 작품을 매칭함. 장르 키워드 ≠ 작품명

[질문 3] Verifier가 거부했는데 Arbiter가 뒤집은 케이스?
  → Verifier의 거부가 정당했는데 Arbiter가 "Decoder 식별 우선" 규칙으로 뒤집음

[질문 4] 아예 새로운 방어막이 필요한 케이스?
  → 이미지 전용 감지, 커뮤니티 은어 사전, 장르키워드 필터 등
""")
