# Feature Improvement TODO

검색 품질, slang DB 회수율, 대시보드/운영 UX처럼 사용자 체감 품질에 가까운 개선 항목을 관리한다.

## Current HEAD evidence refresh

- [ ] Loop455 character bridge runtime closure follow-up
  - 상태: targeted runtime `GO 1/1` / health `GO clean_completed_source` / publication contract `GO 0 violations` / search evidence `REVIEW search_degraded_observed` / stop-condition `GO 101->100 safe 0->1` / full375 `NOT_OPEN` / approval not open
  - 적용: `11669933`은 `중경계`, `서휼`, `해방상제` character/setting bridge로 `회귀수선전(回歸修仙傳)`에 safe-resolved됐다. 새 slang DB write-back, R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry는 없다.
  - 도메인 보정: `아생갤` 같은 `갤러리` 표면은 현실 DC 갤러리명만이 아니라 웹소설 내부 커뮤니티/갤러리 오마주형 제목 또는 약어일 수 있다. 이 정책은 shared work-bridge 경계로 유지한다.
  - 산출물: `docs/devs/loop_reports/LOOP_455_REPORT_20260705.md`, `docs/devs/loop455_11669933_hoegwi_character_bridge_runtime_20260705.json`, `docs/devs/loop455_11669933_hoegwi_character_bridge_data_analytics_artifact.json`.
  - 완료 기준: search degraded `unrecovered=0`와 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop452 known-alias runtime closure follow-up
  - 상태: targeted runtime `GO 1/1` / health `GO clean_completed_source` / search evidence `GO` / publication contract `GO 0 violations` / golden subset `PASS 1/1` / residual queue source baseline `105 -> 102` / known-alias `3 -> 0` / search recovery broader `P0_ROW_LEVEL_GO_ONLY` / full375 `NOT_OPEN` / approval not open
  - 적용: `11708443`은 `괴담출근 -> 괴담에 떨어져도 출근을 해야 하는구나`로 safe-resolved됐다. `SCP 재단`은 설정/배경 비교 단서, `인간추출기`는 작가/사용자 언급으로 처리했다. Loop450/451 stall 뒤 `heretic_url` official lock/budget으로 runtime row 생산을 확인했다.
  - 산출물: `docs/devs/loop_reports/LOOP_452_REPORT_20260705.md`, `docs/devs/loop452_11708443_goedam_commute_known_alias_runtime_20260705.json`, `docs/devs/loop452_11708443_goedam_commute_known_alias_data_analytics_artifact.json`.
  - 완료 기준: known-alias lane은 0이지만 full375 approval은 아니다. 다음은 residual `REPROCESS 74 / HOLD 28`의 작은 lane, survey 136-error, collateral triage, 또는 native/source review로 전환한다.

- [ ] Loop449 known-alias runtime closure follow-up
  - 상태: targeted runtime `GO 1/1` / health `GO clean_completed_source` / search evidence `GO` / publication contract `GO 0 violations` / golden subset `PASS 1/1` / residual queue `105 -> 103` / search recovery broader `P0_ROW_LEVEL_GO_ONLY` / full375 `NOT_OPEN` / approval not open
  - 적용: `11706827`은 `기계공주 -> 헌터갤러리의 국가권력급 기계공주`로 safe-resolved됐다. `일상물/행복`은 별도 작품명이 아니라 작품 톤 cue로 처리했고, `갤러리` 표면은 현실 갤러리명만이 아니라 작품 안의 커뮤니티/갤러리 오마주 장치일 수 있음을 기록했다.
  - 산출물: `docs/devs/loop_reports/LOOP_449_REPORT_20260705.md`, `docs/devs/loop449_11706827_machine_princess_known_alias_runtime_20260705.json`, `docs/devs/loop449_11706827_machine_princess_known_alias_data_analytics_artifact.json`.
  - 완료 기준: 남은 `known_alias_runtime_replay_required=1`인 `11708443`을 단건 runtime 또는 계약 감사로 분리한다. 단건 GO와 queue delta를 full375 approval로 승격하지 않는다.

- [ ] Loop439-441 gallery-homage alias bridge follow-up
  - 상태: Loop441 targeted runtime `GO 1/1` / health `GO clean_completed_source` / search evidence `GO` / publication contract `GO 0 violations` / Loop439 golden18 current proof `NO-GO_RUNTIME_STALL` / golden expected-answer `NOT_REFRESHED_AFTER_LOOP441` / search recovery broader `P0_REVIEW` / full375 `NOT_OPEN` / approval not open
  - 적용: `아생갤`은 현실 갤러리명이 아니라 웹소설 `아카데미 생존 갤러리`의 작품 내부 갤러리/커뮤니티 오마주형 제목 약어일 수 있음을 반영했다. Arbiter와 pipeline의 curated alias bridge 술어를 통합해 official detail 또는 explicit alias relation이 수렴할 때만 작품 bridge를 연다.
  - 산출물: `docs/devs/loop_reports/LOOP_439_441_REPORT_20260705.md`, `docs/devs/loop439_441_gallery_homage_runtime_and_patch_20260705.json`, `docs/devs/loop439_441_gallery_homage_data_analytics_artifact.json`.
  - 완료 기준: Loop439 frontier `11698897` ordered flush/runtime stall 원인을 먼저 분리한다. 동일 stalled golden18 즉시 반복, full375 approval, hard-hold 완화는 금지한다.

- [ ] Loop437-438 gallery-homage candidate preservation follow-up
  - 상태: targeted runtime `GO 1/1` / health `GO clean_completed_source` / publication contract `GO 0 violations` / candidate preservation `GO_TARGETED` / public publish `BLOCKED_OK` / golden expected-answer `NOT_REFRESHED_AFTER_LOOP438` / search recovery broader `P0_REVIEW` / full375 `NOT_OPEN` / approval not open
  - 적용: `아생갤`은 현실 갤러리명만이 아니라 웹소설 `아카데미 생존 갤러리`의 작품 내부 갤러리/커뮤니티 오마주형 제목 약어일 수 있음을 반영했다. Official detail 없는 경우 publish는 막고 `publish_ledger`/`publish_contract_trace` 후보로만 보존한다.
  - 산출물: `docs/devs/loop_reports/LOOP_437_438_REPORT_20260705.md`, `docs/devs/loop437_438_gallery_homage_candidate_preservation_20260705.json`, `docs/devs/loop437_438_gallery_homage_candidate_preservation_data_analytics_artifact.json`.
  - 완료 기준: golden expected-answer refresh, broader search recovery, full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop435-436 runtime proof and gallery-title contract follow-up
  - 상태: Loop436 runtime `GO 18/18` / publication contract `GO 0 violations` / expected-answer `PASS 18/18` / post-patch gallery runtime `NOT_RUN` / search recovery `P0_REVIEW_SEARCH_DEGRADED` / golden shared collateral `NO-GO 6` / full375 `NOT_OPEN` / approval not open
  - 적용: `아생갤`은 현실 갤러리명이 아니라 `아카데미 생존 갤러리` 작품 약어가 될 수 있다는 도메인 계약을 반영했다. Official detail backed known title abbreviation은 작품 bridge로 허용하고, community-only/semantic no-work는 계속 차단한다.
  - 산출물: `docs/devs/loop_reports/LOOP_435_436_REPORT_20260705.md`, `docs/devs/loop435_436_runtime_gallery_contract_20260705.json`, `docs/devs/loop435_436_runtime_gallery_contract_data_analytics_artifact.json`.
  - 완료 기준: post-patch gallery contract를 runtime으로 재실증하고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop434 contextual exact-title official detail gap follow-up
  - 상태: code contract `GO_UNIT` / saved projection probe `GO` / runtime replay after patch `NOT_RUN` / expected-answer `NOT_REFRESHED inherited Loop433 NO-GO 17/18` / search recovery `P0_REVIEW_SEARCH_DEGRADED` / golden shared collateral raw `NO-GO inherited 5` / full375 `NOT_OPEN` / approval not open
  - 적용: `semantic_seed_review` 조기 종료 전에 저장 검색 카탈로그의 contextual exact-title 공식 detail URL gap을 확인하고, `adaptive_official_url`, `adaptive_author_bridge_official_url`만 intent-denied 상태에서 보존한다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_434_REPORT_20260705.md`, `docs/devs/loop434_contextual_exact_title_gap_contract_20260705.json`, `docs/devs/loop434_contextual_exact_title_gap_contract_data_analytics_artifact.json`.
  - 완료 기준: `11694019`를 current runtime 단건 또는 golden18 소규모 재실증으로 확인하고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop433 low-specificity batch alias contract follow-up
  - 상태: code contract `GO_UNIT` / projection publication contract `GO 0 violations` / projection expected-answer `NO-GO 17/18` / runtime replay after patch `NOT_RUN` / search recovery `P0_REVIEW_SEARCH_DEGRADED` / golden shared collateral raw `NO-GO 5` / full375 `NOT_OPEN` / approval not open
  - 적용: 짧은 batch alias 표면과 official detail URL만 있고 후보 title 직접 source 근거, direct work bridge, image/OCR work title, verified character link가 없으며 복수 후보/반론이 남은 public title publish를 차단했다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_433_REPORT_20260705.md`, `docs/devs/loop433_low_specificity_batch_alias_contract_20260705.json`, `docs/devs/loop433_low_specificity_batch_alias_contract_data_analytics_artifact.json`.
  - 완료 기준: 남은 `11694019`를 일반 술어 또는 source-native 검증으로 줄이고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop432 source-denial title-only contract follow-up
  - 상태: code contract `GO_UNIT` / projection publication contract `GO 0 violations` / projection expected-answer `NO-GO 16/18` / runtime replay after patch `NOT_RUN` / search recovery `P0_REVIEW_SEARCH_DEGRADED` / full375 `NOT_OPEN` / approval not open
  - 적용: source text가 특정 작품 사용/언급을 명시적으로 부인하는데 weak `verified_alias_title_only_publication`이 URL 없이 public title을 복구하는 경로를 차단했다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_432_REPORT_20260705.md`, `docs/devs/loop432_source_denial_title_only_contract_20260705.json`, `docs/devs/loop432_source_denial_title_only_contract_data_analytics_artifact.json`.
  - 완료 기준: `11705245`, `11694019`를 일반 술어 또는 source-native 검증으로 줄이고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop431 golden18 OCR publish contract follow-up
  - 상태: runtime `GO 18/18` / publication contract `GO 0 violations` / expected-answer `NO-GO 15/18` / search recovery `P0_REVIEW_SEARCH_DEGRADED` / golden shared collateral raw `NO-GO 6` / full375 `NOT_OPEN` / approval not open
  - 적용: URL 없는 direct-image/OCR public title을 공식 bridge 없이 publish하지 않도록 `expert_main.py` shared publication contract를 추가했다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_431_REPORT_20260705.md`, `docs/devs/loop431_golden18_ocr_contract_20260705.json`, `docs/devs/loop431_golden18_ocr_contract_data_analytics_artifact.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop431_golden18_after_ocr_contract_5150b13f_search_nonlight_result.json`.
  - 완료 기준: `11705245`, `11694019`, `11713212` 또는 survey 136-error anchor를 작은 단위로 줄이고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop430 OVERRIDE AUDIT 11708445 current HEAD follow-up
  - 상태: override audit `GO_ROW_CONTRACT_ONLY` / publication contract `GO 0 violations` / runtime replay `NOT_REQUIRED` / search recovery `P0_REVIEW_LIGHT_HEALTH_CAVEAT` / golden shared collateral `NO-GO 2` / full375 `NOT_OPEN` / approval not open
  - 적용: current HEAD `43fdcd87`에서 completed-source single row를 publication contract 감사로 재검산했다. 코드 변경, R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_430_REPORT_20260704.md`, `docs/devs/loop430_override_audit_11708445_current_head_20260704.json`, `docs/devs/loop430_override_audit_data_analytics_artifact.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop430_override_audit_11708445_current_head_43fdcd87_publication_contract.json`.
  - 완료 기준: `11708445`는 active queue에 재등재하지 않는다. 다음 진행은 docs-only 반복이 아니라 survey 136-error `wrong_work 27` / `recall_miss 49` 또는 collateral 후보 source-native 검증으로 전환한다.

- [ ] Loop429 golden18 after Loop428 follow-up
  - 상태: runtime `GO 18/18` / expected-answer `PASS 18/18` / publication contract `GO 0 violations` / search recovery `P0_REVIEW_LIGHT_HEALTH_CAVEAT` / golden shared collateral `NO-GO 2` / full375 `NOT_OPEN` / approval not open
  - 적용: 신규 대형 런 없이 Loop428 커밋 `9a0ca3af`의 golden18 단일 runtime을 완료했다. 코드 변경, R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_429_REPORT_20260704.md`, `docs/devs/loop429_golden18_after_loop428_20260704.json`, `docs/devs/loop429_golden18_data_analytics_artifact.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop429_golden18_after_loop428_9a0ca3af_search_nonlight_result.json`.
  - 완료 기준: search degraded `unrecovered=0`와 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다. Collateral 후보 `11663521`, `11685994`는 source-native 확인 대상으로 유지한다.

