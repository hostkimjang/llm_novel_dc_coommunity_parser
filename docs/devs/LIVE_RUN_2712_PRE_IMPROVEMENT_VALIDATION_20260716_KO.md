# 2,712건 구현 전 개선 분석 검증 보고서

## Overall Assessment: Share with caveats

동결 2,712건에서 도출한 개선 우선순위와 관측 수치는 공유·의사결정에 사용할 수 있다. 다만 제안된 AFTER 동작은 아직 구현·fresh run·paired BEFORE/AFTER로 측정되지 않았으므로 실제 정확도·비용·지연 개선으로 표현하면 안 된다.

## Methodology Review

- 질문은 “2,712건 전수 판정에서 어떤 개선을 우선하고, 같은 입력이 개선 후 어떻게 달라져야 하는가”로 고정했다.
- 모집단은 `final_2712_row_adjudication_ledger.jsonl`의 고유 `post_id` 2,712개이며 sampling하지 않았다.
- 최종 판정은 독립 reviewer, 고위험 교차검토, 의견 차이 제3 중재가 반영된 `independent_semantic_verdict`를 사용했다.
- baseline은 동결 런의 `pipeline.publish_allowed`, `pipeline.official_title`, 자동 review flag와 최종 dashboard action이다.
- 개선 후보 cohort는 중복을 허용하며 합산하지 않는다.

## Issues Found

1. **[High] 실제 AFTER 결과가 없다.** 보고서의 개선 후 동작은 frozen replay 승인 계약이며 실제 개선률이 아니다.
2. **[Medium] cohort가 중복된다.** 공개 후 개입 35건은 FP·wrong-work·HOLD·mismatch에도 포함되므로 막대 합계를 전체 개선량으로 사용하면 과대계상된다.
3. **[Medium] active run과 현재 worktree가 동일하지 않을 수 있다.** 현재 코드에 일부 유사 게이트가 있어도 실행 중인 런의 결과에 적용됐다고 단정할 수 없다.
4. **[Medium] search degraded가 남아 있다.** HOLD 418건의 복구 가능률은 동일 검색 상태가 아닌 비교에서 측정하면 왜곡된다.

## Calculation Spot-Checks

- 최종 정본 행/고유 ID: `2,712 / 2,712` — verified.
- pipeline publish: `263` — verified.
- 공개 후 개입: `35`, action `HOLD 12 / CORRECT 15 / REMOVE 8`, 공개행 대비 `13.3079%` — verified.
- FN: `339`, explicit OCR title 보유 `107`, title candidate 보유 `249` — verified.
- high-risk: `872`, 자동 review flag 누락 `678` — verified.
- 검증 no-title: `1,580`, 이미지·OCR·후보·댓글이 모두 없는 초저위험 `188` — verified.
- 교차검토 `221`, 의견 차이·중재 대상 `64`, 중재 coverage `64/64` — verified.
- notebook top-to-bottom 실행과 네 개 SQLite CTE source query 실행 — PASS.

## Visualization Review

- 단일 bar chart는 개선 후보별 관측 행 수 비교에 적합하고 0 기준의 절대 건수를 사용한다.
- subtitle과 인접 설명에서 cohort 중복·합산 금지를 명시했다.
- source dataset에는 행 수 외에 비율, 우선순위, cohort 정의, 중복 주의를 함께 보존했다.
- Data Analytics artifact validation과 corrected render가 모두 `PASS`다.

## Suggested Improvements

1. 구현 전에 보고서의 회귀 세트를 기계 판독 가능한 fixture/expected ledger로 고정한다.
2. P0 공개 차단과 P0 정답 회수를 별도 실험 arm으로 검증해 precision/recall tradeoff를 분리한다.
3. false-review rate, search call 수, wall time, token 사용량을 semantic hard regression과 함께 보고한다.
4. active run 종료 후 immutable snapshot으로 새 tail까지 같은 분석을 반복한다.

## Required Caveats for Stakeholders

- 이 결과는 동결 2,712건에만 적용되며 104,502건 전체 오류율이 아니다.
- AFTER는 아직 측정되지 않았다.
- 개선 후보별 건수는 중복되며 합산할 수 없다.
- search 상태와 코드 snapshot이 다른 run끼리 단순 비교하면 안 된다.

## Incomplete Handoff Blockers

- 개선 코드 미구현.
- 동일 RunSpec paired BEFORE/AFTER 미실행.
- fresh search-health matched 결과 미확보.
- 따라서 `REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
