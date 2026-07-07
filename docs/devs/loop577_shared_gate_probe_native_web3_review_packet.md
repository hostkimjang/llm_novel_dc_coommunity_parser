# loop577_shared_gate_probe_refined_p0_dispatch17_batch_hold_review_packet

## 요약

- source_batch_id: `loop577_shared_gate_probe_refined_p0_dispatch17_batch`
- review_rows: `3`
- priority_counts: `{'P0': 3}`
- dispatch_lane_counts: `{'candidate_set_rebuild_review': 2, 'native_web_image_evidence_review': 1}`
- audit_status_counts: `{'None': 3}`
- approval: `false`
- semantic_quality: `REVIEW-LOCKED`

## Review rows

### post_id `11663514`

- priority: `P0`
- dispatch_lane: `candidate_set_rebuild_review`
- audit_status: `None`
- expected_title: `None`
- actual_title: `None`
- actions: `['repair_after_wrong_work', 'native_web_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11698859`

- priority: `P0`
- dispatch_lane: `native_web_image_evidence_review`
- audit_status: `None`
- expected_title: `None`
- actual_title: `None`
- actions: `['repair_safe_loss_restore_supported_title', 'shared_promotion_gate_wiring_required', 'native_web_review_required']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.

### post_id `11703658`

- priority: `P0`
- dispatch_lane: `candidate_set_rebuild_review`
- audit_status: `None`
- expected_title: `None`
- actual_title: `None`
- actions: `['candidate_set_rebuild_required', 'repair_after_wrong_work', 'image_platform_url_preference']`
- review_task: 정답 title variant인지 wrong-work인지 source-native 또는 blind judge로 판정한다.
