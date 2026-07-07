# loop523_direct_title_surface_expected_audit

## 요약

runtime expected-title 재현 게이트는 `NO-GO`다. 정확 safe_resolved 재현은 `19/57`이며, 이 결과는 runtime 재현성만 다루고 full_scan 승인을 의미하지 않는다.

## 런타임 상태

- run_id: `20260707_095930_691121`
- completed/flushed/pending/failed: `57/57/0/0`
- large_run_complete: `True`
- search health: include_search=`True`, light_mode=`False`, ok/failure=`16/0`
- VLM/OCR: ready=`None`, image_post_count=`37`

## 집계

- exact safe_resolved PASS: `19/57`
- runtime safe_resolved: `30/57`
- runtime promotion_blocked: `27/57`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 27, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 11, 'PASS_EXACT_SAFE_RESOLVED': 19}`
- search_status_counts: `{'None': 8, 'SEARCH_DEGRADED': 29, 'SEARCH_DEGRADED_RECOVERED': 16, 'ok': 4}`
- search degraded/unrecovered total: `0/0`

## 행별 결과

| post_id | audit | expected | actual | ledger | decision | search |
| --- | --- | --- | --- | --- | --- | --- |
| `11660271` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `월야의 여인들` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11660273` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `마도서를 줍다 마법사가 되다` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11663535` | `PASS_EXACT_SAFE_RESOLVED` | `퇴마록` | `퇴마록` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11663557` | `PASS_EXACT_SAFE_RESOLVED` | `퇴마록` | `퇴마록` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11665124` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `화산파(화산귀환)` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11668325` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `Fate/stay night` | `마파신부다만?(블아xFATE)` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11669913` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `하룬` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11673102` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `갤질하는 천재 의사` | `댓글 보는 천재 의사` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11677915` | `PASS_EXACT_SAFE_RESOLVED` | `전지적 독자 시점` | `전지적 독자 시점` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11677926` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `재앙급 막내 공자의 회귀` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11681172` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `헌터갤러리의 국가권력급 기계공주` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11690841` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `블루 아카이브` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11694019` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `혼후 순결` | `이세계에서 사이비로 살아남기` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11697242` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `유희왕` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11697256` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `황제의 딸로 환생했다` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11702094` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `#더블오` | `댓글창이 내 흑막 연기를 너무 좋아한다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11706871` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `파우스트` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11708447` | `PASS_EXACT_SAFE_RESOLVED` | `잠룡회귀` | `잠룡회귀` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11710021` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `무한의 마법사` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11710049` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `[림월드]변방계에서 회귀자로 살아남기` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11714887` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `도굴왕 1 |` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11718099` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `빌어먹을 환생` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11718110` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `지구온라인에서 쌀먹합니다` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11718114` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `설정값 딸깍으로 판타지 시스템 정상화` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11666741` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `별을 품은 소드마스터` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11665121` | `PASS_EXACT_SAFE_RESOLVED` | `후회 안 하는 프로듀서` | `후회 안 하는 프로듀서` | `safe_resolved` | `publish` | `ok` / unrecovered `None` |
| `11673077` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `판초우의의 마법사` | `즉사기 들고 무림에 떨어지다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11694068` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `트와일라잇` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11660277` | `PASS_EXACT_SAFE_RESOLVED` | `아카메디 아카데미` | `아카메디 아카데미` | `safe_resolved` | `publish` | `ok` / unrecovered `None` |
| `11663511` | `PASS_EXACT_SAFE_RESOLVED` | `부캐 키우는 황태자님` | `부캐 키우는 황태자님` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11666713` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `21세기 무림세가` | `21세기 현대무림 레거시` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11668300` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `즉사기 들고 게임 속으로` | `` | `promotion_blocked` | `candidate_only` | `ok` / unrecovered `None` |
| `11669921` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `악당은 살고 싶다` | `악당도 살고 싶다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11669926` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `싸울아비 룬` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11669933` | `PASS_EXACT_SAFE_RESOLVED` | `회귀수선전` | `회귀수선전` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11673080` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `갤질하는 천재 의사` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11677924` | `PASS_EXACT_SAFE_RESOLVED` | `고결에 오만이 깃들 때` | `고결에 오만이 깃들 때` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11679547` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `도굴왕` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11681159` | `PASS_EXACT_SAFE_RESOLVED` | `괴담에 휘말렸다` | `괴담에 휘말렸다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11682767` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `묵향` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11682775` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `여자가 되어서라도 복수한다` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11689292` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `최악의 파트너` | `원신` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11692436` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `퍼펙트 메이지` | `죽었다 깨어도 수선` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11692444` | `PASS_EXACT_SAFE_RESOLVED` | `엑스칼리버 뽑습니다` | `엑스칼리버 뽑습니다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11694063` | `PASS_EXACT_SAFE_RESOLVED` | `빙의한 신의 아이, 엘리시아` | `빙의한 신의 아이, 엘리시아` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11694065` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `아카데미에서 살아남기` | `[아카살] 아무 관계도 아니라고!` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11698859` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `귤부인 대롱대롱` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11700483` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `니들 생각 다 들린다` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11700500` | `PASS_EXACT_SAFE_RESOLVED` | `전지적 1인칭 시점` | `전지적 1인칭 시점` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11705230` | `PASS_EXACT_SAFE_RESOLVED` | `월야환담` | `월야환담` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11705251` | `PASS_EXACT_SAFE_RESOLVED` | `월야환담 창월야` | `월야환담 창월야` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11706831` | `PASS_EXACT_SAFE_RESOLVED` | `소설 속 빌런은 아카데미 차석으로 살아간다` | `소설 속 빌런은 아카데미 차석으로 살아간다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11706842` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `삼국지 마대가 되었다` | `대마법사였던것은 다시 대마법사를 꿈꾼다` | `safe_resolved` | `publish` | `ok` / unrecovered `None` |
| `11708470` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `절대 꺾이지 않을거야!` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11708478` | `PASS_EXACT_SAFE_RESOLVED` | `사연 있는 악역으로 착각 당한다` | `사연 있는 악역으로 착각 당한다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11710046` | `PASS_EXACT_SAFE_RESOLVED` | `샷건 치는 병약 천사님` | `샷건 치는 병약 천사님` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11718098` | `PASS_EXACT_SAFE_RESOLVED` | `마법 좋아좋아좋아` | `마법 좋아좋아좋아` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |

## Gate

- projection expected-title: `NO-GO / 19 of 57`
- search evidence: `REVIEW / degraded 또는 timeout은 별도 검색 복구 P0에서 닫는다`
- full375 collateral: `NO-GO / 별도 전수 collateral GO 전까지 유지`
- completion gate: `NO-GO / full375 collateral GO + full_scan 경로 정의 필요`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