- [ ] Loop416 11698897 visual contextual alias release follow-up
  - 상태: targeted runtime `GO 1/1` / targeted expected-answer `GO_TARGETED_SAFE_RESOLVED` / publication contract `GO 0 violations` / search row-level `GO` / broader search recovery `P0_REVIEW` / golden expected-answer `NOT_REFRESHED inherited Loop413 16/18` / full375 `NOT_OPEN` / approval not open
  - 적용: 기존 visual/bracket official-detail release context를 title-led shared alias candidate selection에 연결했다. `랫따싶` registry alias, R1 hardcoded cue/title list, `post_id` 예외, slang DB write-back은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_416_REPORT_20260704.md`, `docs/devs/loop416_11698897_visual_contextual_alias_release_20260704.json`, `docs/devs/loop416_visual_contextual_alias_release_data_analytics_artifact.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop416_11698897_visual_contextual_alias_current_candidate_release_result.json`.
  - 완료 기준: `11698880` positive unresolved 또는 survey 136-error anchor를 작은 단위로 줄이고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop413 runtime proof / OVERRIDE AUDIT / survey anchor follow-up
  - 상태: golden18 runtime `GO 18/18` / expected-answer `NO-GO 16/18` / golden shared collateral `NO-GO 9` / publication contract `GO 0 violations` / override audit `GO_ROW_CONTRACT_ONLY` / search recovery `P0_REVIEW_DEGRADED` / full375 `NOT_OPEN` / approval not open
  - 적용: 신규 대형 런 없이 current HEAD `d95f1a57` golden18 단일 search 포함 non-light 런으로 row 생산을 먼저 실증했다. 코드 변경과 R1 hardcoded cue/title list 확장은 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_413_REPORT_20260704.md`, `docs/devs/loop413_runtime_override_survey_realign_20260704.json`, `docs/devs/loop413_runtime_data_analytics_artifact.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop413_golden18_current_d95f1a57_runtime_proof_search_nonlight_result.json`.
  - 완료 기준: `11698897` wrong publish와 `11698880` positive unresolved를 일반 술어/contract 또는 source-native 판정으로 줄이고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다. 다음 anchor는 survey 136-error의 `wrong_work 27` / `recall_miss 49`다.

- [ ] Loop412 11698880 title-led candidate HOLD follow-up
  - 상태: targeted runtime `GO 1/1` / wrong publish closure `GO_TARGETED` / correct candidate preservation `GO_CANDIDATE_ONLY` / expected-answer `NO-GO inherited Loop411 17/18` / golden shared collateral `NO-GO inherited Loop411 6` / search recovery `P0_ROW_LEVEL_EVIDENCE_WITH_PREFLIGHT_LIGHT_CAVEAT` / full375 `NOT_OPEN` / approval not open
  - 적용: title-led public gate가 `_has_unresolved_body_compound_character_anchor(...)`를 경유하고, promotion-blocked scrub이 stale `candidate_ledger.title_candidates` 요약에도 blocked title을 보존한다. R1 hardcoded cue/title list와 `post_id` 예외는 추가하지 않았다.
  - 산출물: `docs/devs/loop_reports/LOOP_412_REPORT_20260704.md`, `docs/devs/loop412_11698880_title_led_candidate_hold_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop412_11698880_title_led_unresolved_body_anchor_gate_result.json`.
  - 완료 기준: ledger 요약 보정이 실제 직렬화에 반영되는지 단건/projection으로 확인하고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop411 golden18 title-led Series probe follow-up
  - 상태: golden18 runtime `GO 18/18` / expected-answer `NO-GO 17/18` / golden shared collateral `NO-GO 6` / search recovery `P0_REVIEW_TIMEOUT_DEGRADED` / full375 `NOT_OPEN` / approval not open
  - 적용: `11668307` mixed-input에서 `시리즈 빛세구 작가` official detail probe를 budget 안에 보존해 `빚을 져서라도 세상은 구해야 할 거 아니야`를 회복했다. R1 hardcoded cue/title list와 `post_id` 예외는 추가하지 않았다.
  - 산출물: `docs/devs/loop_reports/LOOP_411_REPORT_20260704.md`, `docs/devs/loop411_title_led_series_probe_runtime_20260704.json`, `docs/devs/loop411_golden18_runtime_data_analytics_artifact.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop411_golden18_current_316a6148_title_led_series_probe_search_nonlight_result.json`.
  - 완료 기준: `11698880` wrong title을 일반 술어/후보 보존으로 줄이고, search degraded `unrecovered=0` 및 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop396-398 current-head golden18 stall / `11700470` single-row flush follow-up
  - 상태: current golden18 runtime `NO-GO_RUNTIME_STALL 17/18 completed, 12 flushed` / blocker `11700470` / targeted single row `GO_SINGLE_ROW_FLUSH` / golden18 after patch `NOT_PROVEN` / search recovery `P0_SEARCH_BLIND_CONDITIONAL` / full375 `NOT_OPEN` / approval not open
  - 적용: image/OCR scene HOLD에서 local title bridge 없는 late canonical rescue scan을 스킵한다. 검색 공식 후보와 non-promotable OCR 제목 조각만으로는 direct title support를 열지 않는다.
  - 산출물: `docs/devs/loop_reports/LOOP_396_398_REPORT_20260704.md`, `docs/devs/loop396_398_runtime_stall_and_local_bridge_20260704.json`, `src/llm_batch/agentic_pipeline.py`, `tests/test_title_lead_search_inferred_guard.py`.
  - 완료 기준: current-code golden18이 18/18 row를 flush하고, expected-answer/search/full375 gate를 별도로 통과하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop390 verified-alias competition contract follow-up
  - 상태: code contract `GO_UNIT` / direct resync `GO_DRY` / runtime replay after patch `NOT_RUN_AFTER_PATCH` / expected-answer inherited `NO-GO 15/18` / search recovery `P0_SEARCH_BLIND_CONDITIONAL` / full375 `NOT_OPEN` / approval not open
  - 적용: `11698880`의 title-led `아생갤 -> 아카데미 생존 갤러리` publish가 competing verified alias work `가챠펑크 -> 가챠 중독자의 퓨전펑크 생활`을 덮지 못하도록 final publication ledger 계약을 보강했다.
  - 산출물: `docs/devs/loop_reports/LOOP_390_REPORT_20260704.md`, `docs/devs/loop390_verified_alias_competition_contract_20260704.json`, `expert_main.py`, `tests/test_expert_main_comment_metadata.py`.
  - 완료 기준: current-code runtime에서 `11698880`이 실제 row로 `가챠 중독자의 퓨전펑크 생활` 또는 안전한 candidate-only로 수렴하고, search degraded와 full375 collateral gate가 별도로 닫히기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop389 golden18 runtime after Loop388
  - 상태: golden18 runtime `GO 18/18` / expected-answer `NO-GO 15/18` / search evidence `REVIEW_search_degraded_observed` / golden shared collateral `NO-GO 3` / full375 `NOT_OPEN` / approval not open
  - 적용: 신규 대형 런 없이 현 HEAD `6349197e`의 golden18 단일 search non-light runtime을 완료했다. watchdog/stall 우회는 실제 row를 내는 것으로 실증됐지만 semantic gate는 닫히지 않았다.
  - 산출물: `docs/devs/loop_reports/LOOP_389_REPORT_20260704.md`, `docs/devs/loop389_golden18_after_loop388_runtime_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop389_golden18_after_loop388_6349197e_search_nonlight_result.json`.
  - 완료 기준: `11698880`, `11698897`, `11700470`을 R1 hardcoded cue 없이 줄이고, search degraded `unrecovered=0`과 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [x] Loop388 author_bridge exact official detail runtime closure
  - 상태: row-level runtime `GO 1/1` / row-level semantic `GO` / broader search recovery `P0_SEARCH_BLIND_CONDITIONAL` / full375 `NOT_OPEN` / approval not open
  - 적용: author_bridge title hint마다 official detail URL의 page title exact match를 검사한다. 다른 작품의 official detail URL이 있어도 대상 제목의 exact official detail이 없으면 `no_official_url` gap을 유지한다.
  - 산출물: `docs/devs/loop_reports/LOOP_388_REPORT_20260704.md`, `docs/devs/loop388_author_bridge_exact_gap_runtime_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop388_11694019_author_bridge_exact_gap_search_nonlight_result.json`.
  - 완료 기준: `11694019` 단건 runtime에서 `official_title=이세계에서 사이비로 살아남기`, `official_url=https://novelpia.com/novel/181771`, `candidate_ledger_status=safe_resolved`, `queries=8/degraded=0/unrecovered=0`을 확인했다. 이 완료는 단건 회복이며 full375/golden18/bounded/N>=5를 대체하지 않는다.

- [x] Loop386 author_bridge search recovery follow-up
  - 상태: code contract `GO_UNIT` / Loop388 runtime row closure `GO` / broader search recovery `P0_SEARCH_BLIND_CONDITIONAL` / approval not open
  - 적용: `11694019`에서 author_bridge가 `미츄리` + `이세계에서 사이비로 살아남기`를 잡으면 broad site query보다 먼저 `미츄리 이세계에서 사이비로 살아남기` 공식 detail probe를 실행한다.
  - 산출물: `docs/devs/loop_reports/LOOP_386_REPORT_20260704.md`, `docs/devs/loop386_author_bridge_search_recovery_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop386_11694019_official_gap_probe.json`.
  - 완료 기준: Loop388 단건 runtime으로 candidate evidence 개선을 확인했다. 단 broader search recovery, full375 collateral, golden18 전체, N>=5 flip probe는 아직 별도 open이다.

- [ ] Loop385 runtime proof / locked candidate follow-up
  - 상태: golden18 runtime `GO 18/18` / runtime expected `NO-GO 15/18` / projection expected `NO-GO 16/18` / golden shared collateral projection `NO-GO 4` / search recovery `P0_UNRECOVERED_DEGRADED_OPEN` / approval not open
  - 적용: `11698880`에서 URL 없는 title-only `아카데미 생존 갤러리` overwrite를 locked official-detail 후보 `가챠 중독자의 퓨전펑크 생활`로 되돌리는 publication contract를 추가했다.
  - 산출물: `docs/devs/loop_reports/LOOP_385_REPORT_20260704.md`, `docs/devs/loop385_golden18_runtime_after_loop384_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop385_current_patch_postprocess_resync_audit.json`.
  - 완료 기준: `11668307`/`11700470`을 hardcoded cue 없이 줄이거나 search degraded `unrecovered=0`을 별도 증명하고, full375 collateral 전수 gate가 닫히기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop384 postprocess-only golden pass follow-up
  - 상태: current-code postprocess golden audit `PASS 18/18` / runtime replay after patch `NOT_RUN_POSTPROCESS_ONLY` / golden shared collateral `NO-GO 6` / search recovery `P0_PARTIAL_RUNTIME_GO` / approval not open
  - 적용: `_sync_allowed_publication_result_contract(..., post_title=post_title)` 배선으로 runtime-like payload의 `11663540` OCR 오독이 `전 버튜버가 하고 싶은데요`로 수렴한다. `11663521`은 public title `null`을 유지한 evidence-preserved unresolved 통과다.
  - 산출물: `docs/devs/loop_reports/LOOP_384_REPORT_20260704.md`, `docs/devs/loop384_postprocess_golden_pass_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop384_current_patch_loop382_analysis_postprocess_resync_audit.json`.
  - 완료 기준: current-code golden18 runtime replay 또는 search degraded 100% 복구와 full375 collateral 전수 gate가 별도로 닫히기 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop383 remaining golden expected/search follow-up
  - 상태: current worktree golden18 runtime은 Loop382 기준 `GO 18/18` / Loop383 targeted dry projection `NO-GO 17/18` / runtime after patch `NOT_RUN` / search recovery `P0_PARTIAL_RUNTIME_GO` / approval not open
  - 적용: `11663521` wrong publish `성기사는 버생을 산다`는 dry postprocess에서 `null / promotion_blocked`로 차단됐지만 positive expected는 unresolved다. `11663540` OCR 오독 `전 버디가 하고 싶은데요`는 `전 버튜버가 하고 싶은데요`로 canonicalize된다.
  - 산출물: `docs/devs/loop_reports/LOOP_383_REPORT_20260704.md`, `docs/devs/loop383_targeted_publication_contract_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop383_current_patch_loop382_targeted_postprocess_dry_audit.json`.
  - 완료 기준: `11663521` positive expected 미해소를 source-native/search 또는 일반 술어로 줄이고, current-code golden18 runtime replay 또는 search degraded 100% 복구 및 full375 collateral 전수 gate 전까지 approval과 hard-hold 완화를 열지 않는다.

