# Loop638 판결 baseline 재동결 준비도

Residual queue는 `0`이고 adjudicated re-baseline은 적용됐다. 남은 blocker는 runtime full375 counts와 full_scan 경로다.

## 요약

- gate: `READY_FOR_RUNTIME_FULL375_REPLAY`
- rebaseline_status: `APPLIED`
- adjusted_drift_count: `0`
- historical raw collateral regression: `105` (완료 기준 아님)
- ordinary residual after loop: `0`
- publication contract: `GO`
- blockers: `['collateral_runtime_counts_missing', 'full_scan_path_not_completed']`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 다음 조치

다음 full375/runtime 또는 full_scan 실행은 `--parallel 16`과 웹 대시보드를 붙여 진행한다. raw 105건은 6/26 baseline 대비 역사적 이동량이며 매 run의 완료 blocker가 아니다.
