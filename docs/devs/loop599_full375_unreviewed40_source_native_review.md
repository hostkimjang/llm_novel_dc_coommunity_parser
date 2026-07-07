# Loop599 full375 unreviewed40 source-native/blind 40건 판정

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- batch review rows: `40`
- reviewed rows: `40`
- source-native decision rows: `40`
- info missing rows: `0`
- unreviewed batch rows: `0`
- unreviewed or info-missing rows: `0`
- validation issues: `0`

## 버킷 집계

- `safe_loss_resolved_to_null`: `9`
- `unsafe_promotion_from_hold`: `20`
- `wrong_work_title_flip`: `11`

## 라벨 집계

- `ACCEPT`: `37`
- `HOLD`: `3`

## Action queue 전환

- 원 P0 행: `40`
- source-native 검토 완료: `40`
- source-native decision rows: `40`
- info missing rows: `0`
- gate wiring 뒤 regression count 제외 후보: `37`
- REPROCESS 수리 큐: `0`
- HOLD 정책/native 추가 검토 큐: `3`
- 잔여 action queue: `3`
- full collateral approval open: `false`

## 버킷별 action queue

- `safe_loss_resolved_to_null` rows=`9` decision=`9` info_missing=`0` exclude_candidates=`9` residual=`0`
- `unsafe_promotion_from_hold` rows=`20` decision=`20` info_missing=`0` exclude_candidates=`17` residual=`3`
- `wrong_work_title_flip` rows=`11` decision=`11` info_missing=`0` exclude_candidates=`11` residual=`0`

## Source-native verdict 집계

- `after_null_correct_candidate_wrong_alias_question_context`: `1`
- `after_null_correct_event_context_secondary_work_comment`: `1`
- `after_null_correct_multi_cover_platform_context`: `1`
- `after_null_correct_negative_exclusion_context`: `1`
- `after_null_correct_non_work_food_context`: `1`
- `after_null_correct_non_work_food_memory_context`: `1`
- `after_null_correct_platform_event_context`: `1`
- `after_null_correct_real_world_registration_context`: `1`
- `after_null_correct_recommendation_trope_context`: `1`
- `alias_bridge_unverified_hold`: `1`
- `character_bridge_unverified_hold`: `1`
- `current_after_primary_work_correct_comparison_secondary_only`: `1`
- `current_after_primary_work_correct_event_phrase_not_title`: `1`
- `current_after_primary_work_correct_known_abbreviation`: `1`
- `current_after_primary_work_correct_secondary_reference_only`: `1`
- `current_after_primary_work_correct_title_alias`: `3`
- `current_after_primary_work_correct_title_alias_and_character_context`: `1`
- `current_after_primary_work_correct_title_surface`: `1`
- `current_after_promotion_supported_by_alias_and_character_context`: `2`
- `current_after_promotion_supported_by_alias_and_fanart_context`: `1`
- `current_after_promotion_supported_by_domain_alias`: `1`
- `current_after_promotion_supported_by_domain_alias_and_characters`: `1`
- `current_after_promotion_supported_by_exact_title`: `1`
- `current_after_promotion_supported_by_exact_title_and_characters`: `1`
- `current_after_promotion_supported_by_title_alias`: `7`
- `current_after_promotion_supported_by_title_alias_and_characters`: `1`
- `current_after_promotion_supported_by_title_alias_and_world_rule_context`: `1`
- `current_after_promotion_supported_by_title_fragment_and_character_context`: `1`
- `image_only_candidate_requires_native_review`: `1`
- `same_work_canonical_title_after_preferred`: `2`

## 행별 판정

