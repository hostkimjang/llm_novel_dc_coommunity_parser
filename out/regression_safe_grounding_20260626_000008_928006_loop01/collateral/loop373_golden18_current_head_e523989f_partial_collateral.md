# Loop373 golden18 partial collateral compare

- scope: `golden_canary_shared_posts_only`
- shared posts: `12`
- changed posts: `12`
- collateral regression candidates: `4`
- status counts: `resolved_to_null=7`, `resolved_to_different_title=5`
- runtime: completed=`13`, flushed=`12`, pending=`1`, failed=`0`
- VLM/OCR semantic review ready: `true`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

이 파일은 golden shared post_id partial 비교다. current HEAD golden18 런이 `18/18`로 완주하지 못했으므로 full375 collateral gate나 semantic approval 근거가 아니다.

## 변경 행

- `11661857`: `resolved_to_null`, regression_candidate=`false`, before=`아카데미 개망나니 교수가 되었다`, after=`None`
- `11663521`: `resolved_to_different_title`, regression_candidate=`true`, before=`초전자포] 시스터즈가 되었다`, after=`성기사는 버생을 산다`
- `11663540`: `resolved_to_different_title`, regression_candidate=`false`, before=`방구석 여신이 되었다`, after=`전 버튜버가 하고 싶은데요`
- `11668307`: `resolved_to_different_title`, regression_candidate=`true`, before=`디펜스게임 속 엘리트몹킬러가 되었다`, after=`빚을 져서라도 세상은 구해야 할 거 아니야 [독점]`
- `11669930`: `resolved_to_null`, regression_candidate=`false`, before=`수상할 정도로 돈이 많은 성주님 [독점]`, after=`None`
- `11673082`: `resolved_to_null`, regression_candidate=`false`, before=`용사 파티`, after=`None`
- `11684371`: `resolved_to_null`, regression_candidate=`false`, before=`괴담에 휘말렸다`, after=`None`
- `11685994`: `resolved_to_different_title`, regression_candidate=`true`, before=`무한을 이해한 나는 외신의 사제가 되었습니다`, after=`교황님 아하세요 마왕들 들어가요`
- `11694019`: `resolved_to_null`, regression_candidate=`true`, before=`혼후 순결`, after=`None`
- `11694035`: `resolved_to_null`, regression_candidate=`false`, before=`시로코의 제멋대로 일상 단편선`, after=`None`
- `11698897`: `resolved_to_different_title`, regression_candidate=`false`, before=`스페이스 오페라`, after=`[림월드]변방계에서 회귀자로 살아남기`
- `11705245`: `resolved_to_null`, regression_candidate=`false`, before=`하남자의 탑 공략법`, after=`None`

## Gate

- collateral compare: `NO-GO / partial shared 12`
- full375 collateral gate: `NOT_OPEN`
- golden18 runtime proof: `NO-GO / 13 of 18`
- semantic quality: `REVIEW-LOCKED`
- full scan approval: `false`
