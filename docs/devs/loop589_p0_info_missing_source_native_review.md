# Loop589 P0 INFO_MISSING source-native/blind 7건 검토

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

- `safe_loss_resolved_to_null`: `1`
- `wrong_work_title_flip`: `6`

## 라벨 집계

- `ACCEPT`: `4`
- `REPROCESS`: `3`

## Action queue 전환

- 원 P0 행: `7`
- source-native 검토 완료: `7`
- source-native decision rows: `7`
- info missing rows: `0`
- gate wiring 뒤 regression count 제외 후보: `4`
- REPROCESS 수리 큐: `3`
- HOLD 정책/native 추가 검토 큐: `0`
- 잔여 action queue: `3`
- full collateral approval open: `false`

## 버킷별 action queue

- `safe_loss_resolved_to_null` rows=`1` decision=`1` info_missing=`0` exclude_candidates=`0` residual=`1`
- `wrong_work_title_flip` rows=`6` decision=`6` info_missing=`0` exclude_candidates=`4` residual=`2`

## Source-native verdict 집계

- `candidate_set_incomplete_correct_title_known_from_prior_closure`: `1`
- `current_after_primary_work_correct_phrase_surface_not_title`: `1`
- `current_after_primary_work_correct_previous_work_secondary_reference`: `1`
- `current_after_primary_work_correct_secondary_reference_only`: `1`
- `same_work_canonical_title_after_preferred`: `1`
- `source_alias_supports_official_title_after_variant_wrong_work`: `1`
- `source_context_identifies_internal_entity_after_wrong_work`: `1`

## 행별 판정

- `11660232` `ACCEPT` `current_after_primary_work_correct_secondary_reference_only` selected=`괴담 호텔 탈출기` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목의 `괴담텔`이 현재 글의 주 작품이고 `괴담동이 살짝 생각나네`는 비교 또는 2차 참조 표현이다. 본문도 유선아와 표독미 회상으로 비교 감상에 가깝기 때문에 after의 `괴담 호텔 탈출기`는 wrong-work 회귀로 세지 않는다.
- `11663554` `ACCEPT` `same_work_canonical_title_after_preferred` selected=`전 버튜버가 하고 싶은데요` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `주서연`은 C1 작품 내부 인물 또는 표면으로 보이고 C1/C2는 같은 URL의 같은 작품이다. after는 인물명 괄호 표면을 제거한 canonical title 정리이므로 wrong-work 회귀에서 제외할 수 있다.
- `11682792` `REPROCESS` `source_alias_supports_official_title_after_variant_wrong_work` selected=`이 무림의 미친년은 나야` action=`repair_after_wrong_work, shared_promotion_gate_wiring_required`
  - 근거: 원문 제목의 `무친년`은 작품 별칭이고 본문은 1000회차와 노맨스 감상으로 작품 소비 맥락을 직접 말한다. C2가 공식 제목이고, after의 C1 `[무친년]이 무림의 미친놈`은 title variant/wrong-work 표면이므로 shared promotion gate를 통한 restore 대상이다.
- `11703674` `ACCEPT` `current_after_primary_work_correct_previous_work_secondary_reference` selected=`아카데미의 마피아가 되었다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목이 `아카데미 마피아`를 현재 작품으로 직접 지정하고, 댓글도 `도굴꾼? ㄴㄴ 연중임`, `아카마피아`처럼 이전작과 현재작을 구분한다. `게임 속 도굴꾼이 되었다`는 작가의 과거작 참조라 after의 C2를 wrong-work 회귀로 세지 않는다.
- `11714903` `ACCEPT` `current_after_primary_work_correct_phrase_surface_not_title` selected=`괴담 호텔 탈출기` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 본문이 `그냥 온 세상이 버튜버구나 괴담텔은`이라고 직접 말하므로 현재 작품은 C1 `괴담 호텔 탈출기`다. `온세상이`는 문장형 감탄 또는 표현 표면이며 C2 작품명으로 볼 직접 근거가 부족하므로 after를 wrong-work 회귀로 세지 않는다.
- `11660273` `REPROCESS` `source_context_identifies_internal_entity_after_wrong_work` selected=`마도서를 줍다 마법사가 되다` action=`repair_after_wrong_work, shared_promotion_gate_wiring_required`
  - 근거: 본문이 `그리즐리는 마줍에 나오는 투명 우주 흡혈귀`라고 직접 설명한다. `그리즐리`는 C2 작품 내부 존재 또는 설정이지 별도 작품 제목이 아니므로 after의 `그리즐리 그랑`은 wrong-work이며, C2를 shared promotion gate restore 대상으로 둔다.
- `11671514` `REPROCESS` `candidate_set_incomplete_correct_title_known_from_prior_closure` selected=`None` action=`repair_after_wrong_work, candidate_set_rebuild_required`
  - 근거: `악신총애`와 하진우/세라/미궁의 주인 문맥은 작품 토론이지만, 현재 blind 후보 C1은 prior closure의 교정 제목을 포함하지 않는다. 정확한 후보셋 재구성 전에는 public publish 금지 hold로 유지한다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
