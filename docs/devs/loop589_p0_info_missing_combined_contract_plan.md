# Loop589 P0 INFO_MISSING combined contract plan

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract plan rows: `14`
- expected restore rows: `8`
- official-support-missing hold rows: `1`
- candidate-set rebuild hold rows: `5`
- runtime replay allowed rows: `0`
- full375 collateral gate: `NO-GO`
- execution contract: runtime `NOT_RUN`, 다음 실제 test/runtime run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지
- dashboard: `http://127.0.0.1:8080`, 진행 확인 도구이며 approval 근거가 아님

## 추가된 행

- `11682792`: source-native/blind 판정으로 `이 무림의 미친년은 나야`를 `expected_title_restore_contract_case`에 추가했다.
- `11660273`: source-native/blind 판정으로 `마도서를 줍다 마법사가 되다`를 `expected_title_restore_contract_case`에 추가했다.
- `11671514`: candidate-set rebuild 전 public publish 금지 hold를 유지한다.

## Gate 해석

Loop589 combined plan은 Loop588까지의 combined plan에 source-native wrong-work restore 2건과 candidate-set hold 1건을 합친 장부다. release candidate는 approval이 아니며, full375 collateral GO와 full_scan 경로 정의 전까지 `ACTIVE / NOT_COMPLETE`를 유지한다.