- [ ] Loop365 remaining golden expected/search follow-up
  - 상태: `11713222` source-native expected correction 완료 / golden expected `NO-GO 14/18` / search recovery `P0_OPEN` / approval not open
  - 적용: 본문 `잘생인방`을 current work `잘생기면 편해지는 인방 생활`로, 댓글 `잘생인편`을 previous/mentioned work `잘생기면 인생이 편하다`로 판정해 `golden_manifest.json` expected를 교정했다.
  - 산출물: `docs/devs/loop_reports/LOOP_365_REPORT_20260703.md`, `docs/devs/loop365_11713222_blind_source_native_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop365_11713222_blind_source_native_review.json`.
  - 완료 기준: 남은 실패 `11698897`, `11694019`, `11700470`, `11698880`을 일반 술어/계약 또는 source-native 판정으로 좁히고, search degraded 복구 전 hard-hold 완화와 approval을 열지 않는다.

- [ ] Loop358 LLM stream stall guard follow-up
  - 상태: runtime_aborted_llm_stream_stall / search_go_single_probe / residual_queue_105 / approval_not_open
  - 적용: `11666713` image-free 단건 replay에서 Gatekeeper first-token stall을 분리하고, stream first-token/idle timeout guard를 추가했다.
  - 산출물: `docs/devs/loop_reports/LOOP_358_REPORT_20260703.md`, `docs/devs/loop358_llm_stream_timeout_guard_20260703.json`, `docs/devs/loop358_llm_stream_stall_data_analytics_artifact.json`.
  - 완료 기준: timeout env를 켠 follow-up replay에서 stuck stream이 explicit failure 또는 flushed row로 수렴하고, 그 결과를 residual queue/semantic gate와 분리해 기록한다. 완료 전 hard-hold 완화와 residual closure는 금지한다.

- [ ] Loop357 known-alias comparison boundary follow-up
  - 상태: code_contract_go_unit / runtime_not_run_after_patch / residual_queue_105 / search_recovery_p0_open
  - 적용: `괴담텔 ... 괴담동이 생각나네` 같은 비교문에서 뒤쪽 comparison alias가 current-work anchor로 release되지 않도록 보정했다.
  - 산출물: `docs/devs/loop_reports/LOOP_357_REPORT_20260703.md`, `docs/devs/loop357_known_alias_comparison_boundary_20260703.json`.
  - 완료 기준: `known_alias_runtime_replay_required=3`이 search 포함 non-light runtime에서 flush되고, actionable queue 감소와 동일 packet `safe_resolved` 단조 비감소가 함께 확인돼야 한다. 그 전까지 residual `105`, approval not open, `promotion_blocked=search-blind conditional`을 유지한다.

- [ ] Loop356 current HEAD background dispatch follow-up
  - 상태: current_head_4ebe824b / background_launched / approval_not_open / search_recovery_p0_open
  - 적용: safe-loss N5, full375, bounded1200 completed-source, golden18을 search 포함 non-light로 새 발주했다.
  - 산출물: `docs/devs/loop_reports/LOOP_356_REPORT_20260703.md`, `docs/devs/loop356_current_head_background_dispatch_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop356_search_shard_audit_44_before_current_head_dispatch.json`.
  - 완료 기준: N5 `15/15`와 analyze, golden18 `18/18` audit, full375 `375/375` collateral diff, bounded completion/search degraded audit를 모두 확인한다. 완료 전 stale flip/golden/full375 대체와 hard-hold 완화는 금지한다.

- [ ] Loop355 wrong-work alias contract follow-up
  - 상태: contract_go_unit_only / runtime_not_run_after_patch / residual_queue_105 / search_recovery_p0_open
  - 적용: `11698890`, `11700500`, `11705252`를 alias+work-cue+official detail recall 계약으로 보강했다.
  - 산출물: `docs/devs/loop_reports/LOOP_355_REPORT_20260703.md`, `docs/devs/loop355_wrong_work_alias_contract_20260703.json`.
  - 완료 기준: Loop350 LLM/VLM stall 원인을 분리한 뒤 post-patch non-light replay로 5행 packet 또는 row-level runtime closure를 확인한다. 그 전까지 residual `105`, approval not open 유지.

- [ ] Loop354 current residual forced action lane follow-up
  - 상태: residual_queue_105 / forced_action_lane_not_approval / search_recovery_p0_open
  - 적용: 대형 forced non-light N5/full375/bounded1200/golden18은 background 감시로 두고 current residual `105`를 action group으로 재정렬했다.
  - 현재 큐: residual `105`, `REPROCESS=77`, `HOLD=28`, `repair_safe_loss=72`, `repair_after_wrong_work=5`, `known_alias_runtime_replay_required=3`, `native_image_or_source_review_required=14`.
  - 산출물: `docs/devs/loop_reports/LOOP_354_REPORT_20260703.md`, `docs/devs/loop354_current_residual_forced_action_lane_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop354_current_residual_forced_action_lane.json`.
  - 완료 기준: `repair_after_wrong_work=5` 또는 `known_alias_runtime_replay_required=3`에서 blind/source-native/runtime evidence로 추가 queue 감소를 만든다. N5/golden/full375/bounded 완료 전 approval과 hard-hold 완화는 금지한다.

- [ ] Loop353 11708470 non-light row closure follow-up
  - 상태: residual_queue_105 / row_closure_not_approval / search_recovery_p0_open
  - 적용: Loop324 non-light runtime에서 clean recovery가 확인된 `11708470`만 Loop352 residual `106`에서 제외했다.
  - 현재 큐: residual `105`, `REPROCESS=77`, `HOLD=28`, `repair_safe_loss=72`, `repair_after_wrong_work=5`, `known_alias_runtime_replay_required=3`, `native_image_or_source_review_required=14`.
  - 산출물: `docs/devs/loop_reports/LOOP_353_REPORT_20260703.md`, `docs/devs/loop353_11708470_nonlight_row_closure_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop353_current_residual_action_queue_after_11708470_nonlight_runtime_closure.json`.
  - 완료 기준: Loop324 packet `NO-GO` 행은 제외하지 않는다. 다음 small loop도 search degraded 없는 row-level runtime/contract 근거만 사용한다.

- [ ] Loop352 unsafe-promotion contract exclusion follow-up
  - 상태: residual_queue_106 / queue_delta_not_approval / search_recovery_p0_open
  - 적용: Loop349 current residual `120`에서 Loop300/309 contract replay로 이미 `promotion_blocked=14/14` 수렴한 `repair_unsafe_promotion=14`를 제외했다.
  - 현재 큐: Loop353 이후 residual `105`, `REPROCESS=77`, `HOLD=28`, `repair_safe_loss=72`, `repair_after_wrong_work=5`, `known_alias_runtime_replay_required=3`, `native_image_or_source_review_required=14`.
  - 산출물: `docs/devs/loop_reports/LOOP_352_REPORT_20260703.md`, `docs/devs/loop352_unsafe_promotion_contract_exclusion_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop352_current_residual_action_queue_after_unsafe_promotion_contract_exclusion.json`.
  - 완료 기준: 다음 small loop에서 `repair_safe_loss=72` 또는 `OVERRIDE AUDIT(LLM=False -> final=True)` blind/source-native 검증으로 추가 queue 감소를 만든다. search degraded 복구 전 approval과 hard-hold 완화는 금지한다.

- [ ] Loop351 stale evidence/background audit follow-up
  - 상태: stale_evidence_refresh_incomplete / search_recovery_p0_open / approval_not_open
  - 감사: Loop348 forced non-light N5/full375/bounded1200/golden18은 발주됐지만 Loop351 시점 N5 first `1/0/0/0/0`, full375 `375/1/1/0/0`, bounded `1200/4/0/4/0`, golden18 `18/1/1/0/0`이다.
  - 추적: golden files와 bootstrap/golden 도구는 git 추적 중이며, search recovery probe `tools/run_search_query_expansion_probe.py`를 추적 예외에 추가했다.
  - active 기준: Loop352 residual `106`, `REPROCESS=78`, `HOLD=28`.
  - 완료 기준: N5 `15/15`, golden18 `18/18`, full375/bounded completion, search degraded `unrecovered=0` audit 전까지 stale evidence를 대체하지 않는다.

- [ ] Loop347 remaining known-alias contract/stall follow-up
  - 상태: runtime_aborted_vlm_stall resolved_partially_by_loop448_449 / code_contract_go_unit / approval_not_open
  - 대상: residual `known_alias_runtime_replay_required=1` (`11708443`). `11714907`은 Loop448, `11706827`은 Loop449 단건 runtime으로 expected-title resolved됐다.
  - runtime: run `20260703_131039_800703`, search health `2/2 OK`, manifest `0/0/0/0`, VLM chunk 이후 결과 없음.
  - 적용: `기계공주` 일상물 cue와 `아생갤` 작가/정실 character-relation cue를 shared curated-alias work cue 계약으로 고정했다.
  - 보호: 추천 요청/탐색 hard-hold는 유지하며 `11714892` negated recommendation 계약을 PASS로 확인했다.
  - 산출물: `docs/devs/loop_reports/LOOP_347_REPORT_20260703.md`, `docs/devs/loop347_known_alias_remaining3_contract_and_stall_20260703.json`.
  - 완료 기준: 남은 `11708443`이 runtime에서 flush되어 safe_resolved 단조 비감소와 actionable queue 감소를 만족해야 한다. 그 전까지 search recovery `P0 / ROW_LEVEL_GO_ONLY`, full375 `NOT_OPEN`, approval not open 유지.

- [ ] Loop346 current residual queue follow-up
  - 상태: current_queue_rebased_123 / validation_issue_0 / approval_not_open
  - 적용: `tools/split_collateral_action_queue.py --exclude-post-ids`로 Loop343/344에서 닫힌 `11703624`, `11705230`, `11705251`을 제외했다.
  - 현재 큐: residual `123`, `REPROCESS=92`, `HOLD=31`, `repair_safe_loss=73`, `repair_unsafe_promotion=14`, `native_image_or_source_review_required=14`, `known_alias_runtime_replay_required=3`.
  - 산출물: `docs/devs/loop_reports/LOOP_346_REPORT_20260703.md`, `docs/devs/loop346_current_residual_queue_rebase_20260703.json`.
  - 완료 기준: current residual 123에서 search 상태와 독립적인 source-native/policy/contract lane을 계속 줄이고, bounded completion audit와 search degraded 복구를 별도로 닫는다.

- [ ] Loop345 bounded1200 search-budget follow-up
  - 상태: launched_background / current_head_4f1a488e / search_non_light / approval_not_open
  - 발주: run `20260703_125052_015965`, PID `135528`, completed-source bounded `1200`건, image posts `700`, parallel `6`.
  - shard: `mcp-bridge-37..44`, host `3369-3376`, health `ok=8/8`, search 포함 non-light.
  - stale 구분: Loop339 full375/bounded/golden/N5는 HEAD `77bdbe48` 증거라 current patch approval 근거가 아니다.
  - 산출물: `docs/devs/loop_reports/LOOP_345_REPORT_20260703.md`, `docs/devs/loop345_search_budget_bounded_dispatch_20260703.json`.
  - 완료 기준: bounded manifest completion, search degraded/unrecovered degraded audit, collateral diff, override flip row blind judge 검증. 완료 전 `promotion_blocked`는 `search-blind conditional`로 유지한다.

