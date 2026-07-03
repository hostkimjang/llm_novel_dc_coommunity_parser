# GOAL: Architecture-Integrated Regression-Safe Grounding Loop

## Purpose

현재 개선 하네스 goal은 완료가 아니다. Loop176 기준 broader unittest gate가 `FAIL`이며, 전문가 협업 결과 현재 구조는 단건 guard 누적으로는 한계가 있다고 판단했다. 따라서 다음 goal은 기존 residual queue를 버리는 것이 아니라, 먼저 공통 title-promotion 아키텍처를 추가한 뒤 Loop176 실패와 residual queue로 복귀하는 architecture-integrated goal로 변경한다.

보고서 작성 규칙: 모든 loop report와 goal addendum은 한국어로 작성한다. 간략하게 쓰되 의미, 근거, 산출물 경로, run/semantic/full-scan 게이트 상태를 생략하지 않는다.

## 2026-07-03 Loop356 Addendum - current HEAD background dispatch

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop356은 approval 회차가 아니라 Loop355 이후 현 HEAD `4ebe824b`에서 stale flip/golden/full375/bounded 증거를 갱신할 background run을 새 prefix로 발주한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_356_REPORT_20260703.md`, state `docs/devs/loop356_current_head_background_dispatch_20260703.json`, shard audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop356_search_shard_audit_44_before_current_head_dispatch.json`.
- Dispatch: safe-loss N5 PID `120600`, full375 PID `67072`, bounded1200 PID `140096`, golden18 PID `113216`.
- Health: shard audit `35/44` OK, bad shard `1`, `37-44`; 새 런 manifest는 모두 `mcp_health_include_search=true`, `mcp_health_light_mode=false`.
- Boundary: N5 `15/15`, golden18 `18/18`, full375 `375/375`, bounded completion 전에는 stale flip `0.333`, 2026-06-28 golden `GO`, 과거 full375 증거를 대체하지 않는다.
- Gate: dispatch `GO_CURRENT_HEAD_BACKGROUND_DISPATCH`, runtime completion `IN_PROGRESS / NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop355 Addendum - wrong-work alias contract reinforcement

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop355는 approval 회차가 아니라 `repair_after_wrong_work=5` 중 `11698890`, `11700500`, `11705252` 3행의 known-title-abbreviation work bridge 계약을 보강한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_355_REPORT_20260703.md`, state `docs/devs/loop355_wrong_work_alias_contract_20260703.json`, code `src/llm_batch/experts/utils.py`, tests `tests/test_known_title_abbreviation_support.py`.
- Contract: `댓천마`, `전1시`, `탐재`는 registry 단독 publish 권한이 아니라 글 안의 작품 내부 cue와 official detail recall이 함께 있을 때만 승격된다.
- Verification: related unittest `63`개 PASS.
- Queue: residual action queue `105`, queue delta `0`, runtime closure `0`.
- Gate: contract `GO_UNIT_CONTRACT_ONLY`, runtime closure `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop354 Addendum - current residual forced action lane

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop354는 approval 회차가 아니라 대형 forced non-light 런을 background 감시로 유지하고 active loop를 current residual `105` action lane으로 강제 전환한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_354_REPORT_20260703.md`, state `docs/devs/loop354_current_residual_forced_action_lane_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop354_current_residual_forced_action_lane.json`.
- Queue: residual action queue `105`, `REPROCESS=77`, `HOLD=28`, `safe_loss_resolved_to_null=100`, `wrong_work_title_flip=5`, validation issue `0`.
- Background: N5/full375/bounded1200/golden18 PIDs는 alive지만 full375 checkpoint `4`, bounded checkpoint `8`, golden18 checkpoint `1` 수준이라 approval 근거가 아니다.
- Forced lanes: 다음 active 후보는 `repair_after_wrong_work=5` source-native/stall-root-cause review 또는 `known_alias_runtime_replay_required=3` contract/runtime replay다.
- Gate: forced action lane `GO_QUEUE_RESHAPE_NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=105`, large runs `IN_PROGRESS_OR_PARTIAL / NOT_APPROVAL`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop353 Addendum - 11708470 non-light row closure

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop353은 approval 회차가 아니라 Loop352 residual `106`에서 Loop324 non-light runtime으로 clean row recovery가 확인된 `11708470` 1건을 제외한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_353_REPORT_20260703.md`, state `docs/devs/loop353_11708470_nonlight_row_closure_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop353_current_residual_action_queue_after_11708470_nonlight_runtime_closure.json`.
- Runtime basis: Loop324 runtime은 completed/flushed/pending/failed `7/7/0/0`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`, health `2/0`이다.
- Row decision: `11708470`은 `절꺾않 -> 절대 꺾이지 않을거야!`, Loop323 `promotion_blocked`에서 Loop324 `safe_resolved`로 이동했고 search degraded가 없었다.
- Queue transition: residual action queue `106 -> 105`, `REPROCESS=78 -> 77`, `HOLD=28`, `repair_safe_loss=73 -> 72`, validation issue `0`.
- Gate: row closure `GO_ROW_NONLIGHT_RUNTIME_NOT_APPROVAL`, packet semantic `NO-GO / Loop324 safe_resolved=2/7`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop352 Addendum - unsafe-promotion contract exclusion

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop352는 approval 회차가 아니라 Loop349 residual `120`에서 이미 현 publication contract로 hold 수렴한 `repair_unsafe_promotion=14`를 중복 queue에서 제외한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_352_REPORT_20260703.md`, state `docs/devs/loop352_unsafe_promotion_contract_exclusion_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop352_current_residual_action_queue_after_unsafe_promotion_contract_exclusion.json`.
- Contract basis: Loop300/309 current contract replay가 `REPROCESS=14 -> promotion_blocked=14/14`를 이미 기록했다. 따라서 이 14건은 새 code repair queue가 아니라 중복 residual 표기로 본다.
- Queue transition: residual action queue `120 -> 106`, `REPROCESS=92 -> 78`, `HOLD=28`, `repair_unsafe_promotion=14 -> 0`, validation issue `0`.
- Stop condition: actionable queue 감소는 충족했지만, 이번 회차는 safe_resolved 증가가 아니라 over-promotion 차단 수렴 제거이므로 approval이나 hard-hold 완화 근거가 아니다.
- Gate: queue delta `GO_QUEUE_DELTA_NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=106`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop351 Addendum - stale evidence background audit

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop351은 approval 회차가 아니라 Loop348 forced non-light stale evidence refresh 발주의 현재 completion 상태를 감사하고, 코드 변경 없음 3연속 조건에 따라 대형 런을 background 감시로 내린 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_351_REPORT_20260703.md`, state `docs/devs/loop351_stale_evidence_background_audit_20260703.json`.
- HEAD: 관찰 HEAD는 `2e1d09b0`이고 Loop348 dispatch HEAD `462ec714` 이후 diff는 docs only다. runtime code는 동일하지만 completed evidence는 manifest/result로만 판정한다.
- Runtime snapshot: N5 first `1/0/0/0/0`, full375 `375/1/1/0/0`, bounded completed-source `1200/4/0/4/0`, golden18 `18/1/1/0/0`. stale flip `0.333` 또는 2026-06-28 golden GO를 대체하지 않는다.
- Tracking: golden18 `11660237`, `11698880` 편입 파일은 git 추적 중이다. Loop351에서 search recovery probe `tools/run_search_query_expansion_probe.py`를 git 추적 예외에 추가했다.
- Queue: active 기준은 Loop349 residual `120`, `REPROCESS=92`, `HOLD=28`, `repair_safe_loss=73`, `repair_unsafe_promotion=14`, `repair_after_wrong_work=5`, validation issue `0`.
- Gate: stale evidence refresh `INCOMPLETE / NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=120`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop350 Addendum - repair_after_wrong_work runtime stall

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop350은 approval 회차가 아니라 residual `120`의 `repair_after_wrong_work=5`를 current HEAD runtime으로 확인하려 한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_350_REPORT_20260703.md`, state `docs/devs/loop350_repair_after_wrong_work_runtime_stall_20260703.json`, manifest `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop350_repair_after_wrong_work_5_current_head_44de6d74_search_nonlight_result_manifest.json`.
- Runtime: run `20260703_140627_312360`, input rows `5`, requested/effective parallel `4/4`, endpoints `3334..3337`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`, health `4/0`, VLM/OCR ready.
- Stall: W0은 gatekeeper LLM stream 시작 후, W1/W2/W3은 VLM chunk request 후 로그 갱신이 없었다. manifest는 completed/flushed/pending/failed `0/0/0/0`이고 PID `12064`는 중단했다.
- Queue transition: `NO_DELTA`; residual action queue `120`, `repair_after_wrong_work=5`, `REPROCESS=92`, `HOLD=28` 유지.
- Gate: runtime health `GO_SEARCH_NONLIGHT_HEALTH`, targeted completion `ABORTED_RUNTIME_STALL / NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=120`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop349 Addendum - canonical variant HOLD quarantine

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop349는 approval 회차가 아니라 Loop348 current residual `122` 중 canonical variant 정책 HOLD 2건을 active code repair queue에서 분리한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_349_REPORT_20260703.md`, state `docs/devs/loop349_canonical_variant_quarantine_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop349_current_residual_action_queue_after_canonical_variant_quarantine.json`.
- Row decision: `11663535`는 Loop82-83/Loop251 근거상 public title/url `null`, `promotion_blocked`, `publish_allowed=false`로 유지하고 `퇴마록` 계열 canonical variant quarantine으로 둔다. `11706871`은 Loop83에서 `파우스트 1` 승격이 차단됐으므로 `파우스트`/`파우스트 1` canonical variant quarantine으로 둔다.
- Queue transition: residual action queue `122 -> 120`, `REPROCESS=92`, `HOLD=28`, wrong-work title flip residual `7 -> 5`, validation issue `0`.
- Background caveat: Loop348 forced non-light N5/full375/bounded1200/golden18은 계속 running background이며 completion/approval 근거가 아니다.
- Gate: canonical variant quarantine `GO_QUEUE_DELTA_NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=120`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop347 Addendum - remaining known-alias contract plus VLM stall

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop347은 approval 회차가 아니라 남은 `known_alias_runtime_replay_required=3` 재실행 시도와 code contract 보강 회차다.
- Runtime evidence: run `20260703_131039_800703`, input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop347_known_alias_remaining3_targeted_input.jsonl`, manifest completed/flushed/pending/failed `0/0/0/0`, search health `2/2 OK`, VLM chunk 이후 stall로 중단.
- Code evidence: `11706827 / 기계공주 / 일상물`, `11714907 / 아생갤 / 작가·정실·라나`를 shared curated-alias work cue 계약으로 고정했다. `11708443`은 기존 Loop324/325 계약이 남아 있으나 이번 runtime에서 flush되지 않았다.
- 검증: py_compile PASS, safe-loss contract `11` tests PASS, shared work bridge focused `7` tests PASS, arbiter focused `6` tests PASS, `git diff --check` PASS.
- Gate: runtime replay `ABORTED_VLM_STALL / NOT_APPROVAL`, code contract `GO_UNIT_CONTRACT_ONLY`, residual queue `NO_DELTA / remains 123`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop343 Addendum - post-patch verified alias runtime replay

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop343은 approval 회차가 아니라 Loop342 패치가 실제 runtime output에 반영되는지 확인한 post-patch targeted replay 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_343_REPORT_20260703.md`, state `docs/devs/loop343_post_patch_alias_runtime_replay_20260703.json`, result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop343_known_alias_seed_post_patch_9daf715f_search_nonlight_result.json`, manifest `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop343_known_alias_seed_post_patch_9daf715f_search_nonlight_result_manifest.json`, convergence `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop343_goal_convergence_after_runtime_replay.json`.
- Runtime: run `20260703_093839_730466`, HEAD `9daf715f`, completed/flushed/pending/failed `2/2/0/0`, `large_run_complete=true`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`, `vlm_ocr_semantic_review_ready=true`.
- Result: 동일 packet 기준 `safe_resolved 0/2 -> 2/2`, `promotion_blocked 2 -> 0`, safe loss `0`. `11703624`는 `판초우의의 마법사`와 Munpia URL로 safe_resolved, `11705251`은 `월야환담 창월야` title-only safe_resolved다.
- Stop condition: evaluator는 actionable queue `126 -> 124`, `same_packet=true`, `safe_resolved_monotonic_nondecrease=true`, gate `GO`를 기록했다. 이 GO는 targeted packet 한정이며 전체 goal 정지가 아니다.
- Gate: targeted runtime completion `GO`, targeted packet convergence `GO`, collateral `NO-GO / residual_action_queue_rows=124`, golden18/full375 `NOT_RERUN_AFTER_PATCH`, search recovery `P0 / OPEN / SEARCH_DEGRADED observed`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop342 Addendum - verified alias title-only publication gate

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop342는 approval 회차가 아니라 Loop341 alias seed 2건의 targeted runtime replay와 그 결과에서 확인된 verified alias title-only 복구 계약을 추가한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_342_REPORT_20260703.md`, state `docs/devs/loop342_verified_alias_title_only_publication_20260703.json`, result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop342r2_known_alias_seed_targeted_current_head_71e27ce0_search_nonlight_result.json`, manifest `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop342r2_known_alias_seed_targeted_current_head_71e27ce0_search_nonlight_result_manifest.json`.
- Runtime: run `20260703_075717_945280`, completed/flushed/pending/failed `2/2/0/0`, `large_run_complete=true`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`, `vlm_ocr_semantic_review_ready=true`.
- Result: 런 당시 `11703624`, `11705251` 모두 public `promotion_blocked`였으나, 패치 후 contract sync preview에서 `11705251`만 `official_title=월야환담 창월야`, `official_url=null`, `safe_resolved=true`, publish `true`로 복구된다. `11703624`는 generic/adjacent 판정으로 hold 유지다.
- Code: URL title mismatch가 있는 verified alias는 official URL을 공개하지 않고 title-only로 publish할 수 있게 했다. hard negative flag, source support, context source 조건을 만족하지 않으면 계속 차단한다.
- Verification: py_compile PASS, focused title-only/publication `4` PASS, comment metadata `48` PASS, known abbreviation bundle `38` PASS, title-led guard `185` PASS, promotion/candidate audit `128` PASS, work-bridge/convergence/flip-rate/always-on bundle `26` PASS.
- Gate: targeted runtime completion `GO`, targeted contract preview `PARTIAL_GO`, collateral `NO-GO / residual_action_queue_rows=126`, golden18/full375 `NOT_RERUN_AFTER_PATCH`, search recovery `P0 / OPEN / SEARCH_DEGRADED observed`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop341 Addendum - known alias safe-loss contract seed

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop341은 approval 회차가 아니라 Loop340 `known_alias_runtime_replay_required=6` 중 2건만 shared alias/work-cue 계약으로 올린 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_341_REPORT_20260703.md`, state `docs/devs/loop341_known_alias_safe_loss_contract_20260703.json`, source queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop340_collateral183_residual_action_queue.json`.
- 코드 변경: `판초법사 -> 판초우의의 마법사`, `창월야 -> 월야환담 창월야`를 `KNOWN_TITLE_ABBREVIATIONS`에 추가했고, `게이트/정보통제/경찰력/파워밸런스/서열/강한/강함/강캐/약캐`를 curated alias work cue에 추가했다.
- 보류: `11705230`, `11706827`, `11708443`, `11714907`은 registry 중복 또는 exact/policy/search-recovery 성격이라 runtime replay 또는 policy review로 남긴다.
- Runtime caveat: Loop339 background는 `77bdbe48` dispatch 증거라 현재 base `70b39183` 이후 패치의 승인 근거가 아니다. 최신 관찰은 full375 `1/1/0/0`, bounded1200 r2 `6/0/6/0`, golden18 r2 `1/1/0/0`, safe-loss N5 `1/15`다.
- Verification: py_compile PASS, safe-loss contract `9` PASS, abbreviation support `29` PASS, arbiter curated alias guard `21` PASS.
- Gate: code contract `GO_UNIT`, runtime replay `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=126`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop340 Addendum - collateral183 residual action queue

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop340은 approval 회차가 아니라 Loop332/333 collateral183 residual `126`을 실행 가능한 post_id/action group 큐로 분해한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_340_REPORT_20260703.md`, state `docs/devs/loop340_collateral183_residual_action_queue_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop340_collateral183_residual_action_queue.json`.
- Result: source rows `183`, residual `126`, `REPROCESS=95`, `HOLD=31`, action groups `30`, validation issues `0`.
- 주요 group: `repair_safe_loss=76`, `repair_unsafe_promotion=14`, `native_image_or_source_review_required=14`, `known_alias_runtime_replay_required=6`, `repair_after_wrong_work=5`.
- Runtime caveat: Loop339 background는 full375 `1/1/0/0`, bounded1200 r2 `6/0/6/0`, golden18 r2 `1/1/0/0`, safe-loss N5 `0/15`로 모두 `IN_PROGRESS / NOT_APPROVAL`이다.
- Verification: py_compile PASS, `tests.test_split_collateral_action_queue` `2` tests PASS, queue generation `--fail-on-validation-issue` PASS.
- Gate: queue split `GO`, collateral `NO-GO / residual_action_queue_rows=126`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop339 Addendum - current HEAD runtime dispatch

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop339는 approval 회차가 아니라 현 HEAD `77bdbe48`에서 stale flip/golden 증거를 갱신하기 위한 background runtime 재발주 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_339_REPORT_20260703.md`, state `docs/devs/loop339_current_head_runtime_dispatch_20260703.json`.
- Runtime: `mcp-bridge-13..25`를 build/recreate했고 ports `3345..3357` health는 search 포함 non-light 조건에서 OK다. Active runs는 full375 PID `131976` run `20260703_071219_478271`, bounded1200 r2 PID `49024` run `20260703_071356_731873`, golden18 r2 PID `130412` run `20260703_071359_476753`, safe-loss N5 PID `134636`이다.
- Caveat: 최초 bounded/golden 발주는 expert log run-id 충돌로 증거에서 제외했다. 작성 시점 manifest/checkpoint는 full375 `1/1/0/0`, bounded1200 r2 `4/0/4/0`, golden18 r2 `1/1/0/0`, safe-loss N5 `0/15`다. Bounded는 ordered flush 대기라 approval 근거가 아니다.
- Golden: golden set은 `16 -> 18`이고 `11660237`, `11698880`을 포함한다. 단, current HEAD golden18 완료와 audit 전까지 golden approval은 열리지 않는다.
- Gate: all runs `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop338 Addendum - live shard search recovery canary

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop338은 approval 회차가 아니라 Loop337 search recovery 코드를 live shard에 적용하고 단건 runtime canary로 검증한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_338_REPORT_20260703.md`, state `docs/devs/loop338_search_recovery_live_shard1_replay_20260703.json`, result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop338_override_11705250_search_recovery_live_shard1_result.json`, audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop338_override_11705250_search_recovery_live_shard1_health_audit.json`.
- Result: shard 1 `mcp-bridge` 재빌드/재생성 후 direct probe에서 `fallback_recovered=true`, `degraded_recovered=true`를 확인했다. `11705250` run `20260703_061749_804510`은 `1/1/1/0/0`, `large_run_complete=true`, public identity `심해의 마법사`, URL `https://m.munpia.com/novel/detail/483667`, `candidate_ledger_status=safe_resolved`, publication convergence `GO`다.
- Caveat: row search health는 `SEARCH_DEGRADED`이고 `unrecovered_degraded=13`이다. Search 100% recovery는 아직 실패/미해소이며, promotion 완화나 full approval 근거로 쓰지 않는다.
- Gate: live shard apply `GO`, row public contract `GO_ROW_PUBLIC_CONTRACT`, publication convergence `GO`, search recovery `P0 / PARTIAL_RUNTIME_GO / UNRECOVERED_DEGRADED_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop337 Addendum - search degraded recovery contract

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop337은 approval 회차가 아니라 search degraded 복구를 recovered/unrecovered 계약으로 분리한 코드 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_337_REPORT_20260703.md`, state `docs/devs/loop337_search_degraded_recovery_contract_20260703.json`, Loop336 audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop336_override_11705250_post_patch_f232f31a_search_nonlight_health_audit.json`.
- Result: bridge filter collapse(`raw_total>=10` 후 `no_hangul`/`token_mismatch` 전량 탈락)를 direct fallback 사유로 올리고, `fallback_recovered`, `degraded_recovered`, `unrecovered_degraded`를 public health/audit에 노출한다.
- Caveat: 현재 실행 중인 bridge 컨테이너는 repo bind mount가 아니며 이번 코드가 live shard에 적용되지 않았다. 따라서 runtime replay는 `NOT_RUN_AFTER_REBUILD`이고 approval 근거가 아니다.
- Verification: py_compile PASS, recovery/direct tests `10` PASS, health audit tests `16` PASS.
- Gate: code contract `GO_UNIT`, live shard `NOT_APPLIED_TO_RUNNING_CONTAINERS`, search recovery `P0 / PARTIAL_CODE_ONLY / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop336 Addendum - 11705250 post-patch runtime replay and sequential manifest contract

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop336은 approval 회차가 아니라 Loop335 패치의 단건 runtime replay와 순차 manifest 계약 보정 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_336_REPORT_20260703.md`, state `docs/devs/loop336_post_patch_runtime_replay_20260703.json`, result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop336_override_11705250_post_patch_f232f31a_search_nonlight_result.json`, audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop336_override_11705250_post_patch_f232f31a_search_nonlight_health_audit.json`.
- Result: `11705250`은 `official_title=심해의 마법사`, `heretic_url=https://m.munpia.com/novel/detail/483667`, `candidate_ledger_status=safe_resolved`, `promotion_blocked=false`로 복구됐다. `publication_contract_convergence=GO`, violation `0`이다.
- Caveat: search health는 `SEARCH_DEGRADED`, audit `search_evidence=REVIEW`, blocker `search_degraded_observed`다. 따라서 row replay가 좋아져도 full approval은 열지 않는다.
- 코드 변경: `expert_main.py` 순차 모드 manifest에 `large_run_complete`, `partial_flush_gap`, `ordered_flush_blocked`, `completed_subset_*` 필드를 추가했다. 현재 Loop336 artifact는 패치 전 manifest라 completion field caveat가 남는다.
- Verification: py_compile PASS, `tests.test_audit_expert_run_health` `16` tests PASS.
- Gate: row replay `GO_ROW_PUBLIC_CONTRACT`, publication convergence `GO`, search evidence `REVIEW`, full375/bounded/golden/N5 `IN_PROGRESS_OR_PARTIAL / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop335 Addendum - consumption title-lead alias repair

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop335는 approval 회차가 아니라 Loop334 `11705250` false negative를 코드 계약으로 수리한 회차다.
- 목적: `심해법사 묵혀둔거...`처럼 제목 첫 토큰 약칭 뒤에 작품 소비 cue가 오는 경우를 title-lead alias로 보존해 semantic no-work release context가 정당하게 열리게 한다.
- Evidence: report `docs/devs/loop_reports/LOOP_335_REPORT_20260703.md`, state `docs/devs/loop335_consumption_title_lead_alias_repair_20260703.json`, code `src/llm_batch/agentic_pipeline.py`, test `tests/test_title_lead_search_inferred_guard.py`.
- Result: `11705250` 재현 계약, work-bridge contract, title-lead broader suite가 모두 PASS했다. 그러나 post-patch runtime replay는 아직 `NOT_RUN`이다.
- Verification: py_compile PASS, targeted test PASS, `tests.test_regression_safe_work_bridge_contract` `3` tests PASS, `tests.test_title_lead_search_inferred_guard` `185` tests PASS.
- Gate: code contract `GO_UNIT_AND_BROADER_TITLE_LEAD`, runtime replay `NOT_RUN`, search recovery `P0 / OPEN`, large/background runs `IN_PROGRESS_OR_PARTIAL / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop334 Addendum - override audit 11705250 false negative

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop334는 approval 회차가 아니라 Loop330에서 발주한 `11705250` current HEAD non-light 결과를 blind/source-native로 판정한 회차다.
- 목적: `OVERRIDE AUDIT(LLM=False->final=True)` row를 public publish leak 여부와 false negative 여부로 분리해, 대형 run 대기 대신 actionable queue를 줄인다.
- Evidence: report `docs/devs/loop_reports/LOOP_334_REPORT_20260703.md`, state `docs/devs/loop334_override_audit_11705250_current_head_20260703.json`, review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop334_override_audit_11705250_current_head_blind_source_review.json`.
- Result: current HEAD result는 `1/1/0/0` 완료됐지만 `is_relevant=false`, `work_resolution=none`, `official_title=null`, `SEARCH_DEGRADED`다. 독립 정답은 `심해의 마법사`이므로 row verdict는 `REPROCESS_FALSE_NEGATIVE`다.
- 공개 계약: old light와 current HEAD 모두 public title/url leak은 없다. 따라서 publication leak gate는 `GO_NO_LEAK`지만 row semantic gate는 `NO-GO`다.
- Gate: override audit `NO-GO / REPROCESS_FALSE_NEGATIVE / SEARCH_DEGRADED`, search recovery `P0 / OPEN`, large/background runs `IN_PROGRESS_OR_PARTIAL / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop333 Addendum - collateral gate accounting

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop333은 approval 회차가 아니라 Loop332 source-native summary를 상시 375 collateral gate accounting에 배선한 회차다.
- 목적: `ACCEPT=57`을 chat/report 수준의 제외 후보로 남기지 않고, clean review summary 조건을 통과할 때만 raw collateral regression count에서 차감한다.
- Evidence: report `docs/devs/loop_reports/LOOP_333_REPORT_20260703.md`, state `docs/devs/loop333_collateral_gate_accounting_20260703.json`, gate `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop333_always_on_collateral183_adjusted_gate.json`.
- Result: raw `collateral_regression_count=183`, exclusion candidates `57`, review adjustment applied `true`, adjusted collateral regression count `126`.
- 코드 변경: `tools/evaluate_always_on_regression_gates.py`에 `--collateral-review-summary`를 추가하고, dirty/partial review summary 차감 금지 및 adjusted residual blocker를 계약화했다.
- Verification: py_compile PASS, `tests.test_always_on_regression_gates` `8` tests PASS.
- Gate: always-on `NO-GO`, golden `NO-GO / NOT_AUDITED_CURRENT_HEAD`, collateral `NO-GO / adjusted_regression_count=126`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop332 Addendum - collateral183 combined action queue

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop332는 approval 회차가 아니라 코드 변경 없는 대형 run 대기 흐름을 `collateral183` active triage로 전환한 회차다.
- 목적: `loop291`, `loop300`, `loop321`에 흩어진 source-native verdict를 `loop290` 원본 batch 기준으로 합산해 gate accounting과 repair queue가 사용할 현재 action queue를 만든다.
- Evidence: report `docs/devs/loop_reports/LOOP_332_REPORT_20260703.md`, state `docs/devs/loop332_collateral183_combined_queue_20260703.json`, combined summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop332_collateral183_combined_source_native_queue.json`.
- Result: `183/183` reviewed, validation issues `0`, `ACCEPT=57`, `REPROCESS=95`, `HOLD=31`, regression count 제외 후보 `57`, 잔여 action queue `126`.
- 코드 변경: `tools/summarize_collateral_review_verdicts.py`가 다중 `--verdicts` 입력, `queue_transition`, `queue_by_bucket`, duplicate verdict `NO-GO`를 지원한다.
- Verification: py_compile PASS, `tests.test_summarize_collateral_review_verdicts` `6` tests PASS, collateral/goal/gate 관련 bundle `25` tests PASS.
- Runtime snapshot: full375 `12/6/6/0`, bounded1200 `20/7/13/0`, golden18 `3/3/0/0`, override `11705250` `0/0/0/0`; 모두 approval 근거가 아니다.
- Gate: collateral source-native queue `REVIEW-LOCKED / COMPLETE_183_OF_183 / NOT_APPROVAL`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop331 Addendum - current HEAD partial runtime NO-GO refresh

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop331은 approval 회차가 아니라 현 HEAD `c033dd97` background/targeted 산출물을 감사 시점 스냅샷으로 다시 확인해 stale flip/golden 증거를 대체할 수 없음을 확정한 회차다.
- Evidence: report `docs/devs/loop_reports/LOOP_331_REPORT_20260703.md`, state `docs/devs/loop331_current_head_partial_runtime_no_go_20260703.json`, health audits `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop331_*_health_audit.json`, N5 partial review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop331_safe_loss_flip_rate_n5_current_head_partial_review.json`.
- Runtime snapshot: post-patch `11668283`은 `1/1/0/0` 완료됐지만 `official_title=null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=adjacent`, `SEARCH_DEGRADED`라 Loop328 guard patch runtime 수렴 실패다. full375 `6/1/5/0`, bounded1200 `14/6/8/0`, golden18 `2/2/0/0`, safe-loss N5 `1/15`, override `11705250` `0/0/0/0`은 모두 approval 근거가 아니다.
- Data Analytics validation: current HEAD evidence는 search 포함 non-light이지만 grain이 partial checkpoint라 `Needs revision`이다. 2026-06-28 golden GO와 stale flip rate는 current HEAD 완료 증거로 대체되지 않았다.
- Gate: post-patch `11668283` targeted canary `NO-GO`, full375/bounded/golden/N5/override `IN_PROGRESS_OR_RUNNING_BACKGROUND / NOT_APPROVAL`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop330 Addendum - current HEAD health and override audit transition

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop330은 approval이 아니라 Loop329 current HEAD background run을 최신 health로 감사하고, 대형 런 대기 흐름을 `OVERRIDE AUDIT(LLM=False->final=True)` 단건 current HEAD non-light 검증으로 전환한 회차다.
- 목적: full375/bounded/golden/N5 완료를 기다리며 같은 상태만 반복하지 않고, old light run의 override 후보를 current HEAD non-light 입력으로 재검증할 수 있게 한다.
- Evidence: report `docs/devs/loop_reports/LOOP_330_REPORT_20260703.md`, state `docs/devs/loop330_current_head_health_override_audit_20260703.json`, health audits `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop330_*_health_audit.json`.
- Runtime snapshot: post-patch `11668283` `0/0/0/0`, full375 `3/1/2/0`, bounded1200 `7/2/5/0`, golden18 `1/1/0/0`, safe-loss N5 first run `0/0/0/0`; 모두 완료 전이라 approval 근거가 아니다.
- Override audit: old light `20260702_065642_030743`에서 `LLM=False -> final=True` 후보 `93`건, 미검토 checkpoint 후보 `91`건을 확인했고, `11705250 / 심해법사 묵혀둔거 간만에 보니까 ㄹㅇ 맛있네`를 current HEAD non-light 단건 PID `93016`, run `20260703_034549_939485`로 발주했다.
- Verification: `11705250` launch health는 `mcp_health_include_search=true`, `mcp_health_light_mode=false`, `1/1` OK이고, Loop329 계열의 PowerShell `utf-8` launch warning은 이번 wrapper에서 재발하지 않았다. 다만 검색 단계에서 `search_degraded_detected=6`, `search_upstream_zero=2`가 관측됐다.
- Gate: Loop329 runtime `IN_PROGRESS / NOT_APPROVAL`, override audit `11705250` `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD / SEARCH_DEGRADED_OBSERVED`, safe-loss flip `RUNNING_BACKGROUND / NOT_ANALYZED`, golden18 `APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop329 Addendum - current HEAD c033dd97 runtime dispatch

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop329는 approval이 아니라 Loop328 guard patch 커밋 뒤 runtime 증거를 현 HEAD `c033dd97` 경로로 재발주한 회차다.
- 목적: stale Loop314/Loop326 증거를 끊고, post-patch `11668283` single replay, safe-loss N5, full375, bounded1200 completed-source, golden18을 search 포함 non-light로 다시 시작한다.
- Evidence: report `docs/devs/loop_reports/LOOP_329_REPORT_20260703.md`, state `docs/devs/loop329_current_head_c033dd97_runtime_dispatch_20260703.json`, review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop329_current_head_c033dd97_runtime_dispatch_review.json`.
- Stale handling: Loop314/Loop326 root PID `111032`, `75828`, `9908`, `43208`, `106428`, `34796`, `124704`, `73076`은 중단했고 기존 산출물은 `reference-only / NOT_APPROVAL`이다.
- Launch: post-patch single PID `75828`, full375 PID `3232`, bounded1200 PID `119924`, golden18 PID `95980`, safe-loss N5 PID `107596`.
- Verification: post-patch single `1/1`, full375/bounded `12/12`, golden18 `2/2` launch health OK, N5 first marker 생성. 모두 `mcp_health_include_search=true`, `mcp_health_light_mode=false`다.
- Gate: launch health `GO_SEARCH_NONLIGHT_INITIAL`, post-patch single/N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop328 Addendum - known-abbreviation exact-title public guard repair

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop328은 approval이 아니라 Loop327 patch 후 runtime replay에서 재현된 public serializer overblock을 unit-level guard contract로 수리한 회차다.
- 목적: exact title 감상글이 known-abbreviation current-work scope로 수렴했는데도 official detail URL 부재만으로 public title이 지워지는 병목을 좁게 해소한다.
- Evidence: report `docs/devs/loop_reports/LOOP_328_REPORT_20260703.md`, state `docs/devs/loop328_known_abbreviation_exact_title_guard_20260703.json`, review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop328_known_abbreviation_exact_title_guard_review.json`.
- Runtime: run `20260703_020949_643836`, `1/1/0/0`, search non-light. 결과는 `is_relevant=true`, blocked title `게임 마인드의 중세 현대인`, public title `null`.
- 코드 변경: `candidate_audit.py`에서 `known_abbreviation_title_guard:*` current-work scope + exact title surface + work consumption marker + row work discussion 조건일 때만 weak-source guard를 면제하고, `좋았다` cue를 title-led consumption regex에 동기화했다.
- Verification: py_compile PASS, focused guard `2/2` PASS, existing title-led controls `2/2` PASS, related known-title/arbiter/work-bridge bundle `33/33` PASS.
- Gate: code contract `GO_UNIT`, runtime replay `PRE_PATCH_REPRODUCED_OVERBLOCK / NOT_APPROVAL`, post-patch runtime replay `NOT_RUN_AFTER_GUARD_PATCH`, Loop326 background `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop327 Addendum - override audit middle-age-modern alias repair

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop327은 approval이 아니라 `OVERRIDE AUDIT(LLM=False->final=True)` 확장 중 `11668283` false negative를 찾아 unit-level alias repair로 전환한 회차다.
- 목적: 코드 변경 없는 대형 run 대기 대신 override audit/source-native 검증으로 actionable queue를 줄인다.
- Evidence: report `docs/devs/loop_reports/LOOP_327_REPORT_20260703.md`, state `docs/devs/loop327_override_audit_middle_age_modern_alias_20260703.json`, review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop327_override_audit_middle_age_modern_alias_review.json`.
- 판정: 최신 light run은 `off_topic / context_only / official_title=null`, 과거 독립 run은 `게임 마인드의 중세 현대인` official detail URL resolved다.
- 코드 변경: `중세현대인`, `중세 현대인`, `게임마인드중세`, `게임마인드 중세 현대인` alias와 `좋았다` 계열 curated alias work cue를 추가했다.
- Verification: py_compile PASS, focused unit `9` PASS, related bundle `62` PASS.
- Gate: row contract `GO_UNIT_REPAIR`, runtime replay `NOT_RUN_AFTER_PATCH`, Loop326 background `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop326 Addendum - current HEAD runtime dispatch

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop326은 Loop325 커밋 `1095d447` 이후 safe-loss N5, full375, bounded1200 completed-source, golden18을 current HEAD 기준 새 output 경로로 background 발주한 회차다.
- 목적: 104k run 완료를 기다리지 않고 search 포함 non-light bounded evidence와 full375/golden/N5 증거를 새 HEAD로 갱신한다.
- Evidence: report `docs/devs/loop_reports/LOOP_326_REPORT_20260703.md`, state `docs/devs/loop326_current_head_runtime_dispatch_20260703.json`.
- Launch: N5 PID `73076`, full375 PID `106428`, bounded1200 PID `34796`, golden18 PID `124704`.
- Verification: full375/bounded launch health `12/12` OK, golden18 `2/2` OK, N5 first marker 생성.
- Gate: launch health `GO_SEARCH_NONLIGHT_INITIAL`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, safe-loss N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop325 Addendum - curated alias work-cue contract

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop325는 approval이 아니라 Loop324 `11708443 / 괴담출근` 회귀의 Pipeline/Arbiter cue 불일치를 공통 helper로 수렴시킨 unit/broader contract 회차다.
- 목적: ordinary residual reduction 전에 curated alias promotion gate가 같은 작품 담론 cue를 보도록 한다.
- 코드 변경: `_has_curated_alias_work_discussion_cue`를 추가하고 known-title abbreviation bridge와 Arbiter contextual work anchor가 함께 쓰도록 배선했다.
- Evidence: report `docs/devs/loop_reports/LOOP_325_REPORT_20260703.md`, state `docs/devs/loop325_curated_alias_work_cue_contract_20260703.json`, source review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop324_loop322_alias_targeted_nonlight_review.json`.
- Verification: known-title abbreviation safe-loss contract `8` PASS, Arbiter curated alias guard `21` PASS, py_compile PASS, related work-bridge/title-lead bundle `214` PASS.
- 보호: `괴담텔 ... 괴담동` comparison-only negative는 계속 blocked다.
- Gate: code contract `GO_UNIT_AND_BROADER_214`, runtime replay `NOT_RUN_CURRENT_PATCH`, targeted canary `LOOP324_NO-GO`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop322 Addendum - safe-loss alias shared contract

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop322는 approval이 아니라 Loop321 `repair_safe_loss=76` 중 직접 별칭+작품 소비 cue 7건을 shared promotion gate/known-title abbreviation 계약으로 올린 unit contract 회차다.
- 목적: ordinary residual reduction 전에 shared gate architecture로 반복 safe-loss 표면을 줄인다.
- 코드 변경: `KNOWN_TITLE_ABBREVIATIONS`에 `괴담출근`, `절꺾않`, `무마`, `아카엄창`, `성좌안무서움`, `빌환`, `지구온라인`을 추가하고, work cue에 `표절`, `보러감`을 추가했다.
- 보류: `주전무`는 실제 packet cue가 강하지만 shared cue 폭을 더 넓혀야 하므로 이번 registry 승격에서 제외했다.
- Evidence: report `docs/devs/loop_reports/LOOP_322_REPORT_20260702.md`, state `docs/devs/loop322_safe_loss_alias_contract_20260702.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop322_safe_loss_alias_contract_review.json`.
- Verification: py_compile PASS, safe-loss contract `4` PASS, related alias/arbiter/title-lead bundle `230` PASS, always-on/convergence `12` PASS, actual packet helper check selected `7` allowed and held `주전무=false`.
- Background: Loop314 N5 `4/15`, full375 `36/32/4/0`, bounded1200 `56/52/4/0`, golden18 `14/14/0/0`; 모두 Loop322 코드 이전 background라 approval 근거가 아니다.
- Gate: contract `GO_UNIT_CONTRACT_ONLY`, runtime replay `NOT_RUN`, residual closure `NOT_COUNTED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop321 Addendum - safe-loss source-native queue closure

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop321은 approval이 아니라 Loop301 `safe_loss_resolved_to_null` residual queue를 `119/147`에서 `147/147`로 닫은 source-native review 회차다.
- 목적: Loop314 background run 완료를 기다리지 않고, 남은 safe-loss residual을 source-native/blind 방식으로 먼저 전수 분해한다.
- Evidence: delta `docs/devs/loop321_safe_loss_source_native_verdicts_delta_28.json`, cumulative `docs/devs/loop321_safe_loss_source_native_verdicts_cumulative_147.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop321_safe_loss_source_native_review.json`, report `docs/devs/loop_reports/LOOP_321_REPORT_20260702.md`.
- Result: delta `REPROCESS=15`, `ACCEPT=9`, `HOLD=4`; cumulative reviewed `147/147`, unreviewed `0`, validation issues `0`, cumulative labels `REPROCESS=76`, `ACCEPT=42`, `HOLD=29`.
- Note: 초기 작업 메모의 `16/8/4` 총계는 원문 packet 재확인 후 `15/9/4`로 정정했다.
- Background: Loop314 N5 `3/15`, full375 `30/23/7/0`, bounded1200 `43/35/8/0`, golden18 `11/7/4/0`; 모두 approval 근거가 아니다.
- Gate: source-native review `REVIEW-LOCKED / COMPLETE_SOURCE_NATIVE_QUEUE`, runtime replay `NOT_RUNTIME_VERIFIED`, Loop314 full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop320 Addendum - safe-loss source-native next slice

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop320은 approval이 아니라 Loop301 `safe_loss_resolved_to_null` residual queue를 `104/147`에서 `119/147`로 넓힌 source-native review 회차다.
- 목적: Loop314 background run 완료를 기다리지 않고, 남은 safe-loss residual을 source-native/blind 방식으로 계속 분해한다.
- Evidence: delta `docs/devs/loop320_safe_loss_source_native_verdicts_delta_15.json`, cumulative `docs/devs/loop320_safe_loss_source_native_verdicts_cumulative_119.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop320_safe_loss_source_native_review.json`, report `docs/devs/loop_reports/LOOP_320_REPORT_20260702.md`.
- Result: delta `REPROCESS=8`, `ACCEPT=5`, `HOLD=2`; cumulative reviewed `119/147`, unreviewed `28`, validation issues `0`, cumulative labels `REPROCESS=61`, `ACCEPT=33`, `HOLD=25`.
- Background: Loop314 N5 `3/15`, full375 `24/19/5/0`, bounded1200 `39/19/20/0`, golden18 `9/7/2/0`; 모두 approval 근거가 아니다.
- Gate: source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, Loop314 full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop319 Addendum - OVERRIDE AUDIT 11708445

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop319는 approval이 아니라 `OVERRIDE AUDIT(LLM=False->final=True)` 행의 public publish 누출 여부를 확인한 row-level 계약 검증 회차다.
- 목적: 코드 변경 없는 대형 run 감시/문서 회차가 반복되면 ordinary residual reduction만 계속하지 않고, override audit flip row를 blind/source-native로 확인한다.
- Evidence: review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop319_override_audit_11708445_review.json`, state `docs/devs/loop319_override_audit_11708445_20260702.json`, report `docs/devs/loop_reports/LOOP_319_REPORT_20260702.md`.
- Result: `11708445`는 final public contract에서 `official_title=null`, `official_url=null`, `candidate_ledger_status=promotion_blocked`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `candidate_preserved=true`, `bypassed_gate=false`로 수렴했다. Blind verdict는 `ACCEPT / candidate_only_block_is_correct`다.
- Background: Loop314 N5 `2/15`, full375 `21/17/4/0`, bounded1200 `30/19/11/0`, golden18 `8/7/1/0`; 모두 approval 근거가 아니다.
- Gate: override audit `GO_ROW_CONTRACT_ONLY`, runtime source `BACKGROUND_LIGHT_RUN_NOT_APPROVAL`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop318 Addendum - safe-loss source-native next slice

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop318은 approval이 아니라 Loop301 `safe_loss_resolved_to_null` residual queue를 `89/147`에서 `104/147`로 넓힌 source-native review 회차다.
- 목적: Loop314 background run 완료를 기다리지 않고, 남은 safe-loss residual을 source-native/blind 방식으로 계속 분해한다.
- Evidence: delta `docs/devs/loop318_safe_loss_source_native_verdicts_delta_15.json`, cumulative `docs/devs/loop318_safe_loss_source_native_verdicts_cumulative_104.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop318_safe_loss_source_native_review.json`, report `docs/devs/loop_reports/LOOP_318_REPORT_20260702.md`.
- Result: delta `REPROCESS=5`, `ACCEPT=7`, `HOLD=3`; cumulative reviewed `104/147`, unreviewed `43`, validation issues `0`, cumulative labels `REPROCESS=53`, `ACCEPT=28`, `HOLD=23`.
- Background: Loop314 N5 `1/15`, full375 `11/3/8/0`, bounded1200 `22/6/16/0`, golden18 `5/5/0/0`; 모두 approval 근거가 아니다.
- Gate: source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, Loop314 full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop317 Addendum - safe-loss source-native next slice

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop317은 approval이 아니라 Loop301 `safe_loss_resolved_to_null` residual queue를 `74/147`에서 `89/147`로 넓힌 source-native review 회차다.
- 목적: Loop314 background run 완료를 기다리지 않고, 남은 safe-loss residual을 source-native/blind 방식으로 계속 분해한다.
- Evidence: delta `docs/devs/loop317_safe_loss_source_native_verdicts_delta_15.json`, cumulative `docs/devs/loop317_safe_loss_source_native_verdicts_cumulative_89.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop317_safe_loss_source_native_review.json`, report `docs/devs/loop_reports/LOOP_317_REPORT_20260702.md`.
- Result: delta `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`; cumulative reviewed `89/147`, unreviewed `58`, validation issues `0`, cumulative labels `REPROCESS=48`, `ACCEPT=21`, `HOLD=20`.
- Background: Loop314 N5 `1/15`, full375 `9/3/6/0`, bounded1200 `15/6/9/0`, golden18 `5/5/0/0`; 모두 approval 근거가 아니다.
- Gate: source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, Loop314 full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop316 Addendum - safe-loss source-native next slice

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop316은 approval이 아니라 Loop301 `safe_loss_resolved_to_null` residual queue를 `59/147`에서 `74/147`로 넓힌 source-native review 회차다.
- 목적: Loop314 background run 완료를 기다리지 않고, 남은 safe-loss residual을 source-native/blind 방식으로 계속 분해한다.
- Evidence: delta `docs/devs/loop316_safe_loss_source_native_verdicts_delta_15.json`, cumulative `docs/devs/loop316_safe_loss_source_native_verdicts_cumulative_74.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop316_safe_loss_source_native_review.json`, report `docs/devs/loop_reports/LOOP_316_REPORT_20260702.md`.
- Result: delta `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`; cumulative reviewed `74/147`, unreviewed `73`, validation issues `0`, cumulative labels `REPROCESS=41`, `ACCEPT=15`, `HOLD=18`.
- Gate: source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, Loop314 full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop315 Addendum - character-setting bridge contract

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop315는 approval이 아니라 Loop312 `11669933`의 `회귀수선전` 후보를 shared work bridge 계약으로 고정한 `GO_UNIT_CONTRACT_ONLY` 회차다.
- 목적: 대형 run 완료 대기를 background 감시로 내리고, `중경계/서휼/해방상제`처럼 작품 설정/인물 cluster로 수렴하는 safe-loss를 단순 alias registry가 아니라 character-setting bridge로만 release하게 한다.
- 코드 변경: runtime code는 바꾸지 않았다. 기존 `_post_discusses_work_as_work(...)`가 `_has_deliberated_character_setting_work_convergence(...)`를 경유하는 배선을 positive/negative/소스 계약 테스트로 고정했다.
- Evidence: report `docs/devs/loop_reports/LOOP_315_REPORT_20260702.md`, state `docs/devs/loop315_character_setting_bridge_contract_20260702.json`, verdict `docs/devs/loop312_safe_loss_source_native_verdicts_delta_15.json#post_id=11669933`.
- Verification: py_compile PASS, targeted `3` PASS, related promotion/work-bridge bundle `32` PASS.
- Background: Loop314 full375 `3/1/2/0`, bounded1200 `4/0/4/0`, golden18 `1/1/0/0`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`; 모두 approval 근거가 아니다.
- Gate: character bridge `GO_UNIT_CONTRACT_ONLY`, runtime replay `NOT_RUN`, residual closure `NOT_COUNTED`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop314 Addendum - current-HEAD runtime dispatch

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop314는 approval이 아니라 Loop313 이후 stale/mixed runtime 증거를 current HEAD 경로로 다시 분리한 회차다.
- 목적: Loop288/Loop302 프로세스가 Loop313 이전 코드로 시작됐으므로 current HEAD `64864278` 증거로 오해하지 않게 중단하고 새 background run을 발주한다.
- 코드 변경: `tools/run_independent_plan.py`를 추가했다. `safe_loss_flip_rate_probe.py build-run-plan` 출력 plan을 안정적으로 순차 실행하고 marker/combined 로그를 남긴다.
- Evidence: report `docs/devs/loop_reports/LOOP_314_REPORT_20260702.md`, state `docs/devs/loop314_current_head_runtime_dispatch_20260702.json`, N5 plan `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop314_safe_loss_independent_n5_run_plan.json`.
- Background: N5 PID `111032` result `0/15`, full375 PID `75828` run `20260702_204042_346798`, bounded1200 PID `9908` run `20260702_204042_443948`, golden18 PID `43208` run `20260702_204042_371537`.
- Health: full375/bounded/golden18/N5 first manifest 모두 `mcp_health_include_search=true`, `mcp_health_light_mode=false`다.
- Gate: safe-loss flip `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, golden18 `APPROVAL_NOT_OPEN`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop307 Addendum - safe-loss alias contract expansion

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop307은 approval이 아니라 Loop306 safe-loss alias 후보 일부를 unit-level shared contract로 올린 회차다.
- 목적: 대형 run 대기 대신 source-native alias loss를 계약 테스트로 줄이되, search-blind wrong-work 위험 표면은 보류한다.
- 코드 변경: `KNOWN_TITLE_ABBREVIATIONS`에 `럽코빙의`, `빚세구`, `마줍`, `여신애호`, `별품소`를 추가하고, known-abbreviation work cue를 `연중`, `웹툰`, `결말`, `보러간`, `전생`, `주인공`, `이세계`, `정체`, `설정`으로 보강했다.
- Evidence: report `docs/devs/loop_reports/LOOP_307_REPORT_20260702.md`, state `docs/devs/loop307_safe_loss_alias_contract_expansion_20260702.json`, flip review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop307_safe_loss_flip_rate_n5_current_head_review.json`.
- N5: `11674712` flip_rate `0.4`, `11660237` stable blind judge confirmed, `11698880` flip_rate `0.4`; gate `NO-GO`, hard-hold relaxation `false`.
- Background: full375 `118/105`, bounded1200 `172/167`, 둘 다 `IN_PROGRESS / NOT_APPROVAL`, blocker `search_degraded_observed`.
- Gate: code contract `GO_UNIT`, targeted runtime `NOT_RERUN_AFTER_PATCH`, safe-loss flip `NO-GO`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop306 Addendum - safe-loss source-native next slice review

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop306은 approval이 아니라 Loop301 safe-loss residual source-native review 범위를 넓힌 회차다.
- 목적: Loop305/background run 대기 중에도 `safe_loss_resolved_to_null=147` queue를 source-native로 계속 분해한다.
- Evidence: verdicts `docs/devs/loop306_safe_loss_source_native_verdicts_cumulative_29.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop306_safe_loss_source_native_review.json`, report `docs/devs/loop_reports/LOOP_306_REPORT_20260702.md`.
- Result: reviewed `29/147`, unreviewed `118`, validation issues `0`, labels `REPROCESS=23`, `ACCEPT=4`, `HOLD=2`.
- Gate: source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop305 Addendum - safe-loss alias targeted replay handoff

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop305는 approval이 아니라 Loop304 alias repair의 runtime replay를 시작한 회차다.
- 목적: 코드 변경 없는 대형 run 대기 대신 Loop301 `repair_safe_loss=14` 중 일부 seed를 실제 panel 입력에서 검증한다.
- Evidence: input `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop305_safe_loss_alias_contract_targeted_input.jsonl`, rows `11`, search audit `out/search_shard_audit_20260702_181756.json` `ok=12/12`, run id `20260702_181813_388157`, PID `16380`.
- Runtime: current manifest는 `input=11`, `completed=0`, `flushed=0`, `failed=0`. `11660257`, `11666731`은 VLM chunk result 이후 LLM 단계에 있다.
- Caveat: small-run reuse-only health라 `mcp_health_include_search=false`, `mcp_health_light_mode=true`이다. search recovery나 full approval 증거가 아니다.
- Gate: targeted runtime `IN_PROGRESS / NOT_APPROVAL`, code contract `GO_UNIT`, safe-loss flip `NOT_REFRESHED_CURRENT_HEAD`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop304 Addendum - safe-loss known-alias contract repair

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop304는 approval이 아니라 Loop301 `repair_safe_loss=14` 중 일부 alias seed를 shared known-abbreviation work-cue 계약으로 전환한 회차다.
- 목적: 코드 변경 없는 대형 run 대기 대신 safe-loss queue의 반복 alias loss를 실코드+계약 테스트로 줄인다.
- 코드 변경: `KNOWN_TITLE_ABBREVIATIONS`에 source-native strong alias를 추가하고, `_known_title_abbreviation_update_question_anchor(...)`의 직접 작품 소비/평가 cue를 보강했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_304_REPORT_20260702.md`, state JSON `docs/devs/loop304_safe_loss_alias_contract_repair_20260702.json`, test `tests/test_known_title_abbreviation_safe_loss_contract.py`.
- Evidence: positive alias release 7건과 comparison-only negative control 1건을 계약화했다. Related bundle은 `217` tests PASS다.
- Runtime: targeted replay는 Loop305에서 발주했지만 아직 `IN_PROGRESS / NOT_APPROVAL`; full375/bounded는 background `IN_PROGRESS / NOT_APPROVAL`; search recovery는 `P0 / OPEN`.
- Gate: code contract `GO_UNIT`, safe-loss flip `NOT_REFRESHED_CURRENT_HEAD`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop303 Addendum - runtime recovery and background handoff

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop303은 approval이 아니라 Loop302 runtime blocker를 복구하고 장기 run을 background 감시로 내린 회차다.
- 목적: search shard 복구 여부를 확인하고, N5/full375/bounded/104k를 approval과 분리한 뒤 safe-loss queue로 강제 전환한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_303_REPORT_20260702.md`, state JSON `docs/devs/loop303_current_head_runtime_recovery_20260702.json`, health audits `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop303_*_health_audit.json`.
- Evidence: `3333/3334` health `status=ok`, `headless_search_enabled=true`, MCP bridge container `36`; N5 first row는 official search hit 후 LLM `decoder` 장기화로 foreground 중단; full375 `95/101`, bounded1200 `131/147`, 104k `964/1058` 모두 완료 전이다.
- Forced transition: Loop301 safe-loss queue reviewed/unreviewed `15/132`, `REPROCESS=14`, `ACCEPT=1`; 다음 action은 `repair_safe_loss=14`와 남은 `132` blind/source-native 검토다.
- Gate: search runtime `PARTIAL_RECOVERED`, search degraded `P0 / OPEN`, safe-loss flip `NOT_REFRESHED_CURRENT_HEAD`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop302 Addendum - current HEAD refresh blocked by search runtime

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop302는 approval이 아니라 stale 증거 갱신 시도가 search shard runtime blocker에 막혔음을 기록한 회차다.
- 목적: 현 HEAD `e991a687`에서 safe-loss N5, full375 replay, completed-source bounded non-light run을 갱신한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_302_REPORT_20260702.md`, blocker artifact `docs/devs/loop302_current_head_refresh_blocker_20260702.json`, N5 plan `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop302_safe_loss_independent_n5_run_plan.json`, logs `logs/loop302_safe_loss_independent_n5_plan/*.stderr.log`.
- Evidence: N5 planned runs `15`, missing post ids `[]`, result JSON `0`; `127.0.0.1:3333/3334` 연결 불가; Docker `desktop-linux/default` context 모두 API Internal Server Error; `com.docker.service=Stopped`, `Start-Service` 실패.
- Tracking: `11660237`, `11698880` extra golden row와 golden18 산출물 및 bootstrap/probe/audit 도구는 git 추적 중이다.
- Gate: run integrity `NO-GO_RUNTIME_BLOCKED`, safe-loss flip `NOT_REFRESHED_CURRENT_HEAD`, full375 `NOT_REFRESHED_CURRENT_HEAD`, bounded completed-source `NOT_LAUNCHED_CURRENT_HEAD`, search recovery `P0 / OPEN / LOCAL_DOCKER_SERVICE_BLOCKER`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop301 Addendum - safe-loss seed source-native verdict

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop301은 approval이 아니라 다음 action queue를 `safe_loss_resolved_to_null=147`로 전환하고 seed `15/147`을 source-native verdict로 분해한 산출물이다.
- 목적: 코드 변경 없는 background 대기 대신 safe-loss bucket에서 직접 repair 후보와 regression-count 제외 후보를 분리한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_301_REPORT_20260702.md`, verdicts `docs/devs/loop301_safe_loss_seed_source_native_verdicts.json`, batch `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop301_safe_loss_resolved_to_null_review_batch.*`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop301_safe_loss_seed_source_native_review.*`.
- Evidence: batch selected `147`, missing source/baseline/after `0/0/0`; seed verdict reviewed/unreviewed `15/132`, validation issues `0`, `REPROCESS=14`, `ACCEPT=1`, actions `repair_safe_loss=14`, `exclude_from_regression_count_after_gate_wiring=1`.
- Gate: safe-loss seed verdict `REVIEW-LOCKED`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop300 Addendum - unsafe promotion full source-native verdict and gate wiring

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop300은 approval이 아니라 Loop298 `unsafe_promotion_from_hold=26` 전체를 source-native verdict와 current contract replay로 수렴시킨 action queue 산출물이다.
- 목적: 남은 unreviewed `11`건을 닫고, `REPROCESS`는 `promotion_blocked`, `ACCEPT`는 `safe_resolved`로 수렴하는지 current HEAD에서 확인한다.
- 코드 변경: `expert_main.py`에 publication 후보의 직접 title/url/source/alias support helper를 추가했다. Verified pure-work alias는 URL이 없어도 보존하고, sentence-like/meme/pronoun alias overreach와 official-title token leak는 promotion support로 세지 않는다.
- Artifacts: report `docs/devs/loop_reports/LOOP_300_REPORT_20260702.md`, verdicts `docs/devs/loop300_unsafe_promotion_from_hold_full_source_native_verdicts.json`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop300_unsafe_promotion_from_hold_full_source_native_review.*`, replay `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop300_unsafe_promotion_full_verdict_current_contract_replay.json`.
- Evidence: reviewed/unreviewed `26/0`, validation issues `0`, `REPROCESS=14`, `ACCEPT=12`; contract replay rows/match/mismatch `26/26/0`, `REPROCESS->promotion_blocked=14`, `ACCEPT->safe_resolved=12`.
- Verification: py_compile PASS, metadata unittest `46 tests` PASS, related bundle `137 tests` PASS.
- Background snapshot: full375 `375/69/51/18/0`, bounded1200 `1200/109/96/13/0`, golden18 `18/17/12/5/0`, 모두 `large_run_complete=false`.
- Gate: unsafe promotion full verdict `REVIEW-LOCKED`, contract replay `GO_UNIT_AND_LEGACY_REPLAY_EVIDENCE`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop299 Addendum - unsafe promotion shared contract repair

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop299는 approval이 아니라 Loop298 `repair_unsafe_promotion=8`을 shared publication contract로 실코드화한 계약 수리다.
- 목적: `unsafe_promotion_from_hold` 오승격이 후단 serialized public identity 추정만으로 `safe_resolved`에 남지 않게 한다.
- 코드 변경: `expert_main.py`에 inferred publication demotion 계약을 추가했다. Critical counterevidence는 `inferred_publication_critical_counterevidence`, 직접 source support 부재는 `inferred_publication_missing_direct_source_support`로 기록한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_299_REPORT_20260702.md`.
- Evidence: Loop298 REPROCESS 8건 `11657046`, `11658621`, `11658668`, `11671490`, `11674703`, `11690874`, `11703657`, `11706832`은 legacy replay에서 모두 `promotion_blocked`; positive controls `11674712`, `11695623`, `11669928`은 `safe_resolved` 유지.
- Verification: py_compile PASS, focused unittest 5건 PASS, related bundle 173 tests PASS.
- Background snapshot: full375 `375/62/51/11/0`, bounded1200 `1200/94/77/17/0`, golden18 `18/17/12/5/0`, 모두 `large_run_complete=false`.
- Gate: unsafe promotion contract `GO_UNIT_AND_LEGACY_REPLAY_EVIDENCE`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop298 Addendum - unsafe promotion partial source-native review

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop298은 approval이 아니라 collateral183 P0의 `unsafe_promotion_from_hold=26`을 부분 source-native verdict로 분해한 action queue 산출물이다.
- 목적: 코드 변경 없는 background 감시를 반복하지 않고, `unsafe_promotion_from_hold` bucket을 독립 배치로 떼어 `repair_unsafe_promotion`과 gate 배선 후보를 분리한다.
- 코드 변경: `tools/build_collateral_triage_review_batch.py --bucket` 추가, `tools/summarize_collateral_review_verdicts.py` bucket-agnostic summary 및 partial coverage 추가.
- Artifacts: report `docs/devs/loop_reports/LOOP_298_REPORT_20260702.md`, verdicts `docs/devs/loop298_unsafe_promotion_from_hold_source_native_verdicts.json`, batch `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop298_unsafe_promotion_from_hold_review_batch.*`, summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop298_unsafe_promotion_from_hold_source_native_review.*`.
- Evidence: batch selected `26`, missing source/baseline/after `0/0/0`; partial verdict reviewed `15/26`, unreviewed `11`, validation issues `0`, `REPROCESS=8`, `ACCEPT=7`, actions `repair_unsafe_promotion=8`, `exclude_from_regression_count_after_gate_wiring=7`.
- Gate: unsafe promotion partial review `REVIEW-LOCKED`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop297 Addendum - background health audit

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop297은 approval이 아니라 Loop288 background run 3개의 최신 health checkpoint다.
- 목적: full375, bounded1200 completed-source, golden18을 완료 전 approval 근거로 오해하지 않도록 manifest/checkpoint/result/log 증거를 갱신한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_297_REPORT_20260702.md`, audits `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop297_full375_search_nonlight_current_health_audit.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop297_bounded1200_search_nonlight_current_health_audit.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop297_golden18_search_included_current_health_audit.json`.
- Evidence: latest manifest snapshot은 full375 `375/53/51/2/0`, bounded1200 `1200/88/77/11/0`, golden18 `18/16/12/4/0`, 모두 `large_run_complete=false`다. 세 audit 모두 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 search blocker를 기록했다. full375/bounded는 `search_degraded_observed`, golden18은 `manifest_light_health_only`와 `search_degraded_observed`다.
- Gate: background runs `IN_PROGRESS`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, golden18 approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop296 Addendum - safe-loss N5 독립 실행 wrapper

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop296은 새 approval이 아니라 Loop294 invalid 반복 측정 경로를 막는 실행계획 계약이다.
- 목적: 같은 process에 중복 `post_id`를 넣으면 `input_post_count=3`으로 collapse되므로, safe-loss N5 반복을 `one_post_per_process` 구조로 강제한다.
- 코드 변경: `tools/safe_loss_flip_rate_probe.py`에 `build-run-plan` subcommand를 추가하고, `tests/test_safe_loss_flip_rate_probe.py`에 15개 독립 실행 계획 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_296_REPORT_20260702.md`, plan manifest `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop296_safe_loss_independent_n5_run_plan.json`.
- Evidence: plan은 planned runs `15`, repeat_count_by_post `11674712=5`, `11660237=5`, `11698880=5`, missing post_ids `[]`, `minimum_repeats_contract_met=true`다. 각 단일행 입력은 원본 row만 담고 `_flip_probe` metadata를 넣지 않는다.
- Current N5 evidence: 실제 current HEAD N5 결과는 Loop288을 유지한다. gate는 `NO-GO`; `11674712`와 `11698880`은 flip_rate `0.4`, `11660237`은 stable blind judge confirmed다.
- Background snapshot: full375 `375/49/41/8/0`, bounded1200 `1200/78/69/9/0`, golden18 `18/14/12/2/0`, 모두 `large_run_complete=false`.
- Gate: wrapper `GO_UNIT`, Loop296 execution `PLAN_READY_NOT_EXECUTED`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop291 Addendum - wrong-work title flip source-native 검토

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop291은 approval이 아니라 Loop290 `wrong_work_title_flip` 10행의 source-native 라벨 산출물이다.
- 목적: 코드 변경 없는 대형 run 대기를 멈추고, collateral183 P0 중 wrong-work title flip부터 blind/source-native 판정으로 actionable queue를 줄인다.
- 코드 변경: `tools/summarize_collateral_review_verdicts.py`와 `tests/test_summarize_collateral_review_verdicts.py`를 추가하고, `.gitignore` 추적 예외를 갱신했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_291_REPORT_20260702.md`, verdicts `docs/devs/loop291_wrong_work_title_flip_source_native_verdicts.json`, summary JSON/MD `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop291_wrong_work_title_flip_source_native_review.*`, Data Analytics MCP report `Loop291 wrong-work title flip 검토`.
- Evidence: reviewed rows `10`, validation issues `0`, label counts `REPROCESS=5`, `ACCEPT=3`, `HOLD=2`. report-time background snapshot은 full375 `375/12/3/9/0`, bounded1200 `1200/24/8/16/0`, golden18 `18/4/2/2/0`, 모두 `large_run_complete=false`.
- Gate: source-native review `REVIEW-LOCKED`, action queue `repair_after_wrong_work=5`, `canonical_title_policy_review=2`, `exclude_from_regression_count_after_gate_wiring=3`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop290 Addendum - collateral183 P0 blind/source-native 검토 배치

