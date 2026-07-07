# loop550_c2_canonical_variant_policy_review

Loop548/549 뒤에 남은 C2 canonical variant policy 행을 shared promotion gate 계약 기준으로 검토한 산출물이다. 이 리뷰는 public publish, runtime replay, full_scan approval이 아니며, variant를 no-publish quarantine/exclusion 후보로만 분리한다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- policy_review_rows: `5`
- validation_issue_count: `0`
- regression_exclusion_candidate_rows: `5`
- search_blind_conditional_rows: `4`
- publish_allowed_rows: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`

## Variant 관계

- `current_candidate_matches_clean_canonical`: `2`
- `expected_matches_clean_canonical`: `3`

## 행별 정책

- `11697256` decision=`canonical_variant_quarantine_no_publish` relation=`current_candidate_matches_clean_canonical` canonical=`황제의 딸로 환생했습니다` candidate=`황제의 딸로 환생했습니다` search=`SEARCH_BLIND_BLOCKER` exclusion_candidate=`True`
- `11710021` decision=`canonical_variant_quarantine_no_publish` relation=`expected_matches_clean_canonical` canonical=`무한의 마법사` candidate=`무마` search=`SEARCH_EVIDENCE_MISSING` exclusion_candidate=`True`
- `11714887` decision=`canonical_variant_quarantine_no_publish` relation=`current_candidate_matches_clean_canonical` canonical=`도굴왕` candidate=`도굴왕` search=`SEARCH_RECOVERED_CONDITIONAL` exclusion_candidate=`True`
- `11682767` decision=`canonical_variant_quarantine_no_publish` relation=`expected_matches_clean_canonical` canonical=`묵향` candidate=`묵향 1권` search=`SEARCH_BLIND_BLOCKER` exclusion_candidate=`True`
- `11698859` decision=`canonical_variant_quarantine_no_publish` relation=`expected_matches_clean_canonical` canonical=`귤부인 대롱대롱` candidate=`귤부인` search=`SEARCH_BLIND_BLOCKER` exclusion_candidate=`True`

## Gate 해석

C2 5건은 모두 no-publish quarantine으로 유지한다. regression exclusion 후보로 표시된 행도 queue 회계 후보일 뿐 approval이 아니며, search blind/missing 행은 search 복구 전 promotion approval 근거로 쓰지 않는다. 따라서 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.
