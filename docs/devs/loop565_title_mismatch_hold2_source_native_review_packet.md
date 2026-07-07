# loop565_title_mismatch_hold2_source_native_batch_hold_review_packet

## 요약

- source_batch_id: `loop565_title_mismatch_hold2_source_native_batch`
- review_rows: `2`
- priority_counts: `{'P0': 2}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 2}`
- audit_status_counts: `{'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 2}`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## Review rows

### post_id `11665121`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `후회 안 하는 프로듀서`
- actual_title: `후회 안 하는 프로듀서 [독점]`
- actions: `['canonical_variant_or_wrong_work_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11673080`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `갤질하는 천재 의사`
- actual_title: `흔적을 보는 천재 무사`
- actions: `['canonical_variant_or_wrong_work_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.