- 상태: goal `ACTIVE / NOT_COMPLETE`. 대형 background 런은 완료 전이므로 approval 근거로 쓰지 않는다.
- 목적: 코드 변경 없는 대기 루프를 끊고 Loop289 collateral183 P0 전체를 blind/source-native 검토 가능한 입력으로 고정한다.
- 코드 변경: `tools/build_collateral_triage_review_batch.py`와 `tests/test_build_collateral_triage_review_batch.py`를 추가하고, `.gitignore` 추적 예외를 갱신했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_290_REPORT_20260702.md`, batch JSON `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop290_collateral183_p0_review_batch.json`, JSONL `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop290_collateral183_p0_review_batch.jsonl`, Markdown `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop290_collateral183_p0_review_batch.md`, Data Analytics summary `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop290_collateral183_p0_review_batch_data_analytics_artifact.json`.
- Evidence: selected review rows `183`, missing source/baseline/after `0/0/0`, bucket `wrong_work_title_flip=10`, `unsafe_promotion_from_hold=26`, `safe_loss_resolved_to_null=147`. Loop290 문서화 시점 background snapshot은 full375 `375/3/1/2/0`, bounded1200 `1200/7/0/7/0`, golden18 `18/1/1/0/0`, 모두 `large_run_complete=false`.
- Gate: review batch `REVIEW-LOCKED`, background runs `RUNNING_BACKGROUND`, search degraded recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop289 Addendum - background 감시와 collateral183 triage 전환

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop288 background 런은 완료되지 않았으므로 approval 근거로 쓰지 않고, 대형/장기 run은 background monitoring으로 내렸다.
- 목적: 완료 대기 교착을 피하고 기존 full375 collateral diff의 `183` regression row를 P0 triage해 다음 source-native/blind judge 작업 큐를 만든다.
- 코드 변경: `tools/triage_collateral_regressions.py`를 추가해 collateral compare row를 `safe_loss_resolved_to_null`, `unsafe_promotion_from_hold`, `wrong_work_title_flip` 등으로 분류한다. 테스트 `tests/test_triage_collateral_regressions.py`와 `.gitignore` 추적 예외를 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_289_REPORT_20260702.md`, full375 audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_full375_search_nonlight_inprogress_health_audit.json`, bounded1200 audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_bounded1200_search_nonlight_inprogress_health_audit.json`, golden18 audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_golden18_search_included_inprogress_health_audit.json`, collateral triage `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_collateral183_regression_triage.json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_background_collateral183_data_analytics_artifact.json`.
- Evidence: full375 search non-light run은 `input=375`, `completed=0`, `flushed=0`, result/checkpoint missing이라 `NO-GO/artifact_count_mismatch`다. bounded1200은 `completed=4`, `flushed=0`, `pending=4`, `search_degraded_observed` blocker가 있다. golden18은 `completed/flushed=1/1`, `light_mode=True`라 old golden GO를 대체하지 못한다. collateral183 triage는 changed `223`, regression `183`, P0 `183`: `safe_loss_resolved_to_null=147`, `unsafe_promotion_from_hold=26`, `wrong_work_title_flip=10`.
- Gate: background runs `IN_PROGRESS`, collateral183 triage `NO-GO`, search degraded recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop288 Addendum - safe-loss N5, golden18, search 포함 런 발주

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았고, safe-loss 반복과 상위 gate 산출물 갱신으로 전환했다.
- 목적: stale 증거인 Loop238 flip `0.3333333333333333`과 6/28 golden GO를 current HEAD 기준으로 갱신하고, 검색 포함 bounded completed-source run을 발주해 approval 교착을 푼다.
- 코드 변경: `tools/bootstrap_regression_safe_grounding.py`는 extra golden rows manifest를 받아 golden input/manifest에 편입한다. `tools/evaluate_always_on_regression_gates.py` 기본 golden 기대치를 `18`로 전환했다. `tools/build_goal_action_queue.py`는 search degraded 복구를 P0로 태깅하고, 복구 전 `promotion_blocked`를 `search-blind conditional`로 해석한다. `.gitignore`는 bootstrap/golden audit 도구, bootstrap 테스트, golden 산출물 추적 예외를 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_288_REPORT_20260702.md`, N5 review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop288_safe_loss_current_head_n5_review.json`, extra golden rows `docs/devs/regression_safe_extra_golden_rows_20260702.json`, golden18 manifest/input `out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_manifest.json` / `golden_set.jsonl`, launches `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop288_background_launches.json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop288_safe_loss_search_runs_data_analytics_artifact.json`.
- Evidence: safe-loss N5 gate는 `NO-GO`다. `11660237`은 `5/5` stable blind judge confirmed `테라포밍 / https://novelpia.com/novel/61947`이고, `11674712`와 `11698880`은 flip_rate `0.4`, `nondeterminism_unresolved`다. `11698880`은 `3/5` 오답 `아카데미 생존 갤러리`, `2/5` 정답 title `promotion_blocked`로 갈라졌다. golden set은 `16 -> 18`, 추가 행 `11660237/11698880`, role `safe_loss_blind_judge_expected_work`다.
- Background: full375 replay PID `45436`, bounded1200 completed-source run PID `110660`은 모두 `include_search=True`, `light_mode=False`, shard `12/12 OK`로 시작했다. golden18 replay PID `83216`은 search 포함이나 small-run 정책상 `light_mode=True`다.
- Gate: safe-loss `NO-GO`, hard-hold relaxation `false`, full375 replay `RUNNING_BACKGROUND`, bounded completed-source run `RUNNING_BACKGROUND`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, completed-source approval candidate `0`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop287 Addendum - 11708456 candidate-only release and next frontier

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: `11708456` release가 public publish인지 candidate-only 보존인지 확인하고, 다음 ordered flush frontier를 식별한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_287_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop287_frontier_after_11708456_completion_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop287_completed_source_candidate_audit.md/json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop287_frontier_release_data_analytics_artifact.json`.
- Evidence: `11708456`은 W20에서 완료되어 result JSON에 들어왔고 result_rows가 `343 -> 354`로 전진했다. public title/url은 `null`이며 `promotion_decision.status=candidate_only`, `publish_allowed=false`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=multi_work`, `work_resolution=multi_work`, `bypassed_gate=false`다. Loop287 audit은 result_rows `354`, checkpoint_rows `400`, pending_count_actual `46`, frontier post `11708445`, worker `W24`, observed_elapsed_seconds `3121.812`다. post-audit manifest poll은 input/completed/flushed/pending/failed `104502/407/366/41/0`, `next_save_idx=367`, `large_run_complete=false`, `ordered_flush_blocked=true`이나 별도 감사 전까지 Loop287 approval 근거로 쓰지 않는다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Gate: live run health `IN_PROGRESS`, released frontier `11708456 / candidate_only / promotion_blocked / multi_work`, current frontier `11708445 / W24 in progress`, post-audit live poll `SEPARATE_AUDIT_REQUIRED`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop286 Addendum - frontier release and new Arbiter blocker

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: `11710018` release가 hard-hold 완화인지 candidate-only 보존인지 확인하고, 새 ordered flush frontier를 식별한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_286_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop286_frontier_after_11710018_completion_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop286_completed_source_candidate_audit.md/json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop286_frontier_release_data_analytics_artifact.json`.
- Evidence: `11710018`은 W25에서 완료되어 result JSON에 들어왔고 result_rows가 `317 -> 343`으로 전진했다. public title/url은 `null`이며 `promotion_decision.status=candidate_only`, `publish_allowed=false`, `candidate_ledger_status=promotion_blocked`, `bypassed_gate=false`다. Loop286 audit은 result_rows `343`, checkpoint_rows `375`, pending_count_actual `32`, frontier post `11708456`, worker `W20`, observed_elapsed_seconds `2277.595`다. W20 log는 Synthesizer가 author talk로 수렴하고 Arbiter stream을 시작한 상태를 기록한다. post-audit manifest poll은 input/completed/flushed/pending/failed `104502/378/343/35/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Gate: live run health `IN_PROGRESS`, released frontier `11710018 / candidate_only / promotion_blocked`, current frontier `11708456 / W20 Arbiter stream in progress`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop285 Addendum - frontier 11710018 reason_review audit

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop284부터 계속된 frontier `11710018`이 죽은 작업인지, reason_review 이후에도 writeback 전 병목인지 확인한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_285_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop285_frontier_11710018_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop285_completed_source_candidate_audit.md/json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop285_frontier_11710018_data_analytics_artifact.json`.
- Evidence: Loop285 health audit은 result_rows `317`, checkpoint_rows `371`, pending_count_actual `54`, `next_save_idx=318`, frontier post `11710018`, worker `W25`, observed_elapsed_seconds `1964.767`이다. W25 log는 `reason_review`가 `10:03:40.366`에 완료됐고 `10:05:00.213`에 `Fate/stay night` candidate_url이 page title 불일치로 제거됐음을 보여준다. post-render manifest poll은 input/completed/flushed/pending/failed `104502/374/317/57/0`, `large_run_complete=false`, `ordered_flush_blocked=true`, `11710018_in_result=false`다. `publication_contract_convergence=GO(row_count=317, violation_row_count=0)`, `search_evidence=REVIEW`다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Safe-loss evidence: Loop238 N=3 blind judge probe를 유지한다. `11674712`와 `11698880`은 stable blind judge confirmed, `11660237`은 flip_rate `0.3333333333333333`, `nondeterminism_unresolved`라 hard-hold 완화 금지다.
- Gate: live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG / reason_review_completed_but_no_result_row`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop284 Addendum - frontier chain release and new contract blocker

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop283 frontier 해소 이후 ordered flush가 얼마나 전진했고 어디서 다시 막혔는지 확인한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_284_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop284_frontier_release_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop284_completed_source_candidate_audit.md/json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop284_frontier_release_data_analytics_artifact.json`.
- Evidence: Loop283 frontier `11710049`와 Loop284 early frontier `11710036`은 result JSON에서 `[림월드]변방계에서 회귀자로 살아남기`, `candidate_ledger_status=safe_resolved`로 완료됐다. latest audit은 result_rows `317`, checkpoint_rows `361`, pending_count_actual `44`, frontier post_id `11710018`, worker `W25`, observed_elapsed_seconds `1964.767`다. post-audit manifest poll은 input/completed/flushed/pending/failed `104502/368/317/51/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다. W25 log는 `Fate/stay night` 내부 키워드와 제목-본문 불일치/텍스트 복사 오류 해석이 충돌해 Jury/Debate path가 길어지는 상태를 기록한다. `publication_contract_convergence=GO(row_count=317, violation_row_count=0)`, `search_evidence=REVIEW`다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Safe-loss evidence: Loop238 N=3 blind judge probe를 유지한다. `11674712`와 `11698880`은 stable blind judge confirmed, `11660237`은 flip_rate `0.3333333333333333`, `nondeterminism_unresolved`라 hard-hold 완화 금지다.
- Gate: live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop283 Addendum - frontier release follow-up and new ordered flush blocker

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop282 frontier 해소 이후 ordered flush가 어디서 다시 막혔는지 확인한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_283_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop283_frontier_release_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop283_completed_source_candidate_audit.md/json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop283_frontier_release_data_analytics_artifact.json`.
- Evidence: audit 시점 live run은 result_rows `288`, checkpoint_rows `328`, pending_count_actual `40`, frontier post_id `11710049`, worker `W34`, observed_elapsed_seconds `1912.109`다. post-audit manifest poll은 input/completed/flushed/pending/failed `104502/336/288/48/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다. W34 log는 VLM/OCR direct title `[림월드]변방계에서 회귀자로 살아남기`와 community-meta 반론이 충돌해 Jury/Debate path로 길어지는 상태를 기록한다. `publication_contract_convergence=GO(row_count=288, violation_row_count=0)`, `search_evidence=REVIEW`다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Gate: live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop282 Addendum - live frontier bottleneck and completed source candidate recheck

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: 진행 중인 completed-source 후보 런의 `next_save_idx=280` ordered flush frontier가 정지인지 장기 심의인지 확인한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_282_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop282_latest_live_run_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop282_completed_source_candidate_audit.md/json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop282_live_frontier_data_analytics_artifact.json`.
- Evidence: audit 시점 live run은 result_rows `279`, checkpoint_rows `320`, pending_count_actual `41`, frontier post_id `11710058`, worker `W1`, observed_elapsed_seconds `1506.524`다. W1 log는 `recommendation_guard`, Jury Panel `3/3 irrelevant`, Debate Advocate, `debate_skeptic` 진행을 기록한다. `publication_contract_convergence=GO(row_count=279, violation_row_count=0)`, `search_evidence=REVIEW`다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Gate: live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop281 Addendum - live health and completed source candidate recheck

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: 진행 중인 completed-source 후보 런의 ordered flush 진행, search evidence, publication contract convergence, completed source 후보 존재 여부를 재확인한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_281_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop281_latest_live_run_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop281_completed_source_candidate_audit.md/json`, Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop281_live_health_data_analytics_artifact.json`.
- Evidence: audit 시점 live run은 result_rows `279`, checkpoint_rows `299`, pending_count_actual `20`, frontier post_id `11710058`, worker `W1`, observed_elapsed_seconds `1315.752`다. `publication_contract_convergence=GO(row_count=279, violation_row_count=0)`, `search_evidence=REVIEW`다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Caveat: W27 Synthesizer trace는 Loop278 patch 전 시작된 장기 프로세스 흔적으로 유지한다. `failed=0`으로 전진 중이어도 completed-source approval 후보로 승격하지 않는다.
- Gate: live run health `IN_PROGRESS`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop280 Addendum - live health and completed source candidate recheck

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop279 이후 live run 진행 상태와 completed source approval 후보 존재 여부를 같은 라운드에서 재확인한다.
- 코드 변경: 없음.
- Artifacts: report `docs/devs/loop_reports/LOOP_280_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop280_latest_live_run_health_audit.json`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop280_completed_source_candidate_audit.md/json`.
- Evidence: live run은 result_rows `249`, checkpoint_rows `287`, pending_count_actual `38`, frontier post_id `11711600`, worker `W33`, observed_elapsed_seconds `1259.899`다. `publication_contract_convergence=GO`, `search_evidence=REVIEW`다. completed source 후보 감사는 approval_source_candidate_count `0`이다.
- Gate: live run health `IN_PROGRESS`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop279 Addendum - frontier timing health audit

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: ordered flush frontier가 진행 중인지 장시간 정체인지 판단할 수 있도록 health audit에 worker log timestamp 기반 elapsed time을 추가한다.
- 코드 변경: `tools/audit_expert_run_health.py`가 frontier worker log timestamp를 파싱해 `first_timed_event`, `last_timed_event`, `observed_elapsed_seconds`를 기록한다. CLI 출력에도 elapsed를 표시한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_279_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop279_latest_live_run_health_audit.json`.
- Evidence: Loop278 이후 live run은 `next_save_idx=204`에서 `219`로 전진했다. audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `218`, checkpoint_rows `280`, pending_count_actual `62`다. frontier post_id `11713185`, worker `W25`, observed_elapsed_seconds `1271.708`이다.
- Verification: `tests.test_audit_expert_run_health` `16` tests OK, py_compile PASS.
- Gate: frontier timing audit `PASS`, completed source `PENDING`, current run integrity `IN_PROGRESS`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop278 Addendum - live run health audit and Synthesizer hidden reference guard

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop264 대형 run의 최신 run health/frontier/search/publication gate를 감사하고, worker log에서 관측된 Synthesizer hidden reference 로깅 예외를 방어한다.
- 코드 변경: `src/llm_batch/experts/synthesizer.py`가 `hidden_references` 중 dict 항목만 로그와 Arbiter 요약에 사용한다. non-dict item은 결론 신호로 승격하지 않고 무시한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_278_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop278_latest_live_run_health_audit.json`.
- Evidence: audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `203`, checkpoint_rows `250`, pending_count_actual `47`이다. frontier는 post_id `11713200`, worker `W19`, last_event `synthesizer_start`다. `search_evidence=REVIEW`, `publication_contract_convergence=GO`, violation_row_count `0`이다.
- Verification: `tests.test_synthesizer_hidden_references` `2` tests OK, py_compile PASS.
- Gate: runtime hygiene patch `PASS`, completed source `PENDING`, current run integrity `IN_PROGRESS`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop277 Addendum - completed source 후보 publication contract gate

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: completed source approval 후보 탐색이 source completion/search/random 조건만으로 열리지 않고 publication contract convergence `GO`까지 요구하도록 한다.
- 코드 변경: `tools/build_completed_source_candidate_audit.py`가 candidate 직전 result에 `audit_publication_contract_convergence.py`를 적용하고, `publication_contract_convergence_gate`, `publication_contract_ready`, violation count를 report에 기록한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_277_REPORT_20260702.md`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop277_completed_source_candidate_publication_contract_audit.md/json`.
- Evidence: manifest `733`개 감사 결과 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Verification: `tests.test_completed_source_candidate_audit + tests.test_publication_contract_convergence_audit` `7` tests OK, py_compile PASS.
- Gate: completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, publication contract requirement `ENFORCED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop276 Addendum - health audit publication contract gate integration

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: publication contract convergence를 별도 도구에만 두지 않고 completed-source health audit의 top-level gate로 통합한다.
- 코드 변경: `tools/audit_expert_run_health.py`가 `publication_contract_convergence`를 출력한다. `tools/audit_publication_contract_convergence.py`의 audit logic을 재사용한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_276_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop276_health_audit_with_publication_contract_gate.json`.
- Evidence: audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `164`, checkpoint_rows `208`, pending_count_actual `44`다. `publication_contract_convergence=GO`, violation_row_count `0`이다. frontier는 post_id `11714866`, worker `W0`, last_event `arbiter_start`다.
- Verification: `tests.test_audit_expert_run_health + tests.test_publication_contract_convergence_audit` `19` tests OK, py_compile PASS.
- Gate: publication contract convergence `GO` for audited flushed rows, completed source `PENDING`, current run integrity `IN_PROGRESS`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop275 Addendum - publication contract convergence audit

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: architecture contract 수렴을 helper 내부 테스트에만 두지 않고 result artifact 단위 gate로 감사한다.
- 코드 변경: `tools/audit_publication_contract_convergence.py`가 `PromotionDecision`, `publish_contract_trace.gate_decision`, `publish_ledger.gate_decision`, `candidate_ledger` mirror, serialized public identity를 비교한다. blocked decision이 public title/url을 노출하거나 allowed decision과 serialized title/url이 다르면 `NO-GO`다.
- Artifacts: report `docs/devs/loop_reports/LOOP_275_REPORT_20260702.md`, audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop275_publication_contract_convergence_audit.md/json`.
- Evidence: Loop264 진행 중 flushed result `162`행 감사에서 gate `GO`, violation_row_count `0`이다.
- Verification: `tests.test_publication_contract_convergence_audit` `3` tests OK, `tests.test_expert_main_comment_metadata` `36` tests OK, py_compile PASS.
- Gate: publication contract convergence `GO` for audited flushed rows, completed source `PENDING`, current run integrity `IN_PROGRESS`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop274 Addendum - health audit frontier worker trace

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: ordered flush frontier가 artifact mismatch인지, 특정 worker에서 진행 중인지, 완료 로그가 있는데 flush 반영 전인지 health audit가 직접 보여주게 한다.
- 코드 변경: `tools/audit_expert_run_health.py`에 `frontier_worker_trace`를 추가했다. `flush_integrity.frontier.source_post`의 `global_idx/post_id`로 worker log 이벤트를 집계한다. `tests/test_audit_expert_run_health.py`에 in-progress/completed frontier 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_274_REPORT_20260702.md`, audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop274_frontier_worker_trace_health_audit.json`.
- Evidence: audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `145`, checkpoint_rows `181`, pending_count_actual `36`이다. frontier는 post_id `11714889`, title `김괴라리 괴신 ㅈㄴ무섭네ㅋㅋㅋㅋ`, source_line `161`이고 `frontier_worker_trace=in_progress_in_worker_log`, worker `W35`, last_event `arbiter_start`다.
- Verification: `tests.test_audit_expert_run_health` `14` tests OK, py_compile PASS.
- Gate: completed source `PENDING`, current run integrity `IN_PROGRESS`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop273 Addendum - completed source 후보 search-health requirement

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: completed source 후보 탐색에서 clean counts/VLM/OCR/random rows만으로 approval 후보가 열리지 않게 direct search-health evidence를 필수 조건으로 둔다.
- 코드 변경: `tools/build_completed_source_candidate_audit.py`가 `search_health_ready`를 계산하고 approval source candidate 조건에 포함한다. `tests/test_completed_source_candidate_audit.py`에 direct search-health 없는 clean source 차단 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_273_REPORT_20260702.md`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop273_completed_source_candidate_search_health_audit.md/json`.
- Evidence: manifest `733`개 감사 결과 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Verification: `tests.test_completed_source_candidate_audit` `3` tests OK, py_compile PASS.
- Gate: completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop272 Addendum - health audit search evidence gate

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: completed-source 승격 전에 search-health direct probe 누락과 실제 search degraded 관측을 audit JSON에서 분리한다.
- 코드 변경: `tools/audit_expert_run_health.py`에 `search_evidence` gate를 추가했다. manifest health mode, row-level `identity.search_health`, worker log search counters를 집계한다. `tests/test_audit_expert_run_health.py`에 light-health-only, direct health failure, degraded observation 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_272_REPORT_20260702.md`, search evidence audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop272_search_evidence_health_audit.json`.
- Evidence: audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `129`, checkpoint_rows `155`, pending_count_actual `26`이다. `search_evidence=REVIEW`, blockers `manifest_search_health_not_included`, `manifest_light_health_only`, `search_degraded_observed`다. row search health rows `72`, worker log search degraded `75`, upstream_zero `59`, timeout `0`이다.
- Verification: `tests.test_audit_expert_run_health` `12` tests OK, py_compile PASS.
- Gate: completed source `PENDING`, current run integrity `IN_PROGRESS`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop271 Addendum - health audit frontier source lookup

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: ordered flush gap frontier `global_idx`를 source input post로 해석해 막힌 post_id/title/url을 audit에 남긴다.
- 코드 변경: `tools/audit_expert_run_health.py`에 `--input-jsonl`과 input post lookup을 추가했다. `flush_integrity.frontier.source_post`에 source row를 기록한다. `tests/test_audit_expert_run_health.py`에 comment row가 lookup 순서를 오염시키지 않는 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_271_REPORT_20260702.md`, frontier source audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop271_frontier_source_lookup_health_audit.json`.
- Evidence: audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `117`, checkpoint_rows `135`, pending_count_actual `18`이다. frontier source는 `global_idx=118`, post_id `11716449`, title `케문제는 ㄹㅇ 애증의 소설임`, source_line `133`이다. 직후 manifest poll은 input/completed/flushed/pending/failed `104502/135/117/18/0`, `large_run_complete=false`, `ordered_flush_blocked=true`.
- Verification: `tests.test_audit_expert_run_health` `9` tests OK, py_compile PASS.
- Gate: completed source `PENDING`, current run integrity `IN_PROGRESS`, search-health direct probe `SEPARATE_AUDIT_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop270 Addendum - health audit flush frontier diagnostics

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: ordered flush gap이 있을 때 `next_save_idx` frontier가 checkpoint/pending에 있는지, 아니면 아직 in-flight/missing인지 audit가 직접 보여주게 한다.
- 코드 변경: `tools/audit_expert_run_health.py`의 `flush_integrity`에 `frontier`를 추가했다. `next_save_idx`, frontier status/reason, pending index 범위, completed index 범위를 기록한다. `tests/test_audit_expert_run_health.py`에 clean frontier와 ordered gap frontier 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_270_REPORT_20260702.md`, frontier audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop270_flush_frontier_health_audit.json`.
- Evidence: audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `90`, checkpoint_rows `128`, pending_count_actual `38`이다. frontier는 `next_save_idx=91`, `status=in_flight_or_missing`, `pending_index_min=93`, `pending_index_max=159`다. 직후 manifest poll은 input/completed/flushed/pending/failed `104502/128/90/38/0`, `large_run_complete=false`, `ordered_flush_blocked=true`.
- Verification: `tests.test_audit_expert_run_health` `8` tests OK, py_compile PASS.
- Gate: completed source `PENDING`, current run integrity `IN_PROGRESS`, search-health direct probe `SEPARATE_AUDIT_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop269 Addendum - health audit flush integrity classifier

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: completed-source 판정 전에 manifest/checkpoint/result/pending count 정합성을 audit가 직접 분류하게 한다.
- 코드 변경: `tools/audit_expert_run_health.py`에 `flush_integrity` classifier를 추가했다. `run_integrity_gate`, `classification`, `blockers`, count consistency, pending blocker sample을 기록한다. `tests/test_audit_expert_run_health.py`에 clean completion, ordered flush gap, count mismatch 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_269_REPORT_20260702.md`, flush integrity audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop269_flush_integrity_health_audit.json`.
- Evidence: audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `80`, checkpoint_rows `119`, pending_count_actual `39`이다. count consistency는 result/flushed, checkpoint/completed, pending/completed-minus-flushed 모두 `true`다. 직후 manifest poll은 input/completed/flushed/pending/failed `104502/119/80/39/0`, `large_run_complete=false`, `ordered_flush_blocked=true`.
- Verification: `tests.test_audit_expert_run_health` `8` tests OK, py_compile PASS.
- Gate: completed source `PENDING`, current run integrity `IN_PROGRESS`, search-health direct probe `SEPARATE_AUDIT_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop268 Addendum - health audit result JSON row count 지원

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: completed-source 대형 run 완료 후 `manifest/checkpoint/result/pending` 정합성을 한 audit에서 비교할 수 있게 `result_rows`를 기록한다.
- 코드 변경: `tools/audit_expert_run_health.py`에 `--result-json` 옵션과 `_count_result_rows`를 추가했다. audit JSON은 `artifact_resolution.result_json`, `result_json`, `result_rows`를 기록한다. `tests/test_audit_expert_run_health.py`에 result override와 shape별 row count 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_268_REPORT_20260702.md`, explicit result audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop268_explicit_result_health_audit.json`.
- Evidence: result_rows `12`, checkpoint_rows `95`, pending_count_actual `83`. 직후 manifest poll은 input/completed/flushed/pending/failed `104502/95/12/83/0`, `large_run_complete=false`, `ordered_flush_blocked=true`.
- Verification: `tests.test_audit_expert_run_health` `5` tests OK, py_compile PASS.
- Gate: completed source `PENDING`, run integrity `IN_PROGRESS`, search-health direct probe `SEPARATE_AUDIT_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop267 Addendum - health audit explicit artifact path 지원

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: completed-source 대형 run 완료 후 또는 sampling/custom output 감사 때 기본 `out\expert_result_<run_id>*` 위치에 묶이지 않도록 health audit artifact path를 명시할 수 있게 한다.
- 코드 변경: `tools/audit_expert_run_health.py`에 `--artifact-prefix`, `--manifest`, `--checkpoint`, `--pending-snapshot`, `--log-glob` 옵션을 추가하고, `artifact_resolution.explicit_overrides`를 기록한다. `tests/test_audit_expert_run_health.py`에 explicit path override 계약을 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_267_REPORT_20260702.md`, explicit path audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop267_explicit_path_health_audit.json`.
- Evidence: explicit path audit resolution `explicit_paths`, checkpoint_rows `88`, reason_error_count `0`, slang bad remaining `0`. 직후 manifest poll은 completed/flushed/pending/failed `90/12/78/0`, `large_run_complete=false`, `ordered_flush_blocked=true`.
- Verification: `tests.test_audit_expert_run_health` `4` tests OK, py_compile PASS.
- Gate: completed source `PENDING`, run integrity `IN_PROGRESS`, search-health direct probe `SEPARATE_AUDIT_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop266 Addendum - 진행 중 대형 run health 감사 보정

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop264 completed-source 대형 run을 완료로 승격하지 않고, 진행 중 health audit가 internal run id와 output prefix 불일치를 해석하도록 한다.
- 코드 변경: `tools/audit_expert_run_health.py`는 direct prefix manifest가 없으면 `out\expert_result_*_manifest.json`의 `manifest.run_id`를 스캔해 artifact prefix를 찾는다. `tests/test_audit_expert_run_health.py`와 `.gitignore` 예외를 추가했다.
- Artifacts: report `docs/devs/loop_reports/LOOP_266_REPORT_20260702.md`, health audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop266_inprogress_large_run_health_audit.json`, Data Analytics package `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop266_large_run_health_data_analytics_artifact_package`.
- Evidence: audit resolution `manifest_run_id_lookup`, checkpoint_rows `59`, reason_error_count `0`, slang bad remaining `0`. 직후 manifest poll은 completed/flushed/pending/failed `60/3/57/0`, `large_run_complete=false`, `ordered_flush_blocked=true`.
- Verification: `tests.test_audit_expert_run_health` `2` tests OK, py_compile PASS, Data Analytics validate/render/export PASS.
- Gate: completed source `PENDING`, run integrity `IN_PROGRESS`, search-health direct probe `SEPARATE_AUDIT_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop262 Addendum - completed source 후보 감사

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: completed source blocker를 실제 로컬 manifest 전체 기준으로 확인한다.
- 코드 변경: `tools/build_completed_source_candidate_audit.py`를 추가해 `out/**/_manifest.json`을 clean completion, VLM/OCR ready, result rows, random target 기준으로 감사한다. 이 도구의 후보 판정은 approval이 아니라 completed-source preflight 후보 여부만 뜻한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_262_REPORT_20260702.md`, candidate audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop262_completed_source_candidate_audit.md/json`, partial preflight `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop262_largest_partial_source_preflight.md/json`, clean shortfall preflight `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop262_largest_clean_shortfall_source_preflight.md/json`.
- Evidence: manifest `732`개 중 approval source candidate는 `0`개다. clean VLM/OCR source `429`개는 모두 random target `1000` 미달이며 가장 큰 clean source는 `375` rows다. partial VLM/OCR population 중 가장 큰 source는 `3812` rows지만 input/completed/flushed/pending/failed `104502/3875/3812/63/1`이라 approval source가 아니다.
- Preflight: largest partial source는 `REVIEW-LOCKED`; largest clean source는 run integrity `GO`지만 random shortfall `625`로 `REVIEW-LOCKED`.
- Verification: py_compile PASS, `tests.test_completed_source_candidate_audit` `2` tests OK.
- Gate: completed source candidate `MISSING`, completed-source preflight `REVIEW-LOCKED`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop261 Addendum - completed source preflight blocker 복원

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop260 queue가 `source_review_policy.path_present=false`를 완료 상태처럼 통과시켜 completed source 확보, completed-source preflight, random baseline 1000 blocker를 숨기지 않게 한다.
- 코드 변경: `tools/build_goal_action_queue.py`는 completed source preflight artifact가 없으면 작은 canary가 clean이어도 `obtain_completed_vlm_ocr_source`, `rerun_large_scale_preflight_on_completed_source`, `expanded_random_baseline_1000`, `p0_p1_high_risk_expansion`을 approval blocker로 유지한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_261_REPORT_20260702.md`, action queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop261_loop258_goal_action_queue_source_preflight_required.md/json`, convergence `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop261_loop258_source_preflight_goal_convergence.md/json`.
- Evidence: state map의 `source_review_policy.path_present=false`. current small canary runtime/coverage가 clean이어도 completed source preflight가 아니며, random baseline 1000과 P0/P1 high-risk expansion을 approval evidence로 계산할 source가 없다.
- Action queue: total_actions `10`, ready_now `0`, done `6`, blocked_until_completed_source `4`, approval blockers `4`.
- Convergence: gate `NO-GO`, actionable queue `1 -> 4`, same packet `true`, safe_resolved `3 -> 3`, safe_loss `[]`.
- Verification: py_compile PASS, `tests.test_goal_action_queue + tests.test_goal_convergence` `17` tests OK.
- Gate: completed source preflight `MISSING`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop260 Addendum - comment-author review label and queue semantics

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop259 잔여 `11658637` comment author review-only issue를 packet label로 닫고, current-source audit 완료 항목을 action queue에서 `done`으로 분리한다.
- 코드 변경: `tools/build_semantic_coverage_audit.py`는 `--review-labels`를 받아 `REVIEW` 전용 issue를 닫는다. `REVIEW-LOCKED` hard blocker는 label로 닫지 않는다. `tools/build_goal_action_queue.py`는 이미 수행된 current-source audit류를 `done`으로 표시하고 summary에 `done`을 추가한다.
- Artifacts: report `docs/devs/loop_reports/LOOP_260_REPORT_20260702.md`, label `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_11658637_comment_author_review_labels.jsonl`, semantic coverage `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_loop258_semantic_coverage_with_browser_and_comment_label_audit.md/json`, action queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_loop258_goal_action_queue_after_comment_label.md/json`, convergence `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_loop258_after_comment_label_goal_convergence.md/json`.
- Evidence: `11658637`의 댓글 author 동일성은 검증되지 않았지만 final publish 근거는 direct image/OCR/official URL이다. 댓글 author marker는 작품명 확정의 필수 근거가 아니므로 `ACCEPT/no_action` label로 review-only issue를 닫았다.
- Semantic coverage: gate `GO`, issues `[]`, browser visual required/available/missing `5/5/0`, review closure `11658637`.
- Action queue: total_actions `7`, ready_now `0`, done `6`, blocked_until_completed_source `1`, approval blocker `p0_p1_high_risk_expansion`.
- Convergence: gate `GO`, actionable queue `7 -> 1`, same packet `true`, safe_resolved `3 -> 3`, safe_loss `[]`.
- Verification: py_compile PASS, `tests.test_semantic_coverage_audit + tests.test_goal_action_queue` `43` tests OK.
- Gate: convergence `GO`는 stop-condition 수렴이지 full approval이 아니다. full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop259 Addendum - Loop258 image-row browser visual evidence

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- 목적: Loop258 semantic coverage blocker였던 image row 5건의 `browser_visual_or_direct_evidence_missing`을 닫는다.
- 대상 post_id: `11660277`, `11663544`, `11658637`, `11658668`, `11657046`.
- Artifacts: `docs/devs/loop_reports/LOOP_259_REPORT_20260702.md`, target JSONL `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_browser_visual_targets.jsonl`, capture manifest `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_browser_visual/loop259_browser_visual_manifest.json`, semantic coverage audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_semantic_coverage_with_browser_audit.md/json`, action queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_goal_action_queue_after_browser.md/json`, convergence `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_after_browser_goal_convergence.md/json`.
- Capture result: fallback Playwright browser visual capture로 captured rows `5/5`, screenshot OK `5/5`, visual evidence grade `Strong=5`, article image gate passed `5/5`, blocked/error rows `0`이다. Codex in-app Browser 직접 성공으로 표기하지 않는다.
- Semantic coverage: browser visual required/available/missing `5/5/0`으로 browser visual blocker는 닫혔다. 단, `11658637`의 `comment_author_match_unverified_resolution_review_only`가 남아 gate는 `REVIEW`다.
- Action queue: total_actions `7`, ready_now `6`, blocked_until_completed_source `1`, approval blocker `p0_p1_high_risk_expansion`.
- Convergence: same-packet safe_resolved `3 -> 3`, safe_loss `[]`, monotonic `true`지만 actionable queue `7 -> 7`이라 gate `NO-GO`다.
- Gate: browser visual `GO`, semantic coverage `REVIEW`, convergence `NO-GO`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop257-258 Addendum - URL-null inferred publish hold

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- Loop257 same 7-row packet run `20260702_052346_588912`은 runtime completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`, MCP health `2/2`였지만 semantic `NO-GO`다.
- Loop257 실패: `11663535`가 public title `퇴마록`, URL `null`, `candidate_ledger_status=safe_resolved`로 publish됐다. 이 경로는 resolved-public-title gate가 아니라 `final_publication_decision_inferred_from_serialized_identity`가 URL 없는 serialized identity를 publish로 재해석한 final contract path다.
- 코드 변경(Loop258 preflight): `expert_main._demote_inferred_urlless_publication_contract(...)`를 추가했다. `final_publication_decision_inferred_from_serialized_identity` + `official_url` 누락 + public title 존재 조건만 `candidate_only`, `publish_allowed=false`, `promotion_blocked`로 내린다.
- Trace 수렴 변경: `expert_main._enforce_publish_contract_trace_convergence(...)`가 `post_gate_identity.title_resolution_allowed`, `title_resolution_state`, `work_resolution`, `candidate_ledger_status`를 최종 identity와 동기화한다.
- Loop258 same 7-row packet run `20260702_053635_632644`은 runtime completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`, MCP health `2/2`다.
- Loop258 결과: `11663535`는 `promotion_blocked`, public title/url `null`, `promotion_decision.status=candidate_only`, `publish_allowed=false`로 내려갔다. `11658668` hard-hold는 유지됐고 `11660277`, `11663544`, `11658637`은 정상 safe를 유지했다.
- Data Analytics: MCP report artifact `Loop257-258 URL-null publish hold 검증`을 한국어로 validate/render 완료했다.
- Artifacts: `docs/devs/loop_reports/LOOP_258_REPORT_20260702.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop258_p0_representative_7_after_urlless_inferred_publish_hold_result.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop258_p0_representative_7_goal_convergence.md/json`.
- Verification: py_compile PASS, `tests.test_expert_main_comment_metadata` `36` PASS, focused final contract `4` PASS, convergence/safe-loss/always-on gate `17` PASS, title-lead guard `180` PASS, `git diff --check` PASS.
- Auxiliary audits: runtime `GO(stale process 0)`, reason hygiene `GO(hit_files=0)`, semantic coverage `REVIEW-LOCKED(browser visual 5/0/5)`.
- Gate: Loop258 targeted canary `GO_BLOCK_URL_NULL_PUBLIC_TITLE`, runtime `GO`, convergence `NO-GO(actionable queue 7 -> 7, safe_resolved 4 -> 3, safe_loss 11663535)`, semantic coverage `REVIEW-LOCKED`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop255 Result / Loop256 Preflight Addendum - final contract hard-hold convergence

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- Loop255 same 7-row packet run `20260702_045200_516008`은 runtime completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`, MCP health `2/2`로 완료됐지만 semantic `NO-GO`다.
- 실패: `11658668`은 `resolved_public_title` source로 public title `전 버튜버가 하고 싶은데요`, URL `https://novelpia.com/novel/275975`를 publish했다. 최종 identity에는 `platform_meta_multi_title_blocked`, `promotion_eligible=false` image evidence가 있었지만 기존 `promotion_decision=publish`가 유지됐다.
- 추가 흔들림: `11660277` safe-loss, `11663535` URL 없는 `퇴마록` publish가 발생했다. 따라서 same-packet safe_resolved 단조 비감소 조건은 실패다.
- 코드 변경(Loop256 preflight): `expert_main._sync_final_publication_ledger_contract(...)`의 final publication 수렴 단계에 platform-meta image hard-hold demotion을 추가했다. 최종 identity에 `platform_meta_multi_title_blocked` + matching image `promotion_eligible=false`가 있으면 이미 만들어진 publish decision도 `candidate_only`, `scope_context_only`, `platform_meta_image_title_hard_hold`로 재수렴한다.
- Verification: Loop255 result preview에 새 sync를 적용하면 `11658668`이 `promotion_blocked`, public title/url `null`, `platform_meta_image_title_hard_hold`로 내려간다. py_compile PASS, `tests.test_expert_main_comment_metadata` `35` PASS, `tests.test_title_lead_search_inferred_guard` `180` PASS.
- Gate: Loop255 runtime `GO` but semantic `NO-GO`. full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop254 Result / Loop255 Preflight Addendum - live hard-hold escape

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- Loop254 same 7-row packet run `20260702_043856_711141`은 runtime completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`, MCP health `2/2`로 완료됐지만 semantic gate는 실패다.
- 실패: `11658668`이 계속 `safe_resolved`, public title `전 버튜버가 하고 싶은데요`, URL `https://novelpia.com/novel/275975`, `promotion_gate_state.source=batch_memory_exact_alias_rescued`, reason `context_only,scope_current_work,work_consumption_marker`로 publish됐다.
- 개선된 점: `11663535`는 `promotion_blocked`, `scope_context_only`, `character_title_collision`으로 다시 hold됐다.
- 남은 blocker: `11663544`는 계속 `promotion_blocked` safe-loss이며, `11658668`은 live에서 non-promotable image catalog가 있어도 character/search/direct-anchor류 positive bridge로 hard-hold를 우회했다.
- 코드 변경(Loop255 preflight): `_platform_meta_image_title_requires_hold(...)`가 non-promotable matching image evidence를 먼저 판정하고, 이 경우 generic character/compound bridge로 빠져나가지 못하게 했다. 또한 image catalog가 아직 final에 주입되지 않은 OCR-only block에서도 platform-meta image title hard-hold를 적용한다.
- Verification: focused hard-hold tests `4` PASS, py_compile PASS. broader tests와 next same-packet canary는 커밋 후 실행한다.
- Gate: Loop254 runtime `GO` but semantic `NO-GO`. full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop254 Preflight Addendum - platform-meta image hard-hold contract