- [ ] Loop336 `11705250` post-patch replay follow-up
  - 상태: row_public_contract_recovered / publication_convergence_go / search_degraded_review / approval_not_open
  - 결과: run `20260703_051443_582943`에서 `official_title=심해의 마법사`, `heretic_url=https://m.munpia.com/novel/detail/483667`, `safe_resolved`, `promotion_blocked=false`로 복구됐다.
  - caveat: `SEARCH_DEGRADED`, queries `15`, degraded `15`, upstream zero `10`, audit blocker `search_degraded_observed`.
  - manifest 보정: `expert_main.py` 순차 모드 manifest에 `large_run_complete`, `partial_flush_gap`, `ordered_flush_blocked`, `completed_subset_*` 필드를 추가했다. 현재 Loop336 artifact는 패치 전 manifest라 completion field caveat 유지.
  - 산출물: `docs/devs/loop_reports/LOOP_336_REPORT_20260703.md`, `docs/devs/loop336_post_patch_runtime_replay_20260703.json`.
  - 완료 기준: search degraded 복구, 다음 순차 단건 manifest completion fields 확인, full375/bounded/golden/N5 완료 감사.

- [ ] Loop335 `11705250` consumption title-lead alias repair follow-up
  - 상태: code_contract_go_unit_and_broader_title_lead / post_patch_runtime_recovered_loop336 / approval_not_open
  - 발견: `심해법사 묵혀둔거...`의 첫 토큰 약칭이 title-lead alias 추출에서 빠져 `심해의 마법사`가 false negative로 demote됐다.
  - 적용: consumption cue가 붙은 제목 첫 토큰을 title-lead alias로 보존하고, semantic no-work 기본 차단은 유지한 채 verified batch alias release context만 열었다.
  - 검증: py_compile PASS, targeted test PASS, work-bridge contract `3` tests PASS, title-lead suite `185` tests PASS.
  - 산출물: `docs/devs/loop_reports/LOOP_335_REPORT_20260703.md`, `docs/devs/loop335_consumption_title_lead_alias_repair_20260703.json`.
  - 완료 기준: Loop336에서 row public contract는 복구됐지만 search degraded가 남았으므로, search recovery와 broader gates가 닫힐 때까지 approval로 쓰지 않는다.

- [ ] Loop332 collateral183 combined action queue follow-up
  - 상태: source_native_queue_complete_183_of_183 / gate_accounting_wired_loop333 / repair_queue_open / approval_not_open
  - 발견: `collateral183` P0 verdict가 `wrong_work_title_flip=10`, `unsafe_promotion_from_hold=26`, `safe_loss_resolved_to_null=147`로 나뉘어 있었고, gate accounting이 바로 쓸 수 있는 합산 queue가 없었다.
  - 적용: `tools/summarize_collateral_review_verdicts.py`에 다중 `--verdicts` 입력과 `queue_transition`, `queue_by_bucket` summary를 추가했다.
  - 현재 counts: `ACCEPT=57`, `REPROCESS=95`, `HOLD=31`, validation issues `0`, 잔여 action queue `126`.
  - Loop333 배선: always-on collateral gate에서 raw `183` 중 exclusion candidate `57`을 차감해 adjusted `126`을 남긴다.
  - 산출물: `docs/devs/loop_reports/LOOP_332_REPORT_20260703.md`, `docs/devs/loop_reports/LOOP_333_REPORT_20260703.md`, `docs/devs/loop333_collateral_gate_accounting_20260703.json`.
  - 완료 기준: adjusted residual `126`을 `REPROCESS=95`, `HOLD=31` targeted repair/runtime/policy/native review 큐로 분해하고, full375/bounded/golden/search gate를 current HEAD 완료 증거로 재평가한다.

- [ ] Loop331 partial runtime NO-GO follow-up
  - 상태: evidence_refreshed / approval_no_go / background_monitoring
  - 발견: post-patch `11668283`은 current HEAD search non-light에서 완료됐지만 `official_title=null`, `blocked_official_title=중세`, `promotion_blocked`, `title_resolution_state=adjacent`, `SEARCH_DEGRADED`로 수렴 실패했다.
  - 최신 대형 런 snapshot: full375 `25/21/4/0`, bounded1200 `37/34/3/0`, golden18 `5/5/0/0`, safe-loss N5 first-repeat `3`개, override `11705250` `1/1/0/0`.
  - 산출물: `docs/devs/loop_reports/LOOP_331_REPORT_20260703.md`, `docs/devs/loop331_current_head_partial_runtime_no_go_20260703.json`.
  - Loop334: `11705250` blind/source-native verdict는 `REPROCESS_FALSE_NEGATIVE / public leak 없음 / SEARCH_DEGRADED`로 닫았다.
  - Loop335: `11705250` relation/title-lead overblock은 code contract로 수리했지만 post-patch runtime replay는 아직 `NOT_RUN`이다.
  - 완료 기준: search degraded 복구, N5 `15/15`, golden18 `18/18`, full375/bounded 완료 감사, `11705250` post-patch replay. 완료 전 `promotion_blocked`와 null demotion은 `search-blind conditional`로 태깅한다.

## Curated alias publication convergence

- [ ] Loop328 known-abbreviation exact-title public guard follow-up
  - 상태: code_contract_go_unit / runtime_reproduced_overblock / post_patch_runtime_not_run / approval_not_open
  - 발견: `11668283` non-light replay는 정답 제목 후보를 회복했지만 final public title은 `weak_source_exact_title_without_official_support_public_title_bridge`로 차단됐다.
  - 적용: `known_abbreviation_title_guard:*` current-work scope, exact title surface, `row_discusses_work_as_work`, `scope_current_work`, `work_consumption_marker`, title/body/search context가 모두 있을 때만 weak-source guard를 면제한다.
  - 보호: exact title surface라도 작품 소비 marker가 없으면 계속 hold한다.
  - 산출물: `docs/devs/loop_reports/LOOP_328_REPORT_20260703.md`, `docs/devs/loop328_known_abbreviation_exact_title_guard_20260703.json`
  - 완료 기준: guard patch 후 `11668283` targeted runtime replay, Loop326 full375/bounded/golden18 완료, collateral compare에서 순회귀 0 확인. search degraded가 남으면 approval 금지.

- [ ] Loop327 middle-age-modern alias repair follow-up
  - 상태: row_contract_go_unit_repair / runtime_not_run_after_patch / approval_not_open
  - 발견: `11668283 / 게임 마인드의 중세 현대인 좋았다...`는 최신 light run에서 `off_topic / context_only / official_title=null`로 떨어졌지만, 과거 독립 run은 official detail URL이 붙은 resolved work로 판정했다.
  - 적용: `중세현대인`, `중세 현대인`, `게임마인드중세`, `게임마인드 중세 현대인`을 curated alias로 추가하고, `좋았다` 계열 감상 cue를 shared alias gate에 추가했다.
  - 보호: 단순 `중세 현대인` 단어 언급만 있고 작품 소비 cue가 없는 행은 release하지 않는다.
  - 산출물: `docs/devs/loop_reports/LOOP_327_REPORT_20260703.md`, `docs/devs/loop327_override_audit_middle_age_modern_alias_20260703.json`
  - 완료 기준: patch 후 `11668283` targeted runtime replay, Loop326 full375/bounded/golden18 완료, collateral compare에서 순회귀 0 확인. search degraded가 남으면 approval 금지.

- [ ] Loop325 curated alias work-cue contract follow-up
  - 상태: code_contract_go_unit_and_broader_214 / runtime_not_run_current_patch / approval_not_open
  - 발견: Loop324에서 `11708443 / 괴담출근`은 verifier/relation 단계의 작품 근거가 있었지만 Arbiter curated-alias null guard가 작품 담론 cue를 보지 못해 `promotion_blocked`로 회귀했다.
  - 적용: `_has_curated_alias_work_discussion_cue`를 `utils`에 추가하고 Pipeline known-title abbreviation bridge와 Arbiter contextual work anchor가 함께 사용하게 했다.
  - 보호: `괴담텔 ... 괴담동` 인접 비교 음성 control은 계속 blocked다.
  - 산출물: `docs/devs/loop_reports/LOOP_325_REPORT_20260703.md`, `docs/devs/loop325_curated_alias_work_cue_contract_20260703.json`
  - 완료 기준: current patch 기준 Loop322 alias packet targeted replay, full375/bounded current-head replay, collateral compare에서 순회귀 0 확인. search degraded가 남으면 approval 금지.

## Override audit follow-up

- [ ] `LLM=False->final=True` override audit blind judge expansion
  - 상태: Loop319 single_row_checked / Loop327 false_negative_unit_repaired / Loop334 current_head_false_negative_found / approval_not_open
  - 발견: `11708445`는 worker log에 override event가 있었지만 최종 public contract는 `candidate_only / promotion_blocked / publish_allowed=false`로 수렴했다. Loop327은 `11668283` false negative를 unit repair로 전환했다.
  - Loop330: old light `20260702_065642_030743`에서 후보 `93`건, 기존 검토 제외 미검토 후보 `91`건을 추출했고 `11705250`을 current HEAD non-light 단건 PID `93016`, run `20260703_034549_939485`로 발주했다. 검색 단계에서 `search_degraded_detected=6`, `search_upstream_zero=2`가 관측되어 approval은 계속 금지다.
  - Loop334: `11705250` current HEAD result는 `1/1/0/0` 완료됐지만 `is_relevant=false`, `work_resolution=none`, `official_title=null`로 떨어졌다. 독립 정답은 `심해의 마법사`라 `REPROCESS_FALSE_NEGATIVE`다. Public title/url leak은 없다.
  - Loop335: `11705250`의 title-lead alias extraction gap은 코드 계약으로 수리했지만 runtime replay는 아직 없다.
  - 산출물: `docs/devs/loop_reports/LOOP_319_REPORT_20260702.md`, `docs/devs/loop319_override_audit_11708445_20260702.json`, `docs/devs/loop_reports/LOOP_327_REPORT_20260703.md`, `docs/devs/loop_reports/LOOP_330_REPORT_20260703.md`, `docs/devs/loop_reports/LOOP_334_REPORT_20260703.md`, `docs/devs/loop_reports/LOOP_335_REPORT_20260703.md`, `docs/devs/loop334_override_audit_11705250_current_head_20260703.json`, `docs/devs/loop335_consumption_title_lead_alias_repair_20260703.json`
  - 완료 기준: current HEAD non-light completed-source에서 override audit flip rows를 계속 추출하고, public title publish 누출 여부와 false negative 여부를 분리해 blind/source-native로 확장 판정한다. search degraded가 남으면 approval 금지.

## Collateral unsafe-promotion repair

- [ ] Loop308 `unsafe_promotion_from_hold` repair queue
  - 상태: source_native_triage_complete_26_of_26 / repair_required_14 / approval_not_open
  - 발견: Loop308에서 collateral183 P0 unsafe-promotion bucket을 전수 판정했고 `ACCEPT=12`, `REPROCESS=14`, validation issues `0`으로 분리했다.
  - 산출물: `docs/devs/loop_reports/LOOP_308_REPORT_20260702.md`, `docs/devs/loop308_unsafe_promotion_from_hold_source_native_verdicts.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop308_unsafe_promotion_from_hold_source_native_review.json`
  - 우선 repair 후보: `11658637`, `11668324`, `11673086`, `11677913`, `11695637`, `11718105`
  - 완료 기준: `repair_unsafe_promotion=14`를 shared promotion gate/runtime 계약으로 줄이고, targeted replay와 collateral compare에서 순회귀 0을 확인한다. search degraded가 남으면 approval 금지.

## Safe-loss alias repair

- [ ] Loop307 safe-loss alias contract expansion follow-up
  - 상태: code_contract_go_unit / flip_no_go / approval_not_open
  - 발견: `11660237`은 N5에서 안정 정답으로 회복됐지만 `11674712`, `11698880`은 flip_rate `0.4`로 비결정 미해소다.
  - 적용 alias: `럽코빙의`, `빚세구`, `마줍`, `여신애호`, `별품소`
  - 보류 alias: `가챠펑크`, `즉사기`
  - 산출물: `docs/devs/loop_reports/LOOP_307_REPORT_20260702.md`, `docs/devs/loop307_safe_loss_alias_contract_expansion_20260702.json`
  - 완료 기준: patch 이후 targeted runtime replay, `11674712/11698880` flip 원인 분해, full375/bounded search non-light 완료 및 search degraded 해소.

