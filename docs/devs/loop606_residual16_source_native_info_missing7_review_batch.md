# Loop606 residual16 source-native INFO_MISSING 7 blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `7`
- excluded post_id rows: `0`
- excluded P0 candidate rows: `0`

## 입력

- triage: `docs/devs/loop599_full375_after_residual46_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop605_residual24_candidate_set_projection_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `2`
- `unsafe_promotion_from_hold`: `1`
- `wrong_work_title_flip`: `4`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop606 residual16 source-native INFO_MISSING 7 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11661856` `resolved_to_different_title` post=`오늘에 맘마는~~~` options: C1=너랑은 절! 대! 안 사Kill거니까!, C2=너랑은 절! 대! 안 사갈거니까!
- `11665110` `resolved_to_different_title` post=`사이키델리아 읽었던 사람 있냐?` options: C1=낭만적인 초능력을 위하여, C2=사이키델리아
- `11682791` `resolved_to_different_title` post=`이거 진짜에요?` options: C1=시간을 달리는 소설가, C2=피아조아 <시간을 달리는 소설가>
- `11685994` `resolved_to_different_title` post=`념글 시발 외신소환 주문 뭐임...` options: C1=교황님 아하세요 마왕 들어 가요, C2=무한을 이해한 나는 외신의 사제가 되었습니다

### unsafe_promotion_from_hold
- `11694067` `null_to_resolved` post=`김괴라리) 그롱 이 개새끼 그냥 죽어랏` options: C1=괴담에 휘말렸다

### safe_loss_resolved_to_null
- `11681178` `resolved_to_null` post=`한겨울에 보일러 끄고 나가는걸 잊으면 벌어지는 일` options: C1=재벌가 차녀의 2회차 걸그룹
- `11687661` `resolved_to_null` post=`광고 도움 많이 된다` options: C1=약혼녀가 소천마였다

## Gate 해석

이 산출물은 Loop606 residual16 source-native INFO_MISSING 7를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
