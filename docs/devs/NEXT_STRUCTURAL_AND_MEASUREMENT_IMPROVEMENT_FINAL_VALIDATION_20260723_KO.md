# 구조·계측 개선 v7 최종 검증

작성일: 2026-07-23

범위: 동결 32행 `BEFORE/OFF` 대 `AFTER/AUDIT_ONLY` 각 3회, 동결 2,712행 deterministic replay

운영 경계: `public_apply=false`, `full_scan_approval=false`, commit/push/deploy/central slang DB promotion 없음

## 한눈에 보는 결론

| 게이트 | 판정 | 근거 |
| --- | --- | --- |
| runtime completion | `GO` | 선택한 6개 arm 모두 `32/32` completed·flushed, failed `0` |
| measurement completeness | `GO` | 독립 원장 재판독 `192/192` exact linked, 6/6 arm 완결 |
| publication noninterference | `GO` | 입력·scope 결속 일치, authoritative WAL hash·32 event 불변, `public_apply=false` |
| 2,712 publish-contract replay | `GO` | `2,712/2,712`, 누락·비추정·projection/reason/fingerprint mismatch·정상→비정상 회귀 모두 `0` |
| semantic quality | `NO-GO` | 다수결 품질 `18/32→18/32`, 신규 체계적 cross-arm 회귀는 없지만 persistent unsafe publish와 wrong-work 미해결 |
| search health | `NO-GO` | degraded unrecovered `182→178`; green 아님 |
| review router | `NO-GO` | high-risk recall `44/66(66.67%)→43/66(65.15%)` |
| P2 early route / production | `NO-GO` | 의미·검색·router 게이트가 green이 아니므로 초저위험 188 canary와 전체 운영 전환 미실행 |
| full scan approval | `false` | targeted 32행과 deterministic replay만으로 전체 의미 품질을 승인하지 않음 |

결론적으로 **계측 구조와 공개 결과 비간섭은 검증을 마쳤지만, 의미 정확도 개선은 아직 승인할 수준이 아니다.** 기존 정상 정답이 반복적으로 무너지는 cross-arm 패턴은 v6의 2건에서 v7의 0건으로 줄었고, 정상 PASS·FP 방어도 유지됐다. 다만 correct-title 순회복은 없었고, `WRONG_WORK` 3/5와 evidence-conflict unsafe publish 1건은 계속 남았다.

## 왜 중간에 실패처럼 보였는가

v7 원본 6개 arm은 runtime `6/6`으로 끝났지만 repeat 3 AFTER의 1행이 provider usage를 회수하지 못했다. 의미 결과는 안전한 `HOLD`였고 WAL도 바뀌지 않았지만, actual usage가 `ESTIMATED`이면 writer가 publication link를 만들지 않는 fail-close 계약 때문에 원본 측정은 `191/192`, `5/6 GO`였다.

| 시도 | run ID | 결과 | 처리 |
| --- | --- | --- | --- |
| v7 원본 repeat 3 AFTER | `20260723_010338_574277` | `11718107`의 VERIFIER hard-cap 뒤 usage drain 60초 timeout, `191/192` | 원본 보존, 측정 `NO-GO`; usage 추정·세탁 금지 |
| replacement retry 1 | `20260723_013036_430357` | `11718122` 최초 VLM physical attempt 300초 `ReadTimeout`; retry 의미 성공이나 실패 attempt usage/model 부재, `31/32` | 원본 보존, 측정 `NO-GO`; 안전한 재구성 불가 |
| replacement retry 2 | `20260723_015151_275124` | `32/32` runtime·measurement·noninterference `GO` | 사전 고정·semantic-blind 정책을 만족한 첫 terminal replacement로 선택 |