- [ ] Loop301 `safe_loss_resolved_to_null=147` source-native follow-up
  - 상태: complete_source_native_review_147_of_147 / alias_unit_contract_7 / review_locked / approval_not_open
  - 발견: Loop321까지 누적 `147/147`, unreviewed `0`이 됐다. 단 source-native queue closure는 approval이 아니다.
  - 현재 counts: `REPROCESS=76`, `ACCEPT=42`, `HOLD=29`, validation issues `0`.
  - Loop322 적용: `괴담출근`, `절꺾않`, `무마`, `아카엄창`, `성좌안무서움`, `빌환`, `지구온라인` 7건은 shared alias unit contract로 올렸다. `주전무`는 보류했다.
  - 산출물: `docs/devs/loop_reports/LOOP_321_REPORT_20260702.md`, `docs/devs/loop_reports/LOOP_322_REPORT_20260702.md`, `docs/devs/loop321_safe_loss_source_native_review_20260702.json`, `docs/devs/loop322_safe_loss_alias_contract_20260702.json`
  - 완료 기준: Loop322 alias 7건 targeted runtime replay, 남은 `repair_safe_loss=76` shared gate wiring, `ACCEPT=42` regression count exclusion wiring, `HOLD=29` native review, collateral compare, full375/bounded gate 재평가.

- [ ] Loop301 `repair_safe_loss=14` targeted replay
  - 상태: code_contract_go_unit / runtime_in_progress_not_approval / approval_not_open
  - 발견: Loop304에서 source-native alias seed 일부를 known-abbreviation work-cue 계약으로 전환했다.
  - 적용 alias: `암흑가보스/암보스`, `기계공주`, `약먹마`, `악살싶`, `마도줍`, `괴담동`, `즉사무림`, `밀리언클래스`
  - 보호: `괴담텔 ... 괴담동이 살짝 생각나네` comparison-only negative는 release하지 않음.
  - 산출물: `docs/devs/loop_reports/LOOP_304_REPORT_20260702.md`, `docs/devs/loop_reports/LOOP_305_REPORT_20260702.md`, `docs/devs/loop304_safe_loss_alias_contract_repair_20260702.json`, `docs/devs/loop305_safe_loss_alias_targeted_replay_20260702.json`
  - 현재 replay: run id `20260702_181813_388157`, completed `0/11`, small-run health `include_search=false`, `light_mode=true`라 approval 근거 아님.
  - 완료 기준: Loop301 seed alias rows targeted runtime replay, collateral compare, always-on golden18/full375 gate 재평가. search degraded가 남으면 approval 금지.

## 검색 품질

- [ ] Search degraded P0 복구 및 current HEAD 증거 완료
  - 상태: P0_OPEN / runtime_partially_recovered / approval_not_open
  - Loop344: 기본 search budget을 `retries=1`, `pages=2`, client same-endpoint retry `0`으로 낮추고, 상시 access-denied를 만들던 `presearch`를 기본 engine에서 제외했다.
  - Loop344 live shard 1 probe `월야환담 노벨피아`는 attempts `2`, pages `1`, degraded `false`였지만, `11705230` runtime row는 `SEARCH_DEGRADED`, degraded `11`, unrecovered degraded `7`이라 P0는 아직 open이다.
  - Loop344 산출물: `docs/devs/loop_reports/LOOP_344_REPORT_20260703.md`, `docs/devs/loop344_search_budget_partial_recovery_20260703.json`.
  - 발견: Loop303에서 `3333/3334` health와 MCP bridge `36`은 복구됐지만 full375/bounded1200 runtime audit에 `search_degraded_observed`가 남았다.
  - 2026-07-03 Loop326 갱신: current HEAD `1095d447` 기준 full375, bounded1200 completed-source, golden18, safe-loss N5를 새 output 경로로 발주했다. 초기 health는 full375/bounded `12/12` search non-light OK, golden18 `2/2` search non-light OK다.
  - 영향: `promotion_blocked`는 계속 `search-blind conditional`로만 해석하고 hard-hold 완화 금지.
  - 산출물: `docs/devs/loop_reports/LOOP_303_REPORT_20260702.md`, `docs/devs/loop303_current_head_runtime_recovery_20260702.json`, `docs/devs/loop_reports/LOOP_326_REPORT_20260703.md`, `docs/devs/loop326_current_head_runtime_dispatch_20260703.json`
  - 완료 기준: N5 `15/15` flip probe 결과, full375 completed replay, bounded `1000~1500` completed-source non-light run이 모두 완료되고 search degraded가 0 또는 검토 가능한 수준으로 회복됨.
- [ ] Search shard/Docker runtime 복구 후 current HEAD 증거 갱신
  - 상태: P0_OPEN / local_docker_service_blocker
  - 발견: Loop302에서 `127.0.0.1:3333/3334` health 연결 실패, Docker API Internal Server Error, `com.docker.service=Stopped`가 확인됐다.
  - 영향: safe-loss N5, full375 replay, completed-source bounded non-light run을 현 HEAD에서 갱신하지 못한다.
  - 산출물: `docs/devs/loop_reports/LOOP_302_REPORT_20260702.md`, `docs/devs/loop302_current_head_refresh_blocker_20260702.json`
  - 완료 기준: healthy MCP shard 확보 후 Loop302 N5 plan 재실행, full375 search-including replay, completed-source bounded `1000~1500` non-light run이 result JSON/manifest를 생성하고 search degraded가 0 또는 검토 가능한 수준으로 회복됨.
- [ ] 개선 전후 자동 비교 리뷰 문서 생성
  - 상태: first_manual_comparison_done / mandatory_200_1000_policy_added / automation_tool_next
  - 문제: 품질 개선을 구현해도 baseline/improved run 비교와 전문가 리뷰 패킷 생성이 사람이 기억해야 하는 절차로 남아 누락될 수 있음.
  - 기대 효과: 개선 작업마다 자동으로 테스트 런, run audit, 주요 지표 delta, known bad 판정 변화, LLM 리뷰 패킷 경로가 남음.
  - 1차 확인: late search budget 개선 후 `20260427_121338_563339` vs `20260427_143145_922090` 비교 문서 생성.
  - 2026-04-28 지침: 품질 개선은 targeted/unit 통과 후 200건 canary를 기본으로 실행하고, canary가 `completed=200/200`, `failed=0`, `pending=0`이면 1,000건 risk discovery까지 자동 진행한다.
  - 산출물: `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`, `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.json`
  - 완료 기준: baseline run id, improved run id, 입력 JSONL, 200건 canary, 1,000건 risk discovery, 비교 Markdown/JSON, 남은 리뷰 항목을 자동 생성하는 도구화
- [x] LLM/전문가 정성 리뷰 패킷 생성 도구 추가
  - 상태: implemented
  - 관련 파일: `tools/build_llm_judgment_review_packet.py`
  - 완료 기준: checkpoint, run audit, slang DB를 묶어 JSONL/Markdown 리뷰 패킷 생성
- [ ] 같은 입력의 대형 표본 재처리로 검색 저하율 비교
  - 상태: afterfix12_parallel36_canary_done / quality_review_required
  - 문제: `20260423_170321_250907` run은 shard 장애가 섞인 baseline이라 품질 승인 기준으로 쓰기 어렵다.
  - 현재 확인: `20260427_121338_563339`와 late budget 개선 run `20260427_143145_922090` 모두 checkpoint `200/200`, failed `0`, missing `0`.
  - late budget 비교: 검색 오류 `81 -> 75`, timeout `82 -> 75`, identified title `72 -> 76`, relevant `148 -> 153`.
  - 1,000건 확인: `20260427_212634_728016` risk discovery는 `completed=1000`, `failed=0`, `Relevant=746`, `Identified=351`, `search_timeout=29`, `search_upstream_zero=539`, `search_degraded_detected=130`.
  - afterfix12 36병렬 canary: run id `20260428_142042_238055`, `completed=200/200`, `failed=0`, `Relevant=146`, `Identified=67`, `search_timeout=8`, `search_upstream_zero=105`, `search_degraded_detected=12`.
  - 남은 확인: 품질은 critical FP/alias FN이 남아 `quality_fix_required`. 10,000건 validation 전 parenthetical/generic/title validator 개선 필요.
  - 완료 기준: 안정화 후 200건 canary, 1,000건 risk discovery, 10,000건 validation 표본에서 `search_upstream_zero`, `search_degraded_detected`, `search_timeout` 변화 기록
  - 검증 기록 위치: `VERIFICATION_RESULTS.md`
- [ ] 검색 실패 post 재처리 queue 설계
  - 상태: proposed
  - 기대 효과: 검색 실패/저하가 큰 post를 별도 재처리해 품질 손실을 줄임
  - 완료 기준: post id, query stats, failure reason을 포함한 CSV/JSON 산출물 생성
- [x] 일반 장르/세력명 title-reaction 과확정 차단
  - 상태: afterfix12_parallel36_verified / alias_long_tail_review
  - 발견 사례: `11631298` (`무림맹에 시발 마교 혈교 대가리가 다 있네...`)가 `무림맹주 막내제자`로 resolved.
  - 문제: `무림맹`, `마교`, `혈교`, `맹주`, `제자` 같은 무협 일반 세력/역할어만으로 검색하면 수많은 작품이 뜨며, 특정 작품 고유 앵커가 아님.
  - 개선 방향: 후보 제목과 post 사이의 공유 토큰에서 장르 일반어를 제거한 뒤 남는 고유 토큰이 없으면 `resolved_title` 승격 금지. 본문이 `ㅋㅋㅋㅋ`처럼 짧으면 `genre_general`/`unresolved_title`/`adjacent_relevant` 우선.
  - 2026-04-27 조치: Verifier relation judge에 `generic_relation_only` 가드를 추가하고, code-level body check/FN recovery에서도 무협 일반 세력명만 겹치는 후보를 차단.
  - 2026-04-27 추가 조치: `generic_relation_only` 후처리에서 후보/primary/mentioned를 비우고, 최종 interpretation을 재계산해 `secondary_reference_works` 누수를 제거.
  - 2026-04-27 targeted 결과: `targeted_generic_character_3_20260427_afterfix11_result.json`에서 `11631298`은 `is_relevant=false`, `work_resolution=none`, `title_candidates=[]`, `secondary_reference_works=[]`, `generic_relation_only_demoted`.
  - 2026-04-27 canary 결과: `query_gate_canary_200_afterfix11_20260427_result.json`에서 `11631298`은 비관련/후보 없음으로 유지. 전체 200건은 `completed=200`, `failed=0`, `generic_relation_only_demoted=3`.
  - 2026-04-27 정성 리뷰: 120건 adjudication에서 `11631298`은 ACCEPT. 단, `서울마탑`처럼 확인된 별칭이 generic guard로 과차단되는 사례는 REPROCESS로 남김.
  - 2026-04-27 1,000건 결과: `generic_relation_only_demoted=8`. `11631298`은 정상 차단됐지만 `11562020(서울마탑)`, `11417268(화귀)`, `11459433(언니약혼)` 같은 strong alias 후보 과차단이 섞임.
  - 2026-04-28 afterfix12 36병렬 결과: `11631298`은 non-relevant/title 없음 유지, `11562020(서울마탑)`은 `서울에 마탑 세웠더니 돈이 미쳤다`로 resolved.
  - 남은 작업: `11702067(폴랩)`, `11576520(망교성)`, `화귀`, `언니약혼` long-tail alias를 positive 이웃 케이스로 추가 확인.
  - 완료 기준: `11631298`이 특정 공식 제목/보조 작품 후보로 노출되지 않고, 유사한 무협 일반 세력명 케이스의 false positive가 감소.
