# Loop540 title mismatch HOLD 3 source-native verdicts

Loop540는 Loop539 title mismatch `3`건을 단건 replay로 갈기지 않고 source-native/blind verdict로 먼저 분리했다. 이 산출물은 review verdict이며 runtime release나 full375 approval이 아니다.

## 요약

- source batch: `docs/devs/loop539_title_mismatch_hold3_source_native_batch.json`
- source packet: `docs/devs/loop539_title_mismatch_hold3_source_native_review_packet.json`
- review rows: `3`
- label counts: `ACCEPT 1 / HOLD 1 / REPROCESS 1`
- evidence grade: `Strong 2 / Medium 1`
- regression exclusion candidate after gate wiring: `1`
- repair required: `1`
- hard-hold/native review: `1`
- runtime replay after review: `NOT_RUN_AFTER_REVIEW`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 행별 판정

- `11660277` `ACCEPT`: actual `아카메디 아카데미`가 이미지 OCR의 작품 상세 제목이다. expected `아카메디 아카데미 본 사람?`는 글 표면 질문이 섞인 baseline 값이므로 gate wiring 뒤 expected mismatch 제외 후보로 둔다.
- `11694063` `HOLD`: `엘리시아` 별칭으로 `빙의한 신의 아이, 엘리시아`와 `엘리시아 전기`가 경쟁한다. character-only 이미지와 별칭 경쟁이 남아 native-web character-work disambiguation 전에는 hard-hold를 완화하지 않는다.
- `11718098` `REPROCESS`: Loop492 native-web verdict를 승계한다. expected `마법 좋아좋아좋아`가 공식 title이고 actual `마법 좋아, 마법과 좋아`는 후보/URL 오염이므로 canonical title cleanup과 official URL correction이 필요하다.

## Gate 해석

이 회차로 title mismatch 3건은 모두 검토 상태가 생겼지만, full375 collateral은 계속 `NO-GO`다. `ACCEPT`는 gate wiring 뒤 제외 후보일 뿐이고, `REPROCESS/HOLD`가 남아 full_scan approval은 열리지 않는다.
