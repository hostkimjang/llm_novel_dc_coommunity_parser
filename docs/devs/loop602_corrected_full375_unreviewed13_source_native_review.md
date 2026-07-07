# Loop602 corrected full375 unreviewed13 source-native/blind 판정

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- batch review rows: `13`
- reviewed rows: `13`
- source-native decision rows: `13`
- info missing rows: `0`
- unreviewed batch rows: `0`
- unreviewed or info-missing rows: `0`
- validation issues: `0`

## 버킷 집계

- `safe_loss_resolved_to_null`: `12`
- `wrong_work_title_flip`: `1`

## 라벨 집계

- `ACCEPT`: `1`
- `HOLD`: `3`
- `REPROCESS`: `9`

## Action queue 전환

- 원 P0 행: `13`
- source-native 검토 완료: `13`
- source-native decision rows: `13`
- info missing rows: `0`
- gate wiring 뒤 regression count 제외 후보: `1`
- REPROCESS 수리 큐: `9`
- HOLD 정책/native 추가 검토 큐: `3`
- 잔여 action queue: `12`
- full collateral approval open: `false`

## 버킷별 action queue

- `safe_loss_resolved_to_null` rows=`12` decision=`12` info_missing=`0` exclude_candidates=`0` residual=`12`
- `wrong_work_title_flip` rows=`1` decision=`1` info_missing=`0` exclude_candidates=`1` residual=`0`

## Source-native verdict 집계

- `after_canonical_title_correct_prior_variant_wrong`: `1`
- `alias_or_image_context_requires_native_evidence`: `1`
- `asaenggal_candidate_set_rebuild_required`: `1`
- `candidate_set_incomplete_correct_work_from_source_context`: `1`
- `candidate_set_incomplete_correct_work_not_in_options_mukhyang`: `1`
- `candidate_set_incomplete_ratdasip_expanded_by_comments`: `1`
- `candidate_set_incomplete_rezero_work_not_character_article`: `1`
- `image_only_candidate_requires_native_review`: `1`
- `non_webnovel_classic_policy_hold`: `1`
- `official_title_mismatch_candidate_set_rebuild_required`: `1`
- `primary_alias_not_candidate_secondary_comment_wrong_work`: `1`
- `source_alias_supports_safe_loss_restore`: `1`
- `source_title_exact_safe_loss_restore_requires_gate`: `1`

## 행별 판정

- `11665124` `ACCEPT` `after_canonical_title_correct_prior_variant_wrong` selected=`화산귀환` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 댓글의 `화귀`, 800화, 1250화, 1324화, 해남편 맥락은 `화산귀환`을 직접 가리킨다. prior `화산파(화산귀환)`은 작품 자체가 아니라 파생/항목 표면에 가까워 after의 공식 제목이 더 맞다.
- `11661863` `HOLD` `image_only_candidate_requires_native_review` selected=`None` action=`image_native_review_required`
  - 근거: 텍스트는 `두개 써서 동시에 올리나보네`, `음음 그래 개같이 먹어주마`뿐이고 C1 `저주받은 영애가 되었습니다`를 직접 지지하지 않는다. 이미지 2장이 식별 근거일 수 있으므로 image/native 확인 전 hard-hold를 유지한다.
- `11671512` `HOLD` `alias_or_image_context_requires_native_evidence` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 본문은 패러디 떡밥, 유카리 히로인, 20화 감상을 말하지만 텍스트만으로 C1 `삼시세끼, 심아식당`과의 관계가 확정되지 않는다. 이미지 또는 native-web alias 근거가 필요하다.
- `11682749` `REPROCESS` `candidate_set_incomplete_correct_work_not_in_options_mukhyang` selected=`None` action=`candidate_set_rebuild_required`
  - 근거: 본문이 `묵향이라니까?`라고 직접 정리하고 댓글도 묵향의 약화/재강화, 타이탄, 천마구령심법, 드래곤 하트 맥락을 이어간다. C1 `주인공인데 주인공이 아님`은 지지되지 않지만 null로 닫기보다 `묵향` 후보 재구축이 필요하다.
