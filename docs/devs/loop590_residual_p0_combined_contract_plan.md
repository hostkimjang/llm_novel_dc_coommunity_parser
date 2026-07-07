# Loop590 P0 combined contract plan

Loop590 combined plan은 Loop589 combined plan에 P0 policy hold 2건을 합친 장부다. `11698870`은 기존 `official_support_missing_restore_hold_contract_case` follow-up에서 `non_webnovel_ebook_policy_hold_contract_case`로 교체했고, `11698859`는 `native_web_disambiguation_hold_contract_case`로 추가했다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract plan rows: `15`
- expected restore rows: `8`
- candidate-set rebuild hold rows: `5`
- native-web disambiguation hold rows: `1`
- non-webnovel eBook/classic policy hold rows: `1`
- official-support-missing follow-up rows: `0`
- release candidate rows: `8`
- no-release hold rows: `7`
- runtime replay allowed rows: `0`
- full375 collateral gate: `NO-GO`
- execution contract: 다음 실제 test/runtime run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지
- dashboard: `http://127.0.0.1:8080`, 진행 관측 도구이며 approval 근거가 아님

## 추가/교체 행

- `11698859`: native-web exact title 미확인, official detail title 불일치, tag/context-only 근거라 publish 금지 hold.
- `11698870`: eBook/classic policy hold로 교체하여 webnovel publish contract 밖에서 public identity를 열지 않음.

## Gate 해석

Release candidate `8`건은 full375 GO 전 approval이 아니며, no-release hold `7`건은 public publish를 열지 않는다. P0 residual19 회계는 ordinary `0`으로 닫혔지만 full375 collateral은 아직 `NO-GO`이고 residual46 ordinary `27`건이 남아 goal은 `ACTIVE / NOT_COMPLETE`다.
