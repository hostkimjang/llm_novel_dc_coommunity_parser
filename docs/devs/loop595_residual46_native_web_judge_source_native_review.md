# loop595_residual46_native_web_judge_source_native_review

Loop593 remaining residual 18건에 기존 Codex-native web judge 산출물을 결합한 batch 검토다. 이 문서는 새 runtime replay나 full375 GO가 아니며, `ACCEPT`는 regression count 제외 후보일 뿐 approval이 아니다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- dispatch rows: `18`
- carried rows: `7`
- codex-native found/missing: `9/9`
- reviewed rows: `25`
- source-native decision rows: `16`
- info missing rows: `9`
- exclusion candidates: `7`
- residual action queue rows after exclusion candidates: `18`

## 라벨 집계

- `ACCEPT`: `7`
- `HOLD`: `2`
- `INFO_MISSING`: `9`
- `REJECT`: `1`
- `REPROCESS`: `6`

## Action 집계

- `blind_or_policy_judge_required`: `1`
- `candidate_set_rebuild_required`: `1`
- `exclude_from_regression_count_after_gate_wiring`: `7`
- `native_web_judge_reprocess_required`: `3`
- `native_web_or_image_evidence_required`: `9`
- `native_web_or_image_human_review_required`: `2`
- `native_web_reverify_required`: `1`
- `official_detail_url_enrichment_required`: `1`
- `repair_after_wrong_work`: `3`
- `shared_promotion_gate_wiring_required`: `5`
- `wrong_work_or_cross_media_policy_hold_required`: `1`

## Codex-native judge 누락 post_id

- `11661856`, `11665110`, `11666725`, `11681178`, `11685994`, `11687661`, `11671538`, `11694067`, `11682791`

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
- `11661856` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11665110` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11666725` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11681178` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11685994` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11687661` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11698871` `REPROCESS` `codex_native_web_judge_reprocess_under_resolved` selected=`Re : 제로부터 시작하는 이세계 생활` action=`native_web_judge_reprocess_required, shared_promotion_gate_wiring_required`
  - 근거: 게시글의 '리제로', 에밀리아, 렘 언급은 작품 식별 근거가 충분하다. 카카오페이지 공식 웹소설 상세에서 'Re : 제로부터 시작하는 이세계 생활'과 작가/장르가 확인되므로, 파이프라인의 관련 판정은 맞지만 제목과 URL을 미해결로 둔 것은 과소해결이다.
- `11706844` `REPROCESS` `codex_native_web_judge_reprocess_under_resolved` selected=`호랑이 사냥꾼` action=`native_web_judge_reprocess_required, shared_promotion_gate_wiring_required, native_web_reverify_required`
  - 근거: OCR에는 '범 먹는 괴이 사냥꾼'과 작가 편곤이 명시되어 있고, 현재 문피아 공식 상세는 같은 작가·같은 조선 이매망량 설명의 '호랑이 사냥꾼'으로 확인된다. OCR 제목과 현재 공식 제목이 달라 재검증은 필요하지만, null로 둔 파이프라인은 과소해결이다.
