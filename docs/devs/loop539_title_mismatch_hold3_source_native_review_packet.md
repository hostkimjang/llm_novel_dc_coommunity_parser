# loop539_title_mismatch_hold3_source_native_batch_hold_review_packet

## 요약

- source_batch_id: `loop539_title_mismatch_hold3_source_native_batch`
- review_rows: `3`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'source_native_or_blind_review': 3}`
- audit_status_counts: `{'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 3}`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## Review rows

### post_id `11660277`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `아카메디 아카데미 본 사람?`
- actual_title: `아카메디 아카데미`
- actions: `['canonical_variant_or_wrong_work_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11694063`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `빙의한 신의 아이, 엘리시아`
- actual_title: `엘리시아 전기`
- actions: `['canonical_variant_or_wrong_work_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11718098`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `마법 좋아좋아좋아`
- actual_title: `마법 좋아, 마법과 좋아`
- actions: `['canonical_variant_or_wrong_work_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.