- 상태: goal `ACTIVE / NOT_COMPLETE`. Loop253 same 7-row packet은 runtime `GO`였지만 acceptance가 아니다.
- Loop253 run `20260702_041616_811347`은 completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`였고, `11658668`이 `batch_memory_exact_alias_rescued` semantic no-work 경로로 다시 publish됐다. `promotion_gate_state.title_resolution_state=context_only`, `work_resolution=unresolved`, reason에는 `context_only`가 있었지만 `row_discusses_work_as_work=true` / `scope_current_work`로 publish되어 계약 우회가 확인됐다.
- 코드 변경: platform-meta 원문(`수정/삭제/내리` 포함) + matching image evidence `promotion_eligible=false` + 구조화 direct image/character bridge 없음이면 `_platform_meta_image_title_requires_hold(...)`가 shared `_post_discusses_work_as_work(...)`와 no-work direct anchor rescue를 차단한다. `_can_promote_title_after_semantic_no_work(...)`는 이 경우 `platform_meta_image_title_hard_hold`와 `scope_context_only`를 기록한다.
- 단일 술어 계약: `_has_verified_contextual_alias_work_bridge(...)`는 계속 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")` wrapper를 경유하며 tracked test로 확인했다.
- Unit verification: py_compile PASS, `tests.test_title_lead_search_inferred_guard` `179` PASS, `tests.test_expert_main_comment_metadata` `34` PASS, `git diff --check` PASS.
- Gate: preflight unit checkpoint only. Next same-packet canary는 커밋 뒤 실행한다. 동일 38-row parent packet은 재실행하지 않았다. full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop251 Addendum - 11663535 캐릭터-제목 충돌 canonicalization hold

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- Loop251은 `11663535`가 `조선 퇴마록` public title로 승격되는 P0D drift를 막기 위해 resolved-public-title gate를 보강했다.
- 코드 변경: 후보 제목이 비이미지 본문에 직접 없고 `character_title_collision(major|critical)` 또는 `nullify_title` counter가 있으며 shared `_post_discusses_work_as_work(...)` bridge가 없으면 `character_title_collision` / `missing_direct_candidate_title` scope conflict로 내린다.
- 단일 술어 계약: `_has_verified_contextual_alias_work_bridge(...)`는 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")` wrapper이고, 이번 public gate도 같은 shared predicate를 확인한다.
- Run `20260702_034658_596805`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, image_post_count `0`이다.
- Result는 `candidate_ledger_status=promotion_blocked`, public title/url `null`, blocked candidate `퇴마록`, `title_resolution_state=author_new_work_context`, `title_resolution_allowed=false`, `publish_allowed=false`다.
- Artifacts: `docs/devs/loop_reports/LOOP_251_REPORT_20260702.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop251_11663535_p0d_canonicalization_guard_result.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_runtime_audit.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_semantic_coverage.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_goal_convergence.md`.
- Verification: reason hygiene hit_files `0`, semantic coverage `GO` but approval 아님, `tests.test_title_lead_search_inferred_guard` `176` PASS, `tests.test_candidate_audit` `107` PASS, promotion trace/contract `55` PASS, architecture gate/work-bridge `19` PASS, py_compile PASS.
- Gate: targeted canary `GO_BLOCK_PUBLIC_TITLE`, runtime `GO`, convergence `NO-GO(queue 7 -> 7, packet identity changed)`, parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop250 Addendum - 11658668 이미지 기반 resolved-public-title scope 차단

