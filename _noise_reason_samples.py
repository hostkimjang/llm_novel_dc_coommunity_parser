"""Noise reason 원문 샘플 - discussion_type별 reason 퀄리티 비교"""
import json
from collections import defaultdict
from pathlib import Path

RESULT_FILE = Path("out/expert_result_20260208_220427.json")

with open(RESULT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# discussion_type별로 noise 케이스 수집
by_type = defaultdict(list)
for item in data:
    ar = item.get("analysis_result") or {}
    ident = ar.get("identity") or {}
    if not ident.get("is_relevant", False):
        dt = ident.get("discussion_type", "-")
        by_type[dt].append({
            "pid": item.get("post_id"),
            "title": item.get("title", ""),
            "reason": ident.get("reason", "")[:300],
        })

# 각 type에서 3건씩 reason 원문 표시
for dt in sorted(by_type, key=lambda x: -len(by_type[x])):
    items = by_type[dt]
    print(f"\n{'='*70}")
    print(f"[{dt}] — {len(items)}건")
    print(f"{'='*70}")
    for it in items[:3]:
        print(f"\n  POST {it['pid']}: {it['title'][:50]}")
        # reason을 줄바꿈으로 보기 좋게
        reason = it['reason'].replace('. ', '.\n    ')
        print(f"    reason: {reason}")
    if len(items) > 3:
        print(f"\n  ... 외 {len(items)-3}건")

# noise=true인데 discussion_type이 noise가 아닌 것들 (상세 카테고리가 부여된 것)
print(f"\n\n{'='*70}")
print("📌 noise인데 discussion_type이 'noise'가 아닌 케이스들")
print(f"{'='*70}")
non_noise_dt = [(dt, items) for dt, items in by_type.items() if dt != "noise"]
for dt, items in sorted(non_noise_dt, key=lambda x: -len(x[1])):
    print(f"\n  [{dt}] {len(items)}건:")
    for it in items[:2]:
        print(f"    POST {it['pid']}: {it['title'][:40]}")
        print(f"      → {it['reason'][:150]}")
