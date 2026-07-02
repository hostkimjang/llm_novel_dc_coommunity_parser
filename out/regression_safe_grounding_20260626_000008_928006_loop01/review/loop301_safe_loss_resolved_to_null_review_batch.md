# Collateral P0 blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `147`

## 입력

- triage: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_collateral183_regression_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop49_regression_panel_replay_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `147`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 collateral183의 P0 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### safe_loss_resolved_to_null
- `11658615` `resolved_to_null` post=`좆 됐 다 ! !` options: C1=이거 럽코 빙의물인가요
- `11658620` `resolved_to_null` post=`럽코빙의 원래도 그렇게 대놓고 언급 안했는데` options: C1=이거 럽코 빙의물인가요
- `11660232` `resolved_to_null` post=`괴담텔 이번 전개는 괴담동이 살짝 생각나네` options: C1=괴담 동아리
- `11660237` `resolved_to_null` post=`테라포밍 볼만함?` options: C1=테라포밍
- `11660254` `resolved_to_null` post=`노피아 애니메이션은 뭐임?` options: C1=푸푸푸 랜드의 두가지 일상
- `11660257` `resolved_to_null` post=`암흑가보스<<이거 재밋네` options: C1=암흑가 보스요? 제가요?
- `11660258` `resolved_to_null` post=`괴담텔 아리야...` options: C1=괴담 호텔 탈출기
- `11660259` `resolved_to_null` post=`기계공주 이제 슬슬 갤에서 말한대로 가는건가` options: C1=헌터갤러리의 국가권력급 기계공주

## Gate 해석

대형 런은 background 감시로 내렸고, 이 산출물은 collateral183 P0를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
