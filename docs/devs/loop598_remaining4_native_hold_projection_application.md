# loop598_remaining4_native_hold_projection_application

Remaining native hold contract를 current projection result에 projection-only로 적용한 산출물이다.

## 요약

- projection_rows: `375`
- contract_plan_rows: `4`
- applied_hold_contract_rows: `4`
- applied_scrubbed_public_identity_rows: `4`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## Applied rows

- `11671538` status=`scrubbed_public_identity` candidate=`망한 교단의 성기사`
- `11718057` status=`scrubbed_public_identity` candidate=`컵라면`
- `11687661` status=`scrubbed_public_identity` candidate=`약혼녀가 소천마였다`
- `11716480` status=`scrubbed_public_identity` candidate=`여대생 가랑이 사이 무릎 꿇은 엄마들`

## Gate 해석

이 적용은 public identity 제거와 후보 보존만 수행하며, 새 runtime replay나 full_scan approval이 아니다.
