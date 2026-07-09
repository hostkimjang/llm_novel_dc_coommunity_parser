# loop638_candidate_set6_official_support_projection_application

Candidate-set 계약 계획을 지정된 full375 projection에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release 후보가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- candidate_set_contract_rows: `6`
- applied_restore_rows: `6`
- applied_hold_rows: `0`
- scrubbed_public_identity_rows: `0`
- already_blocked_hold_rows: `0`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- 다음 runtime/test run 실행 계약: `--parallel 16`, web dashboard `http://127.0.0.1:8080`, `--no-dashboard` 금지
- full375 collateral: `NO-GO`
- 완료 기준: `adjusted full375 collateral GO + full_scan path`

## 적용 행

- `11660257` restore target=`암흑가 보스요? 제가요?` superseded=`고수위.국제마약카르텔. 암흑가 의 보스 들 새 창 열림`
- `11694065` restore target=`아카데미에서 살아남기` superseded=`[아카살] 아무 관계도 아니라고!`
- `11698877` restore target=`괴담 호텔 탈출기` superseded=`괴담텔 속 마술사 새 창 열림`
- `11703631` restore target=`나의 악당들` superseded=`피카레스크`
- `11673102` restore target=`댓글 보는 천재 의사` superseded=`방송했더니 천재 의사로 착각당했다`
- `11676309` restore target=`댓글 보는 천재 의사` superseded=`댓글 보는 천재 의사`

## Gate 해석

복구 `6`건은 shared PromotionDecision을 public identity, trace, ledger에 동기화했다. hold `0`건은 serialized public identity를 지우고 후보를 ledger/trace에 보존했다. 이 산출물은 full375 collateral 재평가의 입력일 뿐, runtime 완료나 full_scan approval이 아니다.
