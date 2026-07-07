# Publication contract convergence 감사

- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- 정책: `PromotionDecision`, `publish_contract_trace`, `publish_ledger`, serialized public identity는 같은 publish/block 결론으로 수렴해야 한다.
- 정책: `serialized_public_identity_scrubbed`는 후보가 있으면 candidate ledger/trace에 보존하고, 후보가 없으면 `hold_without_candidates` 같은 no-candidate reason을 남겨야 한다.
- 정책: `PromotionDecision.scope`는 `publish_contract_trace.scope_state`와 일치해야 하며, scope reason code와 publish/block reason code가 충돌하면 안 된다.
- 정책: current-work marker와 non-current/context marker가 reason source 안이나 source 사이에 함께 남으면 mixed trace로 보고 정규화해야 한다.
- 정책: URL/title mismatch block은 후보 URL을 보존하되 public decision/trace/ledger/serialized identity로 URL을 publish하지 않아야 한다.
- 정책: `official_url_withheld_by_title_mismatch`는 제목 publish만 허용하고 URL은 pre-gate 후보로만 남겨야 한다.
- 정책: `promotion_eligible=true`인 이미지/OCR work-title 후보가 current-work shared gate를 충족하면 title-only publish로 수렴해야 하며, 직접 제목 앵커가 없는 이미지는 candidate_only로 남아야 한다.

## 요약

- row_count: `49`
- violation_row_count: `1`
- violation_counts: `{'publish_contract_trace_scope_state_mismatch': 1, 'blocked_decision_has_publish_only_reason': 1, 'published_and_scrubbed_reason_conflict': 1}`

## 위반 샘플

### row 2 post_id `11663535`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `publish_contract_trace_scope_state_mismatch`: publish_contract_trace.scope_state differs from PromotionDecision.scope
  - `blocked_decision_has_publish_only_reason`: blocked decision still carries publish-only reason code
  - `published_and_scrubbed_reason_conflict`: decision carries both serialized_public_identity_published and serialized_public_identity_scrubbed