- [x] 캐릭터 페이지 parenthetical 작품명 회수
  - 상태: afterfix12_parallel36_verified / adjacent_review_required
  - 발견 사례: `11663540` (`주서연`)은 나무위키 검색 결과 `주서연(전 버튜버가 하고 싶은데요)`가 있으나 최신 canary는 정식 제목 미확정.
  - 문제: 캐릭터명 단독은 동명이인/실존/타매체 위험이 있어 곧장 resolved하면 안 되지만, 검색 결과 title parenthetical에 작품명이 명시되면 중간 강도의 근거로 사용할 수 있음.
  - 개선 방향: `인물명(작품명)` 형태의 wiki/result title을 `character_title_link` 후보로 추출하되, post의 캐릭터명 반복, 장르/TS/작품 맥락, 비소설 도메인 부재를 함께 요구.
  - 2026-04-27 조치: snippet/search-result 재스캔에서 캐릭터형 parenthetical bridge를 등록하고, `줄다리기(오징어 게임)` 같은 사건/게임 parenthetical은 제외.
  - 2026-04-27 추가 조치: 최종 consistency pass에서 `ctx.verified_character_work_links`가 비어 있어도 `ctx.search_results`의 `캐릭터명(작품명)` parenthetical을 재구성해 title 후보로 승격. `전차`, `줄다리기`, 사건/게임/일반명사 parenthetical은 캐릭터 앵커에서 제외.
  - 2026-04-27 추가 조치: `comparison_target`이 실제 작품 비교가 아니라 `주서연` 같은 약한 캐릭터 표면 후보일 때는 parenthetical 작품 확정을 막지 않도록 좁은 예외를 추가하고, 해당 캐릭터 표면 후보가 secondary reference로 새지 않게 정리.
  - 2026-04-27 targeted 결과: `targeted_generic_character_3_20260427_afterfix11_result.json`에서 `11663540`은 `is_relevant=true`, `official_title=전 버튜버가 하고 싶은데요`, `discussion_type=character_talk`, `work_resolution=resolved`, `system_state=clean`.
  - 2026-04-27 canary 결과: `query_gate_canary_200_afterfix11_20260427_result.json`에서 `11663540`은 `전 버튜버가 하고 싶은데요`로 resolved. 전체 200건은 `character_parenthetical_title_resolved=5`, `verifier_technical_failure=0`, `[Errno 22] Invalid argument=0`.
  - 2026-04-27 정성 리뷰: 120건 adjudication에서 `11663540`은 ACCEPT였지만, `11718070`, `11689276`, `11620037`, `11512300`, `11141333`은 parenthetical bridge 계열 critical FP로 REJECT.
  - 2026-04-27 1,000건 결과: `character_parenthetical_title_resolved=37`. `11663540`은 회수됐지만 `11718070 -> Depressive disorder`, `11689276 -> 뮤지컬 배우`, `11620037 -> 또는 라쇼몽, 아쿠타가와 류노스케`, `11512300 -> 마피아42`가 critical FP로 재현.
  - 2026-04-28 afterfix12 36병렬 결과: `11663540`은 `전 버튜버가 하고 싶은데요`로 resolved 유지, `11718070`은 non-relevant/title 없음, `11620037`은 non-relevant/title 없음. `11689276`은 title은 제거됐지만 adjacent로 남아 정성 검토 필요.
  - 남은 작업: title FP는 줄었지만 adjacent/relevant 경계가 남은 케이스를 120건 리뷰 패킷에서 판독하고, 1,000건에서 재발률 확인.
  - 완료 기준: `11663540`은 `전 버튜버가 하고 싶은데요`로 resolved되고, 동명이인 character page false positive는 막음.
- [ ] 검색 쿼리 확장 실험
  - 상태: implemented_smoke
  - 관련 파일: `tools/run_search_query_expansion_probe.py`, `src/llm_batch/experts/orchestrator.py`
  - 가설: 작품/약칭 단독 검색보다 `소설`, `장르소설`, `웹소설`, 플랫폼명 조합 검색이 웹소설 도메인 회수율을 높일 수 있음
  - 주의: `장르소설` 추가가 일반 장르 토론/추천글을 특정 작품으로 과잉 확정하는지 함께 확인
  - 현재 관찰: `괴담텔 노벨피아`, `즉사무림 문피아`는 platform detail hit를 늘림. 4건 병렬 smoke에서 일반 제목에도 suffix가 붙는 위험을 발견해 gate를 재조정함.
  - 적용: 확정 약칭은 alias-only 예외로 허용하고, 일반 표면어는 Discourse가 `novel_literature`로 잡은 경우에만 confident query expansion 적용
  - 완료 기준: 200/1,000/10,000건 표본에서 기본 쿼리와 확장 쿼리의 `official_url`, `search_snippets`, false positive/false negative 변화 비교
- [ ] 쿼리 확장 후 대형 병렬 canary 실행
  - 상태: afterfix12_parallel36_canary_done / quality_review_required
  - 관련 입력:
    - `out/sampling/query_gate_canary_200_20260426.jsonl`
    - `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`
    - `out/sampling/query_gate_validation_10000_20260426.jsonl`
  - 1차 결과: `20260427_002737_046977` canary는 checkpoint `199/200`, false failed `105`, stuck `1`로 NO-GO.
  - 조치: CLI progress 오류 방어, 비소설 매체 indirect 보강 차단, MCP client failover budget 추가.
  - 2차 결과: `20260427_121338_563339` canary는 checkpoint `200/200`, false failed `0`, stuck `0`, manifest `completed_count=200`.
  - 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`, `selected=80`.
  - afterfix11 120건 adjudication: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`, `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`.
  - 1,000건 결과: run id `20260427_212634_728016`, `completed=1000`, `failed=0`, audit `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_audit.json`, 리뷰 패킷 `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.md`.
  - afterfix12 36병렬 결과: run id `20260428_142042_238055`, `completed=200`, `failed=0`, 사후 shard audit `ok=36/36`, 리뷰 패킷 `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`.
  - 완료 기준: 1,000건 risk discovery와 10,000건 validation에서 개선 전후 같은 post id 결과 비교, 잡담/비소설 제목의 `confident_title_*` 과확장 재발 없음
- [x] MCP client 검색 failover budget 추가
  - 상태: verified_canary / long_tail_review
  - 관련 파일: `src/llm_batch/search/client.py`
  - 문제: 검색 1건이 failover 과정에서 전체 36 endpoint를 순차로 훑으면 `timeout * retry * shard 수`만큼 long-tail이 발생.
  - 조치: `MCP_CLIENT_SEARCH_TIMEOUT_SEC`, `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH` 추가.
  - 권장 canary env: `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`, `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`, `MCP_CLIENT_SEARCH_MAX_RETRIES=1`
  - 검증: `20260427_121338_563339` 200건 canary에서 checkpoint `200/200`, failed `0`; 단, long-tail 상위 `11457804=886.4s`, `11478694=703.9s` 추가 분석 필요
- [x] post별 late search 누적 예산 가드 추가
  - 상태: verified_canary / quality_review
  - 관련 파일: `src/llm_batch/experts/orchestrator.py`
  - 문제: `_execute_searches` 배치 내부 cap은 있어도 verification/search/recall batch가 반복되면 post 단위 검색 수가 계속 증가해 long-tail이 남음.
  - 조치: `ctx.executed_queries` 기준 post 누적 예산을 `_execute_searches` 중앙 관문에 추가. 초기 탐색은 보존하고, late iteration 또는 `abbreviation_verification`, `decoder_recall_verification`, `unresolved_term_*` 같은 late-purpose batch는 누적 예산을 적용.
  - 기본 cap: `core_fast_resolve=14`, `uncertain_core=16`, `adjacent_meta=10`, `adjacent_meta_cheap=6`, `quarantine_candidate=3`, `deep_research=24`, default `18`.
  - 검증: `py_compile` 통과, late budget 단위 테스트 3건 통과. `11478694` 1 shard 참고 실행은 `completed_count=1`, `291.8s`, 검색 실행 `13건`; 단, 최종 late-purpose refinement 전 시작된 smoke이므로 품질 gate로 쓰지 않음.
  - canary 확인: `20260427_143145_922090` 200건 완료, failed `0`, 사후 shard audit `ok=36/36`.
  - 비교 결과: late budget cap/exhausted `22/14`, 검색 오류 `81 -> 75`, timeout `82 -> 75`, `11478694` `703.9s -> 361.7s`, `11456200` `586.5s -> 267.4s`.
  - 남은 위험: `11457804` `886.4s -> 911.5s`, `11718077` `151.8s -> 496.2s`로 추가 로그 분석 필요.
  - 완료 기준: 1,000건 risk discovery에서도 timeout 감소와 false negative 증가 없음 확인
- [x] 비소설 매체 indirect title/alias/fetch 보강 차단
  - 상태: verified_canary / quality_review
  - 관련 파일: `src/llm_batch/experts/orchestrator.py`
  - 문제: snippet analyzer가 `anime/manga/webtoon/game` 등으로 판단해도 alias bridge가 계속 붙어 false positive와 long-tail을 만들 수 있음.
  - 조치: `hard_non_novel_media` guard로 title/abbreviation/fetchable hints를 비우고 indirect reinforcement를 차단.
  - 단일 확인: `11478694` 재현에서 `비소설 매체 간접 보강 차단` 로그 확인, manifest `completed_count=1`.
  - canary 확인: `20260427_121338_563339` 로그에서 `비소설 매체 간접 보강 차단` 22건, `11478694` 완료.
  - 완료 기준: 1,000/10,000건에서도 off-domain media stuck 및 false positive 재발 없음
- [ ] headless fallback 성공률 리포트
  - 상태: proposed
  - 완료 기준: `headless_used`, `headless_count`, `headless_error`, provider별 성공률 집계
- [ ] 검색 근거 0 resolved_title 승격 제한
  - 상태: proposed
  - 문제: `search_snippets=0 AND official_urls=0`인데 resolved/high로 확정한 오판 존재
  - 1,000건 발견: `Depressive disorder`, `Sword Master`, `BLACKPINK`, `Truth`, `Cecil`, `Ubuya`, `성장판`, `rNN 판`, `主人公,2153` 같은 common/person/media/malformed 후보가 official title로 승격.
  - 완료 기준: 직접 title/OCR/platform URL 근거가 없으면 `unresolved_title` 또는 재처리 큐로 이동
- [x] 의도적 오타/자모 포함 title alias의 HOLD/resolve 정책
  - 상태: afterfix19_targeted_verified / canary_required
  - 발견 사례: `11198715` (`마법소녀ㄴ 생각해보니 공백의 2년 어떻게 한거지`)
  - 문제:
    - `마법소녀ㄴ`은 일반 장르어처럼 보이지만 실제 작품 제목에도 의도적으로 포함될 수 있음.
    - afterfix16 canary에서는 넓은 alias 검색이 `마법소녀물 신전사가 되었다`로 오매칭 resolved.
    - afterfix17 targeted에서는 오답 title lock은 제거됐지만 작품 내부 단서(`세린/세진/계약/은퇴`)까지 무시되어 `Relevant=0`으로 과보수.
  - 개선 방향:
    - broad alias stem은 단일 official title 확정 금지.
    - 단, 본문에 캐릭터명/계약/설정/기간/전개 단서가 있으면 `비관련`이 아니라 `core_relevant + unresolved_work`로 유지.
    - candidate title의 alias stem과 body predicate가 함께 맞는 경우(`마법소녀ㄴ` + `은퇴`)는 별도 RESEARCH/HOLD 큐에 보내고, 캐릭터명 공식 연결 없이는 slang DB 확정 저장 금지.
  - 완료 기준:
    - `11198715`는 오답 title 없이 관련-미확정 또는 정확한 후보로 처리.
    - `11456200`처럼 본문이 장르 클리셰만 있는 이웃은 non-relevant 유지.
    - `불꽃의 마법소녀ㄴ`, `마법소녀ㄴ은 은퇴하고 싶다` 같은 official detail 이웃을 positive/negative로 함께 테스트.
  - 확인:
    - `tests.test_agentic_pipeline_rework`: 155건 OK.
    - afterfix19 targeted `out/sampling/targeted_magicgirl_11198715_afterfix19_20260429_result.json`: `Relevant=1`, `Identified=0`, `official_title=null`, `internal_work_signal_unresolved_recovered`.
    - 단위 negative 이웃 `11456200`은 단일 캐릭터/폼체인지 클리셰만으로 rescue하지 않음.
  - 남은 확인: afterfix19 200건 canary와 1,000건 risk discovery에서 broad alias stem이 과차단/과확정되지 않는지 재집계.
