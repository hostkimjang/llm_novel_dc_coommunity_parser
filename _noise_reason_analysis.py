"""Noise reason 심층 분석 - 카테고리 부족 문제 진단"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

RESULT_FILE = Path("out/expert_result_20260208_220427.json")

with open(RESULT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# === 1. noise 판정된 글들의 reason 수집 ===
noise_reasons = []
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    if not ident.get("is_relevant", False):
        pid = item.get("post_id", "?")
        ptitle = item.get("title", "")
        dt = ident.get("discussion_type", "-")
        reason = ident.get("reason") or ""
        content = item.get("content") or []
        ctext = " ".join(content) if isinstance(content, list) else str(content)
        comments = item.get("comments") or []
        
        noise_reasons.append({
            "pid": pid,
            "title": ptitle,
            "dt": dt,
            "reason": reason,
            "content": ctext[:200],
            "comment_count": len(comments),
        })

print(f"총 noise 판정: {len(noise_reasons)}건\n")

# === 2. reason에 등장하는 핵심 판정 근거 패턴 추출 ===
reason_keywords = {
    "verifier_veto": ["Verifier의 거부권", "Verifier가 거부", "거부권 발동", "거부권이 최우선", "Veto"],
    "no_specific_work": ["특정 작품", "특정 웹소설", "작품 식별", "작품을 식별", "식별하지 못"],
    "genre_general": ["장르 토론", "장르 일반", "트로프", "일반론", "범용적"],
    "real_world": ["현실 영역", "현실 세계", "일상", "현실적"],
    "meme_humor": ["밈", "유머", "장붕", "뻘글"],
    "platform_meta": ["플랫폼", "노벨피아", "문피아", "사이트"],
    "image_only": ["이미지", "type=image", "url="],
    "author_career": ["작가의", "작가가", "작가 비평", "작가명"],
    "recommendation": ["추천", "요청"],
    "decoder_fail": ["Decoder.*식별.*실패", "title=null", "식별 불가"],
    "arbiter_error": ["Arbiter 오류", "NoneType"],
    "discourse_mismatch": ["담화 영역", "담론", "맥락.*불일치", "연상글"],
}

pattern_hits = Counter()
multi_reason_map = defaultdict(list)  # pid -> [matched patterns]

for nr in noise_reasons:
    r = nr["reason"]
    matched = []
    for pat_name, keywords in reason_keywords.items():
        for kw in keywords:
            if re.search(kw, r, re.IGNORECASE):
                matched.append(pat_name)
                break
    
    if not matched:
        matched.append("UNCATEGORIZED")
    
    for m in matched:
        pattern_hits[m] += 1
    multi_reason_map[nr["pid"]] = matched

print("=" * 60)
print("현재 reason에서 감지되는 판정 근거 패턴")
print("=" * 60)

for pat, cnt in sorted(pattern_hits.items(), key=lambda x: -x[1]):
    pct = cnt / len(noise_reasons) * 100
    label = {
        "verifier_veto": "Verifier 거부권 발동",
        "no_specific_work": "특정 작품 식별 불가",
        "genre_general": "장르 일반론/트로프",
        "real_world": "현실/일상 영역",
        "meme_humor": "밈/유머/뻘글",
        "platform_meta": "플랫폼 메타 토론",
        "image_only": "이미지 기반 게시글",
        "author_career": "작가 관련 토론",
        "recommendation": "추천 요청",
        "decoder_fail": "Decoder 식별 실패",
        "arbiter_error": "Arbiter 시스템 오류",
        "discourse_mismatch": "담화 영역 불일치/연상글",
        "UNCATEGORIZED": "⚠️ 분류 불가 (패턴 미매칭)",
    }.get(pat, pat)
    print(f"  {label:30s} {cnt:3d}건 ({pct:.0f}%)")

print()

# === 3. 분류 불가 케이스 reason 샘플 ===
uncategorized = [nr for nr in noise_reasons if "UNCATEGORIZED" in multi_reason_map[nr["pid"]]]
print(f"분류 불가 reason 샘플 ({len(uncategorized)}건 중 상위 15개):")
print("-" * 60)
for nr in uncategorized[:15]:
    print(f"  POST {nr['pid']}: {nr['title'][:40]}")
    print(f"    reason: {nr['reason'][:200]}")
    print()

# === 4. Relevant로 잘못 판정된 FP 케이스들의 reason 패턴 (비교용) ===
print()
print("=" * 60)
print("FP (잘못된 relevant) 케이스들의 reason 패턴 비교")
print("=" * 60)

# 사용자가 체크한 FP post_ids
fp_ids = {
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

fp_reason_keywords = Counter()
for item in data:
    pid = item.get("post_id")
    if pid in fp_ids:
        ar = item.get("analysis_result") or {}
        ident = ar.get("identity") or {}
        reason = ident.get("reason") or ""
        
        # FP reason에 어떤 판정 근거가 있는지
        for pat_name, keywords in reason_keywords.items():
            for kw in keywords:
                if re.search(kw, reason, re.IGNORECASE):
                    fp_reason_keywords[pat_name] += 1
                    break

print("\nFP 케이스에서 언급된 판정 근거 (이게 있는데도 relevant로 판정됨):")
for pat, cnt in sorted(fp_reason_keywords.items(), key=lambda x: -x[1]):
    print(f"  {pat:30s} {cnt:3d}건")

# === 5. 실제로 부족한 카테고리 도출 ===
print()
print("=" * 60)
print("🔍 현재 시스템에 부족한 reason 카테고리 진단")
print("=" * 60)
print()

missing_categories = [
    ("COMMUNITY_CULTURE", "커뮤니티 문화/은어 판정",
     "장붕=유저, 파딱=완장, 분충=분탕충, 누렁이=비선별 독자 등 DC 고유 은어를 식별하고\n"
     "  '이것은 작품명이 아닌 커뮤니티 은어'라는 판정 근거를 제공"),
    
    ("IMAGE_DEPENDENCY", "이미지 의존 게시글 판정",
     "본문이 type=image만 있고 텍스트가 없는 경우\n"
     "  '이미지 해독 불가로 작품 식별 불가능'이라는 명확한 판정"),
    
    ("GENRE_OPINION", "장르 의견 vs 작품 토론 구분",
     "'~하는 소설 없냐', '아카데미 습격은 ~', '하렘은 ~' 같은\n"
     "  장르/소재에 대한 범용 의견을 특정 작품 토론과 구분"),
    
    ("AUTHOR_NEW_WORK", "작가 신작 언급 판정",
     "'목마 신작', '시저디 신작', '양치기 작가' 같은 패턴에서\n"
     "  작가의 기존작을 제목으로 넣지 않고 '작가명+신작' 형태로 처리"),
    
    ("USER_BANTER", "유저 간 잡담/뻘글 판정",
     "'장붕아 ~', '찐친 ~', '글 쓰고 보니' 같은 커뮤니티 내 일상 대화를\n"
     "  소설 토론으로 오인하지 않도록 하는 명확한 카테고리"),
    
    ("WORK_UNIDENTIFIABLE", "작품 불특정 판정",
     "소설에 대해 이야기하긴 하지만 어떤 작품인지 특정할 수 없는 경우\n"
     "  relevant=true이지만 title=null이 정당한 케이스 vs 아예 noise인 케이스 구분"),
    
    ("SEO_POLLUTION", "검색 SEO 오염 판정",
     "검색 결과에서 플랫폼 SEO 문구(웹소설로 꿈꾸는 세상!)가 제목으로 섞이는 패턴\n"
     "  Decoder 검색 후 결과 필터링 강화"),
]

for code, title, desc in missing_categories:
    print(f"[{code}]")
    print(f"  {title}")
    print(f"  → {desc}")
    print()

# === 6. discussion_type 개선 제안 ===
print("=" * 60)
print("현재 discussion_type 체계 vs 제안")
print("=" * 60)

current_types = Counter()
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    dt = ident.get("discussion_type", "-")
    current_types[dt] += 1

print("\n현재:")
for dt, cnt in sorted(current_types.items(), key=lambda x: -x[1]):
    print(f"  {dt:25s} {cnt:3d}건")

print("\n제안 추가:")
suggested_new = [
    ("genre_opinion", "장르/소재에 대한 범용 의견 (특정 작품 없음)"),
    ("community_banter", "커뮤니티 유저 간 잡담/뻘글"),
    ("author_discussion", "작가에 대한 토론 (특정 작품 불특정)"),
    ("image_post", "이미지 중심 게시글 (텍스트 부족)"),
    ("platform_discussion", "플랫폼 자체에 대한 토론"),
    ("unidentifiable_work", "소설 관련이지만 작품 특정 불가"),
]
for code, desc in suggested_new:
    print(f"  + {code:25s} {desc}")
