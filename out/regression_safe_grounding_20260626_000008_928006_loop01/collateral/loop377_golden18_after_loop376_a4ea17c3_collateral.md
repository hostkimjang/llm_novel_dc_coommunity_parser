# Loop377 golden shared collateral 비교

- scope: `golden_canary_shared_posts_only`
- shared posts: `18`
- changed posts: `17`
- collateral regression candidates: `7`
- status counts: `resolved_to_null=12`, `resolved_to_different_title=5`
- runtime: completed=`18`, pending=`0`, failed=`0`
- VLM/OCR semantic gate ready: `true`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

이 파일은 golden shared post_id 비교이며 full375 collateral approval이 아니다.

## Regression Candidates

- `11663521`: `초전자포] 시스터즈가 되었다` -> `구원자의 퍼스트 레이디`
- `11668307`: `디펜스게임 속 엘리트몹킬러가 되었다` -> `None`
- `11685994`: `무한을 이해한 나는 외신의 사제가 되었습니다` -> `None`
- `11694019`: `혼후 순결` -> `None`
- `11698880`: `가챠 중독자의 퓨전펑크 생활` -> `아카데미 생존 갤러리`
- `11698897`: `스페이스 오페라` -> `None`
- `11700470`: `가스라이팅` -> `None`

## Expected-Answer Exemptions

다음 변화는 golden expected-answer에서 정당한 null 또는 정당한 교정으로 exempt 처리됐다: `11661857`, `11663540`, `11669930`, `11673082`, `11684371`, `11694035`, `11705231`, `11705245`, `11713212`, `11713222`.

## Gate

Golden shared collateral은 `NO-GO / 7 regressions`다. full375 collateral은 `NOT_OPEN`, semantic_quality는 `REVIEW-LOCKED`, full_scan_approval은 `false`를 유지한다.