- 상태: goal `ACTIVE / NOT_COMPLETE`. 동일 38-row parent packet은 재실행하지 않았다.
- Loop249 pre-patch run `20260702_031854_134932`은 `11658668`을 `safe_resolved`, `publish_allowed=true`, `scope_kind=current_work`로 계속 publish해 실패 증거가 됐다.
- Loop250 patch는 `src/llm_batch/agentic_pipeline.py`의 resolved-public-title gate에 image/ocr scope conflict를 추가했다. 비이미지 본문에 title이 없고 matching image catalog가 `promotion_eligible=false`이면 `image_title_not_promotion_eligible`로 public title을 후보 보존 상태로 내린다.
- Patched run `20260702_033005_272211`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`다.
- Loop250 result는 `candidate_ledger_status=promotion_blocked`, public title/url `null`, blocked candidate `전 버튜버가 하고 싶은데요`, `publish_allowed=false`, `publish_contract_trace.gate_decision.status=candidate_only`, `scope_kind=context_only`다.
- Artifacts: `docs/devs/loop_reports/LOOP_250_REPORT_20260702.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop250_11658668_resolved_public_image_scope_guard_result.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_runtime_audit.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_semantic_coverage.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_goal_convergence.md`.
- Verification: reason hygiene hit_files `0`, `tests.test_title_lead_search_inferred_guard` `174` PASS, architecture gate/work-bridge `19` PASS, py_compile PASS.
- Gate: targeted canary `GO`, runtime `GO`, semantic coverage `REVIEW-LOCKED(browser visual 1/0/1)`, convergence `NO-GO(queue 7 -> 7, packet identity changed)`, parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## Current Evidence

- Latest Loop260 comment author review label report: `docs/devs/loop_reports/LOOP_260_REPORT_20260702.md`
- Latest Loop260 review label: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_11658637_comment_author_review_labels.jsonl`
- Latest Loop260 semantic coverage with review label: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_loop258_semantic_coverage_with_browser_and_comment_label_audit.md/json`
- Latest Loop260 action queue: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_loop258_goal_action_queue_after_comment_label.md/json`
- Latest Loop260 goal convergence audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop260_loop258_after_comment_label_goal_convergence.md/json`
- Latest Loop259 browser visual evidence report: `docs/devs/loop_reports/LOOP_259_REPORT_20260702.md`
- Latest Loop259 browser visual capture manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_browser_visual/loop259_browser_visual_manifest.json`
- Latest Loop259 semantic coverage with browser audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_semantic_coverage_with_browser_audit.md/json`
- Latest Loop259 action queue after browser evidence: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_goal_action_queue_after_browser.md/json`
- Latest Loop259 goal convergence audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop259_loop258_after_browser_goal_convergence.md/json`
- Latest Loop258 URL-null inferred publish hold report: `docs/devs/loop_reports/LOOP_258_REPORT_20260702.md`
- Latest Loop258 result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop258_p0_representative_7_after_urlless_inferred_publish_hold_result.json`
- Latest Loop258 manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop258_p0_representative_7_after_urlless_inferred_publish_hold_result_manifest.json`
- Latest Loop258 convergence audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop258_p0_representative_7_goal_convergence.md/json`
- Latest Loop258 runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop258_p0_representative_7_runtime_audit.md/json`
- Latest Loop258 semantic coverage audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop258_p0_representative_7_semantic_coverage_audit.md/json`
- Latest Loop258 reason hygiene: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop258_p0_representative_7_reason_hygiene.json`
- Latest Loop257 failure evidence: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop257_p0_representative_7_after_final_contract_hard_hold_result.json`
- Latest Loop257-258 Data Analytics report artifact: `Loop257-258 URL-null publish hold 검증`
- Latest Loop251 11663535 character-title collision hold report: `docs/devs/loop_reports/LOOP_251_REPORT_20260702.md`
- Latest Loop251 result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop251_11663535_p0d_canonicalization_guard_result.json`
- Latest Loop251 runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_runtime_audit.md/json`
- Latest Loop251 semantic coverage audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_semantic_coverage.md/json`
- Latest Loop251 convergence audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_goal_convergence.md/json`
- Latest Loop250 11658668 image scope guard report: `docs/devs/loop_reports/LOOP_250_REPORT_20260702.md`
- Latest Loop250 patched result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop250_11658668_resolved_public_image_scope_guard_result.json`
- Latest Loop250 runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_runtime_audit.md/json`
- Latest Loop250 semantic coverage audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_semantic_coverage.md/json`
- Latest Loop250 convergence audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_goal_convergence.md/json`
- Latest Loop248 P0 representative replay / reason hygiene guard report: `docs/devs/loop_reports/LOOP_248_REPORT_20260702.md`
- Latest Loop248 current result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop248_p0_representative_7_current_result.json`
- Latest Loop248 review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop248_p0_representative_7_current_review.md/json`
- Latest Loop248 original reason hygiene scan: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop248_p0_representative_7_reason_hygiene.json`
- Latest Loop248 sanitized-preview reason hygiene scan: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop248_p0_representative_7_reason_hygiene_sanitized_preview.json`
- Latest Loop247 browser visual coverage report: `docs/devs/loop_reports/LOOP_247_REPORT_20260702.md`
- Latest Loop247 semantic coverage with browser artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop247_run09_semantic_coverage_with_browser_audit.md/json`
- Latest Loop246 architecture gate revalidation report: `docs/devs/loop_reports/LOOP_246_REPORT_20260702.md`
- Latest Loop241 exact-title relation hold contract report: `docs/devs/loop_reports/LOOP_241_REPORT_20260702.md`
- Latest Loop241 focused result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop241_11660237_relation_exact_title_hold_run07_result.json`
- Latest Loop241 review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop241_11660237_relation_exact_title_hold_review.md/json`
- Latest Loop240 title-led platform probe cap report: `docs/devs/loop_reports/LOOP_240_REPORT_20260702.md`
- Latest Loop240 focused result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop240_11660237_title_led_probe_run06_result.json`
- Latest Loop240 review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop240_11660237_title_led_platform_probe_cap_review.md/json`
- Latest Loop238 architecture convergence / safe-loss flip probe report: `docs/devs/loop_reports/LOOP_238_REPORT_20260701.md`
- Latest Loop238 safe-loss flip-rate review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_safe_loss_flip_rate_n3_blind_judge_review.md/json`
- Latest Loop238 always-on golden16/full375 gate: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_always_on_golden16_full375_gate.md/json`
- Latest Loop238 stop-condition tool: `tools/evaluate_goal_convergence.py`
- Latest Loop238 safe-loss probe tool: `tools/safe_loss_flip_rate_probe.py`
- Latest Loop238 always-on gate tool: `tools/evaluate_always_on_regression_gates.py`
- Latest Loop236 URL-title direct-source support guard report: `docs/devs/loop_reports/LOOP_236_REPORT_20260701.md`
- Latest Loop236 URL-title direct-source support guard review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_review.md/json`
- Latest Loop236 Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_data_analytics_artifact.json`
- Latest Loop236 patched canary result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop236b_11663540_url_title_direct_support_guard_result.json`
- Latest Loop237 parent replay after Loop236 URL-title guard report: `docs/devs/loop_reports/LOOP_237_REPORT_20260701.md`
- Latest Loop237 parent replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_review.md/json`
- Latest Loop237 Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_data_analytics_artifact.json`
- Latest Loop237 parent replay result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop237_parent_replay_after_loop236_url_title_direct_support_guard_result.json`

- Latest Loop235 character-parenthetical bridge runtime NO-GO report: `docs/devs/loop_reports/LOOP_235_REPORT_20260701.md`
- Latest Loop235 character-parenthetical bridge review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_no_go_review.md/json`
- Latest Loop235 Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_data_analytics_artifact.json`


- Latest Loop234 direct-image cover-title runtime canary report: `docs/devs/loop_reports/LOOP_234_REPORT_20260701.md`
- Latest Loop234 direct-image cover-title runtime canary artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_review.md/json`
- Latest Loop234 Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_data_analytics_artifact.json`

- Latest Loop233 direct-image character shared gate report: `docs/devs/loop_reports/LOOP_233_REPORT_20260701.md`
- Latest Loop233 direct-image character shared gate artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_review.md/json`
- Latest Loop233 Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_data_analytics_artifact.json`

- Latest Loop232 source/native variance review report: `docs/devs/loop_reports/LOOP_232_REPORT_20260701.md`
- Latest Loop232 source/native variance review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_review.md/json`
- Latest Loop232 Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_data_analytics_artifact.json`

- Latest Loop228 safe-loss source/native review report: `docs/devs/loop_reports/LOOP_228_REPORT_20260701.md`
- Latest Loop231 parent replay after Loop230 report: `docs/devs/loop_reports/LOOP_231_REPORT_20260701.md`
- Latest Loop231 parent replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop231_parent_replay_after_loop230_title_led_serializer_gate_review.md/json`
- Latest Loop231 parent replay Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop231_parent_replay_after_loop230_title_led_serializer_gate_data_analytics_artifact.json`
- Latest Loop228 safe-loss source/native review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_review.md/json`
- Latest Loop228 safe-loss source/native Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_data_analytics_artifact.json`
- Latest Loop227 composite parent replay report: `docs/devs/loop_reports/LOOP_227_REPORT_20260701.md`
- Latest Loop227 composite parent replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop227_composite_parent_replay_after_trace_candidate_priority_review.md/json`
- Latest Loop227 composite parent replay Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop227_composite_parent_replay_after_trace_candidate_priority_data_analytics_artifact.json`
- Latest Loop227 parent checkpoint: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop227_parent_replay_after_trace_candidate_priority_result_checkpoint.jsonl`
- Latest Loop227 missing-row result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop227_missing_11698897_after_trace_candidate_priority_result.json`
- Latest envelope title gate parent replay report: `docs/devs/loop_reports/LOOP_225_REPORT_20260701.md`
- Latest envelope title gate parent replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop225_parent_replay_after_envelope_title_gate_fix_review.md/json`
- Latest envelope title gate parent replay Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop225_parent_replay_after_envelope_title_gate_fix_data_analytics_artifact.json`
- Previous parent replay after Loop223 patch report: `docs/devs/loop_reports/LOOP_224_REPORT_20260701.md`
- Previous parent replay after Loop223 patch review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_review.md/json`
- Previous parent replay after Loop223 patch runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_runtime_audit.md/json`
- Previous parent replay after Loop223 patch Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_data_analytics_artifact.json`
- Latest publish-contract title-field patch report: `docs/devs/loop_reports/LOOP_223_REPORT_20260701.md`
- Latest publish-contract title-field patch review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_review.md/json`
- Latest publish-contract title-field patch runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223b_publish_contract_title_field_runtime_audit.md/json`
- Latest publish-contract title-field patch Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_data_analytics_artifact.json`
- Latest safe-loss source/native review report: `docs/devs/loop_reports/LOOP_222_REPORT_20260701.md`
- Latest safe-loss source/native review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_review.md/json`
- Latest safe-loss source/native Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_data_analytics_artifact.json`
- Latest direct-alias parent replay report: `docs/devs/loop_reports/LOOP_221_REPORT_20260701.md`
- Latest direct-alias parent replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_review.md/json`
- Latest direct-alias parent replay runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_runtime_audit.md/json`
- Latest direct-alias parent replay Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_data_analytics_artifact.json`
- Latest direct alias probe report: `docs/devs/loop_reports/LOOP_220_REPORT_20260701.md`
- Latest direct alias probe review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_review.md/json`
- Latest direct alias probe runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_packet_runtime_audit.md/json`
- Latest direct alias probe Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_data_analytics_artifact.json`
- Latest shared gate unconfirmed-alias report: `docs/devs/loop_reports/LOOP_219_REPORT_20260701.md`
- Latest shared gate unconfirmed-alias review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_review.md/json`
- Latest shared gate unconfirmed-alias runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_packet_runtime_audit.md/json`
- Latest shared gate unconfirmed-alias Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_data_analytics_artifact.json`
- Latest character bridge scope trace report: `docs/devs/loop_reports/LOOP_218_REPORT_20260701.md`
- Latest character bridge scope trace review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_review.md/json`
- Latest character bridge scope trace runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_packet_runtime_audit.md/json`
- Latest character bridge scope trace Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_data_analytics_artifact.json`
- Latest exact-alias image/OCR context trace report: `docs/devs/loop_reports/LOOP_214_217_REPORT_20260701.md`
- Latest exact-alias image/OCR context trace review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop214_217_exact_alias_image_context_trace_review.md/json`
- Latest exact-alias image/OCR context trace runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop217_exact_alias_image_context_reason_trace_packet_runtime_audit.md/json`
- Latest exact-alias image/OCR context trace Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop214_217_exact_alias_image_context_trace_data_analytics_artifact.json`
- Latest title-led unconfirmed-alias guard report: `docs/devs/loop_reports/LOOP_212_213_REPORT_20260701.md`
- Latest title-led unconfirmed-alias guard review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop212_213_title_led_unconfirmed_alias_bridge_review.md/json`
- Latest title-led unconfirmed-alias runtime audits:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop212_title_led_unconfirmed_alias_packet_replay_runtime_audit.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop213_title_led_unconfirmed_alias_packet_repeat_runtime_audit.md/json`
- Latest previous-work candidate preservation report: `docs/devs/loop_reports/LOOP_209_211_REPORT_20260701.md`
- Latest previous-work candidate preservation review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop211_previous_work_candidate_preservation_review.md/json`
- Latest previous-work candidate preservation Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop211_previous_work_candidate_preservation_data_analytics_artifact.json`
- Latest packet variance scope-block report: `docs/devs/loop_reports/LOOP_205_208_REPORT_20260701.md`
- Latest packet variance scope-block review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop205_208_packet_variance_scope_block_review.md/json`
- Latest packet variance runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop208_character_alias_mention_filter_packet_replay_runtime_audit.md/json`
- Latest upstream resolved-public-title gate report: `docs/devs/loop_reports/LOOP_203_204_REPORT_20260701.md`
- Latest upstream resolved-public-title gate review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop204_resolved_public_title_gate_review.md/json`
- Latest upstream resolved-public-title gate Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop204_resolved_public_title_gate_data_analytics_artifact.json`
- Latest final-publication ledger report: `docs/devs/loop_reports/LOOP_200_202_REPORT_20260701.md`
- Latest final-publication ledger review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop202_final_publication_ledger_review.md/json`
- Latest final-publication ledger Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop202_final_publication_ledger_data_analytics_artifact.json`
- Latest packet replay report: `docs/devs/loop_reports/LOOP_198_199_REPORT_20260701.md`
- Latest packet replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop199_title_led_gate_packet_replay_review.md/json`
- Latest packet replay Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop199_title_led_gate_packet_replay_data_analytics_artifact.json`
- Latest acknowledged previous-work scope gate report: `docs/devs/loop_reports/LOOP_195_REPORT_20260701.md`
- Latest acknowledged previous-work scope gate review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop195_acknowledged_previous_work_scope_gate_review.md/json`
- Latest scope-state contract report: `docs/devs/loop_reports/LOOP_193_REPORT_20260701.md`
- Latest scope-state contract review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_review.md/json`
- Latest publish-trace scope propagation report: `docs/devs/loop_reports/LOOP_194_REPORT_20260701.md`
- Latest publish-trace scope propagation review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_review.md/json`
- Latest publish-trace packet replay report: `docs/devs/loop_reports/LOOP_191_192_REPORT_20260701.md`
- Latest publish-trace packet replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_review.md/json`
- Latest publish-contract trace unit report: `docs/devs/loop_reports/LOOP_190_REPORT_20260701.md`
- Latest publish-contract trace unit review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_review.md/json`
- Latest packet replay architecture-gap report: `docs/devs/loop_reports/LOOP_189_REPORT_20260701.md`
- Latest packet replay architecture-gap review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_review.md/json`
- Latest nested scrub follow-up report: `docs/devs/loop_reports/LOOP_187_REPORT_20260701.md`
- Latest implementation report: `docs/devs/loop_reports/LOOP_179_REPORT_20260630.md`
- Latest collateral follow-up report: `docs/devs/loop_reports/LOOP_186_REPORT_20260701.md`
- Latest targeted candidate-hold report: `docs/devs/loop_reports/LOOP_185_REPORT_20260701.md`
- Latest targeted follow-up report: `docs/devs/loop_reports/LOOP_184_REPORT_20260701.md`
- Latest source/native movement review report: `docs/devs/loop_reports/LOOP_183_REPORT_20260701.md`
- Latest post-architecture parent replay report: `docs/devs/loop_reports/LOOP_182_REPORT_20260701.md`
- Latest post-architecture residual canary report: `docs/devs/loop_reports/LOOP_181_REPORT_20260701.md`
- Latest nested scrub follow-up review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_review.md/json`
- Latest collateral follow-up review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_review.md/json`
- Latest targeted candidate-hold review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_review.md/json`
- Latest targeted follow-up review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_review.md/json`
- Latest source/native movement review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop183_loop182_movement_source_native_review.md/json`
- Latest architecture review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_review.md/json`
- Latest parent replay review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_review.md/json`
- Latest residual-return review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_review.md/json`
- Data Analytics artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop204_resolved_public_title_gate_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop202_final_publication_ledger_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop199_title_led_gate_packet_replay_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop195_acknowledged_previous_work_scope_gate_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop180_p1_recall_loss_image_anchor_gate_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop183_loop182_movement_source_native_review_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_data_analytics_artifact.json`
- Latest broader unittest gate: `.venv312\Scripts\python.exe -m unittest discover --start-directory tests`
- Latest result: `1332` tests, `0` failures, `0` errors, `OK`
- Loop176 baseline failure clusters that drove the architecture phase:
  - `acknowledged_previous_work_override`: `3`
  - `batch_alias_rescue_identity_missing`: `2`
  - `direct_ocr_work_surface_lock_bypass`: `1`
  - `community_review_headline_collision`: `1`
  - `candidate_audit_entity_mention_lint`: `1`
- Residual accounting remains from Loop175:
  - full reviewed residual ledger `136`
  - quarantine/human_review `5`
  - next actionable queue `131`
- P0/P1/P2 `0/61/70`

## Loop226 Safe-Loss Trace Candidate Priority

Loop226은 새 parent replay가 아니라 Loop225 실제 payload를 사용한 deterministic trace/ledger 보강이다. `expert_main.py`의 final publication ledger sync가 `promotion_blocked` 행에서 낮은 품질의 `comment_surface` 후보보다 더 강한 보존 후보를 `publish_contract_trace.pre_gate_candidate`로 기록하도록 했다.

검증 결과는 보수적이다. `11668288`은 `가챠펑크`에서 `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`로, `11674712`는 `호각임`에서 `이 무림의 미친년은 나야` / `https://novelpia.com/novel/217943?sid=main5`로, `11706832`은 `표절물인가`에서 `황제분충`으로 trace 후보가 개선됐다. 그러나 세 행 모두 `promotion_blocked`, `publish_allowed=false`를 유지했다.

