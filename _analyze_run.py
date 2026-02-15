"""
테스트 런 결과 분석 스크립트
expert_result_20260208_220427.json 을 분석하여 MD 리포트 생성
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RESULT_FILE = Path("out/expert_result_20260208_220427.json")
OUTPUT_MD = Path("RUN_ANALYSIS_REPORT.md")

def load_data():
    with open(RESULT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def analyze(data):
    total = len(data)
    
    # === 기본 분류 ===
    relevant_posts = []
    not_relevant_posts = []
    
    # === 상세 카운터 ===
    confidence_dist = Counter()
    discussion_types = Counter()
    titles = Counter()
    
    # === 문제 케이스 ===
    cat_a = []  # relevant=True, title=None
    cat_b = []  # confidence=Low/Medium
    cat_c = []  # noise 판정된 포스트 (false negative 가능)
    cat_d = []  # relevant=True, title 있지만 의심스러운 경우 (reason 길이 짧음)
    cat_e = []  # "웹소설로 꿈꾸는 세상!" 같은 플랫폼명이 제목인 경우
    
    # === noise 세부 분류 ===
    noise_reasons = []
    
    # === 제목별 discussion_type 분포 ===
    title_discussion_map = defaultdict(list)
    
    for item in data:
        ar = item.get("analysis_result") or {}
        ident = ar.get("identity") or {}
        ni = ident.get("novel_identity") or {}
        analysis = ar.get("analysis") or {}
        
        is_rel = ident.get("is_relevant", False)
        title = ni.get("official_title")
        conf = ni.get("confidence", "Unknown")
        dt = ident.get("discussion_type", "unknown")
        reason = ident.get("reason") or ""
        post_title = item.get("title", "")
        post_id = item.get("post_id", "?")
        content_blocks = item.get("content") or []
        comments = item.get("comments") or []
        content_text = " ".join(content_blocks) if isinstance(content_blocks, list) else str(content_blocks)
        
        confidence_dist[conf] += 1
        discussion_types[dt] += 1
        
        if is_rel:
            relevant_posts.append(item)
            if title:
                titles[title] += 1
                title_discussion_map[title].append(dt)
            else:
                cat_a.append({
                    "post_id": post_id,
                    "post_title": post_title,
                    "discussion_type": dt,
                    "reason": reason,
                    "content": content_text[:200],
                    "comments": comments[:3],
                })
        else:
            not_relevant_posts.append(item)
            if dt == "noise":
                noise_reasons.append({
                    "post_id": post_id,
                    "post_title": post_title,
                    "reason": reason,
                    "content": content_text[:150],
                })
        
        # Category B: Low/Medium confidence
        if conf in ("Low", "Medium") and title:
            cat_b.append({
                "post_id": post_id,
                "post_title": post_title,
                "official_title": title,
                "confidence": conf,
                "discussion_type": dt,
                "reason": reason,
            })
        
        # Category D: 짧은 reason (LLM이 대충 판정?)
        if is_rel and title and len(reason) < 50:
            cat_d.append({
                "post_id": post_id,
                "post_title": post_title,
                "official_title": title,
                "reason": reason,
            })
        
        # Category E: 플랫폼명이 제목인 경우
        platform_false_titles = [
            "웹소설로 꿈꾸는 세상!", "노벨피아", "문피아", "카카오페이지",
            "네이버 시리즈", "조아라", "리디북스",
        ]
        if title and title in platform_false_titles:
            cat_e.append({
                "post_id": post_id,
                "post_title": post_title,
                "official_title": title,
                "reason": reason,
            })
    
    # === noise 글 중 소설 토론일 가능성 있는 것들 (heuristic) ===
    novel_keywords = [
        "작가", "연재", "완결", "화", "권", "읽", "재밌", "스포", "전개",
        "주인공", "히로인", "캐릭", "결말", "엔딩", "ㅋㅋ", "ㅠㅠ", "스토리",
        "작품", "웹소설", "소설", "노벨", "문피", "카카오", "시리즈",
        "먼치킨", "무협", "판타지", "로맨스", "하렘", "회귀", "빙의",
        "헌터", "마법", "레벨", "스킬", "던전",
    ]
    suspicious_noise = []
    for nr in noise_reasons:
        text = (nr["post_title"] + " " + nr["content"]).lower()
        hits = [kw for kw in novel_keywords if kw in text]
        if len(hits) >= 2:
            suspicious_noise.append({
                **nr,
                "keyword_hits": hits[:5],
            })
    
    return {
        "total": total,
        "relevant_count": len(relevant_posts),
        "not_relevant_count": len(not_relevant_posts),
        "has_title_count": sum(1 for _ in relevant_posts if (((_ .get("analysis_result") or {}).get("identity") or {}).get("novel_identity") or {}).get("official_title")),
        "confidence_dist": confidence_dist,
        "discussion_types": discussion_types,
        "titles": titles,
        "cat_a": cat_a,
        "cat_b": cat_b,
        "cat_d": cat_d,
        "cat_e": cat_e,
        "suspicious_noise": suspicious_noise,
        "noise_reasons": noise_reasons,
        "title_discussion_map": title_discussion_map,
    }


def generate_md(stats):
    lines = []
    L = lines.append
    
    L("# 🔍 테스트 런 분석 리포트")
    L(f"**파일**: `{RESULT_FILE}`")
    L(f"**분석 시각**: 2026-02-09")
    L(f"**총 처리 건수**: {stats['total']}건")
    L("")
    
    # === 1. Overview ===
    L("## 1. 전체 현황 Overview")
    L("")
    L("| 지표 | 건수 | 비율 |")
    L("|------|------|------|")
    t = stats["total"]
    L(f"| ✅ Relevant (소설 관련) | {stats['relevant_count']} | {stats['relevant_count']/t*100:.1f}% |")
    L(f"| ❌ Not Relevant (노이즈) | {stats['not_relevant_count']} | {stats['not_relevant_count']/t*100:.1f}% |")
    L(f"| 📖 제목 식별 성공 | {stats['has_title_count']} | {stats['has_title_count']/t*100:.1f}% |")
    rel = stats['relevant_count'] or 1
    L(f"| 📖 제목 식별률 (relevant 중) | {stats['has_title_count']}/{stats['relevant_count']} | {stats['has_title_count']/rel*100:.1f}% |")
    L("")
    
    # === 2. Confidence Distribution ===
    L("## 2. Confidence 분포")
    L("")
    L("| Confidence | 건수 | 비율 |")
    L("|-----------|------|------|")
    for k in ["Max", "High", "Medium", "Low", "Unknown"]:
        v = stats["confidence_dist"].get(k, 0)
        L(f"| {k} | {v} | {v/t*100:.1f}% |")
    L("")
    L("> **Unknown**: noise 판정되어 confidence가 할당되지 않은 케이스")
    L("")
    
    # Confidence quality
    high_plus = stats["confidence_dist"].get("Max", 0) + stats["confidence_dist"].get("High", 0)
    if stats["has_title_count"] > 0:
        L(f"**High+ 비율** (제목 식별 건 중): {high_plus}/{stats['has_title_count']} = {high_plus/stats['has_title_count']*100:.1f}%")
    L("")
    
    # === 3. Discussion Types ===
    L("## 3. Discussion Type 분포")
    L("")
    L("```")
    dt = stats["discussion_types"]
    max_val = max(dt.values()) if dt else 1
    for k, v in sorted(dt.items(), key=lambda x: -x[1]):
        bar = "█" * int(v / max_val * 30)
        L(f"  {k:20s} {bar} {v}")
    L("```")
    L("")
    
    # === 4. Top Titles ===
    L("## 4. 식별된 소설 제목 Top 20")
    L("")
    L("| # | 소설 제목 | 언급 횟수 | discussion_types |")
    L("|---|----------|----------|-----------------|")
    for i, (title, count) in enumerate(sorted(stats["titles"].items(), key=lambda x: -x[1])[:20], 1):
        dt_list = stats["title_discussion_map"].get(title, [])
        dt_summary = ", ".join(f"{k}({v})" for k, v in Counter(dt_list).most_common(3))
        L(f"| {i} | {title} | {count} | {dt_summary} |")
    L("")
    unique = len(stats["titles"])
    L(f"**총 고유 제목 수**: {unique}개")
    L("")
    
    # === 5. Problem Cases ===
    L("## 5. 🚨 문제 케이스 분석")
    L("")
    
    # Cat A: relevant but no title
    L("### 5-A. relevant=True인데 제목 미식별")
    L(f"**건수**: {len(stats['cat_a'])}건")
    L("")
    if stats["cat_a"]:
        for c in stats["cat_a"]:
            L(f"#### Post {c['post_id']}: {c['post_title']}")
            L(f"- **type**: {c['discussion_type']}")
            L(f"- **content**: {c['content'][:200]}")
            if c['comments']:
                L(f"- **comments**: {'; '.join(str(cm)[:60] for cm in c['comments'][:3])}")
            L(f"- **reason**: {c['reason'][:300]}")
            L("")
    else:
        L("*없음 - 양호* ✅")
        L("")
    
    # Cat B: Low/Medium confidence
    L("### 5-B. confidence=Low/Medium (불확실한 식별)")
    L(f"**건수**: {len(stats['cat_b'])}건")
    L("")
    if stats["cat_b"]:
        for c in stats["cat_b"]:
            L(f"- **Post {c['post_id']}**: `{c['post_title']}`")
            L(f"  - title: `{c['official_title']}` (conf={c['confidence']})")
            L(f"  - type: {c['discussion_type']}")
            L(f"  - reason: {c['reason'][:250]}")
            L("")
    else:
        L("*없음 - 양호* ✅")
        L("")
    
    # Cat E: Platform name as title
    L("### 5-C. 플랫폼명이 소설 제목으로 식별된 경우 (False Positive)")
    L(f"**건수**: {len(stats['cat_e'])}건")
    L("")
    if stats["cat_e"]:
        for c in stats["cat_e"]:
            L(f"- **Post {c['post_id']}**: `{c['post_title']}`")
            L(f"  - ❌ title: `{c['official_title']}`")
            L(f"  - reason: {c['reason'][:250]}")
            L("")
    else:
        L("*없음 - 양호* ✅")
        L("")
    
    # === 6. Noise Analysis ===
    L("## 6. 🗑️ Noise 판정 분석")
    L("")
    L(f"**총 noise 판정**: {stats['discussion_types'].get('noise', 0)}건")
    L("")
    
    L("### 6-A. noise 중 소설 관련 키워드가 2개 이상인 의심 케이스")
    L(f"**건수**: {len(stats['suspicious_noise'])}건")
    L("")
    if stats["suspicious_noise"]:
        L("| post_id | 제목 | 키워드 히트 | reason (요약) |")
        L("|---------|------|------------|--------------|")
        for c in stats["suspicious_noise"][:30]:
            reason_short = c["reason"][:80].replace("|", "/").replace("\n", " ")
            hits = ", ".join(c["keyword_hits"][:5])
            title_short = c["post_title"][:40].replace("|", "/")
            L(f"| {c['post_id']} | {title_short} | {hits} | {reason_short} |")
        L("")
        if len(stats["suspicious_noise"]) > 30:
            L(f"... 외 {len(stats['suspicious_noise'])-30}건")
            L("")
    else:
        L("*없음 - 양호* ✅")
        L("")
    
    # === 7. Noise reason 패턴 분석 ===
    L("## 7. Noise Reason 패턴 분석")
    L("")
    reason_patterns = Counter()
    for nr in stats["noise_reasons"]:
        r = nr["reason"].lower()
        if "밈" in r or "유머" in r or "meme" in r:
            reason_patterns["밈/유머 판정"] += 1
        elif "추천" in r or "recommendation" in r:
            reason_patterns["추천 요청"] += 1
        elif "일상" in r or "개인" in r or "daily" in r:
            reason_patterns["일상 대화"] += 1
        elif "작가" in r:
            reason_patterns["작가 관련"] += 1
        elif "플랫폼" in r or "사이트" in r:
            reason_patterns["플랫폼 메타"] += 1
        elif "장르" in r or "트로프" in r or "trope" in r:
            reason_patterns["장르 일반론"] += 1
        elif "소설" not in r and "작품" not in r:
            reason_patterns["기타 (소설 무관)"] += 1
        else:
            reason_patterns["기타"] += 1
    
    L("| 패턴 | 건수 |")
    L("|------|------|")
    for k, v in sorted(reason_patterns.items(), key=lambda x: -x[1]):
        L(f"| {k} | {v} |")
    L("")
    
    # === 8. Summary & Recommendations ===
    L("## 8. 📊 종합 평가 & 개선 권고")
    L("")
    
    # Scoring
    title_rate = stats['has_title_count'] / max(stats['relevant_count'], 1) * 100
    high_rate = high_plus / max(stats['has_title_count'], 1) * 100
    noise_suspect_rate = len(stats['suspicious_noise']) / max(stats['discussion_types'].get('noise', 1), 1) * 100
    
    L("### 핵심 지표")
    L("")
    L("| 지표 | 값 | 평가 |")
    L("|------|-----|------|")
    L(f"| 제목 식별률 | {title_rate:.1f}% | {'✅ 양호' if title_rate >= 90 else '⚠️ 개선 필요' if title_rate >= 75 else '❌ 미흡'} |")
    L(f"| High+ 신뢰도 비율 | {high_rate:.1f}% | {'✅ 양호' if high_rate >= 85 else '⚠️ 개선 필요' if high_rate >= 70 else '❌ 미흡'} |")
    L(f"| Noise 오판 의심률 | {noise_suspect_rate:.1f}% | {'✅ 양호' if noise_suspect_rate <= 10 else '⚠️ 주의' if noise_suspect_rate <= 20 else '❌ 높음'} |")
    L(f"| 플랫폼명 오식별 | {len(stats['cat_e'])}건 | {'✅ 양호' if len(stats['cat_e']) == 0 else '❌ 수정 필요'} |")
    L(f"| relevant+제목없음 | {len(stats['cat_a'])}건 | {'✅ 양호' if len(stats['cat_a']) <= 2 else '⚠️ 개선 필요'} |")
    L("")
    
    L("### 개선 권고 사항")
    L("")
    if len(stats['cat_a']) > 0:
        L(f"1. **제목 미식별 케이스 {len(stats['cat_a'])}건 조사 필요**: relevant로 판정했지만 공식 제목을 찾지 못한 경우. Decoder의 rescue 로직 또는 검색 결과 부족 가능성.")
    if len(stats['cat_b']) > 0:
        L(f"2. **불확실한 식별 {len(stats['cat_b'])}건 재검토**: Low/Medium confidence는 오식별 위험이 높음. 검색 결과 품질 또는 축약어 매칭 로직 점검 필요.")
    if len(stats['cat_e']) > 0:
        L(f"3. **플랫폼명 오식별 {len(stats['cat_e'])}건 수정 필요**: 플랫폼 가드 로직 강화 필요.")
    if len(stats['suspicious_noise']) > 10:
        L(f"4. **Noise 오판 의심 {len(stats['suspicious_noise'])}건 샘플 검증 필요**: 소설 관련 키워드가 다수 포함된 noise 글. Gatekeeper 임계값 조정 검토.")
    if high_rate < 85:
        L(f"5. **전체 신뢰도 개선**: High+ 비율 {high_rate:.1f}%는 목표(85%) 미달. Decoder-Verifier 협력 강화 또는 프롬프트 개선 필요.")
    L("")
    
    return "\n".join(lines)


def main():
    data = load_data()
    stats = analyze(data)
    md = generate_md(stats)
    
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    
    print(f"✅ Report generated: {OUTPUT_MD}")
    print(f"   Total: {stats['total']} posts")
    print(f"   Relevant: {stats['relevant_count']}, Not Relevant: {stats['not_relevant_count']}")
    print(f"   Titles identified: {stats['has_title_count']}")
    print(f"   Problem cases: A={len(stats['cat_a'])}, B={len(stats['cat_b'])}, E={len(stats['cat_e'])}")
    print(f"   Suspicious noise: {len(stats['suspicious_noise'])}")


if __name__ == "__main__":
    main()
