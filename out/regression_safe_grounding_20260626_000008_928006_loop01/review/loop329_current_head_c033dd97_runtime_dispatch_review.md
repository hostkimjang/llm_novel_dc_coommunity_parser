# Loop329 current HEAD runtime dispatch review

- head: `c033dd97`
- 의미: Loop328 guard patch 이후 stale Loop314/326 런을 중단하고 현 HEAD 전용 output 경로로 재발주했다.
- launch health: post-patch single `1/1`, full375 `12/12`, bounded1200 `12/12`, golden18 `2/2`, 모두 search 포함 non-light다.
- N5: `15` planned, first marker 생성.
- gate: `GO_SEARCH_NONLIGHT_INITIAL`은 발주 health만 뜻한다.
- approval: `NOT_OPEN`
- search recovery: `P0 / OPEN`
- promotion_blocked: `search-blind conditional`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
