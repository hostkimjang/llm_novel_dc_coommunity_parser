# Loop548 B1 canonical candidate verdict application

이 보고서는 canonical candidate recheck verdict를 gate/action queue로 전환하는 적용 결과다. verdict 자체가 없거나 계약 테스트가 닫히지 않으면 runtime replay와 approval은 열리지 않는다.

## 요약

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source batch: `docs\devs\loop547_b1_canonical_candidate_recheck14_batch.json`
- source verdicts: `docs\devs\loop548_b1_canonical_candidate_source_native_verdicts.json`
- batch rows: `14`
- verdict rows: `14`
- reviewed rows: `14`
- accepted verdict rows: `14`
- unreviewed batch rows: `0`
- validation issues: `0`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- completion gate: `full375 collateral GO + full_scan path`

## Verdict 집계

- `EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED`: `6`
- `INSUFFICIENT_EVIDENCE_HOLD`: `3`
- `RELATED_CANONICAL_VARIANT_CONFIRMED`: `5`

## 다음 상태 집계

- `candidate_scrub_or_expected_title_restore_contract_required`: `6`
- `canonical_variant_policy_contract_required`: `5`
- `hard_hold_or_native_web_review_required`: `3`

## 행별 적용

- `11665124` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 댓글의 `화귀 800화`, `1250화`, `해남편` 흐름은 화산귀환 계열 논의다. current projection 후보 `네이버 시리즈`는 플랫폼/검색 후보로 보존됐지만 작품 canonical 후보가 아니다.
- `11668325` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 대화 흐름에서 post author가 `마파두부` 밈을 `페이트스테이나이트`와 직접 연결한다. current projection 후보인 노벨피아 파생/패러디 후보는 원문 canonical 작품보다 뒤에 보존될 후보일 뿐이다.
- `11690841` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 제목의 `블아`와 본문 `칸나 오가타`, 댓글 `리오`는 `블루 아카이브` 맥락을 직접 지지한다. `가츠동도 만들어줌`은 댓글 반응 표면이라 canonical title 후보가 아니다.
- `11697242` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: 원문은 `유희왕 패러디`, 듀얼리스트, 카드 댓글처럼 프랜차이즈/패러디/밈 표면을 다룬다. 웹소설 current-work canonical title로 `유희왕`을 복구하기에는 non-novel/프랜차이즈 오버리치 위험이 남아 hard-hold로 둔다.
- `11697256` verdict=`RELATED_CANONICAL_VARIANT_CONFIRMED` next=`canonical_variant_policy_contract_required` runtime_release=`blocked_until_variant_policy_tests_pass`
  - 근거: 추천 댓글에서 `황제딸` 약칭 뒤 `황제의 딸로 환생했습니다` 풀네임과 노벨피아 플랫폼이 직접 나온다. expected `황제의 딸로 환생했다`와 current candidate는 같은 작품 계열 표기 variant로 보고 variant policy 계약으로 넘긴다.
- `11710021` verdict=`RELATED_CANONICAL_VARIANT_CONFIRMED` next=`canonical_variant_policy_contract_required` runtime_release=`blocked_until_variant_policy_tests_pass`
  - 근거: 제목 `무마 웹툰`과 본문 `시로네` 맥락은 `무한의 마법사` 약칭으로 볼 수 있다. current candidate `무마`는 별도 작품이 아니라 약칭 variant이므로 canonical variant policy 계약으로 둔다.
- `11710049` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 본문의 `랫따싶` 태그 설명과 댓글의 `랫킨`, runtime candidate preview의 `[림월드]변방계에서 회귀자로 살아남기` 표면이 expected 작품을 지지한다. current candidate `변방계 행성 하렘 생존기`는 official URL 후보로 보존됐지만 canonical source-native title과 다르다.
- `11714887` verdict=`RELATED_CANONICAL_VARIANT_CONFIRMED` next=`canonical_variant_policy_contract_required` runtime_release=`blocked_until_variant_policy_tests_pass`
  - 근거: 본문 제목, YouTube/Aniplus PV 제목, 영상 설명이 모두 `도굴왕`을 직접 지지한다. expected `도굴왕 1 |`는 오염된 표기이고 current candidate `도굴왕`은 clean canonical variant로 보되 release는 variant policy 계약 뒤로 둔다.
- `11718099` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 제목 `빌환`과 본문 `시엘`, `세냐`, `아니스티나`, `매르`가 `빌어먹을 환생`을 직접 지지한다. current candidate `불을 먹을 환생`은 제목/URL이 다른 후보라 scrub 또는 expected restore 계약 대상이다.
- `11718114` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: 원문은 시스템 딸깍, 상태창, 파이어볼, 마법 강사질 같은 장르/클리셰 비평이다. expected 장문 제목과 current candidate `시스템` 모두 원문 직접 작품 표면으로 확정하기 어려워 stronger evidence 전 hard-hold로 둔다.
- `11682767` verdict=`RELATED_CANONICAL_VARIANT_CONFIRMED` next=`canonical_variant_policy_contract_required` runtime_release=`blocked_until_variant_policy_tests_pass`
  - 근거: 제목 `묵향`과 본문/댓글의 아르티어스, 드래곤 하트, TS 초기 전개가 같은 작품 맥락을 지지한다. current candidate `묵향 1권`은 권차/상세 페이지 variant라 canonical variant policy 계약으로 둔다.
- `11692436` verdict=`INSUFFICIENT_EVIDENCE_HOLD` next=`hard_hold_or_native_web_review_required` runtime_release=`blocked_until_stronger_evidence`
  - 근거: `류서란(perfect)`와 댓글 `old girl`, 이미지/캐릭터 장면은 `퍼펙트 메이지` 가능성을 주지만 원문 텍스트만으로는 character bridge와 이미지 의존성이 크다. current candidate `죽었다 깨어도 수선`도 다른 작품 후보라, native-web/시각 근거 강화 전 hard-hold로 둔다.
- `11698859` verdict=`RELATED_CANONICAL_VARIANT_CONFIRMED` next=`canonical_variant_policy_contract_required` runtime_release=`blocked_until_variant_policy_tests_pass`
  - 근거: 제목이 `귤부인 대롱대롱`을 직접 말하고 본문이 해당 장면 반응을 이어간다. current candidate `귤부인`은 축약/부분 표면이므로 canonical title은 원문 전체 표면으로 보존한다.
- `11710046` verdict=`EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED` next=`candidate_scrub_or_expected_title_restore_contract_required` runtime_release=`blocked_until_contract_tests_pass`
  - 근거: 원문 `천사님` 피디픽 맥락과 이미지 OCR의 `[TS] 샷건 치는 병약 천사님`, 공식 URL 근거가 expected title을 지지한다. current candidate `병약 미소녀가 되었다.`는 competing candidate라 scrub/restore 계약이 필요하다.

## Gate 해석

이 회차는 residual 단건 replay가 아니라 verdict 적용 경로의 계약화다. canonical verdict와 후속 contract test가 닫히기 전에는 B1 row를 runtime replay로 되돌리지 않는다. full375 collateral은 계속 `NO-GO`이고 goal은 `ACTIVE / NOT_COMPLETE`다.
