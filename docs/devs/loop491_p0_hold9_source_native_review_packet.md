# loop491_p0_runtime_failure_batch_hold_review_packet

## 요약

- source_batch_id: `loop491_p0_runtime_failure_batch`
- review_rows: `9`
- priority_counts: `{'P0': 9}`
- dispatch_lane_counts: `{'canonical_variant_policy_review': 1, 'source_native_or_blind_review': 8}`
- audit_status_counts: `{'FAIL_RUNTIME_PROMOTION_BLOCKED': 3, 'FAIL_SAFE_RESOLVED_TITLE_MISMATCH': 5, 'FAIL_VARIANT_COMPACT_MATCH_ONLY': 1}`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## Review rows

### post_id `11663535`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_RUNTIME_PROMOTION_BLOCKED`
- expected_title: `퇴마록`
- actual_title: `퇴마록 외전 1`
- actions: `['blocked_title_mismatch_source_native_review_required', 'canonical_variant_or_wrong_work_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11673102`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `갤질하는 천재 의사`
- actual_title: `댓글 보는 천재 의사`
- actions: `['canonical_variant_or_wrong_work_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11692436`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `퍼펙트 메이지`
- actual_title: `죽었다 깨어도 수선`
- actions: `['canonical_variant_or_wrong_work_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11698870`

- priority: `P0`
- dispatch_lane: `canonical_variant_policy_review`
- audit_status: `FAIL_VARIANT_COMPACT_MATCH_ONLY`
- expected_title: `인간실격`
- actual_title: `인간 실격`
- actions: `['spacing_or_canonical_variant_policy_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11705230`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `월야환담`
- actual_title: `월야환담 시리즈`
- actions: `['canonical_variant_or_wrong_work_review_required', 'search_degraded_or_timeout_replay_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11714887`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_RUNTIME_PROMOTION_BLOCKED`
- expected_title: `도굴왕 1 |`
- actual_title: `[도굴왕] [fate] 도굴왕에서 에누마 엘리시를!!`
- actions: `['blocked_title_mismatch_source_native_review_required', 'canonical_variant_or_wrong_work_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11718098`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `마법 좋아좋아좋아`
- actual_title: `마법 좋아, 마법과 좋아`
- actions: `['canonical_variant_or_wrong_work_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11673077`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_RUNTIME_PROMOTION_BLOCKED`
- expected_title: `판초우의의 마법사`
- actual_title: `즉사기 들고 무림에 떨어지다`
- actions: `['blocked_title_mismatch_source_native_review_required', 'canonical_variant_or_wrong_work_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11694068`

- priority: `P0`
- dispatch_lane: `source_native_or_blind_review`
- audit_status: `FAIL_SAFE_RESOLVED_TITLE_MISMATCH`
- expected_title: `트와일라잇`
- actual_title: `Twilight`
- actions: `['canonical_variant_or_wrong_work_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.
