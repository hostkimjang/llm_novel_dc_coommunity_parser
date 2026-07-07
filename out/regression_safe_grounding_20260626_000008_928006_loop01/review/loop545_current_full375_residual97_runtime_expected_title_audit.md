# loop545_current_full375_residual97_runtime_replay

## 요약

runtime expected-title 재현 게이트는 `NO-GO`다. 정확 safe_resolved 재현은 `19/49`이며, 이 결과는 runtime 재현성만 다루고 full_scan 승인을 의미하지 않는다.

## 런타임 상태

- run_id: `20260707_185644_707690`
- completed/flushed/pending/failed: `49/49/0/0`
- large_run_complete: `True`
- search health: include_search=`False`, light_mode=`True`, ok/failure=`16/0`
- VLM/OCR: ready=`None`, image_post_count=`32`

## 집계

- exact safe_resolved PASS: `19/49`
- runtime safe_resolved: `27/49`
- runtime promotion_blocked: `23/49`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 23, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 7, 'PASS_EXACT_SAFE_RESOLVED': 19}`
- search_status_counts: `{'None': 5, 'SEARCH_DEGRADED': 29, 'SEARCH_DEGRADED_RECOVERED': 14, 'ok': 1}`
- search degraded/unrecovered total: `0/0`

## 행별 결과

| post_id | audit | expected | actual | ledger | decision | search |
| --- | --- | --- | --- | --- | --- | --- |
| `11660273` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `마도서를 줍다 마법사가 되다` | `그리즐리 그랑` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11663535` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `퇴마록` | `퇴마록` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11663557` | `PASS_EXACT_SAFE_RESOLVED` | `퇴마록` | `퇴마록` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11665124` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `화산파(화산귀환)` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11668325` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `Fate/stay night` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11669913` | `PASS_EXACT_SAFE_RESOLVED` | `하룬` | `하룬` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11673102` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `갤질하는 천재 의사` | `댓글 보는 천재 의사` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11677915` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `전지적 독자 시점` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11677926` | `PASS_EXACT_SAFE_RESOLVED` | `재앙급 막내 공자의 회귀` | `재앙급 막내 공자의 회귀` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11681172` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `헌터갤러리의 국가권력급 기계공주` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11690841` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `블루 아카이브` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11694019` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `혼후 순결` | `이세계에서 사이비로 살아남기` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11697242` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `유희왕` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11697256` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `황제의 딸로 환생했다` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11702094` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `#더블오` | `댓글창이 내 흑막 연기를 너무 좋아한다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11708447` | `PASS_EXACT_SAFE_RESOLVED` | `잠룡회귀` | `잠룡회귀` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11710021` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `무한의 마법사` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11710049` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `[림월드]변방계에서 회귀자로 살아남기` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11714887` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `도굴왕 1 |` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11718099` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `빌어먹을 환생` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11718110` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `지구온라인에서 쌀먹합니다` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11718114` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `설정값 딸깍으로 판타지 시스템 정상화` | `` | `promotion_blocked` | `candidate_only` | `None` / unrecovered `None` |
| `11666741` | `PASS_EXACT_SAFE_RESOLVED` | `별을 품은 소드마스터` | `별을 품은 소드마스터` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11665121` | `PASS_EXACT_SAFE_RESOLVED` | `후회 안 하는 프로듀서` | `후회 안 하는 프로듀서` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11673077` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `판초우의의 마법사` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11694068` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `트와일라잇` | `트와일라잇 시리즈` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11663511` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `부캐 키우는 황태자님` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11666713` | `PASS_EXACT_SAFE_RESOLVED` | `21세기 무림세가` | `21세기 무림세가` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11668300` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `즉사기 들고 게임 속 으로` | `즉사기 인 줄 알았는데 지옥이었다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11669921` | `PASS_EXACT_SAFE_RESOLVED` | `악당은 살고 싶다` | `악당은 살고 싶다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11669926` | `PASS_EXACT_SAFE_RESOLVED` | `싸울아비 룬` | `싸울아비 룬` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11673080` | `PASS_EXACT_SAFE_RESOLVED` | `갤질하는 천재 의사` | `갤질하는 천재 의사` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11681159` | `PASS_EXACT_SAFE_RESOLVED` | `괴담에 휘말렸다` | `괴담에 휘말렸다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11682767` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `묵향` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11682775` | `PASS_EXACT_SAFE_RESOLVED` | `여자가 되어서라도 복수한다` | `여자가 되어서라도 복수한다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11689292` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `최악의 파트너` | `[원신] 최악의 파트너` | `safe_resolved` | `publish` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11692436` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `퍼펙트 메이지` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11692444` | `PASS_EXACT_SAFE_RESOLVED` | `엑스칼리버 뽑습니다` | `엑스칼리버 뽑습니다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11694065` | `PASS_EXACT_SAFE_RESOLVED` | `아카데미에서 살아남기` | `아카데미에서 살아남기` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11698859` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `귤부인 대롱대롱` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11700483` | `PASS_EXACT_SAFE_RESOLVED` | `니들 생각 다 들린다` | `니들 생각 다 들린다` | `safe_resolved` | `publish` | `ok` / unrecovered `None` |
| `11700500` | `PASS_EXACT_SAFE_RESOLVED` | `전지적 1인칭 시점` | `전지적 1인칭 시점` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11705230` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `월야환담` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED_RECOVERED` / unrecovered `None` |
| `11705251` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `월야환담 창월야` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11706831` | `PASS_EXACT_SAFE_RESOLVED` | `소설 속 빌런은 아카데미 차석으로 살아간다` | `소설 속 빌런은 아카데미 차석으로 살아간다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11706842` | `FAIL_SAFE_RESOLVED_TITLE_MISMATCH` | `삼국지 마대 가 되었다` | `대마법사였던것은 다시 대마법사를 꿈꾼다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11708470` | `PASS_EXACT_SAFE_RESOLVED` | `절대 꺾이지 않을거야!` | `절대 꺾이지 않을거야!` | `safe_resolved` | `publish` | `None` / unrecovered `None` |
| `11708478` | `PASS_EXACT_SAFE_RESOLVED` | `사연 있는 악역으로 착각 당한다` | `사연 있는 악역으로 착각 당한다` | `safe_resolved` | `publish` | `SEARCH_DEGRADED` / unrecovered `None` |
| `11710046` | `FAIL_RUNTIME_PROMOTION_BLOCKED` | `샷건 치는 병약 천사님` | `` | `promotion_blocked` | `candidate_only` | `SEARCH_DEGRADED` / unrecovered `None` |

## Gate

- projection expected-title: `NO-GO / 19 of 49`
- search evidence: `REVIEW / degraded 또는 timeout은 별도 검색 복구 P0에서 닫는다`
- full375 collateral: `NO-GO / 별도 전수 collateral GO 전까지 유지`
- completion gate: `NO-GO / full375 collateral GO + full_scan 경로 정의 필요`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