- `11694035` `REPROCESS` `asaenggal_candidate_set_rebuild_required` selected=`None` action=`candidate_set_rebuild_required, native_web_or_image_evidence_required`
  - 근거: `아생갤`은 현실 DC 갤러리 표면으로만 단정할 수 없고 `아카데미 생존 갤러리` 같은 작품 약어일 수 있다. 원문 텍스트와 이미지 2장은 C1 `시로코의 제멋대로 일상 단편선`을 지지하지 않으므로, candidate-set을 `아생갤` 계열로 다시 만들어 확인해야 한다.
- `11694041` `REPROCESS` `source_alias_supports_safe_loss_restore` selected=`격투 소설 엑스트라가 타격 천재임` action=`shared_promotion_gate_wiring_required`
  - 근거: 제목의 `격투천재`와 본문/댓글의 경녀감성, 보지킥, 덤벨/바키 비교가 C1 작품 감상 맥락을 직접 지지한다. null로 해소된 safe-loss는 shared PromotionDecision gate를 통해 restore해야 한다.
- `11698859` `REPROCESS` `source_title_exact_safe_loss_restore_requires_gate` selected=`귤부인 대롱대롱` action=`shared_promotion_gate_wiring_required, official_detail_url_enrichment_required`
  - 근거: 게시글 제목이 C1 `귤부인 대롱대롱`을 그대로 말하고 본문도 그 뒤 전개 감상을 이어간다. 다만 후보 URL이 없으므로 shared gate restore와 공식 상세 URL 보강을 함께 요구한다.
- `11698865` `REPROCESS` `candidate_set_incomplete_rezero_work_not_character_article` selected=`None` action=`candidate_set_rebuild_required, wrong_work_or_cross_media_policy_hold_required`
  - 근거: 댓글이 `리제로?`라고 묻고 글쓴이가 긍정하며 6장/7장, 감시탑, 폭식, 나츠키 스바루를 말한다. C1은 작품 제목이 아니라 캐릭터/위키성 항목이므로 publish 후보가 아니고, `Re:제로` 작품 후보로 재구축해야 한다.
- `11698870` `HOLD` `non_webnovel_classic_policy_hold` selected=`인간실격` action=`wrong_work_or_cross_media_policy_hold_required, blind_or_policy_judge_required`
  - 근거: 원문은 일본의 유명작 `인간실격`과 작가의 자살 맥락을 말해 C1 표면 자체는 맞다. 그러나 웹소설 작품 publish 범위와 고전/일반문학 정책 경계가 남아 있어 policy hold로 유지한다.
- `11703658` `REPROCESS` `official_title_mismatch_candidate_set_rebuild_required` selected=`None` action=`candidate_set_rebuild_required, native_web_or_image_evidence_required`
  - 근거: 게시글 제목은 `문피아 아프리카 식량왕이 되었다`이고 본문/댓글도 카사바, 옥수수, 무료/유료화 감상으로 같은 문피아 작품을 논한다. C1 `아프리카 의 독재자가 되었다 .`는 제목이 맞지 않으므로 공식 상세 확인과 후보 재구축이 필요하다.
- `11705231` `REPROCESS` `candidate_set_incomplete_correct_work_from_source_context` selected=`None` action=`candidate_set_rebuild_required`
  - 근거: 원문과 댓글은 설지후, 유선화, 백혜주, 로유진, 탐식 6년 전 완독 기억을 말해 `탐식의 재림` 맥락을 강하게 지지한다. C1 `한국 레전드 프로게이머...`는 지지되지 않으므로 후보셋 재구축이 필요하다.
- `11708453` `REPROCESS` `primary_alias_not_candidate_secondary_comment_wrong_work` selected=`None` action=`candidate_set_rebuild_required`
  - 근거: 게시글 제목과 본문은 `이불사`, 검머외와 다른 길, 모방 떡밥을 주된 대상으로 삼는다. C1 `감옥학원에서 나만 힐링할거다`는 댓글에서 표절 논란 예시로 나온 보조 맥락이라 public identity로 승격하면 wrong-work 위험이 있다.
- `11710036` `REPROCESS` `candidate_set_incomplete_ratdasip_expanded_by_comments` selected=`None` action=`candidate_set_rebuild_required`
  - 근거: 댓글이 `노피아에 랫따싶 검색`, `변방계에서 회귀자로 살아남기임?`, `랫따싶에 나오는 종족`으로 약어와 풀네임 관계를 설명한다. C1 `쳇바퀴의 생쥐 사도가 되었다`는 지지되지 않으므로 랫따싶 계열 후보를 다시 만들어야 한다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