- `11660262` `ACCEPT` `current_after_primary_work_correct_title_alias` selected=`로판에 도파민을 풀었다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목의 `로파민`은 C2의 축약 표면으로 읽히고, 본문도 완결과 AI 논란 뒤 독서 중단을 말한다. C1을 지지하는 원문 근거는 없다.
- `11665099` `ACCEPT` `current_after_primary_work_correct_event_phrase_not_title` selected=`옥탑방의 천재 마물 소환사` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `옥천마 출정`은 글 안에서 문제 삼은 전개 또는 에피소드 표면이고, 본문은 소환수와 205화 하차를 말한다. C2가 작품 후보로 더 자연스럽고 C1은 작품 확정 근거가 약하다.
- `11666700` `ACCEPT` `current_after_primary_work_correct_comparison_secondary_only` selected=`내 고향엔 무림인이 산다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목과 본문 모두 `내고향무림`을 현재 글의 주 작품으로 말하고, `하남자탑등반`은 도파민 중독자에게 보라는 비교 대상이다.
- `11669929` `ACCEPT` `same_work_canonical_title_after_preferred` selected=`헌터갤러리의 국가권력급 기계공주` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목의 `기계공주`와 본문의 TS/유아퇴행 감상은 C2의 작품 별칭 또는 canonical 축약으로 읽힌다. C1은 별도 공식 작품이라기보다 축약 표면이다.
- `11671500` `ACCEPT` `current_after_primary_work_correct_known_abbreviation` selected=`악당은 살고 싶다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 `악살싶`은 C2 표면과 직접 결속되고, 말투 강제와 강의씬 감상도 해당 작품 문맥이다. C1 `악당도 살고 싶다`로 볼 원문 근거는 약하다.
- `11676314` `ACCEPT` `current_after_primary_work_correct_title_alias` selected=`마도서를 줍다 마법사가 되다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목의 `마도줍`은 C1 축약이고 본문도 완결/연중 가능성을 말한다. `무절살`은 댓글의 비교 또는 농담으로 보이며 C2가 주 작품이라는 근거는 없다.
- `11681152` `ACCEPT` `same_work_canonical_title_after_preferred` selected=`[포켓몬] 체육관 챌린지에서 살아남기` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: C1과 C2는 같은 제목의 prefix/canonical 차이로 보이고, after는 공식 URL이 붙은 canonical 표면이다. 원문은 공지 이후 생존 가능성을 묻는 글이라 별도 작품으로 갈라볼 근거가 없다.
- `11694044` `ACCEPT` `current_after_primary_work_correct_secondary_reference_only` selected=`즉사기 들고 무림에 떨어지다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목의 `즉사무림`과 본문의 유료화 카운트가 C1을 주 작품으로 지정한다. `판초우의`는 같이 따라갈지 묻는 비교 대상이다.
- `11703631` `ACCEPT` `current_after_primary_work_correct_title_surface` selected=`이블 파티 대 헌터` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목이 `이블파티`를 직접 말하고, 본문과 댓글도 주인공 승수의 행위를 논한다. C1 `나의 악당들`로 볼 직접 근거는 없다.
- `11706842` `ACCEPT` `current_after_primary_work_correct_title_alias` selected=`대마법사였던것은 다시 대마법사를 꿈꾼다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `대마대`는 C1 축약 표면으로 읽히고, 본문은 완결과 초창기작 감상을 말한다. C2 `삼국지 마대`는 표면 substring 오인에 가깝다.
- `11718097` `ACCEPT` `current_after_primary_work_correct_title_alias_and_character_context` selected=`망겜의 힐러` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목의 `망겜힐`과 오행복/박태양/ts녀 논의가 C2 작품 문맥을 직접 지지한다. C1은 원문에서 논의된 작품으로 볼 근거가 없다.
- `11658637` `ACCEPT` `current_after_promotion_supported_by_title_alias_and_characters` selected=`재벌집 막내아들` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `재막아` 표면과 진양철/윤기 문맥이 C1을 직접 지지한다. hold에서 C1로 오른 것은 source-native 근거가 있다.
- `11660238` `ACCEPT` `current_after_promotion_supported_by_alias_and_character_context` selected=`무림마조` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `림조` 표면과 한서진/청월 관계 설명이 C1 작품 문맥을 지지한다. 별도 경쟁 후보나 현실 갤러리 맥락은 보이지 않는다.
- `11669928` `ACCEPT` `current_after_promotion_supported_by_title_alias` selected=`탑의 성좌들이 날 애호한다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `탑성좌애호`와 노벨피아/연중 언급이 C1을 직접 지지한다. hold 유지보다 after publish 후보가 source-native로 정당하다.
- `11671501` `ACCEPT` `current_after_promotion_supported_by_title_alias` selected=`판초우의의 마법사` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `판초법사`와 게이트/국군 전개 논의가 C1을 직접 지지한다.
- `11673086` `ACCEPT` `current_after_promotion_supported_by_alias_and_character_context` selected=`[림월드]변방계에서 회귀자로 살아남기` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `랫따싶`과 칸시/시트러스/림월드성 댓글 문맥이 C1 작품 소비 맥락을 지지한다. 다만 전역 slang 등록 근거로는 쓰지 않는다.
- `11674703` `ACCEPT` `current_after_promotion_supported_by_exact_title` selected=`도굴왕` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목과 본문이 `도굴왕` 애니화 난이도와 전투씬을 직접 논한다. C1 promotion은 source-native로 정당하다.
- `11676317` `ACCEPT` `current_after_promotion_supported_by_title_alias` selected=`마도서를 줍다 마법사가 되다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `마도서줍`은 C1 축약이고, 본문은 완결까지 닿지 않는 연재 속도를 말한다. 후보 승격은 source-native 근거가 있다.
- `11677957` `HOLD` `alias_bridge_unverified_hold` selected=`None` action=`native_web_or_alias_relation_review_required`
  - 근거: `페도부이`와 `눈깔사탕`만으로 C1 `음악 천재가 불륜을 못 숨김`을 확정하기에는 alias relation 근거가 부족하다. hardcoded cue 확장 없이 native-web 또는 별칭 관계 검증이 필요하다.