- [x] malformed/generic official title validator 추가
  - 상태: parallel36_verified_afterfix12 / risk_discovery_required
  - 문제: 검색/LLM 후보가 `rNN 판`, `主人公,2153`, 영어 일반어, 인물/그룹명, 너무 짧은 일반명사여도 최종 official title로 들어갈 수 있음.
  - 발견 예시: `Depressive disorder`, `Sword Master`, `BLACKPINK`, `Truth`, `Cecil`, `Ubuya`, `성장판`, `독점`, `아포칼립스`, `r51 판`.
  - 확인: afterfix12 targeted unittest와 `11620037` 단건 실제 rerun에서 source metadata title 제거 확인.
  - 36병렬 확인: `11718070 -> Depressive disorder`, `11620037 -> 라쇼몽 source metadata` resolved title FP는 제거됨.
  - 남은 확인: 1,000건에서 `Sword Master`, `BLACKPINK`, `Truth`, `Cecil`, `rNN 판`류 재발률 재집계.
- [x] character parenthetical bridge false positive gate 강화
  - 상태: parallel36_verified_afterfix12 / adjacent_review_required
  - 문제: `캐릭터명(작품명)` 패턴 회수는 필요하지만, common term/person/media parenthetical이 작품 title로 승격됨.
  - 발견 예시: `11718070`, `11689276`, `11620037`, `11512300`, `11469068`, `11174128`.
  - 확인: `11689276` targeted 실제 run에서 `뮤지컬 배우` title 제거, `11620037` 라쇼몽 메타문구 단건 rerun에서 title 제거.
  - 추가 확인: `11718070` ECT 의학 일반글은 `medical_common_topic_demoted`로 `is_relevant=false`, title 없음.
  - 36병렬 확인: `11718070`, `11620037`은 title 없음. `11663540` positive 회수 유지. `11689276`은 title 없음이나 adjacent로 남아 human review 대상.
  - 남은 확인: `11512300` 포함 1,000건 재처리와 120건 afterfix12 리뷰 판독.
- [x] generic guard 이후 confirmed/strong alias rescue
  - 상태: parallel36_verified_afterfix12 / long_tail_required
  - 문제: generic relation guard가 맞는 케이스와 strong alias 케이스를 같이 non-relevant로 내림.
  - 발견 예시: `11631298`은 정상 차단, `11562020(서울마탑)`, `11417268(화귀)`, `11459433(언니약혼)`은 rescue 필요.
  - 확인: `11562020(서울마탑)`은 `generic_relation_alias_rescued`, `11631298(무림맹)`은 non-relevant/title 없음 유지.
  - 36병렬 확인: `11562020` resolved, `11631298` non-relevant 유지.
  - 남은 확인: `화귀`, `언니약혼`, `폴랩`, `망교성` long-tail targeted 및 1,000건 재집계.
- [x] 공통 제목 stem 충돌 검색 이웃 분리
  - 상태: targeted_verified / canary_needed
  - 발견 사례: `11684407`에서 `마법소녀ㄴ` 표면형이 `마법소녀ㄴ은 은퇴하고 싶다`와 `불꽃의 마법소녀ㄴ` 양쪽 공식 제목에 포함되어, 검색 이웃인 `불꽃의 마법소녀ㄴ`이 `comparison_target`, `recommendation_candidate`, `secondary_reference` 및 slang DB pending 후보로 새는 문제가 발생.
  - 일반 실패 유형: 짧은 표면형이 여러 공식 제목의 공통 stem/prefix/suffix인 경우. 이때 본문/댓글의 캐릭터·설정·작가·회차 앵커가 닫힌 후보만 primary로 남기고, 나머지 공식 제목은 검색 이웃으로 취급해야 함.
  - 2026-04-28 조치: 자모 표기(`ㄴ`)를 보존하는 stem 비교를 추가하고, locked 공식 후보가 decisive support를 갖는 경우 공통 stem 이웃이 단일 후보 rescue를 막지 않도록 변경. 이웃 후보는 outward reference 역할(comparison/recommendation/secondary)에서 제거.
  - LLM 지시: `ambiguous_title_stem` 규칙을 verifier/router prompt에 추가. 복수 공식 제목 공통 stem은 `alias_scope=mixed_unknown`, `store_in_slang_db=false`, 검색 이웃은 slang 후보가 아니라고 명시.
  - 테스트: positive(`마법소녀ㄴ` -> `마법소녀ㄴ은 은퇴하고 싶다`), negative(`불꽃의 마법소녀ㄴ` 직접 언급 시 차단 유지), outward reference pruning 이웃 케이스 추가.
  - targeted 실제 결과: `out/sampling/targeted_ambiguous_title_stem_11684407_afterfix13_20260428_result.json`에서 `official_title=마법소녀ㄴ은 은퇴하고 싶다`, `work_resolution=resolved`, `comparison_target=null`, `mentioned_works=null`, `secondary_reference_works=[]`.
  - 남은 확인: afterfix13 200건 canary 및 1,000건 risk discovery에서 공통 stem 계열 후보가 과차단/과확정되지 않는지 재집계.
- [x] adjacent relevance legacy flag 및 budget profile 정리
  - 상태: regression_verified / canary_needed
  - 발견 계기: 공통 제목 stem guard 이후 `tests.test_agentic_pipeline_rework` 전체 회귀에서 adjacent author/meta/recommendation 및 budget profile 계열 실패 7건을 추출.
  - 일반 실패 유형: `adjacent_relevant`는 주변 담론으로 남겨야 하지만 legacy `is_relevant=true`가 되면 핵심 작품 토론, official title 확정, slang DB 저장 근거로 새어 false positive 지표를 만든다.
  - 개선: 최종 `is_relevant`를 `topicality == core_relevant`로 제한하고, prompt/router/arbiter 지시에 adjacent는 `is_relevant=false`, official title null 기본값을 명시.
  - budget 개선: `adjacent_meta_cheap`은 작가/플랫폼/meta 계열 `max_q=2`, 장르 토론 계열은 공식 근거 확인 슬롯을 남겨 `max_q=3`으로 분기.
  - 테스트: targeted adjacent 7건 OK, budget 이웃 3건 OK, `tests.test_agentic_pipeline_rework` 145건 OK, `tests.test_agentic_pipeline_alias_contract` 30건 OK, 변경 파일 `py_compile` 통과.
  - 남은 확인: 200건 canary와 1,000건 risk discovery에서 adjacent 판정이 `Relevant/Identified/slang DB`로 새지 않는지, 장르 토론 budget 3쿼리가 FP를 늘리지 않는지 집계.