Treat Loop226 as `GO_TRACE_ONLY`, not approval. Current accounting remains `NO_DELTA_TRACE_LEDGER_ONLY`, next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, and `full_scan_approval=false`.

## Loop225 Envelope Title Gate Fix Parent Replay

Loop225 patches the envelope/payload title-loss gap found in Loop224. The final publication ledger sync now receives the caller post title, and deterministic replay of the Loop224 `11661876` payload restores the target from `promotion_blocked` to `safe_resolved`.

Runtime is clean: run `20260701_151744_526664`, completed/flushed/pending/failed `38/38/0/0`, image_post_count `24`, VLM/OCR `READY`, MCP health `36/36`, and Data Analytics validate/render passed.

The semantic result remains `NO-GO / MIXED_MOVEMENT`. Loop225 counts are `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`. `11661876` recovers to `와인의 신`, but Loop224 -> Loop225 changed rows are `21`, including safe-loss rows `11668288`, `11674712`, `11706832` and safe identity drift rows `11658615`, `11695637`, `11705231`.

Treat Loop225 as targeted architecture repair evidence, not approval. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, and `full_scan_approval=false`.

## Loop224 Parent Replay After Loop223 Patch

Loop224 executes the parent/representative replay required by Loop223. Runtime is clean, but semantic movement is still not approval.

