# Loop592 residual46 combined projection application

- 목적: Loop592 combined contract plan을 full375 projection에 projection-only로 적용해 publication/release 계약 상태를 확인했다.
- Projection rows: `375`.
- Contract plan rows: `23`.
- Applied rows: `21`.
- Validation issue: `0`.
- Runtime replay allowed rows: `0`.
- 의미: projection-only 적용은 runtime replay가 아니며 full_scan approval도 아니다.
- Full375 collateral: `NO-GO`.
- Test/runtime 계약: 다음 실제 run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지다.
- Gate: projection application `REVIEW-LOCKED`, semantic quality `REVIEW-LOCKED`, full_scan approval `false`.
