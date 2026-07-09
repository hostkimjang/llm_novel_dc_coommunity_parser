# Loop623 current-head true triage 57 source-native combined review

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- batch review rows: `57`
- reviewed rows: `57`
- source-native decision rows: `26`
- info missing rows: `31`
- unreviewed batch rows: `0`
- unreviewed or info-missing rows: `31`
- validation issues: `0`

## 버킷 집계

- `new_resolution_promotion`: `1`
- `safe_loss_resolved_to_null`: `29`
- `unsafe_promotion_from_hold`: `8`
- `wrong_work_title_flip`: `19`

## 라벨 집계

- `ACCEPT`: `6`
- `HOLD`: `6`
- `INFO_MISSING`: `31`
- `REPROCESS`: `14`

## Action queue 전환

- 원 batch 행: `57`
- source-native 검토 완료: `57`
- source-native decision rows: `26`
- info missing rows: `31`
- gate wiring 뒤 regression count 제외 후보: `6`
- REPROCESS 수리 큐: `14`
- HOLD 정책/native 추가 검토 큐: `6`
- 잔여 action queue: `51`
- full collateral approval open: `false`

## 버킷별 action queue

- `new_resolution_promotion` rows=`1` decision=`0` info_missing=`1` exclude_candidates=`0` residual=`1`
- `safe_loss_resolved_to_null` rows=`29` decision=`16` info_missing=`13` exclude_candidates=`0` residual=`29`
- `unsafe_promotion_from_hold` rows=`8` decision=`3` info_missing=`5` exclude_candidates=`3` residual=`5`
- `wrong_work_title_flip` rows=`19` decision=`7` info_missing=`12` exclude_candidates=`3` residual=`16`

## Source-native verdict 집계

- `after_title_supported_by_abbreviation_and_plot_context`: `1`
- `after_title_supported_by_direct_abbreviation`: `1`
- `after_title_supported_by_short_title_alias`: `1`
- `before_title_supported_after_title_is_comparator`: `1`
- `comment_bridge_supports_safe_title_lost_to_null`: `2`
- `current_regression_row_without_compatible_prior_verdict`: `31`
- `direct_abbreviation_and_plot_context_support_safe_title_lost_to_null`: `1`
- `direct_abbreviation_supports_safe_title_lost_to_null`: `2`
- `direct_title_and_quote_context_support_safe_title_lost_to_null`: `1`
- `direct_title_surface_and_character_context_support_promotion`: `1`
- `direct_title_surface_supports_safe_title_lost_to_null`: `1`
- `gallery_homage_abbreviation_and_character_context_support_promotion`: `1`
- `gallery_homage_abbreviation_and_plot_context_support_promotion`: `1`
- `image_context_required_no_textual_work_anchor`: `1`
- `image_or_context_required_for_safe_title`: `5`
- `source_link_and_plot_context_support_before_title_after_title_surface_collision`: `1`
- `supported_safe_title_lost_to_null`: `4`
- `vlm_ocr_supports_clean_title_after_title_polluted_by_spoiler_prefix`: `1`

## 행별 판정

- `11665099` `ACCEPT` `after_title_supported_by_abbreviation_and_plot_context` selected=`옥탑방의 천재 마물 소환사` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `옥천마`와 본문의 소환수/연참/205화 감상은 `옥탑방의 천재 마물 소환사` 약칭과 작품 소비 맥락으로 이어진다. C1 `옥천마 출정`은 raw surface를 제목처럼 보존한 후보에 가깝고 URL도 없다.
- `11669929` `ACCEPT` `after_title_supported_by_short_title_alias` selected=`헌터갤러리의 국가권력급 기계공주` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문은 `기계공주`를 직접 작품 감상 대상으로 말하고, 후보 C2는 같은 표면을 포함한 공식 full title이다. `갤러리` 표면은 현실 DC 갤러리 단정이 아니라 웹소설 제목/작중 커뮤니티 오마주 표면일 수 있으므로 C2 승격이 타당하다.
- `11679547` `REPROCESS` `before_title_supported_after_title_is_comparator` selected=`도굴왕` action=`repair_after_wrong_work`
  - 근거: 원문은 `나혼렙의 뒤를 잇는`을 비교 기준으로 쓰고 실제 초점은 `도굴왕 애니화`다. after C1 `나 혼자만 레벨업`은 comparator를 final title로 승격한 잘못된 판정이다.
