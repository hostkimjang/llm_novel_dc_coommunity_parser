import json, sys

with open('out/expert_result_20260206_174958.json', encoding='utf-8') as f:
    data = json.load(f)

print(f"총 {len(data)}개 포스트\n")
header = f"{'#':>2} | {'post_id':>10} | rel | {'conf':>6} | {'discussion_type':>15} | {'official_title':<38} | 포스트 제목"
print(header)
print("-" * len(header.encode('utf-8')))

for i, post in enumerate(data, 1):
    ar = post.get('analysis_result', {})
    ident = ar.get('identity', {})
    is_rel = ident.get('is_relevant', False)
    novel = ident.get('novel_identity') or {}
    title = novel.get('official_title') or 'null'
    conf = novel.get('confidence') or '-'
    dtype = ident.get('discussion_type') or '-'
    ptitle = post.get('title', '')[:35]
    rel_mark = ' O ' if is_rel else ' X '
    print(f"{i:>2} | {post['post_id']:>10} | {rel_mark} | {conf:>6} | {dtype:>15} | {title[:38]:<38} | {ptitle}")

# 오류 포스트 확인
print("\n=== 오류/의심 케이스 ===")
for i, post in enumerate(data, 1):
    ar = post.get('analysis_result', {})
    ident = ar.get('identity', {})
    reason = ident.get('reason', '')
    if '오류' in reason or '처리 오류' in reason:
        print(f"  #{i} post_id={post['post_id']}: 처리 오류 발생")
    novel = ident.get('novel_identity') or {}
    title = novel.get('official_title') or ''
    ptitle = post.get('title', '')
    # 포스트 제목이 official_title에 포함되거나 유사한 경우
    if title and title in ptitle:
        print(f"  #{i} post_id={post['post_id']}: official_title '{title}' 이 포스트 제목에 포함됨 (도용 의심)")
