# loop611_full375_after_loop610_publication_sync_projection_collateral_compare

projection 결과를 baseline full375와 비교한 정적 collateral diff다. runtime 375 완주가 아니므로 regression 수가 줄어도 full_scan approval은 열리지 않는다.

## 요약

- gate: `NO-GO`
- projection_static_collateral_gate: `NO-GO`
- runtime_collateral_gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- shared posts: `375/375`
- changed rows: `196`
- raw collateral_regression_count: `139`
- status_counts: `{'null_to_resolved': 24, 'same_title_url_changed': 45, 'resolved_to_null': 89, 'resolved_to_different_title': 38}`
- regression_status_counts: `{'null_to_resolved': 24, 'resolved_to_null': 82, 'resolved_to_different_title': 33}`
- runtime counts: `missing`

## 차단 항목

- `projection_static_collateral_regression_nonzero`
- `collateral_runtime_counts_missing`

## Regression 샘플

- `11657045` `null_to_resolved` `None` -> `금태양과 음침녀` (promotion_blocked -> safe_resolved)
- `11657047` `null_to_resolved` `None` -> `베지테리언 블러드` (promotion_blocked -> safe_resolved)
- `11658626` `resolved_to_null` `아카데미 선비의 생활일지` -> `None` (safe_resolved -> promotion_blocked)
- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11660241` `resolved_to_null` `이세계 TRPG 게임마스터` -> `None` (safe_resolved -> promotion_blocked)
- `11660254` `resolved_to_different_title` `푸푸푸 랜드의 두가지 일상` -> `양판 애니 속으로 들어와 버렸다` (safe_resolved -> safe_resolved)
- `11660257` `resolved_to_different_title` `암흑가 보스요? 제가요?` -> `그룹을 위해 당연한 일을 했을 뿐인데. 정체불명의 암흑가 보스 니 검은 자본이니. 다들 호들갑이 심하다니까` (safe_resolved -> safe_resolved)
- `11660262` `resolved_to_different_title` `그렇게, 그 괴물과 두 번 결혼했다` -> `로판에 도파민을 풀었다` (safe_resolved -> safe_resolved)
- `11660264` `resolved_to_null` `빚을 져서라도 세상은 구해야 할 거 아니야` -> `None` (safe_resolved -> promotion_blocked)
- `11660268` `resolved_to_null` `을 위한 세계는 없다` -> `None` (safe_resolved -> promotion_blocked)
- `11660271` `resolved_to_null` `월야의 여인들` -> `None` (safe_resolved -> promotion_blocked)
- `11660273` `resolved_to_different_title` `마도서를 줍다 마법사가 되다` -> `그리즐리 그랑` (safe_resolved -> safe_resolved)
- `11661856` `resolved_to_null` `너랑은 절! 대! 안 사Kill거니까!` -> `None` (safe_resolved -> promotion_blocked)
- `11661863` `resolved_to_null` `저주받은 영애가 되었습니다` -> `None` (safe_resolved -> promotion_blocked)
- `11661881` `resolved_to_null` `여신이 나만 애호함` -> `None` (safe_resolved -> promotion_blocked)
- `11663511` `resolved_to_null` `부캐 키우는 황태자님` -> `None` (safe_resolved -> promotion_blocked)
- `11663514` `resolved_to_different_title` `마탄 속의 제국` -> `올바른 슬라임 사용법` (safe_resolved -> safe_resolved)
- `11663521` `resolved_to_null` `초전자포] 시스터즈가 되었다` -> `None` (safe_resolved -> promotion_blocked)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11663557` `resolved_to_different_title` `퇴마록` -> `퇴마록 1` (safe_resolved -> safe_resolved)

## Gate 해석

raw regression `139`건이 남아 있다. 따라서 golden18 PASS는 과적합 가능성을 계속 배제하지 못하며, 회귀패널/잔여 큐 확대가 필요하다.
