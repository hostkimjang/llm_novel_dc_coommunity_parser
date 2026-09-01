# 2026-07-16 라이브 런 동결 전수 판정 보고서

## 결론

동결 시점의 처리행 `2,712`건은 한 건도 빠뜨리지 않고 행별 의미 판정과 대시보드 조치를 확정했다. 이는 전체 입력 `104,502`건의 최종 승인이 아니라, 실행 중인 런에서 고정한 prefix `2,590`건과 후속 tail `122`건의 전수 결과다. 이후에도 라이브 결과는 증가하므로, 새 행은 다음 freeze packet에서 같은 절차로 전수 검토해야 한다.

| 전수성 게이트 | 결과 | 근거 |
| --- | ---: | --- |
| prefix 의미 판정 | `2,590 / 2,590` | 26개 batch 모두 `GO`, unique·missing·extra 오류 `0` |
| prefix 고위험 교차 검토 | `221 / 221` | 일치 `157`, 의견 차이 `64` |
| prefix 제3 중재 | `64 / 64` | 의견 차이 전부 중재 완료 |
| 후속 tail 의미 판정 | `122 / 122` | 2개 batch 모두 `GO`, unique·missing·extra 오류 `0` |
| 최종 정본 | `2,712 / 2,712` | 고유 `post_id` 2,712개, 중복·누락 `0` |
| 조치 큐 대조 | `1,131`건 | `NOT_APPLICABLE` 외 모든 조치 행이 존재 |

## 행별 최종 판정

| 판정 | 건수 |
| --- | ---: |
| `NOISE_CORRECT` | 891 |
| `CONTEXT_ONLY_CORRECT` | 719 |
| `FN_TITLE_MISSING` | 339 |
| `EVIDENCE_INSUFFICIENT` | 302 |
| `PASS` | 230 |
| `MULTIWORK_HOLD_CORRECT` | 91 |
| `FP_NONNOVEL` | 72 |
| `WRONG_WORK` | 36 |
| `EVIDENCE_CONFLICT` | 25 |
| `DASHBOARD_TITLE_MISMATCH` | 7 |

따라서 “소설이 아닌데 소설로 채택”된 확정 비소설은 `72`건이며, 다른 작품명으로 잘못 연결된 행은 `36`건이다. 반대로 작품명 누락은 `339`건이다. 근거 충돌·부족·다중 작품으로 단일 제목을 확정하면 안 되는 행은 `25 + 302 + 91 = 418`건이다.

## 대시보드 운영 조치

| 조치 | 건수 | 운영 규칙 |
| --- | ---: | --- |
| `REMOVE` | 80 | 비소설 또는 잘못된 작품 표기를 대시보드에서 제거 |
| `CORRECT` | 369 | 행별 `recommended_title`로 작품명을 정정 |
| `HOLD` | 452 | 근거 보강 전 자동 게시·제목 확정 금지 |
| `KEEP` | 230 | 현재 작품명 유지 |
| `NOT_APPLICABLE` | 1,581 | 작품 표기 조치 대상 아님 |

조치 큐 `1,131`건은 `REMOVE`·`CORRECT`·`HOLD`·`KEEP`의 전 행을 담는다. 집계만 제시한 것이 아니라 각 행의 `post_id`, 최종 판정, 권장 제목, 근거, 우선순위를 보존했다.

## 전수 산출물

- 최종 행별 정본: [`final_2712_row_adjudication_ledger.jsonl`](../../out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl)
- 대시보드 전체 조치 큐: [`dashboard_action_queue.jsonl`](../../out/live_combined_row_review_20260715_143806_848671_2712_20260716/dashboard_action_queue.jsonl)
- 최종 요약 및 재조정 결과: [`final_2712_row_summary.json`](../../out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_summary.json)
- prefix 고위험 교차 검토: [`high_risk_cross_review_summary.json`](../../out/live_full_row_review_20260715_143806_848671_20260716/high_risk_cross_review_summary.json)
- prefix 의견 차이 중재 전수성: [`arbitration_coverage.json`](../../out/live_full_row_review_20260715_143806_848671_20260716/arbitration_coverage.json)
- Data Analytics reader-facing artifact: [`LIVE_RUN_FULL_ROW_DATA_ANALYTICS_ARTIFACT_20260716.json`](LIVE_RUN_FULL_ROW_DATA_ANALYTICS_ARTIFACT_20260716.json)

## 검토 방법과 독립성

prefix는 26개 독립 batch review, 고위험 221건의 별도 재검토, 64건의 제3 중재 순으로 닫았다. 후속 tail 122건도 별도 2개 batch로 모든 행을 재판정했다. 약어·갤러리 표면만으로 비소설을 단정하지 않았고, 작품 약어 가능성은 explicit alias relation, 특정 작품 대상, 공식·커뮤니티 근거, 경쟁 본문 작품 근거로 재확인했다.

GPT Pro에는 새 task `full-live-row-adjudication-20260716`을 한 번 제출했으나 bridge가 `inflight`/recovery 상태여 이번 전수 판정에 쓸 수 있는 신규 응답은 받지 못했다. 중복 요청은 만들지 않았고, 행별 최종 정본은 로컬 독립 reviewers와 중재 결과만으로 완결했다.

Data Analytics artifact는 데이터셋·SQL CTE 출처를 포함해 검증하고, 수정 반영본을 렌더링했다. 외부 공유는 요청되지 않아 수행하지 않았다.

## 라이브 런 상태와 승인 경계

보고서 작성 시점의 읽기 전용 manifest/result 확인값은 `completed_count=2,838`, `flushed_count/result=2,823`, `failed_count=0`, `requested/effective parallel=16/16`, dashboard enabled다. 그러므로 이 보고서의 freeze 정본 `2,712` 뒤에 최소 `111`개의 flushed 결과와 아직 flush 전 checkpoint 행이 존재한다. 이 후속 행은 본 보고서의 검토 범위가 아니다.

`FROZEN_2712_ROW_REVIEW=GO`다. 그러나 런은 아직 `large_run_complete=false`이며 search evidence degraded 관측과 후속 tail 미검토가 남아 있으므로 `ACTIVE_FULL_RUN_SEMANTIC_APPROVAL=NO-GO / REVIEW-LOCKED`를 유지한다. 또한 전체 health script 재실행은 현재 worktree의 `src/llm_batch/experts/arbiter.py` f-string 구문 오류 때문에 완료되지 않았고, 위 라이브 수치는 manifest/result를 직접 읽은 값이다. 실행 중인 런 자체를 중지·수정하지 않았다.
