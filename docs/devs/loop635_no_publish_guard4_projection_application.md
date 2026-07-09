# loop635_no_publish_guard4_projection_application

Candidate-set 계약 계획을 지정된 full375 projection에 적용한 projection-only 산출물이다. 새 runtime replay가 아니며, release 후보가 생겨도 full375 collateral GO 전에는 approval 근거가 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- candidate_set_contract_rows: `4`
- applied_restore_rows: `0`
- applied_hold_rows: `4`
- scrubbed_public_identity_rows: `4`
- already_blocked_hold_rows: `0`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- 다음 runtime/test run 실행 계약: `--parallel 16`, web dashboard `http://127.0.0.1:8080`, `--no-dashboard` 금지
- full375 collateral: `NO-GO`
- 완료 기준: `adjusted full375 collateral GO + full_scan path`

## 적용 행

- `11657038` hold action=`no_publish_intent_guard_contract_case` preserved=`레드 데스티니 [D]` status=`scrubbed_public_identity`
- `11657044` hold action=`no_publish_intent_guard_contract_case` preserved=`웨딩드레스` status=`scrubbed_public_identity`
- `11681180` hold action=`no_publish_intent_guard_contract_case` preserved=`아카데미 패드립 면역` status=`scrubbed_public_identity`
- `11710045` hold action=`no_publish_intent_guard_contract_case` preserved=`공주는 언니를 황제로 만든다` status=`scrubbed_public_identity`

## Gate 해석

복구 `0`건은 shared PromotionDecision을 public identity, trace, ledger에 동기화했다. hold `4`건은 serialized public identity를 지우고 후보를 ledger/trace에 보존했다. 이 산출물은 full375 collateral 재평가의 입력일 뿐, runtime 완료나 full_scan approval이 아니다.
