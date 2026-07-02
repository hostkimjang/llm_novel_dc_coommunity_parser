# Developer TODO Index

> 운영 주석: 이 파일의 과거 `--parallel 36` 기록은 해당 시점의 역사적 실행 로그다. 신규 소규모/targeted 테스트는 `36`을 Gemma 4 4B runtime worker 상한으로만 보고 `min(input_post_count, 36)` 및 manifest의 `effective_parallel` 기준으로 판단한다. Codex goal의 "subagent/전문가 병렬"은 Codex `spawn_agent` 검토 병렬이며 `expert_main.py --parallel`을 올리는 뜻이 아니다.

## 2026-07-02 regression-safe grounding Loop307 TODO

- 상태 업데이트: Loop307은 code contract `GO_UNIT`이지만 N5 flip은 `NO-GO`다. Goal은 `ACTIVE / NOT_COMPLETE`.
- Loop307 TODO:
  - [x] `럽코빙의`, `빚세구`, `마줍`, `여신애호`, `별품소` shared alias 계약을 추가했다.
  - [x] `가챠펑크`, `즉사기` registry 단독 release를 보류하는 negative control을 추가했다.
  - [x] current HEAD N5 flip-rate를 새로 분석했다.
  - [x] full375/bounded1200 최신 health audit를 생성했다.
  - [ ] `11674712`, `11698880` flip 원인을 publish/block trace와 search-blind 조건으로 분해한다.
  - [ ] Loop307 patch 이후 targeted runtime replay를 완료하기 전까지 residual closure로 세지 않는다.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-02 regression-safe grounding Loop303 runtime recovery TODO

- 상태 업데이트: search shard runtime은 복구됐지만 full approval은 열리지 않았다. `3333/3334` health OK, MCP bridge `36`; N5는 first row LLM 장기화로 foreground 중단. Goal은 `ACTIVE / NOT_COMPLETE`.
- Loop303 TODO:
  - [x] Docker/Desktop 복구 후 search health를 확인했다.
  - [x] full375/bounded1200 completed-source search non-light run을 background 감시로 내렸다.
  - [x] 104k light/search-not-included run은 approval 근거가 아님을 기록했다.
  - [x] Loop301 `safe_loss_resolved_to_null=147` queue로 강제 전환했다.
  - [ ] N5 결과 JSON `15/15`를 만들고 flip rate를 current HEAD로 갱신한다.
  - [ ] full375/bounded1200 완료 전 approval 문구를 쓰지 않는다.
  - [ ] 남은 safe-loss `132`와 `repair_safe_loss=14`를 계속 줄인다.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-02 regression-safe grounding Loop302 search runtime TODO

- 상태 업데이트: 현 HEAD `e991a687`에서 N5/full375/bounded non-light 갱신을 시도했으나 search shard/Docker runtime blocker로 result JSON이 생성되지 않았다. Goal은 `ACTIVE / NOT_COMPLETE`.
- Loop302 TODO:
  - [x] N5 독립 실행 plan을 생성했다.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop302_safe_loss_independent_n5_run_plan.json`
    - planned runs `15`, repeat count `5/5/5`, missing `[]`
  - [x] 현재 blocker를 기록했다.
    - logs `logs/loop302_safe_loss_independent_n5_plan/*.stderr.log`
    - Docker API Internal Server Error
    - `com.docker.service=Stopped`
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_302_REPORT_20260702.md`
  - [ ] Docker Desktop service 또는 healthy `MCP_ENDPOINTS`를 복구한다.
  - [ ] 같은 N5 plan을 재실행하고 flip rate를 새로 산출한다.
  - [ ] current HEAD full375 search-including replay를 새로 실행한다.
  - [ ] current HEAD completed-source bounded `1000~1500` non-light run을 새로 발주한다.
  - [ ] 코드 변경 없음/대형 run 대기만 3연속이면 collateral183 triage 또는 OVERRIDE AUDIT blind judge 검증으로 강제 전환한다.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-02 regression-safe grounding Loop251 11663535 canonicalization hold TODO

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. Loop251은 `11663535`의 `조선 퇴마록` public-title drift를 resolved-public-title gate 계약으로 막고, runtime에서 `퇴마록` 후보를 `promotion_blocked`로 보존했다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop251 TODO:
  - [x] Loop248 `11663535` drift 근거를 확인했다.
    - current public title `조선 퇴마록`
    - verifier counter `character_title_collision(major)`
  - [x] resolved-public-title gate를 보강했다.
    - 후보 제목이 비이미지 본문에 직접 없고 `character_title_collision(major)`가 있으면 shared work bridge 없이는 publish하지 않는다.
  - [x] 단일 술어 계약을 유지했다.
    - `_has_verified_contextual_alias_work_bridge(...)`는 `_post_discusses_work_as_work(...)` wrapper다.
    - 이번 public gate도 `_post_discusses_work_as_work(...)`를 경유한다.
  - [x] Loop251 patched run을 실행했다.
    - run `20260702_034658_596805`
    - completed/flushed/pending/failed `1/1/0/0`
    - result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop251_11663535_p0d_canonicalization_guard_result.json`
  - [x] 최종 계약을 확인했다.
    - `candidate_ledger_status=promotion_blocked`
    - public title/url `null`
    - blocked candidate `퇴마록`
    - `publish_allowed=false`
  - [x] 검증을 완료했다.
    - runtime audit `GO`
    - reason hygiene hit_files `0`
    - semantic coverage `GO` but approval 아님
    - title-lead `176`, candidate-audit `107`, promotion trace/contract `55`, architecture `19`, py_compile PASS
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_251_REPORT_20260702.md`
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.
  - [ ] same parent/representative packet 또는 full375 collateral gate를 통과하기 전 approval을 갱신하지 않는다.

## 2026-07-02 regression-safe grounding Loop250 11658668 image scope guard TODO

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. Loop250은 `11658668`의 image OCR 기반 resolved-public-title publish 누수를 `promotion_blocked`로 내렸다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop250 TODO:
  - [x] Loop249 pre-patch 실패를 보존했다.
    - run `20260702_031854_134932`
    - final `candidate_ledger_status=safe_resolved`, `publish_allowed=true`, `scope_kind=current_work`
  - [x] resolved-public-title gate를 보강했다.
    - matching image catalog가 `promotion_eligible=false`이고 non-image 본문 title 언급이 없으면 `image_title_not_promotion_eligible`로 public publish를 막는다.
    - platform meta + relation reject canonical rescue도 차단한다.
  - [x] Loop250 patched run을 실행했다.
    - run `20260702_033005_272211`
    - completed/flushed/pending/failed `1/1/0/0`
    - VLM/OCR `READY`
    - result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop250_11658668_resolved_public_image_scope_guard_result.json`
  - [x] 최종 계약을 확인했다.
    - `candidate_ledger_status=promotion_blocked`
    - public title/url `null`
    - blocked candidate `전 버튜버가 하고 싶은데요`
    - `publish_allowed=false`
    - `publish_contract_trace` blocked 수렴
  - [x] 검증을 완료했다.
    - runtime audit `GO`
    - reason hygiene hit_files `0`
    - title-lead suite `174` PASS
    - architecture gate/work-bridge `19` PASS
    - py_compile PASS
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_250_REPORT_20260702.md`
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.
  - [ ] `11658668` browser visual/direct visual artifact를 붙이기 전 semantic coverage approval로 세지 않는다.
  - [ ] same parent/representative packet 또는 full375 collateral gate를 통과하기 전 approval을 갱신하지 않는다.
  - [ ] `11663535` canonicalization drift를 P0D blocker로 분리한다.

## 2026-07-02 regression-safe grounding Loop248 P0 representative replay and reason hygiene TODO

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. Loop248은 full375 P0 collateral bucket 대표 7건으로 current-code 상태를 진단했고, 원본 result의 reason hygiene 실패를 공개 reason sanitizer 코드로 보강했다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop248 TODO:
  - [x] P0 대표 7건 input을 생성했다.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop248_p0_representative_7.jsonl`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop248_p0_representative_7_manifest.json`
  - [x] current-code run을 실행했다.
    - run `20260702_023732_561254`
    - completed/flushed/pending/failed `7/7/0/0`
    - VLM/OCR `READY`, image_post_count `5`
  - [x] P0 대표 outcome을 기록했다.
    - expected 회복 `2`
    - unexpected/wrong title 차단 `2`
    - expected still missing `1`
    - loop49 after 재현 `1`
    - canonicalization other `1`
  - [x] reason hygiene 원본 실패를 기록했다.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop248_p0_representative_7_reason_hygiene.json`
    - `FAIL`, hit_files `1`, llm_flip hit_count `2`
  - [x] 공개 reason sanitizer를 보강했다.
    - `src/llm_batch/agentic_pipeline.py`
    - `tests/test_title_lead_search_inferred_guard.py`
  - [x] focused 검증을 완료했다.
    - `py_compile` PASS
    - tracked sanitizer regression 1 test PASS
    - sanitized preview reason hygiene hit_files `0`
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_248_REPORT_20260702.md`
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.
  - [x] `11658668` platform meta / expert conflict publish 경로를 Loop250 P0C blocker로 분리하고 단건 publish 누수를 차단했다.
  - [ ] `11663535` canonicalization drift를 P0D blocker로 분리한다.
  - [ ] full375 previous `NO-GO`를 닫기 전까지 residual approval을 갱신하지 않는다.

## 2026-07-02 regression-safe grounding Loop245 11660237 relation-hold patch and convergence review

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. Loop245는 current-code run08에서 재발한 `11660237` safe loss를 Verifier relation-hold 변형으로 좁히고, patch 후 run09 같은 입력에서 `safe_resolved` 회복을 확인했다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop245 TODO:
  - [x] run08 regression을 확인했다.
    - public `official_title=null`
    - `candidate_ledger_status=promotion_blocked`
    - `scope_kind=context_only`
    - `publish_allowed=false`
  - [x] run07->run08 same-packet convergence를 실행했다.
    - output: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop245_11660237_same_packet_goal_convergence.md/json`
    - gate `NO-GO`
    - actionable queue `1 -> 2`
    - safe_resolved `1 -> 0`
    - safe loss `11660237`
  - [x] Verifier relation hold 정규화 계약을 보강했다.
    - 원문 제목 표면이 후보 제목과 직접 맞아야 한다.
    - 공식 상세/정확 제목 검색 수렴이 있어야 한다.
    - `exact_title` 또는 `thematic_overlap_only` hold 변형을 `exact_title / allow`로 정규화한다.
    - search-only hold와 직접 제목 표면이 없는 후보는 계속 차단한다.
  - [x] run09를 실행했다.
    - run id `20260702_020419_735405`
    - completed/flushed/pending/failed `1/1/0/0`
    - VLM/OCR `READY`
    - final `official_title=테라포밍`, URL `https://novelpia.com/novel/61947`
    - `candidate_ledger_status=safe_resolved`, `scope_kind=current_work`, `publish_allowed=true`
  - [x] run08->run09 same-packet convergence를 실행했다.
    - output: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop245_11660237_relation_hold_patch_goal_convergence.md/json`
    - targeted local gate `GO`
    - actionable queue `2 -> 1`
    - safe_resolved `0 -> 1`
    - safe gain `11660237`
  - [x] 단일 술어 계약을 재확인했다: `_has_verified_contextual_alias_work_bridge(...)`는 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")`를 경유한다.
  - [x] full375 collateral diff는 always-on gate로 유지된다. 이번 회차에서는 재실행하지 않아 previous `NO-GO`가 유지된다.
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_245_REPORT_20260702.md`
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.
  - [ ] 다음 approval 갱신 전 same parent/representative packet 또는 full375 collateral gate를 다시 통과한다.

## 2026-07-02 regression-safe grounding Loop244 11660237 publish/block trace-scope review

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. Loop244는 `11660237` run01~run07의 기존 산출물을 `publish_contract_trace`, `publish_ledger`, scope, reason code 기준으로 비교한 evidence review다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop244 TODO:
  - [x] run01~run05 blocked 계열을 확인했다.
    - public title `null`
    - `candidate_ledger_status=promotion_blocked`
    - `scope_kind=context_only`
    - `publish_allowed=false`
  - [x] run04/run05에는 댓글이 존재했으므로 `body_comments_absent_or_empty`는 입력 누락이 아니라 final contract 해석 문제로 분리했다.
  - [x] run06/run07 publish 계열을 확인했다.
    - `candidate_ledger_status=safe_resolved`
    - `scope_kind=current_work`
    - `publish_allowed=true`
    - `official_title=테라포밍`
    - URL `https://novelpia.com/novel/61947`
  - [x] publish direct bridge sources 4종을 확인했다: `title_led_consumption_bridge`, `alias_surface`, `title_abbrev_mentioned`, `official_detail_url`.
  - [x] 진동 갈림점은 검색 title/url 존재 자체가 아니라 final publish contract의 `scope=context_only` vs `scope=current_work` 판정으로 축소했다.
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_244_REPORT_20260702.md`
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.
  - [ ] same-packet parent/representative result를 넣어 `tools/evaluate_goal_convergence.py`를 다시 실행하기 전까지 residual accounting과 approval은 갱신하지 않는다.

## 2026-07-02 regression-safe grounding Loop243 goal convergence preflight after Loop242

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. Loop243은 Loop242 뒤 `tools/evaluate_goal_convergence.py` preflight를 실제 실행했고 gate는 `NO-GO`다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop243 TODO:
  - [x] `tools/evaluate_goal_convergence.py`가 packet identity가 다를 때 safe loss/gain을 계산하지 않게 했다.
  - [x] packet 변경 시 `safe_delta_evaluated=false`, `safe_loss_post_ids=[]`, `safe_gain_post_ids=[]`가 되도록 테스트를 추가했다.
  - [x] `.gitignore` 예외를 추가해 `tools/evaluate_goal_convergence.py`, `tools/safe_loss_flip_rate_probe.py`, `tools/evaluate_always_on_regression_gates.py`와 해당 테스트 3개를 Git 추적 대상으로 만들었다.
  - [x] Loop241 직후 queue `2`개와 Loop242 뒤 queue `1`개를 입력 artifact로 구조화했다.
  - [x] convergence preflight를 실행했다.
    - output: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop242_goal_convergence_preflight_after_artifact_guard.md`
    - actionable queue `2 -> 1`, decreased `true`
    - previous packet Loop237 parent `38` rows, current packet Loop241 targeted `1` row
    - gate `NO-GO`, blocker `packet_identity_changed`
    - safe delta 미평가: `safe_delta_evaluated=false`
  - [x] architecture gate 도구 3개와 테스트 3개를 검증했다.
    - `venv\Scripts\python.exe -m py_compile tools\evaluate_goal_convergence.py tools\safe_loss_flip_rate_probe.py tools\evaluate_always_on_regression_gates.py` -> PASS.
    - `venv\Scripts\python.exe -m unittest tests.test_goal_convergence tests.test_safe_loss_flip_rate_probe tests.test_always_on_regression_gates -v` -> PASS, 17 tests.
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_243_REPORT_20260702.md`
  - [ ] same-packet parent/representative result를 넣어 다시 평가하기 전까지 residual accounting과 approval은 갱신하지 않는다.

## 2026-07-02 regression-safe grounding Loop242 11660237 fanart/cover artifact hint cost guard

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. Loop242는 `테라포밍 표지` fanart/cover artifact 후보가 snippet alias, resolved title follow-up, fetch 후보로 승격되는 비용 경로만 코드 계약으로 닫았다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop242 TODO:
  - [x] 공용 술어 `is_snippet_artifact_title_expansion(...)`을 추가했다.
  - [x] Decoder snippet mapping 주입에서 `테라포밍 -> 테라포밍 표지` 같은 artifact 확장을 `_resolved_mappings`에 넣지 않게 했다.
  - [x] Orchestrator LLM snippet 후처리, 정규식 snippet hint 후처리, resolved-title follow-up query, fanart URL fetch 후보 수집이 같은 술어를 경유하게 했다.
  - [x] LLM snippet prompt에 표지/fanart/커버/일러스트 산출물 페이지 제목은 작품 정식 제목이나 약칭 매핑이 아니라고 명시했다.
  - [x] focused tests를 확인했다.
    - `venv\Scripts\python.exe -m py_compile src\llm_batch\experts\decoder.py src\llm_batch\experts\orchestrator.py` -> PASS.
    - 신규 artifact guard 3 tests -> PASS.
    - relation exact-title 주변 3 tests -> PASS.
    - arbiter/known abbreviation 주변 2 tests -> PASS.
  - [x] 한국어 report를 남겼다.
    - `docs/devs/loop_reports/LOOP_242_REPORT_20260702.md`
  - [x] 다음 parent/representative replay 전 `tools/evaluate_goal_convergence.py` preflight를 실행했다. Loop243 결과는 queue 감소 `true`지만 packet identity가 달라 `NO-GO`다.
  - [ ] same-packet parent/representative result를 넣어 다시 평가하기 전까지 residual accounting과 approval은 갱신하지 않는다.

## 2026-07-02 regression-safe grounding Loop241 11660237 exact-title relation hold contract

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. `11660237` 단건 run07은 runtime `GO`, targeted canary `GO_11660237_RESOLVED`다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop241 TODO:
  - [x] `relation_judge exact_title + promotion_decision=hold` hard-hold 참고 신호를 Verifier 계약으로 정리했다.
  - [x] 원문 직접 grounding, decoder grounding, title/body/alias anchor, `alias_in_post_count >= 1`, `official_exact_title_count >= 1`, 공식 상세 URL/수렴 신호가 함께 있으면 exact-title hold를 `allow`로 정규화한다.
  - [x] 검색 결과에만 기대는 `search_only` exact-title hold는 계속 `nullify_title`되도록 negative contract를 유지했다.
  - [x] `11660237` run07을 실행했다.
    - run id `20260702_010819_484136`
    - completed/flushed/pending/failed `1/1/0/0`
    - VLM/OCR `READY`
    - relation judge actual output `exact_title / allow`
    - final `official_title=테라포밍`, URL `https://novelpia.com/novel/61947`
  - [x] 한국어 report/review artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_241_REPORT_20260702.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop241_11660237_relation_exact_title_hold_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop241_11660237_relation_exact_title_hold_review.json`
  - [x] Loop238 요구사항 재확인: 동일 parent packet 반복 중단, convergence evaluator, safe-loss flip-rate, 단일 술어 경유, full375 always-on gate는 이미 코드/문서에 반영돼 있다.
  - [x] `테라포밍 표지` fanart 후보와 포함어 URL alive-check 비용을 후보 필터/후처리 비용 문제로 분리했다. Loop242에서 snippet artifact expansion 비용 경로를 차단했다.
  - [x] 다음 parent/representative replay 전 `tools/evaluate_goal_convergence.py` preflight를 Loop243에서 실행했다. Gate는 `NO-GO(packet_identity_changed)`다.
  - [ ] same-packet parent/representative result를 넣어 다시 평가하기 전까지 residual accounting과 approval은 갱신하지 않는다.

## 2026-07-02 regression-safe grounding Loop240 11660237 platform probe cap normalization

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. `11660237` 단건 run06은 runtime `GO`, targeted canary `GO_11660237_RESOLVED`다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop240 TODO:
  - [x] `테라포밍 노벨피아`가 `title_anchor_official_probe cap=1`에 막히던 경로를 실행 직전 purpose 정규화로 닫았다.
  - [x] `site:novelpia.com/novel "테라포밍"`은 `title_anchor_official_probe`로 유지하고, non-site Novelpia platform query만 `platform_title_search`로 보냈다.
  - [x] `11660237` run06을 실행했다.
    - run id `20260702_005502_923302`
    - completed/flushed/pending/failed `1/1/0/0`
    - VLM/OCR `READY`
    - final `official_title=테라포밍`, URL `https://novelpia.com/novel/61947`, confidence `High`
  - [x] 한국어 report/review artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_240_REPORT_20260702.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop240_11660237_title_led_platform_probe_cap_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop240_11660237_title_led_platform_probe_cap_review.json`
  - [x] Loop239의 `61947` 직접 미회수/cap 스킵 원인은 targeted scope에서 해소했다.
  - [x] `relation_judge`가 `exact_title`을 보면서도 `promotion_decision=hold`를 낸 hard-hold 참고 신호를 Loop241 Verifier 계약으로 정리했다.
  - [x] `테라포밍 표지` fanart 후보와 포함어 URL alive-check 비용을 후보 필터/후처리 비용 문제로 분리했다. Loop242에서 snippet artifact expansion 비용 경로를 차단했다.
  - [x] 다음 parent/representative replay 전 `tools/evaluate_goal_convergence.py` preflight를 Loop243에서 실행했다. Gate는 `NO-GO(packet_identity_changed)`다.
  - [ ] same-packet parent/representative result를 넣어 다시 평가하기 전까지 residual accounting과 approval은 갱신하지 않는다.

## 2026-07-02 regression-safe grounding Loop239 11660237 title-led probe

- 상태 업데이트: 동일 38-row parent packet은 재실행하지 않았다. `11660237` 단건 run04는 runtime `GO`지만 semantic `NO-GO`, residual accounting `NO_DELTA_TARGETED_CANARY_NO_GO`다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop239 TODO:
  - [x] title-led current-work gate가 기존 `candidate_only/context_only` gate를 갱신할 수 있게 했다.
  - [x] 공식 상세/current-work gate가 없는 generic genre bridge는 계속 차단되도록 했다.
  - [x] title-led official detail probe를 search budget/rerank에서 보존했다.
  - [x] `11660237` run04를 실행했다.
    - run id `20260702_003226_807802`
    - completed/flushed/pending/failed `1/1/0/0`
    - VLM/OCR `READY`
    - final `official_title=null`, `candidate_ledger_status=promotion_blocked`
  - [x] Data Analytics artifact validate/render PASS.
  - [x] 한국어 report/review artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_239_REPORT_20260702.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop239_11660237_title_led_probe_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop239_11660237_title_led_probe_data_analytics_artifact.json`
  - [x] `site:novelpia.com/novel "테라포밍"`이 `61947` 대신 포함어 후보를 반환하는 원인을 provider/cap/fetch 순서로 분리했다. Loop240에서 non-site platform query가 `61947`을 R01로 회수했다.
  - [x] 목적별 cap이 `테라포밍 노벨피아` platform probe를 너무 일찍 스킵하는지 negative/positive tests로 확인했다. Loop240에서 `platform_title_search` 정규화 계약을 추가했다.
  - [x] 정답 상세 `61947`을 직접 발견한 뒤 targeted scope에서 title publish를 확인했다. 단, full375 collateral 미재실행 때문에 overall approval은 금지한다.

## 2026-07-01 regression-safe grounding Loop237 parent replay after Loop236 URL-title guard

- 상태 업데이트: Loop238에서 동일 38-row parent packet 반복을 중단하고 architecture convergence / safe-loss flip-rate / always-on gate를 코드화했다. Goal은 여전히 `ACTIVE / NOT_COMPLETE`.
- Loop238 TODO:
  - [x] 다음 회차 전 워킹트리를 논리 단위로 커밋했다.
    - code/tools checkpoint: `9181a61`
    - docs/reports checkpoint: `6e761fb`
  - [x] `_has_verified_contextual_alias_work_bridge`를 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")` 경유로 배선했다.
  - [x] Alias bridge 없는 relation-hold 후보가 새 경유 로직으로 풀리지 않는지 회귀 테스트로 확인했다.
  - [x] `promotion_decision`, `publish_contract_trace`, `publish_ledger` 수렴 보정과 계약 테스트를 추가했다.
  - [x] stop condition evaluator를 추가했다: `tools/evaluate_goal_convergence.py`.
  - [x] safe-loss flip-rate probe를 추가하고 N=3 반복을 실행했다.
    - review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_safe_loss_flip_rate_n3_blind_judge_review.md`
    - `11660237` flip rate `0.3333333333333333`, classification `nondeterminism_unresolved`.
    - hard-hold relaxation `false`.
  - [x] golden-16/full375 always-on gate evaluator를 추가했다.
    - gate: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_always_on_golden16_full375_gate.md`
    - golden-16 `GO`, full375 collateral `NO-GO`, changed `223`, collateral regression candidates `183`.
  - [x] `11660237`의 nondeterministic publish/block 원인을 `PromotionDecision` scope/state trace 기준으로 축소했다.
    - Loop244: 갈림점은 title/url 존재가 아니라 final publish contract의 `scope=context_only` vs `scope=current_work` 판정이다.
  - [ ] 다음 replay 전에 `tools/evaluate_goal_convergence.py`에 previous/current queue summary와 동일 packet result를 넣어 `NO_DELTA` 여부를 먼저 판정한다.

- 상태: parent/representative replay runtime GO / semantic `NO-GO / MIXED_MOVEMENT` / safe/public count drop / Data Analytics validate-render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Loop236 URL-title direct-source support guard를 parent/representative 38-row packet에서 재검증했다.
    - run id `20260701_215903_177630`
    - completed/flushed/pending/failed `38/38/0/0`
    - VLM/OCR `READY`
    - MCP health ok/failure `36/0`
  - [x] Loop231 대비 count regression을 기록했다: `safe_resolved/public title 11->9`, `promotion_blocked 25->28`.
  - [x] `11663540` parent survival 실패를 기록했다: focused canary 복구 후 parent replay에서는 `promotion_blocked`, public title `null`.
  - [x] Loop231 대비 movement를 분리했다: safe gain `11668288`, safe loss `11660237`, `11674712`, `11698880`, non-safe state change `11700495`.
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_237_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_review.json`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_data_analytics_artifact.json`
  - [x] Data Analytics artifact validate/render PASS를 확인했다.
  - [x] Residual accounting unchanged: `NO_DELTA_PARENT_REPLAY_AFTER_LOOP236_MIXED_MOVEMENT`.
  - [ ] `11663540` parent non-recovery의 OCR variant, character bridge, precision-seed review requirement를 분리해 다음 patch seed로 좁힌다.
  - [ ] `11698880`, `11660237`, `11674712` safe-loss row의 source/native evidence와 `publish_contract_trace`를 비교한다.
  - [ ] `11668288` safe gain은 raw lint flag가 있어 approval evidence로 쓰지 않는다.

## 2026-07-01 regression-safe grounding Loop234 direct-image cover-title runtime canary

- 후속 Loop236 상태: URL-title direct-source support guard 구현 / bad publish demotion preview PASS / patched focused canary PASS / Data Analytics validate-render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- Loop236 TODO:
  - [x] `url_title_verified_official_detail` publish precondition을 직접 post/OCR/alias support 조건으로 좁혔다.
  - [x] generic `official_detail_candidate_cue:주인공` + same-URL search title만으로 publish되는 wrong-work path를 재현했다.
  - [x] 같은 bad result를 resync preview에서 `official_detail_url_missing_direct_source_support`로 `promotion_blocked` 처리했다.
  - [x] patched canary run `20260701_214126_569050`을 완료했다: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - [x] patched canary public title `전 버튜버가 하고 싶은데요`, URL `https://novelpia.com/novel/275975`, `candidate_ledger_status=safe_resolved`를 확인했다.
  - [x] focused tests 3개, `tests.test_expert_main_comment_metadata` 32 OK, `tests.test_promotion_gate_contract + tests.test_candidate_audit` 128 OK, `py_compile` PASS를 확인했다.
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_236_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_data_analytics_artifact.json`
  - [x] Parent/representative packet에서 same guard를 Loop237로 재검증했다.
  - [x] Loop237 parent replay 후에도 residual accounting은 `NO_DELTA_PARENT_REPLAY_AFTER_LOOP236_MIXED_MOVEMENT`로 유지한다.

- 후속 Loop235 상태: focused runtime 재실행 완료 / public title 미복구 / URL-title mismatch 관찰 / Data Analytics validate-render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- Loop235 TODO:
  - [x] `search_character_parenthetical_bridge`와 `direct_image_work_surface_bridge` 단위 계약을 추가했다.
  - [x] focused tests 4개, `tests.test_expert_main_comment_metadata` 29 OK, `tests.test_promotion_gate_contract + tests.test_candidate_audit` 128 OK, `py_compile` PASS를 확인했다.
  - [x] `loop235` 원 런 stuck 상태를 manifest-only incomplete artifact로 보존하고 중단했다.
  - [x] `loop235b` run `20260701_210203_663393`을 완료했다: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - [x] 내부 expert title 확정과 serialized public title `null`을 분리 기록했다.
  - [x] `https://novelpia.com/novel/311328` URL-title mismatch를 다음 architecture seed로 기록했다.
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_235_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_no_go_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_data_analytics_artifact.json`
  - [ ] 다음 patch는 `URL-title verified official detail`을 shared `PromotionDecision` publish precondition으로 추가한다.
  - [ ] URL mismatch candidate는 보존하되 public publish에서는 차단하는 negative control을 추가한다.
  - [ ] Parent/representative replay 전까지 residual accounting을 줄이지 않는다.

- 상태: focused runtime canary 2회 완료 / exact cover-title contract 추가 / 실제 public title 미복구 / Data Analytics validate-render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] `11663540` actual payload focused input을 생성했다.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop234_11663540_direct_image_character_runtime_canary.jsonl`
  - [x] 1차 focused runtime canary를 실행했다.
    - run id `20260701_202952_860752`
    - completed/flushed/pending/failed `1/1/0/0`
    - VLM/OCR `READY`
    - OCR title `전 버튜버가 하고 싶은데요`, official detail URL 존재.
    - final public title `null`, `precision_seed_official_title_requires_review`, `serialized_public_identity_scrubbed`.
  - [x] actual image evidence shape를 반영한 exact cover-title contract를 추가했다.
    - `cover_title`, `work_surface`, `work_anchor` hard image surface.
    - `direct_image_explicit_title_surface`와 `image_ocr_official_detail_title` reason.
  - [x] 2차 focused runtime canary를 실행했다.
    - run id `20260701_203559_843860`
    - completed/flushed/pending/failed `1/1/0/0`
    - VLM/OCR `READY`
    - OCR variant `전 버두바가 하고 싶은데요`, `image_ocr_variant_not_title_in_post`.
    - `주서연(전 버튜버가 하고 싶은데요)` bridge와 official detail URL은 잡혔지만 final public title은 `null`.
  - [x] 검증을 기록했다.
    - focused direct-image tests 3개 PASS.
    - `tests.test_expert_main_comment_metadata`: 27 tests OK.
    - `tests.test_promotion_gate_contract + tests.test_candidate_audit`: 128 tests OK.
    - `py_compile`: PASS.
    - Data Analytics validate/render PASS.
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_234_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_data_analytics_artifact.json`
  - [x] Residual accounting unchanged: `NO_DELTA_TARGETED_CANARY_NO_GO`.
  - [ ] 다음 patch는 `PromotionDecision`과 final serializer 사이의 공용 재평가 단계로 설계한다.
  - [ ] OCR variant, secondary image title, character-page bridge를 후보 보존과 public publish 사이에서 분리하는 negative controls를 추가한다.
  - [ ] Parent/representative replay 전까지 residual accounting을 줄이지 않는다.

## 2026-07-01 regression-safe grounding Loop232 Loop231 safe-loss/variance source-native review

- 상태: review-only / focus 5건 source-native 분해 완료 / Data Analytics validate-render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Loop231 focus 5건을 source/native와 prior review 기준으로 분해했다.
    - `11661876`: `와인의 신`, recurrent overblock, next patch 후보.
    - `11663540`: `전 버튜버가 하고 싶은데요`, OCR/character-title 보존 후보, negative controls 필요.
    - `11695637`: old safe title `도네하지 마라` 복구 금지, `[림월드]변방계에서 회귀자로 살아남기` retarget open.
    - `11660237`: parent에서는 `테라포밍` publish, targeted/parent variance replay 필요.
    - `11706832`: `황제의 딸로 환생했다` 공식 page는 확인됐지만 Loop145 caveat 재개방으로 기록.
  - [x] Native web official page 확인을 기록했다: `와인의 신`, `전 버튜버가 하고 싶은데요`, `테라포밍`, `황제의 딸로 환생했다`, `도네하지 마라`, `[림월드]변방계에서 회귀자로 살아남기`.
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_232_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_data_analytics_artifact.json`
  - [x] Residual accounting unchanged: `NO_DELTA_SOURCE_NATIVE_VARIANCE_REVIEW_ONLY`.
  - [ ] `11661876` recurring overblock patch를 shared `PromotionDecision`/`title_resolution_state`/`work_resolution` 수렴 테스트로 설계한다.
  - [ ] `11663540` OCR/character-title path는 wrong-work negative controls와 함께 설계한다.
  - [ ] `11695637`과 `11706832`은 복구 seed가 아니라 false-safe/caveat guard seed로 유지한다.

## 2026-07-01 regression-safe grounding Loop233 direct-image character shared gate

- 상태: focused code/test patch / `11663540` OCR-character contract 추가 / 신규 focused tests PASS / Data Analytics validate-render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] `expert_main.py` final publication ledger restore에 direct-image character surface 조건을 추가했다.
  - [x] `11663540` 양성 path를 테스트했다: OCR/work-title `전 버튜버가 하고 싶은데요`, character `주서연`, official detail URL이 함께 있을 때 `safe_resolved`로 복구.
  - [x] Wrong-work negative control을 테스트했다: OCR title이 candidate와 맞지 않는 `방구석 여신이 되었다`는 계속 `promotion_blocked`.
  - [x] 검증을 기록했다.
    - 신규 focused tests 2개 PASS
    - `tests.test_expert_main_comment_metadata`: 26 tests OK
    - `tests.test_promotion_gate_contract + tests.test_candidate_audit`: 128 tests OK
    - `py_compile`: PASS
    - Data Analytics validate/render PASS
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_233_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_data_analytics_artifact.json`
  - [x] Residual accounting unchanged: `NO_DELTA_UNIT_CONTRACT_ONLY`.
  - [x] Loop234에서 실제 `11663540` focused runtime canary를 실행했고, public title 미복구를 `NO-GO_PUBLIC_TITLE_NOT_RESTORED`로 기록했다.
  - [ ] `11663540` focused runtime canary를 wrong-work controls와 함께 실행한다.
  - [ ] Parent/representative replay 전까지 residual accounting을 줄이지 않는다.
  - [ ] `11661876` recurrent overblock은 별도 parent-safe shared gate 대상으로 유지한다.

## 2026-07-01 regression-safe grounding Loop228 Loop227 safe-loss source/native review

- 상태: review-only / safe-loss 4건 source-native 검토 완료 / likely_overblock 3, false safe title retarget 1 / Data Analytics validate-render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Loop227 safe-loss 4건을 source/native evidence로 재검토했다.
    - `11660237`: `테라포밍`, likely overblock, title-led evaluation bridge 후보.
    - `11660257`: `암흑가 보스요? 제가요?`, likely overblock, title-led evaluation bridge 후보.
    - `11695637`: Loop225 `도네하지 마라` 복구 금지, `[림월드]변방계에서 회귀자로 살아남기` retarget 후보.
    - `11705231`: `탐식의 재림`, likely overblock, character/comment/native seed convergence 후보.
  - [x] 공식 페이지 존재와 source/native row 정합성을 분리했다: official page exists `4/4`, Loop225 title correct `3/4`.
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_228_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_data_analytics_artifact.json`
  - [x] Residual accounting unchanged: `NO_DELTA_SOURCE_NATIVE_SAFE_LOSS_REVIEW_ONLY`.
  - [ ] `11660237`/`11660257` title-led evaluation bridge patch 후보와 negative control을 설계한다.
  - [ ] `11705231` character/comment/native seed convergence 재발 방지 테스트를 설계한다.
  - [ ] `11695637` retarget lane은 old safe title 복구와 분리한다.

## 2026-07-01 regression-safe grounding Loop227 composite parent replay after Loop226

- 상태: parent replay partial `37/38` + missing-row 단건 보강 `1/1` / composite `38/38` 분석 완료 / safe gain 4, safe loss 4 / semantic `NO-GO / MIXED_MOVEMENT` / Data Analytics artifact 준비 완료 / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Loop227 parent 원 런 `20260701_162837_314765`을 실행하고 checkpoint `37/38`을 확보했다.
  - [x] 원 런이 `large_run_complete=false`, `flushed/pending=24/13` partial임을 승인 근거에서 분리했다.
  - [x] 누락 `11698897`을 단건 재실행해 composite 38행 분석을 완성했다.
  - [x] Safe gain 4건 기록: `11663521`, `11668288`, `11674712`, `11706832`.
  - [x] Safe loss 4건 기록: `11660237`, `11660257`, `11695637`, `11705231`.
  - [x] Residual accounting unchanged: `NO_DELTA_COMPOSITE_PARENT_REPLAY_MIXED_MOVEMENT`.
  - [x] Safe loss 4건 source/native 검토를 Loop228에서 완료했으며 approval 근거로는 계속 쓰지 않는다.
  - [ ] 다음 patch는 final scrub 복구보다 upstream authoritative promotion state convergence에 둔다.

## 2026-07-01 regression-safe grounding Loop226 trace candidate priority

- 상태: deterministic trace/ledger patch implemented / 신규 focused tests GO / promotion gate bundle GO / Data Analytics validate-render PASS / 새 parent replay NOT_RUN / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Loop225 safe-loss 3건의 `publish_contract_trace.pre_gate_candidate` 품질을 재확인했다.
    - `11668288`: `가챠펑크` -> `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`
    - `11674712`: `호각임` -> `이 무림의 미친년은 나야` / `https://novelpia.com/novel/217943?sid=main5`
    - `11706832`: `표절물인가` -> `황제분충`
  - [x] `comment_surface`/`hold_without_promotion` 후보보다 더 강한 보존 후보를 trace candidate로 우선하는 contract를 추가했다.
  - [x] publish gate는 열지 않았다: 세 행 모두 `promotion_blocked`, `publish_allowed=false`.
  - [x] 검증을 기록했다.
    - 신규 focused tests 2개 PASS
    - `tests.test_expert_main_comment_metadata`: 23 tests OK
    - `tests.test_promotion_gate_contract + tests.test_expert_main_comment_metadata`: 43 tests OK
    - `py_compile` PASS
    - Data Analytics validate/render PASS
  - [x] 한국어 report/review/Data Analytics artifacts를 남겼다.
    - `docs/devs/loop_reports/LOOP_226_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop226_trace_candidate_priority_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop226_trace_candidate_priority_data_analytics_artifact.json`
  - [x] Residual accounting unchanged: `NO_DELTA_TRACE_LEDGER_ONLY`, next actionable `131`, P0/P1/P2 `0/61/70`.
  - [ ] 다음 parent/representative replay에서 Loop225 safe-loss movement가 줄었는지 확인한다.
  - [ ] `11674712` character bridge와 `11706832` alias caveat은 source/native 안정성 확인 전까지 approval 근거로 쓰지 않는다.

## 2026-07-01 regression-safe grounding Loop224 parent replay after Loop223 patch checkpoint

- 상태: Loop223b focused patch parent replay executed / runtime GO / VLM-OCR READY / Data Analytics validate-render PASS / `11705231` survived / `11661876` failed parent survival / `11698880` safe-loss recurred / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Run 38-row parent/representative replay after Loop223b.
    - run id `20260701_141454_629022`
    - result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop224_parent_replay_after_loop223_title_field_patch_result.json`
    - completed/flushed/pending/failed `38/38/0/0`
    - image_post_count `24`, VLM/OCR `READY`
  - [x] Run runtime audit.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_runtime_audit.md`
    - runtime contract `GO`, issues `[]`
  - [x] Compare Loop182/Loop221/Loop224 parent status counts.
    - Loop182 `safe_resolved=12,promotion_blocked=24,hold_without_candidates=1,output_consistency_lint=1`
    - Loop221 `safe_resolved=9,promotion_blocked=27,hold_without_candidates=1,output_consistency_lint=1`
    - Loop224 `safe_resolved=10,promotion_blocked=26,hold_without_candidates=1,output_consistency_lint=1`
  - [x] Record changed Loop221 -> Loop224 rows: `11666713`, `11668288`, `11695637`, `11698880`, `11705231`.
  - [x] Persist Korean report/review/Data Analytics artifacts.
    - `docs/devs/loop_reports/LOOP_224_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_data_analytics_artifact.json`
  - [x] Preserve no-delta accounting: `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`, next actionable `131`, P0/P1/P2 `0/61/70`.
  - [ ] Decompose `11661876` architecture gap: `scope_current_work` and `row_discusses_work_as_work` exist, but `context_only/unresolved` still scrubs public publish.
  - [ ] Decompose `11698880` regression against Loop157/158 stable-alias descriptor guard.
  - [ ] Source/native review Loop224 movement rows before any residual decrement claim.
  - [ ] Move next patch direction from final scrub restore to upstream authoritative promotion decision ledger / title-resolution state convergence.

## 2026-07-01 보고서 한국어 지침 고정

- 상태: 사용자 요청에 따라 보고서 작성 언어와 최소 의미 보존 규칙을 repo 지침에 재확인/보강했다.
- TODO:
  - [x] `AGENTS.md`의 한국어 보고 원칙 확인.
  - [x] `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`의 회차 보고서 계약 확인.
  - [x] `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`, `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `docs/devs/OPERATION_QUALITY_CHECKLIST.md`에 보조 지침 보강.
  - [x] 보고서는 한국어로 쓰고, 간략하되 의미/근거/산출물 경로/gate 상태를 생략하지 않는 규칙을 유지.

## 2026-07-01 regression-safe grounding Loop223 publish-contract title-field patch checkpoint

- 상태: Loop222 strong patch candidates implemented / Loop223b focused runtime GO / both target rows safe_resolved / Data Analytics validate-render PASS / full unittest PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Patch and test `11661876` current_work/high final scrub overblock.
  - [x] Patch and test `11705231` official title field separation.
  - [x] Run Loop223 first canary and record partial fix.
    - `11661876` remained `promotion_blocked`
    - `11705231` recovered to `탐식의 재림`
  - [x] Run Loop223b final-contract restore canary.
    - run id `20260701_134929_838421`
    - completed/flushed/pending/failed `2/2/0/0`
    - `11661876` -> `와인의 신`, `https://novel.munpia.com/494781`
    - `11705231` -> `탐식의 재림`, `https://page.kakao.com/content/50219568`
  - [x] Persist Korean report/review/Data Analytics artifacts.
    - `docs/devs/loop_reports/LOOP_223_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_data_analytics_artifact.json`
  - [x] Run full unittest discover: `1335` tests OK.
  - [x] Preserve no-delta accounting: next actionable `131`, P0/P1/P2 `0/61/70`.
  - [ ] Rerun parent/representative packet before any residual decrement claim.
  - [ ] Review `11661876` URL movement in parent scope before treating it as stable.

## 2026-07-01 regression-safe grounding Loop222 safe-loss source/native review checkpoint

- 상태: Loop221 safe-loss 6건 source/native review 완료 / no new canary / no production code change / Data Analytics validate/render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Review Loop221 safe-loss rows with source/native evidence.
    - rows: `11658620`, `11660237`, `11661876`, `11668288`, `11695623`, `11705231`
  - [x] Persist Korean report/review/Data Analytics artifacts.
    - `docs/devs/loop_reports/LOOP_222_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_data_analytics_artifact.json`
  - [x] Record verdict split: `likely_overblock=3`, `ambiguous_hold=2`, `title_field_bug=1`.
  - [x] Mark `11661876` as the first focused publish-contract overblock patch candidate.
  - [x] Mark `11705231` as the character/entity surface vs official-title field split patch candidate.
  - [x] Preserve no-delta accounting: next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Patch and test `11661876` current_work/high final scrub overblock.
  - [x] Patch and test `11705231` official title field separation.
  - [ ] Review Loop221 safe-gain 3건 before any residual decrement claim.

## 2026-07-01 regression-safe grounding Loop221 parent replay after direct alias probe checkpoint

- 상태: Loop220 broader parent replay executed / runtime GO / Data Analytics validate/render PASS / direct alias target `11713222` recovered in parent scope / status count worsened from `safe_resolved=12` to `9` / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Run 38-row parent/representative replay after Loop220.
    - run id `20260701_120437_234858`
    - result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop221_parent_replay_after_direct_alias_probe_result.json`
  - [x] Run runtime audit.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_runtime_audit.md`
    - runtime contract `GO`, completed/flushed/pending/failed `38/38/0/0`
  - [x] Compare against Loop182 parent baseline.
    - Loop182 `safe_resolved=12,promotion_blocked=24,hold_without_candidates=1,output_consistency_lint=1`
    - Loop221 `safe_resolved=9,promotion_blocked=27,hold_without_candidates=1,output_consistency_lint=1`
  - [x] Confirm `11713222` parent recovery.
    - `잘생기면 편해지는 인방 생활`, `https://novelpia.com/novel/384016`
  - [x] Persist Korean report/review/Data Analytics artifacts.
    - `docs/devs/loop_reports/LOOP_221_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_data_analytics_artifact.json`
  - [x] Preserve no-delta accounting: next actionable `131`, P0/P1/P2 `0/61/70`.
  - [ ] Review the 9 changed rows with source/native evidence.
    - Safe-loss 6건은 Loop222에서 source/native review 완료; safe-gain 3건은 아직 별도 review 필요.
  - [x] Decompose 6 safe-loss rows before any residual decrement claim.

## 2026-07-01 regression-safe grounding Loop220 direct alias probe checkpoint

- 상태: `11713222` direct body alias probe repair implemented / Loop220 runtime GO / full unittest GO / Data Analytics validate/render PASS / packet safe count improved to `3/5` / residual accounting no-delta until broader replay / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Add direct non-comment worklike alias probe collection in `orchestrator.py`.
  - [x] Preserve direct alias official/community/author/abbreviation queries through semantic no-work pruning.
  - [x] Boost direct alias queries and defer broad official-hit early stop while direct alias probes remain unprocessed.
  - [x] Add focused regression test for `잘생인방` recovery and comment-only `잘생인편` exclusion.
  - [x] Run verification: `py_compile` PASS, focused direct-alias PASS, title-lead inferred guard `157 OK`, focused contract bundle `39 OK`, candidate-audit `102 OK`, full unittest discover `1332 OK`.
  - [x] Run Loop220 replay and audit: run id `20260701_114043_668022`, runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`.
  - [x] Create Korean loop report and review artifacts.
    - `docs/devs/loop_reports/LOOP_220_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_review.json`
  - [x] Persist Data Analytics artifact.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_data_analytics_artifact.json`
  - [x] Preserve no-delta accounting until broader replay: next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Run broader replay or parent/collateral packet before any residual decrement claim.
    - Loop221 parent replay executed, but mixed movement makes the result no-delta and review-locked.
  - [ ] Monitor precision for direct alias probes so generic aliases and comment-only previous-work candidates do not become public titles.

## 2026-07-01 regression-safe grounding Loop219 shared gate unconfirmed-alias checkpoint

- 상태: `11669928` shared gate unconfirmed-alias repair implemented / Loop219 runtime GO / full unittest GO / Data Analytics validate/render PASS / `11713222` and `11674712` packet regressions open / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Add shared current-work gate exemption for `unconfirmed_alias_official_detail_bridge` in `candidate_audit.py`.
  - [x] Keep the exemption narrow: publish/current_work gate decision, official-detail URL support, title/URL match, no hard context-only/conflict flags.
  - [x] Add focused tests for Loop218-like recovery and context-only non-exemption.
  - [x] Run verification: `py_compile` PASS, focused candidate-audit `4 OK`, full candidate-audit `102 OK`, focused contract bundle `39 OK`, full unittest discover `1331 OK`.
  - [x] Run Loop219 replay and audit: run id `20260701_110936_416066`, runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`.
  - [x] Create Korean loop report and review artifacts.
    - `docs/devs/loop_reports/LOOP_219_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_review.json`
  - [x] Persist Data Analytics artifact.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_data_analytics_artifact.json`
  - [x] Preserve no-delta accounting: next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Review `11713222` previous-work/comment candidate recontamination.
    - Loop220 recovered current-work title `잘생기면 편해지는 인방 생활`; broader replay remains open.
  - [x] Review `11674712` character-bridge/J11-title-drift hold recurrence.
    - Loop220 recovered `이 무림의 미친년은 나야`; broader replay remains open.

## 2026-07-01 regression-safe grounding Loop218 character bridge scope trace checkpoint

- 상태: `11674712` character bridge scope/URL recovery implemented / Loop218 runtime GO / full unittest GO / Data Analytics validate/render PASS / `11669928` packet regression open / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Recover official-detail URL from search evidence for blocked candidate trace.
  - [x] Infer `current_work` scope only when official-detail search evidence and row context converge without hard context-only flags.
  - [x] Add focused regression tests for recovered official URL/scope and no-official-detail scope-null preservation.
  - [x] Run verification: `py_compile` PASS, focused new tests `2 OK`, focused contract bundle `39 OK`, character bridge focused tests `2 OK`, full unittest discover `1329 OK`, `git diff --check` PASS with CRLF warnings only.
  - [x] Run Loop218 replay and audit: run id `20260701_104624_623831`, runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`.
  - [x] Create Korean loop report and review artifacts.
    - `docs/devs/loop_reports/LOOP_218_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_review.json`
  - [x] Persist Data Analytics artifact.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_data_analytics_artifact.json`
  - [x] Preserve no-delta accounting: next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Review `11669928` current-work but candidate-only regression: `unconfirmed_alias_official_detail_bridge`.
    - Loop219 fixed this immediate cause; packet closure remains blocked by `11713222` and `11674712`.

## 2026-07-01 regression-safe grounding Loop214-217 exact-alias image/OCR context trace checkpoint

- 상태: `11660257` exact-alias image/OCR context decomposition complete as trace/rationale / Loop217 runtime GO / final code tests GO / Data Analytics validate/render PASS / residual accounting no-delta / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Keep report-writing instruction in active repo guidance.
    - 보고서는 한국어로 작성한다. 간략하게 쓰되 의미, 근거, 산출물 경로, 게이트 상태를 생략하지 않는다.
  - [x] Add conservative blocked-candidate scope inference in `expert_main.py` final result-contract scrub.
  - [x] Require nonpromotable image/OCR context before inferring `context_only` for blocked exact-alias candidates.
  - [x] Propagate promotion-block/candidate-audit lint reasons into `publish_contract_trace` and gate decision reasons.
  - [x] Add tests for image/OCR context-only trace and text-only alias non-inference.
  - [x] Run verification: `py_compile` PASS, focused new tests `2 OK`, focused contract bundle `37 OK`, full unittest discover `1327 OK`, `git diff --check` PASS with CRLF warnings only.
  - [x] Run Loop217 replay and audit: run id `20260701_102032_074772`, runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`.
  - [x] Create Korean loop report and review artifacts.
    - `docs/devs/loop_reports/LOOP_214_217_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop214_217_exact_alias_image_context_trace_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop214_217_exact_alias_image_context_trace_review.json`
  - [x] Persist Data Analytics artifact.
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop214_217_exact_alias_image_context_trace_data_analytics_artifact.json`
  - [x] Preserve no-delta accounting: next actionable `131`, P0/P1/P2 `0/61/70`.
  - [ ] Review `11674712` scope null / character bridge variance before parent/collateral replay.

## 2026-07-01 regression-safe grounding Loop193-213 scope-state, final-publication ledger, previous-work preservation, and title-led alias guard checkpoint

- 상태: scope-state contract implemented / publish trace scope propagation implemented / acknowledged previous-work override scope gate implemented / batch-alias public-title scope gate implemented / direct OCR work-surface scope gate implemented / final-publication ledger packet contract GO / upstream resolved-public-title gate implemented / Loop205-208 packet variance review complete / Loop209-211 previous-work candidate preservation complete / Loop212-213 title-led alias guard repeat evidence complete / five-row packet replay runtime GO / packet semantic REVIEW-LOCKED / inferred publish decisions CLOSED_FOR_PACKET / residual accounting unchanged / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Persist report-writing instruction.
    - Reports must be Korean, concise, and must not omit meaning, evidence, artifact paths, or gate status.
  - [x] Confirm the pasted goal source still requires continuous loop execution until the documented stop condition.
  - [x] Confirm current active goal is already architecture-integrated and not complete.
  - [x] Reframe the next goal step around an explicit scope-state layer before `can_publish_title(...)`.
  - [x] Update `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`.
  - [x] Update `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md`.
  - [x] Update checklist/history/register/verification docs for the docs-only contract change.
  - [x] Inventory first current scope writer: `_can_promote_title_after_semantic_no_work`.
  - [x] Add `ScopeState` with categories: `current_work`, `previous_work`, `secondary_reference`, `author_new_work`, `image_ocr_derived_work`, `platform_meta_nonwork`, `context_only`, `unknown`.
  - [x] Add focused contract tests for `11669928`, `11713222`, and `11695623` without post_id/title-specific production logic.
  - [x] Feed scope kind/conflicts into `PromotionDecision.reason_codes` and `_promotion_gate_state` for semantic-no-work title promotion.
  - [x] Run focused verification.
    - `venv\Scripts\python.exe -m py_compile src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`: PASS
    - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`: PASS, `11 tests OK`
  - [x] Render Data Analytics artifact `Loop193 Scope-State Contract Checkpoint`.
  - [x] Create Loop193 report/review artifacts.
    - `docs/devs/loop_reports/LOOP_193_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_review.json`
  - [x] Propagate scope-state into publish-contract trace as Loop194.
    - `publish_contract_trace.scope_state`
    - `publish_contract_trace.gate_decision.scope`
    - scope reason-code backfill
  - [x] Run Loop194 focused verification.
    - `venv\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`: PASS
    - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`: PASS, `23 tests OK`
  - [x] Render Data Analytics artifact `Loop194 Publish Trace Scope Propagation Checkpoint`.
  - [x] Create Loop194 report/review artifacts.
    - `docs/devs/loop_reports/LOOP_194_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_review.json`
  - [x] Wire acknowledged previous-work override path through shared scope gate as Loop195.
    - extracted `_record_public_title_gate_decision(...)`
    - `acknowledged_previous_work_comment_override` now records previous-work scope conflicts before public title replacement
    - current-work alias vs previous-work alias conflict stays candidate-only
  - [x] Run Loop195 verification.
    - `venv\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`: PASS
    - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`: PASS, `24 tests OK`
    - `venv\Scripts\python.exe -m unittest discover --start-directory tests`: PASS, `1309 tests OK`
  - [x] Render Data Analytics artifact `Loop195 Acknowledged Previous-Work Scope Gate Checkpoint`.
  - [x] Create Loop195 report/review artifacts.
    - `docs/devs/loop_reports/LOOP_195_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop195_acknowledged_previous_work_scope_gate_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop195_acknowledged_previous_work_scope_gate_review.json`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop195_acknowledged_previous_work_scope_gate_data_analytics_artifact.json`
  - [x] Wire batch-alias public-title publish path through shared scope gate as Loop196.
    - added `_record_batch_alias_public_title_gate_decision(...)`
    - remembered only batch-alias candidates that actually reach public identity output
    - recorded `scope_kind=current_work` and `batch_alias_candidate_accepted` bridge evidence in the final candidate ledger
  - [x] Run Loop196 verification.
    - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py tests\test_agentic_pipeline_rework.py`: PASS
    - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`: PASS, `13 tests OK`
    - targeted batch-alias rework tests: PASS, `2 tests OK`
    - combined promotion/rework bundle: PASS, `15 tests OK`
    - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`: PASS, `25 tests OK`
    - `venv\Scripts\python.exe -m unittest tests.test_known_title_abbreviation_support tests.test_title_lead_search_inferred_guard -v`: PASS, `182 tests OK`
    - `venv\Scripts\python.exe -m unittest discover --start-directory tests`: PASS, `1310 tests OK`
  - [x] Render Data Analytics artifact `Loop196 Batch Alias Scope Gate Checkpoint`.
  - [x] Create Loop196 report/review artifacts.
    - `docs/devs/loop_reports/LOOP_196_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_review.json`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_data_analytics_artifact.json`
  - [x] Wire direct OCR work-surface lock / stale canonical rescue bypass path through shared scope gate as Loop197.
    - added `_record_direct_image_work_surface_gate_decision(...)`
    - recorded `scope_kind=current_work` and `direct_image_work_surface_lock` bridge evidence in the final candidate ledger
    - kept the direct OCR fixture's stale canonical rescue scan skipped
  - [x] Run Loop197 verification.
    - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py tests\test_agentic_pipeline_rework.py`: PASS
    - direct OCR contract: PASS, `1 test OK`
    - direct OCR/canonical rescue bypass integration: PASS, `1 test OK`
    - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`: PASS, `14 tests OK`
    - direct OCR focused bundle: PASS, `5 tests OK`
    - rank OCR/lock suites: PASS, `30 tests OK`
    - expert metadata + promotion bundle: PASS, `26 tests OK`
    - `venv\Scripts\python.exe -m unittest discover --start-directory tests`: PASS, `1311 tests OK`
  - [x] Render Data Analytics artifact `Loop197 Direct OCR Scope Gate Checkpoint`.
  - [x] Create Loop197 report/review artifacts.
    - `docs/devs/loop_reports/LOOP_197_REPORT_20260701.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_review.json`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_data_analytics_artifact.json`
  - [x] Rerun the prior five-row packet as the next runtime loop before any residual accounting decrement.
    - Loop198 run id `20260701_055004_272309`: runtime `GO`, `5/5/0/0`, `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`.
    - Loop198 gap: `11669928` safe-resolved as `탑의 성좌들이 날 애호한다` without `publish_contract_trace`.
  - [x] Wire title-led alias public-title recorder as Loop199 after the trace-free safe-publication gap.
    - added `_record_title_led_alias_public_title_gate_decision(...)`
    - added `test_title_led_alias_public_title_records_current_scope_gate`
  - [x] Run Loop199 verification.
    - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py`: PASS
    - title-led contract: PASS, `1 test OK`
    - promotion-gate suite: PASS, `15 tests OK`
    - title-led acceptance test: PASS, `1 test OK`
    - `venv\Scripts\python.exe -m unittest discover --start-directory tests`: PASS, `1312 tests OK`
  - [x] Run Loop199 packet replay.
    - run id `20260701_060336_094994`: runtime `GO`, `5/5/0/0`, `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`.
  - [x] Render Data Analytics artifact `Loop199 Five-Row Packet Replay Review`.
  - [x] Keep residual accounting unchanged after Loop198/199.
  - [x] Unify final publication ledger before another acceptance replay.
    - Added `_sync_final_publication_ledger_contract(...)` in `expert_main.py`.
    - Loop202 trace coverage `5/5`; final ledger consistency `PASS`.
    - Data Analytics artifact `Loop202 Final Publication Ledger Review` validate/render PASS.
  - [x] Move inferred final-publication decisions upstream into explicit shared promotion-gate records.
    - Added `_record_resolved_public_title_gate_decision(...)` in `src/llm_batch/agentic_pipeline.py`.
    - Preserved `candidate_ledger.promotion_gate_state` and `promotion_gate_evidence` through `build_candidate_audit_fields(...)`.
    - Loop204 has `inferred_publish_decision_count=0`, trace coverage `5/5`, and final-ledger consistency issues `0`.
    - Data Analytics artifact `Loop204 Resolved Public Title Gate Review` validate/render PASS.
  - [x] Review Loop203/204 packet variance before parent/collateral replay.
    - Loop205-208 reviewed the packet movement and added targeted architecture hardening.
    - Loop208 run id `20260701_080838_271200`: runtime `GO`, `5/5/0/0`, VLM/OCR `READY`, `safe_resolved=3`, `promotion_blocked=2`, public title count `3`, inferred publish decisions `0`.
    - `11695623` remains candidate-only despite official-detail candidate preservation; `11674712` is restored through character-alias official-detail support; `11713222` remains review-locked.
    - Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop205_208_packet_variance_scope_block_review.md`.
  - [x] Resolve the immediate `11713222` current-work versus previous-work candidate preservation gap.
    - Loop211 run id `20260701_085524_956588`: runtime `GO`, `5/5/0/0`, VLM/OCR `READY`.
    - `11713222` now publishes `잘생기면 편해지는 인방 생활`; previous-work `잘생기면 인생이 편하다` is preserved candidate-only with conflict evidence.
    - Full unittest discover: PASS, `1324 tests OK`.
    - Data Analytics artifact validate PASS; render output was truncated, so keep render status conservative.
    - Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop211_previous_work_candidate_preservation_review.md`.
  - [x] Resolve the immediate `11669928` title-led unconfirmed-alias demotion cause.
    - Added a narrow candidate-audit exemption for short title-led aliases with official evidence title/snippet support and consumption/status tokens.
    - `py_compile` PASS; focused candidate-audit tests `3 tests OK`; `tests.test_candidate_audit` `100 tests OK`; title-led acceptance regression `1 test OK`.
    - Loop212 run id `20260701_093147_646251`: runtime `GO`, `5/5/0/0`, VLM/OCR `READY`, `11669928` publishes.
    - Loop213 run id `20260701_093833_697684`: runtime `GO`, `5/5/0/0`, VLM/OCR `READY`, `11669928` publishes again.
    - Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop212_213_title_led_unconfirmed_alias_bridge_review.md`.
  - [ ] Rerun parent/collateral packets only after repeat stability is reviewed.
  - [ ] Decompose remaining `11660257` exact-alias + image/OCR context hold before any residual decrement.

## 2026-07-01 regression-safe grounding Loop191/192 publish-trace packet replay

- 상태: Loop190 이후 packet replay 완료 / Loop191 runtime GO / Loop192 runtime GO / trace coverage GO / packet semantic NO-GO / residual accounting `NO_DELTA_PACKET_REPLAY_VARIANCE_ALL_BLOCKED` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Run Loop191 on the prior five-row packet after Loop190 instrumentation.
    - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop191_after_publish_trace_packet_replay_result.json`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop191_after_publish_trace_packet_replay_result_manifest.json`
    - runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop191_after_publish_trace_packet_replay_runtime_audit.md`
  - [x] Record Loop191 result: `safe_resolved=2`, `promotion_blocked=3`, public title count `2`, trace rows `3`.
  - [x] Patch Loop191 trace gap where `11660257` candidate evidence did not populate `pre_gate_candidate`.
  - [x] Add focused regression for candidate-ledger trace source fallback.
  - [x] Run `py_compile` and focused unittest bundle, `12 tests OK`.
  - [x] Run Loop192 after the trace-source fallback patch.
    - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop192_after_candidate_ledger_trace_source_fix_result.json`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop192_after_candidate_ledger_trace_source_fix_result_manifest.json`
    - runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_runtime_audit.md`
    - review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_review.md`
    - report: `docs/devs/loop_reports/LOOP_191_192_REPORT_20260701.md`
  - [x] Record Loop192 result: trace coverage `5/5`, pre-gate title rows `5/5`, but `safe_resolved=0`, `promotion_blocked=5`, public title count `0/5`.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.
  - [x] Extract root-cause seeds for `11669928` and `11713222` safe-resolved to promotion-blocked movement.
    - `11669928`: `unconfirmed_alias_official_detail_bridge` blocks public publish despite pre-gate `탑의 성좌들이 날 애호한다` / `https://novelpia.com/novel/377032`.
    - `11713222`: gate decision includes `row_discussion_missing`, `context_only`, `official_detail_url`, `alias_bridge`; current-work and previous-work candidates both remain in the ledger.
  - [ ] Fix or explicitly hold `11669928` after deciding whether title-lead exact alias + official/detail + discontinued/unavailable context can publish.
  - [ ] Fix or explicitly hold `11713222` after resolving current-work versus previous-work alias scope.
  - [ ] Review `11695623` candidate variance (`[림월드]...` vs `그래-맞아`) before accepting any packet-level fix.

## 2026-07-01 regression-safe grounding Loop190 publish-contract trace unit checkpoint

- 상태: Loop189 publish-contract gap에 대한 단위 계측 완료 / `GO_UNIT_ONLY` / packet replay `OPEN` / residual accounting `NO_DELTA_UNIT_INSTRUMENTATION_ONLY` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Add `publish_contract_trace` to promotion-blocked serialized result scrub.
  - [x] Persist `pre_gate_candidate`, `gate_decision`, `post_gate_identity`, `reason_codes`, and `bypassed_gate=false`.
  - [x] Add `publish_ledger` to split candidate preservation from public publish.
  - [x] Mirror publish trace and ledger inside `candidate_ledger`.
  - [x] Add focused regression assertions in `tests/test_expert_main_comment_metadata.py`.
  - [x] Run `venv\Scripts\python.exe -m py_compile expert_main.py`.
  - [x] Run `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata -v`.
  - [x] Write review artifacts:
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_review.json`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_review.md`
    - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_data_analytics_artifact.json`
    - `docs/devs/loop_reports/LOOP_190_REPORT_20260701.md`
  - [x] Data Analytics artifact validation PASS.
  - [x] Record render as `ATTEMPTED_OUTPUT_TRUNCATED` because the one render call response was truncated before confirmation.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.
  - [x] Rerun prior five-row packet after Loop190 instrumentation.
    - Loop191/192 completed; runtime `GO` but semantic packet `NO-GO`.
  - [x] Use `publish_contract_trace` per `post_id` before any residual accounting decrement.
    - Loop192 trace coverage is `5/5`; no residual accounting decrement.

## 2026-07-01 regression-safe grounding Loop189 packet replay architecture gap

- 상태: Loop188 title-led bridge packet replay 완료 / runtime `GO` / packet semantic `NO-GO` / residual accounting `NO_DELTA_PACKET_REPLAY_REGRESSED_TO_ALL_PROMOTION_BLOCKED` / publish-contract gap `OPEN` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Rerun prior Loop184 five-row packet after Loop188 title-led bridge.
    - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop189_loop184_followup_after_title_led_bridge_result.json`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop189_loop184_followup_after_title_led_bridge_result_manifest.json`
    - runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_runtime_audit.md`
    - review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_review.md`
    - report: `docs/devs/loop_reports/LOOP_189_REPORT_20260701.md`
  - [x] Confirm manifest completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
  - [x] Confirm runtime contract audit `GO`, issues `[]`.
  - [x] Data Analytics artifact `Loop189 Packet Replay Architecture Gap Review` validate/render PASS.
  - [x] Record packet semantic regression: `safe_resolved=0`, `promotion_blocked=5`, public title count `0/5`.
  - [x] Preserve candidate evidence as candidate-only and do not claim public title promotion.
  - [x] Keep residual accounting unchanged: full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Add explicit publish-contract trace fields: `pre_gate_candidate`, `gate_decision`, `post_gate_identity`, `reason_codes`, `bypassed_gate=false`.
    - Loop190 completed the unit serialized-contract instrumentation; packet replay remains open.
  - [x] Split candidate preservation ledger from public publish ledger in artifacts/tests.
    - Loop190 added `publish_ledger` and focused assertions; packet replay artifact coverage remains open.
  - [ ] Add scope-state representation before `can_publish_title(...)`: current-work, previous-work, secondary-reference, author-new-work, image/OCR-derived work, platform-meta/nonwork.
  - [ ] Re-run packet-level deterministic replay after publish-contract instrumentation.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 regression-safe grounding Loop187 nested gate scrub follow-up

- 상태: Loop186 `11713222` nested serialization/ledger collision 단위 보정 완료 / runtime `GO` / residual accounting `NO_DELTA_NESTED_GATE_SCRUB_REVIEW_ONLY` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Patch `expert_main.py` promotion-blocked result contract so nested `novel_identity` public title/URL is scrubbed when `promotion_decision.publish_allowed=false`.
  - [x] Add regression test for gate-blocked nested public title scrub.
  - [x] Run touched-file `py_compile`.
  - [x] Run focused promotion-gate/result-contract unittest bundle.
  - [x] Rerun Loop184 five-row packet after nested gate scrub patch.
    - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop187_loop186_followup_after_nested_gate_scrub_result.json`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop187_loop186_followup_after_nested_gate_scrub_result_manifest.json`
    - runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_runtime_audit.md`
    - review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_review.md`
    - report: `docs/devs/loop_reports/LOOP_187_REPORT_20260701.md`
  - [x] Confirm manifest completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
  - [x] Confirm runtime contract audit `GO`, issues `[]`.
  - [x] Data Analytics artifact `Loop187 Nested Gate Scrub Follow-up Review` validate/render PASS.
  - [x] Record Loop187 ledger split `safe_resolved=2`, `promotion_blocked=3`.
  - [x] Keep `11660257` candidate-hold as stable only for candidate preservation, not approval.
  - [ ] Root-cause `11669928` new safe loss to deliberate-null / explicit-alias bridge review.
  - [ ] Keep `11713222` as alias-precedence variance because Loop186 and Loop187 disagree.
  - [ ] Keep `11695623` as VLM/OCR recommendation-context hold until source/native evidence resolves it.
  - [x] Keep residual accounting unchanged: full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 regression-safe grounding Loop186 collateral follow-up

- 상태: Loop184 five-row packet 재실행 완료 / runtime `GO` / residual accounting `NO_DELTA_COLLATERAL_FOLLOWUP_REVIEW_ONLY` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Rerun Loop184 five-row packet after Loop185 candidate-hold patch.
    - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop186_loop184_followup_after_candidate_hold_patch_result.json`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop186_loop184_followup_after_candidate_hold_patch_result_manifest.json`
    - runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_runtime_audit.md`
    - review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_review.md`
    - report: `docs/devs/loop_reports/LOOP_186_REPORT_20260701.md`
  - [x] Confirm manifest completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
  - [x] Confirm runtime contract audit `GO`, issues `[]`.
  - [x] Confirm `11660257` candidate-hold fix remains stable in packet scope.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Record Loop186 ledger movement: Loop184 `safe_resolved=4`, `promotion_blocked=1` -> Loop186 `safe_resolved=2`, `promotion_blocked=3`.
  - [ ] Root-cause `11695623` safe loss to image/OCR and recommendation-context promotion block.
  - [ ] Root-cause `11713222` status/title collision and alias-precedence label policy.
  - [ ] Keep `11674712` as character-bridge variance/quarantine evidence until native character-source proof and parent stability are recorded.
  - [x] Keep residual accounting unchanged: full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 regression-safe grounding Loop185 exact-alias candidate hold

- 상태: `11660257` candidate-preservation fix 완료 / runtime `GO` / residual accounting `NO_DELTA_TARGETED_SINGLE_ROW_ONLY` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Root-cause Loop184 `11660257` generic/platform-title drift.
  - [x] Skip platform/listing/structural titles during search-result official alias candidate recovery.
  - [x] Preserve blocked `search_evidence_alias_inference` exact-alias candidates as `hold_without_promotion` candidate evidence.
  - [x] Add tests for platform-title skip and blocked exact-alias hold preservation.
  - [x] Run touched-file `py_compile`.
  - [x] Run focused and affected unittest suites.
  - [x] Run Loop185 one-row canary with VLM/OCR on and `--slang-db off`.
    - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop185_11660257_exact_alias_candidate_hold_result.json`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop185_11660257_exact_alias_candidate_hold_result_manifest.json`
    - runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_runtime_audit.md`
    - review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_review.md`
    - report: `docs/devs/loop_reports/LOOP_185_REPORT_20260701.md`
  - [x] Confirm candidate ledger preserves `암흑가 보스요? 제가요?` / `https://novelpia.com/novel/384111` with `promotion_policy=hold_without_promotion`.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Rerun Loop184 five-row packet before any residual accounting delta.
    - Loop186 result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop186_loop184_followup_after_candidate_hold_patch_result.json`
    - conclusion: candidate-hold stable for `11660257`, but packet movement remains no-delta.
  - [ ] Keep `11713222` alias-precedence label review open.
  - [ ] Keep `11674712` character-bridge variance/quarantine open.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 regression-safe grounding Loop183 source/native movement review

- 상태: Loop184 targeted follow-up 완료 / runtime `GO` / residual accounting `NO_DELTA_TARGETED_FOLLOWUP_ONLY` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Review Loop182 safe gains `11669928`, `11695623` before accepting closure.
  - [x] Review Loop182 safe losses `11660257`, `11674712`, `11713222` as conservative holds, recall regressions, or variance rows.
  - [x] Create Loop183 review JSON/MD artifacts.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create `docs/devs/loop_reports/LOOP_183_REPORT_20260701.md`.
  - [x] Keep residual accounting unchanged: full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable `131`, P0/P1/P2 `0/61/70`.
  - [x] Build next targeted follow-up packet around `11660257`, `11695623`, and `11713222`.
    - input: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop184_loop183_source_native_followup_5.jsonl`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop184_loop183_source_native_followup_5_manifest.json`
  - [x] Keep `11669928` and `11674712` as variance-attention controls unless repeat/parent stability clears them.
  - [x] Run Loop184 targeted follow-up with VLM/OCR on and `--slang-db off`.
    - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop184_loop183_source_native_followup_5_result.json`
    - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop184_loop183_source_native_followup_5_result_manifest.json`
    - runtime audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_runtime_audit.md`
    - review: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_review.md`
    - report: `docs/devs/loop_reports/LOOP_184_REPORT_20260701.md`
  - [x] Record Loop184 ledger split `safe_resolved=4`, `promotion_blocked=1`, runtime `GO`, and Data Analytics validate/render PASS.
  - [x] Repair `11660257` candidate-preservation path for exact-alias recall against generic/platform-title drift; keep broader replay/accounting open.
  - [ ] Keep `11713222` open for direct-body current-work alias vs comment previous-work alias label/preference review.
  - [ ] Keep `11674712` as character-bridge variance/quarantine evidence until native character-source proof and parent stability are recorded.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 regression-safe grounding Loop180 residual queue return

- 상태: Loop180 P1 `image_anchor_gate` canary 완료 / strict runtime audit `REVIEW` / semantic gate `REVIEW-LOCKED` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Create Loop180 9-row input and manifest for P1 `recall_loss_review / image_anchor_gate`.
  - [x] Run `expert_main.py` with VLM/OCR on, `--reuse-shards-only`, `--slang-db off`, effective parallel `9`.
  - [x] Confirm manifest completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`.
  - [x] Confirm VLM/OCR `READY`, image_post_count `9`.
  - [x] Record row ledger split: `safe_resolved=5`, `promotion_blocked=4`, relevant `8`, identified `5`.
  - [x] Run `tools/audit_goal_test_run_contract.py`.
  - [x] Preserve strict runtime audit `REVIEW` because search health was included in the small run.
  - [x] Create Loop180 review JSON/MD artifacts.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create `docs/devs/loop_reports/LOOP_180_REPORT_20260630.md`.
  - [x] Do not decrement residual accounting from Loop180 alone.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 regression-safe grounding Loop181 Bridge-only rerun

- 상태: Loop180 strict runtime caveat cleared to `GO` / semantic gate `REVIEW-LOCKED` / residual accounting `NO_DELTA_REVIEW_EVIDENCE_ONLY` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Rerun the same Loop180 9-row P1 `recall_loss_review / image_anchor_gate` input with Bridge-only small-run health.
  - [x] Confirm manifest completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`.
  - [x] Confirm `mcp_health_include_search=false`, MCP health ok/checked `2/2`.
  - [x] Confirm VLM/OCR `READY`, image_post_count `9`.
  - [x] Run `tools/audit_goal_test_run_contract.py` and record `runtime_contract=GO`, issues `[]`.
  - [x] Compare Loop181 against Loop180 row outcomes.
  - [x] Record Loop181 row split: relevant `9`, identified `6`, `safe_resolved=6`, `promotion_blocked=3`.
  - [x] Record semantic movement: `6/9` rows changed; search degraded counters `57 -> 67`.
  - [x] Create Loop181 review JSON/MD artifacts.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create `docs/devs/loop_reports/LOOP_181_REPORT_20260701.md`.
  - [x] Do not decrement residual accounting from Loop181 alone.
  - [x] Use parent/representative replay and source/native review before accepting new safe-resolved movement.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 regression-safe grounding Loop182 architecture parent replay

- 상태: Loop182 parent/representative replay runtime `GO` / semantic gate `REVIEW-LOCKED` / residual accounting `NO_DELTA_REVIEW_EVIDENCE_ONLY` / goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Rerun the 38-row Loop169 parent/representative packet after architecture integration.
  - [x] Confirm manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`.
  - [x] Confirm search-included MCP health ok/checked `36/36`.
  - [x] Confirm VLM/OCR `READY`, image_post_count `24`.
  - [x] Run `tools/audit_goal_test_run_contract.py` and record `runtime_contract=GO`, issues `[]`.
  - [x] Compare Loop182 against Loop169 row outcomes.
  - [x] Record Loop182 row split: relevant `26`, identified `12`, `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`.
  - [x] Record semantic movement: `22/38` rows changed; safe gain `2`, safe loss `3`; search degraded counters `166 -> 178`.
  - [x] Create Loop182 review JSON/MD artifacts.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create `docs/devs/loop_reports/LOOP_182_REPORT_20260701.md`.
  - [x] Do not decrement residual accounting from Loop182 alone.
  - [x] Source/native review Loop182 safe gains and safe losses before accepting any closure.
  - [x] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 regression-safe grounding Loop176 broader unittest gate audit

- 상태: Loop179에서 broader unittest 재실행 `PASS` / semantic gate `REVIEW-LOCKED` / goal completion `NOT_COMPLETE`
- 관찰: 현재 Codex app goal status는 `paused`이며 `complete`가 아니다. repo 운영 계약상 완료 조건도 아직 충족되지 않았다.
- TODO:
  - [x] Run authoritative broader unittest sweep with `--start-directory tests`.
  - [x] Record authoritative result: `1292` tests, `8` failures, `0` errors, exit code `1`.
  - [x] Record first `-s tests` invocation as non-authoritative command-shape issue.
  - [x] Create Loop176 review JSON/MD artifacts.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create `docs/devs/loop_reports/LOOP_176_REPORT_20260630.md`.
  - [x] Repair or explicitly disposition the 8 broader unittest failures.
    - Loop179 broader sweep: `1299` tests, `0` failures, `0` errors, `OK`.
  - [x] Re-run `.venv312\Scripts\python.exe -m unittest discover --start-directory tests`.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal completion `NOT_COMPLETE`.

## 2026-06-30 architecture-integrated goal revision

- 상태: goal 변경 완료 / shared promotion gate 1차 구현 및 Loop179 broader unittest `PASS` / semantic gate `REVIEW-LOCKED` / goal `NOT_COMPLETE`
- TODO:
  - [x] Create `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`.
  - [x] Promote `GroundingState` / `EvidenceRecord` / `PromotionDecision` / `GateReport` / `can_publish_title(...)` from design aid into active goal scope.
  - [x] Update `goal.md` and `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md` with the architecture-integrated objective.
  - [x] Update `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md` status to `PROMOTED_INTO_ACTIVE_GOAL`.
  - [x] Inventory public-title and URL publish paths before implementation.
  - [x] Define the shared promotion decision object and reason-code contract.
  - [x] Wire the highest-risk 2-3 publish paths through the shared gate.
  - [x] Add contract tests for `PromotionDecision.status`, `reason_codes`, `candidate_preserved`, and `bypassed_gate=false`.
  - [x] Re-run focused/affected tests and then Loop176 broader unittest sweep.
    - Loop179 authoritative result: `1299` tests, `0` failures, `0` errors.
  - [x] Return to Loop175 residual accounting only after the architecture phase is verified or explicitly dispositioned.

## 2026-06-30 promotion gate architecture visualization

- 상태: 기존 구조와 추가 아이디어 구조 Mermaid 시각화 완료 / active goal 편입 / Loop179 1차 구현 및 broader unittest `PASS`
- TODO:
  - [x] Create `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md`.
  - [x] Visualize current distributed promotion/rescue architecture.
  - [x] Visualize proposed additive `GroundingState` / `EvidenceRecord` / `PromotionDecision` / `GateReport` / `can_publish_title(...)` architecture.
  - [x] Document migration plan and non-goals.
  - [x] Link the new architecture visualization from `docs/devs/README.md`.
  - [x] Promote the architecture design into the active goal via `GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`.
  - [x] Implement the shared promotion gate layer.
  - [x] Wire the highest-risk public-title publish paths through the gate.
  - [x] Add contract tests that assert `PromotionDecision.status`, `reason_codes`, `candidate_preserved`, and `bypassed_gate=false`.
  - [ ] Return to the latest residual queue after migration; do not start a separate goal.

## 2026-06-30 regression-safe grounding Loop175 11668288 expectation revalidation

- 상태: `11668288` expectation 재검증 완료 / `VARIANCE_QUARANTINE_HUMAN_REVIEW` / semantic gate `REVIEW-LOCKED` / overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Revalidate `11668288` across 15 repeated result files.
  - [x] Confirm repeat split: `safe_resolved=6`, `promotion_blocked_or_hold=9`.
  - [x] Confirm latest Loop173/174 both remain `promotion_blocked / nonwork / title=null`.
  - [x] Separate official title/page existence from row-level work-discussion evidence.
  - [x] Create Loop175 review JSON/MD artifacts.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Residual accounting Data Analytics artifact validate/render PASS.
  - [x] Create `docs/devs/loop_reports/LOOP_175_REPORT_20260630.md`.
  - [x] Apply `VARIANCE_QUARANTINE_HUMAN_REVIEW` to the next queue/golden expectation accounting.
    - residual map: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_current_residual_gate_map_after_11668288_revalidation.md/json`
    - residual accounting artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_residual_accounting_data_analytics_artifact.json`
    - accounting action: `NO_DELTA_ALREADY_COUNTED` because Loop97 already counted `11668288` as quarantine/human_review.
  - [x] Continue remaining movement dispositions from current file evidence.
    - `11669928`, `11674712`, and `11658615` are already prior variance quarantine rows; no new queue decrement.
    - `11706832` remains review attention with no approval delta.
  - [x] Run affected-module or broader unittest sweep before stability language and record Loop176 `FAIL`.
    - authoritative result: `1292` tests, `8` failures, `0` errors.
  - [x] Repair Loop176 failures before stability language.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 regression-safe grounding Loop173-174 parent movement follow-up

- 상태: Loop173/174 runtime `GO`; targeted `11668288` repeat `NO-GO`; semantic gate `REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Run Loop173 movement/control follow-up input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop173_parent_movement_followup_after_loop172_input.jsonl`.
  - [x] Confirm Loop173 completed/flushed/pending/failed `9/9/0/0`.
  - [x] Confirm Loop173 VLM/OCR `READY`, image_post_count `4`, MCP health `2/2/2`.
  - [x] Run Loop173 runtime audit and record `GO`.
  - [x] Record Loop173 ledger counts `safe_resolved=5`, `promotion_blocked=4`.
  - [x] Confirm `11668288` lost again as `promotion_blocked / nonwork / title=null`.
  - [x] Run Loop174 targeted repeat for `11668288`.
  - [x] Confirm Loop174 completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirm Loop174 keeps `11668288` at `promotion_blocked / nonwork / title=null`.
  - [x] Do not adopt the experimental `non_novel(gaming,high)` alias-lock bypass.
  - [x] Re-run focused compile/tests after removing the failed experiment.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create Loop173-174 review/report artifacts.
  - [x] Revalidate `11668288` as positive-control vs variance quarantine/HOLD/human_review.
    - Loop175 disposition: `VARIANCE_QUARANTINE_HUMAN_REVIEW`.
  - [x] Root-cause Decoder alias recognition vs Verifier/Arbiter nonwork rejection.
    - official title existence is strong; row-level work-discussion evidence is `NOT_STABLE`.
  - [x] Disposition `11669928`, `11674712`, `11706832`, and `11658615` before parent stability language.
    - Loop175 residual map: prior variance quarantine no-delta for `11669928`/`11674712`/`11658615`; review attention/no approval delta for `11706832`.
  - [x] Run affected-module or broader unittest sweep and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before parent stability language.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Rerun clean parent/representative scope only after generalizable fix or explicit HOLD disposition.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop170-172 Lubko guard

- 상태: `11658620` targeted guard `GO`; Loop170/171/172 runtime `GO`; parent-prefix semantic gate `NO-GO / REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Reproduce the Loop169 `11658620` risk in Loop170 prefix context.
  - [x] Confirm Loop170 completed/flushed/pending/failed `4/4/0/0`.
  - [x] Patch stable-alias weak-relation bridge exemption in `agentic_pipeline.py`.
  - [x] Add focused stable-alias weak-relation regression test.
  - [x] Run `py_compile`.
  - [x] Run focused stable-alias unittest (`5 tests OK`).
  - [x] Run Loop171 parent-prefix packet after Loop170.
  - [x] Run Loop172 parent-prefix packet after the guard patch.
  - [x] Confirm Loop172 completed/flushed/pending/failed `8/8/0/0`.
  - [x] Confirm Loop172 keeps `11658620` at `promotion_blocked`.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create Loop170-172 review/report artifacts.
  - [x] Prepare Loop173 movement/control follow-up input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop173_parent_movement_followup_after_loop172_input.jsonl`.
  - [x] Run Loop173 movement/control follow-up input.
  - [x] Record Loop173/174 as runtime `GO` but semantic `NO-GO / REVIEW-LOCKED`.
  - [x] Root-cause or explicitly disposition `11674712`.
  - [x] Root-cause or explicitly disposition `11669928`.
  - [x] Re-disposition `11706832`.
  - [x] Review `11658615` URL/source movement.
    - Loop175 residual map keeps `11674712`/`11669928`/`11658615` as no-delta prior variance quarantine rows and `11706832` as review attention/no approval delta.
  - [x] Run affected-module or broader unittest sweep before approval language and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before approval language.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Rerun clean parent/representative scope after movement fixes/dispositions.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop169 parent replay after Loop168

- 상태: Loop169 parent replay runtime `GO`; target recovery `GO`; semantic gate `NO-GO / REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Run clean parent/representative replay after Loop168.
  - [x] Confirm Loop169 completed/flushed/pending/failed `38/38/0/0`.
  - [x] Confirm VLM/OCR `READY`, image_post_count `24`, MCP health `36/36/36`.
  - [x] Run strict runtime contract audit and record `GO`.
  - [x] Confirm `11668288 -> 가챠 중독자의 퓨전펑크 생활`.
  - [x] Confirm `11713222 -> 잘생기면 편해지는 인방 생활`.
  - [x] Confirm `11698880` and `11660259` remained safe-resolved.
  - [x] Record ledger counts and safe movement vs Loop162.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create Loop169 review/report artifacts.
  - [x] Root-cause or explicitly disposition `11658620` safe gain.
  - [x] Root-cause or explicitly disposition `11674712` safe gain.
  - [x] Root-cause or explicitly disposition `11669928` safe loss.
  - [x] Re-disposition `11706832` caveated-demotion boundary reopened as safe-resolved.
  - [x] Review `11658615` same-title URL/source movement.
    - Loop170-172 covered `11658620`; Loop175 residual map covers the remaining movement rows without approval delta.
  - [x] Run affected-module or broader unittest sweep before stability language and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before stability language.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop162-168 goal completion recheck

- 상태: Loop168 2-row parent mimic `GO`; clean parent replay `OPEN`; semantic gate `REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Confirm user correction that the goal is not complete.
  - [x] Review Loop162/165/166/167 as non-approval evidence.
  - [x] Patch title-lead official-detail release flag preservation in `agentic_pipeline.py`.
  - [x] Patch short alias platform/webnovel query preservation in `orchestrator.py`.
  - [x] Patch short alias probe detection for alias plus official/platform/webnovel search requests.
  - [x] Add/update regression tests in `tests/test_title_lead_search_inferred_guard.py`.
  - [x] Run `py_compile`.
  - [x] Run focused 5-test bundle.
  - [x] Run Loop167 and record semantic `NO-GO`.
  - [x] Run Loop168 `20260630_190202_307842`.
  - [x] Confirm Loop168 completed/flushed/pending/failed `2/2/0/0`.
  - [x] Confirm Loop168 resolves `11698880` and `11668288` to `가챠 중독자의 퓨전펑크 생활`.
  - [x] Data Analytics artifact validate/render PASS.
  - [x] Create Loop162-168 review and report artifacts.
  - [x] Run clean parent/representative replay after Loop168 as Loop169.
  - [x] Review `11706832` and `11713222` movement in Loop169 and keep semantic gate locked.
  - [x] Run affected-module or broader unittest sweep before approval language and record Loop176 `FAIL`.
  - [x] Repair Loop176 failures before approval language.
    - Loop179 broader unittest: `1299` tests OK.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop161 11668288 visual title-alias probe

- 상태: `11668288` targeted single-row recovery `GO`; parent stability `OPEN`; semantic gate `REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Reproduce/review Loop158/159 `11668288` null/promotion_blocked loss vs Loop150.
  - [x] Patch visual title-leading alias probe in `src/llm_batch/experts/orchestrator.py`.
  - [x] Limit the bridge to image/VLM context, `title_as_body_continuation`, exact title-leading alias query/suggestion, and alias surface hit.
  - [x] Let the non-novel early exit continue only for the narrow `short_alias_probe`.
  - [x] Restore the title-leading alias as auto seed after semantic seed demotion.
  - [x] Add positive and negative regression tests for visual title-leading aliases.
  - [x] Confirm existing alias-only nonwork forced-upgrade guard still passes.
  - [x] Run `py_compile`.
  - [x] Run focused 4-test bundle.
  - [x] Run Loop161 `20260630_165512_125247`.
  - [x] Confirm Loop161 runtime completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirm VLM/OCR `READY`, image_post_count `1`, MCP health `1/1/1`.
  - [x] Confirm `11668288 -> 가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`.
  - [x] Confirm `candidate_ledger_status=safe_resolved`, `title_resolution_allowed=true`, `title_resolution_state=resolved`, `work_resolution=resolved`.
  - [x] Create Loop161 review artifact `loop161_11668288_visual_title_alias_probe_review.md/json`.
  - [x] Data Analytics artifact `Loop161 11668288 Visual Title-Alias Probe Review` validate/render PASS.
  - [x] Create Loop161 report `docs/devs/loop_reports/LOOP_161_REPORT_20260630.md`.
  - [ ] Rerun parent/representative scope after Loop161.
  - [ ] Review Loop158 `11706832` movement before acceptance.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop155 11660259 short alias reaction probe

- 상태: `11660259` targeted single-row fix seed `GO`; parent stability `OPEN`; semantic gate `REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Mark Loop153 as invalid evidence because Verifier hit `NameError: ctx is not defined`.
  - [x] Patch Verifier relation judge `ctx` propagation.
  - [x] Preserve explicit alias bridge support from snippet/context evidence.
  - [x] Patch short worklike reaction alias search probe for `기계공주` + `말한대로`/`대가리똑딱`-style context.
  - [x] Add regression tests for snippet abbreviation mapping, explicit alias phrase support, official wiki alias bridge, and 11660259-style reaction alias probing.
  - [x] Run `py_compile`.
  - [x] Run focused 4-test bundle.
  - [x] Run broader 11-test relation/alias guard bundle.
  - [x] Run Loop155 `20260630_143521_442264`.
  - [x] Confirm Loop155 runtime completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirm `primary_work=헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
  - [x] Confirm `candidate_ledger_status=safe_resolved`, `title_resolution_allowed=true`, `title_resolution_state=resolved`, `work_resolution=resolved`.
  - [x] Create Loop155 review artifact `loop155_11660259_short_alias_reaction_probe_review.md/json`.
  - [x] Data Analytics artifact `Loop155 11660259 Short Alias Reaction Probe Review` validate/render PASS.
  - [x] Create Loop155 report `docs/devs/loop_reports/LOOP_155_REPORT_20260630.md`.
  - [x] Rerun representative/parent scope containing `11660259` as Loop156.
  - [x] Parent-confirm `11660259` and `11713222` in Loop156.
  - [x] Record Loop156 as runtime `GO`, target confirmation `GO`, semantic `NO-GO`.
  - [x] Root-cause Loop156 `11698880` wrong-title switch risk and parent-confirm repair in Loop158.
  - [x] Review Loop156/158 `11668288` loss vs Loop150 and recover targeted single-row seed in Loop161.
  - [ ] Review Loop156/158 `11706832` gained/changed title.
  - [ ] Rerun parent/representative scope after Loop161.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop156 parent replay after Loop155

- 상태: parent replay runtime `GO`; `11660259`/`11713222` parent-confirmed; semantic gate `NO-GO / REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Run Loop156 parent/representative replay from Loop134 source-enriched packet.
  - [x] Confirm Loop156 run `20260630_144848_180512`.
  - [x] Confirm completed/flushed/pending/failed `38/38/0/0`.
  - [x] Confirm VLM/OCR semantic review `READY` and image_post_count `24`.
  - [x] Confirm MCP health ok/required `36/36`.
  - [x] Confirm `11660259 -> 헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
  - [x] Confirm `11713222 -> 잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
  - [x] Record status counts `safe_resolved=9`, `promotion_blocked=26`, `hold_without_candidates=2`, `output_consistency_lint=1`.
  - [x] Compare movement vs Loop142, Loop136, and Loop150.
  - [x] Create Loop156 review artifact `loop156_parent_replay_after_loop155_alias_probe_review.md/json`.
  - [x] Data Analytics artifact `Loop156 Parent Replay After Loop155 Alias Probe Review` validate/render PASS.
  - [x] Create Loop156 report `docs/devs/loop_reports/LOOP_156_REPORT_20260630.md`.
  - [x] Root-cause `11698880` changed-title risk (`가챠 중독자의 퓨전펑크 생활` -> `상남자 [독점]`) and parent-confirm repair in Loop158.
  - [ ] Review `11706832` gained/changed title before acceptance.
  - [x] Review `11668288` loss vs Loop150 and recover targeted single-row seed in Loop161.
  - [ ] Rerun parent/representative scope after Loop161 before counting stability.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop152 11660259 current-code single repeat

- 상태: `11660259` current-code single repeat `NO-GO_REPRODUCED`; semantic gate `REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Compare `11660259` across Loop136, Loop142, Loop150.
  - [x] Confirm Loop136/Loop142 primary work `헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
  - [x] Confirm Loop150 lost the public title with `promotion_blocked` / `unresolved_matchable`.
  - [x] Extract exact `11660259` row from Loop134 parent source-enriched packet.
  - [x] Run Loop152 current-code single repeat.
  - [x] Confirm Loop152 run `20260630_141044_962593`.
  - [x] Confirm runtime completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirm VLM/OCR semantic gate `READY` with `no_image_blocks`.
  - [x] Confirm final public title/url `null`, `candidate_ledger_status=hold_without_candidates`, `title_resolution_allowed=false`.
  - [x] Record root-cause signal: `relation_judge:thematic_overlap_only`, `memory_query_forced_upgrade_guard`, `title_surface_primary_relation_non_work_blocked`.
  - [x] Create Loop152 review artifact `loop152_11660259_current_code_single_repeat_review.md/json`.
  - [x] Data Analytics artifact `Loop152 11660259 Current-Code Single Repeat NO-GO Review` validate/render PASS.
  - [x] Create Loop152 report `docs/devs/loop_reports/LOOP_152_REPORT_20260630.md`.
  - [x] Root-cause/fix the weak alias bridge path so official detail plus explicit alias evidence can survive relation hold only in safe work-like cases.
  - [x] Repeat `11660259` after the fix in Loop155.
  - [x] Rerun representative/parent scope in Loop156 and confirm `11660259` recovery.
  - [ ] Do not claim stability/approval until Loop156 collateral blockers are resolved.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop151 11713222 current-code single repeat

- 상태: `11713222` current-code single repeat `GO`; parent stability still `OPEN`; semantic gate `REVIEW-LOCKED`
- TODO:
  - [x] Rerun exact `11713222` input after Loop150 parent-scope loss.
  - [x] Confirm Loop151 run `20260630_135620_918136`.
  - [x] Confirm runtime completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirm VLM/OCR semantic gate `READY` with `no_image_blocks`.
  - [x] Confirm primary work `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
  - [x] Confirm `candidate_ledger_status=safe_resolved`, `title_resolution_allowed=true`, `title_resolution_state=resolved`.
  - [x] Record that competing previous work `https://novelpia.com/novel/300042` did not steal public identity.
  - [x] Create Loop151 review artifact `loop151_11713222_current_code_single_repeat_review.md/json`.
  - [x] Data Analytics artifact `Loop151 11713222 Current-Code Repeat Diagnostic` validate/render PASS.
  - [x] Create Loop151 report `docs/devs/loop_reports/LOOP_151_REPORT_20260630.md`.
  - [ ] Treat `11713222` parent stability as open until representative/parent replay preserves the current official detail.
  - [x] Review `11660259` title loss vs Loop142 and Loop136.
  - [x] Track `11660259` as a current-code single-repeat `NO-GO_REPRODUCED` blocker after Loop152; Loop155 now closes the single-row repro seed only.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop150 parent replay after Loop149

- 상태: Loop150 parent replay runtime `GO`; semantic gate `NO-GO / REVIEW-LOCKED`; overall goal `ACTIVE / NOT_COMPLETE`
- TODO:
  - [x] Wait for Loop150 process exit and clean manifest before runtime-complete claims.
  - [x] Confirm Loop150 run `20260630_125822_273225`.
  - [x] Confirm input `38`, completed/flushed/pending/failed `38/38/0/0`.
  - [x] Confirm `large_run_complete=true`.
  - [x] Confirm VLM/OCR semantic review readiness `READY` and image_post_count `24`.
  - [x] Confirm requested/effective parallel `36/36` and MCP health ok/required `36/36`.
  - [x] Create Loop150 review artifact `loop150_parent_replay_after_loop149_review.md/json`.
  - [x] Compare Loop150 semantic movement against Loop142: `same=31`, `lost=5`, `gained=2`.
  - [x] Compare Loop150 semantic movement against Loop136: `same=32`, `lost=4`, `gained=2`.
  - [x] Data Analytics artifact `Loop150 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
  - [x] Create Loop150 report `docs/devs/loop_reports/LOOP_150_REPORT_20260630.md`.
  - [x] Parent-confirm `11660257` stayed public-title blocked, but record it as movement/drift evidence only.
  - [x] Parent-confirm `11669928` resolved and `11674712` held/null in this run.
  - [ ] Root-cause `11713222` parent-scope loss after Loop148 targeted repair.
  - [ ] Review `11660259` title loss vs Loop142 and Loop136.
  - [ ] Re-check `11705231` loss vs Loop136 before claiming targeted repair stability.
  - [ ] Introduce common `GroundingState`/`PromotionDecision`/`can_publish_title` layer or equivalent before continuing broad single-post guard accumulation.
    - visualization/spec: `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md`
  - [ ] Add harness-level collateral compare/gate layer so queue closure cannot imply semantic approval.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop149 11660257 current-code repeat

- 상태: `11660257` current-code single repeat blocked public title; parent semantic quality still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Confirm `11660257` was blocked in Loop107 but reopened in Loop142.
  - [x] Run current-code single repeat with VLM/OCR on and `--require-vlm-ocr-for-images`.
  - [x] Confirm Loop149 runtime completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirm VLM/OCR semantic gate `READY`.
  - [x] Confirm final public title/url `null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_allowed=false`.
  - [x] Preserve competing candidates only as candidate evidence.
  - [x] Create Loop149 review artifact `loop149_11660257_current_code_repeat_review.md/json`.
  - [x] Data Analytics artifact `Loop149 11660257 Current-Code Repeat Review` validate/render PASS.
  - [x] Create Loop149 report `docs/devs/loop_reports/LOOP_149_REPORT_20260630.md`.
  - [ ] Parent-confirm `11660257` with `11669928` and `11674712`.
  - [x] Parent/representative packet reran as Loop150; runtime `GO`, semantic `NO-GO / REVIEW-LOCKED`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop148 11713222 direct body alias previous-work guard

- 상태: `11713222` previous/current work confusion repaired at targeted scope; parent semantic quality still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Reproduce failing baseline where `11713222` resolves to previous work `잘생기면 인생이 편하다`.
  - [x] Confirm native/web evidence that `잘생인방` maps to `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
  - [x] Add direct-current-alias conflict guard in `src\llm_batch\agentic_pipeline.py`.
  - [x] Add verifier-detail lock for current title when body alias is directly grounded.
  - [x] Block `multi_work` previous-work comment override when direct body alias points to the current work.
  - [x] Add regression test `test_multi_work_previous_comment_keeps_direct_body_alias_primary`.
  - [x] Run touched-file `py_compile`: PASS.
  - [x] Run focused title-lead 5-test bundle: PASS.
  - [x] Run Loop148 rerun2 single-row canary for `11713222`: completed/flushed/pending/failed `1/1/0/0`.
  - [x] Confirm Loop148 rerun2 public title `잘생기면 편해지는 인방 생활`, URL `https://novelpia.com/novel/384016`.
  - [x] Confirm previous work `잘생기면 인생이 편하다` is preserved only as mentioned/secondary candidate evidence.
  - [x] Create Loop148 review artifact `loop148_11713222_direct_body_alias_previous_work_guard_review.md/json`.
  - [x] Data Analytics artifact `Loop148 11713222 Direct Body Alias Previous Work Guard` validate/render PASS.
  - [x] Create Loop148 report `docs/devs/loop_reports/LOOP_148_REPORT_20260630.md`.
  - [x] Requeue/repeat `11660257` on current code in Loop149; single-row output stayed promotion-blocked.
  - [ ] Parent-confirm `11660257` after Loop149.
  - [ ] Parent-confirm plausible gained rows `11669928` and `11674712`.
  - [ ] Rerun parent/representative packet after Loop143/Loop144 repairs, Loop145 disposition, Loop146 repair, Loop147 guard, Loop148 guard, and Loop149 repeat.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop147 11714903 wrong-relevance public-title guard

- 상태: `11714903` wrong-relevance public-title serialization blocked at targeted scope; parent semantic quality still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Confirm active goal is not complete.
  - [x] Review Loop142 gained-title rows `11669928`, `11674712`, `11660257`, `11713222`, `11714903`.
  - [x] Classify `11714903` as wrong-relevance public-title leak from Loop142.
  - [x] Add `apply_judge_seed_wrong_relevance_public_title_guard(...)` in `src\llm_batch\candidate_audit.py`.
  - [x] Wire the guard in `expert_main.py` final postprocess.
  - [x] Add regression test `test_wrong_relevance_seed_public_title_is_candidate_hold`.
  - [x] Add reason-scrub regression test for `output_consistency_lint` HOLD rows.
  - [x] Run touched-file `py_compile`: PASS.
  - [x] Run focused wrong-relevance/reason-scrub bundle: PASS.
  - [x] Run Loop147 single-row canary for `11714903`: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - [x] Confirm Loop147 public title/url `null`, `title_resolution_allowed=false`, `candidate_ledger_status=output_consistency_lint`, `work_resolution=none`.
  - [x] Create Loop147 review artifact `loop147_11714903_wrong_relevance_public_title_guard_review.md/json`.
  - [x] Data Analytics artifact `Loop147 11714903 Wrong Relevance Public Title Guard` validate/render PASS.
  - [x] Create Loop147 report `docs/devs/loop_reports/LOOP_147_REPORT_20260630.md`.
  - [x] Root-caused `11713222` previous/current work confusion; targeted repaired in Loop148.
  - [x] Requeue/repeat `11660257` on current code in Loop149; single-row output stayed promotion-blocked.
  - [ ] Parent-confirm `11660257` after Loop149.
  - [ ] Parent-confirm plausible gained rows `11669928` and `11674712`.
  - [x] Parent/representative packet reran as Loop150; runtime `GO`, semantic `NO-GO / REVIEW-LOCKED`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop145 11706832 accepted caveated demotion

- 상태: `11706832` explicitly dispositioned as accepted caveated demotion; parent semantic quality still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Re-read pasted goal contract and confirm the goal is active, not complete.
  - [x] Recheck Loop142/Loop136 compare row for `11706832`.
  - [x] Recheck Loop139 native/web review and local image evidence for `11706832`.
  - [x] Confirm image `loop139_11706832_dc_image.jpg` is textless meme/fanart, not a title/platform anchor.
  - [x] Confirm Loop139 official detail evidence `https://novelpia.com/novel/250464` / `황제의 딸로 환생했다` remains caveated by community-mediated alias bridge.
  - [x] Classify Loop142 public-title null as `ACCEPTED_CAVEATED_DEMOTION_NOT_CODE_REPAIR`.
  - [x] Keep candidate/URL evidence preserved but do not reopen public identity for this row.
  - [x] Ask Council reviewers; all agreed with accepted caveated demotion over code repair.
  - [x] Create Loop145 row review artifact `loop145_11706832_alias_caveat_disposition_review.md/json`.
  - [x] Data Analytics artifact `Loop145 11706832 Accepted Caveated Demotion Review` validate/render PASS.
  - [x] Create Loop145 report `docs/devs/loop_reports/LOOP_145_REPORT_20260630.md`.
  - [x] Repair `11698897` candidate-preservation drift in Loop146: public title blocked, Rimworld candidate preserved, spurious `스페이스 오페라` pruned.
  - [x] Review gained-title rows in Loop147; `11714903` targeted-blocked, `11713222` targeted repaired in Loop148, and `11660257` current-code single repeat blocked in Loop149.
  - [ ] Rerun parent/representative packet after Loop143/Loop144 repairs, Loop145 disposition, Loop146 drift repair, and Loop147 guard.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop146 11698897 candidate-preservation repair

- 상태: `11698897` candidate-preservation drift repaired at targeted scope; parent semantic quality still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Reproduce the drift with diagnostic Loop146 canary: public promotion stayed blocked but `스페이스 오페라` remained in candidate ledger.
  - [x] Add rejected search-alias candidate pruning before candidate-preservation snapshot in `src\llm_batch\agentic_pipeline.py`.
  - [x] Add regression test `test_rejected_search_alias_inference_candidate_is_pruned_from_hold_snapshot`.
  - [x] Preserve existing cross-media title-body hold behavior.
  - [x] Run `py_compile` for touched pipeline/test files: PASS.
  - [x] Run focused title-lead/official-url guard bundle: PASS.
  - [x] Run Loop146b single-row canary for `11698897`: `1/1`, pending `0`, failed `0`, VLM/OCR `READY`.
  - [x] Confirm Loop146b public title `null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_allowed=false`.
  - [x] Confirm `[림월드]변방계에서 회귀자로 살아남기` / `https://novelpia.com/novel/382324` is preserved as candidate evidence.
  - [x] Confirm `스페이스 오페라` is absent from `candidate_preservation_sources`.
  - [x] Create Loop146 review artifact `loop146_11698897_candidate_preservation_repair_review.md/json`.
  - [x] Data Analytics artifact `Loop146 11698897 Candidate Preservation Repair` validate/render PASS.
  - [x] Create Loop146 report `docs/devs/loop_reports/LOOP_146_REPORT_20260630.md`.
  - [x] Review gained-title rows in Loop147; `11714903` targeted-blocked, `11713222` targeted repaired in Loop148, and `11660257` current-code single repeat blocked in Loop149.
  - [ ] Rerun parent/representative packet after Loop143/Loop144 repairs, Loop145 disposition, Loop146 drift repair, and Loop147 guard.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop143 11658615 targeted fix

- 상태: `11658615` targeted repaired; parent semantic quality still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Root-cause Loop142 `11658615` loss as noisy direct image/OCR surface conflicting with verified official platform title.
  - [x] Add narrow verified-alias official-detail lock exemption in `src\llm_batch\candidate_audit.py`.
  - [x] Add regression test `test_verified_alias_detail_lock_exempts_noisy_image_surface_conflict`.
  - [x] Run `py_compile` for touched files: PASS.
  - [x] Run focused 4-test candidate-audit bundle: PASS.
  - [x] Run Loop143 single-row canary for `11658615`: `1/1`, VLM/OCR `READY`.
  - [x] Confirm Loop143 result `safe_resolved`, title `이거 럽코 빙의물인가요`, URL `https://novel.munpia.com/533816`.
  - [x] Create Loop143 review artifact and report.
  - [x] Data Analytics artifact `Loop143 11658615 Targeted Fix Review` validate/render PASS.
  - [ ] Treat full `tests.test_candidate_audit` failure in `test_entity_mentions_do_not_pollute_resolved_titles` as separate open work.
  - [x] Repair `11705231` at targeted scope in Loop144.
  - [x] Explicitly disposition Loop142 remaining title loss `11706832` as Loop145 accepted caveated demotion.
  - [x] Repair `11698897` candidate-preservation drift in Loop146.
  - [ ] Review gained-title rows `11669928`, `11674712`, `11660257`, `11713222`, `11714903`.
  - [ ] Rerun parent/representative packet after the targeted fix before any approval language.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop142 parent replay after Loop141 HOLD boundary

- 상태: parent/representative replay runtime `GO`; semantic quality `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Check vLLM model endpoint before run.
  - [x] Save shard preflight audit `out\search_shard_audit_20260630_loop142_preflight.json` with `36/36` healthy shards.
  - [x] Run Loop142 parent replay from `loop134_parent_representative_after_loop133_source_enriched_packet.jsonl`.
  - [x] Confirm runtime result rows `38/38`, pending snapshot `0`, VLM/OCR `READY`, MCP health `36/36`, no shard auto-up/recreate.
  - [x] Create runtime audit, compare, review artifacts for Loop142.
  - [x] Data Analytics artifact `Loop142 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
  - [x] Confirm Loop141 target rows remain public-title null.
  - [x] Record `11698897` candidate-preservation drift as open.
  - [x] Record Loop139-confirmed title losses: `11658615`, `11706832`, `11705231`.
  - [x] Record `11700470` demotion as expected after Loop137.
  - [x] Repair `11658615` at targeted scope in Loop143.
  - [x] Repair `11705231` at targeted scope in Loop144.
  - [x] Explicitly disposition remaining parent-scope loss `11706832` as Loop145 accepted caveated demotion.
  - [x] Repair `11698897` candidate-preservation drift in Loop146.
  - [ ] Review gained-title rows `11669928`, `11674712`, `11660257`, `11713222`, `11714903`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop141 current expected/recall HOLD boundary review

- 상태: current expected/recall row-level rationale completed as explicit HOLD/control; no code patch; no `expert_main.py` rerun; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Recheck the three remaining current expected/recall rows after Loop140: `11663521`, `11694019`, `11698897`.
  - [x] Inspect available local/downloaded images for `11663521` and `11698897`.
  - [x] Record HTTP 403 for unavailable dccon helper images.
  - [x] Classify `11663521` as `HOLD_BOUNDARY_CONFIRMED`.
  - [x] Classify `11694019` as `HOLD_BOUNDARY_CONFIRMED`.
  - [x] Classify `11698897` as `VARIANCE_HOLD_CONTROL_CONFIRMED`.
  - [x] Reduce current expected/recall unrationalized open rows to `0`.
  - [x] Create Loop141 review artifact and loop report.
  - [x] Data Analytics artifact `Loop141 Current Expected Recall HOLD Boundary Review` validate/render PASS.
  - [x] Run parent/representative semantic replay with current code and Loop137-Loop141 evidence boundary as Loop142.
  - [x] Keep Loop142 semantic approval `NO-GO / REVIEW-LOCKED`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop140 expected/recall disposition consolidation

- 상태: audit-only consolidation completed; current expected/recall remaining list narrowed from six to three; no code patch; no `expert_main.py` rerun; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Re-read pasted goal contract and confirm goal remains active/not complete.
  - [x] Recheck Loop92-93 stable P1A dispositions for `11695623`, `11700495`, and `11705261`.
  - [x] Recheck Loop136 latest row state for the six current expected/recall rows.
  - [x] Split out `11695623`, `11700495`, and `11705261` as explicit current HOLD/no-public dispositions rather than unresolved current expected/recall work.
  - [x] Keep `11663521`, `11694019`, and `11698897` open for targeted review.
  - [x] Create Loop140 review artifact and loop report.
  - [x] Data Analytics artifact `Loop140 Remaining Expected Recall Disposition Consolidation` validate/render PASS.
  - [x] Current expected/recall rows `11663521`, `11694019`, and `11698897` explicitly held with rationale in Loop141.
  - [x] Included Loop137/Loop138/Loop139/Loop140/Loop141 evidence in Loop142 parent/representative replay; runtime `GO`, semantic `NO-GO / REVIEW-LOCKED`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop139 Loop136 safe-resolved native/web review

- 상태: remaining Loop136 `safe_resolved` native/web review completed with `11706832` alias caveat; no code patch; no `expert_main.py` rerun; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Review current official/platform page titles for `11698880`, `11658615`, `11660237`, `11660258`, `11660259`, `11706832`, `11705231`.
  - [x] Download and inspect image evidence for `11698880`, `11658615`, `11660237`, `11706832`.
  - [x] Confirm `11658615` image directly shows the work card title and author.
  - [x] Separate meme/reaction-only images from title-bridge evidence.
  - [x] Keep `11706832` as official-page-confirmed but alias-bridge caveated.
  - [x] Create Loop139 review artifact and loop report.
  - [x] Included Loop137/Loop138/Loop139/Loop140 evidence in Loop142 parent/representative replay; runtime `GO`, semantic `NO-GO / REVIEW-LOCKED`.
  - [x] Split out `11695623`, `11700495`, and `11705261` as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, and `11698897` explicitly held with rationale in Loop141.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop138 11685994 image/native-web verification

- 상태: `11685994` image/native-web exact-title verification completed as `INFO_MISSING_NATIVE_WEB_CONFIRMED / HOLD`; no code patch; no `expert_main.py` rerun; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Recheck Loop136 `11685994` latest row state: public title `null`, `promotion_blocked`, `title_resolution_allowed=false`.
  - [x] Inspect local image and enlarged title crop.
  - [x] Preserve cover title family `교황님 아 하세요 / 마왕들어가요`, author `아데라`, `장편소설` as candidate evidence only.
  - [x] Reject wrong-work candidate pages `https://novelpia.com/novel/270445`, `https://novelpia.com/novel/383971`, and `https://page.kakao.com/content/56516207`.
  - [x] Create Loop138 review artifact and loop report.
  - [x] Confirm no safe code relaxation is justified by this row.
  - [x] Included Loop137/Loop138/Loop139/Loop140 evidence in Loop142 parent/representative replay; runtime `GO`, semantic `NO-GO / REVIEW-LOCKED`.
  - [x] Continue native/web review of remaining Loop136 safe-resolved rows; completed in Loop139 with `11706832` alias caveat.
  - [x] Split out `11695623`, `11700495`, and `11705261` as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, and `11698897` explicitly held with rationale in Loop141.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop137 11700470 listing-description guard

- 상태: Loop136 `11700470` description-title promotion root-caused and repaired to focused HOLD; runtime `GO`; semantic quality still `REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Review Loop136 `11700470` safe_resolved output against native/web evidence.
  - [x] Confirm official page title `납치당했는데 미소녀가 되었다` differs from promoted description surface.
  - [x] Add listing-description official-title promotion guard in `candidate_audit.py`.
  - [x] Add regression test `test_listing_description_official_title_is_demoted_but_preserved`.
  - [x] Run `py_compile`: PASS.
  - [x] Run related 7-test unittest bundle: PASS.
  - [x] Check vLLM model endpoint and 36 search shards before run.
  - [x] Run Loop137 focused canary: `1/1/0/0`, VLM/OCR `READY`.
  - [x] Run strict runtime audit: `GO`.
  - [x] Confirm `11700470` public title `null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_allowed=false`.
  - [x] Create Loop137 review/compare artifacts and report.
  - [x] Included this repair plus Loop138/Loop139/Loop140 evidence in Loop142 parent/representative replay; runtime `GO`, semantic `NO-GO / REVIEW-LOCKED`.
  - [x] Continue native/web review of remaining Loop136 safe-resolved rows; completed in Loop139 with `11706832` alias caveat.
  - [x] Verify `11685994` image/native-web exact-title evidence; Loop138 confirmed `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [x] Split out `11695623`, `11700495`, and `11705261` as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, and `11698897` explicitly held with rationale in Loop141.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop136 parent replay after Loop135 guard

- 상태: Loop136 parent replay runtime `GO`; Loop135 `11694035` guard holds at parent scope; semantic quality still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Rerun Loop134 parent/representative packet after Loop135 patch.
  - [x] Check vLLM model endpoint and 36 search shards before run.
  - [x] Run Loop136 parent replay: `38/38/0/0`, VLM/OCR `READY`.
  - [x] Run strict runtime audit: `GO`.
  - [x] Confirm `11694035` public title remains `null` / `promotion_blocked` at parent scope.
  - [x] Confirm `11705231 -> 탐식의 재림` still holds at parent scope.
  - [x] Create Loop136 compare/review artifacts and loop report.
  - [x] Review `11700470` against native/web title evidence; repaired to focused HOLD in Loop137.
  - [x] Review remaining safe-resolved rows against native/web title evidence; completed in Loop139 with `11706832` alias caveat.
  - [x] Verify `11685994` image/native-web exact-title evidence before code changes; Loop138 confirmed `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [x] Split out `11695623`, `11700495`, and `11705261` as explicit current HOLD/no-public dispositions in Loop140.
  - [x] Current expected/recall rows `11663521`, `11694019`, and `11698897` explicitly held with rationale in Loop141.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop135 11694035 Phase2 HOLD guard

- 상태: Loop135 targeted `11694035` guard PASS; parent/representative replay completed as Loop136 runtime `GO`; semantic gate still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Root-cause Loop134 golden negative violation `11694035 -> 아카데미 생존 갤러리`.
  - [x] Add Phase2 `HOLD` / `re_search` precision-seed bypass block in `candidate_audit.py`.
  - [x] Add regression test `test_phase2_hold_precision_seed_blocks_official_detail_bypass`.
  - [x] Run `py_compile`: PASS.
  - [x] Run related 6-test unittest bundle: PASS.
  - [x] Attempt full `tests.test_candidate_audit`; record separate existing failure.
  - [x] Check vLLM model endpoint and 36 search shards before run.
  - [x] Run Loop135 focused canary: `1/1/0/0`, VLM/OCR `READY`.
  - [x] Run strict runtime audit: `GO`.
  - [x] Confirm `11694035` public title `null`, `candidate_ledger_status=promotion_blocked`, `phase2_hold_seed_requires_review`.
  - [x] Create Loop135 review/compare artifacts and report.
  - [x] Rerun parent/representative packet after Loop135 patch as Loop136.
  - [ ] Review reopened/changed controls `11714903`, `11706832`, `11698880`, `11695623`, `11660257`.
  - [ ] Resolve or explicitly HOLD remaining expected-work losses after Loop138-held `11685994`: `11663521`, `11694019`, `11700470`.
  - [x] Verify `11685994` image/native-web exact-title evidence before code changes; Loop138 confirmed `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop134 parent replay after source repair

- 상태: Loop134 runtime `GO`; `11705231` parent-scope restored; parent/representative semantic gate still `NO-GO / REVIEW-LOCKED`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Build Loop134 source-enriched parent packet from Loop104 38-row role mix.
  - [x] Replace only `11705231` with row-level source-evidence input.
  - [x] Check vLLM model endpoint and 36 search shards before run.
  - [x] Run Loop134 parent/representative replay: `38/38/0/0`.
  - [x] Run strict runtime audit: `GO`.
  - [x] Confirm `11705231 -> 탐식의 재림` at parent scope.
  - [x] Create role-aware review artifact and compare artifact.
  - [x] Data Analytics artifact `Loop134 Parent Replay Quantitative Review` validate/render PASS.
  - [x] Create Loop134 report and update docs/checklists.
  - [x] Root-cause and targeted-repair golden negative violation `11694035 -> 아카데미 생존 갤러리` in Loop135.
  - [ ] Review reopened/changed controls `11714903`, `11706832`, `11698880`, `11695623`, `11660257`.
  - [ ] Resolve or explicitly HOLD remaining expected-work losses after Loop138-held `11685994`: `11663521`, `11694019`, `11700470`.
  - [x] Verify `11685994` image/native-web exact-title evidence before code changes; Loop138 confirmed `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop133 source-enriched focused repair

- 상태: `11705231` targeted source-enriched blocker repaired; two canaries `GO` / `Identified=1`; overall goal still `NOT_COMPLETE`
- TODO:
  - [x] Preserve source evidence fields through JSONL input loading and `PostInput`.
  - [x] Seed orchestrator initial search results from row-level source evidence.
  - [x] Add narrow locked-official contextual-anchor precision bypass.
  - [x] Run focused 13-test bundle: PASS.
  - [x] Run `py_compile` for touched runtime modules: PASS.
  - [x] Run first source-enriched canary: `1/1/0/0`, `Identified=1`, title `탐식의 재림`.
  - [x] Run repeat source-enriched canary: `1/1/0/0`, `Identified=1`, title `탐식의 재림`.
  - [x] Run runtime audits for both latest canaries: `GO`.
  - [x] Update Loop133 report, checklist, history, verification docs.
  - [x] Rerun parent/representative packet after Loop133 repair as Loop134 runtime `GO`.
  - [ ] Achieve semantic `GO` on parent/representative replay after Loop133 repair.
  - [ ] Rerun golden/collateral controls after Loop133 repair.
  - [x] Verify `11685994` exact OCR title/author bridge with native web before code changes; Loop138 confirmed `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [ ] Keep `11663521`, `11694019`, `11700470` as HOLD boundaries unless stronger work-bridge evidence appears.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop131 parent replay runtime GO / semantic NO-GO

- 상태: Loop104 38-row parent replay after Loop130 completed; runtime contract `GO`; semantic quality `NO-GO / REVIEW-LOCKED`; overall goal `NOT_COMPLETE`
- TODO:
  - [x] Run Loop131 parent/representative packet after Loop130 Faust guard.
  - [x] Record Loop131 run `20260630_030549_717991`.
  - [x] Confirm manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`.
  - [x] Record requested/effective parallel `36/36` and MCP health ok/required/after-filter `36/36/36`.
  - [x] Run strict runtime audit `loop131_parent_representative_replay_runtime_audit.md/json`: `GO`.
  - [x] Confirm `11706871 -> 파우스트 1` targeted closure holds at parent scope.
  - [x] Create review artifact `loop131_parent_representative_replay_after_faust_guard_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_131_REPORT_20260630.md`.
  - [x] Data Analytics artifact `Loop131 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
  - [ ] Root-cause expected-work losses after later Loop138-held `11685994`: `11663521`, `11694019`, `11700470`; `11705231` has targeted Loop133 repair but still needs broader replay.
  - [ ] Review Loop129-to-Loop131 public-title movement before collateral stability claim.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop132 completion challenge audit

- 상태: user challenge accepted; runtime remains `GO`; semantic quality remains `NO-GO / REVIEW-LOCKED`; code patch `NOT_ADOPTED`; overall goal `NOT_COMPLETE`
- TODO:
  - [x] Re-read pasted goal contract before continuing.
  - [x] Recheck Loop131 remaining expected-work losses against result JSON and existing test contracts.
  - [x] Create review artifacts `loop132_completion_challenge_disposition_audit.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_132_REPORT_20260630.md`.
  - [x] Data Analytics artifact `Loop132 Completion Challenge Disposition Audit` validate/render PASS.
  - [x] Record disposition counts: `HOLD_BOUNDARY=3`, `INFO_MISSING_NATIVE_WEB=1`, `NARROW_REPLAY_CANDIDATE=1`.
  - [x] Confirm no safe broad code relaxation was adopted.
  - [x] Build focused native-web/replay packet for `11705231`; targeted repaired in Loop133.
  - [x] Verify `11685994` exact OCR title/author bridge with native web before code changes; Loop138 confirmed `INFO_MISSING_NATIVE_WEB / HOLD`.
  - [ ] Keep `11663521`, `11694019`, `11700470` as HOLD boundaries unless stronger work-bridge evidence appears.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop130 Faust direct-rescue guard

- 상태: targeted `11706871` closure PASS; runtime contract `GO`; parent/representative replay after patch `OPEN / NOT_RUN`; overall goal `NOT_COMPLETE`
- TODO:
  - [x] Root-cause Loop129 `11706871 -> 파우스트 1` direct image/OCR rescue bypass.
  - [x] Add physical/classic-book image guard in `src/llm_batch/agentic_pipeline.py`.
  - [x] Preserve physical book OCR as candidates while blocking structured direct-image, image-primary, and OCR-catalog official-title promotion evidence.
  - [x] Add/extend regression coverage in `tests/test_title_lead_search_inferred_guard.py`.
  - [x] Run `py_compile`: PASS.
  - [x] Run 3 focused unittests: PASS.
  - [x] Run Loop130 targeted canary `20260630_024726_142878`.
  - [x] Confirm final public title `null`, `candidate_ledger_status=promotion_blocked`.
  - [x] Run strict runtime audit `loop130_faust_direct_rescue_guard_runtime_audit.md/json`: `GO`.
  - [x] Create review artifact `loop130_faust_direct_rescue_guard_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_130_REPORT_20260630.md`.
  - [x] Data Analytics artifact `Loop130 Faust Direct Rescue Guard Review` validate/render PASS.
  - [x] Rerun Loop104 38-row parent/representative packet after this patch as Loop131.
  - [ ] Root-cause expected-work losses after later Loop138-held `11685994`: `11663521`, `11694019`, `11700470`, `11705231`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop129 parent replay runtime GO / semantic NO-GO

- 상태: shard restore closed runtime blocker; Loop129 parent packet completed `38/38/0/0`; runtime contract `GO`; semantic quality `NO-GO / REVIEW-LOCKED`; overall goal `NOT_COMPLETE`
- TODO:
  - [x] Audit pre-restore shards: `16/36`, bad `17-36`.
  - [x] Restore shards `17-36` with protected incremental `warp_shards.py up`.
  - [x] Audit post-restore shards: `36/36`, bad `[]`.
  - [x] Run Loop129 parent/representative packet.
  - [x] Record Loop129 run `20260630_020121_110991`.
  - [x] Confirm manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`.
  - [x] Record requested/effective parallel `36/36` and MCP health ok/required/after-filter `36/36/36`.
  - [x] Run strict runtime audit `loop129_parent_representative_replay_runtime_audit.md/json`: `GO`.
  - [x] Create review artifact `loop129_parent_representative_replay_after_shard_restore_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_129_REPORT_20260630.md`.
  - [x] Data Analytics artifact `Loop129 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
  - [x] Root-cause `11706871 -> 파우스트 1` and close it with Loop130 targeted canary.
  - [ ] Root-cause expected-work losses after later Loop138-held `11685994`: `11698897`, `11663521`, `11694019`, `11700470`, `11705231`.
  - [ ] Review Loop128-to-Loop129 public-title movement: gained `11698880`, `11669928`, `11661876`; lost `11663540`.
  - [ ] Keep Loop103 suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop128 parent/representative replay NO-GO

- 상태: Loop128 parent packet completed `38/38/0/0`, but runtime contract `NO-GO`; semantic quality `NO-GO / REVIEW-LOCKED`; overall goal `NOT_COMPLETE`
- TODO:
  - [x] Run Loop104 anti-regression parent/representative packet after Loop123-127 targeted repair.
  - [x] Record Loop128 run `20260630_010430_041790`.
  - [x] Confirm manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`.
  - [x] Run runtime audit `loop128_parent_representative_replay_runtime_audit.md/json`.
  - [x] Record strict runtime contract `NO-GO`: endpoint filter `16` < required `36`.
  - [x] Record semantic NO-GO rows: golden positive losses `11698897`, `11663521`, `11685994`, `11694019`, `11700470`, `11705231`.
  - [x] Record recent P0 HOLD/control public-title gain `11706871 -> 파우스트 1`.
  - [x] Create review artifact `loop128_parent_representative_replay_after_loop127_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_128_REPORT_20260630.md`.
  - [x] Data Analytics artifact `Loop128 Parent Replay NO-GO Review` validate/render PASS.
  - [ ] Restore or explicitly audit enough healthy endpoints for a clean parent replay.
  - [ ] Rerun the 38-row parent/representative packet with runtime contract `GO`.
  - [ ] Investigate Loop128 semantic problem rows before resuming Loop103 P1/P2.
  - [ ] Keep parent/representative replay `OPEN`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 regression-safe grounding Loop123-127 public-title reopen repair

- 상태: Loop123-126 repeated variance/reopen evidence / Loop127 targeted five-row public-title hold pass / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- TODO:
  - [x] Repeat Loop115 five-row packet as Loop123 after Loop122 official URL recall bypass.
  - [x] Record Loop124 `NO-GO_REOPENED_11694019`.
  - [x] Record Loop125 `NO-GO_REOPENED_11658620_11668288`.
  - [x] Record Loop126 `NO-GO_REOPENED_11694019`.
  - [x] Add alias-only official URL recall competing-candidate hold.
  - [x] Add generic low-information batch alias blocking.
  - [x] Add forced-upgrade relation-hold blocker.
  - [x] Broaden author+plot composite precision demotion.
  - [x] Add focused regression tests.
  - [x] `py_compile` PASS.
  - [x] Related unittest bundle PASS (`271` tests OK).
  - [x] Loop127 run `20260630_004841_310108` completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, identified `0`.
  - [x] Create review artifact `loop123_127_public_title_reopen_repair_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_123_127_REPORT_20260630.md`.
  - [x] Data Analytics artifact `Loop123-127 Public Title Reopen Repair Review` validate/render PASS.
  - [ ] Run parent/representative replay with recent HOLD controls and golden positive/negative controls.
  - [ ] Keep Loop103 P1/P2 suspended until broader replay passes.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop120-121 batch alias competing-hold guard

- 상태: Loop120 repeat reopened `11698897` / batch alias competing-hold guard patch applied / Loop121 targeted reopen blocked / positive-control drift remains OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- TODO:
  - [x] Repeat Loop119 five-row packet as Loop120.
  - [x] Record Loop120 `NO-GO_REOPENED_11698897`: `[림월드]변방계에서 회귀자로 살아남기` reopened through batch-memory alias rescue.
  - [x] Root-cause `title_lead_alias_official_detail_release` rescue overriding competing-candidate hold flags.
  - [x] Add competing-hold batch alias rescue block in `src/llm_batch/agentic_pipeline.py`.
  - [x] Add candidate-audit demotion before official-detail/precision exemptions.
  - [x] Add regression test for the `랫따싶` / `[림월드]...` competing-hold path.
  - [x] `py_compile` PASS.
  - [x] Affected unittest PASS (`248` tests OK).
  - [x] Loop121 run `20260629_233340_435398` completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, identified `0`.
  - [x] Confirm `11698897` final public title `null`, `candidate_ledger_status=promotion_blocked`, with `batch_memory_alias_rescue_blocked_competing_hold`.
  - [x] Create review artifact `loop120_121_batch_alias_competing_hold_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_120_121_REPORT_20260629.md`.
  - [x] Data Analytics artifact `Loop120-121 Batch Alias Competing-Hold Review` validate/render PASS.
  - [ ] Investigate `11668288` positive/control drift from resolved to `null`/`promotion_blocked`.
  - [ ] Run parent/representative replay with recent HOLD controls and golden positive/negative controls.
  - [ ] Keep Loop103 P1/P2 suspended until broader replay passes without collateral movement.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop116b-116d lubko prefix-context guard

- 상태: 4-row prefix reproduces `11658620` unsafe public title / ambiguous alias guard patch applied / Loop116c+116d repeat HOLD / targeted repair evidence only / semantic quality REVIEW-LOCKED / full scan approval false
- TODO:
  - [x] Build Loop116b four-row prefix packet from original Loop108 rows.
  - [x] Reproduce `11658620` unsafe public title in Loop116b run `20260629_215526_021681`.
  - [x] Add ambiguous stable-alias bridge guard in `src/llm_batch/agentic_pipeline.py`.
  - [x] Preserve known-title abbreviation update-question rescue through later semantic no-work gate.
  - [x] Add focused ambiguous attached slang test.
  - [x] Loop116c run `20260629_220351_554714` completed `4/4/0/0`, VLM/OCR `READY`, `11658620` HOLD.
  - [x] Loop116d repeat `20260629_221301_518080` completed `4/4/0/0`, VLM/OCR `READY`, `11658620` HOLD.
  - [x] `py_compile` PASS; `tests.test_candidate_audit` `83 OK`; `tests.test_known_title_abbreviation_support` `25 OK`; focused stable-alias correction integration OK.
  - [x] Create review artifact `loop116b_116d_lubko_prefix_context_guard_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_116B_116D_REPORT_20260629.md`.
  - [x] Data Analytics artifact `Loop116b-116d Lubko Prefix Guard Review` validate/render PASS.
  - [x] Run broader replay including all Loop114 public-title gain rows before resuming Loop103 P1/P2: Loop117 run `20260629_222704_833019`.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop118-119 reopen guard replay

- 상태: Loop117 reopened paths root-caused / Loop119 targeted replay holds target reopen rows / `11668288` positive-control resolved / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- TODO:
  - [x] Root-cause Loop117 recurrent public-title reopenings for `11666713`, `11694019`, and `11698897`.
  - [x] Add sticky verifier re-promotion veto for search-absent/nullified exact-title paths.
  - [x] Add cross-media title-body-only official URL recall hold.
  - [x] Add high-strength weak-source exact-title bridge hold with medium registry/known-abbreviation exemption.
  - [x] Loop118 run `20260629_225200_510563` completed `5/5/0/0`; `11694019` and `11698897` held, `11666713` still reopened.
  - [x] Loop119 run `20260629_225904_808962` completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, identified `1`.
  - [x] Confirm Loop119 holds `11666713`, `11694019`, and `11698897` with final public title `null`.
  - [x] Separate `11668288` as known positive/control resolution, not target regression closure.
  - [x] `py_compile` PASS; affected unittest `247 OK`; `git diff --check` PASS with line-ending warnings only.
  - [x] Create review artifact `loop118_119_reopen_guard_replay_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_118_119_REPORT_20260629.md`.
  - [x] Data Analytics artifact `Loop118-119 Reopen Guard Replay Review` validate/render PASS.
  - [ ] Repeat Loop119 or run parent/representative lane with recent HOLD controls and golden positive/negative controls.
  - [ ] Keep Loop103 P1/P2 suspended until broader replay passes without collateral movement.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop117 public-title gain replay after guard

- 상태: Loop117 runtime GO / 3 of 5 rows reopened public titles / broader replay NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- TODO:
  - [x] Rerun existing Loop115 five-row variance packet after Loop116b-116d guard.
  - [x] Loop117 run `20260629_222704_833019` completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, identified `3`.
  - [x] Confirm `11658620` remained blocked with `candidate_ledger_status=promotion_blocked`.
  - [x] Confirm recurrent public-title reopenings: `11666713`, `11694019`, `11698897`.
  - [x] Create review artifact `loop117_public_title_gain_after_guard_replay_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_117_REPORT_20260629.md`.
  - [x] Data Analytics artifact `Loop117 Public Title Gain Replay` validate/render PASS.
  - [x] Root-cause recurrent public-title reopenings for `11666713`, `11694019`, and `11698897` in Loop118-119 targeted repair.
  - [ ] Keep Loop103 P1/P2 suspended until broader replay passes without collateral movement.

## 2026-06-29 regression-safe grounding Loop115 goal completion recheck / variance repeat

- 상태: Loop06 completion recheck confirms overall goal NOT_COMPLETE / source full completion OPEN / full-panel collateral approval NO-GO / Loop115 repeat runtime GO but variance quarantine / semantic quality REVIEW-LOCKED / full scan approval false
- TODO:
  - [x] Re-read pasted original goal contract and confirm Loop06 targeted closure is not full pasted-goal completion.
  - [x] Run source/preflight, collateral/semantic, and docs/gate read-only subagent audits.
  - [x] Build Loop115 focus packet from original Loop108 rows for `11658620`, `11666713`, `11668288`, `11694019`, `11698897`.
  - [x] Loop115 run `20260629_212549_694367` completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, identified `0`.
  - [x] Create review artifact `loop115_goal_completion_recheck_variance_repeat_review.md/json`.
  - [x] Data Analytics artifact `Loop115 Goal Completion Recheck` validate/render PASS.
  - [x] Repair garbled title text in `loop111_114_platform_ocr_seo_replay_review.md`.
  - [ ] Do not treat Loop115 all-HOLD repeat as approval; classify Loop114 gains as run-shape variance/quarantine.
  - [ ] Root-cause why Loop114 broad replay opened titles that Loop115 repeat blocked.
  - [ ] Keep Loop103 P1/P2 queue suspended until variance root-cause or quarantine rationale is durable.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop116a lubko neighbor context probe

- 상태: Loop116a runtime GO / `11658620` neighbor-context unsafe serialization NOT reproduced / root-cause narrowed but NOT_COMPLETE / semantic quality REVIEW-LOCKED / full scan approval false
- TODO:
  - [x] Build Loop116a two-row packet from original Loop108 rows: `11658615`, `11658620`.
  - [x] Run Loop116a `20260629_214134_424194` with `--slang-db off`, VLM/OCR on, and image VLM/OCR required.
  - [x] Confirm runtime completed/flushed/pending/failed `2/2/0/0`, VLM/OCR `READY`, identified `1`.
  - [x] Confirm `11658615` still resolves to `이거 럽코 빙의물인가요` / `https://novel.munpia.com/533816`.
  - [x] Confirm `11658620` preserves `primary_work=이거 럽코 빙의물인가요` but final public title remains `null`, `candidate_ledger_status=promotion_blocked`.
  - [x] Create review artifact `loop116a_lubko_neighbor_context_probe_review.md/json`.
  - [x] Create loop report `docs/devs/loop_reports/LOOP_116A_REPORT_20260629.md`.
  - [x] Data Analytics artifact `Loop116a Lubko Neighbor Context Probe` validate/render PASS.
  - [ ] Run wider prefix-context probe before code changes.
  - [ ] Compare broad-run search evidence and stable alias ledger state if the wider prefix still does not reproduce Loop114.
  - [ ] Keep Loop114 gains quarantined and the active goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 regression-safe grounding Loop111-114 platform/OCR SEO replay

- 상태: platform/OCR SEO canonicalization patch focused PASS / Loop114 runtime GO but semantic NO-GO / new public-title gains 4 / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- TODO:
  - [x] Add general platform SEO suffix/prefix and OCR `Lp코`/`럽 코` title-surface canonicalization.
  - [x] Focused tests PASS and full `tests.test_candidate_audit` PASS (`83 tests OK`); `py_compile` PASS.
  - [x] Loop111 focused `11658615` run `20260629_201405_077720` completed `1/1/0/0`, VLM/OCR `READY`.
  - [x] Loop112 broad run `20260629_201737_073867` completed `19/19/0/0`, VLM/OCR `READY`, identified `5`, semantic `NO-GO`.
  - [x] Loop113 focused run `20260629_204129_668787` completed `2/2/0/0`, VLM/OCR `READY`, canonicalized `11658615` and `11698897`.
  - [x] Loop114 broad replay `20260629_204604_191020` completed `19/19/0/0`, VLM/OCR `READY`, identified `8`.
  - [x] Review artifact `loop111_114_platform_ocr_seo_replay_review.md/json` 생성.
  - [x] Data Analytics artifact `Loop111-114 Platform OCR SEO Replay Review` validate/render PASS.
  - [ ] Do not treat Loop111/113 focused pass or Loop114 runtime GO as semantic approval.
  - [ ] Root-cause new Loop114 public-title gains `11658620`, `11666713`, `11668288`, `11694019`.
  - [ ] Recheck why `11698897` focused PASS did not remain safe in the Loop114 broad replay.
  - [ ] Keep Loop103 P1/P2 queue suspended until a clean replay stabilizes.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop106-107 scene/author guard clean replay

- 상태: `11714903` focused fixed / Loop106 runtime GO but `11695637` reopened / scene-only author anchor guard added / Loop107 runtime GO / focused public-title rows `7/7` blocked / identified set unstable / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- TODO:
  - [x] Add general hygiene alias/image conflict guard for `11714903` without post-id hardcoding.
  - [x] Focused `11714903` canary run `20260629_170648_212786` completed `1/1/0/0`, VLM/OCR `READY`, public title blocked.
  - [x] Clean Loop106 replay run `20260629_171206_948236` completed `38/38/0/0`, VLM/OCR `READY`.
  - [x] Record Loop106 semantic `NO-GO`: `11714903` blocked, but `11695637` reopened as `도네하지 마라`.
  - [x] Extend image scene-cue public-title bridge guard to scene-only `author` anchors.
  - [x] Focused `11695637` canary run `20260629_175300_045051` completed `1/1/0/0`, VLM/OCR `READY`, public title blocked.
  - [x] Focused guard tests PASS and `py_compile` PASS.
  - [x] Clean Loop107 replay run `20260629_175738_653862` completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`.
  - [x] Loop107 focused public-title rows `7/7` blocked.
  - [x] Review artifact `loop107_clean_loop104_replay_after_scene_author_guard_review.md/json` 생성.
  - [x] Data Analytics artifact `Loop107 Clean Replay NO-GO Review` validate/render PASS.
  - [ ] Do not treat Loop107 runtime GO or focused closure as semantic approval.
  - [ ] Review Loop106 to Loop107 state changes `19` and identified count drop `12 -> 7`.
  - [ ] Separate desired precision demotions from recall regressions before Loop103 queue resumes.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop108-110 state-change repair

- 상태: Loop107 state changes triaged / Loop108 19-row replay NO-GO / guard patch focused PASS / Loop110 broad replay confirms patch targets / remaining attention rows 5 / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- TODO:
  - [x] Loop107 state-change triage artifact `loop107_state_change_triage.md/json` 생성.
  - [x] Loop108 input `loop108_state_change_adjudication_packet.jsonl` 생성; original Loop104 rows only.
  - [x] Loop108 run `20260629_185544_955672` completed/flushed/pending/failed `19/19/0/0`, VLM/OCR `READY`, identified `8`, semantic `NO-GO`.
  - [x] Add candidate-audit guards for VLM/OCR conflict bypass, secondary-reference precision-downgrade rescue, and direct exact short official titles.
  - [x] `py_compile` PASS and full `tests.test_candidate_audit` `80 OK`.
  - [x] Loop109 focused run `20260629_192037_957246` completed `3/3/0/0`, VLM/OCR `READY`, focused pass `3/3`.
  - [x] Loop110 broad replay `20260629_193104_492126` completed `19/19/0/0`, VLM/OCR `READY`, identified `5`.
  - [x] Loop110 patch targets confirmed: `11660237 -> 테라포밍`, `11700470` HOLD, `11706832` HOLD.
  - [x] Review artifacts `loop108_state_change_adjudication_review.md/json`, `loop109_targeted_guard_repair_3_review.md/json`, `loop110_state_change_post_patch_replay_review.md/json` 생성.
  - [x] Loop report `docs/devs/loop_reports/LOOP_108_110_REPORT_20260629.md` 생성.
  - [x] Data Analytics artifact `Loop108-110 상태 변화 보정 리뷰` validate/render PASS.
  - [ ] Do not treat Loop109 focused pass or Loop110 target pass as goal completion.
  - [ ] Separate remaining attention rows `11658615`, `11663540`, `11666713`, `11668288`, `11705231`.
  - [ ] Keep Loop103 P1/P2 queue suspended until a clean replay stabilizes.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop104 repair patch / reclassification

- 상태: candidate-ledger extraction fixed / static NO-GO reclassified / focused canaries public title blocked / clean Loop104 replay runtime GO but semantic NO-GO / 11714903 reopened as `괴담 호텔 탈출기` / Loop105 repeat not run / Loop103 queue suspended / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- TODO:
  - [x] Static repair artifact `loop104_repair_patch_static_reclassification.md/json` 생성.
  - [x] Old NO-GO `9` 중 candidate-ledger extraction false positives `5` 제거.
  - [x] True NO-GO remaining before clean replay `4`: `11660257`, `11714903`, `11694035`, `11713212`.
  - [x] `tools/build_targeted_followup_remaining_queue.py`가 promotion-blocked `primary_work` 후보를 final title로 읽지 않도록 수정.
  - [x] `src/llm_batch/agentic_pipeline.py`의 `final_decision` fallback과 verifier-counter generic setting/trope title promotion block 보강.
  - [x] Focused unit tests and `py_compile` PASS.
  - [x] Focused `11713212` canary run `20260629_152235_538688` completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, public title `None` 확인.
  - [x] Runtime audit `loop104_repair_11713212_single_runtime_audit.md/json` gate `TARGETED_GO_PUBLIC_TITLE_BLOCKED` 생성.
  - [x] Focused `11694035` canary run `20260629_153923_967759` completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, public title blocked 확인.
  - [x] Runtime audit `loop104_repair_11694035_single_runtime_audit.md/json` and current status `loop104_repair_patch_current_status.md/json` 생성.
  - [x] Focused `11660257` canary run `20260629_155128_226258` completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, public title blocked/non-relevant HOLD 확인.
  - [x] Runtime audit `loop104_repair_11660257_single_runtime_audit.md/json` 생성.
  - [x] Focused `11714903` canary run `20260629_155831_556987` completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, public title blocked/candidate HOLD 확인.
  - [x] Runtime audit `loop104_repair_11714903_single_runtime_audit.md/json` 생성.
  - [x] Remaining true promotion `11714903` classified as final serialized public-title blocked, with internal alias-conflict risk preserved for replay.
  - [x] Data Analytics artifact `Loop104 Repair Patch Reclassification Review` validate/render PASS.
  - [x] Clean 38-row replay run `20260629_161143_395663` completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`.
  - [x] Runtime review artifact `loop105_clean_loop104_replay_after_repair_review.md/json` 생성.
  - [x] Data Analytics artifact `Loop105 Clean Replay NO-GO Review` validate/render PASS.
  - [x] Repeat confirmation result recorded: `11694035`, `11713212`, `11660257` stayed blocked; `11714903` reopened.
  - [ ] Do not treat the `11713212` single canary as Loop104 approval.
  - [ ] Do not treat the `11694035` single canary as Loop104 approval.
  - [ ] Do not treat the `11660257` single canary as Loop104 approval.
  - [ ] Do not treat the `11714903` single canary as Loop104 approval.
  - [ ] Root-cause `11714903` clean-replay public-title reopening before any Loop105 repeat is used as approval evidence.
  - [ ] Add or adjust a general alias-conflict / VLM-OCR-title-conflict guard without post_id/title-specific hardcoding.
  - [ ] Rerun the 38-row replay after the guard, then run a repeat only if the clean replay is semantic GO/REVIEW acceptable.
  - [ ] Keep source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop104 anti-regression replay NO-GO

- 상태: Loop104 primary replay partial / recovery completed / effective 38-row review available / anti-regression gate NO-GO / Loop103 queue suspended / source full completion OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- TODO:
  - [x] Loop104 anti-regression replay packet `38` rows, image_post_count `24` 생성.
  - [x] Primary Loop104 run `20260629_140125_587992` completed/flushed/pending/failed `36/34/2/0`, `large_run_complete=false` 확인.
  - [x] Recovery input `3` rows 생성 and recovery run `20260629_144615_496378` completed/flushed/pending/failed `3/3/0/0` 확인.
  - [x] Effective 38-row review artifacts `loop104_anti_regression_replay_no_go_review.md/json` and gate map 생성.
  - [x] Data Analytics artifact `Loop104 Anti-Regression Replay NO-GO Review` validate/render PASS.
  - [x] Loop103 next actionable total `131`, P0 `0`, P1 `61`, P2 `70`을 `SUSPENDED_UNTIL_ANTI_REGRESSION_REPAIR`로 전환.
  - [ ] Do not continue isolated P1/P2 queue while Loop104 is NO-GO.
  - [ ] Root-cause golden negative public-title hard fails `11694035`, `11713212`.
  - [ ] Root-cause stable/HOLD public-title gains `11658615`, `11658620`, `11660257`, `11695623`, `11705261`, `11714903`, `11695637`.
  - [ ] Review golden positive losses/mismatches before treating recall as stable.
  - [ ] After fixes, rerun a clean Loop104 replay and then repeat Loop105.

## 2026-06-29 regression-safe grounding Loop 102-103 P1 accept-collateral monitor review

- 상태: Loop102/103 runtime PASS / P1 `accept_collateral_monitor=8` reviewed / stable resolved recovery `1` / stable no-public HOLD `6` / variance quarantine `1` / full reviewed residual ledger `136` / quarantine `5` / next actionable queue total `131`, P0 `0`, P1 `61`, P2 `70` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- TODO:
  - [x] Loop102 input `8` rows and manifest를 생성했다.
  - [x] Loop102 completed/flushed/pending/failed `8/8/0/0`, VLM/OCR `READY`, identified `2/8`을 확인했다.
  - [x] Loop103 repeat completed/flushed/pending/failed `8/8/0/0`, VLM/OCR `READY`, identified `1/8`을 확인했다.
  - [x] Runtime audits for Loop102/103 both returned `GO`.
  - [x] `11660258` stable resolved recovery를 확인했다.
  - [x] `11658615`를 branded-title/null repeat variance로 quarantine/human_review 분리했다.
  - [x] Data Analytics artifact `Loop102-103 P1 Accept-Collateral Monitor Review` validate/render PASS.
  - [x] Review artifacts `loop102_103_p1_accept_collateral_monitor_repeatability_review.md/json`, residual map `loop103_current_residual_gate_map_after_p1_accept_collateral_monitor.md/json`, Loop102-103 report를 추가했다.
  - [ ] Do not count stable no-public/HOLD rows as public title approval.
  - [ ] Do not count Loop102-103 as full anti-regression approval.
  - [ ] Before more single-post/code-fix work, build Loop104 or equivalent missing-control replay packet.
    - include `11698880`, `11669928`, `11674712`, `11668288`, `11658615`.
    - include Loop92-93 stable closed rows, recent P0 HOLD controls, and golden positive/negative controls.
    - verify repeat stability, affected-module tests, and collateral movement before further residual reduction.
  - [ ] Continue P1 `recall_loss_review=61` and P2 `safety_demote_review=70` only after the missing-control replay is recorded.

## 2026-06-29 regression-safe grounding Loop 98-101 P1 descriptor guard review

- 상태: Loop98-101 runtime PASS / descriptor wrong-title bug fixed for targeted path / row `11698880` -> `VARIANCE_QUARANTINE_HUMAN_REVIEW` / stable closure `0` / full reviewed residual ledger `143` / quarantine `4` / next actionable queue total `139`, P0 `0`, P1 `69`, P2 `70` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- TODO:
  - [x] Loop98/99로 `11698880` pre-fix 반복성을 확인했다.
  - [x] Loop99에서 `상남자 [독점]` wrong public title 승격을 재현했다.
  - [x] `agentic_pipeline.py`에 descriptor-only stable alias correction guard를 추가했다.
  - [x] descriptor-negative / title-alias positive-control 테스트를 추가했다.
  - [x] Loop100/101 post-fix 반복 실행을 완료했다.
  - [x] Data Analytics artifact `Loop98-101 Stable Alias Descriptor Guard Review` validate/render PASS.
  - [x] Review artifacts `loop98_101_p1_regression_control_stable_alias_descriptor_guard_review.md/json`, residual map `loop101_current_residual_gate_map_after_p1_regression_control_variance.md/json`, Loop98-101 report를 추가했다.
  - [ ] Do not count Loop101 expected-title output as semantic approval because Loop100 remained null/adjacent.
  - [x] Do not continue one-post picking as the immediate next step; Loop102-103 moved to an 8-row P1 repeatability lane.
  - [ ] Loop102-103 did not fully cover fixed/quarantine/golden/control rows, so keep Loop104 missing-control replay open.

## 2026-06-29 regression-safe grounding Loop 96-97 P1 search-correctness variance review

- 상태: Loop96/97 runtime PASS / P1 search-correctness row `11668288` -> `VARIANCE_QUARANTINE_HUMAN_REVIEW` / stable closure `0` / full reviewed residual ledger `143` / quarantine `3` / next actionable queue total `140`, P0 `0`, P1 `70`, P2 `70` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop96 P1 search-correctness input `1` row and manifest를 생성했다.
  - [x] Native web verification으로 `https://novelpia.com/novel/387014` -> `가챠 중독자의 퓨전펑크 생활`을 확인했다.
  - [x] Loop96 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, identified `1/1`, `safe_resolved`를 확인했다.
  - [x] Loop97 repeat completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, identified `0/1`, `promotion_blocked`/`unresolved_matchable`를 확인했다.
  - [x] `11668288`이 RESOLVED/HOLD로 갈리는 반복 variance를 확정했다.
  - [x] `--slang-db off` run에서 production `slang_db/slang_db.json` write-back이 없음을 last modified time으로 확인했다.
  - [x] Data Analytics artifact `Loop96-97 P1 Search-Correctness Variance Review` validate/render PASS.
  - [x] Review artifacts `loop96_97_p1_recall_loss_search_correctness_repeatability_review.md/json`, residual map `loop97_current_residual_gate_map_after_p1_search_variance.md/json`, Loop96-97 report를 추가했다.
- 남은 작업:
  - [ ] `11668288`을 approval이나 stable closure로 승격하지 않는다.
  - [ ] P1 `recall_loss_review=70`을 다음 actionable lane으로 계속 진행한다.
  - [ ] P2 `safety_demote_review=70`을 open으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 94-95 P1A variance repeatability review

- 상태: Loop94/95 runtime PASS / P1A variance rows `2` -> `VARIANCE_QUARANTINE_HUMAN_REVIEW` / stable closure `0` / full reviewed residual ledger `143` / quarantine `2` / next actionable queue total `141`, P0 `0`, P1 `71`, P2 `70` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop94 P1A variance-open input `2` rows and manifest를 생성했다.
  - [x] Model endpoint `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`를 확인했다.
  - [x] Loop94 completed/flushed/pending/failed `2/2/0/0`, image gate `NOT_APPLICABLE`, identified `0/2`를 확인했다.
  - [x] Loop95 repeat completed/flushed/pending/failed `2/2/0/0`, image gate `NOT_APPLICABLE`, identified `1/2`를 확인했다.
  - [x] Loop94/95 leak audit `0`을 확인했다.
  - [x] `11669928` = HOLD/HOLD/RESOLVED, `11674712` = RESOLVED/HOLD/HOLD로 반복 variance를 확정했다.
  - [x] Data Analytics artifact `Loop94-95 P1A Variance Repeatability Review` validate/render PASS.
  - [x] Review artifacts `loop94_95_p1a_variance_repeatability_review.md/json`, residual map `loop95_current_residual_gate_map_after_p1a_variance.md/json`, Loop94-95 report를 추가했다.
- 남은 작업:
  - [ ] `11669928`, `11674712`를 approval이나 stable closure로 승격하지 않는다.
  - [ ] P1 `recall_loss_review=71`을 다음 actionable lane으로 계속 진행한다.
  - [ ] P2 `safety_demote_review=70`을 open으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 92-93 P1A expected recall-improvement review

- 상태: Loop92/93 runtime PASS / P1A expected recall improvement PARTIAL_REVIEWED_WITH_VARIANCE / stable closed `4`, variance open `2` / current residual total `143`, P0 `0`, P1 `73`, P2 `70` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop92 P1A input `6` rows and manifest를 생성했다.
  - [x] Model endpoint `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`를 확인했다.
  - [x] Loop92 completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`, identified `1/6`을 확인했다.
  - [x] Loop92에서 promotion-blocked public URL/primary-role contract leak `3` rows를 확인했다.
  - [x] `expert_main.py` serialized promotion-blocked contract scrub을 public URL/nested URL/primary-role까지 확장했다.
  - [x] Loop93 completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`, identified `1/6`을 확인했다.
  - [x] Loop93 leak audit `promotion_blocked_public_url_or_primary_role_leaks=0`을 확인했다.
  - [x] P1A stable HOLD/no-public/no-work rows `4` and variance-open rows `2`를 분리했다.
  - [x] `py_compile` PASS, focused serialized contract tests PASS, `tests.test_expert_main_comment_metadata -v` `9 tests OK`.
  - [x] Review artifacts `loop92_93_p1a_expected_recall_improvement_review.md/json`, residual map `loop93_current_residual_gate_map_after_p1a.md/json`, Loop92-93 report를 추가했다.
  - [x] Data Analytics artifact `Loop92-93 P1A Expected Recall Improvement Review` validate/render PASS.
- 남은 작업:
  - [ ] `11669928`, `11674712` variance-open rows를 approval로 승격하지 않는다.
  - [ ] Loop92-93 P1A targeted progress를 full-panel collateral approval로 승격하지 않는다.
  - [ ] P1 recall-loss backlog `71` and P2 safety-demote backlog `70`을 계속 open으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 88-91 P0A scope-decision HOLD output consistency

- 상태: Loop88/90 failure evidence retained / Loop91 targeted safe HOLD for `11698871` / P0A scope-decision row TARGETED_SCOPE_DECISION_HOLD_CONSISTENT / public title approval NOT_APPROVED / current residual total `147`, P0 `0`, P1 `77`, P2 `70` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop88 input `loop88_p0a_scope_decision_11698871_1.jsonl` and manifest를 생성했다(row_count `1`, image_post_count `0`).
  - [x] Loop88 targeted canary completed/flushed/pending/failed `1/1/0/0`을 확인하고 public URL/reason confirmation 누수를 failure evidence로 보존했다.
  - [x] Precision-seed demotion이 top-level `identity.heretic_url`를 함께 clear하도록 수정했다.
  - [x] Loop89 targeted canary completed/flushed/pending/failed `1/1/0/0`으로 URL cleanup path를 확인했다.
  - [x] Loop90 targeted canary completed/flushed/pending/failed `1/1/0/0`을 확인하고 reason/analysis.notes confirmation 누수를 failure evidence로 보존했다.
  - [x] Promotion-blocked serialized result contract scrub을 `expert_main.py`에 추가했다.
  - [x] Loop91 targeted canary completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `NOT_APPLICABLE`, final public title/url `null`을 확인했다.
  - [x] Loop91 `11698871`은 `work_resolution=unresolved`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`, `candidate_count=7`로 candidate/HOLD만 보존한다.
  - [x] `py_compile` PASS, focused URL cleanup PASS, focused serialized contract scrub PASS, `tests.test_candidate_audit -v` `74 tests OK`, `tests.test_expert_main_comment_metadata -v` `8 tests OK`.
  - [x] Review artifacts `loop88_91_p0a_scope_decision_hold_review.md/json`, residual map `loop91_current_residual_gate_map_after_p0a.md/json`, Loop88-91 report를 추가했다.
  - [x] Data Analytics artifact `Loop88-91 P0A Scope Decision HOLD Review` validate/render PASS.
- 남은 작업:
  - [ ] P0 `0` 또는 queue zero를 approval로 승격하지 않는다.
  - [ ] `11698871` safe HOLD를 public title approval로 승격하지 않는다.
  - [ ] Loop91 targeted closure를 full-panel collateral approval로 승격하지 않는다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 84-87 P0E variant canonicalization guard

- 상태: Loop85/86 failure evidence retained / Loop87 targeted safe HOLD for `11666713` / P0E wrong-title switch TARGETED_WRONG_TITLE_BLOCKED_SAFE_HOLD / canonical title recovery NOT_APPROVED / current residual total `148`, P0 `1` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop84 current-code P0E rerun completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`를 확인했다.
  - [x] Loop85에서 first review-anchor patch가 `11666713`을 wrong title `21세기 헌터가된 무림인`으로 overpromotion하는 실패를 재현/보존했다.
  - [x] Loop86에서 surface-match narrowing만으로는 plain title-body anchor 우회를 막지 못함을 재현했다.
  - [x] Short work-style review official-url recall은 post-side surface containment가 있을 때만 허용하도록 guard를 추가했다.
  - [x] Title-body work-review surface mismatch는 `official_url_recall_blocked_title_body_work_review_surface_mismatch`로 즉시 차단하도록 했다.
  - [x] Loop87 focused canary completed/flushed/pending/failed `1/1/0/0`, final public title/url `null`, `title_resolution_allowed=false`를 확인했다.
  - [x] `py_compile` PASS, focused P0E guard tests PASS, `tests.test_title_lead_search_inferred_guard -v` `133 tests OK`.
  - [x] Review artifacts `loop84_87_p0e_variant_canonicalization_guard_review.md/json`, residual map `loop87_current_residual_gate_map_after_p0e.md/json`, Loop84-87 report를 추가했다.
  - [x] Data Analytics artifact `Loop84-87 P0E Variant Canonicalization Guard Review` validate/render PASS.
- 남은 작업:
  - [ ] Loop87 safe HOLD를 canonical title approval로 승격하지 않는다.
  - [ ] Loop87 targeted P0E closure를 full-panel collateral approval로 승격하지 않는다.
  - [ ] Remaining P0 `1`: `11698871` P0A scope-decision HOLD.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 82-83 P0D title variant/canonicalization repair

- 상태: Loop82 P0D targeted canary runtime PASS but `11706871` false public-title promotion / Loop83 focused guard PASS / P0D lane TARGETED_REPAIRED_OR_HELD_4_OF_4 / current residual total `149`, P0 `2` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop82 P0D input `4` rows and manifest를 생성했다.
  - [x] Loop82 targeted canary completed/flushed/pending/failed `4/4/0/0`, VLM/OCR `READY`를 확인했다.
  - [x] Loop82에서 `11706871`의 non-novel/literature OCR title `파우스트 1` false promotion을 재현했다.
  - [x] Non-novel/literature discourse warning이 structured OCR/cover title acceptance와 late title promotion을 우회하지 못하도록 guard를 추가했다.
  - [x] Loop83 focused canary completed/flushed/pending/failed `1/1/0/0`, final public title `null`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`를 확인했다.
  - [x] `py_compile` PASS, focused new test PASS, OCR/reference guard tests PASS, `tests.test_title_lead_search_inferred_guard -v` `131 tests OK`.
  - [x] Review artifacts `loop82_83_p0d_title_variant_canonicalization_review.md/json`, residual map `loop83_current_residual_gate_map_after_p0d.md/json`, Loop82-83 report를 추가했다.
  - [x] Data Analytics artifact `Loop82-83 P0D Title Variant Canonicalization Review` validate/render PASS.
- 남은 작업:
  - [ ] Loop82-83 targeted P0D closure를 full-panel collateral approval로 승격하지 않는다.
  - [ ] `11706871`의 polluted candidate ledger는 source-review caveat로 유지한다.
  - [ ] Remaining P0 `2`: `11698871` P0A scope-decision HOLD, `11666713` P0E variant canonicalization follow-up.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 79-81 P0C unexpected public-title repair

- 상태: Loop80 reproduced P0C false positives `2/3` / Loop81 targeted PASS public title `0/3` / P0C unexpected public-title lane TARGETED_REPAIRED_3_OF_3 / current residual total `153`, P0 `6` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop79 P0C input `3` rows and manifest를 생성했다.
  - [x] Loop80 targeted canary completed/flushed/pending/failed `3/3/0/0`으로 `11658621`, `11718105` false-positive public title을 재현했다.
  - [x] Title-body-only official URL recall이 Arbiter deliberate-null을 뒤집지 못하도록 guard를 추가했다.
  - [x] `시리즈` 같은 platform/service alias가 official-alias rescue의 단일 작품 alias로 승격되지 않도록 guard를 추가했다.
  - [x] `multi_work_title_cleared` 이후 secondary-reference/search official-alias rescue를 차단했다.
  - [x] Loop81 targeted canary completed/flushed/pending/failed `3/3/0/0`, public title `0/3`을 확인했다.
  - [x] `py_compile` PASS, `tests.test_title_lead_search_inferred_guard -v` `130 tests OK`, affected suites `115 tests OK`.
  - [x] Review artifacts `loop79_81_p0c_unexpected_public_title_review.md/json`, residual map `loop81_current_residual_gate_map_after_p0c.md/json`, Loop79-81 report를 추가했다.
  - [x] Data Analytics artifact `Loop79-81 P0C Unexpected Public Title Review` validate/render PASS.
- 남은 작업:
  - [ ] Loop81 targeted pass를 full-panel collateral approval로 승격하지 않는다.
  - [ ] `11698871`은 P0A scope-decision HOLD로 유지한다.
  - [ ] 다음 P0 lane은 P0D variant/canonicalization `4` rows 또는 P0E variant `11666713`에서 선택한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 76-78 P0A follow-up repair

- 상태: Loop76 runtime PASS but risky overpromotion retained / Loop77 runtime PASS with public title `5/6` but `11697267` wrong URL / Loop78 focused URL guard PASS for `11697267` / P0A status PARTIAL_REPAIRED_WITH_SCOPE_HOLD / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] `엑칼뽑 -> 엑스칼리버 뽑습니다` known-title abbreviation을 추가했다.
  - [x] Character/work-cue update question에서 known-title abbreviation recall이 작동하도록 anchor를 보강했다.
  - [x] Curated alias resolution anchor recursion guard를 추가했다.
  - [x] Same-URL official-detail canonicalization과 precision/weak-bridge bypass를 이어서 보강했다.
  - [x] Same-frame wrong-core URL guard를 추가해 `아카데미 금태양 갤러리` URL이 `아카데미 생존 갤러리`를 지지하지 못하게 했다.
  - [x] Loop76 targeted canary completed/flushed/pending/failed `6/6/0/0`을 확인하고 risky `11698871` overpromotion을 실패 증거로 보존했다.
  - [x] Loop77 targeted canary completed/flushed/pending/failed `6/6/0/0`을 확인하고 public title `5/6`, safe accepted `4/6`, URL mismatch `1/6`을 기록했다.
  - [x] Loop78 `11697267` focused canary completed/flushed/pending/failed `1/1/0/0`으로 `https://novelpia.com/novel/380218` 회복을 확인했다.
  - [x] `py_compile` PASS 및 `tests.test_final_semantic_reread_gate tests.test_known_title_abbreviation_support tests.test_candidate_audit -v` `115 tests OK`.
  - [x] Review artifacts `loop76_78_p0a_followup_repair.md/json` and Loop76-78 report를 추가했다.
  - [x] Data Analytics artifact `Loop76-78 P0A Follow-up Repair` validate/render PASS.
- 남은 작업:
  - [ ] Loop78 single-row URL guard proof를 P0A lane completion이나 full approval로 승격하지 않는다.
  - [ ] `11698871`은 character/cross-media alias context safe HOLD/scope-decision row로 유지한다.
  - [ ] P0A status는 `PARTIAL_REPAIRED_WITH_SCOPE_HOLD`로 유지하고 full-panel collateral backlog와 분리한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 74-75 P0A expected restoration repair

- 상태: Loop74 runtime PASS but weak-alias late demotion partial / Loop75 runtime PASS / P0A public expected restoration improved `0/6 -> 3/6` / remaining HOLD `3/6` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop73 P0A `0/6` no-go rows의 precision-seed demotion 경로를 진단했다.
  - [x] Same-URL official-detail canonicalization을 precision guard 전에 적용해 짧은 alias surface를 공식 상세 canonical title로 보정했다.
  - [x] Independent official-detail support가 있는 precision seed에 한해 `precision_seed_independent_official_detail_supported` bypass를 추가했다.
  - [x] Identity consistency lint와 weak public-title bridge guard가 해당 bypass를 다시 demote하지 않도록 공유했다.
  - [x] Focused precision/weak-bridge regression tests를 추가했다.
  - [x] `py_compile` PASS 및 `tests.test_candidate_audit -v` `72 tests OK`.
  - [x] Loop74 targeted canary completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`, public restored `1/6`.
  - [x] Loop75 targeted canary completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`, public restored `3/6`.
  - [x] Review artifacts `loop74_75_p0a_expected_restoration_repair.md/json` and Loop74/75 report를 추가했다.
  - [x] Data Analytics artifact `Loop74-75 P0A Expected Restoration Repair` validate/render PASS.
- 남은 작업:
  - [ ] Loop75 `3/6`을 P0A lane completion이나 semantic approval로 승격하지 않는다.
  - [ ] `11692444`는 `엑스칼리버 뽑습니다` official detail 미회복으로 계속 HOLD/open 유지한다.
  - [ ] `11697267`은 `아카데미 생존 갤러리` official detail 미회복/degraded 상태로 계속 HOLD/open 유지한다.
  - [ ] `11698871`은 character/cross-media context unsafe로 계속 HOLD/open 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 73 residual map + P0A expected restoration canary

- 상태: current residual map refreshed / remaining full-panel collateral backlog `161` / remaining P0 `14` / Loop73 P0A runtime PASS / semantic NO-GO expected restoration `0/6` public / candidate evidence preserved `5/6` / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop62 residual map에 Loop63, Loop64, Loop68-72 closure evidence를 반영해 `loop73_current_residual_gate_map.md/json`을 추가했다.
  - [x] P0B residual `4`, P0C slang `7`, P0E terminal rows `4`를 최신 residual count에서 제외했다.
  - [x] Loop64 `11666713`은 `21세기 무림` vs `21세기 무림세가` canonicalization caution으로 별도 open 유지했다.
  - [x] Remaining total `161`, remaining P0 `14`, P1 `77`, P2 `70`으로 갱신했다.
  - [x] Loop73 P0A input `loop73_p0a_expected_restoration_6.jsonl`과 manifest를 생성했다.
  - [x] Loop73 canary를 `--slang-db off --reuse-shards-only --parallel 6 --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
  - [x] Runtime completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`, large run complete `true`.
  - [x] Public expected restoration은 `0/6`; candidate/primary evidence preserved `5/6`; `11697267`은 expected not recovered.
  - [x] Review artifacts `loop73_current_residual_gate_map.md/json`, `loop73_p0a_expected_restoration_canary.md/json`, Loop73 report를 추가했다.
  - [x] Data Analytics artifacts `Loop73 Current Residual Gate Map` and `Loop73 P0A Expected Restoration Canary` validate/render PASS.
- 남은 작업:
  - [ ] Loop73 runtime PASS를 semantic approval로 승격하지 않는다.
  - [ ] P0A expected restoration은 `OPEN`으로 유지하고, candidate-preserved-but-promotion-blocked 원인을 수리한다.
  - [ ] `11697267` expected `아카데미 생존 갤러리` not recovered row를 별도 no-go로 추적한다.
  - [ ] Remaining P0C unexpected, P0D canonicalization, P0E variant caution lanes도 계속 open으로 유지한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 68-72 P0B residual guard continuation

- 상태: Loop68 `11671490` overpromotion reproduced NO-GO / Loop69 `11671490` targeted PASS / Loop70 `11695637` targeted PASS / Loop71 `11695639` partial URL gap / Loop72 `11695639` targeted PASS / Loop65 P0B residual rows TARGETED_REPAIRED / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop68에서 `11671490` direct-image/reference recommendation context가 `게임이 자꾸 사람을 구원함`으로 과승격되는 NO-GO를 재현했다.
  - [x] `candidate_audit`에 direct-image recommendation conflict와 recommendation-context-only public-title conflict hold guard를 추가했다.
  - [x] Loop69에서 `11671490` final `official_title=null`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`를 확인했다.
  - [x] `candidate_audit`에 image scene cue가 public-title bridge로 검증되지 않는 경우 hold하는 guard를 추가했다.
  - [x] Loop70에서 `11695637` final `official_title=null`, `candidate_ledger_status=promotion_blocked`, flag `image_scene_cues_unverified_public_title_bridge`를 확인했다.
  - [x] `agentic_pipeline`에 comment URL answer detail fetch/recovery와 validator-returned URL/candidate graph sync를 추가했다.
  - [x] Loop71에서 `11695639` title recovery but URL gap을 partial로 남겼다.
  - [x] Loop72에서 `11695639` final title `준우승 세 번 했더니 미소녀 됨`, URL `https://novelpia.com/novel/362860`, `primary_work.heretic_url` 보존을 확인했다.
  - [x] Review artifact `loop68_72_p0b_residual_guard_review.md/json`과 Loop68/69/70/71/72 reports를 추가했다.
  - [x] `py_compile` PASS, `tests.test_candidate_audit` `68 tests OK`, focused comment URL answer tests `6 tests OK`, `git diff --check` PASS(line-ending warnings only).
  - [x] Data Analytics artifact `Loop 68-72 P0B Residual Guard Review` validate/render PASS.
- 남은 작업:
  - [ ] Loop65 P0B residual targeted repair를 full-panel collateral approval로 승격하지 않는다.
  - [ ] Loop68 NO-GO와 Loop71 partial evidence를 historical failure/partial evidence로 유지한다.
  - [ ] 다음 concrete lane은 full-panel collateral backlog의 남은 P0A/P0C/P0D/P0E 또는 source full-completion gate에서 선택한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 65-67 P0B residual guard review

- 상태: Loop65 P0B residual targeted rerun semantic NO-GO / Loop66 generic label guard partial but late secondary rescue NO-GO / Loop67 `11706832` deliberate-null secondary rescue targeted PASS / P0B lane OPEN / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop62 `P0B_expected_mismatch_public_title=4` rows를 `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop65_p0b_residual_expected_mismatch_4.jsonl`로 추출했다.
  - [x] Loop65 targeted rerun을 `--slang-db off --reuse-shards-only --parallel 4 --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
  - [x] Loop65 runtime은 run id `20260629_054459_633571`, `large_run_complete=true`, failed rows `0`, VLM/OCR `READY`.
  - [x] Generic evidence-label lint를 추가하고 `웹소설` final-title demotion test를 추가했다.
  - [x] Loop66 single-row canary를 실행해 generic label은 제거됐지만 late secondary-reference rescue가 남는 것을 확인했다.
  - [x] `_title_deliberately_null` 이후 secondary-reference/search official-alias rescue를 차단했다.
  - [x] Loop67 single-row canary에서 `11706832` final `official_title=null`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`를 확인했다.
  - [x] Review artifact `loop65_67_p0b_residual_guard_review.md/json`과 Loop65/66/67 reports를 추가했다.
  - [x] Data Analytics artifact `Loop65-67 P0B Residual Guard Review` validate/render PASS.
- 남은 작업:
  - [ ] Loop65 `11671490`, `11695637`, `11695639`는 여전히 P0B lane open/no-go로 남긴다.
  - [ ] Loop67 targeted pass를 P0B lane completion이나 full-panel collateral approval로 승격하지 않는다.
  - [ ] 다음 concrete lane으로 남은 P0A restoration 또는 residual P0B row repair를 진행한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 64 P0E wrong title switch targeted rerun

- 상태: P0E targeted lane TARGETED_REVIEWED_5_OF_5 / Loop49 wrong-after title reproduced 0 / recovered before 3 / variant caution 1 / demoted 1 / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop51 `P0E_wrong_title_switch=5` rows를 `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop64_p0e_wrong_title_switch_5.jsonl`로 추출했다.
  - [x] `expert_main.py` targeted rerun을 `--slang-db off --reuse-shards-only --parallel 5 --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
  - [x] Runtime completed/flushed/pending/failed `5/5/0/0`, failed `0`, VLM/OCR `READY`.
  - [x] Loop49 wrong-after title reproduced `0`.
  - [x] Row outcomes: `RECOVERED_BEFORE_TITLE=3`, `RECOVERED_VARIANT_NEEDS_CANONICALIZATION_REVIEW=1`, `DEMOTED_TO_NULL=1`.
  - [x] Review artifact `loop64_p0e_wrong_title_switch_targeted_rerun.md/json`과 Loop64 report를 추가했다.
  - [x] Data Analytics artifact `Loop64 P0E Wrong Title Switch Targeted Rerun` validate/render PASS.
- 남은 작업:
  - [ ] `11666713` variant `21세기 무림` vs `21세기 무림세가`는 canonicalization caution으로 후속 확인한다.
  - [ ] P0E targeted review를 full-panel collateral approval로 승격하지 않는다.
  - [ ] 다음 concrete lane으로 `P0B_expected_mismatch_public_title=4` 또는 P0A restoration lanes를 진행한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 63 P0C slang pollution targeted rerun

- 상태: P0C targeted lane TARGETED_REVIEWED_7_OF_7 / row-level demoted 4 and verified 3 / full-panel collateral approval NO-GO / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop51 `P0C_slang_pollution_public_title=7` rows를 `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop63_p0c_slang_pollution_7.jsonl`로 추출했다.
  - [x] vLLM endpoint `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`를 확인했다.
  - [x] `expert_main.py` targeted rerun을 `--slang-db off --reuse-shards-only --parallel 7 --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
  - [x] Runtime completed/flushed/pending/failed `7/7/0/0`, failed `0`, VLM/OCR `READY`.
  - [x] Row outcomes: `DEMOTED_TO_NULL=4`, `VERIFIED_SAME_PUBLIC_TITLE=3`.
  - [x] Review artifact `loop63_p0c_slang_pollution_targeted_rerun.md/json`과 Loop63 report를 추가했다.
  - [x] Data Analytics artifact `Loop63 P0C Slang Pollution Targeted Rerun` validate/render PASS.
- 남은 작업:
  - [ ] P0C targeted lane closure를 full-panel collateral approval로 승격하지 않는다.
  - [x] `P0E_wrong_title_switch=5`는 Loop64에서 targeted rerun/review를 진행했다.
  - [ ] 다음 high-risk P0 lane으로 `P0B_expected_mismatch_public_title=4` 또는 P0A restoration lanes를 진행한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 62 full-panel collateral residual map

- 상태: residual map only / P0C targeted lane later reviewed by Loop63 / full-panel collateral approval NO-GO / source full completion OPEN / Loop10 slang write-back review CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop50 full-panel collateral packet `183` candidates를 재확인했다.
  - [x] Loop53-58 targeted recovery가 실제로 닫은 rows는 `7`개임을 확인했다.
  - [x] 남은 full-panel collateral backlog를 `176`으로 고정했다.
  - [x] 남은 priority split을 `P0=29`, `P1=77`, `P2=70`으로 기록했다.
  - [x] 남은 P0 bucket split을 기록했다: `P0A_expected_title_or_url_restoration=3`, `P0A_expected_title_restoration=3`, `P0B_expected_mismatch_public_title=4`, `P0C_slang_pollution_public_title=7`, `P0C_unexpected_public_title=3`, `P0D_title_variant_or_canonicalization=4`, `P0E_wrong_title_switch=5`.
  - [x] Residual map artifacts `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop62_full_panel_residual_map.md/json`를 추가했다.
  - [x] Loop report `docs/devs/loop_reports/LOOP_62_REPORT_20260629.md`를 추가했다.
  - [x] JSON parse PASS.
  - [x] Data Analytics artifact `Loop62 Full Panel Residual Map` validate PASS; render call은 실행됐으나 현재 컨텍스트에서 응답이 잘렸다.
- 남은 작업:
  - [ ] Loop62 residual map을 full-panel collateral approval로 승격하지 않는다.
  - [x] `P0C_slang_pollution_public_title=7`은 Loop63에서 targeted rerun/review를 진행했다.
  - [x] `P0E_wrong_title_switch=5`는 Loop64에서 targeted rerun/review를 진행했다.
  - [ ] 다음 concrete lane으로 `P0B_expected_mismatch_public_title=4` 또는 P0A restoration lanes를 진행한다.
  - [ ] Source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] Full-panel collateral approval은 계속 `NO-GO`로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 61 slang write-back review

- 상태: Loop 10 slang write-back review CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK / production slang DB write-back NOT_APPROVED / source full completion OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop10 result/manifest/compare/next-queue artifacts를 재감사했다.
  - [x] Runtime completed/flushed/pending/failed `92/92/0/0`, compare `review=92`, targeted next queue `0`를 확인했다.
  - [x] Input manifest policy `off/read-only canary; no production write-back`를 확인했다.
  - [x] Slang signal split을 재계산했다: `store_true=29`, `store_false=31`, no `slang_insight=32`.
  - [x] Store-true rows는 `decode_verified=false 0`, `resolved=27`, `unresolved_matchable=2`임을 확인했다.
  - [x] Unresolved store-true rows `11700500`(`전1시`), `11710043`(`악엔`)을 별도 hold로 기록했다.
  - [x] `19` unique store-true terms가 모두 `slang_db/slang_db.json`에 이미 존재하며, `6` terms가 multi-title/bucket임을 확인했다.
  - [x] `slang_db/slang_db.json`은 git status에서 수정되지 않았다.
  - [x] Data Analytics report `Loop61 Slang Writeback Review Gate` validate/render PASS.
- 남은 작업:
  - [ ] queue `0`을 slang DB approval 또는 semantic approval로 승격하지 않는다.
  - [ ] source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 60 failed-row targeted rerun

- 상태: failed row `11694057` targeted rerun PASS / source full completion OPEN / full-panel collateral approval NO-GO / Loop 10 slang write-back review CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK_BY_LOOP61 / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] prior checkpoint/source evidence에서 `11694057` 원문 입력을 `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop59_failed_row_11694057.jsonl`로 재구성했다.
  - [x] vLLM `/v1/models`에서 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4` endpoint를 확인했다.
  - [x] `expert_main.py` targeted canary를 `--slang-db off --reuse-shards-only --parallel 1 --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
  - [x] Manifest `loop59_failed_row_11694057_result_manifest.json` runtime completed/flushed/pending/failed `1/1/0/0`, failed `0`.
  - [x] Final row `11694057`은 `official_title=괴담에 휘말렸다`, `work_resolution=resolved`, `discussion_type=character_talk`.
  - [x] Data Analytics report `Loop60 Failed Row Targeted Rerun Gate` validate/render PASS.
- 남은 작업:
  - [ ] source manifest input scope `104502`와 `large_run_complete=false` 때문에 source full completion은 계속 `OPEN`으로 유지한다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [x] Loop 10 slang write-back review는 Loop61에서 `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK`으로 닫았다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 59 source integrity recovery

- 상태: source checkpoint recovery PARTIAL_PROGRESS / pending flush gap recovered to separate artifact / failed row `11694057` CLOSED_BY_LOOP60_TARGETED_RERUN / source full completion OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] `out/expert_result_20260626_000008_928006_manifest.json` 기준 source counts를 재검산했다: input `104502`, final flushed `1933`, pending `13`, failed `1`, large_run_complete `false`.
  - [x] checkpoint를 집계했다: completed `1945`, failed `1`.
  - [x] `tools/recover_expert_run_from_checkpoint.py`로 recovered output `out/expert_result_20260626_000008_928006_recovered_from_checkpoint.json` rows `1945`와 recovery summary를 생성했다.
  - [x] pending snapshot rows `13`은 recovered output에 포함됐다.
  - [x] failed placeholder `11694057`는 recovered output에서 제외했다.
  - [x] `src/llm_batch/llm/client.py`에 lone surrogate HTTP JSON transport guard를 추가했다.
  - [x] `tests/test_llm_client_multimodal.py`에 surrogate replacement 및 sanitized HTTP body tests를 추가했다.
  - [x] `py_compile` PASS, focused surrogate transport `2 tests OK`, `tests.test_llm_client_multimodal` `16 tests OK`.
  - [x] Review packet `loop59_source_integrity_recovery.md/json` and Loop 59 report were added.
  - [x] Data Analytics report `Loop59 Source Integrity Recovery Gate` was validate/render PASS.
- 남은 작업:
  - [x] original input/source row for `11694057`를 찾아 targeted rerun을 실행했다(Loop60).
  - [ ] recovered checkpoint output을 full-source completion 또는 approval로 승격하지 않는다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 58 direct expected surface over homonym fix

- 상태: code hook implemented / unit verification PASS / `direct_expected_surface_over_homonym=2` targeted row-level GO in final and repeat canaries / Loop53 concrete expected-recovery targeted lanes `7_OF_7` closed / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop53 `direct_expected_surface_over_homonym=2` input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop58_direct_expected_surface_over_homonym_2.jsonl`로 targeted canary를 실행했다.
  - [x] Final result `loop58_direct_expected_surface_over_homonym_2_after_sixth_patch_result.json`은 runtime completed/flushed/pending/failed `2/2/0/0`, VLM/OCR ready.
  - [x] Repeat result `loop58_direct_expected_surface_over_homonym_2_after_sixth_patch_repeat_result.json`도 runtime completed/flushed/pending/failed `2/2/0/0`, VLM/OCR ready.
  - [x] `11674703` final `official_title=도굴왕`, URL `null`, `candidate_ledger_status=safe_resolved`.
  - [x] `11703657` final `official_title=야만인은 문명하면 안되냐`, URL `https://novelpia.com/novel/405310`, `candidate_ledger_status=safe_resolved`.
  - [x] Direct comment URL answer preservation, weak surface/search title replacement, official-detail URL restoration, decoder-exact post-title surface preservation tests were added.
  - [x] `py_compile` PASS, focused AgenticPipelineRework `11 tests OK`, focused title-lead `3 tests OK`, `tests.test_final_semantic_reread_gate` `18 tests OK`.
  - [x] Review packet `loop58_direct_expected_surface_over_homonym_fix.md/json` and Loop 58 report were added.
  - [x] Data Analytics report `Loop58 Direct URL Surface Homonym Gate` was validate/render PASS.
- 남은 작업:
  - [ ] Loop53 targeted lane closure를 full-panel collateral approval 또는 full-scan approval로 승격하지 않는다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 57 primary expected candidate precedence fix

- 상태: code hook implemented / unit verification PASS / `primary_expected_candidate_precedence=2` targeted row-level GO / `direct_expected_surface_over_homonym=2` OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop53 `primary_expected_candidate_precedence=2` input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop57_primary_expected_precedence_2.jsonl`로 VLM/OCR targeted canary를 실행했다.
  - [x] Final result `loop57_primary_expected_precedence_2_after_second_patch_result.json`은 runtime completed/flushed/pending/failed `2/2/0/0`, VLM/OCR ready.
  - [x] `11658637` final `official_title=재벌집 막내아들`, URL `https://novel.munpia.com/69583`, `candidate_ledger_status=safe_resolved`.
  - [x] `11677913` final `official_title=이세계 검은 머리 외국인`, URL `https://novelpia.com/novel/1082`, `candidate_ledger_status=safe_resolved`.
  - [x] Primary/reference-role precedence, direct OCR/work-cue official probe preservation, official-detail title canonicalization, verified-alias bridge guards, and author/volume wrapper blocking tests were added.
  - [x] `py_compile` PASS, `tests.test_final_semantic_reread_gate` `18 tests OK`, `tests.test_candidate_audit` `64 tests OK`, `tests.test_title_lead_search_inferred_guard` `126 tests OK`.
  - [x] Review packet `loop57_primary_expected_precedence_fix.md/json` and Loop 57 report were added.
  - [x] Data Analytics report `Loop57 Primary Expected Candidate Precedence Fix` was validate/render PASS.
- 남은 작업:
  - [ ] `primary_expected_candidate_precedence=2` targeted recovery를 full-panel collateral approval 또는 full-scan approval로 승격하지 않는다.
  - [ ] Loop53 `direct_expected_surface_over_homonym=2` lane은 아직 open이다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-29 regression-safe grounding Loop 56 ratddasip visual alias catalog fix

- 상태: code hook implemented / unit verification PASS / `11673086` targeted row-level GO / expected-source lane targeted 3_OF_3 recovered / broader Loop53 lanes OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] `11673086` 단일 input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop56_ratddasip_11673086_1.jsonl`로 VLM/OCR targeted canary를 반복 실행했다.
  - [x] Visual alias official-detail bridge를 `[림월드]...` bracket cue와 packet visual evidence가 같이 있을 때만 허용하도록 좁혔다.
  - [x] Same-tag `#랫따싶` competitor보다 visual bracket alias candidate가 우선되도록 catalog scoring에 `visual_bracket_context` anchor를 추가했다.
  - [x] Final result `loop56_ratddasip_11673086_after_catalog_fix_result.json`은 runtime completed/flushed/pending/failed `1/1/0/0`, VLM/OCR ready.
  - [x] `11673086` final `official_title=변방계에서 회귀자로 살아남기`, URL `https://novelpia.com/novel/382324`, `candidate_ledger_status=safe_resolved`, `title_resolution_allowed=true`로 row-level `GO`.
  - [x] `tests.test_title_lead_search_inferred_guard` `119 tests OK`, `tests.test_candidate_audit` `64 tests OK`, `tests.test_known_title_abbreviation_support` `20 tests OK`, `py_compile` PASS.
  - [x] Review packet `loop56_ratddasip_visual_alias_catalog_fix.md/json`과 Loop 56 report를 추가했다.
  - [x] Data Analytics report `Loop56 Ratddasip Visual Alias Catalog Fix`를 validate/render했다.
- 남은 작업:
  - [ ] `11673086` 회복을 full-panel collateral approval 또는 full-scan approval로 승격하지 않는다.
  - [ ] Loop53 `primary_expected_candidate_precedence=2`, `direct_expected_surface_over_homonym=2` lanes는 아직 unchanged/open이다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 55 expected-source remaining canary

- 상태: VLM/OCR targeted canary PASS / `11671501` row-level GO / `11673086` promotion_blocked OPEN / expected-source lane PARTIAL_GO_2_OF_3 / broader Loop53 lanes OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] Loop53 `expected_source_recall_missing_or_demoted` 잔여 2건을 `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop55_expected_source_remaining_2.jsonl`로 실행했다.
  - [x] `loop55_expected_source_remaining_2_result.json` runtime completed/flushed/pending/failed `2/2/0/0`, VLM/OCR ready, image posts `2`.
  - [x] `11671501`은 final `official_title=판초우의의 마법사`, URL `https://novel.munpia.com/530500`, `candidate_ledger_status=safe_resolved`로 row-level `GO`.
  - [x] `11673086`은 expected candidate `변방계에서 회귀자로 살아남기`, URL `https://novelpia.com/novel/382324`를 보존했지만 final public title은 `null`, `candidate_ledger_status=promotion_blocked`로 `OPEN`.
  - [x] Review packet `loop55_expected_source_remaining_canary.md/json`과 Loop 55 report를 추가했다.
  - [x] Data Analytics report `Loop55 Expected-Source Remaining Canary`를 validate/render했다.
- 남은 작업:
  - [ ] `11671501` 회복을 full-panel collateral approval 또는 full-scan approval로 승격하지 않는다.
  - [ ] `11673086` `랫따싶` character/source bridge는 tag-only promotion 없이 계속 검토한다.
  - [ ] Loop53 `primary_expected_candidate_precedence=2`, `direct_expected_surface_over_homonym=2` lanes는 아직 unchanged/open이다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 54 alias-abbreviation recall fix

- 상태: code hook implemented / unit verification PASS / targeted canary `11668324` recovered GO / follow-up Loop55 recovered `11671501` / `11673086` OPEN / broader Loop53 lane OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal ACTIVE NOT_COMPLETE
- 완료:
  - [x] `src/llm_batch/agentic_pipeline.py`에 compact alias abbreviation predicate를 추가했다.
  - [x] `title_alias_platform_recall` 검색어 생성에서 `니생들이랑 -> 니생들`처럼 한국어 조사/연결어 stem을 먼저 시도한다.
  - [x] alias-only official-detail result는 official title abbreviation 형태로 설명될 때만 promotion되도록 제한했다.
  - [x] `src/llm_batch/experts/utils.py`의 `KNOWN_TITLE_ABBREVIATIONS`에 `니생들 -> 니들 생각 다 들린다`를 추가했다.
  - [x] known-abbreviation official URL recall이 post title/body의 leftmost alias occurrence를 우선하도록 했다.
  - [x] update-question/lifecycle anchor를 `언급`, `장갤픽`, 작품 출시/연재/완결/시간 계열로 좁혀 broad `작품` token 단독 승격을 피했다.
  - [x] `랫따싶` tag-only collision negative test를 추가해 공유 tag만으로 promotion되지 않게 고정했다.
  - [x] Data Analytics reports `Loop54 Alias-Abbreviation Recall Fix`, `Loop54 Alias-Abbreviation Canary Gate`, `Loop54b Known-Abbreviation Canary Recovery`를 validate/render했다.
  - [x] Loop 54 report를 `docs/devs/loop_reports/LOOP_54_REPORT_20260628.md`에 추가했다.
  - [x] 첫 `11668324` single-row targeted canary를 실행했다: runtime completed/flushed/pending/failed `1/1/0/0`, semantic `NO-GO`로 expected `니들 생각 다 들린다`, actual `괴담에 휘말렸다` via `김괴라리`를 기록했다.
  - [x] follow-up fix 후 `loop54b_known_abbrev_11668324_result.json` targeted canary를 재실행했다: runtime completed/flushed/pending/failed `1/1/0/0`.
  - [x] second canary row-level `GO`를 기록했다: final `official_title=니들 생각 다 들린다`, URL `https://novelpia.com/novel/384318`, alias `니생들`, `candidate_ledger_status=safe_resolved`, search health `SEARCH_DEGRADED`.
- 남은 작업:
  - [ ] `11668324` targeted canary 회복을 full-panel collateral approval 또는 full-scan approval로 승격하지 않는다.
  - [x] `11671501` `판초법사 -> 판초우의의 마법사` materialization은 Loop55 targeted canary에서 row-level `GO`로 확인했다.
  - [ ] `11673086` `랫따싶` character/source bridge는 tag-only promotion 없이 별도 검토한다.
  - [ ] Loop53 `primary_expected_candidate_precedence=2`, `direct_expected_surface_over_homonym=2` lanes는 아직 unchanged/open이다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 53 P0B concrete expected-recovery packet

- 상태: code-review lane routing DONE / follow-up Loop54b recovered `11668324` / remaining packet rows OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop52 `BLOCK_WRONG_AFTER_RECOVER_EXPECTED=7` rows를 code-review lane으로 분리했다.
  - [x] Packet 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop53_p0b_concrete_expected_recovery_packet.md/json`.
  - [x] Requeue 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop53_p0b_concrete_expected_recovery_requeue.md/json`.
  - [x] Candidate input 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop53_p0b_concrete_expected_recovery_7.jsonl`, rows `7`, missing `0`.
  - [x] Fix lane split 확인: `expected_source_recall_missing_or_demoted=3`, `primary_expected_candidate_precedence=2`, `direct_expected_surface_over_homonym=2`.
  - [x] Data Analytics report `Loop53 P0B Concrete Expected-Recovery Packet`를 validate/render했다.
  - [x] Loop 53 report를 `docs/devs/loop_reports/LOOP_53_REPORT_20260628.md`에 추가했다.
- 남은 작업:
  - [x] `expected_source_recall_missing_or_demoted=3` lane의 첫 code hook은 Loop54에서 `니생들`형 alias-abbreviation recall fix로 처리했다.
  - [x] `11668324`는 Loop54b targeted canary에서 `니들 생각 다 들린다`로 회복됐다.
  - [x] `11671501`은 Loop55 targeted canary에서 `판초우의의 마법사`로 회복됐다.
  - [ ] `expected_source_recall_missing_or_demoted=3` lane의 잔여 `11673086` targeted follow-up은 아직 open이다.
  - [ ] 잔여 `랫따싶` evidence path를 검토한다.
  - [ ] `primary_expected_candidate_precedence=2` lane의 primary/reference_role 후보 우선순위와 final identity sync를 검토한다.
  - [ ] `direct_expected_surface_over_homonym=2` lane의 direct post title/comment URL anchor가 homonym official-detail 후보를 차단하는지 검토한다.
  - [ ] remaining Loop53 packet rows는 code fix 후 targeted canary/recompare를 실행하기 전까지 row-level resolution `OPEN`으로 유지한다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 52 P0B expected-mismatch disposition

- 상태: P0B disposition routing DONE / row-level resolution OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall full approval NOT_GRANTED
- 완료:
  - [x] Loop51 `P0B_expected_mismatch_public_title=11` rows를 네 가지 처분군으로 재분류했다.
  - [x] Disposition 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop52_p0b_expected_mismatch_disposition.md/json`.
  - [x] Requeue 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop52_p0b_expected_mismatch_requeue.md/json`.
  - [x] Candidate input 확인: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop52_p0b_expected_mismatch_11.jsonl`, rows `11`, missing `0`.
  - [x] Disposition split 확인: `BLOCK_WRONG_AFTER_RECOVER_EXPECTED=7`, `BLOCK_WRONG_AFTER_PRESERVE_HYPOTHESIS=2`, `SECONDARY_REFERENCE_HOLD=1`, `EXPECTED_URL_PRESERVED_TITLE_SURFACE_REPAIR=1`.
  - [x] Data Analytics report `Loop52 P0B Expected-Mismatch Disposition`를 validate/render했다.
  - [x] Loop 52 report를 `docs/devs/loop_reports/LOOP_52_REPORT_20260628.md`에 추가했다.
- 남은 작업:
  - [x] `BLOCK_WRONG_AFTER_RECOVER_EXPECTED=7` rows의 code-review lane routing은 Loop53에서 분리했다.
  - [ ] Loop53 code fix/targeted canary 전까지 wrong after-title 차단과 expected title/source 회수 여부는 unresolved로 둔다.
  - [ ] `BLOCK_WRONG_AFTER_PRESERVE_HYPOTHESIS=2` rows는 unresolved hypothesis로 보존하고 web/source 검증 전 forced recovery로 승격하지 않는다.
  - [ ] `SECONDARY_REFERENCE_HOLD=1` row는 direct work bridge 확인 전까지 expected title recovery로 처리하지 않는다.
  - [ ] Loop49 field consistency risk를 닫는다: `identity.official_title=null`인데 compare after surface가 resolved처럼 보이는 상태를 승인 근거로 쓰지 않는다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 51 P0 collateral triage

- 상태: P0 triage DONE / P0 row-level resolution OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall full approval NOT_GRANTED
- 완료:
  - [x] Loop50 P0 `36` rows를 triage bucket으로 분리했다.
  - [x] Triage 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop51_p0_panel_collateral_triage.md/json`.
  - [x] Requeue 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop51_p0_panel_collateral_requeue.md/json`.
  - [x] Candidate input 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop51_p0_panel_collateral_36.jsonl`, rows `36`, missing `0`.
  - [x] Data Analytics report `Loop51 P0 Panel Collateral Triage`를 validate/render했다.
  - [x] Loop 51 report를 `docs/devs/loop_reports/LOOP_51_REPORT_20260628.md`에 추가했다.
- 남은 작업:
  - [x] `P0B_expected_mismatch_public_title=11`의 disposition routing은 Loop52에서 분리했다.
  - [ ] Loop52 P0B row-level resolution/code fix는 아직 open이다.
  - [ ] `P0E_wrong_title_switch=5`를 code/rule review 후보로 분리한다.
  - [ ] `P0D_title_variant_or_canonicalization=4`는 canonical/source 확인 전까지 hard failure로 확정하지 않는다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 50 panel collateral packet

- 상태: Loop49 collateral candidates packetized / requeue surface DONE / P0 review OPEN / full-panel collateral approval NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall full approval NOT_GRANTED
- 완료:
  - [x] Loop49 collateral regression candidates `183`을 review packet으로 구조화했다.
  - [x] Packet 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop50_panel_collateral_candidate_packet.md/json`.
  - [x] Requeue 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop50_panel_collateral_requeue.md/json`.
  - [x] Candidate input 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop50_panel_collateral_regression_candidates_183.jsonl`, rows `183`, missing `0`.
  - [x] Data Analytics report `Loop50 Panel Collateral Candidate Packet`을 validate/render했다.
  - [x] Loop 50 report를 `docs/devs/loop_reports/LOOP_50_REPORT_20260628.md`에 추가했다.
- 남은 작업:
  - [ ] P0 `36` rows를 row-level expected-answer/HOLD/code-fix/no-generalizable-fix로 분리한다.
  - [ ] P1 `77`, P2 `70` rows도 approval 전 row-level rationale이 필요하다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 49 panel replay review

- 상태: panel replay runtime PASS / full-panel collateral approval NO-GO / source full completion OPEN / Loop 10 slang write-back review OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall full approval NOT_GRANTED
- 완료:
  - [x] Regression panel replay 완료: completed/flushed/pending/failed `375/375/0/0`, `large_run_complete=true`.
  - [x] VLM/OCR semantic gate `READY`, image posts `241`, `slang_db=off`, requested/effective parallel `36/16`을 로그/manifest로 확인했다.
  - [x] Result/manifest/log 확인: `loop49_regression_panel_replay_result.json`, `loop49_regression_panel_replay_result_manifest.json`, `loop49_regression_panel_replay_run_20260628.log`.
  - [x] Full-panel collateral compare 생성: `loop49_regression_panel_replay_collateral_compare.md/json`.
  - [x] Data Analytics report `Loop49 Regression Panel Replay Review`를 validate/render했다.
  - [x] Loop 49 report를 `docs/devs/loop_reports/LOOP_49_REPORT_20260628.md`에 추가했다.
- 남은 작업:
  - [ ] Collateral regression candidates `183`을 review/requeue packet으로 분리한다.
  - [ ] full-panel collateral approval은 `NO-GO`로 유지한다.
  - [ ] source full completion gap `13` pending + `1` failed를 닫는다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 48 collateral candidate review

- 상태: Loop47 collateral candidates row-level review DONE / code change NOT_RUN / full-panel collateral approval OPEN / source full completion OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall full approval NOT_GRANTED
- 완료:
  - [x] Loop47 collateral regression candidates `5`를 Loop47 golden audit expected-answer status와 대조했다.
  - [x] Review artifact 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop48_collateral_candidate_review.md/json`.
  - [x] Data Analytics report `Loop 48 Collateral Candidate Review`를 validate/render했다.
  - [x] Loop 48 report를 `docs/devs/loop_reports/LOOP_48_REPORT_20260628.md`에 추가했다.
- 남은 작업:
  - [ ] panel replay가 남아 있다.
  - [ ] source full completion이 남아 있다.
  - [ ] Loop 10 slang write-back review가 남아 있다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 47 merged golden pass

- 상태: Loop47 merged golden semantic gate PASS / golden runtime PASS / Loop48 collateral candidate review DONE / full-panel collateral approval OPEN / semantic quality REVIEW-LOCKED / full scan approval false / overall full approval NOT_GRANTED
- 완료:
  - [x] Loop45 failed rows `11663521`, `11663540`, `11700470` 전용 Loop46 input을 생성했다.
  - [x] Loop46 targeted rerun 완료: `loop46_failed3_after_work_cue_fanfic_ocr_result.json`, completed/flushed/pending/failed `3/3/0/0`, VLM/OCR `READY`.
  - [x] Loop47 merge 생성: `loop47_merged_loop45_loop46_golden_result.json`, `loop47_merged_loop45_loop46_golden_result_manifest.json`, `loop47_merged_loop45_loop46_sources.json`.
  - [x] Loop47 golden audit 생성: `loop47_merged_loop45_loop46_golden_audit.md/json`, pass `16/16`, fail `0`, `canary_semantic_gate=PASS`.
  - [x] Loop47 collateral compare 생성: `loop47_merged_loop45_loop46_golden_collateral_compare.md/json`, collateral regression candidates `5`.
  - [x] broad affected suite `660 tests OK`.
  - [x] Data Analytics report `Loop 47 Golden Gate Status`를 validate/render했다.
  - [x] Loop 47 report를 `docs/devs/loop_reports/LOOP_47_REPORT_20260628.md`에 추가했다.
- 남은 작업:
  - [x] collateral regression candidates `5`를 별도 검토했다: `loop48_collateral_candidate_review.md/json`.
  - [ ] panel replay, source full completion, Loop 10 slang write-back review가 남아 있다.
  - [ ] golden semantic PASS를 full-scan approval로 승격하지 않는다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 유지.

## 2026-06-28 regression-safe grounding Loop 17 locked-official character sentence-alias guard

- 상태: targeted `11700470` prior wrong-title blocker PARTIAL / single-row canary PASS for blocking `도깨비가 되었다.` / golden runtime PASS / golden semantic NO-GO / collateral semantic NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] clean official detail evidence가 unresolved character sentence-like alias risk를 무조건 우회하지 못하도록 `src/llm_batch/agentic_pipeline.py`의 `_locked_official_candidate_has_unresolved_alias_risk(...)`를 보강했다.
  - [x] `tests/test_agentic_pipeline_rework.py`에 `11700470`형 `밤도깨비 에이브` → `도깨비가 되었다.` 오승격 회귀 테스트를 추가했다.
  - [x] focused/unit 재검증: targeted 3 tests `OK`, `tests.test_agentic_pipeline_rework` `451 tests OK`, title-lead guard `114 tests OK`, `py_compile` pass.
  - [x] single-row canary 완료: `loop17_locked_official_character_sentence_alias_11700470_result.json`, completed/flushed/pending/failed `1/1/0/0`, exit `0`, VLM/OCR `READY`, public title `None`.
  - [x] golden replay 완료: `loop17_locked_official_character_sentence_alias_golden_result.json`, completed/flushed/pending/failed `16/16/0/0`, exit `0`, VLM/OCR `READY`.
  - [x] golden audit 생성: `loop17_locked_official_character_sentence_alias_golden_audit.md/json`, pass `10/16`, fail `6`, `canary_semantic_gate=NO-GO`.
  - [x] collateral compare 생성: `loop17_locked_official_character_sentence_alias_golden_collateral_compare.md/json`, collateral regression candidates `6`.
  - [x] Data Analytics artifact `Loop 17 Golden Gate Status`를 validate/render했다.
  - [x] Loop 17 report 추가: `docs/devs/loop_reports/LOOP_17_REPORT_20260628.md`.
- 남은 작업:
  - [ ] `11700470`은 `도깨비가 되었다.`가 아니라 `바람과 별무리`로 여전히 wrong-title이다. expected `악당 얼굴의 B급 모험자` 회수를 위한 next blocker로 유지한다.
  - [ ] `11713222`도 expected `잘생기면 인생이 편하다` 대신 `잘생기면 편해지는 인방 생활` wrong-title로 남았다.
  - [ ] positive unresolved `11663521`, `11685994`, `11694019`, `11705231`을 recall/source-bridge 원인별로 재분리한다.
  - [ ] panel replay, source full completion, Loop 10 slang write-back review가 남아 있어 overall goal은 완료 처리하지 않는다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 16 short-lead confirmed-alias guard

- 상태: targeted `11705245` precision blocker CLOSED / golden runtime PASS / golden semantic NO-GO / collateral semantic NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] `confirmed_alias`/`explicit_alias_official_work_lock`가 official title의 짧은 leading stem alias만으로 weak public-title bridge guard를 우회하지 못하도록 `src/llm_batch/candidate_audit.py`를 보강했다.
  - [x] `tests/test_candidate_audit.py`에 short-lead confirmed stem alias hold와 weak-alias confirmed stem alias hold 회귀 테스트를 추가했다.
  - [x] focused/unit/full 재검증: `tests.test_candidate_audit` `64 tests OK`, title-lead guard `114 tests OK`, full unittest sweep `1165 tests OK`, `py_compile` pass.
  - [x] single-row canary 완료: `loop16_short_lead_confirmed_alias_11705245_result.json`, completed/flushed/pending/failed `1/1/0/0`, exit `0`, VLM/OCR `READY`, public title `None`.
  - [x] golden replay 완료: `loop16_short_lead_confirmed_alias_golden_result.json`, completed `16/16`, exit `0`, VLM/OCR `READY`.
  - [x] golden audit 생성: `loop16_short_lead_confirmed_alias_golden_audit.md/json`, pass `11/16`, fail `5`, `canary_semantic_gate=NO-GO`.
  - [x] collateral compare 생성: `loop16_short_lead_confirmed_alias_golden_collateral_compare.md/json`, collateral regression candidates `5`.
  - [x] Data Analytics artifact `Loop 16 Golden Gate Status`를 validate/render했다.
  - [x] Loop 16 report 추가: `docs/devs/loop_reports/LOOP_16_REPORT_20260628.md`.
- 남은 작업:
  - [x] `11700470` wrong title `도깨비가 되었다.`는 Loop 17 단일 canary에서 차단했다.
  - [ ] Loop 17 golden 기준 `11700470`은 expected `악당 얼굴의 B급 모험자` 대신 `바람과 별무리` wrong-title로 남아 있다.
  - [ ] positive failures `11663521`, `11685994`, `11694019`, `11700470`, `11705231`, `11713222`를 unresolved/wrong-title 원인별로 재분리한다.
  - [ ] panel replay, source full completion, Loop 10 slang write-back review가 남아 있어 overall goal은 완료 처리하지 않는다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 15 known-title anchor guard

- 상태: targeted `11694035` precision blocker CLOSED / golden runtime PASS / golden semantic NO-GO / collateral semantic NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] `KNOWN_TITLE_ABBREVIATIONS` prefix-only alias + official detail URL이 packet-local work cue/direct anchor 없이 public title hard-lock/rescue가 되지 않도록 `src/llm_batch/agentic_pipeline.py`를 보강했다.
  - [x] `tests/test_known_title_abbreviation_support.py`에 `11694035`형 prefix-only known-title abbreviation regression test를 추가했다.
  - [x] focused/unit/full sweep 재검증: known-title support `19 tests OK`, title-lead guard `114 tests OK`, agentic pipeline rework `450 tests OK`, full unittest sweep `1163 tests OK`, `py_compile` pass.
  - [x] single-row canary 완료: `loop15_known_title_anchor_11694035_result.json`, completed/flushed/pending/failed `1/1/0/0`, exit `0`, VLM/OCR `READY`, public title `None`.
  - [x] golden replay 완료: `loop15_known_title_anchor_golden_result.json`, completed `16/16`, exit `0`, VLM/OCR `READY`.
  - [x] golden audit 생성: `loop15_known_title_anchor_golden_audit.md/json`, pass `10/16`, fail `6`, `canary_semantic_gate=NO-GO`.
  - [x] collateral compare 생성: `loop15_known_title_anchor_golden_collateral_compare.md/json`, collateral regression candidates `5`.
  - [x] Data Analytics artifact `Loop 15 Known-Title Anchor Gate`를 validate/render했다.
  - [x] Loop 15 report 추가: `docs/devs/loop_reports/LOOP_15_REPORT_20260628.md`.
- 남은 작업:
  - [ ] `11705245` negative no-public-work unexpected title `하남자의 탑 공략법`을 다음 precision blocker로 분리한다.
  - [ ] positive failures `11663521`, `11685994`, `11700470`, `11705231`, `11713222`를 unresolved/wrong-title 원인별로 재분리한다.
  - [ ] Loop 15 golden replay는 recall-metadata 미세 보정 직전 시작된 run이므로, acceptance가 필요하면 current-code full golden replay를 다시 돌린다.
  - [ ] panel replay, source full completion, Loop 10 slang write-back review가 남아 있어 overall goal은 완료 처리하지 않는다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 14 golden replay continuation

- 상태: golden runtime `PASS` / golden semantic `NO-GO` / collateral semantic `NO-GO` / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] vLLM endpoint와 golden input/tool 존재를 확인한 뒤 `loop14_golden_after_fix_result.json` canary를 실행했다.
  - [x] runtime 완료: completed/flushed/pending/failed `16/16/0/0`, exit `0`, VLM/OCR semantic gate `READY`, `large_run_complete=true`, `slang_db=off`.
  - [x] golden audit 생성: `loop14_golden_after_fix_audit.md/json`, pass `10/16`, fail `6`, `canary_semantic_gate=NO-GO`.
  - [x] collateral compare 생성: `loop14_golden_after_fix_collateral_compare.md/json`, regression candidates `6`.
  - [x] Data Analytics artifact `Loop 14 Golden Gate Status`를 validate/render했다.
- 남은 작업:
  - [ ] `11694035` negative no-public-work 과승격(`아카데미 생존 갤러리`)을 막아야 한다.
  - [ ] positive expected-work unresolved 5건(`#11663521`, `#11663540`, `#11685994`, `#11700470`, `#11713222`)을 원인별로 재분리한다.
  - [ ] panel replay, source full completion, Loop 10 slang write-back review가 남아 있어 overall goal은 완료 처리하지 않는다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 13 completion recheck

- 상태: goal tool `active` / corrected full unittest sweep `FAIL` / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] pasted goal 원문을 재확인했다. 정지 조건은 next queue 비움 또는 모든 잔여 row의 HOLD/human_review/INFO_MISSING/unresolved/quarantine/no_generalizable_fix_left row-level rationale다.
  - [x] Codex goal tool 상태를 확인했다: objective `Loop 06 regression-safe grounding goal completion 재점검`, status `active`.
  - [x] 기존 `unittest discover -s tests` 실패 로그를 회수했다: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop13_full_unittest_sweep_20260628.log`, `1093 tests`, `failures=9`, `errors=5`.
  - [x] `-s tests`가 `expert_main.py --server-type/-s`와 충돌하는 import/discovery 오류를 분리했다.
  - [x] import 충돌 관련 직접 테스트 로그를 남겼다: `loop13_expert_import_direct_73_20260628.log`, `73 tests OK`, exit `0`.
  - [x] `agentic_pipeline_rework` 직접 재현 로그를 남겼다: `loop13_agentic_pipeline_rework_direct_20260628.log`, `450 tests`, `failures=9`, `errors=1`, exit `1`.
  - [x] 긴 옵션 full sweep을 다시 실행했다: `loop13_full_unittest_sweep_long_options_20260628.log`, `1162 tests`, `failures=9`, `errors=1`, exit `1`.
  - [x] Data Analytics artifact `Loop 13 Full-Sweep Gate Audit`를 validate하고 render를 호출했다.
  - [x] Loop 13 gate report 추가: `docs/devs/loop_reports/LOOP_13_REPORT_20260628.md`.
- 남은 작업:
  - [ ] full unittest sweep gate는 `FAIL`이다. `tests.test_agentic_pipeline_rework` 실패 `9`건과 error `1`건을 수정/분리하기 전까지 goal 완료 금지.
  - [ ] panel/golden/collateral replay를 아직 다시 돌리지 않았다.
  - [ ] source full completion과 Loop 10 slang write-back review가 남아 있어 overall goal은 완료 처리하지 않는다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 14 full-sweep recovery

- 상태: affected suite `PASS` / corrected full unittest sweep `PASS` / golden continuation은 위 항목 기준 runtime PASS + semantic NO-GO / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] Loop 13의 `tests.test_agentic_pipeline_rework` failure `9` + error `1`을 공통 결합면별로 수정했다.
  - [x] `src/llm_batch/agentic_pipeline.py`에서 direct image work surface, batch alias/support cheer, stable alias, locked official rescue, derivative/non-novel filtering, direct full-title rescue, final semantic reread, relation hold release, final identity sync를 보강했다.
  - [x] Loop 13 원 실패 10개 checks를 재실행해 모두 `OK`로 닫았다.
  - [x] affected suite 재검증: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop14_agentic_pipeline_rework_after_fix_20260628.log`, `450 tests OK`, exit `0`.
  - [x] corrected full sweep 재검증: `loop14_full_unittest_sweep_after_fix_20260628.log`, `1162 tests OK`, exit `0`.
  - [x] `py_compile` pass: `src\llm_batch\agentic_pipeline.py`.
  - [x] Data Analytics artifact `Loop 14 Regression-Safe Grounding Gate Update`를 validate/render했다.
  - [x] Loop 14 report 추가: `docs/devs/loop_reports/LOOP_14_REPORT_20260628.md`.
- 남은 작업:
  - [ ] 이번 회차는 unittest gate recovery다. golden canary는 이후 continuation에서 runtime PASS였지만 semantic/collateral은 `NO-GO`이고, panel replay는 아직 open이다.
  - [ ] source full completion과 Loop 10 slang write-back review가 남아 있어 overall goal은 완료 처리하지 않는다.
  - [ ] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 12 author-angle residual closure

- 상태: Loop 09 residual `11682791` targeted closure complete / compare `review=1` / targeted next queue `0` / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] `src/llm_batch/candidate_audit.py`에 author-prefixed angle surface canonicalization helper를 추가했다.
  - [x] `expert_main.py` postprocess에서 official-title promotion guard 전에 canonicalization을 호출하도록 연결했다.
  - [x] stale reason/reason_lines가 `피아조아 <시간을 달리는 소설가>`를 계속 말하지 않도록 reason 정합성 보정을 추가했다.
  - [x] regression test 추가: `tests.test_candidate_audit.CandidateAuditTest.test_author_angle_search_surface_uses_matching_official_detail_candidate`.
  - [x] focused verification 통과: py_compile pass, targeted unit pass, `tests.test_candidate_audit -v` `62 tests OK`.
  - [x] single-row canary 완료: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop12_author_angle_11682791_result.json`, run_id `20260628_025822_229151`, completed/flushed/pending/failed `1/1/0/0`.
  - [x] compare/next queue 생성: `loop12_author_angle_11682791_compare.md`, `loop12_author_angle_11682791_next_queue.md`; targeted next queue rows `0`.
  - [x] closure artifact 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop12_author_angle_11682791_closure.json`, status `TARGETED_RESIDUAL_CLOSED`.
  - [x] Data Analytics artifact 검증/렌더 호출: `Loop 12 Author-Angle Residual Closure`.
  - [x] Loop 12 report 추가: `docs/devs/loop_reports/LOOP_12_REPORT_20260628.md`.
- 남은 작업:
  - [ ] Loop 12 next queue `0`은 단일 residual closure일 뿐이다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
  - [ ] panel/golden/collateral replay를 아직 다시 돌리지 않았다.
  - [ ] full unittest sweep은 Loop 13 보정 실행 기준 `1162 tests`, `failures=9`, `errors=1`로 실패했다.
  - [ ] source full completion과 Loop 10 slang write-back review가 남아 있어 overall goal은 완료 처리하지 않는다.

## 2026-06-28 regression-safe grounding Loop 11 human-review boundary closure

- 상태: Phase 2 `human_review_boundary=25` row-level closure documented / runnable canary not applicable / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] Phase 2 queue에서 `human_review_boundary=25`를 재확인했다. 모든 row는 `HOLD`, `boundary_needs_human`, `human_review`, `low`, `disagreement_type=none`이다.
  - [x] closure artifact 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop11_human_review_boundary_25_closure.json`.
  - [x] closure markdown 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop11_human_review_boundary_25_closure.md`.
  - [x] closure manifest 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop11_human_review_boundary_25_closure_manifest.json`.
  - [x] Data Analytics artifact 검증/렌더 호출: `Loop 11 Human Review Boundary Closure`.
  - [x] Loop 11 Korean report 추가: `docs/devs/loop_reports/LOOP_11_REPORT_20260628.md`.
- 남은 작업:
  - [ ] `human_review_boundary=25` closure는 semantic approval이 아니다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
  - [x] Loop 09 residual `11682791` source/page-title canonicalization은 Loop 12 targeted closure로 닫았다.
  - [ ] panel/golden/collateral replay, full unittest sweep, source full completion gate가 남아 있어 overall goal은 완료 처리하지 않는다.

## 2026-06-28 regression-safe grounding Loop 10 continuation

- 상태: Phase 2 `slang_store_gate=92` targeted canary runtime complete / compare `review=92` / targeted next queue `0` / semantic quality REVIEW-LOCKED / full scan approval false / overall goal NOT_COMPLETE
- 완료:
  - [x] Loop 10 input 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop10_slang_store_gate_92.jsonl`, manifest rows `92`, missing post ids `[]`.
  - [x] runtime canary 완료: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop10_slang_store_gate_92_result.json`, completed/flushed/pending/failed `92/92/0/0`, `large_run_complete=true`, VLM/OCR `READY`.
  - [x] requested/effective parallel `36/16`을 manifest 기준으로 확인했다. `reuse_shards_only` healthy endpoint filtering 때문에 실제 worker는 `16`이다.
  - [x] compare 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/compare/loop10_slang_store_gate_92_compare.md`, movement `review=92`.
  - [x] targeted next queue 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/compare/loop10_slang_store_gate_92_next_queue.md`, remaining rows `0`.
  - [x] Data Analytics artifact 렌더링: `Loop 10 Slang Store Gate Validation`.
  - [x] Loop 10 Korean report 추가: `docs/devs/loop_reports/LOOP_10_REPORT_20260628.md`.
- 남은 작업:
  - [ ] Loop 10 next queue `0`은 `slang_store_gate` runnable slice closure일 뿐이다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
  - [ ] `store_in_slang_db=true` `29`건은 review signal이며, `--slang-db off` 실행이므로 생산 DB write-back 승인으로 쓰지 않는다.
  - [ ] `human_review_boundary=25`는 runnable canary 대상이 아니라 explicit `HOLD`/`human_review` closure 후보로 문서화한다.
  - [x] Loop 09 residual `11682791`은 Loop 12 targeted author-angle closure로 닫았다.
  - [ ] panel/golden/collateral/replay/sweep, source-completion gate가 남아 있어 overall goal은 완료 처리하지 않는다.

## 2026-06-26 regression-safe grounding Phase 1 / Phase 2 start

- 상태: Phase 1 deterministic partial aggregate complete / Phase 2 initial queue created / FIX-0 baseline-panel-golden bootstrap complete / FIX-1 work-bridge unit+broad gate green / FIX-1b no-seed golden NO-GO / FIX-2 precision guard runtime green but semantic NO-GO / FIX-3 positive-recall/Kakao evidence runtime green but semantic NO-GO / native-web exhaustive judge blocker remains / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] 최신 source/preflight 확인: `out/expert_result_20260626_000008_928006.json`, manifest `completed_count=1946`, `flushed_count=1933`, `pending_count=13`, `failed_count=1`, `large_run_complete=false`.
  - [x] Phase 1 deterministic judge aggregate 실행: `out/full_post_judge_20260626_000008_928006_phase1`, processed/judged/missing `1933/1933/0`.
  - [x] report/rows 생성: `out/full_post_judge_20260626_000008_928006_phase1/report/full_post_judge_report.md`, rows `p01`-`p07`.
  - [x] analytics chart/table 생성: `out/full_post_judge_20260626_000008_928006_phase1/report/analytics/`.
  - [x] Phase 2 initial queue 생성: `out/full_post_judge_20260626_000008_928006_phase1/phase2_initial_queue.json`, rows `251`.
  - [x] Loop 01 Korean report 추가: `docs/devs/loop_reports/LOOP_01_REPORT_20260626.md`.
  - [x] FIX-0 bootstrap tool 추가: `tools/bootstrap_regression_safe_grounding.py`, focused tests `2 tests OK`.
  - [x] 동결 baseline 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`.
  - [x] regression panel 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel.jsonl`, unique posts `375`, survey `136/136`, Phase 2 queue `251/251`, controls `9/9`.
  - [x] golden set 생성: `out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_set.jsonl`, rows `16`, positive/negative `8/8`.
  - [x] collateral baseline selfcheck 완료: shared `1933`, changed `0`, `collateral_regression_count=0`.
  - [x] FIX-1 first-cut shared predicate 추가: `src/llm_batch/agentic_pipeline.py`의 `_post_discusses_work_as_work(...)`.
  - [x] FIX-1 contract test 추가: `tests/test_regression_safe_work_bridge_contract.py`.
  - [x] focused/rank verification 통과: contract+title-lead `77 tests OK`, rank1/2/3 `40 tests OK`, bootstrap+contract `4 tests OK`.
  - [x] FIX-1 partial repair: memory-query blocked attr 보존, `allow_ocr_catalog` shim compatibility, locked official rescue final-state 보존, OCR conflict 문구를 focused tests로 닫았다.
  - [x] FIX-1 broad affected suite green: `tests.test_agentic_pipeline_rework -v`, `440 tests OK`.
  - [x] 추가 guard verification: decoder slang dictionary guard + work-bridge contract + title-lead `81 tests OK`, rank1/2/3 `40 tests OK`, bootstrap+contract `4 tests OK`, py_compile pass.
  - [x] FIX-1 golden canary runtime 완료: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix1_golden_result.json`, completed/pending/failed `16/0/0`, VLM/OCR `READY`, `slang_db=off`.
  - [x] FIX-1 golden audit/collateral compare 생성: `canary/fix1_golden_audit.json`, `collateral/fix1_golden_collateral_compare.json`.
  - [x] FIX-1b measurement correction: golden input에서 `_judge_seed` 제거, expected answers는 `golden_manifest.json`에만 보존.
  - [x] no-seed golden canary 완료: `fix1b_golden_noseed_result.json`, completed/pending/failed `16/0/0`, VLM/OCR `READY`, `slang_db=off`, audit pass `8/16`.
  - [x] precision guard 추가: `candidate_audit.apply_weak_public_title_bridge_guard(...)` + `expert_main.py` postprocess wiring.
  - [x] FIX-2 precision guard canary 완료: `fix2_golden_precisionguard_result.json`, completed/pending/failed `16/0/0`, VLM/OCR `READY`, audit negative no-public-work `7/8`.
  - [x] latest precision edge unit verification: `tests.test_candidate_audit` `56 tests OK`, surrounding grounding/title-lead `79 tests OK`, py_compile pass.
  - [x] FIX-3 general guard 추가: official/search support 없는 weak `llm_only` direct image/OCR promoted title은 `ocr_explicit_title_unresolved` HOLD로 내린다.
  - [x] FIX-3 Kakao evidence repair 추가: title-matched Kakao comment/notice tab URL은 source title이 같은 웹소설을 명명할 때만 sanitized evidence로 쓰고, clean official detail URL보다 낮은 rank로 둔다.
  - [x] FIX-3 verification 완료: `tests.test_candidate_audit -v` `57 tests OK`, `tests.test_title_lead_search_inferred_guard -v` `75 tests OK`, bootstrap+contract `4 tests OK`, `tests.test_agentic_pipeline_rework` `441 tests OK`.
  - [x] FIX-3 no-seed golden canary 완료: `fix3_golden_positive_recall_result.json`, completed/pending/failed `16/0/0`, VLM/OCR `READY`, `slang_db=off`, audit pass `8/16`.
  - [x] FIX-3 Loop 03 Korean report 추가: `docs/devs/loop_reports/LOOP_03_REPORT_20260626.md`.
- 남은 작업:
  - [ ] native-web blind LLM judge runner/ingest를 복구하거나, deterministic aggregate를 별도 methodology로 명시해 accepted route를 분리한다.
  - [ ] source gap `13` pending rows와 manifest `large_run_complete=false`를 full-source completion으로 닫기 전까지 full approval claim을 금지한다.
  - [x] FIX-0 collateral/golden set을 고정한다: 기존 `136` survey errors와 Phase 2 high-severity wrong-work/source rows를 canary seed로 선정한다.
  - [x] `tests.test_agentic_pipeline_rework -v` 기존 broad failures를 재현/분리/수정하고 `440 tests OK`로 닫았다.
  - [ ] Seeded `fix1_golden_result`는 contaminated/superseded로 본다. 생산형 기준은 no-seed `fix1b`/`fix2` audit이다.
  - [ ] FIX-1b no-seed golden canary는 semantic `NO-GO`: passed `8/16`, negative no-public-work `5/8`, positive expected-work resolved `3/8`.
  - [ ] FIX-2 precision guard canary는 runtime green but semantic `NO-GO`: passed `7/16`, negative no-public-work `7/8`, positive expected-work resolved `0/8`.
  - [ ] FIX-3 positive-recall/Kakao evidence canary는 runtime green but semantic `NO-GO`: passed `8/16`, negative no-public-work `7/8`, positive expected-work resolved `1/8`, collateral regression candidates `8`.
  - [ ] latest edge guard (`없음`, `아카데미 되었다`)는 FIX-3 full golden canary에 포함됐지만 semantic approval 근거가 아니다.
  - [ ] `panel/regression_panel_input.jsonl` full panel canary는 아직 실행하지 않았다. golden이 통과한 뒤 panel collateral compare로 확대한다.
  - [ ] FIX-2/FIX-3 precision guard는 유지하되 accepted 처리 금지. positive recall/work-preservation 수리를 먼저 진행한다.
  - [ ] 다음 repair 축: negative leak `11694035`, OCR typo canonicalization, alias collision (`잘생인방`/`잘생인편`), official detail convergence, cross-media/external expected work HOLD policy.
  - [ ] 후속 reason/evidence mismatch 및 resolved-without-url lint를 final output stage에 추가한다.
  - [ ] 후속 `slang_db` store/read-only guard를 분리하고 common-word pollution 후보를 저장 금지로 유지한다.
  - [ ] 각 code fix 후 targeted canary, compare, docs/checklist/history sync를 같은 pass에서 수행한다.

## 2026-06-24 completed779 Hermes Loop 17 fresh/residual/control closure

- 상태: Loop 17 fresh/residual/control canaries complete / decoder NameError fixed / URL homonym compare closure implemented / latest hard queue `0` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 17 queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop17_fresh_residual_control_queue.json`, rows `28`, text/url/comment `7`, image/OCR `21`, duplicate `0`.
  - [x] text canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fresh_residual_control_text_result.json`, completed/failed/pending `7/0/0`.
  - [x] image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fresh_residual_control_image_ocr_result.json`, completed/failed/pending `21/0/0`, VLM/OCR `READY`.
  - [x] initial compare에서 `11706871` decoder `NameError: _is_genre_물_pattern`와 `11703669` expected URL mismatch residual을 확인했다.
  - [x] `src/llm_batch/experts/decoder.py` NameError 수정 및 `tests/test_decoder_resolved_mapping.py` regression 추가.
  - [x] `11706871` post-fix image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fix1_decoder_genre_pattern_11706871_image_ocr_result.json`, completed/failed/pending `1/0/0`, NameError/Traceback 재발 없음.
  - [x] `src/llm_batch/agentic_pipeline.py`에 author-context official URL ranking/freeze fallback ctx 전달을 보강했다.
  - [x] `tools/compare_completed779_improvement.py`가 expected URL candidate 보존 + same-title official detail alternate URL을 terminal `resolved_expected_title_author_supported_alt_url`로 분류한다.
  - [x] `11703669` post-fix text canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fix2b_author_context_flag_11703669_text_result.json`, completed/failed/pending `1/0/0`.
  - [x] latest combined compare 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop17_fix2b_author_context_flag_compare.json`, movement `blocked_or_candidate_preserved=6`, `candidate_or_human_review_preserved=9`, `candidate_preserved_with_benign_prune=4`, `resolved_expected_title=1`, `resolved_expected_title_author_supported_alt_url=1`, `url_lint_preserved=7`.
  - [x] latest next queue `out/completed779_improvement_goal_20260622/hermes_loop17_fix2b_author_context_flag_next_queue.json` rows `0`.
  - [x] `11694064` sentinel은 bad title로 회귀하지 않고 `판초우의의 마법사` candidate/URL을 보존했다.
  - [x] verification: py_compile pass, focused suite with rank1/2/3 `131 tests OK`, additional surrounding suite `172 tests OK`.
- 남은 작업:
  - [ ] Loop 17 queue `0`은 targeted/fresh-residual-control closure다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
  - [ ] 다음 loop가 필요하면 completed779 full approval이 아니라 fresh/residual/control/limitation pool을 다시 열어 진행한다.

## 2026-06-23 completed779 Loop 16 Claude post-review rank1-3 regression repair

- 상태: blocker reproduced / fixed / rank1-3 permanently added to completed779 verification command / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Claude review 지적을 로컬에서 재현했다: `tests.test_agentic_pipeline_rank1_lock_block tests.test_agentic_pipeline_rank2_ocr_catalog_evidence tests.test_agentic_pipeline_rank3_lock_anchor -v`가 40개 중 2개 실패.
  - [x] 실패한 테스트: `Rank1ChokepointDemoteTest.test_verifier_critical_demotes_but_preserves_title`, `test_official_detail_matched_url_exempt_from_demote`.
  - [x] 원인: `_title_lead_alias_precision_block_signal`이 verifier `critical/major`를 hard block으로 다시 처리해 rank1의 demote-but-preserve candidate를 폐기했다.
  - [x] 수정: `_title_lead_alias_precision_block_signal`에서 `critical_or_major` 트리거 제거. Critical/major 처분은 rank1 gate가 담당하고, 새 title-lead precision gate는 relation/competition/comment-meta 신호만 담당한다.
  - [x] rank1/2/3 suite 재검증: `40 tests OK`.
  - [x] completed779 focused suite에 rank1/2/3 modules를 포함해 재검증: `126 tests OK`.
  - [x] py_compile pass.
- 남은 작업:
  - [ ] 다음 completed779/Hermes goal은 검증 명령에 rank1/2/3 load-bearing modules를 반드시 포함한다.
  - [ ] Loop16 queue `0`은 targeted/control closure다. full scan approval로 승격하지 않는다.

## 2026-06-23 completed779 Hermes Loop 16 post-Loop15 residual/control closure

- 상태: Loop 16 control-only queue/canaries/compare complete / seed-conflict reason scrub implemented / latest hard queue `0` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 16 queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop16_post_loop15_residual_queue.json`, rows `7`, main `0`, controls `7`, text/url/comment `2`, image/OCR `5`, duplicate `0`.
  - [x] regression controls 포함: `11694064`, `11698880`, `11702055`, `11710037`, `11710045`, `11718077`, `11718105`.
  - [x] Hermes council fan-out 6축을 실행하고 메인 Codex가 파일/테스트/canary/compare로 재확인했다.
  - [x] text canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_text_result.json`, completed/failed/pending `2/0/0`.
  - [x] image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_image_ocr_result.json`, completed/failed/pending `5/0/0`, VLM/OCR `READY`.
  - [x] `tools/compare_completed779_improvement.py`에서 expected title match라도 expected URL mismatch면 re-improvement candidate로 남기도록 보강했다.
  - [x] `src/llm_batch/candidate_audit.py`에서 seed-conflict/trope-boundary demotion 후 `reason_lines`와 최종 `reason`의 public-title 확정 문구를 HOLD 문구로 scrub/sync한다.
  - [x] `src/llm_batch/candidate_audit.py`에서 expected seed 후보가 concrete alternate candidate로 오염된 경우 candidate audit lint를 남긴다.
  - [x] focused rerun `11698880`, `11710037`, `11718105`로 reason scrub과 candidate/HOLD 보존을 runtime 확인했다.
  - [x] final control compare 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop16_final_control_compare.json`, movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=3`.
  - [x] latest next queue `out/completed779_improvement_goal_20260622/hermes_loop16_final_control_next_queue.json` rows `0`.
  - [x] verification: py_compile pass, focused suite `86 tests OK`, `git diff --check` pass with LF/CRLF warnings only.
- 남은 작업:
  - [ ] Loop 16 queue `0`은 targeted/control closure다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
  - [ ] `11698880`의 alternate-work discovery와 `11718077` Munpia/Naver canonical distinction은 broader source/candidate strategy future work로 남긴다.

## 2026-06-23 completed779 Hermes Loop 15 trope-boundary guard + control closure

- 상태: Loop 15 queue/canaries/compare complete / trope-boundary guard implemented / latest hard queue `0` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 15 queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop15_remaining_expansion_queue.json`, rows `6`, main `1`, controls `5`, text/url/comment `2`, image/OCR `4`, duplicate `0`.
  - [x] regression controls 포함: `11694064`, `11698880`, `11702055`, `11710045`, `11718105`.
  - [x] Hermes council fan-out를 Candidate/Comment+Prompt, OCR/Visual, Source/URL+Web, Code Hook, Verification/Docs, Regression/Data 6축으로 실행하고 메인 Codex가 파일/테스트/canary/compare로 재확인했다.
  - [x] pre-fix text canary에서 `11710037`이 `괴담 호텔 탈출기` public title로 과승격되는 것을 확인했다.
  - [x] `src/llm_batch/candidate_audit.py`에 `trope_or_author_talk_risk` expected title/url을 candidate/HOLD로 보존하고 public title 승격을 막는 guard를 추가했다.
  - [x] `expert_main.py` postprocess에서 trope-boundary guard를 candidate audit field 산출 전에 호출한다.
  - [x] `tools/compare_completed779_improvement.py`에 `boundary_title_over_promoted`를 추가해 boundary seed가 resolved title로 false-close되지 않게 했다.
  - [x] Loop 15 fix1 text canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_fix1_trope_boundary_text_result.json`, completed/failed/pending `2/0/0`.
  - [x] Loop 15 image/OCR control canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop15_remaining_expansion_image_ocr_result.json`, completed/failed/pending `4/0/0`, VLM/OCR `READY`.
  - [x] Loop 15 combined compare 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop15_combined_fix1_compare.json`, movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=2`.
  - [x] latest next queue `out/completed779_improvement_goal_20260622/hermes_loop15_combined_fix1_next_queue.json` rows `0`.
  - [x] `11694064`는 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않고 `판초우의의 마법사` candidate/URL을 보존했다.
  - [x] verification: py_compile pass, focused suite `84 tests OK`.
- 남은 작업:
  - [ ] Loop 15 queue `0`은 targeted/control closure다. full scan approval로 승격하지 않는다.
  - [ ] 다음 Loop 16은 fresh/residual/control/limitation pool을 새로 열고, `11718077` control coverage gap을 필요 시 재포함한다.
  - [ ] `11710045`의 noisy candidate surfaces, Munpia mobile URL evidence strength normalization, `trope_or_author_talk_risk` taxonomy split은 future work로 남긴다.

## 2026-06-23 completed779 Hermes Loop 14 remaining expansion v2 + source/url retaxonomy

- 상태: Loop 13 source/url retaxonomy complete / Loop 14 v2 canaries complete / fix1 targeted canary complete / latest hard queue `0` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 13 combined compare를 stricter source/url hygiene taxonomy로 재실행해 false-closed `11698880`, `11702055`를 next queue `2`건으로 되살렸다.
  - [x] Loop 14 v2 queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_queue.json`, rows `22`, text/url/comment `8`, image/OCR `14`, duplicate `0`.
  - [x] regression controls 포함: `11694064`, `11698880`, `11702055`, `11710045`, `11718105`, `11718077`.
  - [x] Hermes council fan-out 결과를 메인 Codex가 파일/테스트/canary/compare로 재확인했다. Verification/Docs subagent context-window error와 추가 skeptic spawn thread-limit은 limitation으로 기록했다.
  - [x] Loop 14 v2 text canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_text_result.json`, rows `8/8`.
  - [x] Loop 14 v2 image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_image_ocr_result.json`, rows `14/14`, VLM/OCR `READY`.
  - [x] Loop 14 v2 combined compare 완료: movement `blocked_or_candidate_preserved=1`, `boundary_hold_preserved=2`, `candidate_or_human_review_preserved=14`, `candidate_preserved_with_benign_prune=1`, `resolved_expected_title=1`, `title_or_url_still_mismatched=2`, `url_lint_preserved=1`.
  - [x] Loop 14 v2 next queue `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_next_queue.json` rows `2`: `11698880`, `11702055`.
  - [x] `tools/build_completed779_hermes_expansion.py`에 explicit `--control-post-id`와 empty-main-target regression fix를 추가했다.
  - [x] `tools/compare_completed779_improvement.py`에서 source/url hygiene이 expected title 후보 없이 lint만으로 닫히지 않게 하고, expected-null row의 unexpected public title을 requeue status로 추가했다.
  - [x] `src/llm_batch/candidate_audit.py`에서 `group=hygiene` judge expected title/url도 candidate/HOLD evidence로 보존한다.
  - [x] Loop 14 fix1 targeted canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop14_fix1_hygiene_expected_candidate_v2_image_ocr_result.json`, completed/failed/pending `2/0/0`.
  - [x] Loop 14 fix1 compare 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop14_fix1_hygiene_expected_candidate_v2_compare.json`, movement `url_lint_preserved=2`, next queue `0`.
  - [x] verification: py_compile pass, focused suite `82 tests OK`.
- 남은 작업:
  - [x] final docs sync 이후 `git diff --check`를 재실행했다. 결과는 LF/CRLF 경고만 있고 whitespace error는 없다.
  - [ ] Loop 14 queue `0`은 targeted expansion closure다. full scan approval로 승격하지 않는다.
  - [ ] 다음 Loop 15는 fresh/residual/control pool을 새로 열고 `11694064`, `11710045`, `11718105`, `11698880`, `11702055`를 필요한 경우 regression controls로 유지한다.
  - [ ] prompt/orchestration residual은 별도 future work로 남긴다: snippet analyzer prompt drift, candidate role separation, central promotion gate, source URL canonicalization.

## 2026-06-23 completed779 Hermes Loop 13 residual expansion + relation-HOLD fix

- 상태: residual expansion canary/compare complete / active hard queue `0` rows / targeted `11710045` relation-HOLD fix complete / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 13 residual expansion queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_queue.json`, rows `51`, text/url/comment `9`, image/OCR `42`, duplicate `0`.
  - [x] Source/URL, Search/Web, Candidate/Comment, Prompt/Orchestration, Code Hook, OCR/Visual fan-out를 실행하고 메인 Codex가 파일/테스트/canary/compare로 재확인했다.
  - [x] text/url/comment canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_text_result.json`, rows `9/9`.
  - [x] image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_image_ocr_result.json`, rows `42/42`, VLM/OCR `READY`.
  - [x] combined compare 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop13_residual_expansion_combined_compare.json`.
  - [x] combined movement: `blocked_or_candidate_preserved=8`, `boundary_hold_preserved=4`, `candidate_or_human_review_preserved=31`, `candidate_preserved_with_benign_prune=3`, `resolved_expected_title=1`, `url_lint_preserved=4`.
  - [x] Loop 13 next queue `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_next_queue.json` rows `0`.
  - [x] `tools/compare_completed779_improvement.py`에 boundary-HOLD closure와 author/comment wrapper benign-prune accounting을 추가했다.
  - [x] `src/llm_batch/candidate_audit.py`에 OCR `work_cues` context-only surface 필터를 추가했다.
  - [x] targeted `11710045` pre-fix canary로 relation HOLD가 final gate에서 `넣어 키운 걸그룹` public title로 승격되는 bug를 확인했다.
  - [x] `src/llm_batch/agentic_pipeline.py`에 relation-HOLD indirect character/scene evidence title-resolution block을 추가했다.
  - [x] targeted `11710045` after-fix canary/compare 완료: `official_title=null`, `Identified=0`, `title_resolution_state=context_only`, movement `candidate_or_human_review_preserved=1`.
  - [x] verification: py_compile pass, focused suite `77 tests OK`, `git diff --check` pass with LF/CRLF warnings only before docs sync.
- 남은 작업:
  - [ ] Loop 13 queue `0`은 targeted closure다. full scan approval로 승격하지 않는다.
  - [ ] 다음 goal은 Loop 14 fresh/residual/control pool을 열고 `11694064`, `11710045`, `11718105`를 regression controls로 포함한다.
  - [ ] character/scene-only OCR evidence의 over-demotion risk를 broader sampled validation으로 확인한다.
  - [ ] subagent는 필요한 경우 다양한 전문가/모델/툴 관점으로 분산하되, 모든 결론은 메인 Codex가 재검증한다.

## 2026-06-23 completed779 Hermes Loop 12 fresh expansion + fix2

- 상태: fresh expansion canary/compare complete / targeted `11718105` fix2 complete / active hard queue `0` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 12 fresh expansion queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop12_fresh_expansion_queue.json`, rows `43`, text/url/comment `14`, image/OCR `29`, duplicate `0`.
  - [x] Hermes council 6축 fan-out를 실행하고 메인 Codex가 파일/테스트/canary/compare로 재확인했다.
  - [x] text/url/comment canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_text_result.json`, rows `14/14`.
  - [x] image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_image_ocr_result.json`, rows `29/29`, VLM/OCR `READY`.
  - [x] combined compare 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fresh_expansion_combined_compare.json`.
  - [x] pre-fix next queue는 `11718105` 1건으로 좁혀졌다.
  - [x] `src/llm_batch/candidate_audit.py`에 judge expected `multiple:` 멤버 prune 보호와 image OCR `work_cues` candidate-ledger 보존을 추가했다.
  - [x] `tests/test_candidate_audit.py`에 multi-title member pruning guard와 OCR work-cue ledger 보존 회귀 테스트를 추가했다.
  - [x] targeted fix2 canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fix2_ocr_work_cues_11718105_image_ocr_result.json`, completed/failed/pending `1/0/0`.
  - [x] targeted fix2 compare 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fix2_ocr_work_cues_11718105_compare.json`, movement `candidate_or_human_review_preserved=1`.
  - [x] targeted fix2 next queue `out/completed779_improvement_goal_20260622/hermes_loop12_fix2_ocr_work_cues_next_queue.json` rows `0`.
  - [x] verification: py_compile pass, related suite `74 tests OK`, scoped `git diff --check` pass.
- 남은 작업:
  - [ ] Loop 12 queue `0`은 targeted closure다. full scan approval로 승격하지 않는다.
  - [ ] 다음 goal은 Loop 13 fresh expansion/residual/control pool을 열고, `11718105`를 multi-title OCR work-cue preservation regression control로 포함한다.
  - [ ] `시리즈` 플랫폼 검색이 작품 후보 검색을 압도하는 search-intent/provider degradation은 future prompt/orchestration/search work로 남긴다.

## 2026-06-23 completed779 Hermes Loop 11 benign prune closure

- 상태: compare taxonomy fix complete / Loop 10 canary outputs re-compared / active hard queue `0` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Hermes council 6축 fan-out를 실행했다. Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Code Hook, Prompt/Orchestration findings를 메인 Codex가 파일/compare/tests로 재확인했다.
  - [x] thread limit으로 Verification/Docs subagent spawn은 실패했고, limitation으로 기록한 뒤 메인 Codex가 docs sync를 직접 수행했다.
  - [x] `tools/compare_completed779_improvement.py`에 `candidate_preserved_with_benign_prune` status를 추가했다.
  - [x] expected title/url이 candidate로 보존되고 prune된 surface가 expected title과 무관한 sentence/noise이면 requeue하지 않게 했다.
  - [x] `evidence_flags.expected_url_evidence_strength`를 추가해 `judge_seed_expected`, `active_official_detail`, `unavailable_official_detail`, `wiki`, `community` 등을 분리 기록한다.
  - [x] `tests/test_completed779_compare.py`에 benign prune closure, expected surface prune review 유지, URL evidence strength 분리 테스트를 추가했다.
  - [x] Loop 11 broader recompare 생성: `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_broader_compare.json`, movement `candidate_or_human_review_preserved=18`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=4`, `url_lint_preserved=8`.
  - [x] Loop 11 broader next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_broader_next_queue.json`, rows `0`.
  - [x] Loop 11 candidate/comment recompare 생성: `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_candidate_comment_compare.json`, movement `candidate_or_human_review_preserved=7`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=2`.
  - [x] Loop 11 candidate/comment next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_candidate_comment_next_queue.json`, rows `0`.
  - [x] focused compare tests `23 tests OK`, related suite `74 tests OK`, py_compile pass.
- 남은 작업:
  - [ ] Loop 11 queue `0`은 compare/verification taxonomy closure다. 새 fresh expansion이나 residual/control pool 없이는 full approval로 승격하지 않는다.
  - [ ] `11708478` 같은 작성자 댓글 명시 답변은 future work에서 comment-title bridge provenance/source strength 개선 후보로 남긴다.
  - [ ] full scan approval은 계속 `false`로 유지한다.

## 2026-06-23 completed779 Hermes Loop 9 residual closure

- 상태: Loop 8 fresh expansion canary/compare complete / Loop 9 residual canary/compare complete / active hard queue `0` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 8 fresh expansion queue를 생성했다: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue.json`, rows `43`, main `24`, controls `19`, duplicate `0`.
  - [x] Loop 8 text/url/comment canary를 실행했다: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_text_result.json`, rows `20/20`, VLM/OCR `NOT_APPLICABLE`.
  - [x] Loop 8 image/OCR canary를 실행했다: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_image_ocr_result.json`, rows `23/23`, VLM/OCR `READY`.
  - [x] Loop 8 combined result를 생성했다: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_combined_result.json`, rows `43`, duplicate `0`.
  - [x] Loop 8 combined compare를 생성했다: `out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_combined_compare.json`.
  - [x] compare movement: `blocked_or_candidate_preserved=9`, `candidate_or_human_review_preserved=15`, `resolved_expected_title=4`, `resolved_expected_title_and_url=2`, `url_lint_preserved=5`, `still_under_resolved_or_noise=3`, `title_or_url_still_mismatched=2`, `title_match_url_still_mismatched=3`.
  - [x] `tools/compare_completed779_improvement.py`가 candidate/primary_work 보존과 recall wrong-final-title mismatch를 정확히 분리하도록 보강했다.
  - [x] `tests/test_completed779_compare.py`에 `11694064`형 candidate preservation과 `11716462`형 recall wrong final title 회귀 테스트를 추가했다.
  - [x] `11694064` sentinel은 bad title로 회귀하지 않고 `판초우의의 마법사` 후보/URL을 보존했다.
  - [x] Loop 9 input split 생성: `out/completed779_improvement_goal_20260622/inputs/hermes_loop9_residual_input_manifest.json`, text/url/comment `4`, image/OCR `4`, missing `0`, duplicate `0`.
  - [x] `src/llm_batch/candidate_audit.py`에 comment-surface HOLD 후보 보존, judge-seed expected candidate preservation, weak `llm_only`/`comment_surface` sentence candidate pruning을 추가했다.
  - [x] `expert_main.py` postprocess에서 comment-surface 후보 보존과 judge expected 후보 보존을 candidate audit 전에 호출한다.
  - [x] Loop 9 text/url/comment canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_text_result.json`, rows `4/4`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_113346_494633.log`.
  - [x] Loop 9 image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_image_ocr_result.json`, rows `4/4`, VLM/OCR `READY`, log `logs/expert_run_20260623_113635_246713.log`.
  - [x] Loop 9 combined result 생성: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_combined_result.json`, rows `8`, duplicate `0`.
  - [x] Loop 9 combined compare 생성: `out/completed779_improvement_goal_20260622/compare/hermes_loop9_residual_combined_compare.json`, movement `blocked_or_candidate_preserved=3`, `candidate_or_human_review_preserved=5`.
  - [x] Loop 9 next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop9_residual_next_queue.json`, rows `0`.
  - [x] subagent Loop9 fan-out 결과를 메인 Codex가 파일/테스트/canary로 재확인했다.
  - [x] stale model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` 404를 확인하고, live model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`로 canary를 실행했다.
- 남은 작업:
  - [ ] Loop 9 queue `0`은 targeted closure다. 새 fresh expansion/source-correctness residual/control queue를 만들기 전 broader sample에서 over-hold/over-prune regression을 확인한다.
  - [ ] full scan approval은 계속 `false`로 유지한다.

## 2026-06-23 completed779 Hermes Loop 10 broader + candidate/comment expansion

- 상태: Loop 10 broader regression canary/compare complete / candidate-comment expansion v2 canary/compare complete / next queue `4` rows / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] subagent fan-out를 모델/관점별로 분산했다: Averroes `gpt-5.5`, Mill `gpt-5.4`, Fermat `gpt-5.4-mini`; Sagan은 context-window error로 limitation 기록.
  - [x] `tools/build_completed779_hermes_expansion.py`에 candidate/comment/multi 기본 lane, custom `--main-target`, `--clear-default-main-targets`, `--allow-balanced-main`, custom control URL bucket fix를 추가했다.
  - [x] Loop 10 broader regression queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_queue.json`, rows `32`, text/url/comment `15`, image/OCR `17`, duplicate `0`.
  - [x] Loop 10 broader text canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_text_result.json`, rows `15/15`, VLM/OCR `NOT_APPLICABLE`.
  - [x] Loop 10 broader image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_broader_regression_image_ocr_result.json`, rows `17/17`, VLM/OCR `READY`.
  - [x] Loop 10 broader combined compare 생성: `out/completed779_improvement_goal_20260622/compare/hermes_loop10_broader_regression_combined_compare.json`, movement `candidate_or_human_review_preserved=18`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=4`, `url_lint_preserved=8`.
  - [x] broader next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_next_queue.json`, rows `2` (`11710025`, `11708479`).
  - [x] Loop 10 candidate/comment expansion v2 queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_queue.json`, rows `11`, text/url/comment `4`, image/OCR `7`, duplicate `0`.
  - [x] candidate/comment v2 text canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_text_result.json`, rows `4/4`, VLM/OCR `NOT_APPLICABLE`.
  - [x] candidate/comment v2 image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop10_candidate_comment_expansion_v2_image_ocr_result.json`, rows `7/7`, VLM/OCR `READY`.
  - [x] candidate/comment v2 combined compare 생성: `out/completed779_improvement_goal_20260622/compare/hermes_loop10_candidate_comment_expansion_v2_combined_compare.json`, movement `candidate_or_human_review_preserved=7`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=2`.
  - [x] candidate/comment v2 next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_next_queue.json`, rows `2` (`11698878`, `11708478`).
  - [x] `tools/compare_completed779_improvement.py`가 expected evidence flags, prune review, blocked primary work를 분리하도록 보강했다.
  - [x] `src/llm_batch/candidate_audit.py`에 `blocked_primary_work_conflict` marking을 추가했다.
  - [x] focused tests `72 tests OK`, broader focused suite `170 tests OK`, py_compile pass.
- 남은 작업:
  - [x] Loop 11 input은 두 next queue를 합쳐 `candidate_preserved_with_prune_review` `4`건부터 시작했고, 최신 Loop 11 next queues는 rows `0`이다.
  - [x] `11710025`, `11708479`, `11698878`, `11708478`의 expected title/url candidate preservation과 prune lint가 동시에 생기는 이유를 row-level로 분리했다.
  - [x] prune/review policy fix는 hardcoded post_id가 아니라 expected evidence preservation과 prune surface mismatch rule로 만들었다.
  - [ ] full scan approval은 계속 `false`로 유지한다.

## 2026-06-22 completed779 Hermes Loop 4 closure and next expansion

- 상태: Loop 4 active queue closed / no-search degraded targeted canary / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] Loop 3 remaining `5`건(`11706856`, `11716478`, `11697255`, `11702072`, `11703624`)을 Loop 4 seed/input으로 재구성했다.
  - [x] `agentic_pipeline.py`에 댓글 답변 후보, 짧은/복합 약칭 후보, 캐릭터/설정 cluster 후보를 final promotion 없이 candidate ledger/HOLD로 보존하는 local preservation hook을 추가했다.
  - [x] candidate snapshot에 `local_preservation_type`과 `promotion_policy=hold_without_promotion`을 남겨 compare/docs가 보존 유형을 추적할 수 있게 했다.
  - [x] `compare_completed779_improvement.py`가 URL/domain-shaped title pollution을 `garbage_title_after`로 잡도록 보강했다.
  - [x] subagent fan-out 결과를 반영했다: URL/title pollution risk와 local hold provenance collapse를 메인 Codex가 코드/테스트로 재확인했다.
  - [x] Loop 4 text canary `4/4` 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop4_text_result.json`.
  - [x] Loop 4 image/OCR canary `1/1` 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop4_image_ocr_result.json`.
  - [x] Loop 4 combined compare `5/5` 완료: `out/completed779_improvement_goal_20260622/compare/hermes_loop4_compare.json`, movement `candidate_or_human_review_preserved=5`.
  - [x] active queue를 `out/completed779_improvement_goal_20260622/hermes_loop4_queue.json` rows `0`으로 갱신했다.
  - [x] continuous goal prompt를 Loop 4 queue `0` 기준으로 갱신했다.
- 남은 작업:
  - [x] source-correctness refresh queue/input을 준비했다: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_queue.json`, rows `39`, text/url/comment `14`, image/OCR `25`.
  - [x] 현재 search shard preflight를 남겼다: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/search_shard_audit_preflight.json`, ok `0/2`, Docker Desktop Linux engine pipe missing.
  - [x] next expansion queue 설계 원칙을 남겼다: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/next_expansion_queue_plan_ko.md`, unseen pool `201`.
  - [x] 정상 Docker/SearXNG shard를 복구하고 source-correctness evidence refresh를 별도 loop로 실행했다.
  - [x] source refresh 이후 random/high-risk expansion 또는 새 native-web non-ACCEPT queue를 만들어 다음 Hermes loop를 연다.
    - Loop 5 active queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue.json`
    - rows `44`, main `24`, controls `20`, text/url/comment `19`, image/OCR `25`, duplicate `0`
    - helper: `tools/build_completed779_hermes_expansion.py`
  - [x] Loop 5 text/url/comment canary를 실행했다.
    - 결과: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_text_result.json`, rows `19/19`
    - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_text_compare.json`
    - movement: `candidate_or_human_review_preserved=6`, `resolved_expected_title=3`, `review=4`, `still_under_resolved_or_noise=3`, `url_lint_preserved=3`
  - [x] Loop 5 image/OCR canary를 `--vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
    - 결과: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_image_ocr_result.json`, rows `25/25`, VLM/OCR `READY`
    - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_image_ocr_compare.json`
    - movement: `candidate_or_human_review_preserved=10`, `resolved_expected_title=1`, `review=8`, `still_under_resolved_or_noise=1`, `url_lint_preserved=5`
  - [x] Loop 5 compare와 next queue를 생성했다.
    - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_combined_result.json`, rows `44`, duplicate `0`
    - combined compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_combined_compare.json`
    - movement: `candidate_or_human_review_preserved=16`, `resolved_expected_title=4`, `review=12`, `still_under_resolved_or_noise=4`, `url_lint_preserved=8`
    - hard-fail next queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue.json`, rows `4`
    - operational residual queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_operational_residual_queue.json`, rows `24`
  - [x] Loop 5 hard residual `5`건을 Loop 6 postfix canary로 넘겨 candidate/HOLD preservation 기준으로 닫았다.
    - final queue: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4.json`, rows `0`
    - closed: `11710039`, `11705237`, `11698880`, `11698868`, `11708449`
  - [x] continuous goal prompt를 Loop 6 final queue rows `0` 기준으로 갱신했다. 다음 루프는 old hard-fail queue가 아니라 operational residual `24`건, native-web non-ACCEPT issue index, 또는 새 random/high-risk expansion에서 시작한다.
  - [ ] Loop 5 operational residual `24`건은 full approval 근거가 아니라 broader random/high-risk expansion 및 upstream orchestration research 후보로 유지한다.
  - [ ] Loop 4 no-search degraded evidence를 semantic approval로 승격하지 않는다.
  - [ ] full scan approval은 계속 `false`로 유지한다.

## 2026-06-22 completed779 reimprovement Loop 2 goal

- 상태: active goal prompt authored / execution pending / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] `goal.md`를 Loop 1 이후 남은 post-fix-adjusted `reimprovement_queue` `25`건 중심의 active contract로 갱신했다.
  - [x] 새 copy-paste prompt `docs/devs/COMPLETED779_REIMPROVEMENT_LOOP2_GOAL_PROMPT.md`를 작성했다.
  - [x] Loop 2 baseline을 고정했다: active rows `25`, `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`, active `garbage_title_after=0`.
  - [x] Candidate/comment/recall preservation group `16`건과 source/url hygiene group `9`건을 분리했다.
  - [x] Loop 1 controls를 명시했다: `11694064` bad-title 재승격 금지, `wrong_work=9` bad pipeline title 회귀 금지, snippet/breadcrumb title pollution 재발 금지.
- 남은 작업:
  - [ ] `tools/build_completed779_reimprovement_inputs.py` 또는 동등한 helper로 Loop 2 active queue를 text/url/comment input과 image/OCR input으로 분리한다.
  - [ ] candidate/comment/recall preservation fix와 source/url hygiene fix를 일반화 구현한다.
  - [ ] Loop 2 text/url/comment canary와 image/OCR canary를 실행한다.
  - [ ] Loop 2 compare와 `reimprovement_loop2_queue.json` / `_ko.md`를 생성한다.
  - [ ] 정상 Docker/SearXNG shard가 없고 direct fallback을 쓰면 degraded-provider evidence로만 기록한다.

## 2026-06-22 completed779 native-web improvement goal

- 상태: active goal 재설계 완료 / native-web issue index generated / balanced P0 seed ready / generalized fixes implemented / degraded + direct-search fallback canaries completed / compare + reimprovement queue generated / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] 기존 JUDGE3905 중심 `goal.md`를 `llm_judge_goal.md`로 보관하고, active `goal.md`를 completed779 native-web 개선 계약으로 갱신했다.
  - [x] stale aggregate 금지 규칙을 명시했다. deterministic `full_post_judge_report.md` 집계와 Codex-native web verdict 집계를 섞지 않는다.
  - [x] `tools/build_completed779_issue_index.py`를 추가해 `out/codex_native_web_judge_20260620_165159_711176_completed779/` verdict를 `post_id` 기준으로 dedupe하고 issue index/action queue/seed input을 생성한다.
  - [x] `out/completed779_improvement_goal_20260622/native_web_issue_index.json`과 `native_web_issue_index_ko.md`를 생성했다.
  - [x] native-web 기준 coverage `779/779`, missing `0`, duplicate after dedupe `0`, non-ACCEPT `266`을 재현했다.
  - [x] non-ACCEPT label은 `REPROCESS=208`, `HOLD=49`, `INFO_MISSING=7`, `REJECT=2`로 고정했다.
  - [x] 핵심 이슈 축은 `under_resolved=68`, `under_resolved_false_negative=64`, `wrong_relevance=62`, `heretic_url_null=13`, `wrong_work=9`, `candidate_preservation_missing=6`, `garbage_title=6`, `reason_evidence_mismatch=6`, `conflicting_or_multi_candidate=5`, `comment_explicit_title_missed=4`로 기록했다.
  - [x] balanced P0 seed `65`건을 생성했다. 구성은 precision/identity `15`, candidate/comment/multi-candidate `15`, recall/relevance `25`, source/url hygiene `10`이다.
  - [x] `11694064`는 seed에 포함됐고, `wrong_work=9` 전체도 모두 seed에 포함됐다.
  - [x] canary 입력을 `inputs/balanced_p0_text_url_comment.jsonl` `19`건과 `inputs/balanced_p0_image_ocr.jsonl` `46`건으로 분리했다.
  - [x] `tools/compare_completed779_improvement.py`를 추가해 seed before/after `official_title`, `heretic_url`, resolution/candidate/lint movement를 비교할 scaffold를 만들었다.
  - [x] `tests/test_completed779_issue_index.py`를 추가했다. fixture dedupe/split, 실제 completed779 contract, compare movement를 검증한다.
  - [x] 검증 중 발견된 memory-query taxonomy 회귀를 좁게 보정했다. `memory_query_unsupported_title_blocked`가 붙은 뒤 후단 recommendation guard가 subtype을 `recommendation_request`로 덮어쓰지 않게 했다.
  - [x] 요청된 py_compile/unit/diff 검증을 통과했다. focused suite는 `178 tests OK`다.
  - [x] 다음 자동 개선 연구·검증·재개선 실행용 goal prompt를 `docs/devs/COMPLETED779_AUTO_IMPROVEMENT_GOAL_PROMPT.md`로 작성했다.
  - [x] subagent 4축(taxonomy/source, code-hook, prompt/orchestration, verification/docs) 분석을 받아 메인 Codex가 code hook을 재확인했다.
  - [x] `candidate_audit.py`에 completed779 taxonomy와 `seed_bucket` 기반 group 분류를 추가했다. `wrong_work`/`overresolved_generic_trope`는 보수적 precision demote, source/url hygiene `reason_evidence_mismatch`는 lint로 분리한다.
  - [x] `agentic_pipeline.py`에서 댓글 명시 제목 후보를 final promotion이 아니라 `title_candidates` 보존 경로에 추가했다.
  - [x] `orchestrator.py`에서 semantic seed denial 상태의 댓글 제목 official probe가 전부 잘리지 않도록 intent permit 예외를 추가했다.
  - [x] `prompt_router.py`에 댓글/URL/OCR/짧은 약칭/캐릭터 cluster는 ledger 보존, final promotion은 별도 gate라는 문구를 추가했다.
  - [x] `compare_completed779_improvement.py`에 split canary scope, expected URL mismatch 판정, reimprovement queue 출력을 추가했다.
  - [x] text/url/comment degraded canary `19/19` 완료: `out/expert_result_20260622_161924_359370.json`.
  - [x] image/OCR degraded canary `46/46` 완료: `out/expert_result_20260622_162557_711822.json`, VLM/OCR Semantic Gate `READY`.
  - [x] combined compare `65/65` 생성: `out/completed779_improvement_goal_20260622/compare/combined_degraded_compare.json`.
  - [x] `wrong_work=9` 전체가 bad title finalize에서 벗어나 `blocked_or_candidate_preserved`로 이동했다. `11694064`도 `무협 게임에 빙의했다...스킵충이다`로 확정되지 않았다.
  - [x] reimprovement queue `19`건 생성: `out/completed779_improvement_goal_20260622/compare/combined_degraded_reimprovement_queue.json`.
  - [x] Docker/SearXNG 부재 상황에서 `src/llm_batch/mcp_bridge/server.py`에 Naver/Bing direct HTTP search fallback을 추가했다. 이는 정상 shard approval이 아니라 degraded-provider search evidence다.
  - [x] vLLM `/v1/models`를 확인해 현재 모델 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`로 canary를 실행했다. stale 계획 모델 `bg-digitalservices/Gemma-4-E4B-it-NVFP4`는 404였다.
  - [x] text/url/comment direct-search fallback canary `19/19` 완료: `out/expert_result_20260622_165552_032705.json`.
  - [x] image/OCR direct-search fallback canary `46/46` 완료: `out/expert_result_20260622_171928_162115.json`, VLM/OCR Semantic Gate `READY`.
  - [x] combined direct-search compare `65/65` 생성: `out/completed779_improvement_goal_20260622/compare/combined_direct_search_compare.json`.
  - [x] direct-search compare에서 `garbage_title_after=3`을 별도 포착하도록 `tools/compare_completed779_improvement.py`를 보강했다.
  - [x] 검색 스니펫/브레드크럼이 `official_title`로 승격되는 경로를 `src/llm_batch/candidate_audit.py` promotion guard에서 demote하도록 추가했다. blocked title은 ledger에 보존한다.
  - [x] direct-search 기준 root reimprovement queue `27`건 생성: `out/completed779_improvement_goal_20260622/reimprovement_queue.json`, `reimprovement_queue_ko.md`.
  - [x] snippet/breadcrumb polluted 3건 post-fix mini canary 완료: text 2건 `out/expert_result_20260622_183047_118075.json`, image/OCR 1건 `out/expert_result_20260622_183544_060718.json`.
  - [x] post-fix 결합 compare 생성: `out/completed779_improvement_goal_20260622/compare/garbage_title_postfix_combined_compare.json`, movement `candidate_or_human_review_preserved=2`, `still_under_resolved_or_noise=1`, `garbage_title_after=0`.
  - [x] post-fix-adjusted combined compare 생성: `out/completed779_improvement_goal_20260622/compare/combined_direct_search_postfix_adjusted_compare.json`, movement `blocked_or_candidate_preserved=15`, `candidate_or_human_review_preserved=22`, `resolved_expected_title=2`, `resolved_expected_title_and_url=1`, `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`.
  - [x] root reimprovement queue를 post-fix-adjusted 기준 `25`건으로 갱신했다. `garbage_title_after` active row는 `0`이고, `11716482`는 public-title 오염은 닫혔지만 comment multi-candidate 보존 미흡으로 active queue에 남겼다.
  - [x] 최종 검증 재실행: `py_compile` pass, focused suite `190 tests OK`, `git diff --check` pass(LF/CRLF warning only).
- 남은 작업:
  - [ ] direct-search fallback canary는 검색 기능을 회복했지만 정상 Docker/SearXNG shard가 아니다. 정상 shard search-enabled canary 전까지 semantic quality는 `REVIEW-LOCKED`로 둔다.
  - [ ] post-fix-adjusted root queue `25`건(`still_under_resolved_or_noise=16`, URL mismatch/missing `9`)은 다음 루프 seed로 사용한다.
  - [ ] controls에서 over-promotion이 새로 생기면 semantic `NO-GO`로 기록한다.
  - [ ] full scan approval은 expanded random/high-risk review 전까지 `false`다.

## 2026-06-21 full_post_judge 20260620_165159_711176 completed779 follow-up

- 상태: completed subset 전수 judge 산출 완료 / source coverage 분리 / sentinel wrong_work 포착 / Codex-native web completed779 전수 완료 / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] primary JSON `757`행이 아니라 shutdown flush gap `22`건을 포함한 `out/expert_result_20260620_165159_711176_completed_subset.json` `779`건을 판정 모수로 고정했다.
  - [x] `out/full_post_judge_20260620_165159_711176_completed779/`를 새 산출물 루트로 생성했다.
  - [x] coverage `processed/judged/missing/pending=779/779/0/0`, bad files `0`, run integrity `GO`를 확인했다.
  - [x] `_source_coverage.json`과 report §0.8에 primary flushed `757`, shutdown_pending_flush_gap `22`, flush gap 내 `11694064` 포함을 분리 기록했다.
  - [x] `11694064`는 `wrong_work`, `REPROCESS`, `conflicting_or_multi_candidate`, `Strong`, `high`, `re_judge`로 포착했다. note는 `경합후보=판초우의의 마법사`, `원문별칭=판초법사`, 후보 URL `https://novel.munpia.com/530500`를 남긴다.
  - [x] runbook에 검색/LLM judge 장기 작업은 Codex subagent fan-out으로 분해하고 메인이 post_id completeness/missing=0 병합을 책임지는 운영 지침을 추가했다.
  - [x] `report/rows/full_post_judge_rows_pNN.md`를 `LLM 판단 사유(한글)` 열 중심으로 재생성했다. 모든 post 행은 ACCEPT/none/unresolved 포함 한국어 판단 사유를 가진다.
  - [x] 정정: 사용자가 말한 LLM judge는 deterministic full_post_judge가 아니라 Codex 5.5 native web judge다. `agbrowse`/API key 없이 Codex 내장 web search/open으로 post 원문을 직접 읽고 검색하는 경로로 분리했다.
  - [x] `out/codex_native_web_judge_20260620_165159_711176_completed779/`를 새 산출물 루트로 만들고 `11694064` sentinel Codex-native web verdict를 남겼다.
  - [x] Codex-native web judge subagent 결과 batch `000`..`155`를 raw return과 표준 verdict로 분리 저장했다. 최종 표준 verdict 진행률은 batch 156개 `779`건, unique `779/779`, missing `0`이다.
  - [x] `11718069`는 Beauvoir 판정 후 메인 Codex native web search로 source URL을 보강했다. 결론은 단일 작품 resolved가 아니라 author_talk/adjacent HOLD다.
  - [x] batch `002`..`005` 추가 이슈를 기록했다: `11718085` under-resolved 후보 `로판으로 착각했다`, `11718089` 개돌 신작 author/new-work HOLD, `11718095` 댓글 명시 제목 누락, `11718094` OCR 캐릭터 단서만 있는 unresolved 보존.
  - [x] batch `006`..`011` 추가 이슈를 기록했다: `11718119` 즉사무림 under-resolved, `11718114` generic system trope over-resolved, `11718105` OCR 다중 공식작 후보 누락, `11718091` 정보 부족/human review, `11718106` author_talk/adjacent 보존, `11718061` 복수 추천 목록 null-title 보존.
  - [x] batch `012`..`017` 추가 이슈를 기록했다: `11718057` 컵라면 신작 후보 HOLD, `11718055` 댓글 명시 제목 `새엄마의 친구들` 누락, `11718051` 댓글 단서 `몰락민족의 천재 기사` 누락, `11718049` 추천 댓글 URL 후보 보존 누락, `11716501` 히로인 분양 일반 용어 과승격, `11716500` `검머기 -> 검은머리 기사왕` 누락, `11716492` 댓글 추천작 `2회차 환관이 남성을 되찾음` 누락.
  - [x] batch `018`..`023` 추가 이슈를 기록했다: `11716482` 댓글 다중 후보 HOLD, `11716480` OCR 제목/후보 URL 불일치, `11716479`/`11716475` `고능아 -> 저 머리 좋은데요` 누락, `11716478` 댓글 2작품 후보 보존 누락, `11716462` `니생들 -> 니들 생각 다 들린다` 누락, `11716453` `마학간 -> 마왕은 학원에 간다` 누락, `11716448` `아생갤 -> 아카데미 생존 갤러리` 누락.
  - [x] batch `024`..`029` 추가 이슈를 기록했다: `11714913` `주서연 -> 전 버튜버가 하고 싶은데요` 누락, `11714905` 후보 `오랜만에 만난 가족이 너무 야함`, `11714904` `괴담동 -> 괴담 동아리` 누락, `11714902` `헌터상담` wrong_work, `11714898` OCR 소개문 단일작품 누락, `11714888` `고은하 -> 격투 천재 여고생이 되었다` 누락, `11714887` `도굴왕 1 |` garbage title.
  - [x] batch `030`..`035` 추가 이슈를 기록했다: `11714879` `무한회귀 여자친구 네토라세` 누락, `11714876` `합스부르크의 슈퍼스타가 되었다` 누락, `11714875` `K-문화의 제왕` 누락, `11714869` `묵향`/`묵향 다크레이디` primary 경합, `11714867` `쿠크루` 작가 메타 관련성, `11714865` `현질수선전` 누락, `11713233` `가챠 중독자의 퓨전펑크 생활` 누락, `11713228` `빙엄아유 -> 빙의한 엄마가 아들을 유혹함` 후보 HOLD.
  - [x] batch `036`..`041` 추가 이슈를 기록했다: `11713222` `잘생인방 -> 잘생기면 편해지는 인방 생활` 누락, `11713217` `미래에서 온 연애편지` 마스킹 캐릭터 단서 누락, `11713215` 오늘도요 신작 `즉사기 들고 무림에 떨어지다` 누락, `11713214` `눈물을 마시는 새` 약한 밈 후보 HOLD, `11713210` `설문조사를 했다가 세상을 부숴 먹었다.` 누락, `11713206` `킬더드 -> 킬 더 드래곤` 누락, `11713205` 댓글 공식 URL `농사 좀 지었을 뿐인데 고려가 제국이 되었다` 누락, `11713197` `내 복사 스킬은 아무래도 뭔가 잘못됐다` 공식 URL 보강 필요.
  - [x] batch `042`..`047` 추가 이슈를 기록했다: `11713190` 노피아→문피아 작가/플랫폼 메타 wrong_relevance, `11713186` `목마신작 -> 검귀가 환생함` 누락, `11711636` 작가/프로모션 메타 정보 부족, `11711632` 애니 `너의 이름은.` OCR과 리디 `Your Name` wrong_work, `11711631` `괴담에 휘말렸다` URL mismatch, `11711627` `지구판역 -> 판타지에 지구 역사를 풀었다` 누락, `11711622` 댓글 URL `무림에서 외과의로 살아가는 법` 누락, `11711620` OCR `괴이에게 애호받는 신입이 되었다` 누락, `11711616` `새로운 이치/알렙 -> 괴담 호텔 탈출기` 누락.
  - [x] batch `048`..`053` 추가 이슈를 기록했다: `11711605` `랫따싶` 다중 후보/작품군 HOLD, `11711600` `망카데미 -> 망할 놈의 아카데미` 누락, `11711599` 특정 소설 장면 감상이나 title 정보 부족, `11711597` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 후보, `11711596` 댓글 URL `로판 속 주인공이 나만 좋아함` 누락, `11711590` 문모전/웹소설 공모전 AI 플랫폼 메타 wrong_relevance, `11711582` AI 작가/창작 메타 HOLD, `11711581` 작가 정체성 메타 HOLD, `11710069` 삼국지 서사 감상 wrong_relevance.
  - [x] batch `054`..`059` 추가 이슈를 기록했다: `11710067` 장르 클리셰 토론 wrong_relevance, `11710065` 노피아 랭킹/4드론 플랫폼 메타 wrong_relevance, `11710063` 댓글/인용 제목 `나비꽃` 누락, `11710059` OCR 웹소설 본문 반응 정보 부족, `11710058` `판초우의의 마법사` under-resolved/wrong_relevance, `11710056` `아카데미 생존 갤러리` 누락, `11710055` `가챠 중독자의 퓨전펑크 생활` 캐릭터 근거, `11710052` `아카엄창 -> 아카데미 패드립 면역` 누락, `11710047` wrong_work `로판 속 미움받는 악역이 되었다` vs `아카데미 속 미움받는 악역이 되었다`, `11710045` OCR 웹소설 장면 정보 부족, `11710044` `가챠펑크 -> 가챠 중독자의 퓨전펑크 생활`, `11710043` `악엔 -> 악역의 엔딩은`, `11710042` `아카엠창` weak source HOLD, `11710039` `기계공주 -> 헌터갤러리의 국가권력급 기계공주`, `11710038` 댓글 명시 제목 `제발 죽지 말아주세요, 공녀님`, `11710037` `담텔기 -> 괴담 호텔 탈출기` trope boundary HOLD.
  - [x] batch `060`..`065` 추가 이슈를 기록했다: `11710035` `즉사무림 -> 즉사기 들고 무림에 떨어지다` 누락, `11710033` `판초법사 -> 판초우의의 마법사` wrong_work, `11710025` `망카 -> 망할 놈의 아카데미` 누락, `11710024` `주술초월 -> 주술사는 초월을 원한다` 누락, `11710021` `무마 -> 무한의 마법사` URL missing, `11710020` `주전무 -> 주무시기 전에 무엇을 하셨나요?` URL missing, `11710019` `한가인/승엽이 -> 괴담 호텔 탈출기` 캐릭터 단서 누락, `11708481` `지잡아카 -> 지잡 아카데미와 폐급 히로인들` 누락, `11708479` `시달소 -> 시간을 달리는 소설가` wrong_relevance, `11708478` 댓글 명시 제목 `사연 있는 악역으로 착각 당한다` 누락, `11708475` 브런치 글 OCR wrong_relevance.
  - [x] batch `066`..`071` 추가 이슈를 기록했다: `11708470` `절꺾않` title-correct URL mismatch, `11708469` `기계공쥬 -> 헌터갤러리의 국가권력급 기계공주` 누락, `11708468` `반지성마왕 -> 반지성주의 마왕의 세계침략` 누락, `11708466`/`11708457` `매국노` 누락, `11708461` OCR `마법소녀 갤러리` 누락, `11708460` garbage title `novel.munpia.com`, `11708453` `이불사 -> 이세계 불법체류 사이비` 누락, `11708450` `악살싶`/`변마금` 작품 간 표절 토론 wrong_relevance, `11708449` `담청 -> 죽었다 깨어도 수선` 캐릭터 단서 누락, `11708446` 추천글 후보 ledger 누락, `11708443` `괴담출근` 공식 URL missing, `11708442` 정주행 추천글 다중 후보 보존 누락.
  - [x] batch `072`..`077` 추가 이슈를 기록했다: `11708437` `악살싶` title-correct URL mismatch 및 후보 보존 점검, `11708434` `지갑송 신작 -> 반강제적 제국주의자` 누락, `11708430` `매국노` 누락, `11706873` `전능뇌 -> 전능의 뇌를 얻었다` 누락, `11706871` `파우스트 1` URL missing, `11706860` 림버스 `파우스트` OCR wrong_relevance, `11706857` 댓글 `헌터상담 -> 조향사의 헌터상담기록` 누락, `11706856` 백합 추천글 후보 ledger 누락, `11706855` 웹툰/소설 혼재 추천글 후보 보존 HOLD.
  - [x] batch `078`..`083` 추가 이슈를 기록했다: `11706852` `판초법사 -> 판초우의의 마법사` 별칭 official_title under-resolved, `11706845`/`11706840`/`11706832` `황제분충 -> 황제폐하가 웹소설 작가임을 숨김` 누락 또는 wrong_relevance, `11706844` OCR `범 먹는 괴이 사냥꾼`/편곤 단서와 현 문피아 `호랑이 사냥꾼` 불일치 재검증, `11706828` `내 마법도서관이 살아있다` 누락, `11706827` `기계공주 -> 헌터갤러리의 국가권력급 기계공주` 누락.
  - [x] batch `084`..`089` 추가 이슈를 기록했다: `11705273`/`11705258` `판초우의/판초 10 -> 판초우의의 마법사` 누락, `11705272` `태탑 -> 태양의 탑` garbage_title, `11705266` 노벨피아 자유연재/로판 플랫폼 담론 wrong_relevance, `11705264`/`11705257` `히로히로 -> 히어로 IN 히로인` 누락, `11705262` `수상남매 -> 수상할 정도로 사이가 좋은 남매` 댓글 후보 누락, `11705261` `이티알 -> 이세계 TRPG 게임마스터` 누락, `11705259` `아생갤 -> 아카데미 생존 갤러리` 누락, `11705256` `하남자 탑 -> 하남자의 탑 공략법` 누락, `11705249` 웹툰/소설 adaptation comparison subtype mismatch, `11705248` `이블파티 -> 나의 악당들` wrong_work.
  - [x] batch `090`..`095` 추가 이슈를 기록했다: `11705245`/`11705241`/`11705235` `하남자/하남자탑공략 -> 하남자의 탑 공략법` 누락, `11705243` SF 추천글 wrong_relevance, `11705240` TS여경물 추천 욕구를 `격투 천재 여고생이 되었다`로 over-resolved, `11705239` 도쿄구울 패러디 찾기글 over_resolved, `11705237` 월야환담 웹툰 under-resolved, `11705231` `설지후/탐식 -> 탐식의 재림` wrong_relevance, `11705228` 일본 로맨스소설 장르 담론 wrong_relevance, `11703673` `나비꽃2` 댓글 확인 누락, `11703669` `세나영 -> 세상에 나쁜 영애는 없다` 누락, `11703668` `갤질의사 -> 댓글 보는 천재 의사` 누락, `11703666` 키오스크 괴담 소재 담론 wrong_relevance, `11703663` 노벨피아 플랫폼 이용/추천 맥락 wrong_relevance.
  - [x] batch `096`..`101` 추가 이슈를 기록했다: `11703661` `막드제 -> 막장드라마의 제왕` 누락, `11703658` `아프리카 반란군 사령관이 되었다` 문피아 공식 URL 보강, `11703657`/`11703641` 댓글 URL `야만인은 문명하면 안되냐` 누락, `11703654`/`11703650` 웹소설 소비·추천글 wrong_relevance, `11703649` 댓글 추천작 `레즈돔 일진녀의 마조 노예로 조교당한다` 누락, `11703640` 부수 댓글 `기계공주` over_resolved, `11703637` `주술회전` cross-media 경계, `11703634` `세종 파딱 -> 세종의 종신재상이 되었다` 누락, `11703631` `이블파티 -> 나의 악당들` wrong_work, `11703629` 작품 감상 맥락 정보 부족.
  - [x] batch `102`..`107` 추가 이슈를 기록했다: `11703625` `목마 신작 -> 검귀가 환생함` 누락, `11703624` `판초법사 -> 판초우의의 마법사` 누락, `11703621` 댓글 `시체공양으로 데미갓` HOLD, `11702094` `댓글창 -> 댓글창의 천재 마법사` 누락, `11702090`/`11702082`/`11702078`/`11702077` `괴담 호텔 탈출기` 캐릭터·설정 단서 누락, `11702087` 위키 문서형 garbage title, `11702086` OCR 명시 `6★ 가챠 캐릭터가 되었다` 누락, `11702085` 괴담텔 wrong_relevance, `11702081` `게임 속 재해병 이야기` wrong_relevance, `11702079` `망향무사` URL mismatch.
  - [x] batch `108`..`113` 추가 이슈를 기록했다: `11702072`/`11702068`/`11702066`/`11702063`/`11702060`/`11702059`/`11702054`/`11702052`/`11702051`/`11702047` `괴담 호텔 탈출기` 캐릭터·설정 단서 누락 또는 비관련 오판, `11702064` OCR 명시 `흔해빠진 직업으로 세계최강` 누락, `11702061` 동명 후보 있는 `요리의 신` 후보 보존 필요, `11702057` 댓글 추천작 `멸망할 세계의 파견 용사` 누락, `11702055` `괴담 호텔 탈출기` title-correct URL mismatch, `11702050` `폴라리스 랩소디` URL missing, `11702049` `2레벨무신 -> 2레벨로 회귀한 무신` 누락.
  - [x] batch `114`..`119` 추가 이슈를 기록했다: `11700504` OCR 명시 `시간을 달리는 소설가` title/url 보강, `11700495` `서문청 -> 이 무림의 미친년은 나야` 누락, `11700490` 노피아 독서/추천 플랫폼 메타 wrong_relevance, `11700488`/`11700485` 버거피아/부기 플랫폼 이벤트 메타 wrong_relevance, `11700487` `군필돌 -> 아이돌이 군필을 숨김` URL missing, `11700483` `니생들 -> 니들 생각 다 들린다` URL missing, `11700480` 기계공주 후보 HOLD, `11700475` 댓글 공식 URL `내 파티에는 미친년들만 꼬인다` 누락.
  - [x] batch `120`..`125` 추가 이슈를 기록했다: `11700473` `로나좋 -> 로판 속 주인공이 나만 좋아함` truncated/garbage title, `11700470` OCR `밤도깨비 에이브` 공식 제목 미검증 HOLD, `11700468` `악당 엔딩 -> 악역의 엔딩은` 누락, `11698910` `판초우의 -> 판초우의의 마법사` 누락, `11698907` `괴담텔 -> 괴담 호텔 탈출기` 누락, `11698903` `기계공주 -> 헌터갤러리의 국가권력급 기계공주` title/url mismatch.
  - [x] batch `126`..`131` 추가 이슈를 기록했다: `11698897`/`11698895`/`11698886` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 누락 또는 wrong_relevance, `11698890` `댓천마 -> 댓글창의 천재 마법사` URL missing, `11698888` 월억킥 창작/수익 밈 relevance, `11698884` `무림마조` 캐릭터명 under_resolved, `11698880` `아생갤` title-correct URL mismatch, `11698878` `담청 -> 죽었다 깨어도 수선` OCR/DC콘 후보 HOLD, `11698875` `몸을 만지는 관문지기가 되었다` wrong_relevance, `11698873` `내마도살/전생흑막` 작가-전작 후보 보존, `11698871` `리제로 -> Re : 제로부터 시작하는 이세계 생활`, `11698870` 고전문학 스코프 HOLD, `11698869` `월야환담` URL missing, `11698868` `방타스 -> 방접은 죽어서 하세요`, `11698867` 핵전쟁 이후 생존물 추천 relevance를 추가했다.
  - [x] batch `132`..`137` 추가 이슈를 기록했다: `11698866` `캣파` 장르소설 인접 추천/스코프 HOLD, `11698865` `나츠키 스바루/작중 행적` 위키성 wrong_work를 `Re : 제로부터 시작하는 이세계 생활`로 교정, `11698862` OCR 제목찾기 글 novel-related re_search HOLD, `11698861` `엘황 -> 외신이 쓴 마도서를 주웠다.` 후보, `11698860` `악엔 -> 악역의 엔딩은 죽음뿐` 약칭 under_resolved, `11698859` `귤부인 -> 친아들이 내게 집착한다` wrong_relevance, `11697267` `아생갤` title-correct URL mismatch, `11697266`/`11697258` `담청/죽깨수 -> 죽었다 깨어도 수선`, `11697261` `까꿍공주` info_missing HOLD, `11697256` TS 추천글 multi-candidate HOLD, `11697255` `판초 -> 판초우의의 마법사` wrong_relevance를 추가했다.
  - [x] batch `138`..`143` 추가 이슈를 기록했다: `11697242` 유희왕 패러디/팬픽 장르 트로프 wrong_relevance HOLD, `11697241` 댓글 공식 URL `나폴리탄 괴담 세계 속 대장장이가 살아남는 방법`, `11697239` 조혈모세포 안내 책자 OCR false positive, `11697236` `엘시짤 -> 미래에서 온 연애편지` 캐릭터 앵커 누락, `11697234` `검귀가 환생함`, `11697233` 하츠네 OCR 과민 wrong_relevance, `11697231` `아생갤 -> 아카데미 생존 갤러리`, `11697229` 백합 트로프 scope HOLD, `11697226` 여주물 추천 multi-candidate HOLD, `11697219` `바르바로이 -> 이세계 검은 머리 바르바로이가 미궁에서 살아남는 법`.
  - [x] batch `144`..`149` 추가 이슈를 기록했다: `11695639`, `11695637`, `11695634`, `11695633`, `11695627`, `11695623`, `11695617`, `11695611`에서 마지막 전 구간의 약칭·댓글·OCR 기반 후보 보존 누락을 확인했다.
  - [x] batch `150`..`155` 추가 이슈를 기록했다: `11695609`/`11695607` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 후보 보존 HOLD, `11695608` `예수천국 불신지옥` under_resolved, `11695602` OCR/광고 후보 `로판 속 바바리안 부부`, `11695599` garbage title `창관전생()` -> `창관전생(娼館轉生)`, `11695593` `_172` 신작 `S급 헌터도 결혼이 하고 싶다` 후보 보존, `11694064` sentinel wrong_work, `11694059` 플랫폼/추천글 multi-candidate 후보 보존, `11694042` `김근홍/2회차 -> 괴담에 휘말렸다` 누락.
  - [x] `tools/codex_native_web_judge_ingest.py`를 추가해 subagent raw JSON을 표준 raw/verdict/progress/rows로 병합하는 coordinator helper를 만들었다.
  - [x] PowerShell literal 경로에서 batch `006`..`017` 한국어 사유가 `???`로 깨지는 문제를 발견했고, batch `018`..`155`는 UTF-8-safe ingest 경로로 표준 verdict/raw/rows를 보존했다. 검증상 replacement question run `0`, rows `779`이다.
  - [x] `tools/codex_native_web_judge_ingest.py` progress JSON 저장 순서를 보정하고 external judge enum drift normalization을 추가해 `rows_written=779`, `bad_question_runs=0`이 파일에 남게 했다.
  - [x] `tools/codex_native_web_judge_ingest.py` rows renderer를 post_id 기준으로 dedupe해 standalone sentinel과 표준 batch `153`의 `11694064` 중복을 제거했다.
- 남은 작업:
  - [x] Codex-native web judge를 completed779 전체로 확장했다. 현재 `779/779`, missing `0`이며 모든 post 행은 원문 직접 판단, 필요한 웹검색 URL, 한국어 사유를 가진다.
  - [ ] `wrong_work=2`(`11694064`, `11703674`)는 primary candidate selection bug seed로 분리하고, 공식 URL 존재보다 source-local alias anchor를 우선하는 일반화 fix를 설계한다.
  - [ ] `conflicting_or_multi_candidate` 및 `reason_evidence_mismatch=29`는 agentic primary 선택/근거 정합성 큐로 묶는다.
  - [ ] `re_search`, `re_judge`, `slang_db_review`, `human_review` action queue는 post_id packet 단위로 쪼개고 full scan approval과 섞지 않는다.
  - [ ] 다음 GPT/Claude/vLLM judge 전수 dump에서도 `LLM 판단 사유(한글)` 열이 빈 값 또는 영어 key-value-only로 퇴행하지 않는지 검증한다.

## 2026-06-18 recall 감사 follow-up (IMP-278)

- 상태: 적대적 감사로 IMP-277 런의 recall 러버스탬프 적발 / 강판정 recall 회수 65건 확보 / fix 미구현 / semantic REVIEW-LOCKED / approval false
- 후속(우선순위 순):
  - [ ] (P0) IMP-278 일반화 fix 구현: in-pipeline official-URL DETAIL+제목일치 승격 게이트(+OCR explicit-title 해소), 과승격 가드, 테스트. 시드 `recall_recovery_seed.jsonl`로 회귀.
  - [ ] (P1) recall 회수 exhaustive 확장: score≥5 잔여 풀(~506행)을 강화 recall 프롬프트로 Codex 재판정해 전수 회수 기록.
  - [ ] (P1) precision false-accept(26.7%) 패턴 보정: 표면 URL 일치만으로 ACCEPT 금지 — post↔work 정합 검증 필수화.
  - [ ] (P2) slang one_alias_many_works 오발화 보정(후보 title 문자열 수 ≠ alias 다의성) — pollution_risk 오경보 12/22 제거.
- 주의: 첫 Codex 전수 판정은 구조 GO이나 의미(recall) NO-GO. 품질 베이스라인으로 사용 금지, REVIEW-LOCKED 유지.

## 2026-06-18 full_post_judge 20260616_224555_632905 follow-up

- 상태: 전수 판정 산출 complete / action queue open / semantic quality REVIEW-LOCKED / full scan approval false
- 완료:
  - [x] `out/expert_result_20260616_224555_632905.json` flushed `2246`건을 `docs/devs/FULL_POST_JUDGE_RUNBOOK.md` §3 절차로 전수 판정했다.
  - [x] pending `23`건은 `_pending_rerun.json`으로만 남기고 판정에서 제외했다.
  - [x] compact `batch_NNN.json` `450`개와 FULL `verdicts_NNN.json` `450`개를 생성했다.
  - [x] FULL 16필드/enum/invariant 검증을 통과했다. `judged=2246`, `missing=0`, bad files `0`.
  - [x] `candidate_audit` shadow rebucket mismatch `0`을 확인했다.
  - [x] 정밀 overlay `449` batch, recall hold 15% overlay `42` batch를 생성했다.
  - [x] `report/full_post_judge_report.md`, `report/full_post_judge_metrics.json`, `report/rows/full_post_judge_rows_p01.md`..`p08.md`를 생성했다.
  - [x] slang axis는 `slang_axis_route=="llm"` `94`건만 판정했고 slang DB write-back은 하지 않았다.
- 남은 작업:
  - [ ] `human_review=110`은 boundary/relevance/title recall 경계 case로 따로 packet화한다.
  - [ ] `re_judge=87` 중 high severity `4`와 `official_title_lint` 기반 `REJECT=6`을 우선 회귀 seed로 분리한다.
  - [ ] `re_search=44`와 resolved search `Missing=132`를 official_detail URL/title-match 재탐색 큐로 묶는다.
  - [ ] `slang_db_review=22`와 store=true pollution risk `11`건을 slang DB 쓰기 없이 검수한다.
  - [ ] full_post_judge 결과는 보조 기준선으로만 사용하고, source-backed rerun/canary 전까지 semantic quality `REVIEW-LOCKED`와 full scan approval `false`를 유지한다.

## 2026-06-14 agbrowse GPT Pro judge follow-up

- 상태: runner fixed / full GPT Pro judge complete / report updated
- 완료:
  - [x] `agbrowse` + ChatGPT Pro 로그인/간단 JSON query 동작을 확인했다.
  - [x] 기존 prompt/context 전달 방식이 batch JSON을 안정적으로 전달하지 못해 `batch=null`, `verdicts=[]`가 발생하는 것을 확인했다.
  - [x] `tools/run_agbrowse_llm_judge.py`를 Node 직접 실행, `POSTS_JSON` inline, 5건 sub-call 병합 방식으로 고쳤다.
  - [x] smoke 5건에서 post_id 누락 없는 verdict 저장을 확인했다.
  - [x] `query` 완료 감지 hang을 피하기 위해 `send -> watch -> sessions show` 세션 경로를 기본으로 바꿨다.
  - [x] ChatGPT provider tab cleanup과 실패 chunk 1건 단위 split checkpoint를 추가했다.
  - [x] provider prompt 전송 안정화를 위해 민감 표현 bracket redaction과 stale `sent` session prune을 추가했다.
  - [x] 장기 pass에서 간헐 실패 batch를 건너뛰고 다음 pass에서 checkpoint 기반으로 메울 수 있도록 `--continue-on-fail`을 추가했다.
  - [x] 25건 단일 호출(`--records-per-call 25 --no-split-on-failure`)이 batch `006`~`019`에서 유효 JSON을 반환해 장기 실행 기본 모드가 됐다.
  - [x] `out/_judge3905_gpt_pro_v2` batch `000`~`099`를 검증해 `2500/3874` post, `100/155` batch가 유효함을 확인했다.
  - [x] ChatGPT `요청이 너무 많습니다` 팝업을 snapshot watcher로 닫으며 batch `112`를 slow chunk로 복구했고, batch `113`~`125`는 25건 단일 호출로 검증했다.
  - [x] `out/_judge3905_gpt_pro_v2` batch `000`~`125`를 검증해 `3150/3874` post, `126/155` batch가 유효함을 확인했다.
  - [x] `out/_judge3905_gpt_pro_v2` batch `126`~`154`를 완료해 최종 `3874/3874` post, `155/155` batch, `agree=2303`, `invalid_batches=[]`를 확인했다.
  - [x] `post_reviews.jsonl`, `post_reviews.md`, `post_ids_by_type.json`, `_result.json`을 생성했다.
  - [x] `docs/devs/JUDGE3905_REPORT.md`를 GPT Pro 전수 결과 기준으로 갱신했다.
- 남은 작업:
  - [x] 파이프라인/프롬프트/BatchContext/slang_db 구조와 GPT Pro judge 결과를 묶은 연구 컨텍스트를 `docs/devs/GPT_PRO_PIPELINE_RESEARCH_CONTEXT_20260614.md`로 작성했다.
  - [x] ChatGPT web-ai 심층 분석 결과를 `docs/devs/GPT_PRO_PIPELINE_RESEARCH_DIRECTIONS_20260614.md`로 정리했다. 단, `agbrowse`가 ChatGPT model selector를 찾지 못해 `pro/extended` 강제 확인은 실패했으므로 모델 강제 검증 완료로 표기하지 않는다.
  - [x] `--model pro --effort extended --research deep` 재실행을 수행하고 `docs/devs/GPT_PRO_DEEP_RESEARCH_RERUN_20260614.md`에 session/log/context zip/응답 caveat를 기록했다. 전송 전 UI는 `Pro 확장 모드`였지만, CLI effort 강제와 Deep Research 활성은 검증 완료로 보지 않는다.
  - [x] `post_ids_by_type.json`/`post_reviews.jsonl`에서 recall/precision/hygiene/OCR seed registry JSON을 생성하는 도구를 만들었다.
  - [x] `under_resolved_false_negative` 644건을 `candidate_generation_miss` / `promotion_blocked` / `safe_resolved` / `hold_unresolved` shadow 범주로 분해했다.
  - [x] `cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title` 123건을 precision regression seed로 묶었다.
  - [x] `official_title_lint`와 `identity_consistency_lint`를 shadow/dry-run 모드로 산출했다.
  - [x] `candidate_ledger` shadow artifact를 생성했다.
  - [x] 24건 `expert_main` canary를 실제 실행하고 manifest-scope compare 기준 run integrity `GO`, semantic quality `REVIEW-LOCKED`를 확인했다.
  - [x] `out/expert_result_20260612_174715_296791_checkpoint.jsonl`에서 기존 canary의 image URL 누락 18건을 모두 복원해 source-enriched VLM/OCR canary를 만들었다.
  - [x] `src/llm_batch/candidate_audit.py`와 `expert_main.py` output instrumentation으로 pipeline result에 `candidate_ledger`, `candidate_ledger_status`, promotion/lint flags를 기록한다.
  - [x] source-enriched canary run id `20260615_001642_376095`를 실행했다. completed/flushed/pending/failed `24/24/0/0`, `image_post_count=18`, VLM/OCR semantic gate `READY`, runtime contract `GO`.
  - [x] source-enriched compare 기준 expected/result/compared `24/24/24`, missing `0`, run integrity `GO`, semantic quality `REVIEW-LOCKED`를 확인했다.
  - [x] 기존 canary와 겹치지 않는 source-backed high-risk expansion 36건을 생성했다. group count `recall=12`, `precision=16`, `hygiene=8`, image post `36`, source restore missing `0`.
  - [x] high-risk expansion run id `20260615_012056_067394`를 실행했다. completed/flushed/pending/failed `36/36/0/0`, effective parallel `36`, MCP health `8/8`, `image_post_count=36`, VLM/OCR semantic gate `READY`, runtime contract `GO`.
  - [x] high-risk compare 기준 expected/result/compared `36/36/36`, missing `0`, after labels `safe_resolved=7`, `promotion_blocked=12`, `hold_unresolved=3`, `output_consistency_lint=8`, `identity_consistency_lint=5`, `official_title_lint=1`을 확인했다.
  - [x] high-risk expansion에서 새로 드러난 slang DB 저정보 alias 오염(`novel -> novel.munpia.com`, `dc -> 내가 주인공인 줄 알았다`, `그리고 -> 괴담에 휘말린 피해자가 되었다`)을 `src/llm_batch/slang_db.py` guard로 차단했다.
  - [x] slang guard focused canary run id `20260615_021205_542965`를 실행했다. 3/3 completed, `image_post_count=3`, VLM/OCR `READY`, finalize flush `buffered_observations=0`, runtime contract `GO`.
  - [ ] Deep Research 재실행 응답의 P0 quick wins를 기존 candidate-ledger/promotion-policy 설계에 통합하되, "검증된 Deep Research"가 아니라 보조 분석 근거로만 사용한다.
  - [x] 이 head slice judge를 모집단 오류율/품질 승인으로 환산하지 않고, 후속 random/high-risk expansion 전까지 진단 seed로만 사용한다.
  - [x] 원본 image URL이 빠진 judge-context canary의 한계를 보완하기 위해 source-enriched VLM/OCR canary를 별도로 만들었다.
  - [x] shadow artifact를 실제 pipeline-level candidate ledger / promotion policy instrumentation으로 연결했다.
  - [x] URL/domain/platform label이 `official_title`로 남는 경우를 `src/llm_batch/candidate_audit.py`의 promotion guard에서 demote하고, 차단된 표면은 `blocked_official_title` / `promotion_blocked_reasons` / `candidate_ledger`에 보존했다.
  - [x] domain/lint focused canary run id `20260615_105502_850042`를 실행했다. expected/result/compared `15/15/15`, `11663514`는 `official_title=null`, after labels `promotion_blocked=4`, `identity_consistency_lint=3`, `output_consistency_lint=8`, runtime contract `GO`.
  - [x] source-backed random50 baseline을 `--parallel 32`로 재실행했다. run id `20260615_120734_501402`, completed/failed `50/0`, `image_post_count=30`, VLM/OCR `READY`, runtime contract `GO`, domain/URL official title 재발 `0`.
  - [x] remaining lint focused follow-up에서 `11634549`, `11657028`, `11673108` precision rows는 judge-seed-only promotion guard로 `promotion_blocked`에 내리고 후보 ledger를 보존했다.
  - [x] remaining lint focused follow-up에서 title_noisy_ocr 중 `11605540`, `11628058`, `11629688`은 official search title support 기준 `safe_resolved`, `11602334`는 `hold_unresolved`로 정리했다.
  - [x] `title_noisy_ocr` safe 판정이 `primary_work` self-claim만 믿지 않도록 보강했다. `11636134`처럼 platform search title과 final title이 다르면 `output_consistency_lint`로 남긴다.
  - [x] control `11639284`는 single rerun id `20260615_194903_574111`로 1/1 completed/flushed, runtime contract `GO`를 확인했다. 기존 15건 run `20260615_165906_220298` 자체는 historical `NO-GO`로 유지한다.
  - [x] `title_noisy_ocr` row `11636134`는 image explicit title + official platform search same URL 근거가 일치할 때만 `official_title`을 재정렬하는 guard로 `safe_resolved` 처리했다.
  - [x] combined15 compare 기준 expected/result/compared `15/15/15`, missing `0`, after labels `safe_resolved=4`, `promotion_blocked=7`, `hold_unresolved=1`, `output_consistency_lint=3`을 확인했다.
  - [x] 5개 target/control post_id evidence packet을 `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_manual_evidence_packets.json` / `_ko.md`로 남겼다.
  - [x] continuous improvement loop에서 open/control 9건을 source-backed targeted canary로 재실행했다. run id `20260615_231925_533889`, expected/result/compared `9/9/9`, `image_post_count=9`, VLM/OCR `READY`.
  - [x] 9건 run은 completed/flushed/pending/failed `9/9/0/0`였지만 Deliberation prompt rebuild `NameError: disc` fallback이 있어 runtime audit을 `NO-GO`로 재분류했다.
  - [x] `src/llm_batch/experts/deliberation.py`의 Jury prompt rebuild에서 discourse output을 복원하도록 고쳤고, `tests/test_arbiter_curated_alias_guard.py`에 회귀 테스트를 추가했다.
  - [x] `tools/audit_goal_test_run_contract.py`가 `Traceback`, `NameError`, `Deliberation 오류`를 `runtime_log_exception`으로 잡도록 보강했다.
  - [x] runtime fix verification `11639284` 단건 rerun id `20260615_234526_746998`는 completed/flushed/pending/failed `1/1/0/0`, runtime audit `GO`, compare `promotion_blocked`다.
  - [x] `title_noisy_ocr` seed에서 official URL이 있어도 direct image title과 final public title이 충돌하면 public `official_title`을 hold하는 `apply_judge_seed_title_image_mismatch_guard()`를 추가했다.
  - [x] `11632915`은 public title promotion을 보류해 `hold_unresolved`로 전환했고, 후보는 `candidate_ledger`에 보존한다.
  - [x] `11650591`은 9건 run에서 `주관적인 모바일 앱` 과승격이 드러났고, post-patch 단건 rerun id `20260616_000415_830530`에서 public title을 비워 `hold_unresolved`로 전환했다. runtime audit `GO`.
  - [x] summary artifact: `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_summary.json`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_summary_ko.md`.
  - [ ] 남은 target semantic/output review는 `11602367` wrong_relevance다. `11632915`, `11650591`은 semantic accept가 아니라 public-title overpromotion blocker가 hold로 전환된 상태다.
  - [ ] random50은 small baseline일 뿐이다. source-enriched/high-risk/focused/random evidence 모두 full scan approval로 승격하지 않고 semantic quality는 `REVIEW-LOCKED`로 유지한다.

## 2026-06-13 dashboard UX handoff follow-up

- 상태: implemented / browser-smoked / follow-up open
- 완료:
  - [x] Claude 중단 TODO를 인계받아 dashboard 검색/관련성 필터, 필터 중 SSE restore guard, 상세 모달 JSON 복사 fallback을 보강했다.
  - [x] 전문가 2축 검토에서 confirmed issue를 재현 가능한 코드 위치 기준으로 통합했다.
  - [x] inline script parse와 `tests.test_dashboard_standalone` `26`건 `OK`를 확인했다.
  - [x] standalone dashboard `127.0.0.1:18099` Browser smoke에서 검색/필터 row, 상세 모달, JSON 버튼 클릭, history/live tab 전환, app console error `0`을 확인했다.
- 남은 작업:
  - [ ] `scratch/e2e_dashboard_ui.py`는 API smoke 성격이므로 실제 브라우저 UI E2E로 승격하려면 별도 Playwright/Browser 시나리오를 추가한다.
  - [ ] Tailwind CDN production warning은 local Tailwind build pipeline 전환 시 닫는다.

## 2026-06-02 v527 v284 residual 21-post rerun / issue-focused scope correction

- 상태: runtime contract GO / reason hygiene clean / v528 후속 기준 잔여 HOLD 1건 / 10만 semantic approval REVIEW-LOCKED
- 범위:
  - [x] 현재 goal은 10만 건 semantic approval이 아니라, 10만/partial/source review에서 간추린 known-bad/high-risk seed closure로 취급한다.
  - [x] v284 입력은 raw JSONL `98`줄이지만 실행 단위는 unique/selected post `21`개로 본다.
  - [x] `36`은 Gemma 4 4B worker 상한이며, 이번 run의 effective worker는 `21`이다.
- 완료:
  - [x] `tools/preflight_expert_rerun_runtime.py`가 raw row 수보다 manifest `selected_post_count`/unique post 수를 우선해 execution input count를 계산하도록 보강했다.
  - [x] focused preflight test에서 4 JSONL rows / 2 unique posts / selected post 2개일 때 required shard가 `2`로 줄어드는 것을 확인했다.
  - [x] v527 preflight는 LLM `GO`, MCP effective `GO`, rerun `GO`, full shard `NO-GO(32/36)`로 분리됐다.
  - [x] `v284_residual_p0p1_core21_input.jsonl`을 `--parallel 36 --reuse-shards-only --vlm on --ocr on --require-vlm-ocr-for-images`로 재실행했다.
  - [x] run id `20260602_014729_612198`은 completed/flushed/pending/failed `21/21/0/0`, VLM/OCR ready, Docker lifecycle auto up/recreate `false`다.
  - [x] runtime contract audit `GO`, reason hygiene hit `0`, semantic coverage `REVIEW`를 남겼다.
  - [x] after-review label은 `ACCEPT=19`, `REPROCESS=1`, `HOLD=1`이다.
- 남은 작업:
  - [x] `11718099`는 v528 후속 2건 canary에서 공식/detail 근거와 browser visual evidence로 `ACCEPT/no_action`으로 닫았다.
  - [ ] `11718094`는 작품 장면 출처가 미확정이라 `HOLD/human_review`로 남긴다.
  - [ ] v527 issue-focused closure를 10만 semantic approval로 승격하지 않는다.

## 2026-06-02 v528 remaining 2 seed follow-up

- 상태: targeted residual follow-up complete / v529 issue-focused queue GO / 10만 semantic approval REVIEW-LOCKED
- 완료:
  - [x] v527에서 남은 `11718099`, `11718094`만 `v528_remaining_review_11718099_11718094_input.jsonl`로 분리했다.
  - [x] raw row `7`, unique post `2`로 preflight `GO`를 확인했다.
  - [x] `--parallel 36` max, effective parallel `2`, `--reuse-shards-only`, VLM/OCR on으로 실행했다.
  - [x] runtime contract audit `GO`, reason hygiene hit `0`, semantic coverage `GO`를 확인했다.
  - [x] browser visual required/available/missing `2/2/0`, image catalog present/missing `2/0`을 확인했다.
  - [x] after-review는 `ACCEPT=1`, `HOLD=1`이다.
  - [x] `11718099`는 `빌어먹을 환생`, official/detail URL, browser visual artifact, `빌환` slang alias로 정합해 `ACCEPT/no_action`으로 닫았다.
- 남은 작업:
  - [x] `11718094`는 `예세르`/`아르타` 장면 OCR은 있으나 공식 title 출처가 없어 v529에서 `HOLD/no_action`, `close_as_unresolved`로 수동 리뷰 완료했다.
  - [ ] 이 2건 canary coverage `GO`를 10만 semantic approval로 승격하지 않는다.

## 2026-06-02 v529 11718094 manual unresolved closure

- 상태: issue-focused seed queue GO / row-level HOLD retained / 10만 semantic approval REVIEW-LOCKED
- 완료:
  - [x] `11718094` browser visual artifact와 VLM/OCR image evidence를 다시 확인했다.
  - [x] `에세르/예세르`, `아르타`, exact OCR phrase 계열 검색이 공식 작품 detail로 연결되지 않음을 확인했다.
  - [x] `11718094`는 작품 장면 가능성은 있지만 작품명 확정 근거가 없는 `unresolved_matchable` boundary case로 보존했다.
  - [x] 수동 리뷰 결과를 `v529_11718094_manual_review_label.jsonl`과 `v529_11718094_manual_review_closure_ko.md`에 남겼다.
  - [x] final gate를 `v529_issue_focused_final_gate_ko.md`에 남겼다.
- 남은 작업:
  - [ ] `11718094`를 임의 title/alias로 승격하지 않는다.
  - [ ] issue-focused seed queue `GO`를 10만 semantic approval로 승격하지 않는다.

## 2026-06-02 v526 issue-focused browser visual closure

- 상태: targeted seed browser visual HOLD closed / issue-focused GO / 10만 semantic approval REVIEW-LOCKED
- 완료:
  - [x] Codex 내장 Browser plugin / in-app browser iab 연결을 먼저 시도했고, 현재 세션에서는 browser runtime setup 실패로 blocked evidence를 남겼다.
  - [x] 대체 브라우저 경로로 `11718069`, `11718076` 원문 페이지를 열고 full-page screenshot/snapshot 및 direct capture eval을 남겼다.
  - [x] `11718069`은 direct CLI counter가 `0/1` Weak였지만 Playwright MCP full-page screenshot에서 본문 이미지가 렌더링되어, counter conflict와 직접 시각 증거를 분리 기록했다.
  - [x] `11718076`은 direct Playwright eval에서 article image `1/1` loaded로 확인했다.
  - [x] `v526_browser_visual_after_review_labels.jsonl`에서 두 건을 `ACCEPT/no_action`으로 닫았다.
  - [x] `v526_combined_browser_visual_artifacts_manifest.json`로 v518 누적 browser artifact에 v526 override를 결합했다.
  - [x] v523 seed coverage sanity에서 browser visual required/available/missing `6/6/0`을 확인했다.
- 남은 작업:
  - [ ] v523 원본 artifact의 `11718083` image catalog missing은 v524 단건 재런으로 supersede된 상태를 유지한다. 구 artifact audit의 잔여 issue로 재오픈하지 않는다.
  - [x] v284 98-row expansion deferred 문구는 v527에서 정정했다. raw row `98`은 댓글 포함 입력 줄 수이고 실행 단위는 selected post `21`개다.
  - [ ] 이 issue-focused GO를 random baseline/P0P1 expansion 없는 10만 semantic approval로 승격하지 않는다.

## 2026-06-02 v522 11718080/11718082 live canary

- 상태: targeted known-bad canary recovered / runtime GO / coverage GO / semantic approval REVIEW-LOCKED
- 완료:
  - [x] 원격 vLLM endpoint `10.20.0.101:8000`과 model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` readiness를 확인했다.
  - [x] Docker compose 권한이 없어도 TCP preflight 기준 small canary effective shard `2`개가 열린 것을 확인했다. full 36 shard는 `32/36`으로 `NO-GO`다.
  - [x] `11718080`, `11718082` 2건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on --require-vlm-ocr-for-images`로 재실행했다.
  - [x] runtime audit `GO`, reason hygiene `GO`, semantic coverage with browser `GO`를 남겼다.
  - [x] `11718080` old result의 `소보로설` overresolve가 재발하지 않음을 확인했다.
  - [x] `11718082`는 VLM/OCR catalog/counter와 browser visual artifact가 함께 있는 상태로 resolved를 확인했다.
  - [x] 자연어 label `ACCEPT=2`, action `no_action=2`를 남겼다.
- 남은 작업:
  - [ ] full 36-shard readiness는 Docker 접근 권한 복구 또는 TCP open `36/36`으로 별도 확인한다.
  - [ ] 2건 canary를 10만 semantic approval로 승격하지 않는다.
  - [ ] completed VLM/OCR-on source 확보, random baseline 1000건, P0/P1 high-risk expansion 전까지 전체 gate는 `REVIEW-LOCKED`다.

## 2026-06-01 v519 direct Playwright browser evidence recovery

- 상태: direct browser capture patched / original result visual coverage improved to 37/25/12 / semantic approval REVIEW-LOCKED
- 완료:
  - [x] `playwright-cli eval --filename` 파일이 없으면 stdout JSON을 회수해 `.eval.json`으로 남긴다.
  - [x] `npx.cmd`/daemon이 불안정할 때 설치된 Chromium revision이 있는 cached `node_modules`를 찾아 direct Node Playwright fallback으로 캡처한다.
  - [x] DC UI의 일반 `차단` 단어를 blocked evidence로 오탐하지 않게 했다.
  - [x] v515 completed subset 16건 캡처 결과 `Strong=10`, `Weak=5`, `Missing=1`을 남겼다.
  - [x] v506 completed subset audit을 `browser_visual_required/available/missing=16/10/6`으로 재산출했다.
  - [x] 원본 71행 기준 누적 v518 manifest를 만들고 v519 audit에서 `37/25/12`로 재산출했다.
  - [x] `11718082`는 screenshot과 loading counter `1/1`, pending/broken/incomplete `0`으로 닫혔다.
  - [x] v520 current-state/action queue를 v519 audit 기준으로 재생성했다.
  - [x] action queue의 visual gate evidence에서 unique browser missing count와 blocker signal sum을 분리했다.
- 남은 작업:
  - [ ] 남은 original visual target `12`건을 재시도하거나 image loading failure로 별도 action queue에 묶는다.
  - [ ] 원본 result의 `image_evidence_catalog_missing=37`, `image_ocr_reason_without_public_vlm_counter=34`, comment metadata/dialogue missing을 VLM/OCR-on completed source로 보강한다.
  - [ ] browser `Strong`은 visual evidence일 뿐 semantic ACCEPT가 아니므로 packet별 reason/evidence alignment를 별도 리뷰한다.
  - [ ] expanded random/high-risk semantic review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v510 strict browser artifact gate / Arbiter memory-query guard

- 상태: P0 guard patched / strict browser gate applied / remaining browser targets 16 / semantic approval REVIEW-LOCKED
- 완료:
  - [x] Arbiter `Verifier High-title lock`이 memory-query weak relation-hold에서 title을 되살리는 경로를 차단했다.
  - [x] Arbiter verifier-null restore보다 `memory_query_forced_upgrade_guard`를 먼저 적용한다.
  - [x] external browser artifact는 screenshot/snapshot + grade만으로 통과하지 않고 article image loading counters까지 요구한다.
  - [x] browser target manifest coverage는 0 카운트도 명시한다.
  - [x] v506 completed subset strict gate 재산출 결과 browser visual missing은 `16`건이다.
  - [x] focused Arbiter/browser/audit tests 36건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] 11718049를 포함한 browser visual target `16`건을 `article_image_count`, `article_loaded_count`, pending/broken/placeholder/incomplete counter와 screenshot/observation으로 다시 닫는다.
  - [ ] memory-query/no-work 공통 gate가 Decoder session knowledge, BatchContext rescue, Orchestrator auto search seed에서도 단조적으로 유지되는지 추가 canary를 만든다.
  - [ ] completed source, browser visual artifacts, expanded random/high-risk review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v509 browser attempt failure preserved / Codex subagent 병렬 재확인

- 상태: fallback browser attempt recorded / image loading failed preserved / v510 strict gate supersedes available count / semantic approval REVIEW-LOCKED
- 완료:
  - [x] 이번 병렬 검토를 Codex `spawn_agent` 전문가 병렬로 수행했고, runtime worker `--parallel` 조정과 분리했다.
  - [x] 문서/gate, VLM-OCR-browser, 프롬프트/오케스트레이션 한계 축 subagent를 병렬로 배정했다.
  - [x] Codex in-app Browser 직접 제어 실패를 blocked evidence로 유지했다.
  - [x] fallback Playwright로 `11718068` 원문 URL의 screenshot/snapshot/eval JSON을 남겼다.
  - [x] `11718068` article image가 `article_image_count=1`, `article_loaded_count=0`, `article_incomplete_count=1`이라 visual evidence가 아니라 image loading failure evidence임을 기록했다.
  - [x] v509 attempt manifest를 semantic coverage audit과 browser target builder에 연결해 재산출했다.
  - [x] `11718068`은 target에서 제외하지 않았다. 이후 v510 strict gate에서 11718049도 loading counter 부족으로 target에 복귀해 browser visual target 수는 `16`으로 재산출됐다.
- 남은 작업:
  - [ ] 남은 browser visual target `15`건을 실제 image-loaded visual artifact로 닫는다.
  - [ ] `11718068`류 image loading failure가 반복되면 DC image fetch/session/cookie/referrer 또는 browser wait/retry 경로를 별도 P1로 조사한다.
  - [ ] subagent 프롬프트/오케스트레이션 결과를 받아 no-work/social lament/context-only 공통 선행 게이트 후속 패치를 확정한다.
  - [ ] completed source, browser visual artifacts, expanded random/high-risk review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v508 intent-denied title-present audit / fallback target shrink

- 상태: audit patched / fallback manifest consumed / remaining browser targets 15 / semantic approval REVIEW-LOCKED
- 완료:
  - [x] `intent_permit_for_title_search=false`, `title_resolution_allowed=false`, `context_only/no_work` 신호와 title 공존을 `intent_denied_title_present` issue로 잡도록 semantic coverage audit을 보강했다.
  - [x] `resolved` 상태가 아니어도 `official_title`이 남으면 모순으로 잡는 회귀 테스트를 추가했다.
  - [x] title이 없는 no-work/context-only row는 `intent_denied_title_present`로 오탐하지 않는 회귀 테스트를 추가했다.
  - [x] v507 `fallback_browser` attempt manifest를 semantic coverage audit의 external browser artifact로 읽게 했다.
  - [x] browser visual target builder에 `--browser-artifacts-manifest`를 추가해 fallback 1건을 target에서 제외할 수 있게 했다.
  - [x] v506 completed subset + v507 fallback 기준으로 semantic coverage audit을 재실행했다. browser visual missing은 `16 -> 15`로 줄었다.
  - [x] 남은 browser visual target `15`건을 `v508_remaining_browser_visual_targets.*`로 생성했다.
  - [x] focused audit/target tests 33건, 관련 `py_compile`, v508 JSON validation을 통과했다.
- 남은 작업:
  - [ ] 남은 browser visual target `15`건을 Codex in-app Browser 또는 명시 fallback artifact로 닫는다.
  - [ ] `intent_denied_title_present`가 expanded review에서 발생하면 post intent, direct hard anchor, rescue source를 packet별로 분리한다.
  - [ ] no-work/social lament/context-only를 닫는 공통 선행 게이트를 실제 pipeline search/rescue 경로에 더 강하게 적용하고 live canary로 확인한다.
  - [ ] completed source, browser visual artifacts, expanded random/high-risk review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v507 browser visual target 전수화 / Codex subagent 병렬 재정렬

- 상태: target extraction added / fallback 1건 확인 / Codex in-app Browser blocked / semantic approval REVIEW-LOCKED
- 완료:
  - [x] 이번 `/goal` 병렬을 Codex `spawn_agent` 전문가 병렬로 재정렬했다. `expert_main.py --parallel` worker 병렬과 섞지 않는다.
  - [x] 실행 오케스트레이션, VLM-OCR-browser visual gate, 자연어 이해/프롬프트 한계 축으로 subagent 검토를 분리했다.
  - [x] result JSON에서 browser visual missing target 전체를 생성하는 `tools/build_browser_visual_targets_from_result.py`를 추가했다.
  - [x] audit issue의 sample post 10건 제한 때문에 실제 target 16건이 잘리지 않는지 회귀 테스트를 추가했다.
  - [x] v506 completed subset에서 browser visual target `16`건을 생성했다.
  - [x] Codex in-app Browser 직접 제어가 현재 세션에서 blocked 상태임을 기록했다.
  - [x] fallback Playwright로 `11718049` 1건의 페이지/본문 이미지 screenshot과 snapshot을 남겼다.
  - [x] browser visual attempt manifest와 한국어 summary를 남겼다.
  - [x] 오케스트레이션/VLM-browser/natural-language subagent 결과를 통합 요약으로 남겼다.
  - [x] browser visual target test + semantic coverage audit 29건, 관련 `py_compile`, JSON validation을 통과했다.
- 남은 작업:
  - [ ] Codex in-app Browser 경로가 복구되면 16건 target을 직접 visual artifact로 다시 확인한다.
  - [ ] fallback을 계속 사용할 경우 fallback임을 명시하고 article image counter, screenshot, visible observation, evidence grade를 packet별로 남긴다.
  - [ ] 남은 browser visual target `15`건을 visual artifact로 닫기 전까지 OCR/search/text-only 근거를 Strong으로 승격하지 않는다.
  - [ ] no-work/social lament/context-only 결과가 search/rescue/known alias/session knowledge/Arbiter promotion으로 되살아나지 못하도록 공통 선행 게이트를 적용한다.
  - [ ] image-based resolution은 VLM/OCR direct evidence catalog와 browser image-loading evidence를 함께 요구한다.
  - [ ] comment author/comment id/dialogue context를 `op_confirmation`, `independent_title_answer`, `comment_only_reference`, `unverified_author_match` 같은 evidence role로 정규화한다.
  - [ ] `23센줄`류 오타/축약/말장난은 특정 표현 고정이 아니라 `surface_reread_candidates[]` packet-local reread로 일반화한다.
  - [ ] completed source, browser visual artifacts, expanded random/high-risk review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v506 v504 targeted rerun 중단 감사 / unresolved reason wording 보강

- 상태: interrupted partial recovered / runtime NO-GO / completed subset audited / semantic approval REVIEW-LOCKED
- 완료:
  - [x] v504 seed package 권장 계약으로 VLM/OCR-on targeted rerun을 시작했다.
  - [x] endpoint/model preflight와 shard health를 확인했다. `36` worker 고정이 아니라 `--parallel 24`가 맞다.
  - [x] 사용자 중단 뒤 남은 `expert_main` 계열 Python 프로세스를 정리했다.
  - [x] partial manifest를 감사했다. input `24`, completed `23`, flushed `14`, pending `9`, failed `0`.
  - [x] checkpoint/pending snapshot에서 completed subset `23`개를 복구했다.
  - [x] completed subset semantic coverage를 실행했다. image catalog/comment metadata 공백은 닫혔지만 browser visual missing `16`으로 `REVIEW-LOCKED`.
  - [x] reason hygiene hit의 원인이 unresolved relevant reason 템플릿 문구임을 확인했다.
  - [x] `_format_unresolved_relevant_reason()`의 stale phrase를 낮춘 문구로 교체하고 회귀 테스트를 추가했다.
  - [x] focused sanitize/reason/semantic coverage 31건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] v504 rerun은 full completion이 아니므로 같은 output을 GO 근거로 쓰지 않는다.
  - [ ] pending post 1개 또는 전체 v504 seed를 재실행할 때는 output path를 새로 잡아 old partial과 섞지 않는다.
  - [ ] browser visual required 대상 16건에 대해 Codex in-app Browser 또는 명시 fallback artifact를 확보한다.
  - [ ] reason hygiene fix는 future run에서 재확인한다. old partial artifact의 hit는 old output으로 기록한다.
  - [ ] completed source, browser visual artifacts, expanded random/high-risk review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v505 small-run 후속 검토 / adjacent reason wording guard

- 상태: patched / focused validation passed / old v493 artifact REVIEW / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] Codex `/goal` 병렬을 `spawn_agent` 전문가 병렬로 다시 구분했다. `expert_main.py --parallel` worker 수와 섞지 않는다.
  - [x] v493 runtime contract를 재확인했다. requested/effective worker `2/2`, completed/flushed/pending/failed `2/2/0/0`, docker compose 재시작 신호 없음.
  - [x] v494 browser artifact로 `11718082` 이미지 로딩과 작품 표면을 확인했다.
  - [x] `11718080`은 작품 매칭 실패가 아니라 adjacent/social lament + trope discussion으로 판정해야 하는 케이스임을 정성 리뷰로 분리했다.
  - [x] 기존 v493 reason의 `주변 관련` + `비관련 포스트` 혼합을 `adjacent_reason_non_relevant_wording_conflict` audit issue로 노출했다.
  - [x] `_sanitize_reason()`이 adjacent/trope류에서 `비관련 포스트` 단정 문구를 붙이지 않도록 보강했다.
  - [x] focused sanitize 회귀 3건과 semantic coverage audit 전체 28건을 통과했다.
- 남은 작업:
  - [ ] v493 기존 산출물은 old artifact라 `11718080` reason wording issue 때문에 REVIEW/HOLD로 기록한다.
  - [ ] `11718082`류 OCR 오타 표면은 alias/slang 고정 규칙으로 저장하지 말고 packet-local VLM/OCR evidence로만 다룬다.
  - [ ] 다음 completed VLM/OCR-on rerun에서 adjacent/trope/social lament bucket을 high-risk expansion에 포함한다.
  - [ ] completed source, expanded random baseline, P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v504 Codex subagent 병렬 재정렬 / 다음 seed package

- 상태: seed package generated / subagent review running / semantic approval still REVIEW-LOCKED
- 완료:
  - [x] 이번 라운드의 병렬 작업을 Codex `spawn_agent` 전문가 병렬로 다시 고정했다. `expert_main.py --parallel` worker 증설과 섞지 않는다.
  - [x] goal 문서/오케스트레이션, small-run/runtime 계약, VLM/OCR/browser visual gate를 독립 subagent 축으로 나눴다.
  - [x] `tools/build_goal_next_seed_package.py`와 `tests/test_goal_next_seed_package.py`를 추가했다.
  - [x] current semantic coverage audit의 issue sample post를 v504 다음 실행 seed로 변환했다.
  - [x] v504 seed package는 target post `28`, rerun post `24`, rerun row `86`, browser target `28`, browser visual required `11`을 기록한다.
  - [x] 권장 rerun `--parallel`은 입력 post 기준 `24`로 계산했다. `36`은 Gemma 4 4B runtime worker 상한이며 small run에서 36 worker를 채우기 위해 재실행하지 않는다.
  - [x] `_effective_parallel_for_post_count()` 직접 회귀와 stale `MCP_SHARD_COUNT=36` small-run health budget 회귀를 추가했다.
  - [x] `.gitignore` 예외에 v504 tool/test 파일을 추가해 follow-up 검증 파일이 추적 가능하게 했다.
  - [x] `README.md`/`expert_readme.md`의 `병렬 실행` 절에 Codex `spawn_agent` 병렬과 repo runtime worker 병렬 구분 주석을 추가했다.
  - [x] Codex in-app Browser 연결 초기화 실패로 이번 라운드 visual artifact는 생성하지 못했고, browser evidence는 Missing/blocked로 유지한다.
  - [x] `tests.test_goal_next_seed_package`, `tests.test_expert_main_input_loader`, 관련 `py_compile`, v504 manifest JSON validation을 통과했다.
- 남은 작업:
  - [ ] v504 rerun을 LLM 서버/VLM/OCR on 기준으로 실행한다.
  - [ ] rerun manifest에 대해 `audit_goal_test_run_contract.py --fail-on-no-go`를 실행한다.
  - [ ] rerun result에 대해 semantic coverage audit과 reason hygiene scan을 실행한다.
  - [ ] Codex in-app Browser 또는 명시된 fallback으로 browser image-loading artifact를 확보한다. fallback을 쓰면 Codex in-app Browser evidence와 구분해 기록한다.
  - [ ] completed VLM/OCR-on source, Browser image-loading gate, random 1000+, P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v503 Codex subagent 병렬 통합 / image URL alias / known abbreviation title guard

- 상태: patched / focused+expanded validation passed / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` subagent 3축으로 semantic/orchestration, VLM/OCR/browser, goal docs/runtime 계약을 병렬 감사했다.
  - [x] 원본 `20260528_141006_620986` source를 현재 audit tool로 재확인했고 partial/regression seed 상태를 유지했다.
  - [x] `content_blocks` dict의 `url`, `image_url`, `src`를 모두 `ContentBlock.url`로 보존해 VLM/OCR image gate가 image post를 놓치지 않게 했다.
  - [x] public content block/image URL serialization도 `image_url`/`src` alias를 보존한다.
  - [x] `_apply_known_abbreviation_title_guard()`가 no-work/context-only 공통 gate를 통과해야만 title rewrite를 수행한다.
  - [x] stale `--parallel 36` 문구를 새 소규모 명령 `--parallel min(input_count,36)`와 완료된 p36 run의 `effective_parallel` 계약으로 분리했다.
  - [x] 추가 Codex `spawn_agent` 3축(Peirce/Dalton/Wegener) 재확인으로 GO 과승격 없음, remaining P2 wording/docs cleanup, reason/comment/search-only blocker 유지 상태를 확인했다.
  - [x] 과거 이력의 future-facing `--parallel 36` 문구와 영어 heading을 한국어/상한/effective_parallel 계약으로 정리했다.
  - [x] known abbreviation guard 주석의 "하드코딩/고정" 표현을 curated registry 기반 evidence-aware rewrite 후보로 정정했다.
  - [x] focused image loader/comment metadata 41건, known abbreviation 16건, 관련 `py_compile`을 통과했다.
  - [x] 관련 확장 회귀 묶음 167건, broader `py_compile`, `git diff --check`를 통과했다. `git diff --check` 출력은 CRLF 경고뿐이다.
- 남은 작업:
  - [ ] Decoder `_rescue_null_title` 계열 known abbreviation confidence는 후단 gate가 막는지 expanded high-risk bucket에서 확인한다.
  - [ ] completed VLM/OCR-on source, Browser image-loading gate, random 1000+, P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v502 P2 late rescue 후보 공통 gate 마감

- 상태: patched / focused+expanded validation passed / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] `direct_full_title_candidate_rescued`에 no-work/context-only 공통 gate를 연결했다.
  - [x] `post_main_official_url_title_recovered_from_null`에 no-work/context-only 공통 gate를 연결했다.
  - [x] `direct_image_explicit_title_rescued`에 no-work/context-only 공통 gate를 연결했다.
  - [x] `batch_memory_exact_alias_rescued` 후보 반환 전에 no-work/context-only 공통 gate를 연결했다.
  - [x] late rescue static coverage expected source 목록을 확장했다.
  - [x] focused 23건, VLM counter 포함 24건, 확장 회귀 125건, 관련 파일 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] completed VLM/OCR-on source에서 위 source들을 high-risk expansion bucket에 포함해 실제 재발률을 확인한다.
  - [ ] 10만 semantic approval은 completed source, Browser image-loading gate, random 1000+, P0/P1 high-risk expansion 전까지 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v501 late rescue 추가 P1 / image loading text-match gate

- 상태: patched / focused+expanded validation passed / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] McClintock subagent의 추가 P1 후보 `short_alias_spoiler_recovered`, `multi_work_placeholder_collapsed`, canonical rescue lock을 공통 gate에 묶었다.
  - [x] Mill subagent의 VLM/OCR/browser 제안대로 이미지 로딩 실패/대기 + 텍스트/OCR/search 매칭 사용을 `image_loading_failed_or_pending_text_match_used` issue로 노출했다.
  - [x] focused title gate 23건, semantic coverage audit 27건, 확장 회귀 125건, 관련 파일 `py_compile`을 통과했다.
- 남은 작업:
  - [x] `direct_full_title_candidate_rescued`, `post_main_official_url_title_recovered_from_null`, `direct_image_explicit_title_rescued`, `batch_memory_exact_alias_rescued`는 v502에서 공통 gate와 static coverage를 연결했다.
  - [ ] `browser_loading_complete`, `visual_artifact_linked`, `visual_semantic_alignment` 3단계 표기를 gate report에 더 넓게 반영한다.
  - [ ] completed VLM/OCR-on source에서 `image_loading_failed_or_pending_text_match_used` bucket을 high-risk expansion에 포함한다.
  - [ ] 10만 semantic approval은 completed source, Browser image-loading gate, random 1000+, P0/P1 high-risk expansion 전까지 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v500 Codex subagent 병렬 재확인 / structural-comment rescue gate 확장

- 상태: patched / focused+expanded validation passed / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] 사용자 정정에 맞춰 Codex `/goal` 병렬을 `expert_main.py --parallel`이 아니라 실제 `spawn_agent` 전문가 병렬로 다시 수행했다.
  - [x] code gate, goal/runtime docs, VLM/OCR/browser gate 읽기 전용 subagent를 별도 축으로 띄웠다.
  - [x] structural title rescue가 no-work/context-only 후단 block을 우회하지 못하도록 공통 gate를 연결했다.
  - [x] comment title answer, comment plot answer, character parenthetical, character page title rescue도 `_can_promote_title_after_semantic_no_work()`를 통과해야 한다.
  - [x] session knowledge context-only/no-work 학습 차단 회귀를 추가했다.
  - [x] focused 23건, 관련 확장 회귀 125건, 관련 파일 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] `_has_direct_post_or_visual_work_anchor_for_no_work_search_rescue()`를 hard direct anchor와 contextual support helper로 분리해 명명/계약 혼선을 줄인다.
  - [ ] completed VLM/OCR-on source에서 structural/comment/character rescue source를 P0/P1 high-risk expansion bucket에 포함한다.
  - [ ] Codex subagent 최종 보고는 메인 Codex가 파일/line/post_id/run_id 근거로 재확인한 뒤 gate에 반영한다.
  - [ ] 10만 semantic approval은 completed source, Browser image-loading gate, random 1000+, P0/P1 high-risk expansion 전까지 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v499 subagent 병렬 재점검 / late promotion gate 확장

- 상태: patched / focused validation passed / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 기반으로 runtime/result, code-path, docs/checklist 축을 병렬 재점검했다.
  - [x] 원본 `20260528_141006_620986` result가 partial/regression seed이며 completed 10만 approval source가 아님을 다시 확인했다.
  - [x] `_semantic_seed_no_work_signal()`이 ARBITER `final_decision`만 남은 `title_resolution_allowed=false` / `context_only` 신호도 읽도록 했다.
  - [x] stable-hold canonical rescue가 strict packet-local anchor 없이 no-work/context-only block을 다시 풀지 못하게 했다.
  - [x] question-title official URL, locked official candidate, title-surface primary, short-support anticipation, generic-relation alias, comment URL answer recovery에 공통 no-work promotion gate를 연결했다.
  - [x] session knowledge learning이 no-work/context-only + direct anchor 없음 결과를 전역 alias/knowledge로 학습하지 않도록 했다.
  - [x] 후단 rescue path 공통 gate 회귀와 ARBITER final_decision-only 회귀를 추가했다.
- 남은 작업:
  - [x] 관련 확장 회귀 묶음 124건과 관련 파일 `py_compile`을 다시 실행했다.
  - [ ] completed VLM/OCR-on source에서 `context_only_late_rescue_without_direct_anchor`, `decoder_alias_official_url_late_promotion`, `comment_url_answer_recovered`, `stable_hold_canonical_rescue` bucket을 P0/P1 expansion으로 재검토한다.
  - [ ] 이번 subagent manifest가 v499부터 남았으므로 v497 이전 subagent evidence는 missing artifact로 표시하고, 다음 라운드부터 manifest/summary를 필수 산출물로 유지한다.
  - [ ] 10만 semantic approval은 completed source, Codex Browser image-loading gate, random 1000+, P0/P1 high-risk expansion 전까지 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v497 no-work/context-only 공통 후단 승격 게이트

- 상태: patched / focused validation passed / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] Codex subagent 코드 경로 reviewer가 최종 검증기, 후보 승격, unresolved 단일 후보 승격, recommendation guard 해제에 남은 후단 rescue 위험을 확인했다.
  - [x] semantic no-work/context-only 이후 title promotion/rescue를 `_can_promote_title_after_semantic_no_work()` 공통 gate로 묶었다.
  - [x] `_has_direct_work_anchor_for_no_work_rescue()` semantic 분기에서 Decoder alias 기반 `_title_mentioned_in_post_main_context()`와 official URL 의존을 제거하고 strict packet-local anchor만 보도록 축소했다.
  - [x] `_compute_title_acceptance()`에서 no-work/context-only + direct anchor 없음이면 `semantic_no_work_block=true`, `decision=reject`로 고정했다.
  - [x] `_try_promote_best_candidate()`와 `_pick_safe_single_candidate_unresolved_promotion()`이 official URL/Decoder alias만으로 no-work를 되살리지 못하게 했다.
  - [x] `_context_to_output()` recommendation guard override와 irrelevant canonical rescue block에서 episode ref 단독이 no-work를 열지 못하게 했다.
  - [x] Decoder alias + official URL + episode ref 조합, 후보 promotion, single-candidate promotion, direct image positive path 회귀를 추가했다.
- 남은 작업:
  - [ ] final validator canonical/deliberation rescue를 end-to-end result row 기준으로 한 번 더 expanded high-risk bucket에서 확인한다.
  - [ ] `context_only_late_rescue_without_direct_anchor` bucket에 `decoder_alias_official_url_late_promotion` 하위 태그를 붙여 P0/P1 expansion에 포함한다.
  - [ ] 10만 semantic approval은 completed VLM/OCR-on source, random 1000+, P0/P1 high-risk expansion 전까지 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v496 no-work/context-only late rescue gate

- 상태: patched / focused validation passed / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] `11718080`류 no-work/context-only 이후 후단 `search_evidence_alias_inference`/BatchContext rescue가 official detail URL만으로 title을 되살릴 수 있는 경로를 확인했다.
  - [x] `_search_inferred_alias_nonwork_block_reason()`이 no-work/context-only 상태에서는 `_has_official_title_evidence()`를 direct hard anchor로 보지 않도록 수정했다.
  - [x] `verification_result.title_resolution_state=context_only` 또는 `title_resolution_allowed=false`처럼 discourse 원본 없이 공개 final field만 남은 no-work도 차단 신호로 읽도록 보강했다.
  - [x] official URL이 있어도 direct post/visual work anchor가 없으면 `semantic_seed_no_work_context`로 막는 회귀를 추가했다.
  - [x] 직접 이미지 작품 표면이 있는 `11718082`류 positive path는 계속 허용되는 회귀를 추가했다.
  - [x] `SCAN_RESULT_REVIEW_GUIDE.md`, `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `OPERATION_QUALITY_CHECKLIST.md`에 `context_only_late_rescue_without_direct_anchor` bucket/gate를 기록했다.
- 남은 작업:
  - [ ] `context_only_late_rescue_without_direct_anchor`를 high-risk expansion bucket으로 뽑아 P0/P1 범위에서 반복 여부를 확인한다.
  - [ ] 10만 semantic approval은 completed VLM/OCR-on source, random 1000+, P0/P1 high-risk expansion 전까지 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v495 Codex goal subagent 병렬 운영 재정렬

- 상태: guidance patched / subagent round used / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] 사용자 정정을 repo `expert_main.py --parallel` 조정이 아니라 Codex `/goal`의 `spawn_agent` 전문가 병렬 운영 요구로 재해석했다.
  - [x] 이번 라운드에서 `docs/guidance`, `VLM/browser coverage`, `subagent operation model`을 별도 subagent로 병렬 검토하고 모두 종료했다.
  - [x] `SCAN_RESULT_REVIEW_GUIDE.md`에 "여러 전문가/병렬 검토" 요청 시 먼저 Codex `spawn_agent` 축을 선언하고 실제 subagent를 배정한다는 실행 의무를 강화했다.
  - [x] `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`와 `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`에 subagent 부족을 `expert_main.py --parallel` 재실행으로 대체하지 않는다고 명시했다.
  - [x] `OPERATION_QUALITY_CHECKLIST.md`와 `CHECKLIST.md`에 과거 36워커 기록은 runtime 이력이며 Codex goal subagent 병렬 지침으로 해석하지 않는 가드를 추가했다.
  - [x] v493은 VLM/OCR public counter 공백을 닫았고, v494는 Browser visual artifact linkage 공백을 닫았다는 경계를 다시 기록했다.
- 남은 작업:
  - [ ] 다음 대형 review goal에서는 시작 보고에 `spawn_agent_axes`, subagent별 read/write scope, 최종 통합자 gate 책임을 먼저 남긴다.
  - [x] `11718080`류 no-work/context-only 이후 후단 search/alias/BatchContext rescue가 direct anchor 없이 resolved로 뒤집히지 않는 단일 promotion gate를 계속 검토한다. v496에서 targeted gate와 회귀를 추가했다.
  - [ ] completed VLM/OCR-on source, random 1000+, P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v494 Browser visual artifact linkage

- 상태: targeted browser artifact linked / semantic coverage audit GO / 10만 semantic approval still REVIEW-LOCKED
- 완료:
  - [x] `11718082` 원문 페이지를 Browser fallback으로 열고 본문 이미지가 실제 로드된 screenshot/snapshot을 남겼다.
  - [x] `browser_visual_v494/v494_browser_visual_manifest.json`에 `attempted_in_app_browser=true`, fallback reason, screenshot/snapshot, image loading counters, visual observation을 기록했다.
  - [x] v494 semantic coverage audit에 browser artifact manifest를 연결했고 `browser_visual_available=1`, `browser_visual_missing=0`, issues `[]`, coverage `GO`를 확인했다.
  - [x] 관찰상 이미지에는 `재벌가 차녀의 2회차 걸그룹`, `유은우`, `267화`, KakaoPage 화면이 보여 `11718082` resolved title을 직접 지지한다.
- 남은 작업:
  - [ ] `node_repl` 기반 Codex in-app Browser bootstrap 실패(`windows sandbox failed: spawn setup refresh`)는 별도 환경 이슈로 남긴다. 이번 artifact는 fallback 사용으로 표시했다.
  - [ ] v494 coverage `GO`는 2건 targeted canary의 public evidence coverage sanity일 뿐이다. random 1000/P0P1 expansion 전까지 10만 semantic approval로 승격하지 않는다.
  - [ ] `11718080`류 no-work/context-only 이후 후단 search/alias/BatchContext rescue가 direct anchor 없이 resolved로 뒤집히지 않는 단일 promotion gate를 검토한다.

## 2026-06-01 v493 VLM/OCR public counter result schema 보강

- 상태: patched / live canary passed / runtime GO / semantic coverage still REVIEW-LOCKED
- 완료:
  - [x] `PickvelIdentity`에 VLM/OCR 실행 counter 공개 필드를 추가했다.
  - [x] `_context_to_output()`에서 `ctx.post_data`의 `vlm_enabled`, `ocr_enabled`, `vlm_enrichment_used`, `image_fetch_count`, `image_fetch_success`, `vlm_chunks_sent`, `vlm_total_bytes`, `image_enrichment_limitations`를 public identity로 조인한다.
  - [x] 비이미지 row에는 0 counter noise를 뿌리지 않고, 이미지 block/enrichment/limitation/counter 신호가 있을 때만 공개한다.
  - [x] v493 live canary에서 `11718082` identity에 `image_fetch_count=1`, `image_fetch_success=1`, `vlm_chunks_sent=1`, `vlm_total_bytes=28264`가 남는 것을 확인했다.
  - [x] v493 semantic coverage audit에서 `image_catalog_present_but_vlm_counter_missing=0`, `image_ocr_reason_without_public_vlm_counter=0`으로 해소됐다.
  - [x] `tests.test_agentic_pipeline_rework.AgenticPipelineVLMTest`, `tests.test_semantic_coverage_audit`, `tests.test_goal_test_run_contract_audit` 총 60건 OK.
- 남은 작업:
  - [x] Browser visual/direct evidence artifact linkage가 아직 없어 `browser_visual_or_direct_evidence_missing=1`로 semantic coverage는 `REVIEW-LOCKED` 유지. v494에서 targeted artifact로 닫음.
  - [x] Codex in-app Browser artifact manifest를 result/review packet에 연결해 Browser visual gate를 닫는다. v494에서 fallback artifact manifest로 닫음.
  - [ ] `11718080`류 no-work/context-only 이후 후단 search/alias/BatchContext rescue가 direct anchor 없이 resolved로 뒤집히지 않는 단일 promotion gate를 검토한다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v492 Subagent 통합 / VLM public evidence 계약 강화

- 상태: audit patched / focused validation passed / runtime GO / semantic coverage REVIEW-LOCKED
- 완료:
  - [x] Codex goal 병렬 검토를 VLM/Browser, Runtime/Goal Contract, Semantic/Pipeline, Docs/Gate subagent 4개 축으로 분리했다.
  - [x] `qualitative_review/20260528_141006_620986/v492_subagent_review_manifest.json`와 `v492_subagent_review_summary_ko.md`에 subagent 역할/범위/메인 통합 판정을 남겼다.
  - [x] `tools/build_semantic_coverage_audit.py`가 `image_catalog_present_but_vlm_counter_missing`, `image_ocr_reason_without_public_vlm_counter`, `image_evidence_catalog_unreviewable`, `browser_loading_ok_but_visual_artifact_missing`를 보고한다.
  - [x] `tools/audit_goal_test_run_contract.py`가 small goal/test run에서 `llm_endpoint`, `mcp_health_ok_count`, `mcp_health_failure_count` missing/contradiction을 audit한다.
  - [x] v492 runtime audit에서 v491 manifest는 `runtime_contract=GO`, issues `[]`로 유지됐다.
  - [x] v492 semantic coverage audit에서 `11718082`는 image catalog가 있어도 row-level VLM/OCR counter와 Browser visual artifact가 없어 `REVIEW-LOCKED`로 잡혔다.
- 남은 작업:
  - [x] `expert_main.py` result row에 VLM/OCR fetch/chunk/bytes/status counter를 public field로 조인해 `11718082`류가 로그 없이도 검토 가능하게 한다. v493에서 완료.
  - [ ] Codex in-app Browser artifact manifest를 result/review packet에 연결해 Browser visual gate를 닫는다.
  - [ ] `11718080`류 no-work/context-only 이후 후단 search/alias/BatchContext rescue가 direct anchor 없이 resolved로 뒤집히지 않는 단일 promotion gate를 검토한다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v491 Goal runtime health manifest contract 실서버 확인

- 상태: live small canary passed / runtime audit GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex goal 병렬 검토는 `spawn_agent` subagent 전문가 병렬이며, repo runtime `expert_main.py --parallel` worker 수와 분리했다.
  - [x] v490 live canary에서 Docker/shard lifecycle은 차단되고 VLM/OCR은 동작했지만, `mcp_health_*`가 manifest/run_meta에 남지 않는 관측성 버그를 확인했다.
  - [x] `expert_main.py`가 `llm_endpoint`, `mcp_health_include_search`, `mcp_health_light_mode`, `mcp_health_required_ok_count`, `mcp_health_checked_endpoint_count`, `mcp_health_probe_batch_size`, `mcp_health_workers`, `mcp_health_attempts`, `mcp_health_timeout_sec`를 manifest와 row `run_meta`에 남기도록 수정했다.
  - [x] `audit_goal_test_run_contract.py`가 small goal/test run에서 health manifest 필드가 빠지면 `REVIEW`로 낮추도록 보강했다.
  - [x] v491 2건 live canary를 `--parallel 2 --reuse-shards-only --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했고 `runtime_contract=GO`를 확인했다.
  - [x] v491 manifest 기준 `include_search=false`, `light_mode=true`, `required_ok=2`, `checked=2`, `lifecycle_blocked=true`, `image_post_count=1`, `vlm_ocr_semantic_review_ready=true`를 확인했다.
- 남은 작업:
  - [ ] process snapshot은 현재 Windows 권한 문제로 CIM 기반 command line 확인이 불완전하다. 가능한 경우 외부 snapshot JSON을 주입해 stale process audit을 보강한다.
  - [ ] `11718082`류 이미지 row는 result에 `image_evidence_catalog`가 남지만, Browser visual artifact와 row-level VLM counters는 아직 별도 연결 개선 대상이다.
  - [ ] `11718080`류 no-work/social-lament 판정은 targeted canary에서 정상이어도 random 1000/P0P1 expansion 전까지 10만 approval 근거로 쓰지 않는다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v489 Goal runtime health audit 연동

- 상태: audit tool patched / focused validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `tools/audit_goal_test_run_contract.py`가 v488 `mcp_health_*` manifest 필드를 관측값으로 읽는다.
  - [x] small goal/test run에서 `mcp_health_include_search=true`이면 runtime `GO`가 아니라 `REVIEW`로 잡는다.
  - [x] small goal/test run에서 `mcp_health_light_mode=false`이면 v488 light-health 계약 미적용으로 `REVIEW` 처리한다.
  - [x] `mcp_health_checked_endpoint_count`, `mcp_requested_endpoint_count_before_health_filter`, `mcp_endpoint_count_after_health_filter`, `mcp_health_required_ok_count` 사이의 명백한 모순은 `NO-GO`로 잡는다.
  - [x] 감사 markdown이 health include/search, light mode, required ok, checked endpoint, batch, early-stop 여부를 출력한다.
  - [x] `tests.test_goal_test_run_contract_audit` 15건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] 다음 live small run 후 `audit_goal_test_run_contract.py`로 v489 health audit을 실행해 실제 manifest/log에서 `runtime_contract=GO`인지 확인한다.
  - [ ] live evidence 없이 v489 focused unit test만으로 runtime 실서버 검증 완료라고 표시하지 않는다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v488 Codex subagent 병렬 통합 및 expert_main light health

- 상태: runtime startup cost patched / focused validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex goal 작업을 `runtime/shard`, `VLM/OCR/browser`, `semantic/prompt/orchestration`, `docs/checklist` subagent 축으로 병렬 분해했다.
  - [x] subagent 보고를 그대로 승인하지 않고 메인 Codex가 `expert_main.py`, result row, manifest, docs line 근거를 재확인했다.
  - [x] 소규모 goal/reuse-only run에서 `MCP_HEALTH_INCLUDE_SEARCH` 기본값을 `/readyz` 중심으로 낮췄다.
  - [x] stale explicit `MCP_ENDPOINTS` 목록이 길어도 필요한 healthy endpoint 수를 확보하면 남은 endpoint probe를 생략하는 health probe batch 정책을 추가했다.
  - [x] manifest/run config에 `mcp_health_include_search`, `mcp_health_required_ok_count`, `mcp_health_checked_endpoint_count`, `mcp_health_probe_batch_size`, `mcp_health_probe_stopped_after_required_ok`를 남긴다.
  - [x] `tests.test_expert_main_input_loader` 33건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] 실제 다음 small goal/test run에서 log의 `include_search=False`, `checked_endpoint_count<=required_ok`를 `tools/audit_goal_test_run_contract.py` 또는 수동 로그로 확인한다.
  - [ ] `11718082`류 strict evidence는 Codex in-app Browser iab 직접 캡처가 복구되면 Playwright fallback과 분리해 다시 남긴다.
  - [ ] `11718080`류 no-work sticky veto는 expanded random baseline 1000과 P0/P1 high-risk expansion에서 반복 확인한다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v487 Semantic stability hard-support gate

- 상태: targeted hard-support guard patched / focused validation passed / subagent 4개 축 결과 통합 / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex goal 내부에서 semantic/orchestration, VLM/OCR browser evidence, expert_main runtime 효율, verifier/canonical stability 위험을 subagent 4개 축으로 병렬 검토했다.
  - [x] `_has_title_abbrev_stability_hard_support()`를 추가해 raw `abbrev_stable`과 Verifier veto/High rescue에 쓸 수 있는 hard support를 분리했다.
  - [x] J1 Verifier veto override, multi-source consensus, structural rescue는 raw stability 대신 hard support를 요구한다.
  - [x] canonical rescue strength는 raw stability를 진단 필드로 남기되 score/explicit bridge/OCR penalty escape/strong 판단에는 hard support를 사용한다.
  - [x] J0.6 final rescue, candidate promotion, final rejection profile, nonrelevant candidate exposure 일부도 soft alias stability 단독 승격을 막도록 조정했다.
  - [x] 비공식 검색 alias stability만 있는 actual `_context_to_output()` 케이스에서 Verifier veto가 유지되는 회귀를 추가했다.
  - [x] focused unittest 48건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] `11718080`류 no-work sticky veto는 expanded random baseline 1000과 P0/P1 high-risk expansion으로 반복 확인한다.
  - [ ] `11718082`류 이미지 글은 input image count/result image catalog/VLM chunk/browser visual evidence 불일치 시 semantic ACCEPT 금지 gate를 강화한다.
  - [x] small goal/test run은 v488에서 explicit endpoint light probe와 bridge-only health 기본값으로 별도 보강했다.
  - [ ] raw `abbrev_stable` 잔여 진단/랭킹 보조 경로는 새 실패 pattern이 나오면 hard-support 기준으로 추가 축소한다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v486 Arbiter veto actual / packet label closure

- 상태: Arbiter title veto actual branch regression added / packet label stale blocker closed / stability 후단 보조 P1 유지 / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 전문가 3개 축으로 Arbiter title veto actual 공백, stability 후단 보조 위험, hardcoded alias packet label 후속 상태를 병렬 검토했다.
  - [x] Verifier `is_relevant=false` actual branch에서 post-title abbreviation surface만 있고 hard support가 없으면 veto가 유지되는 회귀를 추가했다.
  - [x] Verifier `is_relevant=false` actual branch에서 post-title abbreviation + official/detail hard support가 있으면 veto exemption이 유지되는 positive control을 추가했다.
  - [x] v465 closure labels를 사용해 v486 action queue를 재생성했고 `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_packet_closed_by_labels=true`, `hardcoded_alias_packet_label_gate=GO`를 확인했다.
  - [x] `build_goal_action_queue.py`에서 packet label gate가 GO인 경우 followup action을 `closed_by_packet_labels` / `executable_now=false`로 표시하게 했다.
  - [x] focused unittest 22건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] `_has_title_abbrev_stability_signal()` / `_has_search_evidence_alias_stability_signal()`이 J1 override, structural rescue, canonical rescue에서 hard support 없이 High/lock 보조로 쓰이지 않는지 actual path 회귀를 추가한다.
  - [ ] `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS` positive registry 전체 경로는 계속 REVIEW blocker로 둔다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v485 Agentic alias metadata/rewrite guard

- 상태: targeted metadata/rewrite guard patched / focused validation passed / registry risk REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 전문가 3개 축으로 serialization 누락, 후단 title rewrite, stability/search inferred 증폭 경로를 병렬 검토했다.
  - [x] v484 `registry_anchor_only` promotion tier를 final `alias_resolution_sources`, reason, round2 packet, LLM judgment packet에 보존하게 했다.
  - [x] `_apply_known_abbreviation_title_guard()`의 hardcoded registry source rewrite는 official/detail/direct hard support 없이는 열리지 않게 했다.
  - [x] J11 title drift가 curated alias lock + 같은 promotion title의 registry-only provenance를 지우지 않게 했다.
  - [x] 비공식 title-lead search inferred candidate는 score가 높아도 `High`가 아니라 `Medium`으로 cap했다.
  - [x] round2 review label에서 `registry_anchor_only` weak resolved packet을 `HOLD/re_judge`로 보낸다.
  - [x] focused unittest 78건과 관련 `py_compile`을 통과했다.
  - [x] v485 audit/action queue에서 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- 남은 작업:
  - [x] Arbiter title veto actual branch는 v486에서 `analyze()` 결과로 negative/positive 회귀를 추가했다.
  - [ ] `_has_title_abbrev_stability_signal()`이 confidence calibration/lock에서 `High` 보조로 쓰이는 잔여 경로를 hard support 기준으로 추가 회귀화한다.
  - [x] v409 hardcoded alias packet label의 HOLD/REJECT 5건은 v465 closure labels와 v486 action queue에서 packet label blocker를 닫았다.
  - [ ] completed VLM/OCR-on source, browser visual evidence, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v484 Agentic known alias promotion confidence gate

- 상태: targeted confidence guard patched / focused validation passed / registry risk REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 전문가 3개 축으로 Agentic direct High, docs/gate, runtime/subagent 분리를 병렬 검토했다.
  - [x] `_try_promote_best_candidate()`의 `KNOWN_*` registry direct promotion에서 hard support를 재평가하게 했다.
  - [x] registry surface + work anchor만 있는 promotion은 `High`가 아니라 `Medium`과 `evidence=registry_anchor_only`로 남긴다.
  - [x] official/detail/direct evidence가 있는 경우만 `High`를 허용하는 positive control을 추가했다.
  - [x] focused unittest 59건과 관련 `py_compile`을 통과했다.
  - [x] v484 audit/action queue에서 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- 남은 작업:
- [x] Agentic `_apply_known_abbreviation_title_guard()` 후단 final title rewrite는 v485에서 registry soft-support 차단으로 1차 고정했다.
  - [ ] `_has_title_abbrev_stability_signal()` 증폭 경로는 direct title 생성은 아니지만 support/lock risk로 계속 검토한다.
  - [ ] Arbiter title veto actual branch는 helper가 아니라 `analyze()` 결과로 검증한다.
  - [ ] completed VLM/OCR-on source, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v483 Arbiter alias-only actual decision-path guard

- 상태: actual branch regression added / focused validation passed / registry risk REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 전문가 2개 축으로 actual decision-path seam과 남은 registry blocker 우선순위를 병렬 검토했다.
  - [x] `multi_work` 비교/나열 문맥의 alias-only 단일 title 승격을 actual `analyze()` 테스트로 차단했다.
  - [x] work-anchor 등록 약칭은 `multi_work` guard에서 보존하는 positive control을 추가했다.
  - [x] `meme/noise`와 `low-confidence` guard가 abbreviation-only anchor + official support만으로 면제되지 않게 했다.
  - [x] focused unittest 13건과 관련 `py_compile`을 통과했다.
  - [x] v483 audit에서 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, `SLANG_DICTIONARY positive=0`을 확인했다.
- 남은 작업:
  - [x] Agentic `_try_promote_best_candidate()`의 `KNOWN_* -> High` direct rescue는 v484에서 confidence/evidence tier 계약으로 낮췄다.
  - [ ] Agentic `_apply_known_abbreviation_title_guard()` 후단 final title rewrite를 별도 회귀로 고정한다.
  - [ ] Arbiter title veto actual branch는 helper가 아니라 `analyze()` 결과로 검증한다.
  - [ ] completed VLM/OCR-on source, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v482 Arbiter strong/official support 계약 분리

- 상태: helper contract patched / focused validation passed / registry risk REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 전문가 2개 축으로 Arbiter 반환 구조와 테스트/문서 공백을 병렬 검토했다.
  - [x] `_has_strong_title_support()`가 official detail/source quality 계산 결과를 실제 반환하도록 고정했다.
  - [x] `_has_official_title_evidence()`를 약칭/registry hint와 분리된 official platform detail evidence helper로 고정했다.
  - [x] deleted/unavailable, community post, listing page는 strong/official support 근거에서 제외했다.
  - [x] 짧은 제목 substring-only official evidence 오탐을 막는 token boundary regression을 추가했다.
  - [x] focused unittest 9건과 관련 `py_compile`을 통과했다.
  - [x] v482 audit에서 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, `SLANG_DICTIONARY positive=0`을 확인했다.
- 남은 작업:
  - [ ] Arbiter `multi_work`, `meme/noise`, `low-confidence`, title veto actual decision-path regression을 추가한다.
  - [ ] `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS` positive registry 전체 경로는 계속 review blocker로 둔다.
  - [ ] completed VLM/OCR-on source, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v476 KNOWN_* prompt pressure 완화 / audit noise 보정

- 상태: prompt pressure reduced / audit noise reduced / registry risk REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 전문가 2개 축으로 current KNOWN_* 코드 경로와 v475/v476 gate 설계를 병렬 검토했다.
  - [x] `EvidenceScorer`에서 등록 약칭을 강한 확정 신호가 아니라 1점짜리 recall hint로 낮췄다.
  - [x] no-work 또는 독립 work anchor 부재 문맥에서는 등록 약칭 positive signal과 Jury/Debate prompt note가 생성되지 않게 했다.
  - [x] Jury/Debate prompt에서 `확정적입니다`, `is_relevant=true` 강제 문구를 제거했다.
  - [x] hardcoded alias risk audit에서 import-only usage와 provenance tuple을 positive blocker로 세지 않게 했다.
  - [x] v476 audit에서 `KNOWN_ABBREVIATIONS` positive usage `103 -> 83`, prompt pressure `18 -> 7` 감소를 확인했다.
  - [x] focused unittest 22건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] `Decoder._rescue_null_title`의 `known_abbreviation_unverified=0.80` 후보 경로를 독립 evidence contract로 낮춘다.
  - [ ] `AgenticPipeline._try_promote_best_candidate`의 `KNOWN_* -> High` 직접 승격을 `registry provenance + independent anchor` 기준으로 재검토한다.
  - [ ] Arbiter multi_work/meme/low-confidence guard exception에서 `KNOWN_ABBREVIATIONS` 단독 면제를 제거하거나 독립 anchor를 요구한다.
  - [ ] `hardcoded_alias_positive_blocker_count=2`가 유지되므로 `hardcoded_alias_risk_review_required`는 계속 approval blocker다.
  - [ ] completed VLM/OCR-on source, random 1000, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v474 SLANG_DICTIONARY hint-only 계약

- 상태: SLANG_DICTIONARY positive blocker 해소 / registry risk REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 전문가 2개 축으로 SLANG_DICTIONARY 계약과 v474 gate 필드를 병렬 검토했다.
  - [x] `SLANG_DICTIONARY` hit가 `official_title`이나 `confidence=High`를 직접 만들지 않게 했다.
  - [x] Decoder dictionary merge가 `slang_dictionary_hint` candidate만 추가하고 기존 `best_match`를 덮어쓰지 않게 했다.
  - [x] LLM이 dictionary-only mapped title을 `best_match.title/high`로 출력해도 독립 URL/플랫폼/비사전 evidence가 없으면 null 처리한다.
  - [x] 감사 도구에서 SLANG provenance tuple과 tooling metadata usage를 positive blocker 오탐으로 세지 않게 했다.
  - [x] v474 audit에서 `SLANG_DICTIONARY gate_status=INFO`, `positive_usage_count=0`을 확인했다.
  - [x] v474 action queue에서 `hardcoded_alias_positive_blocker_count=2`, `hardcoded_alias_packet_effective_gate=GO`를 확인했다.
  - [x] focused unittest 23건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] `hardcoded_alias_risk_review_required`는 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS` blocker 2개 때문에 계속 approval blocker다.
  - [ ] `KNOWN_*` registry도 단독 rescue/High/guard exception 경로를 evidence contract로 더 낮추거나 alias별 canary coverage를 확보해야 한다.
  - [ ] completed VLM/OCR-on source, random baseline 1000건, P0/P1 high-risk expansion 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v470 hardcoded alias audit false-positive / unique scope

- 상태: audit false-positive fixed / packet review effective GO / registry risk REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` subagent 2개 축으로 hardcoded audit 분류와 semantic/VLM 구조 리스크를 병렬 검토했다.
  - [x] `TITLE_ALIAS_SUPPORT_MARKERS`가 coverage scanner marker tuple인데 `ALIAS` 이름 때문에 positive blocker로 잡히는 경로를 확인했다.
  - [x] `tools/` 아래 `*_MARKERS` tuple을 `tooling_marker/INFO`로 분리하고, runtime positive registry 3종은 blocker로 유지했다.
  - [x] raw packet duplicate count와 unique post-context alias coverage를 분리했다.
  - [x] v470 action queue에서 `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_packet_unique_post_context_matches=1`을 확인했다.
  - [x] focused unittest 22건과 관련 `py_compile`을 통과했다.
- 남은 작업:
  - [ ] `hardcoded_alias_risk_review_required`는 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY` 경로가 남아 계속 approval blocker다.
  - [ ] `11718080`형 social lament/no-work가 후단 search/alias/BatchContext rescue로 되살아나는 비단조 구조를 P0 구조 리스크로 계속 추적한다.
  - [ ] `11718082`형 image anchored post는 VLM/OCR catalog와 Browser visual/loading evidence가 구조화되어야 approval 후보가 된다.
  - [ ] completed VLM/OCR-on source 확보 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v467 hardcoded alias packet review reconciliation

- 상태: packet review effective GO / hardcoded alias registry REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] v407 원 packet review의 `matched_packets=11`, raw `gate=REVIEW` 상태를 v465 closure labels와 대조했다.
  - [x] v465 closure labels 11건이 모두 `ACCEPT`, `Strong`, `PROVEN_IN_V450`, `CLOSED_BY_V450_CANARY`인지 확인했다.
  - [x] v450 latest canary가 `source_registry=KNOWN_TITLE_ABBREVIATIONS`, `alias_resolution_source=known_title_abbreviation`, `matched_surface_kind=post_title`를 공개하는지 확인했다.
  - [x] `build_goal_action_queue.py`가 matched packet 수 이상이 모두 ACCEPT로 닫힌 경우 packet review를 `closed_by_packet_labels`로 처리하게 했다.
  - [x] v467 action queue에서 `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_packet_closed_by_labels=true`를 확인했다.
- 남은 작업:
  - [ ] `hardcoded_alias_risk_review_required`는 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY` positive registry 전체 경로가 남아 계속 blocker다.
  - [ ] completed VLM/OCR-on source 확보 전까지 10만 approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v465/v466 hardcoded alias packet label follow-up

- 상태: v465 historical packet label follow-up GO / hardcoded alias registry와 packet review는 계속 REVIEW / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] v409 hardcoded alias packet labels의 `ACCEPT=6`, `HOLD=2`, `REJECT=3` 원인을 다시 분리했다.
  - [x] v450 최신 `11718120` canary에서 `담텔기 -> 괴담 호텔 탈출기`가 `source_registry=KNOWN_TITLE_ABBREVIATIONS`, `alias_resolution_source=known_title_abbreviation`, `matched_surface_kind=post_title`로 공개 provenance를 남기는지 확인했다.
  - [x] v450 latest result에서 final `official_title=괴담 호텔 탈출기`, `heretic_url=https://novelpia.com/novel/102155`, `title_candidates=괴담 호텔 탈출기` 1건만 남는지 확인했다.
  - [x] v465 closure labels를 만들고 11건 모두 `ACCEPT`, `CLOSED_BY_V450_CANARY`로 고정했다.
  - [x] v466 action queue를 재생성해 `hardcoded_alias_packet_label_gate=GO`, label count `{'ACCEPT': 11}`을 확인했다.
- 남은 작업:
  - [ ] `hardcoded_alias_risk_review_required`는 positive registry 3건이 남아 계속 approval blocker다.
  - [ ] `hardcoded_alias_packet_review_required`는 v407 packet/provenance review 자체가 `REVIEW`라 계속 approval blocker다.
  - [ ] completed VLM/OCR-on source 확보 전까지 random baseline 1000건과 P0/P1 high-risk expansion은 실행 불가다.
  - [ ] 이 follow-up closure를 전체 hardcoded alias 승인이나 10만 semantic approval로 승격하지 않는다.

## 2026-06-01 v461~v464 Browser visual 보강 / current-state action queue 재정렬

- 상태: v460 small canary coverage GO / 10만 semantic gate REVIEW-LOCKED
- 완료:
  - [x] v460 result에 대해 `scan_reason_hygiene.py --fail-on-hit`를 재실행했고 hit 0건을 확인했다.
  - [x] v460 result에 `build_semantic_coverage_audit.py`를 실행해 `11718082` Browser visual missing을 확인했다.
  - [x] Codex 내장 Browser iab를 우선 시도했으나 node_repl 연결이 2회 종료되어 직접 iab screenshot은 확보하지 못했다.
  - [x] 대체 Playwright MCP로 `11718082` 페이지를 열고 full-page screenshot, metrics, artifact manifest를 남겼다.
  - [x] metrics 기준 `.write_div` 내부 dcimg 본문 이미지 1개가 `complete=true`, `naturalWidth=850`, `naturalHeight=850`으로 로드됨을 확인했다.
  - [x] v462 semantic coverage audit에서 v460 small canary 기준 `browser_visual_required/available/missing=1/1/0`, `gate=GO`를 확인했다.
  - [x] v463 current-state map과 v464 action queue를 재생성했다. `vlm_ocr_browser_visual_gate`는 v460 small canary 기준 approval blocker에서 빠졌지만, 10만 semantic approval은 `REVIEW-LOCKED`로 유지된다.
- 남은 작업:
  - [ ] Codex 내장 Browser iab가 복구되면 같은 post를 iab로 다시 캡처해 fallback caveat를 줄인다.
  - [ ] completed VLM/OCR-on source를 확보하지 못했으므로 원본 10만 run approval은 계속 `NO-GO/REVIEW-LOCKED`다.
  - [ ] completed source 확보 후 random baseline 1000건, P0/P1 high-risk expansion, hardcoded alias packet follow-up을 다시 실행한다.

## 2026-06-01 v459/v460 이미지 OCR anchor taxonomy / slang context final follow-up

- 상태: patched / v460 targeted canary GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 2개 축으로 anchor consistency와 slang/context output hygiene를 병렬 감사했다.
  - [x] v458의 `title_in_post=false`, `image_ocr_variant=true` reason과 `anchor_type=title_exact` final taxonomy 불일치를 확인했다.
  - [x] 이미지 OCR 변형만 있고 non-image title 직접 언급이 없으면 final `anchor_type=image`, `anchor_strength=high`로 정렬하고 `image_ocr_variant_not_title_in_post` flag를 남기게 했다.
  - [x] `특정 웹소설 일부 인용`, `작품의 설정/줄거리/세계관/배경`, `캐릭터 관계`, `비표준적인 커뮤니티 약칭 또는 OCR 오인` 계열 slang/context overstatement를 packet-local OCR/표지/이미지 장면 단서로 낮췄다.
  - [x] v459 live canary에서 anchor taxonomy 보정이 실제 출력에 반영됨을 확인했다.
  - [x] v460 live canary에서 `11718082`는 `anchor_type=image`, `image_ocr_variant_not_title_in_post`, `slang_insight=null`이고, `11718080`은 `official_title=null`, `work_resolution=none`, `anchor_type=genre`임을 확인했다.
  - [x] v460 runtime audit는 `runtime_contract=GO`, `issues=[]`, requested/raw/capped/effective `64/36/2`, VLM/OCR ready를 남겼다.
  - [x] `py_compile`과 focused unittest 20건을 통과했다.
- 남은 작업:
  - [ ] Browser visual 캡처는 이번 v460에서도 수행하지 않았다. 이미지 row approval은 Browser loading counter 또는 동등한 visual evidence 전까지 `REVIEW-LOCKED`다.
  - [ ] v460은 targeted canary다. 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-06-01 v455~v458 이미지 OCR reason score / slang context follow-up

- 상태: patched / v458 targeted canary GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex subagent 3개 축으로 runtime, semantic/VLM/slang, docs/gate consistency를 읽기 전용 병렬 감사했다.
  - [x] v455/v456/v457 live 결과에서 남은 `slang_insight.cultural_context` 변종과 `title_in_post:+2` score 모순을 확인하고 중간 증거로 분리했다.
  - [x] reason score board가 이미지 OCR 변형을 원문 직접 제목 언급으로 가산하지 않게 했다.
  - [x] 이미지 OCR 표면을 `게시글/제목에 사용된`, `일반적인 오타 또는 축약`, `공식적인 제목`, `고유 명칭`처럼 과장하는 문구를 packet-local OCR/표기 변형 단서로 낮췄다.
  - [x] focused test 8건과 관련 py_compile을 통과했다.
  - [x] v458 live canary와 audit에서 runtime `GO`, `issues=[]`, `title_in_post:+2`/old wording/Docker lifecycle hit 없음, VLM fetch/chunk `1/1`을 확인했다.
- 남은 작업:
  - [ ] Browser visual 캡처는 이번 v458에서도 수행하지 않았다. 이미지 row approval은 Browser loading counter 또는 동등한 visual evidence 전까지 `REVIEW-LOCKED`다.
  - [ ] 이 targeted canary를 10만 semantic approval로 승격하지 않는다. expanded random/high-risk review와 completed source가 필요하다.

## 2026-06-01 v454 Codex 전문가 병렬 / Gemma 4 4B cap / 이미지 OCR reason hygiene

- 상태: patched / focused validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 이번 goal 진행을 Codex `spawn_agent` 4개 전문가 축으로 재분해했다: runtime/orchestration, semantic/VLM, 100k qualitative gate, docs/checklist.
  - [x] `expert_main.py --parallel`은 repo 런타임 worker max이고 Codex subagent 병렬은 별도 goal 운영 분업임을 문서에 다시 남겼다.
  - [x] Gemma 4 E4B/4B 계열 모델에서 `requested_parallel_raw > 36`이면 `requested_parallel=36`으로 cap하고, small input은 기존처럼 `effective_parallel`로 낮아지게 했다.
  - [x] manifest/run_meta에 `requested_parallel_raw`, `model_parallel_max`, `model_parallel_cap_applied`, `model_parallel_cap_model`을 추가했다.
  - [x] `tools\audit_goal_test_run_contract.py`가 모델 cap 필드를 읽고 raw/cap/effective 병렬도를 분리 감사하게 했다.
  - [x] 이미지 OCR 변형 표면은 reason에서 `title_in_post=true`로 과장하지 않고 `image_ocr_variant`와 `official_search_resolution`로 분리했다.
  - [x] VLM/OCR slang context에서 이미지 OCR 표면을 `게시글 제목에 사용된 축약어/오타`처럼 말하지 않도록 낮췄다.
  - [x] `py_compile`, focused 12건/8건, broad 333건, comment/runtime audit 22건을 통과했다.
  - [x] v454 live cap canary를 `--parallel 64`로 실행해 Gemma 4 E4B/4B cap이 `requested_parallel_raw=64 -> requested_parallel=36 -> effective_parallel=2`로 기록되는지 확인했다.
  - [x] `v454_goal_test_run_contract_audit.json` / `_ko.md`를 재생성해 `runtime_contract=GO`, `issues=[]`, `llm_model=bg-digitalservices/Gemma-4-E4B-it-NVFP4`를 남겼다.
  - [x] v454 live result에서 `11718082` reason이 `title_in_post=false`, `image_ocr_variant=true`, `official_search_resolution=true`를 남기고, `11718080`은 no-work/genre anchor로 유지됨을 확인했다.
- 남은 작업:
  - [ ] 10만 semantic approval은 completed source, expanded random baseline, P0/P1 high-risk expansion, Browser visual gate 전까지 `REVIEW-LOCKED`로 유지한다.
  - [ ] 이미지 row 승인에는 여전히 Codex in-app Browser 또는 동등한 visual loading evidence를 붙인다. v454는 새 Browser 캡처가 아니다.
  - [x] v454 live result 이후 추가된 `slang_insight.cultural_context` old wording sanitizer는 v460 live canary에서 runtime output까지 재확인했다. v460 `11718082`는 `slang_insight=null`로 남아 old wording이 재현되지 않았다.
  - [ ] 모델별 parallel cap이 추가되는 다른 모델이 생기면 `_model_parallel_max()`와 audit 기대값을 같은 라운드에서 갱신한다.

## 2026-06-01 v453 no-work late URL recovery / BatchContext wrapper guard

- 상태: patched / v453 targeted canary GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex `spawn_agent` 병렬 감사로 late raw search/URL recovery 축과 BatchContext/slang/known alias rescue 축을 분리 검토했다.
  - [x] `_recover_corrected_title_official_url()`이 semantic no-work + direct post/visual work anchor 부재 상태에서 기존 검색 결과 재사용과 직접 `_search_with_meta()` 검색을 막게 했다.
  - [x] `_has_alias_title_support()`가 decoder/gatekeeper/verifier slang 표면을 보기 전에 같은 no-work/direct-anchor gate를 먼저 타게 했다.
  - [x] `_learn_batch_context()` wrapper가 `title_resolution_state`, `title_resolution_allowed`, `discussion_type`, `subtype`, `work_resolution`, `anchor_type`, `consistency_flags`를 BatchContext로 전달하게 했다.
  - [x] raw `_search_with_meta()` 직접 호출부가 `_search` 래퍼와 guarded recovery 외로 늘어나면 실패하는 static regression을 추가했다.
  - [x] 댓글 author/IP/comment_id/gallery_id coverage 도구와 export 테스트가 현재 checkout에서 존재하고 통과하는지 확인했다.
  - [x] focused test 7건, comment metadata coverage 10건, broad regression 332건을 통과했다.
  - [x] v453 targeted live rerun은 `--parallel 36 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했고 requested/effective parallel `36/2`, counters `2/2/2/0/0`, VLM/OCR ready를 확인했다.
  - [x] v453에서 `11718080`은 `official_title=null`, `title_resolution_allowed=false`, `work_resolution=none`, `anchor_type=genre`로 남고, `11718082`는 이미지 앵커 기반으로 `재벌가 차녀의 2회차 걸그룹`을 회복했다.
- 남은 작업:
  - [ ] `_search_with_meta()` 신규 직접 호출부가 의도적으로 필요해지면 static regression allowlist를 갱신하기 전에 intent/no-work guard와 direct-anchor 예외를 별도 focused test로 증명한다.
  - [ ] `BatchContext`/`slang_db` seed 저장과 dashboard 표시를 expanded P0/P1 sample에서 분리 확인한다.
  - [ ] 전체 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v451/v452 no-work + VLM/OCR image canonical guard

- 상태: v451 residual 확인 / v452 targeted canary GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718080`/`11718082` 기존 입력 `v257_post11718080_11718082_input.jsonl`을 최신 코드로 재실행했다.
  - [x] small targeted run에서는 `--parallel 36`이 max이고 입력 2건 기준 `effective_parallel=2`가 정상임을 manifest로 확인했다.
  - [x] `--reuse-shards-only --no-dashboard`로 실행해 shard/docker lifecycle 재기동 없이 검증했다.
  - [x] v451에서 `11718080`이 더 이상 `소보로설`류 작품명으로 resolved되지 않고 `is_relevant=false`, `official_title=null`, `trope_discussion`, `title_resolution_allowed=false`로 내려감을 확인했다.
  - [x] v451에서 `11718082` VLM/OCR request/result/OCR/enrichment/fetch counter가 실제로 남고 최종 title이 회복됨을 확인했다.
  - [x] v451 로그의 원문 미언급 canonical suspect 흔들림을 residual P1로 분리했다.
  - [x] verified current title lock이 있고 replacement canonical 후보가 post-side 앵커가 없으면 override하지 않는 범용 guard를 추가했다.
  - [x] 새 focused 회귀와 기존 rework suite를 통과했다.
  - [x] v452 live rerun에서 `11718082`가 `anchor_type=image`, `heretic_url=https://page.kakao.com/content/66692543`, VLM `fetch=1/1 chunks=1`로 회복되고, v451의 원문 미언급 canonical suspect override가 사라짐을 확인했다.
- 남은 작업:
  - [ ] 같은 계열을 expanded P0/P1 regression으로 확대한다: no-work 잡담, VLM/OCR 직접 작품 표면, verified title lock, unanchored canonical replacement.
  - [ ] `search_only`/`BatchContext`/`slang_db`/late URL recovery 계열에도 동일 permit/provenance가 관통하는지 별도 subagent 감사와 packet review로 확인한다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v448/v449/v450 curated abbreviation adjacent candidate guard

- 상태: v448 live canary completed / v450 targeted canary GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v448 `11718120` live canary는 result/manifest/checkpoint 기준 input/completed/flushed/pending/failed `1/1/1/0/0`으로 완료됐다.
  - [x] v448에서 `담텔기 -> 괴담 호텔 탈출기` known title abbreviation provenance가 final `official_title=괴담 호텔 탈출기`까지 회복됐다.
  - [x] v448 단건에서 requested/effective parallel `36/1`, VLM/OCR on, image post count `0`, shard lifecycle 재기동 없음 흐름을 분리 기록했다.
  - [x] v448 semantic label은 `title_candidates`에 `괴담 학교 탈출기` 인접 파생 후보가 남아 `HOLD`로 분리했다.
  - [x] 후속 adjacent candidate guard focused regression을 실행했다.
  - [x] v449/v450 live canary를 새 output으로 실행하고 `completed=flushed=input`, `pending=0`, `failed=0`을 확인했다.
  - [x] v450 result에서 final `official_title=괴담 호텔 탈출기`, `heretic_url=https://novelpia.com/novel/102155`가 유지되고, unmentioned adjacent derivative candidate `괴담 학교 탈출기`가 `title_candidates`에 남지 않는지 확인했다.
  - [x] `semantic_seed_no_work + has_episode_reference`만으로 known abbreviation promotion이 풀리지 않는 회귀를 추가했다.
  - [x] curated alias 부분일치를 visible surface 기준으로 좁히는 회귀를 추가했다.
  - [x] 작품군 키워드 hardcode를 일반 토큰 drift 검사로 바꾸고, shared generic keyword만으로 decoder anchor drift가 숨지 않는 회귀를 추가했다.
- 남은 작업:
  - [ ] v450은 targeted canary 통과일 뿐이다. expanded known-bad/positive-control set에서 same-family adjacent candidate와 no-work alias rescue를 추가 표본으로 확인한다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v447 known title abbreviation support and v446 incomplete canary split

- 상태: patched / focused validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v446 단건 canary를 Docker/shard restart 문제가 아니라 output flush 전 중단된 `runtime-incomplete`로 분리했다.
  - [x] `KNOWN_TITLE_ABBREVIATIONS`가 `_try_promote_best_candidate()`, explicit support, alias support, abbreviation stability 경로에 들어가도록 보강했다.
  - [x] 안정 약칭이 post title/body에 있고 회차/스포/작가의 말/positive work intent 같은 packet-local work anchor가 있을 때만 no-work rescue 예외를 허용한다.
  - [x] `11718080`류 no-work/잡담글은 known title abbreviation 표면이 있어도 contextual work anchor 없으면 promotion/stability가 차단됨을 테스트했다.
  - [x] `tests\test_known_title_abbreviation_support.py` 3건, no-work guard 포함 5건, 기존 `AgenticPipelineReworkTest` 305건을 통과했다.
- 남은 작업:
  - [x] v448 새 output에서 `11718120` completed/flush/pending/failed 상태를 확인했고, v450에서 targeted canary `GO`까지 확인했다. 단, 10만 approval source로는 expanded review가 필요하다.
  - [ ] `담텔기`류 known title abbreviation positive와 `305호`류 numeric/episode 후보 provenance를 expanded P0/P1 regression에서 분리 확인한다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v441 semantic no-work abbrev/snippet/stable-hold rescue guard

- 상태: patched / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] no-work 상태에서 decoder abbreviation stability가 raw title/direct visual anchor 없이 작품 support로 살아나지 않도록 했다.
  - [x] no-work 상태에서 snippet canonical alias lock이 raw title/direct visual anchor 없이 strong anchor가 되지 않도록 했다.
  - [x] irrelevant canonical rescue와 stable-hold canonical rescue가 semantic no-work block을 다시 풀지 못하게 했다.
  - [x] focused regression에 decoder alias, snippet lock, stable-hold 차단 assertion을 추가했다.
  - [x] 신규 focused 2건과 기존 `AgenticPipelineReworkTest` 305건을 통과했다.
- 남은 작업:
  - [ ] expanded known-bad/positive-control review 전까지 search/alias/canonical rescue 계열은 `HOLD/REPROCESS`로 유지한다.

## 2026-06-01 v440 malformed browser Strong artifact loading gate

- 상태: patched / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] external browser artifact row가 `visual_evidence_grade=Strong`이어도 loading counter 실패가 있으면 `browser_visual_available`로 세지 않도록 했다.
  - [x] Missing 관찰 문구에 본문 이미지 노드 미검출과 이미지 로딩 근거 없음 사유를 추가했다.
  - [x] malformed Strong external artifact 회귀 테스트를 추가했다.
  - [x] focused/browser/semantic coverage 29건을 통과했다.
- 남은 작업:
  - [ ] VLM/OCR/browser visual axis와 10만 semantic approval은 completed source와 expanded review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v439 semantic no-work search-inferred support guard

- 상태: patched / focused validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718080`류 한탄/잡담 글에서 search support가 좋아도 semantic no-work/intent permit denied가 있으면 title-lead search-inferred candidate를 만들지 않도록 했다.
  - [x] `title_lead_alias_search_work_support`와 `search_evidence_alias_stability`도 같은 no-work/direct-anchor gate를 먼저 타게 했다.
  - [x] 특정 작품명/오타 hardcode 없이 `_semantic_seed_no_work_signal()` 기반 범용 gate로 막았다.
  - [x] `tests\test_title_lead_search_inferred_guard.py`를 추가해 no-work 차단과 positive work seed 허용을 함께 검증했다.
  - [x] 신규 unittest 2건, 기존 `AgenticPipelineReworkTest` 305건, VLM/browser/semantic coverage 26건을 통과했다.
- 남은 작업:
  - [ ] 검색 이후 후보 재승격 계열은 expanded known-bad/positive-control 재검증 전까지 `HOLD/REPROCESS`로 유지한다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v434 weak browser fallback sidecar guard

- 상태: implemented / validation passed / visual gate REVIEW-LOCKED
- 완료:
  - [x] v433 image row 4건용 `v433_vlm_ocr_browser_targets.jsonl`을 만들었다.
  - [x] Codex in-app Browser 재시도 실패를 기록했다: `windows sandbox failed: spawn setup refresh`.
  - [x] Playwright CLI fallback을 sandbox와 external 권한으로 모두 실행했다.
  - [x] external fallback은 screenshot `4/4`를 생성했지만 article image selector `0/0`, visual grade `Weak=4`임을 확인했다.
  - [x] `build_semantic_coverage_audit.py`가 external artifact manifest의 `output_path` JSONL을 읽게 했다.
  - [x] Weak/Missing external browser artifact는 screenshot이 있어도 `browser_visual_available`로 세지 않는 회귀를 추가했다.
  - [x] `capture_vlm_ocr_browser_review_cli.py`에 `--run-id`를 추가했다.
  - [x] Windows `npx.cmd` 경유 Playwright CLI에서 DCInside URL `&no=`가 cmd separator로 깨지는 문제를 `.cmd/.bat` 전용 escape로 막았다.
  - [x] v434 coverage는 weak sidecar를 붙여도 `browser_visual_required/available/missing=4/0/4`와 gate `REVIEW-LOCKED`를 유지했다.
  - [x] v436 fallback recapture는 open/eval/screenshot return code `0`으로 명령 호출 문제는 닫았지만 visual evidence `Missing=4`, article image gate passed `0`임을 확인했다.
  - [x] v437 coverage는 v436 missing sidecar를 붙여도 `browser_visual_required/available/missing=4/0/4`, `browser_visual_external_artifact_available=0`, gate `REVIEW-LOCKED`를 유지했다.
- 남은 작업:
  - [ ] v433 4건의 image loading Strong/Medium evidence를 얻으려면 Codex IAB 복구 또는 DC 원문 이미지 selector가 실제 article image를 잡는 별도 브라우저 캡처가 필요하다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 v432 targeted follow-up closure review

- 상태: partial-closed / targeted gate REVIEW / full semantic gate REVIEW-LOCKED
- 완료:
  - [x] v431 remaining queue 4건을 packet-level로 재판정했다.
  - [x] v432 closure labels/manifest/summary를 작성했다.
  - [x] `11718083`은 unresolved memory query 유지가 타당해 targeted follow-up 기준 닫았다.
  - [x] `11718097`은 comment author 미확정이 final title 필수 근거가 아니므로 targeted follow-up 기준 닫았다.
  - [x] `11718075`는 alias/official evidence가 final title을 직접 지지하므로 targeted follow-up 기준 닫았다.
- 남은 작업:
  - [x] `11718049`: 댓글 URL이 실제 작품 추천 링크로 확인됐으므로, source final의 `noise/unrelated`를 `recommendation_request`/`adjacent_relevant` 또는 comment recommendation candidate로 보존하도록 코드 경로와 focused regression을 추가했다.
  - [x] 검색 결과의 등장인물 페이지 제목, `promotion_eligible=false` VLM/OCR text surface, 짧은 캐릭터 반응 scope 분리 회귀를 추가했고 `AgenticPipelineReworkTest` 305건을 통과했다.
  - [x] `11718049`: 최신 코드 v433 live rerun에서 `comment_url_recommendation_candidate_preserved`와 `recommendation_candidates[]`가 남는지 확인했다.
  - [x] Codex in-app Browser 연결 실패(`windows sandbox failed: spawn setup refresh`)는 browser evidence 확보 경로 이슈로 계속 기록한다.
  - [ ] v433 4건은 VLM/OCR `READY`와 `image_evidence_catalog`는 있으나 browser visual sidecar가 없어 `browser_visual_required/available/missing=4/0/4`다. visual artifact 연결 전까지 targeted coverage는 `REVIEW-LOCKED`다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 v431 targeted follow-up remaining queue

- 상태: implemented / validation passed / targeted gate REVIEW / full semantic gate REVIEW-LOCKED
- 완료:
  - [x] `tools\build_targeted_followup_remaining_queue.py`를 추가해 v429 labels와 v430 coverage에서 남은 targeted follow-up 항목을 합성한다.
  - [x] v431 manifest/queue/packets/summary를 생성했다.
  - [x] v431 counts: `queue_items=4`, `HOLD=2`, `REVIEW_ONLY=2`, `comment_url_verify=1`, `human_review=3`.
- 남은 작업:
  - [x] `11718049`: 댓글 Novelpia URL이 실제 추천/답변 후보로 보존되는지 v432 packet review와 v433 live rerun으로 확인했다.
  - [x] `11718083`: v432에서 exact quote 직접 match를 찾지 못해 unresolved memory query 유지가 타당하다고 packet-level로 닫았다.
  - [x] `11718097`: v432/v430 refined coverage에서 comment author 미확정 신호가 final title의 필수 근거가 아니라고 확인했다.
  - [x] `11718075`: v432/v430 refined coverage에서 `죽깨수` alias와 official/platform evidence가 `죽었다 깨어도 수선`을 직접 지지한다고 확인했다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 Codex goal subagent 병렬 운영

- 상태: implemented / validation passed / targeted coverage REVIEW / full semantic gate REVIEW-LOCKED
- 완료:
  - [x] 사용자 재정정을 반영해 현재 라운드를 Codex 앱 `spawn_agent` 병렬 운영으로 다시 열었다.
  - [x] v411에서 Runtime/manifest, semantic 품질, VLM/OCR 이미지 게이트, 프롬프트/오케스트레이션 한계 subagent 결과를 통합했다.
  - [x] `11718082`는 세대별로 분리했다. v179는 VLM-ready/log가 없어 승인 근거가 아니고, v181/v259/v311/v325/v330은 VLM/OCR이 돌았으며, 원본 10만 partial은 구조화 catalog 부재로 승인 근거가 아니다.
  - [x] 원본 5/28 result의 `batch_memory_exact_alias_rescued` P0 seed를 기록했다: `11718080`, `11718062`, `11718083`, `11718118`, `11718069`.
  - [x] `11718080`류는 앞단 LLM 이해 실패만이 아니라 후단 검색/alias/rescue가 no-work 판단을 뒤집는 비단조 파이프라인 문제로 재분류했다.
  - [x] `hardcoded alias risk` explorer, `VLM/OCR browser evidence gate` explorer, `hardcoded alias audit tool/test` worker를 병렬 투입했다.
  - [x] `tools\audit_hardcoded_alias_risk.py`를 추가하고 curated registry 분류를 보강했다.
  - [x] v405 refined hardcoded alias risk audit를 생성했다: `semantic_approval=REVIEW`, positive blocker `3`, quarantine-only `10`.
  - [x] `build_goal_action_queue.py --hardcoded-alias-audit`를 추가하고 v406 action queue에 `hardcoded_alias_risk_review_required`를 approval blocker로 넣었다.
  - [x] `tools\build_hardcoded_alias_packet_review.py`와 `tests\test_hardcoded_alias_packet_review.py`를 추가했다.
  - [x] v407 packet review를 생성했다. 결과는 scanned files `388`, scanned records `763`, matched packets `11`, `packet_coverage=FOUND`, gate `REVIEW`이다.
  - [x] v407에서 검색 snippet에만 나타난 alias는 context-only로 분리했고, 실제 packet match는 `KNOWN_TITLE_ABBREVIATIONS:담텔기 -> 괴담 호텔 탈출기` 계열로 좁혔다.
  - [x] `build_goal_action_queue.py --hardcoded-alias-packet-review`를 추가하고 v408 action queue에 `hardcoded_alias_packet_review_required`를 approval blocker로 넣었다.
  - [x] v408 action queue는 `total_actions=13`, `ready_now=8`, `blocked_until_completed_source=5`, approval blocker `7`이다.
  - [x] v409 packet label review를 작성했다. 11건 중 `ACCEPT=6`, `HOLD=2`, `REJECT=3`이다.
  - [x] `build_goal_action_queue.py --hardcoded-alias-packet-labels`를 추가하고 v410 action queue에 `hardcoded_alias_packet_label_followup`을 approval blocker로 넣었다.
  - [x] v410 action queue는 `total_actions=14`, `ready_now=9`, `blocked_until_completed_source=5`, approval blocker `8`이다.
  - [x] runtime/shard explorer가 `expert_main.py --parallel 36`은 max이고 small input에서는 effective parallel이 줄어드는 현 계약을 확인했다.
  - [x] semantic/VLM explorer가 intent-first 구조는 있으나 검색 permit hard gate가 약해 `11718080`류 한탄/잡담이 search resolved로 되살아날 수 있음을 P0로 확인했다.
  - [x] `Boole` explorer가 gate/evidence 상태를 확인했다.
  - [x] `Hume` explorer가 runtime/shard/process 공백을 확인했다.
  - [x] `Jason` explorer가 semantic/VLM/comment coverage 공백을 확인했다.
  - [x] `Cicero` worker에 runtime audit process snapshot 개선을 맡겼다.
  - [x] `Confucius` worker에 semantic/VLM/comment coverage audit 신규 도구를 맡겼다.
  - [x] `Cicero` worker 결과를 통합해 process snapshot audit v395를 생성했다.
  - [x] `Confucius` worker 결과를 통합해 semantic coverage audit v396을 생성했다.
  - [x] sandbox CIM 권한 공백을 보완하기 위해 `--process-snapshot-json` 외부 snapshot 주입 경로와 v397 audit를 추가했다.
  - [x] v396 semantic coverage와 v397 process snapshot을 v398 action queue에 통합했다.
  - [x] v398 action queue에서 `modern_semantic_coverage_source_required`, `semantic_coverage_audit_required_for_new_source`, `process_snapshot_required_for_goal_reruns`를 별도 action으로 분리했다.
  - [x] `final_semantic_reread_required/present/missing`을 추가해 non-relevant/context-only row를 final reread 누락으로 과차단하지 않게 했다.
  - [x] v399 clean canary coverage audit, v400 refined original coverage audit, v401 refined action queue, v402 현재 goal 요약을 생성했다.
- 다음 작업:
  - [x] 신규 subagent 결과를 메인 Codex가 통합하고, hardcoded alias/VLM evidence gate 산출물과 검증 결과를 한국어로 갱신했다.
  - [x] `KNOWN_TITLE_ABBREVIATIONS`, `KNOWN_ABBREVIATIONS`, `SLANG_DICTIONARY` positive rescue 경로를 v405 line-level samples와 v407 packet coverage 기준으로 1차 분리했다.
  - [ ] evidence-supported bootstrap 여부는 v407 matched packet 정성 라벨과 targeted canary provenance 확인 뒤 확정한다.
  - [x] v407 matched packet 11건을 원문/evidence/reason 기준으로 ACCEPT/HOLD/REPROCESS/REJECT 라벨링한다.
  - [ ] v409 REJECT 3건을 최신 코드 기준으로 re_judge/re_search canary에 넣는다.
  - [x] registry provenance가 packet에 남지 않는 문제를 1차 해결했다. `NovelIdentity.alias_resolution_sources[]`와 round2 packet `final_decision_fields.alias_resolution_sources`에 `source_registry`, `alias_resolution_source`, `matched_surface_kind`를 노출한다.
  - [x] `tools\build_current_remaining_action_inputs.py` 실행 계약에서 소규모 입력의 권장 `--parallel min(input_count,36)`를 표시하고, `MCP_SHARD_COUNT=36`을 required contract에서 제거한다.
  - [x] Codex `spawn_agent` 병렬 운영과 `expert_main.py --parallel` runtime 병렬도를 문서에서 분리했다. goal 병렬은 전문가 검토 분업이고 runtime 병렬은 worker cap이다.
  - [x] goal 보고서에서는 `requested_parallel=36`, `effective_parallel=N`, `spawn_agent axes=[...]`를 분리 표기한다는 운영 계약을 추가했다.
  - [ ] `KNOWN_ABBREVIATIONS`와 `SLANG_DICTIONARY`는 현재 packet direct evidence가 부족하므로 `히집악`, `전독시` targeted canary로 provenance를 검증한다.
  - [x] `intent_permit_for_title_search=false`일 때 `official_title_verify`, `platform_title_search`, `alias_raw_probe`, `key_term_supplement`, `auto_search_seed` 계열 실행 검색을 hard-block하는 1차 중앙 gate를 추가했다.
  - [x] title-like purpose denylist 누락을 줄이기 위해 permit false 상태는 닫힌 기본값으로 전환했다. `term_definition` 등 안전 목적만 통과하고 unknown purpose는 기본 차단한다.
  - [x] `adaptive_wiki`, `author_works_search` 직접 `search_fn` 호출을 중앙 `_execute_searches(..., ctx=ctx)` 경로로 통일해 intent permit gate를 우회하지 않게 했다.
  - [x] 후단 BatchContext/known alias/slang_db seed/deliberation rescue 경로가 `semantic_seed_review` no-work, `title_resolution_allowed=false`, `context_only` 신호를 독립 작품 evidence처럼 되살리지 않는지 focused 회귀로 닫았다.
  - [x] 이번 후단 rescue 라운드도 Codex `spawn_agent` subagent 2개를 병렬 투입해 후단 우회 감사와 문서/운영 지침 감사를 분리했다.
  - [x] author/comment metadata가 resolver scoring/evidence count에서 independent evidence로 쓰이는지 확인할 별도 audit bucket을 추가했다. `comment_context_resolution_without_attribution`와 `comment_author_match_unverified_used_for_resolution` 기준이다.
  - [ ] `search_only` evidence는 weak로 남기고, `community_banter`, `trope_discussion`, `author_talk`, `recommendation` intent에서는 resolved title 확정을 막는다.
  - [x] completed-source 회귀 감지를 위해 `build_semantic_coverage_audit.py`에 `search_only_resolved_title`, `blocked_intent_resolved_title`, `*_review_only` bucket을 추가했다.
  - [x] VLM/OCR semantic test 명령에서 `--vlm on --ocr on` 누락 시 빠르게 실패하게 하는 옵션/preflight guard를 추가했다. `--require-vlm-ocr-for-images` 또는 `LLM_REQUIRE_VLM_OCR_FOR_IMAGES=1` 기준이다.
  - [x] `image_post_count>0`인데 `vlm_ocr_semantic_review_ready=false`인 run은 manifest뿐 아니라 결과 요약에도 NO-GO 사유와 sample post id를 남긴다.
  - [x] manifest/Summary용 VLM/OCR semantic review skip reason을 `no_image_blocks`, `vlm_disabled`, `ocr_disabled`로 구조화했다. fetch/geometry skip은 per-image status 후속으로 남긴다.
  - [x] `context_sources=image` 또는 `anchor_type=image`만 있고 `image_evidence_catalog`/VLM fetch/chunk counter가 없는 row를 `image_context_without_vlm_catalog` 실패 bucket으로 audit한다.
  - [x] browser screenshot/manifest path만으로 visual evidence를 available로 보지 않고, image loading pending/lazy/data-original/placeholder/incomplete/broken counter를 gate에 반영한다.
  - [x] `failed/timeout/pending/skipped/unsupported/disabled` VLM 상태 문자열은 fetch/chunk evidence가 아니라 blocker로 본다.
  - [x] v414 semantic coverage audit와 v415 action queue를 생성했다. v415는 `image_context_without_vlm_catalog=36`을 `modern_semantic_coverage_source_required` evidence로 포함한다.
  - [x] v417 semantic coverage audit와 v418 action queue를 생성했다. 원본 partial source에서 `comment_context_resolution_without_attribution=19`, `comment_author_match_unverified_used_for_resolution=0`을 확인했다.
  - [x] v419 semantic coverage audit와 v420 action queue를 생성했다. 원본 partial source에서 `search_only_resolved_title=6`, `blocked_intent_resolved_title=7`을 확인했고, `vlm_ocr_browser_visual_gate`를 P0 approval blocker로 승격했다.
  - [x] v421 search-only/blocked-intent bucket 정성 triage를 작성했다. unique post `11`, `HOLD=4`, `REJECT=7`이며 원본 partial source의 승인 근거가 아니라 후속 re_search/re_judge 우선순위다.
  - [x] v422 follow-up 입력 package를 생성했다. `tests\inputs\test01.jsonl`에서 post rows `11`, comment rows `25`, image/browser target `6`, missing post `0`을 복원했다.
  - [x] v422 targeted rerun을 VLM/OCR on 기준으로 실행했다. completed/failed/pending `11/0/0`, requested/effective parallel `36/11`, shard lifecycle `auto_up=false`, `auto_recreate=false`, `reuse_shards_only`다.
  - [x] 이번 후속 라운드도 Codex `spawn_agent` subagent 3개로 source 복원, semantic gate, runtime/shard 계약을 병렬 분리했다. 이는 `expert_main.py --parallel` worker 수와 별개다.
  - [x] v423 자동 after-review `11/11 ACCEPT`는 과낙관으로 분류하고 semantic gate 근거에서 제외했다.
  - [x] v424 coverage audit를 생성했다. search-only/blocked-intent resolved title은 `0/0`으로 개선됐지만 `browser_visual_required/available/missing=6/0/6`이 남아 `REVIEW-LOCKED`다.
  - [x] v425 수동 라벨을 작성했다. `ACCEPT=8`, `HOLD=2`, `REJECT=1`이며, `11718098` positive alias/title-discussion 과차단이 남았다.
  - [x] v426/v429 coverage audit에 외부 browser artifact manifest를 연결해 targeted follow-up의 browser visual evidence를 sidecar로 읽게 했다.
  - [x] v423 자동 after-review 과낙관 원인을 보정했다. 이전 `human_review/comment_url_verify` follow-up이 닫히지 않았거나 positive alias 후보가 과차단되면 자동 ACCEPT로 올리지 않는다.
  - [x] `11718098` positive alias/title-discussion 과차단을 v428에서 재검증했다. context-only 표면어 제거와 `search_query_reviews.keep` positive seed를 분리해 `마법 좋아좋아좋아`로 resolved 됐다.
  - [x] v429 guarded after-review를 생성했다. `ACCEPT=9`, `HOLD=2`, `REJECT=0`이며 남은 HOLD는 `11718049`, `11718083`이다.
  - [x] v430 refined semantic coverage audit를 생성했다. targeted coverage gate는 `REVIEW`이고 browser visual `required/available/missing=6/6/0`, image catalog `6/0`, comment metadata/dialogue `7/0`과 `7/0`이다.
  - [x] v430에서 `11718097` comment author unverified resolution과 `11718075` search-only resolved title은 hard blocker가 아니라 packet-level review-only로 내려갔다. hard counts는 각각 `used_for_resolution=0`, `search_only_resolved_title=0`이다.
  - [x] worker 결과를 메인 Codex가 통합했다.
  - [x] process snapshot audit와 semantic coverage audit 검증 결과를 `VERIFICATION_RESULTS.md`에 기록한다.
  - [x] process snapshot이 Windows 권한 문제로 `available=false`이면 runtime `GO`와 별도로 운영 권한/터미널 상태를 기록한다.
  - [x] focused combined unittest와 `git diff --check`를 최종 확인한다.
  - [ ] 이후 goal/test audit에서 sandbox 수집 실패 시 v397 방식처럼 외부 snapshot JSON을 함께 남긴다.
  - [x] v425 외부 browser screenshot/snapshot artifact를 semantic coverage audit sidecar manifest로 연결해 targeted follow-up에서는 `browser_visual_missing=0`을 확인했다.
  - [x] `11718098` positive alias/title-discussion 과차단을 P1로 두고 재실행했다. v428 결과는 `is_relevant=true`, `official_title=마법 좋아좋아좋아`, confidence `Medium`이다.
  - [x] `11718049` comment URL 후보는 최신 코드 v433에서 `recommendation_request`/`adjacent_relevant` 후보로 보존됐다.
  - [ ] `11718083` quote/title recall은 `human_review`로 유지한다.
  - [x] v423 자동 after-review가 `11/11 ACCEPT`로 과낙관 판정한 원인을 보정했다. v429 guarded after-review는 `ACCEPT=9/HOLD=2`로 후속 미종결 케이스를 보존한다.
  - [ ] v430은 targeted follow-up의 coverage blocker 완화이며 전체 10만 건 승인 근거가 아니다. completed source와 expanded review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`/`NO-GO`로 유지한다.

## 2026-05-31 v394 goal action queue

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `tools\build_goal_action_queue.py`와 `tests\test_goal_action_queue.py`를 추가했다.
  - [x] v393 상태맵에서 v394 action queue를 생성했다.
  - [x] `ready_now=4`, `blocked_until_completed_source=4`, `approval_blockers=4`로 분리했다.
- 다음 작업:
  - [x] focused unittest와 `py_compile`을 최종 확인했다.
  - [ ] ready action 4개는 새 canary/rerun 때마다 운영 절차로 적용한다.
  - [ ] blocked action 4개는 completed VLM/OCR-on source 확보 후 실행한다.
  - [ ] approval blocker 4개가 닫히기 전 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v393 goal current-state map

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `tools\build_goal_current_state_map.py`와 `tests\test_goal_current_state_map.py`를 추가했다.
  - [x] 원본 result, v386 preflight, v391 runtime audit, v392 reason hygiene scan을 입력으로 v393 상태맵을 생성했다.
  - [x] 상태맵이 원본 source approval `NO-GO`, 소규모 runtime `GO`, reason hygiene `GO`, 10만 semantic approval `REVIEW-LOCKED`를 분리 보고한다.
- 다음 작업:
  - [x] focused unittest와 `py_compile`을 최종 확인했다.
  - [ ] completed VLM/OCR-on source 확보 전까지 원본 source는 regression seed로만 사용한다.
  - [ ] completed source에서 random baseline 1000건 이상과 P0/P1 high-risk expansion을 분리 실행한다.

## 2026-05-31 v392 expression reread colon-payload guard

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] public reason이 `표현 오타/축약 패턴(범용): ...` 형식으로 보이지 않도록 문장형 경계로 바꿨다.
  - [x] `tools\scan_reason_hygiene.py`에 `surface_reread_label_colon_payload` hit를 추가했다.
  - [x] 운영/리뷰 문서에 label 뒤 payload 금지 원칙을 반영했다.
- 다음 작업:
  - [x] focused unittest와 `py_compile`을 실행했다.
  - [x] latest clean canary 4건 raw reason hygiene scan에서 colon payload hit가 없음을 확인했다.
  - [ ] 10만 semantic approval은 completed source와 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 v391 goal/test audit auto log discovery

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `tools\audit_goal_test_run_contract.py`가 `run_id` 기반으로 expert log를 자동 탐색한다.
  - [x] log evidence가 없으면 `runtime_contract=REVIEW`로 낮추는 guard를 추가했다.
  - [x] v381 manifest-only 감사에서 자동 log discovery가 동작함을 확인했다.
- 다음 작업:
  - [ ] 이후 소규모 goal/test 완료 보고에는 audit의 `log_evidence_present=true`를 함께 확인한다.
  - [ ] runtime audit `GO`와 semantic approval은 계속 분리한다.

## 2026-05-31 v390 goal/test run contract audit

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 소규모 goal/test run 완료 후 manifest/log 계약을 확인하는 `tools\audit_goal_test_run_contract.py`를 추가했다.
  - [x] `requested_parallel`, `effective_parallel`, lifecycle flags, forbidden log hit, VLM/OCR ready를 같은 audit artifact에 남긴다.
  - [x] v381 clean canary manifest/log를 실제 감사해 `runtime_contract=GO`를 확인했다.
- 다음 작업:
  - [ ] 이후 goal/test rerun은 완료 보고 전에 audit JSON/Markdown을 함께 남긴다.
  - [ ] runtime audit `GO`와 semantic approval은 계속 분리한다.

## 2026-05-31 v389 expression reread active label cleanup

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독 active label을 `표현 오타/축약 패턴(범용)` 하나로 재정리했다.
  - [x] prompt/reason/report/test 기대 문구에서 확장 label drift를 제거했다.
  - [x] 운영 리뷰 지침과 자연어 리뷰 루프 문서를 같은 wording으로 맞췄다.
- 다음 작업:
  - [ ] latest canary 또는 expanded review 전 raw reason hygiene scan으로 old wording drift를 확인한다.
  - [ ] 10만 semantic approval은 completed source와 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 v388 downstream builder locked-source gate

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] random control builder가 locked/missing/mismatched preflight source를 exit code 2로 막게 했다.
  - [x] round2 high-risk builder가 locked/missing/mismatched preflight source를 exit code 2로 막게 했다.
  - [x] helper unit test와 실제 v386 locked preflight dry-run을 통과했다.
- 다음 작업:
  - [ ] approval 자동화 명령에는 preflight뿐 아니라 random/round2 builder에도 `--fail-on-locked-source`를 붙인다.
  - [ ] completed source 확보 전까지 현재 source는 regression seed 또는 targeted triage source로만 쓴다.
  - [ ] 10만 semantic approval은 completed source와 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 v387 expression reread generic label narrowing

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] public label을 `표현 오타/축약 패턴(범용)`으로 좁혔다.
  - [x] prompt와 운영 문서에서 active wording이 특정 표면 복원/계열 규칙처럼 읽히지 않게 정리했다.
  - [x] 테스트 기대 문구를 새 label로 맞췄다.
- 다음 작업:
  - [x] focused final semantic reread unittest와 `py_compile`을 실행했다.
  - [ ] latest canary 또는 expanded review 전 raw reason hygiene scan으로 old wording drift를 확인한다.
  - [ ] 10만 semantic approval은 completed source와 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 v386 preflight fail-on-locked CLI gate

- 상태: implemented / validation passed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] preflight CLI에 `--fail-on-locked` 옵션을 추가했다.
  - [x] 기본 실행은 기존 종료코드 0을 유지하게 했다.
  - [x] 옵션 사용 시 `gate.overall=REVIEW-LOCKED`이면 종료코드 2를 반환하게 했다.
  - [x] 원본 objective source로 v386 preflight를 실행해 `exit_code=2`를 확인했다.
  - [x] focused unittest 4건과 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] 자동화에서 approval 전 preflight를 실행할 때는 `--fail-on-locked`를 사용한다.
  - [ ] completed source 확보 전까지 현재 source는 regression seed로만 쓴다.

## 2026-05-31 v385 expression reread generic wording correction

- 상태: wording contract GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] final semantic reread prompt에서 특정 계열 예시처럼 보이는 문구를 제거했다.
  - [x] 회귀 테스트가 범용 label 문구와 old wording 부재를 확인하게 했다.
  - [x] 운영/리뷰 문서에 `표현 오타/축약 패턴(범용)` active rule을 다시 고정했다.
  - [x] `py_compile`과 focused unittest 9건을 통과했다.
- 다음 작업:
  - [ ] latest canary 또는 expanded review 전 raw reason hygiene scan으로 old wording drift를 확인한다.
  - [ ] 새 문서/보고서에서는 과거 표면형 복원 표현을 historical observation으로만 다룬다.
  - [ ] 10만 semantic approval은 completed source와 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 v384 preflight source policy clarification

- 상태: source-policy clarity GO / original source REVIEW-LOCKED
- 완료:
  - [x] preflight가 manifest partial signal을 source policy에 반영하도록 보강했다.
  - [x] 원본 partial final result를 `partial_final_result_json` / `manifest_partial_run`으로 분류한다.
  - [x] gate에 `required_next_actions`를 추가했다.
  - [x] v384 preflight JSON/Markdown을 생성했다.
  - [x] focused unittest 3건과 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] `obtain_completed_source` 없이는 random/high-risk expansion을 approval 근거로 쓰지 않는다.
  - [ ] completed source 확보 후 preflight를 재실행한다.

## 2026-05-31 v383 original source preflight after affected-row recovery

- 상태: original source REVIEW-LOCKED / docs language guard updated
- 완료:
  - [x] v382 affected-row recovery 이후 원본 objective source를 다시 preflight했다.
  - [x] 원본 result rows `71`, manifest `104502/80/71/9/0`, random shortfall `929`를 재확인했다.
  - [x] preflight gate가 `run_integrity=REVIEW`, `semantic_preflight=REVIEW-LOCKED`, `overall=REVIEW-LOCKED`임을 확인했다.
  - [x] preflight Markdown heading/field label을 한국어 중심으로 고쳤다.
  - [x] 한국어 review artifact heading 회귀 테스트를 추가했다.
- 다음 작업:
  - [ ] original objective file은 regression seed로만 쓰고 approval source로 쓰지 않는다.
  - [ ] source gate를 열려면 새 completed source 또는 충분한 completed subset을 확보한다.
  - [ ] completed source 확보 전 random/high-risk expansion은 approval 근거가 아니라 부족 증거로만 둔다.

## 2026-05-31 v380-v382 original affected-row recovery matrix

- 상태: affected-row targeted regression GO / original approval NO-GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718103`을 v380 단건 clean canary로 분리했다.
  - [x] `11718096`을 v381 단건 clean canary로 분리했다.
  - [x] v380/v381 모두 VLM/OCR on, requested/effective parallel `36/1`, shard lifecycle blocked를 확인했다.
  - [x] v372/v379/v380/v381 clean set reason hygiene scan에서 `files_scanned=4`, `hit_files=0`, `clean_files=4`를 확인했다.
  - [x] v382 affected-row recovery matrix와 labels JSONL을 남겼다.
- 다음 작업:
  - [ ] affected-row targeted regression을 10만 semantic approval 근거로 확대 해석하지 않는다.
  - [ ] 다음 큰 진전은 completed source 확보 또는 random baseline/high-risk expansion이다.
  - [ ] 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v377-v379 original stale reason affected rows follow-up

- 상태: affected-row targeted recovery GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원본 reason hygiene affected rows `11718102`, `11718096`을 VLM/OCR on으로 재검증했다.
  - [x] v377 run manifest에서 requested/effective parallel `36/2`, completed/flushed/pending/failed `2/2/0/0`, shard lifecycle blocked를 확인했다.
  - [x] `11718096`은 direct `기계공주` surface와 official URL evidence로 `ACCEPT/Medium` 처리했다.
  - [x] `11718102` v377 dirty reason의 `단정하기 어려움할` suffix drift를 scanner와 sanitizer로 잡았다.
  - [x] `11718102` v378 scope drift를 막기 위해 non-relevant/no-title/no-anchor platform meta를 `context_only`로 낮췄다.
  - [x] v379 run에서 requested/effective parallel `36/1`, VLM/OCR on, `context_only/title-null`, reason hygiene clean을 확인했다.
- 다음 작업:
  - [ ] v377/v378은 approval source가 아니라 historical repro evidence로만 둔다.
  - [ ] expanded sample에서 `단정하기 어려움할` 또는 비관련/no-anchor `unresolved_matchable`가 재등장하면 P1 public-output/scope-field 회귀로 승격한다.
  - [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v376 expression reread wording contract

- 상태: public wording contract GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독 public label을 `표현 오타/축약 패턴(범용)` 상수로 고정했다.
  - [x] 새 prompt/reason/report/checklist에서 old wording drift를 쓰지 않게 정리했다.
  - [x] `tools\scan_reason_hygiene.py`에 `reread_wording_drift` 패턴을 추가했다.
  - [x] focused reason hygiene tests 2건, focused semantic reread/reason tests 3건, `py_compile`을 통과했다.
- 다음 작업:
  - [ ] 새 targeted run 또는 expanded sample approval 전에는 reason hygiene raw scan에서 `reread_wording_drift` hit도 같이 확인한다.
  - [ ] 재해독 후보는 특정 raw surface/정상형/계열 규칙이 아니라 packet-local 범용 재독해 신호로만 보고한다.

## 2026-05-31 v375 original result reason hygiene scan

- 상태: original result approval NO-GO / regression seed GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] objective 원본 `out\expert_result_20260528_141006_620986.json`를 raw reason hygiene tool로 검사했다.
  - [x] 원본 result에서 `stale_relevant=18`, `llm_flip=9` hit를 확인했다.
  - [x] affected rows `11718085`, `11718103`, `11718102`, `11718096`을 분리했다.
  - [x] manifest `104502/80/71/9/0`, rows `71`, modern review field coverage 부족을 다시 기록했다.
- 다음 작업:
  - [ ] 원본 result는 approval source로 쓰지 않고 regression seed로만 사용한다.
  - [x] affected rows 중 최신 코드 canary가 없던 `11718102`, `11718096`은 v377-v379에서 VLM/OCR on targeted rerun을 완료했다.
  - [ ] 10만 semantic approval은 completed source와 expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v374 reason hygiene raw scan tooling

- 상태: scan tooling GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v373 raw text reason hygiene scan을 `tools\scan_reason_hygiene.py`로 고정했다.
  - [x] `--min-version 360`에서 v번호 없는 JSON을 제외하게 했다.
  - [x] `*_tool_report.json`을 기본 제외해 스캔 리포트 자체가 다음 스캔을 오염시키지 않게 했다.
  - [x] `.gitignore` 예외를 추가해 `tools\scan_reason_hygiene.py`가 git 추적 가능하게 보이도록 했다.
  - [x] v374 tool report에서 `files_scanned=12`, `hit_files=10`, `clean_files=2`를 재현했다.
  - [x] focused unittest와 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] expanded sample이나 새 targeted run마다 latest canary를 approval source로 쓰기 전 `tools\scan_reason_hygiene.py --min-version <v>`를 같이 실행한다.
  - [ ] 이 raw scan tooling은 public-output hygiene 보조 증거이며 10만 semantic approval 근거로 단독 사용하지 않는다.

## 2026-05-31 v373 v360-v372 reason hygiene raw scan

- 상태: latest targeted canaries clean / historical artifacts kept as repro / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v360 이후 result JSON 12개를 raw text 기준으로 스캔했다.
  - [x] v360-v369와 v371은 historical repro artifact라 금지 패턴이 남아 있음을 분리 기록했다.
  - [x] v370과 v372는 raw text forbidden scan이 clean임을 확인했다.
  - [x] raw scan 산출물과 labels JSONL을 남겼다.
- 다음 작업:
  - [ ] historical repro artifact를 current approval source로 섞지 않는다.
  - [ ] expanded sample은 최신 코드 결과 또는 validated completed subset 기준으로 새로 구성한다.
  - [ ] 10만 semantic approval은 random baseline `1000+`와 P0/P1 high-risk expansion 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v371-v372 BatchMem summary and ranked reason hygiene

- 상태: BatchMem summary GO / ranked reason hygiene GO after v372 / semantic gate REVIEW-LOCKED
- 완료:
  - [x] BatchMem seed preload log 기본값을 summary 모드로 축약했다.
  - [x] `PIPELINE_BATCHMEM_SEED_LOG_MODE=summary|full|off` 계약을 추가했다.
  - [x] v371에서 summary 출력은 성공했지만 ranked/search path public reason에 `작품 seed 제외:`가 재등장한 것을 `HOLD`로 기록했다.
  - [x] v372에서 `11718085`를 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재확인했다.
  - [x] v372 result scan에서 `seed 후보(`, `작품 seed 제외`, stale relevant template 계열 금지 패턴이 검출되지 않았다.
  - [x] focused reason hygiene unittest 5건, BatchMem logging unittest 5건, `py_compile`을 통과했다.
- 다음 작업:
  - [ ] expanded sample에서 ranked/search path가 raw seed term을 다시 공개하면 P1 output-hygiene 회귀로 승격한다.
  - [ ] 운영 중 per-alias seed preload 상세 로그가 필요하면 임시로만 `PIPELINE_BATCHMEM_SEED_LOG_MODE=full`을 쓴다.
  - [ ] 이 targeted hygiene 회복을 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v365-v370 relevant-no-title follow-up

- 상태: targeted public-output guard GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원본 result의 `is_relevant=true`, `official_title=null` 후보 `11718085`, `11718103`을 current VLM/OCR on으로 재확인했다.
  - [x] v365에서 `11718085` reason의 stale relevant template과 raw seed 반복을 `HOLD`로 분리했다.
  - [x] v368에서 `seed 후보(...)`, `작품 seed 제외:` 회귀를 재현하고, v370에서 `표현 오타/축약 패턴(범용)` 경계 문구로 회복했다.
  - [x] focused unittest 5건과 `py_compile`을 통과했다.
  - [x] `v365_v370_relevant_no_title_followup_ko.md`와 labels JSONL을 남겼다.
- 다음 작업:
  - [ ] expanded sample에서 장르/축약/비표준 조합 surface가 raw seed 후보로 다시 공개되면 P1 output-hygiene 회귀로 승격한다.
  - [ ] BatchMem/slang seed 초기 로그 축약 옵션을 검토한다.
  - [ ] 이 targeted guard를 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v364 original-vs-current delta follow-up

- 상태: original result approval NO-GO / regression seed GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 목표 파일 `out\expert_result_20260528_141006_620986.json` manifest와 rows 구조를 다시 확인했다.
  - [x] 원본 rows `71`, relevant `29`, irrelevant `42`, official_title rows `27`, modern scope/comment/image evidence coverage `0`을 기록했다.
  - [x] 원본 known-bad 4건과 v360/v363 current small-run delta를 한국어 산출물로 남겼다.
  - [x] 원본 result는 approval source가 아니라 regression seed source로만 쓰도록 gate를 분리했다.
- 다음 작업:
  - [ ] 원본 result rows 전체의 wrong-title/failure pattern은 expanded review 입력으로만 사용하고, 현재 품질 승인 근거로 쓰지 않는다.
  - [ ] modern scope/comment/image evidence 필드가 포함된 새 run 또는 expanded sample으로만 semantic quality gate를 평가한다.
  - [ ] 원본에서 `is_relevant=true`인데 official_title이 없는 `11718085`, `11718103` 같은 케이스는 후속 targeted sample 후보로 둔다.

## 2026-05-31 v360/v363 small-run issue follow-up

- 상태: small-run named-case GO / `11718083` HOLD / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v360 known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
  - [x] v360 manifest에서 completed/flushed/pending/failed `4/4/0/0`, requested/effective parallel `36/4`, image_post_count `3`, shard lifecycle blocked를 확인했다.
  - [x] `11718091` public reason이 raw surface/seed 후보를 해석 근거처럼 반복하는 output hygiene 이슈를 발견했다.
  - [x] v363 단건 canary에서 `표현 오타/축약 패턴(범용)`와 `직접 작품 앵커 없음`만 해석/판정 근거로 남고, `seed 후보(...)`, `작품 seed 제외: ...` raw 후보 반복이 사라진 것을 확인했다.
  - [x] 관련 리뷰 산출물과 label JSONL을 한국어 기준으로 갱신했다.
- 다음 작업:
  - [ ] `11718083` memory-query secondary reference 후보는 quote/source alignment 없으면 자동 ACCEPT 또는 강한 evidence로 쓰지 않는다.
  - [ ] expanded sample에서 surface reread branch가 raw seed 후보를 public reason에 다시 노출하면 wording bug로 승격한다.
  - [ ] Discourse 1차 출력이 짧은 반응을 작품 토론으로 과승격하는 패턴은 semantic guard 누락 여부를 계속 감시한다.
  - [ ] BatchMem/Slang DB seed 주입 로그가 targeted run 가독성을 해치므로 축약 출력 옵션을 검토한다.
  - [ ] 이 small-run 결과를 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v359 expression reread generic-pattern follow-up

- 상태: prompt/output contract tightened / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독 public wording을 `표현 오타/축약 패턴(범용)`로 고정했다.
  - [x] 프롬프트와 reason에서 구체 설명 범주가 자동 차단/허용 규칙처럼 반복되지 않게 `작품 고유 앵커 부족` 중심 문구로 바꿨다.
  - [x] 표면 재해독 차단은 특정 단어 계열이 아니라 `surface_paraphrase_notes`/semantic review 경계 신호가 있을 때만 작동하도록 정리했다.
  - [x] `py_compile`과 focused semantic reread unittest 13건을 통과했다.
- 다음 작업:
  - [ ] 새 review/report/reason에서 구체 표면어, 정규화 값, 계열별 deterministic rule이 재등장하면 wording bug로 승격한다.
  - [ ] 이 targeted wording guard를 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v358 goal completion follow-up

- 상태: targeted GO / full goal NOT COMPLETE / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v356/v357 이후 원 goal을 requirement-by-requirement로 다시 감사했다.
  - [x] targeted known-bad canary와 public reason guard는 `GO`로 분리했다.
  - [x] 원본 result approval source는 partial/coverage gap 때문에 `NO-GO`로 유지했다.
  - [x] 남은 P0/P1 action queue를 `v358_remaining_action_queue_ko.md`로 재정렬했다.
- 다음 작업:
  - [ ] completed source 또는 validated completed subset 확보.
  - [ ] random baseline `1000+`와 P0/P1 high-risk expansion 실행.
  - [ ] `11718083` actual quote/title recall은 human/full-text/source evidence 전까지 자동 ACCEPT하지 않는다.
  - [ ] Codex in-app Browser closure와 Playwright fallback evidence를 분리 유지한다.
  - [ ] comment/IP attribution large coverage를 별도 bucket으로 확장한다.

## 2026-05-31 v356/v357 public reason guard follow-up

- 상태: targeted canary GO / one HOLD remains / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v356 known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
  - [x] v356 manifest에서 completed/flushed/pending/failed `4/4/0/0`, effective parallel `4`, shard lifecycle restart 없음, VLM/OCR on을 확인했다.
  - [x] v356에서 `11718083`, `11718091`, `11718097`, `11718099`의 expected boundary가 유지됨을 확인했다.
  - [x] v356 Round2 review에서 `ACCEPT=3`, `HOLD=1`을 확인했다.
  - [x] v356 `11718091` 공개 reason에 원문에 없는 정규화 해석 괄호가 남은 것을 public-output wording bug로 기록했다.
  - [x] v357 단건 canary에서 해당 해석 괄호/치환 회귀가 사라지고 `context_only/title-null`이 유지됨을 확인했다.
- 다음 작업:
  - [ ] `11718083` actual quote/title recall은 human review 또는 더 강한 source alignment 전까지 자동 ACCEPT하지 않는다.
  - [ ] public-output guard는 targeted 증거이므로 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v355 expression reread public-output follow-up

- 상태: public reason wording tightened / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독은 `표현 오타/축약/띄어쓰기 패턴`의 범용 후보라는 설명만 공개 reason에 남기고, 표면어 후보를 `: X; Y`처럼 별도 나열하지 않게 했다.
  - [x] 표면 재해독 후보를 공개 `작품 seed 제외` 목록에서 제거했다. 원문 title/body/comment에는 남지만, seed 제외 리스트로 다시 규칙화하지 않는다.
  - [x] legacy `paraphrase` 필드를 sanitizer 기준으로 쓰지 않게 했다.
  - [x] focused unittest 11건과 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] 새 review/report/reason에서 표면어를 `재해독 후보: X; Y` 또는 `X -> Y`처럼 쓰는 회귀가 나오면 wording bug로 승격한다.
  - [ ] 이 targeted wording guard를 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v354 browser fallback visual follow-up

- 상태: Playwright fallback visual captured / IAB target closure pending / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex in-app Browser 연결을 재시도했지만 setup 단계에서 실패해 IAB closure로 보지 않기로 했다.
  - [x] Playwright fallback으로 `11718083`, `11718094` 실제 DC 페이지 full-page screenshot과 snapshot을 확보했다.
  - [x] `11718083`은 이미지 로딩은 됐지만 작품명/quote source anchor가 없음을 확인했다.
  - [x] `11718094`는 소설 발췌처럼 보이는 텍스트는 있지만 title/platform/source anchor가 없음을 확인했다.
- 다음 작업:
  - [ ] IAB target closure는 Codex in-app Browser 연결 복구 뒤 별도로 닫는다.
  - [ ] 두 건 모두 human review 또는 더 강한 source alignment 전까지 자동 ACCEPT하지 않는다.

## 2026-05-31 v353 known-bad canary follow-up

- 상태: targeted canary GO / one HOLD remains / semantic gate REVIEW-LOCKED
- 완료:
  - [x] known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
  - [x] manifest에서 completed/flushed/pending/failed `4/4/0/0`, effective parallel `4`, shard lifecycle blocked를 확인했다.
  - [x] `11718083`, `11718091`, `11718097`, `11718099`의 expected boundary가 유지됨을 확인했다.
  - [x] v353 Round2 review에서 `ACCEPT=3`, `HOLD=1`을 확인했다.
- 다음 작업:
  - [ ] `11718083` actual quote/title recall은 human review 또는 더 강한 source alignment 전까지 자동 ACCEPT하지 않는다.
  - [ ] v353 targeted canary를 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v352 expression reread wording follow-up

- 상태: prompt/output contract tightened / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독은 `표현 오타/축약/띄어쓰기 패턴`의 범용 후보일 뿐 특정 정상형 복원이 아니라고 재확인했다.
  - [x] 비슷한 표면 계열을 자동 차단/허용하는 일반규칙도 금지한다고 코드/문서에 반영했다.
  - [x] `나이/외모/친구/한탄`류 표현은 packet-local 재검토 트리거일 뿐 결정 규칙이 아니라고 명시했다.
- 다음 작업:
  - [ ] 새 review/reason 산출물에서 `X -> Y`식 복원이나 계열별 deterministic rule이 재등장하면 즉시 wording bug로 올린다.
  - [ ] 이 wording 보강을 10만 semantic approval 근거로 승격하지 않는다.

## 2026-05-31 v351 remaining HOLD source-alignment follow-up

- 상태: source alignment searched / two HOLD remain / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718083` exact/near quote 검색을 수행했지만 직접 source alignment를 확인하지 못했다.
  - [x] `11718094` exact/near quote 및 `에세르`/`아르타` character-pair 검색을 수행했지만 직접 source alignment를 확인하지 못했다.
  - [x] 두 건 모두 current wrong-title guard는 `GO`, actual title recall은 `HOLD/human_review`로 분리했다.
- 다음 작업:
  - [ ] 사람 검토, 더 강한 full-text/source search, 또는 사용자 추가 단서 전까지 두 건을 자동 ACCEPT하지 않는다.
  - [ ] browser target 28건은 Codex in-app Browser 연결 복구 뒤 별도 visual evidence로 닫는다.

## 2026-05-31 v350 Browser fallback visual follow-up

- 상태: fallback image evidence captured / Browser screenshot pending / 2 HOLD remain / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718083`, `11718094` 이미지 URL을 fallback HTTP 경로로 확보했다.
  - [x] `11718083` 이미지는 작품명/quote alignment 텍스트 없는 게임/캐릭터 화면임을 확인했다.
  - [x] `11718094` 이미지는 소설 본문 발췌지만 작품명/플랫폼/URL anchor가 없음을 확인했다.
  - [x] 두 건 모두 wrong-title 방지는 맞고, actual title recall은 `HOLD/human_review`로 유지한다고 기록했다.
- 다음 작업:
  - [ ] Codex in-app Browser 제어 연결이 복구되면 실제 DC post page screenshot으로 browser target 28건을 닫는다.
  - [ ] `11718083`은 direct quote/full-text source 또는 사람 검토 없이는 자동 title 확정하지 않는다.
  - [ ] `11718094`는 excerpt source/title을 사람 검토 또는 검색으로 확인하되, 검색만으로 임의 title을 되살리지 않는다.
  - [ ] fallback visual evidence를 10만 semantic approval로 승격하지 않는다.

## 2026-05-31 v349 slang/OCR subtype closure follow-up

- 상태: `11718082` closed / 2 HOLD remain / browser visual pending / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 저장 차단된 OCR/표면형이 official detail URL로 정리된 경우 `slang_db_subtype_closed`로 승인 가능하게 했다.
  - [x] `11718082`를 `ACCEPT/no_action`으로 닫았다.
  - [x] v349 relabel에서 `ACCEPT=13`, `HOLD=2`, `REJECT/REPROCESS/INFO_MISSING=0`을 확인했다.
  - [x] focused regression 42건과 `py_compile`을 통과했다.
- 다음 작업:
  - [x] `11718083`은 fallback visual 확인 결과 direct quote/source alignment가 없어 human review 또는 더 강한 quote source가 필요하다고 재확인했다.
  - [x] `11718094`는 fallback visual 확인 결과 이미지 본문 발췌는 있으나 title/URL anchor가 없어 human review 유지로 재확인했다.
  - [ ] browser target 28건은 Codex in-app Browser 연결이 복구된 뒤 닫는다.
  - [ ] v349 targeted relabel을 10만 semantic approval로 승격하지 않는다.

## 2026-05-31 v348 relabel refinement follow-up

- 상태: false-positive HOLD reduced / HOLD remains / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v347 rerun review의 labeler false positive를 줄였다.
  - [x] v348 relabel에서 `ACCEPT=12`, `HOLD=3`, `REJECT/REPROCESS/INFO_MISSING=0`을 확인했다.
  - [x] 재해독 문구를 특정 치환이 아니라 "표현 오타/축약/띄어쓰기 패턴은 범용 신호"라는 public prompt/reason 계약으로 강화했다.
  - [x] focused regression 41건, surface/semantic seed focused 3건, `py_compile`을 통과했다.
- 다음 작업:
  - [ ] `11718083` actual quote/title recall은 `human_review`로 유지한다.
  - [ ] `11718094` image/dialogue weak scene은 Browser visual evidence와 human review로 확인한다.
  - [ ] `11718082`는 OCR/VLM 표면형과 clean alias/slang_db subtype을 분리 검토한다.
  - [ ] browser target 28건은 Codex in-app Browser visual evidence로 닫는다.
  - [ ] v348 targeted relabel을 10만 semantic approval로 승격하지 않는다.

## 2026-05-31 v347 action queue rerun follow-up

- 상태: targeted rerun completed / HOLD remains / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v345 action queue 48건을 action별 입력/리뷰/browser target으로 재구성했다.
  - [x] `re_judge`/`re_search` combined 15건을 VLM/OCR on, `--parallel 36`, `--reuse-shards-only`, `--no-dashboard`로 재실행했다.
  - [x] run id `20260531_030937_599726`에서 completed/failed/pending `15/0/0`, requested/effective parallel `36/15`를 확인했다.
  - [x] rerun 결과 Round2 relabel에서 `REJECT/REPROCESS/INFO_MISSING`이 0건으로 줄었다.
- 다음 작업:
  - [ ] 남은 `HOLD` 8건을 `human_review`/`re_search`/`slang_db_review`로 닫는다.
  - [ ] browser target 28건은 Codex in-app Browser visual evidence로 확인한다.
  - [ ] 이 targeted 15건 결과를 10만 semantic approval로 승격하지 않는다.

## 2026-05-31 v346 goal completion audit follow-up

- 상태: completion audit added / goal IN_PROGRESS / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원 objective 요구사항을 current evidence 기준으로 다시 대조했다.
  - [x] targeted known-bad `GO`와 원본 source/result approval `NO-GO`를 분리했다.
  - [x] `v346_goal_objective_completion_matrix_ko.md`에 요구사항별 증거, 판정, 남은 작업을 남겼다.
- 다음 작업:
  - [ ] 원본 partial이 아닌 completed source로 large rerun 또는 충분한 completed subset을 확보한다.
  - [ ] random baseline `1000+`와 P0/P1 high-risk bucket expansion을 분리 실행한다.
  - [ ] v345 action queue의 `REJECT/REPROCESS/INFO_MISSING`부터 current-code로 재처리한다.
  - [ ] `11718083` actual quote/title recall은 `human_review` queue로 유지한다.

## 2026-05-31 v345 quote alignment review bucket follow-up

- 상태: review tooling patched / focused tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Round2 review tool에 `quote_alignment_missing_for_memory_query` bucket을 추가했다.
  - [x] memory-query/대사·장면 회수 글에서 후보 공식 페이지 hit와 quote/source alignment support를 분리해 packet/result public fields에 남기게 했다.
  - [x] quote alignment support는 `identity.search_evidence_catalog`, `identity.image_evidence_catalog`, `identity.evidence` 같은 direct evidence catalog만 세고, LLM이 만든 `title_candidates`/`entity_mentions` echo는 세지 않게 했다.
  - [x] focused regression 38건과 `py_compile`을 통과했다.
  - [x] v345 original partial review artifact를 재생성해 source policy가 `final_result_json`, `large_run_complete=false`로 기록되는지 확인했다.
- 다음 작업:
  - [ ] 새 completed source 또는 expanded review에서 `quote_alignment_missing_for_memory_query` population/selected count/label 분포를 산출한다.
  - [ ] `11718083` actual quote/title recall은 여전히 `HOLD/human_review`로 유지한다.

## 2026-05-31 v344 expression reread wording correction

- 상태: docs corrected / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 표현 재해독은 특정 의미 복원이 아니라 `표현 오타/축약 패턴(범용)`라는 active contract로 다시 고정했다.
  - [x] `LLM_JUDGMENT_REVIEW.md`의 오래된 active-looking 항목에서 `N세인 줄`류 우선 해석/`X -> Y`식 표현을 현재 계약으로 정정했다.
  - [x] `SCAN_RESULT_REVIEW_GUIDE.md`와 `EXPERT_ORCHESTRATION_LIMITATIONS.md`에 새 문서/prompt/report에서 복원 예시를 쓰지 않는다는 지침을 보강했다.
  - [x] 재해독은 `표현 오타/축약 패턴`을 범용 후보로만 보고, 특정 표면어의 정상형을 새 산출물에 쓰지 않는다고 재확인했다.
- 다음 작업:
  - [ ] 과거 historical section/result JSON에 남은 구체 치환 문구를 새 산출물로 복사하지 않는다.
  - [ ] expanded review에서는 `surface_expression_reread_candidate`를 과차단/미차단 bucket으로만 집계하고 특정 표면어 규칙으로 승격하지 않는다.

## 2026-05-31 v343 `11718083` quote search follow-up

- 상태: strong quote search attempted / actual title recall HOLD / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718083` v341 result와 log evidence에서 title-null, memory-query guard, visual-only image evidence를 재확인했다.
  - [x] exact quote/variant query와 `하차 이후의 소설 속` 후보를 외부 검색으로 대조했다.
  - [x] 공식 작품 페이지 존재와 quote alignment evidence를 분리했다.
- 다음 작업:
  - [ ] `11718083`은 `human_review` queue로 유지한다.
  - [x] search evidence schema에서 exact quote miss와 candidate official page hit를 분리할 수 있는 field를 검토하고 `quote_alignment_missing_for_memory_query` review bucket으로 추가했다.
  - [ ] memory-query post는 quote/source anchor가 없으면 `official_title=null`을 유지한다.

## 2026-05-31 v342 goal audit follow-up

- 상태: evidence audit added / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원본 10만 결과가 full clean run이 아니라 completed `80`, flushed `71`, pending `9` partial source임을 다시 기록했다.
  - [x] 원본 result의 댓글 text와 current-code의 `comment_metadata`/`comment_dialogue_context_lines` 보존 상태를 비교했다.
  - [x] known-bad 4건에서는 post/comment IP가 없어 IP 기반 원글 작성자 확정은 증명할 수 없고, `author_match_unverified`까지만 가능함을 기록했다.
  - [x] v341 current-code canary가 nickname/comment-id/reply metadata와 image evidence catalog를 남기는지 coverage 산출물로 확인했다.
- 다음 작업:
  - [ ] `11718083`은 wrong-title guard와 actual quote/title recall을 분리해 strong quote search 또는 human review로 보낸다.
  - [ ] expanded review에서 `comment_author_match_unverified_not_independent_evidence`를 별도 bucket으로 유지한다.
  - [ ] full/large rerun 또는 충분한 completed source 확보 전까지 원본 partial run을 approval source로 쓰지 않는다.

## 2026-05-31 v341 known-bad current-code follow-up

- 상태: targeted verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] known-bad 4건을 현재 코드로 묶어 VLM/OCR on, `--parallel 36`, `--reuse-shards-only`, `--no-dashboard` 조건에서 재실행했다.
  - [x] v341 manifest에서 completed/failed/pending `4/0/0`, requested/effective parallel `36/4`, small-run shard lifecycle blocked를 확인했다.
  - [x] `11718083`은 wrong-title 재승격 없이 `official_title=null`, `unresolvable_memory_query`를 유지했다.
  - [x] `11718091`은 `표현 오타/축약 패턴(범용)`로만 남고 `context_only` title-null을 유지했다.
  - [x] `11718097`/`11718099`는 각각 `망겜힐`, `빌환` clean alias positive-control을 유지했다.
- 다음 작업:
  - [ ] `11718083` actual quote/title recall은 `HOLD`로 두고 strong quote search 또는 human review로 분리한다.
  - [ ] `surface_expression_reread_candidate`는 특정 표면어 규칙이 아니라 범용 후보 bucket으로만 expanded review에 반영한다.
  - [ ] `comment_author_match_unverified_not_independent_evidence`, `ocr_conflict_context_overstated`, `clean_alias_positive_control` bucket을 expanded review에서 분리 집계한다.
  - [ ] v341 targeted `GO`를 10만 건 semantic `GO`로 승격하지 않는다.

## 2026-05-31 v340 known-bad latest recheck follow-up

- 상태: targeted verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원본 10만 결과의 known-bad 4건 오판 title을 다시 확인했다.
  - [x] v337 `11718083`은 memory-query deliberate null guard로 `official_title=null`을 유지했다.
  - [x] v338 `11718097`은 `망겜의 힐러`와 문피아 URL로 회복됐다.
  - [x] v331 `11718091`은 범용 표현 재해독 후보 wording과 `context_only`를 유지했다.
  - [x] v334 `11718099`는 `빌어먹을 환생`과 OCR conflict boundary를 유지했다.
- 다음 작업:
  - [ ] `11718083` 실제 원작 회수는 strong quote search 또는 human review action으로 분리한다.
  - [ ] `surface_expression_reread_candidate`, `context_only_no_work_anchor`, `ocr_conflict_context_overstated`, `clean_alias_positive_control`을 expanded review bucket으로 유지한다.
  - [ ] known-bad targeted `GO`를 10만 건 semantic `GO`로 승격하지 않는다.

## 2026-05-31 v339 generic expression reread wording follow-up

- 상태: patched / focused verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독 후단 sanitizer 명칭과 조건을 특정 나이/표면 변환이 아니라 `surface_expression_context` 중심으로 정리했다.
  - [x] `23세` 같은 특정 치환 검색 제안이 아니라, context-only/no-work semantic review와 범용 surface probe에 의해 검색 확장을 제거하도록 했다.
  - [x] test/review fixture의 공개 reason 예시는 `표현 오타/축약 패턴(범용)`로 맞췄다.
  - [x] 운영 문서의 현재 규칙은 `X -> Y`식 결정 치환이 아니라 packet-local 범용 표현 재독해 신호로 정리했다.
- 다음 작업:
  - [x] focused unittest, py_compile, `git diff --check`로 v339 변경을 확인했다.
  - [ ] 과거 run result JSON/오래된 이력의 구체 치환 문구는 historical artifact로만 보고, 새 qualitative review/report에는 deterministic rewrite를 쓰지 않는다.
  - [ ] expanded review에서 `surface_expression_reread_candidate`가 과차단/미차단을 만드는지 random/high-risk로 분리 집계한다.

## 2026-05-31 v336 title-prefix / exact-title / author-surface follow-up

- 상태: patched / focused+live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 검색 결과 제목 정규화에서 `스포)`, `질문)`, `소신발언))` 같은 게시글 말머리를 정식 작품명 후보에서 제거했다.
  - [x] exact-title surface만 있는 `slang_insight`는 public output으로 노출하지 않도록 했다.
  - [x] 작가명 surface는 abbreviation alias로 승격하지 않고 author mapping으로만 유지한다.
  - [x] `11718117` v336 live rerun에서 KakaoPage URL, `slang_insight=null`, Slang DB flush `titles=0`을 확인했다.
- 다음 작업:
  - [ ] expanded review에서 커뮤니티 검색 결과 제목의 말머리/후기/리뷰 꼬리가 official title 후보에 섞인 케이스를 `title_prefix_contamination`으로 집계한다.
  - [ ] `exact_title_not_alias`는 output 미노출/저장 차단과 clean short alias recall 보존을 분리해 샘플링한다.
  - [ ] author surface skip 통계와 author mapping recall을 같이 점검한다.

## 2026-05-31 v334 OCR conflict notes follow-up

- 상태: patched / focused+live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] OCR conflict title prefix가 `analysis.notes`에서 공식/비공식 별칭 주장으로 남는 문제를 중화했다.
  - [x] `11718099` v334 live rerun에서 `빌환` 저장 후보와 `빌어먹을 환생` 최종 제목/문피아 URL을 유지했다.
  - [x] OCR/표지 충돌 후보는 본문/별칭/공식 제목 근거로 승격하지 않는다는 neutral note를 남겼다.
- 다음 작업:
  - [ ] expanded review에서 OCR conflict 후보가 `reason`, `analysis.notes`, `slang_insight.cultural_context` 중 어디에서 과장되는지 field별로 분리한다.

## 2026-05-31 v330 generic reread wording follow-up

- 상태: patched / focused+live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독 prompt/reason 계약을 `표현 오타/축약 패턴(범용)`로 정정했다.
  - [x] `surface_paraphrase_notes`의 public payload에서 예전 `paraphrase` 필드를 숨겨 `X -> Y`식 deterministic rewrite가 LLM 입력으로 재주입되지 않게 했다.
  - [x] 비관련 public reason은 로컬 source surface만 보여주고, 특정 표면어를 정답 표현으로 치환하지 않도록 바꿨다.
  - [x] focused unittest와 `11718091` v331 live rerun으로 public reason/prompt에 deterministic paraphrase가 남지 않음을 확인했다.
- 다음 작업:
  - [ ] 과거 문서의 예전 `X -> Y` 표현은 historical evidence로만 두고, 새 지침/보고서에서는 범용 후보 표현을 사용한다.

## 2026-05-31 v329 OCR conflict cultural context follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] final title과 충돌하는 OCR/표지 후보가 `slang_insight.cultural_context`에서 본문/정식 제목 근거처럼 과장되지 않도록 중화했다.
  - [x] 이 처리를 특정 OCR 문자열 치환이 아니라 `image_evidence_catalog`/final title mismatch 기반 evidence-role sanitizer로 구현했다.
  - [x] known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 v329 재실행했다.
  - [x] v329에서 `11718099`는 `빌어먹을 환생`으로 유지되고 OCR 후보는 final title 근거에서 제외됨을 확인했다.
  - [x] v329에서 `11718091`은 deterministic paraphrase를 코드 출력으로 만들지 않음을 확인했다. v330부터 공개 표현은 `표현 오타/축약 패턴(범용)`로 정정한다.
- 다음 작업:
  - [ ] expanded review에서 `vlm_ocr_title_conflict_with_final_title`가 있는 packet의 `slang_insight.cultural_context`가 OCR 후보를 과장하는지 별도 bucket으로 집계한다.
  - [ ] `11718083` quote recall은 자동 title-null은 수용하되, 실제 원작 회수가 필요하면 human/quote-search action으로 분리한다.
  - [ ] `slang_db` flush에서 OCR 충돌 후보가 confirmed alias로 저장되는지 별도 감사한다.

## 2026-05-30 v325 범용 expression reread / title prefix alias follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 재해독 힌트가 특정 표면어 또는 나이 표현 치환을 코드에서 생성하지 않도록 `surface_expression_reread_notes()`를 범용 candidate 방식으로 바꿨다.
  - [x] 검색 pruning 명칭/조건을 `surface_age_expression`에서 `surface_expression_reread`로 일반화했다.
  - [x] `재벌가 차녀의 2회차` 같은 긴 공식 제목 prefix가 BatchMem alias로 학습되지 않도록 했다.
  - [x] `11718080/11718082`를 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 v325 재실행했다.
  - [x] v325에서 Docker/shard lifecycle 재시작 없이 `requested/effective parallel=36/2`로 실행됨을 확인했다.
- 다음 작업:
  - [ ] expanded review에서 `surface_expression_reread_candidate`가 과차단/미차단을 만드는지 별도 bucket으로 집계한다.
  - [ ] `abbreviation_title_variant_surface_skipped`를 BatchMem/slang alias 오염 방지 지표로 수집한다.
  - [ ] 과거 문서의 구체 치환 문구는 known-bad historical artifact로만 남기고, 새 지침에서는 deterministic rule로 읽히지 않게 계속 정리한다.

## 2026-05-30 v311 OCR/VLM 표면형 official detail follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] OCR/VLM 표면형을 특정 오타 치환으로 고치지 않고, 동일 official detail URL의 locked 공식 후보를 우선하는 범용 가드로 처리했다.
  - [x] 표면형 duplicate reference가 `mentioned_works`, `comparison_target`, `recommendation_candidates`, `future_watch_target`에 별도 작품처럼 남지 않게 했다.
  - [x] `11718080/11718082`를 VLM/OCR on, `--parallel 36`, `--reuse-shards-only`, `--no-dashboard`로 재실행했다.
  - [x] v311에서 `11718082`가 `재벌가 차녀의 2회차 걸그룹`으로 resolved되고, `11718080`은 trope/social-lament title-null로 유지됨을 확인했다.
- 다음 작업:
  - [ ] expanded review에서 `official_detail_title_preferred_over_surface_form`과 `surface_form_duplicate_reference_pruned`를 VLM/OCR 표면형 오염 bucket으로 분리 집계한다.
  - [ ] OCR/VLM 표면 문자열이 `slang_db` confirmed alias나 BatchContext seed로 저장되는지 별도 감사한다.

## 2026-05-30 v308 `author_match_unverified` follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 같은 generic author지만 post IP가 없어 원글 작성자로 확정할 수 없는 댓글을 `author_match_unverified`로 유지했다.
  - [x] `author_match_unverified`만 있는 짧은 캐릭터 반응글은 독립 작품 evidence로 강화하지 않도록 `comment_author_match_unverified_not_independent_evidence` flag를 추가했다.
  - [x] known-bad 4건을 VLM/OCR on, `--parallel 36`, `--reuse-shards-only`, `--no-dashboard`로 재실행했다.
  - [x] v308에서 `11718083`, `11718091`, `11718097`, `11718099`가 기대 상태로 유지됨을 확인했다.
- 다음 작업:
  - [ ] expanded review에서 `author_match_unverified` 댓글이 reason/evidence에서 독립 작품 근거처럼 쓰인 케이스를 별도 집계한다.
  - [ ] post row IP coverage가 낮은 source에서는 same-author generic 댓글을 원글 작성자 확정 근거로 쓰지 않는지 계속 감시한다.

## 2026-05-30 v307 `11718117` regression state follow-up

- 상태: audited / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v292 result/log/manifest 기준 `11718117`이 `아카데미의 피해자`로 resolved되고 KakaoPage URL이 유지됨을 재확인했다.
  - [x] VLM/OCR direct evidence가 작품명/작가/회차를 읽었고 `anchor_type=image`, `anchor_strength=high`로 유지됨을 확인했다.
  - [x] exact-title surface는 운영 slang alias로 저장되지 않았고 Slang DB flush `titles=0`임을 확인했다.
- 다음 작업:
  - [ ] expanded review에서 direct image explicit title과 weak visual-only를 분리 집계한다.

## 2026-05-30 v306 `11718114` visual-only image follow-up

- 상태: visual evidence rechecked / browser tool blocked / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Codex in-app Browser를 재시도했지만 `windows sandbox failed: spawn setup refresh`로 실패함을 확인했다.
  - [x] v286 직접 이미지 파일을 다시 시각 확인했다.
  - [x] 이미지에 작품명/작가명/회차/OCR title direct evidence가 없고, v286 final title-null/adjacent가 맞음을 확인했다.
- 다음 작업:
  - [ ] Browser tool health는 semantic result와 분리해 환경 follow-up으로 유지한다.
  - [ ] expanded review에서 `vlm_ocr_public_state_weak`는 Browser 성공/실패와 direct image evidence grade를 분리 기록한다.

## 2026-05-30 v305 `11718078` positive alias control follow-up

- 상태: live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718078`을 VLM/OCR on, `--parallel 36`, `--reuse-shards-only`, `--no-dashboard`로 단건 재실행했다.
  - [x] `즉사무림 -> 즉사기 들고 무림에 떨어지다`가 `official_title`, `heretic_url`, `title_resolution_state=resolved`, `anchor_type=title_exact`로 유지됨을 확인했다.
  - [x] `11718078`은 `23센줄`류와 같은 오타/축약 후보 해석 bucket이 아니라 title alias + official URL positive-control로 분리했다.
- 다음 작업:
  - [x] `11718114` image/VLM public state는 v306에서 visual-only/title-null `ACCEPT / no_action`으로 정리했다.
  - [x] `11718117` regression state는 v307에서 기존 v292 live artifact 기준 `ACCEPT / no_action`으로 정리했다.
  - [ ] expanded review에서 positive title alias bucket과 context-only/no-work reread bucket을 분리 집계한다.

## 2026-05-30 v304 재해독 후보 해석 wording follow-up

- 상태: patched / tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 전역 규칙으로 읽힐 수 있는 prompt 표현을 제거했다.
  - [x] 재해독은 해당 packet 안에서만 후보 해석으로 검토하고, 다른 post에 재사용하지 않는다고 명시했다.
  - [x] final semantic reread tests 9건과 py_compile을 통과했다.
- 다음 작업:
  - [ ] expanded review에서 오타/축약 후보 해석이 slang alias, search seed, resolved title evidence로 승격되는 케이스를 분리 집계한다.
  - [x] `11718078`처럼 실제 제목 약칭 + 공식 URL evidence가 있는 positive-control은 이 no-hardcoding 가드로 과차단하지 않는지 확인한다.

## 2026-05-30 v303 OCR-noise visual anchor follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v302에서 reason의 `grounding_anchor=search_only`와 public `anchor_type=image`가 충돌하는 field mismatch를 확인했다.
  - [x] `character_visual_only` + OCR 잡음 + 일반 `work_cues`가 image anchor로 승격되지 않도록 weak visual 판정을 구조 필드 기준으로 수정했다.
  - [x] v302 형태의 VLM item을 회귀 테스트에 반영했다.
  - [x] v303 live canary에서 `anchor_type=none`, `anchor_strength=none`, `image_evidence_catalog_count=1`을 확인했다.
  - [x] 재해독 관련 prompt/test/docs 문구에서 일괄 적용처럼 보이는 표현을 제거했다.
- 다음 작업:
  - [ ] expanded review에서 `ocr_noise_visual_anchor_mismatch`를 `weak_visual_only_promoted_to_image_anchor` 하위 유형으로 분리 집계한다.
  - [ ] `11718083` quote recall true-title 회수는 human review 또는 stronger quote search로 따로 처리한다.

## 2026-05-30 v301 weak visual-only image anchor follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718083` v214에서 visual-only 이미지가 `anchor_type=image`, `anchor_strength=medium`으로 남는 field mismatch를 확인했다.
  - [x] VLM 실행 여부와 image primary anchor를 분리했다.
  - [x] weak visual-only VLM 결과는 `context_sources=image`와 `image_evidence_catalog`에 남기되 작품 anchor로 승격하지 않게 했다.
  - [x] v301 live canary에서 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`, `image_evidence_catalog_count=1`, `anchor_type=genre`, `anchor_strength=low`를 확인했다.
  - [x] focused VLM/memory-query tests와 py_compile을 통과했다.
- 다음 작업:
  - [ ] expanded review에서 `weak_visual_only_promoted_to_image_anchor`와 `image_evidence_catalog_missing`을 분리 집계한다.
  - [ ] `11718083` quote recall true-title recovery는 stronger quote search/human review 전까지 `HOLD`로 유지한다.

## 2026-05-30 v300f live prompt/reason follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v300f 디버그 로그에서 `comment_context`, `comment_dialogue_context`, `role=author_match_unverified`, `surface_paraphrase_notes`가 `discourse_semantic_seed_guard` payload에 포함됨을 확인했다.
  - [x] 짧은 인명/캐릭터명 단독 seed와 일반어 검색 조합은 직접 작품 앵커 없이는 keep하지 않도록 prompt/test/docs를 보강했다.
  - [x] 직접 작품 앵커 없는 public reason의 `작품 속/작품 내`류 표현을 약한 문맥 표현으로 낮추는 일반 후처리를 추가했다.
  - [x] v300f final은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 유지했다.
  - [x] final semantic reread tests 9건과 py_compile을 통과했다.
- 다음 작업:
  - [ ] expanded review에서 `reason_overstates_context_only`와 `character_name_only_search_keep` bucket을 계속 감시한다.
  - [ ] raw LLM이 여전히 `작품 속`을 생성할 수 있으므로, public reason과 review label은 후처리된 공개 필드를 기준으로 보되 raw prompt/result drift도 별도 기록한다.

## 2026-05-30 v299 comment dialogue payload key follow-up

- 상태: patched / tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `comment_context_lines`/`comment_dialogue_context_lines`가 semantic seed review payload에 직접 전달되지 않을 수 있는 key mismatch를 확인했다.
  - [x] Discourse semantic seed review에서 `comment_context`가 없으면 `comment_context_lines`를 fallback으로 사용하게 했다.
  - [x] final semantic reread payload에도 `comment_context`, `comment_dialogue_context`를 추가했다.
  - [x] `author_match_unverified` line이 LLM user message에 들어가는지 regression을 추가했다.
  - [x] final semantic reread tests 8건, comment metadata tests 4건, qualitative review packet tests 35건, py_compile을 통과했다.
- 다음 작업:
  - [x] v300f live canary에서 `11718091`의 `discourse_semantic_seed_guard` payload/log가 comment dialogue line을 실제 포함하는지 확인했다.
  - [ ] expanded review에서 `author_match_unverified`를 post_author 발화로 과확정하는 케이스와, 반대로 댓글 맥락을 누락하는 케이스를 분리 집계한다.

## 2026-05-30 v298 semantic reread fixed-rule wording follow-up

- 상태: wording corrected / tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718091` 회귀 입력을 hardcoded block이나 표면 패턴 확정 규칙으로 고정하지 않는 방향으로 final semantic reread 지침을 정정했다.
  - [x] semantic seed review 지침도 표현 오타/축약/띄어쓰기 깨짐의 "재해독 관점"으로 정리했다.
  - [x] 짧은 인명/캐릭터명 단독 seed와 일반어 검색 조합은 직접 작품 앵커 없이 keep하지 않도록 semantic seed review 지침을 보강했다.
  - [x] 직접 작품 앵커 없는 reason은 `작품 속`처럼 작품 존재를 확정하지 않고 약한 표현으로 남기도록 했다.
  - [x] `surface_paraphrase_notes`만으로는 seed/search를 내리지 않고, LLM semantic seed review가 no-work/context-only 위험을 표시한 경우에만 sanitizer가 보조 적용되게 했다.
  - [x] 방금 시도한 deterministic regex 확장은 되돌려 새 조사/표면 패턴 규칙을 추가하지 않았다.
  - [x] final semantic reread tests는 v300f 기준 9건, qualitative review packet tests 35건, py_compile을 통과했다.
- 다음 작업:
  - [ ] expanded review에서 `surface_paraphrase`/`semantic_seed_review`가 과차단 규칙처럼 동작하는지 별도 bucket으로 감시한다.
  - [ ] `11718091`류는 direct title evidence 없이 resolved title로 재승격되는지 계속 `final_semantic_reread_missing_for_semantic_seed`로 본다.

## 2026-05-30 v297 goal objective completion audit follow-up

- 상태: audited / goal NOT COMPLETE / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원본 `out\expert_result_20260528_141006_620986.json` manifest를 재확인해 `104502` 입력 중 `80` completed, `71` flushed인 partial artifact임을 기록했다.
  - [x] 원본 wrong-title 4건과 current targeted/v296 회복 상태를 요구사항별로 대조했다.
  - [x] `qualitative_review\20260528_141006_620986\v297_goal_objective_completion_audit_ko.md`를 작성했다.
- 다음 작업:
  - [ ] `11718083` quote/memory-query recall은 stronger quote search 또는 human review 없이는 title 확정하지 않는다.
  - [ ] `11718091` author/IP unverified dialogue bucket을 expanded sample에서 계속 검증한다.
  - [x] `11718117` 등 v296 P1 잔여 action queue를 처리했다. `11718078`은 v305 positive-control, `11718114`는 v306 visual-only/title-null, `11718117`은 v307 direct image title regression audit로 처리했다.
  - [ ] random control v3 1,000건과 P0/P1 high-risk expansion 전까지 active goal은 complete로 닫지 않는다.

## 2026-05-30 v296 goal known-bad semantic review tooling follow-up

- 상태: patched / review regenerated / tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v296 after-review를 재생성해 `11718099` generic bridge 오탐이 사라지고 `ACCEPT / no_action`으로 바뀐 것을 확인했다.
  - [x] `11718097`의 `critical_counter_but_resolved`는 minor alias normalization + official evidence로 분리되어 `ACCEPT / no_action`이 됐다.
  - [x] `23센줄`류 non-relevant reason에서 LLM이 만든 "작품 자체에 대한 논의" 과잉 표현을 일반 잡담/미특정 맥락으로 낮추는 가드를 추가했다.
  - [x] final semantic reread tests 6건, focused semantic reason tests 3건, qualitative review packet tests 35건, py_compile을 통과했다.
- 다음 작업:
  - [ ] `11718083` memory-query/quote recall은 human review 또는 더 강한 quote search evidence 없이 단일 title을 확정하지 않는다.
  - [ ] `11718091`의 `comment_author_match_unverified_dialogue`는 댓글 author/IP가 없는 익명 댓글을 post author 발화로 쓰지 않는지 expanded review에서 계속 본다.
  - [ ] v296은 21건 targeted review이므로 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v294 semantic reread / critical-counter follow-up

- 상태: verified / tooling split completed in v296 / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `23센줄`은 `23세인 줄` 오타/축약이라는 사용자 지적을 current-code 테스트로 재확인했다.
  - [x] `tests.test_final_semantic_reread_gate` 5건이 통과해 search-only 후보가 후단에서 다시 올라온 경우 `final_semantic_reread`가 낮추는 계약을 확인했다.
  - [x] `tests.test_expert_main_comment_metadata` 4건이 통과해 댓글 author/ip/comment_id가 대화 메타로 보존되는지 확인했다.
  - [x] v287 live run 기준 `11718091`은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`로 유지됨을 재확인했다.
  - [x] `11718097`의 v285 `critical_counter_but_resolved` / `HOLD`는 true critical counter가 아니라 minor alias normalization counter였음을 분리했다.
  - [x] v296 review builder/label에서 `minor_alias_normalization_counter`와 true critical counter를 분리했다.
- 다음 작업:
  - [x] `11718078`의 `critical_counter_but_resolved`는 v305에서 title alias + official URL positive-control로 분리해 `ACCEPT / no_action` 처리했다.
  - [ ] expanded review에서 `final_semantic_reread_reviewed`, `surface_paraphrase_non_title_terms_removed`, `semantic_seed_review_non_title_terms_removed` 과차단/미차단을 분리 집계한다.
  - [ ] 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v291 BatchMem exact-title alias guard follow-up

- 상태: patched / unit tests verified / live canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v290 `11718117`은 운영 `slang_db` 저장이 아니라 BatchMem 내부 exact-title alias 등록 노이즈였음을 분리했다.
  - [x] normalized alias와 normalized title이 같으면 BatchMem resolved/pending alias로 등록하지 않게 했다.
  - [x] `abbreviation_exact_title_skipped` 통계를 추가했다.
  - [x] BatchMem/final semantic reread/VLM URL focused regression 18건과 `py_compile`을 통과했다.
  - [x] v292 `11718117` live run에서 `BatchMem: 약칭 즉시등록 '아카데미의 피해자'` 로그가 남지 않는지 확인했다.
  - [x] v292 result/log에서 `store_reason=exact_title_not_alias`, Slang DB flush `titles=0`, VLM `fetch=1/1`, KakaoPage URL 유지를 확인했다.
- 다음 작업:
  - [ ] expanded review에서 `exact_title_not_alias`, `sentence_like_alias_surface`, `pure_work_alias` 상태별 recall impact를 분리한다.
  - [ ] 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v290 `11718117` image platform URL follow-up

- 상태: patched / live canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718117` direct image title + author에서 official URL missing/다른 플랫폼 URL 기울기 경로를 재현했다.
  - [x] promotable image anchor의 title/author 검증 검색을 image-only pruning에서 보호했다.
  - [x] `원작 주인공` 같은 웹소설 소개문 표현을 단독 derivative/fanfic marker로 보지 않게 했다.
  - [x] v290 live run에서 `아카데미의 피해자` URL이 `https://page.kakao.com/content/66611775`로 정리됨을 확인했다.
  - [x] `23센줄 -> 23세인 줄` final semantic reread test 5건이 계속 통과함을 확인했다.
- 다음 작업:
  - [ ] expanded review에서 `ocr_explicit_title_unresolved`, `image_platform_url_preference`, `derivative_marker_false_positive` bucket을 별도 집계한다.
  - [ ] 이미지 플랫폼 cue가 final URL을 바꾼 경우 reason/consistency flag가 충분히 공개되는지 대형 표본에서 확인한다.
  - [ ] 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v286/v287 VLM limit / semantic reread follow-up

- 상태: patched / live canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718114`의 `image_too_large:8428632` 원인이 `expert_main.py` 기본 `8MiB`와 pipeline 기본 `16MiB` 불일치임을 확인했다.
  - [x] `expert_main.py` 기본 VLM 이미지 한도를 `16777216`으로 정렬했다.
  - [x] v286 live run에서 `11718114` VLM chunk가 실제 전송되고, visual-only/title-null 판단이 유지되는지 확인했다.
  - [x] `11718091` v287 live run에서 1차 Discourse가 seed/search를 만들더라도 `discourse_semantic_seed_guard`가 다시 읽어 `title_novel_terms=[]`, `search_suggestions=[]`로 낮추는지 확인했다.
  - [x] `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄`, `작품 seed 제외: 23센줄, 은영이`가 public reason에 남는지 확인했다.
  - [x] focused semantic reread tests 11건과 `py_compile`을 통과했다.
- 다음 작업:
  - [x] `11718117`은 direct image title/author가 있는데 official URL이 비어 있거나 플랫폼 URL이 어긋나는 경로를 v290에서 닫았다.
  - [ ] v287에서 보였듯이 2차 LLM도 `은영이`를 medium keep으로 둘 수 있으므로, expanded review에서 `surface_paraphrase_context_terms`/`semantic_seed_review_context_terms` 과차단과 미차단을 따로 집계한다.
  - [ ] Codex in-app Browser control이 `node_repl kernel exited unexpectedly`로 막힌 상태는 browser-tooling follow-up으로 분리한다.
  - [ ] 10만 건 semantic approval은 expanded random baseline과 P0/P1 high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v284/v285 residual semantic review follow-up

- 상태: patched / after-review regenerated / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v284 잔여 P0/P1 21건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 재실행했다.
  - [x] Docker Compose auto up/recreate 없이 기존 shard만 재사용했고, small run은 `effective_parallel=21`로 줄었다.
  - [x] `11718091`은 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄` 의미 재독해와 title null/context-only를 유지했다.
  - [x] `11718080`은 작품 매칭이 아니라 친구/식사/같이 소설 보는 사람에 대한 한탄형 글로 null-title 유지됐다.
  - [x] Round2 리뷰 도구가 제목 약칭 + 공식 상세 URL 케이스를 no-anchor REJECT로 오분류하던 문제를 보정했다.
  - [x] v285 after-review에서 `reason_says_no_anchor_but_resolved=0`, `REJECT=0`을 확인했다.
- 다음 작업:
  - [x] `11718114`는 Browser 재시도 실패를 환경 follow-up으로 분리하고, 직접 이미지 확인 + v286 VLM result로 visual-only/title-null을 닫았다.
  - [x] `11718117`은 direct image title과 공식 URL 검색 동기화를 v290 live canary로 닫았다.
  - [x] `11718082`는 v293 subtype review에서 OCR 오타 `제벨가/결그룹`이 운영 `slang_db`에 저장되지 않았고 `store_in_slang_db=false`, `store_reason=character_attached_composite`로 차단됨을 확인했다.
  - [x] `11718097`의 `critical_counter_but_resolved`는 v294에서 minor alias normalization counter로 분리해 단건 `ACCEPT / no_action`으로 정리했다.
  - [x] `11718078`의 `critical_counter_but_resolved`는 v305에서 final reason/evidence alignment를 확인해 `ACCEPT / no_action` 처리했다.
  - [ ] 10만 건 semantic approval은 expanded random baseline과 P0/P1 high-risk expansion 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v280 final meaning/url guard follow-up

- 상태: patched / live canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `23센줄`류는 final 단계에서도 하드코딩이 아니라 meaning pass/semantic reread 계약으로 처리한다.
  - [x] freeze 단계에서 제거된 stale URL이 호출부 fallback으로 되살아나는 경로를 차단했다.
  - [x] BatchContext alias rescue가 title과 맞지 않는 공식 상세 URL을 재사용하지 않도록 safe URL 검사를 추가했다.
  - [x] `11718091`은 v280에서 null-title/context-only를 유지했다.
  - [x] `11718097`은 v280에서 `망겜의 힐러`와 `https://novel.munpia.com/328421`로 정리됐다.
  - [x] unit 3건, `py_compile`, v280 known-bad 4건 live canary를 통과했다.
- 다음 작업:
  - [ ] expanded review에서 stale URL cleared/repaired flags를 P1/P2 bucket으로 분리해 반복성을 확인한다.
  - [ ] `reason`에 Verifier hold/거부권과 final recovery가 함께 남는 경우 `reason_decision_contradiction` bucket에서 따로 리뷰한다.
  - [ ] title은 맞지만 URL만 repaired된 케이스와 title 자체가 rescued된 케이스를 분리해 gate 품질을 본다.
  - [ ] 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v278 final semantic reread follow-up

- 상태: patched / focused tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 검색 전 seed 재독해와 별도로 final resolved candidate에 대한 `final_semantic_reread` gate를 추가했다.
  - [x] `semantic_seed_review`/`surface_paraphrase`/`context_only_no_work_anchor` risk가 있을 때 원문 title/body/comment와 evidence를 함께 LLM에 전달한다.
  - [x] `REJECT/HOLD/REPROCESS` 또는 `is_specific_work_discussion=false + Weak/Missing evidence`이면 final title을 null로 낮추는 action을 추가했다.
  - [x] `tests/test_final_semantic_reread_gate.py` 전용 회귀 테스트로 `23센줄 -> 23세인 줄` context-only 재독해 후 search-only 후보 demotion을 확인했다.
  - [x] `23센줄` 계열 focused regression 4건과 social-lament/semantic seed regression 7건을 통과했다.
- 다음 작업:
  - [ ] expanded high-risk review에 `final_semantic_reread_reviewed`, `final_semantic_reread_rejected_resolution`, `final_semantic_reread_accepted_resolution` bucket을 추가한다.
  - [ ] final semantic reread가 direct image/VLM title을 과차단하지 않는지 VLM/OCR involved sample에서 확인한다.
  - [ ] final semantic reread가 stable alias/official URL strong evidence를 과차단하지 않는지 random control과 known-alias bucket에서 확인한다.
  - [ ] v278은 focused regression이므로 10만 건 semantic approval로 승격하지 않는다.

## 2026-05-30 v277 comment metadata coverage follow-up

- 상태: audit tooling added / source profile measured / semantic gate REVIEW-LOCKED
- 완료:
  - [x] source JSONL과 result JSON을 같이 보는 coverage audit tool을 추가했다.
  - [x] `tests\inputs\test01.jsonl`의 post IP coverage가 `0/104517`임을 확인했다.
  - [x] comment IP coverage가 `70337/368334`, comment IP가 있는 post가 `37656`개임을 확인했다.
  - [x] original partial result의 comment metadata/dialogue/image catalog coverage가 모두 0임을 확인했다.
  - [x] v267/v275 targeted rerun에서 comment metadata/dialogue와 image catalog가 들어오는 것을 확인했다.
  - [x] coverage tool tests 3건과 syntax check를 통과했다.
- 다음 작업:
  - [ ] crawler/source 단계에서 post IP를 저장할 수 있는지 확인한다.
  - [ ] post IP가 없을 때는 익명 `ㅇㅇ` author match를 계속 `author_match_unverified`로 유지한다.
  - [ ] 새 completed source 또는 expanded rerun 전체에 v277 audit tool을 다시 실행한다.
  - [ ] `duplicate_comment_ids`가 의미 판단을 과증폭하지 않는지 random/high-risk sample에서 확인한다.

## 2026-05-30 v276 comment metadata loader/output follow-up

- 상태: patched / focused tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `expert_main.py` public result row에 `ip`, `author_ip`, `post_ip`를 추가했다.
  - [x] `load_jsonl_posts()`에서 post/comment `post_id` key를 정규화했다.
  - [x] 중복 comment row를 `comment_id` 기준으로 제거한다.
  - [x] `11718091`, `11718097`, `11718117` 원본 입력 재구성에서 댓글 metadata/dialogue context를 확인했다.
  - [x] focused tests와 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] 새 completed source 또는 expanded rerun 결과에서 `post_ip`, `comment_metadata`, `comment_dialogue_context_lines` 누락률을 산출한다.
  - [ ] `comment_author_match_unverified_dialogue`, `comment_author_ip_mismatch_dialogue`, `comment_answer_side_conversation` bucket을 random/high-risk 분리 결과에 반영한다.
  - [ ] 댓글 dialogue는 의미 이해 보조 맥락으로만 쓰고, 작성자/IP 자체가 작품 identity evidence가 되지 않는지 expanded sample에서 점검한다.

## 2026-05-30 v269 v264 rerun residual follow-up

- 상태: rerun completed / targeted runtime GO / semantic gate REVIEW-LOCKED
- 완료:
  - [x] preflight가 goal/targeted endpoint cap을 반영하도록 수정했다.
  - [x] preflight tests 3건과 `py_compile`을 통과했다.
  - [x] v264 24건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 재실행했다.
  - [x] manifest에서 `requested_parallel=36`, `effective_parallel=24`, endpoint pool `8`, `completed/failed/pending=24/0/0`을 확인했다.
  - [x] known-bad `11718080`, `11718082`, `11718083`, `11718091`, `11718097`, `11718099`의 회복/보류 상태를 확인했다.
- 다음 작업:
  - [ ] `11718094` 유형: `집착/의존/혐오/피폐` 같은 추상 명사 title collision은 official page가 있어도 직접 캐릭터/작가/회차 연결이 약하면 `HOLD/context_only`로 내리는 gate를 설계한다.
  - [x] `11718117` 유형: OCR에 `작품명 작가 | 회차 ... PLATFORM`이 보이면 title candidate로 승격하되 플랫폼 검색으로 검증하는 루프는 v290/v292 live artifact 기준 동작 확인됐다.
  - [ ] v269 residual P1을 expanded review bucket에 넣어 반복성 확인 후 수정 우선순위를 정한다.
  - [ ] 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v266 v264 rerun readiness follow-up

- 상태: readiness checked / rerun not executed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v264 rerun input 24건과 execution contract를 확인했다.
  - [x] vLLM endpoint가 Gemma 4 4B model을 반환함을 확인했다.
  - [x] 관련 Python 점유 프로세스가 없음을 확인했다.
  - [x] MCP/WARP shard가 현재 5/36만 열려 있음을 확인했다.
  - [x] compose status access denied와 shard up 요청 abort를 기록했다.
- 다음 작업:
  - [ ] 36 shard를 준비한다.
  - [ ] 준비 후 `v264_v263_action_from_input_rerun_combined_input.jsonl` 24건을 VLM/OCR on으로 재실행한다.
  - [ ] 실행 manifest에서 `completed/failed/pending`, `requested_parallel=36`, `effective_parallel=min(input_count,36)`, VLM/OCR true, Docker lifecycle false를 확인한다.
  - [ ] 현재 5-shard 상태에서 나온 결과는 36-shard 품질 검증으로 쓰지 않는다.

## 2026-05-30 v265 semantic reread follow-up

- 상태: no-code confirmation / focused regression verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `23센줄 -> 23세인 줄`은 하드코딩 차단이 아니라 meaning pass 문제로 재확인했다.
  - [x] `surface_paraphrase_notes`가 있으면 seed 후보가 없어도 `discourse_semantic_seed_guard`가 한 번 더 실행되는지 확인했다.
  - [x] 짧은 work-like claim이 seed 없이 과분류될 때 semantic review가 한 번 더 도는지 확인했다.
  - [x] social-lament/generic-discourse도 semantic review 대상임을 확인했다.
  - [x] focused regression 5건을 통과했다.
- 다음 작업:
  - [ ] action queue의 `re_judge`는 단순 재실행 전에 title/body/comment/comment_context를 포함한 meaning packet을 우선 검토한다.
  - [ ] `context_only_no_work_anchor`, `surface_paraphrase_non_title_terms_removed`, `semantic_seed_review_non_title_terms_removed`, `friend_social_lament_or_generic_discourse`를 expanded random/high-risk 결과에서 분리 보고한다.
  - [ ] LLM 재독해가 특정 작품 가능성을 남겨도 public evidence에 직접 작품 앵커가 없으면 후단 reconciliation이 `title_resolution_allowed=false`를 유지하는지 대형 샘플에서 확인한다.

## 2026-05-30 v264 v263 action input follow-up

- 상태: action inputs prepared / rerun not executed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v263 `action_queue.json`을 action별 입력으로 분리했다.
  - [x] action input builder가 JSON array queue와 JSONL source를 지원하게 했다.
  - [x] 원본 result JSON source의 image source missing 37건을 확인했다.
  - [x] `tests\inputs\test01.jsonl`에서 post `content_blocks`와 comment row를 복원해 `image_source_missing_post_ids=0`을 만들었다.
  - [x] `rerun_combined=24`, `browser_targets=37`, `human_review=56`, `slang_db_review=7` 산출물을 생성했다.
  - [x] known-bad 6건이 from-input action package에 들어갔는지 확인했다.
  - [x] qualitative packet tests 30건과 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] 36 shard 상태를 확인하고 부족하면 shard 준비를 별도 runtime 작업으로 처리한다.
  - [ ] `v264_v263_action_from_input_rerun_combined_input.jsonl` 24건을 새 템플릿 기준 `expert_main.py --parallel 24 --reuse-shards-only --no-dashboard --server-type vllm --slang-db on --vlm on --ocr on`으로 실행한다. 이미 `--parallel 36`으로 완료된 동등 run은 `effective_parallel=24`와 lifecycle/evidence 계약이 맞으면 재실행하지 않는다.
  - [ ] 실행 후 `completed/failed/pending`, `effective_parallel=min(input_count,36)`, Docker lifecycle false, VLM/OCR true를 manifest로 확인한다.
  - [ ] `v264_v263_action_from_input_browser_targets.jsonl` 37건은 Codex in-app Browser 기준 visual evidence를 남긴다.

## 2026-05-30 v263 original partial 최신 정성 리뷰 follow-up

- 상태: patched / original partial regenerated / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원본 result/manifest/checkpoint/pending snapshot으로 preflight를 다시 생성했다.
  - [x] random control 먼저 실행 후 Round2 실행 시 high-risk가 0건으로 사라지는 dedupe 버그를 수정했다.
  - [x] random control label이 내부 high-risk bucket policy를 적용하게 했다.
  - [x] v263 canonical review rows `141`을 생성했다.
  - [x] known-bad 6건이 `REJECT`/`REPROCESS`/`HOLD`로 분리되는지 확인했다.
  - [x] qualitative packet tests 28건과 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] 새 completed source 또는 대형 재런에서 v263 bucket policy를 적용해 random baseline 1,000건 이상을 다시 생성한다.
  - [ ] `image_evidence_catalog_missing`, `reason_says_no_anchor_but_resolved`, `batch_memory_exact_alias_rescued_no_anchor`, `comments_without_author_metadata`를 P1/P2 확장 표본으로 분리한다.
  - [ ] 원본 partial 71행 결과는 failure pattern evidence로만 쓰고 전체 10만 건 품질률로 말하지 않는다.

## 2026-05-30 Round2/random image evidence catalog gate follow-up

- 상태: patched / focused tests verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] Round2 `evidence_catalog`가 `identity.image_evidence_catalog`를 수집하게 했다.
  - [x] Round2 high-risk bucket에 `image_evidence_catalog_missing`을 추가했다.
  - [x] missing catalog row는 `REPROCESS`로 보내고, 실제 이미지 URL이 있으면 `re_run` action을 우선하도록 했다.
  - [x] Round2/random packet에 `content_blocks`, `image_urls`, `image_count`, `image_evidence_catalog` 계열 필드를 추가했다.
  - [x] focused tests 2건, packet tools 26건, `py_compile`을 통과했다.
  - [x] v259 실제 결과로 `11718082` catalog present / `11718080` image bucket 없음 상태를 확인했다.
- 다음 작업:
  - [ ] 새 completed source에서 `image_evidence_catalog_missing` bucket의 population, selected count, coverage ratio를 산출한다.
  - [ ] `VLM_OCR_involved` 중 catalog present와 missing을 분리해 label/action 분포를 보고한다.
  - [ ] 브라우저 visual review queue와 `image_evidence_catalog_missing` queue를 중복 제거한다.

## 2026-05-30 v259 social-lament/VLM evidence schema follow-up

- 상태: patched / live canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718080/11718082` 2건을 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on`으로 재실행했다.
  - [x] manifest에서 `requested_parallel=36`, `effective_parallel=2`, `completed/failed/pending=2/0/0`, Docker lifecycle false를 확인했다.
  - [x] `11718080`이 사회적 한탄/장르 잡담으로 재독해되어 `official_title=null`, `title_resolution_allowed=false`로 유지됨을 확인했다.
  - [x] `11718082`가 VLM/OCR + 검색으로 `재벌가 차녀의 2회차 걸그룹`을 확정함을 확인했다.
  - [x] public result에 `content_blocks`, `image_urls`, `image_count`, `image_evidence_catalog`를 보존하게 했다.
  - [x] 이미지 없는 글에는 `image_evidence_catalog`가 생기지 않도록 status-only noise를 제거했다.
  - [x] `qualitative_review\20260528_141006_620986\v259_post11718080_11718082_schema_review_ko.md`를 작성했다.
- 다음 작업:
  - [x] expanded review packet builder가 `image_evidence_catalog`를 우선 사용하도록 확인했다.
  - [x] `VLM_OCR_involved` bucket에서 `image_count>0`인데 `image_evidence_catalog`가 비어 있는 행을 `image_evidence_catalog_missing` bucket으로 승격한다.
  - [ ] `friend_social_lament_or_generic_discourse` bucket의 false positive/false negative를 random control과 high-risk sample에서 분리 보고한다.
  - [ ] v259는 targeted canary이므로 10만 건 semantic approval로 승격하지 않는다.

## 2026-05-30 v256 known-bad 4건 VLM/OCR-on follow-up

- 상태: targeted canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `--parallel 36`을 상한으로 호출하되 입력 4건에서 `effective_parallel=4`가 되는지 확인했다.
  - [x] `--reuse-shards-only`와 small-run lifecycle block으로 Docker/shard 재시작이 발생하지 않았음을 확인했다.
  - [x] VLM/OCR on 조건에서 `11718083`, `11718091`, `11718097`, `11718099`를 재실행했다.
  - [x] `11718091`이 `23센줄 -> 23세인 줄` 자연어 재독해 후 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`로 유지됨을 확인했다.
  - [x] `11718091` 댓글 author는 IP 확인이 없으므로 `post_author_match_unverified=true`로 남는지 확인했다.
  - [x] `11718097=망겜의 힐러`, `11718099=빌어먹을 환생` 회복을 확인했다.
  - [x] `qualitative_review\20260528_141006_620986\v256_known_bad_4_after_comment_attribution_review_ko.md`를 작성했다.
- 다음 작업:
  - [ ] `search_degraded_or_timeout`이 reason에 남는 resolved/null-title canary를 high-risk review에서 별도 집계한다.
  - [ ] `VLM_OCR_involved`와 `ocr_title_conflict_with_stable_alias` bucket을 새 completed source에서 재집계한다.
  - [ ] `context_only_no_work_anchor`와 `comment_author_match_unverified_dialogue` bucket의 과차단/미차단을 random control과 high-risk sample로 분리 보고한다.
  - [ ] 비교 run이 slang DB 영향을 받으면 별도 `--slang-db-path` snapshot 사용을 기본으로 검토한다.
  - [ ] v256은 targeted canary이므로 원본 20260528 partial source나 10만 건 semantic approval로 승격하지 않는다.

## 2026-05-30 v255 comment author/IP attribution follow-up

- 상태: patched / focused tests verified / source audit documented / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `tests\inputs\test01.jsonl`의 post/comment row 구조와 댓글 author/IP coverage를 계측했다.
  - [x] 20260528 원본 result가 댓글 문자열은 갖지만 `comment_metadata/comment_context_lines/comment_dialogue_context_lines`는 모두 잃었다는 점을 확인했다.
  - [x] 익명/공통 author는 IP 확인 없이는 `post_author`로 확정하지 않게 했다.
  - [x] `post_author_match_unverified`와 `role=author_match_unverified`를 pipeline/public result 양쪽에 추가했다.
  - [x] Round2 bucket `comment_author_match_unverified_dialogue`를 추가했다.
  - [x] focused regression 10건, packet tools 24건, `py_compile`을 통과했다.
- 다음 작업:
  - [ ] crawler/input 단계에서 post IP 또는 DC 원글 작성자 표시를 수집할 수 있는지 확인한다.
  - [ ] 새 completed source에서 `comment_author_match_unverified_dialogue`, `comment_author_ip_mismatch_dialogue`, `comments_without_author_metadata`, `comment_speaker_context_unavailable`를 분리 집계한다.
  - [ ] 댓글 메타는 title 확정 근거가 아니라 dialogue understanding evidence로만 쓰도록 expanded review label 기준을 유지한다.

## 2026-05-30 v254 `11718091` semantic reread follow-up

- 상태: no-code confirmation / focused regression verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `23센줄`을 `23세인 줄` 오타/축약으로 읽는 것이 맞다는 사용자 지적을 current-code evidence로 재확인했다.
  - [x] v251 current-code canary의 `analysis_result.identity`에서 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 확인했다.
  - [x] reason에 `표면 표현 해석`, `의미 재검토`, `작품 seed 제외`가 남는 것을 확인했다.
  - [x] focused regression 6건을 통과했다.
  - [x] `qualitative_review\20260528_141006_620986\v254_post11718091_semantic_reread_confirmation_ko.md`를 작성했다.
- 다음 작업:
  - [ ] `context_only_no_work_anchor` bucket을 expanded high-risk review에서 별도 과표집한다.
  - [ ] `surface_paraphrase_non_title_terms_removed`와 `semantic_seed_review_non_title_terms_removed`의 과차단/미차단을 random control과 high-risk sample에서 분리 보고한다.
  - [ ] 원본 20260528 partial source와 current-code canary를 섞어서 10만 건 품질 승인처럼 말하지 않는다.

## 2026-05-30 v253 systemic bucket extraction follow-up

- 상태: implemented / focused tests verified / partial-source artifacts generated / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `batch_memory_exact_alias_rescued_no_anchor` bucket을 Round2 builder에 추가했다.
  - [x] `critical_counter_but_resolved`, `notes_demoted_then_resolved`, `title_surface_primary_candidate_rescued` bucket을 Round2 builder에 추가했다.
  - [x] `official_url_missing_for_resolved`, `reason_says_no_anchor_but_resolved`, `search_absent_verified_title_direct_image_title` bucket을 Round2 builder에 추가했다.
  - [x] 각 bucket의 label/action 정책을 추가했다.
  - [x] packet `evidence_counts`와 `result_public_fields`에 systemic flag를 노출했다.
  - [x] focused tests 3건과 review tool `py_compile`을 통과했다.
  - [x] v253 preflight와 v253 Round2 partial-source sample을 생성했다.
- 다음 작업:
  - [ ] `search_absent_verified_title_direct_image_title`는 dedupe 때문에 selected bucket count가 0이므로 image/OCR 전용 follow-up에서 강제 포함한다.
  - [ ] `reason_says_no_anchor_but_resolved`도 dedupe 때문에 selected bucket count가 0이므로 no-anchor 전용 follow-up에서 강제 포함한다.
  - [ ] 새 completed source 또는 recovered completed subset에서 v253 bucket set을 다시 실행한다.
  - [ ] v253 partial source 수치는 전체 오류율로 쓰지 않는다.

## 2026-05-30 current goal known-bad audit follow-up v252

- 상태: audit updated / targeted known-bad recovered / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 원본 `out\expert_result_20260528_141006_620986.json`이 `104502` 입력의 completed approval source가 아니라 output `71` rows, `completed=80`, `flushed=71`, `pending=9` partial source임을 재확인했다.
  - [x] 원본 문제행 `11718083`, `11718091`, `11718097`, `11718099`, `11718080`, `11718082`의 기존 오매칭 상태를 표로 정리했다.
  - [x] v251 기준 `11718083/11718091/11718097/11718099` targeted recovery 상태를 정리했다.
  - [x] v249/v181 기준 `11718080` social-lament fix와 `11718082` VLM/OCR image evidence baseline을 분리 기록했다.
  - [x] audit artifact `qualitative_review\20260528_141006_620986\v252_goal_current_known_bad_audit_ko.md`를 작성했다.
- 다음 작업:
  - [x] `11718082`는 v259 VLM/OCR-on canary와 v293 subtype review로 현재 리뷰 기준 재확인했다. OCR 오타 표면은 저장 차단됐고 운영 `slang_db` 오염은 발견되지 않았다.
  - [ ] `search_absent_verified_title + direct_image_title` bucket을 expanded high-risk review에 추가한다.
  - [ ] `batch_memory_exact_alias_rescued + no_anchor` bucket을 expanded high-risk review에 추가한다.
  - [ ] `title_surface_primary_candidate_rescued` bucket을 expanded high-risk review에 추가한다.
  - [ ] `context_only_no_work_anchor`, `friend_social_lament_or_generic_discourse`, `comment_author_ip_mismatch_dialogue` bucket을 expanded high-risk review에서 분리 보고한다.
  - [ ] 원본 20260528 source는 partial이므로 10만 건 semantic approval 근거로 쓰지 않는다.

## 2026-05-30 v250/v251 VLM/OCR 오독 title conflict follow-up

- 상태: patched / focused unittest verified / live vLLM canary recovered / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v250 `11718099`에서 VLM/OCR이 `검은 여왕의 혼성명`을 표지 title로 읽고, 후단이 이를 final title로 되살리는 회귀를 확인했다.
  - [x] Verifier의 `search_absent_verified_title` 반론이 있어도 image/OCR-only title이 후단 suspected/final title로 부활할 수 있는 경로를 확인했다.
  - [x] weak direct image/OCR title canonical rescue guard를 추가했다.
  - [x] `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias` 구조 flag를 유지/보강했다.
  - [x] `test_verifier_nullified_image_ocr_title_yields_to_stable_alias_canonical_rescue`를 추가했다.
  - [x] focused unittest 5건과 `py_compile`을 통과했다.
  - [x] Codex 내장 브라우저로 `11718099` 실제 이미지 로딩 완료 상태를 확인했고, `qualitative_review\20260528_141006_620986\v251_post11718099_browser_actual.png`로 남겼다.
  - [x] v251 known-bad 4건 live canary를 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
  - [x] v251 manifest에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
  - [x] v251 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://m.munpia.com/novel/detail/222360`, conflict flags 2종으로 확인됐다.
- 다음 작업:
  - [ ] expanded high-risk review에서 `search_absent_verified_title + direct_image_title`, `vlm_ocr_title_conflict_with_stable_alias`, `image_only_title_no_official_evidence` bucket을 별도 과표집한다.
  - [ ] `BatchMem: 약칭 즉시등록 '검은 여왕의 혼성명' -> '검은 여왕의 혼성명'`처럼 OCR-only/title-identical alias 저장을 오염 후보로 스캔한다.
  - [ ] 이미지 로딩이 늦거나 실패한 post는 text-only resolved로 넘기지 말고 `browser_visual_review`/`REPROCESS` action queue로 보낸다.
  - [ ] v251 live recovery는 batch-memory alias rescue 경로였으므로, weak-image canonical rescue branch는 추가 실데이터 bucket에서 실제 trigger 빈도를 확인한다.
  - [ ] targeted canary만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v248/v249 친구/한탄형 장르 잡담 semantic reread follow-up

- 상태: patched / focused unittest verified / live vLLM canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `23센줄`류는 `23세인 줄` 오타/축약으로 읽는 의미 재독해가 이미 필요하며, 같은 원칙을 친구/한탄형 장르 잡담에도 확장했다.
  - [x] `소설 보는 친구 있으면 좋음`, `밥 먹으며 TS/갈드컵 얘기`처럼 소설 일반어와 사회적 한탄 신호가 같이 있으면 `discourse_semantic_seed_guard`를 한 번 더 실행하도록 했다.
  - [x] 기억 회수/작품 찾기 신호(`무슨 소설`, `기억 안남`, `대사`, `장면`, `찾...`)가 있으면 이 social-lament 트리거에서는 제외한다.
  - [x] `test_social_lament_genre_discourse_runs_semantic_review_once_more`를 추가했다.
  - [x] `test_social_lament_review_runs_even_with_non_short_generic_seed`를 추가해, 이미 긴 장르 일반어 seed가 있어도 social-lament trigger가 독립적으로 작동하는지 확인했다.
  - [x] focused unittest 4건과 `py_compile`을 통과했다.
  - [x] v248 `11718080` live canary를 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
  - [x] v249 `11718080` broadened live canary도 같은 조건으로 실행했다.
  - [x] manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, VLM/OCR on, small-run shard lifecycle blocked를 확인했다.
  - [x] v248/v249 log에서 `discourse_semantic_seed_guard` 실행, `title_novel_terms=[]`, `search_suggestions=[]`, 조기 종료를 확인했다.
- 다음 작업:
  - [ ] expanded high-risk review에서 `friend_social_lament_or_generic_discourse` bucket을 별도 집계한다.
  - [ ] 사회적 한탄/장르 잡담과 memory-query/작품 찾기 사이의 false negative를 별도 대조군으로 확인한다.
  - [ ] targeted canary만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v246 익명 author/IP 댓글 dialogue follow-up

- 상태: patched / focused unittest verified / compile verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `ㅇㅇ` 같은 익명 author가 여러 사용자에게 반복될 수 있어, author match만으로 댓글을 `post_author`로 보면 대화 맥락이 오염될 수 있음을 확인했다.
  - [x] `PostInput`에 `ip`, `author_ip`, `post_ip`를 추가했다.
  - [x] `expert_main.py`가 입력의 `ip/author_ip/post_ip/writer_ip`를 보존해 `PostInput`으로 넘기도록 했다.
  - [x] `AgenticPipeline._post_to_dict()`가 `post_ip`를 공개 packet에 남기도록 했다.
  - [x] 익명/공통 author는 IP가 있으면 speaker key를 `author+ip` 단위로 분리하고, post IP와 comment IP가 다르면 `role=post_author`를 부여하지 않도록 했다.
  - [x] `test_anonymous_comment_author_uses_ip_before_post_author_role`을 추가했다.
  - [x] 댓글 dialogue/context 관련 focused unittest 4건과 `py_compile`을 통과했다.
  - [x] Round 2 high-risk bucket에 `comment_author_ip_mismatch_dialogue`, `post_author_comment_not_independent_evidence`, `comment_answer_side_conversation`을 추가했다.
  - [x] `tests.test_qualitative_review_packet_tools` 21건과 review-tool `py_compile`을 통과했다.
  - [x] v247 preflight에서 원본 partial source가 `comments_without_author_metadata=55`, `comment_speaker_context_unavailable=55`이며 새 IP mismatch bucket은 post IP coverage 부족으로 `0`임을 확인했다.
- 다음 작업:
  - [ ] expanded review에서 `comment_author_ip_mismatch_dialogue`, `post_author_comment_not_independent_evidence`, `comment_answer_side_conversation` bucket을 분리 집계한다.
  - [ ] 실제 completed source에서 post IP 필드가 어느 이름(`ip`, `author_ip`, `post_ip`, `writer_ip`)으로 들어오는지 분포를 확인한다.
  - [ ] targeted deterministic guard만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v245 reason scoreboard title-null anchor follow-up

- 상태: patched / focused unittest verified / compile verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v244 `11718089`가 final `official_title=null`, `title_resolution_state=author_new_work_context`, `title_resolution_allowed=false`임에도 reason scoreboard에 `grounding_anchor: +2 (강한 앵커(plot_mention))`가 남은 것을 확인했다.
  - [x] title-null 최종 판정에서는 `plot_mention`류 앵커를 작품명 확정용 strong anchor로 표시하지 않도록 score 보드를 보정했다.
  - [x] `test_scoreboard_does_not_call_plot_anchor_strong_when_title_blocked`를 추가했다.
  - [x] focused unittest 5건과 `py_compile`을 통과했다.
  - [x] v245 단건 canary `20260530_052428_641974`를 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
  - [x] manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
  - [x] v245 `11718089`는 `official_title=null`, `title_resolution_state=author_new_work_context`, `title_resolution_allowed=false`, score line `grounding_anchor: -2 (약한 앵커(search_only))`로 확인됐다.
- 다음 작업:
  - [ ] expanded review에서 `title_resolution_allowed=false`인데 scoreboard가 strong positive evidence처럼 보이는 케이스를 별도 bucket으로 스캔한다.
  - [ ] targeted patch만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v243 author/new-work alias rescue follow-up

- 상태: patched / focused unittest verified / single-post vLLM VLM-OCR verified / slang_db cleanup done / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v242 `11718089`에서 앞단은 `discuss_genre(high)`와 deliberate null을 냈지만 후단 alias rescue가 `개돌 -> 파벨 주니어`로 다시 resolved한 것을 확인했다.
  - [x] `[별명/작가] 신작`, `[별명] 대체 뭘 쓰...` 표면을 author/new-work 문맥으로 추출하는 helper를 추가했다.
  - [x] author/new-work 표면은 `search_evidence_alias_inference`뿐 아니라 이미 오염된 `batch_memory` hit에서도 alias rescue하지 않도록 차단했다.
  - [x] deliberate null + genre/trope/community/no-work 경고 + direct title proof 부재 상태에서는 검색 추정 alias rescue가 앞단 null 판정을 뒤집지 못하게 했다.
  - [x] focused unittest 5건과 `py_compile`을 통과했다.
  - [x] v243 단건 canary `20260530_042526_026150`을 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
  - [x] manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
  - [x] v243 `11718089`는 `official_title=null`, `is_relevant=false`, `discussion_type=noise`, `title_resolution_allowed=false`, flags `batch_memory_alias_rescue_blocked_nonwork_context`, `batch_memory_alias_rescue_blocked_deliberate_null`로 확인됐다.
  - [x] v242가 만든 `slang_db` 오염 `개돌 -> 파벨 주니어` bucket을 제거했고, 현재 DB에서 해당 문자열이 검색되지 않음을 확인했다.
- 다음 작업:
  - [ ] `author_new_work_alias_rescue_blocked`, `deliberate_null_nonwork_context`, `slang_db_author_alias_pollution` bucket을 high-risk expansion에 추가한다.
  - [ ] `11718089` final `title_resolution_state=unresolved_matchable`이 리뷰어에게 "작품 찾기 미해결"로 보일 수 있는지 확인하고, 필요하면 `author_new_work_context`/`genre_context_no_title` scope를 별도 설계한다.
  - [ ] v243은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v240 `23센줄` context-only scope follow-up

- 상태: patched / focused unittest verified / known-bad 4건 VLM-OCR verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v239 `11718091`이 title null은 맞지만 `title_resolution_state=unresolved_matchable`로 남아 리뷰어에게 "아직 매칭 가능한 미해결 작품"처럼 보일 수 있음을 확인했다.
  - [x] `title_resolution_state=context_only`를 추가해 검색 전 의미 재독해가 작품 seed를 문맥 표현으로 낮춘 경우를 별도 scope로 분리했다.
  - [x] 약한 캐릭터 나이/외모 반응 차단 경로에 `context_only_no_work_anchor` flag를 추가했다.
  - [x] `test_semantic_seed_context_only_scope_is_not_unresolved_matchable`을 추가했다.
  - [x] focused unittest 4건과 `py_compile`을 통과했다.
  - [x] v240 known-bad 4건 canary `20260530_032804_873598`을 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
  - [x] v240 manifest에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
  - [x] v240 `11718091`은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`, flags `context_only_no_work_anchor`로 확인됐다.
  - [x] 원본 `out\expert_result_20260528_141006_620986*`는 `input=104502`지만 `completed=80`, `flushed=71`, `pending=9`인 partial source임을 다시 정리했다.
- 다음 작업:
  - [ ] expanded high-risk review에 `context_only_no_work_anchor`, `semantic_seed_review_specific_work_denied`, `weak_character_reaction_unresolved_blocked` bucket을 포함한다.
  - [ ] 원본 partial source는 approval 근거가 아니라 failure-pattern discovery/retest seed로만 사용한다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v239 문피아 브랜딩 title mismatch follow-up

- 상태: patched / focused unittest verified / known-bad 4건 VLM-OCR verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v237 `11718097`에서 `m.munpia.com` 직접 fetch가 `웹소설의 유토피아, 글세상 문피아`를 읽어 URL-title mismatch 경고를 냈던 원인을 확인했다.
  - [x] 문피아 플랫폼 브랜딩 title은 작품 title mismatch로 세지 않도록 `_is_platform_branding_title()`과 fetched-title mismatch 검사를 보강했다.
  - [x] `test_munpia_branding_title_is_not_url_title_mismatch_signal`을 추가했다.
  - [x] focused unittest 4건과 `py_compile`을 통과했다.
  - [x] v239 known-bad 4건 canary `20260530_031006_533601`을 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
  - [x] v239 manifest에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
  - [x] v239 `11718083`, `11718091`은 title null을 유지했다.
  - [x] v239 `11718097`은 `official_title=망겜의 힐러`, `heretic_url=https://novel.munpia.com/328421`, `comment_dialogue_context_lines=5`로 확인됐다.
  - [x] v239 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, OCR conflict flags 2개로 확인됐다.
- 다음 작업:
  - [ ] expanded high-risk review에 `platform_branding_fetch_title`, `official_url_fetch_title_mismatch_false_positive` bucket을 포함한다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v238 VLM/OCR conflict structured flag follow-up

- 상태: patched / focused unittest verified / live VLM-OCR verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v237 `11718099`에서 OCR title mismatch가 reason에는 남지만 `consistency_flags`에는 없던 문제를 확인했다.
  - [x] `_image_grounding_mismatch_flags()`를 추가해 final title과 OCR direct title 후보 충돌을 구조 flag로 남긴다.
  - [x] 안정 alias/locked official candidate가 final title을 뒷받침하는 경우 `ocr_title_conflict_with_stable_alias`를 남긴다.
  - [x] focused unittest 4건과 `py_compile`을 통과했다.
  - [x] v238 단건 canary `20260530_025454_691972`를 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
  - [x] v238 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
  - [x] v238 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, flags `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias`로 확인됐다.
  - [x] `23센줄 -> 23세인 줄` 자연어 재독해 reason regression도 함께 통과했다.
- 다음 작업:
  - [ ] expanded high-risk review에 `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias` bucket을 포함한다.
  - [ ] Arbiter/Verifier 중간 reason이 OCR 오독을 strong evidence처럼 말하는지 별도 HOLD bucket으로 확인한다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v237 `11718099` batch memory alias URL/evidence follow-up

- 상태: patched / focused unittest verified / same-batch VLM-OCR verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v235에서 `11718099`가 `빌어먹을 환생`으로 교정된 뒤에도 `heretic_url=null`, `official_title_evidence=false`가 남을 수 있는 경로를 확인했다.
  - [x] `batch_memory_exact_alias_rescued` 일반 경로에도 corrected title official URL recovery를 연결했다.
  - [x] URL 회복 시 candidate, `primary_work`, `source_tier`, `page_type`, `content_status`를 함께 갱신하게 했다.
  - [x] `batch_memory_alias_official_url_recovered` flag를 추가했다.
  - [x] focused unittest 4건과 `py_compile`을 통과했다.
  - [x] v236 단건 canary `20260530_023033_856559`에서 `11718099`가 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, `official_urls=4`로 확인됐다.
  - [x] v237 동일 4건 canary `20260530_023511_350246`에서 `11718099`가 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, `official_urls=1`로 확인됐다.
  - [x] v237에서 `11718091`은 `23센줄 -> 23세인 줄`, `작품 seed 제외: 23센줄, 은영`, `title_resolution_allowed=false`를 유지했다.
- 다음 작업:
  - [ ] live v236/v237은 정상 검색 경로가 먼저 URL을 확보했으므로, `batch_memory_alias_official_url_recovered` branch는 focused unittest 증거로 분리해 기록한다.
  - [ ] `batch_memory_exact_alias_missing_url`, `ocr_title_conflict_with_stable_alias` bucket을 high-risk expansion에 포함한다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v234 corrected title official URL/evidence follow-up

- 상태: patched / focused unittest verified / live VLM-OCR verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v230에서 남은 `11718077` corrected title의 `heretic_url=null`, `official_title_evidence=false` 후속을 재현했다.
  - [x] late title correction 이후 corrected title 기준 공식 URL 회복 검색을 추가했다.
  - [x] 검색 결과 title이 `네이버 시리즈`, `novel.munpia.com`처럼 generic해도 snippet/content가 corrected title을 직접 포함하면 공식 detail URL 후보로 볼 수 있게 했다.
  - [x] validator가 실패한 경우에도 official detail URL + corrected title strict match를 `validated=false`, `source=title_matched_search`로 보수 회복한다.
  - [x] final reason의 `official_title_evidence`와 `official_urls` counter를 final URL 상태와 동기화했다.
  - [x] focused unittest 9건과 `py_compile`을 통과했다.
  - [x] v234 live canary `20260530_015610_155152`에서 `11718077`이 `official_title=즉사기 들고 무림에 떨어지다`, `heretic_url=https://series.naver.com/novel/detail.series?productNo=14041321`, `official_urls=1`로 확인됐다.
- 다음 작업:
  - [ ] `validated=false` URL recovery는 expanded review에서 validator/fetch 상태와 evidence grade를 분리 확인한다.
  - [ ] `corrected_title_official_url_recovery`, `reason_official_url_summary_sync`, `generic_search_title_snippet_match` bucket을 high-risk expansion에 포함한다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v230 `11718077` stable alias conflict follow-up

- 상태: patched / focused unittest verified / live VLM-OCR verified / official URL follow-up closed by v234 / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v229에서 `즉사무림 -> 즉사수선전`으로 다시 수렴한 원인을 확인했다.
  - [x] 원인은 stable alias 보정 자체가 없어서가 아니라, 이전 Decoder 오판을 current title 원문 언급 증거로 다시 사용한 구조였다.
  - [x] stable alias conflict 판단을 raw title/body/comment strict direct title match 기준으로 바꿨다.
  - [x] Decoder가 `즉사무림 -> 즉사수선전`으로 오판한 상태를 회귀 테스트에 넣었다.
  - [x] focused unittest 3건과 `py_compile`을 통과했다.
  - [x] v230 live canary `20260530_010824_738895`에서 `11718077`이 `official_title=즉사기 들고 무림에 떨어지다`, `discussion_type=review`, `anchor_type=title_alias`로 확인됐다.
  - [x] v219 잔여 action 중 `11718077` alias collision은 targeted 기준으로 닫았다.
- 다음 작업:
  - [x] v230 `11718077`에서 남은 corrected title의 `heretic_url=null`, `official_title_evidence=false`는 v234 targeted 기준으로 닫았다.
  - [ ] expanded high-risk review에 `stable_alias_conflict_corrected`, `search_title_conflict_with_stable_alias` bucket을 추가한다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v228 `11718075` support-cheer alias probe follow-up

- 상태: patched / focused unittest verified / live VLM-OCR verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v226에서 `죽깨수 웹소설` 검증 쿼리가 association/low-specific 필터로 제거되고, 전체 문장 `뜻` 검색으로 미끄러진 원인을 확인했다.
  - [x] 제목의 `올 때 됐다` 기대 프레임과 본문의 `가자` 응원 화행이 함께 있을 때 compact alias probe를 보존하도록 했다.
  - [x] `23센줄` 같은 나이/오타 표면과 일반 상태어는 새 probe 경로에서 제외했다.
  - [x] focused unittest 3건과 `py_compile`을 통과했다.
  - [x] v228 live canary `20260530_003717_935082`에서 `11718075`가 `official_title=죽었다 깨어도 수선`, `is_relevant=true`, `discussion_type=anticipation`, `subtype=support_cheer`, `anchor_type=title_alias`로 확인됐다.
  - [x] v228 summary를 `qualitative_review\20260528_141006_620986\v228_post11718075_support_cheer_taxonomy_summary_ko.md`에 남겼다.
- 다음 작업:
  - [ ] expanded high-risk review에 `short_support_alias_probe`, `support_cheer_alias_recovered`, `association_post_alias_probe_preserved` bucket을 추가한다.
  - [ ] 이 유형은 본문 직접 앵커가 약하므로 evidence grade `Medium`으로 보고, random baseline과 섞어 전체 오류율처럼 말하지 않는다.
  - [x] v219 잔여 action 중 `11718077` alias collision은 v230 targeted 기준으로 닫았다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v225 context-only semantic reread follow-up

- 상태: patched / focused unittest verified / live VLM-OCR verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] seed 후보와 검색 제안이 없어도 짧은 글이 `discuss_work/work`로 과분류되면 `discourse_semantic_seed_guard`가 한 번 더 읽도록 했다.
  - [x] `23센줄` surface note 경로와 별도로, 일반 짧은 나이/외모/잡담 과분류 경로를 context-only 재독해 대상으로 추가했다.
  - [x] 원문에 안정 약칭/정식 제목이 직접 있으면 이 새 경로가 실행되지 않도록 보호했다.
  - [x] focused unittest 5건과 `py_compile`을 통과했다.
  - [x] v225 live canary `20260530_001113_086437`에서 `11718091`이 `official_title=null`, `is_relevant=false`, `title_resolution_allowed=false`를 유지했다.
  - [x] v225 summary를 `qualitative_review\20260528_141006_620986\v225_post11718091_context_only_semantic_summary_ko.md`에 남겼다.
- 다음 작업:
  - [ ] expanded high-risk review에 `context_only_short_reaction` bucket을 추가한다.
  - [ ] `short_context + claimed_specific_work + sentence_like_title + stable_alias_absent` 조건이 정상 약칭 글을 과차단하지 않는지 random/control sample에서 확인한다.
  - [ ] targeted 구조 보강만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v223 `11718069` author-meta alias rescue follow-up

- 상태: patched / live VLM-OCR verified / browser evidence captured / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718069`을 단건 targeted input으로 만들었다.
  - [x] `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on`으로 실행했고 `effective_parallel=1`, Docker lifecycle false를 확인했다.
  - [x] Codex 내장 브라우저에서 원문 제목 `목마는 그냥 현판이나 써야댐`, 본문 두 줄, 첨부 이미지 1개, 댓글 0개를 확인했다.
  - [x] author-meta/adjacent 상태에서 BatchContext alias rescue가 `애호뉴비`를 단일 공식 제목으로 되살리지 않게 했다.
  - [x] 최종 `11718069`은 `official_title=null`, `is_relevant=false`, `discussion_type=author_talk`, `title_resolution_allowed=false`로 확인했다.
  - [x] focused unittest 5건과 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] `author_meta_with_secondary_work_alias`와 `batch_memory_alias_rescue_blocked_by_author_meta`를 high-risk expansion bucket에 포함한다.
  - [ ] Slang DB `pending` alias preview가 실제 오염인지 재관측인지 분리해 `slang_db_review`한다.
  - [x] `11718075` re_search는 v228에서 short support-cheer alias probe 보존으로 닫았다.
  - [x] v219 잔여 action 중 `11718077` alias collision은 v230 targeted 기준으로 닫았다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v222 `23센줄` surface paraphrase semantic guard

- 상태: patched / focused unittest verified / live canary verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `surface_paraphrase_notes`가 있으면 title/search 후보가 비어 있어도 `discourse_semantic_seed_guard`가 실행되도록 했다.
  - [x] `11718091` live canary에서 1차 Discourse가 `은영`, `23센줄`을 seed로 올린 뒤에도 의미 재검토와 sanitizer가 검색/Decoder 재승격 전에 조기 종료하는 것을 확인했다.
  - [x] `11718091` final reason에 `23센줄 -> 23세인 줄`, `작품 seed 제외: 23센줄, 은영`을 남겼다.
  - [x] focused unittest 5건, `py_compile`, v222 live run을 통과했다.
- 다음 작업:
  - [ ] `short_banter_seed_demoted`, `surface_paraphrase_specific_work_denied` failure family를 high-risk expansion에 포함해 false positive/false negative를 분리한다.
  - [ ] 의미 재검토 LLM이 표면 오타는 이해하면서도 `is_specific_work_discussion=true`를 과하게 낼 수 있으므로, seed 제거 후 final reconciliation 검증을 계속 유지한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v221 `11716499`/`11718087` follow-up

- 상태: patched / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11716499`, `11718087`만 포함하는 2-post targeted input을 만들었다.
  - [x] `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고 `effective_parallel=2`, Docker lifecycle false를 확인했다.
  - [x] `11716499`: `그러는데` 접속형 문장 조각을 BatchContext/search alias rescue로 승격하지 않게 했다.
  - [x] `11718087`: non-image 제목의 추천 요청을 VLM/OCR 카드 이미지보다 우선 보존해 `adjacent_relevant/recommendation`으로 남겼다.
  - [x] focused unittest, batch alias/VLM regression, `py_compile`을 통과했다.
- 다음 작업:
  - [x] `11718069`: author-meta alias rescue는 v223에서 `official_title=null`로 닫았다.
- [x] `11718075`: `죽깨수` 직접 근거는 v228에서 `support_cheer`로 닫았다.
  - [x] `11718077`: `즉사무림` alias collision은 v230 targeted 기준으로 닫았다.
  - [ ] v221은 targeted follow-up이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v219 failure family expansion package

- 상태: rerun complete / qualitative labels written / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v215 pattern scan에서 8개 failure family 후보를 뽑았다.
  - [x] 30개 post / 36개 JSONL row 입력을 생성했다.
  - [x] `v219_failure_family_expansion_manifest.json`, `v219_failure_family_expansion_input.jsonl`, `v219_failure_family_expansion_summary_ko.md`, `v219_failure_family_action_queue_ko.md`를 생성했다.
  - [x] JSONL parse 검증에서 `lines=36`, `posts=30`, `comments=6`, source missing `0`을 확인했다.
  - [x] `.\venv\Scripts\python.exe expert_main.py --input qualitative_review\20260528_141006_620986\v219_failure_family_expansion_input.jsonl --output qualitative_review\20260528_141006_620986\v219_failure_family_expansion_result.json --server-type vllm --parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 실행.
  - [x] manifest와 로그에서 Docker lifecycle false, VLM/OCR on, failed/pending `0/0`을 확인했다.
  - [x] v219 결과를 `ACCEPT=25`, `HOLD=3`, `REPROCESS=1`, `REJECT=1`로 after-review했다.
  - [x] v219은 targeted expansion이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`로 둔다.
- 다음 작업:
  - [x] `11716499`: 일반어 alias 과확정 `어느날`은 v221에서 `official_title=null`로 닫았다.
  - [x] `11718087`: VLM/OCR 우선순위 충돌은 v221에서 `adjacent_relevant/recommendation`으로 닫았다.
  - [x] `11718069`: author-meta alias rescue는 v223에서 `official_title=null`로 닫았다.
- [x] `11718075`: `죽깨수` 직접 근거는 v228에서 `support_cheer`로 닫았다.
  - [x] `11718077`: `즉사무림` alias collision은 v230 targeted 기준으로 닫았다.

## 2026-05-29 v218 semantic root-cause matrix 후속

- 상태: documented / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v218 root-cause matrix를 생성했다.
  - [x] 원본 partial run integrity와 v215 pattern scan을 현재 evidence로 다시 묶었다.
  - [x] known-bad 4건과 `11718080` friend/social lament canary의 최신 targeted 상태를 정리했다.
- 다음 작업:
  - [ ] 새 completed source를 만들거나, 현재 partial source는 approval이 아니라 discovery 목적으로만 사용한다.
  - [ ] `friend/social lament`, `memory-query`, `weak character reaction`, `VLM/OCR conflict`, `URL/evidence-state`, `slang_db pollution` failure family별 확대 sample을 준비한다.
  - [ ] `comment_dialogue_context_lines`가 새 run/review packet에서 누락되는 비율을 별도 집계한다.
  - [ ] 10만 건 semantic gate는 random baseline과 P0/P1 high-risk expansion 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v217 `11718080` 친구/한탄형 장르 잡담 재검증

- 상태: live verified / focused unittest verified / no new code patch / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718080`을 단건 targeted input으로 분리했다.
  - [x] v217 live run에서 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준 `effective_parallel=1`, Docker lifecycle false를 확인했다.
  - [x] v217 결과는 `official_title=null`, `is_relevant=false`, `discussion_type=trope_discussion`, `title_resolution_allowed=false`로 확인했다.
  - [x] `소설`은 context-only, TS/갈드컵 검색 제안은 drop되어 작품 seed로 승격되지 않음을 확인했다.
  - [x] late rescue/generic discourse veto와 `23센줄` 의미 재판독 focused regression 7건, 관련 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] `friend/social lament`, `genre_generalization`, `late_rescue_without_public_work_anchor` family를 high-risk expansion에서 확대 확인한다.
  - [ ] random baseline과 high-risk expansion 결과 전까지 v217 단건 결과로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v216 검색 전 의미 재판독 dialogue-context 보강

- 상태: patched / focused unittest verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `discourse_semantic_seed_guard` payload에 `comment_context`, `comment_dialogue_context`를 포함했다.
  - [x] semantic seed review prompt에 오타/축약/띄어쓰기 깨짐을 먼저 자연어 의미로 풀어 읽는 규칙을 추가했다.
  - [x] speaker/author/ip/comment id는 작품 identity evidence가 아니라 대화 흐름 메타라는 규칙을 의미 재판독 단계에도 추가했다.
  - [x] v216 `11718091` live canary에서 `23센줄 -> 23세인 줄`, `작품 seed 제외: 은영이`, `official_title=null`을 확인했다.
- 다음 작업:
  - [ ] `short_banter_seed_demoted`, `semantic_seed_review_specific_work_denied` bucket에서 dialogue-context 입력 보강 후 과차단/미차단을 확대 검토한다.
  - [ ] 댓글이 실제 제목 답변을 주는 memory-query 케이스와 단순 동조/잡담 댓글 케이스를 분리해 회귀 표본으로 만든다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v214 댓글 발화 재구성 / memory-query guard

- 상태: patched / focused unittest verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `comment_dialogue_context_lines`를 result row, pipeline post dict, prompt JSON, Decoder/Arbiter/Synthesizer prompt, qualitative packet에 추가했다.
  - [x] `comment_dialogue_context_lines`는 댓글 text excerpt를 speaker/author/ip/reply 메타와 같은 #번호로 묶어 본문 작성자 댓글 이어쓰기와 타 유저 대화를 LLM이 더 잘 읽게 한다.
  - [x] prompt overlay에서 speaker/author/ip는 작품명/별칭 근거가 아니라 대화 흐름 추적 메타라고 명시했다.
  - [x] memory-query 신호가 있으면 `unresolved_worklike_hold`가 `character_talk`로 되살리지 못하게 했다.
  - [x] v213 targeted 4건에서 `11718091/11718097`의 dialogue context 보존, `11718097/11718099` title recovery를 확인했다.
  - [x] v214 single canary에서 `11718083`은 `official_title=null`, `is_relevant=false`, `discussion_type=recommendation`, `title_resolution_state=unresolvable_memory_query`로 확인했다.
- 다음 작업:
  - [ ] 대형 재런 또는 expanded sample에서 `comment_dialogue_context_lines` 누락/분포를 별도 집계한다.
  - [ ] 댓글이 실제 제목 답변을 제공하는 memory-query 케이스와, 댓글이 동조/잡담뿐인 케이스를 high-risk bucket으로 분리한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v212 `11718097` 공식 URL 보강 / 의미 이해 gate 재확인

- 상태: patched / focused unittest verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `23센줄`은 `23세인 줄` 오타/축약이라는 자연어 이해가 `surface_paraphrase_notes`, `semantic_seed_review`, final reason으로 이어지는지 focused test로 재확인했다.
  - [x] `망겜의 힐러 [단행본] - 웹소설 - 카카오페이지`를 비소설 매체로 오분류하지 않도록 했다.
  - [x] `오행복` 같은 주변어에서 엉뚱한 공식 URL이 잡혀도 `망겜힐 -> 망겜의 힐러` 공식 검증 검색을 생략하지 않게 했다.
  - [x] v212 live run에서 `11718097`은 `official_title=망겜의 힐러`, `heretic_url=https://m.munpia.com/novel/detail/328421`, `confidence=High`로 확인됐다.
  - [x] focused unittest 7건, 전체 `tests.test_agentic_pipeline_rework -v` 335건, 관련 `py_compile`, `git diff --check`를 통과했다.
- 다음 작업:
  - [ ] `m.munpia.com` fetch title이 generic title로 보이는 page fetch 품질 리스크를 별도 관찰한다.
  - [ ] `단행본+웹소설` / `단행본+웹툰` 경계 bucket을 high-risk semantic review에 추가한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v210 `23센줄` 자연어 해석 / 저정보 slang alias cleanup

- 상태: patched / full unittest verified / VLM-OCR targeted reviewed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v210 known-bad 4건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 재확인했다.
  - [x] `11718091`은 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄`을 reason에 남기고 `official_title=null`을 유지했다.
  - [x] `11718083`은 `unresolvable_memory_query/title null`로 유지했다.
  - [x] slang DB에 남아 있던 `너에겐 -> 너 따위에겐 절대X3...` 저정보 alias 오염을 확인하고 제거했다.
  - [x] 대명사+조사, 일반 술어, 담화 표면 alias가 저장/seed 재사용되지 않도록 guard를 추가했다.
  - [x] `tests.test_slang_db -v` `25`건과 `tests.test_agentic_pipeline_rework -v` `333`건을 통과했다.
- 다음 작업:
  - [ ] `11718083`류 memory-query no-anchor와 `너/나/네가`류 저정보 alias를 high-risk bucket에서 확대 검토한다.
  - [ ] `11718097`은 title recall과 URL/evidence strength를 분리해 후속 official URL 보강 여부를 본다.
  - [ ] `11718099`는 VLM/OCR conflict가 전문가 reason에 남는 문제를 계속 `HOLD`로 추적한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v209 `11718099` OCR-only conflicting query prune

- 상태: patched / full unittest verified / VLM-OCR live reviewed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] BatchContext alias도 stable direct seed로 인정했다.
  - [x] OCR/image-only 후보 수집 범위를 Gatekeeper possible title 밖으로 확장했다.
  - [x] long-tail search purpose까지 OCR-only conflict pruning을 적용했다.
  - [x] `_execute_searches()` 직전 pruning으로 후속 검색 batch도 정리한다.
  - [x] v209 live run에서 `11718099`는 `official_title=빌어먹을 환생`, `url=https://novel.munpia.com/222360`으로 확인했다.
  - [x] `tests.test_agentic_pipeline_rework -v` `333`건과 관련 `py_compile`을 통과했다.
  - [x] `slang_db` 신규 오염 없음 확인.
- 다음 작업:
  - [ ] OCR/VLM 후보가 browser visual evidence 또는 stable alias와 충돌하면 검색 pruning뿐 아니라 전문가 입력/심의 reason에서도 `conflict_ocr_title`로 낮춘다.
  - [ ] `image_enrichment`의 OCR-only `explicit_work_title`/`work_cues`가 Decoder term pool과 deliberation support로 강하게 들어가는 경로를 줄인다.
  - [ ] `11718099`류를 high-risk bucket `VLM_OCR_involved`, `reason_decision_contradiction`, `weak_evidence_but_strong_resolution`에서 확대 확인한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v208 `11718099` title-lead alias/status/OCR conflict

- 상태: patched / full unittest verified / VLM-OCR live reviewed / browser visual checked / semantic gate REVIEW-LOCKED
- 완료:
  - [x] BatchContext resolved alias를 검색 seed/budget 보존 경로에 포함했다.
  - [x] 제목 선두 alias `빌환`은 OCR 후보/상태어가 있어도 보존한다.
  - [x] `표지변경됨` 같은 상태어는 standalone 작품 seed와 compact query suffix에서 제외한다.
  - [x] `있어`, `있어도`, `없어` 계열 술어 조각은 alias inference에서 제외한다.
  - [x] episode/detail variant title을 canonical base로 보정하는 guard를 추가했다.
  - [x] v207 slang_db 오염 `있어 -> 따먹을 환생`을 제거했다.
  - [x] v208 live run에서 `11718099`는 `official_title=빌어먹을 환생`, `url=https://novel.munpia.com/222360`으로 확인했다.
  - [x] Codex 내장 브라우저로 원문 이미지 로딩 완료와 실제 표지 제목 `빌어먹을 환생`을 확인했다.
  - [x] `tests.test_agentic_pipeline_rework -v` `333`건과 관련 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] VLM/OCR 후보가 브라우저 시각 근거와 충돌하면 검색/전문가 심의 전에 더 빨리 낮춘다.
  - [ ] `search_absent_verified_title` counter와 최종 alias rescue가 함께 남는 reason-final 정합성 문제를 줄인다.
  - [ ] 이미지 post는 browser visual evidence가 없으면 VLM/OCR 결과만으로 `Strong`에 올리지 않는다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v204 `23센줄` 오타/의미 재검토 reason

- 상태: patched / focused verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] semantic seed review 프롬프트가 `surface_paraphrase_notes`를 원문 이해 힌트로 우선 반영하게 했다.
  - [x] final reason에 `표면 표현 해석: 23센줄 -> 23세인 줄; 16살인줄 -> 16살인 줄`을 남긴다.
  - [x] 마지막 seed가 surface sanitizer에서 제거되면 `semantic_seed_review.is_specific_work_discussion=false`로 내부 flag도 낮춘다.
  - [x] `seed 후보(...)는` 문구로 조사 깨짐을 피한다.
  - [x] v204 live run에서 `11718091`은 `is_relevant=false`, `official_title=null`, `discussion_type=noise`, `title_resolution_allowed=false`로 확인했다.
  - [x] focused unittest와 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] `N센줄`, `N살인줄`, 짧은 인명 + 나이/외모 감상 패턴을 high-risk semantic bucket에서 확대 확인한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v201 semantic seed review reason 반영

- 상태: patched / focused verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 비관련 reason 합성기가 `semantic_seed_review.content_interpretation/post_intent`를 final reason에 반영하게 했다.
  - [x] `semantic_seed_review_context_terms`를 `작품 seed 제외`로 노출해 어떤 표현이 작품명/별칭 seed가 아닌지 남긴다.
  - [x] core reason에 `직접 작품 앵커가 없어 공식 제목은 미확정`을 붙여 과확정처럼 보이지 않게 했다.
  - [x] v201 live run에서 `의미 재검토`, `작품 seed 제외: 은영이, 23센줄`, `official_title=null`을 확인했다.
  - [x] focused unittest와 `py_compile`을 통과했다.
- 다음 작업:
  - [ ] `short_banter_seed_demoted` high-risk bucket에서 reason이 semantic 이해를 충분히 설명하는지 확대 확인한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v199 LLM semantic seed review / no-anchor 조기종료

- 상태: patched / unit verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 표면 규칙만으로 `23센줄`류를 차단하지 않고, `discourse_semantic_seed_guard` LLM hook이 title/body/comment와 1차 seed를 다시 읽게 했다.
  - [x] LLM seed review가 `title_novel_terms`/`search_suggestions`를 작품명 후보가 아닌 자연어 문맥어로 판정하면 제거하고 `semantic_seed_review` 공개 필드에 남긴다.
  - [x] known alias/strong anchor는 보호해, 안정 약칭까지 무조건 drop하지 않는다.
  - [x] Orchestrator가 demoted seed를 `key_terms` fallback으로 되살리지 않도록 했다.
  - [x] 모든 title seed가 demote됐고 이미지/OCR/VLM 또는 강한 작품 앵커가 없으면 Decoder/search rescue를 열지 않고 조기 종료한다.
  - [x] v199 live run은 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 실행했고, manifest 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
  - [x] v199 result에서 `11718091`은 검색/Decoder 재승격 없이 `is_relevant=false`, `official_title=null`, `discussion_type=noise`로 종료했다.
  - [x] `py_compile` 및 `tests.test_agentic_pipeline_rework -v` `329`건을 통과했다.
- 다음 작업:
  - [x] early-exit final reason에 `semantic_seed_review.content_interpretation`을 반영한다. v201에서 targeted 확인 완료.
  - [ ] `short_banter_seed_demoted`, `semantic_seed_review_specific_work_denied`, `search_decoder_early_exit`을 high-risk semantic bucket에 넣어 대량 검토한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다. expanded random baseline/high-risk review 전까지 `REVIEW-LOCKED` 유지.

## 2026-05-29 v195 표면 오타/나이 감상 문맥 가드

- 상태: patched / unit verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `23센줄`을 작품명/별칭 후보가 아니라 `23세인 줄` 자연어 오타/축약으로 해석하는 `surface_paraphrase_notes`를 추가했다.
  - [x] 제목/본문/댓글에서 `23센줄`, `16살인줄` 같은 나이 표현을 `role=non_title_semantic_context`로 전달한다.
  - [x] Discourse 결과의 `title_novel_terms`에서 표면 오타와 짧은 인명형 문맥어를 제거하고, 관련 `search_suggestions`도 제거한다.
  - [x] Orchestrator 검색 seed, Discourse suggestion, verification_search에서 나이/외모 감상 파생 쿼리를 실행 전에 제거한다.
  - [x] v191/v193/v194/v195 단계로 실제 live canary를 확인했고, 최종 v195에서는 실제 검색 실행 없이 `is_relevant=false`, `official_title=null`, `discussion_type=noise`로 종료했다.
  - [x] `py_compile` 및 `tests.test_agentic_pipeline_rework -v` `327`건을 통과했다.
- 다음 작업:
  - [ ] `N센줄`, `N살인줄`, 짧은 인명 + 외모/나이 감상 패턴을 high-risk semantic bucket에 추가 감시한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다. expanded random baseline/high-risk review 전까지 `REVIEW-LOCKED` 유지.

## 2026-05-29 v187 VLM/OCR reason evidence alignment

- 상태: patched / unit verified / live rerun pending / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v184 `11718099`에서 최종 title은 `빌어먹을 환생`으로 회복됐지만 OCR drift 후보 `불먹을 혼성명`이 reason에서 "보조 제목 표기"처럼 남는 잔여 리스크를 분리했다.
  - [x] `_build_image_grounding_note()`가 최종 title과 다른 OCR/표지 후보를 보조 제목 근거로 쓰지 않는다고 명시하도록 바꿨다.
  - [x] `test_image_grounding_note_softens_nonmatching_ocr_title` 기대값을 "최종 제목과 일치하지 않아 / 보조 제목 근거로 사용하지 않습니다"로 갱신했다.
  - [x] focused unittest 2건과 `py_compile`을 통과했다.
  - [x] `qualitative_review\20260528_141006_620986\v187_active_goal_requirement_audit_ko_20260529.md`에 active goal 요구사항별 증거/미완료 범위를 다시 기록했다.
- 다음 작업:
  - [ ] 다음 `--vlm on --ocr on` live canary에서 `11718099` reason이 OCR drift 후보를 보조 근거로 과확정하지 않는지 확인한다.
  - [ ] VLM/OCR OCR-derived title conflict는 high-risk bucket에서 별도 감시한다.

## 2026-05-29 v186 large rerun VLM/OCR-on readiness

- 상태: documented / not executed / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 10만 건급 semantic 재런은 `--vlm on --ocr on` 기준이라는 운영 기준을 재확인했다.
  - [x] 새 completed source는 기존 `out\expert_result_20260528_141006_620986*` partial artifacts를 덮어쓰지 않는 별도 output으로 생성해야 함을 기록했다.
  - [x] 기본 재런 템플릿을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 고정했다.
  - [x] 36-shard Docker lifecycle 검증은 `--allow-goal-shard-lifecycle --auto-up-shards`를 붙인 별도 모드로 분리했다.
  - [x] readiness artifact `qualitative_review\20260528_141006_620986\v186_large_rerun_vlm_ocr_on_readiness_ko_20260529.md`를 추가했다.
- 다음 작업:
  - [ ] 전체 입력 JSONL 경로를 확정한다.
  - [ ] 새 timestamp output path를 정하고 기존 partial output과 충돌하지 않는지 확인한다.
  - [ ] 대형 재런 후 manifest에서 `vlm_enabled=true`, `ocr_enabled=true`, `vlm_ocr_semantic_review_ready=true`, clean completion을 확인한다.
  - [ ] preflight, random baseline 1,000건 이상, P0/P1 high-risk expansion 전까지 semantic gate는 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v184 URL media-type / weak character-page guard 후속

- 상태: patched / unit verified / VLM-OCR live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v183 `11718099`에서 validator가 기각한 KakaoPage 웹툰 URL이 final URL로 남는 증상을 재현 이슈로 분리했다.
  - [x] v183 `11718091`에서 캐릭터 나이/외모 잡담이 등장인물 page 검색만으로 `집이 없어`에 resolved되는 과확정 경로를 분리했다.
  - [x] 같은 URL의 검색 근거가 웹툰/만화/파생 팬픽 매체로만 지지되면 소설 상세 URL 후보에서 제외하도록 했다.
  - [x] URL validator는 해당 URL을 `non_novel_media_platform_detail`로 invalid 처리한다.
  - [x] final reference freeze는 비소설 매체 URL을 지우고, 정확한 소설 상세 URL이 있으면 그쪽으로 동기화한다.
  - [x] 약한 캐릭터 반응글에서 Verifier/관계판정이 작품 승격을 거부하면 `character_page_search` rescue를 막는다.
  - [x] focused regression 7건, `tests.test_agentic_pipeline_rework` 323건, `tests.test_expert_main_input_loader` 29건, 관련 `py_compile` 통과.
  - [x] v184 live run `20260529_155118_539513`을 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 실행했다.
  - [x] v184 manifest 기준 `input_post_count=4`, `effective_parallel=4`, `completed/failed/pending/flushed=4/0/0/4`, `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count=3`, Docker lifecycle flags false를 확인했다.
  - [x] v184 result 기준 `11718091=title null/is_relevant false`, `11718099=빌어먹을 환생 + Naver Series detail URL`, `11718097=망겜의 힐러`, `11718083=title null/unresolvable_memory_query`를 확인했다.
  - [x] v185 goal status audit과 large-scale preflight를 생성해 원본 source가 `104502/80/71/9/0`, random shortfall `929`, overall `REVIEW-LOCKED`임을 재확인했다.
- 다음 작업:
  - [ ] `11718083`류는 `is_relevant`만으로 성공/실패를 판정하지 않고 `title_resolution_state`, `title_resolution_allowed`, `is_resolved_work_discussion`, `work_resolution`을 같이 보는 gate를 유지한다.
  - [ ] `11718097`처럼 title은 맞지만 official detail URL이 없는 케이스는 title correctness와 URL/evidence strength를 분리해 `Medium` 근거로 유지한다.
  - [ ] 새 completed large source를 만들기 전까지 원본 partial result 기반 random/high-risk 산출물은 approval 근거가 아니라 부족 증거로만 둔다.
  - [ ] 10만 건 semantic gate는 expanded random baseline/high-risk bucket review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 title/url match-quality ordering v182 후속

- 상태: patched / unit verified / targeted live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] `11718099` 원본 증상을 `표지변경` title 승격과 후속 title/url pair 흔들림으로 분리했다.
  - [x] source title match 품질을 exact/similar-or-strict/partial phrase로 나누고, URL 선택에서 플랫폼 rank보다 먼저 보도록 했다.
  - [x] reference freeze 단계의 `primary_work.heretic_url` 동기화도 match-quality 기준으로 보강했다.
  - [x] focused regression 3건, `tests.test_agentic_pipeline_rework` 318건, `tests.test_expert_main_input_loader` 29건, 관련 `py_compile` 통과.
  - [x] v182 live run `20260529_151429_633557`을 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 실행했다.
  - [x] v182 manifest 기준 `input_post_count=4`, `effective_parallel=4`, `completed/failed/pending/flushed=4/0/0/4`, `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count=3`, Docker lifecycle flags false를 확인했다.
  - [x] v182 result 기준 `11718099=빌어먹을 환생 + Naver Series detail URL`, `11718097=망겜의 힐러`, `11718083/11718091=title null`을 확인했다.
- 다음 작업:
  - [ ] v182 W3에서 Naver Series URL 직접 fetch가 `content_deleted_or_unavailable`로 기각됐는데 final rescue가 URL을 유지한 경로를 URL validator/final-rescue evidence-state 정합성 P1로 정리한다.
  - [ ] v182 `11718099` flags에 `multi_work_title_cleared`, `primary_work_cleared_non_resolved`, `batch_memory_exact_alias_rescued`가 함께 남는 stale flag cleanup을 후속 처리한다.
  - [ ] title/url pair targeted regression은 통과했지만, 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 VLM/OCR-on semantic baseline v181 후속

- 상태: patched / unit verified / targeted live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] 이미지 post가 포함된 semantic regression 기준을 `--vlm on --ocr on`으로 재고정했다.
  - [x] v181 이후 goal/test semantic regression 명령은 텍스트 전용 예외라고 명시하지 않는 한 `--vlm on --ocr on`을 붙이는 기준으로 문서화했다.
  - [x] `expert_main.py` manifest에 `vlm_enabled`, `ocr_enabled`, `image_post_count`, `image_posts_present`, `vlm_ocr_semantic_review_ready`, `vlm_ocr_semantic_review_warning`을 추가했다.
  - [x] v179 `11718082` text-only 판정은 이미지 OCR/VLM evidence가 없었으므로 semantic approval 근거에서 제외했다.
  - [x] v181 live run `20260529_144914_316168`에서 `11718082`가 이미지 근거로 `재벌가 차녀의 2회차 걸그룹` resolved되는 것을 확인했다.
  - [x] v181 live run에서 `11718080`은 이미지 없는 한탄/장르 일반론으로 rejected/title null 유지되는 것을 확인했다.
  - [x] `11718080`의 본질은 LLM 이해 전문가 실패가 아니라 후단 `batch memory alias` rescue가 generic-discourse veto를 뒤집은 문제로 분리했다.
  - [x] `late_rescue_blocked_by_verifier_generic_veto` guard를 추가했고 post id/특정 alias 하드코딩 없이 공개 expert/evidence fields 기반으로 막았다.
  - [x] `py_compile`, focused semantic/VLM regression 4건, `tests.test_agentic_pipeline_rework` 316건, `tests.test_expert_main_input_loader` 29건을 통과했다.
- 다음 작업:
  - [ ] 10만 건 semantic gate는 targeted 5건으로 올리지 않는다. random baseline 1,000건 이상과 high-risk bucket expansion을 별도로 수행한다.
  - [ ] 이미지 post에서 DC 이미지 로딩 지연/누락이 보이면 Browser visual evidence와 VLM/OCR evidence를 함께 packet에 남기고, 이미지 미제공 상태의 결론은 `INFO_MISSING/REPROCESS`로 보낸다.
  - [ ] `11718082`는 VLM/OCR 때문에 단건 `319.6s`급 long-tail이 생겼으므로 image-heavy path의 OCR/VLM timeout, cache, evidence reuse를 별도 P1 성능 작업으로 분리한다.

## 2026-05-29 goal/reuse-only explicit endpoint filter v180 후속

- 상태: patched / unit verified / live explicit-endpoint case pending
- 완료:
  - [x] 현재 v179 live run은 `--parallel 36`, 입력 5건에서 `effective_parallel=5`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`였고 Docker/Compose 실행 흔적은 없었다.
  - [x] 오래된 `MCP_ENDPOINTS` 명시 목록이 남은 goal/reuse-only run에서도 dead endpoint를 계속 들고 가지 않도록 healthy subset 필터를 autogen 외 경로까지 넓혔다.
  - [x] health failure 안내가 goal/reuse-only에서 `warp_shards.py up`을 기본 조치처럼 보이지 않도록 문구를 분리했다.
  - [x] `tests.test_expert_main_input_loader`에 explicit endpoint 축소와 large validation 미축소 회귀 테스트를 추가했다.
  - [x] `py_compile`, `tests.test_expert_main_input_loader -v` 27건 통과.
- 다음 작업:
  - [ ] 다음 goal live run에서 `mcp_healthy_endpoint_filter`/`mcp_goal_run_health_filtered` 메타와 Docker/Compose 로그 `0`건을 재확인한다.
  - [ ] run이 여전히 느리면 Compose가 아니라 search retry, page analyzer, Decoder/Verifier prompt, expert loop 병목으로 분리한다.

## 2026-05-29 title-lead alias deliberation skip v178 후속

- 상태: patched / unit verified / live verified / semantic gate REVIEW-LOCKED
- 완료:
  - [x] v177 live run에서 `11718097` correct title에도 full deliberation이 남는 병목을 재현했다.
  - [x] `11718097` W2 기준 full deliberation `81.4s`, post total `236.4s`였고, Compose 실행 흔적은 없었다.
  - [x] score `2.0`이라도 검색 결과 `title` 필드가 제목 첫 alias를 동일 작품명으로 직접 닫는 경우만 `evidence_scorer_only`로 내리도록 했다.
  - [x] `py_compile`, `DeliberationLimitTest` 5건, 기존 회귀 묶음 354건을 통과했다.
  - [x] v178 live run에서 `11718097`이 `망겜의 힐러`, `11718099`가 `빌어먹을 환생`으로 유지됐다.
  - [x] v178 W2 로그에서 `11718097`은 `title-lead alias search bridge resolved`, `method=evidence_scorer_only`, `2 iterations`, post total `190.5s`로 종료됐다.
  - [x] v178 로그에서 `full_deliberation_ABC`/debate/jury 및 Docker/Compose/shard lifecycle 실행 흔적이 `0`건임을 확인했다.
- 다음 작업:
  - [ ] `11718097`류 URL 없는 resolved title은 title 판정과 official detail evidence를 분리해 `Medium` 근거로 유지한다.
  - [ ] expanded qualitative review 전까지 10만 건 semantic gate는 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 goal/test Compose status-audit hard block v176 후속

- 상태: patched / unit verified / live reverified / docs updated
- 완료:
  - [x] goal/test run에서 Docker Compose lifecycle뿐 아니라 Compose status audit 경로도 기본 차단했다.
  - [x] stale `MCP_LOCAL_SHARD_STATUS_AUDIT=1`만으로는 `warp_shards.py status`/Compose exec 조회가 열리지 않게 했다.
  - [x] status audit이 진짜 목적이면 `MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT=1`을 추가로 요구한다.
  - [x] manifest/run config에 status audit 요청/허용 상태를 분리 기록한다.
  - [x] `py_compile`, focused lifecycle regression 4건, `tests.test_expert_main_input_loader` 25건을 통과했다.
  - [x] v175 live 로그/manifest에서 compose 관련 실행 흔적이 0건임을 재확인했다.
  - [x] v178 live 로그/manifest에서도 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit=false`, compose 관련 실행 흔적 `0`건을 확인했다.
- 다음 작업:
  - [x] 실제 goal/test 재실행에서는 기본값 또는 `--reuse-shards-only`를 우선 사용하고, shard lifecycle/status audit 검증이 목적일 때만 관련 opt-in을 붙인다.
  - [ ] 단건/소량 run이 느리면 Compose가 아니라 search retry, page analyzer, Decoder/Verifier prompt, expert loop 병목으로 먼저 분리한다.

## 2026-05-29 memory-query weak-title forced-upgrade guard v175 후속

- 상태: patched / unit verified / live verified / performance follow-up closed for title-lead alias
- 완료:
  - [x] `11718083`처럼 기억 회수 글에서 direct proof가 없는 weak title relation-hold 후보가 Arbiter에서 다시 살아나는 경로를 차단했다.
  - [x] Verifier/Relation이 hold/downgrade한 memory-query title-present 케이스는 추가 collaboration/full deliberation을 열지 않도록 했다.
  - [x] post id 하드코딩 없이 direct anchor, post direct grounding, explicit bridge, relation flags, downgrade counter로만 조건을 구성했다.
  - [x] v175 live known-bad 4건에서 `11718083=null`, `11718091=null`, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`을 확인했다.
  - [x] v174 대비 `11718083` 처리 시간이 `330.9s`에서 `102.6s`로 줄었다.
  - [x] `py_compile`과 focused memory-query regression 5건을 통과했다.
- 다음 작업:
  - [x] `11718097` correct title long-tail은 v178에서 `evidence_scorer_only`로 내려 targeted canary 기준 닫았다.
  - [ ] known-bad 4건 canary는 10만 건 semantic approval 근거가 아니므로 expanded qualitative review gate는 계속 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 memory-query unresolved fast-path v173 후속

- 상태: patched / unit verified / live verified / performance follow-up open
- 완료:
  - [x] `11718083` memory-query/null-title 케이스에서 Verifier 공개 출력이 실제로 존재한 뒤에만 settled fast-path가 열리도록 했다.
  - [x] Verifier가 no-title/weak bridge/hold-nullify 방향으로 정리한 memory-query unresolved 케이스는 추가 collaboration과 Synthesizer를 종료하도록 했다.
  - [x] 같은 조건에서 Deliberation은 full Jury/Debate 대신 `evidence_scorer_only`로 종료하도록 했다.
  - [x] direct quote/source, official URL, character/title link, direct title anchor가 있으면 fast-path가 열리지 않도록 했다.
  - [x] v172의 빈 Verifier 조기 skip 위험은 `test_memory_query_settled_rejection_waits_for_verifier_output`로 회귀 테스트화했다.
  - [x] v173 live run `20260529_132113_820839`에서 `11718083`이 `is_relevant=false`, `novel_identity=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`로 유지되는지 확인했다.
  - [x] v173 live run에서 `docker/compose/force-recreate/warp_shards.py` 실행 흔적이 `0`건임을 확인했다.
  - [x] v171 `365.3s`/`102,794` tokens에서 v173 `155.5s`/`62,730` tokens까지 줄였다.
  - [x] `py_compile`, focused regression 5건, 관련 통합 회귀 349건을 통과했다.
- 다음 작업:
  - [ ] v173도 단건 `155.5s`라서 search/deep-search/page analyzer와 대형 Decoder/Verifier prompt를 별도 P1로 줄인다.
  - [ ] memory-query lookup profile에서 direct proof가 없고 weak evidence가 반복되면 검색 retry/page analyzer/Decoder prompt/reason_review를 제한할지 검토한다.
  - [ ] fast-path는 post id 하드코딩이 아니라 공개 필드와 evidence 조건으로만 유지한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 env-only Docker lifecycle block v171 후속

- 상태: patched / unit verified / docs updated
- 완료:
  - [x] `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1`만으로 `expert_main.py`가 Docker Compose lifecycle에 진입하지 않도록 차단했다.
  - [x] env 기반 lifecycle은 명시 ack `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` 또는 legacy `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1`이 있을 때만 인정한다.
  - [x] Codex/small goal run에서는 env ack가 있어도 현재 명령의 `--allow-goal-shard-lifecycle`이 없으면 `up/recreate/local shard management`를 열지 않는다.
  - [x] run config/manifest에 env lifecycle 요청/허용 상태를 남긴다.
  - [x] `tests.test_expert_main_input_loader` 25건, 통합 회귀 344건, `py_compile`을 통과했다.
- 다음 작업:
  - [x] v171 live goal run `20260529_125908_474586` manifest에서 `mcp_env_shard_lifecycle_requested=false`, `mcp_env_shard_lifecycle_allowed=false`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`를 함께 확인했다.
  - [ ] lifecycle 검증이 목적이 아니면 `--auto-up-shards`/`--auto-recreate-shards`를 붙이지 않는다.
  - [ ] 11718083 성능 병목은 Compose 문제가 아니라 search/decoder/verifier 반복 문제로 계속 별도 최적화한다.

## 2026-05-29 settled Verifier veto v169 후속

- 상태: patched / live verified / performance follow-up open
- 완료:
  - [x] `11718083` memory-query/null-title 케이스에서 Verifier critical veto와 음수 evidence가 이미 결론을 지지하면 Jury/Debate를 열지 않는 fast-path를 추가했다.
  - [x] v169 live run에서 `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`를 확인했다.
  - [x] v169 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/flushed/pending/failed=1/1/0/0`을 확인했다.
  - [x] v169 manifest/log에서 Docker Compose lifecycle 미진입을 확인했다.
  - [x] `tests.test_llm_client_multimodal`와 `tests.test_expert_main_input_loader` 통합 회귀 `36`건을 통과했다.
- 다음 작업:
  - [ ] v169 단건 `441.6s`, `total_tokens=176,274`, search degraded `10/13`을 P1 성능 이슈로 최적화한다.
  - [ ] memory-query/unresolvable fast-path에서 direct title proof가 없고 Verifier veto가 있으면 late canonical rescue, 추가 검색 retry, 대형 decoder prompt, reason_review를 줄일 수 있는지 검토한다.
  - [ ] fast-path는 post id 하드코딩이 아니라 공개 필드와 evidence 조건으로만 유지한다.
  - [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 goal/test compose avoidance and partial subset v167 후속

- 상태: patched / unit verified / v169 live compose-free verified / large rerun pending
- 완료:
  - [x] goal/test run에서 Docker Compose lifecycle이 hard opt-in 없이는 열리지 않는 정책을 재검증했다.
  - [x] ordered flush gap이 남으면 primary result를 덮어쓰지 않고 `_completed_subset.json`과 `_completed_subset_manifest.json`을 남기도록 했다.
  - [x] manifest에 completed subset과 `partial_flush_gap`/`ordered_flush_blocked`/`large_run_complete` 상태를 기록하도록 했다.
  - [x] `tests.test_expert_main_input_loader` 24건과 `py_compile`을 통과했다.
  - [x] v169 live goal run에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`와 compose 관련 로그 없음까지 확인했다.
- 다음 작업:
  - [ ] 다음 large rerun은 새 output으로 실행하고 `pending_count=0`, `flushed_count=completed_count=input_post_count`, `large_run_complete=true`를 확인한다.
  - [ ] completed subset artifact가 생성된 run은 triage용으로만 쓰고 semantic approval source로 쓰지 않는다.

## 2026-05-29 large rerun readiness plan v166 후속

- 상태: plan written / environment observed / review locked
- 완료:
  - [x] `qualitative_review\20260528_141006_620986\v166_large_rerun_readiness_plan_ko_20260529.md`를 작성했다.
  - [x] 현재 `expert_main|llm_batch|warp_shards|vllm|uvicorn|openai` 매칭 Python 점유가 없음을 확인했다.
  - [x] 현재 Docker shard는 `1..5` group만 떠 있음을 확인했다.
  - [x] reuse-only safe mode와 explicit 36-shard validation mode를 분리했다.
  - [x] full/large rerun 후 manifest, health audit, large-scale preflight, random baseline, high-risk expansion 순서를 명령 단위로 고정했다.
- 다음 작업:
  - [ ] 실제 large rerun은 기존 `out\expert_result_20260528_141006_620986*`를 덮어쓰지 않고 새 timestamp output으로 실행한다.
  - [ ] 36-shard validation이 필요하면 Docker lifecycle 의도를 명시하고 실행 전후 shard audit을 남긴다.
  - [ ] 새 run manifest가 clean completion을 증명하기 전까지 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-29 large-scale qualitative preflight v165 후속

- 상태: preflight tool added / original and recovered sources checked / review locked
- 완료:
  - [x] `tools/preflight_qualitative_large_scale_review.py`를 추가했다.
  - [x] preflight가 result rows, manifest completed/flushed/pending, checkpoint completed, pending snapshot, source policy, random target feasibility, high-risk target population을 검사한다.
  - [x] 원본 final result source preflight: result rows `71`, manifest `input=104502/completed=80/flushed=71/pending=9`, random shortfall `929`, gate `REVIEW-LOCKED`.
  - [x] recovered subset source preflight: result rows `80`, `source_dataset_kind=checkpoint_recovered_completed_subset`, random shortfall `920`, gate `REVIEW-LOCKED`.
  - [x] `test_large_scale_preflight_blocks_partial_recovered_subset` 회귀 테스트를 추가했다.
- 다음 작업:
  - [ ] large-scale qualitative expansion은 이 preflight가 `GO` 또는 최소 `REVIEW`로 열리는 충분한 completed source에서만 실행한다.
  - [ ] 현재 원본 partial/recovered source로 생성한 리뷰 산출물은 triage/evidence로만 유지하고 approval 근거로 쓰지 않는다.

## 2026-05-29 sample target shortage audit v164 후속

- 상태: tooling patched / shortage audit generated / review locked
- 완료:
  - [x] random control manifest가 요청 표본 수와 실제 선택 수를 분리하도록 했다.
  - [x] `requested_sample_size`, `selected_sample_size`, `sample_shortfall`, `sample_target_satisfied`, `sample_coverage_ratio`를 기록한다.
  - [x] Round2 high-risk manifest가 `target_total`, `selected_total`, `target_satisfied`, `target_shortfalls`, `bucket_coverage_ratios`를 기록한다.
  - [x] `gate_decision.md`가 random baseline `1,000`건 미달과 Round2 high-risk target 미달을 `Weak/Missing` evidence로 반영한다.
  - [x] v164 shortage audit을 생성했다: recovered subset 80건 기준 Round2 target `340` 중 selected `79`, random 요청 `1000` 중 selected `1`.
- 다음 작업:
  - [ ] 현재 recovered subset은 large-scale semantic approval source로 사용할 수 없다.
  - [ ] full/large rerun 또는 충분한 completed source가 생긴 뒤 random baseline `1,000+`와 P0/P1 bucket별 `200~500`건을 다시 생성한다.

## 2026-05-29 recovered subset review source policy v163 후속

- 상태: tooling patched / unit verified / recovered subset smoke verified / review locked
- 완료:
  - [x] `build_qualitative_round2_review.py`가 `v162_run_integrity_recovered_completed_80.json` 같은 recovered artifact 경로에서도 원본 run id `20260528_141006_620986`을 추론하도록 했다.
  - [x] Round2 manifest와 canonical sample manifest에 `source_review_policy`를 추가해 `checkpoint_recovered_completed_subset`, `recoverable_pending_flush_gap`, `large_run_complete=false`, recovered row count를 기록하도록 했다.
  - [x] `build_qualitative_random_control_review.py`도 같은 `source_review_policy`를 남기고, random control 추가 후 `summary.json`/`gate_decision.md`를 재계산하도록 했다.
  - [x] random builder가 canonical summary 재계산 시 Round2 모듈의 기본 run id로 오염되던 문제를 `round2_manifest.run_id`/`sample_seed` 재주입으로 막았다.
  - [x] recovered 80건 subset 기준 v163 smoke를 실행했다: Round2 `30`건, random control `20`건, canonical labels `50`건, gate `NO-GO`.
- 다음 작업:
  - [ ] v163 smoke는 도구 검증용 소표본이므로 전체 품질 기준선으로 쓰지 않는다.
  - [ ] random baseline 최소 `1,000`건과 P0/P1 high-risk 확대 전까지 10만 건 semantic approval은 계속 금지한다.

## 2026-05-29 partial run checkpoint recovery v162 후속

- 상태: run integrity gap classified / recovery tool added / review locked
- 완료:
  - [x] 원본 `20260528_141006_620986` 산출물의 final result `71`, checkpoint completed `80`, pending snapshot `9` 차이를 재검증했다.
  - [x] final에 없는 checkpoint completed 9건이 pending snapshot 9건과 정확히 일치함을 확인했다.
  - [x] ordered flush가 `global_idx=72` 미완료 row에서 막혀 이후 completed row 9건이 pending snapshot에 남은 `recoverable_pending_flush_gap`으로 분류했다.
  - [x] `tools/recover_expert_run_from_checkpoint.py`를 추가해 원본 result를 덮어쓰지 않고 checkpoint completed subset 80건을 복구하도록 했다.
  - [x] `tests/test_recover_expert_run_from_checkpoint.py`와 `py_compile`을 통과했다.
  - [x] 복구 산출물 `qualitative_review\20260528_141006_620986\v162_run_integrity_recovered_completed_80.json`와 요약 `v162_run_integrity_recovery_summary.json`을 남겼다.
- 다음 작업:
  - [x] review builder와 후속 semantic review는 v163부터 `source_review_policy`로 final result, recovered completed subset, checkpoint/pending 설명 중 어떤 기준을 쓰는지 manifest에 남긴다.
  - [ ] `pending_count>0`, `flushed_count<completed_count`, clean completion summary 부재 상태이므로 원본 10만 run은 계속 partial run으로 취급한다.
  - [ ] source run 전체 완료와 10만 건 semantic approval은 expanded random/high-risk review와 별도 full/large rerun 증거 전까지 금지한다.

## 2026-05-29 comment author context lines v161 후속

- 상태: patched / unit verified / live regression passed / review locked
- 완료:
  - [x] `expert_main.py` result row의 `comment_context_lines`에 `author=<comment author>`를 추가했다.
  - [x] `src/llm_batch/agentic_pipeline.py` prompt용 `comment_context_lines`에도 `author=`를 추가했다.
  - [x] `tools/build_qualitative_round2_review.py`가 `comment_metadata`에서 `author=`를 재구성하도록 했다.
  - [x] `tests.test_expert_main_input_loader`, `tests.test_qualitative_review_packet_tools`, focused pipeline tests, `tests.test_agentic_pipeline_rework`를 통과했다.
  - [x] v161 live regression에서 `11718091/11718097`의 comment context line에 `speaker`, `author`, `role=post_author`, `comment_id`가 남는 것을 확인했다.
  - [x] v161 manifest/log에서 Docker Compose lifecycle 미진입과 `requested_parallel=36 -> effective_parallel=5` 축소를 확인했다.
- 다음 작업:
  - [ ] 댓글 작성자 메타는 대화 흐름 해석용으로만 사용하고, 직접 작품 앵커가 없는 경우 independent identity evidence로 세지 않는 guard를 expanded review에서 계속 감시한다.
  - [ ] `qualitative_review\20260528_141006_620986\v161_goal_status_audit_ko_20260529.md`의 P0/P1 남은 작업을 순서대로 처리한다.
  - [x] 원본 partial run의 checkpoint completed `80`, final result `71`, pending `9` 차이는 v162에서 `recoverable_pending_flush_gap`으로 분류하고 completed subset 80건을 별도 복구했다.
  - [ ] random baseline 최소 `1,000`건과 P0/P1 high-risk bucket 확대 전까지 전체 semantic approval은 금지한다.
  - [ ] v161은 targeted regression이므로 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 memory-query batch alias rescue guard v159 후속

- 상태: patched / unit verified / live canary passed / review locked
- 완료:
  - [x] `11718083` memory-query quote post에서 `plot_mention`을 direct title proof로 보지 않도록 했다.
  - [x] BatchContext alias rescue가 memory-query canonical block을 덮어쓰지 못하게 `_memory_query_blocks_batch_alias_rescue()`를 추가했다.
  - [x] `test_memory_query_batch_alias_rescue_does_not_override_blocked_canonical_title` 회귀 테스트를 추가했다.
  - [x] `tests.test_agentic_pipeline_rework` 305건, `tests.test_expert_main_input_loader` 23건, py_compile을 통과했다.
  - [x] v159 live canary에서 `11718083`이 `is_relevant=false`, `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 내려가는 것을 확인했다.
  - [x] v159 manifest/log에서 Docker Compose lifecycle 미진입과 forbidden batch alias registration 미발생을 확인했다.
  - [x] v160 known-bad 5건 regression에서 `11718083/11718091/11718118`은 title null, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`으로 확인했다.
  - [x] v160 manifest/log에서 `completed/failed/pending=5/0/0`, `requested_parallel=36`, `effective_parallel=5`, Docker/warp lifecycle 미진입을 확인했다.
- 다음 작업:
  - [ ] v159/v160은 targeted regression이므로 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 Codex goal env lifecycle hard opt-in v3 후속

- 상태: patched / live verified / semantic follow-up partially patched
- 완료:
  - [x] Codex goal/test run에서 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1` env-only opt-in을 차단했다.
  - [x] env lifecycle opt-in도 현재 명령의 `--allow-goal-shard-lifecycle`과 함께 있을 때만 인정하도록 했다.
  - [x] `tests.test_expert_main_input_loader` 23건과 `py_compile`을 통과했다.
  - [x] v157 live run manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_env_shard_lifecycle_allowed=false`를 확인했다.
  - [x] v157 log에서 `docker compose`, `force-recreate`, `warp_shards.py`, `compose up/down` 실행 흔적이 없음을 확인했다.
  - [x] v159에서 `11718083` memory-query quote post의 wrong-title 재승격을 단건 canary 기준 차단했다.
- 다음 작업:
  - [ ] goal 테스트런이 느릴 때는 Docker lifecycle 여부와 LLM/search 처리 시간을 분리 기록한다.

## 2026-05-29 original partial run semantic pattern scan v155 후속

- 상태: evidence captured / follow-up needed
- 완료:
  - [x] `out/expert_result_20260528_141006_620986.json`와 checkpoint/manifest/pending snapshot을 함께 스캔했다.
  - [x] manifest `input_post_count=104502` 대비 completed `80`, final result rows `71`, pending snapshot `9`인 partial run임을 확인했다.
  - [x] known-bad 4건이 `memory_query_resolved`, `generic_resolved_title`, `weak_evidence_but_strong_resolution`, `resolved_without_direct_post_title_anchor`, `comments_without_author_metadata` 계열에 걸리는 것을 확인했다.
  - [x] `tools/scan_original_semantic_patterns.py`와 v155 JSON/JSONL/Markdown 산출물을 남겼다.
- 다음 작업:
  - [x] high-risk expansion bucket에 `comments_without_author_metadata`, `comment_speaker_context_unavailable`, `memory_query_resolved`, `official_title_evidence_true_but_zero_official_urls`, `platform_non_detail_url_used_near_official_evidence`, `image_or_ocr_involved`를 추가했다.
  - [x] v156 bucket expansion에서 known-bad 4건을 packet으로 커버했다.
  - [x] rare bucket이 큰 bucket에 dedupe 선점되지 않도록 selection order와 covered count를 추가했다.
  - [x] checkpoint completed인데 final result에 없는 9건은 v162에서 pending snapshot과 일치함을 확인하고 `recoverable_pending_flush_gap`으로 분류했다.
  - [ ] image/OCR 개입 row는 브라우저/VLM 직접 확인 packet으로 분리한다.
  - [ ] v155는 자동 flag scan이므로 자연어 semantic label review 전까지 `REVIEW-LOCKED`를 유지한다.

## 2026-05-29 high-risk bucket expansion v156 후속

- 상태: packet generated / review locked
- 완료:
  - [x] `tools/build_qualitative_round2_review.py`에 v155 신규 bucket을 반영했다.
  - [x] `--run-id`와 filename 기반 run id 추론을 추가해 review artifact의 run id 오염을 막았다.
  - [x] candidate count가 적은 bucket을 먼저 선택하고, `selected_counts`와 `covered_counts`를 분리했다.
  - [x] v156 산출물: `qualitative_review/20260528_141006_620986/v156_bucket_expansion`.
  - [x] label counts: `ACCEPT=23`, `HOLD=31`, `REPROCESS=10`, `REJECT=1`, `INFO_MISSING=5`.
  - [x] review packet에 `gallery_id`, `post_author`, `comment_metadata`, `comment_context_lines`, `comment_context_source`를 포함하도록 했다.
  - [x] 댓글은 있으나 author/IP/comment id 메타가 없는 packet은 `INFO_MISSING/human_review`로 분리했다.
- 다음 작업:
  - [ ] v156 `HOLD/REPROCESS/REJECT` queue를 실제 `re_search`/`re_judge`/`human_review`로 처리한다.
  - [ ] `vlm_ocr_public_state_weak`와 `VLM_OCR_involved`는 in-app browser screenshot/VLM 확인 큐로 넘긴다.
  - [ ] `comments_without_author_metadata` bucket은 author/IP/comment_id가 포함된 입력 재구성 후 재판정한다.

## 2026-05-29 small goal/test run shard lifecycle hard opt-in v2 후속

- 상태: patched / unit verified
- 완료:
  - [x] 36건 이하 goal/test run은 Codex 여부와 무관하게 `--auto-up-shards`/`--auto-recreate-shards`만으로 Docker Compose lifecycle이 열리지 않도록 했다.
  - [x] non-Codex small goal run에서 `--auto-*`만 붙어도 local shard management가 비활성으로 남는 회귀 테스트를 추가했다.
  - [x] 운영 문서에 36건 이하 판단 회귀는 기본값 또는 `--reuse-shards-only`로 진행하는 규칙을 갱신했다.
- 다음 작업:
  - [x] v171 live goal run manifest에서 `mcp_small_run_shard_lifecycle_blocked=true`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`를 다시 확인했다.

## 2026-05-29 official URL evidence bucket 후속

- 상태: patched / unit verified / live confirmed
- 완료:
  - [x] v153 `11718097`의 `heretic_url=null`과 reason `official_urls=5` 불일치를 exact row에서 확인했다.
  - [x] 작품 상세가 아닌 플랫폼 URL을 `official_urls` bucket에서 제외했다.
  - [x] v154 run id `20260529_083800_817905`에서 known-bad 4건을 `--parallel 36 --reuse-shards-only`로 재실행했다.
  - [x] v154에서 `11718097=망겜의 힐러`, `official_urls=0`, `heretic_url=null`로 evidence strength가 과장되지 않는 것을 확인했다.
  - [x] v154에서 `11718099=빌어먹을 환생`, Naver Series detail URL 유지 확인.
- 다음 작업:
  - [ ] high-risk expansion에 `official_url_count_mismatch`, `platform_author_or_listing_counted_as_official`, `resolved_without_detail_url` bucket을 추가한다.
  - [ ] `11718097` 같은 URL 없는 resolved title은 title 판정과 official detail evidence를 분리해 `Medium` 근거로 보고한다.
  - [ ] v154는 4건 targeted regression이므로 10만 건 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 late rescue alias self-confirmation guard 후속

- 상태: patched / unit verified / live confirmed
- 완료:
  - [x] v151 live run에서 `11718080`, `11718082`, `11718090`의 late batch memory rescue self-confirmation을 확인했다.
  - [x] 공개 evidence bucket 0 + weak grounding + critical 신호에서는 alias support만으로 direct work bridge를 인정하지 않도록 했다.
  - [x] polluted slang DB seed가 있어도 `batch_memory`/`title_surface` late rescue가 final title을 다시 살리지 못하게 했다.
  - [x] slang DB observation 수집에서 late-rescue contaminated alias 저장을 차단했다.
  - [x] `tests.test_agentic_pipeline_rework` 301건과 `tests.test_slang_db` 20건을 통과했다.
  - [x] v152 live run `20260529_072232_140417`에서 known-bad 8건 완료/실패/대기 `8/0/0`을 확인했다.
  - [x] v152 결과에서 `11718080`, `11718082`, `11718090`, `11718091`, `11718083`, `11716486`은 `official_title=null`, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`으로 확인했다.
- 다음 작업:
  - [ ] 이 guard를 high-risk bucket expansion에서 `weak_evidence_but_strong_resolution`, `slang_db_noise_or_alias_pollution`, `reason_decision_contradiction` 패턴에 적용해 재발률을 확인한다.
  - [ ] v152는 8건 regression이므로 expanded random baseline 전까지 10만 건 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 Codex goal run env lifecycle guard 후속

- 상태: patched / unit verified
- 완료:
  - [x] Codex 실행 환경(`CODEX_SHELL` 또는 `CODEX_THREAD_ID`)에서는 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` env만으로 Docker Compose lifecycle이 켜지지 않도록 했다.
  - [x] 이 차단은 36건 이하뿐 아니라 37건 이상 goal/test 입력에도 적용된다.
  - [x] 현재 명령에 붙은 `--auto-up-shards`/`--auto-recreate-shards`는 계속 명시 opt-in으로 인정한다.
  - [x] env 기반 lifecycle이 꼭 필요해도 Codex goal/test에서는 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1`과 현재 명령의 `--allow-goal-shard-lifecycle`을 함께 사용한다.
  - [x] manifest/run config에 `mcp_interactive_codex_run`, `mcp_env_shard_lifecycle_allowed`, `mcp_env_shard_lifecycle_blocked_by_context`를 남기도록 했다.
  - [x] `py_compile` 및 `tests.test_expert_main_input_loader` 20건을 통과했다.
- 다음 작업:
  - [x] v171 live goal run manifest에서 `mcp_interactive_codex_run=true`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`를 확인했다. 이 run은 stale `MCP_AUTO_*` 요청이 없어서 `mcp_env_shard_lifecycle_blocked_by_context=false`가 정상이다.
  - [ ] shard 복구 자동화 자체를 검증하는 run만 `--auto-up-shards`/`--auto-recreate-shards`를 명령에 명시한다.

## 2026-05-29 goal run healthy shard 기본 필터 후속

- 상태: patched / unit verified / live confirmed
- 완료:
  - [x] 36건 이하 goal/test run에서 lifecycle opt-in이 없으면 autogen endpoint를 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT=8` 기본값으로 제한하도록 했다.
  - [x] `--reuse-shards-only` 없이도 lifecycle-blocked goal run은 healthy autogen endpoint만 남기고 `_PARALLEL`을 healthy 수로 낮춘다.
  - [x] stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수는 여전히 36건 이하 기본 goal run에서 무시된다.
  - [x] stale `MCP_SHARD_COUNT=36`이 남아 있어도 36건 이하 goal/test run은 `MCP_GOAL_RUN_AUTO_SHARD_LIMIT=8`로 제한되도록 했다.
  - [x] `tests.test_expert_main_input_loader` 17건을 통과했다.
- 다음 작업:
  - [x] v150 live goal run에서 healthy filter 메타가 manifest/run_meta에 남는지 확인했다. 입력 8건은 small-run cap으로 endpoint `2`개만 생성됐고 둘 다 healthy라 실제 축소는 발생하지 않았다.
  - [x] v150 manifest/run_meta에서 `mcp_goal_run_health_filtered=false`, `mcp_healthy_autogen_endpoint_filter=false`, `mcp_endpoint_count_after_health_filter=2`, `mcp_healthy_autogen_endpoint_filter_reason=goal_run_lifecycle_blocked`를 확인했다.
  - [ ] shard 복구 자동화 검증 run만 `--auto-up-shards`/`--auto-recreate-shards`를 명시한다.

## 2026-05-29 result row comment speaker context 후속

- 상태: patched / unit verified
- 완료:
  - [x] Pipeline 내부 prompt용 `comment_context_lines`와 별개로 `expert_main.py` 결과 row에도 `comment_context_lines`를 남기도록 했다.
  - [x] `comment_metadata`에서 `speaker`, `author`, `role=post_author`, `ip`, `reply_level`, `reply_to`, `comment_id`를 compact line으로 재구성한다.
  - [x] 댓글 본문에는 author/IP를 섞지 않고 review packet용 공개 메타로 분리 보존한다.
  - [x] `tests.test_expert_main_input_loader` 13건을 통과했다.
- 다음 작업:
  - [x] v150 live goal run 결과 row에서 `comment_context_lines` 필드가 남는지 확인했다. 댓글 없는 row는 `[]`로 기록된다.
  - [x] qualitative review packet builder가 결과 row의 `comment_context_lines`를 우선 사용하고, 없으면 `comment_metadata`에서 재구성하는지 확인했다.
  - [x] `tests.test_qualitative_review_packet_tools`에 packet metadata 보존 및 missing metadata `INFO_MISSING` 회귀 테스트를 추가했다.

## 2026-05-29 title-lead alias discourse preservation 후속

- 상태: code patched / unit verified / live rerun pending
- 완료:
  - [x] `11718097` v148 실패 원인을 Gatekeeper low-specific `community_banter` 유지로 인한 검색 전 조기 종료로 분리했다.
  - [x] 제목 선두 표면 anchor가 Discourse의 novel term/search suggestion에 재포착되고 캐릭터/플롯 논의 신호가 있으면 `worklike_alias_preservation`으로 noise 조기 종료를 보류하도록 했다.
  - [x] Discourse가 재포착한 제목 선두 alias만 검색으로 복구하고, 술어 꼬리 seed는 제외했다.
  - [x] weak single-token/vent negative control은 noise 유지로 확인했다.
  - [x] `tests.test_agentic_pipeline_rework` 298건과 `tests.test_expert_main_input_loader` 12건을 통과했다.
- 다음 작업:
  - [x] v178에서 `11718097` 포함 known-bad set을 `--parallel 36 --reuse-shards-only`로 live rerun했다.
  - [x] v178에서 `11718097`은 검색을 수행했고, 최종 title은 `망겜의 힐러`로 유지됐다. URL 없는 resolved title이므로 evidence strength는 별도 `Medium` 축으로 둔다.
  - [ ] expanded high-risk review에서 `title_lead_alias_discourse_preservation` 계열 false positive 증가 여부를 별도 bucket으로 추적한다.

## 2026-05-29 goal/test lifecycle threshold split 후속

- 상태: patched / unit verified / live confirmed
- 완료:
  - [x] Docker lifecycle 차단 기준을 입력 post 수 기준으로 분리했다.
  - [x] `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD=36` 기본값으로 36건 이하 goal/test regression에서 stale `MCP_AUTO_*` env가 up/recreate를 켜지 않게 했다.
  - [x] endpoint 자동 생성 제한 기준 `MCP_SMALL_RUN_SHARD_THRESHOLD`와 lifecycle 차단 기준을 문서에서 분리했다.
  - [x] manifest/run config에 `mcp_shard_lifecycle_block_threshold`, `mcp_run_post_count_for_lifecycle`를 추가했다.
  - [x] `py_compile` 및 `tests.test_expert_main_input_loader` 12건을 통과했다.
- 다음 작업:
  - [x] v150 live goal run manifest/log에서 36건 이하 입력이 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_run_shard_lifecycle_blocked=true`로 실행됐음을 확인했다.
  - [ ] shard 복구 자동화가 검증 대상인 run만 현재 명령에 `--allow-goal-shard-lifecycle --auto-up-shards` 또는 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 함께 명시한다.

## 2026-05-29 v149 reason/evidence-zero title guard 후속

- 상태: code patched / unit verified / live rerun pending
- 완료:
  - [x] `official_title_evidence=true` + evidence bucket 0 + 원문 anchor 없음 + verifier critical 신호 조합을 final title reject 조건으로 추가했다.
  - [x] `11718082`, `11718080`, `11718090`, `11716486`, `11718097`용 v149 targeted input을 작성했다.
  - [x] synthetic regression과 전체 agentic pipeline rework 테스트를 통과했다.
- 다음 작업:
  - [ ] LLM endpoint 복구 후 `v149_reason_evidence_zero_guard_input.jsonl`을 `--parallel 36 --reuse-shards-only`로 재실행한다.
  - [ ] 결과 manifest에서 local shard management 미진입과 completed/failed/pending을 확인한다.
  - [x] `11718097` alias recall 비단조성은 v178 title-lead alias rerun에서 targeted canary 기준 닫았다.
  - [ ] `11716486` 같은 이미지 의존 generic word 케이스는 브라우저/VLM 직접 확인 전까지 Strong evidence로 승격하지 않는다.

## 2026-05-29 goal/test run local shard management 보강 후속

- 상태: patched / unit verified / live confirmed
- 완료:
  - [x] 일반 goal/targeted run에서 local shard management 경로를 기본 비활성화했다.
  - [x] `up/recreate` 자동화뿐 아니라 `warp_shards.py status/ensure` 비용도 명시 opt-in 전에는 피하도록 했다.
  - [x] `MCP_LOCAL_SHARD_STATUS_AUDIT=1`을 status 감사 전용 escape hatch로 추가했다.
  - [x] `tests.test_expert_main_input_loader`를 12건으로 확장해 통과시켰다.
- 다음 작업:
  - [x] v150 실서버 goal run에서 manifest `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit=false`와 log grep 기준 `docker compose`, `force-recreate`, `warp_shards.py up`, `warp_shards.py recreate`, `warp_shards.py status` 호출 흔적 없음을 확인했다.
  - [ ] shard 복구 자체를 검증하는 canary에서는 `--auto-up-shards`/`--auto-recreate-shards`를 명령에 명시한다.
  - [ ] semantic gate는 이번 runtime 보강과 별개로 `REVIEW-LOCKED`를 유지한다.

## 2026-05-29 v148 후속 작업

- 상태: runtime fixed / v148 live confirmed / semantic gate REVIEW-LOCKED
- 최신 근거:
  - `expert_main.py`
  - `tests/test_expert_main_input_loader.py`
  - `qualitative_review/20260528_141006_620986/v148_partial_run_high_risk_live_review_ko.md`
  - `qualitative_review/20260528_141006_620986/v148_partial_run_high_risk_labels_ko.jsonl`
- 완료:
  - [x] reuse-only run에서 healthy endpoint만 사용하도록 endpoint pool과 parallel을 health check 뒤에 축소했다.
  - [x] v148 targeted 24건을 `--parallel 36 --reuse-shards-only`로 완료했다.
  - [x] Docker Compose lifecycle 미실행을 로그로 확인했다.
- 다음 작업:
  - [x] `11718097`의 v147/v148 차이는 title-leading alias 검색 회복 및 v178 deliberation skip으로 targeted canary 기준 닫았다.
  - [ ] `official_title_evidence=true`인데 `post_spans=0`, `search_snippets=0`, `official_urls=0`인 결과를 P0/P1 bucket으로 승격한다.
  - [ ] 영화/장르/일반 토론 글이 웹소설 title로 resolved되는 경로를 차단한다.
  - [ ] 이미지 의존 post는 브라우저/VLM 확인 없이는 Strong evidence로 승인하지 않는다.
  - [ ] expanded random baseline과 P0/P1 high-risk expansion 전까지 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 v147 weak-character preserve 차단 후속

- 상태: patched / unit verified / v147 live confirmed / semantic gate REVIEW-LOCKED
- 최신 근거:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260528_141006_620986/v147_known_bad_weak_character_preserve_block_result.json`
  - `qualitative_review/20260528_141006_620986/v147_known_bad_weak_character_preserve_block_result_manifest.json`
  - `logs/expert_run_20260529_040313_425572*.log`
- 확인/완료:
  - [x] v146에서 `11718091`이 `unresolved_matchable`이면서도 `is_relevant=true`로 다시 올라간 원인을 `unresolved_worklike_preserve`와 batch memory alias rescue로 분리했다.
  - [x] weak-character reaction guard가 preserve/rescue를 차단하도록 구현했다.
  - [x] v147에서 `11718091`은 `is_relevant=false`, `official_title=null`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`로 확인했다.
  - [x] v147에서 `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`, `11718083=unresolvable_memory_query/null`, `11718118=adjacent/null` 유지 확인.
  - [x] v147 manifest/log 기준 compose lifecycle 미실행을 확인했다.
- 다음 작업:
  - [ ] weak-character guard가 과차단을 만들지 않는지 high-risk expansion에서 `weak_character_reaction_unresolved_blocked` bucket을 별도 추적한다.
  - [ ] reason-final contradiction detector는 계속 별도 작업으로 유지한다. v147은 대표 known-bad 해결이지 10만 건 semantic approval이 아니다.
  - [ ] expanded random baseline과 P0/P1 high-risk review 전까지 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 goal/test run docker lifecycle opt-in

- 상태: patched / stale-env small-run guarded / local unit verified / v145 live goal policy confirmed
- 최신 근거:
  - `expert_main.py`
  - `tests/test_expert_main_input_loader.py`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/CHECKLIST.md`
- 확인/완료:
  - [x] 기존 정책은 10건 미만에서만 compose `up/recreate`를 기본 차단했기 때문에, 10건 이상 goal/canary 성격 테스트에서는 startup auto-manage가 docker lifecycle을 실행할 수 있었다.
  - [x] `expert_main.py`의 docker lifecycle 기본값을 입력 건수와 무관하게 opt-in으로 바꿨다.
  - [x] `--auto-up-shards`, `--auto-recreate-shards`를 추가했다.
  - [x] 기존 env override `MCP_AUTO_UP_SHARDS=1`, `MCP_AUTO_RECREATE_SHARDS=1`는 v171 이후 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` ack 없이는 lifecycle을 열지 않는 방식으로 좁혔다.
  - [x] `MCP_SMALL_RUN_SHARD_THRESHOLD` 미만 goal/targeted run은 stale `MCP_AUTO_UP_SHARDS=1`, `MCP_AUTO_RECREATE_SHARDS=1`이 남아 있어도 자동 `up/recreate`와 compose 기반 shard ensure를 켜지 않도록 했다.
  - [x] 소규모 run에서 복구 자동화가 진짜 검증 대상이면 현재 명령에 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`를 함께 붙이도록 했다.
  - [x] `--reuse-shards-only`는 CLI/env opt-in보다 우선하도록 테스트를 추가했다.
  - [x] manifest/run config에 `mcp_small_run_shard_lifecycle_blocked`를 추가했다.
- 다음 작업:
  - [x] `py_compile`과 `tests.test_expert_main_input_loader`를 통과시킨다.
  - [x] `expert_main.py --help`에서 신규 opt-in 옵션 노출을 확인한다.
  - [x] v141 goal live run manifest/log에서 compose lifecycle 미실행을 확인한다.
  - [x] v145 known-bad goal run을 `--reuse-shards-only --parallel 36`으로 재실행해 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`과 compose lifecycle 미실행을 확인한다.

## 2026-05-28 소규모 goal/targeted run shard 재사용 정책

- 상태: runtime policy patched / compile verified / v138 live-log confirmed / v139 manifest policy confirmed
- 최신 근거:
  - `expert_main.py`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
  - `logs/expert_run_20260529_005903_511505.log`
  - `qualitative_review/20260528_141006_620986/v138_known_bad_alias_lock_character_page_result_manifest.json`
  - `logs/expert_run_20260529_012138_862062.log`
  - `qualitative_review/20260528_141006_620986/v139_known_bad_weak_character_banter_guard_result_manifest.json`
- 확인/완료:
  - [x] `--parallel 36`은 상한이며 소규모 입력에서는 `effective_parallel=input_post_count`로 줄어드는 정책을 유지했다.
  - [x] 10건 미만 targeted/goal run에서 기본적으로 `docker compose up`과 shard `force-recreate`를 자동 실행하지 않도록 했다.
  - [x] 필요 시 CLI `--auto-up-shards`/`--auto-recreate-shards` 또는 env `MCP_AUTO_*` + `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` + `MCP_HEALTH_ATTEMPTS`로 override할 수 있게 했다.
  - [x] 명령 단위 옵션 `--no-auto-recreate-shards`, `--reuse-shards-only`를 추가했다.
  - [x] `py_compile expert_main.py`와 `expert_main.py --help`를 통과했다.
  - [x] v138 run id `20260529_005903_511505`: `requested_parallel=36`, `input_post_count=5`, `effective_parallel=5`, `completed/failed/pending=5/0/0`.
  - [x] v138 startup log 기준 기존 healthy shard 2개를 재사용했고 `docker compose`/`force-recreate` 없이 WARP/health check가 attempt `1/1`로 종료됐다.
  - [x] v139 run id `20260529_012138_862062`: `requested_parallel=36`, `input_post_count=5`, `effective_parallel=5`, `completed/failed/pending=5/0/0`.
  - [x] v139 manifest 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_targeted_run=true`를 확인했다.
  - [x] v139 startup log에서도 health attempt `1/1`이며 `docker compose`/`force-recreate` 실행 흔적이 없음을 확인했다.
- 다음 작업:
  - [x] v138 이후 추가된 manifest 필드 기준으로 다음 1~9건 live targeted run에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_targeted_run=true`를 확인한다.
  - [ ] goal 테스트런에서 compose 재시작을 절대 피해야 하는 경우 명령에 `--reuse-shards-only`를 붙인다.
  - [ ] canary/validation에서는 필요한 경우 CLI `--auto-up-shards`/`--auto-recreate-shards`를 명시한다. env 자동화는 `MCP_AUTO_*`와 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 둔다.

## 2026-05-28 v134 전문가 오케스트레이션/프롬프트 한계 감사

- 상태: 구조 감사 문서화 / schema 분리 1차 구현 및 단위 검증 완료 / semantic gate `REVIEW-LOCKED`
- 최신 근거:
  - `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`
  - `docs/devs/LLM_JUDGMENT_REVIEW.md`
  - `src/llm_batch/models.py`
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/prompts/prompt_router.py`
  - `src/llm_batch/experts/arbiter.py`
- 확인/완료:
  - [x] 오케스트레이션 한계를 LLM 자연어 이해, 작품 identity, 후처리/구조 보정, 리뷰/승인 책임으로 분리했다.
  - [x] `PickvelIdentity`가 `topicality/work_resolution/identity_state`만으로는 소설 관련성과 단일 작품 매칭 가능성을 분리하기 어렵다는 한계를 확인했다.
  - [x] `PickvelIdentity`에 `is_novel_related`, `is_resolved_work_discussion`, `title_resolution_state`, `title_resolution_allowed`를 backward-compatible optional field로 추가했다.
  - [x] `_context_to_output()`에서 범위 분리 필드를 산출하고, 필요한 경우 reason에 `[범위 분리]` 공개 섹션을 붙이도록 했다.
  - [x] `prompt_router.py`는 기억 회수/제목 찾기에서 소설 관련성과 단일 작품 매칭 가능성을 분리하라고 지시하지만, 최종 schema가 이 분리를 공개 필드로 고정하지 못하는 한 reason/final 혼선이 남을 수 있음을 기록했다.
  - [x] `arbiter.py`의 "최종 결론을 지금 내려야 한다" 계열 지시와 `null/HOLD/unresolved` 허용 계약이 작은 모델에서 충돌할 수 있음을 기록했다.
  - [x] `_context_to_output()` 후처리 rescue/demotion 경로가 프롬프트 판단을 다시 뒤집을 수 있으므로 prompt-only fix는 충분하지 않음을 기록했다.
- 다음 작업:
  - [x] `11718091` synthetic context 기준으로 "소설 관련 가능성 있음"과 "단일 작품 매칭 불가"가 동시에 표현되는지 단위 검증했다.
  - [x] `11718083` memory-query/no-anchor synthetic context 기준으로 `unresolvable_memory_query`와 `title_resolution_allowed=false`가 표현되는지 단위 검증했다.
  - [ ] `title_lock_state`와 `evidence_edges`를 후처리 단계 간 공유하고 review packet에 공개하는 설계를 진행한다.
  - [ ] reason-final contradiction detector를 `reason_decision_contradiction` bucket과 action queue에 직접 연결한다.
  - [ ] 프롬프트는 예시/장문 설명보다 출력 계약, hard veto, null/HOLD 정상성 중심으로 축소하는 방향을 검토한다.
  - [x] v145 live LLM targeted rerun에서 `11718091`의 새 공개 필드가 result JSON에 남는지 확인했다.
  - [ ] reason-final contradiction detector 구현 전까지 `11718091`류는 `ACCEPT`가 아니라 `HOLD/docs_issue`로 유지한다.

## 2026-05-28 v133 이후 작업

- 상태: metadata-preserved known-bad rerun 완료 / targeted 핵심 오판 재발 없음 / semantic gate `REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260528_141006_620986/v133_known_bad_metadata_preserved_manifest.json`
  - `qualitative_review/20260528_141006_620986/v133_known_bad_metadata_preserved_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v133_known_bad_metadata_preserved_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v133_known_bad_metadata_preserved_after_review_labels.jsonl`
  - `logs/expert_run_20260528_225755_175469.log`
  - `tests/test_expert_main_input_loader.py`
- 확인/완료:
  - [x] known-bad 5건 입력에 댓글 메타를 포함했다.
  - [x] v133 run id `20260528_225755_175469`: `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`.
  - [x] `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 회복됐다.
  - [x] `11718083`과 `11718118`은 null-title을 유지했다.
  - [x] `11718097` 결과 내부 `comment_metadata` 5건이 보존됐다.
  - [x] 소규모 targeted run에서 자동 shard 생성 과다를 줄이도록 기본 2 shard 제한과 healthy shard 재사용을 추가했다.
- 다음 작업:
  - [x] `11718091`의 `noise/review/관련/비관련` reason 혼선을 schema 분리 이슈로 추적하고 1차 optional field를 추가했다.
  - [x] `is_novel_related`, `is_resolved_work_discussion`, `title_resolution_state` 분리 설계를 1차 구현했다.
  - [ ] `11718091` reason 혼선 자체는 reason-final contradiction detector로 별도 보정한다.
  - [ ] random baseline 1,000건과 P0/P1 high-risk expansion 전까지 10만 건 semantic `GO` 금지.
  - [ ] 다음 1~9건 targeted run에서는 기본 shard 2개 제한 로그와 healthy reuse 로그가 실제로 찍히는지 확인한다.

## 2026-05-28 v132 이후 작업

- 상태: context metadata carrier 보강 완료 / v131 title canary와 dialogue-context approval 분리 / semantic gate `REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260528_141006_620986/v132_orchestration_prompt_limit_context_audit_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v132_topic_particle_title_lead_alias_review_context_audit_manifest.json`
  - `qualitative_review/20260528_141006_620986/v132_topic_particle_title_lead_alias_review_context_audit_packets.jsonl`
  - `tests/test_expert_main_input_loader.py`
- 확인/완료:
  - [x] v132 context audit에서 현재 `out/expert_result_20260528_141006_620986*` 기반 packet은 `11718097`, `11718118`의 `gallery_id`와 `comment_metadata`를 복구하지 못함을 확인했다.
  - [x] `expert_main.py` loader가 입력 `comment_metadata`를 문자열 댓글에 재부착하도록 보강했다.
  - [x] review/targeted input builder들이 원본 row에 존재하는 대화 메타를 다음 산출물로 전달하도록 보강했다.
- 다음 작업:
- [x] 원본 crawl/input 또는 checkpoint 중 실제 `comment_id`/`author`/`ip`가 살아있는 source를 찾아 known-bad 5건 targeted input을 재작성했다. 상세는 v133 섹션을 본다.
- [x] 재작성 입력으로 Gemma 4 4B `expert_main.py --parallel 36` 상한 run을 수행했고, `effective_parallel=5`로 확인했다.
  - [ ] v131 `ACCEPT`는 title-lock canary로만 유지하고, dialogue-context 검증은 새 metadata-preserved run 전까지 `INFO_MISSING / REVIEW-LOCKED`로 둔다.

## 2026-05-28 v125-v131 이후 작업

- 상태: 후단 오케스트레이션 한계 재확인 / `11718118` false positive targeted fixed / `11718097` correct-title recall targeted fixed / semantic gate `REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260528_141006_620986/v125_topic_particle_title_lead_alias_review_summary_ko.md`
  - `qualitative_review/20260528_141006_620986/v126_topic_particle_reject_2_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v127_topic_particle_reject_2_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v128_topic_particle_reject_2_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_after_review_labels.jsonl`
  - `logs/expert_run_20260528_212656_149981_W0.log`
  - `logs/expert_run_20260528_214738_593132_W0.log`
  - `logs/expert_run_20260528_214738_593132_W1.log`
  - `logs/expert_run_20260528_222656_377121_W0.log`
  - `logs/expert_run_20260528_222656_377121_W1.log`
  - `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`
- 확인/완료:
  - [x] v125 bucket triage에서 `topic_particle_title_lead_alias_anchor` 후보 7건 중 `11718097`, `11718118`을 `REJECT/re_judge`로 분리했다.
  - [x] v126 run id `20260528_212656_149981`에서 `11718097`이 중간 전문가 판단으로는 `망겜의 힐러`였으나 후단 보정으로 `게임4판타지`가 final title이 되는 것을 확인했다.
  - [x] v127 run id `20260528_213847_152176`에서 `11718118`이 장르 일반론임에도 `장르소설 마이너 갤러리/밈`으로 rescue되는 것을 확인했다.
  - [x] v128 run id `20260528_214738_593132`: `requested_parallel=36`, `effective_parallel=2`, `completed/failed/pending=2/0/0`.
  - [x] v128에서 `11718118`은 `official_title=null`, `is_relevant=false`, `discussion_type=trope_discussion`, `work_resolution=none`, `anchor_type=genre`로 회복됐다.
  - [x] v128에서 `11718097`은 wrong title 확정은 제거됐지만 `official_title=null`, `is_relevant=true`, `work_resolution=unresolved`, `anchor_type=author`로 남았다.
  - [x] v129에서 `11718097` final은 회복됐지만 canonical suspect 단계가 여전히 `오크 행복`으로 흔들리는 것을 확인했다.
  - [x] v130에서 작가앵커-후보작가 충돌 guard가 locked title을 삭제해 `11718097`이 `HOLD/unresolved`로 회귀하는 것을 확인했다.
  - [x] v131 run id `20260528_222656_377121`: `requested_parallel=36`, `effective_parallel=2`, `completed/failed/pending=2/0/0`.
  - [x] v131 after-review에서 `11718097`, `11718118` 모두 `ACCEPT/no_action`으로 닫았다.
- 다음 작업:
  - [x] `11718097`의 remaining HOLD를 닫기 위해 canonical suspect 보정이 snippet canonical alias lock을 깨지 못하게 했다.
  - [x] `unverified alias/plot title 보류`가 snippet alias lock + title lead alias span + filtered official detail을 잃어버리는 조건을 보정했다.
  - [x] filtered official detail(`token_mismatch:official`)을 snippet/alias lock과 같은 후보일 때 `weak_support`로 고려하도록 정책화했다.
  - [ ] author-name search inference(`검미성`)는 특정 작품 final rescue가 아니라 author/work-family context로만 쓰게 schema를 분리한다.
  - [ ] genre/trope discourse(`ts물`, `대협`)에서는 wiki/community 문서 title rescue를 hard-block하는 회귀를 high-risk expansion에 추가한다.
  - [ ] `post_arbiter_lock_preserved`, `author_anchor_conflict_guard_skip`, `filtered_official_weak_support`를 high-risk expansion bucket에 추가한다.
  - [ ] v125-v131은 targeted/bucket 검증이므로 random baseline `1000+`와 P0/P1 high-risk expansion 전까지 10만 건 semantic `GO` 금지.

## 2026-05-28 v124 이후 작업

- 상태: title-leading alias recall 보강 완료 / v124 targeted canary `ACCEPT=4` / semantic gate `REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v124_title_lead_alias_recall_action_queue_ko_20260528.md`
- 확인/완료:
  - [x] 실행 전 기존 Python 점유 프로세스가 없음을 확인했다.
  - [x] `망겜힐은`처럼 제목 첫 토큰에 조사가 붙은 clean alias를 검색 앵커로 보존하도록 보강했다.
  - [x] 특정 작품명 하드코딩 없이 generic topic, role/species, low-information alias 필터를 유지했다.
  - [x] focused 4 tests와 `tests.test_agentic_pipeline_rework` 전체 `271`건을 통과했다.
  - [x] v124 targeted 4건 실서버 재실행에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`을 확인했다.
  - [x] v124 after-review에서 `11718097` correct title recall이 `ACCEPT/no_action`으로 닫혔다.
- 다음 작업:
  - [ ] `topic_particle_title_lead_alias_anchor`를 high-risk expansion bucket에 추가하고 false positive 증가 여부를 확인한다.
  - [ ] 검색 degraded가 남은 `11718097`, `11718099`류는 대형 표본에서 evidence strength를 별도 집계한다.
  - [ ] role/honorific alias guard는 expanded high-risk sample에서 최소 P1 bucket 규모로 재검증한다.
  - [ ] v124는 targeted canary이므로 random baseline `1000+`와 P0/P1 high-risk expansion 전까지 10만 건 semantic `GO` 금지.

## 2026-05-28 v122/v123 이후 작업

- 상태: 후처리 `post_data` 오류 수정 완료 / 역할·호칭성 search-inferred alias rescue 차단 확인 / targeted canary `ACCEPT=3`, `HOLD=1` / semantic gate `REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260528_141006_620986/v122_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v122_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_result_manifest.json`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v123_role_honorific_alias_rescue_action_queue_ko_20260528.md`
- 확인/완료:
  - [x] v122에서 `11718083`, `11718091`의 `_context_to_output()` `post_data` NameError를 `REPROCESS/re_run`으로 분리했다.
  - [x] v122에서 `11718097`이 `족장님 -> 두 번 각성하는 대족장님`으로 후단 rescue된 것을 역할·호칭성 alias 오삽입 `REJECT`로 분리했다.
  - [x] `post_data` 참조를 `ctx.post_data` 기반으로 수정했다.
  - [x] `search_evidence_alias_inference` 경로에서 역할·호칭성 alias가 단독으로 batch memory title rescue를 만들지 못하게 일반 guard를 추가했다.
  - [x] focused 4건과 `tests.test_agentic_pipeline_rework` 전체 269건을 통과했다.
  - [x] v123 targeted 4건 실서버 재실행에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`을 확인했다.
  - [x] v123 after-review에서 `ACCEPT=3`, `HOLD=1`, `REPROCESS=0`, `REJECT=0`으로 처리 오류와 wrong-title rescue 재발이 없음을 확인했다.
- 다음 작업:
  - [ ] `11718097` correct title recall은 `HOLD/re_search`로 남아 있으므로 검색 evidence edge를 보강한다.
  - [ ] canonical suspect 단계에서 역할·호칭 후보가 생성되는 노이즈를 `role_or_honorific_alias_rescue_blocked` high-risk bucket으로 수집한다.
  - [ ] role/honorific alias guard를 expanded high-risk sample에서 최소 P1 bucket 규모로 재검증한다.
  - [ ] v123은 targeted canary이므로 random baseline `1000+`와 P0/P1 high-risk expansion 전까지 10만 건 semantic `GO` 금지.

## 2026-05-28 v117 이후 작업

- 상태: 부분 런 semantic over-resolution guard 보정 완료 / comment author context 보존 완료 / live targeted rerun 완료 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260528_141006_620986/v117_partial_run_semantic_issue_review_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v117_partial_run_semantic_issue_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v117_partial_run_action_queue_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v117_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v117_targeted_4_after_review_labels.jsonl`
- 확인/완료:
  - [x] `20260528_141006_620986`이 10만 건 전체 완료가 아니라 `completed=80`, `flushed=71`, `pending=9`인 부분 산출물임을 분리 기록했다.
  - [x] `11718083`, `11718099`, `11718091`, `11718097` 네 건을 `REJECT` label로 정리했다.
  - [x] platform/community label 및 meta action/status headline을 작품명 승격에서 차단했다.
  - [x] post `gallery_id`/`post_author`와 comment `comment_id`/`author`/`ip`/reply 메타를 결과 및 prompt context에 분리 보존했다.
  - [x] py_compile 및 focused comment author/IP context 테스트를 통과했다.
  - [x] 4건 targeted rerun `20260528_153350_626964`을 완료했다.
  - [x] `11718097`, `11718099`는 after-review `ACCEPT`로 회복됐다.
  - [x] v119 after-review를 추가 작성했다. 결과는 `ACCEPT=1`, `HOLD=2`, `REJECT=1`이며 `11718083` memory-query 과확정이 계속 남은 것을 확인했다.
  - [x] v121 단건 canary에서 `11718083`은 `official_title=null`, `novel_identity=null`, `work_resolution=none`, `anchor_type=none`으로 내려갔다.
  - [x] `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`에 전문가 오케스트레이션/프롬프트 한계와 hard veto 개선 방향을 정리했다.
  - [x] prompt router에 memory-query/no-direct-anchor official_title null 규칙과 comment metadata 사용 경계를 추가했다.
- 다음 작업:
  - [x] targeted rerun manifest에서 `effective_parallel=min(input_post_count,36)`을 확인한다.
  - [x] rerun 결과 row에 `gallery_id`, `post_author`, `comment_metadata`가 보존되는지 확인한다.
  - [x] rerun 후 `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING` label을 새로 작성한다.
  - [x] `11718083` quote-search overresolve는 v121 단건 canary final output 기준으로 보정 확인했다.
  - [ ] `11718083` memory-query/no-anchor hard veto를 high-risk bucket으로 확대 검증한다.
  - [ ] `11718091` generic phrase alias overresolve는 title 제거까지 확인됐지만, reason/final 충돌과 unresolved preserve audit noise를 추가 보정/재검증한다.
  - [ ] `11718097` correct title recall을 `re_search`/`re_judge`로 닫는다.
  - [ ] 71-row 위험 스캔의 `critical/search_only/official_false/official_urls_0` 교집합을 추가 targeted queue로 확장한다.
  - [ ] expanded random baseline과 P0/P1 high-risk expansion 전까지 10만 건 semantic `GO` 금지.

## 2026-05-28 v115/v116 이후 작업

- 상태: alias common-word pollution targeted fix 완료 / v116 단건 복구 확인 / semantic gate `REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_review_summary_ko_20260528.md`
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_action_queue_ko_20260528.md`
  - `qualitative_review/20260505_214349_324347/v116_post11365197_alias_commonword_guard_p36max_20260528_manifest.json`
- 확인/완료:
  - [x] `애들 -> 잘못된 권유` 오염이 v115에서 제거되는 것을 확인했다.
  - [x] v115에서 새로 드러난 `성이 -> 실패 없는 웹소설 작법서 by 윤재 저` 오염을 일반 규칙으로 차단했다.
  - [x] v116 단건에서 `전1시 -> 전지적 1인칭 시점` 복구를 확인했다.
  - [x] 새 특정 작품명/URL 하드코딩 없이 alias inference와 검색 title 후보 필터를 보정했다.
  - [x] 회귀 `298`건을 통과했다.
- 다음 작업:
  - [ ] v115/v116 shell exit code `1`과 manifest success 불일치를 조사한다.
  - [ ] `탑매`는 검색 degraded/zero-result 구간을 분리해 `re_search`한다.
  - [ ] `아집숨`은 alias+character 질문이 noise로 내려가는 조건을 `re_judge`한다.
  - [ ] `괴출`은 작품 주변 담론과 author/meta 충돌을 `re_search`/`re_judge`한다.
  - [ ] `성녀속마음`은 title은 맞지만 subtype이 author_talk로 남는 문제를 `re_judge`한다.
  - [ ] random baseline 확대와 P0/P1 high-risk expanded review 전까지 10만 건 semantic `GO` 금지.

## 2026-05-27 v108/v109 이후 작업

- 상태: v105 `REJECT/re_judge` 7건 alias recall 보강 / v108 p7 재실행 완료 / v109 after-review `ACCEPT=4`, `HOLD=3`, `REJECT=0` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v109_v105_reject_closure_after_review_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v109_v105_reject_closure_after_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_alias_recall_patch_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_rejudge_targeted_manifest.json`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_rejudge_targeted_input.jsonl`
- 확인/완료:
  - [x] 7건 targeted input count와 missing count `0`을 확인했다.
  - [x] `expert_main.py` adaptive parallel helper에서 7건 입력은 effective `7`로 낮아지는 것을 확인했다.
  - [x] 관련 로컬 회귀 `243`건 + `42`건을 통과했다.
  - [x] LLM endpoint와 search shard `36/36`을 재확인했다.
  - [x] v108 7건을 `--parallel 7`로 실서버 재실행했다.
  - [x] manifest에서 `requested_parallel=7`, `effective_parallel=7`, `input_post_count=7`을 확인했다.
  - [x] v109 단건 guard를 `--parallel 1`로 재실행하고 `effective_parallel=1`을 확인했다.
  - [x] after-review labels를 생성하고 `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING` 분포를 보고했다.
- 다음 작업:
  - [ ] `탑매` HOLD는 evidence catalog 보강을 위해 `re_search`한다.
  - [ ] `괴담텔` HOLD는 final identity/multi_work 상태를 `re_judge`한다.
  - [ ] `괴출` HOLD는 공식/직접 제목 근거를 `re_search`한다.
  - [ ] HOLD 3건과 기존 10만 건 remaining queue가 닫히기 전까지 semantic `GO` 금지.

## 2026-05-27 v105 이후 작업

- 상태: v98/v102 실서버 재실행 완료 / after-review 결과 `ACCEPT=16`, `HOLD=9`, `REJECT=7` / adaptive parallel 정책 정정 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v105_targeted_after_review_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v105_targeted_after_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v106_adaptive_parallel_policy_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v107_effective_parallel_runtime_guard_ko_20260527.md`
- 확인/완료:
  - [x] 실제 endpoint `http://10.20.0.101:8000`과 model `bg-digitalservices/Gemma-4-E4B-it-NVFP4`를 확인했다.
  - [x] v98 7건과 v102 25건을 실서버로 재실행했다.
  - [x] after-review label `32`건을 생성했다.
  - [x] 소규모 targeted run의 병렬도 정책을 `effective_parallel=min(requested_parallel,input_count)`로 정정했다.
  - [x] `expert_main.py` 런타임에서 `--parallel`을 상한으로 처리하고 실제 post 수보다 큰 워커 생성을 막았다.
  - [x] 후속 v108/v109 closure에서 v105 `REJECT=7`을 `REJECT=0`으로 낮췄다.
- 다음 작업:
  - [ ] 후속 closure에서 남은 `탑매`, `괴담텔`, `괴출` HOLD 3건을 닫는다.
  - [ ] `HOLD` 9건은 `human_review`와 `slang_db_review`로 분리해 닫는다.
  - [x] 다음 36건 미만 targeted run manifest에서 `requested_parallel`과 `effective_parallel`이 분리 기록되는지 확인했다.
  - [ ] 남은 `HOLD`와 기존 10만 건 remaining queue closure 전까지 semantic `GO` 금지.

## 2026-05-27 v104 이후 작업

- 상태: search shard `36/36` 정상 / LLM endpoint down / 로컬 회귀 통과 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v104_runtime_preflight_and_local_regression_ko_20260527.md`
  - `out/search_shard_audit_20260527_185927.json`
  - `qualitative_review/20260505_214349_324347/v102_clean_alias_preservation_targeted_manifest.json`
- 확인/완료:
  - [x] `http://127.0.0.1:8000/v1/models` 연결 실패를 재확인했다.
  - [x] `:8000` listener가 없음을 확인했다.
  - [x] search shard audit `ok=36/36`, `bad=[]`를 확인했다.
  - [x] 핵심 회귀 `74`건과 agentic pipeline rework `239`건을 통과했다.
- 다음 작업:
  - [x] LLM endpoint 후보를 `127.0.0.1`, `localhost`, `10.20.0.101`로 확인했고, 실제 endpoint는 `http://10.20.0.101:8000`임을 확인했다.
  - [x] v98 7건과 v102 25건은 이미 `--parallel 36`으로 재실행됐지만, 소규모 targeted run에 36 고정은 비효율로 확인했다.
  - [x] 이후 소규모 targeted run은 `--parallel 36`이 들어와도 실제 워커가 입력 수로 자동 축소된다. 36은 상한으로만 사용한다.
  - [x] v108/v109 result/checkpoint/log/manifest와 after-review label을 생성했다.
  - [ ] 남은 `HOLD`와 기존 10만 건 remaining queue closure 전까지 semantic `GO` 금지.

## 2026-05-27 v102 이후 작업

- 상태: clean alias preservation 계약/프롬프트 보강 완료 / 로컬 회귀 통과 / 실서버 재실행 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v102_clean_alias_preservation_contract_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v102_clean_alias_preservation_targeted_manifest.json`
  - `qualitative_review/20260505_214349_324347/v103_current_100k_remaining_gap_bug_resolution_plan_ko_20260527.md`
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/prompts/prompt_router.py`
  - `src/llm_batch/prompts/expert_prompts.py`
  - `tests/test_agentic_pipeline_alias_contract.py`
- 확인/완료:
  - [x] noisy/composite surface에서는 phrase 저장을 막고 clean alias 후보를 `canonical_work_alias`로 보존하도록 계약을 보강했다.
  - [x] `탑매/탑 매니지먼트`, `탑매`, `환암검천 후기` 회귀 테스트를 추가했다.
  - [x] alias contract `33`건, 관련 회귀 `38`건, agentic pipeline rework `239`건을 통과했다.
  - [x] v101 blocked contract spot review `25`건을 v102 targeted input으로 생성했고 `missing_count=0`을 확인했다.
  - [x] 10만 건 현재 부족점/버그/해결 가능 항목을 v103 summary로 분리 정리했다.
- 다음 작업:
  - [x] v98 7건과 v102 25건은 Gemma 4 4B, `MCP_SHARD_COUNT=36`, `--no-auto-up-shards` 조건으로 실서버 재실행했다.
  - [x] v98/v102 result packet을 after-review하고, clean alias 보존 후속 이슈를 v105/v108/v109 closure로 분리했다.
  - [x] 다음 소규모 targeted run부터는 명령값을 수동으로 줄이는 대신 manifest의 `effective_parallel=input_post_count`를 검증한다.
  - [ ] post-fix random baseline과 P0/P1 high-risk regression 전까지 semantic `GO` 금지.

## 2026-05-27 v101 이후 작업

- 상태: `blocked_by_result_contract=79` 중 25건 spot review 완료 / 과차단 패턴 확인 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v101_blocked_contract_spot_review_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v101_blocked_contract_spot_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v101_blocked_contract_spot_review_action_queue.md`
- 확인/완료:
  - [x] `blocked_by_result_contract=79` 중 25건을 store_reason/alias_scope/relevance 기준으로 과표집했다.
  - [x] 라벨은 `ACCEPT=6`, `HOLD=5`, `REJECT=14`로 확인했다.
  - [x] `sentence_like_alias_surface`, `pure_work_alias`, `exact_title_not_alias`에 과차단/추출 누락 패턴이 섞여 있음을 확인했다.
- 다음 작업:
  - [ ] `sentence_like_alias_surface`는 noisy phrase와 clean alias를 같은 결론으로 묶지 않고 분리 저장/차단한다.
  - [ ] `pure_work_alias`가 `blocked_by_result_contract`에 남은 row는 alias candidate pool로 보존하거나 re-judge queue로 보낸다.
  - [ ] `exact_title_not_alias`는 exact title 차단과 short alias 추출 누락을 분리한다.
  - [ ] 이 보강 전에는 `slang_db_review=87`을 닫거나 semantic `GO`로 올리지 않는다.

## 2026-05-27 v100 이후 작업

- 상태: slang DB 소량 상태 8건 수동 리뷰 완료 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v100_slang_db_small_state_manual_review_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v100_slang_db_small_state_manual_review_labels.jsonl`
- 확인/완료:
  - [x] `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2` 총 8건을 자연어로 판독했다.
  - [x] `프리렌`, `시달소`는 외부 매체 seed라 `REJECT/quarantine` 후보로 분류했다.
  - [x] `탐태창`, `회맹생`, `시천살`, `반로환동전`은 정상 웹소설 alias 후보로 분류했다.
  - [x] `검머외`, `말하는검`은 relevance/canonical 충돌 때문에 `HOLD`로 유지했다.
- 다음 작업:
  - [ ] v98 7건 실서버 재실행 결과와 v100 수동 리뷰를 대조한다.
  - [ ] DB 반영 전 source DB의 saved/pending/conflict bucket을 별도 확인한다.
- [x] `blocked_by_result_contract=79`는 v101에서 25건 spot review로 차단 사유와 recall 영향의 대표 패턴을 확인했다.

## 2026-05-27 v99 이후 작업

- 상태: current slang DB 상태별 큐 재생성 / 도구 packet id 추적성 보정 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v99_current_slang_db_status_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/v99_current_slang_db_status_review_action_queue.md`
  - `tools/build_slang_db_status_review.py`
- 확인/완료:
  - [x] 최신 current `slang_db_review=87`을 상태별로 다시 분리했다.
  - [x] 분포는 `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`다.
  - [x] 상태별 followup action을 `confirm_block_reason_and_recall_impact`, `verify_saved_alias_not_pollution`, `resolve_conflicting_alias`, `confirm_pending_or_promote`로 나눴다.
  - [x] `build_slang_db_status_review.py`의 packet id prefix 고정 버그를 수정했다.
  - [x] 관련 단건 테스트와 38개 회귀 테스트를 통과했다.
- 다음 작업:
  - [ ] `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`는 소량이므로 우선 자연어 리뷰로 확정한다.
  - [x] `blocked_by_result_contract=79`는 v101에서 차단 사유가 `exact_title_not_alias`, `sentence_like_alias_surface`, `pure_work_alias` 등으로 맞게 분기됐는지 spot review했다.
  - [ ] v99 상태별 큐를 닫기 전에는 `slang_db_review=87`을 승인 완료로 표시하지 않는다.

## 2026-05-27 v98 이후 작업

- 상태: targeted input 준비 완료 / LLM endpoint 미기동 또는 포트 불일치 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v98_non_novel_slang_seed_quarantine_targeted_manifest.json`
  - `qualitative_review/20260505_214349_324347/v98_non_novel_slang_seed_quarantine_targeted_input.jsonl`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/v98_11097334_current_image_loading_probe_20260527.json`
- 확인/완료:
  - [x] v97 non-novel slang seed quarantine 회귀 확인용 targeted input `7`건을 준비했다.
  - [x] negative control `3`건과 positive webnovel alias control `4`건을 같이 넣었다.
  - [x] `2026-05-27T17:54:24+09:00` 기준 LLM endpoint 연결 실패와 관련 Python 점유 프로세스 없음 상태를 확인했다.
  - [x] `post_id=11097334` 현재 iab 재확인에서 placeholder가 `complete=true/naturalWidth>0`으로 보이는 함정을 다시 확인했다.
- 다음 작업:
  - [x] v105에서 Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `--no-auto-up-shards` 조건으로 v98 `7`건을 재실행했다. 후속 7건 재확인은 `--parallel 7`로 실행한다.
  - [ ] v98 result/checkpoint/manifest/log를 after-review packet/label로 닫는다.
  - [ ] v98 negative control이 `resolved_title=null` 또는 non-relevant로 유지되는지, positive control이 alias recall을 유지하는지 확인한다.
  - [ ] VLM/OCR image gate는 `img.complete`가 아니라 `placeholder_current_src_count=0`, `data_original_pending_count=0` 기준으로 닫는다.

## 2026-05-27 v97 이후 작업

- 상태: non-novel slang seed quarantine 보강 / 실서버 재실행 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v97_non_novel_slang_seed_quarantine_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v86_slang_db_status_review_after_conflict_detection_packets.jsonl`
- 확인/완료:
  - [x] `post_id=9687991` `프리렌 -> 장송의 프리렌` 저장 seed를 known-bad non-novel media alias seed로 확인했다.
  - [x] `post_id=11097307` `시달소 -> 시간을 달리는 소녀` conflict seed를 known-bad non-novel media alias seed로 확인했다.
  - [x] `BatchContextMemory`에서 두 seed가 structured slang support가 있어도 pending/resolved memory로 승격되지 않도록 차단했다.
  - [x] `tests.test_batch_context` 9건, `tests.test_agentic_pipeline_rework tests.test_batch_context` 248건 통과.
- 다음 작업:
  - [ ] LLM endpoint 복구 후 Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `--no-auto-up-shards`로 targeted rerun을 수행하되, `--parallel 36`은 상한으로 두고 manifest의 `effective_parallel`을 확인한다.
  - [ ] `slang_db_review=87` 중 `persisted_conflict=3`, `persisted_pending=2`, `persisted_as_slang=3`을 상태별로 닫는다.
  - [x] `blocked_by_result_contract=79`는 v101에서 차단 사유와 alias recall 영향만 spot review했다.
  - [ ] `human_review=122`, `INFO_MISSING=1`을 닫기 전 semantic `GO` 금지.

## 2026-05-27 v96 이후 작업

- 상태: VLM/OCR 첨부 팝업 evidence 보강으로 `INFO_MISSING=1` / approval excluded `209` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v96_info_missing_attachment_popup_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v96_info_missing_attachment_popup_after_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 확인/완료:
  - [x] `post_id=10794867`은 본문 인라인 이미지 `0`개였지만 `viewimagePop.php` 첨부 이미지가 로드되는 것을 확인했다.
  - [x] 첨부 이미지는 갤러리 소개 이미지라 작품 직접 근거가 아니므로 `INFO_MISSING -> HOLD/human_review`로 재분류했다.
  - [x] `post_id=10892069`은 삭제/리다이렉트 상태라 `INFO_MISSING/human_review` 유지가 맞다고 확인했다.
  - [x] latest closure에서 `ACCEPT=375`, `HOLD=208`, `INFO_MISSING=1`, browser image gate `pass=99`, `fail=1`을 확인했다.
- 다음 작업:
  - [ ] 남은 `INFO_MISSING=1` (`10892069`)은 삭제/리다이렉트로 인한 irrecoverable evidence인지, 원본 source image URL 복구 가능성이 있는지 별도 확인한다.
  - [ ] `human_review=122`를 packet별 자연어 리뷰로 닫는다.
  - [ ] `slang_db_review=87`은 저장 차단/충돌/pending/family alias 상태별로 닫는다.
  - [ ] VLM/OCR image gate와 post-fix random/P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v95 이후 작업

- 상태: structured evidence catalog 라벨러 보정으로 `re_search=0` / approval excluded `209` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v95_catalog_evidence_relabel_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v95_re_search1_catalog_evidence_after_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 확인/완료:
  - [x] `9803986`의 `search_evidence_catalog`에 문피아/작품 근거가 있는데 stale `official_urls=0` reason counter 때문에 `REPROCESS`가 유지되던 라벨러 문제를 수정했다.
  - [x] v95 after-review에서 `9803986`을 `ACCEPT/no_action`으로 전환했다.
  - [x] 최신 closure에서 `re_search=0`, `ACCEPT=375`, approval excluded `209`를 확인했다.
- 다음 작업:
  - [ ] `human_review=122`를 packet별 자연어 리뷰로 닫는다.
  - [ ] `slang_db_review=87`은 저장 차단/충돌/pending/family alias 상태별로 닫는다.
  - [x] `INFO_MISSING=2` 중 `10794867`은 v96 attachment popup review로 `HOLD` 전환했고, `10892069`만 남았다.
  - [ ] VLM/OCR image gate와 post-fix random/P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v94 이후 작업

- 상태: broad topic/comment composite 과잉 확정 보정 및 잔여 `re_search=3` 재검토 완료 / approval excluded `210` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v94_broad_topic_comment_conflict_guard_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v94_re_search3_broad_topic_comment_conflict_guard_after_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 확인/완료:
  - [x] `10529582`의 `삼국지 떡밥` broad topic + 캐릭터 댓글이 `삼국지 태사자`로 승격되는 경로를 차단했다.
  - [x] `10870841`의 `괴담동?` 본문 추측 alias가 `악엔/악역의 엔딩은` 댓글 답변과 충돌할 때 title 확정을 막았다.
  - [x] v94 36워커 재실행에서 shard health `36/36`, 입력 `3/3` 완료를 확인했다.
  - [x] v94 after-review를 closure에 반영해 `ACCEPT=374`, `HOLD=207`, `REPROCESS=1`, `INFO_MISSING=2`로 갱신했다.
  - [x] `py_compile` 및 `273`개 관련 회귀 테스트를 통과했다.
- 다음 작업:
  - [x] 남은 `re_search=1`: `9803986`은 v95 structured evidence catalog relabel로 `ACCEPT/no_action` 전환되어 닫혔다.
  - [ ] `human_review=122`는 packet별 자연어 리뷰로 ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING을 확정한다.
  - [ ] `slang_db_review=87`은 저장 차단/충돌/pending/family alias 상태별로 닫는다.
  - [ ] VLM/OCR image gate는 lazy placeholder와 실제 이미지 의미 근거를 분리해 재리뷰한다.
  - [ ] post-fix random baseline 및 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v92 이후 작업

- 상태: `post_id=9197737` 비소설 disclaimer false positive 수정 및 v92 canary 통과 / approval excluded `211` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v92_100k_fixable_gap_bug_action_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v92_explicit_non_novel_disclaimer_9197737_after_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 확인/완료:
  - [x] `소설얘기아닌데`처럼 명시적으로 비소설 토론임을 선언한 post가 외부 매체 title로 복구되는 경로를 차단했다.
  - [x] v91 canary 실패를 재현하고, v92 canary에서 `is_relevant=false`, `official_title=null`, `work_resolution=none`을 확인했다.
  - [x] v92 after-review `REPROCESS->ACCEPT=1`을 closure에 반영했다.
  - [x] locked official detail 후보 중복/role 변환 회귀를 보정했다.
  - [x] `270`개 관련 회귀 테스트를 통과했다.
- 다음 작업:
  - [x] 남은 `re_search=3`: `10529582`, `10870841`은 v94에서, `9803986`은 v95에서 닫혔다.
  - [ ] `slang_db_review=87`을 저장/차단/충돌/pending/family alias 상태별로 닫는다.
  - [ ] `VLM/OCR evidence gap=27`은 Codex in-app browser image loading evidence가 포함된 packet으로 다시 리뷰한다.
  - [ ] `human_review=121`은 자연어 packet 단위로 ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING을 확정한다.
  - [ ] post-fix random baseline 및 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v89 이후 작업

- 상태: v84 action input `199`건 36워커 재실행/병합/after-review 완료 / approval excluded `221` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v89_100k_fixable_gap_bug_action_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v89_current_remaining_action_after_v88_tooling_after_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 확인/완료:
  - [x] v89 checkpoint `74`건과 잔여 완료 `125`건을 병합해 `199/199` 무결성을 확인했다.
  - [x] after-review를 생성해 `ACCEPT=170`, `HOLD=16`, `REPROCESS=13`을 기록했다.
  - [x] latest closure에 v89 after-review를 반영해 `ACCEPT=363`, approval excluded `221`로 갱신했다.
  - [x] `tools/build_qualitative_exit_action_closure.py`가 v89 supplemental labels/packets를 읽도록 갱신했다.
- 다음 작업:
  - [ ] `re_search=13` post_id를 우선 재검색한다: `10824887`, `9452117`, `10357119`, `9803986`, `10388517`, `9197737`, `10529582`, `8879698`, `10870841`, `11418927`, `9339510`, `11262769`, `8705431`.
  - [ ] `slang_db_review=87`을 저장/차단/conflict/pending/family alias 상태별로 닫는다.
  - [ ] VLM/OCR evidence gap `27`건을 Codex in-app browser packet으로 다시 라벨링한다.
  - [ ] alias recall false negative 잔여 `73`건은 positive alias recall과 generic 오탐 회귀를 함께 검증한다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v88 이후 작업

- 상태: VLM/OCR lazy placeholder 도구 보강 / 관련 테스트 통과 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v88_vlm_lazy_placeholder_tooling_fix_ko_20260527.md`
  - `tools/capture_vlm_ocr_browser_review_cli.py`
  - `tools/build_qualitative_exit_action_closure.py`
  - `tools/build_v78_vlm_browser_semantic_relabel.py`
- 확인/완료:
  - [x] browser capture에 `article_lazy_pending_count`, `data_original_pending_count`, `placeholder_current_src_count`를 추가했다.
  - [x] closure가 legacy `imageGatePass=true`보다 image counter 실패를 우선하도록 고쳤다.
  - [x] v80 VLM relabel이 image gate 실패 시 `Strong`을 `Weak`로 낮추도록 고쳤다.
  - [x] 관련 회귀 테스트를 추가했다.
  - [x] `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools` `27 tests OK`.
- 다음 작업:
  - [ ] VLM/OCR `27`건을 새 image gate counter가 포함된 packet으로 다시 캡처/라벨링한다.
  - [ ] endpoint 복구 후 v84 rerun combined `199`건을 36워커로 재실행한다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v87 이후 작업

- 상태: 10만 건 부족점/버그 정리 갱신 / image placeholder complete trap 재확인 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v87_100k_fixable_gap_bug_action_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/v87_11097334_placeholder_complete_trap_probe_20260527.json`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/v87_11097334_placeholder_complete_trap_probe_20260527.png`
  - `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`
- 확인/완료:
  - [x] 10만 건 현재 부족점/버그/해결 가능 항목을 v87 action summary로 정리했다.
  - [x] `post_id=11097334`에서 placeholder 이미지가 `complete=true`, `naturalWidth>0`으로 잡히는 함정을 Codex in-app browser로 재확인했다.
  - [x] 스크롤/대기 후 `data-original`의 실제 `dcimg` URL로 교체되는 것을 확인했다.
  - [x] scan result review guide에 `data-original` 교체 확인과 placeholder currentSrc 감지 규칙을 추가했다.
  - [x] `2026-05-27 12:26:14 +09:00` 기준 LLM endpoint `127.0.0.1:8000`은 연결 실패, listener 없음, 관련 Python 점유 없음으로 확인했다.
- 다음 작업:
  - [ ] VLM/OCR `27`건은 `img.complete`가 아니라 placeholder 교체 완료와 이미지 의미/작품 판정 지지 여부를 분리 라벨링한다.
  - [ ] endpoint 복구 후 `v84_current_remaining_action_after_source_slang_fallback_rerun_combined_input.jsonl` `199`건을 36워커로 재실행한다.
  - [ ] `persisted_conflict=3` (`8650236`, `10173521`, `11097307`)은 alias 충돌 해소 리뷰로 닫는다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v86 이후 작업

- 상태: slang DB conflict 상태 정정 / latest remaining `391`건 / LLM endpoint 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v86_slang_conflict_status_correction_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v86_slang_db_status_review_after_conflict_detection_manifest.json`
  - `tools/build_qualitative_exit_action_closure.py`
  - `tools/build_slang_db_status_review.py`
- 확인/완료:
  - [x] `post_id=10173521`은 저장 누락이 아니라 `server_poc:conflict` 상태임을 확인했다.
  - [x] `titles[].conflicts[]`를 `persisted_conflict`로 인식하도록 classifier를 보정했다.
  - [x] 최신 `slang_db_review=87` 상태를 `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`로 정정했다.
  - [x] `extracted_not_persisted=0`을 확인했다.
- 다음 작업:
  - [ ] `persisted_conflict=3` (`8650236`, `10173521`, `11097307`)은 alias 충돌 해소 대상으로 리뷰한다.
  - [x] `blocked_by_result_contract=79`는 v101에서 차단 사유와 alias recall 영향을 spot review했다.
  - [ ] endpoint 복구 후 `v84_current_remaining_action_after_source_slang_fallback_rerun_combined_input.jsonl` `199`건을 36워커로 재실행한다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v85 이후 작업

- 상태: v86에서 conflict 상태 누락으로 정정됨 / 이 항목은 중간 상태 큐 기록
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v85_slang_db_status_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/v85_slang_db_status_review_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v85_slang_db_status_review_action_queue.md`
  - `tools/build_slang_db_status_review.py`
- 확인/완료:
  - [x] `slang_db_review=87`을 상태별 후속 큐로 분리했다.
  - [x] `blocked_by_result_contract=79`는 `confirm_block_reason_and_recall_impact`로 묶었다.
  - [x] `persisted_as_slang=3`은 `verify_saved_alias_not_pollution`으로 묶었다.
  - [x] `persisted_pending=2`는 `confirm_pending_or_promote`로 묶었다.
  - [x] `family_alias=2`는 `verify_family_alias_display_recall`로 묶었다.
  - [x] `extracted_not_persisted=1`은 `REPROCESS/investigate_persistence_gap`으로 우선 조사 대상으로 올렸다.
- 다음 작업:
  - [x] `extracted_not_persisted=1` (`post_id=10173521`)은 v86에서 `persisted_conflict`로 정정했다.
  - [x] `blocked_by_result_contract=79`는 v101에서 차단 사유와 alias recall 영향을 spot review했다.
  - [ ] endpoint 복구 후 `v84_current_remaining_action_after_source_slang_fallback_rerun_combined_input.jsonl` `199`건을 36워커로 재실행한다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v84 이후 작업

- 상태: source slang fallback 정정 / latest remaining `391`건 / LLM endpoint 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v84_source_slang_fallback_correction_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v84_current_remaining_action_after_source_slang_fallback_manifest.json`
  - `tools/build_qualitative_exit_action_closure.py`
- 확인/완료:
  - [x] v83의 `docs_issue=64`가 source field 결손이 아니라 closure fallback 누락이라는 점을 확인했다.
  - [x] review packet의 빈 `slang_db_fields` dict가 원본 `identity.slang_insight` fallback을 막던 문제를 고쳤다.
  - [x] latest closure를 재생성해 `docs_issue=0`, `slang_db_review=87`로 정정했다.
  - [x] v84 action package를 재생성했다: `re_search=127`, `re_judge=72`, `human_review=105`, `slang_db_review=87`, rerun combined `199`, browser target `27`.
  - [x] slang DB 리뷰 상태를 `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_pending=2`, `family_alias=2`, `extracted_not_persisted=1`로 재분류했다.
- 다음 작업:
  - [ ] endpoint 복구 후 `v84_current_remaining_action_after_source_slang_fallback_rerun_combined_input.jsonl` `199`건을 Gemma 4 4B, `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`, `--no-auto-up-shards`로 재실행한다.
  - [ ] `slang_db_review=87`은 저장 차단/저장됨/pending/family/extracted_not_persisted별로 자연어 근거와 recall 영향을 리뷰한다.
  - [ ] VLM/OCR `27`건은 Codex in-app browser에서 이미지 로딩과 semantic evidence를 분리 확인한다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v83 이후 작업

- 상태: v84에서 source fallback 누락으로 정정됨 / 이 항목은 중간 가설 기록
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v83_current_remaining_action_after_slang_field_routing_manifest.json`
  - `qualitative_review/20260505_214349_324347/v83_current_remaining_action_after_slang_field_routing_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v83_100k_fixable_gap_bug_summary_ko_20260527.md`
  - `tools/build_qualitative_exit_action_closure.py`
  - `tools/build_current_remaining_action_inputs.py`
- 확인/완료:
  - [x] `slang_db_review=87` 중 공개 slang 필드가 없는 `64`건을 `INFO_MISSING/docs_issue`로 분리했다.
  - [x] 실제 `blocked_by_result_contract` slang DB 리뷰는 `23`건으로 좁혔다.
  - [x] v83 action package를 재생성했다: `re_search=127`, `re_judge=72`, `human_review=105`, `docs_issue=64`, `slang_db_review=23`.
  - [x] rerun combined는 `199`건, browser target은 `27`건으로 유지된다.
  - [x] review packet에 `slang_db_fields`, `final_decision_fields`, `reason`, `search_health_flags`를 포함하도록 보강했다.
  - [x] 관련 테스트 `28`건을 통과했다.
- 다음 작업:
  - [ ] endpoint 복구 후 `v83_current_remaining_action_after_slang_field_routing_rerun_combined_input.jsonl` `199`건을 Gemma 4 4B, `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`, `--no-auto-up-shards`로 재실행한다.
  - [ ] `docs_issue=64`는 packet export/label routing 결손을 원인별로 재분류한다.
  - [ ] `slang_db_review=23`은 차단 사유와 recall 영향만 검토한다.
  - [ ] VLM/OCR `27`건은 Codex in-app browser에서 이미지 로딩과 semantic evidence를 분리 확인한다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v81 이후 작업

- 상태: v80 VLM/OCR current remaining 재라벨 반영 / latest remaining `391`건 / LLM endpoint 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v80_vlm_ocr_current_remaining_iab_semantic_relabel_manifest.json`
  - `qualitative_review/20260505_214349_324347/v81_current_remaining_action_after_v80_vlm_manifest.json`
  - `tools/build_v78_vlm_browser_semantic_relabel.py`
  - `tools/build_qualitative_exit_action_closure.py`
- 확인된 사실:
  - [x] VLM/OCR current remaining `28`건을 이미지 로딩 gate와 semantic evidence로 분리했다.
  - [x] `post_id=9531764` 단건은 Codex in-app browser 수동 확인을 반영해 `ACCEPT/no_action`으로 닫았다.
  - [x] 나머지 VLM/OCR은 `HOLD=25`, `INFO_MISSING=2`로 승인 제외 유지.
  - [x] latest closure는 `ACCEPT=193`, approval excluded `391/584`.
  - [x] latest action package는 rerun combined `199`건이며 `re_run=0`.
  - [x] `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools` 18건 통과.
- 다음 작업:
  - [ ] endpoint 복구 후 `v81_current_remaining_action_after_v80_vlm_rerun_combined_input.jsonl` `199`건을 36워커로 재실행한다.
  - [ ] `v81_current_remaining_action_after_v80_vlm_browser_targets.jsonl` `27`건은 이미지 로딩이 아니라 이미지 의미/작품 판정 지지 여부를 사람/브라우저 리뷰로 닫는다.
  - [x] `slang_db_review=87`을 `no_slang_term_in_packet=64`, `blocked_by_result_contract=23`으로 1차 분리했다.
  - [ ] `no_slang_term_in_packet=64`는 packet 공개 필드/export 또는 라벨 라우팅 문제로 분리 처리한다.
  - [ ] `blocked_by_result_contract=23`은 차단 사유와 recall 영향만 검토한다.
  - [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v78 이후 작업

- 상태: latest remaining `392`건 action별 입력 패키지 생성 완료 / LLM endpoint 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_manifest.json`
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_summary_ko.md`
  - `tools/build_current_remaining_action_inputs.py`
- 확인된 사실:
  - [x] latest remaining queue `392`건 전체를 패키징했다.
  - [x] `re_search=127`, `re_judge=72`, `re_run=27`을 rerun combined input `226`건으로 묶었다.
  - [x] `human_review=79`, `slang_db_review=87`은 별도 review packet으로 분리했다.
  - [x] `vlm_ocr_evidence_gap` 중심 browser target `28`건을 별도 파일로 분리했다.
  - [x] missing post_id `0`, duplicate 제거 `0`.
  - [x] `tests.test_qualitative_review_packet_tools`에 action split 회귀 테스트를 추가했다.
- 다음 작업:
  - [ ] endpoint 복구 후 `v78_current_remaining_action_rerun_combined_input.jsonl` `226`건을 36워커로 재실행한다.
  - [ ] VLM/OCR `28`건은 브라우저 이미지 gate와 OCR/VLM semantic evidence를 분리 확인한다.
  - [ ] `slang_db_review=87`은 저장/차단/pending/family/noise/display 상태로 수동 또는 도구 리뷰한다.
  - [ ] 실제 결과만 closure/gate에 반영한다.

## 2026-05-27 v77 이후 작업

- 상태: after-review readiness 보강 완료 / LLM endpoint 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v76_after_review_readiness_fix_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_preflight_original_after_manifest.json`
  - `tools/build_qualitative_round3_after_review.py`
- 확인된 사실:
  - [x] v75 input `96`건 전체에 `_round3_target.packet_id`와 `_round3_target.bucket`을 명시했다.
  - [x] after-review 도구가 `base_packet_id`/`primary_pattern` fallback을 사용하도록 보강했다.
  - [x] preflight original subset `96`건에서 packet/label `96`, missing target `0`을 확인했다.
  - [x] `tests.test_qualitative_review_packet_tools` 7건 통과.
- 다음 작업:
  - [ ] LLM endpoint 복구 후 v75 P0 input을 36워커로 실제 재실행한다.
  - [ ] 실제 결과에 대해 `build_qualitative_round3_after_review.py`를 실행하고 preflight가 아닌 post-fix label을 생성한다.
  - [ ] post-fix label만 closure/gate 판단에 사용한다.

## 2026-05-27 v76 이후 작업

- 상태: P0 잔여 targeted input 준비 완료 / LLM endpoint 대기 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input_manifest.json`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input.jsonl`
- 확인된 사실:
  - [x] `generic_common_surface=80`과 `weak_evidence_strong_resolution=16` 전체를 합쳐 P0 잔여 `96`건 입력을 생성했다.
  - [x] missing post_id는 `0`이다.
  - [x] input 구조와 manifest count 검증을 통과했다.
  - [x] `expert_main.py --help` 기준 `--parallel`, `--no-auto-up-shards`, `--server-type vllm`, `--slang-db` 플래그 사용 가능함을 확인했다.
  - [x] LLM endpoint `http://127.0.0.1:8000/v1/models`는 현재 connection refused 상태다.
- 다음 작업:
  - [ ] endpoint 복구 후 Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`, `--no-auto-up-shards`로 `v75_p0_generic_weak_remaining_input.jsonl`을 실행한다.
  - [ ] 결과 manifest에서 completed/failed/pending/flushed count를 확인한다.
  - [ ] after-review packet/label을 생성해 P0 큐가 실제로 닫혔는지 확인한다.
  - [ ] 결과를 `expanded_gate_decision.md`, `VERIFICATION_RESULTS.md`, `CHECKLIST.md`, `HISTORY.md`에 다시 반영한다.

## 2026-05-27 v75 이후 작업

- 상태: supplemental after-review closure 병합 보정 완료 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/supplemental_after_review_closure_merge_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
  - `qualitative_review/20260505_214349_324347/current_100k_fixable_gap_bug_summary_ko_20260527.md`
- 확인된 사실:
  - [x] v68/v71/v73 supplemental after-review label/packet이 latest closure에 반영되도록 병합했다.
  - [x] closure 최신 라벨은 `ACCEPT=192`, `HOLD=297`, `REPROCESS=93`, `INFO_MISSING=2`.
  - [x] approval excluded는 `392/584`로 갱신됐다.
  - [x] `supplemental_update_rows=19`를 manifest에 기록했다.
  - [x] 관련 Python 점유 프로세스는 없고, search shard 컨테이너는 36개 계열이 올라와 있음을 확인했다.
  - [x] LLM endpoint `http://127.0.0.1:8000/v1/models`는 현재 connection refused 상태다.
- 다음 작업:
  - [ ] LLM endpoint 복구 또는 포트 확인 후 Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 잔여 targeted set을 재실행한다.
  - [ ] `generic_common_surface=80` 중 unchanged `re_judge` 큐부터 direct evidence/generic surface 기준으로 닫는다.
  - [ ] `alias_recall_loss_false_negative=96`, `slang_db_alias_subtype=88`, `worker_shard_degraded_window=84`, `vlm_ocr_evidence_gap=28`, `weak_evidence_strong_resolution=16`을 각각 별도 action queue로 유지한다.
  - [ ] post-fix random baseline과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v74 이후 작업

- 상태: weak evidence closure guard 과차단 보정 완료 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/weak_evidence_closure_guard_fix_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 확인된 사실:
  - [x] `weak_evidence_strong_resolution` guard가 비관련/title-null ACCEPT까지 HOLD로 되돌리던 과차단을 수정했다.
  - [x] `tests.test_exit_action_closure` 6건 통과.
  - [x] closure 재생성 후 최신 라벨은 `ACCEPT=183`, `HOLD=306`, `REPROCESS=93`, `INFO_MISSING=2`.
  - [x] approval excluded는 `460/584 -> 401/584`로 감소.
  - [x] `weak_evidence_strong_resolution` 잔여는 `75 -> 16`으로 감소.
- 다음 작업:
  - [ ] `generic_common_surface=89`를 우선 targeted regression/라벨 보정 대상으로 처리한다.
  - [ ] `alias_recall_loss_false_negative=96`에서 실제 alias recall 버그와 human-review 경계 케이스를 분리한다.
  - [ ] `slang_db_alias_subtype=88`을 saved/blocked/pending/family/noise/display 상태별로 닫는다.
  - [ ] `worker_shard_degraded_window=84`는 fresh search 재검증 또는 degraded quarantine 기준으로 정리한다.
  - [ ] `vlm_ocr_evidence_gap=28`은 Browser image gate와 semantic OCR/VLM evidence를 분리해 처리한다.
  - [ ] post-fix random baseline과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v71 이후 작업

- 상태: `post_id=9218133` 일반 개념 질문 작품명 과확정 targeted fix 검증 완료 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/generic_concept_question_guard_fix_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v71_generic_concept_question_9218133_p36_20260527_manifest.json`
  - `qualitative_review/20260505_214349_324347/v71_generic_concept_question_9218133_after_packet_review_manifest.json`
- 확인된 사실:
  - [x] `9218133`에서 `반로환동/환골탈태` 개념 질문이 더 이상 `반로환동으로 신분세탁` resolved title로 확정되지 않는다.
  - [x] v71 run id `20260527_021145_875530`: completed `1`, failed `0`, pending `0`.
  - [x] v71 final: `is_relevant=false`, `official_title=null`, `work_resolution=none`, `discussion_type=trope_discussion`.
  - [x] v71 after-review: `ACCEPT=1`, `HOLD->ACCEPT=1`.
  - [x] canonical rescue 및 title-surface primary rescue 우회 경로를 모두 테스트로 고정했다.
- 다음 작업:
  - [ ] `generic_common_surface` 잔여 HOLD에서 일반 개념/설정/trope question 계열을 추가 추출한다.
  - [ ] decoder/verifier 내부 mapping 시도가 final decision에 영향을 주는 다른 row가 있는지 확인한다.
  - [ ] `weak_evidence_strong_resolution` bucket에서 official URL/search convergence만으로 과확정되는 이웃 케이스를 재검토한다.
  - [ ] post-fix random baseline `500~1000`건과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v68 이후 작업

- 상태: `post_id=8424362` 캐릭터 표면명 작품명 승격 targeted fix 검증 완료 / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/character_surface_title_rescue_fix_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v68_character_surface_title_8424362_p36_20260527_manifest.json`
  - `qualitative_review/20260505_214349_324347/v68_character_surface_title_8424362_after_packet_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/11097334_image_loading_probe_20260527.json`
- 확인된 사실:
  - [x] `8424362`에서 `에미야 키리츠구`가 더 이상 `official_title`로 확정되지 않는다.
  - [x] v68 run id `20260527_004625_654237`: completed `1`, failed `0`, pending `0`.
  - [x] v68 final: `is_relevant=false`, `official_title=null`, `work_resolution=none`.
  - [x] v68 after-review: `ACCEPT=1`, `HOLD->ACCEPT=1`.
  - [x] 검색 shard audit `36/36 OK`.
  - [x] Browser `iab`로 `11097334` 이미지 lazy-load를 재확인했다. initial placeholder `1`, 최종 loaded `3/3`, placeholder/incomplete/broken `0`.
- 다음 작업:
  - [ ] `generic_common_surface` 잔여 HOLD 전체에 같은 exact-detail guard가 충분한지 P0/P1 regression으로 확인한다.
  - [ ] `weak_evidence_strong_resolution` bucket에서 상세 URL substring/reader page/wikipedia hit가 strong evidence로 과승격되는지 재검토한다.
  - [ ] VLM/OCR closure builder가 final image state를 보지 않고 `ACCEPT`로 올리는 row가 남아 있는지 점검한다.
  - [ ] post-fix random baseline `500~1000`건과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v67 이후 작업

- 상태: direct/locked title rescue 상태 오염 targeted fix 검증 완료 / `generic_common_surface` 잔여 19건 after-review `ACCEPT=7`, `HOLD=12`, `REJECT=0` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/direct_locked_title_rescue_fix_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v67_generic_common_surface_hold19_after_packet_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/v67_generic_common_surface_hold19_p36_20260527_manifest.json`
  - `logs/expert_run_20260527_000930_077939.log`
- 확인된 사실:
  - [x] v64의 `post_id=10190186` `REJECT` 원인은 rescue 후 stale demotion/noise 상태 오염이었다.
  - [x] direct full-title rescue와 locked official candidate rescue 모두 stale demotion flag를 제거하도록 수정했다.
  - [x] `m.munpia.com/novel/detail/<id>` 문피아 모바일 작품 상세 URL을 작품 상세 URL로 인정하도록 수정했다.
  - [x] v66 단건 run id `20260527_000539_077549`: completed `1`, failed `0`, pending `0`, `10190186` stale demotion flag 없음.
  - [x] v67 19건 run id `20260527_000930_077939`: completed `19`, failed `0`, pending `0`.
  - [x] v67 after-review: `ACCEPT=7`, `HOLD=12`, `REJECT=0`.
  - [x] focused unittest와 py_compile 통과.
- 다음 작업:
  - [ ] `generic_common_surface` 잔여 `HOLD=12`를 원인별로 재분류한다.
  - [ ] `alias_recall_loss_false_negative`, `slang_db_alias_subtype`, `worker_shard_degraded_window`, `vlm_ocr_evidence_gap` 잔여 큐를 계속 처리한다.
  - [ ] post-fix random baseline `500~1000`건과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-26 v63 이후 작업

- 상태: targeted verified / packet 라벨 `ACCEPT=5`, `HOLD=1` / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/current_100k_gap_bug_fixable_summary_ko_20260526.md`
  - `qualitative_review/20260505_214349_324347/v63_character_virtual_battle_unresolved_guard_after_packet_review_summary.md`
  - `qualitative_review/20260505_214349_324347/v63_character_virtual_battle_unresolved_guard_after_packet_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v63_character_virtual_battle_unresolved_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_231204_349215.log`
- 확인된 사실:
  - [x] v63 run id `20260526_231204_349215`: completed `6`, failed `0`, pending `0`, flushed `6`
  - [x] 검색 shard health `36/36 OK`
  - [x] `count>=2`이지만 `slang_insight`가 없는 seed는 즉시 resolved 승격하지 않고 pending/review로 보류
  - [x] `강연금 -> 강철의 연금술사` exact non-novel media seed quarantine 유지
  - [x] `히집악` positive alias는 구조화된 `slang_insight` 근거로 계속 복구
  - [x] Browser `iab` 현재 확인 기준 `11097334` 본문 이미지 `3/3` loaded, placeholder `0`
  - [x] `11663540` character-only virtual battle 대표 케이스는 v63에서 `non-relevant/title null/none`으로 닫힘
  - [ ] `10426463` adjacent/trope/setting-borrowing 관련성 보존 정책 확장 검증
  - [x] 자동 after-review 라벨러가 `Weak + unresolved/title null + boundary risk`를 `ACCEPT`로 올리는 과허용 수정
- 다음 작업:
  - [ ] `weak_evidence_strong_resolution=75`, `generic_common_surface=89` targeted regression 재검증
  - [ ] `11663540`과 같은 character-only virtual battle pattern의 P0/P1 regression 이웃 케이스 검증
  - [ ] slang DB seed 상태를 `saved/blocked/pending/family/noise/display_missing`으로 분리하고 외부 IP seed 일반화
  - [ ] VLM/OCR `28`건 Browser image gate와 semantic evidence 재라벨
  - [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `GO` 금지

## 2026-05-26 v61 이후 작업

- 상태: targeted verified / known-bad 5 ACCEPT + 1 HOLD / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v61_catalog_tier_fix_after_packet_review_summary.md`
  - `qualitative_review/20260505_214349_324347/v61_catalog_tier_fix_after_packet_review_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/v61_catalog_tier_fix_after_packet_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v61_catalog_tier_fix_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_221106_422763.log`
- 확인된 사실:
  - [x] v61 run id `20260526_221106_422763`: completed `6`, failed `0`, pending `0`, flushed `6`
  - [x] 검색 shard health `36/36 OK`
  - [x] `py_compile` 및 focused unittest 5건 통과
  - [x] `강연금 -> 강철의 연금술사` seed는 BatchContextMemory 주입 단계에서 quarantine
  - [x] `9981263` 노벨피아 상세 page UI의 `웹툰코인` 문구가 `non_novel_media_platform`으로 오분류되지 않음
  - [x] `9981263`, `11205204` positive alias control 유지
  - [x] `11663540`, `8531521`, `8601885` negative control 유지
  - [ ] `10426463` adjacent/trope 관련성 보존 정책 확장 검증
- 다음 작업:
  - [ ] 외부 만화/애니/게임 IP alias seed quarantine을 exact blocklist에서 일반화 규칙으로 확장
  - [ ] `weak_evidence_strong_resolution=75`, `generic_common_surface=89` targeted regression 재검증
  - [ ] VLM/OCR `28`건은 Browser `iab` screenshot/image loaded count/OCR-VLM 공개 field를 붙여 재라벨
  - [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `GO` 금지

## 2026-05-26 10만 건 현재 액션 요약 이후 작업

- 상태: current summary refreshed / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 정리본:
  - `qualitative_review/20260505_214349_324347/current_100k_actionable_issue_summary_ko_20260526.md`
- 확인된 현재 기준:
  - [x] v61 targeted run `20260526_221106_422763`: completed `6`, failed `0`, pending `0`, flushed `6`
  - [x] random baseline 1000건: `ACCEPT=889`, `REPROCESS=109`, `HOLD=2`, `REJECT=0`
  - [x] high-risk expansion 5000건: `ACCEPT=2041`, `HOLD=1528`, `REPROCESS=1430`, `REJECT=1`
  - [x] current combined review 584건: `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`
  - [x] approval excluded `460/584`
  - [x] v61 기준 `8531521`은 final `non-relevant/title null`로 닫힘
  - [x] `강연금 -> 강철의 연금술사`는 런타임 seed quarantine 확인, 원본 DB cleanup/generalization 후보로 별도 유지
  - [x] Browser `post_id=11097334` 재확인: lazy placeholder 가능성이 있어 VLM/OCR은 본문 이미지 gate와 semantic evidence를 분리해야 함
- 다음 작업:
  - [ ] `weak_evidence_strong_resolution=75`, `generic_common_surface=89` targeted regression 재검증
  - [ ] `slang_db_review=87`을 saved/blocked/pending/family/noise/display 상태로 분리
  - [ ] 외부 만화/애니/게임 IP alias seed는 BatchContextMemory 즉시등록이 아니라 quarantine/review로 보냄
  - [ ] VLM/OCR `28`건은 Browser `iab` screenshot/image loaded count/OCR-VLM 공개 field를 붙여 재라벨
  - [ ] `10426463` 유사 adjacent/trope/setting-borrowing bucket 정책 결정
  - [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `GO` 금지

## 2026-05-26 v58 detail URL/media guard 이후 작업

- 상태: targeted verified / known-bad 5 ACCEPT + 1 HOLD / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v58_detail_url_media_guard_after_packet_review_summary.md`
  - `qualitative_review/20260505_214349_324347/v58_detail_url_media_guard_after_packet_review_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/v58_detail_url_media_guard_after_packet_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v58_detail_url_media_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_210850_328711.log`
- 확인된 사실:
  - [x] v58 run id `20260526_210850_328711`: completed `6`, failed `0`, pending `0`
  - [x] 검색 shard health `36/36 OK`
  - [x] `py_compile` 및 focused unittest 10건 통과
  - [x] result JSON에 row별 `search_evidence_catalog` 구조화 export
  - [x] fanart/comic/webtoon/viewer URL을 clean novel detail evidence에서 제외
  - [x] `11663540` `주서연 전차` direct title false positive 차단
  - [x] `8531521` `강철의 연금술사` 외부 만화/애니 IP false positive 차단
  - [x] `9981263`, `11205204` positive alias control 유지
  - [x] `8601885` game IP negative control 유지
  - [ ] `10426463` adjacent/trope 관련성 보존 정책 확장 검증
  - [ ] `강연금 -> 강철의 연금술사` 같은 외부 IP alias seed를 slang DB review bucket으로 분리
- 다음 작업:
  - [ ] `non_novel_media_platform`, `platform_reader_page` tier가 high-risk expansion packet에 충분히 노출되는지 점검
  - [ ] `generic_battle_anchor`, `media_platform_url_demoted`, `adjacent_ip_unresolved_policy_boundary` bucket 확장 표본화
  - [ ] expanded random baseline과 P0/P1 regression validation 전까지 semantic gate `GO` 금지

## 2026-05-26 v55 known-bad media/alias guard 이후 작업

- 상태: targeted verified / known-bad partial pass / adjacent IP HOLD / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_packet_manifest.json`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_195550_803682.log`
- 확인된 사실:
  - [x] v55 run id `20260526_195550_803682`: completed `6`, failed `0`, pending `0`
  - [x] `py_compile` 및 focused unittest 7건 통과
  - [x] `9981263` positive alias control 유지: `성녀의 속마음이 들린다`
  - [x] `11205204` positive alias control 유지: `히어로가 집착하는 악당이 되었다`
  - [x] `11663540` character-only 가상 대결 resolved 우회 경로 차단
  - [x] `8531521` 외부 만화/애니 IP non-relevant 유지
  - [x] `8601885` LoL/노틸러스 게임 IP non-relevant 유지
  - [x] v55 review packet `6`행 생성 및 packet manifest parse 확인
  - [x] positive control packet evidence URL 수집 확인: `9981263`, `11205204`
  - [x] v55 packet에 후보별 `evidence_catalog`와 reason 기반 `evidence_counts` 추가
  - [ ] `10426463` adjacent/trope 관련성 보존 정책 확장 검증
- 다음 작업:
  - [ ] `generic_battle_anchor`와 character-only virtual battle bucket을 확장 표본에서 재검증
  - [ ] `adjacent_ip_unresolved_policy_boundary`를 P1 bucket으로 분리하고 `10426463` 유사 케이스를 추가 표본화
  - [x] v55 review packet에는 `primary_work`/`novel_identity`/candidate `heretic_url` 기반 evidence URL을 구조화 export
  - [x] v55 review packet에는 후보별 title/alias/URL/source metadata catalog를 구조화 export
  - [ ] result JSON에 row별 raw search evidence catalog/EID/URL/snippet 전체를 구조화 export
  - [ ] expanded random baseline과 P0/P1 regression validation 전까지 semantic gate `GO` 금지

## 2026-05-26 v51 known-bad media/alias guard 이후 작업

- 상태: targeted partial verified / positive alias inversion fixed / character bridge policy open / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v51_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v51_known_bad_media_alias_guard_after_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v51_known_bad_media_alias_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_185600_839070.log`
- 확인된 사실:
  - [x] v51 run id `20260526_185600_839070`: completed `6`, failed `0`, pending `0`
  - [x] `py_compile` 및 focused unittest 11건 통과
  - [x] `9981263` positive alias inversion 수정 확인: `성녀의 속마음이 들린다`
  - [x] `8531521` 외부 만화/애니 IP가 최종 non-relevant로 유지됨
  - [x] `8601885` LoL/노틸러스 게임 IP가 최종 non-relevant로 유지됨
  - [x] `11205204` 히집악 positive control resolved 유지
  - [x] `10426463` adjacent/external IP 글을 relevant/unresolved로 보존
  - [ ] `11663540` character-parenthetical bridge resolved 허용 정책 결정
- 다음 작업:
  - [ ] character-only 가상 대결 글을 `resolved`, `relevant_unresolved`, `human_review` 중 어디로 보낼지 정책 고정
  - [ ] `locked_official_candidate_rescued`가 character-only bridge에서 발동하는 케이스를 P1 high-risk bucket으로 확장 표본화
  - [ ] result JSON의 `identity.evidence=null` 문제를 review packet 구조화 evidence export로 보강
  - [ ] expanded random baseline과 P0/P1 regression validation 전까지 semantic gate `GO` 금지

## 2026-05-26 v50 known-bad media/alias guard 이후 작업

- 상태: targeted partial verified / external IP fix confirmed / positive control regression open / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v50_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v50_known_bad_media_alias_guard_after_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v50_known_bad_media_alias_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_182412_783072.log`
- 확인된 사실:
  - [x] v50 run id `20260526_182412_783072`: completed `6`, failed `0`, pending `0`
  - [x] focused unittest 8건 통과
  - [x] `8531521` 외부 만화/애니 IP가 최종 non-relevant로 차단됨
  - [x] `8601885` LoL/노틸러스 게임 IP가 최종 non-relevant로 유지됨
  - [x] `11205204` 히집악 positive control resolved 유지
  - [x] `9981263` `성녀 속마음` positive control이 `아카데미의 순애`로 뒤집히는 회귀 수정
  - [ ] `10426463` adjacent/external IP overblocking 후보 정책 결정
  - [ ] `11663540` character-only 가상 대결 정책 결정
- 다음 작업:
  - [ ] title-side primary alias가 comparison/mentioned 후보보다 낮아지는 경로 추적
  - [ ] reason 내부에 title mismatch 반론이 있으면 resolved 확정을 낮추는 guard 추가
  - [x] 수정 후 known-bad 6건을 Gemma 4 4B `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 v51 재실행
  - [ ] `positive_alias_inversion`, `external_ip_overblocking_candidate`, `character_talk_policy_boundary`를 P0/P1 확장 bucket에 추가
  - [ ] expanded random baseline과 P0/P1 regression validation 전까지 semantic gate `GO` 금지

## 2026-05-26 v48 known-bad media/alias guard 이후 작업

- 상태: targeted partial verified / `8601885` fixed / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v48_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v48_known_bad_media_alias_guard_after_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v48_known_bad_media_alias_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_170233_055943_W5.log`
- 확인된 사실:
  - [x] v48 run id `20260526_170233_055943`: completed `6`, failed `0`, pending `0`
  - [x] `identified_category=game`을 비소설 매체 차단 신호로 처리하도록 보강
  - [x] `8601885` LoL/노틸러스 게임 IP가 최종 `is_relevant=false`, `official_title=null`, `work_resolution=none`으로 유지됨
  - [x] `8531521` `강철의 연금술사` resolved title false positive는 제거됨
  - [x] `9981263`, `11205204` positive control resolved 유지
- 다음 작업:
  - [ ] `8531521` 외부 만화/애니 IP를 `relevant/unresolved`로 보존할지 `non-relevant`로 닫을지 정책 결정
  - [ ] `11663540` character-only virtual battle 정책을 `HOLD`에서 확정
  - [ ] `10426463` 설정 차용/인접 IP bucket 확대 리뷰
  - [ ] slang DB pending alias `강연금 -> 강철의 연금술사` 같은 외부 IP 후보 quarantine/review
  - [ ] `weak_evidence_strong_resolution`, `generic_common_surface`, `non_novel_ip_alias_pollution` P0/P1 bucket 확장 검증
  - [ ] expanded random baseline과 P0/P1 regression 전까지 semantic gate `GO` 금지

## 2026-05-26 v42/v43 known-bad media/alias guard 이후 작업

- 상태: targeted partial verified / P0 regression open / semantic gate `NO-GO / REVIEW-LOCKED`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v42_v43_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v42_v43_known_bad_media_alias_guard_after_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/current_100k_gap_bug_fixable_summary_ko_20260526.md`
  - `qualitative_review/20260505_214349_324347/v43_single_8531521_media_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_154837_721537.log`
- 확인된 사실:
  - [x] v42 run id `20260526_153538_350152`: completed `6`, failed `0`, pending `0`
  - [x] v43 run id `20260526_154837_721537`: completed `1`, failed `0`, pending `0`
  - [x] `9981263`은 `성녀의 속마음이 들린다`로 resolved 유지
  - [x] `11205204`는 `히집악 -> 히어로가 집착하는 악당이 되었다` resolved 유지
  - [x] `11663540`은 `전 버튜버가 하고 싶은데요` title over-resolution 제거
  - [x] `8601885`는 노틸러스/LoL 외부 IP non-relevant 유지
  - [ ] `8531521`은 v43에서 `title_surface_primary_candidate_rescued` 경로로 `강철의 연금술사`가 다시 resolved 되어 P0 open
- 다음 작업:
  - [ ] `title_surface_primary_candidate_rescued` 직전에 non-novel media/IP guard 재적용
  - [ ] wiki/media/영화/단행본/OTT/파생 hit를 웹소설 `official_title_evidence`에서 제외
  - [ ] 파생/패러디/크로스오버 플랫폼 hit는 원작 title 직접 근거가 아니라 adjacent/derivative evidence로 분리
  - [ ] `8531521` 수정 후 `9981263`, `11205204`, `11663540`, `10426463`, `8531521`, `8601885`를 Gemma 4 4B `expert_main.py --parallel 36`으로 다시 재실행
  - [ ] P0 bucket `weak_evidence_strong_resolution=75`, `generic_common_surface=89` 확장 회귀 전까지 semantic gate `GO` 금지

## 2026-05-26 v38 known-bad media/alias guard 이후 작업

- 상태: targeted verified / semantic gate `NO-GO / REVIEW-LOCKED` 유지
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v38_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v38_known_bad_media_alias_guard_after_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v38_known_bad_media_alias_guard_p36_20260526_manifest.json`
  - `logs/expert_run_20260526_141931_661420.log`
- 확인된 사실:
  - [x] v38 run id `20260526_141931_661420`: completed `6`, failed `0`, pending `0`
  - [x] 실행 전 LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4`, search shard `36/36`, 이전 `expert_main`/`llm_batch`/`warp_shards` Python 잔존 없음
  - [x] `9981263`은 `성녀의 속마음이 들린다`로 resolved 복구
  - [x] `11205204`는 fresh/custom slang DB에서도 `히집악 -> 히어로가 집착하는 악당이 되었다` resolved 복구
  - [x] `8601885`는 노틸러스/LoL 외부 IP를 non-relevant로 처리
  - [x] `11663540`은 `전 버튜버가 하고 싶은데요` over-resolution 제거
  - [x] `8531521`은 `강연금 -> 강철의 연금술사` title 오염 제거
- 다음 작업:
  - [ ] `8531521` 계열: 비웹소설 IP가 `title=null`이어도 `is_relevant=true`로 남는 관련성 과포함 후단 guard 추가
  - [ ] `11663540` 계열: 캐릭터 talk를 `non_relevant`로 둘지 `relevant/unresolved`로 둘지 정책 기준 확정
  - [ ] `10426463` 계열: Project Moon/림버스 설정 비교와 웹소설/팬픽션 경계 bucket 추가 검토
  - [ ] v38 보정이 `weak_evidence_strong_resolution`, `generic_common_surface`, `alias_recall_loss_false_negative`, `non_novel_ip_alias_pollution` 확장 bucket에서 전이되는지 확인
  - [ ] expanded random baseline 및 P0/P1 bucket review 전까지 semantic gate `GO` 금지

## 2026-05-26 10만건 테스트 부족점/버그 최신 정리

- 상태: 최신 closure 기준 정리 완료 / semantic gate `NO-GO / REVIEW-LOCKED` 유지
- 최신 정리본:
  - `qualitative_review/20260505_214349_324347/current_100k_gap_bug_fixable_summary_ko_20260526.md`
- 기준 manifest:
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 확인된 핵심 수치:
  - `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`
  - approval excluded `460/584`
  - action queue: `human_review=138`, `re_search=120`, `re_judge=88`, `slang_db_review=87`, `re_run=27`
  - pattern queue: `weak_evidence_strong_resolution=75`, `generic_common_surface=89`, `alias_recall_loss_false_negative=96`, `slang_db_alias_subtype=88`, `worker_shard_degraded_window=84`, `vlm_ocr_evidence_gap=28`
- 다음 작업:
  - [ ] `weak_evidence_strong_resolution=75`와 `generic_common_surface=89`를 우선 targeted regression으로 재검증
  - [ ] `9981263`, `11205204`, `11663540`, `10426463` known-bad/positive-control 포함 후 `expert_main.py --parallel 36` 재실행
  - [ ] `slang_db_review=87`을 saved/blocked/pending/family/noise/display 상태로 분리
  - [ ] `vlm_ocr_evidence_gap=28`은 Browser `iab` screenshot, image loaded count, OCR/VLM field를 붙인 뒤 재라벨
  - [ ] 남은 approval excluded `460/584` 처리 전까지 `GO` 금지

## 2026-05-26 최신 10만 건 잔여 이슈 큐 정리

- 상태: 부족점/버그/해결 가능 항목 정리 완료 / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/current_100k_fixable_issue_queue_ko_20260526.md`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_remaining_queue.jsonl`
  - `qualitative_review/20260505_214349_324347/v31_single_10426463_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v33_single_11663540_after_summary_ko.md`
- 이번에 확인된 사실:
  - [x] 최신 closure는 `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`, approval excluded `460/584`
  - [x] 남은 action queue는 `human_review=138`, `re_search=120`, `re_judge=88`, `slang_db_review=87`, `re_run=27`
  - [x] 남은 pattern queue는 `alias_recall_loss_false_negative=96`, `generic_common_surface=89`, `slang_db_alias_subtype=88`, `worker_shard_degraded_window=84`, `weak_evidence_strong_resolution=75`, `vlm_ocr_evidence_gap=28`
  - [x] `random_control_v3` 1000건은 `ACCEPT=889`, `REPROCESS=109`, `HOLD=2`, `REJECT=0`
  - [x] high-risk expansion 5000건은 `ACCEPT=2041`, `HOLD=1528`, `REPROCESS=1430`, `REJECT=1`
  - [x] `v30_single_10426463` 0건 로드 원인은 UTF-8 BOM 처리 누락으로 확인하고, loader를 `utf-8-sig`로 보강
  - [x] `v31_single_10426463` 36워커 rerun completed `1`, failed `0`, pending `0`
  - [x] `10426463`은 current code 기준 `is_relevant=false`, `official_title=null`, `work_resolution=none`으로 `단테 [BL][단행본]` 오확정 재현 없음
  - [x] `11663540` v32에서 `title_deliberately_null` 뒤 canonical suspect 보정이 `전 버튜버가 하고 싶은데요`를 되살리는 over-resolution 경로 확인
  - [x] v33에서 `11663540`은 `is_relevant=true`, `official_title=null`, `work_resolution=unresolved`, flag `character_parenthetical_title_null_blocked`로 보류됨
- 다음 작업:
  - [x] `11663540` 계열 character-parenthetical + weak anchor + `_title_deliberately_null` over-resolution guard 추가 및 단건 검증
  - [ ] `weak_evidence_strong_resolution=75`와 `generic_common_surface=89` 확장 회귀에서 v33 guard 전이 확인
  - [x] `v30_single_10426463` 입력 `0개 포스트` 문제를 loader BOM 처리/preflight 검증으로 수정하고 재실행
  - [ ] `alias_recall_loss_false_negative=96`에서 positive control 손실 여부 재확인
  - [ ] `slang_db_review=87`을 saved/blocked/pending/family/noise/display 상태로 분리
  - [ ] VLM/OCR `28`건은 Browser `iab` screenshot/image gate와 semantic evidence를 분리해 재라벨
  - [ ] 위 큐 정리 전까지 semantic gate `GO` 금지

## 2026-05-26 v23 final targeted guard 이후 남은 작업
- 상태: targeted partial verified / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v23_final_targeted_guard_p36_20260526.json`
  - `qualitative_review/20260505_214349_324347/v23_final_targeted_guard_p36_20260526_manifest.json`
  - `qualitative_review/20260505_214349_324347/v23_final_targeted_guard_after_summary.md`
  - `logs/expert_run_20260526_001642_295323.log`
- 이번에 확인된 사실:
  - [x] v23 completed `5`, failed `0`, pending `0`
  - [x] `8705431`은 무관 `루팅능력자` search hit 교체가 차단되고 본문 공식 URL title로 복구됨
  - [x] `8601885`는 게임 IP title 오매치 제거 후 after-review `ACCEPT`
  - [x] `8424362`는 캐릭터 표면 title 승격 제거 후 unresolved/HOLD
  - [x] `8531521`은 non-novel media alias 오염 제거 후 unresolved/HOLD
  - [x] `8834919`는 v23 당시 false negative였으나 v29 `20260526_104800_163466`에서 `아포칼립스에 집을 숨김` resolved로 복구됨
- 다음 작업:
  - [x] `아집숨`/별칭+캐릭터+지칭어 조합 positive control은 v29에서 복구 확인
  - [ ] `alias_recall_loss_false_negative` bucket에서 v23 guard가 recall을 깨지 않는지 100건 이상 확장 확인
  - [ ] `weak_evidence_but_strong_resolution`, `generic_common_surface`, `non_novel_ip_alias_pollution` bucket 회귀 표본 확대
  - [ ] random baseline 1,000건 및 P0/P1 bucket 200건 이상 검토 전까지 `GO` 금지
  - [ ] VLM/OCR row는 Browser `iab` 스크린샷/비전 근거 포함 packet으로만 Strong evidence 인정

## 2026-05-25 v16-v19 비웹소설 IP / 본문 공식 URL 재확인

- 상태: targeted partial verified / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/v19_body_url_non_novel_guard_p36_20260525.json`
  - `qualitative_review/20260505_214349_324347/v19_body_url_non_novel_guard_p36_20260525_manifest.json`
  - `logs/expert_run_20260525_231813_131527.log`
  - `qualitative_review/20260505_214349_324347/current_100k_issue_resolution_summary_ko_20260525.md`
- 이번에 확인한 사실:
  - [x] v19 completed `5`, failed `0`, pending `0`
  - [x] `post_id=8601885`는 `리그 오브 레전드` title 확정 제거
  - [x] `post_id=8424362`는 `Fate/에미야` IP title 확정 제거, unresolved 보류
  - [x] `post_id=8834919` positive control 유지
  - [ ] `post_id=8531521`은 `batch_memory_exact_alias_rescued` 경로로 `강철의 연금술사`가 되살아남
  - [ ] `post_id=8705431`은 본문 공식 URL과 직접 title이 있는데도 author mismatch/unavailable 처리로 title evidence가 소실됨
- 남은 작업:
  - [ ] batch memory/slang_db exact alias rescue 직전에 비웹소설 media evidence와 alias pollution guard를 재적용
  - [ ] 본문 플랫폼 URL+직접 title은 fetch unavailable 상태라도 `HOLD` 이상의 원문 evidence로 남기는 규칙 추가
  - [ ] `generic_common_surface`, `weak_evidence_strong_resolution`, `alias_recall_loss_false_negative` 확장 회귀
  - [ ] VLM/OCR image loading gate는 Browser `iab` screenshot 근거 없으면 승인 제외
  - [ ] expanded random baseline 및 P0/P1 bucket review 전까지 `GO` 금지

## 2026-05-25 alias/bridge v15 제목란 alias 복구 재확인

- 상태: targeted verified / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v15_p36_20260525.json`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v15_p36_20260525_manifest.json`
  - `logs/expert_run_20260525_210222_899635.log`
  - `out/search_shard_audit_20260525_210133.json`
- 이번에 확인한 사실:
  - [x] v15 completed `8`, failed `0`, pending `0`
  - [x] v15 전 shard audit `36/36`, LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4`
  - [x] `post_id=9981263`은 `성녀의 속마음이 들린다`로 resolved 복구됨
  - [x] `post_id=9901127`은 `multi_work`, `official_title=null`로 단일 title 과확정 차단 유지
  - [x] `post_id=10190186`, `11205204`, `11113480`은 positive/control resolved 유지
  - [x] `post_id=9000828`, `9019735`는 generic/common surface 과확정 없음
- 남은 작업:
  - [ ] v15 보정이 `alias_recall_loss_false_negative`, `generic_parenthetical_bridge` 확장 bucket에서 과확정 없이 작동하는지 확인
  - [ ] `multi_work_title_list_resolution_demoted`가 정상 단일 작품 감상글을 과보수 demote하지 않는지 positive neighbor 회귀
  - [ ] VLM/OCR lazy image row는 `placeholder/incomplete/broken=0` 스크린샷 전까지 승인 제외 유지
  - [ ] expanded random baseline 및 P0/P1 bucket review 전까지 `GO` 금지

## 2026-05-25 alias/bridge v11-v14 후속 재확인

- 상태: targeted partial verified / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v11_p36_20260525.json`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v12_p36_20260525.json`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v13_p36_20260525.json`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v14_p36_20260525.json`
  - `logs/expert_run_20260525_193840_310458.log`
  - `logs/expert_run_20260525_195506_155856.log`
  - `logs/expert_run_20260525_200735_669612.log`
  - `logs/expert_run_20260525_202201_766849.log`
- 이번에 확인한 사실:
  - [x] v11/v12/v13/v14 모두 completed `8`, failed `0`, pending `0`
  - [x] v14 전 shard audit `36/36`, LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4`
  - [x] `post_id=9901127`은 v14에서 `is_relevant=true`, `work_resolution=multi_work`, `official_title=null`로 내려가 단일 title 과확정이 차단됨
  - [x] `post_id=9981263`은 v14에서 오답 확정은 피했지만 `official_title=null`, `unresolved_work`로 남음
  - [x] `post_id=10190186`, `11205204`, `11113480`은 positive/control resolved 유지
  - [x] `post_id=11097334` 직접 브라우저 재확인에서 lazy placeholder가 남을 수 있음을 확인
- 남은 작업:
  - [x] `post_id=9981263` 계열 제목란 alias 후보가 본문 비교작 후보와 같이 잡혀도 정확한 primary 후보로 복구되도록 v15에서 보강
  - [ ] `multi_work_title_list_resolution_demoted`가 정상 단일 제목글을 과보수 demote하지 않는지 positive neighbor 회귀 추가
  - [ ] `multi_work_or_adjacent_risk`, `weak_evidence_but_strong_resolution`, `alias_recall_loss_false_negative` bucket 확장 회귀
  - [ ] VLM/OCR lazy image row는 `placeholder/incomplete/broken=0` 스크린샷 전까지 승인 제외 유지
  - [ ] expanded random baseline 및 P0/P1 bucket review 전까지 `GO` 금지

## 2026-05-25 alias/bridge v8-v10 후속 재확인

- 상태: 후속 targeted 재실행 완료 / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v8_p36_20260525.json`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v9_p36_20260525.json`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v10_p36_20260525.json`
  - `logs/expert_run_20260525_183704_522400.log`
  - `logs/expert_run_20260525_185932_392781.log`
  - `logs/expert_run_20260525_191458_896289.log`
- 이번에 확인한 사실:
  - [x] v8/v9/v10 모두 completed `8`, failed `0`, pending `0`
  - [x] v10 전 shard audit `36/36`, LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4`
  - [x] `post_id=11205204`는 v9/v10에서 `히어로가 집착하는 악당이 되었다`로 유지
  - [x] `post_id=9901127`은 비관련 과차단은 줄었지만 v9/v10에서 `나 혼자만 솔플러` 단일 title 과확정
  - [x] `post_id=9981263`은 v8/v9에서 회수됐으나 v10에서 `unresolved_work`로 회귀
- 남은 작업:
  - [ ] `title_surface_primary_candidate_rescued`가 `relation_hold_unresolved_recovered`와 multi-work 신호를 무시하고 단일 title을 되살리는 경로 차단
  - [ ] 제목란 alias 후보가 본문 비교작 후보보다 primary로 보존되도록 `성녀 속마음` 회귀 보강
  - [x] v11 이상 targeted 재실행 후 `9981263`, `9901127`, `11205204`, `9000828`, `10190186`, `11113480`를 함께 검증
  - [ ] 통과하더라도 random baseline 및 P0/P1 bucket expanded review 전까지 `GO` 금지

## 2026-05-25 10만건 테스트 부족점 및 해결 가능 항목

- 상태: 부족점 정리 완료 / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/current_100k_issue_resolution_summary_ko_20260525.md`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
  - `qualitative_review/20260505_214349_324347/alias_recall_bridge_slang_fix_v6_p36_20260525.json`
  - `logs/expert_run_20260525_174243_300254.log`
- 이번에 확인한 사실:
  - [x] 최신 closure는 `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`, approval excluded `460/584`
  - [x] 당시 targeted run `20260525_174243_300254`은 completed `8`, failed `0`, pending `0`, shard `36/36`
  - [x] `post_id=9019735`, `9325585`는 일반어/캐릭터 bridge 과잉 title 확정이 제거됨
  - [x] positive control `11113480`은 resolved 유지
  - [x] `post_id=9000828`의 `라미아` generic species/trope surface title 오매칭은 targeted v4에서 차단됨
  - [x] `post_id=10190186`의 `성기사 -> 월드 오브 워크래프트` generic role bridge 오매칭은 targeted v6에서 차단되고 `망한 교단의 성기사`로 복구됨
  - [x] `post_id=11205204`의 `히집악` slang_db exact alias false negative 및 output schema `anchor_type` 매핑 오류는 targeted v4에서 해결됨
- 남은 작업:
  - [x] `post_id=10190186`의 `망한 교단의 성기사` direct full-title rescue 처리
  - [x] `post_id=9981263`의 `성녀 속마음` 제목란 alias 후보가 후보 pool에서 보존되지 못하는 회귀는 v15에서 처리
  - [ ] `post_id=9901127`처럼 여러 작품 감상 비교 글이 단일 title 미확정 때문에 비관련으로 내려가는 과차단 처리
  - [x] generic species/role/trope surface가 원문 full title 없이 primary title이 되지 않도록 일반화
  - [x] slang_db exact alias lookup에서 감탄사/감상어 제거 후 alias 후보를 rescue
  - [ ] safe compound phrase가 포함된 query는 감상어가 붙어도 pruning하지 않도록 회귀 테스트 고정
  - [x] targeted 8건을 Gemma 4 4B, `expert_main.py --parallel 36`으로 v15 재실행
  - [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 `GO` 금지

## 2026-05-25 generic_common_surface 전수 회귀 및 잔여 HOLD

- 상태: full bucket regression 완료 / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/generic_common_surface_full_regression_review_ko_20260525.md`
  - `qualitative_review/20260505_214349_324347/generic_common_surface_full_regression_p36_20260525_manifest.json`
  - `qualitative_review/20260505_214349_324347/generic_common_surface_full_regression_p36_20260525_after_manifest.json`
  - `qualitative_review/20260505_214349_324347/generic_common_surface_thin_bridge_guard_v2_p36_20260525_manifest.json`
- 이번에 완료한 확인:
  - [x] `generic_common_surface` population `89/89` 전수 입력 생성
  - [x] search shard audit `36/36`
  - [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` full bucket regression 수행
  - [x] full regression completed `89`, failed `0`, pending `0`
  - [x] after-review `ACCEPT=1`, `HOLD=88` 확인
  - [x] `thin-bridge title` guard 및 `unverified alias/plot title` guard 추가
  - [x] 잔여 8건 v2 회귀 completed `8`, failed `0`, pending `0`
  - [x] residual v2 기준 `9019735`, `9325585`, `9000828` 일반어/캐릭터/트로프 과잉 title 확정 제거
  - [x] residual v2 기준 positive control `9901127`, `11113480` resolved 유지
- 남은 작업:
  - [x] 최신 slang/bridge run에서 `9000828` generic surface title 회귀가 차단됐는지 재확인
  - [x] 최신 slang/bridge run에서 `9901127` positive control resolved 복구 확인
  - [x] `post_id=11205204`의 `히집악` false negative alias recall 원인 분리 및 처리
  - [x] 최신 slang/bridge run에서 `post_id=9981263`의 `성녀 속마음` alias 후보가 multi-work primary로 확정되지 못하는 원인 처리
  - [x] `post_id=9981263` 회수 개선은 v15 targeted run에서 재확인
  - [ ] `generic_common_surface`는 `HOLD=88/89`이므로 `re_judge` 종료가 아니라 추가 alias recall/근거 보강 후 재검증
  - [ ] `weak_evidence_strong_resolution` bucket으로 같은 guard의 과보수/과확정 전이 여부 확인

## 2026-05-25 search_only zero-bucket 과잉 확정 가드

- 상태: targeted regression 통과 / semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/search_only_zero_bucket_guard_review_ko_20260525.md`
  - `qualitative_review/20260505_214349_324347/issue_regression_search_only_guard_p36_20260525_manifest.json`
  - `qualitative_review/20260505_214349_324347/issue_regression_search_only_guard_p36_20260525.json`
- 이번에 완료한 확인:
  - [x] `search_only + post_spans=0 + official_urls=0 + official_nonwiki=0` 단일 작품명 과잉 확정 guard 추가
  - [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` 회귀런 수행
  - [x] `post_id=11663540`, `10824887`은 관련글 유지 + title unresolved 확인
  - [x] positive control `post_id=9722392`는 `아카데미 플레이어를 죽였다` resolved 유지 확인
- 남은 작업:
  - [x] `generic_common_surface` bucket 확장 회귀: population `89/89` 전수 재실행 완료
  - [ ] `weak_evidence_strong_resolution` bucket에서 직접 evidence 유무 기준 재판정
  - [ ] guard print 분기 발화를 증명할 synthetic/unit fixture 추가
  - [ ] expanded random baseline 및 P0/P1 bucket 재검증 전까지 `GO` 금지

## 2026-05-25 Codex 내장 브라우저 이미지 로딩 게이트 반영

- 상태: semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/vlm_ocr_iab_image_gate_manifest.json`
  - `qualitative_review/20260505_214349_324347/browser_visual_vlm_ocr_iab_image_gate/vlm_ocr_iab_image_gate_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/remaining_issues_fix_plan_ko_20260525.md`
  - `qualitative_review/20260505_214349_324347/fix_test_review_ko_20260525.md`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 이번에 완료한 확인:
  - [x] Codex 내장 Browser `iab`로 VLM/OCR 100건 재검증
  - [x] 본문 이미지 lazy-load 스크롤/대기 게이트 추가
  - [x] `post_id=11097334` 스크롤 전/후 이미지 로딩 상태 증거 저장
  - [x] closure 재계산: `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`
  - [x] VLM/OCR fallback 캡처 도구가 `article_image_count/loaded/incomplete/placeholder/broken`을 기록하고, 이미지 미로딩 상태를 `Strong`으로 승격하지 않도록 패치
  - [x] `expert_main.py --parallel 36` smoke test: venv Python 기준 `completed=2`, `failed=0`, shard health `36/36`
- 남은 작업:
  - [ ] `remaining_issues_fix_plan_ko_20260525.md` 기준으로 `re_search=120`, `re_judge=88`, `slang_db_review=87`, `re_run=27`, `human_review=138` 순서로 닫기
  - [x] `post_id=10794867`: v96에서 `viewimagePop.php` 첨부 팝업 이미지를 확인하고 `HOLD/human_review`로 전환
  - [ ] `post_id=10892069`: 삭제/목록 리다이렉트로 `INFO_MISSING/human_review`, source image URL 복구 가능성 별도 확인
  - [ ] v96 기준 approval excluded `209` 후속 처리

## 2026-05-24 server-poc 갱신 지침 재확인 결과

- 상태: semantic gate `NO-GO`
- 최신 근거:
  - `qualitative_review/20260505_214349_324347/round3_exit_action_closure_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/updated_guideline_execution_audit_ko.md`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 이번에 완료한 확인:
  - [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` 재실행
    - `round3_exit_re_search_re_run_p36_result_manifest.json`: completed `155/155`, failed `0`
    - `search_shard_audit_36_current.json`: shard `36/36`
  - [x] VLM/OCR 전체 bucket `100`건 브라우저 직접 확인
    - `browser_visual_vlm_ocr_all/vlm_ocr_browser_visual_manifest.json`: captured `100/100`
    - visual evidence: `Weak=100`, `Strong=0`
    - 기존 VLM/OCR `ACCEPT=70`건은 새 지침상 승인 제외
  - [x] judgment guard / slang_db / manual review 큐 문서화
    - `round3_manual_guard_slang_reviews.jsonl`: `385`건
    - slang_db 상태: `no_slang_term_in_packet=344`, `blocked_by_result_contract=37`, `persisted_as_slang=2`, `family_alias=1`, `persisted_pending=1`
- 최신 closure 결과:
  - `ACCEPT=52`, `HOLD=365`, `REPROCESS=94`, `INFO_MISSING=73`
  - approval excluded: `532/584`
- 남은 exit action:
  - [ ] `re_search` `120`건: 직접 official/work evidence 보강 또는 demote 확정
  - [ ] `re_judge` `88`건: generic/common surface guard 수정 또는 수동 relabel
  - [ ] `slang_db_review` `87`건: saved/blocked/pending/family/noise/display 상태 확정
  - [ ] `human_review` `210`건: 원문 의도/evidence 거리/alias recall 사람 판독
  - [ ] `re_run` `27`건: 필요한 입력 modality 또는 검색 증거 보강 후 재실행
  - [x] VLM/OCR 후속 브라우저 판독은 Codex 내장 Browser plugin `@browser` / in-app browser `iab`로 먼저 수행
  - [ ] Playwright CLI/headless fallback 사용 시 내장 브라우저 사용 불가 사유와 fallback 명령/stdout/stderr를 manifest에 기록
  - [ ] exit action 이후 random baseline 재검증
  - [ ] exit action 이후 P0/P1 regression validation 재검증

## server-poc `20260505_214349_324347` 품질 GO 전 남은 작업

- 상태: semantic gate `NO-GO`
- 근거:
  - `qualitative_review/20260505_214349_324347/test_scan_review_analysis_ko_20260523.md`
  - `qualitative_review/20260505_214349_324347/review_completion_audit_ko.md`
- 남은 exit action:
  - [ ] `fresh_search_with_direct_evidence_or_demote` `125`건 처리
  - [ ] `fix_judgment_guard_or_manual_relabel` `88`건 처리
  - [ ] `complete_slang_db_state_review` `87`건 처리
  - [ ] `manual_adjudication` `59`건 처리
  - [ ] `rerun_with_required_input_modality_or_quarantine_disabled_modality` `30`건 처리
  - [ ] exit action 이후 random baseline 재검증
  - [ ] exit action 이후 P0/P1 regression validation 재검증
- 실행 기준:
  - Gemma 4 4B 후속 재확인/재처리는 `MCP_SHARD_COUNT=36` 및 shard audit `36/36`을 맞추고 기록
  - 실제 워커 수는 `effective_parallel=min(requested_parallel,input_count)`로 확인하고, 36건 미만 targeted run은 자동 축소된 manifest 값을 검증

이 문서는 개발/기능개선 TODO의 색인이다. 실제 항목 관리는 아래 문서에서 나누어 진행한다.

- 개발/인프라/테스트: `DEV_TODO.md`
- 기능 개선/품질 개선: `FEATURE_IMPROVEMENT_TODO.md`
- 품질 승인 체크: `OPERATION_QUALITY_CHECKLIST.md`
- 검증 결과: `VERIFICATION_RESULTS.md`

## P0 - 런 안정성

- [x] 죽은 MCP/SearchXNG shard가 endpoint pool에 남는 문제 확인
  - 완료 기준: `tools/audit_search_shards.py --count 36`에서 문제 shard 목록 확인
  - 결과: 최초 `27/36` 정상, 문제 `[1,10,13,15,26,27,29,33,34]`
- [x] 문제 shard recreate 후 재확인
  - 완료 기준: 재감사 `ok=36/36`
  - 상세: `docs/search_reliability_review_20260426.md`
- [x] 런 시작 health check가 `/readyz`까지 확인하도록 보강
  - 완료 기준: bridge는 살아 있고 SearchXNG가 죽은 shard를 실패로 판정
- [x] MCP client failover 보강
  - 완료 기준: 워커 기본 shard 실패/저하 시 다른 endpoint 후보를 시도
- [x] MCP client failover budget 추가
  - 완료 기준: 검색 1건이 전체 36 shard를 순차 순회하지 않도록 `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH`와 `MCP_CLIENT_SEARCH_TIMEOUT_SEC` 지원
  - 상세: `IMPROVEMENT_REGISTER.md`
- [x] post별 late search 누적 예산 가드 추가
  - 완료 기준: 반복 verification/recall 검색이 post 단위 누적 예산을 넘으면 cap 또는 skip
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `IMPROVEMENT_REGISTER.md`
- [x] VLM/OCR degenerate image geometry guard 추가
  - 완료 기준: 1px 높이, 0px 크기, 극단 비율 이미지가 vLLM multimodal payload로 들어가기 전에 fetch 단계 limitation으로 격리됨
  - 발견: run `20260501_010427_282685`와 과거 run `20260423_170321_250907` 모두 loaded index `4049`, post `11589463`에서 `bytes=448` VLM 요청 직후 `500 -> 502`로 전파
  - 원인 증거: 해당 dcimg 응답은 `application/octet-stream`이지만 JPEG signature이며 실제 dimensions는 `389x1`
  - 확인: `tests.test_agentic_pipeline_rework` 161건 OK, `tools/audit_expert_run_health.py --run-id 20260501_010427_282685` 재실행
  - 서버 재기동 후 확인: 단건 canary `20260501_160410_623323`에서 completed `1/1`, VLM chunk request 없음, 500/502 없음
  - 상세: `DEV_TODO.md`, `IMPROVEMENT_REGISTER.md`, `HISTORY.md`, `VERIFICATION_RESULTS.md`
- [x] Arbiter `suspected_titles` confidence 혼합 타입 정렬 오류 수정
  - 완료 기준: `confidence`가 `"High"`, `"0.65"`, `0.2`, `None`처럼 섞여도 정렬 TypeError가 발생하지 않음
  - 발견: server-poc run `20260505_214349_324347`에서 W12/post `9984573`, W10/post `8641648`, W26/post `9775371`, W5/post `9785421`에 동일한 `'< not supported between instances of float and str'` 오류 발생
  - 확인: targeted unittest 5건 OK, `py_compile` pass
  - 상세: `IMPROVEMENT_REGISTER.md`, `HISTORY.md`, `VERIFICATION_RESULTS.md`
- [ ] VLM image fetch limitation observability 보강
  - 완료 기준: full pipeline result/log/audit에서 `image_geometry_too_small:389x1` 같은 VLM fetch skip 사유가 post별로 확인됨
  - 발견: 단건 canary `20260501_160410_623323`은 `vlm: used=False, fetch=0/1`로 crash 방어는 확인됐지만 limitation 문자열은 최종 output/log에 노출되지 않음
  - 상세: `IMPROVEMENT_REGISTER.md`, `VERIFICATION_RESULTS.md`
- [ ] VLM/OCR browser visual evidence packet tooling 추가
  - 완료 기준: `VLM_OCR_involved` packet에 browser URL, access status, screenshot path, vision/manual observation, visual evidence grade가 포함됨
  - 완료 기준: 브라우저 접근 실패/삭제/로그인 필요/시각-OCR 충돌 케이스가 `INFO_MISSING`/`HOLD`/`REPROCESS`/`REJECT`로 분리되고 `ACCEPT`로 승인되지 않음
  - 상세: `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `SCAN_RESULT_REVIEW_GUIDE.md`, `OPERATION_QUALITY_CHECKLIST.md`
- [ ] 장시간 런 중 shard readiness 주기 snapshot 추가
  - 완료 기준: N분 단위 `out/search_shard_audit_*.json` 또는 monitor event 기록
  - 상세: `DEV_TODO.md`
- [ ] post별 search health flag 저장
  - 완료 기준: 검색 빈 결과/저하/timeout이 결과 JSON에서 후처리 대상으로 식별됨
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`

## P1 - 검색 품질

- [x] generic relation only / character parenthetical targeted 회귀 수정
  - 완료 기준: `11631298`은 비관련/후보 누수 없음, `11663540`은 `전 버튜버가 하고 싶은데요`로 resolved
  - 남은 상태: afterfix11 200건 canary 통과, 120건 LLM 리뷰 패킷 판독 완료, 1,000건 risk discovery 완료. 품질은 critical FP/FN 재현으로 추가 개선 필요
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `VERIFICATION_RESULTS.md`
- [x] afterfix12 P0 title/alias gate targeted 수정
  - 완료 기준: `뮤지컬 배우`, `라쇼몽 source metadata`, `무림맹` 과구제를 막고 `서울마탑`은 구제
  - 확인: targeted unittest `13/13 OK`, core4 targeted run 및 `11620037` 단건 rerun 통과
  - 확인 추가: afterfix12 36병렬 canary `20260428_142042_238055`에서 `200/200`, failed `0`, `11718070/11620037` FP 제거, `11663540/11562020` positive 유지
  - 남은 상태: 120건 리뷰 패킷 판독과 1,000건 risk discovery에서 재발률 확인 필요
  - 상세: `VERIFICATION_RESULTS.md`, `HISTORY.md`
- [x] 공통 제목 stem 충돌 검색 이웃 분리
  - 완료 기준: `마법소녀ㄴ`처럼 복수 공식 제목에 공통으로 들어가는 stem에서 본문 앵커가 닫힌 후보만 primary로 유지하고, 검색 이웃은 comparison/recommendation/slang 후보로 저장하지 않음
  - 확인: `tests.test_agentic_pipeline_alias_contract` 30건 통과, `11684407` 단건 실제 rerun에서 `마법소녀ㄴ은 은퇴하고 싶다` resolved 및 `comparison_target=null`
  - 남은 상태: afterfix13 200건 canary와 1,000건 risk discovery에서 과차단/과확정 재집계 필요
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `VERIFICATION_RESULTS.md`, `IMPROVEMENT_REGISTER.md`
- [x] adjacent relevance legacy flag 및 budget profile 정리
  - 완료 기준: adjacent author/meta/recommendation은 주변 담론으로 보존하되 legacy `is_relevant`와 official title 확정으로 새지 않고, genre discussion budget은 공식 근거 확인 슬롯을 유지
  - 확인: targeted adjacent 7건, budget 이웃 3건, `tests.test_agentic_pipeline_rework` 145건, `tests.test_agentic_pipeline_alias_contract` 30건 통과
  - 남은 상태: 200건 canary와 1,000건 risk discovery에서 adjacent 누수와 genre budget FP 증가 여부 확인 필요
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `VERIFICATION_RESULTS.md`, `IMPROVEMENT_REGISTER.md`
- [x] Namu 의학/일반 개념 official title 승격 차단
  - 완료 기준: `11718111`처럼 나무위키 일반 의학 항목이 URL-backed 보정이나 character-parenthetical bridge로 작품 title이 되지 않음
  - 확인: targeted 5건, `tests.test_agentic_pipeline_rework` 147건, `tests.test_agentic_pipeline_alias_contract` 30건, 단건 actual run `20260428_230857_637381` 통과
  - 확대 확인: afterfix14 canary `20260428_233059_378617`은 `completed=200/200`, risk discovery `20260429_002511_375830`은 `completed=1001/1001`, 모두 failed/pending 0
  - 남은 상태: risk discovery에서 `11718111 -> 정신과 의사`가 재발하여 weak-evidence official title guard로 확장 필요
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `VERIFICATION_RESULTS.md`, `IMPROVEMENT_REGISTER.md`
- [ ] weak-evidence official title 승격 제한
  - 완료 기준: `official_title_evidence=false` 또는 `post_spans=0/search_snippets=0/official_urls=0`인데 플랫폼 URL/검색 bootstrap만으로 resolved되는 케이스를 HOLD/REPROCESS로 이동
  - 발견: afterfix14 risk discovery `20260429_002511_375830`에서 약한 근거 official title 후보 35건 추출
  - 대표 사례: `11718111 -> 정신과 의사`, `11684415 -> 小數, decimal number`, `11505857 -> Cecil`, `11684401 -> 추리 소설`, `11205227 -> 챌린지`
  - positive 보존: `나혼렙`, `마법소녀ㄴ은 은퇴하고 싶다`, `전 버튜버가 하고 싶은데요`, `서울에 마탑 세웠더니 돈이 미쳤다`
  - 진행: afterfix15~16에서 literal/dictionary/medical unresolved guard 추가, `tests.test_agentic_pipeline_rework` 153건 OK, afterfix16 200 canary `20260429_175638_261091` 완료.
  - 보류: afterfix17 targeted에서 `11198715` 오답 title lock은 제거됐지만 `Relevant=0` 과보수라 1,000건 risk discovery는 HOLD.
  - 다음 단계: 의도적 오타/자모 title alias가 본문 고유 단서와 결합할 때 `관련-미확정`으로 유지하는 positive/negative 이웃 테스트 추가 후 200 canary 재실행
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `IMPROVEMENT_REGISTER.md`, `VERIFICATION_RESULTS.md`
- [ ] generic concept parenthetical bridge 차단
  - 완료 기준: `오러(판타지 용어)`처럼 개념어 parenthetical이 character/work bridge로 등록되어 `판타지 용어`를 official title로 승격하지 않음
  - 발견: VLM runtime canary `20260501_160410_623323`에서 internal reasoning은 장르 일반론/non-relevant였지만 최종 output은 `판타지 용어` resolved/title로 뒤집힘
  - 일반화: parenthetical 내부가 `용어`, `개념`, `설정`, `장르`, `목록`, `대문`, `분류` 등 비작품 범주일 때는 작품명 bridge 후보에서 제외
  - 이웃 보존: `주서연(전 버튜버가 하고 싶은데요)` 같은 character(work title) bridge는 유지
  - 상세: `VERIFICATION_RESULTS.md`
- [x] 의도적 오타/자모 포함 title alias 정책
  - 완료 기준: `마법소녀ㄴ`처럼 일반 장르어와 실제 작품명이 겹치는 표면에서 오답 resolved를 막고, 본문 고유 캐릭터/설정 단서가 있으면 비관련이 아니라 관련-미확정으로 유지
  - 대표 사례: `11198715`은 afterfix16에서 `마법소녀물 신전사가 되었다`로 오매칭, afterfix17 targeted에서 오매칭은 제거됐으나 과보수 non-relevant
  - negative 이웃: `11456200`처럼 장르 클리셰만 있는 폼체인지 글은 non-relevant 유지
  - 확인: afterfix19 targeted `11198715`은 `Relevant=1`, `Identified=0`, `official_title=null`, flag `internal_work_signal_unresolved_recovered`; 단위 테스트에서 `11456200` negative 이웃은 rescue되지 않음
  - 확대 확인: afterfix19 200건 canary `20260429_204443_104695`, 1,001건 risk discovery `20260429_213837_418990` 완료. `11198715`은 관련-미확정 유지.
  - 남은 상태: `11616838`처럼 body 내부 캐릭터/설정 단서가 더 많은 positive 이웃은 resolved가 맞는지 계속 리뷰 필요
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `VERIFICATION_RESULTS.md`
- [ ] locked official 후보 bad metadata 재승격 방지
  - 완료 기준: locked 공식 후보라도 `community_post`, `deleted/unavailable`, `url_deleted_or_unavailable`, `url_is_community_post`, `listing_only`, `title_url_mismatch` 신호가 있으면 unresolved/non-relevant를 resolved로 되살리지 않음
  - 발견: afterfix19 risk discovery `20260429_213837_418990`에서 `11631298 -> 무림맹주 막내제자` 재승격
  - 진행: afterfix20에서 구조 가드 추가, `tests.test_agentic_pipeline_rework` 157건 OK, targeted `20260430_015935_598854`에서 `11631298` title 없음 확인
  - 확대 확인: afterfix20 200건 canary `20260430_021001_693350` 완료, `completed=200/200`, `reason_errors=0`, `11631298` title 없음
  - 확대 확인: afterfix20 1,001건 risk discovery `20260430_025849_885589` 완료, `completed=1001/1001`, `reason_errors=0`, `11631298` title 없음
  - 남은 상태: 기능 자체는 통과했지만 risk 전체 품질은 `11505857 -> Cecil`, `11456200` 과복구 때문에 REVIEW
  - 상세: `VERIFICATION_RESULTS.md`, `IMPROVEMENT_REGISTER.md`
- [x] 짧은 인명/캐릭터 표면 title 오승격 방지
  - 완료 기준: 본문이 `세실` 같은 인명/캐릭터 표면만 갖고 있고 작품 고유 앵커가 약하면 `Cecil` 같은 영문 title로 resolved하지 않음
  - 발견: afterfix20 risk discovery `20260430_025849_885589`에서 `11505857 -> Cecil` 재발
  - 일반화: 단어 blacklist가 아니라 character-parenthetical bridge의 대상 title이 작품 페이지/공식 URL/캐릭터-작품 링크로 닫히는지 확인
  - positive 보존: 실제 캐릭터 괄호형 bridge가 검색 title/snippet과 본문 캐릭터를 함께 만족하는 `11663540 -> 전 버튜버가 하고 싶은데요`
  - 진행: afterfix21에서 짧은 영어 인명형 title은 post-side work anchor가 없으면 resolved 금지
  - 확인: targeted `20260430_120419_466550`, canary `20260430_121717_430655`, risk `20260430_131615_234022`에서 `11505857` title 없음, `11663540` resolved 유지
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `IMPROVEMENT_REGISTER.md`
- [x] trope-only internal work signal 과복구 축소
  - 완료 기준: `11456200`처럼 단일 캐릭터 + 폼체인지/장르 클리셰만 있는 글은 관련-미확정으로 과복구하지 않음
  - 발견: afterfix20 risk discovery에서 `11456200`이 official title은 없지만 `is_relevant=true + unresolved`로 복구됨
  - positive 보존: `11198715`, `11616838`처럼 복수/구체 캐릭터와 설정/전개 단서가 같이 있는 경우는 관련-미확정 유지
  - 진행: afterfix21에서 trope-only 표면은 강한 plot term 없이는 internal work signal rescue 금지
  - 확인: targeted/canary/risk에서 `11456200` title 없음 및 non-relevant, risk에서 `11198715`, `11616838` 관련-미확정 유지
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `IMPROVEMENT_REGISTER.md`
- [ ] afterfix21 risk resolved 증가분 정성 리뷰
  - 완료 기준: afterfix21 risk `Identified=308` 증가분이 recall 개선인지 false positive 증가인지 `ACCEPT/HOLD/REPROCESS/REJECT`로 분류
  - 발견: afterfix20 risk `Identified=277` 대비 afterfix21 risk `Identified=308`, `Relevant=382 -> 396`
  - 다음 단계: resolved 저근거, character_parenthetical, locked rescue, single_candidate_unresolved_promoted 표본을 우선 리뷰 패킷으로 추출
  - 상세: `VERIFICATION_RESULTS.md`, `HISTORY.md`
- [ ] server-poc full run known-case mismatch 재처리 비교
  - 완료 기준: `20260505_214349_324347`의 `11718111`, `11663540`, `11616838`, `11631298`를 현재 코드로 단건 재처리해 server result와 비교
  - 발견: server result에서 `11718111 -> 정신분열병` 재발, `11663540` title 없음/multi-work, `11616838` non-relevant, `11631298` related unresolved가 afterfix21 기대와 충돌
  - 다음 단계: 동일 입력 단건 JSONL 생성, 현재 코드 rerun, 차이가 재현되면 `synthetic_primary_frozen`/character bridge/internal work signal 경로로 이슈 분리
  - 상세: `VERIFICATION_RESULTS.md`, `IMPROVEMENT_REGISTER.md`
- [x] server-poc 1차 stratified 정성 리뷰 packet 생성 및 판독
  - 완료 기준: `resolved_with_degraded_majority=12220`, `resolved_with_weak_evidence_text=3223` 표본을 포함한 stratified packet을 만들고 `ACCEPT/HOLD/REPROCESS/REJECT` 판독
  - 발견: full run은 완료됐지만 검색 degraded/weak evidence resolved가 많아 품질 승인은 `REVIEW`
  - 결과: `172`건 packet 판독, `ACCEPT=107`, `HOLD=26`, `REPROCESS=27`, `REJECT=12`
  - 산출물: `server-poc/qualitative_review_packet_20260505_214349_324347_20260522.jsonl`, `server-poc/qualitative_review_packet_20260505_214349_324347_20260522.md`, `server-poc/qualitative_review_adjudication_20260505_214349_324347_20260522.md`
  - 표준화 산출물: `qualitative_review/20260505_214349_324347/sample_manifest.json`, `review_packets.jsonl`, `review_labels.jsonl`, `pattern_summary.md`, `gate_decision.md`, `action_queue.md`
  - 상세: `VERIFICATION_RESULTS.md`, `IMPROVEMENT_REGISTER.md`
- [x] server-poc deterministic random control 100건 생성 및 1차 라벨링
  - 완료 기준: 전체 `104502` result row에서 기존 172건과 post_id 중복 없이 seed 고정 random control `100`건을 추출하고 같은 `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING` schema로 라벨링
  - 결과: random control `100`건, `ACCEPT=86`, `HOLD=14`, `REPROCESS=0`, `REJECT=0`, `INFO_MISSING=0`
  - seed: `20260505_214349_324347:random_control:v2_unbiased`, selected row index range `1002~100830`
  - 산출물: `qualitative_review/20260505_214349_324347/random_control_manifest.json`, `random_control_packets.jsonl`, `random_control_labels.jsonl`, `random_control_summary.md`
  - 상세: `VERIFICATION_RESULTS.md`, `qualitative_review/20260505_214349_324347/gate_decision.md`
- [x] server-poc random control v3 1,000건 stratified 확대
  - 완료 기준: 10만 건 품질 기준선용 random baseline을 최소 1,000건으로 확대하고 row-index decile/base decision state 기준 층화, worker/search_degraded/slang 분포를 manifest에 기록
  - 결과: `1000`건, `ACCEPT=889`, `HOLD=2`, `REPROCESS=109`, `REJECT=0`
  - seed: `20260505_214349_324347:random_control:v3_1000_stratified`
  - 산출물: `qualitative_review/20260505_214349_324347/random_control_v3_manifest.json`, `random_control_v3_packets.jsonl`, `random_control_v3_labels.jsonl`
- [x] server-poc 2차 확대 정성 리뷰
  - 완료 기준: 1차 판독에서 `HOLD/REPROCESS/REJECT`가 나온 유형을 중심으로 degraded-majority/generic-title/relevant-without-title/false-negative 후보를 추가 추출해 유형별 오판율을 산출
  - 결과: high-risk expansion `5000`건, `ACCEPT=2041`, `HOLD=1528`, `REPROCESS=1430`, `REJECT=1`, `INFO_MISSING=0`
  - merged 결과: `6172`건, `ACCEPT=3037`, `HOLD=1556`, `REPROCESS=1566`, `REJECT=13`, `INFO_MISSING=0`
  - 산출물: `qualitative_review/20260505_214349_324347/round2_manifest.json`, `round2_packets.jsonl`, `round2_labels.jsonl`, `round2_summary.md`
  - large-scale aliases: `high_risk_expansion_manifest.json`, `high_risk_expansion_packets.jsonl`, `high_risk_expansion_labels.jsonl`, `pattern_coverage_summary.md`, `expanded_gate_decision.md`
  - 발견: Round 2에서도 generic bridge, weak-evidence strong resolution, degraded-search approval, alias recall loss가 반복되어 자연어 품질 승인은 계속 `NO-GO`
  - 상세: `VERIFICATION_RESULTS.md`, `server-poc/qualitative_review_adjudication_20260505_214349_324347_20260522.md`, `qualitative_review/20260505_214349_324347/gate_decision.md`
- [x] server-poc Round 3 P0/P1 후보 재검색/재판정
  - 완료 기준: Round 2 `HOLD/REPROCESS/REJECT` 대표 유형을 현재 코드로 targeted re-run 또는 re-search/re-judge하고, 새 systemic failure pattern이 추가되는지 확인
  - 준비 완료: P0/P1 대표 후보 `584`건과 targeted input `584`건 생성
  - 준비 산출물: `qualitative_review/20260505_214349_324347/round3_p0p1_manifest.json`, `round3_p0p1_candidates.jsonl`, `round3_targeted_input.jsonl`, `round3_issue_templates.md`, `round3_action_plan.md`
  - readiness: `round3_search_shard_audit_latest.json` 기준 search shards `8/8` OK, 기본 vLLM endpoint `http://10.20.0.101:8000/v1/models` HTTP 200
  - 실행 상태: 초기 `--parallel 8` run은 checkpoint `116`건, failed `0`까지 보존하고 중단. 남은 `468`건은 당시 기준 `--parallel 32`, `MCP_SHARD_COUNT=8`로 재개.
  - 최신 기준: Gemma 4 4B 후속 재확인/재처리는 `MCP_SHARD_COUNT=36` 및 shard audit `36/36`을 기본 검증으로 맞춘다. `--parallel`은 상한으로 두고 manifest의 `effective_parallel`을 검증한다.
  - shard 확인: 현재 Docker WARP/MCP stack은 8 shard(`3333..3340`)만 live. `3341..3364`는 이전 Python 점유가 아니라 리스너 부재이며, 중단된 8병렬 run의 stale child 2개는 정리.
  - 다음 대형 실행 보정: true 32-search-shard가 필요하면 `--no-auto-up-shards`를 제거하고 `MCP_SHARD_COUNT=32`로 `expert_main.py`의 `tools/warp_shards.py up --count 32` 경로를 사용.
  - 실행 결과: `584`건 완료, failed `0`, duplicate post id `0`; `round3_after_merged_result.json`, `round3_after_packets.jsonl`, `round3_after_labels.jsonl`, `round3_after_summary.md`, `round3_after_gate_decision.md` 생성
  - after labels: `ACCEPT=179`, `HOLD=268`, `REPROCESS=137`, `REJECT=0`
  - 우선 대상: `generic_parenthetical_bridge`, `weak_evidence_but_strong_resolution`, `worker_or_shard_degraded_window`, `slang_db_store_block_pending_family_noise`, `round2_false_negative_recall`
  - gate: 최근 2개 round에서 새 실패 유형이 거의 나오지 않고 P0/P1 queue가 정리될 때까지 semantic decision quality는 `NO-GO`
  - 상세: `qualitative_review/20260505_214349_324347/action_queue.md`, `pattern_summary.md`, `gate_decision.md`
- [ ] server-poc Round 3 잔여 HOLD/REPROCESS 큐 축소
  - 완료 기준: Round 3 after-rerun combined `HOLD=288`, `REPROCESS=101`을 pattern별로 줄이거나 explicit quarantine으로 고정하고, post-fix random baseline + P0/P1 regression을 재실행
  - 주요 잔여: `generic_common_surface HOLD=88`, `alias_recall_loss_false_negative HOLD=48/REPROCESS=48`, `slang_db_alias_subtype HOLD=80/REPROCESS=10`, `vlm_ocr_evidence_gap REPROCESS=36`, `worker_shard_degraded_window HOLD=52/REPROCESS=32`
  - action 큐: `round3_after_queue_re_search.jsonl` `153`건, `round3_after_queue_re_judge.jsonl` `88`건, `round3_after_queue_slang_db_review.jsonl` `80`건, `round3_after_queue_human_review.jsonl` `48`건, `round3_after_queue_re_run.jsonl` `36`건
  - 재처리 입력: `round3_after_rerun_input_re_search_re_run.jsonl` `189`건 (`re_search` + `re_run`)
  - 재처리 결과: `round3_after_rerun_re_search_re_run_result.json` `189`건 완료, failed `0`; `round3_after_rerun_labels.jsonl` `ACCEPT=16`, `HOLD=72`, `REPROCESS=101`
  - combined 최신 상태: `round3_after_rerun_combined_summary.md`, `ACCEPT=195`, `HOLD=288`, `REPROCESS=101`, `REJECT=0`, 잔여 non-ACCEPT `389`
  - quarantine 분리: `round3_after_rerun_quarantine_summary.md`, 승인 제외 `389`건, `P0=91`, `P1=298`
  - exit action: `fresh_search_with_direct_evidence_or_demote=125`, `fix_judgment_guard_or_manual_relabel=88`, `complete_slang_db_state_review=87`, `manual_adjudication=59`, `rerun_with_required_input_modality_or_quarantine_disabled_modality=30`
  - 상세 분석: `round3_after_residual_analysis.md`, `round3_after_residual_analysis.json`
  - gate: hard `REJECT`는 `0`으로 내려갔지만 잔여 non-ACCEPT `389` 때문에 semantic decision quality는 계속 `NO-GO`
- [x] server-poc Round 3 P0/P1 후보 세트 준비
  - 완료 기준: action queue의 `REJECT/REPROCESS/HOLD`를 pattern별로 묶고, all-REJECT + pattern별 대표 후보와 재실행 입력 JSONL을 생성
  - 결과: `584`건 선정, `REJECT=13`, `REPROCESS=442`, `HOLD=129`; targeted input도 `584`건, post_id 중복 `0`
  - pattern coverage: `generic_common_surface`, `weak_evidence_strong_resolution`, `alias_recall_loss_false_negative`, `slang_db_alias_subtype`, `vlm_ocr_evidence_gap`, `worker_shard_degraded_window`, `boundary_domain_drift` 각 `100`건
  - 상세: `qualitative_review/20260505_214349_324347/round3_action_plan.md`, `round3_issue_templates.md`
- [ ] 캐릭터 괄호형 bridge recall 손실 개선
  - 완료 기준: `주서연(전 버튜버가 하고 싶은데요)`처럼 검색 snippet/title에 character(work) bridge가 잡히면 resolved하고, 검색 결과가 누락되면 non-relevant로 흔들리지 않도록 RESEARCH/HOLD 또는 추가 query로 보완
  - 발견: `11663540`은 canary/targeted run마다 `전 버튜버가 하고 싶은데요` resolved, unresolved, non-relevant가 변동
  - 다음 단계: character-only + 장르/플랫폼 query 후보를 보강하고, 검색 결과 누락 시 RESEARCH queue로 보내는 정책 검토
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`, `VERIFICATION_RESULTS.md`
- [ ] 개선 전후 자동 테스트/비교 문서 생성 루틴 도입
  - 현재 상태: 지침 추가 완료, afterfix11 vs afterfix12 parallel36 수동 비교 문서 생성 완료, 2026-04-28부터 품질 개선 후 200건 canary와 1,000건 risk discovery 자동 진행을 기본 정책으로 격상, 전용 자동 비교 도구는 미구현
  - 완료 기준: 개선 작업 후 200건 canary, 1,000건 risk discovery, baseline/improved run 감사와 비교 Markdown/JSON이 자동 생성되고 `VERIFICATION_RESULTS.md`에 링크됨
  - 상세: `CHECKLIST.md`, `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`, `DEV_TODO.md`, `FEATURE_IMPROVEMENT_TODO.md`
- [ ] 같은 입력의 소량 재처리로 검색 저하율 비교
  - 현재 상태: 2차 200건 canary는 안정성 `GO` (`20260427_121338_563339`, checkpoint `200/200`, failed `0`, missing `0`)
  - 남은 상태: 품질은 `REVIEW`; late search budget 추가 후 검색 오류/timeout/infra no-result와 long-tail 상위 post는 200/1,000/10,000건에서 계속 비교 필요
  - 완료 기준: 200건 canary, 1,000건 risk discovery, 10,000건 validation 표본에서 `search_upstream_zero`, `search_degraded_detected`, `search_timeout` 변화 기록
  - 상세: `VERIFICATION_RESULTS.md`
- [ ] 쿼리 확장 gate 개선 후 대형 샘플 재처리
  - 현재 상태: afterfix12 P0 title/alias gate targeted 검증 및 36병렬 200건 canary 완료
  - 다음 단계: afterfix12 120건 리뷰 판독, `폴랩/망교성/화귀/언니약혼` long-tail targeted, 1,000건 risk discovery 재실행
  - 완료 기준: 확정 약칭/웹소설 도메인 표면어는 회수율 개선, 잡담/비소설 제목은 false positive 증가 없음
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`
- [ ] 검색 실패 post 재처리 queue 설계
  - 완료 기준: 검색 실패/저하가 많은 post id 목록을 CSV/JSON으로 추출
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`
- [ ] headless fallback 효율 점검
  - 완료 기준: `headless_used`, `headless_count`, `headless_error`별 성공률 리포트
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`

## P1 - Slang DB 품질

- [x] 20k run 기준 slang DB audit
  - 결과: `slang_insight=1817`, 보정 후 저장 후보 `532`, 오염성 alias `0`
- [ ] `unclear_canonical_alias` 차단 후보 review queue 분리
  - 완료 기준: 실제 약칭 가능성이 높은 후보와 차단 유지 후보가 분리됨
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`
- [ ] 대시보드에서 `examples.bucket`, `family_aliases` 노출
  - 완료 기준: `titles[].slang/pending` 외 보류/가족 alias가 화면에서 확인됨
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`
- [ ] `pending` 하위 버킷 설계
  - 완료 기준: `pending_alias`, `secondary_reference`, `comparison_only` 같은 구분 도입 여부 결정
  - 상세: `FEATURE_IMPROVEMENT_TODO.md`

## P2 - 문서/운영

- [x] `docs/devs` 문서 허브 생성
- [x] 개선 레지스터/체크리스트/히스토리 규격화
- [x] 샘플링/병렬 테스트 규모 기준 문서화
  - 상세: `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- [x] scan result directory 리뷰 지침 추가
  - 완료 기준: 지침 작성 모드와 실제 런 리뷰 모드 분리, 증거 등급, GO/REVIEW/NO-GO gate, 실패 taxonomy, action queue, systemic issue dedupe 규칙 문서화
  - 상세: `SCAN_RESULT_REVIEW_GUIDE.md`, `OPERATION_QUALITY_CHECKLIST.md`, `IMPROVEMENT_REGISTER.md`
- [x] 테스트 런 자연어 품질 검증 루프 지침 추가
  - 완료 기준: 자동 감사와 semantic decision quality를 분리하고, random control + high-risk bucket, 라벨 체계, packet 필드, 반복 round, 종료 조건, 산출물 규격을 문서화
  - 결과: `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md` 추가, `SCAN_RESULT_REVIEW_GUIDE.md`, `OPERATION_QUALITY_CHECKLIST.md`, `CHECKLIST.md`에 gate 반영
  - 상세: `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `SCAN_RESULT_REVIEW_GUIDE.md`, `OPERATION_QUALITY_CHECKLIST.md`
- [x] 자연어 리뷰 packet/label 생성 도구 보강
  - 완료 기준: `qualitative_review/<run_id>/sample_manifest.json`, `review_packets.jsonl`, `review_labels.jsonl`, `pattern_summary.md`, `gate_decision.md`, `action_queue.md`를 자동 생성
  - 결과: `tools/build_qualitative_round2_review.py` 추가. result JSON을 스트리밍해 Round 2 failure-pattern bucket, packet, label, summary, gate, action queue를 생성
  - 주의: 현재 스크립트는 Round 2 전용이며 random control v2 생성은 기존 산출물을 재사용한다. 다음 일반화 때 run id/source path/round schema를 CLI화한다.
  - 상세: `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `IMPROVEMENT_REGISTER.md`
- [ ] 새 기능 변경 시 PR/commit 전 문서 갱신 확인 루틴 도입
  - 완료 기준: `CHECKLIST.md` 항목이 실제 변경 흐름에 사용됨
  - 상세: `DEV_TODO.md`
- [ ] README에서 `docs/devs` 링크 추가 검토
  - 완료 기준: 사용자가 개발 운영 문서를 바로 찾을 수 있음
  - 상세: `DEV_TODO.md`
- [ ] server-poc 산출물 패키지 규격 보강
  - 완료 기준: 서버 테스트 디렉터리에 result/logs 외 manifest, checkpoint JSONL, run audit JSON, comparison/review packet이 함께 포함됨
  - 발견: `server-poc`에는 result JSON, logs, WARP status, `slang_db` snapshot은 있으나 manifest/checkpoint/run audit/review packet이 없어 `SCAN_RESULT_REVIEW_GUIDE.md` 기준 Strong evidence가 부족
  - 상세: `IMPROVEMENT_REGISTER.md`, `VERIFICATION_RESULTS.md`
- [ ] 10만 건 semantic 잔여 큐 `391`건 정리
  - 완료 기준: `v81_current_remaining_action_after_v80_vlm_manifest.json`의 `HOLD=322`, `REPROCESS=67`, `INFO_MISSING=2`를 action별로 재처리하거나 승인 제외 quarantine으로 고정
  - 우선순위: `re_search=127`, `re_judge=72`를 합친 rerun combined `199`건과 `slang_db_review=87`, `human_review=105`, `browser_target=27`을 분리 처리
  - 다음 단계: post-fix random baseline `500~1000`건과 P0/P1 high-risk regression 재실행
  - 기준 문서: `qualitative_review/20260505_214349_324347/current_100k_fixable_gap_bug_summary_ko_20260527.md`, `qualitative_review/20260505_214349_324347/v78_current_remaining_action_summary_ko.md`
  - 2026-05-26 추가 확인: `v63_character_virtual_battle_unresolved_guard_p36_20260526.json` 6건 targeted run 완료, `ACCEPT=5`, `HOLD=1`; `11663540`은 `non-relevant/title null/none`으로 닫혔지만 전체 gate는 계속 `NO-GO / REVIEW-LOCKED`
- [x] VLM/OCR 이미지 lazy-load 누락을 캡처 도구에서 직접 로딩 확인하도록 보강
  - 확인 사례: Browser `iab`로 `11097334` 확인 시 전체 image `98`, pending/lazy/placeholder `41`, 스크롤 후 본문 pending `32`
  - 조치: `tools/capture_vlm_ocr_browser_review_cli.py`에서 본문 첨부 selector를 좁히고 평가 전 `scrollIntoView`/대기 루프를 추가
  - 검증: 새 기준으로 `11097334` 본문 첨부 `3`, 스크롤 전 loaded `2/3`, placeholder `1`; 스크롤/대기 후 loaded `3/3`, placeholder `0`
  - 남은 기준: packet에 screenshot path, loaded image count, pending image count, visual observation을 남기고 placeholder가 남으면 Strong evidence 금지
- [x] VLM/OCR 브라우저 target/closure builder에 본문 이미지 gate 반영
  - 조치: `build_vlm_browser_targets_from_review.py`는 캡처 도구와 같은 selector를 사용
  - 조치: `build_qualitative_exit_action_closure.py`는 flat/nested image state를 모두 읽고 image gate 실패 시 `ACCEPT` 차단
  - 검증: `tests.test_exit_action_closure` 통과, `vlm_ocr_all_browser_gate_v2_20260526_manifest.json` 생성
- [ ] VLM/OCR quarantine `30`건을 새 selector/scroll gate 기준으로 재캡처하고 재라벨
  - 완료 기준: `vlm_ocr_evidence_gap` 잔여가 `REPROCESS=0`이 되거나 명시 quarantine으로 고정
- [ ] VLM/OCR direct image title bucket P0/P1 regression
  - 완료 기준: `explicit_text|cover_title`, `title_role=work_title`, `promotion_eligible=true` 단일 작품 표면이 검색 URL 부족만으로 `noise`가 되지 않고, 배경 목록/타매체/다중 제목 이미지는 과확정되지 않음
  - 확인된 targeted fix: `11718117` v275에서 `is_relevant=true`, `official_title=아카데미의 피해자`, `heretic_url=null`, `direct_image_explicit_title_rescued`
  - 남은 기준: official detail URL evidence는 title correctness와 분리하고, P0/P1 high-risk regression 전까지 전체 semantic gate는 `NO-GO / REVIEW-LOCKED`
- [ ] final semantic reread / official URL synopsis mismatch P0/P1 regression
  - 완료 기준: 표현 오타/축약/띄어쓰기 붕괴를 packet-local 재해독 힌트로만 쓰고, `surface_paraphrase`/`semantic_seed_review`가 있는 context-only 글은 후단 search/alias rescue로 작품명 재승격되지 않으며, 같은 URL 검색 title/snippet이 직접 작품명을 지지하는 공식 상세 URL은 fetch 시놉시스 제목 때문에 과삭제되지 않음
  - 확인된 targeted fix: `11718091` v282에서 `23센줄 -> 23세인 줄` 의미 해석 후 `official_title=null`, `title_resolution_state=context_only`; `11718097` v282에서 `망겜의 힐러`와 `https://m.munpia.com/novel/detail/328421` 회복
  - 도구화 확인: v283에서 Round2 review builder가 `final_semantic_reread_missing_for_semantic_seed`, `final_semantic_reread_reviewed`, `official_url_synopsis_or_branding_mismatch` bucket을 생성하고, v282 `11718097`을 `official_url_synopsis_or_branding_mismatch` / `ACCEPT/no_action`으로 분리함
  - 남은 기준: post-fix random baseline과 `weak_evidence_strong_resolution`, `reason_decision_contradiction`, `official_url_synopsis_or_branding_mismatch` bucket 확대 확인 전까지 전체 semantic gate는 `NO-GO / REVIEW-LOCKED`
- [x] Decoder `KNOWN_ABBREVIATIONS` 미검증 rescue 차단
  - 발견: registry hit만으로 `known_abbreviation_unverified` 0.80 rescue 후보가 되고 LLM 비제목 판단을 우회할 수 있었음
  - 조치: 검색/공식 제목 근거 없는 등록 약칭은 hint-only로 남기고 `best_title/best_score`를 세우지 않음
  - v478 추가 조치: `_resolved_mappings` suspected, high-fit interpretation, weak thematic guard도 registry pair 단독으로 열리지 않게 함
  - 검증: `tests.test_decoder_known_abbreviation_guard` 9건 통과, py_compile 통과
  - 산출물: `qualitative_review/20260528_141006_620986/v477_decoder_known_abbrev_unverified_guard_review_ko.md`, `qualitative_review/20260528_141006_620986/v478_decoder_known_abbrev_suspected_guard_review_ko.md`
- [ ] hardcoded alias registry-only High/lock 예외 축소
  - 완료 기준: `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`가 registry hit만으로 final title, `High`, stability/lock, Arbiter guard exception을 열지 않음
  - v479 조치: Agentic direct promotion, stability, title lock에는 `visible alias surface + semantic no-work 차단 + 독립 work anchor` 조건을 적용했다.
  - v480 조치: Agentic `_has_alias_title_support()`와 `_collect_title_support_kinds()`도 등록 약칭 surface만으로 강한 support나 `post_main_mention`을 만들지 않게 했다.
  - v481 조치: Arbiter `multi_work`, `meme/noise`, `low-confidence`, title veto exception에도 `_has_curated_alias_guard_exception()` 조건을 적용했다.
  - 다음 단계: Arbiter actual decision-path 테스트를 추가하고, `_has_strong_title_support()` / `_has_official_title_evidence()` 반환 구조 의심을 별도 P1로 정리한다.
  - 보존해야 할 positive: `담텔기`처럼 work_discussion, 회차/스포/작가의 말/캐릭터 맥락이 있는 케이스
  - 계속 막아야 할 negative: `11718080`류 community banter/context-only 케이스
  - 현재 v481: `hardcoded_alias_gate=REVIEW`, blocker `2`, semantic approval `REVIEW-LOCKED`
- [ ] slang DB 외부 매체 alias 오염 검토
  - 완료 기준: `강연금 -> 강철의 연금술사` 같은 외부 매체 alias, composite alias, 일반어 alias를 `saved/blocked/pending/family/noise` 상태별로 분리하고 quality approval에서 제외
- [ ] Gemma 4 4B 후속 재실행은 `MCP_SHARD_COUNT=36`과 shard audit `36/36`을 runtime 검증으로 분리하되, 새 소규모 명령은 `--parallel min(input_count,36)`를 권장하고 manifest의 `effective_parallel`을 검증
  - 완료 기준: 실행 전 Python 점유와 shard `36/36` 상태를 기록하고, `requested_parallel`은 상한/명령 입력, `effective_parallel`은 입력 수 또는 healthy endpoint 수 이하인지와 `--slang-db-path` 경로가 실제 qualitative review snapshot을 가리키는지 확인
  - 2026-05-26 확인: 실행 전 관련 `expert_main|llm_batch|warp_shards` Python 점유 없음, `/v1/models`는 `bg-digitalservices/Gemma-4-E4B-it-NVFP4`, Docker shard `1..36` live, v63 targeted run은 `--parallel 36`으로 완료
  - 2026-05-27 현재 확인: `/v1/models`는 연결 실패, `:8000`은 listener 없이 `SYN_SENT`만 확인되어 `v81` rerun combined `199`건 재실행은 endpoint 복구 후 진행
  - 2026-06-01 v521 확인: `/v1/models`는 여전히 연결 실패, `:8000` listener 없음, `:3333`만 listener 확인. `Get-CimInstance Win32_Process`와 Docker engine pipe 접근이 권한 거부되어 python command line/compose 상태는 확정 불가. 새 completed VLM/OCR-on source 재실행 전 endpoint와 Docker/shard 접근 복구가 필요하다.
  - v521 문서 동기화: `README.md`, `expert_readme.md`도 `--parallel`은 max이고 small run은 `effective_parallel`로 검증한다고 안내하도록 수정했다.
- [x] BatchContextMemory 저근거/generic inline alias 반복 승격 차단
  - 발견: `logs/expert_run_20260527_000930_077939_W12.log`에서 `카드아카 -> 카드 아카데미 1타강사`가 `일반명사형 약칭 즉시등록 보류` 후 `count=2`로 승격됨
  - 완료 기준: `generic_inline_alias` 또는 저근거 seed는 structured slang support 없이 pending count 2만으로 resolved memory에 승격되지 않음
  - 검증: `tests.test_batch_context` 7건 통과, Gemma 4 4B `expert_main.py --parallel 36` v72 targeted 재실행에서 `BatchMem: 약칭 승격 '카드아카'` 로그가 사라지고 `약칭 승격 보류 ... reason=generic_inline_alias`만 남음
  - 기준 문서: `qualitative_review/20260505_214349_324347/current_100k_fixable_gap_bug_summary_ko_20260527.md`
  - 상세 산출물: `qualitative_review/20260505_214349_324347/batchmem_generic_inline_alias_seed_guard_ko_20260527.md`
- [x] review labeler의 direct evidence/degraded action routing 보정
  - 발견: `generic_parenthetical_bridge` bucket에서 공식 상세 근거가 있는 row도 모두 `HOLD/re_judge`로 남고, `degraded_queries: 0` 필드명만으로 search degraded가 true가 될 수 있음
  - 조치: 직접 작품 근거가 강하고 degraded가 없으면 ACCEPT 가능, degraded가 있으면 `HOLD/re_search`, generic bridge 자체 문제는 `HOLD/re_judge`로 분리
  - 검증: `tests.test_qualitative_review_packet_tools` 6건 통과, v67 19건 재적용 결과 `ACCEPT=7`, `HOLD=12`, actions `no_action=7`, `re_search=7`, `re_judge=5`
  - 상세 산출물: `qualitative_review/20260505_214349_324347/review_labeler_direct_evidence_degraded_routing_ko_20260527.md`
- [x] v523 issue-focused seed closure 잔여 처리
  - 범위: 10만 전체 semantic approval이 아니라 10만 partial run에서 간추린 known-bad/high-risk seed closure
  - 확인: `v422` 11건 follow-up은 run completed/flushed/pending/failed `11/11/0/0`, requested/effective parallel `36/11`, VLM/OCR ready, no lifecycle로 통과
  - P0 닫힘: `11718083` memory query/unresolved work request의 `PickvelIdentity subtype` validation error는 v524에서 코드 보정 + 단건 live rerun으로 `ACCEPT/no_action`
  - P1 닫힘: `11718118`/`11718091` reason/discussion_type mismatch는 v525 코드 보정 + 2건 live rerun으로 `ACCEPT/no_action`
  - P1 닫힘: `11718069`/`11718076` browser visual artifact 보강은 v526에서 screenshot/visual observation으로 `ACCEPT/no_action`
  - deferred: `v284` 98 row 후보는 open shard `32/36`, required `36`으로 preflight `NOT_READY`이며 seed closure 완료와 별개로 둔다.
  - 산출물: `qualitative_review/20260528_141006_620986/v523_issue_focused_scope_and_review_ko.md`, `qualitative_review/20260528_141006_620986/v525_reason_discussion_type_rejudge_review_ko.md`, `qualitative_review/20260528_141006_620986/v526_browser_visual_closure_review_ko.md`, `qualitative_review/20260528_141006_620986/v526_issue_focused_action_queue_ko.md`
- [ ] v284 98-row expansion 재개 조건 확인
  - 조건: full shard `36/36` readiness 또는 worker/shard policy 재결정
  - 주의: 이 expansion은 10만 semantic approval이 아니라 후속 targeted expansion이다.
- [x] verifier cap 이후 D4 55-row integrated VLM/OCR canary 재실행
  - 완료 기준: `expert_main.py --parallel 16 --vlm on --ocr on`으로 55건 completed/pending/failed `55/0/0`, VLM/OCR semantic gate `READY`, verifier runaway 미재현
  - 현재 증거: D4는 `--parallel 16`으로 completed/pending/failed `30/2/0`에서 verifier `acc_chars=121,531` runaway를 확인해 중단했고, D5 5건 suspect subset은 cap 이후 `5/0/0`, 최대 `acc_chars=6,363`으로 완료
  - D10 8-row patch target canary는 `--parallel 16`, VLM/OCR on, completed/pending/failed `8/0/0`으로 완료했고 `11682781` direct URL 유지 및 `11652175` known-title update alias 회수를 확인
  - D11 55-row integrated canary는 `--parallel 16`, VLM/OCR on, `--slang-db off`, `MCP_HEALTH_INCLUDE_SEARCH=1`로 completed/flushed/pending/failed `55/55/0/0`, VLM/OCR semantic gate `READY`, search health `16/16 OK`, `large_run_complete=true`로 완료
  - 주의: D11은 integrated runtime/target acceptance 근거이며 full scan approval 근거가 아니고 semantic quality는 계속 `REVIEW-LOCKED / NO-GO`
- [x] 검증 LLM/`expert_main.py` 운영 병렬도 `--parallel 16` 기록 규칙 반영
  - 기준: 명령의 `requested_parallel=16`과 manifest의 `effective_parallel`을 함께 기록
  - 소규모 입력은 `effective_parallel <= input_count`로 줄어드는 것이 정상이며, 이 경우도 요청 병렬 16 준수로 기록
- [x] D10 direct URL / known-title update alias patch target 재검증
  - 결과: `out\recall_gate_canary\patch_targets_D10_vlmocr16_20260620_0203.json`
  - 로그: `logs\expert_run_20260620_020258_749960.log`
  - run meta: `requested_parallel_raw=16`, `requested_parallel=16`, `effective_parallel=8`, VLM/OCR semantic gate `READY`
  - `--slang-db off`로 실행했으며 slang DB write-back 없음
- [ ] D11 잔여 title quality 후보 P1 정리
  - 후보: `11657008` 플랫폼명 `노벨피아` title 잔존, `11698889` OCR typo `푸림마조`, `11661893` wrong-work title
  - 기준: 플랫폼명/브랜딩 title과 OCR typo title은 final official_title로 남지 않고, wrong-work URL/title은 seed expected 또는 unresolved로 분리
  - 주의: 별도 코드 변경 시 사용자 지시대로 실제 `expert_main.py --parallel 16` targeted canary까지 돌려 효과를 확인

## 2026-06-22 completed779 Loop 2 후속 TODO

- [x] completed779 post-fix-adjusted active queue `25`건 Loop 2 input split 생성
  - 산출물: `out/completed779_improvement_goal_20260622/inputs/reimprovement_loop2_text_url_comment.jsonl` (`8` rows), `out/completed779_improvement_goal_20260622/inputs/reimprovement_loop2_image_ocr.jsonl` (`17` rows)
- [x] Loop 2 text/url/comment canary 완료
  - 결과: `out/expert_result_20260622_201044_448457.json`, rows `8/8`
  - 주의: direct Naver/Bing fallback 사용, degraded-provider evidence
- [x] Loop 2 image/OCR canary 완료
  - 결과: `out/expert_result_20260622_201630_167085.json`, rows `17/17`, VLM/OCR Semantic Gate `READY`
  - 주의: direct Naver/Bing fallback 사용, degraded-provider evidence
- [x] Loop 2 combined compare 및 remaining queue 생성
  - compare: `out/completed779_improvement_goal_20260622/compare/reimprovement_loop2_combined_compare.json`
  - remaining queue: `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue.json`, `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue_ko.md`
- [ ] completed779 Loop 3 candidate/comment recall 잔여 `8`건 정리
  - 대상 post_id: `11695623`, `11706856`, `11708442`, `11716478`, `11697241`, `11697255`, `11702072`, `11703624`
  - 기준: candidate ledger/HOLD/human_review/unresolved_matchable 보존을 강화하되 post_id/title 하드코딩 금지
  - gate: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`
- [x] completed779 Loop 3+ 운영을 Hermes Continuous Goal로 재정의
  - 산출물: `goal.md`, `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`
  - 핵심: 7축 Council role, subagent fan-out, 모델/툴 다양성, queue-empty 또는 명시 HOLD/human_review/quarantine 전까지 반복
  - 주의: subagent 결과는 승인 근거가 아니라 메인 Codex의 재확인 입력

## 2026-06-22 completed779 source-correctness refresh 후속 TODO

- [x] source-correctness refresh 정상 shard canary 완료
  - shard audit: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/search_shard_audit_after_restore.json`, `ok=2/2`, direct fallback `false`
  - text/url/comment: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_text_result.json`, `14/14`
  - image/OCR: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_image_ocr_result.json`, `25/25`, VLM/OCR `READY`
  - compare: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/compare/source_correctness_refresh_compare.json`, `39/39`, movement `resolved_expected_title_and_url=6`, `review=12`, `url_lint_preserved=21`
  - next queue: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_next_queue.json`, rows `0`
  - 주의: targeted refresh 완료이며 semantic approval은 계속 `REVIEW-LOCKED`, full scan approval `false`
- [x] completed779 Hermes 다음 expansion queue 생성
  - 후보 축: `판초법사 -> 판초우의의 마법사` alias recall, `괴담 호텔 탈출기` character/setting cluster, OCR explicit title + search absent 분리, classic/cross-domain OCR pollution, source-local alias conflict guard
  - seed source: source-correctness refresh residual `review=12`, `url_lint_preserved=21`, native-web non-ACCEPT unused pool
  - 기준: 기존 39건 단순 재실행 금지, post_id/title 하드코딩 금지, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`
  - 산출물: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue.json`, rows `44`, main `24`, controls `20`
- [x] completed779 Hermes Loop 5 canary/compare 실행
  - text/url/comment input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_text_url_comment.jsonl`, rows `19`
  - image/OCR input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_image_ocr.jsonl`, rows `25`
- [ ] completed779 Hermes Loop 5 residual fix loop 실행
  - hard-fail next queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue.json`, rows `4`
  - operational residual queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_operational_residual_queue.json`, rows `24`
  - 핵심: `11694064`/`11710033` 판초 alias consistency, `11698880` title/body conflict HOLD, `11702055` character/setting cluster, `11716480` OCR/search candidate pruning
  - [x] postfix1 slice: subagent council 검토를 반영해 `11698880` source/url hygiene expected-title conflict를 final public promotion에서 차단
    - code: `apply_judge_seed_hygiene_expected_title_guard`
    - canary: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_postfix1_11698880_image_ocr_result.json`, `1/1`
    - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop5_postfix1_11698880_compare.json`, movement `url_lint_preserved=1`
  - [ ] upstream orchestration: `11698880`은 runtime 내부에서 아직 `가챠펑크 -> 가챠 중독자의 퓨전펑크 생활`로 강하게 끌리므로 title/body multi-candidate HOLD를 primary selection 전에 일반화
  - [ ] postfix1 next queue `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue_postfix1.json`, rows `5`를 다음 loop 입력에 반영

## 2026-06-23 completed779 Hermes Loop 7 TODO

- [x] completed779 Loop 7 broader residual queue 생성
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue.json`
  - report: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue_ko.md`
  - rows `36`, main `16`, controls `20`, text/url/comment `16`, image/OCR `20`
  - buckets: `under_resolved=3`, `under_resolved_false_negative=8`, `wrong_relevance=5`, `operational_residual_review=12`, `operational_residual_url_lint_preserved=8`
- [x] Loop 7 text partial canary와 blocker 증거 기록
  - first run `20260623_022342_639179`: completed/flushed/pending/failed `12/11/1/0`, ordered flush blocked
  - resume run `20260623_024758_871942`: completed/flushed/pending/failed `2/0/2/0`, ordered flush blocked
  - partial combined: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_partial_combined_result.json`, rows `14`
  - blocker report: `out/completed779_improvement_goal_20260622/hermes_loop7_text_runtime_blockers_ko.md`
- [x] `11702087` 1차 generalized fix 반영
  - `agentic_pipeline.py`: `_context_to_output` early `flags` `UnboundLocalError` 수정
  - `orchestrator.py`: dense character/setting cluster가 `semantic_seed_review` 조기 종료를 우회할 수 있게 보강
  - `orchestrator.py`: `그래서` 등 Korean connective/question lead token을 low-specificity로 보고 Phase34.5가 재추가하지 않게 보강
  - 검증: `tests.test_title_lead_search_inferred_guard`, `67 tests OK`
- [x] `11702087` downstream guard P0 fix
  - fix8: postprocess 내부는 `괴담 호텔 탈출기`/`https://novelpia.com/novel/102155`를 rescue했지만 `candidate_audit` precision seed guard가 `source_url_hygiene + garbage_title` row를 다시 demote했다.
  - fix9: `source_url_hygiene` seed bucket은 precision demotion이 아니라 hygiene lint로 처리하게 수정했고, single-row canary completed/failed/pending `1/0/0`.
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11702087_fix9_result.json`
  - final state: `official_title=괴담 호텔 탈출기`, `heretic_url=https://novelpia.com/novel/102155`, `work_resolution=resolved`, `title_resolution_state=resolved`, `candidate_ledger_status=output_consistency_lint`.
  - caution: runtime `436.8s`; verifier official-detail fast path was unit-verified after the canary, but a full rerun after that performance micro-optimization is not yet done.
- [ ] `11705239` ordered-flush blocker 격리
  - 같은 broad text canary에 바로 재투입하지 말고 single-row runtime root cause 또는 quarantine/resume command 기록 후 진행
- [ ] Loop 7 image/OCR `20`건 canary 실행
  - input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_broader_residual_image_ocr.jsonl`
  - `--vlm on --ocr on --require-vlm-ocr-for-images`, VLM/OCR gate `READY` 별도 기록
- [ ] Loop 7 combined compare 및 next queue 생성
  - text partial, blocker quarantine, image/OCR result를 섞을 때 runtime integrity와 semantic movement를 분리
  - semantic quality `REVIEW-LOCKED`, full scan approval `false` 유지

## 2026-06-23 completed779 Hermes Loop 7 fix1 후속 TODO

- [x] `11705239` ordered-flush blocker를 single-row로 격리하고 과승격 방지 fix를 검증
  - pre-fix hang log: `logs/expert_run_20260623_050058_659227.log`
  - post-fix result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11705239_fix1_result.json`
  - final: `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`
- [x] Loop 7 text combined fix1 `16/16` 생성 및 compare 완료
  - combined: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_combined_fix1_result.json`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_text_fix1_compare.json`
- [~] Loop 7 image/OCR canary 실행
  - broad result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_image_ocr_fix1_result.json`
  - status: `19/20` rows, missing `11716480`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_image_ocr_fix1_compare.json`
- [x] `11716480` postprocess hang root-cause fix
  - broad run `20260623_052157_158066` missing `11716480`
  - single rerun `20260623_061321_455105` reached OCR/Jury title recovery but result/checkpoint not written
  - fix2/fix3: result/checkpoint not flushed
  - fix4: runtime completed but semantic failed as `weak_visual_only`/no OCR title
  - fix5: OCR title recovered but close OCR variant was demoted by source/url hygiene expected-title mismatch
  - fix6: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result.json`, completed/flushed/pending/failed `1/1/0/0`
  - generalized hooks: focused OCR retry for all-weak textless VLM chunks, VLM retry merge of structural fields, close OCR/title variant matching in source/url hygiene guard
  - final: `official_title=여대생 가랑이 사이 무릎 끓은 엄마들`, `heretic_url=null`, movement `url_lint_preserved`
- [x] Loop 7 combined partial compare 생성
  - combined partial: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix1_partial35_result.json`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix1_partial35_compare.json`
  - movement: `candidate_or_human_review_preserved=5`, `resolved_expected_title=1`, `resolved_expected_title_and_url=1`, `review=12`, `still_under_resolved_or_noise=10`, `title_or_url_still_mismatched=2`, `url_lint_preserved=4`
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix1_partial35.json`, rows `12`
- [x] Loop 7 final combined `36/36` compare를 재구성하고 hard queue를 닫음
  - final combined: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix6_final36_result.json`, rows `36/36`
  - fix7 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix7_unwrapped_final36_compare.json`
  - fix7 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix7_unwrapped_final36.json`, rows `2`
  - fix11 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_fix11_short_alias_fetch_next_queue.json`, rows `0` by candidate preservation
  - fix17 semantic improvement: `11706832` resolved `황제폐하가 웹소설 작가임을 숨김` / `https://novelpia.com/novel/385635`
  - fix17 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix17_j11_alias_lock_11706832_compare.json`, movement `resolved_expected_title=1`
  - fix17 next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_fix17_j11_alias_lock_next_queue.json`, rows `0`
  - gate: `semantic_quality=REVIEW-LOCKED`
  - full scan approval: `false`

## 2026-06-23 completed779 Hermes 다음 루프 TODO

- [ ] 새 expansion/source-correctness queue 생성
  - Loop 7 hard queue는 `0`이므로 그대로 재처리하지 않는다.
  - source: completed779 native-web non-ACCEPT residual coverage, stale `review` rows, URL hygiene residuals, source-correctness refresh, or balanced high-risk controls.
  - controls: `11694064`, Loop 1 `wrong_work=9`, `11702087`, `11705239`, `11716480`, `11706832`.
- [ ] subagent/model/tool diversity fan-out를 새 queue 기준으로 재실행
  - 최소 role: candidate/comment, OCR/visual, source/url, search/web, code hook, prompt/orchestration, verification/docs.
  - 가능하면 모델/툴 관점을 분산하되, 메인 Codex가 파일/로그/테스트/웹 근거를 재검증한다.
- [ ] tag-heavy OCR/search query pruning과 official detail URL discovery를 다음 generalized loop 후보로 검토
  - `11716480`은 runtime quarantine이 아니라 URL/source hygiene residual control로 유지한다.

## 2026-06-27 regression-safe grounding Loop 04 TODO

- [x] FIX-3b bracket/post cue guard 구현 및 focused tests 추가
  - `11698897` actual moved to `[림월드]변방계에서 회귀자로 살아남기`.
  - tests: title-lead `76 OK`, candidate audit `58 OK`, rank3 lock anchor `12 OK`.
- [x] FIX-3b golden canary 실행 및 audit/collateral 생성
  - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix3b_bracket_cue_golden_result.json`
  - audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix3b_bracket_cue_golden_audit.json`
  - collateral: `out/regression_safe_grounding_20260626_000008_928006_loop01/collateral/fix3b_bracket_cue_golden_collateral_compare.json`
- [x] Loop 04 report와 Data Analytics artifact 생성
  - report: `docs/devs/loop_reports/LOOP_04_REPORT_20260627.md`
  - artifact: `LOOP 04 Regression-Safe Grounding Audit`
- [ ] Loop 05 priority blocker: `11661857` negative leak
  - current actual: `아카데미 야겜에 빙의했다.`
  - required direction: invented/community scenario should remain HOLD/null unless a direct work bridge exists.
- [ ] Loop 05 relabel/HOLD review: `11694035`
  - current FIX-3b actual is null, but subagent/web evidence suggests `아생갤` may legitimately refer to `아카데미 생존 갤러리`; do not globally block this alias.
- [ ] Continue positive recall bridge queue
  - `11694019`, `11700470`, `11685994`, `11663521`, `11713222`.
  - Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, `slang_db=off`.
## 2026-06-27 - Loop 05 follow-up queue

- [ ] P0 `11661857`: block phonetic/invented dessert + title-form parody from verified-alias official detail promotion (`두쫀쿠` -> `두바이의 쫀득한 여초딩 재벌 9세`).
- [ ] P1 `11663540`: resolve OCR explicit title `전 버튜버가 하고 싶은데요` without accepting `방구석 여신이 되었다`.
- [ ] P1 `11663521`: add source-domain/known-IP bridge for 금서목록/초전자포.
- [x] P1 `11685994`: bridge cover OCR title/author safely reviewed in Loop138; exact official/native-web bridge remains missing, so keep `INFO_MISSING_NATIVE_WEB / HOLD`.
- [ ] P1 `11694019`: bridge `미츄리` + `혼후순결` to `이세계에서 사이비로 살아남기`.
- [ ] P1 `11700470`: bridge OCR phrase/character evidence to `악당 얼굴의 B급 모험자`.
- [ ] P1 `11705231`: prevent `탐식의 재림` from falling to `author_new_work_context`.
- [ ] Review `11713222` native/current-title drift caveat despite FIX-7 audit pass.
- [ ] Do not run panel/full scan until golden semantic and collateral gates are both green.

## 2026-06-27 - Loop 06 FIX-8az follow-up queue

- [x] Close Loop 05 P0 negative leak `11661857` without forcing a public title.
  - FIX-8az audit: `11661857` is `expected_null_respected`.
- [x] Recover `11694019` with a public-work detail lock.
  - targeted source: `fix8av_loop06_search_consistency_11694019_11713222_result.json`
  - final: `이세계에서 사이비로 살아남기`
- [x] Recover `11705231` without `author_new_work_context` demotion.
  - FIX-8az audit: expected `탐식의 재림`, actual `탐식의 재림`.
- [x] Render Data Analytics report artifact.
  - artifact: `LOOP 06 Regression-Safe Grounding Audit`
- [x] Sync Loop 06 report/checklist/history/verification docs.
  - report: `docs/devs/loop_reports/LOOP_06_REPORT_20260627.md`
- [ ] HOLD `11663521` unless a safe external-IP/fanfic official bridge is verified.
  - current audit: expected `어떤 마술의 금서목록 / 어떤 과학의 초전자포`, actual `None`.
- [x] HOLD `11685994` after image/native-web verification; Loop138 could not identify a reliable exact official title URL, so keep public title `null`.
  - current expected is a cover-family unknown title: `교황님(아파하세요) 계열 표지 작품(미상)`.
- [ ] HOLD `11700470` until character/phrase evidence closes to a safe official/public detail.
  - current audit: expected `악당 얼굴의 B급 모험자`, actual `None`.
- [ ] Put `11713222` into golden-label review, not a forced code fix.
  - direct alias/current-work evidence resolves `잘생인방` to `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
  - frozen golden expected `잘생기면 인생이 편하다` appears to be related/previous work evidence.
- [ ] Do not run panel/full scan until golden semantic and collateral gates are both green.
  - current Loop 06 gate: golden `NO-GO`, collateral `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-27 - Goal reopen / not-complete correction

- [x] Correct the prior completion claim.
  - Loop 06 was a targeted golden canary improvement, not full pasted-goal completion.
- [x] Reopen active goal tracking.
  - Reason: Phase 2 queue remains open and panel/full collateral/sweep gates are not closed.
- [ ] Process Phase 2 initial queue from `out\full_post_judge_20260626_000008_928006_phase1\phase2_initial_queue.json`.
  - rows `251`
  - completed targeted runtime slices: `wrong_work_disambiguation=7`, `resolution_promotion_gate=102`, `image_anchor_gate=25`
  - remaining unrun axes: `slang_store_gate=92`, `human_review_boundary=25`
- [ ] Close latest-run source completeness caveat.
  - current source run is partial: `large_run_complete=false`, `1933` flushed judged, `13` pending rerun, `1` failed.
- [ ] Run Phase 3 canary with queue seed + Regression Panel + golden set.
- [ ] Run full baseline∩canary collateral, not only golden shared-post collateral.
- [ ] Run required affected-module tests plus full unittest sweep before any goal completion.

## 2026-06-27 - Loop 07 wrong-work targeted canary TODO

- [x] Build targeted input for Phase 2 `wrong_work_disambiguation` rows.
  - input: `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop07_wrong_work_disambiguation_7.jsonl`
  - rows `7`
- [x] Run targeted canary with VLM/OCR required.
  - result: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop07_wrong_work_disambiguation_7_result.json`
  - completed/pending/failed `7/0/0`
- [x] Run seed movement compare.
  - compare: `out\regression_safe_grounding_20260626_000008_928006_loop01\compare\loop07_wrong_work_disambiguation_7_compare.md`
  - movement `review=7`
- [x] Render Data Analytics report artifact.
  - artifact: `LOOP 07 Wrong-Work Targeted Canary`
- [ ] Promote no public title from this slice without full panel/golden collateral.
  - current result is precision-safe candidate preservation, not full semantic approval.
- [x] Continue to Phase 2 `resolution_promotion_gate=102`.
  - Loop 08 input/result/compare completed; movement `review=102`, targeted next queue `0`.

## 2026-06-27 - Loop 08 resolution-promotion targeted canary TODO

- [x] Build targeted input for Phase 2 `resolution_promotion_gate` rows.
  - input: `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop08_resolution_promotion_gate_102.jsonl`
  - rows `102`
- [x] Run targeted canary with VLM/OCR required.
  - result: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop08_resolution_promotion_gate_102_result.json`
  - completed/pending/failed `102/0/0`
  - effective parallel `16` after `reuse_shards_only` health filtering.
- [x] Run seed movement compare.
  - compare: `out\regression_safe_grounding_20260626_000008_928006_loop01\compare\loop08_resolution_promotion_gate_102_compare.md`
  - movement `review=102`
  - targeted next queue `0`
- [x] Render Data Analytics report artifact.
  - artifact: `Loop 08 Resolution Promotion Gate Review`
- [ ] Do not treat Loop 08 targeted queue `0` as full approval.
  - all compared rows are still `review`.
  - `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
- [ ] Continue remaining Phase 2 axes.
  - `slang_store_gate=92`
  - `human_review_boundary=25`
  - `image_anchor_gate=25` completed in Loop 09 with next queue `1`

## 2026-06-28 - Loop 09 image-anchor targeted canary TODO

- [x] Build targeted input for Phase 2 `image_anchor_gate` rows.
  - input: `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop09_image_anchor_gate_25.jsonl`
  - input manifest: `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop09_image_anchor_gate_25_manifest.json`
  - rows `25`, structured image rows `25`, recommended action `re_judge=25`
- [x] Run targeted canary with VLM/OCR required.
  - result: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop09_image_anchor_gate_25_result.json`
  - completed/flushed/pending/failed `25/25/0/0`
  - manifest `large_run_complete=true`, `ordered_flush_blocked=false`, `partial_flush_gap=false`
  - VLM/OCR semantic gate `READY`, `slang_db=off`
- [x] Run seed movement compare.
  - compare: `out\regression_safe_grounding_20260626_000008_928006_loop01\compare\loop09_image_anchor_gate_25_compare.md`
  - movement `review=24`, `garbage_title_after=1`
  - targeted next queue `1`
- [x] Render Data Analytics validation artifact.
  - artifact: `Loop 09 Image Anchor Gate Validation`
- [ ] Do not treat Loop 09 targeted runtime `GO` as semantic approval.
  - `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`
  - next queue row `11682791` remains `garbage_title_after`
- [ ] Continue remaining Phase 2 axes.
  - `slang_store_gate=92`
  - `human_review_boundary=25`

## 2026-06-27 - Goal session 019f0387 completion review follow-up

- [x] Review Codex goal session `019f0387-24d0-7313-a6c0-66d09f04bb33` against the pasted objective and final `update_goal complete` call.
  - report: `docs/devs/GOAL_SESSION_REVIEW_019f0387_20260627.md`
  - 판정: `PARTIAL-COMPLETE / GOAL-COMPLETE-NO`
- [ ] Do not treat thread `019f0387-24d0-7313-a6c0-66d09f04bb33` as full objective completion evidence.
  - accepted interpretation: Loop 06 targeted checkpoint closed intentionally.
  - rejected interpretation: pasted full goal completed.
- [ ] Resume from Phase 1 action queue plus Loop 06 HOLD/label-review rows if the work continues.
  - Phase 1 queue: `out/full_post_judge_20260626_000008_928006_phase1/phase2_initial_queue.json`
  - Loop 06 HOLD/label-review: `11663521`, `11685994`, `11700470`, `11713222`
- [ ] Before any future goal completion claim, re-check source completeness, golden semantic, collateral semantic, panel/full scan, and original stop condition.

## 2026-06-30 - Loop 133 focused replay TODO

- [x] Acknowledge user correction that current goal is not complete.
- [x] Re-read pasted goal source and preserve the original stop condition.
- [x] Patch and test stale precision guard / Kakao comment-tab canonicalization / deliberated relation-block bypass.
- [x] Run focused replay after relation patch.
  - result: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop133_11705231_character_setting_kakao_focus_after_relation_patch_result.json`
  - completed/flushed/pending/failed `1/1/0/0`
  - Identified `0`
- [x] Run runtime contract audit.
  - audit: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop133_11705231_character_setting_after_relation_patch_runtime_audit.md`
- [x] Render Data Analytics focused replay artifact.
  - artifact: `Loop 133 Focused Replay Gate Review`
- [ ] Build a true source-enriched `11705231` row where `탐식의 재림` official detail/search evidence is consumed by `expert_main.py`, not only stored in a manifest.
- [ ] Re-run the source-enriched focused canary at least twice with `--slang-db off`.
- [ ] Do not mark goal complete until panel/golden/collateral/replay/full-sweep gates are closed or residual rows have accepted HOLD/human_review/no_generalizable_fix rationale.

## 2026-06-30 - Loop 157 stable-alias descriptor guard TODO

- [x] Patch the Loop156 `11698880` wrong-title switch repro seed.
  - guard: high/medium-fit descriptor + low/none-fit title + no best-match title blocks stable-alias replacement.
- [x] Add focused regression coverage.
  - `test_stable_alias_conflict_ignores_low_fit_title_when_descriptor_context_is_stronger`
- [x] Run targeted canary for `11698880`.
  - run id `20260630_154514_521625`
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop157_11698880_stable_alias_descriptor_context_guard_result.json`
- [x] Record review/report/Data Analytics artifacts.
- [ ] Rerun the parent/representative packet after Loop157.
- [ ] Compare parent replay against Loop156/Loop150/Loop142/Loop136, with special attention to `11706832` and `11668288`.
- [ ] Run affected-module plus full unittest sweep.
- [ ] Do not promote Loop157 single seed recovery to full approval.

## 2026-06-30 - Loop 158 parent replay TODO

- [x] Rerun the parent/representative packet after Loop157.
  - run id `20260630_160219_354659`
  - completed/flushed/pending/failed `38/38/0/0`
  - VLM/OCR `READY`, effective parallel `36`, MCP health `36/36`
- [x] Confirm parent-scope recovery for `11698880`.
  - Loop158 title/url: `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`
- [x] Record review/report/Data Analytics artifacts.
  - report `docs/devs/loop_reports/LOOP_158_REPORT_20260630.md`
  - review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop158_parent_replay_after_loop157_stable_alias_descriptor_guard_review.md`
  - Data Analytics `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop158_data_analytics_artifact.json`
- [x] Triage `11668288` lost-vs-Loop150.
  - Loop150 `가챠 중독자의 퓨전펑크 생활`
  - Loop158 null / `promotion_blocked`
  - Loop175 disposition `VARIANCE_QUARANTINE_HUMAN_REVIEW`
- [ ] Triage `11706832` title movement under degraded search.
  - Loop156 `황제폐하가 웹소설 작가임을 숨김`
  - Loop158 `황제의 딸로 환생했다`
- [ ] Build the next queue from Loop158 changed/gained/lost rows, separating justified recall improvements from regressions.
- [ ] Run affected-module plus full unittest sweep before any approval claim.
- [ ] Do not promote Loop158 runtime GO or `11698880` parent recovery to full approval.

## 2026-07-01 - Loop 225 envelope title gate parent replay TODO

- [x] Patch final publication ledger sync so inner `analysis_result` payload can receive the outer post title.
  - `expert_main.py` now passes `post_title=post.title`.
  - fallback source title lookup covers serialized payload metadata fields.
- [x] Add regression coverage for inner analysis payload without top-level `title`.
  - `test_inner_analysis_payload_uses_caller_post_title_for_shared_gate_restore`
- [x] Run focused verification.
  - `.venv312\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata`
  - `21 tests OK`
  - `.venv312\Scripts\python.exe -m py_compile expert_main.py tests\test_expert_main_comment_metadata.py`
- [x] Run Loop225 parent/representative replay.
  - run id `20260701_151744_526664`
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop225_parent_replay_after_envelope_title_gate_fix_result.json`
  - completed/flushed/pending/failed `38/38/0/0`
  - VLM/OCR `READY`
- [x] Record review/report/Data Analytics artifacts.
  - report `docs/devs/loop_reports/LOOP_225_REPORT_20260701.md`
  - review `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop225_parent_replay_after_envelope_title_gate_fix_review.md`
  - Data Analytics artifact `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop225_parent_replay_after_envelope_title_gate_fix_data_analytics_artifact.json`
- [x] Confirm target row recovery evidence.
  - deterministic replay: Loop224 actual payload + caller post title restores `11661876`
  - Loop225 live parent replay: `11661876` -> `와인의 신`
- [ ] Review Loop225 collateral safe-loss rows before any approval claim.
  - `11668288`, `11674712`, `11706832`
- [ ] Review Loop225 safe identity drift rows.
  - `11658615`, `11695637`, `11705231`
- [ ] Do not promote Loop225 runtime GO or `safe_resolved=12` count to semantic approval.
  - keep `semantic_quality=REVIEW-LOCKED`
  - keep `full_scan_approval=false`

## 2026-07-01 - Loop 229 title-led evaluation bridge TODO

- [x] Add a narrow title-led evaluation bridge for `볼만함` / `재밋네` style post-title markers.
  - code surfaces: `src/llm_batch/candidate_audit.py`, `src/llm_batch/agentic_pipeline.py`
- [x] Add focused regression coverage.
  - candidate audit title-led marker tests passed.
  - title-led inferred guard tests passed.
  - promotion gate contract tests passed.
- [x] Run the two-row Loop229 canary twice.
  - run `20260701_180326_874711`
  - run `20260701_181447_543860`
  - both completed/flushed/pending/failed `2/2/0/0`
  - VLM/OCR `READY`
- [x] Record review/report/Data Analytics artifacts.
  - report `docs/devs/loop_reports/LOOP_229_REPORT_20260701.md`
  - review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop229_title_led_evaluation_bridge_review.md`
  - Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop229_title_led_evaluation_bridge_data_analytics_artifact.json`
- [ ] Do not decrement residual accounting from Loop229.
  - final public title count stayed `0/2`
  - residual accounting `NO_DELTA_TITLE_LED_BRIDGE_CANARY_NO_GO`
- [ ] Split title-led evaluation question routing from broad recommendation/non-novel force paths.
- [ ] Align serializer/candidate audit scrub policy with upstream `scope_current_work` promotion decisions.
- [ ] Add end-to-end final JSON serialization tests before any parent replay.

## 2026-07-01 - Loop 230 title-led serializer/gate TODO

- [x] Keep reports and reader-facing review artifacts in Korean.
  - Applies to loop reports, review Markdown, Data Analytics artifact text, and future gate summaries.
  - Keep enum/paths/commands/URLs in raw form when needed for audit.
- [x] Patch serializer/candidate audit alignment for title-led alias + official detail + current-work scope.
  - code surfaces: `src/llm_batch/candidate_audit.py`, `expert_main.py`
- [x] Add end-to-end final JSON serialization coverage.
  - `test_current_work_gate_title_led_alias_scope_exempts_weak_alias_scrub`
  - `test_title_led_current_work_scope_restores_alias_candidate_publication`
- [x] Run Loop230 two-row canary.
  - run `20260701_183700_752963`
  - completed/flushed/pending/failed `2/2/0/0`
  - public title `1/2`
  - VLM/OCR `READY`
- [x] Record review/report/Data Analytics artifacts.
  - report `docs/devs/loop_reports/LOOP_230_REPORT_20260701.md`
  - review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop230_title_led_serializer_gate_review.md`
  - Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop230_title_led_serializer_gate_data_analytics_artifact.json`
- [ ] Do not decrement residual accounting from Loop230 alone.
  - residual accounting `NO_DELTA_TITLE_LED_SERIALIZER_CANARY_PARTIAL_RECOVERY_PARENT_REPLAY_REQUIRED`
  - `11660237` stayed `promotion_blocked`
- [ ] Run parent/representative packet replay before treating `11660257` as stable recovered evidence.
- [ ] Compare `publish_contract_trace`, `publish_ledger`, `promotion_decision`, and serialized `novel_identity` across the parent replay.
- [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop 231 parent replay after Loop230 TODO

- [x] Run parent/representative replay after Loop230.
  - run `20260701_190002_650661`
  - completed/flushed/pending/failed `38/38/0/0`
  - VLM/OCR `READY`, MCP health `36/36`
- [x] Confirm `11660257` parent survival.
  - public title `암흑가 보스요? 제가요?`
  - URL `https://novelpia.com/novel/384111`
- [x] Compare against Loop225 clean parent baseline.
  - Loop225 public title `12`, Loop231 public title `11`
  - safe gain `2`, safe loss `3`, safe identity drift `2`
- [x] Record Korean report/review/Data Analytics artifacts.
  - report `docs/devs/loop_reports/LOOP_231_REPORT_20260701.md`
  - review `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop231_parent_replay_after_loop230_title_led_serializer_gate_review.md`
  - Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop231_parent_replay_after_loop230_title_led_serializer_gate_data_analytics_artifact.json`
- [ ] Do not decrement residual accounting from Loop231.
  - residual accounting `NO_DELTA_PARENT_REPLAY_AFTER_LOOP230_MIXED_MOVEMENT`
  - parent semantic result `NO-GO / MIXED_MOVEMENT`
- [ ] Decompose Loop231 safe-loss rows before any approval claim.
  - `11661876`, `11663540`, `11695637`
- [ ] Track `11660237` as targeted/parent variance.
  - Loop230 targeted: `promotion_blocked/context_only`
  - Loop231 parent: `safe_resolved/테라포밍`
- [ ] Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.
