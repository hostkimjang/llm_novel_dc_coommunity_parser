# loop623_loop620_current_head_projection_collateral_compare

projection 결과를 baseline full375와 비교한 정적 collateral diff다. runtime 375 완주가 아니므로 regression 수가 줄어도 full_scan approval은 열리지 않는다.

## 요약

- gate: `NO-GO`
- projection_static_collateral_gate: `NO-GO`
- runtime_collateral_gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- shared posts: `375/375`
- changed rows: `212`
- raw collateral_regression_count: `141`
- status_counts: `{'same_title_url_changed': 60, 'null_to_resolved': 26, 'resolved_to_null': 91, 'resolved_to_different_title': 35}`
- regression_status_counts: `{'null_to_resolved': 26, 'resolved_to_null': 85, 'resolved_to_different_title': 30}`
- runtime counts: `missing`

## 차단 항목

- `projection_static_collateral_regression_nonzero`
- `collateral_runtime_counts_missing`

## Regression 샘플

- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11660229` `resolved_to_null` `로판 속 미친 북부대공이 되었다` -> `None` (safe_resolved -> promotion_blocked)
- `11660254` `resolved_to_null` `푸푸푸 랜드의 두가지 일상` -> `None` (safe_resolved -> promotion_blocked)
- `11660257` `resolved_to_null` `암흑가 보스요? 제가요?` -> `None` (safe_resolved -> promotion_blocked)
- `11660258` `resolved_to_null` `괴담 호텔 탈출기` -> `None` (safe_resolved -> promotion_blocked)
- `11660262` `resolved_to_null` `그렇게, 그 괴물과 두 번 결혼했다` -> `None` (safe_resolved -> promotion_blocked)
- `11660264` `resolved_to_null` `빚을 져서라도 세상은 구해야 할 거 아니야` -> `None` (safe_resolved -> promotion_blocked)
- `11660268` `resolved_to_null` `을 위한 세계는 없다` -> `None` (safe_resolved -> promotion_blocked)
- `11660271` `resolved_to_null` `월야의 여인들` -> `None` (safe_resolved -> promotion_blocked)
- `11661856` `resolved_to_different_title` `너랑은 절! 대! 안 사Kill거니까!` -> `다녀왔어` (safe_resolved -> safe_resolved)
- `11661857` `resolved_to_different_title` `아카데미 개망나니 교수가 되었다` -> `두바이의 쫀득한 여초딩 재벌 9세` (safe_resolved -> safe_resolved)
- `11661863` `resolved_to_null` `저주받은 영애가 되었습니다` -> `None` (safe_resolved -> promotion_blocked)
- `11663514` `resolved_to_different_title` `마탄 속의 제국` -> `올바른 슬라임 사용법` (safe_resolved -> safe_resolved)
- `11663521` `resolved_to_different_title` `초전자포] 시스터즈가 되었다` -> `카미조 토우마가 IS세계관에 떨어지는 이야기. 꽤 예전에 썼던 글인데 저쪽에선 읽기 힘들어서 여기에 재업합니다` (safe_resolved -> safe_resolved)
- `11663535` `resolved_to_null` `퇴마록` -> `None` (safe_resolved -> promotion_blocked)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11663557` `resolved_to_different_title` `퇴마록` -> `퇴마록 1` (safe_resolved -> safe_resolved)
- `11665099` `resolved_to_different_title` `옥천마 출정` -> `옥탑방의 천재 마물 소환사` (safe_resolved -> safe_resolved)
- `11665110` `resolved_to_different_title` `낭만적인 초능력을 위하여` -> `사이키델리아` (safe_resolved -> safe_resolved)
- `11665121` `resolved_to_null` `후회 안 하는 프로듀서` -> `None` (safe_resolved -> promotion_blocked)

## Gate 해석

raw regression `141`건이 남아 있다. 따라서 golden18 PASS는 과적합 가능성을 계속 배제하지 못하며, 회귀패널/잔여 큐 확대가 필요하다.
