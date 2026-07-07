# Loop591 residual46 combined contract plan

- 목적: Loop591 candidate-set hold `4`건을 기존 residual46 계약 계획과 합쳐 release gate가 볼 수 있는 단일 계획으로 정리했다.
- Plan rows: `19`.
- Action counts: `expected_title_restore_contract_case 8`, `candidate_set_rebuild_required_before_publish 9`, `native_web_disambiguation_hold_contract_case 1`, `non_webnovel_ebook_policy_hold_contract_case 1`.
- Promotion decision: `publish 8`, `reject 9`, `hold 2`.
- Release candidate `8`건은 approval이 아니며 full375 collateral `GO` 전 release 근거로 쓰지 않는다.
- Candidate-set rebuild hold `9`건, native-web hold `1`건, non-webnovel eBook/classic policy hold `1`건은 no-release 계약이다.
- Runtime replay allowed rows: `0`.
- Test/runtime 계약: 다음 실제 run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지다.
- Gate: combined contract plan `REVIEW-LOCKED`, full375 collateral `NO-GO`, completion gate `full375 collateral GO + full_scan path`.
