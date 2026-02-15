"""심층 분석 스크립트 - False Negative/Positive 핵심 분석"""
import json

with open("out/expert_result_20260208_220427.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# === 1. 명확한 False Negative 후보 ===
print("=== 명확한 False Negative 후보 (noise인데 실제 특정 소설 언급) ===")
fn_keywords = ["괴담텔", "지구온라인", "마녀도시", "해리포터", "개돌 신작",
               "담텔기", "괴담호텔"]
clearly_fn = []
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    if not ident.get("is_relevant", False) and ident.get("discussion_type") == "noise":
        pid = item.get("post_id")
        ptitle = item.get("title", "")
        content = item.get("content") or []
        ctext = " ".join(content) if isinstance(content, list) else str(content)
        check_all = (ptitle + " " + ctext).lower()
        
        matches = [kw for kw in fn_keywords if kw in check_all]
        if matches:
            reason = ident.get("reason", "")[:200]
            print(f"  POST {pid}: {ptitle}")
            print(f"    matched: {matches}")
            print(f"    content: {ctext[:150]}")
            print(f"    reason: {reason}")
            print()
            clearly_fn.append(pid)

print(f"명확한 FN 후보: {len(clearly_fn)}건\n")

# === 2. 정상 noise 판정 대표 사례 ===
print("=== 올바른 noise 판정 대표 사례 (Top 5) ===")
cnt = 0
novel_kw = ["작가","소설","작품","웹소설","문피","노벨","히로인","주인공","하렘"]
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    if not ident.get("is_relevant", False) and ident.get("discussion_type") == "noise":
        pid = item.get("post_id")
        ptitle = item.get("title", "")
        content = item.get("content") or []
        ctext = " ".join(content) if isinstance(content, list) else str(content)
        hits = [kw for kw in novel_kw if kw in (ptitle + " " + ctext).lower()]
        if len(hits) == 0:
            cnt += 1
            print(f"  {cnt}. POST {pid}: {ptitle}")
            print(f"     content: {ctext[:80]}")
            print()
            if cnt >= 5:
                break

# === 3. 전체 discussion_type별 올바른 판정 비율 추정 ===
print("\n=== 판정 정확도 추정 ===")
# relevant 판정 중 확실히 잘된 것 (High/Max + title)
total_rel = 0
good_rel = 0
questionable_rel = 0
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    ni = ident.get("novel_identity") or {}
    if ident.get("is_relevant"):
        total_rel += 1
        conf = ni.get("confidence", "")
        title = ni.get("official_title")
        if conf in ("High", "Max") and title:
            good_rel += 1
        elif not title or conf in ("Low",):
            questionable_rel += 1

print(f"  Relevant 판정 총: {total_rel}건")
print(f"  확실한 정판정 (High/Max + title): {good_rel}건 ({good_rel/max(total_rel,1)*100:.1f}%)")
print(f"  의문 판정 (no title or Low): {questionable_rel}건 ({questionable_rel/max(total_rel,1)*100:.1f}%)")

# === 4. 카테고리별 정확도 분석 - 각 discussion_type 분포 ===
print("\n=== Discussion Type별 Confidence 분포 ===")
from collections import Counter, defaultdict
dt_conf = defaultdict(Counter)
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    ni = ident.get("novel_identity") or {}
    if ident.get("is_relevant"):
        dt = ident.get("discussion_type", "unknown")
        conf = ni.get("confidence", "Unknown")
        dt_conf[dt][conf] += 1

for dt_name in sorted(dt_conf.keys()):
    confs = dt_conf[dt_name]
    total_dt = sum(confs.values())
    parts = ", ".join(f"{k}={v}" for k, v in sorted(confs.items()))
    print(f"  {dt_name}: {total_dt}건 → {parts}")

# === 5. 특정 소설인데 noise로 빠진 것 같은 핵심 케이스들 ===
print("\n=== 핵심 FN 심사 (수동 검토 필요) ===")
manual_review = []
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    if not ident.get("is_relevant", False):
        pid = item.get("post_id")
        ptitle = item.get("title", "")
        content = item.get("content") or []
        ctext = " ".join(content) if isinstance(content, list) else str(content)
        comments = item.get("comments") or []
        reason = ident.get("reason", "")
        
        # 댓글에서 작품명 언급되는 경우 = 명확한 FN
        comment_text = " ".join(str(c) for c in comments)
        if any(kw in comment_text for kw in ["제목좀", "제목 좀", "뭔 소설", "무슨 소설", "작품명"]):
            manual_review.append({
                "post_id": pid,
                "title": ptitle,
                "content": ctext[:150],
                "comment_hint": comment_text[:200],
                "reason": reason[:150],
            })

for mr in manual_review:
    print(f"  POST {mr['post_id']}: {mr['title']}")
    print(f"    content: {mr['content']}")
    print(f"    comment hint: {mr['comment_hint']}")
    print(f"    reason: {mr['reason']}")
    print()

print(f"수동 검토 필요: {len(manual_review)}건")