선택 정책은 결과를 본 뒤 유리한 의미 판정을 고르는 규칙이 아니다. retry 2 실행 전에 저장한 `retry_policy.json`을 사용했고 `semantic_result_blind=true`, 원본 `NO-GO`, replacement `GO`, 실행 선후관계, 32/32 scope를 분석기가 재검증했다. 정책 SHA-256은 `78f5eb2d919912c24760b6d0c6501f703004932d41105bf9bffbb950bcdab580`이다. 원본과 retry 1은 삭제하거나 덮어쓰지 않았다.

## v6에서 v7로 개선된 점

| 지표 | v6 | v7 qualified | 판정 |
| --- | ---: | ---: | --- |
| runtime arm GO | 6/6 | 6/6 | 유지 |
| measurement arm GO | 4/6 | 6/6 | 개선 |
| exact linked observations | 190/192 | 192/192 | 개선 |
| majority compliant, BEFORE→AFTER | 19→17 | 18→18 | v6 악화 패턴 제거, 순개선은 없음 |
| systematic cross-arm regression | 2 | 0 | 개선 |
| introduced unsafe publish | 2 | 0 | 개선 |
| introduced wrong-title publish | 2 | 0 | 개선 |
| PASS majority retention | 1/2→1/2 | 2/2→2/2 | 정상군 안정화 |
| correct-title majority | 2→0 | 1→1 | v6의 붕괴는 제거, 회복 확대는 실패 |
| wrong-work unrecovered | 3/5→3/5 | 3/5→3/5 | 미개선 |

v7은 동일 입력·동일 모델·동일 publication scope·각 3회 조건의 exact pairing이다. 다만 AFTER는 recovery sidecar `AUDIT_ONLY`이며 실제 public apply가 없으므로, 관측 차이를 production patch의 인과 효과로 과장하지 않는다.

## 문제 유형별 BEFORE/AFTER

| cohort | BEFORE | AFTER | 해석 |
| --- | --- | --- | --- |
| 전체 adjudicated compliance | majority `18/32`, exact `54/96` | majority `18/32`, exact `54/96` | 순품질 변화 없음 |
| unsafe publish | any-run 3건, exact 4회, majority 1건 | any-run 1건, exact 2회, majority 1건 | 일회성 2건 해소, persistent 1건 |
| wrong-title publish | any-run 2건, exact 2회 | 0건 | 위험 방향 개선 |
| correct-title recovery | any-run 2/11, majority 1/11 | any-run 1/11, majority 1/11 | 확장 실패; 한 행의 일회성 recovery 소실 |
| HOLD integrity | majority 4/5, exact 13/15 | majority 4/5, exact 13/15 | 유지, conflict 1건 실패 지속 |
| WRONG_WORK | unrecovered 3/5 | unrecovered 3/5 | 개선 없음 |
| PASS | majority 2/2, exact 5/6 | majority 2/2, exact 5/6 | 정상군 유지 |
| FP_NONNOVEL | 0/3 | 0/3 | 새 false positive 없음 |

### 개선된 예

- `11718051`: BEFORE 1/3에서 잘못된 `양치기 마법사`를 공개했으나 AFTER는 3/3 `HOLD`였다. unsafe/wrong-title은 해소됐지만 정답 작품 복구는 여전히 실패했다.
- `11716480`: BEFORE 1/3 오타 제목 공개가 AFTER 3/3 `HOLD`로 닫혔다. 잘못 공개하는 위험은 줄었으나 correct-title 회복은 없다.
- `11718097`: 정답 `망겜의 힐러`가 BEFORE 2/3에서 AFTER 3/3으로 안정됐다.

### 개선이 미미하거나 실패한 예

- `11718117`: source 정답 `아카데미의 피해자`가 BEFORE 1/3에서만 복구됐고 AFTER는 0/3이었다. 두 arm 모두 majority noncompliant라 systematic cross-arm regression으로 집계되지는 않지만 FN recovery 관점의 악화 신호다.
- `11718099`: `EVIDENCE_CONFLICT`인데도 `빌어먹을 환생` unsafe publish가 BEFORE와 AFTER 모두 2/3으로 지속됐다. 가장 분명한 미해결 fail-close 문제다.
- `11718051`, `11716500`, `11714903`: `WRONG_WORK` 3/5가 양 arm에서 모두 미복구다.