- run id: `20260701_141454_629022`
- runtime: `GO`, completed/flushed/pending/failed `38/38/0/0`, image_post_count `24`, VLM/OCR `READY`, MCP health `36/36`
- status counts: Loop224 `safe_resolved=10`, `promotion_blocked=26`, `hold_without_candidates=1`, `output_consistency_lint=1`
- changed rows from Loop221: `11666713`, `11668288`, `11695637`, `11698880`, `11705231`
- focused target split:
  - `11705231` survived as `탐식의 재림` / `https://page.kakao.com/content/50219568`
  - `11661876` failed parent survival and returned to `promotion_blocked`
- collateral regression: `11698880` regressed from stable `가챠 중독자의 퓨전펑크 생활` to candidate-only under `platform_meta_nonwork`
- Data Analytics artifact `Loop224 Loop223 패치 parent replay 검토`: validate/render PASS

Treat Loop224 as `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`. The next architecture move is to converge `title_resolution_state`, `work_resolution`, `scope_state`, and `publish_contract_trace` around an upstream authoritative promotion decision ledger instead of relying on final scrub restore alone.

## Loop223 Publish Contract Title Field Patch

Loop223 implements and verifies the two strongest Loop222 patch candidates, but it does not close the goal.

- code update: `src/llm_batch/candidate_audit.py` same-official-URL page-title canonicalization for character/entity surfaces such as `설지후` and conservative shared-current-work weak-alias exemption.
- code update: `expert_main.py` final blocked-result contract restore when shared gate evidence proves current_work, row_discusses_work_as_work, official detail URL, and no hard negative flags.
- focused result: Loop223 first canary fixed `11705231` but left `11661876` `promotion_blocked`.
- final result: Loop223b run `20260701_134929_838421`, runtime `GO`, completed/flushed/pending/failed `2/2/0/0`, issues `[]`, image_post_count `0`.
- row outcome: `11661876` -> `safe_resolved`, `와인의 신`, `https://novel.munpia.com/494781`.
- row outcome: `11705231` -> `safe_resolved`, `탐식의 재림`, `https://page.kakao.com/content/50219568`.
- verification: focused new tests `4` PASS, expert metadata suite `20` OK, candidate audit suite `104` OK, promotion gate contract suite `20` OK, full unittest discover `1335` OK.
- Data Analytics artifact `Loop223 Publish Contract Title Field 패치 검토`: validate/render PASS.

