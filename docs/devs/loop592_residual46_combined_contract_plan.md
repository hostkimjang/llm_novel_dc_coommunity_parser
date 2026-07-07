# Loop592 residual46 combined contract plan

- 목적: Loop592 multi-work/listing hold `4`건을 residual46 누적 계약 계획에 합쳐 현재 release gate 입력을 갱신했다.
- Plan rows: `23`.
- Action counts: `expected_title_restore_contract_case 8`, `candidate_set_rebuild_required_before_publish 13`, `native_web_disambiguation_hold_contract_case 1`, `non_webnovel_ebook_policy_hold_contract_case 1`.
- Promotion decision: `publish 8`, `reject 13`, `hold 2`.
- Release candidate `8`건은 full375 collateral `GO` 전 approval이 아니다.
- No-release hold: candidate-set rebuild `13`, native-web disambiguation `1`, non-webnovel eBook/classic policy `1`.
- Multi-work/listing hold rows: `4`.
- Runtime replay allowed rows: `0`.
- Test/runtime 계약: 다음 실제 run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지다.
- Gate: combined contract plan `REVIEW-LOCKED`, full375 collateral `NO-GO`, completion gate `full375 collateral GO + full_scan path`.