## 정상 정답 보존과 변동성

- PASS 2행은 양 arm 모두 majority `2/2`, exact `5/6`을 유지했다.
- FP_NONNOVEL 3행은 양 arm 모두 false positive `0`이었다.
- cross-arm systematic improvement와 regression은 각각 `0`이다.
- normal→abnormal 전이가 특정 AFTER 행에 반복·집중되는 패턴은 없었다.
- AFTER에서 반복별 결과가 달라진 행은 2건, BEFORE는 6건이었다. 이 수치는 더 안정적일 가능성을 시사하지만 표본 32행이므로 일반화하지 않는다.
- 한 번 흔들린 결과는 즉시 코드 rollback 사유로 취급하지 않았고, 3회 합의·source-relative 판정·cohort 집중도를 함께 봤다.

## 검색·review router·sidecar

| 지표 | BEFORE | AFTER | 판정 |
| --- | ---: | ---: | --- |
| high-risk review recall | 44/66, 66.67% | 43/66, 65.15% | `NO-GO` |
| normal-control false-review rate | 7/30, 23.33% | 6/30, 20.00% | 소폭 개선이나 recall 하락 |
| search calls | 520 | 495 | -25, -4.81% |
| unrecovered degraded search | 182 | 178 | 여전히 green 아님 |
| recovery-plan receipt | 96/96 | 96/96 | coverage `GO` |
| recovery-plan network/search/public apply | 0/0/0 | 0/0/0 | 비간섭 `GO` |

review router는 false-review가 조금 줄었지만 high-risk recall도 내려갔다. 평균 하나로 승격하지 않고 recall을 hard guardrail로 유지한다. recovery plan은 192개 receipt를 모두 남겼지만 실행 권한이 없는 audit-only 계획이므로 semantic recovery 성공으로 세지 않는다.

## 호출·토큰·시간

immutable decision-call ledger를 arm별 3개 모두 독립 재판독했다. 아래는 추정치가 아닌 provider-reported actual 합계다.

| 지표 | BEFORE | AFTER | 변화 |
| --- | ---: | ---: | ---: |
| expert calls | 883 | 867 | -16, -1.81% |
| text calls | 808 | 792 | -16 |
| VLM calls | 75 | 75 | 0 |
| retry count | 0 | 0 | 0 |
| prompt tokens | 10,951,754 | 10,715,092 | -236,662, -2.16% |
| completion tokens | 565,056 | 621,973 | +56,917, +10.07% |
| total tokens | 11,516,810 | 11,337,065 | -179,745, -1.56% |
| physical-call wall 합 | 32,867,375 ms | 35,823,371 ms | +2,955,996 ms, +8.99% |
| run wall 합 | 3,210.4 s | 3,949.8 s | +739.4 s, +23.03% |

AFTER run wall에는 retry 2의 긴 꼬리 `1,917.5 s`가 포함된다. 3회 소표본과 transient transport tail이 섞였으므로 이를 일반적인 속도 악화율로 확정하지 않는다. total token은 줄었지만 completion token과 wall은 늘었으므로 비용/지연 게이트도 자동 green으로 보지 않는다.

## 2,712행 deterministic replay

최종 코드로 persisted result를 다시 계산했으며 네트워크와 `expert_main.py`는 사용하지 않았다.

| 항목 | 결과 |
| --- | ---: |
| ledger rows / unique post_id | 2,712 / 2,712 |
| estimable / not estimable | 2,712 / 0 |
| raw missing / raw extra | 0 / 395 |
| public projection mismatch | 0 |
| reason-code mismatch | 0 |
| fingerprint mismatch | 0 |
| internally invalid | 0 |
| normal→abnormal contract regression | 0 |

이 replay는 공개 계약 직렬화와 불변성을 증명한다. LLM을 다시 호출하지 않았으므로 2,712행 의미 정확도 개선을 증명하는 근거는 아니다.