This closes the focused `11661876`/`11705231` patch item from Loop222. It is still not residual accounting approval. Parent/representative replay must prove the final-contract restore and title-field split do not reopen collateral movement. Keep next actionable `131`, P0/P1/P2 `0/61/70`, `semantic_quality=REVIEW-LOCKED`, and `full_scan_approval=false`.

## Loop222 Loop221 Safe-Loss Source/Native Review

Loop222 decomposes the six Loop221 `safe_resolved -> promotion_blocked` rows before any residual decrement. It is review-only: no new canary was run and no production code was changed.

- reviewed rows: `11658620`, `11660237`, `11661876`, `11668288`, `11695623`, `11705231`
- source/native existence: official or native web evidence confirmed for all six rows
- review verdict count: `likely_overblock=3`, `ambiguous_hold=2`, `title_field_bug=1`
- strongest architecture patch candidates:
  - `11661876`: current_work/high, row-discusses-work, and official detail evidence are present, but final publish contract scrub still blocks `와인의 신`
  - `11705231`: character/entity surface `설지후` is mixed into the official title field for the official `탐식의 재림` URL
- medium targeted lanes: `11660237` generic-common exact title question re-search, `11695623` alias-tag/VLM-OCR canary
- control/hold lanes: `11658620` alias competition, `11668288` short-body/image-without-title bridge
- Data Analytics: validate/render PASS
- accounting: `NO_DELTA_SOURCE_NATIVE_SAFE_LOSS_REVIEW_ONLY`
- active gate: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

Loop222 closes the Loop221 safe-loss decomposition item, but not the whole 9-row movement review and not the goal. Next implementation should start with focused tests for `11661876` and `11705231` before any broader replay or residual decrement claim.

## Loop221 Parent Replay After Direct Alias Probe

Loop221 executes the broader replay required after Loop220's packet-positive direct alias probe. It validates that the key direct-alias recovery survives parent scope, but it does not close the goal.

- Loop221 run id: `20260701_120437_234858`
- runtime completion: completed/flushed/pending/failed `38/38/0/0`
- parallel: requested/effective `36/36`
- VLM/OCR: required image scope `READY`, image_post_count `24`
- runtime contract audit: `GO`, issues `[]`
- Data Analytics: validate/render PASS
- status count: Loop182 `safe_resolved=12,promotion_blocked=24,hold_without_candidates=1,output_consistency_lint=1` -> Loop221 `safe_resolved=9,promotion_blocked=27,hold_without_candidates=1,output_consistency_lint=1`
- good movement: `11713222` recovered to `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`; `11674712` recovered to `이 무림의 미친년은 나야`; `11666713` moved to safe
- blocking movement: six rows moved `safe_resolved -> promotion_blocked`: `11658620`, `11660237`, `11661876`, `11668288`, `11695623`, `11705231`
- accounting: `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`
- active gate: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

Loop221 closes the "run broader replay" action as executed, but not as approved. The next work is movement review for the 9 changed rows, with safe loss rows reviewed before any residual decrement.

## Loop220 Direct Alias Probe Review

Loop220 fixes the immediate `11713222` direct-alias search ordering gap from Loop219, but it does not close the goal.

- Loop220 run id: `20260701_114043_668022`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`
- VLM/OCR: `READY`, image_post_count `2`
- health: Bridge-only MCP health `2/2`
- runtime contract audit: `GO`, issues `[]`
- code/test gate: `py_compile` PASS, new direct-alias focused test PASS, title-lead search inferred guard `157 OK`, expert metadata + promotion bundle `39 OK`, candidate-audit `102 OK`, full unittest discover `1332 OK`
- Data Analytics: validate/render PASS
- row outcome: `11713222` recovered to `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016` / `scope=current_work`; `11674712` recovered to `이 무림의 미친년은 나야` / `https://novelpia.com/novel/217943?sid=main5` / `scope=current_work`; `11669928` stayed safe
- packet count: Loop219 `safe_resolved=1,promotion_blocked=4` -> Loop220 `safe_resolved=3,promotion_blocked=2`
- accounting: `GO_PACKET_POSITIVE_DELTA_REPLAY_REQUIRED / NO_DELTA_UNTIL_BROADER_REPLAY`
- active gate: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

## Loop219 Shared Gate Unconfirmed-Alias Review

Loop219 fixes the immediate `11669928` candidate-audit regression from Loop218, but it does not close the goal.

- Loop219 run id: `20260701_110936_416066`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`
- VLM/OCR: `READY`, image_post_count `2`
- health: Bridge-only MCP health `2/2`
- runtime contract audit: `GO`, issues `[]`
- code/test gate: `py_compile` PASS, focused candidate-audit `4 OK`, full candidate-audit `102 OK`, expert metadata + promotion bundle `39 OK`, full unittest discover `1331 OK`
- Data Analytics: validate/render PASS
- row outcome: `11669928` recovered to `탑의 성좌들이 날 애호한다` / `https://novelpia.com/novel/377032` / `scope=current_work`
- blocking movement: `11713222` regressed to promotion_blocked through previous-work/comment candidate contamination; `11674712` regressed to promotion_blocked with `character_bridge_variance_hold`
- accounting: `NO_DELTA_SHARED_GATE_UNCONFIRMED_ALIAS_ONLY`
- active gate: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

## Loop218 Character Bridge Scope Trace

Loop218 fixes the immediate `11674712` trace gap from Loop217, but it does not close the goal.

- Loop218 run id: `20260701_104624_623831`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`
- VLM/OCR: `READY`, image_post_count `2`
- health: Bridge-only MCP health `2/2`
- runtime contract audit: `GO`, issues `[]`
- code/test gate: `py_compile` PASS, focused new tests `2 OK`, expert metadata + promotion bundle `39 OK`, title-led character bridge focused tests `2 OK`, full unittest discover `1329 OK`
- Data Analytics: validate/render PASS
- row outcome: `11674712` recovered to `이 무림의 미친년은 나야` / `https://novelpia.com/novel/217943` / `scope=current_work`
- blocking movement: `11669928` regressed to promotion_blocked with `scope=current_work`, URL `https://novelpia.com/novel/377032`, and reason `unconfirmed_alias_official_detail_bridge`
- accounting: `NO_DELTA_CHARACTER_BRIDGE_SCOPE_TRACE_ONLY`
- active gate: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

## Loop214-217 Exact-Alias Image/OCR Trace

Loop214-217 decomposed the remaining `11660257` exact-alias + image/OCR context issue as trace/rationale work. The final code path keeps the official-detail candidate preserved but blocks public title promotion when the only extra support is nonpromotable image/OCR context and there is no body/comment work bridge.

- Loop217 run id: `20260701_102032_074772`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`
- VLM/OCR: `READY`, image_post_count `2`
- health: Bridge-only MCP health `2/2`
- runtime contract audit: `GO`, issues `[]`
- code/test gate: `py_compile` PASS, focused new tests `2 OK`, expert metadata + promotion bundle `37 OK`, full unittest discover `1327 OK`
- Data Analytics: validate/render PASS
- row outcome: `11660257` remains candidate-only with `scope=context_only`; `11674712` remains open with scope null
- accounting: `NO_DELTA_TRACE_OBSERVABILITY_ONLY`
- active gate: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

## Loop205-208 Packet Variance Scope-Block Review

Loop205-208 reviewed the Loop203/204 packet variance before parent/collateral replay. It tightened candidate preservation and scope-block handling without claiming semantic approval.

- Loop208 run id: `20260701_080838_271200`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`
- VLM/OCR: `READY`, image_post_count `2`
- health: Bridge-only MCP health `2/2`
- runtime contract audit: `GO`, issues `[]`
- row outcome: `safe_resolved=3`, `promotion_blocked=2`, public title count `3`, inferred publish decisions `0`
- key row movements:
  - `11695623`: official-detail candidate preserved, but context-only / unresolved-worklike scope keeps public publish blocked.
  - `11674712`: restored to safe resolved as `이 무림의 미친년은 나야`.
  - `11713222`: no longer degrades to `@ㅇㅇ`, but remains review-locked because previous-work/comment override flags and competing candidates remain.
- residual accounting action: `NO_DELTA_PACKET_VARIANCE_REVIEW_ONLY`

This confirms the architecture can preserve stronger candidates while blocking context-only publish paths. It still does not satisfy the overall stop condition. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop209-211 Previous-Work Candidate Preservation

Loop209-211 resolves the immediate `11713222` scope-precedence collision without claiming broader semantic approval.

- Loop211 run id: `20260701_085524_956588`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`
- VLM/OCR: `READY`, image_post_count `2`
- health: Bridge-only MCP health `2/2`
- runtime contract audit: `GO`
- row outcome: `safe_resolved=3`, `promotion_blocked=2`, public title count `3`
- key row result:
  - `11713222`: public title `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`
  - previous-work candidate `잘생기면 인생이 편하다` / `https://novelpia.com/novel/300042` preserved candidate-only
- verification: focused previous-work tests `4 OK`, focused architecture bundle `38 OK`, broad architecture bundle `290 OK`, full unittest discover `1324 OK`
- residual accounting action: `NO_DELTA_SCOPE_PRECEDENCE_PACKET_REVIEW_ONLY`

This closes the immediate current-work versus previous-work steal for `11713222`. It still does not satisfy the overall stop condition because `11660257` and `11669928` moved between Loop210 and Loop211. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop179 Implementation Status

Phase A/B/C are complete enough to return to residual queue work:

- shared gate module added: `src/llm_batch/promotion_gate.py`
- selected high-risk paths wired in `src/llm_batch/agentic_pipeline.py`
- candidate ledger decision preservation added in `src/llm_batch/candidate_audit.py`
- contract tests added in `tests/test_promotion_gate_contract.py`
- Loop179 broader unittest gate is `GO`

This does not satisfy the overall stop condition. The goal remains `NOT_COMPLETE`.

## Loop180 Residual Queue Return

Loop180 returns from the architecture phase to the latest residual queue. It executed the smallest remaining P1 lane, `recall_loss_review / image_anchor_gate`, with 9 image rows.

- run id: `20260630_231142_887357`
- runtime completion: completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `9`
- row outcome: relevant `8`, identified public title `5`, `safe_resolved=5`, `promotion_blocked=4`
- strict runtime audit: `REVIEW` because this small run included search health (`MCP_HEALTH_INCLUDE_SEARCH=1`) instead of Bridge-only health
- Data Analytics artifact: validate/render PASS
- residual accounting action: `NO_DELTA_REVIEW_EVIDENCE_ONLY`

This confirms that candidate preservation and public-title promotion are separated in a real residual canary. It does not reduce the residual queue and does not unlock semantic/full-scan approval.

## Loop181 Bridge-Only Runtime Rerun

Loop181 reran the same 9-row P1 `image_anchor_gate` canary with Bridge-only small-run health to clear the Loop180 strict-runtime caveat.

- run id: `20260630_234216_623989`
- runtime completion: completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `9`
- health: `mcp_health_include_search=false`, MCP health ok/checked `2/2`
- runtime contract audit: `GO`, issues `[]`
- row outcome: relevant `9`, identified public title `6`, `safe_resolved=6`, `promotion_blocked=3`
- movement versus Loop180: `6/9` rows changed; degraded search counters `57 -> 67`
- residual accounting action: `NO_DELTA_REVIEW_EVIDENCE_ONLY`

This converts the Loop180 strict runtime caveat into clean runtime evidence only. It does not reduce the residual queue and does not unlock semantic/full-scan approval.

## Loop182 Parent/Representative Replay

Loop182 reran the 38-row parent/representative packet used by Loop169 after the shared promotion-gate architecture was integrated.

- run id: `20260701_001958_875919`
- input: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop134_parent_representative_after_loop133_source_enriched_packet.jsonl`
- runtime completion: completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `24`
- health: `mcp_health_include_search=true`, MCP health ok/checked `36/36`
- runtime contract audit: `GO`, issues `[]`
- row outcome: relevant `26`, identified public title `12`, `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`
- movement versus Loop169: `22/38` rows changed; `promotion_blocked -> safe_resolved` 2 rows; `safe_resolved -> promotion_blocked` 3 rows; degraded search counters `166 -> 178`
- residual accounting action: `NO_DELTA_REVIEW_EVIDENCE_ONLY`

This is the first architecture-integrated parent replay runtime `GO`, but it is not semantic approval. Source/native review is still required for the new safe gains and safe losses before any residual queue decrement.

## Loop183 Source/Native Movement Review

Loop183 reviewed the Loop182 parent movement rows without running a new canary. It covered safe gains `11669928`, `11695623` and safe losses `11660257`, `11674712`, `11713222`.

- source/native reviewed rows: `5/5`
- new residual closures: `0`
- residual accounting action: `NO_DELTA_SOURCE_NATIVE_REVIEW_ONLY`
- Data Analytics artifact: validate/render PASS
- next targeted surfaces: `11660257` exact-alias recall loss, `11695623` VLM/OCR-on stability repeat, `11713222` direct-body current-work alias vs comment previous-work alias competition

This review narrows the next queue surface but does not unlock semantic/full-scan approval.

## Loop184 Targeted Follow-up

Loop184 executed the five Loop183 follow-up rows with VLM/OCR on and Bridge-only small-run health.

- run id: `20260701_014002_948127`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `2`
- health: `mcp_health_include_search=false`, MCP health ok/checked `2/2`
- runtime contract audit: `GO`, issues `[]`
- row outcome: `safe_resolved=4`, `promotion_blocked=1`
- residual accounting action: `NO_DELTA_TARGETED_FOLLOWUP_ONLY`

This confirms runtime stability for the small follow-up only. It does not close the residual queue. `11660257` remains an exact-alias recall loss, `11713222` needs alias-precedence label review, and `11674712` remains character-bridge variance evidence.

## Loop185 Exact-Alias Candidate Hold

Loop185 is a one-row architecture-integrated candidate-preservation fix for `11660257`.

- run id: `20260701_021353_263678`
- runtime completion: completed/flushed/pending/failed `1/1/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `1`
- health: `mcp_health_include_search=false`, MCP health ok/checked `1/1`
- runtime contract audit: `GO`, issues `[]`
- code change: skip platform/listing/structural titles during official alias candidate recovery, and preserve blocked `search_evidence_alias_inference` exact-alias candidates as hold-only candidates
- row outcome: public `official_title=null`, `candidate_ledger_status=promotion_blocked`, preserved candidate `암흑가 보스요? 제가요?`, preserved URL `https://novelpia.com/novel/384111`
- residual accounting action: `NO_DELTA_TARGETED_SINGLE_ROW_ONLY`

This fixes the candidate-preservation failure exposed by Loop184 without public title promotion. It does not close the residual queue, reduce the next actionable count, or unlock semantic/full-scan approval.

## Loop186 Collateral Follow-up After Candidate Hold

Loop186 reran the five-row Loop184 follow-up packet after the Loop185 candidate-hold patch.

- run id: `20260701_022923_198719`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `2`
- health: `mcp_health_include_search=false`, MCP health ok/checked `2/2`
- runtime contract audit: `GO`, issues `[]`
- row outcome: `safe_resolved=2`, `promotion_blocked=3`
- movement versus Loop184: `3/5` rows moved; safe losses `11695623`, `11713222`
- `11660257`: candidate-hold fix remains stable, preserving `암흑가 보스요? 제가요?` / `https://novelpia.com/novel/384111` without public title promotion
- residual accounting action: `NO_DELTA_COLLATERAL_FOLLOWUP_REVIEW_ONLY`

This confirms the `11660257` candidate-hold fix in packet scope, but it also shows the packet is not semantically stable. `11695623` and `11713222` must be root-caused or explicitly quarantined before parent/collateral replay can support queue movement.

## Loop187 Nested Gate Scrub Follow-up

Loop187 patched the Loop186 `11713222` serialization/ledger collision at result-contract level, then reran the same five-row packet.

- run id: `20260701_025510_236345`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `2`
- health: `mcp_health_include_search=false`, MCP health ok/checked `2/2`
- runtime contract audit: `GO`, issues `[]`
- patch contract: `GO_UNIT_ONLY` via `py_compile` PASS and focused unittest bundle `10 tests OK`
- row outcome: `safe_resolved=2`, `promotion_blocked=3`
- `11660257`: candidate-hold fix remains stable with public title blocked
- `11713222`: Loop186 blocked/collision did not reproduce and the row returned to safe-resolved, so alias-precedence variance remains open
- `11669928`: new safe loss to promotion-blocked, requiring deliberate-null / explicit-alias bridge root-cause
- residual accounting action: `NO_DELTA_NESTED_GATE_SCRUB_REVIEW_ONLY`

Loop187 closes the nested scrub unit contract but not the live semantic packet. It does not reduce the residual queue, unlock source/full-panel completion, or change `full_scan_approval=false`.

## Loop188/189 Title-Led Bridge And Packet Replay

Loop188 added a narrow `title_led_consumption_bridge` and recovered `11669928` in a one-row canary. That was useful as root-cause evidence, but it was not sufficient packet evidence.

Loop189 reran the prior five-row Loop184 packet after Loop188.

- run id: `20260701_034236_736272`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `2`
- health: `mcp_health_include_search=false`, MCP health ok/checked `2/2`
- runtime contract audit: `GO`, issues `[]`
- row outcome: `safe_resolved=0`, `promotion_blocked=5`, public title count `0`
- residual accounting action: `NO_DELTA_PACKET_REPLAY_REGRESSED_TO_ALL_PROMOTION_BLOCKED`

Loop189 changes the architecture interpretation. The next step is not another isolated rescue condition. Candidate evidence survives in candidate/primary-work fields, but final serialized public identity blocks all titles. The active architecture goal therefore incorporates a second additive layer: public publish-contract observability.

Required additions:

- persist row-level `pre_gate_candidate`, `gate_decision`, `post_gate_identity`, `reason_codes`, and `bypassed_gate=false`
- split candidate preservation ledger from public publish ledger in artifacts and tests
- represent scope before `can_publish_title(...)`: current-work, previous-work, secondary-reference, author-new-work, image/OCR-derived work, and platform-meta/nonwork
- require stable packet replay before any residual accounting decrement

This keeps the original residual queue and stop condition. It does not create approval, closure, or a new queue baseline.

## Loop190 Publish-Contract Trace Unit Checkpoint

Loop190 implemented the first publish-contract observability layer required by Loop189. The change is intentionally narrow: it instruments the promotion-blocked serialized result contract and focused tests, but it does not claim packet semantic recovery.

- code surface: `expert_main._scrub_promotion_blocked_result_contract`
- trace fields: `pre_gate_candidate`, `gate_decision`, `post_gate_identity`, `reason_codes`, `bypassed_gate=false`
- ledger split: `publish_ledger.candidate_preservation` versus `publish_ledger.public_publish`
- downstream mirror: `candidate_ledger.publish_contract_trace` and `candidate_ledger.publish_ledger`
- focused test surface: `tests/test_expert_main_comment_metadata.py`
- verification: `py_compile` PASS and focused unittest PASS (`11 tests OK`)
- Data Analytics artifact: validation PASS; render call recorded as `ATTEMPTED_OUTPUT_TRUNCATED`

This is `GO_UNIT_ONLY`. The required next gate is still a five-row packet replay after instrumentation, using `publish_contract_trace` per `post_id` to explain candidate-to-public-title movement. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop191/192 Publish-Trace Packet Replay

Loop191 and Loop192 executed the required five-row packet replay after Loop190 instrumentation.

- Loop191 run id: `20260701_041346_483852`
- Loop191 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- Loop191 packet: `safe_resolved=2`, `promotion_blocked=3`, public title count `2`, trace rows `3`, pre-gate title rows `2`
- Loop191 gap: `11660257` preserved a candidate in `candidate_ledger`, but `pre_gate_candidate` was empty
- patch: derive trace candidate evidence from `candidate_ledger.candidate_preservation_sources` and string `title_candidates`
- unit verification after patch: `py_compile` PASS and focused unittest PASS (`12 tests OK`)
- Loop192 run id: `20260701_042125_503632`
- Loop192 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- Loop192 observability: trace coverage `5/5`, pre-gate title rows `5/5`
- Loop192 semantic packet: `NO-GO`, with `safe_resolved=0`, `promotion_blocked=5`, public title count `0`

