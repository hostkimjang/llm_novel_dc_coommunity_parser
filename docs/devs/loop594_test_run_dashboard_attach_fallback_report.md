# Loop594 테스트런 대시보드 attach fallback 보강

- 상태: `REVIEW-LOCKED`
- 목적: 테스트런/검증런 진행상황을 `http://127.0.0.1:8080` 웹 대시보드에서 더 안정적으로 볼 수 있게 한다.
- 실행 범위: 새 runtime replay, bounded run, full375 대형 runtime run은 발주하지 않았다.

## 변경

- `tools/run_independent_plan.py`는 dashboard 기본 ON일 때 각 planned run의 `manifest_json` 또는 `output_json` 기반 manifest 경로를 계산하고, run 시작과 동시에 `tools/attach_manifest_dashboard.py`를 별도 프로세스로 실행한다.
- `tools/attach_manifest_dashboard.py`는 막 시작한 run의 manifest가 아직 생성되지 않은 경우 `--wait-for-manifest-sec` 동안 기다린 뒤 manifest/checkpoint 기반 진행률 snapshot을 대시보드로 보낸다.
- 계획 내부 `--no-dashboard` 제거, `DASHBOARD_URL`, `DASHBOARD_PORT`, `EXPERT_DASHBOARD_FORWARD=1` 전달, standalone dashboard 자동 기동 계약은 유지한다.
- attach 프로세스 pid, manifest 경로, attach log, exit 상태를 run marker와 runner JSON 출력에 남긴다.

## 검증

- `python -m unittest tests.test_run_independent_plan tests.test_attach_manifest_dashboard tests.test_safe_loss_flip_rate_probe`
  - 결과: `15 tests / OK`
- `python -m py_compile tools\run_independent_plan.py tools\attach_manifest_dashboard.py tools\test_run_dashboard_policy.py`
  - 결과: `PASS`
- Dashboard health: `http://127.0.0.1:8080/api/health`
  - 결과: `ok=true`, `service=expert-pipeline-monitor`, `standalone=true`, `pid=9320`

## 게이트

- dashboard: `GO_PROGRESS_VIEW_NOT_APPROVAL`
- runtime replay: `NOT_RUN`
- residual46: `REVIEW-LOCKED / ordinary 18`
- full375 collateral: `NO-GO / raw 76 / adjusted 72 / runtime counts missing`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- overall goal: `ACTIVE / NOT_COMPLETE`

다음 실제 test/runtime run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지로 실행한다. Dashboard는 진행 확인 도구이며 semantic/full_scan approval 근거가 아니다.
