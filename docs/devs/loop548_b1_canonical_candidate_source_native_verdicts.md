# Loop548 B1 canonical candidate source-native verdicts

Loop548은 Loop547 B1 canonical recheck packet `14`건을 source-native verdict로 채운 회차다. 새 runtime replay, bounded run, full375 대형 런은 실행하지 않았다.

## 요약

- source batch: `docs/devs/loop547_b1_canonical_candidate_recheck14_batch.json`
- verdict rows: `14`
- `EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED`: `6`
- `RELATED_CANONICAL_VARIANT_CONFIRMED`: `5`
- `INSUFFICIENT_EVIDENCE_HOLD`: `3`
- runtime_replay_allowed_rows: `0`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 판정 원칙

- 원문 title/body/comment 또는 이미지 OCR이 expected/source-native 작품을 직접 지지하면 `EXPECTED_SOURCE_NATIVE_TITLE_CONFIRMED`로 둔다.
- 권차, 약칭, 오염된 expected 문자열, 표기 차이는 `RELATED_CANONICAL_VARIANT_CONFIRMED`로 두고 variant policy 계약 전에는 publish하지 않는다.
- 프랜차이즈/밈/클리셰/이미지 의존성이 커서 직접 작품 근거가 부족한 경우는 `INSUFFICIENT_EVIDENCE_HOLD`로 유지한다.

## 행별 판정

- `11665124`: expected `화산파(화산귀환)` 확인. `네이버 시리즈`는 플랫폼 후보 오염.
- `11668325`: expected `Fate/stay night` 확인. 마파두부 밈이 댓글 대화에서 직접 연결되지만 contract test 전 release는 금지.
- `11690841`: expected `블루 아카이브` 확인. `가츠동도 만들어줌`은 댓글 반응 표면.
- `11697242`: hold. `유희왕` 프랜차이즈/패러디/카드 밈 표면이라 웹소설 current-work 복구 위험이 남는다.
- `11697256`: variant. `황제의 딸로 환생했다`와 `황제의 딸로 환생했습니다`는 같은 후보군 표기 차이.
- `11710021`: variant. `무마`는 `무한의 마법사` 약칭.
- `11710049`: expected `[림월드]변방계에서 회귀자로 살아남기` 확인. `변방계 행성 하렘 생존기`는 다른 official URL 후보.
- `11714887`: variant. expected `도굴왕 1 |`는 오염 표기이고 clean title은 `도굴왕`.
- `11718099`: expected `빌어먹을 환생` 확인. `불을 먹을 환생`은 다른 작품 후보.
- `11718114`: hold. 시스템/상태창 클리셰 비평으로 직접 title anchor가 약하다.
- `11682767`: variant. `묵향 1권`은 `묵향` 권차/상세 variant.
- `11692436`: hold. `퍼펙트 메이지` 가능성은 있으나 character/image bridge 의존성이 커서 stronger evidence 필요.
- `11698859`: variant. `귤부인`은 `귤부인 대롱대롱` 축약 표면.
- `11710046`: expected `샷건 치는 병약 천사님` 확인. `병약 미소녀가 되었다.`는 competing candidate.

## Gate

이 verdict는 contract queue 입력이며 runtime replay 허가가 아니다. C1/C2 contract test와 C3 stronger evidence/native-web 확인 전에는 B1 row release를 열지 않는다. 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
