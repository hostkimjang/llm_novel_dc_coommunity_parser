# Loop638 adjudication ledger

Loop632 이후 residual chain에서 판결된 행을 새 adjudicated baseline의 판결 ledger로 고정한다. 이 ledger는 runtime replay나 full_scan approval이 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- adjudicated_rows: `59`
- duplicate_or_validation_issue_count: `0`
- decision_kind_counts: `{'no_publish_or_hold_not_approval': 17, 'release_candidate_not_approval_full375_recheck_required': 31, 'source_native_exclusion_candidate_not_approval': 11}`
- triage_bucket_counts: `{'safe_loss_resolved_to_null': 29, 'unsafe_promotion_from_hold': 9, 'wrong_work_title_flip': 21}`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- completion gate: `adjusted full375 collateral GO + full_scan path`
- raw 2026-06-26 baseline: `diagnostic only`

## 묶음

- `loop632_initial_contract18`: `18`건 - Loop632 shared-gate/candidate/canonical 초기 계약 18건
- `loop633_source_native_exclusion11`: `11`건 - Loop633 source-native/blind 판결 exclusion 11건
- `loop634_shared_gate_restore6`: `6`건 - Loop634 shared-gate restore 6건
- `loop635_no_publish_guard4`: `4`건 - Loop635 no-publish intent guard 4건
- `loop636_canonical_cleanup1`: `1`건 - Loop636 canonical cleanup 1건
- `loop637_native_hold12`: `12`건 - Loop637 native/web/image no-release hold 12건
- `loop637_canonical_cleanup1`: `1`건 - Loop637 canonical cleanup 1건
- `loop638_candidate_set_restore6`: `6`건 - Loop638 candidate-set official support restore 6건