- `11682791` `HOLD` `image_context_required_no_textual_work_anchor` selected=`None` action=`image_native_review_required, native_web_review_required`
  - 근거: 텍스트에는 `아령`, `핑크덤벨`만 있고 후보 C1/C2를 직접 지지하는 작품 표면이 없다. 이미지 앞부분이 판단 근거일 수 있으므로 시각 근거 확인 전까지 HOLD가 맞다.
- `11682768` `ACCEPT` `direct_title_surface_and_character_context_support_promotion` selected=`마법소녀는 은퇴하고 싶다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `마법소녀ㄴ`은 C1 title surface와 직접 맞고, 세진/세린/앨리스 댓글 맥락도 같은 작품 내부 설정으로 보인다.
- `11687618` `ACCEPT` `gallery_homage_abbreviation_and_character_context_support_promotion` selected=`아카데미 생존 갤러리` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `아생갤`은 `아카데미 생존 갤러리` 약칭일 수 있고, 라나/엘리/클레어/아레스 맥락이 작품 내부 논의를 지지한다. `갤러리` 표면은 현실 DC 갤러리명으로 단정하지 않는다.
- `11697231` `ACCEPT` `gallery_homage_abbreviation_and_plot_context_support_promotion` selected=`아카데미 생존 갤러리` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `아생갤`과 현실쪽 위기/괴담/판타지 기대 맥락은 `아카데미 생존 갤러리` 작품 논의로 읽힌다. `갤러리`를 현실 커뮤니티명으로만 해석하지 않는다.
- `11660271` `REPROCESS` `supported_safe_title_lost_to_null` selected=`월야의 여인들` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: 본문과 댓글이 `월야의 여인들`을 직접 말하고 아이돌 히로인 장면을 같은 작품 근거로 설명한다.
- `11663535` `REPROCESS` `supported_safe_title_lost_to_null` selected=`퇴마록` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: post title과 본문이 `퇴마록` 인물/능력 체계를 직접 열거한다.
- `11666725` `HOLD` `image_or_context_required_for_safe_title` selected=`None` action=`image_native_review_required, native_web_review_required`
  - 근거: post는 이미지 기반 감상으로 보이고 source text만으로 후보 title을 직접 확인할 수 없다.
- `11668325` `REPROCESS` `comment_bridge_supports_safe_title_lost_to_null` selected=`Fate/stay night` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: 본문/댓글이 마파두부 밈과 `페이트스테이나이트`를 직접 연결하므로 후보 작품 맥락이 성립한다.
- `11671512` `HOLD` `image_or_context_required_for_safe_title` selected=`None` action=`image_native_review_required, native_web_review_required`
  - 근거: source text는 유카리 히로인 패러디 언급뿐이고 후보 title `삼시세끼, 심아식당`은 이미지/외부 맥락 확인이 필요하다.
- `11677924` `HOLD` `image_or_context_required_for_safe_title` selected=`None` action=`image_native_review_required, native_web_review_required`
  - 근거: source text는 남캐 일러/갑옷 감상만 있고 후보 작품명은 보이지 않는다. 이미지 확인 없이는 복원할 수 없다.
- `11677926` `REPROCESS` `comment_bridge_supports_safe_title_lost_to_null` selected=`재앙급 막내 공자의 회귀` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: 댓글이 `무영자 카카페 재앙급 막내공자 355`라고 직접 회차/플랫폼/작품을 확인한다.
- `11681152` `HOLD` `image_or_context_required_for_safe_title` selected=`None` action=`image_native_review_required, native_web_review_required`
  - 근거: 본문은 공지 생존 여부만 말하며 후보 title은 source text에 직접 없다. 이미지 공지 확인이 필요하다.
- `11682775` `HOLD` `image_or_context_required_for_safe_title` selected=`None` action=`image_native_review_required, native_web_review_required`
  - 근거: source text는 TS무협 추천 질문뿐이고 후보 title은 직접 보이지 않는다. 이미지/게시물 맥락 확인이 필요하다.
- `11706871` `REPROCESS` `supported_safe_title_lost_to_null` selected=`파우스트` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: post title과 본문이 `파우스트` 독후감/결말을 직접 말한다.
- `11714887` `REPROCESS` `supported_safe_title_lost_to_null` selected=`도굴왕 1 |` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: post title과 본문 링크/영상 제목이 `도굴왕` PV를 직접 지지한다.
- `11718099` `REPROCESS` `direct_abbreviation_supports_safe_title_lost_to_null` selected=`빌어먹을 환생` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: `빌환`은 후보 title의 직접 약칭이고 표지 변경 감상 맥락이다.
- `11666741` `REPROCESS` `direct_abbreviation_supports_safe_title_lost_to_null` selected=`별을 품은 소드마스터` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: 원문 `별품소`와 기사뽕/웹툰 감상 맥락은 C1 `별을 품은 소드마스터`의 약칭 소비 맥락이다. after null은 safe title loss다.
- `11679537` `REPROCESS` `direct_abbreviation_and_plot_context_support_safe_title_lost_to_null` selected=`죽었다 깨어도 수선` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: 본문의 `죽깨수`와 선협/신선/단약 전개 언급이 C1 `죽었다 깨어도 수선`을 직접 지지한다. after null은 safe title loss다.
- `11663514` `REPROCESS` `source_link_and_plot_context_support_before_title_after_title_surface_collision` selected=`마탄 속의 제국` action=`repair_after_wrong_work, native_web_review_required`
  - 근거: 본문의 Munpia URL, 리겔/느와르/범죄수사/게파르토 제국 소개문은 C1 쪽 작품 설명으로 읽힌다. 제목의 슬라임 표면만으로 C2를 final로 올린 것은 후보 충돌이다.
- `11676314` `ACCEPT` `after_title_supported_by_direct_abbreviation` selected=`마도서를 줍다 마법사가 되다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목 `마도줍`은 C1 `마도서를 줍다 마법사가 되다`의 직접 약칭으로 읽힌다. C2 `소설 속 엑스트라`를 지지하는 표면은 없다.
- `11673077` `REPROCESS` `direct_title_surface_supports_safe_title_lost_to_null` selected=`판초우의의 마법사` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: 원문 제목과 본문이 `판초우의`를 직접 평가한다. C1 title loss는 수리 대상이다.
- `11694068` `REPROCESS` `direct_title_and_quote_context_support_safe_title_lost_to_null` selected=`트와일라잇` action=`repair_safe_loss_restore_supported_title, shared_promotion_gate_wiring_required`
  - 근거: 원문 제목과 댓글 인용이 `트와일라잇`을 직접 다룬다. C1 title loss는 수리 대상이다.
