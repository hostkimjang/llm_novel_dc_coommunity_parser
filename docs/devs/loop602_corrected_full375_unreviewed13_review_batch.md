# Loop602 corrected full375 unreviewed raw 13 blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `13`
- excluded post_id rows: `0`
- excluded P0 candidate rows: `0`

## 입력

- triage: `docs/devs/loop599_full375_after_residual46_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop598_remaining4_native_hold_projection_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `12`
- `wrong_work_title_flip`: `1`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop602 corrected full375 unreviewed raw 13 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11665124` `resolved_to_different_title` post=`난 시리즈 댓글은 정말 많이 달았었음` options: C1=화산귀환, C2=화산파(화산귀환)

### safe_loss_resolved_to_null
- `11661863` `resolved_to_null` post=`두개 써서 동시에 올리나보네` options: C1=저주받은 영애가 되었습니다
- `11671512` `resolved_to_null` post=`패러디 떡밥 하니까 이거 봐야하는데` options: C1=삼시세끼, 심아식당
- `11682749` `resolved_to_null` post=`TS주인공인데 힘 쎄지는 템플릿이 어디서 나왔냐고?` options: C1=주인공인데 주인공이 아님
- `11694035` `resolved_to_null` post=`아생갤) 가장 무서웠던 순간이` options: C1=시로코의 제멋대로 일상 단편선
- `11694041` `resolved_to_null` post=`격투천재 살짝 경녀감성임?` options: C1=격투 소설 엑스트라가 타격 천재임
- `11698859` `resolved_to_null` post=`귤부인 대롱대롱 좋았는데` options: C1=귤부인 대롱대롱
- `11698865` `resolved_to_null` post=`스바루는 6장이 ㄹㅇ개씹테토남` options: C1=나츠키 스바루/작중 행적/5~8장
- `11698870` `resolved_to_null` post=`인간실격이 살자엔딩이였나?` options: C1=인간실격

## Gate 해석

이 산출물은 Loop602 corrected full375 unreviewed raw 13를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
