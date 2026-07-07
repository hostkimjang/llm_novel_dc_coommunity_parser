# Loop591 residual46 candidate-set rebuild batch

- 목적: Loop590 이후 residual46 ordinary `27`건 중 candidate-set 재구성이 필요한 행을 단건 반복이 아니라 batch로 분리했다.
- 선택 행: `11671512`, `11694041`, `11694035`, `11698865`.
- 실행 범위: 새 runtime replay, bounded run, full375 대형 runtime run은 실행하지 않았다.
- 처리 원칙: 후보셋 재구성 전에는 public identity를 publish하지 않고 no-release hold로 보존한다.
- 후속 산출물: `docs/devs/loop591_residual46_candidate_set_contract_plan.json/.md`, `docs/devs/loop591_residual46_candidate_set_projection_application.json/.md`.
- Test/runtime 계약: 다음 실제 test/runtime run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지로 실행한다.
- Gate: candidate-set batch `REVIEW-LOCKED`, full375 collateral `NO-GO`, goal `ACTIVE / NOT_COMPLETE`.