- `11663554` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11714903` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11684370` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_unsafe_promotion_from_hold_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11690855` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_unsafe_promotion_from_hold_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11710045` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_unsafe_promotion_from_hold_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11669926` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11682767` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11695599` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11708443` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11710052` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11661863` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11669907` `REPROCESS` `vlm_ocr_supports_clean_title_after_title_polluted_by_spoiler_prefix` selected=`마법 좋아좋아좋아` action=`canonical_title_cleanup_required, title_url_or_variant_trace_repair`
  - 근거: Loop511 결과의 candidate ledger에는 `마법 좋아좋아좋아`가 VLM/OCR explicit work title로 남아 있고, after public title은 `약스포)` 접두가 붙은 검색/제목 오염형이다. clean title로 정리하되 URL 보존 경로는 별도 gate 수리가 필요하다.
- `11663521` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11661857` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11663557` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11665110` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11673080` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11689248` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11694049` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11698880` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11702094` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11705269` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_wrong_work_title_flip_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11687627` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_unsafe_promotion_from_hold_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11702060` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_unsafe_promotion_from_hold_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11660229` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11660264` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11660268` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11682780` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11694047` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11702090` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11703622` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_safe_loss_resolved_to_null_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.
- `11682800` `INFO_MISSING` `current_regression_row_without_compatible_prior_verdict` selected=`None` action=`source_native_or_blind_review_required, p0_new_resolution_promotion_review_required`
  - 근거: 현재 full375 collateral P0 회귀 행이지만 prior source-native verdict가 동일 post_id, 동일 triage_bucket, 현재 후보 title/url 조건을 통과하지 못했다. 정답성 확정 전까지 별도 blind/source-native 검토가 필요하다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