- `11681177` `ACCEPT` `current_after_promotion_supported_by_title_alias` selected=`격투 천재 여고생이 되었다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `격투 천재`와 노피아 독서 감상이 C1 축약 표면을 지지한다. 별도 경쟁 후보가 없다.
- `11682768` `ACCEPT` `current_after_promotion_supported_by_title_fragment_and_character_context` selected=`마법소녀ㄴ은 은퇴하고 싶다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목이 `마법소녀ㄴ`을 직접 포함하고, 세진/세린/앨리스 쌍둥이 문맥도 C1 내부 설정으로 이어진다.
- `11687618` `ACCEPT` `current_after_promotion_supported_by_domain_alias_and_characters` selected=`아카데미 생존 갤러리` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `아생갤`은 작품 약어로 보이고 라나/엘리/클레어/아레스 문맥이 C1과 결속된다. `갤러리` 표면을 현실 DC 갤러리명으로 단정하지 않는다.
- `11687635` `HOLD` `image_only_candidate_requires_native_review` selected=`None` action=`image_native_review_required`
  - 근거: 텍스트는 `이런 히로인 나오는 소설 추천`과 `꼴림`뿐이고, C1을 직접 지지하는 제목/별칭은 이미지에 의존한다. OCR 또는 native image 확인 전에는 promotion hold를 완화하지 않는다.
