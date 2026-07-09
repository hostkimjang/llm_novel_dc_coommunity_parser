# Loop638 adjudicated re-baseline manifest

Loop638은 판결된 375행 projection을 새 adjudicated baseline으로 재동결했다. 이후 collateral은 2026-06-26 raw 변화가 아니라 이 baseline 대비 `adjusted_drift_count`로 본다.

## 요약

- rebaseline_status: `APPLIED`
- baseline rows: `375`
- adjudication ledger rows: `59`
- ordinary residual after loop: `0`
- publication contract: `GO`
- adjusted_drift_count: `0`
- historical raw collateral regression: `105` (참고값)
- always-on gate: `NO-GO` / blockers `['collateral:collateral_runtime_counts_missing']`
- completion gate metric: `adjusted_drift_count`
- full_scan_approval: `false`

## 해시

- adjudicated_baseline_result_sha256: `958b5c547e03df3931d25606b4e8204fcb85a58a6642d70443478adad91c74cb`
- projection_result_sha256: `958b5c547e03df3931d25606b4e8204fcb85a58a6642d70443478adad91c74cb`
- adjudication_ledger_sha256: `5b2b73219d1c72a6575386389631c68e9a556eb9182697cfea1754e86fb6a8e3`

## Gate 해석

정적 adjusted drift는 `0`이지만 runtime counts가 없으므로 always-on은 아직 `NO-GO`다. 완료 기준은 raw가 아니라 adjusted 기준이며, full_scan 경로가 끝나기 전까지 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
