# loop598_remaining4_native_hold_full375_collateral_compare

Loop580 projection 결과를 baseline full375와 비교한 정적 collateral diff다. runtime 375 완주가 아니므로 regression 수가 줄어도 full_scan approval은 열리지 않는다.

## 요약

- gate: `NO-GO`
- projection_static_collateral_gate: `NO-GO`
- runtime_collateral_gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- shared posts: `375/375`
- changed rows: `152`
- raw collateral_regression_count: `73`
- status_counts: `{'same_title_url_changed': 66, 'null_to_resolved': 21, 'resolved_to_different_title': 27, 'resolved_to_null': 38}`
- regression_status_counts: `{'null_to_resolved': 21, 'resolved_to_different_title': 21, 'resolved_to_null': 31}`
- runtime counts: `missing`

## 차단 항목

- `projection_static_collateral_regression_nonzero`
- `collateral_runtime_counts_missing`

## Regression 샘플

- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11660232` `resolved_to_different_title` `괴담 동아리` -> `괴담 호텔 탈출기` (safe_resolved -> safe_resolved)
- `11660238` `null_to_resolved` `None` -> `무림마조` (promotion_blocked -> safe_resolved)
- `11660254` `resolved_to_null` `푸푸푸 랜드의 두가지 일상` -> `None` (safe_resolved -> promotion_blocked)
- `11660262` `resolved_to_different_title` `그렇게, 그 괴물과 두 번 결혼했다` -> `로판에 도파민을 풀었다` (safe_resolved -> safe_resolved)
- `11661856` `resolved_to_different_title` `너랑은 절! 대! 안 사Kill거니까!` -> `너랑은 절! 대! 안 사갈거니까!` (safe_resolved -> safe_resolved)
- `11661863` `resolved_to_null` `저주받은 영애가 되었습니다` -> `None` (safe_resolved -> promotion_blocked)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11665099` `resolved_to_different_title` `옥천마 출정` -> `옥탑방의 천재 마물 소환사` (safe_resolved -> safe_resolved)
- `11665110` `resolved_to_different_title` `낭만적인 초능력을 위하여` -> `사이키델리아` (safe_resolved -> safe_resolved)
- `11665124` `resolved_to_different_title` `화산파(화산귀환)` -> `화산귀환` (safe_resolved -> safe_resolved)
- `11666700` `resolved_to_different_title` `하남자의 탑 공략법` -> `내 고향엔 무림인이 산다` (safe_resolved -> safe_resolved)
- `11668278` `resolved_to_null` `짜장면` -> `None` (safe_resolved -> promotion_blocked)
- `11668305` `resolved_to_null` `Fate/stay night` -> `None` (safe_resolved -> promotion_blocked)
- `11669928` `null_to_resolved` `None` -> `탑의 성좌들이 날 애호한다` (promotion_blocked -> safe_resolved)
- `11669929` `resolved_to_different_title` `기계공주` -> `헌터갤러리의 국가권력급 기계공주` (safe_resolved -> safe_resolved)
- `11671500` `resolved_to_different_title` `악당도 살고 싶다` -> `악당은 살고 싶다` (safe_resolved -> safe_resolved)
- `11671501` `null_to_resolved` `None` -> `판초우의의 마법사` (promotion_blocked -> safe_resolved)
- `11671512` `resolved_to_null` `삼시세끼, 심아식당` -> `None` (safe_resolved -> promotion_blocked)
- `11671514` `resolved_to_null` `악신에게 총애받는 자` -> `None` (safe_resolved -> promotion_blocked)

## Gate 해석

정적 projection 기준 raw regression `73`건이 남아 있다. 따라서 golden18 PASS는 과적합 가능성을 계속 배제하지 못하며, 회귀패널/잔여 큐 확대가 필요하다.
