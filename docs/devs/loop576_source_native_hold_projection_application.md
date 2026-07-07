# Source-native HOLD projection contract 적용

- application_id: `loop576_source_native_hold_projection_contract`
- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- projection_rows: `375`
- verdict_rows: `21`
- eligible_unsafe_promotion_rows: `4`
- outcome_counts: `{'applied_source_native_hold': 4}`
- applied_hold_rows: `4`
- skipped_rows: `0`

## 적용 행

- `11710044` `applied_source_native_hold` before=`퓨전 펑크 의 전생자` after_status=`promotion_blocked` verdict=`gacha_punk_alias_collision_current_option_misses_correct_work`
- `11657047` `applied_source_native_hold` before=`사이버펑크 베지테리언 매드니스` after_status=`promotion_blocked` verdict=`generic_idea_prompt_not_candidate_work_discussion`
- `11658621` `applied_source_native_hold` before=`무능한게 아니라 전설이였다고?` after_status=`promotion_blocked` verdict=`title_similarity_and_character_image_not_enough_for_publish`
- `11690855` `applied_source_native_hold` before=`[림버스] 혈귀를 미치게 하는 피를 가져버렸다.` after_status=`promotion_blocked` verdict=`nonwork_limbus_game_metrics_context_blocks_fanfic_title_promotion`

## 승인 경계

- Source-native HOLD 적용은 projection/static 계약 수렴이며 full_scan approval이 아니다.
- Public title은 제거하고 candidate ledger/trace에 보존한다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
