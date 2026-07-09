# Loop637 판결 baseline 재동결 준비도

Loop637은 re-baseline을 적용하지 않았다. 전 행 판결 조건이 아직 닫히지 않았고, 남은 ordinary residual `6`건이 모두 `candidate_set_rebuild_review`다.

## 요약

- gate: `NOT_READY`
- rebaseline_status: `NOT_APPLIED`
- source residual: `19`
- native/web/image evidence hold: `12`
- canonical cleanup: `1`
- ordinary residual after loop: `6`
- residual lane: `candidate_set_rebuild_review 6`
- golden18: `GO`
- full375 collateral: `NO-GO`
- historical raw collateral regression: `109`
- adjusted_drift_count: `null`
- completion gate: `adjusted full375 collateral GO + full_scan path`
- completion metric: `not_open_until_adjudicated_rebaseline`
- raw 2026-06-26 baseline completion gate: `false`

## 차단 항목

- `candidate_set_rebuild_review` 6건이 아직 판결되지 않았다.
- adjusted full375 collateral `GO`가 아직 없다.
- full_scan 경로가 아직 완료되지 않았다.
- projection-only compare의 runtime counts는 missing이며 runtime/full_scan approval 근거가 아니다.

## 다음 조치

남은 6건을 단건 반복이 아니라 candidate-set rebuild batch로 판결한 뒤, 전 행 adjudicated 상태가 되면 그 판결 결과를 새 baseline으로 재동결한다. 이후 collateral은 2026-06-26 raw 변화가 아니라 올바른 행동 대비 `adjusted_drift`를 완료 지표로 쓴다.