## 구현·검증 경계

- `src/llm_batch/llm/client.py`: hard-cap 및 repeat-stop 뒤 의미 출력 동결, bounded provider-usage drain, kill switch, 실패 시 추정치를 actual로 승격하지 않는 fail-close.
- `src/llm_batch/experts/synthesizer.py`: 기본 2,048 token cap과 trusted terminal quarantine.
- `src/llm_batch/agentic_pipeline.py`: verifier의 `slang_insight`·`grounding_check`를 dict-only로 소비하는 shape guard.
- `tools/analyze_recovery_sidecar_grouped_ab.py`: immutable ledger 독립 재판독, precommitted semantic-blind replacement 검증, actual calls/tokens 집계.
- `tools/build_next_structural_measurement_final_report.py`: v6/v7/replay 정본으로 portable Data Analytics artifact를 재생성.
- hardcoded `post_id`·작품명·alias production 예외는 추가하지 않았다.
- 보호 run `20260715_143806_848671`과 shard `3333~3348`은 중지·수정·재사용하지 않았다.

최종 deterministic 회귀 묶음은 focused client/Synth/shape `31/31`, 인접 publication/measurement/router/recovery `263/263`, analyzer `12/12`, 관련 Python compile과 `git diff --check`로 다시 확인한다. 이 문서의 최종 완료 표시는 해당 감사 완료 후 체크리스트에 기록한다.

## 최종 산출물과 재현 근거

- reader-facing 보고서: [`NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_REPORT_20260723_KO.html`](NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_REPORT_20260723_KO.html)
- portable artifact: [`NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_ARTIFACT_20260723.json`](NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_ARTIFACT_20260723.json)
- v7 qualified 분석: `out/regression_safe_2712_next_improvements_20260722/grouped_ab_v7_early_stop_drain_20260722_231437/grouped_analysis_v7_qualified`
- independent readback: 위 분석 디렉터리의 `sidecar_grouped/report.json`
- exact paired transitions: 위 분석 디렉터리의 `sidecar_grouped/transitions.jsonl`
- 3회 합의: 위 분석 디렉터리의 `repeat_consensus_summary.json`, `repeat_consensus_posts.jsonl`
- 2,712 replay: `out/regression_safe_2712_next_improvements_20260722/grouped_ab_v7_early_stop_drain_20260722_231437/frozen2712_publish_contract_replay_final_qualified_20260723/publish_contract_replay_summary.json`
- replacement policy: `out/regression_safe_2712_next_improvements_20260722/grouped_ab_v7_early_stop_drain_20260722_231437/replacement_attempts/repeat_3_after_measurement_retry_2/retry_policy.json`

Data Analytics artifact는 canonical renderer validation/package를 통과했다. 이 환경에는 Chromium headless-shell이 없어 verification은 `structural_only`이며 source interaction과 viewport browser QA는 수행하지 못했다. 이는 데이터·구조 검증 성공과 별개의 렌더링 QA 한계다.

## 다음 개선 우선순위

1. `11718099` 유형의 primary/evidence-conflict finalizer를 fail-close하는 targeted patch와 dedicated bundle을 먼저 닫는다.
2. wrong-work 3건은 canonical-title 복구보다 관계 분류(`primary/previous/mentioned/comparison`)와 competing-work evidence를 먼저 강화한다.
3. direct OCR/official detail recovery는 conflict 없음·single-work·canonical binding을 모두 만족할 때만 review candidate로 활성화한다.
4. router는 high-risk recall을 먼저 회복하고 false-review rate를 보조 지표로 둔다.
5. search health와 semantic gate가 green이 되기 전에는 P2 초저위험 188행 canary와 production activation을 열지 않는다.

현재 최종 판정은 `measurement=GO`, `semantic_quality=NO-GO`, `search_health=NO-GO`, `review_router=NO-GO`, `full_scan_approval=false`다.
