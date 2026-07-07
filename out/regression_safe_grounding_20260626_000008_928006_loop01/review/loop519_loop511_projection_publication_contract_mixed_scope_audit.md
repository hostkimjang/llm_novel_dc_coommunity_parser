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

- row_count: `375`
- violation_row_count: `36`
- violation_counts: `{'mixed_current_noncurrent_scope_reason_codes': 36}`

## 위반 샘플

### row 28 post_id `11668324`

- public_identity: `{'official_title': '니들 생각 다 들린다', 'official_url': 'https://novelpia.com/novel/384318'}`
- decision: `{'status': 'publish', 'publish_allowed': True, 'official_title': '니들 생각 다 들린다', 'official_url': 'https://novelpia.com/novel/384318'}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 37 post_id `11677920`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 54 post_id `11700495`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 68 post_id `11714913`

- public_identity: `{'official_title': '전 버튜버가 하고 싶은데요', 'official_url': 'https://novelpia.com/novel/275975'}`
- decision: `{'status': 'publish', 'publish_allowed': True, 'official_title': '전 버튜버가 하고 싶은데요', 'official_url': 'https://novelpia.com/novel/275975'}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 69 post_id `11718057`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 78 post_id `11682749`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work'] with non-current markers ['scope_context_only', 'scope_not_current_work']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']
### row 88 post_id `11706842`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work'] with non-current markers ['scope_context_only', 'scope_not_current_work']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 89 post_id `11708453`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 90 post_id `11710036`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 114 post_id `11668313`

- public_identity: `{'official_title': '귀환 용사의 현대 생활', 'official_url': 'https://novelpia.com/novel/391587'}`
- decision: `{'status': 'publish', 'publish_allowed': True, 'official_title': '귀환 용사의 현대 생활', 'official_url': 'https://novelpia.com/novel/391587'}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 116 post_id `11669926`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work'] with non-current markers ['scope_not_current_work']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 123 post_id `11673080`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work'] with non-current markers ['scope_context_only', 'scope_not_current_work']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 136 post_id `11694065`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 137 post_id `11694067`

- public_identity: `{'official_title': '괴담에 휘말렸다', 'official_url': 'https://novelpia.com/novel/363195'}`
- decision: `{'status': 'publish', 'publish_allowed': True, 'official_title': '괴담에 휘말렸다', 'official_url': 'https://novelpia.com/novel/363195'}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 140 post_id `11695637`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 144 post_id `11698910`

- public_identity: `{'official_title': '판초우의의 마법사', 'official_url': 'https://series.naver.com/novel/detail.series?productNo=14207846'}`
- decision: `{'status': 'publish', 'publish_allowed': True, 'official_title': '판초우의의 마법사', 'official_url': 'https://series.naver.com/novel/detail.series?productNo=14207846'}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 146 post_id `11702085`

- public_identity: `{'official_title': '괴담 호텔 탈출기', 'official_url': 'https://novelpia.com/novel/102155'}`
- decision: `{'status': 'publish', 'publish_allowed': True, 'official_title': '괴담 호텔 탈출기', 'official_url': 'https://novelpia.com/novel/102155'}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 148 post_id `11703624`

- public_identity: `{'official_title': '판초우의의 마법사', 'official_url': 'https://novel.munpia.com/530500'}`
- decision: `{'status': 'publish', 'publish_allowed': True, 'official_title': '판초우의의 마법사', 'official_url': 'https://novel.munpia.com/530500'}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work', 'scope_current_work'] with non-current markers ['context_only']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 153 post_id `11705251`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work'] with non-current markers ['scope_context_only', 'scope_not_current_work']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']

### row 155 post_id `11706832`

- public_identity: `{'official_title': None, 'official_url': None}`
- decision: `{'status': 'candidate_only', 'publish_allowed': False, 'official_title': None, 'official_url': None}`
- violations:
  - `mixed_current_noncurrent_scope_reason_codes`: scope reason codes mix current-work markers ['row_discusses_work_as_work'] with non-current markers ['scope_context_only', 'scope_not_current_work']; sources=['PromotionDecision.reason_codes', 'publish_contract_trace.reason_codes', 'publish_contract_trace.gate_decision.reason_codes', 'publish_ledger.gate_decision.reason_codes', 'candidate_ledger.promotion_decision.reason_codes', 'candidate_ledger.publish_contract_trace.reason_codes']
