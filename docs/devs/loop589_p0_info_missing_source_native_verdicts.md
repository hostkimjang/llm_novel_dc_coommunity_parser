# Loop589 P0 INFO_MISSING source-native/blind verdict

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- source batch: `docs/devs/loop589_p0_info_missing_source_native_batch.json`
- reviewed rows: `7`
- ACCEPT/exclusion 후보: `4`
- REPROCESS restore 후보: `2`
- candidate-set rebuild hold: `1`
- runtime replay: `NOT_RUN`

## 행별 판정

- `11660232` `ACCEPT` `C2` `괴담 호텔 탈출기`: 제목의 `괴담텔`이 현재 글의 주 작품이고 `괴담동이 살짝 생각나네`는 비교 또는 2차 참조 표현이다. after는 wrong-work 회귀로 세지 않는다.
- `11663554` `ACCEPT` `C1` `전 버튜버가 하고 싶은데요`: `주서연`은 작품 내부 인물 표면이고 C1/C2는 같은 URL의 같은 작품이다. after는 canonical title 정리로 본다.
- `11682792` `REPROCESS` `C2` `이 무림의 미친년은 나야`: 원문 `무친년`은 작품 별칭이고 본문은 작품 소비 맥락이다. C1은 title variant/wrong-work 표면이므로 shared promotion gate restore 대상이다.
- `11703674` `ACCEPT` `C2` `아카데미의 마피아가 되었다`: 제목과 댓글이 현재작 `아카마피아`와 과거작 `도굴꾼`을 구분한다. after를 wrong-work 회귀로 세지 않는다.
- `11714903` `ACCEPT` `C1` `괴담 호텔 탈출기`: 본문이 `괴담텔은`이라고 직접 말한다. `온세상이`는 문장형 표현 표면이므로 C2 작품명 승격 근거가 부족하다.
- `11660273` `REPROCESS` `C2` `마도서를 줍다 마법사가 되다`: 본문이 `그리즐리`를 `마줍` 내부 존재로 설명한다. after의 `그리즐리 그랑`은 wrong-work이며 shared promotion gate restore 대상이다.
- `11671514` `REPROCESS` `HOLD` `None`: `악신총애` 문맥은 작품 토론이지만 현재 후보셋은 prior closure의 교정 제목을 포함하지 않는다. 후보셋 재구성 전 public publish 금지 hold다.

## Gate 해석

ACCEPT 4건은 source-native 관점에서 regression count 제외 후보일 뿐이며, gate wiring 전 full375 approval 근거가 아니다. REPROCESS 2건은 `repair_after_wrong_work`를 shared promotion gate restore seed로 통과시켜야 하고, `11671514`는 후보셋 재구성 전 public publish 금지 hold로 유지한다. 완료 기준은 계속 `full375 collateral GO + full_scan path`다.
