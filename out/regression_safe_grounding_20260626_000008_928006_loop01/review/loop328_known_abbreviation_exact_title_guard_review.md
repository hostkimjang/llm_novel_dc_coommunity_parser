# Loop328 known-abbreviation exact-title guard review

- 대상: `11668283 / 게임 마인드의 중세 현대인 좋았다...`
- runtime: `20260703_020949_643836`, `1/1/0/0`, search 포함 non-light.
- 결과: 관련 글로 판정됐지만 public title은 `null`, blocked title은 `게임 마인드의 중세 현대인`.
- 원인: `weak_source_exact_title_without_official_support_public_title_bridge`.
- 의미: LLM/Jury/Judge는 정답 제목으로 수렴했지만, 공식 detail URL이 없다는 이유로 final serializer가 exact title 감상글까지 hold했다.
- 수리: `known_abbreviation_title_guard` current-work scope와 exact title surface, 작품 소비 marker가 모두 있을 때만 weak-source guard를 면제한다.
- 검증: py_compile PASS, 새 focused guard `2/2` PASS, 기존 guard controls `2/2` PASS, known-title/arbiter/work-bridge bundle `33/33` PASS.
- 게이트: code contract `GO_UNIT`, runtime replay `PRE_PATCH_REPRODUCED_OVERBLOCK / NOT_APPROVAL`, post-patch runtime replay `NOT_RUN_AFTER_GUARD_PATCH`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
