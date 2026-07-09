# loop626_loop623_current_search_non_ok_gate current search non-ok gate

## 결론

- gate: `NO-GO`
- source_rows: `141`
- non_ok_rows: `15`
- hard_replay_rows: `5`
- recovered_observation_rows: `10`
- status_counts: `{"MISSING": 4, "SEARCH_DEGRADED": 1, "SEARCH_DEGRADED_RECOVERED": 10}`
- hard_reason_counts: `{"search_degraded": 1, "search_health_missing": 4}`
- hard_post_ids: `[11660258, 11690841, 11694026, 11708453, 11710021]`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 해석

- `SEARCH_DEGRADED_RECOVERED`이고 unrecovered degraded가 `0`인 행은 recovered-only 관측으로 분리한다.
- `MISSING`, `SEARCH_DEGRADED`, unrecovered degraded가 남은 행은 runtime replay 대상이다.
- 이 current search gate는 full375 collateral GO나 full_scan approval이 아니다.

## Hard replay rows

- `11660258` status=`MISSING` reason=`search_health_missing` primary_action=`hold_for_search_health_missing` before=`괴담 호텔 탈출기` after=`None` post=`괴담텔 아리야...`
- `11690841` status=`MISSING` reason=`search_health_missing` primary_action=`hold_for_search_health_missing` before=`블루 아카이브` after=`None` post=`블아는 칸나 미만 잡`
- `11694026` status=`SEARCH_DEGRADED` reason=`search_degraded` primary_action=`hold_for_search_recovery_rerun` before=`괴담 호텔 탈출기` after=`None` post=`미로 방이 확실히 프로스페리티 테마긴 한듯`
- `11708453` status=`MISSING` reason=`search_health_missing` primary_action=`expected_fp_removal_exempt` before=`감옥학원에서 나만 힐링할거다` after=`None` post=`미츄리가 이불사 쓸 때 했던 모방이 딱 모범적임`
- `11710021` status=`MISSING` reason=`search_health_missing` primary_action=`expected_fp_removal_exempt` before=`무한의 마법사` after=`None` post=`무마 웹툰 보는데`

## Recovered-only observations

- `11660257` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11661856` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11665121` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11669924` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11669933` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11698870` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11710049` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11711606` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11716480` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`hold_for_search_recovery_rerun` unrecovered=`0`
- `11718097` status=`SEARCH_DEGRADED_RECOVERED` primary_action=`blind_judge_title_correctness` unrecovered=`0`
