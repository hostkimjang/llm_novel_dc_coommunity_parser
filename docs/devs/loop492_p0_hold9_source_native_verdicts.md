# Loop492 P0 HOLD 9 source-native verdict

## 요약

- 대상: Loop491 `HOLD 9`
- 판정: `ACCEPT 4 / REPROCESS 3 / HOLD 2`
- native web 보강: `3`행
- runtime replay after review: `NOT_RUN_AFTER_REVIEW`
- full375 collateral: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- goal: `ACTIVE / NOT_COMPLETE`

이번 회차는 hard-hold 완화 전 canonical/variant 판정을 먼저 닫기 위한 source-native/blind 검토다. `ACCEPT`는 full375 regression count에서 바로 제외한다는 뜻이 아니라, variant policy 또는 gate wiring 뒤 제외 후보가 된다는 뜻이다.

## 판정표

| post_id | before/expected | after/actual | verdict | 근거/조치 |
| --- | --- | --- | --- | --- |
| `11663535` | `퇴마록` | `퇴마록 외전 1` | `REPROCESS` | 원문은 `퇴마록` 본편/세계관과 인물/능력 단서를 직접 말한다. 외전 1은 과특정 variant라 canonical base로 재처리한다. |
| `11673102` | `갤질하는 천재 의사` | `댓글 보는 천재 의사` | `ACCEPT` | 원문 `갤질의사`와 공식 노벨피아 제목/태그가 같은 작품을 지지한다. 별칭/공식 제목 variant로 둔다. |
| `11692436` | `퍼펙트 메이지` | `죽었다 깨어도 수선` | `HOLD` | 텍스트는 `류서란(perfect)`뿐이고 이미지 1장이 핵심이다. image/native 또는 blind judge 전 단일 작품 확정 금지. |
| `11698870` | `인간실격` | `인간 실격` | `ACCEPT` | 띄어쓰기 차이만 있는 같은 작품 variant다. |
| `11705230` | `월야환담` | `월야환담 시리즈` | `ACCEPT` | 원문이 `월야환담` 세계/시대 변화 맥락을 직접 논한다. base/series variant로 본다. |
| `11714887` | `도굴왕 1 |` | `[도굴왕] [fate] 도굴왕에서 에누마 엘리시를!!` | `REPROCESS` | 원문은 애니플러스 PV의 `도굴왕`이다. expected는 권/페이지 오염, actual은 파생/팬픽 표면이라 후보 재구성이 필요하다. |
| `11718098` | `마법 좋아좋아좋아` | `마법 좋아, 마법과 좋아` | `REPROCESS` | 원문 `마좋좋좋`과 공식 노벨피아 상세는 `마법 좋아좋아좋아`를 지지한다. actual 제목/URL은 오염으로 재처리한다. |
| `11673077` | `판초우의의 마법사` | `즉사기 들고 무림에 떨어지다` | `HOLD` | `즉사무림`, `판초우의`, `빛세구`를 함께 본 다작품 감상이다. 단일 current work 승격 정책 전까지 보류한다. |
| `11694068` | `트와일라잇` | `Twilight` | `ACCEPT` | 한국어/영어 제목 variant로 같은 작품을 가리킨다. |

## 산출물

- verdict JSON: `docs/devs/loop492_p0_hold9_source_native_verdicts.json`
- verdict Markdown: `docs/devs/loop492_p0_hold9_source_native_verdicts.md`
- state: `docs/devs/loop492_p0_hold9_source_native_state_20260706.json`
- report: `docs/devs/loop_reports/LOOP_492_REPORT_20260706.md`

## 게이트

- source-native review: `REVIEW-LOCKED / completed 9 of 9`
- variant accept candidates: `4`
- repair required rows: `3`
- policy/native hold rows: `2`
- runtime replay after review: `NOT_RUN_AFTER_REVIEW`
- full375 collateral: `NO-GO`
- full_scan_approval: `false`
- completion criterion: `full375 collateral GO + full_scan path definition`
