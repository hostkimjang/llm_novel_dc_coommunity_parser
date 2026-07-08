# loop604_residual28_shared_gate_contract_plan

Shared promotion gate projection을 residual 회계가 이해하는 contract plan으로 변환한 산출물이다. 이 산출물은 새 runtime replay가 아니며 full375 collateral approval도 아니다.

## 요약

- source_projection_id: `loop604_residual28_shared_gate_projection`
- source_residual_dispatch_id: `None`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- contract_plan_rows: `4`
- contract_action_counts: `{'candidate_scrub_no_publish_contract_case': 1, 'expected_title_restore_contract_case': 3}`
- promotion_decision_status_counts: `{'candidate_only': 1, 'publish': 3}`
- publish_release_candidate_rows: `3`
- candidate_only_no_publish_rows: `1`
- validation_issue_count: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## 행별 계획

- `11694041` action=`expected_title_restore_contract_case` decision=`publish` target=`격투 소설 엑스트라가 타격 천재임` url=`https://novelpia.com/novel/427330`
- `11698859` action=`expected_title_restore_contract_case` decision=`publish` target=`귤부인 대롱대롱` url=`None`
- `11706844` action=`expected_title_restore_contract_case` decision=`publish` target=`호랑이 사냥꾼` url=`https://m.munpia.com/novel/detail/522066`
- `11710047` action=`candidate_scrub_no_publish_contract_case` decision=`candidate_only` target=`아카데미 속 미움받는 악역이 되었다` url=`https://novelpia.com/novel/387035`

## Gate 해석

publish decision 행은 shared `PromotionDecision`을 통과한 release-candidate일 뿐이다. candidate-only 행은 no-publish contract로 보존하며 public title을 열지 않는다. 따라서 goal은 계속 `ACTIVE / NOT_COMPLETE`이고 완료 기준은 `full375 collateral GO + full_scan 경로 정의`다.
