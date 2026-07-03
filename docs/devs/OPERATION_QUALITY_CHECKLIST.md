# Operation Quality Checklist

## Global Report Language Gate

- [x] 보고서는 한국어로 작성한다.
- [x] 간략하게 쓰되 의미, 근거, 산출물 경로, gate 상태를 생략하지 않는다.
- [x] `runtime GO`, `targeted canary GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 분리해 적는다.

## 2026-07-03 Loop371 golden18 runtime 재검증 quality gate

- 근거:
  - [x] 신규 full375/bounded/N5 대형 런을 발주하지 않았음을 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_371_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop371_golden18_after_loop370_20260703.json`.
  - [x] Runtime result/manifest/checkpoint `18/18/18` 완료를 기록했다.
  - [x] Health audit 기록 완료: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop371_golden18_after_loop370_runtime_health_audit.json`.
  - [x] Expected-answer audit와 collateral Markdown을 한국어로 정리했다.
- 품질 게이트:
  - [x] `runtime production GO / 18 of 18`와 semantic approval을 분리한다.
  - [x] manifest `mcp_health_light_mode=true` caveat를 숨기지 않는다.
  - [x] search degraded unrecovered `1`을 P0 open으로 유지한다.
  - [x] `11698880` wrong publish를 safe-loss 정당 해소로 쓰지 않는다.
  - [x] golden shared collateral `5` regressions를 full375 collateral approval과 분리한다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop370 search degraded-zero suppression quality gate

- 근거:
  - [x] 신규 대형 런과 동일 parent packet replay가 없음을 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_370_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop370_search_degraded_zero_suppression_20260703.json`.
  - [x] focused unittest `5` tests PASS와 `git diff --check` PASS를 기록했다.
- 품질 게이트:
  - [x] degraded-zero suppression을 정상 search cache hit로 세지 않는다.
  - [x] `degraded_zero_suppressed_total`을 검색 성공이나 hard-hold 완화 근거로 쓰지 않는다.
  - [x] runtime replay 전 search recovery 완료를 선언하지 않는다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop360 background watchdog hardening quality gate

- 근거:
  - [x] Loop359 background 런이 `0/0/0/0` completion 상태임을 manifest로 재확인했다.
  - [x] safe-loss first combined log에서 `llm-watchdog` 사용자 재개 대기 상태를 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_360_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop360_background_watchdog_hardening_20260703.json`.
  - [x] Review artifact 기록 완료: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop360_background_watchdog_hardening_review.json`.
  - [x] focused unittest `9` tests PASS를 기록했다.
- 품질 게이트:
  - [x] background launch health와 runtime completion을 분리한다.
  - [x] watchdog pause를 search recovery 또는 semantic failure로 오분류하지 않는다.
  - [x] result/checkpoint `0`인 런을 stale evidence replacement나 approval 근거로 쓰지 않는다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop359 current HEAD background dispatch quality gate

- 근거:
  - [x] 현 HEAD `6741ff80`에서 N5/full375/bounded1200/golden18을 새 prefix로 background 발주했다.
  - [x] shard audit `35/44` OK와 bad shard `1`, `37-44` 제외를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_359_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop359_current_head_background_dispatch_20260703.json`.
  - [x] collateral active lane snapshot 기록 완료: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop359_current_residual_background_separated_action_lane.json`.
- 품질 게이트:
  - [x] 발주와 approval을 분리한다.
  - [x] N5/golden18/full375/bounded completion 전 stale evidence replacement를 선언하지 않는다.
  - [x] active lane은 최신 residual `105` 기준이며 원본 collateral183 `126`으로 되돌리지 않는다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop358 LLM stream stall guard quality gate

- 근거:
  - [x] `11666713` image-free 단건 replay로 VLM 전용 stall이 아님을 분리했다.
  - [x] search health `GO 1/0`와 result/checkpoint 부재를 함께 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_358_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop358_llm_stream_timeout_guard_20260703.json`.
  - [x] Data Analytics artifact 기록 완료: `docs/devs/loop358_llm_stream_stall_data_analytics_artifact.json`.
  - [x] stream timeout unit 검증 PASS를 기록했다.
- 품질 게이트:
  - [x] search health GO와 runtime completion을 분리한다.
  - [x] result JSON 없음과 checkpoint `0`을 approval 근거에서 제외한다.
  - [x] stream timeout guard를 승격/매칭 로직 변경으로 쓰지 않는다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop357 known-alias comparison boundary quality gate

- 근거:
  - [x] `known_alias_runtime_replay_required=3`를 동일 stalled replay가 아니라 contract audit로 전환했다.
  - [x] comparison-only adjacent alias 실패를 재현했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_357_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop357_known_alias_comparison_boundary_20260703.json`.
  - [x] 관련 unit 검증 PASS를 기록했다.
- 품질 게이트:
  - [x] comparison target release 차단과 primary alias release 보존을 동시에 확인한다.
  - [x] runtime replay 전 residual closure를 선언하지 않는다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop356 current HEAD background dispatch quality gate

- 근거:
  - [x] 현 HEAD `4ebe824b`에서 N5/full375/bounded1200/golden18을 새 prefix로 background 발주했다.
  - [x] shard audit `35/44` OK와 bad shard `1`, `37-44` 제외를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_356_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop356_current_head_background_dispatch_20260703.json`.
- 품질 게이트:
  - [x] 발주와 approval을 분리한다.
  - [x] N5/golden18/full375/bounded completion 전 stale evidence replacement를 선언하지 않는다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop355 wrong-work alias contract quality gate

- 근거:
  - [x] `11698890`, `11700500`, `11705252`의 known-title-abbreviation work bridge 계약을 추가했다.
  - [x] 관련 unittest `63`개 PASS를 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_355_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop355_wrong_work_alias_contract_20260703.json`.
- 품질 게이트:
  - [x] registry-only positive promotion으로 기록하지 않는다.
  - [x] runtime replay 전 residual closure를 선언하지 않는다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop354 current residual forced action lane quality gate

- 근거:
  - [x] Loop353 current residual `105`를 입력으로 action lane을 생성했다.
  - [x] `split_collateral_action_queue.py --fail-on-validation-issue`가 validation issue `0`으로 통과했다.
  - [x] background PIDs `137688`, `16352`, `40088`, `138056`가 alive임을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_354_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop354_current_residual_forced_action_lane_20260703.json`.
- 품질 게이트:
  - [x] forced action lane을 approval과 분리한다.
  - [x] partial full375/bounded/golden/N5 snapshot을 stale evidence replacement로 쓰지 않는다.
  - [x] residual `105`, `REPROCESS=77`, `HOLD=28`, validation issue `0`을 기록한다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop353 11708470 non-light row closure quality gate

- 근거:
  - [x] Loop324 runtime health `7/7/0/0`, search 포함 non-light를 확인했다.
  - [x] `11708470` row가 expected title로 `safe_resolved`됐고 search degraded가 없음을 확인했다.
  - [x] `split_collateral_action_queue.py --fail-on-validation-issue`로 queue를 재생성했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_353_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop353_11708470_nonlight_row_closure_20260703.json`.
- 품질 게이트:
  - [x] Loop324 packet 전체 `NO-GO`와 row-level closure를 분리한다.
  - [x] residual `106 -> 105`와 validation issue `0`을 기록한다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop352 unsafe-promotion contract exclusion quality gate

- 근거:
  - [x] 입력 queue를 Loop349 current residual `120`으로 고정했다.
  - [x] Loop300/309 current contract replay `REPROCESS=14 -> promotion_blocked=14/14` 근거를 확인했다.
  - [x] `split_collateral_action_queue.py --fail-on-validation-issue`로 queue를 재생성했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_352_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop352_unsafe_promotion_contract_exclusion_20260703.json`.
- 품질 게이트:
  - [x] `repair_unsafe_promotion=14` 제외를 approval이나 hard-hold 완화로 쓰지 않는다.
  - [x] residual `120 -> 106`과 validation issue `0`을 기록한다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop351 stale evidence/background audit quality gate

- 근거:
  - [x] N5/full375/bounded/golden18 latest manifest를 확인했다.
  - [x] incomplete 결과를 stale evidence replacement로 쓰지 않았다.
  - [x] HEAD diff가 docs only임을 확인했지만 completion 판정은 manifest/result 기준으로 유지했다.
  - [x] golden files와 bootstrap/golden tools git tracking을 확인했다.
  - [x] search recovery probe 추적 예외를 추가했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_351_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop351_stale_evidence_background_audit_20260703.json`.
- 품질 게이트:
  - [x] 2026-06-28 golden GO를 current approval로 재사용하지 않는다.
  - [x] flip-rate는 N5 `15/15` 완료 전 갱신하지 않는다.
  - [x] 대형 런은 background 감시로 내리고 active lane은 residual queue/OVERRIDE AUDIT로 전환한다.
  - [x] search recovery 전 `promotion_blocked=search-blind conditional`을 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop336 post-patch runtime replay quality gate

- 근거:
  - [x] `11705250` post-patch search non-light 단건 replay를 완료했다.
  - [x] result/checkpoint/manifest counts `1/1/0/0`을 확인했다.
  - [x] public identity `심해의 마법사`, URL `https://m.munpia.com/novel/detail/483667` 복구를 확인했다.
  - [x] `publication_contract_convergence=GO`, violation `0`을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_336_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop336_post_patch_runtime_replay_20260703.json`.
- 품질 게이트:
  - [x] `SEARCH_DEGRADED` row를 approval 근거로 쓰지 않는다.
  - [x] result/checkpoint clean count와 full approval을 혼동하지 않는다.
  - [x] 순차 manifest completion field 누락을 코드로 보정했지만, 현재 artifact caveat는 유지한다.
  - [x] full375/bounded/golden/N5 partial snapshot을 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop335 consumption title-lead alias repair quality gate

- 근거:
  - [x] `11705250` false negative의 직접 원인을 title-lead alias 추출 누락으로 분리했다.
  - [x] 코드 변경 경로를 `src/llm_batch/agentic_pipeline.py`로 제한했다.
  - [x] 재현 테스트를 `tests/test_title_lead_search_inferred_guard.py`에 추가했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_335_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop335_consumption_title_lead_alias_repair_20260703.json`.
- 품질 게이트:
  - [x] semantic no-work 기본 차단을 그대로 유지한다.
  - [x] verified batch alias release context가 있을 때만 release 가능성을 연다.
  - [x] unit/broader test PASS를 runtime approval로 쓰지 않는다.
  - [x] post-patch runtime replay `NOT_RUN`, search recovery `P0 / OPEN`을 명시한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop334 override audit quality gate

- 근거:
  - [x] `11705250` current HEAD result 완료 `1/1/0/0`을 확인했다.
  - [x] old light internal override event와 public contract를 분리했다.
  - [x] prior native web judge와 live web 확인으로 expected `심해의 마법사`를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_334_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop334_override_audit_11705250_current_head_20260703.json`.
- 품질 게이트:
  - [x] public title/url leak 없음과 semantic false negative를 혼동하지 않는다.
  - [x] `SEARCH_DEGRADED` row를 approval 근거로 쓰지 않는다.
  - [x] search recovery 전 promotion gate hard-hold를 완화하지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-03 Loop333 collateral gate accounting quality gate

- 근거:
  - [x] Loop332 clean review summary `183/183`, validation issue `0`을 확인했다.
  - [x] `exclude_from_regression_count_after_gate_wiring=57`만 raw collateral regression count에서 차감했다.
  - [x] adjusted collateral regression count `126`을 gate report에 남겼다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_333_REPORT_20260703.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop333_collateral_gate_accounting_20260703.json`.
- 품질 게이트:
  - [x] raw `183`을 숨기지 않고 adjusted `126`과 함께 기록한다.
  - [x] dirty/partial review summary는 count 차감에 쓰지 않는다.
  - [x] adjusted residual `126`이 남으면 collateral gate는 `NO-GO`다.
  - [x] current HEAD golden18 expected-answer audit 미완료를 old golden GO로 대체하지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop322 safe-loss alias contract quality gate

- 근거:
  - [x] Loop321 source-native repair 후보 중 직접 별칭+작품 소비 cue 7건만 shared registry에 추가했다.
  - [x] `주전무`는 cue 폭 확장 위험 때문에 보류했다.
  - [x] 실제 Loop321 packet helper check에서 선택 7건은 allowed, 보류 1건은 blocked였다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_322_REPORT_20260702.md`.
- 품질 게이트:
  - [x] unit-level registry contract를 runtime replay나 full approval로 쓰지 않는다.
  - [x] registry alias는 `registry_anchor_only`/Medium 계약을 유지하며 hard evidence 없이 High로 올리지 않는다.
  - [x] recommendation/negated row는 release하지 않는 계약을 유지한다.
  - [x] Loop314 background progress는 Loop322 코드 이전 evidence라 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop321 safe-loss source-native quality gate

- 근거:
  - [x] Loop321 delta verdict `28`건을 작성했다.
  - [x] 누적 verdict `147/147`과 unreviewed `0`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] delta labels `REPROCESS=15`, `ACCEPT=9`, `HOLD=4`를 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_321_REPORT_20260702.md`.
- 품질 게이트:
  - [x] source-native queue closure를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=76`은 shared gate/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=42`는 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=29`는 native image/OCR/source/scope 확인 전까지 닫지 않는다.
  - [x] Loop314 partial progress를 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop320 safe-loss source-native quality gate

- 근거:
  - [x] Loop320 delta verdict `15`건을 작성했다.
  - [x] 누적 verdict `119/147`과 unreviewed `28`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] delta labels `REPROCESS=8`, `ACCEPT=5`, `HOLD=2`를 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_320_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial source-native review를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=61`은 shared gate/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=33`은 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=25`는 native image/web/source/canonical policy 확인 전까지 닫지 않는다.
  - [x] Loop314 partial progress를 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop319 OVERRIDE AUDIT quality gate

- 근거:
  - [x] `11708445` completed row를 result/checkpoint에서 확인했다.
  - [x] worker log의 `LLM=False -> final=True` 이벤트를 final result contract와 분리했다.
  - [x] public title/url이 `null/null`이고 `candidate_only / promotion_blocked`로 수렴했음을 확인했다.
  - [x] blind verdict `ACCEPT / candidate_only_block_is_correct`를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_319_REPORT_20260702.md`.
- 품질 게이트:
  - [x] 내부 override event를 public publish approval로 쓰지 않는다.
  - [x] 104k background light run을 full-scan approval 근거로 쓰지 않는다.
  - [x] search degraded가 남은 row는 `search-blind conditional`로 태깅한다.
  - [x] reason hygiene forbidden marker hit `0`을 확인했다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop318 safe-loss source-native quality gate

- 근거:
  - [x] Loop318 delta verdict `15`건을 작성했다.
  - [x] 누적 verdict `104/147`과 unreviewed `43`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] delta labels `REPROCESS=5`, `ACCEPT=7`, `HOLD=3`을 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_318_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial source-native review를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=53`은 shared gate/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=28`은 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=23`은 native image/web/source/scope/publish-trace 확인 전까지 닫지 않는다.
  - [x] `11698880` known variance control은 repair나 hard-hold 완화 근거로 세지 않는다.
  - [x] Loop314 partial progress를 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop317 safe-loss source-native quality gate

- 근거:
  - [x] Loop317 delta verdict `15`건을 작성했다.
  - [x] 누적 verdict `89/147`과 unreviewed `58`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] delta labels `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`를 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_317_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial source-native review를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=48`은 shared gate/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=21`은 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=20`은 native image/web/source/canonical policy 확인 전까지 닫지 않는다.
  - [x] Loop314 partial progress를 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop316 safe-loss source-native quality gate

- 근거:
  - [x] Loop316 delta verdict `15`건을 작성했다.
  - [x] 누적 verdict `74/147`과 unreviewed `73`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] delta labels `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`를 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_316_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial source-native review를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=41`은 shared gate/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=15`는 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=18`은 native image/web/source/canonical policy 확인 전까지 닫지 않는다.
  - [x] Loop314 partial progress를 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop315 character-setting bridge quality gate

- 근거:
  - [x] Loop312 `11669933` source-native verdict를 확인했다.
  - [x] `중경계/서휼/해방상제` cluster를 `회귀수선전` character-setting bridge로만 release하도록 positive test를 추가했다.
  - [x] 충돌 hidden work cluster 음성 control을 추가했다.
  - [x] shared work bridge ownership contract를 추가했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_315_REPORT_20260702.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop315_character_setting_bridge_contract_20260702.json`.
- 품질 게이트:
  - [x] unit contract를 runtime replay 또는 full approval로 쓰지 않는다.
  - [x] Loop314 partial background progress를 approval 근거로 쓰지 않는다.
  - [x] `회귀수선전`을 전역 alias registry release로 풀지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop314 current-HEAD dispatch quality gate

- 근거:
  - [x] Loop288/Loop302 background 프로세스가 Loop313 이전 코드로 시작됐음을 stale/mixed evidence로 분리했다.
  - [x] 현 HEAD `64864278` 기준 N5/full375/bounded/golden18을 새 경로로 발주했다.
  - [x] N5 runner 도구 `tools/run_independent_plan.py`를 추가하고 py_compile를 통과했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_314_REPORT_20260702.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop314_current_head_runtime_dispatch_20260702.json`.
- 품질 게이트:
  - [x] 기존 partial run을 current HEAD approval로 쓰지 않는다.
  - [x] 새 partial run도 완료 전 approval로 쓰지 않는다.
  - [x] N5 `0/15` 상태를 flip-rate 갱신으로 쓰지 않는다.
  - [x] golden18 완료 전 6/28 golden GO를 대체하지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop313 safe-loss alias contract quality gate

- 근거:
  - [x] `악살싶` canonical title을 shared registry에서 정정했다.
  - [x] `전독시` stable alias를 known-title abbreviation gate에 추가했다.
  - [x] adaptation cue를 work-cue에 추가했다.
  - [x] 동음 후보 위험이 있는 `악신총애`는 registry 추가를 보류했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_313_REPORT_20260702.md`.
  - [x] State JSON 기록 완료: `docs/devs/loop313_safe_loss_alias_contract_repair_20260702.json`.
- 품질 게이트:
  - [x] registry 자체를 public publish 권한으로 쓰지 않고 shared work-cue/promotion gate 입력으로만 둔다.
  - [x] unit-only 결과를 runtime replay나 full approval로 쓰지 않는다.
  - [x] N5 result `1/15` 상태를 flip-rate 갱신으로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop312 safe-loss source-native quality gate

- 근거:
  - [x] Loop312 delta verdict `15`건을 작성했다.
  - [x] 누적 verdict `59/147`과 unreviewed `88`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] delta labels `REPROCESS=7`, `ACCEPT=3`, `HOLD=5`를 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_312_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial source-native review를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=34`는 shared gate/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=9`는 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=16`은 native image/web/source/canonical policy 확인 전까지 닫지 않는다.
  - [x] N5 result `0/15` 상태를 flip-rate 갱신으로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop311 current HEAD runtime refresh quality gate

- 근거:
  - [x] search shard `/api/health`를 live로 확인했다.
  - [x] N5 plan을 background runner로 발주했다.
  - [x] golden18 row count와 `11660237/11698880` 포함을 확인했다.
  - [x] full375/bounded1200 health audit를 Loop311 이름으로 생성했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_311_REPORT_20260702.md`.
- 품질 게이트:
  - [x] N5 result `0/15` 상태를 flip-rate 갱신으로 쓰지 않는다.
  - [x] full375/bounded1200 partial progress를 approval 근거로 쓰지 않는다.
  - [x] search degraded/timeout blocker가 남으면 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] golden18 tracked 상태를 golden approval로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop310 safe-loss source-native quality gate

- 근거:
  - [x] Loop310 delta verdict `15`건을 작성했다.
  - [x] 누적 verdict `44/147`과 unreviewed `103`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] delta labels `REPROCESS=4`, `ACCEPT=2`, `HOLD=9`를 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_310_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial source-native review를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=27`은 shared gate/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=6`은 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=11`은 native image/web/canonical policy 확인 전까지 닫지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop307 safe-loss alias contract quality gate

- 근거:
  - [x] Loop307 report 기록 완료: `docs/devs/loop_reports/LOOP_307_REPORT_20260702.md`.
  - [x] state JSON 기록 완료: `docs/devs/loop307_safe_loss_alias_contract_expansion_20260702.json`.
  - [x] N5 flip-rate current HEAD 분석을 새로 생성했다.
  - [x] full375/bounded1200 최신 health audit를 새로 생성했다.
  - [x] Data Analytics validate/render PASS를 기록했다.
- 품질 게이트:
  - [x] `가챠펑크`와 `즉사기`는 search-blind registry release 대상에서 제외했다.
  - [x] N5 flip `NO-GO`이므로 hard-hold 완화를 허용하지 않는다.
  - [x] full375/bounded1200은 `IN_PROGRESS`라 approval 근거로 쓰지 않는다.
  - [x] `search_degraded_observed`가 남아 `promotion_blocked`는 계속 `search-blind conditional`로 해석한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop306 safe-loss source-native next slice quality gate

- 근거:
  - [x] 누적 verdict `29/147`과 unreviewed `118`을 기록했다.
  - [x] validation issue `0`인 summary JSON/MD를 생성했다.
  - [x] `REPROCESS=23`, `ACCEPT=4`, `HOLD=2`를 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_306_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial source-native review를 full collateral approval로 쓰지 않는다.
  - [x] `repair_safe_loss=23`은 targeted guard/runtime replay 전까지 queue closure가 아니다.
  - [x] `ACCEPT=4`는 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
  - [x] `HOLD=2`는 native image/source 확인 전까지 닫지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop305 safe-loss alias targeted replay quality gate

- 근거:
  - [x] Loop304 alias seed를 `11`행 targeted replay 입력으로 만들었다.
  - [x] search shard audit `ok=12/12`를 남겼다.
  - [x] replay run id `20260702_181813_388157`와 PID `16380`을 기록했다.
  - [x] in-progress health audit을 남겼다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_305_REPORT_20260702.md`.
- 품질 게이트:
  - [x] completed `0`이므로 replay 성공이나 queue 감소로 쓰지 않는다.
  - [x] small-run health가 `include_search=false`, `light_mode=true`이므로 search recovery approval 증거로 쓰지 않는다.
  - [x] Loop305 control 3건을 N5 flip-rate 갱신으로 계산하지 않는다.
  - [x] full375/bounded 완료 전 approval 근거로 쓰지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop303 runtime recovery quality gate

- 근거:
  - [x] search health `3333/3334` OK와 MCP bridge `36`을 기록했다.
  - [x] N5 first row가 search를 통과했지만 LLM 장기화로 result JSON이 없음을 기록했다.
  - [x] full375/bounded1200 audit을 새로 남겼다.
  - [x] 104k는 light/search-not-included라 approval 근거가 아님을 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_303_REPORT_20260702.md`.
- 품질 게이트:
  - [x] search runtime 복구와 search degraded 복구를 분리한다.
  - [x] N5 flip rate를 갱신했다고 쓰지 않는다.
  - [x] full375/bounded1200 완료 전 approval 근거로 쓰지 않는다.
  - [x] `promotion_blocked`는 계속 `search-blind conditional`로 태깅한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop302 current HEAD refresh quality gate

- 근거:
  - [x] 현 HEAD `e991a687`를 기록했다.
  - [x] N5 독립 실행 plan `15`개를 만들었다.
  - [x] 실행 결과 JSON이 `0`개임을 확인했다.
  - [x] search shard `3333/3334` 연결 실패와 Docker API/Internal Service blocker를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_302_REPORT_20260702.md`.
- 품질 게이트:
  - [x] result JSON이 없으므로 stale flip rate를 갱신했다고 쓰지 않는다.
  - [x] Loop288 background snapshot을 현 HEAD approval 근거로 재사용하지 않는다.
  - [x] golden18 추적 확인은 approval이 아니라 입력/게이트 준비 상태로만 본다.
  - [x] 검색 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] 코드 변경 없음 3연속이면 대형 run 대기 대신 collateral183 triage 또는 OVERRIDE AUDIT blind judge 검증으로 강제 전환한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop301 safe-loss seed quality gate

- 근거:
  - [x] `safe_loss_resolved_to_null=147` 전용 batch를 생성했다.
  - [x] selected rows `147`, missing source/baseline/after `0/0/0`을 기록했다.
  - [x] seed verdict `15/147`, validation issues `0`, `REPROCESS=14`, `ACCEPT=1`, unreviewed `132`를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_301_REPORT_20260702.md`.
- 품질 게이트:
  - [x] Loop301은 partial source-native verdict이지 full collateral approval이 아니다.
  - [x] `REPROCESS=14`는 targeted guard/runtime follow-up 전까지 닫지 않는다.
  - [x] `ACCEPT=1`은 gate 배선 뒤 regression count 제외 후보로만 둔다.
  - [x] search degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop300 unsafe promotion full verdict quality gate

- 근거:
  - [x] `unsafe_promotion_from_hold=26` 전체를 source-native verdict로 닫았다.
  - [x] validation issues `0`, `REPROCESS=14`, `ACCEPT=12`, unreviewed `0`을 기록했다.
  - [x] current HEAD replay에서 match/mismatch `26/0`을 확인했다.
  - [x] related bundle 137 tests PASS를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_300_REPORT_20260702.md`.
- 품질 게이트:
  - [x] Loop300은 action queue 수렴과 unit/legacy replay evidence이지 full collateral approval이 아니다.
  - [x] `ACCEPT=12`는 current gate 배선에서 `safe_resolved`로 수렴하지만 search 복구 전 full approval 근거로 쓰지 않는다.
  - [x] `REPROCESS=14`는 targeted guard/runtime follow-up 전까지 full collateral count에서 닫지 않는다.
  - [x] search degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop299 unsafe promotion contract quality gate

- 근거:
  - [x] Loop298 `repair_unsafe_promotion=8`을 current HEAD shared contract로 재현했다.
  - [x] 8/8 REPROCESS row가 legacy replay에서 `promotion_blocked`로 demote됨을 확인했다.
  - [x] positive controls `11674712`, `11695623`, `11669928`은 `safe_resolved`를 유지했다.
  - [x] related bundle 173 tests PASS를 기록했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_299_REPORT_20260702.md`.
- 품질 게이트:
  - [x] Loop299는 unit/legacy replay evidence이지 full collateral approval이 아니다.
  - [x] background run 3개는 완료 전 approval 근거로 쓰지 않는다.
  - [x] search degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop298 unsafe promotion review quality gate

- 근거:
  - [x] `unsafe_promotion_from_hold=26`을 독립 batch로 분리했다.
  - [x] `15/26` source-native partial verdict를 작성했다.
  - [x] validation issues `0`, `REPROCESS=8`, `ACCEPT=7`, unreviewed `11`을 기록했다.
  - [x] 도구가 bucket filter와 partial coverage를 기록하도록 보강됐다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_298_REPORT_20260702.md`.
- 품질 게이트:
  - [x] partial verdict는 action queue 분해이며 full collateral approval이 아니다.
  - [x] `ACCEPT=7`은 gate 배선 전까지 regression count 제외 근거로만 둔다.
  - [x] `REPROCESS=8`은 targeted guard/runtime follow-up 전까지 닫지 않는다.
  - [x] unreviewed `11`은 native web/image 확인 없이 닫지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop297 background health quality gate

- 근거:
  - [x] full375, bounded1200, golden18 background run을 완료 전 approval 근거로 쓰지 않고 health audit로만 기록했다.
  - [x] latest manifest snapshot을 남겼다: full375 `375/53/51/2/0`, bounded1200 `1200/88/77/11/0`, golden18 `18/16/12/4/0`.
  - [x] 세 audit 모두 `IN_PROGRESS/ordered_flush_gap_in_progress`임을 확인했다.
  - [x] search degraded blocker가 계속 열려 있음을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_297_REPORT_20260702.md`.
- 품질 게이트:
  - [x] `publication_contract_convergence=GO`는 현재 flushed rows의 구조 계약만 뜻한다.
  - [x] full375 완료 전 collateral approval을 열지 않는다.
  - [x] golden18 완료 전 6/28 golden GO를 대체하지 않는다.
  - [x] search degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop291 wrong-work title flip review quality gate

- 근거:
  - [x] Loop290 `wrong_work_title_flip` 10행을 source-native verdict로 판정했다.
  - [x] `REPROCESS=5`, `ACCEPT=3`, `HOLD=2`, validation issues `0`을 파일로 남겼다.
  - [x] Data Analytics MCP report를 한국어로 작성하고 validate/render했다.
  - [x] background full375/bounded/golden18 런을 완료 전 approval 근거로 쓰지 않았다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_291_REPORT_20260702.md`.
- 품질 게이트:
  - [x] Loop291 source-native label은 approval 산출물이 아니라 수리 큐다.
  - [x] `REPROCESS` 5건은 targeted guard/runtime follow-up 전까지 닫지 않는다.
  - [x] `HOLD` 2건은 wrong-work로 강제 계산하지 않고 canonical title variant 정책으로 분리한다.
  - [x] 검색 degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop290 collateral183 P0 review batch quality gate

- 근거:
  - [x] background full375/bounded/golden18 런을 완료 전 approval 근거로 쓰지 않았다.
  - [x] collateral183 P0 전체 `183`행을 blind/source-native 검토 배치로 생성했다.
  - [x] source/baseline/after row 누락이 `0/0/0`임을 확인했다.
  - [x] judge-facing 입력에서 전후 비교와 `reason_lines`를 제외했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_290_REPORT_20260702.md`.
- 품질 게이트:
  - [x] review batch는 정답 라벨 입력이지 approval 산출물이 아니다.
  - [x] native web 확인 전 `needs_native_web_check=true`를 유지한다.
  - [x] 검색 degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop289 background / collateral183 quality gate

- 근거:
  - [x] background 런 3개를 현재 manifest/checkpoint/result/log 기준으로 재감사했다.
  - [x] bounded1200의 `search_degraded_observed`를 P0 blocker로 기록했다.
  - [x] full375/golden18 미완료 상태를 old GO나 approval 근거로 쓰지 않았다.
  - [x] collateral183 regression row를 P0 bucket으로 분류했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_289_REPORT_20260702.md`.
- 품질 게이트:
  - [x] background run 완료 전 full375 collateral approval을 열지 않는다.
  - [x] collateral triage는 우선순위 산출물이며 approval 산출물이 아니다.
  - [x] P0 bucket은 blind judge 또는 source-native review 없이는 닫지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop288 safe-loss / search recovery quality gate

- 근거:
  - [x] current HEAD safe-loss N5 결과를 파일로 남겼다.
  - [x] blind judge 기준과 반복 outcome을 분리해 기록했다.
  - [x] golden set `16 -> 18` 갱신과 추가 행 근거 manifest를 남겼다.
  - [x] full375와 bounded1200 search 포함 non-light 런을 background로 발주했다.
  - [x] Data Analytics artifact validate/render를 통과했다.
- 품질 게이트:
  - [x] `11674712`, `11698880` 진동을 safe loss로 승인하지 않는다.
  - [x] `11660237` stable 확인은 hard-hold 완화 전체 승인이 아니라 golden 편입 근거로만 쓴다.
  - [x] 검색 degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
  - [x] full375/bounded/golden18 background 완료 전 full collateral approval을 열지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop287 frontier release quality gate

- 근거:
  - [x] Loop264 대형 run의 최신 health audit를 실행했다.
  - [x] completed source 후보 감사를 재실행했다.
  - [x] `11708456` result JSON contract가 candidate-only/promotion_blocked/multi_work임을 확인했다.
  - [x] W24 log에서 새 frontier `11708445`이 진행 중임을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_287_REPORT_20260702.md`.
- 품질 게이트:
  - [x] `11708456` release를 hard-hold 완화나 public approval로 해석하지 않는다.
  - [x] live run은 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 completed source가 아니다.
  - [x] post-audit live poll `next_save_idx=367`은 별도 audit 전까지 approval 근거로 세지 않는다.
  - [x] `publication_contract_convergence=GO`는 flushed `354` rows contract 수렴만 뜻한다.
  - [x] completed source 후보가 없으므로 random baseline/P0-P1 expansion/full375 collateral approval을 열지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop286 frontier release quality gate

- 근거:
  - [x] Loop264 대형 run의 최신 health audit를 실행했다.
  - [x] completed source 후보 감사를 재실행했다.
  - [x] `11710018` result JSON contract가 candidate-only/promotion_blocked임을 확인했다.
  - [x] W20 log에서 새 frontier `11708456`이 Arbiter stream 진행 중임을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_286_REPORT_20260702.md`.
- 품질 게이트:
  - [x] `11710018` release를 hard-hold 완화나 public approval로 해석하지 않는다.
  - [x] live run은 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 completed source가 아니다.
  - [x] `publication_contract_convergence=GO`는 flushed `343` rows contract 수렴만 뜻한다.
  - [x] completed source 후보가 없으므로 random baseline/P0-P1 expansion/full375 collateral approval을 열지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop285 frontier reason_review quality gate

- 근거:
  - [x] Loop264 대형 run의 최신 health audit를 실행했다.
  - [x] completed source 후보 감사를 재실행했다.
  - [x] W25 log에서 `11710018`의 reason_review 완료와 candidate URL 제거를 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_285_REPORT_20260702.md`.
- 품질 게이트:
  - [x] live run은 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 completed source가 아니다.
  - [x] `11710018`은 result JSON에 없고, 뒤쪽 completed rows 증가는 approval 근거가 아니다.
  - [x] `publication_contract_convergence=GO`는 flushed `317` rows contract 수렴만 뜻한다.
  - [x] completed source 후보가 없으므로 random baseline/P0-P1 expansion/full375 collateral approval을 열지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop280 live health / completed source candidate quality gate

- 근거:
  - [x] Loop264 대형 run의 최신 health audit를 실행했다.
  - [x] completed source 후보 감사를 재실행했다.
  - [x] approval_source_candidate_count `0`을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_280_REPORT_20260702.md`.
- 품질 게이트:
  - [x] live run은 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 completed source가 아니다.
  - [x] `publication_contract_convergence=GO`는 flushed rows contract 수렴만 뜻한다.
  - [x] completed source 후보가 없으므로 random baseline/P0-P1 expansion/full approval을 열지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop279 frontier timing health quality gate

- 근거:
  - [x] Loop264 대형 run의 최신 health audit를 실행했다.
  - [x] frontier worker trace가 worker/event뿐 아니라 elapsed time을 기록한다.
  - [x] Loop278 이후 `next_save_idx=204 -> 219` 전진을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_279_REPORT_20260702.md`.
- 품질 게이트:
  - [x] health audit는 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 completed source가 아니다.
  - [x] observed elapsed는 frontier 판단 보조 지표이며 approval 근거가 아니다.
  - [x] `publication_contract_convergence=GO`는 flushed rows contract 수렴만 뜻한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop278 live run health / Synthesizer hidden reference quality gate

- 근거:
  - [x] Loop264 대형 run의 최신 health audit를 실행했다.
  - [x] ordered flush frontier와 worker trace를 같은 audit에 남겼다.
  - [x] Synthesizer `hidden_references` non-dict item 로깅 예외를 재현 가능한 로그 근거로 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_278_REPORT_20260702.md`.
- 품질 게이트:
  - [x] health audit는 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 completed source가 아니다.
  - [x] `publication_contract_convergence=GO`는 flushed rows contract 수렴만 뜻한다.
  - [x] Synthesizer hidden reference guard는 runtime hygiene patch이며 semantic approval 근거가 아니다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop277 completed source 후보 publication contract quality gate

- 근거:
  - [x] completed source 후보 감사가 `publication_contract_convergence_gate=GO`를 approval source candidate 조건으로 요구한다.
  - [x] clean/VLM/OCR/search/random/result 조건을 통과했지만 publication contract가 준비되지 않은 source를 별도 목록으로 남긴다.
  - [x] 실제 `out` manifest 후보 감사를 재실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_277_REPORT_20260702.md`.
- 품질 게이트:
  - [x] approval_source_candidate_count `0`을 유지한다.
  - [x] 현재는 random target `1000`을 만족하는 clean completed source가 없어 publication contract blocker 후보도 `0`임을 기록한다.
  - [x] publication contract requirement `ENFORCED`를 residual 감소나 full approval로 해석하지 않는다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop276 integrated health audit quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 `publication_contract_convergence`를 top-level gate로 기록한다.
  - [x] health audit 한 번으로 run integrity, frontier trace, search evidence, publication contract convergence를 함께 본다.
  - [x] 실제 Loop264 진행 중 run에서 통합 health audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_276_REPORT_20260702.md`.
- 품질 게이트:
  - [x] flushed result `164`행의 publication contract convergence는 `GO`, violation `0`이다.
  - [x] 같은 audit에서 run integrity는 `IN_PROGRESS`, search evidence는 `REVIEW`라 approval blocker가 남아 있다.
  - [x] run 완료 후 final health audit에서 세 gate를 다시 확인한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop275 publication contract convergence quality gate

- 근거:
  - [x] `audit_publication_contract_convergence.py`가 result row의 publication contract 수렴을 감사한다.
  - [x] stale trace, missing contract, blocked public leak를 계약 테스트로 잡는다.
  - [x] 실제 Loop264 진행 중 flushed result에서 audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_275_REPORT_20260702.md`.
- 품질 게이트:
  - [x] flushed result `162`행의 publication contract convergence는 `GO`, violation `0`이다.
  - [x] 이 `GO`는 artifact-level contract gate이며 completed source나 semantic approval이 아니다.
  - [x] run 완료 후 final result 전체에 같은 audit를 다시 실행한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop274 frontier worker trace quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 `frontier_worker_trace`를 기록한다.
  - [x] frontier source post의 worker, event_count, first_event, last_event를 audit JSON에 남긴다.
  - [x] 실제 Loop264 진행 중 run에서 frontier worker trace audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_274_REPORT_20260702.md`.
- 품질 게이트:
  - [x] frontier post `11714889`는 worker `W35`에서 `arbiter_start`까지 관측됐고 completed source가 아니다.
  - [x] 현재 audit의 `run_integrity_gate=IN_PROGRESS`와 `search_evidence=REVIEW`를 approval blocker로 유지한다.
  - [x] 동일 38-row parent packet 재실행 대신 worker trace와 final health audit로 다음 상태를 확인한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop273 completed source 후보 quality gate

- 근거:
  - [x] completed source 후보 감사가 `search_health_ready=true`를 approval source candidate 조건으로 요구한다.
  - [x] clean VLM/OCR source 중 direct search-health 미준비 수를 별도 카운트한다.
  - [x] 실제 `out` manifest 후보 감사를 재실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_273_REPORT_20260702.md`.
- 품질 게이트:
  - [x] approval_source_candidate_count `0`을 유지한다.
  - [x] clean_vlm_ocr_search_health_not_ready_count `420`을 approval blocker evidence로 남긴다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop272 search evidence quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 `search_evidence` gate를 기록한다.
  - [x] manifest direct search-health, row-level `search_health`, worker log search counters를 분리한다.
  - [x] 실제 Loop264 진행 중 run에서 search evidence audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_272_REPORT_20260702.md`.
- 품질 게이트:
  - [x] light-health-only manifest는 approval-ready가 아니다.
  - [x] 현재 audit의 `search_evidence=REVIEW`를 completed-source approval blocker로 유지한다.
  - [x] 최신 manifest `104502/155/129/26/0`, `large_run_complete=false`를 run integrity `IN_PROGRESS`로 둔다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop271 frontier source lookup quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 `--input-jsonl`로 frontier source post를 기록한다.
  - [x] comment row를 제외한 expert_main post map order 기반 lookup을 사용한다.
  - [x] 실제 Loop264 진행 중 run에서 frontier source audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_271_REPORT_20260702.md`.
- 품질 게이트:
  - [x] frontier post는 `11716449`, title `케문제는 ㄹㅇ 애증의 소설임`, source_line `133`이다.
  - [x] `global_idx=118`과 raw `source_line=133`은 다르므로 혼동하지 않는다.
  - [x] 최신 manifest `104502/135/117/18/0`, `large_run_complete=false`를 run integrity `IN_PROGRESS`로 둔다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop270 flush frontier diagnostics quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 `next_save_idx` frontier 상태를 기록한다.
  - [x] frontier가 checkpoint/pending 양쪽에 없는 경우 `in_flight_or_missing`으로 분리한다.
  - [x] 실제 Loop264 진행 중 run에서 frontier audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_270_REPORT_20260702.md`.
- 품질 게이트:
  - [x] frontier `91`이 checkpoint/pending에 없고 pending은 `93`부터 시작하므로, 현재는 frontier row 미완료로 ordered flush가 막힌 상태다.
  - [x] 이 상태는 run integrity `IN_PROGRESS`이며 completed source나 approval이 아니다.
  - [x] 최신 manifest `104502/128/90/38/0`, `large_run_complete=false`를 run integrity `IN_PROGRESS`로 둔다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop269 flush integrity classifier quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 manifest/checkpoint/result/pending count 정합성을 직접 분류한다.
  - [x] clean completion, ordered flush gap, artifact mismatch 계약 테스트를 추가했다.
  - [x] 실제 Loop264 진행 중 run에서 flush integrity audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_269_REPORT_20260702.md`.
- 품질 게이트:
  - [x] audit snapshot `IN_PROGRESS/ordered_flush_gap_in_progress`는 artifact mismatch가 아니라 진행 중 ordered flush gap이다.
  - [x] result/flushed, checkpoint/completed, pending/completed-minus-flushed consistency가 모두 `true`여도 completed source는 아니다.
  - [x] 최신 manifest `104502/119/80/39/0`, `large_run_complete=false`를 run integrity `IN_PROGRESS`로 둔다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop268 result JSON health audit quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 result JSON 경로를 직접 받도록 보강했다.
  - [x] result row count가 `result_rows`와 `result_json`에 남도록 했다.
  - [x] 실제 Loop264 진행 중 run에서 explicit result audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_268_REPORT_20260702.md`.
- 품질 게이트:
  - [x] result_rows `12`와 flushed_count `12`는 현재 primary result JSON이 ordered flushed prefix임을 뜻한다.
  - [x] checkpoint_rows `95`, pending_count_actual `83`은 completed source 완료가 아니라 ordered flush gap 진행 중 증거로 둔다.
  - [x] 최신 manifest `104502/95/12/83/0`, `large_run_complete=false`를 run integrity `IN_PROGRESS`로 둔다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop267 explicit path health audit quality gate

- 근거:
  - [x] `audit_expert_run_health.py`가 manifest/checkpoint/pending/log glob 경로를 직접 받도록 보강했다.
  - [x] explicit path override가 `artifact_resolution.explicit_overrides`에 남도록 했다.
  - [x] 실제 Loop264 진행 중 run에서 explicit path audit를 실행했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_267_REPORT_20260702.md`.
- 품질 게이트:
  - [x] explicit path audit `PASS`는 completed source approval이 아니다.
  - [x] 최신 manifest `90/12/78/0`, `large_run_complete=false`를 run integrity `IN_PROGRESS`로 둔다.
  - [x] `mcp_health_include_search=false`, `mcp_health_light_mode=true` caveat를 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop265 strict always-on gate quality gate

- 근거:
  - [x] full375 collateral diff가 runtime count 없는 산출물로 통과하지 못하도록 코드를 강화했다.
  - [x] `collateral_runtime_counts_missing` blocker 계약 테스트를 추가했다.
  - [x] 강화된 gate로 기존 golden/full375 산출물을 재평가했다.
  - [x] Data Analytics 표/차트 산출물을 validate/render/export했다.
- 품질 게이트:
  - [x] golden-16 `GO`만으로 approval을 갱신하지 않는다.
  - [x] full375 collateral `NO-GO`와 regression candidates `183`을 유지한다.
  - [x] `11660237` flip이 남아 있어 hard-hold 완화 금지를 유지한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop264 completed source launch quality gate

- 근거:
  - [x] full input `tests\inputs\test01.jsonl`을 runtime preflight했다.
  - [x] LLM endpoint가 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`를 반환함을 확인했다.
  - [x] MCP TCP shard `36/36` open을 확인했다.
  - [x] completed-source attempt를 `--reuse-shards-only`, `--slang-db off`, `--vlm on`, `--ocr on`, `--require-vlm-ocr-for-images`로 시작했다.
  - [x] 초기 manifest에서 VLM/OCR ready, image_post_count `55259`, health `36/36`을 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_264_REPORT_20260702.md`.
- 품질 게이트:
  - [x] launch `GO_STARTED`는 completed source나 semantic approval이 아니다.
  - [x] initial completed/flushed/pending/failed `0/0/0/0` 상태에서는 random baseline/P0-P1 expansion을 시작하지 않는다.
  - [x] `mcp_health_include_search=false`, `mcp_health_light_mode=true` caveat를 완료 후 runtime audit에서 다시 확인한다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop262 completed source candidate quality gate

- 근거:
  - [x] 전체 `out` manifest `732`개를 구조적으로 감사했다.
  - [x] approval source candidate가 `0`개임을 기록했다.
  - [x] 가장 큰 clean source는 `375` rows라 random baseline `1000`에 `625` 부족함을 preflight로 확인했다.
  - [x] 가장 큰 partial source는 `3812` rows가 있지만 pending/failed/flush gap 때문에 approval source가 아님을 preflight로 확인했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_262_REPORT_20260702.md`.
- 품질 게이트:
  - [x] completed source candidate `MISSING`, completed-source preflight `REVIEW-LOCKED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
  - [x] partial source의 random feasibility를 approval evidence로 쓰지 않는다.

## 2026-07-02 Loop261 source preflight quality gate

- 근거:
  - [x] 작은 canary의 runtime/coverage `GO`가 completed source preflight를 대체하지 못하게 했다.
  - [x] `source_review_policy.path_present=false`는 approval blocker다.
  - [x] completed source 확보, completed-source preflight, random baseline 1000, P0/P1 high-risk expansion을 별도 blocker로 유지했다.
  - [x] Loop261 queue output: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop261_loop258_goal_action_queue_source_preflight_required.md`.
  - [x] Loop261 convergence output: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop261_loop258_source_preflight_goal_convergence.md`.
- 품질 게이트:
  - [x] convergence `NO-GO`, completed source preflight `MISSING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
  - [x] Loop260 local convergence `GO`를 full semantic approval로 쓰지 않는다.

## 2026-07-02 Loop260 comment-author review label / queue semantics quality gate

- 근거:
  - [x] 동일 38-row parent packet을 재실행하지 않았다.
  - [x] `11658637`의 comment author marker는 작품명 확정의 필수 근거가 아님을 packet review label로 확인했다.
  - [x] direct image/OCR/official URL evidence가 final publish를 독립 지지한다.
  - [x] `--review-labels` closure는 `REVIEW` 전용 issue만 닫고 `REVIEW-LOCKED` hard blocker는 닫지 않도록 테스트했다.
  - [x] current-source audit 완료 항목은 action queue에서 `done`으로 분리했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_260_REPORT_20260702.md`.
- 품질 게이트:
  - [x] Semantic coverage gate `GO`를 10만 건 semantic approval로 쓰지 않는다.
  - [x] Convergence `GO`를 full scan approval로 쓰지 않는다.
  - [x] `p0_p1_high_risk_expansion`이 남아 있으면 approval blocker를 유지한다.
  - [x] full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop251 11663535 character-title collision quality gate

- 근거:
  - [x] 동일 38-row parent packet을 재실행하지 않았다.
  - [x] Loop248 `11663535` `조선 퇴마록` public-title drift를 P0D blocker로 분리했다.
  - [x] `character_title_collision(major)`와 후보 제목 직접 언급 부재를 resolved-public-title scope conflict로 반영했다.
  - [x] `_post_discusses_work_as_work(...)` shared predicate를 경유해 단일 술어 계약을 유지했다.
  - [x] Loop251 patched run은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`로 runtime `GO`다.
  - [x] 최종 serialized output은 public title/url `null`, `candidate_ledger_status=promotion_blocked`, `publish_allowed=false`다.
  - [x] reason hygiene hit_files `0`.
  - [x] title-lead `176`, candidate-audit `107`, promotion trace/contract `55`, architecture gate/work-bridge `19`, py_compile PASS.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_251_REPORT_20260702.md`.
- 품질 게이트:
  - [x] targeted canary `GO_BLOCK_PUBLIC_TITLE`를 full scan approval로 쓰지 않는다.
  - [x] semantic coverage `GO`를 full semantic approval로 쓰지 않는다.
  - [x] convergence `NO-GO(queue 7 -> 7, packet identity changed)`를 approval blocker로 유지한다.
  - [x] Parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop250 11658668 image scope guard quality gate

- 근거:
  - [x] 동일 38-row parent packet을 재실행하지 않았다.
  - [x] Loop249 pre-patch 실패를 보존했다: `safe_resolved`, `publish_allowed=true`, `scope_kind=current_work`.
  - [x] image catalog `promotion_eligible=false`를 resolved-public-title scope conflict로 반영했다.
  - [x] Loop250 patched run은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`로 runtime `GO`다.
  - [x] 최종 serialized output은 public title/url `null`, `candidate_ledger_status=promotion_blocked`, `publish_allowed=false`다.
  - [x] `publish_contract_trace`가 blocked decision으로 수렴했다.
  - [x] reason hygiene hit_files `0`.
  - [x] title-lead suite `174` tests PASS, architecture gate/work-bridge `19` tests PASS, py_compile PASS.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_250_REPORT_20260702.md`.
- 품질 게이트:
  - [x] targeted canary `GO`를 full scan approval로 쓰지 않는다.
  - [x] runtime `GO`와 reason hygiene `GO`를 semantic coverage approval로 합치지 않는다.
  - [x] browser visual required/available/missing `1/0/1`이면 semantic coverage는 `REVIEW-LOCKED`다.
  - [x] convergence `NO-GO(queue 7 -> 7, packet identity changed)`를 approval blocker로 유지한다.
  - [x] Parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop248 P0 representative / reason hygiene quality gate

- 근거:
  - [x] 동일 38-row parent packet을 재실행하지 않았다.
  - [x] Loop51 P0 collateral bucket 대표 7건으로 current-code 상태만 진단했다.
  - [x] runtime은 completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`로 `GO`다.
  - [x] 원본 reason hygiene failure를 보존했다: hit_files `1`, `llm_flip` hit_count `2`.
  - [x] 공개 reason에 내부 `LLM(False)→최종(True)` marker가 남지 않도록 code/test를 보강했다.
  - [x] sanitized preview reason hygiene scan은 hit_files `0`이다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_248_REPORT_20260702.md`.
- 품질 게이트:
  - [x] sanitized preview `GO`를 원본 Loop248 result approval로 쓰지 않는다.
  - [x] Runtime `GO`와 reason hygiene `GO`를 semantic coverage approval로 합치지 않는다.
  - [x] browser visual required/available/missing `5/0/5`이면 semantic coverage는 `REVIEW-LOCKED`다.
  - [x] `11658668` platform meta / expert conflict publish는 별도 P0C blocker로 남긴다.
  - [x] `11663535` canonicalization drift는 별도 P0D blocker로 남긴다.
  - [x] Parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 Loop247 browser visual coverage quality gate

- 근거:
  - [x] `11660237` browser visual target 1건을 생성했다.
  - [x] fallback Playwright browser artifact를 남겼고, in-app Browser 직접 성공으로 과장하지 않았다.
  - [x] screenshot을 직접 확인했다.
  - [x] article image loading counter가 통과했다: loaded/total `1/1`, pending/placeholder/broken `0`.
  - [x] semantic coverage rerun이 `browser_visual_required/available/missing=1/1/0`, gate `GO`, issues `[]`를 기록했다.
  - [x] action queue는 semantic coverage gate `GO`를 반영했지만 approval blocker `p0_p1_high_risk_expansion`을 유지했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_247_REPORT_20260702.md`.
- 품질 게이트:
  - [x] Browser visual coverage GO를 full semantic approval로 쓰지 않는다.
  - [x] 이미지 catalog가 `promotion_eligible=false`, `title_role=unknown`이면 작품 title 직접 근거로 쓰지 않는다.
  - [x] Fallback artifact는 fallback으로 표기하고 Codex in-app Browser 직접 성공으로 기록하지 않는다.
  - [x] Parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop238 architecture convergence / flip-rate quality gate

- 근거:
  - [x] 동일 38-row parent packet 즉시 재실행을 중단하고 회차 수 기반 stop condition을 폐기했다.
  - [x] `PromotionDecision`, `publish_contract_trace`, `publish_ledger`, `candidate_ledger` 수렴 계약을 코드와 단위 테스트로 추가했다.
  - [x] `_has_verified_contextual_alias_work_bridge`가 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")` 계약을 경유하도록 배선했다.
  - [x] Alias bridge 없는 relation-hold 후보는 새 경유 로직에서도 계속 차단되는지 확인했다.
  - [x] Safe-loss 후보 `11674712`, `11660237`, `11698880`을 동일 입력 N=3 반복으로 측정했다.
  - [x] `11660237`은 `safe_resolved` 2회 / `promotion_blocked` 1회로 진동해 `nondeterminism_unresolved`로 분류했다.
  - [x] Blind judge 기대 title/url은 맞았지만, 진동 row가 있어 hard-hold relaxation을 허용하지 않았다.
  - [x] Golden-16 + full 375 collateral diff 조합 게이트를 작성하고 산출물을 보존했다.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_238_REPORT_20260701.md`.
- 품질 게이트:
  - [x] 다음 회차 시작 전 `actionable queue 감소`와 동일 packet `safe_resolved` 단조 비감소를 동시에 요구한다.
  - [x] Safe-loss row가 진동하면 safe loss가 아니라 비결정 미해소로 분류한다.
  - [x] Blind judge 정답성만으로 hard-hold를 완화하지 않는다. 반복 안정성이 같이 필요하다.
  - [x] Verified contextual alias release는 전용 source 경로에서만 허용한다.
  - [x] Golden-16 PASS만으로 approval을 주장하지 않는다.
  - [x] Full 375 collateral regression이 0이 아니면 full-panel gate는 `NO-GO`다.
  - [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop237 parent replay quality gate

- 근거:
  - [x] Loop237 parent replay run `20260701_215903_177630` 완료: completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`.
  - [x] Runtime integrity `GO_PARENT_RUNTIME_38_38`를 semantic result와 분리했다.
  - [x] Semantic result `NO-GO / MIXED_MOVEMENT / SAFE_COUNT_DROP`를 기록했다.
  - [x] `11663540` parent survival failure를 기록했다.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_237_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] `py_compile`, focused 3 tests, metadata 32 tests, promotion/candidate 128 tests PASS.
  - [x] JSON parse와 `git diff --check` PASS.
- 품질 게이트:
  - [x] Parent runtime GO를 approval로 쓰지 않는다.
  - [x] Focused canary 복구를 parent survival로 간주하지 않는다.
  - [x] `11668288` safe gain은 raw lint flag가 있어 approval evidence로 쓰지 않는다.
  - [x] Residual accounting delta `NO_DELTA_PARENT_REPLAY_AFTER_LOOP236_MIXED_MOVEMENT`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop236 URL-title direct-source support quality gate

- 근거:
  - [x] Loop236 원 canary wrong publish evidence를 보존했다.
  - [x] Bad public title `두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)`와 URL `https://novelpia.com/novel/427233`을 기록했다.
  - [x] Resync preview에서 같은 산출물이 `promotion_blocked`로 내려가는지 확인했다.
  - [x] Patched canary run `20260701_214126_569050` 완료: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - [x] Correct public title `전 버튜버가 하고 싶은데요`와 URL `https://novelpia.com/novel/275975`를 확인했다.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_236_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- 품질 게이트:
  - [x] Same-URL page title만으로 publish하지 않는다.
  - [x] Direct post/OCR/alias support 없는 official detail 후보는 candidate로 보존하되 public publish에서는 차단한다.
  - [x] Targeted canary GO를 parent semantic approval로 쓰지 않는다.
  - [x] Residual accounting delta `NO_DELTA_TARGETED_URL_TITLE_DIRECT_SUPPORT_GUARD`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop235 character-parenthetical bridge quality gate

- 근거:
  - [x] Loop235 원 런 stuck 상태를 incomplete artifact로 보존했다.
  - [x] Loop235b runtime `20260701_210203_663393` 완료: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - [x] 내부 expert title과 serialized public title을 분리했다.
  - [x] public title이 `null`로 남은 것을 확인했다.
  - [x] URL-title mismatch를 public publish 차단 seed로 기록했다.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_235_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- 품질 게이트:
  - [x] Runtime `GO`를 semantic approval로 쓰지 않는다.
  - [x] Internal expert resolution을 serialized public title 복구로 간주하지 않는다.
  - [x] URL-title mismatch 후보를 public publish 근거로 쓰지 않는다.
  - [x] Residual accounting delta `NO_DELTA_TARGETED_CANARY_NO_GO`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop234 direct-image cover-title runtime canary quality gate

- 근거:
  - [x] `11663540` focused runtime input을 생성했다.
  - [x] run `20260701_202952_860752` 완료: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - [x] run `20260701_203559_843860` 완료: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - [x] 두 run 모두 final public title `null`로 남은 것을 확인했다.
  - [x] Actual image evidence shape에 맞춰 exact cover-title contract를 추가했다.
  - [x] Focused direct-image tests 3개 PASS.
  - [x] `tests.test_expert_main_comment_metadata` 27 OK.
  - [x] `tests.test_promotion_gate_contract + tests.test_candidate_audit` 128 OK.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_234_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- 품질 게이트:
  - [x] Runtime `GO_FOCUSED_RUNTIME_2X`를 semantic approval로 쓰지 않는다.
  - [x] Targeted canary는 `NO-GO_PUBLIC_TITLE_NOT_RESTORED`로 기록한다.
  - [x] OCR variant `전 버두바가 하고 싶은데요`와 secondary title `태양을 숨긴 달`을 public title 근거로 바로 쓰지 않는다.
  - [x] Residual accounting delta `NO_DELTA_TARGETED_CANARY_NO_GO`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop233 direct-image character shared gate quality gate

- 근거:
  - [x] `11663540` OCR/character-title path를 단위 계약으로 고정했다.
  - [x] Candidate-matching OCR/work-title evidence와 verified character bridge를 모두 요구한다.
  - [x] Wrong-work candidate `방구석 여신이 되었다`가 OCR mismatch로 계속 차단되는지 확인했다.
  - [x] 신규 focused tests 2개 PASS.
  - [x] `tests.test_expert_main_comment_metadata` 26 OK.
  - [x] `tests.test_promotion_gate_contract + tests.test_candidate_audit` 128 OK.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_233_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- 품질 게이트:
  - [x] Unit contract only이므로 runtime GO나 targeted canary GO를 주장하지 않는다.
  - [x] Focused tests를 semantic approval로 쓰지 않는다.
  - [x] Residual accounting delta `NO_DELTA_UNIT_CONTRACT_ONLY`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop232 source/native variance review quality gate

- 근거:
  - [x] Loop231 focus rows `11661876`, `11663540`, `11695637`, `11660237`, `11706832`를 검토했다.
  - [x] Native web official page title 확인과 row-level publish disposition을 분리했다.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_232_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- 품질 게이트:
  - [x] Review-only이므로 runtime GO나 targeted canary GO를 주장하지 않는다.
  - [x] Official page existence를 semantic approval로 쓰지 않는다.
  - [x] `11695637` old title restore와 `11706832` safe gain을 residual 감소로 세지 않는다.
  - [x] Residual accounting delta `NO_DELTA_SOURCE_NATIVE_VARIANCE_REVIEW_ONLY`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop231 parent replay after Loop230 quality gate

- 근거:
  - [x] Loop231 parent replay run `20260701_190002_650661`을 완료했다.
  - [x] completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, MCP health `36/36`을 확인했다.
  - [x] Loop225 baseline과 Loop231 result를 비교했다.
  - [x] `11660257` parent survival을 확인했다.
  - [x] safe gain 2건, safe loss 3건, safe identity drift 2건을 분리 기록했다.
  - [x] `11660237` targeted/parent variance를 기록했다.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_231_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- 품질 게이트:
  - [x] Runtime `GO`를 parent semantic approval로 쓰지 않는다.
  - [x] `11660257` survival은 positive evidence only로 둔다.
  - [x] Parent semantic result를 `NO-GO / MIXED_MOVEMENT`로 둔다.
  - [x] Residual accounting delta `NO_DELTA_PARENT_REPLAY_AFTER_LOOP230_MIXED_MOVEMENT`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop228 Loop227 safe-loss source/native review quality gate

- 근거:
  - [x] Loop227 safe-loss 4건을 모두 검토했다: `11660237`, `11660257`, `11695637`, `11705231`.
  - [x] Official/native page exists `4/4`와 source/native correct title `3/4`를 분리했다.
  - [x] `11695637`은 old safe title 복구 금지 및 retarget lane으로 분리했다.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_228_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- 품질 게이트:
  - [x] Review-only이므로 runtime GO나 targeted canary GO를 주장하지 않는다.
  - [x] Official page existence를 semantic approval로 쓰지 않는다.
  - [x] Residual accounting delta `NO_DELTA_SOURCE_NATIVE_SAFE_LOSS_REVIEW_ONLY`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop227 composite parent replay quality gate

- 근거:
  - [x] Parent 원 런 partial을 그대로 기록했다: `37/38`, `large_run_complete=false`, `flushed/pending=24/13`.
  - [x] Missing-row `11698897` 1/1 보강 run을 별도 기록했다.
  - [x] Composite 38/38 분석을 parent checkpoint + missing result로 구성했다.
  - [x] Safe gain 4건과 safe loss 4건을 모두 기록했다.
  - [x] Review JSON/MD 산출물 기록 완료.
  - [x] Loop report 기록 완료: `docs/devs/loop_reports/LOOP_227_REPORT_20260701.md`.
  - [x] Data Analytics artifact 준비 완료.
- 품질 게이트:
  - [x] Parent 원 런은 runtime approval이 아니라 partial evidence로만 취급한다.
  - [x] Composite는 분석 근거이며 semantic approval이 아니다.
  - [x] Residual accounting delta `NO_DELTA_COMPOSITE_PARENT_REPLAY_MIXED_MOVEMENT`를 유지한다.
  - [x] Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 Loop226 safe-loss trace candidate priority quality gate

- Evidence:
  - [x] Loop225 safe-loss rows `11668288`, `11674712`, `11706832` were replayed deterministically through patched final publication ledger sync.
  - [x] Trace candidate priority patch avoids post_id/title-specific hardcoding.
  - [x] Comment-surface hold candidates no longer outrank stronger preserved candidates in `publish_contract_trace.pre_gate_candidate`.
  - [x] Focused unittest passed: new 2 tests OK.
  - [x] `tests.test_expert_main_comment_metadata` passed: 23 tests OK.
  - [x] Promotion gate bundle passed: 43 tests OK.
  - [x] `py_compile` passed for `expert_main.py` and `tests/test_expert_main_comment_metadata.py`.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Review JSON/MD artifacts written.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_226_REPORT_20260701.md`.
- Quality gates:
  - [x] Treat this as trace/ledger architecture evidence only.
  - [x] Confirm all three safe-loss rows remain `promotion_blocked` and `publish_allowed=false`.
  - [x] Keep residual accounting delta `NO_DELTA_TRACE_LEDGER_ONLY`.
  - [x] Do not count Loop226 as parent replay or semantic approval.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop225 envelope title gate fix quality gate

- Evidence:
  - [x] Loop224 `11661876` failure root cause recorded as envelope/payload title-loss in final publication ledger sync.
  - [x] Code patch avoids post_id/title-specific hardcoding.
  - [x] Regression test added for inner payload without top-level `title`.
  - [x] Focused unittest passed: `tests.test_expert_main_comment_metadata`, `21 tests OK`.
  - [x] `py_compile` passed for `expert_main.py` and `tests/test_expert_main_comment_metadata.py`.
  - [x] Deterministic replay of Loop224 actual payload plus caller post title restored `11661876`.
  - [x] Loop225 parent replay run `20260701_151744_526664` completed by manifest counts.
  - [x] completed/flushed/pending/failed `38/38/0/0`.
  - [x] image_post_count `24`, VLM/OCR `READY`.
  - [x] Loop224/Loop225 status counts and movement classes recorded.
  - [x] Review JSON/MD artifacts written.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_225_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Treat runtime `GO` as runtime only, not semantic approval.
  - [x] Treat target recovery as targeted evidence only.
  - [x] Treat Loop225 semantic result as `NO-GO / MIXED_MOVEMENT`.
  - [x] Keep residual accounting delta `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`.
  - [x] Record safe-loss rows `11668288`, `11674712`, `11706832`.
  - [x] Record safe identity drift rows `11658615`, `11695637`, `11705231`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop224 parent replay after Loop223 patch quality gate

- Evidence:
  - [x] Loop224 parent/representative replay run `20260701_141454_629022` completed by manifest counts.
  - [x] Runtime audit returned `runtime_contract=GO`, issues `[]`.
  - [x] completed/flushed/pending/failed `38/38/0/0`.
  - [x] image_post_count `24`, VLM/OCR `READY`.
  - [x] Loop182/Loop221/Loop224 status counts recorded.
  - [x] Loop221 -> Loop224 changed rows recorded: `11666713`, `11668288`, `11695637`, `11698880`, `11705231`.
  - [x] `11705231` parent survival recorded as `safe_resolved`.
  - [x] `11661876` parent survival failure recorded as `promotion_blocked`.
  - [x] `11698880` safe-loss recurrence recorded.
  - [x] Review JSON/MD artifacts written.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_224_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Treat runtime `GO` as runtime only, not semantic approval.
  - [x] Treat Loop224 semantic result as `NO-GO / MIXED_MOVEMENT`.
  - [x] Keep residual accounting delta `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`.
  - [x] Record next architecture step as upstream authoritative promotion decision ledger / state convergence, not more final scrub restore only.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop223 publish-contract title-field patch quality gate

- Evidence:
  - [x] Loop222 strong patch targets isolated: `11661876`, `11705231`.
  - [x] Candidate-audit page-title canonicalization implemented for same official URL title-field contamination.
  - [x] Final serialized publish-contract restore implemented for `11661876`-class current_work/high overblock.
  - [x] Loop223 first canary and Loop223b final canary outcomes recorded separately.
  - [x] Loop223b run `20260701_134929_838421` completed by manifest counts.
  - [x] Runtime audit returned `runtime_contract=GO`, issues `[]`.
  - [x] Both target rows final `safe_resolved`.
  - [x] Full unittest discover PASS, `1335` tests.
  - [x] Review JSON/MD artifacts written.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_223_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Treat Loop223 as focused target recovery only.
  - [x] Keep residual accounting delta `NO_DELTA_FOCUSED_CANARY_ONLY`.
  - [x] Record parent/representative replay as still required.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop222 safe-loss source/native review quality gate

- Evidence:
  - [x] Loop221 safe-loss rows reviewed: `11658620`, `11660237`, `11661876`, `11668288`, `11695623`, `11705231`.
  - [x] Official/native evidence checked for all six rows.
  - [x] Review verdict split recorded: `likely_overblock=3`, `ambiguous_hold=2`, `title_field_bug=1`.
  - [x] Strong patch candidates recorded: `11661876` final scrub overblock, `11705231` title-field split.
  - [x] Review JSON/MD artifacts written.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_222_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Treat Loop222 as review-only, not runtime or semantic approval.
  - [x] Record targeted canary status as `NOT_RUN`.
  - [x] Keep residual accounting delta `NO_DELTA_SOURCE_NATIVE_SAFE_LOSS_REVIEW_ONLY`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.
  - [x] Run focused tests/patches for `11661876` and `11705231` before any broader replay approval claim.

## 2026-07-01 Loop191/192 publish trace packet replay quality gate

- Evidence:
  - [x] Loop191 reran the prior five-row packet after Loop190 trace instrumentation.
  - [x] Loop191 run `20260701_041346_483852` completed by manifest counts.
  - [x] Loop191 runtime audit returned `runtime_contract=GO`, issues `[]`.
  - [x] Loop191 exposed trace gap for `11660257`.
  - [x] Candidate-ledger trace source fallback patched and focused regression added.
  - [x] `py_compile` PASS.
  - [x] Focused unittest PASS, `12 tests OK`.
  - [x] Loop192 reran the same five-row packet after the trace-source patch.
  - [x] Loop192 run `20260701_042125_503632` completed by manifest counts.
  - [x] Loop192 runtime audit returned `runtime_contract=GO`, issues `[]`.
  - [x] Loop192 trace coverage `5/5`, pre-gate title rows `5/5`.
  - [x] Review JSON/MD artifacts written.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_191_192_REPORT_20260701.md`.
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Treat trace coverage as observability progress, not residual closure.
  - [x] Treat Loop192 packet semantic as `NO-GO_PACKET`.
  - [x] Record Loop192 ledger split `safe_resolved=0`, `promotion_blocked=5`.
  - [x] Record public title count `0/5`.
  - [x] Keep residual accounting delta `NO_DELTA_PACKET_REPLAY_VARIANCE_ALL_BLOCKED`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop190 publish-contract trace unit quality gate

- Evidence:
  - [x] `expert_main.py` records `publish_contract_trace` for promotion-blocked serialized results.
  - [x] Trace includes `pre_gate_candidate`, `gate_decision`, `post_gate_identity`, `reason_codes`, and `bypassed_gate=false`.
  - [x] `publish_ledger` separates candidate preservation from public publish.
  - [x] `candidate_ledger` mirrors the publish trace and ledger for downstream review.
  - [x] Focused regression assertions updated in `tests/test_expert_main_comment_metadata.py`.
  - [x] `py_compile expert_main.py` PASS.
  - [x] Focused unittest PASS, `11 tests OK`.
  - [x] Review JSON/MD artifacts written.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_190_REPORT_20260701.md`.
  - [x] Data Analytics artifact validation PASS.
  - [x] Data Analytics render status recorded conservatively as `ATTEMPTED_OUTPUT_TRUNCATED`.
- Quality gates:
  - [x] Treat Loop190 as `GO_UNIT_ONLY`.
  - [x] Separate unit instrumentation from packet semantic approval.
  - [x] Keep residual accounting delta `NO_DELTA_UNIT_INSTRUMENTATION_ONLY`.
  - [x] Keep packet replay `OPEN`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop189 packet replay architecture-gap quality gate

- Evidence:
  - [x] Loop189 reran the prior five-row Loop184 follow-up packet after the Loop188 title-led bridge.
  - [x] Loop189 run `20260701_034236_736272` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `2`.
  - [x] Bridge-only MCP health recorded: `mcp_health_include_search=false`, MCP health `2/2`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_189_REPORT_20260701.md`.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Treat Loop189 as packet semantic `NO-GO`, not residual closure.
  - [x] Record Loop189 ledger split `safe_resolved=0`, `promotion_blocked=5`.
  - [x] Record public title count `0/5`.
  - [x] Confirm Loop188 `11669928` single-post recovery did not survive five-row packet replay.
  - [x] Preserve candidate evidence as candidate-only, without public `official_title` promotion.
  - [x] Keep residual accounting delta `NO_DELTA_PACKET_REPLAY_REGRESSED_TO_ALL_PROMOTION_BLOCKED`.
  - [x] Add architecture gap: final public identity publish contract must be traceable separately from candidate preservation.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop188 title-led alias bridge single-post quality gate

- Evidence:
  - [x] Loop188 ran the one-row `11669928` title-led alias consumption canary.
  - [x] Loop188 run `20260701_032856_094482` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `1/1/0/0`.
  - [x] VLM/OCR `READY`, image_post_count `0`, skip reason `no_image_blocks`.
  - [x] Bridge-only MCP health recorded: `mcp_health_include_search=false`, MCP health `1/1`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_188_REPORT_20260701.md`.
  - [x] Unit guard `test_title_led_discontinuation_alias_accepts_official_detail_hold` PASS.
  - [x] Full guard module `tests.test_title_lead_search_inferred_guard` PASS, `155 tests OK`.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Treat `11669928` recovery as `GO_SINGLE_POST`, not packet closure.
  - [x] Confirm official title `탑의 성좌들이 날 애호한다` and URL `https://novelpia.com/novel/377032` are restored.
  - [x] Record `candidate_ledger_status=safe_resolved`, `work_resolution=resolved`, `title_resolution_state=resolved`.
  - [x] Preserve intermediate J11 title-drift demotion as residual packet-risk evidence.
  - [x] Keep residual accounting delta `NO_DELTA_SINGLE_POST_CANARY_ONLY`.
  - [x] Keep packet replay `OPEN`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop187 nested gate scrub follow-up quality gate

- Evidence:
  - [x] Loop187 reran the Loop184 five-row packet after the nested promotion-gate scrub patch.
  - [x] Loop187 run `20260701_025510_236345` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `2`.
  - [x] Bridge-only MCP health recorded: `mcp_health_include_search=false`, MCP health `2/2`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_187_REPORT_20260701.md`.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Treat nested scrub as `GO_UNIT_ONLY`, not live packet closure.
  - [x] Treat `11660257` candidate-hold stability as candidate-preservation evidence only.
  - [x] Preserve `11669928` as new safe-loss root-cause row.
  - [x] Preserve `11713222` as alias-precedence variance because Loop186 and Loop187 disagree.
  - [x] Keep residual accounting delta `NO_DELTA_NESTED_GATE_SCRUB_REVIEW_ONLY`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop186 collateral follow-up quality gate

- Evidence:
  - [x] Loop186 reran the Loop184 five-row packet after the Loop185 candidate-hold patch.
  - [x] Loop186 run `20260701_022923_198719` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `2`.
  - [x] Bridge-only MCP health recorded: `mcp_health_include_search=false`, MCP health `2/2`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_186_REPORT_20260701.md`.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Treat `11660257` candidate-hold stability as single-row regression evidence only.
  - [x] Treat Loop186 ledger movement `safe_resolved=4 -> 2` as no-delta semantic review evidence.
  - [x] Preserve `11695623` and `11713222` as open root-cause rows.
  - [x] Keep residual accounting delta `NO_DELTA_COLLATERAL_FOLLOWUP_REVIEW_ONLY`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop185 exact-alias candidate-hold quality gate

- Evidence:
  - [x] Loop185 ran the one-row `11660257` exact-alias candidate-hold canary.
  - [x] Loop185 run `20260701_021353_263678` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `1/1/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `1`.
  - [x] Bridge-only MCP health recorded: `mcp_health_include_search=false`, MCP health `1/1`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_185_REPORT_20260701.md`.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Treat candidate preservation as `GO_FOR_CANDIDATE_HOLD_FIX_ONLY`, not recall approval.
  - [x] Confirm public title remains blocked while `암흑가 보스요? 제가요?` is preserved as candidate evidence.
  - [x] Keep residual accounting delta `NO_DELTA_TARGETED_SINGLE_ROW_ONLY`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.
  - [x] Require Loop184 packet rerun before any accounting delta.
    - Loop186 completed and remained no-delta due to packet movement.

## 2026-07-01 Loop184 targeted follow-up quality gate

- Evidence:
  - [x] Loop184 ran the five Loop183 follow-up rows.
  - [x] Loop184 run `20260701_014002_948127` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `2`.
  - [x] Bridge-only MCP health recorded: `mcp_health_include_search=false`, MCP health `2/2`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_184_REPORT_20260701.md`.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Treat `safe_resolved=4`, `promotion_blocked=1` as targeted evidence only.
  - [x] Preserve `11660257`, `11713222`, and `11674712` as unresolved semantic/accounting work.
  - [x] Keep residual accounting delta `NO_DELTA_TARGETED_FOLLOWUP_ONLY`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop183 source/native movement review quality gate

- Evidence:
  - [x] Loop183 reviewed Loop182 safe gains `11669928`, `11695623`.
  - [x] Loop183 reviewed Loop182 safe losses `11660257`, `11674712`, `11713222`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_183_REPORT_20260701.md`.
- Quality gates:
  - [x] Treat source/native review as review-only evidence, not closure.
  - [x] Preserve `11660257` and `11713222` as next targeted follow-up surfaces.
  - [x] Preserve `11669928` and `11674712` as variance-attention controls.
  - [x] Keep residual accounting delta `NO_DELTA_SOURCE_NATIVE_REVIEW_ONLY`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop182 architecture parent replay quality gate

- Evidence:
  - [x] Loop182 reused the Loop169 38-row parent/representative input after architecture integration.
  - [x] Loop182 run `20260701_001958_875919` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `24`.
  - [x] Search-included MCP health recorded: `mcp_health_include_search=true`, MCP health `36/36`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_182_REPORT_20260701.md`.
- Quality gates:
  - [x] Separate parent runtime `GO` from semantic approval.
  - [x] Preserve Loop182 row movement `22/38` as review evidence, not approval.
  - [x] Preserve safe gain `2` and safe loss `3` as source/native review requirements.
  - [x] Preserve degraded search counter increase `166 -> 178` as replay/source-review risk.
  - [x] Keep residual accounting delta `NO_DELTA_REVIEW_EVIDENCE_ONLY`.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 Loop181 Bridge-only rerun quality gate

- Evidence:
  - [x] Loop181 reused the Loop180 9-row P1 `image_anchor_gate` input.
  - [x] Loop181 run `20260630_234216_623989` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `9`.
  - [x] Bridge-only health recorded: `mcp_health_include_search=false`, MCP health `2/2`.
  - [x] Runtime audit artifact written with `runtime_contract=GO`, issues `[]`.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_181_REPORT_20260701.md`.
- Quality gates:
  - [x] Separate runtime `GO` from semantic approval.
  - [x] Record Loop181 as the runtime-caveat cleanup for Loop180.
  - [x] Preserve Loop181 row movement `6/9` as review evidence, not approval.
  - [x] Preserve degraded search counter increase `57 -> 67` as replay/source-review risk.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop180 residual queue return quality gate

- Evidence:
  - [x] Loop180 input and manifest created for 9 P1 `image_anchor_gate` rows.
  - [x] Loop180 run `20260630_231142_887357` completed by manifest counts.
  - [x] Manifest completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `9`.
  - [x] Runtime audit artifact written.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_180_REPORT_20260630.md`.
- Quality gates:
  - [x] Separate manifest completion from strict runtime audit.
  - [x] Preserve strict runtime audit as `REVIEW` because search health was included in a small run.
  - [x] Separate `safe_resolved=5` evidence from residual queue decrement.
  - [x] Preserve `promotion_blocked=4` as candidate-ledger evidence, not public title approval.
  - [x] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop176 broader unittest gate quality audit

- Evidence:
  - [x] Codex app goal status observed as `paused`, not `complete`.
  - [x] Authoritative command executed: `.venv312\Scripts\python.exe -m unittest discover --start-directory tests`.
  - [x] Result recorded: `1292` tests, `8` failures, `0` errors, exit code `1`.
  - [x] Non-authoritative `-s tests` invocation documented as command-shape issue.
  - [x] Review JSON/MD artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_176_REPORT_20260630.md`.
  - [x] Loop179 repair report written: `docs/devs/loop_reports/LOOP_179_REPORT_20260630.md`.
- Quality gates:
  - [x] Separate command execution from test approval.
  - [x] Count broader unittest execution as `COMPLETE_WITH_FAILURES`.
  - [x] Count broader unittest sweep as `FAIL`.
  - [x] Repair or explicitly disposition all 8 broader unittest failures.
    - Loop179 broader unittest: `1299` tests, `0` failures, `0` errors.
  - [x] Re-run the broader unittest sweep after fixes.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `NOT_COMPLETE`.

## 2026-06-30 architecture-integrated goal revision quality gate

- Evidence:
  - [x] New goal contract created: `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`.
  - [x] Active goal files updated: `goal.md`, `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`.
  - [x] Architecture design doc promoted from reference aid to active goal scope.
  - [x] README/TODO/CHECKLIST updated to point at the new goal contract.
  - [x] Shared promotion gate implemented in `src/llm_batch/promotion_gate.py`.
  - [x] Contract tests added in `tests/test_promotion_gate_contract.py`.
  - [x] Loop179 Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Do not count architecture documentation as implementation.
  - [x] Do not reset the residual queue.
  - [x] Keep runtime harness preservation as a non-goal for rewrite.
  - [x] Inventory publish paths before code wiring.
  - [x] Add shared promotion gate and contract tests before broad rewiring.
  - [x] Re-run focused/affected tests and Loop176 broader sweep after implementation.
    - Loop179 authoritative broader result: `1299` tests OK.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `NOT_COMPLETE`.

## 2026-06-30 Loop175 11668288 expectation revalidation quality gate

- Evidence:
  - [x] Reviewed 15 repeated `11668288` result files.
  - [x] Outcome split recorded: `safe_resolved=6`, `promotion_blocked_or_hold=9`.
  - [x] Latest Loop173/174 both remain `promotion_blocked / nonwork / title=null`.
  - [x] Official title/page existence separated from row-level work-discussion evidence.
  - [x] Review artifacts written.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Residual accounting Data Analytics artifact validate/render PASS.
  - [x] Loop report written: `docs/devs/loop_reports/LOOP_175_REPORT_20260630.md`.
- Quality gates:
  - [x] Count official title/page existence as `STRONG`.
  - [x] Count row-level work-discussion expectation as `NOT_STABLE`.
  - [x] Mark `11668288` as `VARIANCE_QUARANTINE_HUMAN_REVIEW`.
  - [x] Do not count `11668288` as stable positive-control closure.
  - [x] Do not adopt post_id/title-specific or `gaming(high)` nonwork bypass.
  - [x] Apply the quarantine disposition to next queue/golden expectation accounting.
    - map: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_current_residual_gate_map_after_11668288_revalidation.md/json`
    - accounting artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_residual_accounting_data_analytics_artifact.json`
    - no duplicate queue decrement: Loop97 already counted `11668288` as quarantine/human_review.
  - [x] Continue remaining movement dispositions before parent stability language.
    - prior quarantine rows: `11669928`, `11674712`, `11658615`
    - review attention/no approval delta: `11706832`
  - [x] Run broader unittest gate and record Loop176 `FAIL`.
    - authoritative result: `1292` tests, `8` failures, `0` errors.
  - [x] Repair Loop176 failures before stability claim.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop173-174 parent movement follow-up quality gate

- Evidence:
  - [x] Loop173 movement/control follow-up executed after Loop172.
  - [x] Loop173 completed/flushed/pending/failed `9/9/0/0`.
  - [x] Loop173 VLM/OCR `READY`; image_post_count `4`.
  - [x] Loop173 MCP health ok/checked/required `2/2/2`.
  - [x] Loop173 runtime audit `GO`.
  - [x] Loop174 `11668288` targeted repeat executed.
  - [x] Loop174 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Loop174 VLM/OCR `READY`; image_post_count `1`.
  - [x] Loop174 MCP health ok/checked/required `1/1/1`.
  - [x] Loop174 runtime audit `GO`.
  - [x] `11668288` remains `promotion_blocked / nonwork / title=null` in Loop173 and Loop174.
  - [x] Experimental `non_novel(gaming,high)` alias-lock bypass removed/not adopted.
  - [x] `py_compile` PASS after removal.
  - [x] Focused tests PASS (`2 + 1 + 2` tests).
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Count Loop173/174 runtime as `GO`.
  - [x] Do not count runtime `GO` as semantic approval.
  - [x] Count Loop174 targeted semantic canary as `NO-GO`.
  - [x] Record `11668288` as unresolved variance/expectation revalidation blocker.
  - [x] Revalidate `11668288` expectation before another fix attempt.
    - Loop175 disposition: `VARIANCE_QUARANTINE_HUMAN_REVIEW`.
  - [x] Finish movement disposition for `11669928`, `11674712`, `11706832`, and `11658615`.
    - Loop175 residual map records no-delta prior variance quarantine for `11669928`/`11674712`/`11658615` and review attention/no approval delta for `11706832`.
  - [x] Run affected-module or broader unittest sweep before stability claim and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before stability claim.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Rerun clean parent/representative scope only after generalizable fix or explicit HOLD disposition.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop170-172 Lubko guard quality gate

- Evidence:
  - [x] Loop170 prefix repro executed after Loop169.
  - [x] Loop170 completed/flushed/pending/failed `4/4/0/0`.
  - [x] Loop170 VLM/OCR `READY`; image_post_count `2`.
  - [x] Loop170 MCP health ok/checked/required `2/2/2`.
  - [x] Stable-alias weak-relation bridge guard added.
  - [x] `py_compile` PASS.
  - [x] Focused stable-alias unittest PASS (`5 tests OK`).
  - [x] Loop171 parent-prefix runtime `8/8/0/0`.
  - [x] Loop172 parent-prefix runtime `8/8/0/0`.
  - [x] Loop172 VLM/OCR `READY`; image_post_count `5`; MCP health `2/2/2`.
  - [x] Loop172 keeps `11658620` at `promotion_blocked`.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Loop173 movement/control follow-up input prepared and executed.
- Quality gates:
  - [x] Count Loop170/171/172 runtime as `GO`.
  - [x] Count `11658620` target guard as `GO`.
  - [x] Do not count Loop172 as semantic approval.
  - [x] Record `11674712` reopening as semantic blocker.
  - [x] Run Loop173 movement/control follow-up input.
  - [x] Record Loop173/174 runtime `GO` but semantic `NO-GO / REVIEW-LOCKED`.
  - [x] Root-cause or explicitly disposition `11674712`, `11669928`, `11706832`, and `11658615`.
    - Loop175 residual map closes this accounting/disposition step without approval language.
  - [x] Run affected-module or broader unittest sweep before stability claim and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before stability claim.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Rerun clean parent/representative scope after movement fixes/dispositions.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop169 parent replay quality gate

- Evidence:
  - [x] Loop169 clean parent/representative replay executed after Loop168.
  - [x] Completed/flushed/pending/failed `38/38/0/0`.
  - [x] `large_run_complete=true`; no partial flush gap.
  - [x] VLM/OCR `READY`; image_post_count `24`.
  - [x] MCP health ok/checked/required `36/36/36`.
  - [x] Strict runtime contract audit `GO`.
  - [x] `11668288` and `11713222` recovered in parent scope.
  - [x] `11698880` and `11660259` remained safe-resolved.
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Count Loop169 runtime as `GO`.
  - [x] Count Loop169 target recovery as `GO`.
  - [x] Do not count Loop169 as semantic approval.
  - [x] Record movement rows that keep semantic gate locked.
  - [x] Root-cause or explicitly disposition `11658620`, `11674712`, `11669928`, `11706832`, and `11658615`.
    - Loop170-172 covers `11658620`; Loop175 residual map covers the remaining movement rows without approval delta.
  - [x] Run affected-module or broader unittest sweep before stability claim and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before stability claim.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Rerun follow-up after movement fixes/dispositions.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop162-168 completion recheck quality gate

- Evidence:
  - [x] Current goal status checked as `active`.
  - [x] Loop162 parent replay marked semantic `NO-GO`.
  - [x] Loop165 parent replay marked partial runtime evidence, not approval.
  - [x] Loop166 and Loop167 marked semantic `NO-GO` before final patch.
  - [x] Code patches are scoped to title-lead official-detail release flag propagation and short alias platform probe preservation.
  - [x] `py_compile` PASS.
  - [x] Focused 5-test bundle PASS.
  - [x] Loop168 run `20260630_190202_307842` exited cleanly.
  - [x] Completed/flushed/pending/failed `2/2/0/0`.
  - [x] VLM/OCR `READY`; MCP health ok/checked/required `2/2/2`.
  - [x] `11698880` and `11668288` both resolved to `가챠 중독자의 퓨전펑크 생활`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Count Loop168 as mini parent-mimic recovery.
  - [x] Do not count Loop168 as parent approval.
  - [x] Run clean parent/representative replay after Loop168 as Loop169.
  - [x] Review `11706832` and `11713222` movement in Loop169 and keep semantic gate locked.
  - [x] Run affected-module or broader unittest sweep before stability claim and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before stability claim.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## Standing anti-whack-a-mole replay gate

- 단건 post는 repro/fix seed일 뿐이다.
  - [ ] 단건/소형 lane code fix 후 바로 다음 단건 queue로 이동하지 않는다.
  - [ ] fixed row를 2회 이상 repeat한다.
  - [ ] parent lane 또는 representative mini-lane replay를 수행한다.
  - [ ] 최근 closed/HOLD controls와 golden positive/negative controls를 같이 replay한다.
  - [ ] affected-module tests와 collateral movement를 기록한다.
  - [ ] mixed resolved/HOLD/wrong-title 결과는 stable closure가 아니라 `VARIANCE_QUARANTINE_HUMAN_REVIEW` 또는 reopen으로 기록한다.

## 2026-06-30 Loop161 11668288 visual title-alias probe

- Evidence:
  - [x] Loop158/159 `11668288` loss vs Loop150 was reviewed.
  - [x] Visual title-leading alias probe added in `src/llm_batch/experts/orchestrator.py`.
  - [x] Probe restricted to image/VLM context, `title_as_body_continuation`, exact alias query/suggestion, and alias surface hit.
  - [x] Game-context negative case remains blocked.
  - [x] Existing alias-only nonwork forced-upgrade guard remains PASS.
  - [x] `py_compile` PASS.
  - [x] Focused 4-test bundle PASS.
  - [x] Loop161 run `20260630_165512_125247` exited cleanly.
  - [x] Completed/flushed/pending/failed `1/1/0/0`.
  - [x] VLM/OCR semantic gate `READY`; image_post_count `1`.
  - [x] MCP health ok/checked/required `1/1/1`.
  - [x] `11668288` recovered as `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Count Loop161 as targeted single-row recovery.
  - [x] Do not count Loop161 as semantic approval.
  - [ ] Run parent/representative replay after Loop161.
  - [ ] Review `11706832` title movement before any approval claim.
  - [ ] Keep Loop103 queue suspended while semantic gate is not approved.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop156 parent replay after Loop155

- Evidence:
  - [x] Loop156 run `20260630_144848_180512` exited cleanly.
  - [x] Completed/flushed/pending/failed `38/38/0/0`.
  - [x] VLM/OCR semantic review `READY`; image_post_count `24`.
  - [x] MCP health ok/required `36/36`.
  - [x] `11660259` parent-confirmed as `헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
  - [x] `11713222` parent-confirmed as `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Count Loop156 as runtime `GO`.
  - [x] Count Loop156 as target confirmation `GO`.
  - [x] Do not count Loop156 as semantic approval.
  - [x] Keep `11698880` changed-title risk open.
  - [x] Root-cause `11698880` wrong-title switch risk and parent-confirm repair in Loop158.
  - [ ] Review `11706832` gained/changed title.
  - [x] Review `11668288` loss vs Loop150 and recover targeted seed in Loop161.
  - [ ] Rerun parent/representative scope after Loop161.
  - [ ] Keep Loop103 queue suspended while semantic gate is `NO-GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop155 11660259 short alias reaction probe

- Evidence:
  - [x] Loop153 invalid evidence recorded: Verifier `NameError: ctx is not defined`.
  - [x] Verifier relation judge `ctx` propagation fixed.
  - [x] Explicit alias bridge and short worklike reaction alias probe covered by regression tests.
  - [x] `py_compile` PASS.
  - [x] Focused 4-test bundle PASS.
  - [x] Broader 11-test relation/alias bundle PASS.
  - [x] Loop155 run `20260630_143521_442264` exited cleanly.
  - [x] Completed/flushed/pending/failed `1/1/0/0`.
  - [x] VLM/OCR semantic gate `READY`; skip reason `no_image_blocks`.
  - [x] `11660259` primary work recovered as `헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Count Loop155 as targeted single-row fix seed `GO`.
  - [x] Do not count Loop155 as approval.
  - [x] Representative/parent replay preserves the `11660259` target fix in Loop156.
  - [x] `11713222` parent stability is recovered in Loop156.
  - [ ] Resolve Loop156 collateral blockers before any stability or approval claim.
  - [ ] Keep Loop103 queue suspended while semantic gate is not approved.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop152 11660259 current-code single repeat NO-GO

- Evidence:
  - [x] Loop136/Loop142 baseline preserved `11660259` as `헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
  - [x] Loop150 parent replay lost the public title.
  - [x] Loop152 run `20260630_141044_962593` exited cleanly.
  - [x] Completed/flushed/pending/failed `1/1/0/0`.
  - [x] VLM/OCR semantic gate `READY`; skip reason `no_image_blocks`.
  - [x] Final public title/url stayed `null`.
  - [x] Root-cause signals include `relation_judge:thematic_overlap_only`, `memory_query_forced_upgrade_guard`, and `title_surface_primary_relation_non_work_blocked`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Count Loop152 as single-row `NO-GO_REPRODUCED`.
  - [x] Do not count Loop152 as approval.
  - [x] Weak alias bridge path is fixed and covered by regression tests in Loop155.
  - [x] `11660259` repeat after fix passes in Loop155.
  - [x] Representative/parent replay preserves the fix in Loop156.
  - [ ] Resolve Loop156 collateral blockers before any stability or approval claim.
  - [ ] Keep Loop103 queue suspended while semantic gate is `NO-GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop151 11713222 current-code repeat diagnostic

- Evidence:
  - [x] Loop151 run `20260630_135620_918136` exited cleanly.
  - [x] Completed/flushed/pending/failed `1/1/0/0`.
  - [x] VLM/OCR semantic gate `READY`; skip reason `no_image_blocks`.
  - [x] Primary work `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
  - [x] Previous-work candidate `https://novelpia.com/novel/300042` did not override current direct alias.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Count Loop151 as single-row diagnostic `GO`.
  - [x] Do not count Loop151 as parent approval.
  - [ ] Keep `11713222` parent stability open until representative/parent replay preserves the current official detail.
  - [x] Review `11660259` title loss before any broader closure.
  - [x] Fix/replay `11660259` after Loop152 single-row `NO-GO_REPRODUCED` in Loop155.
  - [ ] Keep Loop103 queue suspended while semantic gate is `NO-GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop150 parent replay after Loop149

- Evidence:
  - [x] Loop150 parent replay run `20260630_125822_273225` exited cleanly.
  - [x] Manifest observed input `38`, completed/flushed/pending/failed `38/38/0/0`.
  - [x] Manifest observed `large_run_complete=true`.
  - [x] VLM/OCR semantic review readiness is `READY`; image_post_count `24`.
  - [x] Requested/effective parallel `36/36`; MCP health ok/required `36/36`.
  - [x] Review/report artifacts created.
  - [x] Loop142 movement compare created: `same=31`, `lost=5`, `gained=2`.
  - [x] Loop136 movement compare created: `same=32`, `lost=4`, `gained=2`.
  - [x] Data Analytics artifact validate/render PASS.
- Quality gates:
  - [x] Count Loop150 as runtime-complete only.
  - [x] Do not count Loop150 as semantic approval.
  - [x] Parent-check `11660257`: public title blocked, but still movement/drift evidence only.
  - [x] Parent-check `11669928`: resolved in this run, confirmation-only.
  - [x] Parent-check `11674712`: HOLD/null in this run.
  - [ ] Root-cause `11713222` parent-scope loss after Loop148 targeted repair.
  - [ ] Review `11660259` title loss vs Loop142/Loop136.
  - [ ] Keep Loop103 queue suspended while semantic gate is `NO-GO`.
  - [ ] Add a common grounding/promotion gate layer before continuing long single-post guard accumulation.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop149 11660257 current-code repeat

- Evidence:
  - [x] Loop107 blocked `11660257`, while Loop142 reopened it as a gained-title variance/control row.
  - [x] Loop149 current-code single repeat completed with VLM/OCR `READY`.
  - [x] Final serialized output kept public title/url `null`.
  - [x] Candidate evidence remained preserved but not promoted.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Targeted single repeat status is `GO_BLOCKED_TO_CANDIDATE_HOLD`.
  - [x] Public title remains `null`; `title_resolution_allowed=false`.
  - [x] Full-scan approval remains `false`.
  - [ ] `11660257` has parent/representative confirmation.
  - [ ] `11669928` and `11674712` have parent/representative confirmation.
  - [ ] Parent or representative replay after Loop143-Loop149 work has run.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop148 11713222 direct body alias previous-work guard

- Evidence:
  - [x] Failing baseline reproduced `11713222 -> 잘생기면 인생이 편하다` from previous-work/comment alias confusion.
  - [x] Native/web evidence confirmed direct body alias `잘생인방 -> 잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
  - [x] Patch preserves previous work `잘생기면 인생이 편하다` only as mentioned/secondary candidate evidence.
  - [x] Final result keeps current work as public title and URL.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Targeted row status is `TARGETED_CURRENT_ALIAS_PRESERVED`.
  - [x] Public title is `잘생기면 편해지는 인방 생활`; `title_resolution_allowed=true`.
  - [x] Focused tests and Loop148 rerun2 canary PASS.
  - [x] Full-scan approval remains `false`.
  - [x] `11660257` current-code single repeat is blocked in Loop149.
  - [ ] `11660257` has parent/representative confirmation.
  - [ ] `11669928` and `11674712` have parent or representative confirmation.
  - [ ] Parent or representative replay after Loop143-Loop149 work has run.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop147 11714903 wrong-relevance public-title guard

- Evidence:
  - [x] Loop142 `11714903` public title `온 세상이 정신이상자다` reviewed as wrong-relevance public-title leak, not title-existence failure.
  - [x] Patch demotes wrong-relevance candidate/hygiene seed public titles to candidate/HOLD.
  - [x] Final result keeps public title/url `null` and preserves candidate evidence only.
  - [x] Reason text says `공식 제목: 미확정 (promotion blocked; 후보로만 보존)`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Targeted row status is `TARGETED_BLOCKED_TO_CANDIDATE_HOLD`.
  - [x] Public title remains `null`; `title_resolution_allowed=false`.
  - [x] Focused tests and Loop147 canary PASS.
  - [x] Full-scan approval remains `false`.
  - [x] Gained-title rows were reviewed and split into targeted-blocked, repeat-required, and open requeue buckets.
  - [x] `11713222` wrong-related previous/current work issue is targeted repaired in Loop148.
  - [x] `11660257` current-code single repeat is blocked in Loop149.
  - [ ] `11660257` has parent/representative confirmation.
  - [ ] `11669928` and `11674712` have parent or representative confirmation.
  - [ ] Parent or representative replay after Loop143-Loop149 work has run.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop146 11698897 candidate-preservation repair

- Evidence:
  - [x] Diagnostic Loop146 canary separated public promotion blocking from candidate-ledger pollution.
  - [x] Spurious `스페이스 오페라` candidate was confirmed as rejected search/adaptive noise, not a preservation target.
  - [x] Correct official-detail candidate `[림월드]변방계에서 회귀자로 살아남기` / `https://novelpia.com/novel/382324` was confirmed in Loop146b.
  - [x] Patch prunes only already rejected `search_evidence_alias_inference` candidates before preservation snapshot.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Targeted row repair status is `TARGETED_REPAIRED_TO_CANDIDATE_HOLD`.
  - [x] Public title remains `null`; candidate evidence remains preserved.
  - [x] `스페이스 오페라` is absent from candidate preservation sources.
  - [x] Focused tests and Loop146b canary PASS.
  - [x] Full-scan approval remains `false`.
  - [x] Gained-title rows reviewed in Loop147; `11714903` targeted-blocked, `11713222` targeted repaired in Loop148, and `11660257` current-code single repeat blocked in Loop149.
  - [ ] Parent or representative replay after Loop143/Loop144 repairs, Loop145 disposition, Loop146 repair, Loop147 guard, Loop148 guard, and Loop149 repeat has run.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop145 11706832 accepted caveated demotion

- Evidence:
  - [x] Loop142 `11706832` title loss was reviewed as a row-level disposition candidate.
  - [x] Loop139 official detail page evidence confirms `황제의 딸로 환생했다` at `https://novelpia.com/novel/250464`.
  - [x] Post-side bridge is weak/community-mediated: `황제분충`, `문피안가`, `노피아`, `표절물인가`.
  - [x] Local image is textless meme/fanart and does not carry title/platform evidence.
  - [x] Council reviewers agreed that code repair would risk community-alias over-promotion.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Row disposition status is `GO_ACCEPTED_CAVEATED_DEMOTION`.
  - [x] Public title remains `null`; no code repair adopted.
  - [x] Full-scan approval remains `false`.
  - [x] `11698897` candidate-preservation drift is repaired in Loop146.
  - [x] Gained-title rows reviewed in Loop147; `11714903` targeted-blocked, `11713222` targeted repaired in Loop148, and `11660257` current-code single repeat blocked in Loop149.
  - [ ] Parent or representative replay after Loop143/Loop144 repairs, Loop145 disposition, Loop146 repair, Loop147 guard, Loop148 guard, and Loop149 repeat has run.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop144 11705231 targeted fix

- Evidence:
  - [x] Loop142 `11705231` failure root-caused to stale multi-work precision hold flags not being recoverable through verified-alias final-reread support.
  - [x] Narrow candidate-audit recovery added for verified alias + official detail + final semantic reread.
  - [x] Regression test added in `tests/test_candidate_audit.py`.
  - [x] `py_compile` PASS for touched files.
  - [x] Focused 7-test precision guard bundle PASS.
  - [x] Loop144 targeted canary completed `1/1`, pending snapshot `[]`, VLM/OCR `NOT_APPLICABLE` because no image blocks.
  - [x] Loop144 result `11705231` is `safe_resolved`, title `탐식의 재림`, URL `https://series.naver.com/novel/detail.series?productNo=2847498`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Targeted row fix status is `TARGETED_11705231_REPAIRED_NOT_APPROVAL`.
  - [x] Full-scan approval remains `false`.
  - [ ] Full `tests.test_candidate_audit` is green.
  - [ ] Fixed row has a repeat run.
  - [ ] Parent or representative replay after Loop143/Loop144 patches has run.
  - [x] Remaining Loop142 title loss `11706832` is explicitly dispositioned in Loop145.
  - [x] `11698897` candidate-preservation drift is repaired in Loop146.
  - [ ] Gained-title rows are reviewed.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop143 11658615 targeted fix

- Evidence:
  - [x] Loop142 `11658615` failure root-caused to noisy direct image/OCR title surface conflicting with verified official title.
  - [x] Narrow candidate-audit exemption added for verified alias + official detail lock.
  - [x] Regression test added in `tests/test_candidate_audit.py`.
  - [x] `py_compile` PASS for touched files.
  - [x] Focused 4-test candidate audit bundle PASS.
  - [x] vLLM model endpoint checked before run.
  - [x] Search shard status checked as `36/36` running and healthy.
  - [x] Loop143 targeted canary completed `1/1`, VLM/OCR `READY`.
  - [x] Loop143 result `11658615` is `safe_resolved`, title `이거 럽코 빙의물인가요`, URL `https://novel.munpia.com/533816`.
  - [x] Review/report artifacts and Data Analytics report created.
- Quality gates:
  - [x] Targeted row fix status is `TARGETED_11658615_REPAIRED_NOT_APPROVAL`.
  - [x] Full-scan approval remains `false`.
  - [ ] Full `tests.test_candidate_audit` is green.
  - [ ] Fixed row has a repeat run.
  - [ ] Parent or representative replay after Loop143 patch has run.
  - [x] Loop144 repaired `11705231` at targeted scope.
  - [x] Remaining Loop142 title loss `11706832` is explicitly dispositioned in Loop145.
  - [x] `11698897` candidate-preservation drift is repaired in Loop146.
  - [ ] Gained-title rows are reviewed.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop142 parent replay after Loop141 HOLD boundary

- Evidence:
  - [x] vLLM model endpoint checked before run.
  - [x] Search shard preflight audit saved with `36/36` healthy shards.
  - [x] Loop142 replay used `--reuse-shards-only`, `--slang-db off`, VLM/OCR on, and effective parallel `36`.
  - [x] Final result rows `38/38`; pending snapshot `0`.
  - [x] Runtime audit `loop142_parent_replay_after_loop141_hold_boundary_runtime_audit.md/json` created.
  - [x] Compare `loop142_parent_vs_loop136_compare.md/json` created.
  - [x] Review `loop142_parent_replay_after_loop141_hold_boundary_review.md/json` created.
  - [x] Data Analytics artifact `Loop142 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
- Quality gates:
  - [x] Runtime contract is `GO`.
  - [x] Current Loop141 targets stay public-title null: `11663521`, `11694019`, `11698897`.
  - [x] `11700470` unsafe Loop136 listing-description title remains demoted.
  - [x] Semantic quality is not approved: Loop142 is `NO-GO / REVIEW-LOCKED`.
  - [x] Repair `11658615` at targeted scope in Loop143.
  - [x] Repair `11705231` at targeted scope in Loop144.
  - [x] Explicitly disposition remaining Loop139-confirmed title loss `11706832` in Loop145.
  - [x] Repair `11698897` candidate-preservation drift in Loop146.
  - [ ] Review gained-title rows before broader approval language.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop141 current expected/recall HOLD boundary review

- Evidence:
  - [x] Remaining current expected/recall rows after Loop140 reviewed: `11663521`, `11694019`, `11698897`.
  - [x] Loop136 row fields and Loop120-121 / Loop123-127 / Loop132 / Loop140 review artifacts checked.
  - [x] `11663521` downloaded image visually inspected; no work-title/platform bridge.
  - [x] `11698897` downloaded images visually inspected; Rimworld/game-mechanics context only, no direct official title/platform bridge.
  - [x] DCCon helper images that returned HTTP 403 recorded as unavailable evidence.
  - [x] `11663521` classified as `HOLD_BOUNDARY_CONFIRMED`.
  - [x] `11694019` classified as `HOLD_BOUNDARY_CONFIRMED`.
  - [x] `11698897` classified as `VARIANCE_HOLD_CONTROL_CONFIRMED`.
  - [x] Review artifact `loop141_current_expected_recall_hold_boundary_review.md/json` created.
  - [x] Loop report `LOOP_141_REPORT_20260630.md` created.
  - [x] Data Analytics artifact `Loop141 Current Expected Recall HOLD Boundary Review` validate/render PASS.
- Quality gates:
  - [x] Current expected/recall unrationalized open rows after Loop141: `0`.
  - [x] Loop141 status is `AUDIT_ONLY_HOLD_BOUNDARY_REVIEW`.
  - [x] Code patch is `NOT_ADOPTED`.
  - [x] `expert_main.py` rerun is `NOT_RUN_AUDIT_ONLY_NO_ROW_MOVEMENT`.
  - [x] Parent/representative replay after Loop137/Loop138/Loop139/Loop140/Loop141 evidence executed as Loop142.
  - [x] Loop142 semantic quality remains `NO-GO / REVIEW-LOCKED`.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop140 expected/recall disposition consolidation

- Evidence:
  - [x] Pasted goal contract re-read; active goal remains `ACTIVE / NOT_COMPLETE`.
  - [x] Loop92-93 P1A stable dispositions rechecked for `11695623`, `11700495`, `11705261`.
  - [x] Loop136 current row state rechecked for six current expected/recall rows.
  - [x] `11695623` classified as `CURRENT_HOLD_CONFIRMED_FROM_LOOP92_93_AND_LOOP136`.
  - [x] `11700495` classified as `CURRENT_NO_PUBLIC_CONFIRMED_FROM_LOOP92_93_AND_LOOP136`.
  - [x] `11705261` classified as `CURRENT_HOLD_CONFIRMED_FROM_LOOP92_93_AND_LOOP136`.
  - [x] Remaining current expected/recall rows recorded as `11663521`, `11694019`, `11698897`.
  - [x] Review artifact `loop140_remaining_expected_recall_disposition_consolidation.md/json` created.
  - [x] Loop report `LOOP_140_REPORT_20260630.md` created.
  - [x] Data Analytics artifact `Loop140 Remaining Expected Recall Disposition Consolidation` validate/render PASS.
- Quality gates:
  - [x] Loop140 status is `AUDIT_ONLY_DISPOSITION_CONSOLIDATION`.
  - [x] Code patch is `NOT_ADOPTED`.
  - [x] `expert_main.py` rerun is `NOT_RUN_AUDIT_ONLY_NO_ROW_MOVEMENT`.
  - [x] Parent/representative replay after Loop137/Loop138/Loop139/Loop140 evidence executed as Loop142; semantic approval remains `NO-GO / REVIEW-LOCKED`.
  - [x] Current expected/recall rows `11663521`, `11694019`, `11698897` explicitly held with rationale in Loop141.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop139 Loop136 safe-resolved native/web review

- Evidence:
  - [x] Remaining Loop136 `safe_resolved` set reviewed: `11698880`, `11658615`, `11660237`, `11660258`, `11660259`, `11706832`, `11705231`.
  - [x] Current official/platform page title checked for all seven URLs.
  - [x] Image rows downloaded and visually inspected.
  - [x] `11658615` image directly confirms the work card title and author.
  - [x] Meme/reaction-only images separated from title-bridge evidence.
  - [x] Review artifact `loop139_loop136_safe_resolved_native_web_review.md/json` created.
  - [x] Loop report `LOOP_139_REPORT_20260630.md` created.
- Quality gates:
  - [x] Remaining safe-resolved native/web review status is `COMPLETE_WITH_11706832_ALIAS_CAVEAT`.
  - [x] Code patch is `NOT_ADOPTED`.
  - [x] `expert_main.py` rerun is `NOT_RUN_AUDIT_ONLY_NO_ROW_MOVEMENT`.
  - [x] Parent/representative replay after Loop137/Loop138/Loop139 evidence executed as Loop142; semantic approval remains `NO-GO / REVIEW-LOCKED`.
  - [x] `11695623`, `11700495`, and `11705261` were split out as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, `11698897` explicitly held with rationale in Loop141.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop138 11685994 image/native-web verification

- Evidence:
  - [x] Loop136 latest row state checked: public title `null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_allowed=false`.
  - [x] Local image and enlarged title crop reviewed.
  - [x] Cover title family `교황님 아 하세요 / 마왕들어가요`, author `아데라`, `장편소설` preserved as candidate evidence.
  - [x] Wrong-work candidate pages rejected: `https://novelpia.com/novel/270445`, `https://novelpia.com/novel/383971`, `https://page.kakao.com/content/56516207`.
  - [x] Review artifact `loop138_11685994_image_native_web_verification_review.md/json` created.
  - [x] Loop report `LOOP_138_REPORT_20260630.md` created.
- Quality gates:
  - [x] `11685994` status is `IMAGE_NATIVE_WEB_VERIFIED_INFO_MISSING_HOLD`.
  - [x] Code relaxation is `NOT_ADOPTED`.
  - [x] `expert_main.py` rerun is `NOT_RUN_NO_CODE_CHANGE_CURRENT_STATE_ALREADY_HOLD`.
  - [x] Parent/representative replay after Loop137/Loop138 evidence executed as Loop142; semantic approval remains `NO-GO / REVIEW-LOCKED`.
  - [x] Remaining safe-resolved rows manually reviewed against native/web evidence in Loop139, with `11706832` alias caveat.
  - [x] `11695623`, `11700495`, and `11705261` were split out as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, `11698897` explicitly held with rationale in Loop141.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop137 11700470 listing-description guard

- Evidence:
  - [x] Loop136 `11700470` safe_resolved row reviewed against native/web evidence.
  - [x] Official page title confirmed as `납치당했는데 미소녀가 되었다`.
  - [x] Loop136 promoted title identified as listing/page description text.
  - [x] `candidate_audit.py` listing-description promotion guard added.
  - [x] Regression test added in `tests/test_candidate_audit.py`.
  - [x] `py_compile` PASS.
  - [x] Related 7-test unittest bundle PASS.
  - [x] Pre-run model check and shard audit passed; shard audit `36/36`, bad `[]`.
  - [x] Loop137 run `20260630_074755_088187` completed/flushed/pending/failed `1/1/0/0`.
  - [x] VLM/OCR `READY`, image_post_count `1`.
  - [x] Runtime audit `loop137_11700470_listing_description_guard_runtime_audit.md/json` is `GO`.
  - [x] `11700470` final public title `null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_allowed=false`.
  - [x] Compare/review artifacts created: `loop137_11700470_vs_loop136_compare.md/json`, `loop137_11700470_listing_description_guard_review.md/json`.
- Quality gates:
  - [x] `11700470` status is `TARGETED_11700470_REPAIRED_TO_HOLD_LOOP137_NOT_APPROVAL`.
  - [x] `11685994` image/native-web verification later completed in Loop138 as `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [x] Parent/representative replay after Loop137 repair executed as Loop142; semantic approval remains `NO-GO / REVIEW-LOCKED`.
  - [x] Remaining Loop136 safe-resolved rows manually reviewed against native/web evidence in Loop139, with `11706832` alias caveat.
  - [x] `11695623`, `11700495`, and `11705261` were split out as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, `11698897` explicitly held with rationale in Loop141.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop136 parent replay after Loop135 guard

- Evidence:
  - [x] Loop134 parent/representative 38-row packet reran after Loop135.
  - [x] Pre-run model check and shard audit passed; shard audit `36/36`, bad `[]`.
  - [x] Loop136 run `20260630_065926_226944` completed/flushed/pending/failed `38/38/0/0`.
  - [x] VLM/OCR `READY`, image_post_count `24`.
  - [x] Runtime audit `loop136_parent_replay_after_loop135_phase2_hold_guard_runtime_audit.md/json` is `GO`.
  - [x] Loop135 `11694035` guard held at parent scope: public title `null`, `candidate_ledger_status=promotion_blocked`.
  - [x] `11705231` remained restored as `탐식의 재림`.
  - [x] Compare/review artifacts created: `loop136_parent_vs_loop134_compare.md/json`, `loop136_parent_replay_after_loop135_phase2_hold_guard_review.md/json`.
- Quality gates:
  - [x] Parent/representative replay after Loop135 patch is complete at runtime level.
  - [ ] Parent/representative semantic replay is complete.
  - [x] `11700470` manually reviewed and repaired to focused HOLD in Loop137.
  - [x] `11685994` image/native-web verification completed in Loop138 as `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [x] Remaining safe-resolved rows manually reviewed against native/web evidence in Loop139, with `11706832` alias caveat.
  - [x] `11695623`, `11700495`, and `11705261` were split out as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, `11698897` explicitly held with rationale in Loop141.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop135 11694035 Phase2 HOLD guard

- Evidence:
  - [x] Loop134 golden negative violation `11694035 -> 아카데미 생존 갤러리` root-caused.
  - [x] `candidate_audit.py` now blocks independent official-detail bypass for Phase2 `HOLD` / `re_search` precision seeds.
  - [x] Regression test added in `tests/test_candidate_audit.py`.
  - [x] `py_compile` PASS.
  - [x] Related 6-test unittest bundle PASS.
  - [x] Full `tests.test_candidate_audit` attempted; separate existing failure recorded.
  - [x] Pre-run model check and shard audit passed; shard audit `36/36`, bad `[]`.
  - [x] Loop135 run `20260630_065021_019075` completed/flushed/pending/failed `1/1/0/0`.
  - [x] VLM/OCR `READY`, image_post_count `1`.
  - [x] Runtime audit `loop135_11694035_phase2_hold_guard_runtime_audit.md/json` is `GO`.
  - [x] `11694035` final public title `null`, `candidate_ledger_status=promotion_blocked`, reason `phase2_hold_seed_requires_review`.
  - [x] Review `loop135_11694035_phase2_hold_guard_review.md/json` created.
- Quality gates:
  - [x] `11694035` status is `TARGETED_11694035_REPAIRED_LOOP135_NOT_APPROVAL`.
  - [x] Parent/representative replay after Loop135 patch is complete as Loop136 runtime `GO`.
  - [ ] Parent/representative semantic replay is complete.
  - [ ] Reopened/changed controls `11714903`, `11706832`, `11698880`, `11695623`, `11660257` are reviewed.
  - [ ] Remaining expected-work losses after Loop138-held `11685994` are resolved or explicitly held with rationale: `11663521`, `11694019`, `11700470`.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop134 parent replay after Loop133 source repair

- Evidence:
  - [x] Source-enriched parent packet created: Loop104 38-row role mix plus `11705231` source-evidence row.
  - [x] Pre-run model check and shard audit passed; shard audit `36/36`, bad `[]`.
  - [x] Loop134 run `20260630_055411_323400` completed/flushed/pending/failed `38/38/0/0`.
  - [x] VLM/OCR `READY`, image_post_count `24`.
  - [x] Runtime audit `loop134_parent_representative_after_loop133_source_enriched_runtime_audit.md/json` is `GO`.
  - [x] `11705231` restored at parent scope as `탐식의 재림`, `candidate_ledger_status=safe_resolved`.
  - [x] Role-aware review `loop134_parent_representative_after_loop133_source_enriched_review.md/json` created.
  - [x] Data Analytics artifact `Loop134 Parent Replay Quantitative Review` validate/render PASS.
- Quality gates:
  - [x] `11705231` status is `PARENT_SCOPE_TARGET_RESTORED_LOOP134_NOT_APPROVAL`.
  - [ ] Parent/representative semantic replay is complete.
  - [x] Golden negative violation `11694035 -> 아카데미 생존 갤러리` is root-caused and targeted-repaired in Loop135.
  - [ ] Reopened/changed controls `11714903`, `11706832`, `11698880`, `11695623`, `11660257` are reviewed.
  - [ ] Remaining expected-work losses after Loop138-held `11685994` are resolved or explicitly held with rationale: `11663521`, `11694019`, `11700470`.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop133 source-enriched focused repair

- Evidence:
  - [x] `11705231` true source-enriched row consumed row-level source evidence (`source-evidence search seed: 3/3 results loaded from input row`).
  - [x] Input loader / model / orchestrator preserve source evidence fields.
  - [x] Precision seed guard now allows locked official contextual anchors only with official detail support, stale-demotion clear, core discussion, and search evidence.
  - [x] Focused 13-test bundle PASS.
  - [x] `py_compile` PASS for touched runtime modules.
  - [x] Canary `after_precision_context_anchor` completed/flushed/pending/failed `1/1/0/0`, `Identified=1`, title `탐식의 재림`, `candidate_ledger_status=safe_resolved`.
  - [x] Repeat canary `after_precision_context_anchor_repeat` completed/flushed/pending/failed `1/1/0/0`, `Identified=1`, title `탐식의 재림`, `candidate_ledger_status=safe_resolved`.
  - [x] Runtime audits for both latest canaries are `GO`.
  - [x] Loop133 report updated: `docs/devs/loop_reports/LOOP_133_REPORT_20260630.md`.
- Quality gates:
  - [x] `11705231` focused blocker status is `TARGETED_REPAIR_PASS_LOOP133_NOT_APPROVAL`.
  - [x] Parent/representative replay after Loop133 repair ran as Loop134 runtime `GO`.
  - [ ] Parent/representative replay after Loop133 repair reached semantic `GO`.
  - [ ] Golden/collateral replay after Loop133 repair is complete.
  - [x] `11685994` image/native-web exact-title verification complete in Loop138 as `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [ ] Remaining expected-work losses are fully dispositioned in a broader replay.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop132 completion challenge audit

- Evidence:
  - [x] User completion challenge accepted.
  - [x] Pasted goal contract re-read.
  - [x] Loop131 remaining expected-work losses rechecked from result JSON.
  - [x] Existing regression tests checked before any precision-seed relaxation.
  - [x] Review artifact `loop132_completion_challenge_disposition_audit.md/json` created.
  - [x] Data Analytics artifact `Loop132 Completion Challenge Disposition Audit` validate/render PASS.
  - [x] Disposition counts recorded: `HOLD_BOUNDARY=3`, `INFO_MISSING_NATIVE_WEB=1`, `NARROW_REPLAY_CANDIDATE=1`.
- Quality gates:
  - [x] Runtime contract inherited from Loop131 remains `GO`.
  - [x] No unsafe code patch adopted.
  - [x] `11705231` focused native-web/replay evidence completed in Loop133 and parent-scope restored in Loop134.
  - [ ] `11705231` evidence counts as full parent/representative semantic approval.
  - [x] `11685994` image/native-web exact-title verification complete in Loop138 as `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [ ] Semantic parent/representative replay is complete.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop131 parent/representative replay after Faust guard

- Evidence:
  - [x] Loop104 38-row parent/representative packet reran after Loop130.
  - [x] Loop131 run `20260630_030549_717991` completed `38/38/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `24`.
  - [x] Runtime audit artifact `loop131_parent_representative_replay_runtime_audit.md/json` created.
  - [x] Runtime audit is `GO`.
  - [x] Targeted `11706871 -> 파우스트 1` closure held at parent replay scope.
  - [x] Expected-work remaining losses recorded: `11663521`, `11685994`, `11694019`, `11700470`, `11705231`.
  - [x] Loop129-to-Loop131 public-title movement recorded.
  - [x] Review artifact `loop131_parent_representative_replay_after_faust_guard_review.md/json` created.
  - [x] Data Analytics artifact `Loop131 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
- Quality gates:
  - [x] Runtime contract is `GO`.
  - [ ] Semantic parent/representative replay is complete.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Full scan approval may be claimed.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop130 Faust direct-rescue targeted guard

- Evidence:
  - [x] Loop129 P0 HOLD/control `11706871 -> 파우스트 1` root-caused.
  - [x] Physical/classic-book image guard added.
  - [x] Candidate preservation kept separate from public-title promotion.
  - [x] Focused regression coverage added/extended.
  - [x] `py_compile` PASS.
  - [x] 3 focused unittests PASS.
  - [x] Loop130 run `20260630_024726_142878` completed `1/1/0/0`.
  - [x] VLM/OCR `READY`, image_post_count `1`.
  - [x] Runtime audit artifact `loop130_faust_direct_rescue_guard_runtime_audit.md/json` created.
  - [x] Runtime audit is `GO`.
  - [x] Target row final public title `null`, `candidate_ledger_status=promotion_blocked`.
  - [x] Review artifact `loop130_faust_direct_rescue_guard_review.md/json` created.
  - [x] Data Analytics artifact `Loop130 Faust Direct Rescue Guard Review` validate/render PASS.
- Quality gates:
  - [x] Targeted row is `TARGETED_PASS`.
  - [x] Loop104 38-row parent/representative replay after patch is complete as Loop131.
  - [ ] Five remaining expected-work losses are resolved.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Full scan approval may be claimed.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop129 parent/representative replay runtime GO / semantic NO-GO

- Evidence:
  - [x] Pre-restore shard audit `16/36`, bad `17-36`.
  - [x] Missing shards `17-36` restored with protected incremental lifecycle.
  - [x] Post-restore shard audit `36/36`, bad `[]`.
  - [x] Loop129 run `20260630_020121_110991` completed `38/38/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `24`.
  - [x] Runtime audit artifact `loop129_parent_representative_replay_runtime_audit.md/json` created.
  - [x] Runtime audit is `GO`.
  - [x] Loop123-127 target rows stayed without final public title.
  - [x] Golden positive expected-work losses remain: `11698897`, `11663521`, `11685994`, `11694019`, `11700470`, `11705231`.
  - [x] Recent P0 HOLD/control public-title gain `11706871 -> 파우스트 1` was root-caused and targeted-closed in Loop130.
  - [x] Loop128-to-Loop129 public-title movement recorded.
  - [x] Review artifact `loop129_parent_representative_replay_after_shard_restore_review.md/json` created.
  - [x] Data Analytics artifact `Loop129 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
- Quality gates:
  - [x] Runtime contract is `GO`.
  - [ ] Semantic parent/representative replay is complete.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Full scan approval may be claimed.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop128 parent/representative replay NO-GO

- Evidence:
  - [x] Loop104 anti-regression parent/representative packet reran after Loop123-127.
  - [x] Loop128 run `20260630_010430_041790` completed `38/38/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `24`.
  - [x] Runtime audit artifact `loop128_parent_representative_replay_runtime_audit.md/json` created.
  - [x] Runtime audit is `NO-GO`: `mcp_endpoint_count_after_filter_lt_health_required_ok_count`, after_filter `16`, required_ok `36`.
  - [x] Loop123-127 target rows stayed without final public title.
  - [x] Golden negative no-public-work public-title gains `0`.
  - [x] Golden positive expected-work title losses recorded: `11698897`, `11663521`, `11685994`, `11694019`, `11700470`, `11705231`.
  - [x] Recent P0 HOLD/control public-title gain recorded: `11706871 -> 파우스트 1`.
  - [x] Review artifact `loop128_parent_representative_replay_after_loop127_review.md/json` created.
  - [x] Data Analytics artifact `Loop128 Parent Replay NO-GO Review` validate/render PASS.
- Quality gates:
  - [ ] Runtime contract is `GO`.
  - [ ] Parent/representative replay is complete.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Full scan approval may be claimed.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 Loop123-127 public-title reopen targeted progress

- Evidence:
  - [x] Loop123 repeated the Loop115 five-row packet.
  - [x] Loop124 reopening `11694019` recorded.
  - [x] Loop125 reopenings `11658620` and `11668288` recorded.
  - [x] Loop126 reopening `11694019` recorded.
  - [x] Alias-only official URL recall, generic batch alias, forced-upgrade relation hold, and author+plot composite precision guards added.
  - [x] Focused regression tests added.
  - [x] `py_compile`, focused tests, and related unittest bundle `271 OK` passed.
  - [x] Loop127 run `20260630_004841_310108` completed `5/5/0/0`, VLM/OCR `READY`, image_post_count `2`.
  - [x] Loop127 identified titles `0`; all five rows final public title `null`.
  - [x] Review artifact `loop123_127_public_title_reopen_repair_review.md/json` created.
  - [x] Data Analytics artifact `Loop123-127 Public Title Reopen Repair Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [x] Targeted five-row public-title reopen status is `TARGETED_REPAIR_PASS_LOOP127_NOT_APPROVAL`.
  - [ ] Parent/representative replay is complete.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Full scan approval may be claimed.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop120-121 batch alias competing-hold targeted progress

- Evidence:
  - [x] Loop120 repeat ran from the Loop119 five-row packet.
  - [x] Loop120 runtime was `5/5/0/0`, but `11698897` reopened as `[림월드]변방계에서 회귀자로 살아남기`.
  - [x] Batch-memory exact alias rescue root cause recorded.
  - [x] Competing-hold rescue block added in pipeline and candidate audit.
  - [x] Regression test added.
  - [x] `py_compile` and affected unittest `248 OK` passed.
  - [x] Loop121 run `20260629_233340_435398` completed `5/5/0/0`, VLM/OCR `READY`, image_post_count `2`.
  - [x] Loop121 `11698897` final title stayed `null` with `batch_memory_alias_rescue_blocked_competing_hold`.
  - [x] Review artifact `loop120_121_batch_alias_competing_hold_review.md/json` created.
  - [x] Data Analytics artifact `Loop120-121 Batch Alias Competing-Hold Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [x] Targeted `11698897` reopen path is blocked in Loop121.
  - [ ] Positive/control stability is restored (`11668288` drift remains open).
  - [ ] Parent/representative replay is complete.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Full scan approval may be claimed.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop118-119 reopen guard targeted progress

- Evidence:
  - [x] Loop117 recurrent reopen paths root-caused for `11666713`, `11694019`, and `11698897`.
  - [x] Sticky verifier veto, cross-media recall hold, and weak-source exact-title bridge hold added.
  - [x] Loop118 run `20260629_225200_510563` completed `5/5/0/0`; one target reopen path remained.
  - [x] Loop119 run `20260629_225904_808962` completed `5/5/0/0`, VLM/OCR `READY`, image_post_count `2`.
  - [x] Loop119 target reopen rows held: `11666713`, `11694019`, `11698897`.
  - [x] Positive/control `11668288` separated from target-regression closure.
  - [x] `py_compile`, affected unittest `247 OK`, and `git diff --check` passed.
  - [x] Review artifact `loop118_119_reopen_guard_replay_review.md/json` created.
  - [x] Data Analytics artifact `Loop118-119 Reopen Guard Replay Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [x] Targeted reopen path status is `TARGETED_REOPEN_PATHS_HELD`.
  - [ ] Repeat or parent/representative replay is complete.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Source full completion is closed.
  - [ ] Full-panel collateral approval is `GO`.
  - [ ] Full scan approval may be claimed.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop117 broader replay NO-GO

- Evidence:
  - [x] Existing Loop115 five-row variance packet rerun after Loop116b-116d guard.
  - [x] Loop117 run `20260629_222704_833019` completed `5/5/0/0`, VLM/OCR `READY`, image_post_count `2`.
  - [x] `11658620` remained blocked.
  - [x] Reopened rows recorded: `11666713`, `11694019`, `11698897`.
  - [x] Review artifact `loop117_public_title_gain_after_guard_replay_review.md/json` created.
  - [x] Data Analytics artifact `Loop117 Public Title Gain Replay` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [ ] Broader replay semantic gate is `GO`.
  - [ ] Loop103 P1/P2 queue may resume.
  - [ ] Full scan approval may be claimed.

## 2026-06-29 Loop116b-116d lubko prefix-context guard NO-GO

- Evidence:
  - [x] Loop116b four-row prefix packet generated from original Loop108 rows.
  - [x] Loop116b run `20260629_215526_021681` reproduced `11658620` unsafe public title.
  - [x] Ambiguous stable-alias bridge guard added.
  - [x] Loop116c run `20260629_220351_554714` completed `4/4/0/0`, VLM/OCR `READY`, `11658620` public title blocked.
  - [x] Loop116d repeat `20260629_221301_518080` completed `4/4/0/0`, VLM/OCR `READY`, `11658620` public title blocked.
  - [x] `py_compile`, `tests.test_candidate_audit`, `tests.test_known_title_abbreviation_support`, and focused stable-alias integration passed.
  - [x] Review artifact `loop116b_116d_lubko_prefix_context_guard_review.md/json` created.
  - [x] Data Analytics artifact `Loop116b-116d Lubko Prefix Guard Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [x] Targeted patch status is `TWO_REPEAT_HOLD_FOR_11658620`.
  - [x] Current broad semantic gate remains `NO-GO / REVIEW-LOCKED`.
  - [x] Broader replay including all Loop114 public-title gains ran as Loop117 and returned NO-GO.
  - [ ] Repeat or parent/representative replay after Loop118-119 targeted guards still required.
  - [ ] Keep Loop103 P1/P2 queue suspended.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop116a lubko neighbor context probe NO-GO

- Evidence:
  - [x] Loop116a input generated from original Loop108 rows for `11658615` and `11658620`.
  - [x] Loop116a run `20260629_214134_424194` completed `2/2/0/0`, VLM/OCR `READY`.
  - [x] `11658615` preserved official detail resolution.
  - [x] `11658620` preserved `primary_work` and verified alias evidence.
  - [x] `11658620` final public title remained blocked.
  - [x] Review artifact `loop116a_lubko_neighbor_context_probe_review.md/json` created.
  - [x] Data Analytics artifact `Loop116a Lubko Neighbor Context Probe` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [x] Immediate neighbor context does not reproduce Loop114 unsafe final serialization.
  - [x] Current broad semantic gate remains `NO-GO / REVIEW-LOCKED`.
  - [ ] Wider prefix-context probe still required.
  - [ ] Keep Loop114 public-title gains quarantined.
  - [ ] Keep Loop103 P1/P2 queue suspended.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop115 completion recheck / variance repeat NO-GO

- Evidence:
  - [x] Original pasted goal and Loop06 report rechecked.
  - [x] Source/preflight subagent audit completed read-only.
  - [x] Collateral/semantic subagent audit completed read-only.
  - [x] Docs/gate sync subagent audit completed read-only.
  - [x] Loop115 input generated from original Loop108 rows for five variance/gain candidates.
  - [x] vLLM `/v1/models` live check passed.
  - [x] Loop115 run `20260629_212549_694367` completed `5/5/0/0`, VLM/OCR `READY`, identified `0`.
  - [x] Review artifact `loop115_goal_completion_recheck_variance_repeat_review.md/json` created.
  - [x] Data Analytics artifact `Loop115 Goal Completion Recheck` validate/render PASS.
- Quality gates:
  - [x] Loop115 runtime integrity is `GO`.
  - [x] Loop115 repeat confirms no public title on all five rows.
  - [x] Current broad semantic gate remains `NO-GO / REVIEW-LOCKED`.
  - [ ] Do not count Loop115 all-HOLD repeat as approval.
  - [ ] Root-cause Loop114 broad replay title openings versus Loop115 repeat blocks.
  - [ ] Keep Loop103 P1/P2 queue suspended.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop111-114 platform/OCR SEO replay NO-GO

- Evidence:
  - [x] Platform SEO suffix/prefix and OCR title-surface canonicalization added.
  - [x] `py_compile` PASS.
  - [x] Full `tests.test_candidate_audit` PASS (`83 tests OK`).
  - [x] Loop111 focused run `20260629_201405_077720` completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] Loop112 broad replay run `20260629_201737_073867` completed `19/19/0/0`, VLM/OCR `READY`, semantic `NO-GO`.
  - [x] Loop113 focused run `20260629_204129_668787` completed `2/2/0/0`, VLM/OCR `READY`.
  - [x] Loop114 broad replay run `20260629_204604_191020` completed `19/19/0/0`, VLM/OCR `READY`, identified `8`.
  - [x] Review artifact `loop111_114_platform_ocr_seo_replay_review.md/json` created.
  - [x] Data Analytics artifact `Loop111-114 Platform OCR SEO Replay Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [x] Focused canonicalization target closure is `GO`.
  - [x] Broad replay semantic gate is `NO-GO / REVIEW-LOCKED`.
  - [ ] Do not count Loop111/113 focused pass as semantic approval.
  - [ ] Do not count Loop114 runtime GO as goal completion.
  - [ ] New public-title gains `11658620`, `11666713`, `11668288`, `11694019` need root-cause and repair.
  - [ ] Reconcile Loop113 focused PASS versus Loop114 broad HOLD for `11698897`.
  - [ ] Keep Loop103 P1/P2 queue suspended.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop108-110 state-change repair NO-GO

- Evidence:
  - [x] Loop107 `19` state changes triaged in `loop107_state_change_triage.md/json`.
  - [x] Loop108 run `20260629_185544_955672` completed `19/19/0/0`, VLM/OCR `READY`, identified `8`, semantic `NO-GO`.
  - [x] Candidate-audit guard patch added for conflict bypass, secondary-reference rescue, and direct exact short titles.
  - [x] `py_compile` PASS.
  - [x] Full `tests.test_candidate_audit` PASS (`80 tests OK`).
  - [x] Loop109 focused run `20260629_192037_957246` completed `3/3/0/0`, focused pass `3/3`.
  - [x] Loop110 broad run `20260629_193104_492126` completed `19/19/0/0`, VLM/OCR `READY`, identified `5`.
  - [x] Loop110 confirms patch targets `11660237`, `11700470`, `11706832`.
  - [x] Review artifacts and `LOOP_108_110_REPORT_20260629.md` created.
  - [x] Data Analytics artifact `Loop108-110 상태 변화 보정 리뷰` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO`.
  - [x] Focused patch target closure is `GO`.
  - [x] Broad state-change replay semantic gate is `NO-GO / REVIEW-LOCKED`.
  - [ ] Do not count Loop109 focused pass as approval.
  - [ ] Do not count Loop110 patch-target pass as goal completion.
  - [ ] Remaining attention rows `11658615`, `11663540`, `11666713`, `11668288`, `11705231` need separate handling.
  - [ ] Keep Loop103 P1/P2 queue suspended.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop106-107 scene/author guard replay NO-GO

- Evidence:
  - [x] Focused `11714903` run `20260629_170648_212786` completed `1/1/0/0`, VLM/OCR `READY`, public title blocked.
  - [x] Loop106 clean replay run `20260629_171206_948236` completed `38/38/0/0`, VLM/OCR `READY`, but `11695637` reopened.
  - [x] Focused `11695637` run `20260629_175300_045051` completed `1/1/0/0`, VLM/OCR `READY`, public title blocked.
  - [x] Loop107 clean replay run `20260629_175738_653862` completed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`.
  - [x] requested/effective parallel `36/16` recorded after healthy endpoint filtering.
  - [x] Focused public-title rows `7/7` blocked.
  - [x] Review artifact `loop107_clean_loop104_replay_after_scene_author_guard_review.md/json` created.
  - [x] Data Analytics artifact `Loop107 Clean Replay NO-GO Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity is `GO_WITH_HEALTHY_ENDPOINT_FILTER_16_OF_36`.
  - [x] Focused false-promotion closure is `GO`.
  - [x] Clean replay semantic gate is `NO-GO / REVIEW-LOCKED`.
  - [ ] Do not count focused closure as semantic approval.
  - [ ] Review identified count drop `12 -> 7` and state changes `19`.
  - [ ] Keep Loop103 P1/P2 queue suspended.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop105 clean replay after repair NO-GO

- Evidence:
  - [x] Clean 38-row replay run `20260629_161143_395663` completed `38/38/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR `READY`, image_post_count `24`.
  - [x] requested/effective parallel `36/16` recorded after healthy endpoint filtering.
  - [x] Review artifact `loop105_clean_loop104_replay_after_repair_review.md/json` created.
  - [x] Data Analytics artifact `Loop105 Clean Replay NO-GO Review` validate/render PASS.
  - [x] `11694035`, `11713212`, and `11660257` stayed public-title-blocked.
  - [x] `11714903` reopened as `괴담 호텔 탈출기`.
- Quality gates:
  - [x] Runtime integrity is `GO_WITH_HEALTHY_ENDPOINT_FILTER_16_OF_36`.
  - [x] Clean replay semantic gate is `NO-GO`.
  - [x] Loop105 repeat is `NOT_RUN_BECAUSE_CLEAN_REPLAY_NO_GO`.
  - [ ] Do not count runtime GO as semantic approval.
  - [ ] Root-cause `11714903` before any repeat approval evidence.
  - [ ] Keep Loop103 P1/P2 queue suspended.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop104 repair patch reclassification

- Evidence:
  - [x] Static reclassification artifact created: `loop104_repair_patch_static_reclassification.md/json`.
  - [x] Candidate-ledger extraction false positives removed: `5/9`.
  - [x] True NO-GO remaining before clean replay: `4`.
  - [x] Focused `11713212` canary run `20260629_152235_538688` completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] `11713212` public title blocked with `candidate_ledger_status=promotion_blocked`.
  - [x] Focused `11694035` canary run `20260629_153923_967759` completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] `11694035` public title blocked with `candidate_ledger_status=promotion_blocked` and `title_resolution_allowed=false`.
  - [x] Focused `11660257` canary run `20260629_155128_226258` completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] `11660257` public title blocked with `candidate_ledger_status=hold_without_candidates` and `title_resolution_allowed=false`.
  - [x] Focused `11714903` canary run `20260629_155831_556987` completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] `11714903` public title blocked with `candidate_ledger_status=output_consistency_lint`, `title_resolution_allowed=false`, and blocked title `온 세상이 정신이상자다`.
  - [x] Current status artifact `loop104_repair_patch_current_status.md/json` created.
  - [x] Focused tests and `py_compile` PASS.
  - [x] Data Analytics artifact `Loop104 Repair Patch Reclassification Review` validate/render PASS.
- Quality gates:
  - [ ] Do not count static reclassification as clean Loop104 replay.
  - [ ] Do not count `11713212` single canary as Loop104 or full-panel approval.
  - [ ] Do not count `11694035` single canary as Loop104 or full-panel approval.
  - [ ] Do not count `11660257` single canary as Loop104 or full-panel approval.
  - [ ] Do not count `11714903` single canary as Loop104 or full-panel approval.
  - [ ] Confirm `11713212`, `11694035`, `11660257`, and `11714903` stay blocked in clean Loop104 replay and Loop105 repeat.
  - [ ] Rerun clean Loop104 and Loop105 repeat before queue progression.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop104 anti-regression replay NO-GO

- Evidence:
  - [x] Built replay packet with fixed/variance rows, Loop102-103 lane controls, Loop92-93 stable HOLD controls, recent P0 HOLD controls, and golden controls.
  - [x] Primary Loop104 was partial: completed/flushed/pending/failed `36/34/2/0`, `large_run_complete=false`.
  - [x] Recovery run completed `3/3/0/0`; effective rows available `38/38`.
  - [x] Data Analytics artifact `Loop104 Anti-Regression Replay NO-GO Review` validate/render PASS.
- Quality gates:
  - [x] Anti-regression gate is `NO-GO`.
  - [x] Loop103 next actionable queue is suspended until anti-regression repair.
  - [ ] Do not count recovery-backed effective rows as a clean replay pass.
  - [ ] Do not advance isolated P1/P2 queue.
  - [ ] Root-cause golden negative and stable-HOLD public-title promotions before more queue work.
  - [ ] Rerun clean Loop104 and repeat Loop105 after fixes.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop 102-103 P1 accept-collateral monitor

- Evidence:
  - [x] Loop102/103 repeat runs completed `8/8/0/0`, VLM/OCR `READY`.
  - [x] Runtime audits returned `GO`.
  - [x] Stable resolved recovery `11660258`.
  - [x] Variance quarantine `11658615`.
  - [x] Data Analytics artifact `Loop102-103 P1 Accept-Collateral Monitor Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity PASS.
  - [ ] Loop102-103 remains targeted queue accounting, not full anti-regression approval.
  - [ ] Before more single-post/code-fix work, run Loop104 or equivalent missing-control replay for `11698880`, `11669928`, `11674712`, `11668288`, `11658615`, Loop92-93 stable rows, recent P0 HOLD controls, and golden controls.
  - [ ] Full-panel collateral approval remains NO-GO.
  - [ ] Source full completion remains OPEN.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 Loop 98-101 P1 stable-alias descriptor guard

- Evidence:
  - [x] Loop98/99 pre-fix runs completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] Loop99 reproduced `상남자 [독점]` wrong public-title promotion.
  - [x] Code guard added for Decoder descriptor-only stable alias correction.
  - [x] Loop100/101 post-fix runs completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] Post-fix logs did not reproduce `stable alias conflict correction alias='상남자'`.
  - [x] Data Analytics artifact `Loop98-101 Stable Alias Descriptor Guard Review` validate/render PASS.
- Quality gates:
  - [x] Runtime integrity PASS.
  - [x] Focused new tests PASS.
  - [ ] Full test module not green: existing `test_update_question_known_title_abbreviation_survives_semantic_no_work_without_search` failure remains.
  - [ ] Row approval NOT granted: Loop100/101 still split.
  - [ ] Full-panel collateral approval remains NO-GO.
  - [ ] Source full completion remains OPEN.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
  - [x] Next step moved to a broader 8-row P1 repeatability lane as Loop102-103.
  - [ ] Missing fixed/quarantine/golden/control replay remains open after Loop102-103.
- Current accounting:
  - residual total `143`
  - quarantine/human_review `4`
  - next actionable total `139`, P0 `0`, P1 `69`, P2 `70`

## 2026-06-29 Loop 96-97 P1 search-correctness variance review

- Runtime/source scope:
  - [x] Built Loop96 input for P1 `search_correctness` row `11668288`.
  - [x] Confirmed native web page `https://novelpia.com/novel/387014` for `가챠 중독자의 퓨전펑크 생활`.
  - [x] Ran Loop96 with `--slang-db off`, `--reuse-shards-only`, VLM/OCR on, and `--require-vlm-ocr-for-images`.
  - [x] Confirmed Loop96 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Ran Loop97 repeat on the same input.
  - [x] Confirmed Loop97 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirmed both runs VLM/OCR `READY` because `image_post_count=1`.
- Row outcome scope:
  - [x] Confirmed Loop96 identified `1/1` with `safe_resolved`.
  - [x] Confirmed Loop97 identified `0/1` with `promotion_blocked` / `unresolved_matchable`.
  - [x] Recorded `11668288` as `VARIANCE_QUARANTINE_HUMAN_REVIEW`.
  - [x] Confirmed `--slang-db off` did not write production `slang_db/slang_db.json`.
- Gate scope:
  - [x] Data Analytics artifact `Loop96-97 P1 Search-Correctness Variance Review` validate/render PASS.
  - [ ] Do not promote quarantine/human_review row to approval.
  - [ ] Do not promote Loop96 single success to stable closure.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 94-95 P1A variance repeatability review

- Runtime/source scope:
  - [x] Built Loop94 input for P1A variance-open rows `11669928`, `11674712`.
  - [x] Confirmed model endpoint returned `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`.
  - [x] Ran Loop94 with `--slang-db off`, `--reuse-shards-only`, and `--parallel 2`.
  - [x] Confirmed Loop94 completed/flushed/pending/failed `2/2/0/0`.
  - [x] Ran Loop95 repeat on the same input.
  - [x] Confirmed Loop95 completed/flushed/pending/failed `2/2/0/0`.
  - [x] Confirmed image gate `NOT_APPLICABLE` because `image_post_count=0`.
- Row outcome scope:
  - [x] Confirmed Loop94 identified `0/2`.
  - [x] Confirmed Loop95 identified `1/2`.
  - [x] Confirmed `11669928` = HOLD/HOLD/RESOLVED across Loop93/94/95.
  - [x] Confirmed `11674712` = RESOLVED/HOLD/HOLD across Loop93/94/95.
  - [x] Recorded both as `VARIANCE_QUARANTINE_HUMAN_REVIEW`.
- Gate scope:
  - [x] Loop94/95 leak audit `0`.
  - [x] Data Analytics artifact `Loop94-95 P1A Variance Repeatability Review` validate/render PASS.
  - [ ] Do not promote quarantine/human_review rows to approval.
  - [ ] Do not promote Loop94-95 targeted progress to full-panel collateral approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 92-93 P1A expected recall-improvement review

- Runtime/source scope:
  - [x] Built Loop92 P1A input for six expected recall-improvement candidates.
  - [x] Confirmed model endpoint returned `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`.
  - [x] Ran Loop92 with `--slang-db off`, VLM/OCR on, and `--require-vlm-ocr-for-images`.
  - [x] Confirmed Loop92 completed/flushed/pending/failed `6/6/0/0`.
  - [x] Ran Loop93 after the output-contract fix on the same input.
  - [x] Confirmed Loop93 completed/flushed/pending/failed `6/6/0/0`.
  - [x] Confirmed Loop92/93 VLM/OCR semantic review `READY`.
- Row outcome scope:
  - [x] Confirmed Loop92 contract leak rows `3`.
  - [x] Confirmed Loop93 contract leak rows `0`.
  - [x] Confirmed stable HOLD/no-public/no-work rows `4`.
  - [x] Confirmed variance-open rows `11669928`, `11674712`.
  - [x] Recorded P1A as `PARTIAL_REVIEWED_WITH_VARIANCE`.
- Gate scope:
  - [x] `py_compile` PASS.
  - [x] Focused serialized contract tests PASS.
  - [x] `tests.test_expert_main_comment_metadata -v` `9 tests OK`.
  - [x] Data Analytics artifact `Loop92-93 P1A Expected Recall Improvement Review` validate/render PASS.
  - [ ] Do not promote variance-open rows to approval.
  - [ ] Do not promote Loop92-93 targeted progress to full-panel collateral approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 88-91 P0A scope-decision HOLD output consistency

- Runtime/source scope:
  - [x] Built Loop88 focused input for `11698871`.
  - [x] Confirmed Loop88 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirmed Loop88 VLM/OCR semantic review `NOT_APPLICABLE` because `image_post_count=0`.
  - [x] Ran Loop89 after top-level URL cleanup.
  - [x] Confirmed Loop89 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Ran Loop90 and retained it as reason/notes leak failure evidence.
  - [x] Ran Loop91 after serialized contract scrub.
  - [x] Confirmed Loop91 completed/flushed/pending/failed `1/1/0/0`.
- Row outcome scope:
  - [x] Confirmed Loop88 leaked top-level public URL and reason confirmation despite promotion-blocked structure.
  - [x] Confirmed Loop90 still leaked reason/notes confirmation after URL cleanup.
  - [x] Confirmed Loop91 final title/url are `null`.
  - [x] Confirmed Loop91 `work_resolution=unresolved`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`.
  - [x] Confirmed Loop91 `candidate_ledger_status=promotion_blocked`, `candidate_count=7`.
  - [x] Recorded public title approval as `NOT_APPROVED`.
- Gate scope:
  - [x] `py_compile` PASS.
  - [x] Focused URL cleanup test PASS.
  - [x] Focused serialized contract scrub test PASS.
  - [x] `tests.test_candidate_audit -v` `74 tests OK`.
  - [x] `tests.test_expert_main_comment_metadata -v` `8 tests OK`.
  - [x] Data Analytics artifact `Loop88-91 P0A Scope Decision HOLD Review` validate/render PASS.
  - [ ] Do not promote P0 `0` to approval.
  - [ ] Do not promote Loop91 safe HOLD to public title approval.
  - [ ] Do not promote Loop91 targeted closure to full-panel collateral approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 84-87 P0E variant canonicalization guard

- Runtime/source scope:
  - [x] Reran Loop64 P0E input as Loop84 current-code canary.
  - [x] Confirmed Loop84 completed/flushed/pending/failed `5/5/0/0`.
  - [x] Confirmed Loop84 VLM/OCR semantic review `READY`.
  - [x] Ran Loop85 after the first review-anchor patch.
  - [x] Confirmed Loop85 completed/flushed/pending/failed `5/5/0/0` and retained it as failure evidence.
  - [x] Built focused Loop86 input for `11666713`.
  - [x] Confirmed Loop86 completed/flushed/pending/failed `1/1/0/0` and retained it as failure evidence.
  - [x] Ran Loop87 after the immediate mismatch block.
  - [x] Confirmed Loop87 completed/flushed/pending/failed `1/1/0/0`.
- Row outcome scope:
  - [x] Confirmed Loop85 promoted wrong title `21세기 헌터가된 무림인`.
  - [x] Confirmed Loop86 still promoted wrong title through the plain title-body anchor path.
  - [x] Confirmed Loop87 final title/url are `null`.
  - [x] Confirmed Loop87 `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`.
  - [x] Confirmed Loop87 flags include `official_url_recall_blocked_title_body_work_review_surface_mismatch`.
  - [x] Recorded canonical-title recovery as `NOT_APPROVED`.
- Gate scope:
  - [x] `py_compile` PASS.
  - [x] Focused P0E guard tests PASS.
  - [x] `tests.test_title_lead_search_inferred_guard -v` `133 tests OK`.
  - [x] Data Analytics artifact `Loop84-87 P0E Variant Canonicalization Guard Review` validate/render PASS.
  - [ ] Do not promote Loop87 safe HOLD to canonical title approval.
  - [ ] Do not promote Loop87 targeted closure to full-panel collateral approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 82-83 P0D title variant/canonicalization repair

- Runtime/source scope:
  - [x] Built Loop82 P0D input and manifest for `11663535`, `11682791`, `11706871`, and `11710049`.
  - [x] Ran Loop82 targeted canary.
  - [x] Confirmed Loop82 completed/flushed/pending/failed `4/4/0/0`.
  - [x] Confirmed Loop82 VLM/OCR semantic review `READY`.
  - [x] Built focused Loop83 input for `11706871`.
  - [x] Ran Loop83 focused canary.
  - [x] Confirmed Loop83 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirmed Loop83 VLM/OCR semantic review `READY`.
- Row outcome scope:
  - [x] Confirmed `11663535` remains public-title null with candidate evidence preserved.
  - [x] Confirmed `11682791` resolves to Munpia official detail.
  - [x] Confirmed Loop82 false-promoted `11706871` to `파우스트 1`.
  - [x] Confirmed Loop83 blocks `11706871` public title promotion.
  - [x] Confirmed `11710049` resolves to bracket-preserved Novelpia title.
  - [x] Recorded polluted candidate ledger caveat in `loop82_83_p0d_title_variant_canonicalization_review.md/json`.
- Gate scope:
  - [x] `py_compile` PASS.
  - [x] Focused new non-novel OCR promotion test PASS.
  - [x] OCR/reference guard tests PASS.
  - [x] `tests.test_title_lead_search_inferred_guard -v` `131 tests OK`.
  - [x] Data Analytics artifact `Loop82-83 P0D Title Variant Canonicalization Review` validate/render PASS.
  - [ ] Do not promote Loop83 targeted closure to full-panel collateral approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 79-81 P0C unexpected public-title repair

- Runtime/source scope:
  - [x] Built Loop79 P0C input and manifest for `11657046`, `11658621`, and `11718105`.
  - [x] Ran Loop80 targeted canary and reproduced false positives.
  - [x] Ran Loop81 targeted canary after code changes.
  - [x] Confirmed Loop81 completed/flushed/pending/failed `3/3/0/0`.
  - [x] Confirmed Loop81 VLM/OCR semantic review `READY`.
- Row outcome scope:
  - [x] Confirmed `11657046` remains public-title null.
  - [x] Confirmed `11658621` no longer promotes `무능한게 아니라 전설이였다고?`.
  - [x] Confirmed `11718105` no longer promotes `브로드웨이의 신`.
  - [x] Recorded row-level flags in `loop79_81_p0c_unexpected_public_title_review.md/json`.
- Gate scope:
  - [x] `py_compile` PASS.
  - [x] `tests.test_title_lead_search_inferred_guard -v` `130 tests OK`.
  - [x] Affected suites `115 tests OK`.
  - [x] Data Analytics artifact `Loop79-81 P0C Unexpected Public Title Review` validate/render PASS.
  - [ ] Do not promote Loop81 targeted repair to full-panel collateral approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 76-78 P0A follow-up repair

- Runtime/source scope:
  - [x] Ran Loop76 targeted canary after character/work-cue and precision preservation repairs.
  - [x] Confirmed Loop76 completed/flushed/pending/failed `6/6/0/0`.
  - [x] Ran Loop77 targeted canary after retaining safe hold handling.
  - [x] Confirmed Loop77 completed/flushed/pending/failed `6/6/0/0`.
  - [x] Built focused Loop78 input for `11697267`.
  - [x] Confirmed Loop78 completed/flushed/pending/failed `1/1/0/0`.
- Row outcome scope:
  - [x] Recorded Loop76 `11698871` risky overpromotion as failure evidence.
  - [x] Recorded Loop77 public title `5/6` with `11697267` wrong adjacent URL.
  - [x] Confirmed Loop78 `11697267` title `아카데미 생존 갤러리`, URL `https://novelpia.com/novel/380218`.
  - [x] Confirmed `11698871` remains safe HOLD/scope-decision open.
  - [x] Recorded row-level details in `loop76_78_p0a_followup_repair.md/json`.
- Gate scope:
  - [x] `py_compile` PASS.
  - [x] Affected suites `115 tests OK`.
  - [x] Data Analytics artifact `Loop76-78 P0A Follow-up Repair` validate/render PASS.
  - [ ] Do not promote Loop78 focused proof to semantic approval.
  - [ ] P0A status remains `PARTIAL_REPAIRED_WITH_SCOPE_HOLD`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Source full completion remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 74-75 P0A expected restoration repair

- Runtime/source scope:
  - [x] Reused Loop73 P0A six-row input.
  - [x] Ran Loop74 targeted canary after precision-seed official-detail bypass.
  - [x] Confirmed Loop74 completed/flushed/pending/failed `6/6/0/0`.
  - [x] Confirmed Loop74 VLM/OCR semantic review `READY`.
  - [x] Ran Loop75 targeted canary after weak-bridge bypass preservation.
  - [x] Confirmed Loop75 completed/flushed/pending/failed `6/6/0/0`.
  - [x] Confirmed Loop75 VLM/OCR semantic review `READY`.
- Row outcome scope:
  - [x] Confirmed public restoration improved from Loop73 `0/6` to Loop75 `3/6`.
  - [x] Confirmed restored rows `11660277`, `11663544`, `11671517`.
  - [x] Confirmed remaining HOLD/open rows `11692444`, `11697267`, `11698871`.
  - [x] Recorded row-level details in `loop74_75_p0a_expected_restoration_repair.md/json`.
- Gate scope:
  - [x] `py_compile` PASS.
  - [x] `tests.test_candidate_audit` `72 tests OK`.
  - [x] Data Analytics artifact `Loop74-75 P0A Expected Restoration Repair` validate/render PASS.
  - [ ] Do not promote Loop75 `3/6` partial restoration to semantic approval.
  - [ ] P0A expected restoration remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Source full completion remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 73 residual map and P0A canary

- Runtime/source scope:
  - [x] Refreshed Loop62 residual map with Loop63/64/68-72 targeted closure evidence.
  - [x] Confirmed remaining full-panel collateral candidates `161`.
  - [x] Confirmed remaining P0 rows `14`.
  - [x] Prepared Loop73 P0A input rows `6`.
  - [x] Confirmed Loop73 input missing ids `[]`.
  - [x] Ran Loop73 targeted canary with VLM/OCR required for image rows.
  - [x] Confirmed completed/flushed/pending/failed `6/6/0/0`.
  - [x] Confirmed VLM/OCR semantic review `READY`.
- Row outcome scope:
  - [x] Public expected restoration `0/6`.
  - [x] Candidate or primary evidence preserved `5/6`.
  - [x] Expected missing/no-go `1/6` (`11697267`).
  - [x] Recorded row-level details in `loop73_p0a_expected_restoration_canary.md/json`.
- Gate scope:
  - [x] Data Analytics artifact `Loop73 Current Residual Gate Map` validate/render PASS.
  - [x] Data Analytics artifact `Loop73 P0A Expected Restoration Canary` validate/render PASS.
  - [ ] Do not promote runtime PASS to semantic approval.
  - [ ] P0A expected restoration remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Source full completion remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 68-72 P0B residual guard continuation

- Runtime/source scope:
  - [x] Reproduced Loop68 `11671490` overpromotion as `NO-GO`.
  - [x] Ran Loop69 `11671490` targeted canary after recommendation/direct-image guard fix.
  - [x] Ran Loop70 `11695637` targeted canary after image scene cue bridge guard fix.
  - [x] Ran Loop72 `11695639` targeted canary after comment URL answer URL sync fix.
  - [x] Confirmed Loop72 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirmed VLM/OCR semantic review `READY` for image rows.
- Row outcome scope:
  - [x] Recorded Loop68 as overpromotion failure evidence.
  - [x] Confirmed Loop69 `11671490` public title `null` and `promotion_blocked`.
  - [x] Confirmed Loop70 `11695637` public title `null` and `promotion_blocked`.
  - [x] Recorded Loop71 as title-only recovery with URL gap.
  - [x] Confirmed Loop72 `11695639` title and URL preservation.
  - [x] Recorded row-level details in `loop68_72_p0b_residual_guard_review.md/json`.
- Gate scope:
  - [x] Data Analytics artifact `Loop 68-72 P0B Residual Guard Review` validate/render PASS.
  - [x] `tests.test_candidate_audit` `68 tests OK`.
  - [x] Focused comment URL answer tests `6 tests OK`.
  - [ ] Do not promote targeted P0B repair to full-panel collateral approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 65-67 P0B residual guard review

- Runtime/source scope:
  - [x] Extracted Loop62 `P0B_expected_mismatch_public_title=4` rows into Loop65 targeted input.
  - [x] Ran Loop65 targeted canary with `--slang-db off`, `--reuse-shards-only`, VLM/OCR enabled, and image requirement guard.
  - [x] Confirmed Loop65 failed rows `0`.
  - [x] Ran Loop66 and Loop67 single-row canaries for `11706832`.
  - [x] Confirmed Loop67 VLM/OCR semantic review `READY`.
- Row outcome scope:
  - [x] Recorded Loop65 `11671490`, `11695637`, `11706832` as semantic `NO-GO` due unsafe resolved/allowed state or secondary rescue.
  - [x] Recorded Loop65 `11695639` as `OPEN` because expected URL/title was not recovered.
  - [x] Confirmed Loop67 blocked `11706832` late secondary rescue and left public title `null`.
  - [x] Recorded row-level details in `loop65_67_p0b_residual_guard_review.md/json`.
- Gate scope:
  - [x] Data Analytics artifact `Loop65-67 P0B Residual Guard Review` validate/render PASS.
  - [ ] Do not promote Loop67 targeted pass to P0B lane completion.
  - [ ] Keep residual P0B rows open for follow-up.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Source full completion remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 64 P0E wrong title switch targeted rerun

- Runtime/source scope:
  - [x] Extracted Loop51 `P0E_wrong_title_switch=5` rows into Loop64 targeted input.
  - [x] Ran targeted canary with `--slang-db off`, `--reuse-shards-only`, VLM/OCR enabled, and image requirement guard.
  - [x] Confirmed completed/flushed/pending/failed `5/5/0/0`.
  - [x] Confirmed VLM/OCR semantic review `READY` for `4` image posts.
- Row outcome scope:
  - [x] Confirmed Loop49 wrong-after title reproduced `0`.
  - [x] Recovered before title for `3` rows: `11698890`, `11700500`, `11705252`.
  - [x] Recorded canonicalization caution for `11666713`: current `21세기 무림` vs before `21세기 무림세가`.
  - [x] Demoted `11716448` to null/promotion-blocked.
  - [x] Recorded row-level details in `loop64_p0e_wrong_title_switch_targeted_rerun.md/json`.
- Gate scope:
  - [x] P0E targeted lane classified as `TARGETED_REVIEWED_5_OF_5`.
  - [x] Data Analytics artifact `Loop64 P0E Wrong Title Switch Targeted Rerun` validate/render PASS.
  - [ ] Do not promote P0E targeted review to full-panel collateral approval.
  - [ ] Keep `11666713` variant under canonicalization follow-up review.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Source full completion remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 63 P0C slang pollution targeted rerun

- Runtime/source scope:
  - [x] Extracted Loop51 `P0C_slang_pollution_public_title=7` rows into Loop63 targeted input.
  - [x] Confirmed vLLM model endpoint before rerun.
  - [x] Ran targeted canary with `--slang-db off`, `--reuse-shards-only`, VLM/OCR enabled, and image requirement guard.
  - [x] Confirmed completed/flushed/pending/failed `7/7/0/0`.
  - [x] Confirmed VLM/OCR semantic review `READY` for `6` image posts.
- Row outcome scope:
  - [x] Demoted public title to null for `4` rows: `11685985`, `11685995`, `11687618`, `11690874`.
  - [x] Verified same public title for `3` rows: `11658668`, `11660238`, `11697231`.
  - [x] Recorded row-level details in `loop63_p0c_slang_pollution_targeted_rerun.md/json`.
- Gate scope:
  - [x] P0C targeted lane classified as `TARGETED_REVIEWED_7_OF_7`.
  - [x] Data Analytics artifact `Loop63 P0C Slang Pollution Targeted Rerun` validate/render PASS.
  - [ ] Do not promote P0C targeted review to full-panel collateral approval.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Source full completion remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 62 full-panel collateral residual map

- Runtime/source scope:
  - [x] Rechecked Loop50 full-panel collateral packet `183` candidates.
  - [x] Rechecked Loop53-58 targeted closure evidence for `7` rows.
  - [x] Confirmed remaining full-panel collateral backlog `176`.
  - [x] Confirmed remaining priority split `P0=29`, `P1=77`, `P2=70`.
- Residual P0 scope:
  - [x] `P0A_expected_title_or_url_restoration=3`
  - [x] `P0A_expected_title_restoration=3`
  - [x] `P0B_expected_mismatch_public_title=4`
  - [x] `P0C_slang_pollution_public_title=7`
  - [x] `P0C_unexpected_public_title=3`
  - [x] `P0D_title_variant_or_canonicalization=4`
  - [x] `P0E_wrong_title_switch=5`
- Gate scope:
  - [x] Residual map artifacts `loop62_full_panel_residual_map.md/json` added.
  - [x] Loop62 report added.
  - [x] JSON parse PASS.
  - [x] Data Analytics artifact `Loop62 Full Panel Residual Map` validate PASS.
  - [ ] Do not promote residual mapping to full-panel collateral approval.
  - [ ] Do not treat targeted queue `0` as approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep Loop10 slang write-back review `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 61 slang write-back review

- Runtime/source scope:
  - [x] Rechecked Loop10 result manifest, compare, next queue, and input policy.
  - [x] Confirmed runtime completed/flushed/pending/failed `92/92/0/0`.
  - [x] Confirmed compare movement `review=92` and targeted next queue `0`.
  - [x] Confirmed Loop10 canary policy was `off/read-only canary; no production write-back`.
- Slang DB scope:
  - [x] Recomputed signal split: `store_true=29`, `store_false=31`, no `slang_insight=32`.
  - [x] Confirmed store-true decode verification failures `0`.
  - [x] Recorded unresolved store-true rows `11700500` and `11710043`.
  - [x] Confirmed all `19` unique store-true terms already exist in `slang_db/slang_db.json`.
  - [x] Confirmed `6` terms are multi-title/bucket risk terms.
  - [x] Confirmed `slang_db/slang_db.json` was not modified in git status.
- Gate scope:
  - [x] Loop10 slang write-back review closed as `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK`.
  - [x] Data Analytics artifact `Loop61 Slang Writeback Review Gate` validate/render PASS.
  - [ ] Do not promote queue `0` to slang DB approval.
  - [ ] Do not promote review-only closure to semantic approval.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 60 failed-row targeted rerun

- Runtime/source scope:
  - [x] Reconstructed `11694057` one-row input from prior checkpoint/source evidence.
  - [x] Confirmed vLLM model endpoint before rerun.
  - [x] Ran targeted canary with `--slang-db off` and `--reuse-shards-only`.
  - [x] Confirmed completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirmed final row `official_title=괴담에 휘말렸다`, `work_resolution=resolved`, `discussion_type=character_talk`.
- Gate scope:
  - [x] Concrete failed-row runtime blocker `11694057` closed.
  - [x] Data Analytics artifact `Loop60 Failed Row Targeted Rerun Gate` validate/render PASS.
  - [ ] Do not promote one-row targeted rerun to source full completion.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [x] Loop 10 slang write-back review closed by Loop61 as `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK`.
- Keep source full completion `OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 59 source integrity recovery

- Runtime/source scope:
  - [x] Read source manifest, checkpoint, and pending snapshot.
  - [x] Confirmed final result rows `1933`, checkpoint completed rows `1945`, checkpoint failed rows `1`, pending snapshot rows `13`.
  - [x] Confirmed manifest input posts `104502` and `large_run_complete=false`.
  - [x] Recovered completed checkpoint rows into separate output rows `1945`.
  - [x] Excluded failed placeholder `11694057` from recovered output.
- Code/verification scope:
  - [x] Added lone surrogate replacement before HTTP JSON transport.
  - [x] Added nested payload and HTTP body regression tests.
  - [x] `py_compile` PASS.
  - [x] focused surrogate transport tests `2 tests OK`.
  - [x] `tests.test_llm_client_multimodal` `16 tests OK`.
  - [x] Data Analytics artifact `Loop59 Source Integrity Recovery Gate` validate/render PASS.
  - [ ] Do not promote recovered checkpoint output to source full completion.
  - [x] Reran failed row `11694057` after original/source row was located in Loop60.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Loop 10 slang write-back review remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 58 direct expected surface over homonym fix

- Runtime scope:
  - [x] Ran final two-row targeted canary with VLM/OCR required.
  - [x] Ran repeat two-row targeted canary with VLM/OCR required.
  - [x] Final manifest runtime recorded: completed/flushed/pending/failed `2/2/0/0`.
  - [x] Repeat manifest runtime recorded: completed/flushed/pending/failed `2/2/0/0`.
  - [x] Requested/effective parallel `1/1`.
  - [x] VLM/OCR semantic review ready for target rows `11674703`, `11703657`.
- Gate scope:
  - [x] `11674703` recovered: `도굴왕`, URL `null`, `candidate_ledger_status=safe_resolved`.
  - [x] `11703657` recovered: `야만인은 문명하면 안되냐`, `https://novelpia.com/novel/405310`, `candidate_ledger_status=safe_resolved`.
  - [x] Direct comment/self-resolution URL preservation covered by regression test.
  - [x] Title-request comment URL answer recovery covered by regression test.
  - [x] Weak surface/search title replacement and official-detail URL restoration covered by regression tests.
  - [x] Decoder-exact post-title surface guard covered by regression test.
  - [x] Data Analytics artifact `Loop58 Direct URL Surface Homonym Gate` validate/render PASS.
  - [ ] Do not promote targeted lane recovery to full-panel collateral approval.
  - [ ] Full-panel collateral approval remains `NO-GO`.
  - [ ] Source full completion remains `OPEN`.
  - [ ] Loop 10 slang write-back review remains `OPEN`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 57 primary expected candidate precedence fix

- Runtime scope:
  - [x] Ran final two-row targeted canary with VLM/OCR required.
  - [x] Manifest runtime recorded: completed/flushed/pending/failed `2/2/0/0`.
  - [x] Requested/effective parallel `1/1`.
  - [x] VLM/OCR semantic review ready for image posts `11658637`, `11677913`.
- Gate scope:
  - [x] `11658637` recovered: `재벌집 막내아들`, `https://novel.munpia.com/69583`, `candidate_ledger_status=safe_resolved`.
  - [x] `11677913` recovered: `이세계 검은 머리 외국인`, `https://novelpia.com/novel/1082`, `candidate_ledger_status=safe_resolved`.
  - [x] Direct OCR/work-cue official probe preservation covered by regression test.
  - [x] Blog/review suffix and author/volume wrapper promotion blocking covered by regression tests.
  - [x] Verified alias official-detail bridge path covered by regression test.
  - [x] Data Analytics artifact `Loop57 Primary Expected Candidate Precedence Fix` validate/render PASS.
  - [ ] Do not promote targeted lane recovery to full-panel collateral approval.
  - [ ] Keep `direct_expected_surface_over_homonym=2` open.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 Loop 56 ratddasip visual alias catalog fix

- Runtime scope:
  - [x] Ran final `11673086` single-row targeted canary with VLM/OCR required.
  - [x] Manifest runtime recorded: completed/flushed/pending/failed `1/1/0/0`.
  - [x] Requested/effective parallel `1/1`.
  - [x] VLM/OCR semantic review ready for image post `11673086`.
- Gate scope:
  - [x] `11673086` recovered: `변방계에서 회귀자로 살아남기`, `https://novelpia.com/novel/382324`, `candidate_ledger_status=safe_resolved`.
  - [x] Positive visual bracket alias behavior covered by regression test.
  - [x] Tag-only `랫따싶` promotion remains blocked by regression test.
  - [x] Same-tag competitor catalog path covered by regression test.
  - [x] Data Analytics artifact `Loop56 Ratddasip Visual Alias Catalog Fix` validate/render PASS.
  - [ ] Do not promote targeted row recovery to full-panel collateral approval.
  - [ ] Keep `primary_expected_candidate_precedence=2` and `direct_expected_surface_over_homonym=2` open.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 55 expected-source remaining canary

- Runtime scope:
  - [x] Ran remaining Loop53 expected-source image rows with VLM/OCR required.
  - [x] Manifest runtime recorded: completed/flushed/pending/failed `2/2/0/0`.
  - [x] `large_run_complete=true`, `partial_flush_gap=false`, `ordered_flush_blocked=false`.
  - [x] Requested/effective parallel `2/2`.
  - [x] VLM/OCR semantic review ready for image posts `11671501`, `11673086`.
- Gate scope:
  - [x] `11671501` recovered: `판초우의의 마법사`, `https://novel.munpia.com/530500`, `candidate_ledger_status=safe_resolved`.
  - [x] `11673086` preserved candidate evidence but stayed unresolved: public title `null`, `candidate_ledger_status=promotion_blocked`.
  - [x] Data Analytics artifact `Loop55 Expected-Source Remaining Canary` validate/render PASS.
  - [ ] Do not promote `11671501` row-level recovery to full-panel collateral approval.
  - [ ] Do not promote `11673086` candidate preservation to public-title resolution.
  - [ ] Keep `11673086`, `primary_expected_candidate_precedence=2`, and `direct_expected_surface_over_homonym=2` open.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 54 alias-abbreviation recall fix

- Code-hook scope:
  - [x] General predicate only; no post_id/title-specific production hardcoding.
  - [x] `니생들이랑 -> 니생들` search materialization covered by unit test.
  - [x] `랫따싶` tag-only promotion remains blocked by negative unit test.
  - [x] `니생들 -> 니들 생각 다 들린다` is curated in `KNOWN_TITLE_ABBREVIATIONS`, not inferred from the failing post id alone.
  - [x] Mixed curated aliases are ordered by post-local occurrence so `니생들` can beat later `김괴라리` in `니생들이랑 김괴라리 ...`.
  - [x] Lifecycle/update-question release is narrow and does not treat any broad `작품` token as a standalone anchor.
- Gate scope:
  - [x] Unit/syntax verification recorded.
  - [x] First targeted canary runtime recorded: completed/flushed/pending/failed `1/1/0/0`.
  - [x] First targeted canary semantic `NO-GO` recorded: expected `니들 생각 다 들린다`, actual `괴담에 휘말렸다`.
  - [x] Second targeted canary runtime recorded: completed/flushed/pending/failed `1/1/0/0`.
  - [x] Second targeted canary row-level `GO` recorded for `11668324`: `니들 생각 다 들린다`, `https://novelpia.com/novel/384318`, alias `니생들`, `candidate_ledger_status=safe_resolved`.
  - [ ] Second canary search health `SEARCH_DEGRADED` must remain visible; do not treat it as broad search/provider approval.
  - [x] Loop55 recovered `11671501` as row-level `GO`.
  - [ ] Remaining Loop53 lanes must stay open: `11673086`, `primary_expected_candidate_precedence=2`, `direct_expected_surface_over_homonym=2`.
  - [ ] Full-panel collateral approval remains `NO-GO`.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 53 P0B concrete expected-recovery gate

- Loop53 packet is a code-review routing artifact, not a code fix, row-level resolution, or approval.
- `expected_source_recall_missing_or_demoted=3` should be reviewed for alias/search recall and candidate materialization before promotion.
- Follow-up status: `11668324` and `11671501` are recovered by targeted canaries; `11673086` remains open with candidate preservation but promotion blocked.
- `primary_expected_candidate_precedence=2` should be reviewed for `reference_role=primary` and final identity sync precedence over noisy candidates.
- `direct_expected_surface_over_homonym=2` should be reviewed for direct post-title/comment-URL anchors blocking homonym official-detail candidates.
- Any code fix from these lanes needs targeted canary/recompare before row closure.
- Keep source full completion and Loop 10 slang write-back review separate.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 52 P0B expected-mismatch disposition gate

- Loop52 disposition is a routing artifact, not row-level resolution or approval.
- `BLOCK_WRONG_AFTER_RECOVER_EXPECTED=7` rows need direct wrong-after blocking plus expected title/source recovery verification before they can close.
- `BLOCK_WRONG_AFTER_PRESERVE_HYPOTHESIS=2` rows preserve unresolved hypotheses; do not force expected-title recovery until web/source evidence is verified.
- `SECONDARY_REFERENCE_HOLD=1` must stay HOLD until direct work-bridge evidence proves the expected reference is the actual discussed work.
- `EXPECTED_URL_PRESERVED_TITLE_SURFACE_REPAIR=1` is title-surface repair on an expected URL/source overlap, not broad approval.
- Loop49 field consistency risk remains open: `identity.official_title=null` with a resolved-looking compare after surface is candidate-surface/field-sync risk.
- Keep source full completion and Loop 10 slang write-back review separate.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 51 P0 panel collateral triage gate

- P0 triage is a routing artifact, not a row-level resolution artifact.
- `P0B_expected_mismatch_public_title=11` rows should be treated as wrong-title risk until the wrong after-title is blocked, the expected title is recovered, or HOLD/no-generalizable-fix rationale is recorded.
- `P0D_title_variant_or_canonicalization=4` rows must not be counted as hard failures until canonical title and source URL are verified.
- `P0C_slang_pollution_public_title=7` rows need direct work-bridge verification before keeping any public title.
- Keep source full completion and Loop 10 slang write-back review separate.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 50 panel collateral packet gate

- A requeue packet is a routing artifact, not a semantic approval artifact.
- Loop50 packet rows `183` must each receive row-level disposition before full-panel collateral approval can change from `NO-GO`.
- P0 rows `36` are the immediate queue: `known_expected_title_lost=6`, `precision_regression_review=21`, `wrong_title_switch_review=9`.
- `expected_recall_improvement_candidate=6` may become exemptions only after direct expected-answer evidence is recorded.
- `safety_demote_review=70` may be acceptable demotion only after HOLD/no-generalizable-fix/expected-null rationale is recorded.
- Keep source full completion and Loop 10 slang write-back review separate.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 49 regression panel replay gate

- Panel replay runtime `375/375/0/0` closes the replay execution gate only.
- Full-panel collateral compare is the approval gate for this step; Loop49 result is `NO-GO` because collateral regression candidates are `183`.
- `resolved_to_null` changes must be triaged carefully: some may be safer demotions, but they are not approval until row-level expected-answer or HOLD rationale is recorded.
- `same_title_url_changed` rows are not counted as regression candidates by the current compare function, but they still need source hygiene review before broad approval.
- Data Analytics render success is reporting evidence only. It is not semantic approval.
- Source full completion and Loop 10 slang write-back review remain separate open gates.
- Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-28 Loop 48 collateral candidate review gate

- `loop47_merged_loop45_loop46_golden_collateral_compare.md/json`의 regression candidates `5`는 Loop 47 expected-answer audit과 대조해 row-level 처분을 남겨야 한다.
- `boundary_unresolved_pass`는 public title recall success가 아니라 evidence-preserved HOLD/pass boundary다.
- `direct_image_hypothesis_pass`는 direct image evidence 기반의 golden PASS이며, exact official title/source completion approval과 동일하지 않다.
- Loop 48 review artifact `loop48_collateral_candidate_review.md/json`이 있어도 full-panel collateral approval은 open으로 유지한다.
- Panel replay, source full completion, Loop 10 slang write-back review가 닫히기 전까지 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-28 Loop 47 merged golden pass gate

- `loop47_merged_loop45_loop46_golden_audit.md/json` 기준 pass `16/16`, fail `0`, `canary_semantic_gate=PASS`이면 16-row golden semantic gate는 닫힌 것으로 기록한다.
- 이 PASS는 full-scan approval이 아니다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 계속 유지한다.
- `expected_work_evidence_preserved_unresolved`와 `positive_image_boundary_preserved_unresolved`는 안전한 HOLD/증거보존 상태이지 public-title recall success가 아니다.
- `11700470`처럼 expected work가 있으나 image-boundary title bridge가 충분하지 않은 row는 unsafe public title 대신 `title_resolution_allowed=false`로 보존되는 것이 이번 gate의 의도다.
- `loop47_merged_loop45_loop46_golden_collateral_compare.md/json`의 collateral regression candidates `5`는 별도 review queue다. Golden PASS와 같은 의미로 합치지 않는다.
- Panel replay, source full completion, Loop 10 slang write-back review가 닫히기 전까지 goal completion이나 full approval을 선언하지 않는다.

## 2026-06-28 Loop 17 locked-official character sentence-alias gate

- Clean official detail evidence is not enough to promote a candidate when the packet only provides an unresolved character-attached sentence-like alias.
- `11700470`처럼 `밤도깨비 에이브`가 character cue로만 확인되고 work-title bridge가 부족하면 `도깨비가 되었다.` 같은 partial-token official detail hit는 public title이 아니라 HOLD/unresolved여야 한다.
- Single-row canary에서 prior wrong title이 사라져도 golden replay에서 다른 wrong title이 생기면 closure가 아니다.
- `loop17_locked_official_character_sentence_alias_golden_audit.md/json` 기준 pass `10/16`, fail `6`, `canary_semantic_gate=NO-GO`이면 goal은 여전히 open이다.
- `11700470`이 `바람과 별무리`로 resolved되면 expected `악당 얼굴의 B급 모험자`에 도달하지 못한 wrong-title blocker로 유지한다.
- `loop17_locked_official_character_sentence_alias_golden_collateral_compare.md/json`의 collateral regression candidates `6`은 full-panel collateral approval이 아니라 remaining risk evidence다.
- 계속 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 Loop 16 short-lead confirmed-alias stem gate

- Confirmed alias flags are not enough to promote a short leading stem alias when the packet lacks a direct work anchor.
- `11705245`처럼 `하남자`가 `하남자의 탑 공략법`의 leading stem이면서 genre/slang surface일 수 있는 row는 candidate evidence를 보존하되 final public title은 `None`/unresolved가 맞다.
- `_confirmed_alias_exempts_weak_bridge(...)` may preserve non-stem aliases, but leading stem aliases with weak bridge shape must still hit `short_lead_surface_public_title_bridge`.
- `loop16_short_lead_confirmed_alias_11705245_result.json` single-row canary가 green이어도 전체 semantic approval이 아니다.
- `loop16_short_lead_confirmed_alias_golden_audit.md/json` 기준 pass `11/16`, fail `5`, `canary_semantic_gate=NO-GO`이면 goal은 여전히 open이다.
- `loop16_short_lead_confirmed_alias_golden_collateral_compare.md/json`의 collateral regression candidates `5`는 full-panel collateral approval이 아니라 remaining risk evidence다.
- 계속 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 Loop 15 known-title abbreviation hard-lock gate

- Curated known-title abbreviation이 post title prefix에 보이고 official detail URL이 검색되더라도, packet-local work cue/direct anchor가 없으면 public title hard-lock/rescue로 쓰지 않는다.
- `11694035`처럼 community shorthand가 잡담/밈 prefix로만 쓰인 row는 candidate evidence를 보존하되 final public title은 `None`/unresolved가 맞다.
- update-question recall semantics는 work cue release로 볼 수 있지만, strict direct anchor와 섞어 title lock 근거로 확장하지 않는다.
- `loop15_known_title_anchor_11694035_result.json` single-row canary가 green이어도 전체 semantic approval이 아니다.
- `loop15_known_title_anchor_golden_audit.md/json` 기준 pass `10/16`, fail `6`, `canary_semantic_gate=NO-GO`이면 goal은 여전히 open이다.
- `loop15_known_title_anchor_golden_collateral_compare.md/json`의 collateral regression candidates `5`는 full-panel collateral approval이 아니라 remaining risk evidence다.
- 계속 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 Loop 14 golden replay / semantic NO-GO gate

- Golden canary가 completed/flushed/pending/failed `16/16/0/0`, exit `0`, VLM/OCR `READY`로 끝나도 이는 runtime gate일 뿐이다.
- `loop14_golden_after_fix_audit.md/json` 기준 pass `10/16`, fail `6`, `canary_semantic_gate=NO-GO`이면 semantic gate는 닫히지 않았다.
- `loop14_golden_after_fix_collateral_compare.md/json`의 collateral regression candidates `6`은 full-panel collateral approval이 아니라 regression evidence다.
- `11694035`처럼 known-title abbreviation이 official detail을 찾더라도, negative no-public-work golden row에서 public title로 과승격하면 hard fail로 유지한다.
- Positive expected-work unresolved/HOLD row는 runtime 성공으로 자동 승인하지 않는다. shared grounding/promotion guard 수정, golden rerun, panel replay가 별도로 필요하다.
- 계속 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 Loop 14 full-sweep recovery / still-not-complete gate

- Loop 14에서 affected suite `450 tests OK`와 corrected full sweep `1162 tests OK`가 나왔더라도, 이것은 unittest gate recovery일 뿐이다.
- full sweep green을 semantic approval로 승격하지 않는다. golden runtime이 green이어도 semantic/collateral `NO-GO`이면 open이고, panel replay, source full completion, Loop 10 slang write-back review가 닫히기 전까지 overall goal은 `ACTIVE / NOT_COMPLETE`다.
- 후단 rescue/guard 수정은 direct image work surface, batch alias, locked official, final reread, relation hold처럼 여러 결합면이 같은 title state를 만지므로, 테스트 기대값을 낮추기 전에 결합면 우선순위를 코드에서 정렬해야 한다.
- Data Analytics artifact는 gate status를 시각화한 보조 산출물이다. artifact render 성공도 semantic approval이 아니다.
- 계속 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-28 Loop 13 completion recheck / full-sweep gate

- goal tool status가 `active`여도, 문서/로그 gate가 열려 있으면 완료 처리하지 않는다.
- `unittest discover -s tests`는 `expert_main.py`의 `--server-type/-s`와 충돌할 수 있으므로 full sweep evidence는 긴 옵션 `--start-directory tests --pattern "test_*.py"` 실행을 기준으로 남긴다.
- Loop 13 보정 full sweep 결과는 `1162 tests`, `failures=9`, `errors=1`, exit `1`이다. 이 상태에서는 affected-module/sweep gate가 `FAIL`이며 semantic approval은 금지된다.
- 실패는 `tests.test_agentic_pipeline_rework` 독립 실행에서도 `450 tests`, `failures=9`, `errors=1`로 재현된다. import 충돌 73개 직접 테스트는 `OK`라서 command/discovery 문제와 실제 agentic regression을 분리해 추적한다.
- panel/golden/collateral replay, source full completion, Loop 10 slang write-back review도 계속 open이다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 Author-angle official-detail canonicalization gate

- `작가 <작품명>` 또는 동등한 author-angle search surface는 그 자체로 public official title이 아니다.
- 동일 row의 candidate ledger에 inner title과 일치하는 official detail candidate가 있으면 public identity, nested `novel_identity`, `primary_work`, URL을 official detail title로 canonicalize한다.
- 원래 author-angle surface는 증거로 보존하되, final reason/reason_lines가 이전 bad surface를 계속 official title처럼 말하면 회귀다.
- targeted next queue `0`은 단일 residual closure일 뿐이다. panel/golden/collateral replay, full unittest sweep, source full completion 전에는 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-01 Codex goal subagent 병렬과 repo worker 병렬 분리

- Codex `/goal`에서 "여러 전문가와 병렬"은 Codex `spawn_agent` subagent를 뜻한다. `expert_main.py --parallel`, shard 수, 내부 LLM 전문가 체인 병렬도와 같은 repo runtime 설정으로 대체하지 않는다.
- 메인 Codex는 즉시 필요한 blocking patch와 최종 gate 통합을 맡고, subagent에는 서로 독립적인 sidecar audit을 배정한다.
- 추천 기본 축은 `code gate`, `runtime/source`, `semantic/VLM/browser`, `slang_db/BatchContext`, `prompt/orchestration`, `docs/checklist`다. small targeted run에서는 2~4개 축으로 줄일 수 있다.
- subagent 결과는 candidate evidence다. 최종 보고 전 메인 Codex가 파일 경로, line, `post_id`, `run_id`, manifest/checkpoint/review packet 근거를 직접 확인해야 한다.
- subagent 병렬을 수행했더라도 completed source, Browser image-loading gate, random baseline, P0/P1 expansion이 없으면 10만 semantic approval은 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 Browser image loading text-match gate

- 이미지 row에서 `article_loaded_count < article_image_count`, lazy/data-original/placeholder/incomplete/broken pending, 또는 동등한 browser loading failure가 있으면 screenshot/visual artifact가 있어도 visual evidence는 미완료다.
- 이 상태에서 resolved title, OCR/reason, search-only/text match가 결론 근거로 쓰이면 `image_loading_failed_or_pending_text_match_used` issue로 분리한다.
- `browser_visual_available`은 `browser_loading_complete`, `visual_artifact_linked`, `visual_semantic_alignment`를 모두 뜻하지 않는다. 보고서에서는 세 단계를 분리해 적는다.
- 로딩 실패/대기 row는 텍스트 매칭만으로 `Strong` evidence나 semantic `GO`를 열 수 없다. Browser 재확인, VLM/OCR 재처리, 또는 human review가 필요하다.
- 입력 loader와 review packet은 image block URL alias를 `url` 하나로만 보지 않는다. `image_url` 또는 `src`만 있는 block도 image post로 세야 하며, 이미지가 있는 source에서 `image_post_count=0`이 나오면 `no_image_blocks`가 아니라 loader/source evidence gap부터 의심한다.

## 2026-06-01 no-work/context-only 공통 후단 승격 게이트

- `semantic_seed_review`, `title_resolution_allowed=false`, `title_resolution_state=context_only` 등 no-work/context-only 신호가 있으면 후단 최종 검증기, 후보 승격, unresolved 단일 후보 승격, recommendation guard 해제도 같은 단조성 gate를 따라야 한다.
- no-work/context-only 해제용 strict direct anchor는 packet-local 직접 근거만 인정한다. raw post title/body/comment 직접 작품 표면, VLM/OCR 직접 작품 표면, image primary work anchor, verified character-work link, compound title-character bridge가 대표 예다.
- official detail URL, search result title match, canonical convergence, Decoder best_match alias mapping, episode ref 단독은 direct hard anchor가 아니다.
- `_title_mentioned_in_post_main_context()`처럼 Decoder alias를 포함할 수 있는 helper를 no-work 해제용 direct anchor로 쓰면 회귀다. no-work 해제는 strict helper 또는 동등한 raw/visual packet-local evidence를 써야 한다.
- `_compute_title_acceptance()`는 no-work/context-only + direct anchor 없음이면 `semantic_no_work_block=true`와 non-accept decision을 남겨야 한다.
- 소규모 targeted 회귀가 통과해도 expanded `context_only_late_rescue_without_direct_anchor` bucket과 random baseline 전에는 10만 semantic approval을 열지 않는다.

## 2026-06-01 no-work/context-only late rescue gate

- `semantic_seed_review`, `discourse_semantic_seed_guard`, `final_semantic_reread`, `title_resolution_allowed=false`, `title_resolution_state=context_only`가 no-work/context-only를 표시하면 후단 search/known alias/`slang_db`/`BatchContext` rescue는 direct hard anchor 없이 title을 되살릴 수 없다.
- 공식 플랫폼 상세 URL이나 검색 title match는 작품 존재 증거일 수 있지만, no-work/context-only 발화 의도를 특정 작품 토론으로 바꾸는 direct hard anchor가 아니다.
- direct hard anchor는 원문 title/body/comment의 직접 작품명/안정 별칭, VLM/OCR 직접 작품명, verified character-work link처럼 packet-local 직접 작품 근거다. 회차/스포/작가의 말, 공식 플랫폼 URL, 공식 detail edge는 보조 evidence일 수 있지만 no-work/context-only 해제에는 위 직접 근거와 결합되어야 하며 단독으로 resolved title을 되살릴 수 없다.
- `search_evidence_alias_inference`와 batch alias rescue가 official detail URL만으로 no-work를 통과하면 `context_only_late_rescue_without_direct_anchor` 회귀다.
- 단건 canary에서 `11718080`류가 정상 non-resolved로 나와도, expanded random baseline과 P0/P1 high-risk bucket 검토 전까지 10만 semantic approval로 승격하지 않는다.

## 2026-06-01 Codex goal spawn_agent 병렬 운영 재확인

- 사용자가 goal 작업에서 "여러 전문가", "subagent", "병렬 검토"를 말하면 먼저 Codex `spawn_agent` 전문가 축을 선언하고 실제 subagent를 배정한다.
- `expert_main.py --parallel`, shard/worker 수, 내부 `src/llm_batch/experts/*` 전문가 체인은 repo runtime 계층이다. Codex goal subagent 병렬 검토와 섞지 않는다.
- 대형 10만 건 품질 리뷰 기본 축은 `semantic`, `VLM/browser`, `runtime/log`, `prompt/pipeline`, `docs/checklist`다. 필요하면 `slang_db/BatchContext`와 `source/preflight`를 별도로 둔다.
- 각 subagent는 읽기 전용 감사 또는 명시된 disjoint write scope만 맡고, 공통 docs/checklist와 최종 gate는 메인 Codex가 통합한다.
- subagent는 단독 승인자가 아니다. subagent의 `GO` 제안은 candidate finding이며, 메인 Codex가 파일 경로, line, `post_id`, `run_id`, manifest/checkpoint/review packet 근거를 재확인해야 한다.
- subagent 검토가 부족하면 `spawn_agent` 축과 scope를 보강한다. small input을 `--parallel 36`으로 반복 실행하는 것은 리뷰 병렬 보강이 아니다.
- goal 보고서에는 `spawn_agent_axes`, `expert_main_requested_parallel`, `expert_main_effective_parallel`, `runtime_gate`, `semantic_gate`를 분리해 남긴다.
- runtime `GO`, targeted canary `GO`, browser/VLM coverage `GO`는 10만 semantic approval이 아니다. completed source, random baseline, P0/P1 expansion, browser/image-loading gate가 모두 닫히기 전까지 `NO-GO / REVIEW-LOCKED`를 유지한다.

## 2026-06-01 Agentic alias metadata/rewrite guard

- `registry_anchor_only` provenance는 최종 output, reason, qualitative packet, LLM judgment packet에서 사라지면 안 된다.
- `alias_resolution_sources`에 `promotion_evidence_tier`, `promotion_confidence`, `confidence_demoted_without_hard_evidence`가 있으면 review label은 evidence tier를 읽어야 한다.
- registry alias + suspected/decoder/search 반복은 soft support다. official/detail/direct hard support 없이 `_apply_known_abbreviation_title_guard()`가 final title을 rewrite하면 회귀다.
- 비공식 title-lead alias search inferred 후보는 score가 높아도 `High`로 올리지 않는다. `source_tier != official_detail`이면 `Medium`이 상한이다.
- `weak_evidence_but_strong_resolution` + `registry_anchor_only`는 `ACCEPT`가 아니라 `HOLD/re_judge`가 기본이다.
- targeted metadata guard 통과는 10만 semantic approval이 아니다. completed source, random baseline, P0/P1 high-risk expansion, browser/VLM evidence gate를 별도로 확인한다.

## 2026-06-01 Agentic known alias promotion confidence gate

- `registry + post-side work anchor`와 `High final rescue`를 같은 단계로 보지 않는다.
- `_try_promote_best_candidate()`는 confidence tier를 evidence strength와 동기화한다.
- official/detail/direct hard support 없는 registry promotion은 `Medium` 또는 review 후보이며 approval evidence가 아니다.
- source/provenance에는 `evidence=registry_anchor_only` 또는 동등한 evidence tier가 남아야 한다.
- targeted guard 통과는 10만 semantic approval이 아니다. completed source, random baseline, P0/P1 high-risk expansion, browser/VLM evidence gate를 별도로 확인한다.

## 2026-06-01 Arbiter alias-only actual branch guard

- Arbiter actual `analyze()` 결과에서 alias-only anchor는 guard exception이 아니다.
- `multi_work` 비교/나열/질문 문맥은 단일 title 강제승격보다 null/보류가 우선이다. 등록 약칭이 보이더라도 post-side work anchor가 없으면 `multi_work_guard`를 유지한다.
- `meme/noise`와 `low-confidence` guard에서 `title_abbrev_mention` / `body_abbrev_mention`은 `_has_curated_alias_guard_exception()` 통과 전까지 weak evidence다.
- 공식 플랫폼 상세 evidence는 작품 존재 증거이지, no-work/context-only 글의 발화 의도를 자동으로 작품 토론으로 바꾸는 증거가 아니다.
- actual branch 테스트는 helper 테스트와 별도로 유지한다. helper가 true/false인 것과 final decision이 null/보존되는 것은 다른 gate다.

## 2026-06-01 Arbiter strong/official support evidence contract

- Arbiter `_has_strong_title_support()`와 `_has_official_title_evidence()`를 같은 gate로 취급하지 않는다.
- official evidence는 공식 플랫폼 상세 URL과 fetched official detail title match가 직접 final title을 지지할 때만 Strong 후보로 본다.
- `known_abbreviation`, `KNOWN_*`, snippet abbreviation hint는 official evidence가 아니다.
- deleted/unavailable, community post, listing/search page는 title text가 겹쳐도 official evidence가 아니다.
- 짧은 title은 다른 공식 제목 내부 substring만으로 통과하지 않는다. token boundary 또는 동등한 직접 표면을 요구한다.
- helper contract 통과는 actual Arbiter decision-path 통과나 10만 semantic approval이 아니다.

## 2026-06-01 Arbiter registered alias guard exception

- Arbiter `multi_work`, `meme/noise`, `low-confidence`, title veto exception은 Registry Alias Evidence Rule 적용 대상이다.
- 등록 약칭 surface만 있으면 guard exception을 열지 않는다. post-side work anchor 또는 동등한 직접/검증 앵커가 필요하다.
- 로그/packet에 `등록 약칭 + 독립 작품 앵커 확인` 수준의 근거가 없으면 registry alias 면제를 Strong evidence로 보지 않는다.
- helper-only 테스트 통과를 actual decision-path 통과로 오독하지 않는다.
- `_has_strong_title_support()` / `_has_official_title_evidence()` 반환 구조 의심은 별도 P1로 추적한다.

## 2026-06-01 Agentic alias support surface/anchor separation

- 등록 약칭 surface 발견은 약한 관측값이다. 강한 alias support로 쓰려면 post-side work anchor가 필요하다.
- `_has_alias_title_support()` 또는 동등 helper가 known abbreviation alias만으로 true가 되면 회귀 후보로 둔다.
- support kinds에서 약칭 surface만으로 `post_main_mention`이 생기면 `reason_evidence_state_mismatch` 또는 hardcoded alias support inflation으로 본다.
- positive packet은 `known_abbreviation_alias`와 `curated_alias_work_anchor`처럼 surface와 앵커를 분리해 남겨야 한다.
- targeted guard 통과는 10만 semantic approval이 아니다. Arbiter와 expanded review gate를 별도로 본다.

## 2026-06-01 Agentic registered alias anchor guard

- Agentic promotion/stability/lock에서 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`는 recall/provenance hint이며 단독 확정 근거가 아니다.
- visible alias surface가 있어도 post-side work anchor 또는 compound title-character bridge가 없으면 direct promotion, stability signal, title lock을 열지 않는다.
- post-side work anchor가 있더라도 official/detail/direct hard support가 없으면 direct promotion confidence는 `High`가 아니라 `Medium` 또는 review-tier로 둔다.
- comment-only alias는 attribution과 대화 흐름을 확인하기 전까지 lock 근거가 아니다.
- no-work/context-only 글에서 search/alias/BatchContext가 등록 약칭을 되살리면 `known_abbreviation_promotion_blocked_missing_anchor` 또는 동등 issue를 기대한다.
- targeted canary의 positive 복구는 10만 semantic approval이 아니다. hardcoded alias static gate, Arbiter guard exception, random/high-risk expansion을 따로 확인한다.

## 2026-06-01 KNOWN_* Jury/Debate hint contract

- `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`는 LLM/Jury/Debate prompt에서 확정 근거로 쓰지 않는다.
- registered alias hit는 no-work가 아니고 독립 work anchor가 있을 때만 weak hint로 전달한다.
- prompt 문구는 `등록 약칭 후보(검토용 힌트)`로 쓰고, 단독 확정 근거가 아니며 독립 evidence가 필요하다는 문장을 함께 둔다.
- `확정적입니다`, `is_relevant=true로 판정하세요`, `Decoder가 실패해도 이 약칭이 해당 작품을 지칭` 같은 결론 강제 문구는 금지한다.
- audit에서 import-only usage와 provenance tuple은 positive blocker가 아니다. runtime promotion/lock/guard exception 경로와 분리한다.
- prompt pressure 감소는 registry risk closure가 아니다. direct rescue와 guard exception이 남으면 `hardcoded_alias_risk_review_required`는 계속 blocker다.

## 2026-06-01 SLANG_DICTIONARY hint-only evidence contract

- `SLANG_DICTIONARY`는 recall hint다. 단독 hit만으로 `official_title`, `resolved_title`, `best_match.title`, `confidence=high`를 만들면 안 된다.
- dictionary hit는 `slang_dictionary_hint` candidate로 남겨도 되지만, 승격에는 원문 직접 title/alias, VLM/OCR 직접 작품 제목, verified character-work link, 또는 no-work가 아닌 상태의 공식 플랫폼 URL + strict snippet/content match처럼 독립 evidence가 필요하다. no-work/context-only 상태에서는 공식 URL/search match 단독을 direct hard anchor로 쓰지 않는다.
- LLM 출력이 dictionary-only mapped title을 high로 올리면 후처리에서 `title=null`, `confidence=none`, `dictionary_alias_hint_requires_independent_evidence`로 낮춘다.
- audit 도구는 provenance tuple과 packet-review tooling metadata를 positive blocker로 세지 않는다. 단, runtime final rescue/High/guard exception 경로는 blocker로 유지한다.
- v474 기준 `SLANG_DICTIONARY`는 `INFO`로 내려갔지만, `KNOWN_ABBREVIATIONS`와 `KNOWN_TITLE_ABBREVIATIONS`는 계속 `REVIEW` blocker다.
- 이 계약의 통과는 hardcoded alias 전체 승인도, 10만 semantic approval도 아니다. action queue에서 completed source, random baseline, P0/P1 expansion blocker를 별도로 확인한다.

## 2026-06-01 hardcoded alias audit tooling marker / unique packet scope

- `tools/` 아래 coverage/audit용 `*_MARKERS` tuple은 runtime hardcoded alias registry가 아니다. audit에는 남기되 `tooling_marker/INFO`로 분리한다.
- positive blocker count에는 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY`처럼 runtime final title rescue/High/prompt pressure 경로에 닿는 registry만 포함한다.
- packet review는 raw artifact duplicate count와 unique post-context registry match count를 함께 보고한다.
- action queue closure는 raw `matched_packets`보다 `unique_post_context_registry_match_count`를 우선한다. historical labels가 unique post-context coverage를 모두 `ACCEPT`로 닫았으면 packet review action은 `closed_by_packet_labels`로 내릴 수 있다.
- 이 closure는 hardcoded alias packet follow-up만 닫는다. registry risk, completed source, random baseline, P0/P1 high-risk expansion은 별도 blocker로 유지한다.
- Codex subagent 병렬 검토 결과는 evidence packet이다. 메인 Codex가 runtime `GO`, packet effective `GO`, semantic approval `REVIEW-LOCKED`를 한 번 더 분리해 통합한다.

## 2026-06-01 packet review raw/effective gate reconciliation

- packet review artifact의 raw `gate=REVIEW`와 최신 action queue의 effective gate를 분리한다.
- raw packet review가 요구한 matched packet 라벨링이 후속 labels에서 모두 `ACCEPT`로 닫혔고 matched count 이상을 커버하면 `closed_by_packet_labels=true`로 둘 수 있다.
- 이 경우 action queue는 `hardcoded_alias_packet_gate=REVIEW`, `hardcoded_alias_packet_effective_gate=GO`를 함께 보고한다.
- packet effective `GO`는 hardcoded alias registry 전체 `GO`가 아니다. positive registry blocker가 남아 있으면 `hardcoded_alias_risk_review_required`는 계속 approval blocker다.
- reconciliation artifact에는 raw packet review, closure labels, latest canary provenance field, remaining blockers를 모두 적는다.

## 2026-06-01 hardcoded alias follow-up closure handling

- hardcoded alias packet label follow-up과 hardcoded alias registry review를 같은 gate로 합치지 않는다.
- historical HOLD/REJECT label은 최신 canary가 같은 post/alias를 더 강한 provenance와 official/platform evidence로 닫았을 때만 `CLOSED_BY_*`로 승격한다.
- closure label에는 최소한 최신 result path, post_id, alias/canonical, `source_registry`, `alias_resolution_source`, `matched_surface_kind`, final title, official/platform evidence를 남긴다.
- v466처럼 label gate가 `GO`여도 `hardcoded_alias_gate=REVIEW` 또는 `hardcoded_alias_packet_gate=REVIEW`가 남으면 approval blocker는 계속 유지한다.
- action queue는 label closure, registry positive risk, packet/provenance review를 각각 다른 action id로 보고해야 한다.
- targeted canary closure는 10만 semantic approval 근거가 아니다. completed source, random baseline, high-risk expansion 상태를 별도 gate로 다시 확인한다.

## 2026-06-01 Browser/CLI fallback metrics missing handling

- fallback Browser evidence는 `Strong`이어도 `approval_scope=post_level_visual_loading_only`로 해석한다. iab 직접 증거와 10만 semantic approval 증거로 승격하지 않는다.
- CLI/Playwright capture가 return code 0이어도 `eval_path=null`, eval JSON empty, `article_image_count=0`이면 metrics missing으로 별도 집계한다.
- Windows `npx.cmd`/playwright-cli daemon 경로가 npm cache `EPERM`, JS 인자 재파싱, `eval_path=null`로 흔들리면 installed browser revision이 있는 cached Playwright `node_modules`를 찾아 direct Node Playwright fallback을 사용한다. 이 경우도 `browser_surface=fallback_playwright_node`로 표기한다.
- DC UI의 일반 `차단` 단어만으로 blocked evidence를 만들지 않는다. `접근이 차단`, `차단되었습니다`, `접근 제한`처럼 실제 접근 제한 문구가 있어야 blocked로 본다.
- screenshot에 이미지가 보이는 것과 자동 gate가 구조화 metrics를 읽은 것은 다르다. metrics missing이면 visual grade를 `Missing/Weak`로 낮추고 원인을 리포트에 남긴다.
- VLM/OCR ready는 run-level 준비 상태다. per-image approval에는 image evidence catalog, fetch/chunk/OCR status, browser article loaded counter, placeholder/incomplete/broken/lazy pending counter, screenshot/observation alignment가 함께 필요하다.

## 2026-06-01 Browser visual fallback evidence handling

- 이미지 row visual gate는 Codex 내장 Browser iab를 우선한다.
- iab 연결이 실패하면 실패 원인과 시도 횟수를 artifact manifest에 남기고, 대체 Playwright MCP/CLI 증거는 fallback으로만 해석한다.
- fallback screenshot과 metrics가 모두 있을 때만 `browser_visual_available`로 올린다. 최소한 게시글 제목/URL, 본문 이미지 selector, loaded counter, placeholder/incomplete/broken/lazy pending counter가 함께 있어야 한다.
- fallback/external artifact가 `Medium` 또는 `Strong` grade여도 article image loading counters가 없으면 `browser_visual_available`로 세지 않는다. 사람이 본 screenshot은 review note일 수 있지만 strict gate evidence는 아니다.
- fallback evidence가 `Strong`이어도 10만 semantic approval을 닫지 않는다. 이는 해당 post/image row의 visual/loading evidence 공백을 줄이는 post-level 증거다.
- coverage audit의 `gate=GO`는 구조/공개 evidence coverage sanity다. original source가 partial이거나 random/high-risk review가 없으면 최종 gate는 계속 `REVIEW-LOCKED`다.

## 2026-06-01 이미지 OCR anchor taxonomy와 slang context overstatement guard

- `title_in_post=false`이고 `image_ocr_variant=true`인데 final `anchor_type=title_exact`가 남으면 output taxonomy 불일치다. 이미지가 직접 작품 표면을 제공한 경우 `anchor_type=image`로 정렬한다.
- 이 경우 `image_ocr_variant_not_title_in_post` 같은 consistency flag를 남겨, 원문 직접 title 언급과 이미지 OCR 변형 보정을 리뷰에서 분리할 수 있게 한다.
- `slang_insight.cultural_context`는 이미지 OCR/표지 표면을 `특정 웹소설의 일부 인용`, `작품의 설정`, `캐릭터 관계`, `세계관/배경`, `비표준적인 커뮤니티 약칭 또는 OCR 오인`처럼 단정하지 않는다.
- 안전하게 낮출 수 없으면 `slang_insight`를 공개 출력하지 않는 편이 낫다. `store_in_slang_db=false`만으로는 public context overstatement가 사라진 것이 아니다.
- Codex goal에서 이런 잔여를 볼 때는 anchor consistency, slang/context output hygiene, runtime contract를 서로 다른 subagent 축으로 나눠도 된다. 최종 gate 통합은 메인 Codex가 한 번만 한다.
- v460 targeted canary는 이 계약의 positive proof다. 다만 Browser visual/loading evidence와 10만 semantic approval gate는 별도다.

## 2026-06-01 Codex goal subagent 재정렬과 모델 병렬 cap

- 사용자가 "여러 전문가와 병렬"을 말하면 먼저 Codex `spawn_agent` 축을 선언하고 실제 subagent를 띄운다. `expert_main.py --parallel` 값을 늘리는 대응으로 해석하지 않는다.
- 기본 분해 축은 `runtime/orchestration`, `semantic/VLM/browser/comment`, `100k qualitative gate`, `docs/checklist`이며, 필요하면 `slang_db/BatchContext`와 `prompt/hardcode`를 별도 축으로 나눈다.
- Gemma 4 E4B/4B 계열은 `model_parallel_max=36`이다. `requested_parallel_raw`가 36을 넘으면 `requested_parallel=36`으로 cap하고, small input에서는 이후 `effective_parallel`이 입력 수/healthy endpoint 수로 낮아지는 것이 정상이다.
- manifest/run_meta에는 `requested_parallel_raw`, `requested_parallel`, `effective_parallel`, `model_parallel_max`, `model_parallel_cap_applied`, `model_parallel_cap_model`을 함께 남긴다.
- cap 계약 증명이 필요하면 focused canary에서 `--parallel 64`처럼 cap 초과 값을 한 번 넣고, 감사 산출물에서 `requested_parallel_raw > requested_parallel == model_parallel_max`와 `effective_parallel <= input_post_count`를 확인한다.
- `title_in_post`는 원문/댓글에 작품명이 직접 보인다는 뜻으로만 쓴다. 이미지 OCR 변형을 공식 검색으로 보정한 경우에는 `image_ocr_variant`와 `official_search_resolution`으로 분리한다.
- 같은 원칙은 reason score board에도 적용한다. `[근거 요약]`에서 `title_in_post=false`인데 `[근거 스코어]`에서 `title_in_post:+2`를 주면 gate 불일치다.
- 이미지 OCR/표지 표면에 대한 slang/cultural context는 packet-local 근거 위치만 말한다. 이를 일반 한국어 오타 규칙, 지속 alias, 작품 고유 명칭처럼 단정하면 후속 live canary에서 깨끗한 runtime output을 확인하기 전까지 approval evidence로 올리지 않는다.
- `slang_insight.cultural_context`가 `게시글/제목에 사용된`, `공식적인 제목`, `일반적인 오타 또는 축약`, `고유 명칭`처럼 말하면, `store_in_slang_db=false`라도 output hygiene follow-up 대상으로 둔다.
- VLM/OCR ready는 run-level 준비 상태다. 이미지 row approval에는 여전히 image evidence catalog, VLM fetch/chunk status, Codex in-app Browser loading counter 또는 동등한 visual evidence가 필요하다.

## 2026-05-31 Codex goal subagent 병렬 운영

- 이 항목은 Codex 앱의 `spawn_agent` 기반 goal 운영 지침이다. repo 내부 `expert_main.py` 전문가 오케스트레이션 개선 지침이 아니다.
- Codex goal 진행에서 말하는 subagent 병렬화는 `expert_main.py --parallel`이나 내부 LLM 전문가 호출과 별개다.
- `parallel`이라는 단어는 항상 두 계층을 분리해 기록한다. `Codex spawn_agent parallel`은 리뷰/감사/구현 분업이고, `expert_main.py --parallel`은 repo 런타임 worker cap이다.
- goal 보고서에는 `Codex goal orchestration`과 `expert_main runtime`을 별도 항목으로 쓴다. `requested_parallel=36`, `effective_parallel=N`, `spawn_agent axes=[...]`를 한 문장에 섞지 않는다.
- 메인 Codex는 coordinator로 남아 gate/통합/최종 판단을 맡고, subagent는 독립 질문 또는 disjoint write scope만 맡긴다.
- 기본 병렬 역할은 `gate/evidence`, `runtime/shard/process`, `semantic/VLM/comment`처럼 서로 겹치지 않게 나눈다.
- 대형 scan/result review의 기본 분해 축은 `run integrity/manifest`, `runtime/shard/process`, `semantic/VLM/browser/comment`, `slang_db/BatchContext`, `prompt/orchestration/hardcode`, `docs/checklist`다.
- hardcoded alias, VLM/OCR browser evidence, semantic reread, runtime/process snapshot처럼 서로 다른 위험축이 동시에 열려 있으면 Codex subagent를 병렬 spawn하고, 메인 Codex는 중복 구현 대신 결과 통합과 최종 검증을 맡는다.
- 대형 goal에서 서로 독립적인 탐색/감사/구현 축이 2개 이상 열리면, 메인 Codex가 모든 것을 순차 처리하지 말고 Codex `spawn_agent` subagent를 병렬 투입한다. 이는 Codex 운영 분업 규칙이며 `expert_main.py --parallel`, 내부 LLM 전문가 호출 수, shard/worker 수를 늘리라는 뜻이 아니다.
- 읽기 전용 explorer는 파일을 수정하지 않고 증거/공백/다음 action만 보고한다.
- Codex worker-type subagent는 담당 파일 범위를 명시하고, 다른 subagent나 사용자의 변경을 되돌리지 않는다.
- subagent는 읽기 전용 explorer 또는 명시된 disjoint write scope만 맡고, 최종 gate 판단과 문서 통합은 메인 Codex가 수행한다.
- subagent는 최종 승인자가 아니다. subagent의 개별 `GO`나 "문제 없음" 보고는 evidence packet이며, 메인 Codex가 source integrity, semantic coverage, random/high-risk review 상태를 재통합해야 한다.
- subagent 결과는 메인 Codex가 통합하되, runtime `GO`, reason hygiene `GO`, semantic approval `REVIEW-LOCKED`를 섞지 않는다.
- subagent 보고와 최종 검토 문서는 한국어로 작성한다. JSON key, enum, command, path는 원문 표기를 유지할 수 있다.
- 사용자가 "여러 전문가와 병렬"을 다시 지적하면 먼저 Codex `spawn_agent` 분해 축을 선언한다. `expert_main.py --parallel` 값을 늘리거나 같은 small run을 반복하는 것으로 대응하지 않는다.
- targeted follow-up에서는 subagent가 만든 evidence packet을 그대로 gate로 올리지 않는다. 메인 Codex가 source 복원, runtime, semantic label, browser/VLM evidence를 통합해 최종 `GO/REVIEW/NO-GO`를 한 번만 판정한다.
- v422/v425 기준 예시: source 복원, semantic gate, runtime/shard 계약은 subagent로 병렬 검토했고, `--parallel 36`은 runtime max로만 기록했다. targeted rerun `GO`와 manual semantic gate `REVIEW-LOCKED`는 서로 대체하지 않는다.
- 자동 after-review가 `ACCEPT`를 대량 반환해도 coverage audit 또는 수동 리뷰에서 HOLD/REJECT가 남으면 gate를 올리지 않는다. v423 `11/11 ACCEPT`는 v425 수동 라벨 `ACCEPT=8/HOLD=2/REJECT=1` 때문에 approval evidence로 쓰지 않는다.
- semantic hard-deny 회귀를 볼 때는 no-work 보호와 positive alias 회복을 분리한다. v428 기준 `11718098`은 `semantic_seed_review_non_title_terms_removed`가 있어도 `search_query_reviews.keep`와 specific-work positive 신호가 있어 resolved 회복 대상이고, `11718080`류 사회적 한탄/장르 잡담은 계속 no-work 보호 대상이다.
- v429처럼 after-review가 `ACCEPT=9/HOLD=2`로 개선돼도, coverage audit에 `comment_author_match_unverified_used_for_resolution` 또는 `search_only_resolved_title` 계열이 남으면 hard blocker인지 review-only인지 분기해서 보고한다. review-only로 내려간 항목도 packet-level human/quality confirmation 대상이며, 그 자체로 approval evidence가 아니다.
- `search_only_resolved_title`은 원문 직접 title/안정 alias 없이 검색 결과만으로 final title을 세운 경우 hard blocker다. 반대로 `11718075`처럼 title/alias surface와 platform/official evidence가 같은 작품을 지지하고 search-only marker만 남은 경우는 `search_only_resolved_title_review_only`로 낮춰 수동 확인한다.
- `comment_author_match_unverified_used_for_resolution`은 동일 닉네임/익명 댓글 attribution이 final title의 유일한 bridge일 때 hard blocker다. 반대로 `11718097`처럼 comment author unverified가 있어도 별도 title/alias/search support가 final title을 지지하면 `comment_author_match_unverified_resolution_review_only`로 낮춘다.
- 10만 semantic approval은 completed source, expanded random baseline, P0/P1 high-risk expansion, VLM/OCR/browser visual gate가 모두 별도로 충족되기 전까지 `REVIEW-LOCKED`다.
- 댓글 URL이 실제 작품 상세 페이지이고 원문이 장르/추천 요청이면, URL 작품을 원글 final title로 강제하지 않는다. 대신 `recommendation_request` 또는 `adjacent_relevant`와 comment recommendation candidate를 보존해야 한다. 이 경로가 `noise/unrelated`로 떨어지면 `comment_url_recommendation_context_underclassified`로 본다.
- 댓글 공식 URL을 resolved title로 복구하는 것은 명시 제목 질문, 작성자 확인/감사, 직접 답변 관계가 있는 경우로 제한한다. 짧은 제목 길이나 장르 소망 표현만으로는 title-answer로 보지 않는다.
- 검색 결과의 등장인물/캐릭터 페이지 제목은 원문 본문 앵커가 아니다. verifier가 `community_banter/reject`로 본 짧은 캐릭터 반응에서는 character-page rescue가 final title을 되살리면 안 된다.
- `text_surface` 또는 `promotion_eligible=false`인 VLM/OCR 제목은 direct image title rescue와 `anchor_type=image` 승격에서 제외한다. 직접 작품 표면은 `title_role=work_title`, `focus_role=work_anchor`, `promotion_eligible=true` 또는 동등 조건으로 확인한다.
- `semantic_seed_review`가 no-work/context-only를 명시하지 않은 짧은 캐릭터 반응은 무조건 `context_only`로 접지 않는다. 작품 확정은 막되 `unresolved_matchable` 범위 분리 상태를 유지할 수 있다.

## 2026-05-31 hardcoded alias risk audit

- hardcoded alias/abbreviation registry는 semantic approval 근거가 아니라 별도 `REVIEW` 또는 `REVIEW-LOCKED` 근거다.
- `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY`처럼 final title 복구, `High` 승격, guard 예외, prompt pressure에 닿는 positive map은 `tools\audit_hardcoded_alias_risk.py`로 감사한다.
- `STOPLIST`, `NOISE`, `PLATFORM`, `GENERIC_TERM`, `LOW_INFORMATION`, `TROPE`, `BLOCKLIST`, `QUARANTINE` 계열은 quarantine/prompt-hint로 분리해 positive alias blocker와 섞지 않는다.
- action queue를 만들 때 hardcoded alias 감사가 있으면 `build_goal_action_queue.py --hardcoded-alias-audit <path>`로 주입한다.
- v405 refined hardcoded alias audit는 함수 내부 local literal을 `local_runtime_literal/INFO`로 분리하고, `semantic_approval=REVIEW`, positive blocker `3`, quarantine-only registry `10`으로 좁혔다.
- v406 action queue는 refined hardcoded alias audit를 반영해 `hardcoded_alias_gate=REVIEW`, positive blocker `3`, total actions `12`, approval blocker `6`으로 갱신됐다.
- hardcoded alias packet review는 코드 registry 감사와 별도다. `tools\build_hardcoded_alias_packet_review.py`로 실제 result/review packet에서 registry alias/marker가 드러났는지 확인한다.
- v407 packet review는 report self-hit를 제외하고, 검색 snippet에만 스친 alias는 `context-only`로 분리했다. 결과는 scanned files `388`, scanned records `763`, matched packets `11`, packet coverage `FOUND`, gate `REVIEW`다.
- v407에서 실제 packet match는 `KNOWN_TITLE_ABBREVIATIONS`의 `담텔기 -> 괴담 호텔 탈출기` 계열로 좁혀졌다. `KNOWN_ABBREVIATIONS`, `SLANG_DICTIONARY`는 현재 scan 대상에서 direct packet match가 아니라 targeted canary/provenance 보강 대상으로 둔다.
- v408 action queue는 packet review를 통합해 `hardcoded_alias_packet_review_required`를 approval blocker로 추가했다. `total_actions=13`, `ready_now=8`, `blocked_until_completed_source=5`, approval blocker `7`이다.
- v409 packet label review는 v407 matched packet 11건을 정성 라벨링했다. 결과는 `ACCEPT=6`, `HOLD=2`, `REJECT=3`이며, gate는 `REVIEW`다.
- v409에서 `REJECT`인 경우는 author/meta 과차단 1건, noise 과차단 1건, wrong canonical title `한가인(괴담 호텔 탈출기)` 1건이다.
- v410 action queue는 v409 label을 반영해 `hardcoded_alias_packet_label_followup`을 approval blocker로 추가했다. `total_actions=14`, `ready_now=9`, `blocked_until_completed_source=5`, approval blocker `8`이다.
- `NovelIdentity.alias_resolution_sources[]`와 packet `final_decision_fields.alias_resolution_sources`로 `source_registry`, `alias_resolution_source`, `matched_surface_kind`를 노출한다.
- hardcoded alias packet이 의미상 맞아도 registry provenance가 비어 있거나 검색 evidence와 섞여 있으면 approval용 `ACCEPT`로 올리지 않는다.

## 2026-05-31 goal/test expert_main runtime contract refresh

- `expert_main.py --parallel 36`은 worker 고정값이 아니라 최대치다. small input은 `effective_parallel=min(requested_parallel,input_post_count,healthy_endpoint_count)` 계열로 줄어드는 것이 정상이다.
- 단건/소수 post canary에서 `requested_parallel=36`, `effective_parallel=1..N`이면 정상이다. effective worker를 36으로 맞추려고 같은 소규모 테스트를 재실행하지 않는다.
- 이 runtime 병렬도는 Codex `spawn_agent` 병렬 검토와 무관하다. small test runtime evidence가 부족하면 runtime audit를 보강하고, goal 검토 축이 부족하면 Codex subagent를 추가한다.
- 소규모 goal/test run에서 Docker Compose/shard lifecycle은 기본 금지다. shard 복구 자체가 검증 대상일 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 같이 쓴다.
- 현재 확인 기준에서 `--allow-goal-shard-lifecycle` 없이 `--auto-up-shards`/`--auto-recreate-shards`가 붙거나 stale env가 있어도 small goal/test lifecycle은 열리지 않아야 한다.
- semantic regression은 VLM/OCR on 기준이다. 이미지 row가 있는 run에서 `--vlm on --ocr on`이 빠지면 runtime warning/audit로 잡고 semantic approval에는 쓰지 않는다.
- 이미지 row가 있는 semantic/VLM 회귀에서는 `--require-vlm-ocr-for-images` 또는 `LLM_REQUIRE_VLM_OCR_FOR_IMAGES=1`을 사용해 VLM/OCR 누락을 시작 전 exit code 2로 실패시킬 수 있다. text-only guard나 crash isolation처럼 예외 목적일 때만 이 guard를 끈다.
- manifest/Summary의 `vlm_ocr_semantic_review_skip_reasons`는 `no_image_blocks`, `vlm_disabled`, `ocr_disabled` 같은 run-level reason을 남긴다. fetch 실패, geometry skip, unsupported image format은 per-image status/catalog 후속 필드로 분리한다.
- `vlm_enabled=true`, `ocr_enabled=true`, `vlm_ocr_semantic_review_ready=true`는 per-image success가 아니다. 이미지 row approval은 `image_evidence_catalog`, vLLM/OCR response status, browser `article_loaded_count == article_image_count`, placeholder/incomplete/broken 0 또는 동등한 manual visual review까지 확인한다.
- Gemma 4 4B 계열은 운영상 parallel max `36`으로 둔다. 본체는 `requested_parallel_raw`를 보존한 뒤 `requested_parallel`을 모델 cap으로 낮추고, manifest/run_meta에 `model_parallel_max`와 `model_parallel_cap_applied`를 남긴다.

## 2026-05-31 process snapshot and semantic coverage audits

- 소규모 goal/test run을 감사할 때 stale Python/process 공백이 문제이면 `audit_goal_test_run_contract.py --collect-process-snapshot`을 사용한다.
- process snapshot이 권한 문제로 `available=false`여도 runtime contract를 자동 `NO-GO`로 내리지 않는다. 대신 `process_snapshot.error`와 운영 환경 권한 공백을 별도 evidence로 기록한다.
- sandbox 권한 때문에 direct snapshot이 실패하면 외부에서 캡처한 JSON을 `audit_goal_test_run_contract.py --process-snapshot-json <path>`로 주입한다.
- process snapshot 기본 패턴은 `expert_main`, `llm_batch`, `warp_shards`, `vllm`, `uvicorn`이다. `openai`처럼 Codex 앱 자체까지 잡을 수 있는 넓은 패턴은 명시 요청이 있을 때만 추가한다.
- 대형/부분 result의 자연어 검토 준비 상태는 `build_semantic_coverage_audit.py`로 image evidence catalog, browser visual evidence, comment metadata, comment dialogue context, final semantic reread coverage를 분리 집계한다.
- semantic coverage audit의 `GO`는 구조 필드 sanity만 뜻한다. 10만 semantic approval은 completed source, random baseline, high-risk expansion, browser visual gate가 별도로 필요하다.
- 원본 partial source에서 image/comment/final reread coverage가 부족하면 regression seed로만 사용하고 approval source로 쓰지 않는다.
- `context_sources=image` 또는 `anchor_type=image`가 있는데 `image_evidence_catalog`와 VLM fetch/chunk counter가 모두 없으면 `image_context_without_vlm_catalog`로 센다. 이 bucket은 이미지가 판정에 관여했다는 주장과 구조화 VLM/OCR 증거 사이의 공백이다.
- `vlm_chunk_count`, `image_fetch_success`, `vlm.status` 계열 값이 `failed`, `timeout`, `pending`, `skipped`, `unsupported`, `disabled`이면 VLM evidence가 아니라 blocker다.
- `browser_screenshot_path`나 `browser_visual_manifest` 경로만으로 visual available을 인정하지 않는다. lazy/data-original/placeholder/incomplete/broken/pending counter가 있으면 explicit verified flag보다 loading 실패 신호를 우선한다.
- external browser artifact manifest가 `output_path` JSONL을 가리키면 coverage audit는 그 rows를 읽어야 한다. 단, `visual_evidence_grade=Weak|Missing`, `article_image_count=0`, `article_image_gate_passed_rows=0`이면 screenshot path가 있어도 `browser_visual_available`로 세지 않는다.
- fallback browser capture의 `Weak` screenshot은 "브라우저 접근 시도/스크린샷 생성" evidence이지 "본문 이미지 로딩 완료" evidence가 아니다. action queue에서는 계속 `vlm_ocr_browser_visual_gate` blocker로 둔다.
- 댓글 맥락이 resolved 판정에 관여했는데 `comment_metadata`와 `comment_dialogue_context_lines`가 없으면 `comment_context_resolution_without_attribution`으로 센다. 이는 댓글을 독립 작품 evidence로 볼 수 있는지 검토할 공개 attribution이 없는 상태다.
- `author_match_unverified` 또는 `post_author_match_unverified`가 resolved 판정과 함께 보이면 `comment_author_match_unverified_used_for_resolution`으로 세되, final title의 유일/주요 bridge인지와 별도 title/alias/search support가 있는지를 분리한다. 전자이면 hard blocker, 후자이면 `comment_author_match_unverified_resolution_review_only`다.
- `search_only`, `official_search_only_without_post_anchor`, `search_only_title_promotion` 신호가 있는데 resolved title이 남으면 `search_only_resolved_title`로 센다. 원문 직접 title/안정 alias와 official/platform evidence가 없으면 hard blocker이고, 별도 direct title/alias + platform support가 있으면 `search_only_resolved_title_review_only`다.
- `community_banter`, `trope_discussion`, `author_talk`, `recommendation` intent에서 resolved title이 남으면 `blocked_intent_resolved_title`로 센다. 다만 `specific_work + hold/allow + direct anchor`가 함께 있으면 hard blocker가 아니라 `*_review_only`로 분리한다.
- goal action queue를 만들 때는 가능하면 `build_goal_action_queue.py --semantic-coverage-audit <path> --process-snapshot-audit <path>`로 coverage/process 증거를 함께 주입해 approval blocker와 ready action을 분리한다.
- `vlm_ocr_browser_visual_gate`는 image catalog/browser visual/context catalog가 Missing/Weak인 source에서는 P0 approval blocker로 둔다.
- `final_semantic_reread_missing`는 전체 관찰값이고, 실제 요구 조건은 `final_semantic_reread_required/present/missing`으로 판단한다. semantic-risk가 있으면서 최종 resolved title이 살아난 row에 후단 reread가 필요하며, 이미 non-relevant/context-only로 내려간 row를 이 항목만으로 과차단하지 않는다.

## 2026-05-31 goal current-state evidence map

- goal을 이어받을 때는 `tools\build_goal_current_state_map.py`로 원본 source/preflight/runtime audit/reason hygiene를 한 번에 묶어 본다.
- 상태맵의 `original_source_approval`, `small_run_runtime_contract`, `latest_reason_hygiene`, `semantic_approval`을 서로 대체하지 않는다.
- 원본 source가 partial이면 current-state map의 `NO-GO`를 우선하고, 해당 source는 regression seed/targeted triage로만 사용한다.
- `small_run_runtime_contract=GO`는 expert_main 구동 계약 통과일 뿐이며, 10만 semantic approval을 닫지 않는다.

## 2026-05-31 expression reread label colon-payload guard

- 재해독 공개 label은 `표현 오타/축약 패턴(범용)`이며, label 뒤에 `: 표면값` payload를 붙이지 않는다.
- public reason은 `표현 오타/축약 패턴(범용)은 packet-local 원문 재검토 신호`처럼 문장형 경계만 남긴다.
- `tools\scan_reason_hygiene.py`의 `surface_reread_label_colon_payload` hit는 latest canary/approval evidence blocker다.
- 이 guard는 특정 표면어 정상형 복원도, 특정 계열 일반규칙도 아니다.

## 2026-05-31 goal/test run contract audit auto log discovery

- `tools\audit_goal_test_run_contract.py`는 manifest의 `run_id`로 log를 자동 탐색한다.
- 자동 탐색 결과 로그가 없으면 `log_evidence_missing`으로 `runtime_contract=REVIEW`를 남긴다.
- runtime 계약 `GO`를 주장하려면 manifest뿐 아니라 expert run log 또는 자동 발견 log가 같이 있어야 한다.
- v391 산출물: `qualitative_review\20260528_141006_620986\v391_goal_test_run_contract_auto_log_audit.json`, `_ko.md`.

## 2026-05-31 goal/test run contract audit

- 소규모 goal/test run 완료 후 `tools\audit_goal_test_run_contract.py`로 manifest/log 기반 계약 감사를 실행한다.
- 감사는 `requested_parallel`, `effective_parallel`, completed/flushed/pending/failed, Docker/shard lifecycle flags, forbidden log pattern, VLM/OCR ready를 함께 본다.
- `runtime_contract=NO-GO`이면 같은 run을 자연어 리뷰 증거로 승격하지 말고 runtime 설정/로그부터 처리한다.
- `runtime_contract=GO`라도 semantic approval은 별도다. random/high-risk 정성 리뷰와 evidence alignment를 통과해야 한다.
- v390 산출물: `qualitative_review\20260528_141006_620986\v390_goal_test_run_contract_audit.json`, `_ko.md`.

## 2026-05-31 downstream qualitative builder locked-source gate

- approval 목적 자동화에서는 preflight만 `--fail-on-locked`로 실행하고 끝내지 않는다.
- `build_qualitative_random_control_review.py`와 `build_qualitative_round2_review.py`에도 `--preflight <preflight.json> --fail-on-locked-source`를 붙인다.
- preflight가 없거나, preflight의 `source_result_path`가 builder의 `--result`와 다르거나, `gate.overall=REVIEW-LOCKED`이면 downstream builder는 exit code 2로 멈춰야 한다.
- 이 gate가 exit code 2를 반환하면 output dir가 생성되지 않아야 한다.
- locked source에서 random/high-risk artifact를 만들 필요가 있으면 approval artifact가 아니라 regression seed/targeted triage 산출물이라고 별도 표시한다.

## 2026-05-31 preflight fail-on-locked automation gate

- approval 목적 자동화에서 large-scale qualitative preflight를 실행할 때는 `--fail-on-locked`를 사용한다.
- 기본 preflight 종료코드 0은 보고서 생성 성공만 뜻하며, semantic approval 가능을 뜻하지 않는다.
- `--fail-on-locked` 사용 시 `gate.overall=REVIEW-LOCKED`이면 종료코드 2를 기대값으로 본다.
- 종료코드 2가 나오면 random/high-risk expansion을 approval 근거로 진행하지 말고 `required_next_actions`를 먼저 처리한다.
- partial source는 계속 regression seed 또는 targeted triage source로만 둔다.

## 2026-05-31 expression reread generic wording correction

- 재해독 공개 label은 `표현 오타/축약 패턴(범용)`로만 쓴다.
- 특정 표면형의 정상 표현, 특정 계열명, `X -> Y` 복원을 새 reason/prompt/report에 쓰지 않는다.
- `표현 오타/축약 패턴(범용)`은 packet-local 원문 재검토 신호이며, 그 자체로 작품 seed를 낮추거나 올리는 자동 규칙이 아니다.
- 과거 known-bad surface는 historical observation으로만 보관하고 최신 승인 문구나 테스트 기대 문구로 재사용하지 않는다.
- raw reason hygiene에서 old wording drift가 나오면 latest canary나 approval evidence로 쓰지 않는다.

## 2026-05-31 manifest-derived source policy

- preflight source policy는 파일명보다 manifest/checkpoint/result row count 증거를 우선한다.
- final result JSON이라도 manifest가 partial이면 `partial_final_result_json`과 `manifest_partial_run`으로 분류한다.
- `large_run_complete=false`가 확인된 source는 semantic approval source가 아니라 regression seed 또는 targeted triage source로만 쓴다.
- gate에는 다음 필수 액션을 명시해, `REVIEW-LOCKED`가 왜 풀리지 않는지 추적 가능하게 한다.

## 2026-05-31 Korean review artifact language guard

- 리뷰/검토/피드백 목적 Markdown은 heading과 설명 문장을 한국어로 쓴다.
- JSON key, enum, action id, bucket id, 명령어, 코드 심볼은 원문 표기를 유지해도 된다.
- `_ko.md` 산출물이 영어 heading 중심이면 문서 품질 이슈로 보고 도구 출력부터 고친다.
- preflight나 review builder 도구를 수정할 때는 한국어 heading 회귀 테스트를 함께 둔다.
- 이미지/VLM/OCR review 문서도 한국어로 결론을 남긴다. 단, screenshot path, browser manifest path, CSS selector, JSON field, log line은 원문 그대로 보존한다.

## 2026-05-31 non-relevant platform meta scope and suffix drift guard

- 비관련/no-title/no-anchor platform/UI/meta 잡담은 broad novel/platform context가 있어도 `unresolved_matchable`로 남기지 않는다.
- `title_resolution_state=context_only`, `title_resolution_allowed=false`로 두고, reason은 특정 작품 확정 가능성처럼 말하지 않는다.
- `단정하기 어려움할`, `단정하기 어려움하기` 같은 suffix drift는 public-output hygiene blocker다.
- latest canary를 approval evidence로 쓰기 전 `tools\scan_reason_hygiene.py --fail-on-hit`로 bad phrase와 stale template hit가 없는지 확인한다.
- 이미지가 platform catalog/background listing 또는 character visual only이면 VLM/OCR on이어도 title evidence로 승격하지 않는다.
- targeted canary가 통과해도 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 original result is a regression seed, not approval source

- `out\expert_result_20260528_141006_620986.json`는 active goal의 핵심 evidence지만 current approval source가 아니다.
- manifest가 partial이고 modern review fields가 부족하면, raw reason scan이 clean해도 approval source가 될 수 없다.
- v375 기준 원본 result에는 stale relevant template과 `LLM(False)→최종(True)` 계열 문구가 남아 있으므로 public-output hygiene 관점에서도 `NO-GO`다.
- 원본 result의 affected rows는 최신 코드 targeted rerun 후보로 쓰고, 10만 semantic approval은 completed source와 expanded review에서 별도로 판단한다.

## 2026-05-31 reusable reason hygiene raw scan

- public reason hygiene는 `tools\scan_reason_hygiene.py`로 raw text 기준 스캔한다.
- `--min-version`을 사용할 때 v번호가 없는 review/action JSON은 기본 제외한다.
- `*_tool_report.json`은 다음 스캔 대상에서 제외해 리포트 자체에 들어간 pattern/sample이 hit count를 오염시키지 않게 한다.
- 새 review tool을 추가하면 `/tools/*` ignore 정책 아래에서 필요한 파일만 명시적으로 unignore한다.
- 새 latest canary를 approval source로 말하기 전에는 해당 canary 파일이 raw scan clean인지 확인한다.
- 이 스캔은 output hygiene 보조 증거이며, 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 latest canary vs historical repro artifact

- `qualitative_review` 폴더의 과거 result JSON을 전체 approval source처럼 취급하지 않는다.
- 실패를 재현하던 historical artifact는 `HOLD_AS_REPRO_EVIDENCE`로 보관하고, 최신 보정 canary와 분리 보고한다.
- reason hygiene 검사는 JSON parse 결과뿐 아니라 raw text 기준 forbidden pattern scan도 함께 본다.
- 최신 canary가 clean이어도 이는 targeted public-output hygiene 증거이며, 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 ranked/search reason seed-term guard

- `표현 오타/축약 패턴(범용)`는 검색/랭킹 경로를 탔더라도 raw seed 목록으로 되살리지 않는다.
- 장르 조합, 클리셰, 커뮤니티 조어, 작품 앵커 부족처럼 직접 작품 근거가 약한 topic은 public reason에서 `작품 seed 제외:`로 열거하지 않는다.
- 이는 특정 장르어, post id, surface string hardcode가 아니라 public-output hygiene이다.
- 원문 title/body/comment에는 표면어가 남아도 되지만, 판정/해석 문장은 `작품명/별칭 근거가 아니다`와 `직접 작품 앵커 부족` 수준으로만 공개한다.
- targeted canary가 통과해도 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 BatchMem seed preload log mode

- 기본 seed preload 로그는 summary 모드로 둔다.
- `PIPELINE_BATCHMEM_SEED_LOG_MODE=summary`는 총량과 대표 preview만 남기며 targeted run 로그 가독성을 우선한다.
- `PIPELINE_BATCHMEM_SEED_LOG_MODE=full`은 per-alias 등록/보류 로그가 필요한 디버깅에서만 임시 사용한다.
- `PIPELINE_BATCHMEM_SEED_LOG_MODE=off`는 seed preload 요약도 끄는 모드이며, run evidence에는 별도 보완 로그가 필요하다.
- 로그 축약은 런 가독성 개선일 뿐 semantic approval 근거가 아니다.

## 2026-05-31 public reason non-verbatim interpretation guard

- `표현 오타/축약 패턴(범용)` 신호가 있는 공개 reason은 원문에 없는 정규화 값, 숫자/slash/arrow 해석성 괄호, `X -> Y` 치환을 남기지 않는다.
- 이 규칙은 특정 표면어/표면 계열을 차단하는 규칙이 아니라 public-output hygiene이다.
- 원문 title/body/comment/comment_dialogue에는 표면어가 남아도 되지만, 공개 결론/의미 재검토 문장에는 정상형 복원처럼 보이는 값을 새로 만들지 않는다.
- v357 `11718091` 단건 canary처럼 targeted 검증이 통과해도 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 expression reread public-output guard

- 재해독은 `표현 오타/축약 패턴(범용)`라는 packet-local 경계만 공개한다.
- 공개 reason/report에는 표면어 목록, `X -> Y`, `작품 seed 제외: ..., X`처럼 `표현 오타/축약 패턴(범용)` 신호를 다시 규칙화하는 문구를 쓰지 않는다.
- 표면어는 원문 title/body/comment/comment_dialogue 맥락으로만 확인하고, 별도 direct title/alias/evidence가 없으면 작품 seed 근거로 올리지 않는다.
- legacy `paraphrase` 필드가 있어도 sanitizer/prompt 근거로 재사용하지 않는다.
- 이 가드는 출력 계약이며, targeted test 통과만으로 10만 semantic approval을 올리지 않는다.

## 2026-05-31 expression reread generic-pattern guard

- 재해독은 `표현 오타/축약 패턴(범용)`을 보는 단계다.
- 특정 표면어 정상형 복원뿐 아니라, 비슷한 표면 범주를 자동 차단/허용하는 규칙도 만들지 않는다.
- 표면 범주는 예시적 위험 신호이며, 해당 packet 원문과 direct evidence를 다시 읽기 위한 트리거로만 사용한다.
- 공개 reason/prompt/report에는 `X -> Y`식 치환, post id/string hardcode, 자동 차단/허용 규칙을 쓰지 않는다.
- targeted canary가 통과해도 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 expression typo/abbreviation pattern is generic

- 재해독은 `표현 오타/축약 패턴(범용)`을 보는 단계다.
- 공개 label은 `표현 오타/축약 패턴(범용)`로 유지한다.
- `X -> Y`식 정상형 복원, 표면 계열 전용 규칙, 특정 post/string hardcode를 새 prompt/report/reason에 쓰지 않는다.
- 해당 packet의 title/body/comment/comment_dialogue와 direct evidence를 함께 읽은 의미 재검토 없이는 작품 seed를 낮추거나 올렸다고 단정하지 않는다.
- 이 지침이 통과해도 targeted canary일 뿐이며 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 title prefix / exact-title / author surface guard

- 검색 결과 제목이나 커뮤니티 링크 제목의 `스포)`, `질문)`, `소신발언))`, `후기`, `리뷰` 말머리/꼬리는 작품명 후보가 아니다.
- VLM/OCR direct title이 `아카데미의 피해자`인데 검색 결과에 `스포) 아카데미의 피해자 리뷰`가 보이면 final title은 direct title/official URL과 정합되는 `아카데미의 피해자`여야 한다.
- exact-title surface는 title evidence이지 slang alias evidence가 아니다. distinct clean alias가 없으면 `slang_insight`를 공개 출력하지 않고 Slang DB/BatchMem 저장도 하지 않는다.
- VLM/OCR footer나 verifier가 작가명으로 식별한 surface는 author mapping으로만 유지하고 abbreviation alias로 승격하지 않는다.
- 대시보드/보고서에서 `store_in_slang_db=false`인 문장형/합성형 surface는 confirmed alias처럼 말하지 말고 `슬랭 후보(저장 차단)` 또는 `저장 차단 후보`로 표시한다.
- targeted canary가 통과해도 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 generic expression reread wording guard

- 재해독 단계는 `표현 오타/축약 패턴(범용)`로만 보고한다.
- 공개 reason, prompt, review report에는 `X -> Y`식 deterministic paraphrase를 남기지 않는다.
- `surface_paraphrase_notes`는 `source_surface`와 범용 pattern scope만 전달하고, 예전 packet에 `paraphrase`가 있어도 LLM prompt payload에서는 숨긴다.
- 이 가드는 특정 표면어/숫자 패턴을 차단하는 규칙이 아니라, packet-local 자연어 재검토가 전역 규칙으로 오염되는 것을 막는 출력/프롬프트 계약이다.
- targeted canary가 통과해도 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-30 non-relevant semantic seed wording guard

- known-bad raw surface는 `표현 오타/축약 패턴(범용)`의 historical 예시일 뿐이며, 공개 지침에서는 정답 치환 규칙으로 쓰지 않는다.
- 최종이 `discussion_type=noise`, `title_resolution_state=context_only`, `title_resolution_allowed=false`인데 semantic seed review 문구가 "작품 자체에 대한 논의"처럼 과하게 남으면, 공개 reason에서는 일반 잡담/미특정 맥락으로 낮춘다.
- 이 가드는 결론을 새로 확정하는 장치가 아니라, 비관련/title-null 결론의 설명문이 evidence보다 강하게 말하지 않게 하는 reason 품질 가드다.
- 댓글 `author=ㅇㅇ`처럼 author 문자열만 같고 IP/comment_id 계보가 불충분하면 post author 발화로 쓰지 않는다. `comment_author_match_unverified_dialogue`는 계속 `HOLD / human_review` 후보로 본다.
- focused test가 통과해도 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-30 explanatory parentheses are not generic bridges

- `generic_parenthetical_bridge`는 작품명/별칭 후보가 일반어 괄호 설명으로 강화되는 경우를 잡기 위한 bucket이다.
- `본문 내용(이미지 요약)`, `설정(캐릭터 구성, 장르)`처럼 reason 설명문 자체의 괄호는 작품 후보 bridge가 아니므로 이 bucket으로 올리지 않는다.
- generic bridge 판정은 원문/title/resolved_title/evidence 후보의 관계를 봐야 하며, reason prose의 설명용 괄호만으로 `HOLD`를 만들면 안 된다.
- 이 규칙은 `11718099`처럼 `빌환 -> 빌어먹을 환생` alias와 공식 상세 URL이 직접 지지하는 케이스의 review-label 오탐을 줄인다.
- 실제 `오러(판타지 용어)`류 일반어 bridge는 계속 P1 bucket으로 과표집한다.

## 2026-05-30 minor alias counter is not a hard contradiction

- `critical_counter_but_resolved`는 모두 같은 심각도가 아니다.
- `망겜힐 -> 망겜의 힐러`처럼 원문 제목 표면이 약칭이고 final이 정식명인 경우, 공식/플랫폼 검색 evidence가 직접 지지하면 이는 작품 충돌이 아니라 alias normalization이다.
- reason에 `정식명 불일치(minor)`가 남고 동시에 `official_title_evidence=true`, official URL/search snippet, title/body/comment anchor가 있으면 단건 label은 `ACCEPT` 또는 `ACCEPT with follow-up bucket`으로 둘 수 있다.
- 반대로 major counter, 공식 URL 불일치, evidence 없음, reason이 반론을 해소하지 못하는 경우는 true `critical_counter_but_resolved`로 보고 `HOLD` 또는 `REJECT` 후보로 둔다.
- 대형 review builder는 `minor_alias_normalization_counter_resolved_by_official_evidence`와 true critical counter를 분리 집계한다.
- 이 세분화는 review-label 오탐을 줄이는 규칙이며, 10만 건 semantic approval 근거가 아니다.

## 2026-05-30 exact-title is not an alias rule

- `slang_insight.store_reason=exact_title_not_alias` 또는 normalized detected term이 normalized official title과 같은 경우, 운영 `slang_db`뿐 아니라 BatchMem resolved/pending alias에도 등록하지 않는다.
- 정식 제목 자체가 원문에 보이는 것은 title evidence이지 community alias evidence가 아니다.
- clean short alias는 유지한다. 예: `빌환 -> 빌어먹을 환생`, `죽깨수 -> 죽었다 깨어도 수선`.
- v292 `11718117` live run처럼 exact-title surface가 `store_reason=exact_title_not_alias`, flush `titles=0`, BatchMem 즉시등록 log `NOT_FOUND`로 끝나는지 확인한다.
- `term-role` 내부 해석 기록은 남을 수 있으나, 이것을 BatchMem resolved/pending alias 등록이나 운영 `slang_db` 저장과 혼동하지 않는다.
- 이 규칙도 hygiene guard이며, 대형 semantic approval 근거가 아니다.

## 2026-05-30 OCR typo slang subtype rule

- 이미지 OCR/VLM이 작품명을 잘못 읽은 표면은 public evidence에 보존하되, 그 자체를 community alias로 저장하지 않는다.
- 예: `11718082`의 `제벨가 차녀의 2회차 결그룹`은 final title `재벌가 차녀의 2회차 걸그룹`으로 정정됐지만, OCR 오타 표면은 `store_in_slang_db=false`, `store_reason=character_attached_composite`로 차단됐다.
- `재차걸`처럼 검색 snippet이 직접 `약칭은 ...` 근거를 제공한 clean alias는 OCR 오타 표면과 분리해서 본다.
- review packet에서는 `detected_term`, `decoded_term`, `canonical_work_alias`, `store_in_slang_db`, `store_reason`, `image_evidence_catalog.explicit_work_title`을 함께 읽는다.
- 이 subtype review도 단건 hygiene 증거이며, `slang_db_alias_subtype` expanded review 전까지 대형 semantic approval 근거가 아니다.

## 2026-05-30 image platform URL and derivative marker rule

- VLM/OCR이 `작품명 + 작가 + PLATFORM` 형태를 직접 읽고 `promotion_eligible=true`이면 해당 title/author 검증 검색을 image-only pruning에서 제거하지 않는다.
- 이미지 하단 또는 OCR/VLM cue에 `KAKAOPAGE`, `문피아`, `노벨피아`, `네이버시리즈` 같은 플랫폼이 보이면 final title과 같은 작품을 지지하는 해당 플랫폼 official detail URL을 우선 검토한다.
- 단독 `원작` 문자열은 derivative/fanfic marker로 쓰지 않는다. `원작 주인공`, `원작 세계`는 작품 소개문 안의 서사 표현일 수 있다.
- `원작 소설 기반 웹툰`, `원작 웹툰`, `패러디`, `팬픽`, `2차 창작`, `크로스오버`처럼 파생/비소설 매체 문맥이 강한 경우에는 계속 non-novel/derivative evidence로 차단한다.
- targeted canary에서 image platform URL이 회복되어도 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-05-30 meaning pass is a three-layer contract

- 재해독 단계는 `표현 오타/축약 패턴(범용)`로 먼저 다룬다. 단, 이 처리는 특정 문자열 hardcode나 `X -> Y` 치환이 아니라 원문 title/body/comment/comment dialogue 재독해 계약이다.
- 재해독 결과를 특정 계열 일반규칙으로 고정하지 않는다. `표현 오타/축약 패턴(범용)`은 packet-local 자연어 재해독 신호이며, direct title/alias/evidence와 분리해 `HOLD/re_judge/re_search` 여부를 판단한다.
- 1차 Discourse가 문장 일부나 인명처럼 보이는 표면 seed를 올릴 수 있으므로, `discourse_semantic_seed_guard`가 실제 호출됐는지 로그와 result public fields로 확인한다.
- 2차 LLM이 일부 seed를 medium keep으로 둘 수 있으므로, `surface_paraphrase_notes`, `surface_paraphrase_context_terms`, `semantic_seed_review_context_terms`, sanitizer warning이 final scope까지 이어졌는지 본다.
- final은 직접 작품 앵커가 없으면 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`여야 한다.
- 이 gate가 작동해도 targeted canary일 뿐이다. random baseline과 high-risk expansion 전까지 10만 건 semantic approval은 `REVIEW-LOCKED`다.

## 2026-05-30 VLM image byte limit consistency rule

- VLM/OCR on run에서 이미지가 `image_too_large`로 빠지면 먼저 run config의 `LLM_VLM_MAX_IMAGE_BYTES`를 확인한다.
- `expert_main.py` 기본값은 pipeline 기본값보다 더 엄격하면 안 된다. 현재 기본 기준은 `16777216` bytes다.
- 이미지가 VLM으로 들어갔더라도 OCR title/author가 없고 visual scene만 있으면 Strong title evidence가 아니다.
- Browser 확인이 막히면 fallback visual evidence 파일과 `view_image` 확인 결과를 남기되, browser-tooling failure는 별도 follow-up으로 기록한다.

## 2026-05-30 no-anchor vs title-alias evidence rule

- `고유 앵커 부족` 문구가 reason에 있어도 제목 약칭/직접 제목 표면과 공식 상세 URL이 함께 있으면 즉시 REJECT하지 않는다.
- no-anchor 계열은 원문 제목 앵커가 없고 공식 URL/search evidence도 약할 때만 P1 resolved overreach로 본다.
- 표현 오타/축약 패턴(범용)처럼 표면어 자체가 문맥 표현으로 읽히는 경우는 제목 약칭 evidence가 아니며 meaning pass/context-only guard로 처리한다.
- targeted canary에서 리뷰 라벨러 오탐이 줄어도 10만 건 semantic gate는 expanded random/high-risk review 전까지 올리지 않는다.

## 2026-05-30 v269 targeted rerun evidence gate

- 소규모 goal/test 재런에서 `--parallel 36`은 최대치이며 실제 worker는 manifest의 `effective_parallel`로 확인한다.
- endpoint pool은 goal cap으로 8개까지 줄 수 있으므로, `mcp_full_shard_readiness`와 `required_open_for_run`을 분리 보고한다.
- VLM/OCR on run은 manifest의 `vlm_enabled=true`, `ocr_enabled=true`, `vlm_ocr_semantic_review_ready=true`를 확인한다.
- known-bad가 회복되어도 residual P1이 있으면 targeted semantic gate는 `REVIEW`로 남긴다.
- `11718094` 같은 추상 명사 title collision과 `11718117` 같은 OCR explicit title unresolved는 별도 P1 bucket으로 action queue에 올린다.

## 2026-05-30 weak VLM/OCR title browser/evidence gate

- VLM/OCR direct title 후보는 이미지가 있다는 이유만으로 Strong evidence가 아니다.
- image/OCR-only title이 비이미지 원문에 없고 official URL/search snippet으로도 검증되지 않으면 `search_absent_verified_title` 반론을 우선 확인한다.
- 글 제목/본문/댓글의 안정 alias나 official detail URL이 다른 작품을 지지하면 image/OCR title은 `vlm_ocr_title_conflict_with_final_title`로 남긴다.
- 안정 alias/official evidence가 final title을 따로 지지하면 `ocr_title_conflict_with_stable_alias`도 남겨 high-risk bucket에서 과표집한다.
- 이미지 row에서 브라우저 화면 확인이 필요한 경우 Codex 내장 브라우저로 post를 열고, 실제 이미지 로딩 완료 상태와 스크린샷을 review evidence로 남긴다.
- lazy-load 실패, 403, 이미지 미로딩, VLM/OCR 미실행 상태에서 text/search만으로 resolved title을 확정한 row는 `REPROCESS` 또는 `browser_visual_review` action queue로 보낸다.
- targeted canary에서 4건이 회복돼도 10만 건 semantic gate는 expanded random/high-risk review 전까지 올리지 않는다.

## 2026-05-30 social-lament semantic reread rule

- `표현 오타/축약 패턴(범용)`와 마찬가지로, 일반어/커뮤니티 발화가 단일 작품 seed인지 검색 전에 자연어 의도를 다시 읽는다.
- 소설/웹소/TS/갈드컵 같은 일반어와 친구/밥/같이/토론/한탄 신호가 같이 있으면, 단일 작품 seed가 아니라 사회적 한탄/장르 잡담일 수 있다.
- `discourse_semantic_seed_guard`가 이런 장르/커뮤니티 용어를 `context_only/drop`으로 낮추면 `title_novel_terms=[]`, `search_suggestions=[]`인지 확인한다. 이 확인은 seed가 이미 있는 경우에도 적용한다.
- 기억 회수/작품 찾기 신호(`무슨 소설`, `기억 안남`, `대사`, `장면`, `찾...`)가 있으면 같은 친구/장면 단어가 있어도 social-lament로 단정하지 않는다.
- `11718080` 같은 결과는 `is_novel_related=true`와 `official_title=null`이 동시에 맞을 수 있다. 이때 `is_resolved_work_discussion=false`, `title_resolution_allowed=false`가 유지되어야 한다.
- 이 규칙도 targeted canary 품질 보강이며, expanded random/high-risk review 전까지 10만 건 semantic gate를 올리는 근거가 아니다.

## 2026-05-30 comment author/IP dialogue rule

- 댓글 author/ip/comment_id/reply_to는 작품 근거가 아니라 대화 흐름 메타로 취급한다.
- `ㅇㅇ` 같은 익명/공통 author는 author 문자열만으로 같은 사람이라고 보지 않는다.
- post IP와 comment IP가 모두 있고 서로 다르면 `role=post_author`를 부여하지 않는다.
- `post_author_comment_not_independent_evidence` 또는 `comment_author_ip_mismatch_dialogue` 계열은 high-risk review bucket으로 분리한다.
- review packet에는 `post_ip`, `comment_author_ip_mismatch_count`, `post_author_comment_count`, `independent_commenter_count`를 남겨야 한다.
- 이 규칙도 targeted deterministic guard이며, expanded random/high-risk review 전까지 10만 건 semantic gate를 올리는 근거가 아니다.

## 2026-05-30 title-null reason scoreboard rule

- `official_title=null`과 `title_resolution_allowed=false`가 함께 있으면 reason scoreboard의 positive anchor 문구를 별도로 확인한다.
- `plot_mention`, `character_title_link`, `character_mention`, `author_mention`이 있더라도 final title을 확정하지 않은 경우 `강한 앵커`로 표시하지 않는다.
- 비관련 title-null이면 `작품명 확정에는 쓰지 않는 맥락 앵커`, 관련 title-null이면 `정식 제목 미확정`을 reason score에 남겨야 한다.
- scoreboard가 final scope와 충돌하면 semantic 판정 실패로 단정하기 전에 `reason_evidence_alignment` 또는 `review-signal-quality` 이슈로 분리한다.
- targeted patch가 통과해도 10만 건 semantic gate는 expanded random/high-risk review 전까지 올리지 않는다.

## 2026-05-30 context-only no-work-anchor scope rule

- 표현 오타/축약 패턴(범용)가 작품 seed를 문맥 표현으로 낮춘 경우, final reason만 보지 말고 `title_resolution_state`도 확인한다.
- 직접 작품명, 안정 alias, 공식 URL, 강한 캐릭터-작품 연결이 없으면 `unresolved_matchable`이 아니라 `context_only` 또는 명확한 no-work-anchor 상태로 남겨야 한다.
- `context_only`는 "소설 커뮤니티/캐릭터 맥락일 수는 있으나 단일 작품 매칭 근거로는 부족함"을 뜻한다.
- `context_only_no_work_anchor`, `semantic_seed_review_specific_work_denied`, `weak_character_reaction_unresolved_blocked`가 있으면 검색/Decoder 재승격이 일어나지 않았는지 확인한다.
- 이 규칙도 targeted canary 품질 보강이며, expanded random/high-risk review 전까지 10만 건 semantic gate를 올리는 근거가 아니다.

## 2026-05-30 platform branding fetch-title rule

- 공식 플랫폼 URL fetch title이 플랫폼 슬로건/브랜딩이면 작품명으로 쓰지 않는다.
- 플랫폼 브랜딩 title은 URL-title mismatch로도 세지 않는다.
- 같은 URL의 search title/snippet/content가 final title을 직접 지지하면 search evidence를 URL 검증 근거로 유지한다.
- fetched title이 브랜딩이 아닌 다른 작품명일 때만 `official_url_fetch_title_mismatch` 후보로 본다.
- targeted run에서 false mismatch가 제거되어도 대형 리뷰에서는 `platform_branding_fetch_title` bucket을 별도 집계한다.

## 2026-05-30 VLM/OCR conflict structured flag rule

- VLM/OCR direct title 후보가 final official title과 다르면 reason 설명뿐 아니라 `consistency_flags`에도 남겨야 한다.
- 기본 flag는 `vlm_ocr_title_conflict_with_final_title`다.
- final title이 안정 alias, locked official candidate, official detail URL로 별도 뒷받침되면 `ocr_title_conflict_with_stable_alias`를 추가한다.
- 이 flag가 있으면 이미지 OCR 후보는 final title의 Strong evidence가 아니라 conflict/weak visual evidence로 검토한다.
- 표현 오타/축약 패턴(범용)로 seed를 내린 케이스도 공개 reason과 구조 필드가 함께 남는지 확인한다.
- targeted canary에서 flag가 정상 노출되어도, 10만 건 semantic gate는 expanded random/high-risk review 전까지 올리지 않는다.

## 2026-05-30 exact alias rescue URL/evidence sync rule

- `batch_memory_exact_alias_rescued`로 title이 회복된 경우도 late correction으로 취급한다.
- 회복된 title의 `heretic_url`이 비어 있으면 corrected title 기준 official URL recovery를 수행했는지 확인한다.
- final `novel_identity.heretic_url`, `primary_work.heretic_url`, candidate URL, reason의 `official_title_evidence`/`official_urls`가 같은 title 기준인지 확인한다.
- VLM/OCR 표지 title이 final title과 다르면 `ocr_title_conflict_with_stable_alias`로 보고, 공식 URL/안정 alias가 없으면 Strong evidence로 승격하지 않는다.
- 동일 known-bad 묶음 재실행에서 결과가 회복됐더라도, 새 branch가 live에서 직접 필요하지 않았다면 branch 증거는 focused unittest와 분리해 기록한다.

## 2026-05-30 corrected title URL/evidence sync rule

- 후단에서 final title이 바뀌면 `heretic_url`, `official_title_evidence`, `official_urls` reason counter가 final title 기준으로 동기화됐는지 확인한다.
- search result title이 generic한 플랫폼명이어도 snippet/content/description에 final title이 strict match되고 URL이 작품 상세 페이지이면 official URL 후보로 볼 수 있다.
- validator/fetch가 실패한 URL 회복은 `validated=false` 상태를 숨기지 않고 evidence grade를 분리한다.
- `official_urls=0`인데 final `heretic_url`이 작품 상세 URL이면 reason/evidence sync 이슈로 본다.
- 이 규칙은 targeted canary 품질 보강이며, expanded random/high-risk review 전까지 10만 건 semantic gate를 올리는 근거가 아니다.

## 2026-05-29 large rerun VLM/OCR-on gate

- 새 10만 건 completed source 생성 명령에는 `--vlm on --ocr on`을 반드시 명시한다.
- 전체 입력 JSONL 경로와 새 output path가 확정되기 전에는 대형 재런을 시작하지 않는다.
- 기존 partial artifact `out\expert_result_20260528_141006_620986*`는 덮어쓰지 않는다.
- 기본 대형 재런은 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행한다.
- Docker Compose/shard lifecycle 검증이 목적이면 `--allow-goal-shard-lifecycle --auto-up-shards`를 붙이고, semantic 검증과 별도 gate로 보고한다.
- manifest에서 `vlm_enabled=true`, `ocr_enabled=true`, `vlm_ocr_semantic_review_ready=true`가 확인되기 전에는 이미지 row를 approval 근거로 쓰지 않는다.
- v186 readiness 문서: `qualitative_review\20260528_141006_620986\v186_large_rerun_vlm_ocr_on_readiness_ko_20260529.md`.

## 2026-05-29 semantic/VLM test baseline rule

- 자연어 판정 품질 regression은 기본적으로 `--vlm on --ocr on`으로 실행한다.
- VLM 서버가 열려 있으면 goal/test semantic regression 명령에 `--vlm on --ocr on`을 명시한다.
- 이미지 첨부 post가 포함된 run에서 `vlm_enabled=false` 또는 `ocr_enabled=false`이면 그 run은 text-only run이다.
- text-only run은 Docker/worker/runtime health 확인에는 쓸 수 있지만, 이미지 근거가 필요한 semantic quality approval에는 쓰지 않는다.
- manifest에서 `image_post_count>0`이고 `vlm_ocr_semantic_review_ready=false`이면 해당 이미지 row는 `INFO_MISSING`, `REPROCESS`, 또는 browser/VLM 재확인 큐로 보낸다.
- `11718082`처럼 첨부 이미지에 작품명/회차가 보이면 OCR/VLM 또는 Browser visual evidence가 직접 근거가 되어야 한다.
- `11718080`처럼 본문 자체가 “소설 보는 친구와 밥 먹으며 장르/TS/갈드컵 얘기”라는 한탄글이면 검색 결과의 우연한 작품명이나 batch memory alias만으로 resolved title을 확정하지 않는다.

## 2026-05-29 env-only Docker lifecycle block rule

- `MCP_AUTO_UP_SHARDS=1` 또는 `MCP_AUTO_RECREATE_SHARDS=1` 환경변수만으로 Docker Compose lifecycle을 열지 않는다.
- env 기반 lifecycle을 허용하려면 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` 또는 legacy `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1` ack가 필요하다.
- Codex 또는 36건 이하 small goal/test run에서는 env ack가 있어도 현재 명령에 `--allow-goal-shard-lifecycle`이 없으면 lifecycle을 열지 않는다.
- shard lifecycle 자체가 검증 대상일 때만 현재 명령에 `--allow-goal-shard-lifecycle --auto-up-shards` 또는 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 함께 붙인다.
- manifest에서 `mcp_env_shard_lifecycle_requested`, `mcp_env_shard_lifecycle_global_opt_in`, `mcp_env_shard_lifecycle_allowed`, `mcp_auto_up_shards`, `mcp_auto_recreate_shards`, `mcp_local_shard_management_enabled`를 같이 확인한다.
- lifecycle이 꺼졌는데 단건이 느리면 Docker 문제가 아니라 검색 retry, decoder/verifier prompt, expert iteration 병목으로 분리 보고한다.

## 2026-05-29 settled null-title fast-path rule

- Verifier critical veto, 음수 evidence, deliberate null-title, direct title proof 부재가 동시에 있으면 Jury/Debate를 여는 대신 settled veto fast-path로 종료할 수 있다.
- 이 fast-path는 post id나 특정 제목 문자열로 열면 안 된다. 공개 decision field, evidence score, verifier counter, anchor 상태만으로 판단한다.
- direct title proof가 본문/댓글에 있거나 positive evidence가 강하면 fast-path로 심의를 스킵하지 않는다.
- `11718083` 같은 기억 회수/소설 찾기 글은 `is_novel_related=true`일 수 있지만, 단일 작품 매칭은 `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`로 남길 수 있다.
- goal/test run에서 Compose lifecycle 미진입이 확인되어도 단건 elapsed/token/search retry가 과하면 별도 performance gate로 본다.
- v169 기준 Compose 문제는 `GO`지만 settled memory-query 성능은 `REVIEW`다.

## 2026-05-29 goal/test and partial flush artifact rule

- goal/targeted 테스트런에서 Docker Compose lifecycle은 hard opt-in이 없으면 열지 않는다.
- shard 복구 자동화 자체가 검증 대상일 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 사용한다.
- 소규모 판단 회귀의 새 명령은 `--parallel min(input_count,36)`를 권장한다. 과거/기존 run에 `--parallel 36`이 남아 있어도 manifest의 `effective_parallel`이 입력 수 또는 healthy endpoint 수로 낮아졌고 lifecycle/evidence 계약이 맞으면 재실행하지 않는다.
- 병렬 run에서 `partial_flush_gap=true` 또는 `ordered_flush_blocked=true`이면 final result JSON만 보지 않는다.
- `_completed_subset.json`은 recovery/triage artifact이고, primary result JSON은 ordered flushed prefix다.
- `_completed_subset_manifest.json`의 `flushed_count`, `pending_count`, `next_save_idx`, `pending_rows`를 확인한다.
- `large_run_complete=false`이면 completed subset이 있어도 전체 run completion과 semantic approval은 금지한다.

## 2026-05-29 partial run review rule

- manifest의 `input_post_count`를 완료 건수로 해석하지 않는다. `completed_count`, `flushed_count`, final result row count, checkpoint completed row count, pending snapshot row count를 분리 확인한다.
- checkpoint completed row가 final result JSON보다 많으면 semantic quality review 전에 run flush/pending integrity 이슈로 기록한다.
- final result에 없는 checkpoint completed row가 pending snapshot과 정확히 일치하면 `recoverable_pending_flush_gap`으로 분류할 수 있다. 이 경우 원본 result를 덮어쓰지 말고 checkpoint completed subset을 별도 recovered artifact로 생성한다.
- `pending_count>0`, `flushed_count<completed_count`, clean completion summary 부재 중 하나라도 있으면 large run completion은 미입증으로 둔다.
- qualitative review builder는 source가 final result JSON인지, checkpoint recovered completed subset인지, checkpoint/pending 설명을 포함한 partial subset인지 `source_review_policy`로 manifest와 gate에 남겨야 한다.
- random control builder가 canonical `review_labels.jsonl`을 갱신하면 `summary.json`, `sample_manifest.json`, `gate_decision.md`, `action_queue.md`도 같은 run id/seed 기준으로 재계산한다.
- large-scale qualitative expansion 전에는 preflight로 source completeness와 sampling feasibility를 확인한다. preflight가 `REVIEW-LOCKED`이면 후속 expansion 산출물은 approval 근거가 아니라 부족 증거다.
- partial run 산출물은 known-bad triage와 failure pattern discovery에는 사용할 수 있지만, 10만 건 semantic approval 근거로 사용하지 않는다.
- 댓글이 있는 row에서 `comment_metadata` 또는 `comment_context_lines`가 없으면 자연어 판단 품질 review에서 author/speaker context missing bucket으로 분리한다.
- review packet builder는 `gallery_id`, `post_author`, `comment_metadata`, `comment_context_lines`, `comment_dialogue_context_lines`, `comment_context_source`를 packet에 직접 남긴다. `comment_context_lines`는 가능한 경우 `speaker`, `author`, `role=post_author`, `ip`, `reply_level`, `reply_to`, `comment_id`를 포함해야 한다. `comment_dialogue_context_lines`는 같은 #번호에 댓글 text excerpt를 붙여 대화 흐름을 읽게 하되, speaker/author/ip 자체를 작품 identity evidence로 세지 않는다. `comment_context_lines`가 없고 `comment_metadata`가 있으면 metadata에서 재구성하고, 둘 다 없으면 `INFO_MISSING/human_review`로 승인 제외한다.
- 댓글 작성자 닉네임/IP/comment id는 대화 흐름 해석용 메타이며, 댓글 원문이 직접 작품 앵커를 제공하지 않으면 independent identity evidence로 세지 않는다.
- review artifact builder는 source result의 run id를 파일명, manifest, 또는 명시 `--run-id`에서 가져와야 한다. 다른 run id 상수를 재사용하면 evidence path 오염으로 본다.
- bucket selection은 primary selected count와 risk-tag covered count를 분리 보고한다. dedupe 때문에 rare bucket primary count가 0으로 보일 수 있으므로 covered count를 함께 확인한다.

## 2026-05-29 goal/test run shard management rule v2

- 일반 goal/targeted 회귀 실행은 Docker Compose lifecycle뿐 아니라 `warp_shards.py status/ensure` 기반 local shard management도 기본 생략한다.
- 기본 실행은 MCP endpoint health check만 수행한다. 실패 endpoint가 있어도 자동 stop/start/recreate로 문제를 가리지 않는다.
- 36건 이하 goal/test regression은 Codex 여부와 무관하게 `--auto-up-shards`/`--auto-recreate-shards`만으로 lifecycle을 열지 않는다.
- 36건 이하에서 shard 복구 검증까지 해야 할 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 붙인다.
- Codex goal/test run에서는 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1` 같은 env escape도 현재 명령의 `--allow-goal-shard-lifecycle` 없이는 무시한다.
- 대형/운영 검증에서 shard 자동 기동 검증은 `--auto-up-shards`를 명시한다. env 기반 자동화는 `MCP_AUTO_UP_SHARDS=1`과 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 둔다.
- 대형/운영 검증에서 shard 자동 재생성 검증은 `--auto-recreate-shards`를 명시한다. env 기반 자동화는 `MCP_AUTO_RECREATE_SHARDS=1`과 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 둔다.
- compose lifecycle 없이 status 감사만 필요하면 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`을 명시한다.
- 36건 이하 goal/test regression은 `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD=36` 기본값 기준으로 stale `MCP_AUTO_*` env를 무시하고 up/recreate를 차단한다.
- `MCP_SMALL_RUN_SHARD_THRESHOLD`는 endpoint 자동 생성 제한 기준이며, compose lifecycle 차단 기준이 아니다.
- run manifest에서 `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit=false`면 기본 goal/test 경로가 local shard management를 건드리지 않은 것이다.
- run manifest에서 `mcp_shard_lifecycle_block_threshold=36`, `mcp_run_post_count_for_lifecycle<=36`, `mcp_small_run_shard_lifecycle_blocked=true`이면 goal/test lifecycle 차단이 적용된 것이다.
- compose 재시작을 절대 피해야 하는 단건/소량 run은 기본값으로 충분하지만, 운영 실수를 줄이려면 `--reuse-shards-only`도 붙인다.

## 2026-05-29 goal/test run shard lifecycle rule

- 일반 goal/targeted/canary/validation 실행은 기본적으로 기존 shard를 재사용하고, `docker compose up` 또는 shard `force-recreate`를 자동 실행하지 않는다.
- 36건 이하에서는 shard 자동 기동까지 검증할 때 `--allow-goal-shard-lifecycle --auto-up-shards`를 함께 명시한다.
- 36건 이하에서는 실패 shard 자동 재생성까지 검증할 때 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 함께 명시한다.
- compose 재시작을 절대 피해야 하는 goal 테스트런은 기본값으로 충분하지만, 운영 실수를 줄이려면 `--reuse-shards-only`를 추가한다.
- run manifest에서 `mcp_shard_lifecycle_policy=docker_up_recreate_opt_in+missing_shard_scale_up_default_on`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`를 확인한다. (라벨 뒤쪽은 대형 autogen 런 한정 missing shard 증분 기동이 기본 ON임을 뜻한다 — 소규모 goal/test 런에서는 `mcp_missing_shard_scale_up_allowed=false`여야 한다.)
- v141 run id `20260529_020958_837665`에서 위 manifest 값(당시 라벨 `docker_up_recreate_opt_in`)과 `docker compose`/`force-recreate` 미실행을 확인했다.

## 2026-05-28 현재 판정 - v131 post-Arbiter title lock propagation

- 판정: `REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v131_post_arbiter_lock_action_queue_ko_20260528.md`
- 최신 gate 메모:
  - v131은 run health 정상(`completed=2`, `failed=0`, `pending=0`)이며 manifest 기준 `requested_parallel=36`, `effective_parallel=2`다.
  - v131 after-review는 `ACCEPT=2`, `HOLD=0`, `REPROCESS=0`, `REJECT=0`, `INFO_MISSING=0`이다.
  - `11718097`은 `망겜의 힐러`로 회복됐고, `11718118`은 `trope_discussion/null title`로 유지됐다.
  - v130의 author conflict guard 과삭제는 회귀 seed로 남긴다.
- 운영 규칙:
  - final 성공과 중간 guard 충돌은 분리 보고한다.
  - snippet/alias lock, filtered official weak support, title abbreviation stability가 있으면 후단 title 삭제 guard가 더 강한 반대 evidence를 요구해야 한다.
  - targeted canary 통과만으로 10만 건 semantic approval을 올리지 않는다.
  - expanded random baseline과 P0/P1 high-risk review 전까지 semantic approval은 금지한다.

## 2026-05-28 현재 판정 - v124 title lead alias recall

- 판정: `REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v124_title_lead_alias_recall_action_queue_ko_20260528.md`
- 최신 gate 메모:
  - v124는 run health 정상(`completed=4`, `failed=0`, `pending=0`)이며 manifest 기준 `requested_parallel=36`, `effective_parallel=4`다.
  - v124 after-review는 `ACCEPT=4`, `HOLD=0`, `REPROCESS=0`, `REJECT=0`, `INFO_MISSING=0`이다.
  - `11718097` correct title recall은 `망겜힐은 -> 망겜힐` title-leading alias anchor 보존으로 회복됐다.
  - v122의 역할·호칭성 wrong-title rescue는 재발하지 않았다.
- 운영 규칙:
  - topic-particle title lead alias는 검색 앵커로는 보존하되 final title 확정과 분리한다.
  - 검색 degraded나 official evidence 약함이 있으면 evidence strength를 `Medium` 이하로 남기고 high-risk expansion에서 감시한다.
  - targeted canary 통과만으로 10만 건 semantic approval을 올리지 않는다.
  - expanded random baseline과 P0/P1 high-risk review 전까지 semantic approval은 금지한다.

## 2026-05-28 현재 판정 - v123 role/honorific alias rescue guard

- 판정: `REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260528_141006_620986/v122_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v122_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v123_role_honorific_alias_rescue_action_queue_ko_20260528.md`
- 최신 gate 메모:
  - v122는 run health는 정상(`completed=4`, `failed=0`, `pending=0`)이었지만, 정성 라벨은 `REPROCESS=2`, `REJECT=1`, `ACCEPT=1`이라 승인 근거가 아니었다.
  - v122 `11718083`, `11718091`은 `_context_to_output()`의 `post_data` NameError로 재처리 대상이다.
  - v122 `11718097`은 `족장님` 같은 역할·호칭성 표현이 검색 추론 alias로 과승격되어 wrong title이 final에 들어간 구조 이슈다.
  - v123은 같은 4건에서 `ACCEPT=3`, `HOLD=1`, `REPROCESS=0`, `REJECT=0`으로 처리 오류와 wrong-title final 삽입이 재발하지 않았다.
  - `11718097` correct title recall은 아직 `HOLD/re_search`이며, canonical suspect 후보 노이즈는 high-risk bucket에서 계속 감시한다.
- 운영 규칙:
  - 역할·호칭성 alias는 직접 title/안정 별칭/캐릭터-작품/evidence edge 없이 단독 title rescue 근거로 쓰지 않는다.
  - targeted canary 통과만으로 10만 건 semantic approval을 올리지 않는다.
  - expanded random baseline과 P0/P1 high-risk review 전까지 semantic approval은 금지한다.

## 2026-05-28 현재 판정 - v115/v116 alias common-word guard

- 판정: `REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_review_summary_ko_20260528.md`
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_action_queue_ko_20260528.md`
  - `qualitative_review/20260505_214349_324347/v115_alias_commonword_guard_p36max_20260528_manifest.json`
  - `qualitative_review/20260505_214349_324347/v116_post11365197_alias_commonword_guard_p36max_20260528_manifest.json`
- 최신 gate 메모:
  - 100% 작품 매칭은 목표가 아니다. 목표는 잘못된 확정 판정을 줄이고 애매한 케이스를 `HOLD`/`REPROCESS`로 남기는 것이다.
  - v115에서 일반어 alias 오염 중 `애들 -> 잘못된 권유`는 제거됐지만 `성이 -> 실패 없는 웹소설 작법서 by 윤재 저`가 새로 확인됐다.
  - v116 단건에서 해당 오염은 제거됐고 `전1시 -> 전지적 1인칭 시점`으로 복구됐다.
  - v115/v116 모두 `--parallel 36`으로 호출했지만 manifest에서 각각 `effective_parallel=7`, `effective_parallel=1`로 축소됐다.
  - 이번 결과는 targeted regression evidence이며 10만 건 전체 승인 근거가 아니다.
- 운영 규칙:
  - 새 특정 작품명/URL 하드코딩으로 해결하지 않는다.
  - 검색 alias inference는 일반어, 조사 붙은 문법 조각, 문서/가이드형 검색 결과를 작품 후보로 승격하지 않는다.
  - shell exit와 manifest가 충돌하면 manifest/checkpoint/result/log를 분리 확인하고, 불일치 원인을 별도 action queue로 남긴다.
  - expanded random baseline과 P0/P1 high-risk review 전까지 semantic approval은 금지한다.

## 2026-05-27 현재 판정 - v109 v105 REJECT closure after-review

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v109_v105_reject_closure_after_review_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v109_v105_reject_closure_after_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_rejudge_targeted_p7_20260527.json`
  - `qualitative_review/20260505_214349_324347/v109_v108_11365197_neighbor_guard_p1_20260527.json`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_alias_recall_patch_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_rejudge_targeted_manifest.json`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_rejudge_targeted_input.jsonl`
- 최신 gate 메모:
  - v105 `REJECT/re_judge` 7건은 v108/v109 after-review 기준 `REJECT=0`으로 닫혔다.
  - v108 7건은 `--parallel 7`, v109 단건 guard는 `--parallel 1`로 실행했고 각 manifest에서 `effective_parallel=input_post_count`를 확인했다.
  - after-review는 `ACCEPT=4`, `HOLD=3`, `REPROCESS=0`, `REJECT=0`, `INFO_MISSING=0`이다.
  - `탑매`, `괴담텔`, `괴출` HOLD 3건과 기존 10만 건 remaining queue가 남아 semantic approval은 금지한다.

## 2026-05-27 현재 판정 - v105 targeted rerun

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v105_targeted_after_review_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v105_targeted_after_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v106_adaptive_parallel_policy_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v107_effective_parallel_runtime_guard_ko_20260527.md`
- 최신 gate 메모:
  - v98 7건과 v102 25건 실서버 run은 completed/failed/pending `32/0/0`으로 완료됐다.
  - after-review는 `ACCEPT=16`, `HOLD=9`, `REJECT=7`이다.
  - v105 `REJECT=7`은 후속 v108/v109 closure에서 `REJECT=0`으로 내려갔지만 `HOLD=3`이 남았다.
  - 이후 36건 미만 targeted run은 `--parallel 36`을 상한으로 두고 manifest의 `effective_parallel=input_post_count`를 확인한다.
  - `expert_main.py`는 이제 `--parallel`을 상한으로 처리하고 manifest/run_meta에 요청 병렬도와 실제 병렬도를 분리 기록한다.
  - 남은 `HOLD`와 기존 10만 건 remaining queue closure 전까지 semantic approval은 금지한다.

## 2026-05-27 현재 판정 - v104 runtime preflight

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v104_runtime_preflight_and_local_regression_ko_20260527.md`
  - `out/search_shard_audit_20260527_185927.json`
- 최신 gate 메모:
  - v104 당시 LLM endpoint `http://127.0.0.1:8000/v1/models`는 연결 실패였고, 후속 확인에서 실제 endpoint는 `http://10.20.0.101:8000`으로 정정했다.
  - v98/v102 실서버 재실행과 after-review는 후속 v105/v108/v109에서 완료했다.
  - search shard audit는 `ok=36/36`이다.
  - 로컬 회귀는 `74 tests OK`, `239 tests OK`로 통과했다.
  - 후속 재실행 후에도 `HOLD`와 기존 remaining queue가 남아 semantic approval은 금지한다.

## 2026-05-27 현재 판정 - v102 clean alias preservation contract

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v102_clean_alias_preservation_contract_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v102_clean_alias_preservation_targeted_manifest.json`
  - `qualitative_review/20260505_214349_324347/v103_current_100k_remaining_gap_bug_resolution_plan_ko_20260527.md`
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/prompts/prompt_router.py`
  - `src/llm_batch/prompts/expert_prompts.py`
  - `tests/test_agentic_pipeline_alias_contract.py`
- 최신 gate 메모:
  - noisy/composite surface 저장 차단과 clean short alias 보존을 분리했다.
  - `탑매/탑 매니지먼트`, `탑매`, `환암검천 후기` 계약 회귀를 테스트로 고정했다.
  - v102 targeted input `25`건을 생성했고 `missing_count=0`을 확인했다.
  - v98 7건과 v102 25건 실서버 재실행 및 후속 after-review는 v105/v108/v109에서 완료했다.
  - 후속 closure 기준 `HOLD=3`과 post-fix high-risk regression이 남아 semantic approval은 금지한다.

## 2026-05-27 현재 판정 - v101 blocked contract spot review

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v101_blocked_contract_spot_review_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v101_blocked_contract_spot_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v101_blocked_contract_spot_review_action_queue.md`
- 최신 gate 메모:
  - `blocked_by_result_contract=79` 중 25건 spot review 결과는 `ACCEPT=6`, `HOLD=5`, `REJECT=14`다.
  - `sentence_like_alias_surface`는 문장형 term과 정상 약칭 후보가 섞여 있어 term 단위 분리가 필요하다.
  - `pure_work_alias`가 저장 차단에 남는 경우 alias recall false negative로 이어질 수 있다.
  - spot review는 전체 승인 근거가 아니며, prompt/router 또는 후처리 보강과 회귀 전까지 `slang_db_review=87`은 닫지 않는다.

## 2026-05-27 현재 판정 - v100 slang DB small-state manual review

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v100_slang_db_small_state_manual_review_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v100_slang_db_small_state_manual_review_labels.jsonl`
- 최신 gate 메모:
  - v99 소량 상태 8건은 `ACCEPT=4`, `HOLD=2`, `REJECT=2`로 분류됐다.
  - `프리렌`, `시달소`는 외부 매체 seed로 quarantine 후보.
  - `검머외`, `말하는검`은 재판정/canonical title 검토 후보.
  - 이 리뷰는 DB 반영 또는 전체 semantic approval이 아니므로 gate는 유지한다.

## 2026-05-27 현재 판정 - v99 current slang DB status queue

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v99_current_slang_db_status_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/v99_current_slang_db_status_review_action_queue.md`
  - `tools/build_slang_db_status_review.py`
- 최신 gate 메모:
  - `slang_db_review=87`은 최신 current 기준 `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`다.
  - v99는 상태별 큐를 만든 것이며 승인 완료가 아니다.
  - `persisted_as_slang`, `persisted_conflict`, `persisted_pending` 소량 큐를 우선 자연어 리뷰로 닫는다.
  - `blocked_by_result_contract=79`는 전체 수동 판독보다 차단 사유와 alias recall 영향 표본 점검을 우선한다.

## 2026-05-27 현재 판정 - v98 targeted rerun input

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v98_non_novel_slang_seed_quarantine_targeted_manifest.json`
  - `qualitative_review/20260505_214349_324347/v98_non_novel_slang_seed_quarantine_targeted_input.jsonl`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/v98_11097334_current_image_loading_probe_20260527.json`
- 최신 gate 메모:
  - v98은 v97 seed quarantine 실서버 검증용 입력 준비 단계다.
  - negative control `3`건과 positive alias control `4`건을 포함했다.
  - 현재 `127.0.0.1:8000` LLM endpoint는 연결 실패이고 관련 Python 점유 프로세스는 없다.
  - `11097334`에서 placeholder 이미지가 `complete=true`, `naturalWidth>0`으로 관측되는 함정을 현재 iab 브라우저로 재확인했다.
  - 입력 준비와 image loading probe만으로 semantic approval을 내지 않는다.

## 2026-05-27 현재 판정 - v97 non-novel slang seed quarantine

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v97_non_novel_slang_seed_quarantine_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v86_slang_db_status_review_after_conflict_detection_packets.jsonl`
- 최신 gate 메모:
  - `프리렌 -> 장송의 프리렌`, `시달소 -> 시간을 달리는 소녀` known-bad seed가 batch memory resolved alias로 되살아나지 않도록 차단했다.
  - `tests.test_batch_context` 9건과 `tests.test_agentic_pipeline_rework tests.test_batch_context` 248건은 통과했다.
  - v105에서 실서버 재실행은 완료됐지만, 소규모 targeted run에 36 worker를 고정 기동하는 것은 비효율로 정정했다. 후속 36건 미만 재확인은 `--parallel`을 상한으로 두고 `effective_parallel`을 확인한다.
  - 이 항목은 재발 방지 보강이며 `slang_db_review=87`, `human_review=122`, `INFO_MISSING=1`을 닫은 것이 아니다.

## 2026-05-27 현재 판정 - v96 VLM/OCR attachment popup evidence

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v96_info_missing_attachment_popup_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v96_info_missing_attachment_popup_after_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/v96_info_missing_attachment_popup_browser_reviews.jsonl`
- 최신 gate 메모:
  - `post_id=10794867`은 본문 인라인 이미지 `0`개였지만 `원본 첨부파일 1`과 `viewimagePop.php` 첨부 이미지 링크가 확인됐다.
  - 첨부 팝업 이미지는 `550x350`으로 로드됐지만 갤러리 소개 이미지라 작품 판정을 직접 지지하지 않아 `INFO_MISSING -> HOLD/human_review`로 전환했다.
  - `post_id=10892069`은 삭제/리다이렉트 상태라 `INFO_MISSING/human_review` 유지.
  - latest closure는 `ACCEPT=375`, `HOLD=208`, `INFO_MISSING=1`, approval excluded `209`, browser image gate `pass=99`, `fail=1`이다.
  - `human_review=122`, `slang_db_review=87`, `INFO_MISSING=1`이 남아 semantic approval은 아직 금지한다.

## 2026-05-27 현재 판정 - v78 current remaining action package

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_manifest.json`
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_summary_ko.md`
  - `tools/build_current_remaining_action_inputs.py`
- 최신 gate 메모:
  - latest remaining `392`건 전체가 action별 입력/리뷰 패킷으로 나뉘었다.
  - rerun combined `226`건은 endpoint 복구 후 Gemma 4 4B, 36워커로 실행한다.
  - browser target `28`건은 Codex in-app browser 또는 동등한 시각 검증으로 이미지 loading gate와 semantic evidence를 분리 확인한다.
  - human/slang DB review packet은 자동 런 성공과 분리해서 닫는다.
  - 패키징 완료와 semantic approval을 혼동하지 않는다.

## 2026-05-27 현재 판정 - v77 after-review readiness

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v76_after_review_readiness_fix_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_preflight_original_after_manifest.json`
  - `tools/build_qualitative_round3_after_review.py`
- 최신 gate 메모:
  - v75 P0 input의 target lineage가 보강됐다.
  - preflight original subset에서 after-review packet/label 생성은 성공했다.
  - preflight는 원본 결과 기반이므로 semantic quality gate 완화 근거가 아니다.
  - 실제 post-fix 36워커 재실행 결과를 기다린다.

## 2026-05-27 현재 판정 - v76 P0 remaining targeted input

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input_manifest.json`: P0 잔여 targeted input manifest
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input_summary_ko.md`: 한국어 요약
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input.jsonl`: 36워커 재실행 대상
- 최신 gate 메모:
  - `generic_common_surface=80`, `weak_evidence_strong_resolution=16` 전체를 `96`건 입력으로 준비했다.
  - endpoint 복구 후 Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `--no-auto-up-shards`로 실행하되, 실제 워커 수는 `effective_parallel=min(requested_parallel,input_count)`로 확인한다.
  - 현재 LLM endpoint가 connection refused라 실행 결과/after-review는 아직 없다.
  - 입력 준비만으로 semantic quality를 승인하지 않는다.

## 2026-05-27 현재 판정 - v75 supplemental after-review closure merge

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/supplemental_after_review_closure_merge_ko_20260527.md`: 병합 누락/수치 갱신 정리
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`: latest closure
  - `qualitative_review/20260505_214349_324347/current_100k_fixable_gap_bug_summary_ko_20260527.md`: 10만 건 부족점/버그/해결 가능 항목 요약
- 최신 gate 메모:
  - v68/v71/v73 supplemental after-review 결과 `19`건을 latest closure에 반영했다.
  - 최신 closure는 `ACCEPT=192`, `HOLD=297`, `REPROCESS=93`, `INFO_MISSING=2`, approval excluded `392/584`.
  - 남은 action queue는 `human_review=79`, `re_search=127`, `re_judge=72`, `slang_db_review=87`, `re_run=27`.
  - LLM endpoint `http://127.0.0.1:8000/v1/models`는 현재 connection refused라 추가 36워커 실행 전에 복구/포트 확인이 필요하다.
  - 자동 감사/closure 병합 성공과 10만 건 semantic `GO`는 분리한다.

## 2026-05-27 현재 판정 - v74 weak evidence closure guard

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/weak_evidence_closure_guard_fix_ko_20260527.md`: 원인/수정/검증 정리
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`: 최신 closure
  - `tests.test_exit_action_closure`: 6 tests OK
- 최신 gate 메모:
  - 비관련/title-null로 안전하게 내려간 row는 `weak_evidence_strong_resolution` guard로 다시 `HOLD` 처리하지 않는다.
  - 최신 closure는 `ACCEPT=183`, `HOLD=306`, `REPROCESS=93`, `INFO_MISSING=2`, approval excluded `401/584`.
  - `weak_evidence_strong_resolution` 잔여는 `16`으로 감소했다.
  - 남은 high-risk queue 때문에 10만 건 semantic `GO` 근거로 쓰지 않는다.

## 2026-05-27 현재 판정 - v73 review labeler direct evidence/degraded routing

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v73_review_labeler_direct_evidence_11113480_after_packet_review_summary.md`: v72 단건 after-review `HOLD=1`, action `re_search=1`
  - `qualitative_review/20260505_214349_324347/v73_review_labeler_direct_evidence_generic_hold19_after_packet_review_summary.md`: v67 19건 after-review `ACCEPT=7`, `HOLD=12`, actions `no_action=7`, `re_search=7`, `re_judge=5`
  - `qualitative_review/20260505_214349_324347/review_labeler_direct_evidence_degraded_routing_ko_20260527.md`: 원인/수정/검증 정리
- gate 메모:
  - `degraded_queries: 0` 필드명만으로 search degraded를 true로 보지 않는다.
  - 직접 작품 근거가 있는 generic bucket은 degraded 여부에 따라 `ACCEPT/no_action` 또는 `HOLD/re_search`로 분리한다.
  - action queue를 정확히 나눈 것이며, 라벨 count를 올려 10만 건 semantic `GO`를 선언하는 근거로 쓰지 않는다.

## 2026-05-27 현재 판정 - v72 BatchContextMemory alias promotion guard

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v72_batchmem_generic_inline_alias_11113480_p36_20260527.json`: targeted 1건 completed `1`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v72_batchmem_generic_inline_alias_11113480_p36_20260527_manifest.json`: completed `1`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v72_batchmem_generic_inline_alias_11113480_after_packet_review_summary.md`: after-review `HOLD=1`, `HOLD->HOLD`
  - `qualitative_review/20260505_214349_324347/batchmem_generic_inline_alias_seed_guard_ko_20260527.md`: 원인/수정/검증 정리
- gate 메모:
  - `generic_inline_alias` 또는 저근거 seed가 pending count 2만으로 `BatchMem` resolved memory에 승격되지 않는지 확인한다.
  - 승격 차단 로그는 `약칭 승격 보류 ... reason=generic_inline_alias|low_evidence_seed`로 남긴다.
  - positive structured slang support 승격 경로가 깨지지 않는지 `tests.test_batch_context`로 확인한다.
  - known-bad post는 Gemma 4 4B, `MCP_SHARD_COUNT=36` 조건을 유지하되 `--parallel`은 상한으로 두고 `effective_parallel`을 검증한다.
  - 단건 closure는 10만 건 semantic `GO` 근거로 쓰지 않는다. broader `generic_common_surface/slang_db_review` regression 전까지 `NO-GO / REVIEW-LOCKED` 유지.

## 2026-05-27 현재 판정 - v71 일반 개념 질문 rescue guard

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v71_generic_concept_question_9218133_p36_20260527.json`: targeted 1건 completed `1`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v71_generic_concept_question_9218133_p36_20260527_manifest.json`: completed `1`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v71_generic_concept_question_9218133_after_packet_review_manifest.json`: after-review `ACCEPT=1`, `HOLD->ACCEPT=1`
  - `qualitative_review/20260505_214349_324347/generic_concept_question_guard_fix_ko_20260527.md`: 원인/수정/검증 정리
- gate 메모:
  - `9218133`은 일반 무협 개념 질문으로 닫혔고, `반로환동으로 신분세탁` resolved title은 제거됐다.
  - 일반 개념 질문에서 전체 작품명이 원문에 직접 없으면 canonical convergence/search hit/official URL만으로 `Strong` 또는 resolved title로 승격하지 않는다.
  - v71은 1건 targeted 재검증이며 10만 건 전체 품질 승인 표본이 아니다.
  - post-fix random baseline 및 P0/P1 bucket 회귀 전까지 `GO` 금지.

## 2026-05-27 현재 판정 - v68 캐릭터 표면명 guard 및 이미지 lazy-load 재확인

- 판정: `NO-GO / REVIEW-LOCKED`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v68_character_surface_title_8424362_p36_20260527.json`: targeted 1건 completed `1`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v68_character_surface_title_8424362_p36_20260527_manifest.json`: completed `1`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v68_character_surface_title_8424362_after_packet_review_manifest.json`: after-review `ACCEPT=1`, `HOLD->ACCEPT=1`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/11097334_image_loading_probe_20260527.json`: Browser `iab` image lazy-load probe
- gate 메모:
  - `8424362`는 `에미야 키리츠구` 캐릭터 표면명 확정이 제거되어 `is_relevant=false`, `official_title=null`, `work_resolution=none`으로 닫혔다.
  - 캐릭터 표면명 후보는 source/fetched title이 후보를 작품명으로 정확히 지칭하지 않으면 상세 URL substring 근거만으로 `Strong` 또는 resolved title로 승격하지 않는다.
  - `11097334`는 initial placeholder `1`이 스크롤/대기 후 `0`으로 내려가고 최종 loaded `3/3`, incomplete `0`, broken `0`이었다.
  - VLM/OCR row는 본문 이미지 영역까지 스크롤/대기 후 `loaded == article_image_count`, `placeholder/incomplete/broken=0`을 확인하기 전까지 `Strong`으로 보지 않는다.
  - v68은 1건 targeted 재검증이며 10만 건 전체 품질 승인 표본이 아니다. post-fix random baseline 및 P0/P1 bucket 회귀 전까지 `GO` 금지.

## 2026-05-26 현재 판정 - v23 final targeted guard 반영

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v23_final_targeted_guard_p36_20260526.json`: targeted 5건 completed `5`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v23_final_targeted_guard_p36_20260526_manifest.json`: completed `5`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v23_final_targeted_guard_after_summary.md`: after-review `ACCEPT=1`, `HOLD=4`
  - `logs/expert_run_20260526_001642_295323.log`: v23 run log
- gate 메모:
  - `8705431`, `8601885`, `8424362`, `8531521`의 주요 오탐 승격 경로는 targeted 기준에서 차단 또는 unresolved/HOLD로 내려갔다.
  - `8834919` positive control이 `is_relevant=false`로 떨어지는 false negative 회귀가 남아 있다.
  - after-review가 `ACCEPT=1`, `HOLD=4`이므로 품질 승인 근거로 부족하다.
  - v23은 5건 targeted 재검증이며 10만건 전체 품질 승인 표본이 아니다.
  - random baseline 1,000건 및 P0/P1 high-risk bucket 확장 검토 전까지 `GO` 금지.
  - VLM/OCR row는 Codex 내장 Browser `iab` 스크린샷/비전 근거가 없는 경우 `Strong` evidence로 승인하지 않는다.

대량 런과 품질 승인에 쓰는 운영 게이트다. 최종 판정은 `GO`, `REVIEW`, `NO-GO` 중 하나로 남긴다.

## 2026-05-25 현재 판정 - v19 비웹소설 IP / 본문 공식 URL targeted 반영

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/v19_body_url_non_novel_guard_p36_20260525.json`: targeted 5건 completed `5`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/v19_body_url_non_novel_guard_p36_20260525_manifest.json`: completed `5`, failed `0`, pending `0`
  - `logs/expert_run_20260525_231813_131527.log`: v19 run log
  - `qualitative_review/20260505_214349_324347/current_100k_issue_resolution_summary_ko_20260525.md`: v16-v19 후속 재확인 반영
- gate 메모:
  - `8601885`의 게임 IP title 오매칭은 targeted set 기준 해결됐다.
  - `8424362`는 비웹소설 IP 확정 제거 후 unresolved 보류다.
  - `8531521`의 slang_db/batch memory exact alias 오염과 `8705431`의 본문 공식 URL evidence 소실이 남아 있다.
  - VLM/OCR row는 Codex 내장 Browser `iab`에서 본문 이미지 `placeholder/incomplete/broken=0`을 확인하기 전까지 `Strong`으로 보지 않는다.
  - targeted 5건은 품질 승인 표본이 아니므로 expanded random baseline 및 P0/P1 bucket 회귀 전까지 `GO` 금지.

## 2026-05-25 현재 판정 - alias/bridge v15 targeted 반영

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v15_p36_20260525.json`: targeted 8건 completed `8`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v15_p36_20260525_manifest.json`: completed `8`, failed `0`, pending `0`
  - `logs/expert_run_20260525_210222_899635.log`: `post_id=9981263`에서 `official_title='성녀의 속마음이 들린다'`
  - `logs/expert_run_20260525_210222_899635.log`: `post_id=9901127`에서 `hold: multi-work title-list demoted final title`
  - `out/search_shard_audit_20260525_210133.json`: shard audit `ok=36/36`
  - `qualitative_review/20260505_214349_324347/current_100k_issue_resolution_summary_ko_20260525.md`: v15 후속 재확인 반영
- gate 메모:
  - `9981263` 제목란 alias false negative는 targeted set 기준 해결됐다.
  - `9901127` 복수 작품 감상글 단일 title 과확정 차단은 유지됐다.
  - targeted 8건은 품질 승인 표본이 아니므로 expanded random baseline 및 P0/P1 bucket 회귀 전까지 `GO` 금지.
  - VLM/OCR row는 Codex 내장 Browser `iab`에서 본문 이미지 `placeholder/incomplete/broken=0`을 확인하기 전까지 `Strong`으로 보지 않는다.

## 2026-05-25 현재 판정 - alias/bridge v14 targeted 반영

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v14_p36_20260525.json`: targeted 8건 completed `8`, failed `0`, pending `0`
  - `logs/expert_run_20260525_202201_766849.log`: `post_id=9901127`에서 `hold: multi-work title-list demoted final title official_title='나 혼자만 솔플러'`
  - `out/search_shard_audit_20260525_193805.json`: shard audit `ok=36/36`
  - `qualitative_review/20260505_214349_324347/current_100k_issue_resolution_summary_ko_20260525.md`: v11-v14 후속 재확인 반영
- gate 메모:
  - `9901127`의 복수 작품 감상글 단일 title 과확정은 v14 targeted set에서 차단됐다.
  - `9981263`은 오답 확정은 피했지만 정확한 `성녀의 속마음이 들린다` 복구가 아니라 unresolved 보류다.
  - targeted 8건은 품질 승인 표본이 아니므로 expanded random baseline 및 P0/P1 bucket 회귀 전까지 `GO` 금지.
  - VLM/OCR row는 Codex 내장 Browser `iab`에서 본문 이미지 `placeholder/incomplete/broken=0`을 확인하기 전까지 `Strong`으로 보지 않는다.

## 2026-05-25 현재 판정 - generic_common_surface 전수 회귀 반영

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/generic_common_surface_full_regression_review_ko_20260525.md`: bucket 전수 회귀 및 잔여 이슈 검토
  - `qualitative_review/20260505_214349_324347/generic_common_surface_full_regression_p36_20260525_manifest.json`: completed `89`, failed `0`, pending `0`
  - `qualitative_review/20260505_214349_324347/generic_common_surface_full_regression_p36_20260525_after_manifest.json`: after-review `ACCEPT=1`, `HOLD=88`
  - `qualitative_review/20260505_214349_324347/generic_common_surface_thin_bridge_guard_v2_p36_20260525_manifest.json`: residual v2 completed `8`, failed `0`, pending `0`
  - `src/llm_batch/agentic_pipeline.py`: `thin-bridge title` 및 `unverified alias/plot title` 보류 guard
- gate 메모:
  - 전수 재실행으로 `generic_common_surface` 확장 회귀 부족은 해소했지만, 결과는 `HOLD=88/89`라 승인 근거가 아니다.
  - 일반어/트로프/캐릭터 bridge 과잉 확정은 일부 제거됐다.
  - `히집악` false negative와 `성녀 속마음` alias recall 미완료가 남아 semantic decision quality는 계속 `NO-GO`다.

## 2026-05-25 현재 판정 - search_only zero-bucket guard 반영

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/search_only_zero_bucket_guard_review_ko_20260525.md`: 하위 패턴 수정 및 회귀 검토
  - `qualitative_review/20260505_214349_324347/issue_regression_search_only_guard_p36_20260525_manifest.json`: completed `3`, failed `0`, pending `0`
  - `src/llm_batch/agentic_pipeline.py`: weak anchor + zero evidence bucket 단일 title 보류 guard
- gate 메모:
  - `post_id=11663540`, `10824887`은 관련글 유지 + title unresolved로 내려갔다.
  - positive control `post_id=9722392`는 resolved title을 유지했다.
  - 이 검증은 3건 targeted regression이므로 `generic_common_surface` 전체와 10만건 semantic quality approval의 근거로 쓰지 않는다.
  - expanded random baseline 및 P0/P1 bucket 확장 회귀 전까지 `GO` 금지.

## 2026-05-25 현재 판정 - Codex 내장 브라우저 이미지 로딩 게이트 반영

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/vlm_ocr_iab_image_gate_manifest.json`: Codex 내장 Browser `iab`, VLM/OCR `100/100`, `Strong=98`, `Missing=2`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/issue_11097334_image_loading_probe_v2.json`: `post_id=11097334`에서 스크롤 전 본문 이미지 `3`개 중 로드 `2`, placeholder `1`; 스크롤 후 로드 `3`, placeholder `0`
  - `qualitative_review/20260505_214349_324347/fix_test_review_ko_20260525.md`: fallback 캡처 도구 이미지 게이트 패치 및 36워커 smoke test 리뷰
  - `qualitative_review/20260505_214349_324347/expert_main_smoke_p36_20260525_manifest.json`: smoke completed `2`, failed `0`, shard health `36/36`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`: `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`
- gate 메모:
  - VLM/OCR은 본문 이미지 영역 스크롤/대기 후 `placeholder/incomplete/broken=0`일 때만 `Strong`으로 본다.
  - Playwright/headless fallback 산출물도 `article_image_count/loaded/incomplete/placeholder/broken` 없이는 `Strong`으로 보지 않는다.
  - `post_id=10794867`, `10892069`는 VLM/OCR 승인 subset에서 제외하고 `human_review`로 남긴다.
  - 36워커 실행과 VLM/OCR 이미지 게이트는 수행됐지만 approval excluded `460/584`가 남아 semantic decision quality는 `NO-GO`다.

## 2026-05-24 현재 판정 - server-poc 갱신 지침 재확인

- 판정: `NO-GO`
- 실행 근거:
  - `qualitative_review/20260505_214349_324347/round3_exit_re_search_re_run_p36_result_manifest.json`: completed `155/155`, failed `0`
  - `qualitative_review/20260505_214349_324347/search_shard_audit_36_current.json`: shard `36/36`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_all/vlm_ocr_browser_visual_manifest.json`: VLM/OCR captured `100/100`, visual evidence `Weak=100`, `Strong=0`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`: `ACCEPT=52`, `HOLD=365`, `REPROCESS=94`, `INFO_MISSING=73`
- gate 메모:
  - 36워커 실행 성공은 run health 근거로만 본다.
  - VLM/OCR 브라우저 시각 증거가 `Strong`이 아니므로 기존 VLM/OCR ACCEPT도 품질 승인에서 제외한다.
  - approval excluded `532/584`가 남아 semantic decision quality는 `NO-GO`다.

## 1. 검색 Shard / MCP Reliability

- [ ] `tools/audit_search_shards.py --count <N>` 실행
- [ ] `ok_count == count`
- [ ] `bad_count == 0`
- [ ] 모든 shard의 `/healthz` 정상
- [ ] 모든 shard의 `/readyz.payload.searxng == true`
- [ ] SearchXNG UI 포트 정상
- [ ] Docker state에서 `Running=true`, `OOMKilled=false`, `Dead=false`
- [ ] `mcp-bridge`, `searchxng`, `browser-search`, `warp`가 exited/restarting/dead 상태가 아님
- [ ] WARP snapshot에서 `warp=on`
- [ ] `MCP_HEALTH_USE_READYZ=1`
- [ ] `MCP_CLIENT_ENDPOINT_FAILOVER=1`
- [ ] `MCP_CLIENT_ENDPOINT_BACKOFF_SEC` 설정 확인

게이트:

- `GO`: `ok_count == count`, `bad_count == 0`
- `NO-GO`: bad shard 1개 이상, `/readyz` 실패, SearchXNG UI 실패
- `REVIEW`: 정상화됐지만 `Exited (137)`, `can't start new thread`, `Resource temporarily unavailable`, `pthread_create failed`, DNAT/iptables fork 실패 흔적이 있음

## 2. Run Audit

- [ ] `tools/audit_expert_run_health.py --run-id <RUN_ID>` 실행
- [ ] `checkpoint_rows == manifest.completed_count`
- [ ] `pending_count_actual == manifest.pending_count`
- [ ] `status_counts.failed == 0` 또는 실패 post id/원인 문서화
- [ ] `reason_error_count == 0` 또는 known issue 문서화
- [ ] `fatal_or_trace_line == 0` 권장
- [ ] `llm_connection_refused` 반복 여부 확인
- [ ] `search_upstream_zero` 확인
- [ ] `search_degraded_detected` 확인
- [ ] `search_bridge_after_filter_zero` 확인
- [ ] `search_timeout` 확인
- [ ] `headless_engine_counts` 확인
- [ ] worker별 degradation top 확인

게이트:

- `GO`: checkpoint/manifest 정합성 통과, fatal trace 0, shard 장애 없음
- `REVIEW`: run은 완료됐지만 검색 저하율 상승, failed/reason error 소수 존재, pending/flush 차이 존재
- `NO-GO`: 정합성 실패, fatal trace 증가, shard 장애 동반 결과를 품질 승인하려는 경우

## 2-1. VLM/OCR Image Payload Reliability

- [ ] VLM enabled run에서 `VLM chunk request` 직후 `500 -> 502` fanout이 있는지 확인
- [ ] `image_geometry_invalid`, `image_geometry_too_small`, `image_aspect_ratio_extreme` limitation 카운트 확인
- [ ] dcimg `application/octet-stream` 응답이 signature sniffing으로 image 처리되는 경우 dimension guard가 적용되는지 확인
- [ ] 새 degenerate 이미지가 발견되면 post id가 아니라 width/height/aspect ratio 같은 일반화 기준으로 차단
- [ ] 서버 재기동 후 known incident post `11589463` 포함 소량 canary에서 VLM request 미발생과 서버 생존 확인
- [ ] VLM/OCR semantic sample은 원문 post URL, image URL, evidence URL 중 접근 가능한 원본을 브라우저로 직접 열어 확인
- [ ] 브라우저 확인은 Codex 내장 Browser plugin `@browser` / in-app browser `iab`를 1순위로 사용
- [ ] Playwright CLI/headless fallback을 썼다면 내장 브라우저 사용 불가 사유와 fallback 명령/stdout/stderr를 manifest에 기록
- [ ] 브라우저 확인 대상은 screenshot path, capture timestamp, viewport, browser access status를 packet/label에 기록
- [ ] screenshot/vision 관찰이 `ocr_text`, `resolved_title`, `reason`, final decision과 일치하는지 기록
- [ ] 브라우저 접근 실패, 삭제, 로그인/성인 인증, 404, blocked response는 `Missing`/`Weak` evidence로 기록하고 `ACCEPT` 금지

게이트:

- `GO`: degenerate image는 limitation으로 격리되고, VLM request 직후 500/502 fanout이 없으며, VLM/OCR semantic sample의 Codex 내장 브라우저 screenshot/vision evidence가 `Strong` 또는 충분한 `Medium`
- `REVIEW`: limitation은 기록되지만 dashboard/audit 집계가 부족하거나, unknown-dimension 포맷이 있거나, 일부 VLM/OCR 시각 evidence가 `Weak`/`Missing`
- `NO-GO`: 동일 이미지/동일 geometry 계열이 VLM payload로 들어가 serving crash를 재현하거나, VLM/OCR 개입 케이스를 Codex 내장 브라우저 시각 확인 없이 품질 승인하려는 경우

## 3. Slang DB Audit

- [ ] `slang_insight_count` 확인
- [ ] `old_store_true_count` 확인
- [ ] `new_store_true_after_patch_count` 확인
- [ ] `old_store_true_blocked_by_patch_count` 확인
- [ ] `blocked_reason_counts` 확인
- [ ] `blocked_samples` 수동 검토
- [ ] `slang_db/slang_db.json` title count 확인
- [ ] slang term count 확인
- [ ] family aliases count 확인
- [ ] sentence-like term 오염 수 확인
- [ ] title과 완전 동일 alias 오염 수 확인

게이트:

- `GO`: 문장형 term 오염 0, title 동일 alias 오염 0, review 후보 처리됨
- `REVIEW`: 오염은 0이지만 `unclear_canonical_alias` 실제 약칭 후보가 남음
- `NO-GO`: `sentence_or_exact_bad_remaining > 0`

## 4. Sampling / Parallel Regression

- [ ] `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md` 기준으로 표본 단계 기록
- [ ] 4~20건 스모크를 품질 승인 근거로 쓰지 않음
- [ ] canary 입력 100~500건 이상 생성
- [ ] risk discovery 입력 1,000~3,000건 이상 생성
- [ ] validation 입력 10,000건 이상 생성 또는 전체 run 100% 자동 감사와 결합
- [ ] 검색 저하, unresolved, slang 후보, non-relevant 경계, 정상 대조군 포함
- [ ] 자동 감사 결과와 자연어 판정 품질 리뷰를 분리해서 기록
- [ ] random control sample과 high-risk semantic bucket 과표집을 병행
- [ ] 같은 post id를 개선 전후 재처리해 false positive/false negative 변화를 비교
- [ ] 병렬 실행 시 shard 수, worker 수, env override를 문서에 기록
- [ ] Gemma 4 4B 대형 재처리/명시 shard audit은 `MCP_SHARD_COUNT=36`과 shard audit `36/36`을 기록한다. 소규모 reuse-only goal/test에서는 required env가 아니며 manifest의 `effective_parallel`과 lifecycle 차단 여부를 본다
- [ ] 실제 워커 수는 `effective_parallel=min(requested_parallel,input_count)`로 검증하고, 36은 상한으로만 사용한다
- [ ] 36건 미만 targeted run에서 실제 워커가 36개로 고정 기동되지 않았는지 manifest로 확인한다
- [ ] 기능/품질 개선 후 자동 테스트 런을 실행하고 baseline 대비 비교 문서를 생성
- [ ] 품질 개선 targeted/unit 통과 후 200건 canary를 기본 후속 작업으로 실행
- [ ] 200건 canary가 `completed=200/200`, `failed=0`, `pending=0`이면 1,000건 risk discovery를 이어서 실행
- [ ] 200건 canary 실패 시 1,000건으로 진행하지 않고 failure summary, stuck/failed post, shard/search 상태를 기록
- [ ] 즉시 실행하지 못한 경우 defer 사유와 재개 명령을 `HISTORY.md`/`TODO.md`에 기록
- [ ] 비교 문서에 baseline run id, improved run id, 입력 JSONL, 명령, env, 주요 지표 delta를 포함
- [ ] top latency, timeout/degraded, failed/pending, known bad post id 변화가 누락되지 않음

게이트:

- `GO`: 100% 자동 감사와 대형 validation/정성 리뷰가 함께 완료되고, semantic decision quality가 별도 `GO`
- `REVIEW`: 200건 canary와 1,000건 risk discovery는 완료됐지만 정성 리뷰/validation이 남음
- `NO-GO`: 수백만 건 운영 변경을 4~20건 스모크나 targeted만으로 승인하거나, canary 통과 없이 risk discovery/validation으로 넘어가려는 경우

## 5. 대시보드 / 문서 갱신

- [ ] run audit 요약 문서 또는 대시보드 갱신
- [ ] shard audit 요약 문서 또는 대시보드 갱신
- [ ] slang DB 품질 지표 문서 또는 대시보드 갱신
- [ ] 개선 전후 비교 요약 문서 갱신
- [ ] 리뷰/분석/검토/피드백 Markdown의 사람이 읽는 본문은 한국어로 작성
- [ ] JSON key, enum, action id, bucket id, 명령어, 로그 원문은 원문을 유지하되 해석/판정/후속 작업 설명은 한국어로 작성
- [ ] audit JSON 경로 기록
- [ ] 실행 명령 기록
- [ ] 남은 TODO 기록

게이트:

- `GO`: 운영자가 문서/대시보드만 보고 현재 상태를 판단할 수 있음
- `REVIEW`: 코드 개선은 됐지만 대시보드 반영이 남음
- `NO-GO`: 새 reliability/slang/품질 변경이 있는데 검증 문서 또는 개선 전후 비교 문서가 없음

## 6. 일반화 / 하드코딩 방지 게이트

- [ ] 실패 사례가 특정 post id/제목 문자열이 아니라 재사용 가능한 실패 유형으로 기록됨
- [ ] LLM 프롬프트 변경은 "예시 암기"가 아니라 판단 rubric/증거 조건을 강화함
- [ ] 코드 변경에 exact bad-title blacklist가 추가됐다면 범주형 lexicon으로 대체 가능한지 검토함
- [ ] 범주형 lexicon은 `의학/건강`, `장르 일반어`, `검색 메타데이터`, `타매체`처럼 이름과 목적이 명확함
- [ ] positive rescue 케이스와 negative veto 케이스를 같은 테스트 묶음에서 검증함
- [ ] known bad 사례의 통과만으로 승인하지 않고, 200/1,000건 표본에서 새 FP/FN을 재확인함

게이트:

- `GO`: 실패 유형 정의, 범주형 규칙/프롬프트, 이웃 케이스 회귀 테스트, 표본 재확인이 모두 충족됨
- `REVIEW`: 단일 사례는 고쳤지만 일반화 근거 또는 이웃 케이스 검증이 부족함
- `NO-GO`: 특정 post id/제목/검색 문자열을 직접 하드코딩해 대량 런에 투입하려는 경우

## 7. LLM / 전문가 정성 리뷰

- [ ] `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md` 기준 적용
- [ ] `tools/build_llm_judgment_review_packet.py --run-id <RUN_ID>` 실행
- [ ] `qualitative_review/<run_id>/sample_manifest.json` 작성
- [ ] `qualitative_review/<run_id>/review_packets.jsonl` 작성
- [ ] `qualitative_review/<run_id>/review_labels.jsonl` 작성
- [ ] `qualitative_review/<run_id>/pattern_summary.md` 작성
- [ ] `qualitative_review/<run_id>/gate_decision.md` 작성
- [ ] `qualitative_review/<run_id>/action_queue.md` 작성
- [ ] random control sample 포함
- [ ] 검색 저하 + slang 후보 위험군 포함
- [ ] resolved title 저근거/고신뢰 케이스 포함
- [ ] unresolved/multi_work/adjacent/trope/author_talk 경계 케이스 포함
- [ ] non-relevant 오분류 가능 케이스 포함
- [ ] generic parenthetical bridge bucket 포함
- [ ] VLM/OCR 개입 케이스 포함
- [ ] VLM/OCR 개입 packet은 브라우저 원문 확인, screenshot path, vision/manual observation, visual evidence grade를 포함
- [ ] VLM/OCR 브라우저 접근 실패/삭제/로그인 필요 케이스는 `INFO_MISSING`, `HOLD`, 또는 `REPROCESS`로 분리하고 `ACCEPT` 금지
- [ ] screenshot/vision 관찰이 OCR text 또는 reason과 충돌하면 `REJECT`/`REPROCESS` 후보로 승격
- [ ] worker/shard degraded window 전후 케이스 포함
- [ ] `unclear_canonical_alias`, pending, family, noise, blocked 후보 포함
- [ ] 각 packet에 title/body/comment/evidence/reason/final decision 포함
- [ ] 각 packet에 post intent, model decision, evidence alignment, reason quality, boundary risk, slang_db effect를 짧게 기록
- [ ] 2인 독립 리뷰 또는 최종 조정자 판정 기록
- [ ] `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING` 집계 기록
- [ ] action을 `no_action`, `re_search`, `re_judge`, `re_run`, `human_review`, `slang_db_review`, `docs_issue` 중 하나로 기록
- [ ] 최근 round에서 새 실패 유형이 거의 나오지 않는지 failure pattern saturation 확인

게이트:

- `GO`: 필수 위험군 정성 리뷰 완료, random control과 high-risk bucket 결과 분리 보고, DB 반영 후보 확정, 재처리 대상 분리
- `REVIEW`: 패킷은 생성됐지만 리뷰가 미완료이거나 `HOLD/REPROCESS/INFO_MISSING` 대상이 남음
- `NO-GO`: 정성 리뷰가 필요한 run을 리뷰 없이 품질 승인하려는 경우

## 8. Scan Result Directory Review Intake

- [ ] `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md` 기준으로 작업 모드 결정: `GUIDE_MODE` / `RUN_REVIEW_MODE` / `MIXED_MODE`
- [ ] scan result directory inventory 작성
- [ ] manifest/checkpoint/run audit/log/comparison/review packet/slang DB snapshot 존재 여부 확인
- [ ] 서버에서 복사한 run package라면 result/logs만으로 `GO` 판정하지 않고 manifest/checkpoint/run audit/review packet 누락을 `Missing` evidence로 기록
- [ ] 결론마다 증거 등급 기록: `Strong`, `Medium`, `Weak`, `Missing`
- [ ] 가장 이른 fatal/error/timeout/degraded 이벤트와 후속 fanout 분리
- [ ] runtime/search/judgment quality/slang_db/docs-tooling taxonomy로 실패 유형 분류
- [ ] `generic_parenthetical_bridge`가 resolved/relevance/reason을 과도하게 강화했는지 확인
- [ ] `slang_db` 후보 상태를 저장/차단/미추출/표시 누락으로 세분화
- [ ] action queue 작성: re-run, re-search, re-judge, human review, slang_db review, docs/checklist update
- [ ] 동일 원인 post는 systemic issue로 묶고 개별 post id는 evidence example로만 기록
- [ ] 자동 감사만 완료된 상태를 자연어 품질 승인으로 쓰지 않음
- [ ] 대량 품질 승인 전 `QUALITATIVE_SEMANTIC_REVIEW_LOOP` 산출물 존재 여부 확인

게이트:

- `GO`: 핵심 파일과 run integrity가 설명 가능하고, 자연어 리뷰 loop에서 random control/high-risk bucket 모두 승인 가능함
- `REVIEW`: 런은 완료됐지만 일부 evidence가 `Weak`/`Missing`이거나 검색 저하, 판단 과잉, slang DB 저장/차단/표시 혼선 또는 semantic review 미완료가 남음
- `NO-GO`: 핵심 증거가 없어 런 검증이 불가능하거나, 카운트 정합성 붕괴/전체 fanout/대량 오염/약한 evidence 기반 강한 resolution이 반복되거나, 자동 감사만으로 품질 승인하려는 경우

## 2026-04-26 판정

- 관련 run id: `20260423_170321_250907`
- 최초 shard 상태: `ok=27/36`, bad `[1,10,13,15,26,27,29,33,34]` -> `NO-GO`
- recreate 후 shard 상태: `ok=36/36` -> shard gate `GO`
- 이후 병렬 smoke 실행으로 테스트용 shard 2개가 자동 구성됨: `out/search_shard_audit_20260427_000659.json`, `ok=2/2`
- slang DB: 오염 0, `unclear_canonical_alias` 후보 14 -> `REVIEW`
- 정성 리뷰: 패킷 생성/전문가 판정 필요 -> `REVIEW`
- 전체 판정: `REVIEW`
- 이유: 검색 인프라는 정상화됐지만 shard 장애가 섞인 20k run 결과는 검색 안정화 후 대형 샘플 재처리가 필요함. 4건 smoke는 승인 근거가 아님.

## 2026-04-27 판정 - query gate 200 canary auto rerun

- 관련 run id: `20260427_121338_563339`
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 실행 경로: `expert_main.py` startup auto-manage, `--no-auto-up-shards` 미사용
- shard 상태:
  - startup health: `ok=36/36`
  - 사후 audit: `out/search_shard_audit_20260427_134858.json`, `ok_count=36`, `bad_count=0`
  - shard reliability gate: `GO`
- run 상태:
  - checkpoint `200/200`
  - manifest `completed_count=200`, `flushed_count=200`, `pending_count=0`, `failed_count=0`
  - 1차 stuck `post_id=11478694` 완료, `703.9s`
  - run stability gate: `GO`
- sampling/regression 상태:
  - canary 200건 완료.
  - 1,000건 risk discovery와 10,000건 validation은 아직 미완료.
  - sampling gate: `REVIEW`
- LLM/전문가 정성 리뷰:
  - 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`
  - `selected=80`, 검색 저하/은어/공식 제목 미확정/경계 케이스 포함.
  - adjudication 미완료.
  - qualitative gate: `REVIEW`
- 전체 판정: `REVIEW`
- 이유:
  - canary 안정성은 통과했지만 검색 오류 `81`, timeout `82`, infra no-result `220`, long-tail 상위 post가 남음.
  - 수백만 건 운영 승인 또는 10,000건 validation GO 전에는 80건 정성 리뷰와 1,000건 risk discovery가 필요함.

## 2026-04-27 판정 - late search budget guard

- 관련 변경: `src/llm_batch/experts/orchestrator.py`
- 자동 테스트:
  - `py_compile`: pass
  - targeted unit tests: `3/3 OK`
- 참고 실행:
  - `20260427_140716_814536`, `11478694`, `completed_count=1`, `failed_count=0`
  - shard `1/1` 및 최종 late-purpose refinement 전 시작된 smoke라 품질 gate로 사용하지 않음
- 현재 gate:
  - implementation gate: `GO`
  - canary/regression gate: `REVIEW`
  - qualitative gate: `REVIEW`
- 다음 gate 조건:
  - 36 shard / 200건 canary에서 `failed=0`, missing `0`
  - `late_budget_capped_total` 또는 `late_budget_exhausted_total` 발생 케이스가 false negative를 늘리지 않는지 전문가 리뷰
  - top latency 상위 post의 처리 시간과 검색 실행 수 감소 확인

## 2026-04-27 판정 - late search budget 200 canary comparison

- 관련 run id:
  - baseline: `20260427_121338_563339`
  - improved: `20260427_143145_922090`
- 비교 문서:
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.json`
- run 상태:
  - checkpoint `200/200`
  - manifest `completed_count=200`, `flushed_count=200`, `pending_count=0`, `failed_count=0`
  - 사후 shard audit `out/search_shard_audit_20260427_late_budget_postrun.json`: `ok=36/36`
  - run stability gate: `GO`
- 비교 상태:
  - 검색 오류 `81 -> 75`
  - timeout `82 -> 75`
  - identified title `72 -> 76`
  - relevant `148 -> 153`
  - late budget cap/exhausted `22/14`
  - total time `5452.3s -> 5453.8s`
  - comparison gate: `REVIEW`
- LLM/전문가 정성 리뷰:
  - 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_143145_922090_20260427_160810.md`
  - `selected=100 from rows=200`
  - qualitative gate: `REVIEW`
- 전체 판정: `REVIEW`
- 이유:
  - 안정성은 통과했고 late budget guard도 실제 발동했지만, 결과 품질은 사람이 읽어야 한다.
  - `11478694`, `11456200` tail은 개선됐으나 `11457804`, `11718077`은 회귀/잔류 병목이다.
  - infra no-result `220 -> 244`와 output 판정 변화가 있어 1,000건 risk discovery 전 전문가 adjudication이 필요하다.

## 2026-04-27 판정 - afterfix11 qualitative adjudication

- 관련 run id: `20260427_191203_030136`
- canary 상태:
  - checkpoint `200/200`
  - failed `0`, pending `0`
  - WARP/MCP startup health `36/36`
  - run stability gate: `GO`
- 정성 리뷰:
  - 원본 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`
  - 판독 산출물: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`
  - 집계: `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`
  - qualitative gate: `REVIEW`
- 확대 검증:
  - 1,000건 risk discovery 완료: run id `20260427_212634_728016`
  - 입력: `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`
  - 출력: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`
  - 결과: `completed=1000/1000`, `failed=0`, `pending=0`, `Relevant=746`, `Identified=351`
  - audit: `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_audit.json`
- 전체 판정: `REVIEW`
- 이유:
  - `11631298`, `11663540` known bad는 정성 리뷰에서도 개선 인정.
  - 그러나 1,000건에서 parenthetical bridge critical FP 4건이 재현됐고, malformed/generic official title 후보 14건, strong alias 과차단이 확인되어 후속 rule 개선이 필요하다.

## 2026-04-28 판정 - afterfix12 P0 targeted gate

- 관련 변경:
  - final official title validator
  - character parenthetical false positive gate
  - generic relation strong alias rescue
- 자동 테스트:
  - `py_compile`: pass
  - targeted unittest: `13/13 OK`
- 실제 targeted run:
  - core4 run id `20260428_123539_845850`, `completed=4/4`, `failed=0`
  - `11689276`: title 없음, adjacent.
  - `11631298`: non-relevant/title 없음.
  - `11562020`: title resolved.
  - `11620037`: core4 첫 실행에서 source metadata title 재발.
  - rashomon 단건 rerun id `20260428_124339_828427`: `11620037` non-relevant/title 없음.
- gate:
  - implementation/targeted gate: `GO`
  - 200/1,000 canary gate: `REVIEW`
  - qualitative gate: `REVIEW`
- 다음 gate 조건:
  - 200건 canary에서 known critical FP 재발 없음.
  - 1,000건 risk discovery에서 malformed/generic title 후보 감소.
  - strong alias rescue가 `서울마탑` 외 long-tail(`화귀`, `언니약혼`, `폴랩`, `망교성`)에서 false positive 없이 작동하는지 리뷰.

### 2026-04-28 addendum - ECT medical chatter gate

- 관련 post: `11718070`
- 실제 run id: `20260428_132300_821816`
- 결과:
  - `is_relevant=false`
  - official title 없음
  - `topicality=unrelated`
  - `work_resolution=none`
  - `consistency_flags=medical_common_topic_demoted`
- gate 영향:
  - targeted ECT gate: `GO`
  - broader medical/nonwork generalization gate: `REVIEW`

### 2026-04-28 addendum - Namu medical/common concept title gate

- 관련 post: `11718111`
- 실제 run id: `20260428_230857_637381`
- 결과:
  - `is_relevant=false`
  - official title 없음
  - `discussion_type=noise`
  - `topicality=unrelated`
  - `work_resolution=none`
  - `consistency_flags=medical_common_topic_demoted`
- regression:
  - `tests.test_agentic_pipeline_rework`: `147 OK`
  - `tests.test_agentic_pipeline_alias_contract`: `30 OK`
  - `py_compile`: pass
- gate 영향:
  - targeted Namu medical concept gate: `GO`
  - broader Namu fallback/medical positive-neighbor gate: `REVIEW`

## 2026-04-28 판정 - afterfix12 36병렬 canary

- 관련 run id: `20260428_142042_238055`
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`
- 실행 조건:
  - `expert_main.py` startup auto shard 관리 경로.
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`, `--parallel 36`.
  - startup WARP `36/36`, MCP bridge health `36/36`.
- run 상태:
  - checkpoint `200/200`
  - manifest `completed_count=200`, `failed_count=0`, `pending_count=0`
  - `Relevant=146`, `Identified=67`
  - `Total Time=2473.3s`, `Avg Time/Post=12.4s`
  - run stability gate: `GO`
- shard 상태:
  - 사전 수동 audit은 `ok=4/36`이라 startup auto 재정리 경로를 사용.
  - `tools/warp_shards.py` status/trace timeout 보정 후 startup 확인 통과.
  - 사후 audit `out/search_shard_audit_20260428_after_afterfix12_parallel36_retry.json`: `ok=36/36`, `bad=[]`
  - shard reliability gate: `GO`
- 일반화/이웃 케이스:
  - `11718070`: medical/common-topic FP 제거.
  - `11631298`: generic faction/worldbuilding FP 차단 유지.
  - `11663540`: character parenthetical positive 회수 유지.
  - `11620037`: source metadata title 오염 제거.
  - `11562020`: strong alias positive rescue 확인.
  - `11702067`, `11576520`: relevant지만 title 미확정으로 alias long-tail review 필요.
  - generalization gate: `PARTIAL-GO`
- 정성 리뷰:
  - 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
  - selected `120/200`
  - adjudication 미완료.
  - qualitative gate: `REVIEW`
- 전체 판정: `REVIEW`
- 이유:
  - 실행/검색 shard 안정성은 통과했고, afterfix11 critical FP 일부는 제거됐다.
  - 하지만 adjacent/relevant 경계와 strong alias long-tail이 남아 1,000건 risk discovery 및 120건 리뷰 판독 전 품질 승인은 보류.

## 2026-04-29 판정 - afterfix14 canary/risk discovery

- 관련 run id:
  - canary: `20260428_233059_378617`
  - risk discovery: `20260429_002511_375830`
- 입력:
  - canary: `out/sampling/query_gate_canary_200_20260426.jsonl`
  - risk discovery: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429.jsonl`
- 출력:
  - canary result: `out/sampling/query_gate_canary_200_afterfix14_20260428_result.json`
  - risk result: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_result.json`
  - risk audit: `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_audit.json`
  - risk review packet: `out/llm_judgment_reviews/llm_judgment_review_20260429_002511_375830_risk1000_afterfix14.md`
- run 상태:
  - canary `completed=200/200`, `failed=0`, `pending=0`, `Relevant=70`, `Identified=61`.
  - risk discovery `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=381`, `Identified=297`.
  - risk runtime `13487.3s`, 평균 `13.5s/post`.
- shard 상태:
  - 사전 audit: `out/search_shard_audit_20260429_before_afterfix14_risk1000.json`, `ok=36/36`.
  - 사후 audit: `out/search_shard_audit_20260429_after_afterfix14_risk1000.json`, `ok=36/36`.
  - shard reliability gate: `GO`.
- audit:
  - `reason_errors=0`
  - `slang_db_bad_remaining=0`
  - `search_timeout=4`
  - `search_degraded_detected=173`
  - `headless_naver_playwright=184`, `headless_google_cloak=18`
- 품질 확인:
  - `11718070`: ECT/우울증 치료 일반글은 non-relevant/title 없음.
  - `11631298`: 무림맹 일반 세력어는 non-relevant/title 없음.
  - `11456200`: 마법소녀ㄴ/폼체인지 검색 이웃은 non-relevant/title 없음.
  - `11616838`, `11198715`: 마법소녀ㄴ positive stem resolved 유지.
  - `11066247`: 다중 애니 캐릭터/트로프 글은 adjacent/title 없음.
- 실패/리뷰:
  - `11718111`: `정신과 의사`로 resolved 재발. targeted 통과만으로는 대형 표본 품질 승인이 불가함을 확인.
  - `11684415`: `小數, decimal number`로 resolved. reason 내부는 `official_title_evidence=false`, `post_spans=0`, `search_snippets=0`, `official_urls=0`.
  - `11505857`: `Cecil`로 resolved. 본문이 `ㄹㅇ`뿐인 인명/캐릭터 표면이라 title 확정 근거가 약함.
  - weak-evidence official title 후보 35건을 후속 개선 대상으로 분리.
- gate 영향:
  - run stability: `GO`
  - shard reliability: `GO`
  - known-case regression: `PARTIAL-GO`
  - production quality: `REVIEW`
- 다음 gate 조건:
  - weak-evidence official title guard targeted positive/negative 이웃 통과.
  - 개선 후 같은 정책으로 200건 canary와 1,000건 risk discovery 자동 재실행.
  - `11718111`, `11684415`, `11505857`이 title 없음/HOLD/REPROCESS로 이동하고, `나혼렙`, `마법소녀ㄴ`, `전 버튜버`, `서울마탑` positive가 유지되는지 확인.

## 2026-04-30 판정 - afterfix21 canary/risk discovery

- 관련 run id:
  - targeted: `20260430_120419_466550`
  - canary: `20260430_121717_430655`
  - risk discovery: `20260430_131615_234022`
- run 상태:
  - targeted `completed=5/5`, `Relevant=3`, `Identified=2`.
  - canary `completed=200/200`, `failed=0`, `pending=0`, `Relevant=82`, `Identified=65`.
  - risk `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=396`, `Identified=308`.
- audit:
  - canary `reason_errors=0`, `slang_db_bad_remaining=0`, `search_degraded_detected=25`.
  - risk `reason_errors=0`, `slang_db_bad_remaining=0`, `search_degraded_detected=163`, `search_upstream_zero=436`, `search_bridge_after_filter_zero=434`.
- 품질 확인:
  - `11505857`: short person/character surface false bridge 차단, title 없음.
  - `11456200`: trope-only internal work signal 과복구 차단, non-relevant/title 없음.
  - `11718070`, `11718111`, `11631298`: title 없음 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11198715`, `11616838`: risk에서 관련-미확정 유지.
- gate 영향:
  - run stability: `GO`.
  - known-case regression: `GO`.
  - production quality: `REVIEW`.
- REVIEW 사유:
  - afterfix20 risk 대비 afterfix21 risk `Identified=277 -> 308`, `Relevant=382 -> 396`으로 증가.
  - 증가분이 검색 회수율 개선인지 false positive 증가인지 정성 리뷰 전에는 production GO로 승인하지 않음.
- 다음 gate 조건:
  - afterfix21 risk resolved 증가분 리뷰 패킷 생성.
  - 고위험 resolved 표본을 `ACCEPT/HOLD/REPROCESS/REJECT`로 판독.

## 2026-05-22 판정 - server-poc qualitative correction

- 관련 run id:
  - full server run: `20260505_214349_324347`
- 산출물:
  - `server-poc/run_review_20260505_214349_324347.md`
  - `server-poc/qualitative_review_packet_20260505_214349_324347_20260522.jsonl`
  - `server-poc/qualitative_review_adjudication_20260505_214349_324347_20260522.md`
  - `qualitative_review/20260505_214349_324347/round2_manifest.json`
  - `qualitative_review/20260505_214349_324347/round2_labels.jsonl`
- gate 보정:
  - 자동 로그/카운트/필드 감사와 자연어 품질 판독을 분리한다.
  - 10만 건 전체 결과를 자동 스캔했다고 해서 자연어 품질 승인을 완료한 것으로 쓰지 않는다.
  - 1차 packet `172`건 판독 결과 `ACCEPT=107`, `HOLD=26`, `REPROCESS=27`, `REJECT=12`.
  - random control `100`건은 `ACCEPT=86`, `HOLD=14`.
  - random control v3 `1000`건은 `ACCEPT=889`, `HOLD=2`, `REPROCESS=109`, `REJECT=0`.
  - high-risk expansion `5000`건은 `ACCEPT=2041`, `HOLD=1528`, `REPROCESS=1430`, `REJECT=1`.
  - merged `6172`건은 `ACCEPT=3037`, `HOLD=1556`, `REPROCESS=1566`, `REJECT=13`.
  - Round 3 P0/P1 후보 `584`건과 targeted input `584`건은 현재 코드로 재검색/재판정/재실행 완료.
  - 최신 지침: Gemma 4 4B급 vLLM 대형 후속 실행/명시 shard audit에서는 `MCP_SHARD_COUNT=36`과 shard audit `36/36`을 기록한다. 소규모 targeted run은 `--parallel 36`을 상한으로만 보며, 실제 워커 수는 `effective_parallel`로 확인한다.
  - 이력 참고: 2026-05-22 Round 3 실행은 초기 `--parallel 8` checkpoint `116`건을 보존한 뒤, 남은 `468`건을 당시 기준 `--parallel 32`로 재개했다.
  - Round 3 after: `584`건 완료, failed `0`, duplicate post id `0`, `ACCEPT=179`, `HOLD=268`, `REPROCESS=137`, `REJECT=0`.
  - Round 3 residual rerun 이력: `re_search + re_run` `189`건을 당시 기준 `--parallel 32`로 재처리, failed `0`; combined latest `ACCEPT=195`, `HOLD=288`, `REPROCESS=101`, `REJECT=0`.
  - 대형 후속 재확인 실행은 shard audit `36/36`과 `requested_parallel/effective_parallel`을 함께 기록한다. 소규모 reuse-only canary는 shard audit 강제 대신 lifecycle 차단과 `effective_parallel`을 확인한다.
  - Round 3 quarantine: accepted subset `195`, quality approval 제외 `389`, `P0=91`, `P1=298`.
  - Round 3 readiness: search shards `8/8` OK, 기본 vLLM endpoint HTTP 200.
- 품질 판정:
  - run integrity: `REVIEW`
  - natural-language quality approval: `NO-GO`
- 다음 gate 조건:
  - Round 3 after-rerun combined의 `HOLD/REPROCESS=389`를 pattern별로 줄이거나 explicit quarantine으로 고정.
  - quarantine은 GO가 아니며, exit action 완료 후 post-quarantine random baseline + P0/P1 regression이 필요.
  - `정신분열병`, `판타지 용어`, `2016`, `Legend` 같은 generic title surface는 현재 코드에서 재발 차단 유지.
  - `갤질의사` canonical drift와 `즉사무림`류 false-negative alias는 slang/family/display state를 분리해 재검증.

## 2026-05-26 추가 운영 체크

- [ ] 자동 감사, 카운트, checkpoint 완료를 semantic quality `GO`로 해석하지 않는다.
- [ ] Gemma 4 4B 후속 재실행은 shard `36/36` 및 Python stale process 여부를 기록하고, `--parallel 36`을 상한으로 둔 뒤 manifest의 `effective_parallel`을 검증한다.
- [ ] Browser `iab` 이미지 확인이 필요한 post는 스크롤/대기 후 `placeholder/lazy/loading` 잔존 여부를 기록한다.
- [ ] DC 본문 첨부 이미지는 `.write_div .img_area/.imgwrap` 중심으로 세고, 댓글/추천/캡차/광고 이미지를 본문 이미지 수에 섞지 않는다.
- [ ] lazy 이미지가 있으면 각 본문 첨부 이미지를 `scrollIntoView`한 뒤 다시 `loaded/placeholder/incomplete/broken` 상태를 평가한다.
- [ ] 본문 인라인 이미지가 0개라도 `원본 첨부파일`, `download.php`, `viewimagePop.php`가 있으면 attachment popup/direct image를 Browser `iab`로 열고 link count, screenshot, dimension을 기록한다.
- [ ] VLM/OCR closure builder는 `visual_evidence_grade=Strong`만 보지 말고 `article_loaded_count==article_image_count`, `placeholder/incomplete/broken=0`을 함께 확인한다.
- [ ] `naturalWidth=0`, `complete=false`, `gallview_loading_ori.gif`, `data-original` 미교체 이미지가 남으면 VLM/OCR evidence를 `Strong`으로 승격하지 않는다.
- [ ] 첨부 팝업 이미지가 로드돼도 작품 판정 직접 근거가 아니면 `ACCEPT`가 아니라 `HOLD/human_review`로 둔다.
- [ ] 이미지 근거가 필요한데 Browser 확인이 실패하면 `REPROCESS` 또는 `INFO_MISSING`로 라벨링하고 semantic `GO`에서 제외한다.
- [ ] 외부 매체 IP, 웹툰/만화/COMIC 플랫폼 URL, 파생 팬픽 URL은 웹소설 official title evidence로 세기 전에 별도 media-risk guard를 통과시킨다.

## 2026-06-01 추가 운영 체크 - Codex subagent 병렬 / 등록 약칭 evidence gate

- [ ] Codex goal 병렬 요청은 `spawn_agent` 전문가 분업으로 처리하고, repo 내부 `expert_main.py --parallel` worker cap과 혼동하지 않는다.
- [ ] subagent는 read-only 감사 또는 disjoint write scope로 나누고, 최종 gate 판단은 메인 Codex가 통합한다.
- [ ] `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY`는 서로 다른 provenance source로 기록하되, registry hit 자체를 semantic approval evidence로 쓰지 않는다.
- [ ] 등록 약칭이 final title, `High`, stability/lock, guard exception에 관여하면 visible alias surface, semantic no-work 차단 여부, 독립 work anchor를 함께 확인한다.
- [ ] 등록 약칭이 suspected title, high-fit interpretation, weak thematic guard exception에 관여해도 같은 evidence gate를 적용한다.
- [ ] `audit_hardcoded_alias_risk.py` 산출물에서 positive blocker가 남아 있으면 completed source와 expanded review가 있어도 hardcoded alias gate를 별도 `REVIEW`로 둔다.
- [ ] targeted guard 통과, small canary runtime `GO`, hardcoded alias packet label closure를 10만 semantic `GO`로 오독하지 않는다.

## 2026-06-28 추가 운영 체크 - Phase 2 targeted queue closure boundary

- [ ] targeted canary의 next queue `0`은 해당 runnable slice closure일 뿐이다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
- [ ] `slang_store_gate` 실행에서 `store_in_slang_db=true`가 나와도 `--slang-db off`이면 review signal이며 production write-back 승인으로 보지 않는다.
- [ ] `human_review_boundary` row는 runnable canary failure가 아니다. explicit `HOLD`/`human_review` closure rationale을 post_id별로 남긴다.
- [ ] targeted axis closure와 Loop 09 residual, panel/collateral/replay/sweep/source-completion gate를 한 gate로 합치지 않는다.
- [ ] Loop 11 `human_review_boundary=25` closure artifact는 boundary-accounting 근거다. 이를 semantic approval, runtime canary green, 또는 goal completion 근거로 쓰지 않는다.

## 2026-06-30 추가 운영 체크 - Loop 133 source-enriched replay boundary

- [ ] Focused input manifest의 `native_web_seed`는 그 자체로 pipeline evidence가 아니다. `expert_main.py`가 소비하는 JSONL row 또는 precomputed evidence path에 공식 detail/search evidence가 있어야 source-enriched replay로 계산한다.
- [ ] `11705231` focused replay의 runtime `GO`와 Identified `0`을 분리 보고한다.
- [ ] `search_absent_verified_title`로 오타 후보가 null 처리된 것은 precision-safe evidence이지 recall success가 아니다.
- [ ] `설지후` 같은 character-only bridge만으로 `official_title`을 승격하지 않는다. 공식 detail/title evidence 또는 검증된 title abbreviation bridge가 필요하다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-06-30 추가 운영 체크 - Loop 157 stable-alias descriptor boundary

- [ ] `search_evidence_alias_inference`나 official-detail 존재만으로 stable alias correction을 승인하지 않는다. 원문에서 alias 표면이 descriptor/high-fit으로 쓰였는지 먼저 확인한다.
- [ ] Decoder가 high/medium-fit descriptor와 low/none-fit title을 동시에 남긴 표면은 public-title replacement가 아니라 candidate/hold 쪽으로 취급한다.
- [ ] `상남자라서`처럼 조사/어미가 붙은 성격 묘사 표현을 title alias로 승격하지 않는다.
- [ ] Loop157 단일 seed recovery를 parent replay, panel/golden/collateral, repeated replay, full sweep approval로 오독하지 않는다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-06-30 추가 운영 체크 - Loop 158 parent replay boundary

- [ ] Parent replay runtime `GO`는 semantic approval이 아니다.
- [ ] `11698880` parent recovery는 stable-alias descriptor guard의 범위 확인일 뿐, panel/golden/collateral closure가 아니다.
- [ ] `11668288`처럼 이전 parent baseline에서 resolved였다가 null로 돌아간 row는 precision-safe hold인지 recall regression인지 별도 판정한다.
- [ ] `11706832`처럼 degraded search에서 title이 바뀐 row는 native/source evidence 없이 approval로 세지 않는다.
- [ ] Loop158 movement counts는 단순 변화량으로만 채택/거절하지 말고 golden/expected direction과 대조한다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-07-01 추가 운영 체크 - Loop 229 title-led bridge boundary

- [ ] 제목에 `볼만함`, `재밋네` 같은 평가/소비 표지가 있어도 final public title이 비어 있으면 residual closure로 세지 않는다.
- [ ] `promotion_decision.scope.scope_kind=current_work`와 `serialized_public_identity_scrubbed`가 동시에 나오면 architecture conflict로 기록한다.
- [ ] `weak_alias_surface_public_title_bridge`가 남아 있는 locked official detail 후보는 public publish가 아니라 candidate preservation 상태로 판독한다.
- [ ] recommendation/non-novel force path가 title-led evaluation question을 먼저 압도한 경우, official detail 후보 rescue 실패를 semantic approval이 아니라 architecture blocker로 남긴다.
- [ ] Loop229 two-row canary runtime `GO`와 final public title `0/2`를 분리 보고한다.
- [ ] `NO_DELTA_TITLE_LED_BRIDGE_CANARY_NO_GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-07-01 추가 운영 체크 - Loop 230 title-led serializer/gate boundary

- [ ] 신규/갱신 report, loop report, review Markdown, Data Analytics reader-facing artifact는 한국어로 작성한다.
- [ ] 간략하게 쓰되 의미, 근거, 산출물 경로, gate 상태를 생략하지 않는다.
- [ ] enum, 명령어, 파일 경로, URL은 필요한 경우 원문 그대로 둔다.
- [ ] Loop230 public title `1/2`는 targeted partial recovery이며 residual closure가 아니다.
- [ ] `11660257` recovery는 parent/representative replay 전까지 stable recovered evidence로 세지 않는다.
- [ ] `11660237` `promotion_blocked`는 source/native evidence 없이 강제 publish하지 않는다.
- [ ] 중간 noise/community-banter force 로그와 final publish 결론이 충돌하는 row는 parent replay에서 `publish_contract_trace`, `publish_ledger`, `promotion_decision`, serialized `novel_identity`를 함께 비교한다.
- [ ] `NO_DELTA_TITLE_LED_SERIALIZER_CANARY_PARTIAL_RECOVERY_PARENT_REPLAY_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-07-02 추가 운영 체크 - Loop 281 long-running live process caveat

- [ ] 장기 실행 중 코드 패치를 한 경우, 이미 시작된 worker process에는 패치가 적용되지 않았음을 health/report에 명시한다.
- [ ] pre-patch worker trace가 남은 live run은 `failed=0`으로 계속 전진해도 completed-source approval 후보로 승격하지 않는다.
- [ ] `publication_contract_convergence=GO`는 flushed row contract 수렴만 뜻한다. search evidence `REVIEW`, `large_run_complete=false`, completed-source candidate `0`이면 semantic approval로 세지 않는다.
- [ ] completed source 후보가 생기기 전까지 random baseline 1000, P0/P1 high-risk expansion, full375 collateral approval을 열지 않는다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-07-02 추가 운영 체크 - Loop 282 ordered flush frontier 병목

- [ ] `completed_count`가 증가해도 `flushed_count/result_rows`가 증가하지 않으면 `next_save_idx` frontier를 먼저 확인한다.
- [ ] frontier가 checkpoint와 pending snapshot 양쪽에 없으면 worker log lifecycle을 확인해 in-flight, stuck, failed-missing을 분리한다.
- [ ] work evidence와 recommendation guard가 충돌해 Jury/Debate로 길어지는 row는 runtime failure로 단정하지 않는다.
- [ ] 장기 심의 row가 flush를 막는 동안 뒤쪽 completed rows를 completed source approval 근거로 쓰지 않는다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-07-02 추가 운영 체크 - Loop 283 frontier release 후속

- [ ] 이전 frontier가 풀렸더라도 새 `next_save_idx` frontier가 생기면 completed source로 보지 않는다.
- [ ] `completed_count`가 계속 증가하고 `flushed_count`가 고정되면 behind completed rows를 approval source로 쓰지 않는다.
- [ ] 이미지/OCR direct title과 community-meta 해석이 충돌해 Jury/Debate로 길어지는 row는 worker log 단계와 manifest frontier를 함께 기록한다.
- [ ] completed source 후보 감사는 `approval_source_candidate_count=0`이면 full375 collateral approval을 열지 않는다.
- [ ] `publication_contract_convergence=GO`는 flushed row contract 수렴만 뜻하며, search evidence `REVIEW` 또는 completed-source candidate `MISSING`을 덮지 않는다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-07-02 추가 운영 체크 - Loop 284 frontier chain release 경계

- [ ] released frontier가 safe_resolved로 완료되어도, 새 `next_save_idx` frontier가 있으면 completed-source approval 후보로 보지 않는다.
- [ ] same-packet safe_resolved 단조 비감소는 후퇴 증거 없음만 의미한다. completed-source, search evidence, full375 collateral gate를 대체하지 않는다.
- [ ] `Fate/stay night`처럼 작품 내부 키워드가 강해도 제목-본문 불일치/텍스트 복사 오류가 실제 담론이면 `_post_discusses_work_as_work`와 promotion hard-hold를 우회하지 않는다.
- [ ] `11660237`처럼 flip_rate가 있는 row는 stable blind judge evidence 없이 hard-hold를 완화하지 않는다.
- [ ] completed behind rows가 늘어도 `flushed_count/result_rows`와 `next_save_idx` frontier를 우선 확인한다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.

## 2026-07-02 추가 운영 체크 - Loop 308 collateral triage boundary

- [ ] collateral bucket source-native triage가 `26/26` 완료돼도 `REPROCESS`가 남으면 full collateral approval을 열지 않는다.
- [ ] `ACCEPT` verdict는 regression count 재분류 후보일 뿐, gate wiring과 replay 전에는 approval evidence가 아니다.
- [ ] `REPROCESS` verdict는 shared promotion gate repair queue로 옮기고, row별 rationale을 보존한다.
- [ ] 대형 run이 `IN_PROGRESS`이고 search blockers가 있으면 health 증가분을 completed-source approval로 쓰지 않는다.
- [ ] `promotion_blocked`는 search 복구 전까지 `search-blind conditional`로 태깅한다.
- [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `NOT_COMPLETE`를 유지한다.