- `11695611` `ACCEPT` `current_after_promotion_supported_by_title_alias` selected=`여신이 나만 애호함` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `여신애호`와 홍보/디시콘 문맥이 C1 축약 표면을 지지한다. 단 이 판정은 row-local 근거이며 slang DB write-back 근거가 아니다.
- `11697231` `ACCEPT` `current_after_promotion_supported_by_domain_alias` selected=`아카데미 생존 갤러리` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `아생갤`은 C1 작품 약어로 보이며, 현실 위기와 전쟁 전개 감상은 작품 내용 맥락이다. `갤러리` 표면을 현실 갤러리명으로 자동 고정하지 않는다.
- `11705256` `ACCEPT` `current_after_promotion_supported_by_title_alias` selected=`하남자의 탑 공략법` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `하남자 탑`은 C1을 직접 가리키며 본문도 국뽕 전개 때문에 하차했다는 작품 감상이다.
- `11705257` `ACCEPT` `current_after_promotion_supported_by_alias_and_fanart_context` selected=`히어로 IN 히로인` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `히로히로 팬아트`와 시아루트/연재 댓글이 C1의 팬아트 문맥을 지지한다. 이미지가 포함되어도 텍스트 자체에 alias가 있으므로 hold만 유지할 필요는 낮다.
- `11706852` `ACCEPT` `current_after_promotion_supported_by_title_alias` selected=`판초우의의 마법사` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `판초법사`와 작품 추천/감상 댓글이 C1을 직접 지지한다.
- `11708466` `ACCEPT` `current_after_promotion_supported_by_exact_title_and_characters` selected=`매국노` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목이 `매국노 본 게이들`이라고 직접 묻고, 하루토/이설/유하은 관계 질문도 C1 내부 문맥이다.
- `11710037` `ACCEPT` `current_after_promotion_supported_by_title_alias_and_world_rule_context` selected=`괴담 호텔 탈출기` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 본문이 `담텔기 상식`을 직접 말하고, 상식/세계관 서술트릭을 작품 감상으로 논한다. C1 promotion은 source-native 근거가 있다.
- `11714913` `HOLD` `character_bridge_unverified_hold` selected=`None` action=`character_bridge_native_web_review_required`
  - 근거: 원문은 주서연/삣삐미쿠 캐릭터 대결을 말하지만, 텍스트 패킷 안에 C1 공식 제목이나 검증된 character-work link가 없다. character bridge 검증 전 safe publish로 줄이지 않는다.
- `11660254` `ACCEPT` `after_null_correct_multi_cover_platform_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문은 글로벌 노피아 애니메이션과 여러 표지/AI 여부를 말한다. C1 단일 작품을 직접 논하는 텍스트 근거가 없으므로 after null이 단일 title publish보다 안전하다.
- `11668278` `ACCEPT` `after_null_correct_non_work_food_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 글은 짜장면 고명과 음식점 이야기를 한다. C1 동명 도서로 확정할 작품 토론 근거가 없다.
- `11668305` `ACCEPT` `after_null_correct_non_work_food_memory_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 본문과 댓글은 급식/학원 근처 마파두부 추억을 말한다. C1 `Fate/stay night` 작품 토론 근거는 없다.
- `11695609` `ACCEPT` `after_null_correct_candidate_wrong_alias_question_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `랫따싶`이 무엇인지 묻는 글이고 댓글은 림월드 밈 쪽으로 정리된다. C1 `쳇바퀴의 생쥐 사도가 되었다`는 원문에서 지지되지 않으므로 after null이 더 안전하다.
- `11697239` `ACCEPT` `after_null_correct_real_world_registration_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 글은 조혈모세포 기증 등록 안내를 받은 현실 경험을 말한다. C1 리디북스 도서 제목으로 publish할 작품 토론 근거가 없다.
- `11697249` `ACCEPT` `after_null_correct_platform_event_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: `버거피아 합석`은 노벨피아 행사나 사회성 실험 맥락으로 보이고, C1 `버거피아`를 작품 제목으로 확정할 근거가 없다. 댓글의 `기계공주`는 인접 권유다.
- `11698904` `ACCEPT` `after_null_correct_recommendation_trope_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목은 `타락한 TS녀가 마법소녀를 타락시키는 소설 추천`이라는 trope/recommendation 요청이다. C1 `타락` 단일 작품을 지목했다는 근거는 없다.
- `11703640` `ACCEPT` `after_null_correct_event_context_secondary_work_comment` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 주 글은 `부기피아` 행사 경험을 말하고, `기계공주`는 댓글의 질문/옆자리 대화 소재다. C1을 글의 public identity로 승격하기보다 after null이 안전하다.
- `11714892` `ACCEPT` `after_null_correct_negative_exclusion_context` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 글쓴이는 신작 추천을 요청하면서 `기계공주는 ㄴㄴ`, `ts는 안 봄`이라고 제외 조건을 건다. C1은 명시적 비대상이라 after null이 단일 작품 publish보다 맞다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
