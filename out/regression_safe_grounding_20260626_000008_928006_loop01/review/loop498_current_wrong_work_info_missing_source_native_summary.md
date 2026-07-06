# Loop498 current full375 INFO_MISSING wrong_work_title_flip 11 source-native review

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- batch review rows: `47`
- reviewed rows: `11`
- unreviewed batch rows: `36`
- validation issues: `0`

## 버킷 집계

- `wrong_work_title_flip`: `11`

## 라벨 집계

- `ACCEPT`: `6`
- `HOLD`: `2`
- `REPROCESS`: `3`

## Action queue 전환

- 원 P0 행: `47`
- source-native 검토 완료: `11`
- gate wiring 뒤 regression count 제외 후보: `6`
- REPROCESS 수리 큐: `3`
- HOLD 정책/native 추가 검토 큐: `2`
- 잔여 action queue: `41`
- full collateral approval open: `false`

## 버킷별 action queue

- `wrong_work_title_flip` rows=`11` exclude_candidates=`6` residual=`5`

## Source-native verdict 집계

- `after_canonical_title_supported_character_context_same_url`: `1`
- `after_fandom_prefixed_official_title_supported_by_source_context`: `1`
- `after_title_directly_mentioned_in_post_title`: `1`
- `after_title_supported_as_primary_work_with_secondary_comparison`: `1`
- `after_title_supported_but_candidate_url_rebuild_required`: `1`
- `after_title_supported_by_raw_abbreviation`: `1`
- `before_exact_title_supported_after_series_title_needs_cleanup`: `1`
- `before_title_character_bridge_supported_after_wrong`: `1`
- `current_work_vs_phrase_policy_review`: `1`
- `hold_preferred_both_candidates_not_source_supported`: `1`
- `image_or_context_required_for_wrong_work_candidate`: `1`

## 행별 판정

- `11660262` `ACCEPT` `after_title_supported_by_raw_abbreviation` selected=`로판에 도파민을 풀었다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `로파민`과 본문 완결/AI 논란 맥락은 `로판에 도파민을 풀었다` 약칭으로 읽힌다. C1 `그렇게, 그 괴물과 두 번 결혼했다`를 지지하는 원문 표면은 없다.
- `11663554` `ACCEPT` `after_canonical_title_supported_character_context_same_url` selected=`전 버튜버가 하고 싶은데요` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 `주서연`은 같은 Novelpia URL의 작품 내부 인물 표면으로 보이며 C2는 캐릭터명 괄호 표시형이다. C1은 같은 작품의 canonical title 정리라 wrong-work 회귀에서 제외할 수 있다.
- `11677924` `HOLD` `image_or_context_required_for_wrong_work_candidate` selected=`None` action=`image_native_review_required, native_web_review_required`
  - 근거: 원문 텍스트는 남캐 일러/갑옷 감상만 있고 C1/C2 작품명을 직접 지지하지 않는다. 이미지 확인 없이는 어느 후보도 source-native 정답으로 세울 수 없다.
- `11682749` `ACCEPT` `hold_preferred_both_candidates_not_source_supported` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 본문과 댓글은 TS 템플릿 원형으로 `묵향`을 말한다. C1 `주인공인데 주인공이 아님`과 C2 `템플릿 헌터` 모두 source-native 근거가 약하므로 후보 변경 회귀로 세지 않고 hold/null 선호로 제외한다.
- `11689292` `ACCEPT` `after_fandom_prefixed_official_title_supported_by_source_context` selected=`[원신] 최악의 파트너` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목이 `최악의 파트너`를 직접 말하고 댓글의 타르탈리아/시뇨라/원신 패러디 맥락이 C1의 fandom prefix를 지지한다. C1/C2는 같은 URL이며 after의 `[원신]` 표면은 source context를 더 잘 보존한다.
- `11692436` `REPROCESS` `before_title_character_bridge_supported_after_wrong` selected=`퍼펙트 메이지` action=`repair_after_wrong_work, character_bridge_review_required`
  - 근거: `류서란(perfect)`와 댓글 `old girl`은 C2 `퍼펙트 메이지`의 캐릭터/작품 맥락으로 결속된다. Current after C1 `죽었다 깨어도 수선`을 지지하는 원문 표면은 없다.
- `11694044` `ACCEPT` `after_title_supported_as_primary_work_with_secondary_comparison` selected=`즉사기 들고 무림에 떨어지다` action=`exclude_from_regression_count_after_gate_wiring, preserve_secondary_candidates`
  - 근거: 원문 제목의 주어는 `즉사무림 유료화`이고 본문은 `판초우의`와 비교한다. C1은 primary work로 타당하지만 C2는 secondary comparison 후보로 보존해야 한다.
- `11703658` `ACCEPT` `after_title_directly_mentioned_in_post_title` selected=`아프리카 식량왕이 되었다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목이 `문피아 아프리카 식량왕이 되었다`를 직접 말하고, 본문도 식량/옥수수/카사바 전개 감상으로 이어진다. C2는 인접 제목 오귀속이다.
- `11705230` `REPROCESS` `before_exact_title_supported_after_series_title_needs_cleanup` selected=`월야환담` action=`repair_after_wrong_work, canonical_title_cleanup_required`
  - 근거: post title과 본문이 `월야환담` 세계관의 시대 변화 영향을 직접 논의한다. Current after C2 `월야환담 시리즈`는 URL 없는 broad series 표면이므로 C1 official URL 기반 title로 정리해야 한다.
- `11710036` `REPROCESS` `after_title_supported_but_candidate_url_rebuild_required` selected=`[림월드]변방계에서 회귀자로 살아남기` action=`candidate_set_rebuild_required, shared_promotion_gate_wiring_required`
  - 근거: 댓글이 `변방계에서 회귀자로 살아남기`를 직접 후보로 제시하고 `랫따싶` 검색 안내와 이어진다. Current after title 방향은 맞지만 URL이 없으므로 후보 재구성이 필요하다.
- `11714903` `HOLD` `current_work_vs_phrase_policy_review` selected=`None` action=`policy_or_canonical_title_review_required, native_web_review_required`
  - 근거: 본문은 `괴담텔` 인물들이 모두 버튜버라는 감상이고 `온 세상이 버튜버`는 표현/패러디 표면이다. C1/C2 중 어느 쪽을 public title로 세울지는 native web 또는 canonical policy 확인이 필요하다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
