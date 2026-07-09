# loop629_full375_after_loop628_collateral_compare

baseline full375와 runtime replay 결과를 비교한 collateral diff다. runtime 375 완주 여부를 포함하지만 semantic/full_scan approval은 별도 게이트에서 판단한다.

## 요약

- gate: `NO-GO`
- projection_static_collateral_gate: `NO-GO`
- runtime_collateral_gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- baseline_mode: `bootstrap_20260626`
- collateral_measure: `historical_raw_vs_20260626`
- shared posts: `375/375`
- changed rows: `206`
- raw collateral_regression_count: `137`
- adjusted_drift_count: `None`
- historical_raw_collateral_regression_count: `137`
- status_counts: `{'null_to_resolved': 26, 'same_title_url_changed': 58, 'resolved_to_null': 86, 'resolved_to_different_title': 36}`
- regression_status_counts: `{'null_to_resolved': 26, 'resolved_to_null': 79, 'resolved_to_different_title': 32}`
- runtime counts: `completed=375, pending=0, failed=0, runtime_complete=True`

## 차단 항목

- `projection_static_collateral_regression_nonzero`

## Regression 샘플

- `11657038` `null_to_resolved` `None` -> `레드 데스티니 [D]` (promotion_blocked -> safe_resolved)
- `11657044` `null_to_resolved` `None` -> `웨딩드레스` (promotion_blocked -> safe_resolved)
- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11660238` `null_to_resolved` `None` -> `무림마조` (promotion_blocked -> safe_resolved)
- `11660241` `resolved_to_null` `이세계 TRPG 게임마스터` -> `None` (safe_resolved -> promotion_blocked)
- `11660254` `resolved_to_null` `푸푸푸 랜드의 두가지 일상` -> `None` (safe_resolved -> promotion_blocked)
- `11660257` `resolved_to_different_title` `암흑가 보스요? 제가요?` -> `고수위.국제마약카르텔. 암흑가 의 보스 들 새 창 열림` (safe_resolved -> safe_resolved)
- `11660262` `resolved_to_different_title` `그렇게, 그 괴물과 두 번 결혼했다` -> `로판에 도파민을 풀었다` (safe_resolved -> safe_resolved)
- `11660268` `resolved_to_null` `을 위한 세계는 없다` -> `None` (safe_resolved -> promotion_blocked)
- `11660271` `resolved_to_null` `월야의 여인들` -> `None` (safe_resolved -> promotion_blocked)
- `11660273` `resolved_to_null` `마도서를 줍다 마법사가 되다` -> `None` (safe_resolved -> promotion_blocked)
- `11661856` `resolved_to_null` `너랑은 절! 대! 안 사Kill거니까!` -> `None` (safe_resolved -> promotion_blocked)
- `11663511` `resolved_to_null` `부캐 키우는 황태자님` -> `None` (safe_resolved -> promotion_blocked)
- `11663514` `resolved_to_different_title` `마탄 속의 제국` -> `올바른 슬라임 사용법` (safe_resolved -> safe_resolved)
- `11663521` `resolved_to_null` `초전자포] 시스터즈가 되었다` -> `None` (safe_resolved -> promotion_blocked)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11663557` `resolved_to_null` `퇴마록` -> `None` (safe_resolved -> promotion_blocked)
- `11665099` `resolved_to_different_title` `옥천마 출정` -> `옥탑방의 천재 마물 소환사` (safe_resolved -> safe_resolved)
- `11665110` `resolved_to_different_title` `낭만적인 초능력을 위하여` -> `사이키델리아` (safe_resolved -> safe_resolved)
- `11665121` `resolved_to_null` `후회 안 하는 프로듀서` -> `None` (safe_resolved -> promotion_blocked)

## Gate 해석

raw regression `137`건이 남아 있다. 따라서 golden18 PASS는 과적합 가능성을 계속 배제하지 못하며, 회귀패널/잔여 큐 확대가 필요하다.
