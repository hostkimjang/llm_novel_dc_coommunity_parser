# Generalization Case Matrix

품질 실패를 고칠 때 특정 `post_id`나 오답 title만 막지 않고, 실패 유형과 이웃 케이스를 함께 본다.

## 2026-04-28 afterfix12 parallel36 canary matrix

입력: `out/sampling/query_gate_canary_200_20260426.jsonl`

| 실패 유형 | 기대 방향 | negative / 차단 케이스 | positive / rescue 케이스 |
| --- | --- | --- | --- |
| 실제 의학/건강 주제 + 작품 앵커 없음 | `is_relevant=false`, title 없음 | `11718070` ECT/우울증 치료 | 작품/캐릭터/회차 앵커가 있으면 차단 금지 |
| 장르/세계관 일반어만 겹침 | 특정 작품명 승격 금지 | `11631298` 무림맹/마교/혈교 일반 세력어 | 안정된 약칭/공식근거가 있는 `11562020` 서울마탑 |
| 캐릭터명(작품명) 검색 결과 | 캐릭터 반복 + 같은 근거의 작품 연결일 때만 title 확정 | `11689276` 일반 인물/직업 parenthetical, `11620037` source metadata phrase | `11663540` 주서연 -> 전 버튜버가 하고 싶은데요 |
| 검색 메타데이터/저자 꼬리 title 오염 | source metadata phrase는 title로 쓰지 않음 | `11620037` 또는 라쇼몽, 저자 메타데이터 | 실제 작품 detail URL/공식 title 근거가 있으면 허용 |
| strong alias 과차단 | generic guard 이후 alias rescue | 일반 세력명만 있는 `11631298`은 rescue 금지 | `11562020` 서울마탑, `11702067` 폴랩, `11576520` 망교성 등은 재검토 |

이번 canary는 36 shard/36 worker 병렬 경로에서 위 matrix가 같이 유지되는지 확인한다.

## 2026-04-28 afterfix12 parallel36 결과

- run id: `20260428_142042_238055`
- 결과 파일: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result_checkpoint.jsonl`
- case matrix 추출:
  - `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_case_matrix.json`
  - `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_case_matrix.md`
- 비교:
  - `out/comparisons/query_gate_canary_200_afterfix11_vs_afterfix12_parallel36_20260428.md`
- 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`

| 실패 유형 | 결과 | 다음 액션 |
| --- | --- | --- |
| 실제 의학/건강 주제 + 작품 앵커 없음 | `11718070`은 `is_relevant=false`, title 없음, `medical_common_topic_demoted` | 1,000건에서 현실 의학/건강/일상 정보글의 adjacent 오분류 재집계 |
| 장르/세계관 일반어만 겹침 | `11631298`은 non-relevant/title 없음 유지 | 일반 세력어 차단과 strong alias rescue가 충돌하지 않는지 계속 확인 |
| 캐릭터명(작품명) 검색 결과 | `11663540`은 `전 버튜버가 하고 싶은데요` resolved 유지. `11689276`은 title은 제거됐지만 adjacent로 남음 | `11689276`류 인물/직업 parenthetical은 정성 리뷰에서 ACCEPT/HOLD/REJECT 판독 |
| 검색 메타데이터/저자 꼬리 title 오염 | `11620037`은 non-relevant/title 없음 | source metadata phrase validator를 1,000건에서 재집계 |
| strong alias 과차단 | `11562020`은 `서울에 마탑 세웠더니 돈이 미쳤다` resolved | `11702067(폴랩)`, `11576520(망교성)`, `화귀`, `언니약혼` long-tail targeted 추가 |

현재 결론: 36병렬 canary에서는 핵심 negative/positive 이웃 케이스가 대체로 의도대로 움직였지만, adjacent 경계와 long-tail alias 회수는 아직 `REVIEW`다.

## 2026-04-30 afterfix21 matrix

입력:
- targeted: `out/sampling/targeted_short_person_trope_afterfix21_20260430.jsonl`
- canary: `out/sampling/query_gate_canary_200_20260426.jsonl`
- risk: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429.jsonl`

| 실패 유형 | 기대 방향 | negative / 차단 케이스 | positive / rescue 케이스 | afterfix21 결과 |
| --- | --- | --- | --- | --- |
| 짧은 인명/캐릭터 표면이 영문 title로 승격 | post-side work anchor 없으면 resolved 금지 | `11505857 -> Cecil` | `11663540 -> 전 버튜버가 하고 싶은데요` | risk에서 `11505857` title 없음, `11663540` resolved 유지 |
| trope-only internal work signal 과복구 | 폼체인지/변신/의상만 있으면 non-relevant/adjacent | `11456200` | `11198715`, `11616838` | risk에서 `11456200` non-relevant/title 없음, positive는 관련-미확정 유지 |
| 현실 의학/건강 주제 + 작품 앵커 없음 | non-relevant/title 없음 | `11718070`, `11718111` | 실제 작품/회차/캐릭터 anchor가 있으면 차단 금지 | risk에서 둘 다 title 없음 |
| 일반 세력/세계관 명사 | 단일 작품명 승격 금지 | `11631298` | 안정 alias/official evidence가 강한 케이스 | risk에서 title 없음 |

현재 결론: afterfix21은 목표 negative/positive 이웃을 통과했지만, risk resolved 총량이 늘어 새 고위험 resolved 표본 리뷰가 필요하다.