This makes the publish-contract architecture more inspectable, but it also proves the packet remains unstable. `11669928` and `11713222` moved from Loop191 `safe_resolved` to Loop192 `promotion_blocked`. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## 2026-07-01 Goal Change: Scope-State Architecture Delta

Expert-agent review and the Loop189-192 packet evidence show that the current shared promotion gate is necessary but not sufficient. The next goal shape is therefore changed from "keep reducing residual rows with local gate repairs" to "add an explicit scope-state layer before further residual reduction."

This is an additive architecture idea, not a rewrite and not a new approval baseline. The runtime harness, residual queue, and original stop condition stay active. The new required design delta is:

- Introduce an explicit scope state before `can_publish_title(...)`.
- Classify each candidate as one of: `current_work`, `previous_work`, `secondary_reference`, `author_new_work`, `image_ocr_derived_work`, `platform_meta_nonwork`, `context_only`, or `unknown`.
- Carry scope evidence and conflicts alongside the candidate: direct body/title bridge, comment-only bridge, official-detail URL, image/OCR anchor, recommendation/context-only signal, and competing candidate list.
- Permit public publishing only when scope is current-work or otherwise directly row-grounded; previous-work, secondary-reference, author-new-work, platform-meta, and context-only candidates must remain candidate-only/HOLD unless a later contract test proves a safe generalized exception.
- Make `publish_contract_trace` report both the scope classification and the final public-publish decision, so reviewers can see whether a title was blocked because evidence was weak, because scope was not the current work, or because packet variance forced quarantine.

Immediate Loop193 direction:

- Treat `11669928`, `11713222`, and `11695623` as scope-state contract seeds before writing another rescue.
- Do not force-publish `11669928` solely from title-lead alias + official detail until the scope contract defines why discontinued/unavailable context is still current-work discussion.
- Keep `11713222` as current-work versus previous-work alias competition until the scope layer can prefer or hold candidates deterministically.
- Keep `11695623` as candidate-variance evidence until the scope layer explains why `[림월드]...` versus `그래-맞아` appears across packet runs.
- Count this phase as architecture design/contract work only until focused tests and packet replay are recorded.

## Loop193 Scope-State Contract Checkpoint

Loop193 implements the first code-level scope-state contract.

- code surfaces:
  - `src/llm_batch/promotion_gate.py`
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_promotion_gate_contract.py`
- new contract object: `ScopeState`
- scope categories: `current_work`, `previous_work`, `secondary_reference`, `author_new_work`, `image_ocr_derived_work`, `platform_meta_nonwork`, `context_only`, `unknown`
- wiring: `_can_promote_title_after_semantic_no_work` now records scope in `_promotion_gate_state`
- focused seeds: `11669928`, `11713222`, `11695623`
- verification:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`: PASS
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`: PASS, `11 tests OK`
  - Data Analytics artifact `Loop193 Scope-State Contract Checkpoint`: validate/render PASS
- report: `docs/devs/loop_reports/LOOP_193_REPORT_20260701.md`
- review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_review.md/json`

This is `GO_UNIT_ONLY`. It does not run a canary, decrement residual accounting, or unlock semantic/full-scan approval. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop194 Publish-Trace Scope Propagation Checkpoint

Loop194 propagates the Loop193 scope-state contract into serialized publish-contract traces.

- code surfaces:
  - `expert_main.py`
  - `tests/test_expert_main_comment_metadata.py`
- contract update:
  - read `promotion_gate_state.scope` from `identity` or `candidate_ledger`
  - persist it as `publish_contract_trace.scope_state`
  - mirror it in `publish_contract_trace.gate_decision.scope`
  - add missing scope reason codes to `publish_contract_trace.reason_codes`
- verification:
  - `venv\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`: PASS
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`: PASS, `23 tests OK`
  - Data Analytics artifact `Loop194 Publish Trace Scope Propagation Checkpoint`: validate/render PASS
- report: `docs/devs/loop_reports/LOOP_194_REPORT_20260701.md`
- review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_review.md/json`

This is `GO_UNIT_ONLY`. It does not run a canary, decrement residual accounting, or unlock semantic/full-scan approval. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop195 Acknowledged Previous-Work Scope Gate Checkpoint

Loop195 wires the first remaining high-risk public-title publish path into the shared scope-state gate.

- code surfaces:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_promotion_gate_contract.py`
- contract update:
  - extracted `_record_public_title_gate_decision(...)` so publish paths outside semantic-no-work can reuse the same decision ledger
  - routes `acknowledged_previous_work_comment_override` through `ScopeState` and `can_publish_title(...)`
  - records `scope_kind=previous_work` for direct current-work alias versus comment previous-work alias conflicts
  - blocks those conflicts as candidate-only instead of silently replacing the public `official_title`
- verification:
  - `venv\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`: PASS
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`: PASS, `24 tests OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`: PASS, `1309 tests OK`
  - Data Analytics artifact `Loop195 Acknowledged Previous-Work Scope Gate Checkpoint`: validate/render PASS
- report: `docs/devs/loop_reports/LOOP_195_REPORT_20260701.md`
- review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop195_acknowledged_previous_work_scope_gate_review.md/json`

This is `GO_UNIT_ONLY`. It does not run a canary, decrement residual accounting, or unlock semantic/full-scan approval. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop196 Batch Alias Scope Gate Checkpoint

Loop196 wires the next high-risk public-title publish path into the shared scope-state gate.

- code surfaces:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_promotion_gate_contract.py`
  - `tests/test_agentic_pipeline_rework.py`
- contract update:
  - adds `_record_batch_alias_public_title_gate_decision(...)`
  - remembers the batch-alias candidate/hit only when the path actually produces public identity output
  - records `ScopeState(scope_kind=current_work)` after final demotion and semantic reread logic has settled
  - preserves `promotion_decision` and `promotion_gate_state` in the final candidate ledger for batch-alias public-title output
- verification:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py tests\test_agentic_pipeline_rework.py`: PASS
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`: PASS, `13 tests OK`
  - targeted batch-alias rework tests: PASS, `2 tests OK`
  - combined promotion/rework bundle: PASS, `15 tests OK`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`: PASS, `25 tests OK`
  - `venv\Scripts\python.exe -m unittest tests.test_known_title_abbreviation_support tests.test_title_lead_search_inferred_guard -v`: PASS, `182 tests OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`: PASS, `1310 tests OK`
  - Data Analytics artifact `Loop196 Batch Alias Scope Gate Checkpoint`: validate/render PASS
- report: `docs/devs/loop_reports/LOOP_196_REPORT_20260701.md`
- review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_review.md/json`

This is `GO_UNIT_ONLY`. It does not run a canary, decrement residual accounting, or unlock semantic/full-scan approval. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop197 Direct OCR Scope Gate Checkpoint

Loop197 wires the direct OCR work-surface lock path into the shared scope-state promotion ledger at the final public identity boundary.

- code surfaces:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_promotion_gate_contract.py`
  - `tests/test_agentic_pipeline_rework.py`
- contract update:
  - adds `_record_direct_image_work_surface_gate_decision(...)`
  - records `ScopeState(scope_kind=current_work)` for `direct_image_work_surface_lock` publication
  - preserves `promotion_decision` and `promotion_gate_state` in the final candidate ledger for direct OCR work-surface output
  - keeps stale canonical rescue scanning skipped for the locked direct OCR work-surface title
- verification:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py tests\test_agentic_pipeline_rework.py`: PASS
  - direct OCR contract test: PASS, `1 test OK`
  - direct OCR/canonical rescue bypass integration test: PASS, `1 test OK`
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`: PASS, `14 tests OK`
  - direct OCR focused integration bundle: PASS, `5 tests OK`
  - rank OCR/lock suites: PASS, `30 tests OK`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`: PASS, `26 tests OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`: PASS, `1311 tests OK`
  - Data Analytics artifact `Loop197 Direct OCR Scope Gate Checkpoint`: validate/render PASS
- report: `docs/devs/loop_reports/LOOP_197_REPORT_20260701.md`
- review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_review.md/json`

This is `GO_UNIT_ONLY`. It does not run a canary, decrement residual accounting, or unlock semantic/full-scan approval. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The goal remains `ACTIVE / NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop198/199 Five-Row Packet Replay

Loop198 reran the prior five-row packet after Loop193-197 scope-gate wiring.

- run id: `20260701_055004_272309`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `2`
- health: `mcp_health_include_search=false`, MCP health ok/checked `2/2`
- runtime contract audit: `GO`, issues `[]`
- row outcome: `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`
- key gap: `11669928` safe-resolved as `탑의 성좌들이 날 애호한다` without `publish_contract_trace`

Loop199 added a narrow title-led alias public-title gate recorder, then reran the same five-row packet.

- run id: `20260701_060336_094994`
- runtime completion: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`
- VLM/OCR: `READY`, image_post_count `2`
- health: `mcp_health_include_search=false`, MCP health ok/checked `2/2`
- runtime contract audit: `GO`, issues `[]`
- code update: `_record_title_led_alias_public_title_gate_decision(...)` plus a promotion-gate contract test
- verification: `py_compile` PASS, title-led contract PASS, promotion-gate suite `15 tests OK`, title-led acceptance test PASS, full unittest discover `1312 tests OK`
- Data Analytics artifact `Loop199 Five-Row Packet Replay Review`: validate/render PASS
- row outcome: `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`

The packet remains semantic `NO-GO`. Loop199 narrowed the missing-trace surface, but it exposed a deeper final-publication ledger gap:

- `11669928`: final public identity is blocked/null, while `candidate_ledger.promotion_decision` still says `publish`.
- `11713222`: safe-resolved as `잘생기면 인생이 편하다` without a publish trace, while competing `잘생기면 편해지는 인방 생활` evidence remains in the candidate ledger.

Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The next architecture step is to unify `promotion_decision`, `publish_contract_trace.gate_decision`, `publish_ledger.public_publish`, and serialized `novel_identity` behind one final publication decision before another acceptance replay.

## Loop200-202 Final-Publication Ledger Checkpoint

Loop200-202 implemented and replayed the final-publication ledger unification layer exposed by Loop199.

- code update: `_sync_final_publication_ledger_contract(...)` in `expert_main.py`
- blocked final identity now rewrites stale publish decisions to `candidate_only` / `publish_allowed=false`
- allowed final identity now receives `publish_contract_trace`, `publish_ledger`, and matching `promotion_decision`
- scope payload is reconstructed from `scope_*` reason codes when needed
- verification: `py_compile` PASS, final-publication focused tests PASS, expert metadata plus promotion-gate suite `30 tests OK`, full unittest discover `1315 tests OK`
- Loop202 run id: `20260701_064737_150518`
- Loop202 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- Loop202 row outcome: `safe_resolved=2`, `promotion_blocked=3`, public title count `2`, trace count `5/5`
- Loop202 final-ledger consistency: `PASS`
- Data Analytics artifact `Loop202 Final Publication Ledger Review`: validate/render PASS

This closes the final-ledger mismatch for the five-row packet contract, but it is not semantic approval. Loop202 still has `inferred_publish_decision_count=2`, meaning some allowed final-publication decisions are inferred at serialization time rather than recorded upstream by a shared promotion-gate path.

Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The next architecture step is to replace inferred safe-publication decisions with upstream shared promotion-gate records, then review repeat packet stability before parent/collateral replay.

## Loop203-204 Resolved Public-Title Gate Checkpoint

Loop203-204 moved safe public-title decisions out of serialization inference and into the shared promotion-gate architecture.

- code update: `_record_resolved_public_title_gate_decision(...)` in `src/llm_batch/agentic_pipeline.py`
- code update: preserve `candidate_ledger.promotion_gate_state` and `promotion_gate_evidence` in `src/llm_batch/candidate_audit.py`
- verification: `py_compile` PASS, expert metadata plus promotion-gate suite `33 tests OK`, full unittest discover `1318 tests OK`
- Loop203 run id: `20260701_070958_405409`
- Loop203 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- Loop203 row outcome: `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace count `5/5`, inferred publish decisions `0`
- Loop204 run id: `20260701_071813_517226`
- Loop204 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- Loop204 row outcome: `safe_resolved=2`, `promotion_blocked=3`, public title count `2`, trace count `5/5`, inferred publish decisions `0`
- Data Analytics artifact `Loop204 Resolved Public Title Gate Review`: validate/render PASS

This closes the serialization-inferred safe-publication gap for the five-row packet. It is still not semantic approval. Loop203 moved `11695623`, `11713222`, and `11669928`, so repeat stability is not yet proven.

Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The next architecture step is to investigate packet variance before parent/collateral replay or residual decrement.

## Architecture Change To Incorporate

Use `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md` as the design reference. The change is additive, not a rewrite:

- Keep `expert_main.py` runtime/checkpoint/shard machinery.
- Add a shared promotion gate layer with local names close to:
  - `GroundingState`
  - `EvidenceRecord`
  - `ScopeState`
  - `PromotionDecision`
  - `GateReport`
  - `can_publish_title(...)`
- Route high-risk public-title and URL publishing through the shared gate.
- Preserve candidates on HOLD/quarantine paths instead of forcing `official_title` promotion.
- Make tests assert decision status, reason codes, candidate preservation, and `bypassed_gate=false`, not only final title/null.
- Add publish-contract trace tests that compare analysis-time candidate evidence with final serialized public identity.
- Make tests assert scope classification before public-title publish, especially current-work versus previous-work and context-only candidates.
- Treat one-row recovery as root-cause evidence only until packet replay proves stable publication behavior.

## Implementation Phases

### Phase A0 - Scope-State Contract

- Extend the shared promotion contract with explicit scope fields before adding more residual-row fixes.
- Define scope reason codes for `current_work`, `previous_work`, `secondary_reference`, `author_new_work`, `image_ocr_derived_work`, `platform_meta_nonwork`, `context_only`, and `unknown`.
- Add contract tests for:
  - `11669928`: title-lead exact alias + official detail + discontinued/unavailable context.
  - `11713222`: direct-body current-work alias competing with comment previous-work alias.
  - `11695623`: candidate variance between bracketed RimWorld title and generic/other candidate.
- Keep these as generalized scope fixtures; do not add post_id/title-specific production branches.

### Phase A - Inventory And Contract

- Inventory public-title / URL publish paths in:
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/candidate_audit.py`
  - `expert_main.py`
  - `src/llm_batch/experts/arbiter.py`
  - `src/llm_batch/experts/verifier.py`
  - `src/llm_batch/experts/decoder.py`
  - `src/llm_batch/experts/orchestrator.py`
  - compare/audit scripts that turn movement into queue status
- Define the shared decision object and reason-code contract.
- Add minimum contract tests before broad rewiring.

### Phase B - First Gate Wiring

Wire only the highest-risk 2-3 paths first:

- acknowledged previous-work override path
- batch alias rescue identity publishing path
- direct OCR work-surface lock / canonical rescue bypass path

Do not add post_id/title-specific production rules.

### Phase C - Verification

- Run focused contract tests.
- Run affected unittest suites for the touched modules.
- Re-run the authoritative broader sweep:

```powershell
.venv312\Scripts\python.exe -m unittest discover --start-directory tests
```

- Re-run targeted canary and representative parent/golden/collateral gates only after the broader unittest gate is clean or explicitly dispositioned.

### Phase D - Return To Residual Queue

Return to the Loop175 residual accounting only after:

- at least one shared promotion gate exists,
- explicit scope-state classification is wired before public publish decisions,
- selected high-risk publish paths route through it,
- contract tests prove `bypassed_gate=false`,
- contract tests prove non-current-work candidates remain candidate-only/HOLD unless a generalized exception is documented,
- Loop176 broader unittest failures are fixed or explicitly dispositioned,
- docs/checklists/history/verification are synced.

## Non-Negotiable Gates

- `semantic_quality=REVIEW-LOCKED`
- `full_scan_approval=false`
- source full completion `OPEN`
- full-panel collateral approval `NO-GO`
- goal completion `NOT_COMPLETE`
- queue `0`, runtime `GO`, targeted canary `GO`, or P0 `0` is not approval by itself.

## Stop Condition

이 goal은 회차 수, queue `0`, runtime `GO`, targeted canary `GO`, golden 단독 `GO`만으로 완료 처리하지 않는다. 완료 전에는 아래 조건이 모두 참이어야 한다.

1. Architecture integration phase가 실코드와 계약 테스트로 구현되어 있고, `PromotionDecision`, `publish_contract_trace`, `publish_ledger`가 같은 publish/block 결론으로 수렴한다.
2. `tools/evaluate_goal_convergence.py` 기준으로 previous/current queue 사이 `actionable queue`가 감소했고, 동일 packet에서 `safe_resolved`가 단조 비감소해야 한다. 둘 중 하나라도 실패하면 residual accounting은 `NO_DELTA`다.
3. Safe-loss row는 반복 입력 probe로 flip rate를 측정한다. 진동 row는 safe-loss가 아니라 `nondeterminism_unresolved`이며, blind judge가 정답성을 확인하고 반복 결과가 안정적일 때만 hard-hold 완화를 검토한다.
4. Golden-16과 full 375 collateral diff는 `tools/evaluate_always_on_regression_gates.py`로 항상 함께 gate한다. Golden 단독 통과는 approval이 아니며, collateral regression count가 0이 아니면 full-panel collateral approval은 `NO-GO`다.
5. 원래 residual stop condition도 유지한다: next queue가 비었거나, 모든 residual row가 row-level rationale과 required replay gate와 함께 HOLD/human_review/INFO_MISSING/unresolved_matchable/quarantine/no_generalizable_fix_left로 명시 처리되어야 한다.

## Loop229 Current Addendum

Loop229 keeps this goal active. The title-led evaluation bridge patch produced useful architecture evidence, but it did not satisfy the residual stop condition.

- canary input: `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop229_title_led_evaluation_bridge_2.jsonl`
- run `20260701_180326_874711`: runtime `GO`, public title `0/2`
- run `20260701_181447_543860`: runtime `GO`, public title `0/2`
- `11660257`: gate scope improved to `current_work`, but final serializer kept `candidate_only`
- `11660237`: stayed `context_only` under recommendation/non-novel force behavior
- residual accounting: `NO_DELTA_TITLE_LED_BRIDGE_CANARY_NO_GO`

The next architecture step is to separate title-led evaluation question scope from broad recommendation/noise forcing and to align final serialization with upstream `PromotionDecision` before returning to parent replay or residual decrement.

## Loop230 Current Addendum

Loop230 keeps this goal active. It proves that the Loop229 serializer/gate conflict can be repaired for one targeted row, but it does not satisfy the residual stop condition.

- report language contract: 신규/갱신 report, loop report, review Markdown, Data Analytics reader-facing artifact는 한국어로 작성한다. 간략하게 쓰되 의미, 근거, 산출물 경로, gate 상태를 생략하지 않는다.
- canary input: `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop229_title_led_evaluation_bridge_2.jsonl`
- run `20260701_183700_752963`: runtime `GO`, completed/flushed/pending/failed `2/2/0/0`, public title `1/2`
- `11660257`: recovered to `safe_resolved`, public title `암흑가 보스요? 제가요?`
- `11660237`: stayed `promotion_blocked`, `scope_context_only`, public title null
- residual accounting: `NO_DELTA_TITLE_LED_SERIALIZER_CANARY_PARTIAL_RECOVERY_PARENT_REPLAY_REQUIRED`

The next architecture step is parent/representative replay with explicit comparison of `promotion_decision`, `publish_contract_trace`, `publish_ledger`, and serialized `novel_identity`.

## Loop231 Current Addendum

Loop231 keeps this goal active. It proves Loop230's `11660257` recovery can survive one parent/representative replay, but it also proves the parent semantic gate is still not stable.

- report language contract: 신규/갱신 report, loop report, review Markdown, Data Analytics reader-facing artifact는 한국어로 작성한다. 간략하게 쓰되 의미, 근거, 산출물 경로, gate 상태를 생략하지 않는다.
- parent input: `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop134_parent_representative_after_loop133_source_enriched_packet.jsonl`
- run `20260701_190002_650661`: runtime `GO`, completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, MCP health `36/36`
- Loop225 -> Loop231: public title `12 -> 11`, safe_resolved `12 -> 11`
- `11660257`: survived as `safe_resolved`, public title `암흑가 보스요? 제가요?`
- `11660237`: Loop230 targeted hold conflicts with Loop231 parent publish `테라포밍`, so track it as targeted/parent variance
- safe-loss rows: `11661876`, `11663540`, `11695637`
- residual accounting: `NO_DELTA_PARENT_REPLAY_AFTER_LOOP230_MIXED_MOVEMENT`

The next architecture step is safe-loss decomposition and promotion-state convergence, not residual decrement. Keep `source_full_completion=OPEN`, `full_panel_collateral_approval=NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, and goal `ACTIVE / NOT_COMPLETE`.

## Loop324 Current Addendum

Loop324 keeps this goal active. It fixed the health-contract gap and proved the targeted replay can run with search-included non-light health, but it did not satisfy the stop condition.

- code checkpoint: `8c4ec326 fix: route safe-loss alias bridge through promotion gate`
- run `20260702_235904_452705`: completed/flushed/pending/failed `7/7/0/0`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`, VLM/OCR `READY`
- comparison: Loop324 `safe_resolved=2/7`, `promotion_blocked=5/7`, expected match `3/7`, search degraded rows `5/7`
- movement: `절꺾않` improved to safe_resolved, but `괴담출근` regressed from safe_resolved to promotion_blocked
- `빌환`, `지구온라인`, `성좌안무서움` remain unresolved/promotion-blocked; this is not residual closure
- Loop314 full375/bounded1200/N5 remain background monitoring only and are stale relative to `8c4ec326`
- artifacts: `docs/devs/loop_reports/LOOP_324_REPORT_20260703.md`, `docs/devs/loop324_loop322_alias_nonlight_replay_20260703.json`

Gate remains: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, search recovery `P0 / OPEN`, targeted canary `NO-GO`, goal `ACTIVE / NOT_COMPLETE`.