- `11706867` `ACCEPT` `codex_native_web_judge_pipeline_correct` selected=`NTR 쯔꾸르에 빙의했다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 이미지 OCR은 성인 웹소설 본문 캡처로 보이고, 댓글의 징계나무 단서가 노벨피아 공식 상세 페이지의 작품 소개 문구와 맞다. 공식 페이지에서 같은 작품명과 URL을 확인했으므로 파이프라인의 작품명 및 공식 상세 URL 해소가 맞다.
- `11710047` `REPROCESS` `codex_native_web_judge_reprocess_wrong_work` selected=`아카데미 속 미움받는 악역이 되었다` action=`native_web_judge_reprocess_required, shared_promotion_gate_wiring_required`
  - 근거: 이미지 OCR에는 제목이 '아카데미 속 미움받는 악역이 되었다'이고 작가도 파워후단벌신사 계열로 읽히며, 노벨피아 공식 상세 페이지에서도 같은 작품과 URL이 확인되므로 파이프라인이 선택한 '로판 속 미움받는 악역이 되었다'는 유사 제목의 다른 작품으로 판단됩니다.
- `11711632` `REJECT` `codex_native_web_judge_reject_wrong_work` selected=`너의 이름은.` action=`wrong_work_or_cross_media_policy_hold_required, blind_or_policy_judge_required`
  - 근거: OCR과 시각 단서는 신카이 마코토의 2016년 애니메이션 영화 '너의 이름은.' 포스터와 개봉일 정보를 가리킵니다. 파이프라인 URL은 리디의 십이월사일 로맨스 웹소설 '유어 네임(YOUR NAME)' 계열로, 제목이 유사할 뿐 다른 작품입니다. 유명 애니 OCR 단서를 웹소설 상세로 흡수한 교차매체 오매칭이므로 현재 resolved title은 reject해야 합니다.
- `11714885` `ACCEPT` `codex_native_web_judge_pipeline_null_correct` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 부모가 자식 몸으로 갈아탄다는 소재/트로프 잡담으로 보이며, 댓글 '제목'은 작품명을 제시한 것이 아니라 제목을 묻는 반응이다. 단일한 명시 작품 타깃이 없으므로 트로프성 게시글은 null-title로 보존하는 것이 맞다.
- `11716480` `HOLD` `codex_native_web_judge_hold_heretic_url_null` selected=`여대학생 가랑이 사이 무릎 꿇은 엄마들` action=`native_web_or_image_human_review_required, official_detail_url_enrichment_required`
  - 근거: 이미지 OCR에 작품 제목 '여대학생 가랑이 사이 무릎 꿇은 엄마들'과 작가명 '후타보로'가 직접 찍혀 있어 작품명 판정 자체는 pipeline이 맞습니다. 다만 웹 검색으로 동일 제목의 공식 상세 URL은 확인하지 못했고, 후보 목록에 있던 https://novel.munpia.com/208082 는 열어보면 '내 매니저는 스타 작가님'이라 OCR 제목과 전혀 맞지 않는 URL/title mismatch입니다. 그래서 제목은 유지하되 heretic_url은 null 상태로 HOLD하고 재검색이 필요합니다.
- `11716505` `ACCEPT` `codex_native_web_judge_pipeline_correct` selected=`A급 헌터가 살아가는 법` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 이미지 OCR에 작품명 A급 헌터가 살아가는 법이 명시되어 있고, 댓글 화면도 해당 작품의 독자 반응을 캡처한 맥락이다. OCR 안의 망겜의 성기사는 같은 작가의 다른 작품을 언급한 비교 대상으로 보이며 이 게시글의 주 대상은 아니다. 네이버 시리즈 공식 상세 페이지에서 같은 제목과 productNo 11641627이 확인되어 파이프라인의 제목과 URL 판단이 맞다.
- `11718057` `HOLD` `codex_native_web_judge_hold_under_resolved_false_negative` selected=`B급 헌터로 살아남기` action=`native_web_or_image_human_review_required`
  - 근거: 웹 검색상 같은 글과 주변 리뷰에서 컵라면 작가의 신작이 B급 헌터로 살아남기이며 발키리 히로인 언급도 이 작품 맥락으로 이어진다. 문피아 공식 상세 페이지도 제목과 작가 컵라면을 확인해 준다. 다만 배치 입력의 글 자체에는 컵라면이라는 작가명과 발키리·딸내미 트로프만 있고 직접 제목 앵커가 없으므로 자동 확정은 위험하다. 파이프라인의 완전 비관련 처리는 약하지만, 후보 보존 후 사람이 확인하는 HOLD가 적절하다.
- `11671538` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11694067` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.
- `11682791` `INFO_MISSING` `codex_native_web_judge_missing_for_current_dispatch` selected=`None` action=`native_web_or_image_evidence_required`
  - 근거: 현재 residual dispatch에는 native-web/image evidence가 필요하지만, 기존 Codex-native web judge 산출물에서 이 post_id 판정을 찾지 못했다. 따라서 regression count 제외나 shared-gate publish 후보로 세지 않는다.

## Gate 해석

`REPROCESS` 행은 shared promotion gate와 공식 detail URL 검증을 통과하기 전 publish 후보로 줄이지 않는다. `HOLD`, `REJECT`, `INFO_MISSING` 행은 native-web/image 또는 policy 검토가 더 필요하므로 ordinary residual에 남긴다. full375 collateral `GO`와 full_scan 경로가 정의되기 전까지 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
