# Loop590 P0 policy hold contract plan

Loop590 policy hold plan은 Loop589 뒤 P0 ordinary로 남은 `11698859`, `11698870` 2건을 batch로 정리한 post-verdict contract plan이다. 새 runtime replay, bounded run, full375 대형 runtime run은 실행하지 않았다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract plan rows: `2`
- native-web disambiguation hold rows: `1`
- non-webnovel eBook/classic policy hold rows: `1`
- release candidate rows: `0`
- runtime replay allowed rows: `0`
- full375 collateral gate: `NO-GO`
- execution contract: 다음 실제 test/runtime run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지
- dashboard: `http://127.0.0.1:8080`, 진행 관측 도구이며 approval 근거가 아님

## 행별 결정

- `11698859`: target `귤부인 대롱대롱`은 원문 title/context가 강하지만, NovelPia 공식 상세는 `친아들이 내게 집착한다`이고 `#귤부인` 태그 문맥만 확인됐다. exact-title publish 근거가 아니므로 `native_web_disambiguation_hold_contract_case`로 no-release 유지.
- `11698870`: target `인간실격`은 Naver Series eBook/classic detail로 확인되지만, 현재 webnovel official detail publish contract 범위 밖이다. `non_webnovel_ebook_policy_hold_contract_case`로 no-release 유지.

## Gate 해석

두 행 모두 closed contract row지만 release candidate나 approval이 아니다. full375 collateral은 Loop589 기준 `NO-GO / raw 79 / adjusted 75 / runtime counts missing` 그대로이며, 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
