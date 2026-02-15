"""전체 303건 차트 MD 생성 - 체크리스트 포함"""
import json
from pathlib import Path

RESULT_FILE = Path("out/expert_result_20260208_220427.json")
OUTPUT_MD = Path("ALL_POSTS_CHART.md")

with open(RESULT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

lines = []
L = lines.append

L("# 📋 전체 게시글 판정 차트 (303건)")
L("")
L(f"**파일**: `{RESULT_FILE}`  ")
L(f"**생성일**: 2026-02-09  ")
L(f"**용도**: 각 게시글의 판정 결과를 확인하고, 잘못된 판정에 체크(`[x]`)하세요.")
L("")
L("> **사용법**: `[ ]`를 `[x]`로 바꾸면 오판 체크 완료")
L("")

# ===== SECTION 1: Relevant 판정 (소설 관련) =====
L("---")
L("")
L("## ✅ Part A: Relevant 판정 (소설 관련)")
L("")

relevant_posts = []
noise_posts = []

for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    ni = ident.get("novel_identity") or {}
    
    pid = item.get("post_id", "?")
    ptitle = item.get("title", "")
    content = item.get("content") or []
    ctext = " ".join(content) if isinstance(content, list) else str(content)
    comments = item.get("comments") or []
    
    is_rel = ident.get("is_relevant", False)
    official_title = ni.get("official_title") or "-"
    conf = ni.get("confidence") or "-"
    dt = ident.get("discussion_type", "-")
    reason = (ident.get("reason") or "")
    
    # content 요약 (이미지 URL 제거)
    content_short = ctext.replace("type=image ", "📷").replace("url=", "")
    if len(content_short) > 80:
        content_short = content_short[:80] + "…"
    content_short = content_short.replace("|", "∣").replace("\n", " ")
    
    # reason 요약
    reason_short = reason[:120].replace("|", "∣").replace("\n", " ")
    if len(reason) > 120:
        reason_short += "…"
    
    # 게시글 제목 정리
    ptitle_clean = ptitle.replace("|", "∣").replace("\n", " ")
    official_clean = official_title.replace("|", "∣").replace("\n", " ")
    
    # 댓글 수
    comment_count = len(comments)
    
    row = {
        "pid": pid,
        "ptitle": ptitle_clean,
        "content": content_short,
        "official_title": official_clean,
        "conf": conf,
        "dt": dt,
        "reason": reason_short,
        "comment_count": comment_count,
        "is_rel": is_rel,
    }
    
    if is_rel:
        relevant_posts.append(row)
    else:
        noise_posts.append(row)

# --- Relevant 테이블 ---
L(f"**총 {len(relevant_posts)}건** — 소설 토론으로 판정된 게시글")
L("")
L("| 오판 | # | Post ID | 게시글 제목 | 식별 제목 | Conf | Type | 본문 요약 | 댓글 | Reason 요약 | 내 의견 |")
L("|:----:|:-:|---------|-----------|----------|:----:|:----:|----------|:----:|------------|--------|")

for i, r in enumerate(relevant_posts, 1):
    conf_icon = {"High": "🟢", "Max": "🔵", "Medium": "🟡", "Low": "🔴"}.get(r["conf"], "⚪")
    L(f"| [ ] | {i} | {r['pid']} | {r['ptitle'][:35]} | {r['official_title'][:25]} | {conf_icon}{r['conf']} | {r['dt']} | {r['content'][:50]} | {r['comment_count']} | {r['reason'][:80]} | |")

L("")

# ===== SECTION 2: Not Relevant 판정 (노이즈) =====
L("---")
L("")
L("## ❌ Part B: Not Relevant 판정 (노이즈)")
L("")
L(f"**총 {len(noise_posts)}건** — 소설과 무관한 것으로 판정된 게시글")
L("")
L("| 오판 | # | Post ID | 게시글 제목 | Type | 본문 요약 | 댓글 | Reason 요약 | 내 의견 |")
L("|:----:|:-:|---------|-----------|:----:|----------|:----:|------------|--------|")

for i, r in enumerate(noise_posts, 1):
    L(f"| [ ] | {i} | {r['pid']} | {r['ptitle'][:40]} | {r['dt']} | {r['content'][:55]} | {r['comment_count']} | {r['reason'][:90]} | |")

L("")

# ===== SECTION 3: 요약 통계 =====
L("---")
L("")
L("## 📊 체크 후 사용법")
L("")
L("1. 위 테이블에서 잘못 판정된 것에 `[x]` 체크")
L("2. **내 의견** 컬럼에 왜 잘못됐는지 자유롭게 메모 (예: `실제론 noise`, `제목 틀림`, `이건 XX 소설임`)")
L("3. Part A에서 `[x]` = **False Positive** (소설 아닌데 소설로 판정)")
L("4. Part B에서 `[x]` = **False Negative** (소설인데 노이즈로 판정)")
L("5. 체크 완료 후 저에게 알려주시면 오판 패턴 분석 & 코드 개선 진행")
L("")

md_text = "\n".join(lines)

with open(OUTPUT_MD, "w", encoding="utf-8") as f:
    f.write(md_text)

print(f"✅ Generated: {OUTPUT_MD}")
print(f"   Relevant: {len(relevant_posts)}건")
print(f"   Not Relevant: {len(noise_posts)}건")
print(f"   Total rows: {len(relevant_posts) + len(noise_posts)}건")
