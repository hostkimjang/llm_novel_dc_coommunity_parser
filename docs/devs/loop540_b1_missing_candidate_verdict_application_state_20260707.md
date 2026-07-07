# Loop540 B1 missing-candidate verdict application

이 보고서는 canonical candidate recheck verdict를 gate/action queue로 전환하는 적용 결과다. verdict 자체가 없거나 계약 테스트가 닫히지 않으면 runtime replay와 approval은 열리지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source batch: `docs\devs\loop539_b1_missing_candidate_canonical_recheck11_batch.json`
- source verdicts: `docs\devs\loop540_b1_missing_candidate_source_native_verdicts.json`
- batch rows: `11`
- verdict rows: `11`
- reviewed rows: `11`
- accepted verdict rows: `11`
- unreviewed batch rows: `0`
- validation issues: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- completion gate: `full375 collateral GO + full_scan path`

## Verdict 집계

- `EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED`: `6`
- `INSUFFICIENT_EVIDENCE_HOLD`: `5`

## 다음 상태 집계

- `candidate_scrub_or_expected_title_restore_contract_required`: `6`
- `hard_hold_or_native_web_review_required`: `5`

## 행별 적용

- `11669913` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: 원문 제목에는 `하룬`이 보이나 본문은 수학 마법 평가이고 댓글은 `판수대`로 다른 작품을 끌어온다. Loop538도 `multi_work/context_only`와 `exact_alias_candidate_preserved_without_work_discussion`을 기록했으므로 expected title을 public restore 계약으로 넘기기에는 증거가 부족하다.
- `11697242` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: 원문과 OCR은 `유희왕` 카드/캐릭터 밈을 다루며 Loop538은 `non_novel_discourse`, `community_banter`, `thematic_overlap_only`를 기록했다. 웹소설 current-work title로 expected를 복구하면 비소설/밈 표면 승격 위험이 크다.
- `11697256` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 댓글에서 `황제딸`과 `황제의 딸로 환생했습니다`가 추천 답변으로 직접 나오고, Loop538 search evidence는 노벨피아 공식 상세 `황제의 딸로 환생했다`를 잡았다. 다만 추천 문맥과 weak alias bridge가 있어 runtime 복구 전 계약 테스트가 필요하다.
- `11718114` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: 원문은 `시스템 딸깍`, `파이어볼`, `마법 강사질` 같은 장르/클리셰 비평이고 이미지도 character_visual_only다. Loop538은 `context_only`, `scope_not_current_work`, `image_ocr_without_title_anchor`를 기록했으므로 특정 expected title 복구는 보류한다.
- `11666741` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 원문 제목과 본문은 `별품소` 웹툰/결말/기사뽕을 직접 말하고, Loop538 search evidence는 `별을 품은 소드마스터`를 별품소 약칭과 웹툰 맥락으로 회수했다. 공식 URL은 부족하므로 Medium으로 두고 계약 테스트 전 runtime release는 열지 않는다.
- `11694068` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 원문 제목은 `트와일라잇 인터뷰`이고 이미지 OCR도 `Twilight`와 작가 맥락을 직접 잡는다. Loop492는 한국어/영어 표기 variant same-work로 이미 ACCEPT 판정했으므로, missing-candidate 상태에서는 expected `트와일라잇`을 source-native title로 유지한다.
- `11663511` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 원문 제목 `부캐황태자99화)`는 expected title의 약칭과 회차 표면을 직접 포함하고 본문도 해당 회차 반응이다. Loop538은 current_work와 official_detail recovery 후보를 기록했으나 다른 후보로 scrub됐으므로 expected restore 계약 테스트가 필요하다.
- `11669926` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: 이미지 OCR은 `싸울 아비문`처럼 읽혔고 검색은 `싸울아비 룬` 쪽을 회수했지만, 원문 텍스트는 직업/마녀/유사TS 감상만으로 제목을 직접 확인하지 못한다. OCR/검색 후보 충돌을 풀기 전 expected title 복구는 보류한다.
- `11669933` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 원문은 `중경계`, `해방상제`, `서휼` 등 회귀수선전 고유 설정/인물을 직접 묻고, search evidence도 회귀수선전 설정 문서를 회수한다. expected title 자체는 source-native로 확인되며 후속은 candidate restore 계약 테스트 문제다.
- `11677924` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: 이미지 OCR과 search evidence는 `귀쟁이 투기장의 역배 기사님`과 `고결에 오만이 깃들 때`를 함께 보존한다. 원문은 남캐 일러/갑옷 감상이라 두 후보 중 단일 current work를 확정하기 어렵고, multi-work/image-title conflict가 남아 HOLD가 맞다.
- `11706831` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 원문 제목 `빌런차석 살아남?`과 댓글 `연재는 하고 있음`은 해당 작품의 약칭/연재 상태 질문이고, Loop538 search evidence는 노벨피아 공식 상세 `소설 속 빌런은 아카데미 차석으로 살아간다`를 회수했다. expected title은 source-native로 유지한다.

## Gate 해석

이 회차는 residual 단건 replay가 아니라 verdict 적용 경로의 계약화다. canonical verdict와 후속 contract test가 닫히기 전에는 B1 row를 runtime replay로 되돌리지 않는다. full375 collateral은 계속 `NO-GO`이고 goal은 `ACTIVE / NOT_COMPLETE`다.