- [x] Namu 의학/일반 개념 official title 승격 차단
  - 상태: risk_discovery_done / residual_fp_found
  - 발견 계기: `11718111`이 `조현병` 나무위키 일반 의학 항목을 official title로 승격.
  - 일반 실패 유형: 위키 URL과 괄호형 검색 결과가 있어도, 표면어가 현실 의학/건강/사회 개념이고 작품 고유 앵커가 없으면 웹소설 title 근거가 아니다.
  - 개선: `medical_common_topic_title` hard reject profile을 추가하고, character-parenthetical bridge 및 URL-backed replacement가 같은 rejection profile을 사용.
  - 테스트: targeted 5건 OK, `tests.test_agentic_pipeline_rework` 147건 OK, `tests.test_agentic_pipeline_alias_contract` 30건 OK, 단건 actual run `20260428_230857_637381`에서 `11718111` non-relevant/title 없음.
  - 200건 canary 확인: run id `20260428_233059_378617`, `completed=200/200`, `failed=0`, `Relevant=70`, `Identified=61`.
  - 1,001건 risk discovery 확인: run id `20260429_002511_375830`, `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=381`, `Identified=297`, 사후 shard audit `ok=36/36`.
  - 통과한 이웃: `11718070` ECT와 `11631298` 무림맹은 title 없음, `11616838/11198715` 마법소녀ㄴ positive stem은 resolved 유지.
  - 잔존 실패: `11718111`은 risk discovery에서 `정신과 의사`로 재발. 의료 명사만이 아니라 현실 직업/일반 개념 title과 platform URL-backed 승격을 함께 막아야 함.
  - 산출물: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_audit.json`, `out/llm_judgment_reviews/llm_judgment_review_20260429_002511_375830_risk1000_afterfix14.md`.
  - 후속: 아래 weak-evidence official title guard로 확장.
- [ ] weak-evidence official title 승격 제한
  - 상태: discovered_afterfix14_risk1001
  - 발견 계기: afterfix14 risk discovery에서 약한 근거 official title 후보 35건 추출.
  - 일반 실패 유형: reason 내부에는 `official_title_evidence=false`, `search_snippets=0`, `official_urls=0`, `post_spans=0`, `thematic_overlap_only`, `search_only` 같은 반론이 있는데, 후처리 스코어가 플랫폼 URL 또는 title_in_post 가산점으로 resolved title을 확정함.
  - 대표 사례: `11718111 -> 정신과 의사`, `11684415 -> 小數, decimal number`, `11505857 -> Cecil`, `11713208 -> 코믹 메이플스토리`, `11684401 -> 추리 소설`, `11205227 -> 챌린지`.
  - 해결 방향: 특정 title blacklist가 아니라 evidence invariant로 처리. `post_spans=0 AND search_snippets=0 AND official_urls=0` 또는 `official_title_evidence=false`인 경우 플랫폼 URL 가산점만으로 resolved를 허용하지 않고 `unresolved_title`/`REPROCESS`로 보냄.
  - positive 이웃: 안정 약칭과 직접 앵커가 있는 `나혼렙`, `마법소녀ㄴ은 은퇴하고 싶다`, `전 버튜버가 하고 싶은데요`, `서울에 마탑 세웠더니 돈이 미쳤다`는 유지.
  - 완료 기준: targeted positive/negative 이웃 통과 후 200건 canary와 1,000건 risk discovery 자동 재실행. 약한 근거 35건의 resolved 재발률과 alias rescue 회귀를 비교 문서로 기록.
- [ ] 댓글 URL evidence 역할 분리
  - 상태: proposed
  - 문제: 댓글 추천/예시 URL이 원글 primary work로 과잉 승격됨
  - 완료 기준: 댓글 URL이 `primary_evidence`인지 `secondary_reference`인지 구분
- [ ] off-domain media gate 추가
  - 상태: proposed
  - 대상 예시: `블아`, `페그오`, 현실 의학, 영화, 연예인 비교
  - 완료 기준: 비웹소설/타매체가 웹소설 작품으로 자동 승격되지 않음
- [ ] reason/최종 필드 불일치 validator
  - 상태: proposed
  - 완료 기준: reason은 비관련/미확정인데 최종 필드가 relevant/resolved인 케이스를 REPROCESS 큐로 분리
- [ ] 과거 result 파일의 처리 오류 row 회수/표시
  - 상태: discovered_fixed_in_latest
  - 발견 사례: `out/sampling/query_gate_canary_200_20260427_result.json`의 `11549038`은 `[Errno 22] Invalid argument`로 실패 row가 남아 있음.
  - 현재 확인: `20260427_121338_563339`, `20260427_143145_922090`에서는 같은 post가 정상 처리되어 재발하지 않음.
  - 완료 기준: 오래된 partial/failed result 파일을 볼 때 false failed인지 최신 rerun에서 회수됐는지 자동 표시하는 audit 리포트 생성

## 2026-07-03 Loop324 alias replay 후속

- [ ] Loop324 targeted canary `NO-GO` 후속 처리
  - 상태: runtime_complete_semantic_no_go
  - 근거: run `20260702_235904_452705`, `7/7/0/0`, non-light search health.
  - 집계: `safe_resolved=2/7`, `promotion_blocked=5/7`, search degraded rows `5/7`.
  - 개선: `11708470 절꺾않 -> 절대 꺾이지 않을거야!`.
  - 회귀: `11708443 괴담출근` safe-resolved에서 promotion-blocked로 하락.
  - 남은 작업: `11708443`, `11718099`, `11718110` publish trace와 final serializer 불일치 검토, `11713220` OCR 문장형 title-role 분리.
  - 완료 기준: 동일 packet safe_resolved 단조 비감소와 actionable queue 감소가 같이 관측되고, search degraded가 P0에서 해소됨.

## LLM / 전문가 정성 리뷰

- [ ] LLM 프롬프트/후처리 규칙 일반화 원칙 적용
  - 상태: guideline_added / ongoing_review
  - 문제: `11718070` 같은 오답을 볼 때 해당 게시글이나 오답 제목만 직접 막으면 다른 현실 주제/검색 메타데이터/타매체 케이스에서 같은 문제가 반복된다.
  - 원칙: 사례별 해결이 아니라 실패 유형을 정의한다. 예: 실제 의학/건강 주제 + 작품 앵커 없음, 장르 일반어만 겹침, 검색 결과의 저자/출판 메타데이터가 제목으로 승격, 타매체/인물명이 웹소설 제목으로 오인.
  - 프롬프트 기준: 예시는 암기 대상이 아니라 rubric 설명용이다. 모델은 `본문/댓글 고유 앵커`, `공식 플랫폼 근거`, `안정된 약칭`, `캐릭터-작품 연결`, `도메인 불일치` 같은 증거 조건으로 결론을 내야 한다.
  - 코드 기준: exact bad-title blacklist 대신 범주형 lexicon과 증거 게이트를 우선한다. lexicon 추가 시 범주 이름, 목적, 과차단 방지 rescue 조건, positive/negative 이웃 테스트를 남긴다.
  - 완료 기준: 새 품질 패치마다 `CHECKLIST.md`의 일반화/하드코딩 금지 항목을 통과하고, 200/1,000건 표본에서 새 FP/FN을 재확인.
- [ ] Locked official bad metadata 재승격 방지
  - 상태: afterfix20_risk_guard_go / overall_quality_review
  - 문제: afterfix19 risk discovery에서 locked official candidate가 `community_post/deleted/url_deleted_or_unavailable` 음성 메타를 가진 상태인데도 resolved title로 되살아남.
  - 대표 사례: `11631298 -> 무림맹주 막내제자`
  - 일반화: 작품명 blacklist가 아니라 candidate의 page/content/evidence metadata를 기준으로 rescue eligibility를 판단한다.
  - 구현: afterfix20에서 locked candidate selection이 `community_post`, `deleted/unavailable`, `url_deleted_or_unavailable`, `url_is_community_post`, `listing_only`, `title_url_mismatch` 신호를 가진 후보를 제외.
  - 검증: `tests.test_agentic_pipeline_rework` 157건 OK, targeted `20260430_015935_598854`에서 `11631298` title 없음.
  - canary: `20260430_021001_693350`, `completed=200/200`, `Relevant=73`, `Identified=57`, `reason_errors=0`, `11631298` title 없음.
  - risk: `20260430_025849_885589`, `completed=1001/1001`, `Relevant=382`, `Identified=277`, `reason_errors=0`, `11631298` title 없음.
  - 남은 상태: locked metadata guard 자체는 통과. 전체 risk 품질은 `11505857 -> Cecil`, `11456200` 과복구 때문에 REVIEW.
- [ ] 캐릭터 괄호형 search bridge recall 안정화
  - 상태: discovered
  - 문제: `주서연(전 버튜버가 하고 싶은데요)` 같은 캐릭터-작품 괄호형 bridge가 검색 결과에 잡히면 resolved되지만, 검색 결과가 누락되면 같은 post가 unresolved/non-relevant로 흔들림.
  - 대표 사례: `11663540`
  - 개선 방향: character-only query, character + `웹소설/장르소설/나무위키/노벨피아` query, search miss 시 RESEARCH/HOLD 큐를 검토.
  - 완료 기준: `11663540` positive 이웃은 검색 결과 편차에도 non-relevant로 떨어지지 않고, 단일 작품 title이 불충분하면 관련-미확정으로 유지.
- [x] 짧은 인명/캐릭터 surface의 영문 title 오승격 방지
  - 상태: verified_afterfix21_risk
  - 문제: 본문/제목의 짧은 인명 표면이 검색 결과의 영문 제목으로 과도하게 연결됨.
  - 대표 사례: `11505857 -> Cecil`
  - 일반화: character-parenthetical bridge는 `캐릭터명(작품명)` 형태와 본문 캐릭터 anchor, 공식/작품 URL 또는 명확한 작품 설명이 함께 있을 때만 title resolved를 허용.
  - positive 보존: `11663540 -> 전 버튜버가 하고 싶은데요`.
  - 구현: afterfix21에서 짧은 영어 인명형 title은 post-side work anchor 없이 resolved 승격하지 않도록 제한.
  - 검증: `tests.test_agentic_pipeline_rework` 159건 OK, targeted/canary/risk에서 `11505857` title 없음, `11663540` resolved 유지.
  - 완료 기준: `Cecil`류는 title 없음 또는 RESEARCH/HOLD, 실제 캐릭터-작품 괄호형 bridge는 유지.
- [x] Internal work signal trope-only 과복구 축소
  - 상태: verified_afterfix21_risk
  - 문제: `internal_work_signal_unresolved_recovered`가 단일 캐릭터 + 트로프 일반론까지 관련-미확정으로 복구할 수 있음.
  - 대표 사례: `11456200` (`마법소녀ㄴ 생각해보니 이거 완전 폼체인지`)
  - positive 보존: `11198715`, `11616838`처럼 복수/구체 캐릭터와 설정/전개 단서가 같이 있는 글.
  - 구현: `폼체인지/변신/의상/추가파츠/마법소녀` trope-only 표면은 강한 plot term 없이 internal work signal rescue 불가. `승급`은 strong plot term으로 추가.
  - 검증: afterfix21 targeted/canary/risk에서 `11456200` non-relevant/title 없음, risk에서 `11198715`, `11616838` 관련-미확정 유지.
  - 완료 기준: trope-only neighbor는 non-relevant/adjacent로 유지하고, plot/character density가 높은 positive neighbor만 unresolved core로 복구.
- [ ] afterfix21 resolved 증가분 정성 리뷰
  - 상태: risk_review_required
  - 문제: afterfix21 risk에서 `Relevant=396`, `Identified=308`로 afterfix20 `Relevant=382`, `Identified=277` 대비 증가.
  - 확인된 개선: `11505857`, `11456200`, `11718070`, `11718111`, `11631298` known bad는 title 없음.
  - 남은 위험: 증가분이 검색 회수율 개선인지 resolved false positive 증가인지 미확정.
  - 완료 기준: afterfix21 risk 결과에서 고위험 resolved 표본을 추출해 `ACCEPT/HOLD/REPROCESS/REJECT` 판독 후 다음 개선 항목으로 분리.
- [x] 20k run 위험군 정성 리뷰 1차 배치 수행
  - 상태: verified
  - 관련 run id: `20260423_170321_250907`
  - 완료 기준: 검색 저하, slang 후보, resolved 저근거, unresolved/multi_work, non-relevant 경계, 정상군 대조 샘플 리뷰 완료
- [ ] 20k run 계층 샘플 정성 리뷰 확대
  - 상태: packet_generated
  - 문제: 300건 위험군 샘플은 오류 유형 발견에는 충분하지만 전체 20k 품질 승인에는 부족
  - 관련 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_234227.jsonl`
  - 완료 기준: 위험군 1,000건 이상, 검색 정상 대조군, bucket별 최소 표본, 개선 후 10,000건 이상 재처리 비교 결과 기록
- [ ] 리뷰 결과 adjudication sheet 누적
  - 상태: first_afterfix11_sheet_recorded
  - 2026-04-27 기록: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`, `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`
  - 완료 기준: `ACCEPT/HOLD/RESEARCH/REPROCESS/REJECT` 집계와 error type/severity 기록
- [x] afterfix11 120건 리뷰 패킷 adjudication
  - 상태: completed
  - 관련 run id: `20260427_191203_030136`
  - 관련 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`
  - 판독 산출물: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`
  - 집계: `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`
  - 후속: 1,000건 risk discovery 완료 후 같은 rubric으로 재집계 비교
- [ ] 200건 canary 2차 리뷰 패킷 adjudication
  - 상태: packet_generated
  - 관련 run id: `20260427_121338_563339`
  - 관련 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`
  - 표본: `selected=80`, `search_degraded_majority=64`, `slang_insight=43`, `relevant_without_official_title=15`
  - 완료 기준: 전문가가 직접 읽고 `ACCEPT/HOLD/REPROCESS/REJECT` 집계, long-tail/검색저하가 판정 품질에 미친 영향 분리
- [ ] 다음 run checkpoint에 검색 evidence 필드 추가
  - 상태: proposed
  - 완료 기준: `search_health_flags`, `used_evidence_urls`, `raw/filtered search preview`, `executed_queries`, `degraded_queries` 저장

## Slang DB 품질

- [ ] `unclear_canonical_alias` 후보 review queue 분리
  - 상태: proposed
  - 문제: `빌환`, `무마`, `악엔`, `림조`, `드유`처럼 실제 약칭 가능성이 있는 후보가 차단됨
  - 완료 기준: 실제 약칭 가능성이 높은 후보와 차단 유지 후보를 분리한 review artifact 생성
- [ ] `pending` 하위 버킷 설계
  - 상태: proposed
  - 후보: `pending_alias`, `secondary_reference`, `comparison_only`
  - 완료 기준: 스키마 변경 여부와 대시보드 표시 정책 결정
- [ ] `family_aliases` 승격 조건 재조정
  - 상태: proposed
  - 완료 기준: 실데이터 샘플에서 false positive/false negative를 비교해 조건 확정
- [ ] `alias_span` 추출 도입
  - 상태: proposed
  - 문제: `즉사무림이유백`, `괴담텔이 뭔데`, `전능뇌 히로인`처럼 phrase 전체가 잡힘
  - 완료 기준: surface phrase와 실제 alias span을 분리 저장
- [ ] 조사/어미/캐릭터 결합 제거
  - 상태: proposed
  - 완료 기준: `이유백`, `히로인`, `엘리`, `봐볼려는데`, `이 뭔데`, `올 때 됐다` 같은 suffix 제거
- [ ] already_confirmed alias risk 분리
  - 상태: proposed
  - 완료 기준: 이미 DB confirmed인 alias가 `slang_not_stored` 고위험으로 잡히지 않음

## 대시보드/운영 UX

- [ ] slang DB 화면에 `examples.bucket`, `family_aliases` 표시
  - 상태: proposed
  - 문제: 현재 조회 레이어가 `titles[].slang/pending`만 보면 저장이 누락된 것처럼 보일 수 있음
  - 완료 기준: confirmed slang, pending, examples bucket, family aliases가 모두 확인됨
- [ ] run audit 요약 대시보드 표시
  - 상태: proposed
  - 완료 기준: run id, completed/failed/pending/flushed, reason errors, 검색 저하/timeout, bad shard count가 표시됨
- [ ] shard audit 요약 대시보드 표시
  - 상태: proposed
  - 완료 기준: `ok_count/count`, bad shard 목록, `/healthz`/`/readyz`/SearchXNG UI 상태, Docker exited/OOM/dead 여부 표시
- [ ] Loop392 runtime proof after Loop390
  - 상태: golden18 runtime `GO 18/18` / search `GO_GOLDEN18_ONLY` / expected-answer `NO-GO 15/18` / golden shared collateral `NO-GO 5` / full375 `NOT_OPEN` / approval not open
  - 적용: current HEAD `e3e71b16`에서 Loop390 후 golden18 단일 search non-light runtime을 완료했다. watchdog/stall 우회는 row를 실제로 내지만 semantic gate는 닫혀 있다.
  - 산출물: `docs/devs/loop_reports/LOOP_391_392_REPORT_20260704.md`, `docs/devs/loop392_golden18_after_loop390_runtime_20260704.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop392_golden18_after_loop390_e3e71b16_search_nonlight_result.json`.
  - 완료 기준: `11698880` mixed wrong publish, `11700470` expected 충돌, `11663521` positive unresolved를 R1 hardcoded cue 없이 줄이고 full375 collateral gate를 별도 증명하기 전까지 approval과 hard-hold 완화를 열지 않는다.
## 2026-07-04 Loop393 Follow-up

- [x] `11700470` image-scene-only official detail publish를 일반 promotion gate 술어로 차단했다.
- [x] Golden expected를 `expected_no_public_title=true` HOLD로 교정했다.
- [ ] current-code targeted replay로 `11700470`이 `null / promotion_blocked`로 내려가는지 확인한다.
- [ ] `11698880` mixed golden18 비결정 재오귀속을 batch-context 경쟁 후보 수렴으로 계속 좁힌다.
