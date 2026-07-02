# Collateral P0 blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `26`

## 입력

- triage: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_collateral183_regression_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop49_regression_panel_replay_result.json`

## Bucket

- `unsafe_promotion_from_hold`: `26`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 collateral183의 P0 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### unsafe_promotion_from_hold
- `11657046` `null_to_resolved` post=`근데 사실 마블이 히어로 대명사 된건 얼마 안되긴함` options: C1=[블루아카이브] 키보토스 속 슈퍼히어로가 되었다
- `11658621` `null_to_resolved` post=`아니 변명이 아니라 진짜였다고` options: C1=무능한게 아니라 전설이였다고?
- `11658637` `null_to_resolved` post=`재막아)영기는 진짜 답이 없구나` options: C1=일본 재벌집 막내아들
- `11658668` `null_to_resolved` post=`문피아에서는 수정하면 욕 처먹는거고` options: C1=전 버튜버가 하고 싶은데요
- `11660238` `null_to_resolved` post=`오늘 림조 한서진 청월한테 말하는 게 개웃기네` options: C1=무림마조
- `11668324` `null_to_resolved` post=`니생들이랑 김괴라리 장갤픽 아니였음?` options: C1=괴담에 휘말렸다
- `11669928` `null_to_resolved` post=`탑성좌애호 노벨피아 이거 연중했었네` options: C1=탑의 성좌들이 날 애호한다
- `11671490` `null_to_resolved` post=`림월드 << 마땅히 장갤러라면 한번쯤은 해야만함` options: C1=게임이 자꾸 사람을 구원함

## Gate 해석

대형 런은 background 감시로 내렸고, 이 산출물은 collateral183 P0를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
