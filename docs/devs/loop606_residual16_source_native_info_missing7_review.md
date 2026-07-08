# Loop606 residual16 source-native INFO_MISSING 7건 blind/source-native 판정

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- batch review rows: `7`
- reviewed rows: `7`
- source-native decision rows: `7`
- info missing rows: `0`
- unreviewed batch rows: `0`
- unreviewed or info-missing rows: `0`
- validation issues: `0`

## 버킷 집계

- `safe_loss_resolved_to_null`: `2`
- `unsafe_promotion_from_hold`: `1`
- `wrong_work_title_flip`: `4`

## 라벨 집계

- `ACCEPT`: `1`
- `HOLD`: `6`

## Action queue 전환

- 원 P0 행: `7`
- source-native 검토 완료: `7`
- source-native decision rows: `7`
- info missing rows: `0`
- gate wiring 뒤 regression count 제외 후보: `1`
- REPROCESS 수리 큐: `0`
- HOLD 정책/native 추가 검토 큐: `6`
- 잔여 action queue: `6`
- full collateral approval open: `false`

## 버킷별 action queue

- `safe_loss_resolved_to_null` rows=`2` decision=`2` info_missing=`0` exclude_candidates=`0` residual=`2`
- `unsafe_promotion_from_hold` rows=`1` decision=`1` info_missing=`0` exclude_candidates=`0` residual=`1`
- `wrong_work_title_flip` rows=`4` decision=`4` info_missing=`0` exclude_candidates=`1` residual=`3`

## Source-native verdict 집계

- `alias_or_character_bridge_requires_native_web_review`: `1`
- `current_after_primary_work_correct_exact_title_surface`: `1`
- `image_context_required_for_same_work_canonical_variant`: `1`
- `image_only_candidate_requires_native_review`: `1`
- `image_only_variant_title_requires_native_review`: `1`
- `image_or_ad_context_requires_native_review`: `1`
- `image_or_native_web_needed_for_foreign_god_title_flip`: `1`

## 행별 판정

- `11661856` `HOLD` `image_only_variant_title_requires_native_review` selected=`None` action=`image_native_review_required`
  - 근거: 텍스트는 `오늘에 맘마는~~~`, `누야호`, `암타/보빔 냄새` 반응뿐이고 C1/C2 제목 차이를 직접 가르는 작품 표면이 없다. 이미지 1장이 실제 근거일 수 있으므로 이미지/native 확인 전에는 어느 variant도 safe publish로 보지 않는다.
- `11665110` `ACCEPT` `current_after_primary_work_correct_exact_title_surface` selected=`사이키델리아` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 게시글 제목이 `사이키델리아 읽었던 사람 있냐?`로 C2 제목을 직접 말하고, 본문과 댓글도 과거 독서 기억을 이어간다. C1 `낭만적인 초능력을 위하여`를 지지하는 원문 근거는 없다.
- `11682791` `HOLD` `image_context_required_for_same_work_canonical_variant` selected=`None` action=`image_native_review_required`
  - 근거: 텍스트는 `아령 즉시 구매`, `핑크덤벨` 반응만 있고 `시간을 달리는 소설가` 제목이나 피아조아 표면을 직접 말하지 않는다. C1/C2가 같은 작품 canonical variant일 가능성은 있지만 이미지 2장 확인 전 regression 제외나 publish 후보로 줄이지 않는다.
- `11685994` `HOLD` `image_or_native_web_needed_for_foreign_god_title_flip` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 제목의 `외신소환 주문`은 C2 `무한을 이해한 나는 외신의 사제가 되었습니다` 쪽을 떠올리게 하지만, 본문은 `도와줘?`뿐이고 이미지 1장에 실제 주문/제목 근거가 있을 수 있다. C1 `교황님 아하세요 마왕 들어 가요`도 OCR/이미지 후보로 보존하고 native-web/image 확인 전 HOLD한다.
- `11694067` `HOLD` `alias_or_character_bridge_requires_native_web_review` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: `김괴라리`, `그롱`, `대롱`은 C1 `괴담에 휘말렸다`와 연결될 가능성이 있지만, 텍스트만으로 검증된 별칭/캐릭터-work 관계를 확정하기에는 부족하다. 이미지 1장 또는 native-web 별칭 관계 확인 전 unsafe promotion hold를 완화하지 않는다.
- `11681178` `HOLD` `image_only_candidate_requires_native_review` selected=`None` action=`image_native_review_required`
  - 근거: 텍스트는 `한겨울에 보일러 끄고 나가는걸 잊으면 벌어지는 일`, `댕댕이들이 노릇노릇해짐`뿐이고 C1 `재벌가 차녀의 2회차 걸그룹`을 직접 지지하지 않는다. 이미지 1장이 식별 근거일 수 있으므로 image/native 확인 전 hard-hold를 유지한다.
- `11687661` `HOLD` `image_or_ad_context_requires_native_review` selected=`None` action=`image_native_review_required`
  - 근거: 텍스트는 광고 반응과 댓글 농담 위주이고 C1 `약혼녀가 소천마였다`를 직접 말하지 않는다. 광고 이미지가 작품을 직접 보여줄 수 있으므로 이미지/native 확인 전에는 safe-loss 복원을 열지 않는다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
