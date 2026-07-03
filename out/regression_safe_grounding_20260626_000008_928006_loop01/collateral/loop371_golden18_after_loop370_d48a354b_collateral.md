# Loop371 golden shared collateral 비교

- scope: `golden_canary_shared_posts_only`
- shared posts: `18`
- changed posts: `17`
- collateral regression candidates: `5`
- status counts: `resolved_to_null=11`, `resolved_to_different_title=6`
- runtime: completed=`18`, pending=`0`, failed=`0`
- VLM/OCR semantic gate ready: `true`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

이 파일은 golden shared post_id 비교이며, full375 collateral approval이 아니다.

## 변경 행

- `11661857`: `resolved_to_null`, regression_candidate=`false`, before=`아카데미 개망나니 교수가 되었다`, after=`None`
- `11663521`: `resolved_to_different_title`, regression_candidate=`true`, before=`초전자포] 시스터즈가 되었다`, after=`성기사는 버생을 산다`
- `11663540`: `resolved_to_different_title`, regression_candidate=`false`, before=`방구석 여신이 되었다`, after=`전 버튜버가 하고 싶은데요`
- `11668307`: `resolved_to_null`, regression_candidate=`false`, before=`디펜스게임 속 엘리트몹킬러가 되었다`, after=`None`
- `11669930`: `resolved_to_null`, regression_candidate=`false`, before=`수상할 정도로 돈이 많은 성주님 [독점]`, after=`None`
- `11673082`: `resolved_to_null`, regression_candidate=`false`, before=`용사 파티`, after=`None`
- `11684371`: `resolved_to_null`, regression_candidate=`false`, before=`괴담에 휘말렸다`, after=`None`
- `11685994`: `resolved_to_null`, regression_candidate=`true`, before=`무한을 이해한 나는 외신의 사제가 되었습니다`, after=`None`
- `11694019`: `resolved_to_null`, regression_candidate=`true`, before=`혼후 순결`, after=`None`
- `11694035`: `resolved_to_null`, regression_candidate=`false`, before=`시로코의 제멋대로 일상 단편선`, after=`None`
- `11698880`: `resolved_to_different_title`, regression_candidate=`true`, before=`가챠 중독자의 퓨전펑크 생활`, after=`아카데미 생존 갤러리`
- `11698897`: `resolved_to_different_title`, regression_candidate=`false`, before=`스페이스 오페라`, after=`[림월드]변방계에서 회귀자로 살아남기`
- `11700470`: `resolved_to_null`, regression_candidate=`true`, before=`가스라이팅`, after=`None`
- `11705231`: `resolved_to_different_title`, regression_candidate=`false`, before=`한국 레전드 프로게이머인 내가 일본판타지 사정에 휘말린 것에 대하여`, after=`탐식의 재림`
- `11705245`: `resolved_to_null`, regression_candidate=`false`, before=`하남자의 탑 공략법`, after=`None`
- `11713212`: `resolved_to_null`, regression_candidate=`false`, before=`SSS급 지력무한 영지를 손에 넣었다`, after=`None`
- `11713222`: `resolved_to_different_title`, regression_candidate=`false`, before=`하렘으로 장르를 착각함`, after=`잘생기면 편해지는 인방 생활`

Gate: golden shared collateral `NO-GO / 5 regressions`, full375 collateral `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
