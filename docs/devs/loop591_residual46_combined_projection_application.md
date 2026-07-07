# Loop591 residual46 combined projection application

- 목적: Loop591 combined contract plan을 full375 projection에 projection-only로 적용해 release/publication 계약 상태를 확인했다.
- Projection rows: `375`.
- Contract plan rows: `19`.
- Applied rows: `17`.
- Validation issue: `0`.
- Runtime replay allowed rows: `0`.
- 의미: projection 적용은 static 검증이며 runtime replay나 full_scan approval이 아니다.
- Full375 collateral: `NO-GO`.
- Test/runtime 계약: 다음 실제 run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지다.
- Gate: projection application `REVIEW-LOCKED`, semantic quality `REVIEW-LOCKED`, full_scan approval `false`.
