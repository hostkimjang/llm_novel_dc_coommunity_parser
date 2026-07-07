# Full375 residual gate action queue

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- raw regression rows: `73`
- reviewed raw regression rows: `73`
- reviewed non-regression rows: `5`
- exclusion candidate rows: `45`
- residual action queue rows: `28`
- reviewed raw residual rows: `28`
- unreviewed raw residual rows: `0`

## Lane Counts

- `alias_relation_native_web_review`: `1`
- `candidate_set_rebuild_contract`: `8`
- `character_bridge_native_web_review`: `1`
- `image_native_review`: `2`
- `native_web_or_image_evidence_batch`: `8`
- `native_web_or_image_human_review`: `2`
- `policy_or_cross_media_hold_review`: `2`
- `shared_promotion_gate_contract_repair`: `4`

## Rows

- `11661856` lane=`native_web_or_image_evidence_batch` status=`resolved_to_different_title` coverage=`reviewed_raw_regression` label=`INFO_MISSING` before=`너랑은 절! 대! 안 사Kill거니까!` after=`너랑은 절! 대! 안 사갈거니까!`
  - 근거: source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다.
- `11661863` lane=`image_native_review` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`HOLD` before=`저주받은 영애가 되었습니다` after=`None`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.
- `11665110` lane=`native_web_or_image_evidence_batch` status=`resolved_to_different_title` coverage=`reviewed_raw_regression` label=`INFO_MISSING` before=`낭만적인 초능력을 위하여` after=`사이키델리아`
  - 근거: source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다.
- `11671512` lane=`native_web_or_image_evidence_batch` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`HOLD` before=`삼시세끼, 심아식당` after=`None`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.
- `11671514` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`악신에게 총애받는 자` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11677957` lane=`alias_relation_native_web_review` status=`null_to_resolved` coverage=`reviewed_raw_regression` label=`HOLD` before=`None` after=`음악 천재가 불륜을 못 숨김`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.
- `11681178` lane=`native_web_or_image_evidence_batch` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`INFO_MISSING` before=`재벌가 차녀의 2회차 걸그룹` after=`None`
  - 근거: source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다.
- `11682749` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`주인공인데 주인공이 아님` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11682791` lane=`native_web_or_image_evidence_batch` status=`resolved_to_different_title` coverage=`reviewed_raw_regression` label=`INFO_MISSING` before=`피아조아 <시간을 달리는 소설가>` after=`시간을 달리는 소설가`
  - 근거: source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다.
- `11685994` lane=`native_web_or_image_evidence_batch` status=`resolved_to_different_title` coverage=`reviewed_raw_regression` label=`INFO_MISSING` before=`무한을 이해한 나는 외신의 사제가 되었습니다` after=`교황님 아하세요 마왕 들어 가요`
  - 근거: source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다.
- `11687635` lane=`image_native_review` status=`null_to_resolved` coverage=`reviewed_raw_regression` label=`HOLD` before=`None` after=`아포칼립스의 던전주가 되었다`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.
- `11687661` lane=`native_web_or_image_evidence_batch` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`INFO_MISSING` before=`약혼녀가 소천마였다` after=`None`
  - 근거: source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다.
- `11694035` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`시로코의 제멋대로 일상 단편선` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11694041` lane=`shared_promotion_gate_contract_repair` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`격투 소설 엑스트라가 타격 천재임` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11694067` lane=`native_web_or_image_evidence_batch` status=`null_to_resolved` coverage=`reviewed_raw_regression` label=`INFO_MISSING` before=`None` after=`괴담에 휘말렸다`
  - 근거: source-native/native-web 근거가 누락되어 raw regression을 제외할 수 없다.
- `11698859` lane=`shared_promotion_gate_contract_repair` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`귤부인 대롱대롱` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11698865` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`나츠키 스바루/작중 행적/5~8장` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11698870` lane=`policy_or_cross_media_hold_review` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`HOLD` before=`인간실격` after=`None`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.
- `11703658` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`아프리카 의 독재자가 되었다 .` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11705231` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`한국 레전드 프로게이머인 내가 일본판타지 사정에 휘말린 것에 대하여` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11706844` lane=`shared_promotion_gate_contract_repair` status=`resolved_to_different_title` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`범 먹는 괴이 사냥꾼` after=`호랑이 사냥꾼`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11708453` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`감옥학원에서 나만 힐링할거다` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11710036` lane=`candidate_set_rebuild_contract` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`쳇바퀴의 생쥐 사도가 되었다` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11710047` lane=`shared_promotion_gate_contract_repair` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REPROCESS` before=`로판 속 미움받는 악역이 되었다` after=`None`
  - 근거: source-native 판정이 수리 또는 shared gate 계약 처리를 요구한다.
- `11711632` lane=`policy_or_cross_media_hold_review` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`REJECT` before=`유어 네임(YOUR NAME)` after=`None`
  - 근거: wrong-work 또는 cross-media policy hold 검토가 필요하다.
- `11714913` lane=`character_bridge_native_web_review` status=`null_to_resolved` coverage=`reviewed_raw_regression` label=`HOLD` before=`None` after=`전 버튜버가 하고 싶은데요`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.
- `11716480` lane=`native_web_or_image_human_review` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`HOLD` before=`여대생 가랑이 사이 무릎 꿇은 엄마들` after=`None`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.
- `11718057` lane=`native_web_or_image_human_review` status=`resolved_to_null` coverage=`reviewed_raw_regression` label=`HOLD` before=`컵라면` after=`None`
  - 근거: native-web, image, alias, character bridge 검토 전 hard-hold를 유지한다.

## Gate 해석

이 큐는 corrected full375 gate 기준의 남은 raw regression action queue다. 큐가 0이 되고 full375 runtime counts가 확인되기 전까지 full_scan approval은 열리지 않는다.
