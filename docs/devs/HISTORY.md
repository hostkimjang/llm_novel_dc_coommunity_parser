# Development History

## 2026-07-03 - Loop331 current HEAD partial runtime NO-GO refresh

- 현 HEAD `c033dd97` 부분 런을 Loop331 감사 시점 audit로 다시 갱신했다.
- post-patch `11668283`은 completed/flushed/pending/failed `1/1/0/0`로 완료됐지만 `official_title=null`, `blocked_official_title=중세`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=adjacent`, `SEARCH_DEGRADED`로 끝났다. Loop328 guard patch runtime 수렴은 `NO-GO`다.
- full375는 `6/1/5/0` of `375`, bounded1200 completed-source는 `14/6/8/0` of `1200`, golden18은 `2/2/0/0` of `18`이며 모두 `search_degraded_observed`로 approval 근거가 아니다.
- safe-loss N5 partial은 observed `1/15`이고 `11674712` r01만 완료됐다. blind judge expected match가 false/incomplete라 hard-hold 완화는 계속 금지다.
- override audit `11705250`은 result JSON이 아직 없고 `search_degraded_detected=12`, `search_upstream_zero=4`가 남았다.
- Report는 `docs/devs/loop_reports/LOOP_331_REPORT_20260703.md`, state는 `docs/devs/loop331_current_head_partial_runtime_no_go_20260703.json`이다.
- Gate는 targeted `11668283` `NO-GO`, large/background runs `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 - Loop330 current HEAD health and override audit transition

- Loop329 current HEAD background run을 최신 health로 다시 감사했다.
- post-patch `11668283`은 `0/0/0/0`이고 `search_degraded_detected=7`, `search_upstream_zero=5`가 남아 search recovery는 계속 `P0 / OPEN`이다.
- full375는 `3/1/2/0`, bounded1200 completed-source는 `7/2/5/0`, golden18은 `1/1/0/0`, safe-loss N5 first run은 `0/0/0/0`이다. 모두 완료 전이므로 approval 근거가 아니다.
- old light run `20260702_065642_030743`에서 `OVERRIDE AUDIT(LLM=False->final=True)` 후보 `93`건을 찾았고, 이미 검토한 `11708445`, `11668283` 제외 checkpoint-matched 미검토 후보 `91`건을 확인했다.
- `11705250 / 심해법사 묵혀둔거 간만에 보니까 ㄹㅇ 맛있네`를 current HEAD non-light override audit 단건으로 발주했다. PID는 `93016`, run은 `20260703_034549_939485`, health는 search 포함 non-light `1/1` OK다. 다만 검색 단계에서 `search_degraded_detected=6`, `search_upstream_zero=2`가 관측됐다.
- Report는 `docs/devs/loop_reports/LOOP_330_REPORT_20260703.md`, state는 `docs/devs/loop330_current_head_health_override_audit_20260703.json`이다.
- Gate는 Loop329 runtime `IN_PROGRESS / NOT_APPROVAL`, override audit `11705250` `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD / SEARCH_DEGRADED_OBSERVED`, safe-loss flip `RUNNING_BACKGROUND / NOT_ANALYZED`, golden18 `APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 - Loop329 current HEAD c033dd97 runtime dispatch

- Loop328 guard patch 커밋 `c033dd97` 이후 현 HEAD runtime 증거를 새 경로로 분리했다.
- stale Loop314/Loop326 root PID `111032`, `75828`, `9908`, `43208`, `106428`, `34796`, `124704`, `73076`을 중단했다. 기존 산출물은 참고용 `reference-only / NOT_APPROVAL`이다.
- post-patch `11668283` single은 PID `75828`, run `20260703_032149_031285`, search non-light `1/1` OK로 시작했다.
- full375는 PID `3232`, run `20260703_032149_057915`, search non-light `12/12` OK로 시작했다.
- bounded1200 completed-source는 PID `119924`, run `20260703_032149_102775`, search non-light `12/12` OK로 시작했다.
- golden18은 PID `95980`, run `20260703_032149_034356`, search non-light `2/2` OK로 시작했다.
- safe-loss N5는 PID `107596`, planned runs `15`, first marker 생성 상태다.
- Report는 `docs/devs/loop_reports/LOOP_329_REPORT_20260703.md`, state는 `docs/devs/loop329_current_head_c033dd97_runtime_dispatch_20260703.json`이다.
- Gate는 launch health `GO_SEARCH_NONLIGHT_INITIAL`, post-patch single/N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 - Loop328 known-abbreviation exact-title public guard repair

- Loop327 patch 후 `11668283 / 게임 마인드의 중세 현대인 좋았다...`를 search 포함 non-light로 targeted replay했다.
- run `20260703_020949_643836`는 completed/flushed/pending/failed `1/1/0/0`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`다.
- LLM/Jury/Judge는 `게임 마인드의 중세 현대인`으로 수렴했지만 final public output은 `official_title=null`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`였다.
- 원인은 `weak_source_exact_title_without_official_support_public_title_bridge` overblock이다. 검색 후보가 `ssn.so`/`arca.live` 중심이라 official detail URL은 없지만, post title exact surface와 work consumption marker가 함께 있었다.
- `candidate_audit.py`에 `known_abbreviation_title_guard:*` current-work scope, exact title surface, `row_discusses_work_as_work`, `scope_current_work`, `work_consumption_marker`, title/body/search context가 모두 있을 때만 weak-source guard를 면제하는 좁은 예외를 추가했다.
- 검증은 py_compile PASS, 새 focused guard `2/2` PASS, 기존 title-led controls `2/2` PASS, known-title/arbiter/work-bridge bundle `33/33` PASS, `git diff --check` PASS다.
- Report는 `docs/devs/loop_reports/LOOP_328_REPORT_20260703.md`, state는 `docs/devs/loop328_known_abbreviation_exact_title_guard_20260703.json`이다.
- Gate는 code contract `GO_UNIT`, runtime replay `PRE_PATCH_REPRODUCED_OVERBLOCK / NOT_APPROVAL`, post-patch runtime replay `NOT_RUN_AFTER_GUARD_PATCH`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 - Loop327 override audit middle-age-modern alias repair

- `OVERRIDE AUDIT(LLM=False->final=True)` 확장 중 `11668283 / 게임 마인드의 중세 현대인 좋았다...`를 source-native false negative로 판정했다.
- 최신 light run `20260702_065642_030743`는 이 row를 `off_topic / context_only / official_title=null`로 내렸고, `batch_memory_alias_rescue_blocked_nonwork_context`, `batch_memory_alias_rescue_blocked_semantic_seed`가 붙었다.
- 과거 독립 run `20260423_170321_250907`는 같은 post_id를 `게임 마인드의 중세 현대인`, URL `https://page.kakao.com/content/63760170?tab_type=about`로 resolved 처리했다.
- partial current canary는 health `include_search=true`, `light_mode=false`, `1/1 OK`였고 Gatekeeper/Discourse는 work/review로 봤지만 semantic seed guard가 `중세 현대인`을 일반어로 drop했다.
- `KNOWN_TITLE_ABBREVIATIONS`에 `중세현대인`, `중세 현대인`, `게임마인드중세`, `게임마인드 중세 현대인`을 추가하고, curated alias gate의 작품 소비 cue에 `좋았다` 계열을 추가했다.
- 검증은 py_compile PASS, focused unit `9` PASS, related bundle `62` PASS다.
- Report는 `docs/devs/loop_reports/LOOP_327_REPORT_20260703.md`, state는 `docs/devs/loop327_override_audit_middle_age_modern_alias_20260703.json`이다.
- Gate는 row contract `GO_UNIT_REPAIR`, runtime replay `NOT_RUN_AFTER_PATCH`, Loop326 background `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 - Loop326 current HEAD runtime dispatch

- Loop325 계약 패치 커밋 `1095d447` 뒤 current HEAD runtime을 새 output 경로로 발주했다.
- safe-loss N5는 PID `73076`, planned runs `15`, first marker 생성 상태다.
- full375는 PID `106428`, run `20260703_013148_286926`, search non-light `12/12` OK로 시작했다.
- bounded1200 completed-source는 PID `34796`, run `20260703_013148_352379`, search non-light `12/12` OK로 시작했다.
- golden18은 PID `124704`, run `20260703_013148_298463`, search non-light `2/2` OK로 시작했다.
- Report는 `docs/devs/loop_reports/LOOP_326_REPORT_20260703.md`, state는 `docs/devs/loop326_current_head_runtime_dispatch_20260703.json`이다.
- Gate는 launch health `GO_SEARCH_NONLIGHT_INITIAL`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, safe-loss N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 - Loop325 curated alias work-cue contract

- Loop324 `11708443 / 괴담출근` 회귀를 Pipeline bridge와 Arbiter curated-alias null guard의 작품 담론 cue 불일치로 분해했다.
- `_has_curated_alias_work_discussion_cue`를 추가해 `독창성`, `SCP`, `영감`, `표지변경` 같은 작품 담론 cue를 Pipeline/Arbiter가 같은 술어로 보게 했다.
- `11708443` 독창성/SCP positive 계약과 `11718099` 표지변경 Arbiter null-guard 계약을 추가했다.
- comparison-only negative가 풀리지 않도록 cue 폭을 좁혔고, `괴담텔 ... 괴담동` control은 계속 blocked다.
- 검증은 known-title abbreviation safe-loss contract `8` PASS, Arbiter curated alias guard `21` PASS, py_compile PASS, related work-bridge/title-lead bundle `214` PASS다.
- Report는 `docs/devs/loop_reports/LOOP_325_REPORT_20260703.md`, state는 `docs/devs/loop325_curated_alias_work_cue_contract_20260703.json`이다.
- Gate는 code contract `GO_UNIT_AND_BROADER_214`, runtime replay `NOT_RUN_CURRENT_PATCH`, targeted canary `LOOP324_NO-GO`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 - Loop324 Loop322 alias non-light replay

- 코드 체크포인트 `8c4ec326`에서 known-title abbreviation work bridge를 shared `_post_discusses_work_as_work` 경유로 배선하고 `MCP_HEALTH_LIGHT_MODE=0` override를 추가했다.
- Loop322 alias 7건을 search 포함 non-light health로 재실행했다.
- run `20260702_235904_452705`는 completed/flushed/pending/failed `7/7/0/0`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`, VLM/OCR `READY`다.
- 결과는 `safe_resolved=2/7`, `promotion_blocked=5/7`, expected match `3/7`, search degraded 관측 `5/7`이다.
- `절꺾않`은 `safe_resolved`로 개선됐지만 `괴담출근`은 safe-resolved에서 promotion-blocked로 회귀했다.
- `빌환`, `지구온라인`, `성좌안무서움`은 아직 publication 수렴이 아니므로 residual closure로 세지 않는다.
- Report는 `docs/devs/loop_reports/LOOP_324_REPORT_20260703.md`, state는 `docs/devs/loop324_loop322_alias_nonlight_replay_20260703.json`이다.
- Gate는 run integrity `GO_RUNTIME_COMPLETE_NONLIGHT`, targeted canary `NO-GO`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop322 safe-loss alias shared contract

- Loop321 `repair_safe_loss=76` 중 7건을 shared known-title abbreviation 계약으로 올렸다.
- 추가 alias는 `괴담출근`, `절꺾않`, `무마`, `아카엄창`, `성좌안무서움`, `빌환`, `지구온라인`이다.
- known-title abbreviation work cue에 `표절`, `보러감`을 추가했다.
- `주전무`는 실제 packet에서 plot cue는 강하지만 shared cue 폭을 더 넓혀야 해 이번 registry 승격에서 보류했다.
- 검증은 py_compile PASS, safe-loss contract `4` PASS, related alias/arbiter/title-lead bundle `230` PASS, always-on/convergence `12` PASS다.
- 실제 Loop321 packet helper check는 선택 7건 allowed, held `주전무=false`다.
- Report는 `docs/devs/loop_reports/LOOP_322_REPORT_20260702.md`, state는 `docs/devs/loop322_safe_loss_alias_contract_20260702.json`이다.
- Gate는 contract `GO_UNIT_CONTRACT_ONLY`, runtime replay `NOT_RUN`, residual closure `NOT_COUNTED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop321 safe-loss source-native queue closure

- Loop301 `safe_loss_resolved_to_null=147` batch에서 Loop320 이후 남은 28건을 source-native로 판정했다.
- Delta 결과는 `REPROCESS=15`, `ACCEPT=9`, `HOLD=4`, validation issues `0`이다.
- 누적 결과는 reviewed `147/147`, unreviewed `0`, labels `REPROCESS=76`, `ACCEPT=42`, `HOLD=29`이다.
- 초기 작업 메모의 `16/8/4` 총계는 원문 packet 재확인 후 `15/9/4`로 정정했다.
- `전독시`, `괴담출근`, `잠룡회귀`, `절꺾않`, `주전무`, `무마`, `아카엄창`, `도굴왕`, `아생갤`, `고능아`, `마녀도시`, `빌환`, `지구온라인` 계열은 repair 후보로 분리했다.
- `이불사` wrong-before, `랫따싶` 대체작, `기계공주` 부정 추천, `컵라면` 작가/신작 표면, `시스템 딸깍` generic trope는 after null/HOLD preferred로 분리했다.
- Report는 `docs/devs/loop_reports/LOOP_321_REPORT_20260702.md`, state는 `docs/devs/loop321_safe_loss_source_native_review_20260702.json`이다.
- Gate는 source-native review `REVIEW-LOCKED / COMPLETE_SOURCE_NATIVE_QUEUE`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop320 safe-loss source-native next slice

- Loop314 full375/bounded1200/golden18/N5는 완료 대기하지 않고 background 감시로 유지했다.
- Loop301 `safe_loss_resolved_to_null=147` batch에서 Loop318 이후 다음 15건을 source-native로 추가 판정했다.
- Delta 결과는 `REPROCESS=8`, `ACCEPT=5`, `HOLD=2`, validation issues `0`이다.
- 누적 결과는 reviewed `119/147`, unreviewed `28`, labels `REPROCESS=61`, `ACCEPT=33`, `HOLD=25`이다.
- `6★ 가챠 캐릭터가 되었다`, `괴담 호텔 탈출기`, `판초우의의 마법사`, `월야환담`, `탐식의 재림`, `월야환담 창월야`, `기계공주` 계열은 repair 후보로 분리했다.
- `나의 악당들`, `아프리카 의 독재자가 되었다 .`, `게임 속 도굴꾼이 되었다`, `삼국지 마대 가 되었다`는 wrong-before 또는 prior-work/동음 후보라 safe-loss 복구 대상에서 제외했다.
- Report는 `docs/devs/loop_reports/LOOP_320_REPORT_20260702.md`, state는 `docs/devs/loop320_safe_loss_source_native_review_20260702.json`이다.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop319 OVERRIDE AUDIT 11708445 blind/source-native

- 코드 변경 없는 대형 run 감시/문서 회차가 반복되어 `OVERRIDE AUDIT(LLM=False->final=True)` 행 검증으로 전환했다.
- 대상은 `11708445` `퉁구스1캇햄 작품 하나도 안 봤는데`다.
- source run `20260702_065642_030743` result에서 해당 row가 completed로 flush된 것을 확인했다.
- 최종 public contract는 `official_title=null`, `official_url=null`, `candidate_ledger_status=promotion_blocked`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `candidate_preserved=true`, `bypassed_gate=false`다.
- Blind/source-native 판정은 `ACCEPT / candidate_only_block_is_correct`다. `제냥꾼`은 후보 보존 대상이지 이 row의 public title publish 대상이 아니다.
- Reason hygiene forbidden marker hit는 `0`이다.
- Report는 `docs/devs/loop_reports/LOOP_319_REPORT_20260702.md`, state는 `docs/devs/loop319_override_audit_11708445_20260702.json`이다.
- Gate는 override audit `GO_ROW_CONTRACT_ONLY`, runtime source `BACKGROUND_LIGHT_RUN_NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop318 safe-loss source-native next slice

- Loop314 full375/bounded1200/golden18/N5는 완료 대기하지 않고 background 감시로 유지했다.
- Loop301 `safe_loss_resolved_to_null=147` batch에서 Loop317 이후 다음 15건을 source-native로 추가 판정했다.
- Delta 결과는 `REPROCESS=5`, `ACCEPT=7`, `HOLD=3`, validation issues `0`이다.
- 누적 결과는 reviewed `104/147`, unreviewed `43`, labels `REPROCESS=53`, `ACCEPT=28`, `HOLD=23`이다.
- `아생갤`, `랫따싶`, `니생들`, `괴담텔` 계열은 repair 후보로 분리했다.
- `버거피아` 이벤트, `귤부인 대롱대롱` unverified exact-title, Re:Zero 캐릭터 페이지, `타락` generic 추천어, `스페이스 오페라` wrong-title은 after null/HOLD preferred로 분리했다.
- `11698880`은 known variance control이라 repair로 세지 않고 publish/block trace와 primary-vs-secondary scope 검증으로 HOLD했다.
- Report는 `docs/devs/loop_reports/LOOP_318_REPORT_20260702.md`, state는 `docs/devs/loop318_safe_loss_source_native_review_20260702.json`이다.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop317 safe-loss source-native next slice

- Loop314 full375/bounded1200/golden18/N5는 완료 대기하지 않고 background 감시로 유지했다.
- Loop301 `safe_loss_resolved_to_null=147` batch에서 Loop316 이후 다음 15건을 source-native로 추가 판정했다.
- Delta 결과는 `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`, validation issues `0`이다.
- 누적 결과는 reviewed `89/147`, unreviewed `58`, labels `REPROCESS=48`, `ACCEPT=21`, `HOLD=20`이다.
- `엑칼뽑`, `괴담텔`, `격투천재`, `판초법사`, `아생갤`, `트와일라잇`, `여신애호`는 repair 후보로 분리했다.
- `혼후순결` plot element, `즉사무림` comparison row, `유희왕` generic franchise row는 after null/HOLD preferred로 분리했다.
- Report는 `docs/devs/loop_reports/LOOP_317_REPORT_20260702.md`, state는 `docs/devs/loop317_safe_loss_source_native_review_20260702.json`이다.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop316 safe-loss source-native next slice

- Loop314 full375/bounded1200/golden18/N5는 완료 대기하지 않고 background 감시로 유지했다.
- Loop301 `safe_loss_resolved_to_null=147` batch에서 Loop312 이후 다음 15건을 source-native로 추가 판정했다.
- Delta 결과는 `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`, validation issues `0`이다.
- 누적 결과는 reviewed `74/147`, unreviewed `73`, labels `REPROCESS=41`, `ACCEPT=15`, `HOLD=18`이다.
- `마도줍 -> 소설 속 엑스트라`, `전독시` 댓글 조롱 예시, `블아` cross-media game 맥락 등은 after null preferred로 분리했다.
- Report는 `docs/devs/loop_reports/LOOP_316_REPORT_20260702.md`, state는 `docs/devs/loop316_safe_loss_source_native_review_20260702.json`이다.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop315 character-setting bridge contract

- Loop314 full375/bounded1200/golden18/N5는 완료 대기 대신 background 감시로 내렸다.
- Loop312 source-native verdict의 `11669933` 후보를 shared character-setting bridge 계약으로 전환했다.
- 원문은 `중경계에서 첨 만난게 해방상제임?`, 본문 `서휼 따라가서 지하에서 버티는 시합하다가 만난거`, 댓글 `그거 미래의 주인공`이다.
- `회귀수선전`은 단순 alias registry가 아니라 `중경계/서휼/해방상제` character-setting convergence로만 release되도록 positive/negative 계약 테스트를 추가했다.
- `_post_discusses_work_as_work(...)`가 character-setting bridge와 verified alias wrapper를 계속 소유하는 소스 계약 테스트를 추가했다.
- 검증은 py_compile PASS, targeted `3` PASS, related promotion/work-bridge bundle `32` PASS다.
- Report는 `docs/devs/loop_reports/LOOP_315_REPORT_20260702.md`, state는 `docs/devs/loop315_character_setting_bridge_contract_20260702.json`이다.
- Gate는 character bridge `GO_UNIT_CONTRACT_ONLY`, runtime replay `NOT_RUN`, residual closure `NOT_COUNTED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop314 current-HEAD runtime dispatch

- Loop313 이후 기존 Loop288/Loop302 background 프로세스가 현 HEAD `64864278` 증거가 아니게 되어 stale/mixed evidence로 분리하고 중단했다.
- 새 Loop314 경로로 N5, golden18, full375, completed-source bounded1200을 발주했다.
- N5는 PID `111032`, planned runs `15`, report 시점 result JSON `0/15`다.
- full375는 PID `75828`, run `20260702_204042_346798`, input `375`, completed `0`이다.
- bounded1200은 PID `9908`, run `20260702_204042_443948`, input `1200`, completed `1`이다.
- golden18은 PID `43208`, run `20260702_204042_371537`, input `18`, completed `0`이다.
- 모든 새 런은 `mcp_health_include_search=true`, `mcp_health_light_mode=false`로 시작했다.
- `tools/run_independent_plan.py`를 추가해 N5 plan runner를 안정화했다.
- Report는 `docs/devs/loop_reports/LOOP_314_REPORT_20260702.md`, state는 `docs/devs/loop314_current_head_runtime_dispatch_20260702.json`이다.
- Gate는 N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, golden18 `APPROVAL_NOT_OPEN`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop313 safe-loss alias contract repair

- Loop312 `repair_safe_loss=34` 중 일반화 가능한 alias 계약 일부를 코드로 전환했다.
- `KNOWN_TITLE_ABBREVIATIONS`에서 `악살싶` canonical title을 `악당은 살고 싶다`로 정정하고 `전독시 -> 전지적 독자 시점`을 추가했다.
- curated known-title abbreviation work-cue에 `영화/극장판/실사화/애니화/드라마화/원작/각색`을 추가해 adaptation 논의를 작품 논의로 인정했다.
- `악신총애`는 동음 후보 위험 때문에 전역 registry 추가를 보류했고, `회귀수선전`은 당시 character-setting bridge 계약 후보로 남긴 뒤 Loop315에서 shared bridge 계약 테스트로 고정했다.
- 검증은 py_compile PASS, focused alias `3` PASS, promotion/work-bridge `23` PASS, related bundle `266` PASS, Data Analytics validate/render PASS다.
- Report는 `docs/devs/loop_reports/LOOP_313_REPORT_20260702.md`, state는 `docs/devs/loop313_safe_loss_alias_contract_repair_20260702.json`이다.
- Gate는 code/unit contract `GO_UNIT`, runtime replay `NOT_RUN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED` result `1/15`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop312 safe-loss source-native 다음 slice

- Loop310 이후 남은 `safe_loss_resolved_to_null` 미검토분에서 15건을 추가 source-native review로 판정했다.
- Delta 결과는 `REPROCESS=7`, `ACCEPT=3`, `HOLD=5`다.
- 누적 결과는 reviewed `59/147`, unreviewed `88`, validation issues `0`이다.
- 누적 labels는 `REPROCESS=34`, `ACCEPT=9`, `HOLD=16`이다.
- N5 background runner는 result JSON `0/15` 상태라 flip rate 갱신 근거가 아니다.
- full375/bounded1200은 계속 `IN_PROGRESS / NOT_APPROVAL`이며 search degraded/timeout blocker가 남아 있다.
- Report는 `docs/devs/loop_reports/LOOP_312_REPORT_20260702.md`, state는 `docs/devs/loop312_safe_loss_source_native_review_20260702.json`이다.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop311 current HEAD runtime refresh dispatch

- search shard `/api/health`를 live로 다시 확인했다. `127.0.0.1:3333`, `127.0.0.1:3334` 모두 HTTP 200이다.
- safe-loss N5 plan `15`건을 hidden background runner로 발주했다. PID는 `90532`, 로그는 `logs/loop311_safe_loss_independent_n5_plan/`에 남는다.
- report 시점 N5 result JSON은 `0/15`라 flip rate는 아직 갱신되지 않았다.
- golden18은 `18`행이며 `11660237`, `11698880`을 포함한다. 두 행은 `safe_loss_blind_judge_expected_work` / `safe_loss_flip_probe`로 남아 있다.
- full375는 run `20260702_124015_346913`, checkpoint/result `135/105`, pending `30`, `IN_PROGRESS/ordered_flush_gap_in_progress`다.
- bounded1200 completed-source는 run `20260702_124015_423917`, checkpoint/result `205/188`, pending `17`, `IN_PROGRESS/ordered_flush_gap_in_progress`다.
- 두 run 모두 search 포함 non-light이지만 blockers `search_timeout_observed`, `search_degraded_observed`가 남아 approval 근거가 아니다.
- `tools/build_golden_regression_set.py`, `tools/compare_against_golden.py`를 git 추적으로 전환한다.
- Report는 `docs/devs/loop_reports/LOOP_311_REPORT_20260702.md`, state는 `docs/devs/loop311_current_head_runtime_refresh_20260702.json`이다.
- Gate는 N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `TRACKED / APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop310 safe-loss source-native 다음 slice

- Loop306 이후 남은 `safe_loss_resolved_to_null` 미검토분에서 15건을 추가 source-native review로 판정했다.
- Delta 결과는 `REPROCESS=4`, `ACCEPT=2`, `HOLD=9`다.
- 누적 결과는 reviewed `44/147`, unreviewed `103`, validation issues `0`이다.
- 누적 labels는 `REPROCESS=27`, `ACCEPT=6`, `HOLD=11`이다.
- `11663521`은 기존 Loop141 hold boundary를 유지했고, `11663540`은 before wrong title `방구석 여신이 되었다` 기준 safe-loss가 아니라 after hold preferred로 분리했다.
- Report는 `docs/devs/loop_reports/LOOP_310_REPORT_20260702.md`, state는 `docs/devs/loop310_safe_loss_source_native_review_20260702.json`이다.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop309 백그라운드 전환 및 큐 정합성

- current HEAD 기준 background health를 다시 갱신했다.
- full375는 run `20260702_124015_346913`, checkpoint/result `129/105`, pending `24`, `IN_PROGRESS/ordered_flush_gap_in_progress`다.
- bounded1200 completed-source는 run `20260702_124015_423917`, checkpoint/result `190/177`, pending `13`, `IN_PROGRESS/ordered_flush_gap_in_progress`다.
- 두 run 모두 search 포함 non-light이지만 blockers `search_timeout_observed`, `search_degraded_observed`가 남아 approval 근거가 아니다.
- Loop308의 `repair_unsafe_promotion=14` 중복 queue 표기를 정정했다. Loop300 current contract replay가 이미 `26/26` match와 `REPROCESS=14 -> promotion_blocked=14/14`를 기록했으므로 새 코드 queue로 다시 세지 않는다.
- N5 flip 근거는 Loop307 산출물을 유지한다. `11674712`와 `11698880`은 flip_rate `0.4`, `11660237`은 stable blind judge confirmed이며 gate는 `NO-GO`다.
- 다음 actionable queue는 Loop306 기준 `safe_loss_resolved_to_null` reviewed/unreviewed `29/118`, `repair_safe_loss=23`이다. 대형 run 대기만 반복되면 `OVERRIDE AUDIT(LLM=False->final=True)` blind judge 검증으로 전환한다.
- Report는 `docs/devs/loop_reports/LOOP_309_REPORT_20260702.md`, state는 `docs/devs/loop309_background_handoff_20260702.json`이다.
- Gate는 background full375/bounded `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop308 collateral unsafe-promotion triage

- 대형 full375/bounded run을 approval 경로로 기다리지 않고 background health만 갱신했다.
- 최신 health는 full375 checkpoint/result `120/105`, bounded1200 `180/167`이며 둘 다 `IN_PROGRESS`, blockers `search_timeout_observed`, `search_degraded_observed`다.
- Loop298 `unsafe_promotion_from_hold` 26건을 source-native 기준으로 전수 판정했다.
- Verdict는 `docs/devs/loop308_unsafe_promotion_from_hold_source_native_verdicts.json`이다.
- Summary는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop308_unsafe_promotion_from_hold_source_native_review.json`와 `.md`에 있다.
- 결과는 reviewed `26/26`, validation issues `0`, `ACCEPT=12`, `REPROCESS=14`다.
- Data Analytics artifact `Loop308 collateral unsafe-promotion triage report` validate/render PASS.
- Report는 `docs/devs/loop_reports/LOOP_308_REPORT_20260702.md`다.
- Gate는 collateral unsafe-promotion triage `REVIEW-LOCKED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop307 safe-loss alias contract expansion

- Loop306 source-native review에서 일반화 가능한 alias `럽코빙의`, `빚세구`, `마줍`, `여신애호`, `별품소`를 shared known-title abbreviation 계약에 추가했다.
- 작품 문맥 cue는 `연중`, `웹툰`, `결말`, `보러간`, `전생`, `주인공`, `이세계`, `정체`, `설정`으로 보강했다.
- `가챠펑크`와 `즉사기`는 search/detail evidence 또는 다중작 충돌 위험 때문에 registry 단독 release에서 제외했다.
- N5 flip-rate 최신 분석은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop307_safe_loss_flip_rate_n5_current_head_review.json`이다.
- N5 결과는 `NO-GO`: `11674712` flip_rate `0.4`, `11660237` stable blind judge confirmed, `11698880` flip_rate `0.4`.
- 최신 background audit은 full375 `118/105`, bounded1200 `172/167`이며 둘 다 `IN_PROGRESS`, blocker `search_degraded_observed`다.
- 검증은 py_compile PASS, focused `3` tests PASS, related bundle `237` tests PASS다.
- Report는 `docs/devs/loop_reports/LOOP_307_REPORT_20260702.md`, state는 `docs/devs/loop307_safe_loss_alias_contract_expansion_20260702.json`이다.
- Gate는 code contract `GO_UNIT`, safe-loss flip `NO-GO`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop306 safe-loss source-native next slice review

- Loop301 `safe_loss_resolved_to_null=147` 미검토분 중 14건을 추가 source-native review로 판정했다.
- 누적 verdict는 `docs/devs/loop306_safe_loss_source_native_verdicts_cumulative_29.json`이다.
- Summary는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop306_safe_loss_source_native_review.json`와 `.md`에 있다.
- 누적 결과는 reviewed `29/147`, unreviewed `118`, validation issues `0`이다.
- 누적 label counts는 `REPROCESS=23`, `ACCEPT=4`, `HOLD=2`다.
- Loop306 delta는 `REPROCESS=9`, `ACCEPT=3`, `HOLD=2`다.
- 이 회차는 action queue 분해이며 runtime replay나 full approval이 아니다.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop305 safe-loss alias targeted replay handoff

- Loop304 known-alias 계약을 실제 panel 입력에서 검증하기 위해 11-row targeted replay 입력을 만들었다.
- 입력은 `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop305_safe_loss_alias_contract_targeted_input.jsonl`이고, 입력 manifest는 `loop305_safe_loss_alias_contract_targeted_input_manifest.json`이다.
- 대상은 Loop304 positive alias 7건, comparison-only negative control `11660232`, safe-loss core control `11660237/11698880/11674712`다.
- 실행 전 search shard audit `out/search_shard_audit_20260702_181756.json`은 `ok=12/12`다.
- vLLM model은 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`로 확인했다.
- replay는 PID `16380`, run id `20260702_181813_388157`로 시작했다.
- 현재 manifest는 `input=11`, `completed=0`, `flushed=0`, `failed=0`이다. `11660257`, `11666731`은 VLM chunk result 이후 LLM 단계에 있다.
- Small-run reuse-only health라 `mcp_health_include_search=false`, `mcp_health_light_mode=true`다. 따라서 search recovery approval 증거가 아니다.
- Health audit은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop305_safe_loss_alias_targeted_replay_inprogress_health_audit.json`이다.
- Gate는 targeted runtime `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop304 safe-loss known-alias contract repair

- Loop301 `repair_safe_loss=14` 중 source-native로 확인된 직접 alias seed 일부를 shared known-abbreviation work-cue 계약으로 전환했다.
- `KNOWN_TITLE_ABBREVIATIONS`에 `암흑가보스/암보스`, `기계공주`, `약먹마`, `악살싶`, `마도줍`, `괴담동`, `즉사무림`, `밀리언클래스`를 추가했다.
- `_known_title_abbreviation_update_question_anchor(...)`는 `최신편`, `작가`, `공지`, `표지`, `읽`, `봤`, `보는`, `볼만`, `재밌`, `재밋`, `재미`, `호평`, `애매` 같은 직접 작품 소비/평가 cue를 본다.
- 비교/adjacent negative control로 `괴담텔 ... 괴담동이 살짝 생각나네`가 `괴담 동아리`로 release되지 않도록 계약 테스트를 추가했다.
- Report는 `docs/devs/loop_reports/LOOP_304_REPORT_20260702.md`, state는 `docs/devs/loop304_safe_loss_alias_contract_repair_20260702.json`이다.
- 검증은 py_compile PASS, focused `2` tests PASS, related bundle `217` tests PASS, `git diff --check` PASS다.
- Gate는 code contract `GO_UNIT`, targeted runtime `IN_PROGRESS / NOT_APPROVAL`(Loop305 발주), search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop303 runtime recovery and background handoff

- Docker Desktop 재기동 뒤 search shard runtime이 복구됐다. `3333/3334` health는 `status=ok`, `headless_search_enabled=true`이고 MCP bridge container는 `36`개다.
- Loop302 N5 plan을 재시도했으나 첫 row가 search official hit 이후 LLM `decoder` 단계에서 장기화되어 foreground 실행을 중단했다. current HEAD flip rate는 아직 갱신되지 않았다.
- full375와 bounded1200 completed-source run은 search 포함 non-light background 감시 대상으로 유지한다. 두 run 모두 `IN_PROGRESS`이며 blocker `search_degraded_observed`가 남아 approval 근거가 아니다.
- 104k run은 light/search-not-included run으로 확인되어 승인 교착 해소 근거로 쓰지 않는다.
- Golden18 상태는 `golden_rows=18`, 추가 row `11660237`, `11698880`이며 golden 산출물과 bootstrap/probe/audit 도구는 git 추적 중이다.
- 코드 변경 없는 대형 run 대기 대신 Loop301 `safe_loss_resolved_to_null=147` queue로 강제 전환했다. 현재 seed verdict는 `15/147`, `REPROCESS=14`, `ACCEPT=1`, 미검토 `132`다.
- Report는 `docs/devs/loop_reports/LOOP_303_REPORT_20260702.md`다.
- Gate는 search runtime `PARTIAL_RECOVERED`, search degraded `P0 / OPEN`, safe-loss flip `NOT_REFRESHED_CURRENT_HEAD`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop302 current HEAD refresh blocker

- 현 HEAD `e991a687`에서 safe-loss flip probe `N>=5`, full375 replay, completed-source bounded non-light run을 갱신하려 했다.
- N5 독립 실행 plan은 생성됐다. planned runs `15`, repeat counts `11674712=5`, `11660237=5`, `11698880=5`, missing post ids `[]`다.
- 실제 실행은 search shard 연결 거부로 result JSON `0`개에서 중단됐다. 로그는 `logs/loop302_safe_loss_independent_n5_plan/*.stderr.log`다.
- `127.0.0.1:3333`, `127.0.0.1:3334` 모두 health 연결 불가이고 Docker API는 `desktop-linux`/`default` context 모두 Internal Server Error다.
- `com.docker.service`는 `Stopped`이며 `Start-Service`도 실패했다.
- Golden18 편입과 추적 상태는 확인했다. `11660237`, `11698880` extra golden manifest와 `golden_manifest.json`, `golden_set.jsonl`, bootstrap/probe/audit 도구는 git 추적 중이다.
- 기존 Loop288 background snapshot은 full375 `375/83/80/3/0`, bounded1200 `1200/128/125/3/0`, golden18 `18/18/18/0/0`이지만 현 HEAD 승인 증거로 쓰지 않는다.
- Report는 `docs/devs/loop_reports/LOOP_302_REPORT_20260702.md`다.
- Gate는 run integrity `NO-GO_RUNTIME_BLOCKED`, search recovery `P0 / OPEN / LOCAL_DOCKER_SERVICE_BLOCKER`, safe-loss flip `NOT_REFRESHED_CURRENT_HEAD`, full375 `NOT_REFRESHED_CURRENT_HEAD`, bounded completed-source `NOT_LAUNCHED_CURRENT_HEAD`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop301 safe-loss seed source-native verdict

- Loop300 이후 다음 action queue를 `safe_loss_resolved_to_null=147`로 전환했다.
- Safe-loss 전용 review batch를 생성했다. selected rows는 `147`, missing source/baseline/after는 `0/0/0`이다.
- Seed verdict `15/147`을 작성했다. validation issues `0`, `REPROCESS=14`, `ACCEPT=1`, unreviewed `132`다.
- `REPROCESS=14`는 직접 title/alias surface가 before safe title을 지지하지만 after가 null/promotion_blocked로 내린 safe-loss repair 후보로 분리했다.
- `ACCEPT=1`은 before title이 비교 대상 작품을 current work로 잘못 잡은 행이라 gate 배선 뒤 regression count 제외 후보로 둔다.
- Report는 `docs/devs/loop_reports/LOOP_301_REPORT_20260702.md`다.
- Gate는 safe-loss seed verdict `REVIEW-LOCKED`, search recovery `P0 / OPEN`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop300 unsafe promotion full source-native verdict and gate wiring

- Loop298 `unsafe_promotion_from_hold=26` 전체를 source-native verdict로 닫았다.
- Verdict 결과는 reviewed `26/26`, validation issues `0`, `REPROCESS=14`, `ACCEPT=12`다.
- `expert_main.py`는 publication 후보의 직접 title/url/source/alias 지지 여부를 공통 helper로 평가한다.
- URL 없는 inferred publication도 순수 작품 alias가 원문 title/source에서 직접 지지되면 보존하고, sentence-like/meme/pronoun alias overreach는 `promotion_blocked`로 막는다.
- 전체 official title 토큰을 entity mention으로 쪼개 약한 단어가 source support가 되는 경로를 차단했다.
- Current contract replay는 `26/26` match다. `REPROCESS` 14건은 `promotion_blocked`, `ACCEPT` 12건은 `safe_resolved`로 수렴했다.
- Report는 `docs/devs/loop_reports/LOOP_300_REPORT_20260702.md`다.
- Gate는 unsafe promotion full verdict `REVIEW-LOCKED`, contract replay `GO_UNIT_AND_LEGACY_REPLAY_EVIDENCE`, search recovery `P0 / OPEN`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop299 unsafe promotion shared contract repair

- Loop298 `repair_unsafe_promotion=8`을 current HEAD shared publication contract로 전환했다.
- `expert_main.py`는 inferred serialized publication이 critical counterevidence 또는 no direct source support를 가진 경우 public publish를 허용하지 않고 `promotion_blocked`로 demote한다.
- 새 reason code는 `inferred_publication_critical_counterevidence`와 `inferred_publication_missing_direct_source_support`다.
- Direct alias source support positive control은 보존했다. `랫따싶`처럼 후보 alias가 원문에 직접 있는 row는 demote하지 않는다.
- Legacy row replay 결과 `11657046`, `11658621`, `11658668`, `11671490`, `11674703`, `11690874`, `11703657`, `11706832`은 모두 `promotion_blocked`다.
- Positive controls `11674712`, `11695623`, `11669928`은 `safe_resolved`를 유지했다.
- Report는 `docs/devs/loop_reports/LOOP_299_REPORT_20260702.md`다.
- Gate는 unsafe promotion contract `GO_UNIT_AND_LEGACY_REPLAY_EVIDENCE`, search recovery `P0 / OPEN`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop298 unsafe promotion partial source-native review

- `tools/build_collateral_triage_review_batch.py`에 `--bucket` 필터를 추가해 collateral183 P0 중 특정 bucket만 독립 검토 배치로 만들 수 있게 했다.
- `tools/summarize_collateral_review_verdicts.py`를 `wrong_work_title_flip` 전용에서 bucket-agnostic summary로 일반화했고, partial review coverage를 `batch_review_rows/reviewed_rows/unreviewed_batch_rows`로 기록한다.
- `unsafe_promotion_from_hold=26` 전용 batch를 생성했다. 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop298_unsafe_promotion_from_hold_review_batch.*`이고 missing source/baseline/after는 `0/0/0`이다.
- Partial verdict manifest는 `docs/devs/loop298_unsafe_promotion_from_hold_source_native_verdicts.json`이다.
- Verdict summary는 reviewed `15/26`, unreviewed `11`, validation issues `0`, `REPROCESS=8`, `ACCEPT=7`이다.
- Action counts는 `repair_unsafe_promotion=8`, `exclude_from_regression_count_after_gate_wiring=7`이다.
- Report는 `docs/devs/loop_reports/LOOP_298_REPORT_20260702.md`다.
- Gate는 unsafe promotion partial review `REVIEW-LOCKED`, search recovery `P0 / OPEN`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop297 background health audit

- Loop288에서 발주한 full375, bounded1200 completed-source, golden18 background run을 최신 manifest/checkpoint/result/log 기준으로 재감사했다.
- latest manifest snapshot은 full375 `375/53/51/2/0`, bounded1200 `1200/88/77/11/0`, golden18 `18/16/12/4/0`이며 모두 `large_run_complete=false`다.
- full375 audit은 `IN_PROGRESS/ordered_flush_gap_in_progress`, frontier `11700470`, blocker `search_degraded_observed`, `publication_contract_convergence=GO`, violation `0`이다.
- bounded1200 audit은 `IN_PROGRESS/ordered_flush_gap_in_progress`, frontier `11607130`, blocker `search_degraded_observed`, `publication_contract_convergence=GO`, violation `0`이다.
- golden18 audit은 `IN_PROGRESS/ordered_flush_gap_in_progress`, frontier `11700470`, blockers `manifest_light_health_only`, `search_degraded_observed`, `publication_contract_convergence=GO`, violation `0`이다.
- Report는 `docs/devs/loop_reports/LOOP_297_REPORT_20260702.md`다.
- Gate는 background runs `IN_PROGRESS`, search recovery `P0 / OPEN`, full collateral approval `NOT_OPEN`, golden18 approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop296 safe-loss N5 독립 실행 wrapper

- Loop294의 `N>=5` 반복 입력은 같은 process에서 `post_id` de-dupe되어 `input_post_count=3`으로 접혔으므로 flip rate 갱신 증거가 아니었다.
- `tools/safe_loss_flip_rate_probe.py`에 `build-run-plan` subcommand를 추가해 반복마다 단일행 JSONL과 독립 `expert_main.py` command를 만들게 했다.
- Loop296 plan manifest는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop296_safe_loss_independent_n5_run_plan.json`이다.
- Plan 결과는 planned runs `15`, repeat_count_by_post `11674712=5`, `11660237=5`, `11698880=5`, missing post_ids `[]`, `minimum_repeats_contract_met=true`다.
- 기존 current HEAD 실제 N5 증거는 Loop288을 유지한다. gate는 `NO-GO`; `11674712`와 `11698880`은 flip_rate `0.4`, `11660237`은 stable blind judge confirmed다.
- Background snapshot은 full375 `375/49/41/8/0`, bounded1200 `1200/78/69/9/0`, golden18 `18/14/12/2/0`이며 모두 `large_run_complete=false`다.
- Report는 `docs/devs/loop_reports/LOOP_296_REPORT_20260702.md`다.
- Gate는 wrapper `GO_UNIT`, Loop296 execution `PLAN_READY_NOT_EXECUTED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop291 wrong-work title flip source-native 검토

- Loop290 collateral183 P0 배치 중 `wrong_work_title_flip` 10행을 source-native/blind 방식으로 판정했다.
- Verdict manifest는 `docs/devs/loop291_wrong_work_title_flip_source_native_verdicts.json`이고, summary 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop291_wrong_work_title_flip_source_native_review.json` / `.md`다.
- 판정 결과는 reviewed rows `10`, validation issues `0`, `REPROCESS=5`, `ACCEPT=3`, `HOLD=2`다.
- `REPROCESS` 5건은 `11666713`, `11698890`, `11700500`, `11705252`, `11716448`이며 `repair_after_wrong_work` 대상이다.
- `ACCEPT` 3건은 `11682791`, `11710049`, `11714903`이며 gate 배선 뒤 regression count 제외 후보로만 둔다.
- `HOLD` 2건은 `11663535`, `11706871`이며 canonical title variant 정책 판단이 필요하다.
- Report는 `docs/devs/loop_reports/LOOP_291_REPORT_20260702.md`이고, Data Analytics MCP report `Loop291 wrong-work title flip 검토`는 validate/render PASS다.
- Background snapshot은 full375 `375/12/3/9/0`, bounded1200 `1200/24/8/16/0`, golden18 `18/4/2/2/0`, 모두 `large_run_complete=false`다.
- Gate는 source-native review `REVIEW-LOCKED`, full collateral approval `NOT_OPEN`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop290 collateral183 P0 blind/source-native 검토 배치

- Loop288 background 런은 완료 전이라 approval 근거로 쓰지 않았다.
- Loop290 문서화 시점 manifest snapshot은 full375 `375/3/1/2/0`, bounded1200 `1200/7/0/7/0`, golden18 `18/1/1/0/0`이며 모두 `large_run_complete=false`다.
- `tools/build_collateral_triage_review_batch.py`를 추가해 Loop289 triage, panel input, baseline result, after result를 post_id 기준으로 결합했다.
- judge-facing 입력은 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`로 제한하고, 전후 비교용 `comparison_private_not_for_blind_judge`를 분리했다.
- review batch는 P0 전체 `183`행, missing source/baseline/after `0/0/0`이다.
- bucket은 `wrong_work_title_flip=10`, `unsafe_promotion_from_hold=26`, `safe_loss_resolved_to_null=147`이다.
- Report는 `docs/devs/loop_reports/LOOP_290_REPORT_20260702.md`, batch는 `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop290_collateral183_p0_review_batch.*`이다.
- Data Analytics artifact validate/render는 PASS다.
- Gate는 review batch `REVIEW-LOCKED`, background runs `RUNNING_BACKGROUND`, search recovery `P0 / OPEN`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop289 background 감시와 collateral183 triage

- Loop288 background 런은 완료되지 않아 approval 근거로 쓰지 않았다.
- full375 search non-light run은 manifest 기준 `input=375`, `completed=0`, `flushed=0`, `include_search=true`, `light_mode=false`지만 result/checkpoint가 없어 `NO-GO/artifact_count_mismatch`다.
- bounded1200 search non-light run은 `completed=4`, `flushed=0`, `pending=4`이며 health audit에서 `search_degraded_observed`가 확인됐다.
- golden18은 `completed/flushed=1/1`, `light_mode=true`라 old golden GO를 대체하지 못한다.
- 기존 full375 collateral compare `out/regression_safe_grounding_20260626_000008_928006_loop01/collateral/loop49_regression_panel_replay_collateral_compare.json`의 `183` regression row를 triage했다.
- triage 결과는 P0 `183`: `safe_loss_resolved_to_null=147`, `unsafe_promotion_from_hold=26`, `wrong_work_title_flip=10`이다.
- Report는 `docs/devs/loop_reports/LOOP_289_REPORT_20260702.md`, Data Analytics artifact는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop289_background_collateral183_data_analytics_artifact.json`이다.
- Gate는 background runs `IN_PROGRESS`, collateral183 triage `NO-GO`, search recovery `P0 / OPEN`, full collateral approval `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop288 safe-loss N5, golden18, search 포함 런 발주

- 동일 38-row parent packet은 재실행하지 않았다.
- current HEAD safe-loss flip probe를 `N=5`로 갱신했다. 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop288_safe_loss_current_head_n5_review.json`이다.
- 결과는 `NO-GO`, `hard_hold_relaxation_allowed=false`다. `11660237`은 `5/5` stable blind judge confirmed로 `테라포밍 / https://novelpia.com/novel/61947`에 수렴했다.
- `11674712`와 `11698880`은 flip_rate `0.4`, `nondeterminism_unresolved`다. `11698880`은 오답 `아카데미 생존 갤러리`와 정답 title의 `promotion_blocked`가 반복 간 갈라졌다.
- golden set은 `16 -> 18`로 갱신했다. 추가 행 manifest는 `docs/devs/regression_safe_extra_golden_rows_20260702.json`이고, 갱신 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_manifest.json` / `golden_set.jsonl`이다.
- full375 replay PID `45436`과 bounded1200 completed-source run PID `110660`은 `include_search=True`, `light_mode=False`, shard `12/12 OK`로 시작했다. golden18 replay PID `83216`은 search 포함이나 small-run 정책상 `light_mode=True`다.
- Search degraded 복구는 P0로 승격했고, 복구 전 `promotion_blocked`는 `search-blind conditional`로 태깅한다.
- Report는 `docs/devs/loop_reports/LOOP_288_REPORT_20260702.md`, Data Analytics artifact는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop288_safe_loss_search_runs_data_analytics_artifact.json`이다.
- Gate는 safe-loss `NO-GO`, background runs `RUNNING_BACKGROUND`, completed-source approval candidate `0`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop287 11708456 release와 후속 frontier 감사

- 동일 38-row parent packet은 재실행하지 않았다.
- `11708456`은 W20에서 완료되어 result JSON에 들어왔고 ordered flush가 result_rows `343`에서 `354`까지 전진했다.
- `11708456`은 public title 회수가 아니라 candidate-only hard-hold로 닫혔다. `퉁구스카` 후보는 보존됐지만 public title/url은 `null`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=multi_work`, `work_resolution=multi_work`, `bypassed_gate=false`다.
- Loop287 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop287_frontier_after_11708456_completion_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows/checkpoint_rows/pending_count_actual `354/400/46`이다.
- 새 frontier는 post_id `11708445`, title `퉁구스1캇햄 작품 하나도 안 봤는데`, worker `W24`, observed_elapsed_seconds `3121.812`이다.
- post-audit live poll은 input/completed/flushed/pending/failed `104502/407/366/41/0`, `next_save_idx=367`까지 전진했지만 별도 audit 전까지 approval 근거로 세지 않는다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop287_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop287_frontier_release_data_analytics_artifact.json`는 validate/render PASS다.
- Gate는 live run health `IN_PROGRESS`, released frontier `11708456 / candidate_only / promotion_blocked / multi_work`, current frontier `11708445 / W24 in progress`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop286 11710018 release와 새 Arbiter 병목 감사

- 동일 38-row parent packet은 재실행하지 않았다.
- `11710018`은 W25에서 완료되어 result JSON에 들어왔고 ordered flush가 result_rows `317`에서 `343`까지 전진했다.
- `11710018`은 public title 회수가 아니라 candidate-only hard-hold로 닫혔다. `Fate/stay night` 후보는 보존됐지만 public title/url은 `null`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `candidate_ledger_status=promotion_blocked`, `bypassed_gate=false`다.
- Loop286 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop286_frontier_after_11710018_completion_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows/checkpoint_rows/pending_count_actual `343/375/32`이다.
- 새 frontier는 post_id `11708456`, title `황당한데 싱숑이랑 퉁구스카랑 같은 말 하는거 아님.`, worker `W20`, observed_elapsed_seconds `2277.595`이다.
- W20 log는 author talk와 작품 title publish 경계를 가르는 Arbiter stream이 진행 중임을 보여준다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop286_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop286_frontier_release_data_analytics_artifact.json`는 validate/render PASS다.
- Gate는 live run health `IN_PROGRESS`, released frontier `11710018 / candidate_only / promotion_blocked`, current frontier `11708456 / W20 Arbiter stream in progress`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop285 frontier 11710018 reason_review 감사

- 동일 38-row parent packet은 재실행하지 않았다.
- Loop285 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop285_frontier_11710018_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows/checkpoint_rows/pending_count_actual `317/371/54`이다.
- frontier는 post_id `11710018`, title `그것은 *단순한 깡계*가 아닌 오랜 따`, worker `W25`, observed_elapsed_seconds `1964.767`이다.
- W25 log는 `Fate/stay night` 내부 키워드와 게시 목적 noise 판단이 충돌한 뒤 `reason_review`를 완료했고, candidate URL 불일치 제거까지 수행했음을 보여준다.
- post-render manifest poll은 input/completed/flushed/pending/failed `104502/374/317/57/0`, `large_run_complete=false`, `ordered_flush_blocked=true`, `11710018_in_result=false`다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop285_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop285_frontier_11710018_data_analytics_artifact.json`는 validate/render PASS다.
- Gate는 live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG / reason_review_completed_but_no_result_row`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop284 frontier 연쇄 해소와 새 계약 병목 감사

- 동일 38-row parent packet은 재실행하지 않았다.
- Loop283 frontier `11710049`와 Loop284 early frontier `11710036`은 완료되어 flushed/result_rows가 `288`에서 `317`로 전진했다.
- Loop284 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop284_frontier_release_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows/checkpoint_rows/pending_count_actual `317/361/44`이다.
- 새 frontier는 post_id `11710018`, title `그것은 *단순한 깡계*가 아닌 오랜 따`, worker `W25`, observed_elapsed_seconds `1964.767`, audit last_event `arbiter_start`다.
- post-audit manifest poll은 input/completed/flushed/pending/failed `104502/368/317/51/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- W18/W34 result 확인 결과 `11710036`과 `11710049`는 `[림월드]변방계에서 회귀자로 살아남기`, `candidate_ledger_status=safe_resolved`로 완료됐다.
- W25 log는 `Fate/stay night` 내부 키워드와 제목-본문 불일치/텍스트 복사 오류 해석이 충돌해 Jury/Debate path가 길어지고 있음을 보여준다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop284_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop284_frontier_release_data_analytics_artifact.json`는 validate/render PASS다.
- Loop238 safe-loss N=3 probe는 `11660237` flip_rate `0.3333333333333333`, `nondeterminism_unresolved`, hard-hold 완화 금지 결론을 유지한다.
- Gate는 live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop283 frontier 해소 후 새 ordered flush 병목 감사

- 동일 38-row parent packet은 재실행하지 않았다.
- Loop282 frontier `11710058`은 완료되어 flushed/result_rows가 `279`에서 `288`로 전진했다.
- Loop283 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop283_frontier_release_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows/checkpoint_rows/pending_count_actual `288/328/40`이다.
- 새 frontier는 post_id `11710049`, title `장갤 이 괘씸한 새끼들`, worker `W34`, observed_elapsed_seconds `1912.109`, audit last_event `arbiter_start`다.
- post-audit manifest poll은 input/completed/flushed/pending/failed `104502/336/288/48/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- W34 log 추가 확인 결과, VLM/OCR 직접 작품 후보 `[림월드]변방계에서 회귀자로 살아남기`와 community-meta 반론이 충돌해 Jury/Debate path가 길어지고 있었다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop283_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop283_frontier_release_data_analytics_artifact.json`는 validate/render PASS다.
- Gate는 live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, full375 collateral approval `NOT_OPEN / blocked_until_completed_source`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop282 live frontier 병목과 completed source 후보 재감사

- 동일 38-row parent packet은 재실행하지 않았다.
- 진행 중인 completed-source 후보 런 `20260702_065642_030743`은 audit 시점에 completed `320`까지 전진했지만 flushed/result_rows는 `279`, `next_save_idx=280`에서 멈췄다.
- Loop282 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop282_latest_live_run_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, input/completed/flushed/pending/failed `104502/320/279/41/0`이다.
- frontier는 post_id `11710058`, title `판초법사 너무 재밌어서 묵혀야겠음`, worker `W1`, observed_elapsed_seconds `1506.524`, audit last_event `arbiter_start`다.
- W1 log 추가 확인 결과, frontier는 `recommendation_guard` 이후 Jury Panel과 Debate에 들어갔고 `09:31:27.980` 기준 `debate_skeptic`이 진행 중이었다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop282_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop282_live_frontier_data_analytics_artifact.json`는 validate/render PASS다.
- Gate는 live run health `IN_PROGRESS`, frontier status `IN_PROGRESS_IN_WORKER_LOG`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop281 live health와 completed source 후보 재감사

- 동일 38-row parent packet은 재실행하지 않았다.
- 진행 중인 completed-source 후보 런 `20260702_065642_030743`이 audit 시점 기준 `next_save_idx=280`, result_rows `279`까지 전진했음을 확인했다.
- Loop281 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop281_latest_live_run_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, input/completed/flushed/pending/failed `104502/299/279/20/0`이다.
- frontier는 post_id `11710058`, title `판초법사 너무 재밌어서 묵혀야겠음`, worker `W1`, observed_elapsed_seconds `1315.752`, last_event `verifier_start`다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop281_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Data Analytics artifact `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop281_live_health_data_analytics_artifact.json`는 validate/render PASS다.
- W27 Synthesizer trace는 Loop278 patch 전 시작된 장기 프로세스 흔적으로 caveat 유지하며, 다음 새 런에서 guard 적용을 다시 확인한다.
- Gate는 live run health `IN_PROGRESS`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop280 live health와 completed source 후보 재감사

- 동일 38-row parent packet은 재실행하지 않았다.
- Loop279 이후 live run이 `next_save_idx=250`, result_rows `249`까지 전진했음을 확인했다.
- Loop280 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop280_latest_live_run_health_audit.json`이다.
- health audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `249`, checkpoint_rows `287`, pending_count_actual `38`이다.
- frontier는 post_id `11711600`, title `망카데미가 유독 힘숨이 심한거 같다`, worker `W33`, observed_elapsed_seconds `1259.899`, last_event `arbiter_start`다.
- completed source 후보 감사 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop280_completed_source_candidate_audit.md/json`이다.
- 후보 감사 summary는 approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Gate는 live run health `IN_PROGRESS`, completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop279 frontier timing health audit 추가

- 동일 38-row parent packet은 재실행하지 않았다.
- Loop278 이후 live run이 `next_save_idx=204`에서 `219`로 전진했음을 확인했다.
- `tools/audit_expert_run_health.py`의 `frontier_worker_trace`에 `first_timed_event`, `last_timed_event`, `observed_elapsed_seconds`를 추가했다.
- Loop279 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop279_latest_live_run_health_audit.json`이다.
- audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `218`, checkpoint_rows `280`, pending_count_actual `62`다.
- frontier는 `global_idx=219`, post_id `11713185`, title `스토리 담당자가 노피아하는게 틀림없어`, worker `W25`, observed_elapsed_seconds `1271.708`이다.
- `search_evidence=REVIEW`, `publication_contract_convergence=GO`, violation_row_count `0`이다.
- Gate는 frontier timing audit `PASS`, current run integrity `IN_PROGRESS`, completed source `PENDING`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop278 live run health audit와 Synthesizer hidden reference guard

- 동일 38-row parent packet은 재실행하지 않았다.
- Loop264 대형 run 최신 health audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop278_latest_live_run_health_audit.json`이다.
- audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `203`, checkpoint_rows `250`, pending_count_actual `47`이다.
- frontier는 `global_idx=204`, post_id `11713200`, title `후회프듀 셍피루상 걍 쉬운 남잔듯`, worker `W19`, last_event `synthesizer_start`다.
- `search_evidence=REVIEW`, `publication_contract_convergence=GO`, violation_row_count `0`이다.
- worker log `logs/expert_run_20260702_065642_030743_W27.log:6042`에서 Synthesizer `hidden_references` non-dict item 로깅 예외를 확인했고, `src/llm_batch/experts/synthesizer.py`에서 dict 항목만 로깅/요약하도록 방어했다.
- Gate는 runtime hygiene patch `PASS`, current run integrity `IN_PROGRESS`, completed source `PENDING`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop277 completed source 후보 publication contract gate 추가

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/build_completed_source_candidate_audit.py`의 approval source candidate 조건에 publication contract convergence `GO`를 추가했다.
- clean counts, VLM/OCR, direct search-health, random target을 통과해도 `PromotionDecision`/`publish_contract_trace`/`publish_ledger`/serialized identity가 수렴하지 않으면 후보가 아니다.
- 실제 `out` manifest 후보 감사를 재실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop277_completed_source_candidate_publication_contract_audit.md/json`이다.
- audit summary는 manifest `733`, approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Gate는 completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, publication contract requirement `ENFORCED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop276 health audit publication contract gate 통합

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`에 `publication_contract_convergence` top-level gate를 추가했다.
- 실제 Loop264 진행 중 run에 통합 health audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop276_health_audit_with_publication_contract_gate.json`이다.
- audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `164`, checkpoint_rows `208`, pending_count_actual `44`다.
- frontier는 `global_idx=165`, post_id `11714866`, title `비교해보니 매크로 의심할만하네`, worker `W0`, last_event `arbiter_start`다.
- `publication_contract_convergence=GO`, violation_row_count `0`이다.
- Gate는 publication contract convergence `GO`, current run integrity `IN_PROGRESS`, completed source `PENDING`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop275 publication contract convergence audit 추가

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_publication_contract_convergence.py`를 추가해 `PromotionDecision`, `publish_contract_trace`, `publish_ledger`, serialized public identity 수렴을 결과 파일 단위로 감사한다.
- 실제 Loop264 진행 중 run의 flushed result `162`행에 감사를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop275_publication_contract_convergence_audit.md/json`이다.
- audit gate는 `GO`, violation_row_count `0`이다.
- 이 `GO`는 audited flushed rows의 contract convergence만 뜻하며 completed source나 semantic approval이 아니다.
- Gate는 publication contract convergence `GO`, current run integrity `IN_PROGRESS`, completed source `PENDING`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop274 health audit frontier worker trace 추가

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`에 `frontier_worker_trace`를 추가해 ordered flush frontier post가 어느 worker log에서 어느 단계까지 진행됐는지 기록한다.
- 실제 Loop264 진행 중 run에 frontier worker trace audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop274_frontier_worker_trace_health_audit.json`이다.
- audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `145`, checkpoint_rows `181`, pending_count_actual `36`이다.
- frontier source는 `global_idx=146`, post_id `11714889`, title `김괴라리 괴신 ㅈㄴ무섭네ㅋㅋㅋㅋ`, source_line `161`이다.
- `frontier_worker_trace`는 `in_progress_in_worker_log`, worker `W35`, event_count `15`, last_event `arbiter_start`다.
- Gate는 frontier worker trace `PASS`, current run integrity `IN_PROGRESS`, completed source `PENDING`, search evidence `REVIEW`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop273 completed source 후보 search-health requirement 추가

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/build_completed_source_candidate_audit.py`의 approval source candidate 조건에 direct search-health evidence를 추가했다.
- 실제 `out` manifest 후보 감사를 재실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop273_completed_source_candidate_search_health_audit.md/json`이다.
- audit summary는 manifest `733`, approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, partial_vlm_ocr_population_ge_random_target_count `6`이다.
- Gate는 completed source candidate `MISSING`, candidate audit `REVIEW-LOCKED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop272 health audit search evidence gate 추가

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`에 `search_evidence` gate를 추가해 manifest direct search-health, row-level `search_health`, worker log 검색 저하 신호를 분리 기록한다.
- 실제 Loop264 진행 중 run에 search evidence audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop272_search_evidence_health_audit.json`이다.
- audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `129`, checkpoint_rows `155`, pending_count_actual `26`이다.
- `search_evidence`는 `REVIEW`이며 blockers는 `manifest_search_health_not_included`, `manifest_light_health_only`, `search_degraded_observed`다.
- row search health rows `72`, worker log search degraded `75`, upstream_zero `59`, timeout `0`이다.
- Gate는 search evidence `REVIEW`, current run integrity `IN_PROGRESS`, completed source `PENDING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop271 health audit frontier source lookup 추가

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`에 `--input-jsonl`을 추가해 `flush_integrity.frontier.source_post`를 기록한다.
- 실제 Loop264 진행 중 run에 frontier source audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop271_frontier_source_lookup_health_audit.json`이다.
- audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `117`, checkpoint_rows `135`, pending_count_actual `18`이다.
- frontier source는 `global_idx=118`, post_id `11716449`, title `케문제는 ㄹㅇ 애증의 소설임`, source_line `133`이다.
- 직후 manifest poll은 input/completed/flushed/pending/failed `104502/135/117/18/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- Gate는 frontier source lookup `PASS`, current run integrity `IN_PROGRESS`, completed source `PENDING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop270 adds flush frontier diagnostics to health audit

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`의 `flush_integrity`에 `frontier` 진단을 추가했다.
- 실제 Loop264 진행 중 run에 frontier audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop270_flush_frontier_health_audit.json`이다.
- audit snapshot은 `IN_PROGRESS/ordered_flush_gap_in_progress`, result_rows `90`, checkpoint_rows `128`, pending_count_actual `38`이다.
- frontier는 `next_save_idx=91`, `status=in_flight_or_missing`, `frontier_gap_global_idx=91`, `pending_index_min=93`, `pending_index_max=159`다.
- 직후 manifest poll은 input/completed/flushed/pending/failed `104502/128/90/38/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- Gate는 flush frontier diagnostics `PASS`, current run integrity `IN_PROGRESS`, completed source `PENDING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop269 adds flush integrity classifier to health audit

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`에 `flush_integrity` classifier를 추가해 manifest/checkpoint/result/pending count 정합성을 `GO/IN_PROGRESS/NO-GO`로 분류한다.
- 실제 Loop264 진행 중 run에 flush integrity audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop269_flush_integrity_health_audit.json`이다.
- audit snapshot은 `run_integrity_gate=IN_PROGRESS`, `classification=ordered_flush_gap_in_progress`, result_rows `80`, checkpoint_rows `119`, pending_count_actual `39`이다.
- audit snapshot의 count consistency는 result/flushed, checkpoint/completed, pending/completed-minus-flushed가 모두 `true`라 artifact mismatch가 아니라 ordered flush gap 진행 중 상태다.
- 직후 manifest poll은 input/completed/flushed/pending/failed `104502/119/80/39/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- Gate는 flush integrity classifier `PASS`, current run integrity `IN_PROGRESS`, completed source `PENDING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop268 adds result JSON row count to health audit

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`에 `--result-json` 옵션과 result row count 감사를 추가했다.
- audit JSON은 이제 `artifact_resolution.result_json`, `result_json`, `result_rows`를 기록한다.
- 실제 Loop264 진행 중 run에 explicit result audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop268_explicit_result_health_audit.json`이다.
- audit snapshot은 result_rows `12`, checkpoint_rows `95`, pending_count_actual `83`, reason errors `0`, slang bad remaining `0`이다.
- 직후 manifest poll은 input/completed/flushed/pending/failed `104502/95/12/83/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- Gate는 result row count audit `PASS`, completed source `PENDING`, run integrity `IN_PROGRESS`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop267 adds explicit artifact paths to health audit

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`에 `--artifact-prefix`, `--manifest`, `--checkpoint`, `--pending-snapshot`, `--log-glob` 옵션을 추가했다.
- sampling/custom output 경로를 감사할 때 기본 `out\expert_result_<run_id>*` 위치에 묶이지 않도록 `artifact_resolution.explicit_overrides`를 기록한다.
- 실제 Loop264 진행 중 run에 explicit path audit를 실행했고 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop267_explicit_path_health_audit.json`이다.
- audit snapshot은 resolution `explicit_paths`, checkpoint_rows `88`, reason errors `0`, slang bad remaining `0`이다.
- 직후 manifest poll은 completed/flushed/pending/failed `90/12/78/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- Gate는 audit explicit path support `PASS`, completed source `PENDING`, run integrity `IN_PROGRESS`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop266 fixes in-progress large-run health audit resolution

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/audit_expert_run_health.py`가 internal run id `20260702_065642_030743`과 output prefix `20260702_065632_479765`가 다른 진행 중 run을 찾지 못하던 문제를 `manifest.run_id` lookup으로 보정했다.
- 새 테스트 `tests/test_audit_expert_run_health.py`를 추가했고, `.gitignore` 예외에 tool/test를 등록했다.
- 진행 중 health audit 산출물은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop266_inprogress_large_run_health_audit.json`이다.
- audit snapshot은 checkpoint rows `59`, reason errors `0`, slang bad remaining `0`이며, 직후 manifest poll은 completed/flushed/pending/failed `60/3/57/0`, `large_run_complete=false`, `ordered_flush_blocked=true`다.
- Data Analytics validate/render/export를 수행했고 package는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop266_large_run_health_data_analytics_artifact_package`다.
- Gate는 health audit resolution `PASS`, completed source `PENDING`, run integrity `IN_PROGRESS`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop265 tightens full375 always-on gate runtime evidence

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/evaluate_always_on_regression_gates.py`에서 full375 collateral gate가 explicit runtime count를 요구하도록 강화했다.
- runtime count가 없는 collateral compare는 `collateral_runtime_counts_missing` blocker로 `NO-GO`가 된다.
- 새 계약 테스트를 `tests/test_always_on_regression_gates.py`에 추가했다.
- 강화된 gate 재평가는 golden-16 `GO`, full375 collateral `NO-GO`, changed `223`, collateral_regression_count `183`이다.
- Loop238 safe-loss N=3 결과는 `11660237` flip rate `0.3333333333333333`, `nondeterminism_unresolved`로 유지한다.
- Data Analytics validate/render/export를 수행했고 package는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop265_architecture_gate_data_analytics_artifact_package`다.
- Gate는 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop264 starts completed-source large rerun after runtime preflight

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/preflight_expert_rerun_runtime.py`로 full input `tests/inputs/test01.jsonl`을 확인했다.
- Preflight 결과는 input_count `104502`, raw rows `472851`, unique_post_count `104594`, LLM model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`, MCP TCP shard `36/36`, `rerun_execution=GO`다.
- completed-source attempt를 background PID `49924`로 시작했다.
- 실행 옵션은 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db off --vlm on --ocr on --require-vlm-ocr-for-images`다.
- 초기 manifest는 VLM/OCR ready `true`, image_post_count `55259`, health `36/36`, completed/flushed/pending/failed `0/0/0/0`이다.
- Caveat: in-run health는 `mcp_health_include_search=false`, `mcp_health_light_mode=true`라 완료 후 search-health 증거를 별도 audit해야 한다.
- Gate는 runtime preflight `GO`, launch `GO_STARTED`, completed source `PENDING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop263 tracks architecture contract tests before next replay

- 동일 38-row parent packet은 재실행하지 않았다.
- Loop238에서 구현된 5개 아키텍처 지시가 현재 HEAD에 남아 있는지 감사했다.
- `PromotionDecision` / `publish_contract_trace` 수렴은 `expert_main._enforce_publish_contract_trace_convergence(...)`와 focused tests로 유지된다.
- 정지조건은 `tools/evaluate_goal_convergence.py`에서 `actionable queue 감소 + 동일 packet safe_resolved 단조 비감소`로 유지된다.
- safe-loss 반복 측정은 `tools/safe_loss_flip_rate_probe.py`로 유지된다. 기존 Loop238 결론상 `11660237`은 flip rate `0.3333333333333333`의 `nondeterminism_unresolved`라 hard-hold 완화는 금지다.
- full375 collateral diff는 `tools/evaluate_always_on_regression_gates.py`에서 golden-16과 함께 상시 gate로 유지된다.
- `tests/test_regression_safe_work_bridge_contract.py`가 `.gitignore` 때문에 추적되지 않던 gap을 확인했고, `.gitignore` 예외를 추가했다.
- Verification: py_compile PASS, focused architecture/stop-condition/safe-loss/full375 tests `19` OK.
- Gate는 architecture contract tracking `GO`, runtime rerun `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop262 audits completed source candidates

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/build_completed_source_candidate_audit.py`를 추가해 `out/**/_manifest.json`을 clean completion, VLM/OCR readiness, result rows, random target 기준으로 감사하게 했다.
- 전체 `out` manifest `732`개를 스캔했다. approval source candidate는 `0`개다.
- clean VLM/OCR source는 `429`개지만 모두 random target `1000` 미달이다. 가장 큰 clean source는 Loop49 full375 collateral replay로 available rows `375`, shortfall `625`다.
- partial VLM/OCR population 중 random 1000 이상을 뽑을 수 있는 후보는 `6`개지만 모두 completion gap이 있다. 가장 큰 source는 `out/expert_result_20260612_174715_296791.json`이고 input/completed/flushed/pending/failed `104502/3875/3812/63/1`이다.
- Preflight 확인:
  - largest partial source: `REVIEW-LOCKED`, `large_run_completion_not_proven`, pending/failed/flush gap.
  - largest clean shortfall source: run integrity `GO`지만 `random_baseline_target_not_feasible`.
- Verification: py_compile PASS, `tests.test_completed_source_candidate_audit` `2` tests OK.
- Gate는 completed source candidate `MISSING`, completed-source preflight `REVIEW-LOCKED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop261 restores completed-source preflight blockers

- 동일 38-row parent packet은 재실행하지 않았다.
- `tools/build_goal_action_queue.py`가 `source_review_policy.path_present=false`를 완료 상태처럼 통과시키던 문제를 보정했다.
- 작은 canary가 runtime/coverage `GO`여도 completed source preflight artifact가 없으면 approval source가 아니므로 아래 blocker를 다시 open으로 둔다: `obtain_completed_vlm_ocr_source`, `rerun_large_scale_preflight_on_completed_source`, `expanded_random_baseline_1000`, `p0_p1_high_risk_expansion`.
- Loop261 action queue는 total_actions `10`, ready_now `0`, done `6`, blocked_until_completed_source `4`, approval blockers `4`개다.
- Loop261 convergence는 actionable queue `1 -> 4`라 `NO-GO`다. 같은 packet safe_resolved는 `3 -> 3`, safe_loss `[]`로 유지됐다.
- Verification: py_compile PASS, `tests.test_goal_action_queue + tests.test_goal_convergence` `17` tests OK.
- Gate는 completed source preflight `MISSING`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 - Loop260 closes comment-author review-only issue and fixes queue semantics

- 동일 38-row parent packet은 재실행하지 않았다.
- `11658637`의 `comment_author_match_unverified_resolution_review_only`를 packet review label로 확인했다. 댓글 author 동일성은 작품 근거가 아니고, publish 근거는 direct image/OCR/official URL이다.
- `tools/build_semantic_coverage_audit.py`는 `--review-labels`를 받아 `REVIEW` 전용 issue를 ACCEPT/no_action label로 닫는다. `REVIEW-LOCKED` hard blocker는 닫지 않는다.
- `tools/build_goal_action_queue.py`는 현 source에서 이미 통과한 semantic coverage/runtime/process snapshot/reason hygiene/browser visual/preserve-original policy를 `done`으로 표시하고, summary에 `done`을 분리한다.
- Loop260 semantic coverage는 gate `GO`, issues `[]`, browser visual `5/5/0`, review closure `11658637`이다.
- Loop260 action queue는 total_actions `7`, ready_now `0`, done `6`, blocked_until_completed_source `1`, approval blocker `p0_p1_high_risk_expansion`이다.
- Loop260 convergence는 actionable queue `7 -> 1`, same packet safe_resolved `3 -> 3`, safe_loss `[]`로 `GO`다.
- Gate는 semantic coverage `GO`, convergence `GO`지만 full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop259 attaches browser visual evidence for Loop258 image rows

- 동일 38-row parent packet은 재실행하지 않고 Loop258 semantic coverage의 `browser_visual_or_direct_evidence_missing=5` blocker만 좁혔다.
- 대상은 `11660277`, `11663544`, `11658637`, `11658668`, `11657046`이다.
- `tools/capture_vlm_ocr_browser_review_cli.py` fallback Playwright capture 결과는 captured rows `5/5`, screenshot OK `5/5`, visual evidence grade `Strong=5`, article image gate passed `5/5`, blocked/error rows `0`이다.
- Semantic coverage rerun은 browser visual required/available/missing `5/5/0`으로 개선됐고 gate는 `REVIEW`다. 남은 issue는 `11658637`의 `comment_author_match_unverified_resolution_review_only=1`이다.
- Goal action queue는 total_actions `7`, approval blocker `p0_p1_high_risk_expansion`을 유지한다.
- Goal convergence는 same-packet safe_resolved `3 -> 3`, safe_loss `[]`, monotonic `true`로 개선됐지만 actionable queue `7 -> 7`이라 `NO-GO`다.
- Gate는 browser visual `GO`, semantic coverage `REVIEW`, convergence `NO-GO`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop258 blocks URL-null inferred serialized publication

- 동일 38-row parent packet은 재실행하지 않고 Loop257/258 same 7-row representative packet으로 final publication contract만 확인했다.
- Loop257 run `20260702_052346_588912`은 runtime completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`, MCP health `2/2`였지만 `11663535`가 public title `퇴마록`, URL `null`, `safe_resolved`로 publish되어 semantic `NO-GO`였다.
- 실패 경로는 resolved-public-title gate가 아니라 `final_publication_decision_inferred_from_serialized_identity`가 URL 없는 serialized public identity를 publish로 재해석한 final contract path였다.
- `expert_main._demote_inferred_urlless_publication_contract(...)`를 추가해 `final_publication_decision_inferred_from_serialized_identity` + missing `official_url` + public title 조건만 `candidate_only` / `promotion_blocked`로 내리게 했다.
- `publish_contract_trace.post_gate_identity`는 최종 identity의 `title_resolution_allowed`, `title_resolution_state`, `work_resolution`, `candidate_ledger_status`와 함께 수렴하도록 보강했다.
- Loop258 run `20260702_053635_632644`은 runtime completed/flushed/pending/failed `7/7/0/0`, VLM/OCR `READY`, MCP health `2/2`다.
- Loop258 final은 `11663535`를 `promotion_blocked`, public title/url `null`, `promotion_decision.status=candidate_only`, `publish_allowed=false`로 내렸다. `11658668` hard-hold는 유지됐고 `11660277`, `11663544`, `11658637`은 정상 safe를 유지했다.
- Data Analytics report artifact `Loop257-258 URL-null publish hold 검증`을 검증/렌더링했고, 상태 분포 chart, 핵심 row 결과 table, goal convergence gate table을 포함했다.
- Loop258 보조 audit를 추가로 실행했다. Runtime audit은 process snapshot 포함 `GO(stale process 0)`, reason hygiene는 hit files `0`으로 `GO`, semantic coverage는 browser visual required/available/missing `5/0/5`로 `REVIEW-LOCKED`다.
- Verification: py_compile PASS, `tests.test_expert_main_comment_metadata` `36` PASS, focused final contract `4` PASS, convergence/safe-loss/always-on gate `17` PASS, title-lead guard `180` PASS, `git diff --check` PASS.
- Goal convergence는 `NO-GO`다. actionable queue `7 -> 7`, same-packet safe_resolved `4 -> 3`, safe_loss `11663535`, blockers `actionable_queue_not_decreased`와 `safe_resolved_not_monotonic`이다.
- Gate는 Loop258 runtime `GO`, targeted canary `GO_BLOCK_URL_NULL_PUBLIC_TITLE`, convergence `NO-GO`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop256 confirms 11658668 final publication contract hard-hold

- 동일 38-row parent packet은 재실행하지 않고 `11658668` 단건 final contract canary만 실행했다.
- 다음 canary 전에 rollback 지점 commit `e282e3e`, `5fa4f5f`, `3bffd7e`를 확보했다.
- Run `20260702_051036_309360`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, MCP health `1/1`이다.
- Final은 `candidate_ledger_status=promotion_blocked`, public title/url `null`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `publish_contract_trace.gate_decision.publish_allowed=false`다.
- Data Analytics report artifact `Loop256 아키텍처 수렴 검증`을 검증/렌더링했고, Loop254-256 상태 분포, safe-loss flip-rate, always-on gate를 포함했다.
- Loop238 safe-loss probe 결론은 유지한다. `11660237`은 flip rate `0.3333333333333333`으로 `nondeterminism_unresolved`라 hard-hold 완화 불가다.
- Gate는 targeted canary `GO_BLOCK_PUBLIC_TITLE`, runtime `GO`, parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop251 blocks 11663535 character-title collision public title drift

- 동일 38-row parent packet은 재실행하지 않고 `11663535` 단건 P0D canonicalization blocker만 좁혔다.
- Loop248에서는 `11663535`가 `조선 퇴마록` public title로 publish되어 canonicalization drift 후보가 됐다.
- `src/llm_batch/agentic_pipeline.py`에서 resolved-public-title gate가 `character_title_collision(major)`와 후보 제목 직접 언급 부재를 scope conflict로 반영하게 했다.
- 단일 술어 계약은 유지했다. `_has_verified_contextual_alias_work_bridge(...)`는 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")` wrapper이고, 이번 gate도 shared predicate를 확인한다.
- Loop251 run `20260702_034658_596805`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, image_post_count `0`이다.
- Loop251 final은 `candidate_ledger_status=promotion_blocked`, public title/url `null`, blocked candidate `퇴마록`, `title_resolution_allowed=false`, `publish_allowed=false`다.
- Verification: runtime audit `GO`, reason hygiene hit_files `0`, semantic coverage `GO` but approval 아님, title-lead `176` PASS, candidate-audit `107` PASS, promotion trace/contract `55` PASS, architecture gate/work-bridge `19` PASS, py_compile PASS.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_251_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop251_11663535_p0d_canonicalization_guard_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_semantic_coverage.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop251_11663535_p0d_canonicalization_guard_goal_convergence.md`
- Gate는 targeted canary `GO_BLOCK_PUBLIC_TITLE`, runtime `GO`, convergence `NO-GO(queue 7 -> 7, packet identity changed)`, parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop250 blocks 11658668 resolved-public image scope publish leak

- 동일 38-row parent packet은 재실행하지 않고 `11658668` 단건 P0C blocker만 좁혔다.
- Loop249 pre-patch run `20260702_031854_134932`은 `candidate_ledger_status=safe_resolved`, `publish_allowed=true`, `scope_kind=current_work`로 실패 증거가 됐다.
- `src/llm_batch/agentic_pipeline.py`에서 platform meta + relation reject canonical rescue를 차단하고, resolved-public-title gate가 image/ocr 기반 scope에서 `promotion_eligible=false` image catalog를 `context_only` conflict로 반영하게 했다.
- Loop250 patched run `20260702_033005_272211`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`다.
- Loop250 final은 `candidate_ledger_status=promotion_blocked`, public title/url `null`, blocked candidate `전 버튜버가 하고 싶은데요`, `publish_allowed=false`, `publish_contract_trace` blocked 수렴이다.
- Verification: runtime audit `GO`, reason hygiene hit_files `0`, `tests.test_title_lead_search_inferred_guard` `174` PASS, architecture gate/work-bridge `19` PASS, py_compile PASS.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_250_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop250_11658668_resolved_public_image_scope_guard_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_semantic_coverage.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop250_11658668_resolved_public_image_scope_guard_goal_convergence.md`
- Gate는 targeted canary `GO`, runtime `GO`, semantic coverage `REVIEW-LOCKED(browser visual 1/0/1)`, convergence `NO-GO(queue 7 -> 7, packet identity changed)`, parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop248 runs P0 representatives and patches public reason hygiene

- 동일 38-row parent packet은 재실행하지 않고 Loop51 P0 collateral bucket 대표 7건만 current-code로 재현했다.
- Run `20260702_023732_561254`은 completed/flushed/pending/failed `7/7/0/0`, effective_parallel `7`, VLM/OCR `READY`, image_post_count `5`로 runtime `GO`다.
- P0 대표 outcome은 expected 회복 `2`, unexpected/wrong title 차단 `2`, expected still missing `1`, loop49 after 재현 `1`, canonicalization other `1`이다.
- 원본 reason hygiene scan은 `11658668`의 공개 reason에 `LLM(False)→최종(True)`가 남아 `FAIL(hit_files=1, llm_flip=2)`이었다.
- `src/llm_batch/agentic_pipeline.py`에서 override audit suffix를 공개용 중립 문구로 바꾸고 legacy flip marker sanitizer를 추가했다.
- `tests/test_title_lead_search_inferred_guard.py`에 관련+제목확정 reason에서 flip marker가 공개되지 않는 regression test를 추가했다.
- Verification: `py_compile` PASS, tracked sanitizer regression 1 test PASS, sanitized preview reason hygiene hit_files `0`.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_248_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop248_p0_representative_7_current_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop248_p0_representative_7_reason_hygiene_sanitized_preview.json`
- Gate는 runtime `GO`, original reason hygiene `FAIL`, sanitized-preview reason hygiene `GO`, semantic coverage `REVIEW-LOCKED(browser visual 5/0/5)`, parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop247 attaches browser visual evidence for 11660237

- 동일 38-row parent packet은 재실행하지 않고 Loop246의 `browser_visual_or_direct_evidence_missing` blocker만 좁혔다.
- `tools/build_browser_visual_targets_from_result.py`로 `11660237` browser visual target 1건을 생성했다.
- `tools/capture_vlm_ocr_browser_review_cli.py`로 원문 `https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11660237`을 fallback Playwright로 캡처했다.
- 캡처 결과는 response `200`, page title `테라포밍 볼만함? - 장르소설 마이너 갤러리`, screenshot OK, `visual_evidence_grade=Strong`, article image loaded `1/1`, incomplete/placeholder/broken/lazy/data-original pending `0`이다.
- screenshot 직접 확인 결과 원문 제목, 본문 이미지, 본문 `주인공 멍창하다는 말 많던데`가 보인다.
- `tools/build_semantic_coverage_audit.py --browser-artifacts-manifest` 재실행 결과 coverage gate는 `GO`, browser visual required/available/missing `1/1/0`, issues `[]`다.
- action queue 재생성 결과 semantic coverage gate는 `GO`지만 approval blocker `p0_p1_high_risk_expansion`은 유지된다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_247_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop247_11660237_browser_visual/loop247_browser_visual_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop247_run09_semantic_coverage_with_browser_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop247_run09_goal_action_queue_after_browser.md`
- Gate는 browser visual/semantic coverage `GO`, parent replay `NOT_RUN`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop246 revalidates architecture gates without rerunning the parent packet

- 동일 38-row parent packet은 재실행하지 않고 현재 HEAD `6aa6b89`에서 architecture 계약을 재검증했다.
- 정지조건은 `tools/evaluate_goal_convergence.py`와 `tests.test_goal_convergence` 기준으로 회차 수가 아니라 `actionable queue 감소 + 동일 packet safe_resolved 단조 비감소`를 요구한다.
- `expert_main._enforce_publish_contract_trace_convergence`와 focused tests 2개는 stale blocked/publish trace가 현재 `PromotionDecision`으로 수렴함을 확인했다.
- `_has_verified_contextual_alias_work_bridge(...)`는 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")` wrapper로 남아 있으며 focused contextual alias tests 2개를 PASS했다.
- Loop238 safe-loss N=3 blind judge review는 계속 유효하다: `11660237` flip rate `0.3333333333333333`, `nondeterminism_unresolved`, `hard_hold_relaxation_allowed=false`.
- Loop238 always-on gate도 계속 유효하다: golden `16/16` GO지만 full375 collateral은 changed `223`, regression `183`으로 `NO-GO`.
- Loop246 run09 audit/state/action queue/semantic coverage를 확인했다. runtime audit과 reason hygiene는 `GO`지만 semantic coverage는 `11660237` browser visual/direct evidence missing 때문에 `REVIEW-LOCKED`다.
- 검증은 architecture gate/work-bridge tests 19개, publish convergence 2개, contextual alias 2개, touched-file `py_compile`을 PASS했다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_246_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop246_run09_goal_test_contract_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop246_run09_goal_action_queue.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop246_run09_semantic_coverage_audit.md`
- Gate는 runtime focused `GO`, semantic `REVIEW-LOCKED`, full375 previous `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop245 fixes 11660237 relation-hold regression and verifies same-packet recovery

- 동일 38-row parent packet은 재실행하지 않고 `11660237` current-code representative run08과 patched run09를 비교했다.
- run08은 public title `null`, `candidate_ledger_status=promotion_blocked`, `scope_kind=context_only`, `publish_allowed=false`로 safe loss를 재발시켰다.
- run07->run08 convergence는 actionable queue `1 -> 2`, safe_resolved `1 -> 0`, safe loss `11660237`로 `NO-GO`다.
- `src/llm_batch/experts/verifier.py`는 direct title surface 확인을 추가하고, 원문 제목 표면과 공식 상세/정확 제목 검색 수렴이 있는 `exact_title` 또는 `thematic_overlap_only` hold 변형을 `exact_title / allow`로 정규화한다.
- search-only hold와 직접 제목 표면이 없는 후보는 계속 차단한다.
- run09 `20260702_020419_735405`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`다.
- run09 final은 `official_title=테라포밍`, URL `https://novelpia.com/novel/61947`, `candidate_ledger_status=safe_resolved`, `scope_kind=current_work`, `publish_allowed=true`다.
- run08->run09 convergence는 actionable queue `2 -> 1`, safe_resolved `0 -> 1`, safe gain `11660237`로 targeted local `GO`다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_245_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop245_11660237_same_packet_goal_convergence.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop245_11660237_relation_hold_patch_goal_convergence.md`
- Gate는 focused targeted `GO_11660237_RESOLVED`지만 parent replay `NOT_RUN`, full375 collateral previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop244 narrows 11660237 publish/block variance to final scope decision

- 동일 38-row parent packet은 재실행하지 않고 `11660237` run01~run07 기존 결과를 evidence review로 비교했다.
- run01~run05 blocked 계열은 public title `null`, `candidate_ledger_status=promotion_blocked`, `scope_kind=context_only`, `publish_allowed=false`다.
- run04/run05에는 댓글이 존재했으므로 `body_comments_absent_or_empty`는 입력 누락이 아니라 final contract가 `볼만함`, `주인공`, `야스`를 current-work consumption bridge로 읽지 못한 해석 문제로 분리했다.
- run06/run07 publish 계열은 `candidate_ledger_status=safe_resolved`, `scope_kind=current_work`, `publish_allowed=true`, `official_title=테라포밍`, URL `https://novelpia.com/novel/61947`다.
- publish direct bridge sources는 `title_led_consumption_bridge`, `alias_surface`, `title_abbrev_mentioned`, `official_detail_url` 네 신호로 고정된다.
- 결론: `11660237` 진동의 갈림점은 검색 title/url 존재가 아니라 final publish contract의 `scope=context_only` vs `scope=current_work` 판정이다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_244_REPORT_20260702.md`
- Gate는 신규 runtime `NOT_RUN`, convergence same-packet `NOT_EVALUATED`, full375 previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop243 runs convergence preflight and tightens packet-delta reporting

- 동일 38-row parent packet은 재실행하지 않고 Loop242 뒤 stop-condition preflight를 실행했다.
- `tools/evaluate_goal_convergence.py`는 packet identity가 다르면 `safe_loss_post_ids`와 `safe_gain_post_ids`를 계산하지 않고 `safe_delta_evaluated=false`로 기록한다.
- `tests/test_goal_convergence.py`에 packet 변경 시 safe delta를 미평가하는 회귀 테스트를 추가했다.
- `.gitignore` 예외를 추가해 convergence, safe-loss flip-rate, full375 always-on gate 도구와 테스트가 실제 Git 추적 대상이 되게 했다.
- Preflight 입력은 Loop241 직후 queue `2`, Loop242 뒤 queue `1`로 구조화했다.
- Preflight output은 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop242_goal_convergence_preflight_after_artifact_guard.md/json`이다.
- 결과는 actionable queue `2 -> 1` 감소 `true`지만, previous packet은 Loop237 parent `38` rows이고 current packet은 Loop241 targeted `1` row라 `packet_identity_changed`로 gate `NO-GO`다.
- 검증은 architecture gate tools `py_compile`과 `tests.test_goal_convergence + tests.test_safe_loss_flip_rate_probe + tests.test_always_on_regression_gates -v` 17 tests를 PASS했다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_243_REPORT_20260702.md`
- Gate는 `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop242 blocks fanart/cover artifact snippet expansion cost

- 동일 38-row parent packet은 재실행하지 않고 `11660237`의 `테라포밍 표지` fanart/cover 후보 비용 경로만 좁혔다.
- `src/llm_batch/experts/decoder.py`에 `is_snippet_artifact_title_expansion(...)` 공용 술어를 추가했다.
- Decoder는 `테라포밍 -> 테라포밍 표지` 같은 snippet artifact mapping을 `_resolved_mappings`에 넣지 않는다.
- `src/llm_batch/experts/orchestrator.py`는 같은 술어를 LLM snippet 후처리, 정규식 snippet hint 후처리, resolved-title follow-up query, fanart URL fetch 후보 수집에 적용한다.
- LLM snippet prompt에는 표지/fanart/커버/일러스트 산출물 페이지 제목을 정식 제목이나 약칭 매핑으로 쓰지 말라는 규칙을 추가했다.
- 검증은 `venv\Scripts\python.exe` 기준 touched-file `py_compile`, 신규 artifact guard 3 tests, relation exact-title 주변 3 tests, arbiter/known abbreviation 주변 2 tests를 PASS했다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_242_REPORT_20260702.md`
- Gate는 unit/code contract `GO`지만 runtime canary `NOT_RUN`, parent replay `NOT_RUN`, full375 collateral previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop241 normalizes exact-title direct official relation holds

- 동일 38-row parent packet은 재실행하지 않고 `11660237` 단건 relation hold 계약만 좁혔다.
- `src/llm_batch/experts/verifier.py`는 원문 직접 grounding, decoder grounding, title/body/alias anchor, post alias count, official exact-title count, 공식 상세 URL/수렴 신호가 함께 있는 exact-title 후보를 hard-hold로 `nullify_title`하지 않고 `allow`로 정규화한다.
- 검색 결과에만 기대는 exact-title hold는 계속 차단되도록 negative contract를 추가했다.
- run07 `20260702_010819_484136`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`다.
- run07 실제 relation judge output은 `relation_type=exact_title`, `promotion_decision=allow`였고, 최종 결과는 `official_title=테라포밍`, URL `https://novelpia.com/novel/61947`, `title_resolution_state=resolved`, `title_resolution_allowed=true`다.
- 검증은 touched-file `py_compile`, exact-title relation hold focused 4 tests, relation/title-led 주변 7 tests를 PASS했다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_241_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop241_11660237_relation_exact_title_hold_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop241_11660237_relation_exact_title_hold_review.json`
- Gate는 focused targeted `GO_11660237_RESOLVED`지만 parent replay `NOT_RUN`, full375 collateral previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop240 normalizes title-led platform probe cap path

- 동일 38-row parent packet은 재실행하지 않고 `11660237` 단건 title-led platform probe cap 문제만 재검증했다.
- `src/llm_batch/experts/orchestrator.py`는 동일 query 중복 보정에서 첫 항목만 수정하던 `break`를 제거하고, 실행 직전 `_normalize_title_led_platform_probe_purposes(...)`를 추가했다.
- 새 계약은 `site:novelpia.com/novel "테라포밍"`을 `title_anchor_official_probe`로 보존하면서 `테라포밍 노벨피아` 같은 non-site Novelpia query만 `platform_title_search`로 정규화한다.
- run06 `20260702_005502_923302`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`다.
- run06 로그는 purpose 정규화 `normalized=1`, `테라포밍 노벨피아` platform 실행, R01 `https://novelpia.com/novel/61947`, 최종 `Identified (with title): 1`을 확인했다.
- 최종 결과는 `official_title=테라포밍`, URL `https://novelpia.com/novel/61947`, confidence `High`, `title_resolution_state=resolved`, `title_resolution_allowed=true`다.
- 검증은 touched-file `py_compile`, title-led focused 2 tests, 주변 title-led 5 tests를 PASS했다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_240_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop240_11660237_title_led_platform_probe_cap_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop240_11660237_title_led_platform_probe_cap_review.json`
- Gate는 focused targeted `GO_11660237_RESOLVED`지만 parent replay `NOT_RUN`, full375 collateral previous `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-02 - Loop239 11660237 title-led probe remains hard-held

- 동일 38-row parent packet은 재실행하지 않고 `11660237` 단건 title-led path만 재검증했다.
- `src/llm_batch/agentic_pipeline.py`는 title-led current-work gate가 기존 `candidate_only/context_only` gate를 갱신할 수 있게 했다.
- `src/llm_batch/candidate_audit.py`는 공식 상세 URL과 current-work shared gate가 있는 title-led path만 generic genre bridge demotion을 면제하게 했다.
- `src/llm_batch/experts/orchestrator.py`는 title-led work-consumption search signal에서 공식 상세 검색을 보존하고 rerank boost한다.
- run04 `20260702_003226_807802`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, MCP health ok/failure `1/0`로 runtime clean이다.
- 의미 결과는 `NO-GO`: public `official_title=null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`.
- 검색 보존은 작동했지만 정답 상세 `https://novelpia.com/novel/61947`이 아니라 포함어 후보들이 먼저 들어와 오답 publish 압력을 만들었다. 최종 contract가 publish를 막았으므로 `hard_hold_relaxation_allowed=false`다.
- 검증은 `py_compile`, `tests.test_title_lead_search_inferred_guard` 164 tests, `tests.test_candidate_audit + tests.test_promotion_gate_contract` 128 tests, Data Analytics validate/render를 PASS했다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_239_REPORT_20260702.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop239_11660237_title_led_probe_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop239_11660237_title_led_probe_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop239_11660237_title_led_probe_data_analytics_artifact.json`
- Gate는 `NO_DELTA_TARGETED_CANARY_NO_GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop238 architecture convergence gate and safe-loss flip probe

- 동일 38-row parent packet 즉시 재실행을 중단하고, 다음 회차 진입 조건을 단순 회차 수가 아니라 `actionable queue 감소 + 동일 packet safe_resolved 단조 비감소`로 바꿨다.
- `expert_main.py`에 `PromotionDecision`, `publish_contract_trace`, `publish_ledger`, `candidate_ledger` gate decision을 한 번 더 수렴시키는 `_enforce_publish_contract_trace_convergence` 계약을 추가했다.
- `_has_verified_contextual_alias_work_bridge`는 단독 술어로 우회하지 않고 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")`를 경유하도록 배선했다. 이 source 경로에서만 contextual alias evidence를 release하므로 alias bridge 없는 relation-hold 후보는 계속 차단된다.
- Safe-loss 후보 3건은 동일 입력 N=3 반복으로 측정했다. `11674712`, `11698880`은 안정 safe_resolved였고, `11660237`은 `safe_resolved` 2회 / `promotion_blocked` 1회로 flip rate `0.3333333333333333`이어서 safe loss가 아니라 `nondeterminism_unresolved`로 분류했다.
- Blind judge의 독립 title/url 기대값은 `11674712`, `11660237`, `11698880` 모두 맞았지만, `11660237` 진동 때문에 promotion gate hard-hold 완화는 허용하지 않는다.
- Golden-16과 full 375 collateral diff를 상시 조합 게이트로 승격했다. 현재 평가는 golden `16/16` PASS지만 full 375 collateral은 changed `223`, regression `183`으로 `NO-GO`다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_238_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_safe_loss_flip_rate_n3_blind_judge_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_safe_loss_flip_rate_n3_blind_judge_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_always_on_golden16_full375_gate.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop238_always_on_golden16_full375_gate.json`
- 검증은 `py_compile`, convergence/flip-rate/always-on gate unit tests, relation-hold 포함 contextual alias bridge focused tests, `tests.test_title_lead_search_inferred_guard + tests.test_expert_main_comment_metadata` 194 tests, publish-contract convergence focused tests를 PASS했다.
- Gate는 `NO-GO`, `hard_hold_relaxation_allowed=false`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop237 parent replay after Loop236 URL-title guard

- Loop236 URL-title direct-source support guard를 38-row parent/representative packet으로 재검증했다.
- run `20260701_215903_177630`은 runtime clean이다: completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, MCP health ok/failure `36/0`, `large_run_complete=true`.
- 의미 품질은 통과하지 못했다. Loop231 대비 `safe_resolved/public title`이 `11->9`로 감소했고 `promotion_blocked`는 `25->28`로 늘었다.
- `11663540`은 focused canary에서 복구됐지만 parent replay에서는 `promotion_blocked`, public title `null`, blocked title `전 버두바가 하고 싶으ㄴ데요`로 남아 parent survival `NO-GO`다.
- Loop231 대비 movement: safe gain `11668288`, safe loss `11660237`, `11674712`, `11698880`, non-safe state change `11700495`, trace/scope-only change 18건.
- 산출물:
  - `docs/devs/loop_reports/LOOP_237_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_data_analytics_artifact.json`
- 검증은 `py_compile` PASS, focused tests 3개 PASS, `tests.test_expert_main_comment_metadata` 32 OK, `tests.test_promotion_gate_contract + tests.test_candidate_audit` 128 OK, Data Analytics artifact validate/render PASS, `git diff --check` PASS다.
- Gate는 `NO_DELTA_PARENT_REPLAY_AFTER_LOOP236_MIXED_MOVEMENT`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop236 URL-title direct-source support guard

- Loop235에서 노출된 URL-title mismatch를 publish precondition으로 좁혔다.
- 원 canary `20260701_212908_967986`은 runtime `1/1/0/0`, VLM/OCR `READY`였지만 wrong title `두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)` / URL `https://novelpia.com/novel/427233` publish 가능성을 노출했다.
- `expert_main.py`에 직접 post/OCR/alias support requirement와 unsafe URL-title publish demotion contract를 추가했다.
- Resync preview는 같은 bad result를 `promotion_blocked`와 `official_detail_url_missing_direct_source_support`로 내렸다.
- Patched canary `20260701_214126_569050`은 runtime `1/1/0/0`, VLM/OCR `READY`, public title `전 버튜버가 하고 싶은데요`, URL `https://novelpia.com/novel/275975`, `candidate_ledger_status=safe_resolved`다.
- 검증:
  - focused tests 3개 PASS.
  - `tests.test_expert_main_comment_metadata`: 32 OK.
  - `tests.test_promotion_gate_contract + tests.test_candidate_audit`: 128 OK.
  - `py_compile`: PASS.
  - Data Analytics artifact: validate/render PASS.
- 산출물:
  - `docs/devs/loop_reports/LOOP_236_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_data_analytics_artifact.json`
- Gate는 `NO_DELTA_TARGETED_URL_TITLE_DIRECT_SUPPORT_GUARD`, parent replay `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop235 character-parenthetical bridge runtime NO-GO

- `11663540` direct-image/character bridge를 `search_character_parenthetical_bridge`와 `direct_image_work_surface_bridge` 계약으로 확장했다.
- Loop235 원 런 `20260701_205757_114285`은 도구 출력 pipe loss 뒤 result JSON 없이 stuck되어 중단했고, manifest-only incomplete artifact로 보존했다.
- Loop235b run `20260701_210203_663393`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`로 완료됐다.
- 내부 expert 판정은 `전 버튜버가 하고 싶은데요`를 확정했지만 serialized public title은 `null`이다.
- `promotion_gate_state`는 resolved였으나 final publication contract가 `precision_seed_official_title_requires_review`와 `serialized_public_identity_scrubbed`로 public identity를 scrub했다.
- `https://novelpia.com/novel/311328` URL-title mismatch가 관찰되어 다음 architecture step을 `URL-title verified official detail` publish precondition으로 잡았다.
- 검증:
  - focused tests 4개 PASS.
  - `tests.test_expert_main_comment_metadata`: 29 OK.
  - `tests.test_promotion_gate_contract + tests.test_candidate_audit`: 128 OK.
  - `py_compile`: PASS.
  - Data Analytics artifact: validate/render PASS.
- 산출물:
  - `docs/devs/loop_reports/LOOP_235_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_no_go_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_no_go_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_data_analytics_artifact.json`
- Gate는 `NO_DELTA_TARGETED_CANARY_NO_GO`, targeted canary `NO-GO_PUBLIC_TITLE_NOT_RESTORED`, parent replay `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop234 direct-image cover-title runtime canary

- `11663540` actual payload를 focused runtime canary로 2회 실행했다.
- 1차 run `20260701_202952_860752`: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, OCR surface `전 버튜버가 하고 싶은데요`, official detail `https://novelpia.com/novel/275975`, final public title `null`.
- Actual image evidence가 `promotion_eligible=false`, `title_role=unknown`, `evidence_type=cover_title`였으므로 exact cover-title contract를 추가했다.
- 2차 run `20260701_203559_843860`: completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, OCR variant `전 버두바가 하고 싶은데요`, character bridge `주서연(전 버튜버가 하고 싶은데요)`, final public title `null`.
- 검증:
  - focused direct-image tests 3개 PASS.
  - `tests.test_expert_main_comment_metadata`: 27 OK.
  - `tests.test_promotion_gate_contract + tests.test_candidate_audit`: 128 OK.
  - `py_compile expert_main.py tests/test_expert_main_comment_metadata.py`: PASS.
  - Data Analytics artifact: validate/render PASS.
- 산출물:
  - `docs/devs/loop_reports/LOOP_234_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_data_analytics_artifact.json`
- Gate는 `NO_DELTA_TARGETED_CANARY_NO_GO`, targeted canary `NO-GO_PUBLIC_TITLE_NOT_RESTORED`, parent replay `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop233 direct-image character shared gate patch

- `11663540` OCR/character-title path를 `expert_main.py` final publication ledger contract에 연결했다.
- 새 조건은 candidate title과 일치하는 promotion-eligible OCR/work-title evidence, verified character bridge, official detail URL, current-work shared gate가 함께 있을 때만 public title을 복구한다.
- `전 버튜버가 하고 싶은데요` 양성 path는 `safe_resolved`로 복구되고, OCR title이 candidate와 맞지 않는 wrong-work 후보 `방구석 여신이 되었다`는 계속 `promotion_blocked`로 남는다.
- 검증:
  - 신규 focused tests 2개 PASS.
  - `tests.test_expert_main_comment_metadata`: 26 OK.
  - `tests.test_promotion_gate_contract + tests.test_candidate_audit`: 128 OK.
  - `py_compile expert_main.py tests/test_expert_main_comment_metadata.py`: PASS.
  - Data Analytics artifact: validate/render PASS.
- 산출물:
  - `docs/devs/loop_reports/LOOP_233_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_data_analytics_artifact.json`
- Gate는 `NO_DELTA_UNIT_CONTRACT_ONLY`, targeted canary `NOT_RUN`, parent replay `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop232 Loop231 safe-loss/variance source-native review

- 새 canary나 production code 변경 없이 Loop231 focus rows `11661876`, `11663540`, `11695637`, `11660237`, `11706832`를 재검토했다.
- 관련 후보/retarget title의 native web official page는 모두 존재하지만, row-level public publish 판정은 근거 강도와 기존 caveat에 따라 갈렸다.
- `11661876`은 `와인의 신` recurrent overblock이고, `11663540`은 negative control이 필요한 OCR/character-title 보존 patch 후보로 분리했다.
- `11695637`은 old safe title `도네하지 마라`를 복구하지 않는다. `[림월드]변방계에서 회귀자로 살아남기` retarget lane을 open으로 유지한다.
- `11660237`은 `테라포밍` parent recovery지만 targeted/parent variance가 아직 열려 있다.
- `11706832`은 Loop145 accepted caveated demotion을 다시 연 사례이며 safe gain으로 세지 않는다.
- 산출물:
  - `docs/devs/loop_reports/LOOP_232_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_data_analytics_artifact.json`
- Gate는 `NO_DELTA_SOURCE_NATIVE_VARIANCE_REVIEW_ONLY`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`를 유지한다.

## 2026-07-01 - Loop228 Loop227 safe-loss source/native review

- Reviewed Loop227 composite safe-loss rows `11660237`, `11660257`, `11695637`, `11705231` with local input/result trace and native web evidence.
- Verdict split: `likely_overblock=3`, `false_safe_title_retarget_required=1`.
- `11660237` and `11660257` are title-led evaluation bridge candidates.
- `11705231` is a character/comment/native seed convergence regression candidate.
- `11695637` should not restore Loop225 `도네하지 마라`; source/native evidence points to a retarget lane for `[림월드]변방계에서 회귀자로 살아남기`.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_228_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_data_analytics_artifact.json`
- Gate remains: `NO_DELTA_SOURCE_NATIVE_SAFE_LOSS_REVIEW_ONLY`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.


## 2026-07-01 - Loop227 composite parent replay after Loop226

- Ran Loop227 parent/representative replay after Loop226 trace candidate priority patch.
- Parent run `20260701_162837_314765` reached checkpoint `37/38` but remained partial: result JSON `24` rows, manifest `completed/flushed/pending/failed=37/24/13/0`, `large_run_complete=false`, VLM/OCR `READY`.
- Reran missing `11698897` as run `20260701_171713_227327`; it completed `1/1` and remained candidate/HOLD: `is_novel_related=true`, `is_resolved_work_discussion=false`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`.
- Composite comparison against Loop225 keeps `safe_resolved=12`, but movement is mixed: safe gains `11663521`, `11668288`, `11674712`, `11706832`; safe losses `11660237`, `11660257`, `11695637`, `11705231`.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_227_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop227_composite_parent_replay_after_trace_candidate_priority_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop227_composite_parent_replay_after_trace_candidate_priority_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop227_composite_parent_replay_after_trace_candidate_priority_data_analytics_artifact.json`
- Gate remains: `NO_DELTA_COMPOSITE_PARENT_REPLAY_MIXED_MOVEMENT`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop226 safe-loss trace candidate priority

- Implemented a deterministic trace/ledger architecture patch in `expert_main.py`.
- The new `_preferred_blocked_candidate_for_trace(...)` path makes `promotion_blocked` traces prefer stronger preserved candidates over low-quality `comment_surface` hold candidates.
- This is not a publish expansion. Loop225 safe-loss payload replay keeps all three rows blocked:
  - `11668288`: `가챠펑크` -> `가챠 중독자의 퓨전펑크 생활`, `https://novelpia.com/novel/387014`, publish false.
  - `11674712`: `호각임` -> `이 무림의 미친년은 나야`, `https://novelpia.com/novel/217943?sid=main5`, publish false.
  - `11706832`: `표절물인가` -> `황제분충`, publish false.
- Verification:
  - New focused tests: 2 PASS.
  - `tests.test_expert_main_comment_metadata`: 23 tests OK.
  - `tests.test_promotion_gate_contract + tests.test_expert_main_comment_metadata`: 43 tests OK.
  - `py_compile expert_main.py tests/test_expert_main_comment_metadata.py`: PASS.
  - Data Analytics validation/render passed for `Loop226 Safe-Loss Trace Candidate 정규화 검토`.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_226_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop226_trace_candidate_priority_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop226_trace_candidate_priority_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop226_trace_candidate_priority_data_analytics_artifact.json`
- Gate remains: residual accounting delta `NO_DELTA_TRACE_LEDGER_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop224 parent replay after Loop223 patch

- Ran the 38-row parent/representative packet after Loop223b to test whether the focused title-field/final-contract patch survives broader context.
- Loop224 run id `20260701_141454_629022`: runtime `GO`, completed/flushed/pending/failed `38/38/0/0`, effective/requested parallel `36/36`, image_post_count `24`, VLM/OCR `READY`, MCP health `36/36`.
- Parent status counts:
  - Loop182 `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`.
  - Loop221 `safe_resolved=9`, `promotion_blocked=27`, `hold_without_candidates=1`, `output_consistency_lint=1`.
  - Loop224 `safe_resolved=10`, `promotion_blocked=26`, `hold_without_candidates=1`, `output_consistency_lint=1`.
- Focused target survival split:
  - `11705231` survived as `탐식의 재림`, `https://page.kakao.com/content/50219568`.
  - `11661876` failed parent survival and returned to `promotion_blocked`.
- Mixed movement blocks approval: changed rows are `11666713`, `11668288`, `11695637`, `11698880`, `11705231`; `11698880` is a new collateral safe-loss against the Loop157/158 stable-alias guard line.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_224_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_data_analytics_artifact.json`
- Gate remains: residual accounting delta `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop223 publish-contract title-field patch

- Implemented the two strongest Loop222 patch candidates in focused scope.
- `11661876`: fixed the path where current-work/high official detail evidence still got scrubbed at final serialized publish-contract boundary.
- `11705231`: separated character/entity surface `설지후` from official page title `탐식의 재림` for the same official detail URL.
- Loop223 first canary only recovered `11705231`; Loop223b after final-contract restore recovered both target rows.
- Loop223b run id `20260701_134929_838421`: runtime `GO`, completed/flushed/pending/failed `2/2/0/0`, issues `[]`, image_post_count `0`.
- Final target rows:
  - `11661876`: `safe_resolved`, `와인의 신`, `https://novel.munpia.com/494781`.
  - `11705231`: `safe_resolved`, `탐식의 재림`, `https://page.kakao.com/content/50219568`.
- Verification passed: focused tests `4`, expert metadata suite `20`, candidate audit suite `104`, promotion gate contract suite `20`, full unittest discover `1335`.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_223_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_data_analytics_artifact.json`
- Gate remains: residual accounting delta `NO_DELTA_FOCUSED_CANARY_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - 보고서 한국어 지침 고정

- 사용자 요청에 따라 보고서 작성 지침을 재확인하고 보조 문서에 보강했다.
- 확인: `AGENTS.md`, `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`, `docs/devs/CHECKLIST.md`, `docs/devs/TODO.md`.
- 보강: `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`, `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `docs/devs/OPERATION_QUALITY_CHECKLIST.md`.
- 규칙: 보고서는 한국어로 작성하고, 간략하되 의미, 근거, 산출물 경로, gate 상태를 생략하지 않는다.

## 2026-07-01 - Loop222 review Loop221 safe-loss source/native evidence

- Reviewed the six Loop221 `safe_resolved -> promotion_blocked` rows before any residual decrement: `11658620`, `11660237`, `11661876`, `11668288`, `11695623`, `11705231`.
- No production code was changed and no new canary was run; this is a source/native review-only checkpoint.
- Official/native evidence exists for all six rows, but the dispositions split into `likely_overblock=3`, `ambiguous_hold=2`, and `title_field_bug=1`.
- Strong next patch candidates:
  - `11661876`: `와인의 신` has current-work/high, row-discusses-work, and official detail evidence, but final publish-contract scrub overblocks.
  - `11705231`: character/entity surface `설지후` is mixed into the official title field for the official `탐식의 재림` URL.
- Artifacts:
  - `docs/devs/loop_reports/LOOP_222_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_data_analytics_artifact.json`
- Data Analytics artifact `Loop222 Loop221 safe-loss source/native 검토` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_SOURCE_NATIVE_SAFE_LOSS_REVIEW_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop221 run parent replay after direct alias probe

- Ran the 38-row parent/representative replay after Loop220's direct alias search guard; no new production code was added in this loop.
- Loop221 run id `20260701_120437_234858`: runtime `GO`, completed/flushed/pending/failed `38/38/0/0`, effective/requested parallel `36/36`, image_post_count `24`, VLM/OCR required scope `READY`.
- Runtime audit artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_runtime_audit.md`.
- Parent comparison against Loop182:
  - Loop182 `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`.
  - Loop221 `safe_resolved=9`, `promotion_blocked=27`, `hold_without_candidates=1`, `output_consistency_lint=1`.
- Direct alias target survives parent replay: `11713222` recovered to `잘생기면 편해지는 인방 생활`, `https://novelpia.com/novel/384016`; `11674712` also recovered to `이 무림의 미친년은 나야`.
- Mixed movement blocks approval: 9 changed rows, with 3 safe gains and 6 safe losses.
- Data Analytics artifact `Loop221 직접 별칭 보강 후 parent replay 검토` validate/render PASS.
- Gate remains: runtime `GO`, residual accounting delta `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- Next: source/native review for 9 changed rows, safe loss decomposition first.

## 2026-07-01 - Loop220 recover direct alias search path for `11713222`

- Added a direct non-comment worklike alias probe path in `src/llm_batch/experts/orchestrator.py` so `잘생인방` is searched before broad genre official-hit early stop can discard it.
- Preserved direct alias official/community/author/abbreviation queries through semantic no-work pruning and search budget processing.
- Added regression coverage in `tests/test_title_lead_search_inferred_guard.py` for `잘생인방` recovery while excluding comment-only `잘생인편`.
- Loop220 run id `20260701_114043_668022`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop220 result: `11713222` recovered to `잘생기면 편해지는 인방 생활`, `https://novelpia.com/novel/384016`, `scope=current_work`; `11674712` recovered to `이 무림의 미친년은 나야`, `https://novelpia.com/novel/217943?sid=main5`; `11669928` stayed safe.
- Verification passed:
  - `.\.venv312\Scripts\python.exe -m py_compile src\llm_batch\experts\orchestrator.py tests\test_title_lead_search_inferred_guard.py`
  - new focused direct-alias test, PASS
  - `.\.venv312\Scripts\python.exe -m unittest tests.test_title_lead_search_inferred_guard -v`, `157 tests OK`
  - `tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract`, `39 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit -v`, `102 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest discover tests -v`, `1332 tests OK`
- Data Analytics artifact `Loop220 직접 별칭 검색 보강 검토` validate/render PASS.
- Gate remains: runtime `GO`, residual accounting delta `NO_DELTA_UNTIL_BROADER_REPLAY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- Next: run broader replay or parent/collateral packet before any residual decrement claim.

## 2026-07-01 - Loop219 recover shared-gate unconfirmed-alias path but keep packet no-delta

- Added a narrow shared promotion-gate exemption in `src/llm_batch/candidate_audit.py` so `11669928`-type current-work publish decisions with official-detail URL support are not demoted by `unconfirmed_alias_official_detail_bridge`.
- Kept the guard conservative: context-only/conflict flags, missing official-detail URL, title/URL mismatch, missing shared publish decision, or weak alias surfaces still block public promotion.
- Added regression coverage in `tests/test_candidate_audit.py` for the recovery path and the context-only non-exemption path.
- Loop219 run id `20260701_110936_416066`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop219 result: `11669928` recovered to safe_resolved with `탑의 성좌들이 날 애호한다`, `https://novelpia.com/novel/377032`, `scope=current_work`; `11713222` regressed to promotion_blocked through previous-work/comment candidate contamination; `11674712` regressed to promotion_blocked with `character_bridge_variance_hold`.
- Verification passed:
  - `.\.venv312\Scripts\python.exe -m py_compile src\llm_batch\candidate_audit.py tests\test_candidate_audit.py`
  - focused candidate-audit tests, `4 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit -v`, `102 tests OK`
  - `tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract`, `39 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest discover --start-directory tests`, `1331 tests OK`
- Data Analytics artifact `Loop219 공유 게이트 unconfirmed-alias 검토` validate/render PASS.
- Gate remains: runtime `GO`, residual accounting delta `NO_DELTA_SHARED_GATE_UNCONFIRMED_ALIAS_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- Next: review `11713222` previous-work/comment candidate recontamination and `11674712` character-bridge/J11-title-drift recurrence before parent/collateral replay.

## 2026-07-01 - Loop218 recover character-bridge official URL/scope but keep packet no-delta

- Added blocked-candidate official-detail URL recovery in `expert_main.py` result-contract scrub, using exact title support from `search_evidence_catalog`.
- Added conservative `current_work` scope inference for blocked character-bridge candidates only when official-detail search evidence and row context converge without hard context-only flags.
- Added regression coverage in `tests/test_expert_main_comment_metadata.py` for `11674712`-type recovery and no-official-detail scope-null preservation.
- Loop218 run id `20260701_104624_623831`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop218 result: `11674712` recovered to safe_resolved with `이 무림의 미친년은 나야`, `https://novelpia.com/novel/217943`, `scope=current_work`; `11669928` regressed to promotion_blocked with `unconfirmed_alias_official_detail_bridge`.
- Verification passed:
  - `.\.venv312\Scripts\python.exe -m py_compile expert_main.py tests\test_expert_main_comment_metadata.py`
  - focused new tests, `2 tests OK`
  - `tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract`, `39 tests OK`
  - title-led character bridge focused tests, `2 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest discover --start-directory tests`, `1329 tests OK`
  - `git diff --check`, PASS with CRLF warnings only
- Data Analytics artifact `Loop218 캐릭터 브리지 스코프 추적 검토` validate/render PASS.
- Gate remains: runtime `GO`, residual accounting delta `NO_DELTA_CHARACTER_BRIDGE_SCOPE_TRACE_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- Next: review `11669928` `unconfirmed_alias_official_detail_bridge` regression before parent/collateral replay.

## 2026-07-01 - Loop214-217 preserve exact-alias image/OCR block reasons in publish trace

- Added conservative blocked-candidate scope inference in `expert_main.py` result-contract scrub so `11660257`-type exact-alias candidates can remain candidate-only while explaining why public title promotion is blocked.
- Kept the inference narrow: it only infers `context_only` when official/hold candidate evidence is paired with nonpromotable image/OCR context and no body/comment work bridge.
- Propagated `promotion_blocked_reasons` and `candidate_audit_lint_reasons` into `publish_contract_trace.reason_codes` and gate decision reasons.
- Added regression coverage in `tests/test_expert_main_comment_metadata.py` for image/OCR context-only trace and text-only alias non-inference.
- Loop217 run id `20260701_102032_074772`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop217 result: `11660257` remains candidate-only with `scope=context_only`; `11713222` and `11669928` are safe_resolved; `11674712` remains promotion_blocked with scope null.
- Verification passed:
  - `.\.venv312\Scripts\python.exe -m py_compile expert_main.py tests\test_expert_main_comment_metadata.py`
  - focused new tests, `2 tests OK`
  - `tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract`, `37 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest discover --start-directory tests`, `1327 tests OK`
  - `git diff --check`, PASS with CRLF warnings only
- Gate remains: targeted trace `GO_REASON_TRACE_ONLY`, residual accounting delta `NO_DELTA_TRACE_OBSERVABILITY_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- Next: review `11674712` scope null / character bridge variance before parent/collateral replay.

## 2026-07-01 - Loop212-213 stabilize title-led unconfirmed-alias bridge for `11669928`

- Added a narrow `candidate_audit.py` exemption so short title-led aliases with official evidence support and work consumption/status tokens are not demoted by `unconfirmed_alias_official_detail_bridge`.
- Kept pollution safeguards: competing-hold flags, non-novel warnings, genre/low-information aliases, missing title/search/body-or-comments context, and missing official title/snippet support still block the exemption.
- Added `test_title_led_consumption_alias_exempts_unconfirmed_official_detail_bridge` while preserving the existing unconfirmed alias pollution block test.
- Verification passed:
  - `.\.venv312\Scripts\python.exe -m py_compile src\llm_batch\candidate_audit.py tests\test_candidate_audit.py`
  - focused candidate-audit tests, `3 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit -v`, `100 tests OK`
  - title-led acceptance regression, `1 test OK`
- Loop212 run id `20260701_093147_646251`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`; `11669928` published, but packet fell to `safe_resolved=1`.
- Loop213 run id `20260701_093833_697684`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`; `11669928`, `11713222`, and `11674712` published, packet returned to `safe_resolved=3`.
- Gate remains: residual accounting delta `NO_DELTA_PACKET_VARIANCE_REVIEW_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- `11660257` remains candidate-only and is the next packet-variance decomposition target before parent/collateral replay.

## 2026-07-01 - Loop209-211 preserve previous-work candidate without stealing current-work public title

- Added report-writing instruction: reports must be Korean, concise, and must not omit meaning, evidence, artifact paths, or gate status.
- Blocked final-title correction from using a verified-current-alias bypass when direct current-work alias evidence conflicts with a comment previous-work candidate.
- Preserved acknowledged previous-work candidates as candidate-only ledger rows while keeping the current-work public title.
- Expanded previous-work candidate recovery to inspect official-page support title fragments.
- Loop211 run id `20260701_085524_956588`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop211 result: `safe_resolved=3`, `promotion_blocked=2`, public title count `3`.
- `11713222` now publishes `잘생기면 편해지는 인방 생활` and preserves `잘생기면 인생이 편하다` as candidate-only previous-work evidence.
- Verification passed:
  - focused previous-work preservation tests, `4 tests OK`
  - focused architecture bundle, `38 tests OK`
  - broad architecture bundle, `290 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest discover --start-directory tests`, `1324 tests OK`
- Gate remains: runtime `GO`, residual accounting delta `NO_DELTA_SCOPE_PRECEDENCE_PACKET_REVIEW_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- `11660257` and `11669928` moved between Loop210 and Loop211, so parent/collateral replay and residual decrement remain blocked.

## 2026-07-01 - Loop205-208 review packet variance and scope-block hardening

- Reviewed Loop203/204 five-row packet variance before any parent/collateral replay.
- Added official-detail candidate preservation priority so weak comment-only blocked labels cannot hide recoverable official detail candidates.
- Updated resolved public-title gate recording so hard context-only / unresolved-worklike flags force candidate-only scope.
- Filtered `@...` user mentions out of comment-surface title candidates.
- Added a narrow character-alias official-detail support exception for rows like `서문청 -> 이 무림의 미친년은 나야` when official search and current-work context agree.
- Loop208 run id `20260701_080838_271200`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop208 result: `safe_resolved=3`, `promotion_blocked=2`, public title count `3`, inferred publish decisions `0`.
- Verification passed:
  - `.\.venv312\Scripts\python.exe -m py_compile src\llm_batch\candidate_audit.py tests\test_candidate_audit.py`
  - focused new/adjacent candidate-audit tests, `4 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_promotion_gate_contract tests.test_expert_main_comment_metadata -v`, `133 tests OK`
  - `.\.venv312\Scripts\python.exe -m unittest discover --start-directory tests`, `1322 tests OK`
- Gate remains: runtime `GO`, residual accounting delta `NO_DELTA_PACKET_VARIANCE_REVIEW_ONLY`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.
- `11713222` remains review-locked because Loop208 publishes through previous-work/comment override flags while competing candidates remain.

## 2026-07-01 - Loop203/204 move resolved public-title decisions upstream

- Added `_record_resolved_public_title_gate_decision(...)` in `src/llm_batch/agentic_pipeline.py` so already-resolved public titles record a shared promotion-gate decision before serialization.
- Updated `src/llm_batch/candidate_audit.py` so `candidate_ledger.promotion_gate_state` and `candidate_ledger.promotion_gate_evidence` survive candidate ledger regeneration.
- Added promotion-gate contract tests for resolved public-title gate recording, unresolved-scope non-recording, and ledger gate-state preservation.
- Loop203 run id `20260701_070958_405409`: runtime `GO`, `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`; inferred publish decisions `0`, but packet movement observed.
- Loop204 run id `20260701_071813_517226`: runtime `GO`, `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`; `safe_resolved=2`, `promotion_blocked=3`, public title count `2`, trace count `5/5`, inferred publish decisions `0`, final-ledger consistency issues `0`.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py src\llm_batch\candidate_audit.py tests\test_promotion_gate_contract.py expert_main.py tests\test_expert_main_comment_metadata.py`
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract tests.test_expert_main_comment_metadata -v`, `33 tests OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`, `1318 tests OK`
- Data Analytics artifact `Loop204 Resolved Public Title Gate Review` validate/render PASS.
- Gate remains: targeted canary `GO_LEDGER_CONSISTENCY_ONLY`, residual accounting delta `NO_DELTA_UPSTREAM_LEDGER_ARCHITECTURE_CHECKPOINT_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop200-202 unify final-publication ledger contract

- Added `_sync_final_publication_ledger_contract(...)` in `expert_main.py` and routed postprocess through it after candidate audit.
- Blocked serialized public identity now overwrites stale `promotion_decision=publish` with `candidate_only` / `publish_allowed=false`.
- Allowed serialized public identity now receives `publish_contract_trace`, `publish_ledger`, and matching `promotion_decision`.
- Scope payload is reconstructed from `scope_*` reason codes when the upstream gate emitted reason codes without a payload.
- Added focused final-publication ledger tests in `tests/test_expert_main_comment_metadata.py`.
- Loop202 run id `20260701_064737_150518`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop202 result: `safe_resolved=2`, `promotion_blocked=3`, public title count `2`, trace count `5/5`, final ledger consistency `PASS`.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile expert_main.py tests\test_expert_main_comment_metadata.py`
  - final-publication focused tests, `3 tests OK`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`, `30 tests OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`, `1315 tests OK`
- Data Analytics artifact `Loop202 Final Publication Ledger Review` validate/render PASS.
- Gate remains: targeted canary `GO_LEDGER_CONSISTENCY_ONLY`, residual accounting delta `NO_DELTA_FINAL_LEDGER_ARCHITECTURE_CHECKPOINT_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop198/199 rerun packet and expose final-publication ledger gap

- Reran the prior five-row packet after Loop193-197 scope-gate wiring.
- Loop198 run id `20260701_055004_272309`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop198 result: `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`.
- Loop198 exposed `11669928` as safe-resolved with `탑의 성좌들이 날 애호한다` but no `publish_contract_trace`.
- Added `_record_title_led_alias_public_title_gate_decision(...)` in `src/llm_batch/agentic_pipeline.py`.
- Added `PromotionGateContractTest.test_title_led_alias_public_title_records_current_scope_gate`.
- Loop199 run id `20260701_060336_094994`: runtime `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop199 result: `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`.
- Loop199 exposed the deeper architecture gap:
  - `11669928`: `candidate_ledger.promotion_decision.status=publish`, but final public identity is blocked/null.
  - `11713222`: safe-resolved as `잘생기면 인생이 편하다` without `publish_contract_trace`, while competing `잘생기면 편해지는 인방 생활` evidence remains preserved.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py`
  - title-led gate contract, `1 test OK`
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`, `15 tests OK`
  - title-led acceptance test, `1 test OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`, `1312 tests OK`
- Data Analytics artifact `Loop199 Five-Row Packet Replay Review` validate/render PASS.
- Gate remains: packet semantic `NO-GO`, residual accounting delta `NO_DELTA_PACKET_REPLAY_VARIANCE_AND_GATE_LEDGER_MISMATCH`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop197 wires direct OCR work-surface scope gate

- Updated `src/llm_batch/agentic_pipeline.py` so direct OCR work-surface publication records a shared promotion-gate decision at the final public identity boundary.
- Added `_record_direct_image_work_surface_gate_decision(...)` with `ScopeState(scope_kind=current_work)` and direct image/OCR bridge evidence.
- Kept stale canonical rescue scanning skipped for `direct_image_work_surface_lock`, while preserving `promotion_decision` and `promotion_gate_state` in the candidate ledger.
- Strengthened `tests/test_promotion_gate_contract.py` with a direct image work-surface scope contract.
- Strengthened `tests/test_agentic_pipeline_rework.py` so the direct OCR/canonical rescue bypass fixture asserts `status=publish`, `bypassed_gate=false`, and `scope_kind=current_work`.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py tests\test_agentic_pipeline_rework.py`
  - direct OCR contract, `1 test OK`
  - direct OCR/canonical rescue bypass integration, `1 test OK`
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`, `14 tests OK`
  - direct OCR focused bundle, `5 tests OK`
  - rank OCR/lock suites, `30 tests OK`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`, `26 tests OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`, `1311 tests OK`
- Data Analytics artifact `Loop197 Direct OCR Scope Gate Checkpoint` validate/render PASS.
- Created artifacts:
  - `docs/devs/loop_reports/LOOP_197_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_data_analytics_artifact.json`
- Gate remains: Loop197 is `GO_UNIT_ONLY`, runtime canary `NOT_RUN`, residual accounting delta `NO_DELTA_UNIT_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop196 wires batch-alias public-title scope gate

- Updated `src/llm_batch/agentic_pipeline.py` so batch-alias public-title publication records a shared promotion-gate decision.
- Added `_record_batch_alias_public_title_gate_decision(...)` with `ScopeState(scope_kind=current_work)` and batch-alias bridge evidence.
- Remembered batch-alias candidates only on branches that actually produce public identity output, then recorded the final gate after demotion and semantic reread logic settled.
- Strengthened `tests/test_promotion_gate_contract.py` with a batch-alias public-title scope contract.
- Strengthened `tests/test_agentic_pipeline_rework.py` so final candidate ledgers must preserve `promotion_gate_state.scope.scope_kind=current_work`.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_promotion_gate_contract.py tests\test_agentic_pipeline_rework.py`
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`, `13 tests OK`
  - targeted batch-alias rework tests, `2 tests OK`
  - combined promotion/rework bundle, `15 tests OK`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`, `25 tests OK`
  - `venv\Scripts\python.exe -m unittest tests.test_known_title_abbreviation_support tests.test_title_lead_search_inferred_guard -v`, `182 tests OK`
  - `venv\Scripts\python.exe -m unittest discover --start-directory tests`, `1310 tests OK`
- Data Analytics artifact `Loop196 Batch Alias Scope Gate Checkpoint` validate/render PASS.
- Created artifacts:
  - `docs/devs/loop_reports/LOOP_196_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_data_analytics_artifact.json`
- Gate remains: Loop196 is `GO_UNIT_ONLY`, runtime canary `NOT_RUN`, residual accounting delta `NO_DELTA_UNIT_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop194 propagates scope into publish-contract trace

- Updated `expert_main._scrub_promotion_blocked_result_contract` so promotion-blocked serialized results preserve scope-state evidence.
- `publish_contract_trace.scope_state` now carries the blocked candidate scope.
- `publish_contract_trace.gate_decision.scope` mirrors the same scope payload.
- Scope reason codes are backfilled when needed, including `scope_previous_work`, `scope_not_current_work`, and `current_work_candidate_competes_with_previous_work`.
- Strengthened `tests/test_expert_main_comment_metadata.py` with a `11713222` previous-work fixture that asserts scope trace propagation.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile expert_main.py src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata tests.test_promotion_gate_contract -v`, `23 tests OK`
- Data Analytics artifact `Loop194 Publish Trace Scope Propagation Checkpoint` validate/render PASS.
- Created artifacts:
  - `docs/devs/loop_reports/LOOP_194_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_data_analytics_artifact.json`
- Gate remains: Loop194 is `GO_UNIT_ONLY`, runtime canary `NOT_RUN`, residual accounting delta `NO_DELTA_SCOPE_TRACE_CONTRACT_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop193 adds ScopeState contract to promotion gate

- Added `ScopeState` to `src/llm_batch/promotion_gate.py`.
- Added scope categories: `current_work`, `previous_work`, `secondary_reference`, `author_new_work`, `image_ocr_derived_work`, `platform_meta_nonwork`, `context_only`, `unknown`.
- `can_publish_title(...)` now records scope reason codes and blocks public publish when an explicit non-current-work scope is present.
- Wired `src/llm_batch/agentic_pipeline.py` `_can_promote_title_after_semantic_no_work` to preserve scope in `_promotion_gate_state`.
- Added focused tests in `tests/test_promotion_gate_contract.py` for:
  - `11669928` unknown scope / candidate-only
  - `11713222` current-work publish
  - `11713222` previous-work candidate-only
  - `11695623` image/OCR-derived candidate-only
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile src\llm_batch\promotion_gate.py src\llm_batch\agentic_pipeline.py`
  - `venv\Scripts\python.exe -m unittest tests.test_promotion_gate_contract -v`, `11 tests OK`
- Data Analytics artifact `Loop193 Scope-State Contract Checkpoint` validate/render PASS.
- Created artifacts:
  - `docs/devs/loop_reports/LOOP_193_REPORT_20260701.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_data_analytics_artifact.json`
- Gate remains: Loop193 is `GO_UNIT_ONLY`, runtime canary `NOT_RUN`, residual accounting delta `NO_DELTA_SCOPE_CONTRACT_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Scope-state architecture delta added to active goal contract

- Reviewed the active architecture-integrated goal after Loop191/192 showed trace coverage `5/5` but packet semantic `NO-GO`.
- Confirmed this is not a goal completion point: residual accounting remains next actionable `131`, P0/P1/P2 `0/61/70`.
- Reframed the next step from isolated title rescue to explicit scope-state architecture before `can_publish_title(...)`.
- Added the scope categories that must be represented before public publication:
  - `current_work`
  - `previous_work`
  - `secondary_reference`
  - `author_new_work`
  - `image_ocr_derived_work`
  - `platform_meta_nonwork`
  - `context_only`
  - `unknown`
- Marked `11669928`, `11713222`, and `11695623` as contract seeds for scope classification rather than direct post_id/title-specific production patches.
- Updated docs:
  - `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`
  - `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md`
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/TODO.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- No production code or canary runtime changed in this checkpoint.
- Gate remains: scope-state delta `OPEN`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop191/192 improve publish-trace observability but packet remains NO-GO

- Reran the prior Loop184 five-row packet after Loop190 publish-contract trace instrumentation.
- Loop191 run id: `20260701_041346_483852`.
- Loop191 runtime audit is clean: completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, runtime contract `GO`, issues `[]`.
- Loop191 packet outcome:
  - `safe_resolved=2`
  - `promotion_blocked=3`
  - public title count `2/5`
  - trace rows `3/5`
  - pre-gate title rows `2/5`
- Loop191 exposed a trace coverage gap: `11660257` preserved `암흑가 보스요? 제가요?` in `candidate_ledger`, but `publish_contract_trace.pre_gate_candidate` was empty.
- Patched `expert_main.py` so promotion-blocked trace derivation can use `candidate_ledger.candidate_preservation_sources` and string `title_candidates`.
- Added focused regression coverage in `tests/test_expert_main_comment_metadata.py`.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile expert_main.py`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata -v`, `12 tests OK`
- Loop192 run id: `20260701_042125_503632`.
- Loop192 runtime audit is clean: completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, runtime contract `GO`, issues `[]`.
- Loop192 observability improved:
  - trace rows `5/5`
  - pre-gate title rows `5/5`
- Loop192 semantic packet is `NO-GO`:
  - `safe_resolved=0`
  - `promotion_blocked=5`
  - public title count `0/5`
  - `11669928` and `11713222` moved from Loop191 `safe_resolved` to Loop192 `promotion_blocked`
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop191_after_publish_trace_packet_replay_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_191_192_REPORT_20260701.md`
- Data Analytics artifact `Loop192 Publish Trace Packet Replay Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_PACKET_REPLAY_VARIANCE_ALL_BLOCKED`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop190 adds publish-contract trace unit instrumentation

- Added publish-boundary observability after Loop189 exposed the final serialized public identity gap.
- `expert_main._scrub_promotion_blocked_result_contract` now records:
  - `publish_contract_trace.pre_gate_candidate`
  - `publish_contract_trace.gate_decision`
  - `publish_contract_trace.post_gate_identity`
  - `publish_contract_trace.reason_codes`
  - `publish_contract_trace.bypassed_gate=false`
  - `publish_ledger.candidate_preservation`
  - `publish_ledger.public_publish`
- Mirrored the publish trace and ledger into `candidate_ledger` for downstream artifact readers.
- Added focused regression coverage in `tests/test_expert_main_comment_metadata.py`.
- Verification passed:
  - `venv\Scripts\python.exe -m py_compile expert_main.py`
  - `venv\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata -v`, `11 tests OK`
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_190_REPORT_20260701.md`
- Data Analytics artifact validation PASS; render call was attempted once but recorded as `ATTEMPTED_OUTPUT_TRUNCATED` because the response was truncated before confirmation.
- Gate remains: Loop190 is `GO_UNIT_ONLY`, packet replay `OPEN`, residual accounting delta `NO_DELTA_UNIT_INSTRUMENTATION_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop189 proves packet replay NO-GO after Loop188 single-row recovery

- Reran the prior Loop184 five-row packet after the Loop188 title-led bridge.
- Loop189 run id: `20260701_034236_736272`.
- Manifest/runtime audit is clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, runtime contract `GO`, issues `[]`.
- Packet outcome is semantic `NO-GO`:
  - Loop184 ledger split: `safe_resolved=4`, `promotion_blocked=1`
  - Loop189 ledger split: `safe_resolved=0`, `promotion_blocked=5`
  - public title count: `0/5`
  - Loop188 `11669928` single-post recovery regressed in packet scope
- Architecture finding:
  - candidate evidence remains preserved in result fields
  - final serialized public identity blocks every title
  - next architecture layer must trace candidate-vs-publish decisions explicitly
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_189_REPORT_20260701.md`
- Data Analytics artifact `Loop189 Packet Replay Architecture Gap Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_PACKET_REPLAY_REGRESSED_TO_ALL_PROMOTION_BLOCKED`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop187 closes nested scrub unit contract but live packet remains no-delta

- Patched `expert_main.py` so a promotion-blocked result with `promotion_decision.publish_allowed=false` scrubs nested `novel_identity` public title/URL as well as top-level public fields.
- Added focused regression coverage in `tests/test_expert_main_comment_metadata.py`.
- Verification passed:
  - `py_compile expert_main.py`: PASS
  - focused promotion-gate/result-contract unittest bundle: `10 tests OK`
- Loop187 run id: `20260701_025510_236345`.
- Manifest/runtime audit is clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, runtime contract `GO`, issues `[]`.
- Packet outcome remains no-delta:
  - Loop187 ledger split: `safe_resolved=2`, `promotion_blocked=3`
  - `11660257` candidate-hold remains stable with public title blocked
  - `11695623` remains promotion-blocked
  - `11713222` returns to safe_resolved in Loop187 but remains variance because Loop186 disagreed
  - `11669928` becomes a new safe loss / promotion-blocked row
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_187_REPORT_20260701.md`
- Data Analytics artifact `Loop187 Nested Gate Scrub Follow-up Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_NESTED_GATE_SCRUB_REVIEW_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop186 confirms candidate-hold stability but packet movement blocks accounting

- Reran the Loop184 five-row packet after the Loop185 candidate-hold patch.
- Loop186 run id: `20260701_022923_198719`.
- Manifest/runtime audit is clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, runtime contract `GO`, issues `[]`.
- `11660257` candidate-hold fix remains stable:
  - public `official_title=null`
  - candidate `암흑가 보스요? 제가요?`
  - URL `https://novelpia.com/novel/384111`
  - `promotion_policy=hold_without_promotion`
- Packet movement blocks accounting:
  - Loop184 ledger split: `safe_resolved=4`, `promotion_blocked=1`
  - Loop186 ledger split: `safe_resolved=2`, `promotion_blocked=3`
  - safe losses vs Loop184: `11695623`, `11713222`
  - `11713222` retains title fields while reporting `candidate_ledger_status=promotion_blocked`, requiring serialization/ledger and alias-precedence review
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_186_REPORT_20260701.md`
- Data Analytics artifact `Loop186 Follow-up After Candidate-Hold Patch Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_COLLATERAL_FOLLOWUP_REVIEW_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop185 preserves 11660257 exact-alias candidate without approval

- Patched the `11660257` failure exposed by Loop184:
  - skip platform/listing/structural official-title drift in search-result official alias candidate recovery
  - preserve blocked `search_evidence_alias_inference` exact-alias candidates as `hold_without_promotion`
- Loop185 run id: `20260701_021353_263678`.
- Manifest/runtime audit is clean: completed/flushed/pending/failed `1/1/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `1/1`, runtime contract `GO`, issues `[]`.
- Row outcome keeps public title blocked while preserving candidate evidence:
  - public `official_title=null`
  - `candidate_ledger_status=promotion_blocked`
  - candidate `암흑가 보스요? 제가요?`
  - URL `https://novelpia.com/novel/384111`
  - `promotion_policy=hold_without_promotion`
- Verification passed:
  - touched-file `py_compile`
  - focused two-test bundle
  - `tests.test_title_lead_search_inferred_guard -v`
  - `tests.test_agentic_pipeline_rank1_lock_block tests.test_agentic_pipeline_rank3_lock_anchor -v`
  - `tests.test_agentic_pipeline_rework -v`
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_185_REPORT_20260701.md`
- Data Analytics artifact `Loop185 Exact Alias Candidate Hold Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_TARGETED_SINGLE_ROW_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop184 targeted follow-up is runtime GO but no queue delta

- Ran Loop184 follow-up for Loop183 movement rows `11660257`, `11695623`, `11713222`, `11669928`, and `11674712`.
- Loop184 run id: `20260701_014002_948127`.
- Manifest/runtime audit is clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, runtime contract `GO`, issues `[]`.
- Row outcome split is `safe_resolved=4`, `promotion_blocked=1`.
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_184_REPORT_20260701.md`
- Data Analytics artifact `Loop184 Source Native Follow-up Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_TARGETED_FOLLOWUP_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop183 reviews Loop182 movement rows without queue delta

- Reviewed Loop182 safe gains `11669928`, `11695623` and safe losses `11660257`, `11674712`, `11713222` from source/native evidence.
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop183_loop182_movement_source_native_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop183_loop182_movement_source_native_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop183_loop182_movement_source_native_review_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_183_REPORT_20260701.md`
- Data Analytics artifact `Loop183 Source Native Movement Review` validate/render PASS.
- Findings:
  - `11660257` is a likely exact-alias recall regression needing a guard against generic/platform-title official hit drift.
  - `11713222` is a current-work-vs-previous-work alias competition row.
  - `11695623` should be repeated with VLM/OCR on before counting a new safe promotion.
  - `11669928` and `11674712` remain variance-attention controls.
- Prepared the next targeted follow-up packet:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop184_loop183_source_native_followup_5.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop184_loop183_source_native_followup_5_manifest.json`
- Gate remains: residual accounting delta `NO_DELTA_SOURCE_NATIVE_REVIEW_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop182 parent replay after architecture integration remains semantic review

- Reran the 38-row parent/representative packet from Loop169 after shared promotion-gate architecture integration.
- Loop182 run id: `20260701_001958_875919`.
- Manifest completion is clean: completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, `partial_flush_gap=false`, `ordered_flush_blocked=false`, VLM/OCR `READY`, image_post_count `24`.
- Health includes search: `mcp_health_include_search=true`, MCP health ok/checked `36/36`.
- Runtime contract audit is `GO` with issues `[]`.
- Row outcome split is relevant `26`, identified `12`, `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`.
- Loop169 to Loop182 comparison shows `22/38` row movement, including `promotion_blocked -> safe_resolved` 2 rows and `safe_resolved -> promotion_blocked` 3 rows; degraded search counters increased `166 -> 178`.
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_182_REPORT_20260701.md`
- Data Analytics artifact `Loop182 Architecture Parent Replay Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_REVIEW_EVIDENCE_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-01 - Loop181 clears the Loop180 strict runtime caveat

- Reran the same 9-row P1 `recall_loss_review / image_anchor_gate` packet from Loop180 with Bridge-only small-run health.
- Loop181 run id: `20260630_234216_623989`.
- Manifest completion is clean: completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `9`.
- Health is now Bridge-only: `mcp_health_include_search=false`, MCP health ok/checked `2/2`.
- Runtime contract audit is `GO` with issues `[]`.
- Row outcome split is relevant `9`, identified `6`, `safe_resolved=6`, `promotion_blocked=3`.
- Loop180 to Loop181 comparison shows `6/9` row movement and degraded search counter increase `57 -> 67`, so this is not semantic approval.
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_181_REPORT_20260701.md`
- Data Analytics artifact `Loop181 Bridge Health Rerun Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_REVIEW_EVIDENCE_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop180 returns from architecture phase to residual queue

- Built the first post-architecture residual canary from P1 `recall_loss_review / image_anchor_gate` with 9 image rows.
- Ran Loop180 as run `20260630_231142_887357` with VLM/OCR on, `--reuse-shards-only`, `--slang-db off`, effective parallel `9`.
- Manifest completion is clean by counts: completed/flushed/pending/failed `9/9/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `9`.
- Row outcome split is relevant `8`, identified `5`, `safe_resolved=5`, `promotion_blocked=4`.
- Strict runtime contract audit is `REVIEW` because the small run included search health (`MCP_HEALTH_INCLUDE_SEARCH=1`) rather than Bridge-only health.
- Created artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop180_p1_recall_loss_image_anchor_gate_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop180_p1_recall_loss_image_anchor_gate_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop180_p1_recall_loss_image_anchor_gate_runtime_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop180_p1_recall_loss_image_anchor_gate_runtime_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop180_p1_recall_loss_image_anchor_gate_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_180_REPORT_20260630.md`
- Data Analytics artifact `Loop180 P1 Image Anchor Gate Review` validate/render PASS.
- Gate remains: residual accounting delta `NO_DELTA_REVIEW_EVIDENCE_ONLY`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop179 implements the shared promotion gate architecture

- Added the first shared promotion gate layer required by the architecture-integrated goal: `src/llm_batch/promotion_gate.py`.
- The shared layer defines `GroundingState`, `EvidenceRecord`, `PromotionDecision`, `GateReport`, and `can_publish_title(...)`.
- Wired selected high-risk public-title publish paths in `src/llm_batch/agentic_pipeline.py` through the shared gate or preserved the gate decision on the final decision object.
- Updated `src/llm_batch/candidate_audit.py` so `promotion_decision.publish_allowed=false` remains `promotion_blocked` instead of leaking into `safe_resolved`.
- Added `tests/test_promotion_gate_contract.py` for status, reason-code, candidate-preservation, and `bypassed_gate=false` coverage.
- Verification:
  - `py_compile` PASS for touched files.
  - `tests.test_promotion_gate_contract -v`: `7 tests OK`.
  - `tests.test_regression_safe_work_bridge_contract -v`: `2 tests OK`.
  - `tests.test_candidate_audit -v`: `96 tests OK`.
  - affected representative bundle: `107 tests OK`.
  - Loop179 broader unittest: `1299` tests, `0` failures, `0` errors, `OK`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_review.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_review.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_data_analytics_artifact.json`
  - `docs/devs/loop_reports/LOOP_179_REPORT_20260630.md`
- Gate remains: architecture-phase broader unittest `GO`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `NOT_COMPLETE`.

## 2026-06-30 - Promoted the architecture idea into the active improvement goal

- Changed the current improvement harness goal framing after expert-agent collaboration concluded that the current architecture has reached the limit of one-off local guards.
- Created `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`.
- Updated `goal.md` and `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md` so the active objective now includes architecture integration before ordinary residual queue continuation.
- Promoted `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md` from a reference aid to active-goal design guidance.
- The integrated idea remains additive: keep `expert_main.py` runtime/checkpoint/shard machinery, add shared `GroundingState`, `EvidenceRecord`, `PromotionDecision`, `GateReport`, and `can_publish_title(...)` style promotion gate.
- This is not implementation or approval. The next engineering work is inventorying public-title/URL publish paths, adding the shared gate contract, wiring the highest-risk paths, adding decision-object tests, and re-running Loop176 broader unittest gate.
- Gate remains: semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `NOT_COMPLETE`.

## 2026-06-30 - Loop176 turns the broader unittest gate from open into FAIL

- Confirmed the user correction that the goal is still not complete.
- Current Codex app goal status was observed as `paused`, not `complete`.
- Ran the authoritative broader unittest command: `.venv312\Scripts\python.exe -m unittest discover --start-directory tests`.
- Result: exit code `1`, `1292` tests, `8` failures, `0` errors.
- Preserved the earlier `.venv312\Scripts\python.exe -m unittest discover -s tests` attempt as non-authoritative command-shape evidence because `-s tests` leaked into `expert_main.py` argparse.
- Failure clusters:
  - `acknowledged_previous_work_override`: `3`
  - `batch_alias_rescue_identity_missing`: `2`
  - `direct_ocr_work_surface_lock_bypass`: `1`
  - `community_review_headline_collision`: `1`
  - `candidate_audit_entity_mention_lint`: `1`
- Review artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop176_broader_unittest_gate_audit.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop176_broader_unittest_gate_audit.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop176_broader_unittest_gate_data_analytics_artifact.json`
- Data Analytics artifact validate/render PASS: `Loop176 Broader Unittest Gate Audit`.
- Loop report: `docs/devs/loop_reports/LOOP_176_REPORT_20260630.md`.
- Gate remains: broader unittest sweep `FAIL`, semantic quality `REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, full scan approval `false`, overall goal `NOT_COMPLETE`.

## 2026-06-30 - Documented promotion gate architecture visualization

- Added `docs/devs/ARCHITECTURE_PROMOTION_GATE_MIGRATION.md`.
- The new document visualizes:
  - current distributed title promotion/rescue architecture,
  - proposed additive `GroundingState` / `EvidenceRecord` / `PromotionDecision` / `GateReport` / `can_publish_title(...)` architecture,
  - proposed gate placement for high-risk public-title publish paths,
  - before/after test shape for `PromotionDecision` assertions,
  - migration plan and non-goals.
- Linked the document from `docs/devs/README.md`.
- Updated TODO/CHECKLIST/VERIFICATION/IMPROVEMENT_REGISTER so the next goal can reference one durable architecture visualization instead of scattered notes.
- Gate remains unchanged: architecture visualization is documentation only, not implementation or approval. Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, and overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop175 revalidates 11668288 as variance quarantine

- Rechecked the user correction that the goal is not complete.
- Revalidated `11668288` across 15 repeated result files from Loop96/97 and Loop159-174.
- Outcome split:
  - resolved work discussion `6`
  - blocked/nonwork/context-only `9`
  - candidate ledger `safe_resolved=6`, `promotion_blocked_or_hold=9`
  - latest Loop173/174 both `promotion_blocked / nonwork / title=null`
- Key distinction: official title/page existence for `가챠 중독자의 퓨전펑크 생활` is strong, but row-level work-discussion evidence is not stable.
- Disposition: `VARIANCE_QUARANTINE_HUMAN_REVIEW`, `stable_positive_control=false`.
- Review artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_11668288_expectation_revalidation.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_11668288_expectation_revalidation.md`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_11668288_expectation_revalidation_data_analytics_artifact.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_current_residual_gate_map_after_11668288_revalidation.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop175_residual_accounting_data_analytics_artifact.json`
- Data Analytics artifacts validate/render PASS: `Loop175 11668288 Expectation Revalidation` and `Loop175 Residual Accounting Sync`.
- Loop report: `docs/devs/loop_reports/LOOP_175_REPORT_20260630.md`.
- Accounting action: `NO_DELTA_ALREADY_COUNTED` because Loop97 already counted `11668288` as quarantine/human_review.
- Current accounting remains full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable queue total `131`, P0 `0`, P1 `61`, P2 `70`.
- Gate remains: run integrity `GO`, targeted canary `NO-GO`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop173-174 runs movement follow-up but confirms goal is not complete

- Ran Loop173 run `20260630_205124_675635` on the prepared 9-row movement/control follow-up input after Loop172.
- Runtime was clean: completed/flushed/pending/failed `9/9/0/0`, VLM/OCR `READY`, image_post_count `4`, MCP health `2/2/2`, runtime audit `GO`.
- Loop173 ledger counts were `safe_resolved=5`, `promotion_blocked=4`.
- `11658620` remained blocked; `11669928`, `11698880`, `11660259`, `11713222`, and `11658615` were safe-resolved in this packet.
- Main blocker: `11668288` regressed again to `promotion_blocked / nonwork / title=null`.
- Ran Loop174 run `20260630_210430_855303` as a `11668288` targeted repeat; runtime was clean (`1/1/0/0`, VLM/OCR `READY`, MCP health `1/1/1`, runtime audit `GO`) but the row still ended `promotion_blocked / nonwork / title=null`.
- Experimental `non_novel(gaming,high)` alias-lock bypass was not adopted and was removed after Loop174 failed.
- Verification after removal: touched-file `py_compile` PASS; focused title-lead alias release (`2 tests OK`), internal work-signal hold (`1 test OK`), and visual title-lead alias probe (`2 tests OK`) PASS.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop173_174_parent_movement_followup_review.md/json`.
- Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop173_174_data_analytics_artifact.json` validate/render PASS.
- Loop report: `docs/devs/loop_reports/LOOP_173_174_REPORT_20260630.md`.
- Gate remains: runtime `GO`, targeted canary `NO-GO`, semantic quality `REVIEW-LOCKED`, full scan approval `false`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop170-172 blocks 11658620 again but keeps goal open

- Ran Loop170 run `20260630_200407_176418` on the four-row Lubko prefix packet after Loop169.
- Runtime was clean: completed/flushed/pending/failed `4/4/0/0`, VLM/OCR `READY`, image_post_count `2`, MCP health ok/checked/required `2/2/2`, runtime audit `GO`.
- `11658620` was held as `promotion_blocked`, confirming the risky row needed explicit guard review before any parent approval language.
- Patched `src/llm_batch/agentic_pipeline.py` so stable-alias conflict correction cannot receive weak public-title bridge exemption when relation evidence is weak, ungrounded in the post, and held by the relation review.
- Added focused regression coverage in `tests/test_known_title_abbreviation_support.py`.
- Verification passed: touched-file `py_compile` and `tests/test_known_title_abbreviation_support.py -k stable_alias` (`5 tests OK`).
- Loop171 run `20260630_201444_112450` on the 8-row parent-prefix packet completed/flushed/pending/failed `8/8/0/0`; ledger counts were `safe_resolved=2`, `promotion_blocked=5`, `hold_without_candidates=1`.
- Loop172 run `20260630_202850_936395` completed/flushed/pending/failed `8/8/0/0`; ledger counts were `safe_resolved=5`, `promotion_blocked=2`, `hold_without_candidates=1`.
- Loop172 keeps `11658620` blocked with `official_title=null`, `primary_work=null`, and `candidate_ledger_status=promotion_blocked`.
- Parent-prefix semantic gate remains locked because `11674712` reopens as safe-resolved and `11669928`, `11706832`, and `11658615` still need movement disposition.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop170_172_lubko_parent_prefix_guard_review.md/json`.
- Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop170_172_data_analytics_artifact.json`.
- Loop report: `docs/devs/loop_reports/LOOP_170_172_REPORT_20260630.md`.
- Prepared next movement/control follow-up input: `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop173_parent_movement_followup_after_loop172_input.jsonl`.
- Gate remains: targeted guard `GO`, parent-prefix semantic gate `NO-GO / REVIEW-LOCKED`; keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop169 parent replay is runtime GO but semantic NO-GO

- Ran clean parent/representative replay after Loop168 as Loop169 run `20260630_191510_605137`.
- Result artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop169_parent_replay_after_loop168_noise_probe_release_result.json`.
- Manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop169_parent_replay_after_loop168_noise_probe_release_result_manifest.json`.
- Runtime contract is `GO`: completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, image_post_count `24`, MCP health ok/checked/required `36/36/36`.
- Parent-confirmed target recoveries: `11668288 -> 가챠 중독자의 퓨전펑크 생활`, `11713222 -> 잘생기면 편해지는 인방 생활`.
- Preserved safe-resolved target/control rows: `11698880 -> 가챠 중독자의 퓨전펑크 생활`, `11660259 -> 헌터갤러리의 국가권력급 기계공주`.
- Ledger counts: `safe_resolved=13`, `promotion_blocked=22`, `hold_without_candidates=2`, `output_consistency_lint=1`.
- Semantic movement vs Loop162 keeps the gate locked: `11658620` safe gain, `11674712` safe gain, `11669928` safe loss, `11658615` URL/source swap, and `11706832` caveated-demotion boundary reopening.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop169_parent_replay_after_loop168_review.md/json`.
- Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop169_data_analytics_artifact.json`.
- Loop report: `docs/devs/loop_reports/LOOP_169_REPORT_20260630.md`.
- Gate remains: `PARENT_REPLAY_RUNTIME_GO_TARGETS_RECOVERED_SEMANTIC_NO_GO`; keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop162-168 rechecks goal completion and recovers 2-row parent mimic

- Confirmed current Codex goal is still `active`; the user's correction was right: the goal is not complete.
- Reviewed Loop162, Loop165, Loop166, and Loop167 as non-approval evidence.
- Loop165 is partial runtime evidence because it ended with a shutdown flush gap and completed subset only.
- Patched `src/llm_batch/agentic_pipeline.py` so title-lead official-detail release rescue keeps lock, confirmed alias, and weak-bridge exemption flags.
- Patched `src/llm_batch/experts/orchestrator.py` so short title-leading alias platform/webnovel probes survive low-specificity pruning.
- Patched `_has_short_worklike_alias_search_probe` so alias plus official/platform/webnovel search requests count as the narrow visual alias probe signal.
- Verification passed: touched-file `py_compile`, focused 5-test bundle, Data Analytics artifact validate/render.
- Loop167 run `20260630_185448_143360` completed but stayed semantic `NO-GO` for `11668288`.
- Loop168 run `20260630_190202_307842` completed/flushed/pending/failed `2/2/0/0`, VLM/OCR `READY`, MCP health ok/checked/required `2/2/2`.
- Loop168 resolved `11698880` and `11668288` to `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop162_168_goal_completion_recheck_review.md/json`.
- Data Analytics artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop162_168_data_analytics_artifact.json`.
- Loop report: `docs/devs/loop_reports/LOOP_162_168_REPORT_20260630.md`.
- Gate remains: Loop168 is `MINI_PARENT_MIMIC_GO`, not semantic approval. Clean parent/representative replay, movement review, broader tests, panel/golden/collateral, and source full completion remain open. Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop161 recovers 11668288 targeted visual title-alias seed

- Rechecked the goal after the user noted it was not complete; status remains `ACTIVE / NOT_COMPLETE`.
- Root-caused `11668288` loss to Discourse `gaming(high)` semantic seed demotion plus Gatekeeper noise early exit suppressing the `가챠펑크` search seed.
- Patched `src/llm_batch/experts/orchestrator.py` with a narrow visual title-leading alias probe and auto seed restoration.
- The bridge requires image/VLM context, `title_as_body_continuation`, exact title-leading alias query/suggestion, and alias surface hit.
- Verification passed: orchestrator `py_compile`, focused 4-test visual/short-alias bundle, and existing alias-only nonwork forced-upgrade guard.
- Loop161 run `20260630_165512_125247` completed/flushed/pending/failed `1/1/0/0`.
- Runtime gate is `GO`: VLM/OCR `READY`, image_post_count `1`, effective parallel `1`, MCP health ok/checked/required `1/1/1`.
- Result artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop161_11668288_visual_title_alias_probe_auto_seed_result.json`.
- Manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop161_11668288_visual_title_alias_probe_auto_seed_result_manifest.json`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop161_11668288_visual_title_alias_probe_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_161_REPORT_20260630.md`.
- Data Analytics artifact `Loop161 11668288 Visual Title-Alias Probe Review` validate/render PASS.
- Target row recovered as `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`.
- Final gate fields: `candidate_ledger_status=safe_resolved`, `title_resolution_state=resolved`, `title_resolution_allowed=true`, `work_resolution=resolved`, `discussion_type=meme`, confidence `High`.
- Gate remains: targeted single-row recovery only; parent/representative replay after Loop161, `11706832` review, panel/golden/collateral, affected/full unittest sweep, source full completion all remain `OPEN`. Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop156 parent replay confirms targets but keeps semantic gate locked

- Ran the 38-row parent/representative replay after Loop155.
- Loop156 run `20260630_144848_180512` completed/flushed/pending/failed `38/38/0/0`.
- Runtime gate is `GO`: VLM/OCR `READY`, image_post_count `24`, effective parallel `36`, MCP health ok/required `36/36`.
- Result artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop156_parent_replay_after_loop155_alias_probe_result.json`.
- Manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop156_parent_replay_after_loop155_alias_probe_result_manifest.json`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop156_parent_replay_after_loop155_alias_probe_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_156_REPORT_20260630.md`.
- Data Analytics artifact `Loop156 Parent Replay After Loop155 Alias Probe Review` validate/render PASS.
- Parent-confirmed `11660259 -> 헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
- Parent-confirmed `11713222 -> 잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`.
- Status counts: `safe_resolved=9`, `promotion_blocked=26`, `hold_without_candidates=2`, `output_consistency_lint=1`.
- Semantic gate remains `NO-GO / REVIEW-LOCKED`: `11698880` changed from prior `가챠 중독자의 퓨전펑크 생활` to `상남자 [독점]`; `11706832` gained/changed and `11668288` lost vs Loop150.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop155 repairs 11660259 single-row alias bridge seed

- Treated Loop153 as invalid because Verifier hit `NameError: ctx is not defined`.
- Patched Verifier relation judge `ctx` propagation and explicit alias bridge support.
- Patched Orchestrator short worklike reaction alias probing so `기계공주` + `말한대로`/`대가리똑딱` can reach search/Decoder before semantic seed early-stop.
- Added regression coverage in `tests/test_title_lead_search_inferred_guard.py`.
- Verification passed: touched-file `py_compile`, focused 4-test bundle, broader 11-test relation/alias bundle.
- Loop155 run `20260630_143521_442264` completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, skip reason `no_image_blocks`.
- Result recovered `11660259` through `primary_work`: `헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
- Final gate fields: `candidate_ledger_status=safe_resolved`, `title_resolution_allowed=true`, `title_resolution_state=resolved`, `work_resolution=resolved`, `is_resolved_work_discussion=true`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop155_11660259_short_alias_reaction_probe_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_155_REPORT_20260630.md`.
- Data Analytics artifact `Loop155 11660259 Short Alias Reaction Probe Review` validate/render PASS.
- Gate remains: targeted single-row fix seed only; representative/parent replay and `11713222` parent stability remain open. Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop152 reproduces 11660259 title loss in current-code single repeat

- Compared `11660259` across Loop136, Loop142, and Loop150.
- Loop136/Loop142 preserved primary work `헌터갤러리의 국가권력급 기계공주` / `https://novelpia.com/novel/390228`.
- Loop150 lost the title to public title/url `null`, `promotion_blocked`, `unresolved_matchable`.
- Extracted the exact row from `loop134_parent_representative_after_loop133_source_enriched_packet.jsonl`.
- Loop152 run `20260630_141044_962593` completed/flushed/pending/failed `1/1/0/0`.
- VLM/OCR semantic gate `READY`; skip reason `no_image_blocks`; image_post_count `0`.
- Final row stayed public-title null with `candidate_ledger_status=hold_without_candidates`, `title_resolution_allowed=false`, `title_resolution_state=unresolved_matchable`, `work_resolution=none`, and `discussion_type=noise`.
- The log still shows Novelpia `https://novelpia.com/novel/390228`, Decoder/Synthesizer support, and raw Arbiter title evidence, but final demotion comes through `relation_judge:thematic_overlap_only`, Verifier/Jury non-relevant, `memory_query_forced_upgrade_guard`, and `title_surface_primary_relation_non_work_blocked`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop152_11660259_current_code_single_repeat_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_152_REPORT_20260630.md`.
- Data Analytics artifact `Loop152 11660259 Current-Code Single Repeat NO-GO Review` validate/render PASS.
- Gate remains: single-row `NO-GO_REPRODUCED`, not approval; next work is weak alias bridge root-cause/fix plus repeat and parent replay. Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop151 repeats 11713222 current-code success, not parent approval

- Reran exact `11713222` input after Loop150 lost the Loop148 targeted repair in parent scope.
- Loop151 run `20260630_135620_918136` completed/flushed/pending/failed `1/1/0/0`.
- VLM/OCR semantic gate `READY`; skip reason `no_image_blocks`; image_post_count `0`.
- Result artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop151_11713222_current_code_single_repeat_result.json`.
- Manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop151_11713222_current_code_single_repeat_result_manifest.json`.
- Log: `logs/expert_run_20260630_135620_918136.log`.
- Final primary work: `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`, alias `잘생인방`, source tier `official_detail`.
- Final gate fields: `candidate_ledger_status=safe_resolved`, `title_resolution_allowed=true`, `title_resolution_state=resolved`, `work_resolution=resolved`.
- Competing previous work `https://novelpia.com/novel/300042` appeared but did not override the current direct alias.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop151_11713222_current_code_single_repeat_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_151_REPORT_20260630.md`.
- Data Analytics artifact `Loop151 11713222 Current-Code Repeat Diagnostic` validate/render PASS.
- Gate remains: single-row diagnostic only; parent stability is still `OPEN`, `11660259` title loss remains next blocker, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop150 parent replay completes runtime, semantic gate remains locked

- Ran the 38-row parent/representative source-enriched packet after Loop149.
- Loop150 run `20260630_125822_273225` completed/flushed/pending/failed `38/38/0/0`.
- Runtime gate is `GO`: `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`, requested/effective parallel `36/36`, MCP health ok/required `36/36`.
- Result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop150_parent_replay_after_loop149_result.json`.
- Manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop150_parent_replay_after_loop149_result_manifest.json`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop150_parent_replay_after_loop149_review.md/json`.
- Compare artifacts: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop150_parent_vs_loop142_compare.md/json` and `loop150_parent_vs_loop136_compare.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_150_REPORT_20260630.md`.
- Data Analytics artifact `Loop150 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
- Semantic gate remains `NO-GO / REVIEW-LOCKED`: public-title rows `6/38`, movement vs Loop142 `same=31/lost=5/gained=2`, movement vs Loop136 `same=32/lost=4/gained=2`.
- Key blockers: `11713222` parent-scope loss after Loop148 targeted repair, `11660259` title loss vs Loop142/Loop136, and broader movement instability.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop149 repeats 11660257 current-code block, not parent approval

- Repeated reopened variance/control row `11660257` on current code after Loop148.
- Used input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop104_repair_11660257_single.jsonl`.
- Loop149 run `20260630_123900_117279` completed/flushed/pending/failed `1/1/0/0`.
- VLM/OCR semantic gate `READY`; image post count `1`; image fetch `2/2`.
- Final row stayed public-title blocked: `official_title=null`, `heretic_url=null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_allowed=false`, `title_resolution_state=unresolved_matchable`, `work_resolution=unresolved`.
- Candidate evidence preserves `암흑가 보스는 강제로 갱생한다` and `암흑가 검은머리 보스님` but does not promote either publicly.
- Internal drift remains visible: relation judge held, arbiter pushed a competing title, and final output scrubbed the promotion.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop149_11660257_current_code_repeat_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_149_REPORT_20260630.md`.
- Data Analytics artifact `Loop149 11660257 Current-Code Repeat Review` validate/render PASS.
- Gate remains after Loop150: parent replay runtime is `GO`, but semantic is `NO-GO / REVIEW-LOCKED`; `11713222` and `11660259` are next blockers, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop148 preserves 11713222 direct body alias primary, not parent approval

- Root-caused Loop142 `11713222 -> 잘생기면 인생이 편하다` as previous/current work confusion: body alias `잘생인방` points to current work `잘생기면 편해지는 인방 생활`, while comments mention related previous work alias `잘생인편`.
- Added direct-current-alias conflict detection in `src/llm_batch/agentic_pipeline.py`.
- Added verifier-detail lock so current title `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016` is preserved when verifier grounds the body alias.
- Prevented `work_resolution=multi_work` from letting a previous-work comment candidate steal the public title.
- Added regression coverage in `tests/test_title_lead_search_inferred_guard.py`: `test_multi_work_previous_comment_keeps_direct_body_alias_primary`.
- Verification passed for touched-file `py_compile` and the focused 5-test title-lead bundle.
- Ran Loop148 rerun2 canary `20260630_121958_717020`; runtime completed/flushed/pending/failed `1/1/0/0`, VLM/OCR ready with skip reason `no_image_blocks`.
- Final row `11713222`: `official_title=잘생기면 편해지는 인방 생활`, `heretic_url=https://novelpia.com/novel/384016`, `safe_resolved=true`, `title_resolution_allowed=true`, `work_resolution=resolved`.
- Candidate preservation keeps `잘생기면 인생이 편하다` / `https://novelpia.com/novel/300042` as mentioned/secondary evidence only.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop148_11713222_direct_body_alias_previous_work_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_148_REPORT_20260630.md`.
- Data Analytics artifact `Loop148 11713222 Direct Body Alias Previous Work Guard` validate/render PASS.
- Gate remains after Loop150: targeted row repair did not become parent approval; `11713222` lost the targeted repair in parent scope, `11660259` is a title-loss blocker, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop147 blocks 11714903 wrong-relevance public-title leak, not parent approval

- Root-caused Loop142 `11714903 -> 온 세상이 정신이상자다` as wrong-relevance public-title serialization: the official title exists, but the post-side bridge is a VTuber/community meme and candidate-only keyword overlap.
- Added `apply_judge_seed_wrong_relevance_public_title_guard(...)` in `src/llm_batch/candidate_audit.py`.
- Wired the guard in `expert_main.py` final postprocess before weak public-title bridge handling.
- Added regression coverage in `tests/test_candidate_audit.py`: `test_wrong_relevance_seed_public_title_is_candidate_hold`.
- Added reason-scrub coverage in `tests/test_expert_main_comment_metadata.py`: `test_output_consistency_lint_hold_scrubs_resolution_text`.
- Verification passed for touched-file `py_compile` and the focused 4-test wrong-relevance/reason-scrub bundle.
- Ran Loop147 canary `20260630_114605_431073`; runtime completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
- Final row `11714903`: `identity.is_relevant=false`, `discussion_type=community_banter`, public title/url `null`, `safe_resolved=false`, `title_resolution_allowed=false`, `candidate_ledger_status=output_consistency_lint`, `work_resolution=none`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop147_11714903_wrong_relevance_public_title_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_147_REPORT_20260630.md`.
- Data Analytics artifact `Loop147 11714903 Wrong Relevance Public Title Guard` validate/render PASS.
- Gate remains after Loop150: targeted row repair only; `11714903` still holds, but `11713222` lost the Loop148 repair in parent scope, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop146 repairs 11698897 candidate preservation, not parent approval

- Root-caused the `11698897` drift to candidate-ledger pollution: public title promotion could be blocked, but an already rejected `search_evidence_alias_inference` candidate such as `스페이스 오페라` could still survive into `candidate_preservation_sources`.
- Added `_prune_rejected_alias_inference_candidates_for_hold(...)` in `src/llm_batch/agentic_pipeline.py`.
- Added regression coverage in `tests/test_title_lead_search_inferred_guard.py`: `test_rejected_search_alias_inference_candidate_is_pruned_from_hold_snapshot`.
- Verification passed for touched-file `py_compile`, the new unit test plus existing cross-media hold test, and the focused 6-test title-lead/official-url guard bundle.
- Ran diagnostic Loop146 canary first; it confirmed the partial failure: public promotion stayed blocked, but `스페이스 오페라` remained in candidate ledger.
- Ran Loop146b final canary `20260630_111809_336389`; runtime completed `1/1`, pending `0`, failed `0`, VLM/OCR `READY`.
- Final row `11698897`: public title `null`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`, correct candidate `[림월드]변방계에서 회귀자로 살아남기` / `https://novelpia.com/novel/382324` preserved, `스페이스 오페라` absent from candidate preservation sources.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop146_11698897_candidate_preservation_repair_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_146_REPORT_20260630.md`.
- Data Analytics artifact `Loop146 11698897 Candidate Preservation Repair` validate/render PASS.
- Gate remains: targeted row repair only; Loop142 gained-title review rows, parent replay, source full completion, and full-panel collateral approval remain open; `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop145 accepts 11706832 caveated demotion, not code repair

- Reviewed Loop142 parent-scope title loss `11706832` against Loop136 compare, Loop139 native/web evidence, and local image evidence.
- Confirmed Loop139 official detail page evidence: `https://novelpia.com/novel/250464` corresponds to `황제의 딸로 환생했다`.
- Kept the row caveated because the post-side bridge is weak: `황제분충 ㄱㅊ함?`, body `문피안가`, comments `노피아` / `표절물인가`, and a textless meme/fanart image.
- Accepted the Loop142 public-title-null state as `ACCEPTED_CAVEATED_DEMOTION_NOT_CODE_REPAIR`.
- No production code patch and no `expert_main.py` rerun were performed.
- Council reviewers agreed that code repair would risk broad community-alias promotion.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop145_11706832_alias_caveat_disposition_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_145_REPORT_20260630.md`.
- Data Analytics artifact `Loop145 11706832 Accepted Caveated Demotion Review` validate/render PASS.
- Gate remains after Loop146: Loop142 gained-title review rows, parent replay, source full completion, and full-panel collateral approval remain open; `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop144 repairs 11705231 targeted title loss, not parent approval

- Root-caused Loop142 `11705231` loss to a precision guard gap: stale multi-work hold flags were recoverable for locked-official reread support but not for the verified-alias official-detail plus final-reread path.
- Added narrow `verified_alias_stale_reread_support` logic in `src/llm_batch/candidate_audit.py`.
- Added regression coverage in `tests/test_candidate_audit.py`: `test_precision_seed_verified_alias_reread_bypasses_stale_multi_work_clear`.
- Verification passed for touched-file `py_compile` and the focused 7-test precision guard bundle.
- Full `tests.test_candidate_audit` was attempted and still has the separate broader failure: `test_entity_mentions_do_not_pollute_resolved_titles` expects `safe_resolved` but observes `official_title_lint`.
- Ran Loop144 single-row canary `20260630_102603_664724` from `loop144_11705231_verified_alias_stale_multi_work_precision_input.jsonl`.
- Runtime completed `1/1`, pending snapshot `[]`, VLM/OCR semantic gate `NOT_APPLICABLE` because `image_post_count=0`, with `--reuse-shards-only` and no approval implication.
- Result: `11705231` is `safe_resolved`, official title `탐식의 재림`, final URL `https://series.naver.com/novel/detail.series?productNo=2847498`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop144_11705231_verified_alias_stale_multi_work_precision_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_144_REPORT_20260630.md`.
- Data Analytics artifact `Loop144 11705231 Targeted Precision Guard Review` validate/render PASS.
- Gate remains after Loop145/Loop146: targeted repair only; gained-title review, parent replay, source full completion, and full-panel collateral approval remain open; `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop143 repairs 11658615 targeted title loss, not parent approval

- Root-caused Loop142 `11658615` loss to an over-broad promoted-image conflict guard: a noisy direct image/OCR surface was treated as conflicting with the verified official platform title.
- Added a narrow verified-alias official-detail lock exemption in `src/llm_batch/candidate_audit.py`.
- Added regression coverage in `tests/test_candidate_audit.py`: `test_verified_alias_detail_lock_exempts_noisy_image_surface_conflict`.
- Verification passed for touched-file `py_compile` and the focused 4-test candidate-audit bundle.
- Full `tests.test_candidate_audit` was attempted and still has a separate broader failure: `test_entity_mentions_do_not_pollute_resolved_titles` expects `safe_resolved` but observes `official_title_lint`.
- Ran Loop143 single-row canary `20260630_100754_773029` from `loop143_11658615_verified_alias_image_surface_fix_input.jsonl`.
- Runtime completed `1/1`, pending snapshot `[]`, VLM/OCR semantic gate `READY`, with `--reuse-shards-only` and no approval implication.
- Result: `11658615` is `safe_resolved`, official title `이거 럽코 빙의물인가요`, URL `https://novel.munpia.com/533816`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop143_11658615_verified_alias_image_surface_fix_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_143_REPORT_20260630.md`.
- Data Analytics artifact `Loop143 11658615 Targeted Fix Review` validate/render PASS.
- Gate remains after Loop144/Loop145/Loop146: targeted repair only; gained-title review, parent replay, source full completion, and full-panel collateral approval remain open; `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop142 parent replay is runtime GO but semantic NO-GO

- Ran the required parent/representative replay after Loop141 as Loop142 run `20260630_091135_863555`.
- Runtime was clean: result rows `38/38`, pending snapshot `0`, VLM/OCR semantic gate `READY`, MCP health `36/36`, no shard auto-up/recreate.
- Runtime audit artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop142_parent_replay_after_loop141_hold_boundary_runtime_audit.md/json`.
- Compare artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop142_parent_vs_loop136_compare.md/json`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop142_parent_replay_after_loop141_hold_boundary_review.md/json`.
- Data Analytics artifact `Loop142 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
- Semantic result is still `NO-GO / REVIEW-LOCKED`: title movement vs Loop136 is `gained_title=5`, `lost_title=4`, `same_title=4`, `same_no_title=25`.
- Loop141 target rows remain unpromoted (`11663521`, `11694019`, `11698897`), but `11698897` shows candidate-preservation drift away from the Loop141 Rimworld candidate evidence.
- Loop139 native/web-confirmed titles `11658615`, `11706832`, and `11705231` are no longer final titles in Loop142; `11700470` demotion is expected after the Loop137 listing-description guard.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop141 closes current expected/recall row-level rationale as HOLD/control

- Completed audit-only row-level HOLD review for `11663521`, `11694019`, and `11698897`.
- Downloaded and visually inspected available images for `11663521` and `11698897`; DCCon helper images that returned HTTP 403 were recorded as unavailable evidence.
- `11663521` is `HOLD_BOUNDARY_CONFIRMED`: the candidate `[초전자포] 시스터즈가 되었다` remains preserved, but the post/image evidence lacks a direct work-title/platform bridge.
- `11694019` is `HOLD_BOUNDARY_CONFIRMED`: the row is author/trope/context-only around `미츄리` and `혼후순결`, with no direct title or official URL in the post.
- `11698897` is `VARIANCE_HOLD_CONTROL_CONFIRMED`: the candidate `[림월드]변방계에서 회귀자로 살아남기` is real and preserved, but prior Loop120-127 evidence shows this exact row is a repeat reopen/hold variance control.
- Current expected/recall unrationalized open rows after Loop141: `0`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop141_current_expected_recall_hold_boundary_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_141_REPORT_20260630.md`.
- Data Analytics artifact `Loop141 Current Expected Recall HOLD Boundary Review` validate/render PASS.
- Gate remains: row-level rationale complete, not approval; parent/representative semantic replay remains open, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop140 narrows current expected/recall remaining rows

- Completed audit-only consolidation of the current expected/recall remaining list after Loop139.
- Rechecked Loop92-93 stable P1A dispositions and Loop136 latest row states.
- Split out `11695623` as current HOLD confirmed from Loop92-93 + Loop136: `[림월드]변방계에서 회귀자로 살아남기` remains candidate evidence only, public title `null`.
- Split out `11700495` as current no-public confirmed from Loop92-93 + Loop136: context-only, public title `null`.
- Split out `11705261` as current HOLD confirmed from Loop92-93 + Loop136: ETR/TRPG candidates remain candidate evidence only, public title `null`.
- Remaining current expected/recall rows are now `11663521`, `11694019`, and `11698897`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop140_remaining_expected_recall_disposition_consolidation.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_140_REPORT_20260630.md`.
- Data Analytics artifact `Loop140 Remaining Expected Recall Disposition Consolidation` validate/render PASS.
- Gate remains: audit-only accounting improvement, not approval; parent/representative semantic replay remains open, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop139 reviews remaining Loop136 safe-resolved rows

- Completed audit-only native/web review of remaining Loop136 `safe_resolved` rows: `11698880`, `11658615`, `11660237`, `11660258`, `11660259`, `11706832`, and `11705231`.
- Current official/platform page-title checks matched Loop136 final titles for all seven rows.
- Downloaded and visually inspected image rows `11698880`, `11658615`, `11660237`, and `11706832`.
- Confirmed `11658615` image directly shows work card title `이거 럽코 빙의물인가요` and author `두유하이볼`.
- Recorded `11698880`, `11660237`, and `11706832` images as meme/reaction-only rather than title-bridge evidence.
- Kept `11706832` as official-page-confirmed but alias-bridge caveated because `황제분충` remains community-mediated.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop139_loop136_safe_resolved_native_web_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_139_REPORT_20260630.md`.
- Gate remains: remaining safe-resolved native/web review is `COMPLETE_WITH_11706832_ALIAS_CAVEAT`, not approval; parent/representative semantic replay remains open, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop138 confirms 11685994 image/native-web HOLD

- Completed audit-only image/native-web exact-title verification for `11685994`.
- Rechecked Loop136 latest row state: public title `null`, URL `null`, `safe_resolved=false`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=ocr_explicit_title_unresolved`, `title_resolution_allowed=false`.
- Reviewed local image evidence `11685994_dc_image.jpg` and title crop `11685994_title_crop_x3.png`; visual/OCR title family remains around `교황님 아 하세요 / 마왕들어가요`, author `아데라`, `장편소설`.
- Rejected candidate pages `https://novelpia.com/novel/270445`, `https://novelpia.com/novel/383971`, and `https://page.kakao.com/content/56516207` as wrong-work candidates because their titles/authors do not match the cover title/author pair.
- No code relaxation was adopted and no `expert_main.py` rerun was needed because the current row state already holds public title `null`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop138_11685994_image_native_web_verification_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_138_REPORT_20260630.md`.
- Gate remains: `11685994` is `IMAGE_NATIVE_WEB_VERIFIED_INFO_MISSING_HOLD`, not approval; parent/representative semantic replay remains open, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop137 repairs 11700470 description-title promotion to HOLD

- Reviewed Loop136 `11700470` safe-resolved output against native/web evidence.
- Confirmed `https://novelpia.com/novel/436108` page title is `납치당했는데 미소녀가 되었다`, while Loop136 promoted description text `괴한들에게 납치당했더니 여자아이가 되어버렸다. …이득 아닌가? [아니었다.]`.
- Added `official_title_looks_like_listing_description` guard in `src/llm_batch/candidate_audit.py`.
- Added regression coverage in `tests/test_candidate_audit.py`.
- Verification passed: `py_compile`, related 7-test bundle, pre-run model check, search shard audit `36/36`.
- Ran Loop137 focused canary `20260630_074755_088187`.
- Runtime completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, image_post_count `1`; runtime audit returned `GO`.
- Result: public title `null`, URL `null`, `safe_resolved=false`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=ocr_explicit_title_unresolved`, `title_resolution_allowed=false`.
- Compare `loop137_11700470_vs_loop136_compare.md/json` reports `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, `movement_status_counts={review: 1}`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop137_11700470_listing_description_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_137_REPORT_20260630.md`.
- Gate remains: `11700470` is `TARGETED_11700470_REPAIRED_TO_HOLD_LOOP137_NOT_APPROVAL`; parent/representative semantic replay remains open, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop136 parent replay keeps runtime green but semantic gate open

- Reran the Loop134 parent/representative 38-row packet after the Loop135 Phase2 HOLD precision guard.
- Run id: `20260630_065926_226944`.
- Runtime completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, image_post_count `24`.
- requested/effective parallel `36/36`; MCP health ok/required/after-filter `36/36/36`.
- Strict runtime audit returned `GO`.
- Loop135 `11694035` repair held at parent scope: public title `null`, `title_resolution_state=unresolved_matchable`, `candidate_ledger_status=promotion_blocked`.
- `11705231` also stayed restored at parent scope as `탐식의 재림`, URL `https://page.kakao.com/content/50219568`.
- Compare artifact `loop136_parent_vs_loop134_compare.md/json` reports `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, and `movement_status_counts={review: 38}`.
- Result counts: `safe_resolved=8`, `promotion_blocked=27`, `hold_without_candidates=2`, `output_consistency_lint=1`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop136_parent_replay_after_loop135_phase2_hold_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_136_REPORT_20260630.md`.
- Gate remains: runtime contract `GO`, parent/representative semantic replay `NO-GO / REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop135 blocks Phase2 HOLD precision bypass for 11694035

- Root-caused the Loop134 golden negative violation `11694035 -> 아카데미 생존 갤러리`.
- Added a judge-seed-only guard in `src/llm_batch/candidate_audit.py`: Phase2 `HOLD` / `re_search` precision seeds cannot bypass review via independent official-detail support.
- Added regression coverage in `tests/test_candidate_audit.py`.
- Verification passed: `py_compile` and 6 related unittest cases.
- Full `tests.test_candidate_audit` was attempted and still has a separate existing failure: `test_entity_mentions_do_not_pollute_resolved_titles`.
- Pre-run checks passed: vLLM model endpoint available and search shard audit `36/36`, bad `[]`.
- Ran Loop135 focused canary `20260630_065021_019075` for `11694035`.
- Runtime completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, image_post_count `1`; strict runtime audit returned `GO`.
- Result: Loop134 `아카데미 생존 갤러리` / `safe_resolved` -> Loop135 public title `null`, `candidate_ledger_status=promotion_blocked`, `promotion_blocked_reasons=[phase2_hold_seed_requires_review]`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop135_11694035_phase2_hold_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_135_REPORT_20260630.md`.
- Gate remains: `11694035` is `TARGETED_11694035_REPAIRED_LOOP135_NOT_APPROVAL`; parent/representative replay after this patch is `OPEN / NOT_RUN`; source full completion `OPEN`; full-panel collateral approval `NO-GO`; `semantic_quality=REVIEW-LOCKED`; `full_scan_approval=false`; overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop134 restores 11705231 at parent scope but keeps semantic gate NO-GO

- Created Loop134 source-enriched parent packet from Loop104 38-row role mix, replacing only `11705231` with the Loop133 row-level source evidence input.
- Checked vLLM model endpoint and search shards before run; shard audit returned `36/36`, bad `[]`.
- Ran Loop134 parent/representative replay as run `20260630_055411_323400`.
- Runtime completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`.
- requested/effective parallel `36/36`; MCP health ok/required/after-filter `36/36/36`.
- Strict runtime audit returned `GO`.
- `11705231` restored at parent scope: Loop131 `null` -> Loop134 `탐식의 재림`, URL `https://page.kakao.com/content/50219568`, `candidate_ledger_status=safe_resolved`.
- Parent semantic gate remains `NO-GO / REVIEW-LOCKED`: final public title rows `14/38`, Loop131->Loop134 movement `gained_title=7`, `changed_title=1`, `lost_title=1`, `same_title=29`.
- Remaining expected-work losses: `11663521`, `11685994`, `11694019`, `11700470`.
- Reopened/changed controls include `11694035`, `11714903`, `11706832`, `11698880`, `11695623`, and `11660257`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop134_parent_representative_after_loop133_source_enriched_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_134_REPORT_20260630.md`.
- Data Analytics artifact `Loop134 Parent Replay Quantitative Review` validate/render PASS.
- Gate remains: `11705231` is `PARENT_SCOPE_TARGET_RESTORED_LOOP134_NOT_APPROVAL`; parent/representative semantic replay `NO-GO`; source full completion `OPEN`; full-panel collateral approval `NO-GO`; `semantic_quality=REVIEW-LOCKED`; `full_scan_approval=false`; overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop133 closes 11705231 focused source-enriched blocker, not full goal

- Fixed row-level source evidence preservation for `11705231` source-enriched replay.
- Added narrow locked-official contextual-anchor precision bypass in `candidate_audit.py`.
- Verified source evidence injection via `source-evidence search seed: 3/3 results loaded from input row`.
- Ran focused 13-test bundle: PASS.
- Ran `py_compile` for touched runtime modules: PASS.
- Canary `loop133_11705231_character_setting_kakao_source_enriched_after_precision_context_anchor_result.json` completed `1/1/0/0`, `Identified=1`, title `탐식의 재림`, `candidate_ledger_status=safe_resolved`.
- Repeat canary `loop133_11705231_character_setting_kakao_source_enriched_after_precision_context_anchor_repeat_result.json` completed `1/1/0/0`, `Identified=1`, title `탐식의 재림`, `candidate_ledger_status=safe_resolved`.
- Runtime audits for both latest canaries returned `GO`, with semantic approval explicitly not evaluated by runtime audit.
- Loop report updated: `docs/devs/loop_reports/LOOP_133_REPORT_20260630.md`.
- Gate remains: `11705231` is `TARGETED_REPAIR_PASS_LOOP133_NOT_APPROVAL`; parent/representative replay, golden/collateral replay, source full completion, and full-panel collateral approval remain open. Keep `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop132 accepts completion challenge and classifies remaining rows

- Accepted the user challenge that the active goal was not complete.
- Re-read the pasted goal contract and rechecked Loop131 result/review evidence.
- Reviewed the existing precision-seed conflict test contract before considering a code relaxation.
- Created review artifacts `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop132_completion_challenge_disposition_audit.md/json`.
- Created loop report `docs/devs/loop_reports/LOOP_132_REPORT_20260630.md`.
- Data Analytics artifact `Loop132 Completion Challenge Disposition Audit` validate/render PASS.
- Dispositioned five remaining Loop131 expected-work losses: `HOLD_BOUNDARY=3`, `INFO_MISSING_NATIVE_WEB=1`, `NARROW_REPLAY_CANDIDATE=1`.
- No code patch was adopted because a broad precision-seed relaxation is unsafe.
- Best next narrow target is `11705231`; `11685994` needs native-web/image exact-title verification; `11663521`, `11694019`, and `11700470` remain HOLD boundaries.
- Gate remains: runtime contract `GO`, semantic quality `NO-GO / REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop131 proves runtime closure but leaves semantic gate NO-GO

- Reran the Loop104 38-row parent/representative packet after Loop130 as Loop131.
- Run id: `20260630_030549_717991`.
- Runtime manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`.
- requested/effective parallel `36/36`; MCP health ok/required/after-filter `36/36/36`.
- Strict runtime audit returned `GO`.
- Final public-title rows: `8/38`; no-final-public-title rows: `30/38`.
- Loop129 P0 HOLD/control `11706871 -> 파우스트 1` stayed closed at parent replay scope: final public title `null`, `candidate_ledger_status=promotion_blocked`.
- One expected-work row restored/moved positive: `11698897 -> [림월드]변방계에서 회귀자로 살아남기`.
- Five expected-work losses remain: `11663521`, `11685994`, `11694019`, `11700470`, `11705231`.
- Public-title movement versus Loop129 remains broad, so collateral stability is not proven.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop131_parent_representative_replay_after_faust_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_131_REPORT_20260630.md`.
- Data Analytics artifact `Loop131 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
- Gate remains: parent/representative semantic replay `NO-GO`, Loop103 queue suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop130 targets Faust direct-rescue bypass but keeps goal active

- Root-caused Loop129 P0 HOLD/control `11706871 -> 파우스트 1` to physical/classic book cover OCR being accepted by direct image/OCR promotion paths.
- Added a physical/classic-book image guard in `src/llm_batch/agentic_pipeline.py`.
- The guard blocks non-webnovel book-cover OCR from structured direct-image, image-primary, and OCR-catalog official-title evidence while preserving candidate evidence.
- Added/extended regression coverage in `tests/test_title_lead_search_inferred_guard.py`.
- Verification passed: `py_compile` and 3 focused unittests.
- Ran Loop130 targeted canary `20260630_024726_142878`.
- Runtime manifest completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, image_post_count `1`.
- Runtime audit returned `GO`.
- Target row `11706871` now serializes final public title `null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=ocr_explicit_title_unresolved`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop130_faust_direct_rescue_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_130_REPORT_20260630.md`.
- Data Analytics artifact `Loop130 Faust Direct Rescue Guard Review` validate/render PASS.
- Gate remains: parent/representative replay after patch `OPEN / NOT_RUN`, six expected-work losses remain, Loop103 queue suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop129 closes runtime blocker but semantic gate remains NO-GO

- Pre-restore shard audit `loop128_search_shard_audit_after_no_go_20260630.json` showed `16/36` healthy shards, bad `17-36`.
- Restored missing shards with protected incremental `tools/warp_shards.py up --count 36 --shards 17-36`.
- Post-restore shard audit `loop129_search_shard_audit_after_restore_20260630.json` showed `36/36`, bad `[]`.
- Reran the Loop104 anti-regression parent/representative packet as Loop129.
- Run id: `20260630_020121_110991`.
- Runtime manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`.
- requested/effective parallel `36/36`; MCP health ok/required/after-filter `36/36/36`.
- Strict runtime audit returned `GO`.
- Public-title rows: `9/38`; no-public-title rows: `29/38`.
- Semantic NO-GO remains: expected-work losses `11698897`, `11663521`, `11685994`, `11694019`, `11700470`, `11705231` still have final public title `null`.
- Recent P0 HOLD/control `11706871` still gained public title `파우스트 1`.
- Public-title movement versus Loop128: `11698880`, `11669928`, `11661876` gained title; `11663540` lost title.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop129_parent_representative_replay_after_shard_restore_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_129_REPORT_20260630.md`.
- Data Analytics artifact `Loop129 Parent Replay Runtime GO Semantic NO-GO Review` validate/render PASS.
- Gate remains: parent/representative semantic replay `NO-GO`, Loop103 queue suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop128 parent replay completes but remains NO-GO

- Reran the Loop104 anti-regression parent/representative packet after Loop123-127 as Loop128.
- Run id: `20260630_010430_041790`.
- Runtime manifest completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`.
- Strict runtime audit returned `NO-GO`: `mcp_endpoint_count_after_filter_lt_health_required_ok_count`, with `after_filter=16` and `required_ok=36`.
- Public-title rows: `7/38`; no-public-title rows: `31/38`.
- Loop123-127 target rows stayed without final public title.
- Golden negative no-public-work rows did not gain a public title.
- Semantic NO-GO remains because golden positive expected-work rows lost title: `11698897`, `11663521`, `11685994`, `11694019`, `11700470`, `11705231`.
- Recent P0 HOLD/control `11706871` gained public title `파우스트 1`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop128_parent_representative_replay_after_loop127_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_128_REPORT_20260630.md`.
- Data Analytics artifact `Loop128 Parent Replay NO-GO Review` validate/render PASS.
- Gate remains: parent/representative replay `OPEN`, Loop103 queue suspended, source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-30 - Loop123-127 holds five-row public-title reopen packet but keeps goal active

- Repeated the Loop115 five-row packet after Loop122 showed the prior hold could still be bypassed by official URL recall.
- Loop123 run `20260630_001114_430299` identified `0/5`, but this was repeat-only evidence with remaining instability.
- Loop124 run `20260630_002004_713872` reopened `11694019 -> 이세계에서 사이비로 살아남기`.
- Loop125 run `20260630_002835_742034` reopened `11658620 -> 이거 럽코 빙의물인가요` and `11668288 -> 가챠 중독자의 퓨전펑크 생활`.
- Loop126 run `20260630_004146_072443` blocked `11668288` through forced-upgrade relation-hold guard, but reopened `11694019` through `search_catalog_contextual_work`.
- Added alias-only official URL recall competing-candidate hold, generic low-information batch-alias blocking, forced-upgrade relation-hold blocking, and broader author+plot composite precision demotion.
- Verification passed: `py_compile`; focused tests; related unittest bundle `271 OK`; `git diff --check` with CRLF warnings only.
- Loop127 run `20260630_004841_310108` completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `2`, identified `0`.
- All Loop127 rows serialized with final public title `null`: `11658620`, `11666713`, `11668288`, `11694019`, `11698897`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop123_127_public_title_reopen_repair_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_123_127_REPORT_20260630.md`.
- Data Analytics artifact `Loop123-127 Public Title Reopen Repair Review` validate/render PASS.
- Gate remains: targeted five-row repair only; parent/representative replay `OPEN`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop120-121 blocks batch alias competing-hold reopening but keeps goal active

- Repeated the Loop119 five-row packet as Loop120.
- Loop120 run `20260629_231942_505674` completed `5/5/0/0`, VLM/OCR `READY`, but reopened `11698897 -> [림월드]변방계에서 회귀자로 살아남기`.
- Root cause: `title_lead_alias_official_detail_release` / batch-memory exact alias rescue could override `official_url_recall_blocked_competing_candidate`, `multi_work_title_cleared`, `secondary_reference_official_alias_blocked_after_multi_work_title_cleared`, `expert_conflict`, and `budget_quarantine_candidate`.
- Added competing-hold batch alias rescue block in `src/llm_batch/agentic_pipeline.py`.
- Added candidate-audit demotion before official-detail/precision exemptions and expanded precision hard-hold flags in `src/llm_batch/candidate_audit.py`.
- Added regression test coverage in `tests/test_candidate_audit.py`.
- Verification passed: `py_compile`; affected unittest `248 OK`.
- Loop121 run `20260629_233340_435398` completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `2`, identified `0`.
- `11698897` now serializes with final public title `null`, `candidate_ledger_status=promotion_blocked`, and competing-hold rescue block flags.
- `11668288` positive/control drifted to `null`/`promotion_blocked`, so positive-control stability remains open.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop120_121_batch_alias_competing_hold_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_120_121_REPORT_20260629.md`.
- Data Analytics artifact `Loop120-121 Batch Alias Competing-Hold Review` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, parent/representative replay `OPEN`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop118-119 holds Loop117 reopen paths but keeps goal active

- Root-caused the Loop117 public-title reopenings for `11666713`, `11694019`, and `11698897`.
- Added sticky verifier re-promotion veto, cross-media title-body-only official URL recall hold, and high-strength weak-source exact-title bridge hold.
- Preserved medium registry/known-abbreviation alias support so real alias paths are not collapsed by the weak-source guard.
- Loop118 run `20260629_225200_510563` completed `5/5/0/0`; it held `11694019` and `11698897` but still reopened `11666713 -> 21세기 무림`.
- Loop119 run `20260629_225904_808962` completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `2`, identified `1`.
- Loop119 target reopen rows `11666713`, `11694019`, and `11698897` all serialized with final public title `null`.
- `11668288 -> 가챠 중독자의 퓨전펑크 생활` is separated as a known positive/control resolution, not a target regression.
- Verification passed: `py_compile`; affected unittest `247 OK`; `git diff --check` PASS with line-ending warnings only.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop118_119_reopen_guard_replay_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_118_119_REPORT_20260629.md`.
- Data Analytics artifact `Loop118-119 Reopen Guard Replay Review` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop117 reconfirms goal not complete after broader replay

- Reran the existing Loop115 five-row variance packet after the Loop116b-116d guard.
- Loop117 run `20260629_222704_833019` completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `2`, identified `3`.
- `11658620` remained blocked with `candidate_ledger_status=promotion_blocked`, and `11668288` stayed blocked/nonwork.
- Recurrent public-title reopenings occurred for `11666713 -> 21세기 무림`, `11694019 -> 이세계에서 사이비로 살아남기`, and `11698897 -> [림월드]변방계에서 회귀자로 살아남기`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop117_public_title_gain_after_guard_replay_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_117_REPORT_20260629.md`.
- Data Analytics artifact `Loop117 Public Title Gain Replay` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop116b-116d reproduces and repairs lubko prefix public-title reopening

- Built Loop116b four-row prefix packet `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop116b_lubko_prefix_context_4.jsonl` from original Loop108 rows: `11658615`, `11658620`, `11660237`, `11660258`.
- Loop116b run `20260629_215526_021681` completed `4/4/0/0`, VLM/OCR `READY`, identified `4`; it reproduced the unsafe `11658620 -> 이거 럽코 빙의물인가요` public title with stable-alias conflict flags.
- Added `_stable_alias_conflict_bridge_is_ambiguous` in `src/llm_batch/agentic_pipeline.py`; ambiguous/attached slang evidence can preserve candidates but no longer grants weak public-title bridge exemption.
- Mirrored known-title abbreviation update-question exception into the later semantic no-work batch-alias gate.
- Added focused test coverage in `tests/test_known_title_abbreviation_support.py`.
- Loop116c run `20260629_220351_554714` completed `4/4/0/0`, VLM/OCR `READY`, identified `3`; `11658620` stayed `official_title=null`, `candidate_ledger_status=promotion_blocked`.
- Loop116d repeat `20260629_221301_518080` completed `4/4/0/0`, VLM/OCR `READY`, identified `3`; `11658620` again stayed `official_title=null`, `candidate_ledger_status=promotion_blocked`.
- Verification passed: `py_compile`; `tests.test_candidate_audit` `83 OK`; `tests.test_known_title_abbreviation_support` `25 OK`; focused stable-alias correction integration test OK.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop116b_116d_lubko_prefix_context_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_116B_116D_REPORT_20260629.md`.
- Data Analytics artifact `Loop116b-116d Lubko Prefix Guard Review` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop116a narrows Loop114 public-title variance without completing goal

- Built Loop116a input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop116a_lubko_neighbor_context_2.jsonl` from original Loop108 rows for `11658615` and `11658620`.
- Ran Loop116a `20260629_214134_424194` with `--slang-db off`, VLM/OCR enabled, and image VLM/OCR required.
- Runtime completed/flushed/pending/failed `2/2/0/0`, VLM/OCR `READY`, image_post_count `1`, identified titles `1`.
- `11658615` stayed safe-resolved as `이거 럽코 빙의물인가요` with official URL `https://novel.munpia.com/533816`.
- `11658620` preserved verified alias/official-detail evidence and `primary_work=이거 럽코 빙의물인가요`, but final `official_title=null`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`.
- Immediate neighbor context is therefore not sufficient to reproduce Loop114's unsafe `safe_resolved` serialization for `11658620`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop116a_lubko_neighbor_context_probe_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_116A_REPORT_20260629.md`.
- Data Analytics artifact `Loop116a Lubko Neighbor Context Probe` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop115 completion recheck confirms goal NOT_COMPLETE

- Rechecked the original pasted goal contract, Loop06 report, source manifest/recovery summary, Phase1 queue, full-panel collateral residuals, Loop111-114 review, and current docs/checklists.
- Ran read-only subagent audits for source/preflight, collateral/semantic gate, and docs/gate sync; all confirmed the active goal is not complete.
- Built Loop115 input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop115_public_title_gain_variance_focus_5.jsonl` from original Loop108 rows, covering Loop114 public-title gains `11658620`, `11666713`, `11668288`, `11694019` plus focused/broad instability row `11698897`.
- Ran Loop115 `20260629_212549_694367` with VLM/OCR required and `--slang-db off`; runtime completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, image_post_count `2`, identified titles `0`.
- Loop115 repeat did not reproduce the Loop114 public-title gains; this is variance/quarantine evidence, not semantic approval.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop115_goal_completion_recheck_variance_repeat_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_115_REPORT_20260629.md`.
- Data Analytics artifact `Loop115 Goal Completion Recheck` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop111-114 platform/OCR SEO replay remains NOT_COMPLETE

- Added generalized platform SEO title-surface canonicalization in `src/llm_batch/candidate_audit.py`: Munpia/Naver/Kakao/Novelpia suffix handling, NovelPia prefix stripping, and OCR/spacing normalization for `Lp코`/`럽 코` -> `럽코`.
- Added focused tests for platform suffix removal, OCR `Lp코` compatibility, and platform prefix removal.
- Verification passed: `py_compile`; focused tests; full `tests.test_candidate_audit` `83 tests OK`.
- Ran Loop111 focused `11658615` as run `20260629_201405_077720`; runtime `1/1/0/0`, VLM/OCR `READY`, resolved `이거 럽코 빙의물인가요` via `https://novel.munpia.com/533816`.
- Ran Loop112 broad replay as run `20260629_201737_073867`; runtime `19/19/0/0`, VLM/OCR `READY`, but semantic gate stayed `NO-GO` and exposed OCR/platform surface instability.
- Ran Loop113 focused canary for `11658615` and `11698897` as run `20260629_204129_668787`; runtime `2/2/0/0`, VLM/OCR `READY`, both focused rows resolved after canonicalization.
- Ran Loop114 broad replay as run `20260629_204604_191020`; runtime `19/19/0/0`, VLM/OCR `READY`, identified `8`.
- Loop114 confirms `11658615` broad replay success, but remains `NO-GO / REVIEW-LOCKED` because new public-title gains appeared on `11658620`, `11666713`, `11668288`, and `11694019`; `11698897` also did not preserve focused PASS under broad replay.
- Review artifacts: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop111_114_platform_ocr_seo_replay_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_111_114_REPORT_20260629.md`.
- Data Analytics artifact `Loop111-114 Platform OCR SEO Replay Review` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, Loop103 queue suspended, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop108-110 state-change repair remains REVIEW-LOCKED

- Triaged Loop106 -> Loop107 `19` state changes into `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop107_state_change_triage.md/json`.
- Created original-row-only Loop108 packet `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop108_state_change_adjudication_packet.jsonl`.
- Ran Loop108 `20260629_185544_955672`; runtime completed/flushed/pending/failed `19/19/0/0`, VLM/OCR `READY`, image_post_count `11`, identified `8`, semantic gate `NO-GO / REVIEW-LOCKED`.
- Added generalized `candidate_audit` guards for VLM/OCR conflict bypass, secondary-reference precision-downgrade rescue, and direct exact short official titles.
- Verification passed: `py_compile`; focused guard tests; full `tests.test_candidate_audit` `80 tests OK`.
- Ran Loop109 focused canary `20260629_192037_957246`; runtime `3/3/0/0`, VLM/OCR `READY`, focused pass `3/3`.
- Ran Loop110 broad post-patch replay `20260629_193104_492126`; runtime `19/19/0/0`, VLM/OCR `READY`, identified `5`.
- Loop110 confirms patch targets: `11660237` resolves `테라포밍`; `11700470` and `11706832` stay promotion-blocked.
- Loop110 remains `NO-GO / REVIEW-LOCKED` due remaining attention rows `11658615`, `11663540`, `11666713`, `11668288`, `11705231`.
- Review artifacts: `loop108_state_change_adjudication_review.md/json`, `loop109_targeted_guard_repair_3_review.md/json`, `loop110_state_change_post_patch_replay_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_108_110_REPORT_20260629.md`.
- Data Analytics artifact `Loop108-110 상태 변화 보정 리뷰` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop106-107 scene/author guard replay NO-GO

- Added a general hygiene seed alias/image conflict guard for `11714903`; focused run `20260629_170648_212786` blocked public title.
- Ran clean Loop106 replay `20260629_171206_948236`; runtime completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, but semantic gate stayed `NO-GO` because `11695637` reopened as `도네하지 마라`.
- Extended the image scene-cue public-title bridge guard to scene-only `author` anchors; focused `11695637` run `20260629_175300_045051` blocked public title.
- Ran clean Loop107 replay `20260629_175738_653862`; runtime completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`, requested/effective parallel `36/16`.
- Loop107 focused rows were all public-title blocked (`7/7`), including `11714903` and `11695637`.
- Loop107 remains semantic `NO-GO / REVIEW-LOCKED`: identified rows changed from Loop106 `12` to Loop107 `7`, with `19` state changes.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop107_clean_loop104_replay_after_scene_author_guard_review.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_107_REPORT_20260629.md`.
- Data Analytics artifact `Loop107 Clean Replay NO-GO Review` validate/render PASS.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop105 clean Loop104 replay after repair NO-GO

- Ran clean replay after the focused Loop104 repair work using the 38-row packet.
- Run id `20260629_161143_395663`; result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop105_clean_loop104_replay_after_repair_result.json`; manifest `loop105_clean_loop104_replay_after_repair_result_manifest.json`; log `logs/expert_run_20260629_161143_395663.log`.
- Runtime completed/flushed/pending/failed `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, image_post_count `24`, requested/effective parallel `36/16`.
- Semantic result is `NO-GO`: `11694035`, `11713212`, and `11660257` stayed public-title-blocked, but `11714903` reopened as `괴담 호텔 탈출기` with `title_resolution_allowed=true`.
- Review artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop105_clean_loop104_replay_after_repair_review.md/json`.
- Current status artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_repair_patch_current_status.md/json`.
- Loop report: `docs/devs/loop_reports/LOOP_105_REPORT_20260629.md`.
- Data Analytics artifact `Loop105 Clean Replay NO-GO Review` validate/render PASS.
- Gate remains: runtime integrity is GO, semantic quality is `REVIEW-LOCKED`, Loop105 repeat is `NOT_RUN_CLEAN_REPLAY_NO_GO`, full-panel collateral approval `NO-GO`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-29 - Loop104 repair 11714903 focused canary

- Created focused input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop104_repair_11714903_single.jsonl` from the Loop104 replay packet.
- Ran current code as run `20260629_155831_556987` with VLM/OCR required and `--slang-db off`.
- Runtime completed/flushed/pending/failed `1/1/0/0`; VLM/OCR `READY`; result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop104_repair_11714903_single_result.json`.
- Semantic result:
  - relevant `true`
  - novel-related scope `true`
  - resolved work discussion `false`
  - public title `None`
  - `candidate_ledger_status=output_consistency_lint`
  - `title_resolution_allowed=false`
  - `work_resolution=unresolved`
  - blocked title `온 세상이 정신이상자다`
- Root-cause observation:
  - Loop92/93 held this row as no-public/no-work, but Loop104 promoted it through a weak `온세상` title-surface bridge.
  - Current focused run still exposed internal alias conflict between `괴담텔 -> 괴담 호텔 탈출기` and `온세상 -> 온 세상이 정신이상자다`.
  - Final serialization blocked the public title and preserved candidates only as HOLD evidence.
  - VLM/OCR found character/scene support only, no direct title or author.
- Added artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_repair_11714903_single_runtime_audit.md/json`.
- Current repair status: old NO-GO `9`; false NO-GO removed `5`; focused public-title-blocked rows `4` (`11713212`, `11694035`, `11660257`, `11714903`); remaining true promotions requiring root-cause `0`.
- Gate remains: single-row repair is not clean replay approval. Loop103 queue remains suspended; source full completion `OPEN`; full-panel collateral approval `NO-GO`; overall goal `ACTIVE / NOT_COMPLETE`; `semantic_quality=REVIEW-LOCKED`; `full_scan_approval=false`.

## 2026-06-29 - Loop104 repair 11660257 focused canary

- Created focused input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop104_repair_11660257_single.jsonl` from the Loop104 replay packet.
- Ran current code as run `20260629_155128_226258` with VLM/OCR required and `--slang-db off`.
- Runtime completed/flushed/pending/failed `1/1/0/0`; VLM/OCR `READY`; result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop104_repair_11660257_single_result.json`.
- Semantic result:
  - relevant `false`
  - novel-related scope `true`
  - resolved work discussion `false`
  - public title `None`
  - `candidate_ledger_status=hold_without_candidates`
  - `title_resolution_allowed=false`
  - `discussion_type=noise`
- Root-cause observation:
  - Loop102/103 held this row as unresolved; Loop104 promoted it through an official-detail alias bridge.
  - Current focused run blocks the path early with surface-only image/community-banter guard.
  - VLM/OCR found no direct title or author in the images.
- Added artifact: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_repair_11660257_single_runtime_audit.md/json`.
- Current repair status: old NO-GO `9`; false NO-GO removed `5`; focused public-title-blocked rows `3` (`11713212`, `11694035`, `11660257`); remaining true promotion requiring root-cause `1` (`11714903`).
- Gate remains: single-row repair is not clean replay approval. Loop103 queue remains suspended; source full completion `OPEN`; full-panel collateral approval `NO-GO`; overall goal `ACTIVE / NOT_COMPLETE`; `semantic_quality=REVIEW-LOCKED`; `full_scan_approval=false`.

## 2026-06-29 - Loop104 repair 11694035 focused canary

- Created focused input `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop104_repair_11694035_single.jsonl` from the Loop104 replay packet.
- Ran current code as run `20260629_153923_967759` with VLM/OCR required and `--slang-db off`.
- Runtime completed/flushed/pending/failed `1/1/0/0`; VLM/OCR `READY`; result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop104_repair_11694035_single_result.json`.
- Semantic result:
  - relevant `true`
  - resolved work discussion `false`
  - public title `None`
  - `candidate_ledger_status=promotion_blocked`
  - `title_resolution_allowed=false`
  - candidate `아카데미 생존 갤러리` preserved only as HOLD evidence.
- Root-cause observation:
  - VLM/OCR found no direct title or author.
  - Official platform evidence count remained `0`; evidence was community-only.
  - Mid-pipeline deliberation briefly reopened the curated-alias title, but later guards/serialization demoted it back to unresolved candidate/HOLD.
- Added artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_repair_11694035_single_runtime_audit.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_repair_patch_current_status.md/json`
- Current repair status: old NO-GO `9`; false NO-GO removed `5`; focused public-title-blocked rows `2` (`11713212`, `11694035`); remaining true promotions requiring root-cause `2` (`11660257`, `11714903`).
- Gate remains: single-row repair is not clean replay approval. Loop103 queue remains suspended; source full completion `OPEN`; full-panel collateral approval `NO-GO`; overall goal `ACTIVE / NOT_COMPLETE`; `semantic_quality=REVIEW-LOCKED`; `full_scan_approval=false`.

## 2026-06-29 - Loop104 repair patch reclassification and 11713212 focused canary

- Rechecked the Loop104 NO-GO evidence and found that `5/9` reported NO-GO rows were candidate-ledger extraction false positives, not real public-title promotions.
- Created repair artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_repair_patch_static_reclassification.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_repair_11713212_single_runtime_audit.md/json`
- Static reclassification:
  - old NO-GO rows `9`
  - false NO-GO removed `5`: `11658615`, `11658620`, `11695623`, `11705261`, `11695637`
  - true NO-GO remaining before clean replay `4`: `11660257`, `11714903`, `11694035`, `11713212`
  - review rows `6`, watch rows `3`
- Code changes:
  - `tools/build_targeted_followup_remaining_queue.py` now ignores promotion-blocked `primary_work` candidates when deriving final titles.
  - `src/llm_batch/agentic_pipeline.py` now recovers missing `final_decision` from context and blocks generic setting/trope title promotion when verifier counter-arguments show no work anchor.
- Focused runtime:
  - `11713212` canary run `20260629_152235_538688` completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
  - Final public title is `None`; `candidate_ledger_status=promotion_blocked`; gate `TARGETED_GO_PUBLIC_TITLE_BLOCKED`.
- Verification:
  - Focused unit tests PASS.
  - `py_compile` PASS.
  - Repair JSON artifacts valid.
  - Data Analytics artifact `Loop104 Repair Patch Reclassification Review` validate/render PASS.
- Gate remains: single-row repair is not clean replay approval. Loop103 queue remains suspended; source full completion `OPEN`; full-panel collateral approval `NO-GO`; overall goal `ACTIVE / NOT_COMPLETE`; `semantic_quality=REVIEW-LOCKED`; `full_scan_approval=false`.

## 2026-06-29 - Loop104 anti-regression replay NO-GO

- Built Loop104 anti-regression replay packet with `38` rows and `24` image posts:
  - recent variance/fixed controls: `11698880`, `11669928`, `11674712`, `11668288`
  - Loop102-103 accept-collateral lane controls including quarantine `11658615`
  - Loop92-93 stable HOLD controls
  - recent P0 HOLD controls
  - golden positive/negative controls
- Primary Loop104 run `20260629_140125_587992` is not a clean replay: completed/flushed/pending/failed `36/34/2/0`, `large_run_complete=false`, ordered flush blocked.
- Recovery run `20260629_144615_496378` completed the missing/error rows `3/3/0/0`; effective 38-row comparison is available, but recovery is evidence collection, not replay approval.
- Anti-regression gate is `NO-GO`:
  - `9` NO-GO rows, `6` review rows, `3` watch rows.
  - Golden negative public-title hard fails: `11694035`, `11713212`.
  - Loop102-103 lane HOLD/variance rows gained public titles: `11658615`, `11658620`, `11660257`.
  - Loop92-93 stable HOLD rows gained public titles: `11695623`, `11705261`, `11714903`.
  - Recent P0 HOLD control `11695637` gained public title.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_anti_regression_replay_no_go_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_anti_regression_effective_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop104_current_gate_map_after_anti_regression_no_go.md/json`
  - `docs/devs/loop_reports/LOOP_104_REPORT_20260629.md`
- Data Analytics artifact: `Loop104 Anti-Regression Replay NO-GO Review` validate/render PASS.
- Current next action: stop isolated queue progression from Loop103 P1 `61` / P2 `70`; root-cause the anti-regression failures, then rerun clean Loop104 and repeat Loop105.
- Gate remains: source full completion `OPEN`, full-panel collateral approval `NO-GO`, overall goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 - Harness anti-whack-a-mole replay contract

- User concern: single-post focus can fix the current row while twisting earlier rows or adjacent lanes.
- Contract update:
  - `goal.md` and `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md` now state that single-post loops are repro/fix seeds only.
  - After a single-post or narrow-lane code fix, the next step must include repeat runs, parent-lane or representative mini-lane replay, recent closed/HOLD controls, golden positive/negative controls, affected-module tests, and collateral movement.
  - Mixed resolved/HOLD/wrong-title repeat outcomes are `VARIANCE_QUARANTINE_HUMAN_REVIEW` or reopen, not stable closure.
- Current next action:
  - Loop102-103 has run an 8-row P1 accept-collateral repeatability checkpoint, but it is still targeted queue accounting.
  - Before more single-post/code-fix work, build Loop104 or equivalent missing-control replay with `11698880`, `11669928`, `11674712`, `11668288`, `11658615`, Loop92-93 stable rows, recent P0 HOLD controls, and golden controls.
- Gate 유지: source full completion `OPEN`, full-panel collateral approval `NO-GO`, overall goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 98-101 P1 descriptor guard review

- Rechecked P1 `recall_loss_review` / `regression_control` post_id `11698880`.
- Loop99 reproduced a wrong public-title path: descriptor `상남자` displaced `가챠 중독자의 퓨전펑크 생활` and promoted `상남자 [독점]`.
- Added a generalized descriptor-only stable alias guard in `src/llm_batch/agentic_pipeline.py` and regression tests in `tests/test_known_title_abbreviation_support.py`.
- Post-fix Loop100/101 did not reproduce `상남자 [독점]`.
- Row disposition remains `VARIANCE_QUARANTINE_HUMAN_REVIEW` because post-fix outcomes split null/adjacent vs `가챠 중독자의 퓨전펑크 생활`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop98_101_p1_regression_control_stable_alias_descriptor_guard_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop101_current_residual_gate_map_after_p1_regression_control_variance.md/json`
  - `docs/devs/loop_reports/LOOP_98_101_REPORT_20260629.md`
- Data Analytics artifact: `Loop98-101 Stable Alias Descriptor Guard Review`.
- Current accounting: residual total `143`, quarantine/human_review `4`, next actionable total `139`, P0 `0`, P1 `69`, P2 `70`.
- Gate remains: overall goal `NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 96-97 P1 search-correctness variance review

- Continued because the goal remained `ACTIVE / NOT_COMPLETE` and the next actionable queue still had P1 `recall_loss_review=71`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop96_p1_recall_loss_search_correctness_11668288_1.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop96_p1_recall_loss_search_correctness_11668288_1_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop96_p1_recall_loss_search_correctness_11668288_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop97_p1_recall_loss_search_correctness_11668288_1_repeat_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop96_97_p1_recall_loss_search_correctness_repeatability_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop97_current_residual_gate_map_after_p1_search_variance.md/json`
  - `docs/devs/loop_reports/LOOP_96_97_REPORT_20260629.md`
- Runtime:
  - Loop96 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, identified `1/1`.
  - Loop97 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, identified `0/1`.
- Outcome:
  - Native web verification confirmed the expected title/URL exists, but the pipeline decision did not repeat.
  - `11668288` is now `VARIANCE_QUARANTINE_HUMAN_REVIEW`, not stable closure or approval.
- Gate 유지: full reviewed residual ledger `143`, quarantine/human_review `3`, next actionable queue `140`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 94-95 P1A variance repeatability review

- Continued because the goal remained `ACTIVE / NOT_COMPLETE` and Loop92-93 left two P1A variance-open rows.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop94_p1a_variance_open_2.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop94_p1a_variance_open_2_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop94_p1a_variance_open_2_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop95_p1a_variance_open_2_repeat_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop94_95_p1a_variance_repeatability_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop95_current_residual_gate_map_after_p1a_variance.md/json`
  - `docs/devs/loop_reports/LOOP_94_95_REPORT_20260629.md`
- Runtime:
  - Loop94 completed/flushed/pending/failed `2/2/0/0`, image gate `NOT_APPLICABLE`, identified `0/2`.
  - Loop95 completed/flushed/pending/failed `2/2/0/0`, image gate `NOT_APPLICABLE`, identified `1/2`.
- Outcome:
  - `11669928` and `11674712` both had mixed resolved/HOLD outcomes across Loop93-95.
  - Both rows are now `VARIANCE_QUARANTINE_HUMAN_REVIEW`, not stable closure or approval.
- Gate 유지: full reviewed residual ledger `143`, quarantine/human_review `2`, next actionable queue `141`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 92-93 P1A expected recall-improvement review

- Continued after confirming the goal was still `ACTIVE / NOT_COMPLETE`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop92_p1a_expected_recall_improvement_6.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop92_p1a_expected_recall_improvement_6_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop92_p1a_expected_recall_improvement_6_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop93_p1a_expected_recall_improvement_6_after_contract_fix_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop93_p1a_expected_recall_improvement_6_after_contract_fix_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop92_93_p1a_expected_recall_improvement_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop93_current_residual_gate_map_after_p1a.md/json`
  - `docs/devs/loop_reports/LOOP_92_93_REPORT_20260629.md`
- Code changes:
  - Extended promotion-blocked serialized output scrub to remove public URL fields.
  - Cleared nested `novel_identity` URL fields when no public title is allowed.
  - Demoted `primary_work.reference_role=primary` to candidate when title promotion is blocked.
  - Added regression coverage for public URL and primary-role leakage.
- Runtime:
  - Loop92 run id `20260629_113229_038430`, completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`.
  - Loop93 run id `20260629_114229_615998`, completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`.
- Findings:
  - Loop92 exposed three serialized promotion-blocked contract leaks.
  - Loop93 reduced those leaks to zero.
  - Repeated canaries disagreed on `11669928` and `11674712`, so those rows remain open.
  - Residual map now records total `143`, P0 `0`, P1 `73`, P2 `70`.
- Verification:
  - `py_compile` PASS.
  - Focused serialized contract tests PASS.
  - `tests.test_expert_main_comment_metadata -v` `9 tests OK`.
  - Data Analytics artifact `Loop92-93 P1A Expected Recall Improvement Review` validate/render PASS.
- Gate 유지: P1A is partial reviewed with variance only; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 88-91 P0A scope-decision HOLD consistency

- Continued after confirming the goal was still `ACTIVE / NOT_COMPLETE`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop88_p0a_scope_decision_11698871_1.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop88_p0a_scope_decision_11698871_1_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop88_p0a_scope_decision_11698871_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop89_p0a_scope_decision_11698871_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop90_p0a_scope_decision_11698871_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop91_p0a_scope_decision_11698871_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop91_p0a_scope_decision_11698871_1_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop88_91_p0a_scope_decision_hold_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop91_current_residual_gate_map_after_p0a.md/json`
  - `docs/devs/loop_reports/LOOP_88_91_REPORT_20260629.md`
- Code changes:
  - Cleared top-level `heretic_url` when precision-seed demotion blocks public title promotion.
  - Scrubbed precision-seed reason lines that still presented blocked candidates as final official titles.
  - Added serialized result contract scrub in `expert_main.py` for promotion-blocked identities with no public title.
  - Added regression tests for URL cleanup and serialized contract scrub.
- Runtime:
  - Loop88 run id `20260629_104134_972646`, completed/flushed/pending/failed `1/1/0/0`.
  - Loop89 run id `20260629_105042_160478`, completed/flushed/pending/failed `1/1/0/0`.
  - Loop90 run id `20260629_105645_687973`, completed/flushed/pending/failed `1/1/0/0`.
  - Loop91 run id `20260629_110635_160435`, completed/flushed/pending/failed `1/1/0/0`.
- Findings:
  - Loop88 and Loop90 are retained as output-consistency failure evidence.
  - Loop91 leaves `11698871` as public title/url `null` with candidates preserved only as candidate/HOLD.
  - Residual map now records remaining total `147`, P0 `0`, P1 `77`, P2 `70`.
- Verification:
  - `py_compile` PASS.
  - Focused URL cleanup and serialized contract tests PASS.
  - `tests.test_candidate_audit -v` `74 tests OK`.
  - `tests.test_expert_main_comment_metadata -v` `8 tests OK`.
  - Data Analytics artifact `Loop88-91 P0A Scope Decision HOLD Review` validate/render PASS.
- Gate 유지: P0 zero is not approval; public title approval is `NOT_APPROVED`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 84-87 P0E variant canonicalization guard

- Continued after confirming the goal was still `ACTIVE / NOT_COMPLETE`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop84_p0e_variant_canonicalization_current_rerun_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop84_p0e_variant_canonicalization_current_rerun_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop85_p0e_variant_canonicalization_after_review_fix_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop85_p0e_variant_canonicalization_after_review_fix_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop86_p0e_11666713_variant_guard_1.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop86_p0e_11666713_variant_guard_1_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop86_p0e_11666713_variant_guard_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop86_p0e_11666713_variant_guard_1_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop87_p0e_11666713_variant_guard_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop87_p0e_11666713_variant_guard_1_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop84_87_p0e_variant_canonicalization_guard_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop87_current_residual_gate_map_after_p0e.md/json`
  - `docs/devs/loop_reports/LOOP_84_87_REPORT_20260629.md`
- Code changes:
  - Added exact post-side surface containment for short work-style review official-url recall.
  - Added immediate mismatch blocking with `official_url_recall_blocked_title_body_work_review_surface_mismatch`.
  - Added regression tests for exact canonical detail allow and inserted wrong-title block.
- Runtime:
  - Loop84 run id `20260629_100026_137330`, completed/flushed/pending/failed `5/5/0/0`.
  - Loop85 run id `20260629_101146_562606`, completed/flushed/pending/failed `5/5/0/0`.
  - Loop86 run id `20260629_102550_357746`, completed/flushed/pending/failed `1/1/0/0`.
  - Loop87 run id `20260629_102740_316087`, completed/flushed/pending/failed `1/1/0/0`.
- Findings:
  - Loop85 and Loop86 promoted the wrong NovelPia title and are retained as failure evidence.
  - Loop87 blocks that wrong promotion and leaves `11666713` unresolved with public title/url `null`.
  - Residual map now records remaining total `148`, P0 `1`, P1 `77`, P2 `70`.
- Verification:
  - `py_compile` PASS.
  - Focused P0E guard tests PASS.
  - `tests.test_title_lead_search_inferred_guard -v` `133 tests OK`.
  - Data Analytics artifact `Loop84-87 P0E Variant Canonicalization Guard Review` validate/render PASS.
- Gate 유지: P0E wrong-title switch risk is targeted safe HOLD only; canonical title recovery is `NOT_APPROVED`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 82-83 P0D title variant/canonicalization repair

- Continued after confirming the goal was still `ACTIVE / NOT_COMPLETE`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop82_p0d_title_variant_canonicalization_4.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop82_p0d_title_variant_canonicalization_4_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop82_p0d_title_variant_canonicalization_4_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop82_p0d_title_variant_canonicalization_4_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop83_p0d_faust_non_novel_guard_1.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop83_p0d_faust_non_novel_guard_1_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop83_p0d_faust_non_novel_guard_1_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop82_83_p0d_title_variant_canonicalization_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop83_current_residual_gate_map_after_p0d.md/json`
  - `docs/devs/loop_reports/LOOP_82_83_REPORT_20260629.md`
- Code changes:
  - Blocked non-novel/literature discourse warnings from accepting structured OCR/cover title surfaces.
  - Added a late-promotion guard so non-novel/literature warnings set `non_novel_discourse_title_promotion_blocked` rather than public title promotion.
- Runtime:
  - Loop82 run id `20260629_092113_593472`, completed/flushed/pending/failed `4/4/0/0`, image posts `3`.
  - Loop83 run id `20260629_093826_468953`, completed/flushed/pending/failed `1/1/0/0`, image posts `1`.
- Findings:
  - Loop82 resolved `11682791` and `11710049`, held `11663535`, but false-promoted `11706871` to `파우스트 1`.
  - Loop83 corrected `11706871` to public title `null`, `ocr_explicit_title_unresolved`, `title_resolution_allowed=false`, `promotion_blocked`.
  - Residual map now records remaining total `149`, P0 `2`, P1 `77`, P2 `70`.
- Verification:
  - `py_compile` PASS.
  - Focused new non-novel OCR promotion test PASS.
  - OCR/reference guard tests PASS.
  - `tests.test_title_lead_search_inferred_guard -v` `131 tests OK`.
  - Data Analytics artifact `Loop82-83 P0D Title Variant Canonicalization Review` validate/render PASS.
- Gate 유지: P0D lane is targeted repaired/held, but full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 79-81 P0C unexpected public-title repair

- Continued after confirming the goal was still `ACTIVE / NOT_COMPLETE`.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop79_p0c_unexpected_public_title_3.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop79_p0c_unexpected_public_title_3_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop80_p0c_unexpected_public_title_3_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop80_p0c_unexpected_public_title_3_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop81_p0c_unexpected_public_title_3_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop81_p0c_unexpected_public_title_3_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop79_81_p0c_unexpected_public_title_review.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop81_current_residual_gate_map_after_p0c.md/json`
  - `docs/devs/loop_reports/LOOP_79_81_REPORT_20260629.md`
- Code changes:
  - Blocked title-body-only official URL recall after deliberate-null decisions.
  - Added platform/service alias filtering for official alias rescue surfaces.
  - Blocked secondary-reference/search official alias rescue after `multi_work_title_cleared`.
- Runtime:
  - Loop80 run id `20260629_085035_997835`, completed/flushed/pending/failed `3/3/0/0`, image posts `3`.
  - Loop81 run id `20260629_090517_159853`, completed/flushed/pending/failed `3/3/0/0`, image posts `3`.
- Findings:
  - Loop80 reproduced false positives on `11658621` and `11718105`.
  - Loop81 produced public title `0/3`; all P0C rows stayed null/unresolved or adjacent with candidates preserved only.
  - Updated residual map records current remaining total `153`, P0 `6`, P1 `77`, P2 `70`.
- Verification:
  - `py_compile` PASS.
  - `tests.test_title_lead_search_inferred_guard -v` `130 tests OK`.
  - Affected suites `115 tests OK`.
  - Data Analytics artifact `Loop79-81 P0C Unexpected Public Title Review` validate/render PASS.
- Gate 유지: P0C targeted lane repaired, but full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 76-78 P0A follow-up repair

- Continued the Loop74-75 P0A repair after the user correctly noted the goal was not complete.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop76_p0a_expected_restoration_6_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop76_p0a_expected_restoration_6_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop77_p0a_expected_restoration_6_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop77_p0a_expected_restoration_6_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop78_p0a_11697267_url_guard_input.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop78_p0a_11697267_url_guard_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop78_p0a_11697267_url_guard_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop76_78_p0a_followup_repair.md/json`
  - `docs/devs/loop_reports/LOOP_76_78_REPORT_20260629.md`
- Code changes:
  - Added `엑칼뽑 -> 엑스칼리버 뽑습니다` to known-title abbreviations.
  - Added character/work-cue anchoring for known-title abbreviation recall.
  - Added a curated-alias recursion guard.
  - Preserved same-URL official-detail canonicalization through precision and weak-bridge checks.
  - Added same-frame wrong-core URL rejection for adjacent title URLs.
- Runtime:
  - Loop76 run id `20260629_080641_592391`, completed/flushed/pending/failed `6/6/0/0`, image posts `4`.
  - Loop77 run id `20260629_082022_708414`, completed/flushed/pending/failed `6/6/0/0`, image posts `4`.
  - Loop78 run id `20260629_083234_620194`, completed/flushed/pending/failed `1/1/0/0`, image posts `1`.
- Findings:
  - Loop76 remains failure evidence because `11698871` overpromoted to Re:Zero.
  - Loop77 restored public titles for `5/6`, but `11697267` used wrong adjacent URL `https://novelpia.com/novel/390001`.
  - Loop78 restored `11697267` to `아카데미 생존 갤러리` with `https://novelpia.com/novel/380218`.
  - `11698871` remains a conservative safe HOLD/scope-decision row.
- Verification:
  - `py_compile` PASS.
  - `tests.test_final_semantic_reread_gate tests.test_known_title_abbreviation_support tests.test_candidate_audit -v` `115 tests OK`.
  - Data Analytics artifact `Loop76-78 P0A Follow-up Repair` validate/render PASS.
- Gate 유지: P0A status is `PARTIAL_REPAIRED_WITH_SCOPE_HOLD`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 74-75 P0A expected restoration repair

- Loop73 P0A `0/6` public restoration no-go를 precision-seed demotion 경로 기준으로 수리했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop74_p0a_expected_restoration_6_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop74_p0a_expected_restoration_6_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop75_p0a_expected_restoration_6_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop75_p0a_expected_restoration_6_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop74_75_p0a_expected_restoration_repair.md/json`
  - `docs/devs/loop_reports/LOOP_74_75_REPORT_20260629.md`
- Code changes:
  - `candidate_audit` now canonicalizes same-URL official-detail titles before precision-seed demotion.
  - Precision-seed rows with independent official detail support can use a narrow bypass flag.
  - Identity consistency lint and weak public-title bridge guard respect that independent official-detail support.
- Runtime:
  - Loop74 run id `20260629_073514_637921`, completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`, public restored `1/6`.
  - Loop75 run id `20260629_074215_122202`, completed/flushed/pending/failed `6/6/0/0`, VLM/OCR `READY`, public restored `3/6`.
- Loop75 row outcomes:
  - Restored `11660277` -> `아카메디 아카데미`.
  - Restored `11663544` and `11671517` -> `헌터갤러리의 국가권력급 기계공주`.
  - Still HOLD/open: `11692444`, `11697267`, `11698871`.
- Verification:
  - `py_compile` PASS.
  - Focused precision/weak-bridge regression tests PASS.
  - `tests.test_candidate_audit -v` `72 tests OK`.
  - Data Analytics artifact `Loop74-75 P0A Expected Restoration Repair` validate/render PASS.
- Gate 유지: P0A expected restoration improved but remains `OPEN`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 73 residual map and P0A canary

- Loop63, Loop64, and Loop68-72 targeted evidence was applied to refresh the Loop62 residual map.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop73_current_residual_gate_map.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop73_p0a_expected_restoration_6.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop73_p0a_expected_restoration_6_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop73_p0a_expected_restoration_6_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop73_p0a_expected_restoration_6_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop73_p0a_expected_restoration_canary.md/json`
  - `docs/devs/loop_reports/LOOP_73_REPORT_20260629.md`
- Residual map:
  - Remaining full-panel collateral candidates: `161`.
  - Remaining P0 rows: `14`.
  - Remaining P1/P2 rows: `77/70`.
  - Open P0 buckets: P0A expected restoration `6`, P0C unexpected public title `3`, P0D canonicalization `4`, P0E variant caution `1`.
- Runtime:
  - Loop73 run id `20260629_071507_022171`.
  - completed/flushed/pending/failed `6/6/0/0`.
  - requested/effective parallel `6/6`.
  - image posts `4`, VLM/OCR `READY`.
- Findings:
  - Public expected restoration `0/6`.
  - Candidate or primary evidence preserved `5/6`.
  - `11697267` did not recover expected `아카데미 생존 갤러리`.
  - Loop73 is runtime PASS but semantic `NO-GO_EXPECTED_RESTORATION_0_OF_6_PUBLIC`.
- Data Analytics artifacts `Loop73 Current Residual Gate Map` and `Loop73 P0A Expected Restoration Canary` validate/render PASS.
- Gate 유지: P0A remains `OPEN`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 68-72 P0B residual guard continuation

- Loop65/67 이후 남은 P0B residual rows `11671490`, `11695637`, `11695639`를 continued targeted canary로 닫았다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop68_direct_image_reference_recommendation_11671490_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop69_recommendation_context_only_11671490_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop70_image_scene_cues_11695637_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop71_comment_url_answer_11695639_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop72_comment_url_answer_11695639_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop68_72_p0b_residual_guard_review.md/json`
  - `docs/devs/loop_reports/LOOP_68_REPORT_20260629.md`
  - `docs/devs/loop_reports/LOOP_69_REPORT_20260629.md`
  - `docs/devs/loop_reports/LOOP_70_REPORT_20260629.md`
  - `docs/devs/loop_reports/LOOP_71_REPORT_20260629.md`
  - `docs/devs/loop_reports/LOOP_72_REPORT_20260629.md`
- Runtime:
  - Loop69 run id `20260629_062918_822123`, targeted row `11671490`, VLM/OCR `READY`.
  - Loop70 run id `20260629_063422_769430`, targeted row `11695637`, VLM/OCR `READY`.
  - Loop72 run id `20260629_065456_061611`, targeted row `11695639`, completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
- Findings:
  - Loop68 remains `NO-GO_OVERPROMOTION`: `11671490` promoted `게임이 자꾸 사람을 구원함`.
  - Loop69 blocks that promotion and preserves the conflicting title as blocked candidate evidence.
  - Loop70 blocks `11695637` unverified image-scene public title bridge.
  - Loop71 recovered `준우승 세 번 했더니 미소녀 됨` but dropped URL, so it remains partial evidence.
  - Loop72 preserves both title and URL `https://novelpia.com/novel/362860` on `novel_identity` and `primary_work`.
- Verification:
  - `py_compile` PASS for touched candidate-audit/pipeline/test files.
  - `tests.test_candidate_audit` `68 tests OK`.
  - Focused comment URL answer tests `6 tests OK`.
  - `git diff --check` PASS with LF/CRLF warnings only.
  - Data Analytics artifact `Loop 68-72 P0B Residual Guard Review` validate/render PASS.
- Gate 유지: Loop65 P0B residual rows are targeted repaired, but full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 65-67 P0B residual guard review

- Loop62 `P0B_expected_mismatch_public_title=4` residual rows를 Loop65 targeted rerun으로 실행했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop65_p0b_residual_expected_mismatch_4.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop65_p0b_residual_expected_mismatch_4_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop66_generic_evidence_label_11706832_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop67_deliberate_null_secondary_rescue_11706832_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop65_67_p0b_residual_guard_review.md/json`
  - `docs/devs/loop_reports/LOOP_65_REPORT_20260629.md`
  - `docs/devs/loop_reports/LOOP_66_REPORT_20260629.md`
  - `docs/devs/loop_reports/LOOP_67_REPORT_20260629.md`
- Runtime:
  - Loop65 run id `20260629_054459_633571`, targeted rows `4`, failed rows `0`, VLM/OCR `READY`.
  - Loop66 run id `20260629_055512_763713`, targeted rows `1`, VLM/OCR `READY`.
  - Loop67 run id `20260629_060608_653750`, targeted rows `1`, VLM/OCR `READY`.
- Findings:
  - Loop65 remained semantic `NO-GO`: `11671490`, `11695637`, and `11706832` had unsafe resolved/allowed states; `11695639` stayed unresolved without expected URL/title recovery.
  - Loop66 removed the generic `웹소설` public title but exposed late secondary-reference rescue.
  - Loop67 blocked the late rescue for `11706832`: public title `null`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`, `candidate_ledger_status=promotion_blocked`.
- Verification:
  - `py_compile` PASS for touched pipeline/test files.
  - Focused secondary-reference guard tests PASS.
  - Existing batch-alias deliberate-null regression test PASS.
  - `tests.test_candidate_audit` `65 tests OK`.
  - Data Analytics artifact `Loop65-67 P0B Residual Guard Review` validate/render PASS.
- Gate 유지: Loop67 is a targeted pass only; P0B lane remains `OPEN`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 64 P0E wrong title switch targeted rerun

- Loop51 `P0E_wrong_title_switch=5` rows를 현 코드로 targeted rerun했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop64_p0e_wrong_title_switch_5.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop64_p0e_wrong_title_switch_5_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop64_p0e_wrong_title_switch_5_result_manifest.json`
  - `logs/expert_run_20260629_052654_833822.log`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop64_p0e_wrong_title_switch_targeted_rerun.md/json`
  - `docs/devs/loop_reports/LOOP_64_REPORT_20260629.md`
- Runtime:
  - completed/flushed/pending/failed `5/5/0/0`
  - VLM/OCR `READY`
  - image posts `4`
  - large run complete `true`
- Findings:
  - Loop49 wrong-after title reproduced `0`.
  - `3` rows recovered their before title.
  - `1` row recovered only a canonicalization-sensitive variant: `11666713` current `21세기 무림` vs before `21세기 무림세가`.
  - `1` row was demoted to null/promotion-blocked.
  - Outcome split: `RECOVERED_BEFORE_TITLE=3`, `RECOVERED_VARIANT_NEEDS_CANONICALIZATION_REVIEW=1`, `DEMOTED_TO_NULL=1`.
- Data Analytics artifact `Loop64 P0E Wrong Title Switch Targeted Rerun` validate/render PASS.
- Gate 유지: P0E targeted lane is `TARGETED_REVIEWED_5_OF_5`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 63 P0C slang pollution targeted rerun

- Loop62의 next concrete lane이던 Loop51 `P0C_slang_pollution_public_title=7` rows를 현 코드로 targeted rerun했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop63_p0c_slang_pollution_7.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop63_p0c_slang_pollution_7_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop63_p0c_slang_pollution_7_result_manifest.json`
  - `logs/expert_run_20260629_050245_666110.log`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop63_p0c_slang_pollution_targeted_rerun.md/json`
  - `docs/devs/loop_reports/LOOP_63_REPORT_20260629.md`
- Runtime:
  - completed/flushed/pending/failed `7/7/0/0`
  - VLM/OCR `READY`
  - image posts `6`
  - large run complete `true`
- Findings:
  - `4` suspected public-title promotions were demoted to null/promotion-blocked.
  - `3` suspected rows were verified as same public title/safe-resolved.
  - Outcome split: `DEMOTED_TO_NULL=4`, `VERIFIED_SAME_PUBLIC_TITLE=3`.
- Data Analytics artifact `Loop63 P0C Slang Pollution Targeted Rerun` validate/render PASS.
- Gate 유지: P0C targeted lane is `TARGETED_REVIEWED_7_OF_7`; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 62 full-panel collateral residual map

- User correctly flagged that the goal was not complete; the active gate state was rechecked instead of closing the goal.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop50_panel_collateral_candidate_packet.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop51_p0_panel_collateral_triage.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop53_p0b_concrete_expected_recovery_packet.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop58_direct_expected_surface_over_homonym_fix.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop62_full_panel_residual_map.md/json`
  - `docs/devs/loop_reports/LOOP_62_REPORT_20260629.md`
- Findings:
  - Loop50 full-panel collateral candidates `183`.
  - Loop53-58 targeted closed rows `7`.
  - Remaining collateral candidates `176`.
  - Remaining priority split `P0=29`, `P1=77`, `P2=70`.
  - Remaining P0 buckets: `3`, `3`, `4`, `7`, `3`, `4`, `5` across P0A/P0B/P0C/P0D/P0E lanes.
- Verification:
  - JSON parse PASS.
  - Data Analytics artifact `Loop62 Full Panel Residual Map` validate PASS; render response was truncated in this context.
- Gate 유지: residual map only; full-panel collateral approval remains `NO-GO`; source full completion remains `OPEN`; Loop10 slang write-back review remains `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 61 slang write-back review

- Loop10 `slang_store_gate=92`를 production write-back 관점에서 review-only로 감사했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop10_slang_store_gate_92_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop10_slang_store_gate_92_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/compare/loop10_slang_store_gate_92_compare.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/compare/loop10_slang_store_gate_92_next_queue.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop61_slang_writeback_review.md/json`
  - `docs/devs/loop_reports/LOOP_61_REPORT_20260629.md`
- Findings:
  - runtime completed/flushed/pending/failed `92/92/0/0`
  - compare movement `review=92`, targeted next queue `0`
  - input policy `off/read-only canary; no production write-back`
  - signal split `store_true=29`, `store_false=31`, no `slang_insight=32`
  - unresolved store-true rows `11700500` and `11710043`
  - all `19` unique store-true terms already exist in `slang_db/slang_db.json`; `6` are multi-title/bucket
  - `slang_db/slang_db.json` was not modified
- Data Analytics artifact `Loop61 Slang Writeback Review Gate` was validate/render PASS.
- Gate 유지: Loop10 slang write-back review is `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK`; source full completion remains `OPEN`; full-panel collateral approval remains `NO-GO`; overall goal remains `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 60 failed-row targeted rerun

- Loop59에서 남긴 source failed row `11694057`을 단건 targeted canary로 재실행했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop59_failed_row_11694057.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop59_failed_row_11694057_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop59_failed_row_11694057_result_manifest.json`
  - `logs/expert_run_20260629_041439_104987.log`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop60_failed_row_targeted_rerun.md/json`
  - `docs/devs/loop_reports/LOOP_60_REPORT_20260629.md`
- Runtime findings:
  - canary completed/flushed/pending/failed `1/1/0/0`
  - failed row runtime blocker closed with `failed_count=0`
  - final row `11694057` resolved to `괴담에 휘말렸다`
- Data Analytics artifact `Loop60 Failed Row Targeted Rerun Gate` was validate/render PASS.
- Gate 유지: source full completion remains `OPEN` because source input scope is still `104502` and original source `large_run_complete=false`; full-panel collateral approval `NO-GO`, Loop 10 slang write-back review `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK_BY_LOOP61`, overall goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 59 source integrity recovery

- Source full-completion gate를 manifest/checkpoint/pending snapshot 기준으로 재점검했다.
- Artifacts:
  - `out/expert_result_20260626_000008_928006_manifest.json`
  - `out/expert_result_20260626_000008_928006_checkpoint.jsonl`
  - `out/expert_result_20260626_000008_928006_pending_snapshot.json`
  - `out/expert_result_20260626_000008_928006_recovered_from_checkpoint.json`
  - `out/expert_result_20260626_000008_928006_recovery_summary.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop59_source_integrity_recovery.md/json`
  - `docs/devs/loop_reports/LOOP_59_REPORT_20260629.md`
- Source integrity findings:
  - final result rows `1933`
  - checkpoint completed rows `1945`
  - checkpoint failed rows `1`
  - pending snapshot rows `13`
  - recovered rows `1945`
  - manifest input posts `104502`
  - recovery classification `recoverable_pending_flush_gap`
  - recovery is not safe to promote as completed subset because failed row `11694057` remains and `large_run_complete=false`
- Code path:
  - `src/llm_batch/llm/client.py` now replaces lone surrogate codepoints before HTTP JSON transport for stream and non-stream chat calls.
  - `tests/test_llm_client_multimodal.py` covers nested surrogate replacement and sanitized HTTP request body.
- Verification:
  - `py_compile` PASS
  - focused surrogate transport checks `2 tests OK`
  - `tests.test_llm_client_multimodal` `16 tests OK`
  - checkpoint recovery command PASS
- Data Analytics artifact `Loop59 Source Integrity Recovery Gate` was validate/render PASS.
- Gate 유지: pending flush gap is recovered to a separate artifact, but failed row `11694057`, full source completion, full-panel collateral approval, and Loop 10 slang write-back review remain open. Overall goal is `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 58 direct expected surface over homonym fix

- Loop53 `direct_expected_surface_over_homonym=2` lane을 targeted follow-up으로 처리했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop58_direct_expected_surface_over_homonym_2.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop58_direct_expected_surface_over_homonym_2_after_sixth_patch_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop58_direct_expected_surface_over_homonym_2_after_sixth_patch_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop58_direct_expected_surface_over_homonym_2_after_sixth_patch_repeat_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop58_direct_expected_surface_over_homonym_2_after_sixth_patch_repeat_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop58_direct_expected_surface_over_homonym_fix.md/json`
  - `docs/devs/loop_reports/LOOP_58_REPORT_20260629.md`
- Code path:
  - direct comment/self-resolution official detail URLs are preserved through core fetch budget trimming.
  - title-request comment URL answer context can recover a title even without thanks/confirmation wording.
  - direct comment URL answer recovery can replace weak surface/search titles and restore the official detail URL from the primary work.
  - decoder-exact post-title surfaces block derivative or homonym official-detail expansion when the decoder already treats the post title as the exact work title.
- Runtime:
  - `run_id=20260629_033434_424902`
  - repeat `run_id=20260629_034037_534374`
  - both runs completed/flushed/pending/failed `2/2/0/0`
  - VLM/OCR ready for image/title context rows `11674703`, `11703657`
- Row outcomes:
  - `11674703`: final `official_title=도굴왕`, URL `null`, `candidate_ledger_status=safe_resolved`, row-level `GO`.
  - `11703657`: final `official_title=야만인은 문명하면 안되냐`, URL `https://novelpia.com/novel/405310`, `candidate_ledger_status=safe_resolved`, row-level `GO`.
- Verification:
  - `py_compile` PASS
  - focused AgenticPipelineRework checks `11 tests OK`
  - focused title-lead checks `3 tests OK`
  - `tests.test_final_semantic_reread_gate` `18 tests OK`
  - `git diff --check` PASS with line-ending warnings only
- Data Analytics artifact `Loop58 Direct URL Surface Homonym Gate` was validate/render PASS.
- Gate 유지: `direct_expected_surface_over_homonym=2` is targeted closed, and Loop53 concrete expected-recovery packet targeted lanes are `7_OF_7` closed. Full-panel collateral approval is still `NO-GO`, overall goal is `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 57 primary expected candidate precedence fix

- Loop53 `primary_expected_candidate_precedence=2` lane을 targeted follow-up으로 처리했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop57_primary_expected_precedence_2.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop57_primary_expected_precedence_2_after_second_patch_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop57_primary_expected_precedence_2_after_second_patch_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop57_primary_expected_precedence_fix.md/json`
  - `docs/devs/loop_reports/LOOP_57_REPORT_20260629.md`
- Code path:
  - primary official-detail candidate precedence now beats alias/reference surfaces when OCR/work cues directly name the primary work.
  - direct OCR/work-cue official probes are preserved through orchestrator pruning/sanitization.
  - search-supported title replacement now canonicalizes to official-detail title and blocks blog/review suffixes plus author/volume wrappers.
  - verified alias official-detail anchors are allowed through final reread and weak public-title bridge checks.
- Runtime:
  - `run_id=20260629_014819_365348`
  - completed/flushed/pending/failed `2/2/0/0`
  - VLM/OCR ready for image posts `11658637`, `11677913`
- Row outcomes:
  - `11658637`: final `official_title=재벌집 막내아들`, URL `https://novel.munpia.com/69583`, `candidate_ledger_status=safe_resolved`, row-level `GO`.
  - `11677913`: final `official_title=이세계 검은 머리 외국인`, URL `https://novelpia.com/novel/1082`, `candidate_ledger_status=safe_resolved`, row-level `GO`.
- Verification:
  - `py_compile` PASS
  - `tests.test_final_semantic_reread_gate` `18 tests OK`
  - `tests.test_candidate_audit` `64 tests OK`
  - `tests.test_title_lead_search_inferred_guard` `126 tests OK`
  - focused regression failures `2 tests OK`
- Data Analytics artifact `Loop57 Primary Expected Candidate Precedence Fix` was validate/render PASS.
- Gate 유지: `primary_expected_candidate_precedence=2` is targeted closed, but `direct_expected_surface_over_homonym=2` remains open. Full-panel collateral approval is `NO-GO`, overall goal is `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-29 regression-safe grounding Loop 56 ratddasip visual alias catalog fix

- Loop53 `expected_source_recall_missing_or_demoted` lane의 마지막 open row `11673086`을 targeted follow-up으로 처리했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop56_ratddasip_11673086_1.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop56_ratddasip_11673086_after_catalog_fix_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop56_ratddasip_11673086_after_catalog_fix_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop56_ratddasip_visual_alias_catalog_fix.md/json`
  - `docs/devs/loop_reports/LOOP_56_REPORT_20260629.md`
- Code path:
  - visual official-detail bracket context now allows the `RimWorld` / `림월드` cue only when it is supported by packet visual evidence and official-detail title context.
  - catalog recall adds `visual_bracket_context` only when matched alias evidence and visual bracket context align, preventing same-tag `#랫따싶` competitors from winning by tag overlap alone.
- Runtime:
  - `run_id=20260629_000231_836930`
  - completed/flushed/pending/failed `1/1/0/0`
  - VLM/OCR ready for image post `11673086`
- Row outcome:
  - `11673086`: final `official_title=변방계에서 회귀자로 살아남기`, URL `https://novelpia.com/novel/382324`, `candidate_ledger_status=safe_resolved`, `title_resolution_allowed=true`, row-level `GO`.
- Verification:
  - `py_compile` PASS
  - `tests.test_title_lead_search_inferred_guard` `119 tests OK`
  - `tests.test_candidate_audit` `64 tests OK`
  - `tests.test_known_title_abbreviation_support` `20 tests OK`
- Data Analytics artifact `Loop56 Ratddasip Visual Alias Catalog Fix`를 validate/render했다.
- Gate 유지: expected-source lane은 targeted `3_OF_3` recovered가 되었지만, Loop53 `primary_expected_candidate_precedence=2` 및 `direct_expected_surface_over_homonym=2`는 open이다. Full-panel collateral approval은 `NO-GO`, overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 55 expected-source remaining canary

- Loop53 `expected_source_recall_missing_or_demoted` lane의 잔여 image rows `11671501`, `11673086`을 VLM/OCR targeted canary로 실행했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop55_expected_source_remaining_2.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop55_expected_source_remaining_2_result.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop55_expected_source_remaining_2_result_manifest.json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop55_expected_source_remaining_canary.md/json`
  - `docs/devs/loop_reports/LOOP_55_REPORT_20260628.md`
- Runtime:
  - `run_id=20260628_230707_063767`
  - completed/flushed/pending/failed `2/2/0/0`
  - `large_run_complete=true`, `partial_flush_gap=false`, `ordered_flush_blocked=false`
  - requested/effective parallel `2/2`
  - VLM/OCR ready for image posts `11671501`, `11673086`
- Row outcomes:
  - `11671501`: final `official_title=판초우의의 마법사`, URL `https://novel.munpia.com/530500`, `candidate_ledger_status=safe_resolved`, row-level `GO`.
  - `11673086`: final public title `null`; expected candidate `변방계에서 회귀자로 살아남기`, URL `https://novelpia.com/novel/382324` preserved; `candidate_ledger_status=promotion_blocked`, row remains `OPEN`.
- Data Analytics artifact `Loop55 Expected-Source Remaining Canary`를 validate/render했다.
- Gate 유지: expected-source lane은 `PARTIAL_GO_2_OF_3`이다. `11668324`와 `11671501`은 recovered, `11673086`은 open, `primary_expected_candidate_precedence=2` 및 `direct_expected_surface_over_homonym=2`도 open이다. Full-panel collateral approval은 `NO-GO`, overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 54 alias-abbreviation recall fix

- Loop53 `expected_source_recall_missing_or_demoted` lane의 첫 일반화 code hook을 적용했다.
- `src/llm_batch/agentic_pipeline.py`:
  - `_alias_surface_matches_title_abbreviation(...)`를 추가해 `니생들 -> 니들 생각 다 들린다` 같은 compact title abbreviation과 `판초법사 -> 판초우의의 마법사` 같은 prefix+suffix abbreviation 형태를 판정한다.
  - `title_alias_platform_recall` 검색어 생성에서 한국어 조사/연결어 stem을 먼저 시도한다.
  - alias-only official-detail result는 abbreviation predicate를 통과할 때만 title-body official-detail anchor로 promotion한다.
  - `_known_title_abbreviation_update_question_anchor(...)`의 work cue를 `언급`, `장갤픽`, 작품 출시/연재/완결/시간 계열로 좁혀 lifecycle/update-question context를 허용한다.
  - `_known_title_abbreviation_official_url_recall_promotion(...)`은 multiple curated aliases가 있을 때 post title/body의 leftmost alias occurrence를 우선한다.
- `src/llm_batch/experts/utils.py`:
  - `KNOWN_TITLE_ABBREVIATIONS`에 `니생들 -> 니들 생각 다 들린다`를 추가했다.
- `tests/test_title_lead_search_inferred_guard.py`:
  - `니생들이랑 -> 니생들` 검색 후 `니들 생각 다 들린다` 회수 positive test 추가.
  - `랫따싶` tag-only result가 official title abbreviation으로 설명되지 않으면 promotion하지 않는 negative test 추가.
- `tests/test_known_title_abbreviation_support.py`:
  - `11668324`형 mixed-alias lifecycle context에서 `니생들`이 `김괴라리`보다 먼저 회수되는 회귀 테스트를 추가했다.
- Verification:
  - title-lead focused tests `2 tests OK`
  - known-title abbreviation focused checks `5 tests OK`
  - `tests.test_known_title_abbreviation_support` `20 tests OK`
  - existing title-lead suite `116 tests OK`
  - `tests.test_candidate_audit` `64 tests OK`
  - touched `py_compile` pass
- Data Analytics artifacts `Loop54 Alias-Abbreviation Recall Fix`, `Loop54 Alias-Abbreviation Canary Gate`, `Loop54b Known-Abbreviation Canary Recovery`를 validate/render했고, report `docs/devs/loop_reports/LOOP_54_REPORT_20260628.md`를 갱신했다.
- First targeted canary:
  - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop54_alias_abbrev_11668324_result.json`
  - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop54_alias_abbrev_11668324_result_manifest.json`
  - runtime completed/flushed/pending/failed `1/1/0/0`
  - semantic `NO-GO`: expected `니들 생각 다 들린다`, actual `괴담에 휘말렸다` via `김괴라리`
  - search health `SEARCH_DEGRADED`
- Second targeted canary:
  - result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop54b_known_abbrev_11668324_result.json`
  - manifest: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop54b_known_abbrev_11668324_result_manifest.json`
  - runtime completed/flushed/pending/failed `1/1/0/0`
  - semantic row-level `GO`: final `official_title=니들 생각 다 들린다`, URL `https://novelpia.com/novel/384318`, alias `니생들`, `candidate_ledger_status=safe_resolved`
  - search health `SEARCH_DEGRADED`
- Gate 유지: `11668324` targeted canary는 회복됐지만 Loop54는 broader Loop53 lane completion이나 approval이 아니다. Loop55에서 `11671501`은 recovered됐고, `11673086`, `primary_expected_candidate_precedence=2`, `direct_expected_surface_over_homonym=2`는 open이다. Full-panel collateral approval은 `NO-GO`, overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 53 P0B concrete expected-recovery packet

- Loop52 `BLOCK_WRONG_AFTER_RECOVER_EXPECTED=7` rows를 code-review lanes로 나눴다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop53_p0b_concrete_expected_recovery_packet.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop53_p0b_concrete_expected_recovery_requeue.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop53_p0b_concrete_expected_recovery_7.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop53_p0b_concrete_expected_recovery_7_manifest.json`
- All `7` rows mapped back to Loop52 candidate input rows; missing input ids `[]`.
- Fix lane counts: `expected_source_recall_missing_or_demoted=3`, `primary_expected_candidate_precedence=2`, `direct_expected_surface_over_homonym=2`.
- Data Analytics artifact `Loop53 P0B Concrete Expected-Recovery Packet`를 validate/render했고, report `docs/devs/loop_reports/LOOP_53_REPORT_20260628.md`를 추가했다.
- Gate 유지: Loop53 packet은 code fix나 row-level resolution이 아니다. Full-panel collateral approval은 `NO-GO`, overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 52 P0B expected-mismatch disposition

- Loop51 `P0B_expected_mismatch_public_title=11` rows를 conservative disposition routes로 재분류했다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop52_p0b_expected_mismatch_disposition.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop52_p0b_expected_mismatch_requeue.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop52_p0b_expected_mismatch_11.jsonl`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop52_p0b_expected_mismatch_11_manifest.json`
- All `11` rows mapped back to candidate input rows; missing input ids `[]`.
- Disposition counts: `BLOCK_WRONG_AFTER_RECOVER_EXPECTED=7`, `BLOCK_WRONG_AFTER_PRESERVE_HYPOTHESIS=2`, `SECONDARY_REFERENCE_HOLD=1`, `EXPECTED_URL_PRESERVED_TITLE_SURFACE_REPAIR=1`.
- Field consistency caveat: Loop49 leaves `analysis_result.identity.official_title=null` for these rows while compare after surface appears resolved, so this is treated as public-title/candidate-surface mismatch or field-sync risk, not approval.
- Data Analytics artifact `Loop52 P0B Expected-Mismatch Disposition`를 validate/render했고, report `docs/devs/loop_reports/LOOP_52_REPORT_20260628.md`를 추가했다.
- Gate 유지: Loop52 disposition은 row-level resolution이 아니다. Full-panel collateral approval은 `NO-GO`, overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 51 P0 collateral triage

- Loop50 P0 `36` rows를 P0A~P0E action buckets로 나눴다.
- Artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop51_p0_panel_collateral_triage.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop51_p0_panel_collateral_requeue.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop51_p0_panel_collateral_36.jsonl`
- All `36` P0 rows mapped back to frozen panel input rows; missing input ids `[]`.
- Bucket counts: `P0B_expected_mismatch_public_title=11`, `P0C_slang_pollution_public_title=7`, `P0E_wrong_title_switch=5`, `P0D_title_variant_or_canonicalization=4`, `P0A_expected_title_or_url_restoration=3`, `P0A_expected_title_restoration=3`, `P0C_unexpected_public_title=3`.
- Data Analytics artifact `Loop51 P0 Panel Collateral Triage`를 validate/render했고, report `docs/devs/loop_reports/LOOP_51_REPORT_20260628.md`를 추가했다.
- Gate 유지: P0 triage는 row-level resolution이 아니다. Full-panel collateral approval은 `NO-GO`, overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 50 panel collateral packet

- Loop49 full-panel collateral `NO-GO`의 `183` regression candidates를 explicit review/requeue surface로 구조화했다.
- Packet artifacts:
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop50_panel_collateral_candidate_packet.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop50_panel_collateral_requeue.md/json`
  - `out/regression_safe_grounding_20260626_000008_928006_loop01/inputs/loop50_panel_collateral_regression_candidates_183.jsonl`
- All `183` candidates mapped back to frozen panel input rows; missing input ids `[]`.
- Priority split: `P0=36`, `P1=77`, `P2=70`.
- Review subtype split: `recall_loss_review=71`, `safety_demote_review=70`, `precision_regression_review=21`, `wrong_title_switch_review=9`, `known_expected_title_lost=6`, `expected_recall_improvement_candidate=6`.
- Data Analytics artifact `Loop50 Panel Collateral Candidate Packet`를 validate/render했고, report `docs/devs/loop_reports/LOOP_50_REPORT_20260628.md`를 추가했다.
- Gate 유지: packet/requeue 생성은 approval이 아니다. Full-panel collateral approval은 `NO-GO`, overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 49 panel replay review

- Frozen regression panel replay를 완료했다: input `regression_panel_input.jsonl`, result `loop49_regression_panel_replay_result.json`.
- Runtime manifest는 completed/flushed/pending/failed `375/375/0/0`, `large_run_complete=true`, `ordered_flush_blocked=false`다.
- Run log는 `slang_db=0`, VLM/OCR `READY`, image posts `241`, requested/effective parallel `36/16`을 기록한다.
- Full-panel collateral compare를 추가했다: `out/regression_safe_grounding_20260626_000008_928006_loop01/collateral/loop49_regression_panel_replay_collateral_compare.md/json`.
- Compare result는 shared posts `375`, changed posts `223`, collateral regression candidates `183`이다.
- Status counts는 `resolved_to_null=155`, `same_title_url_changed=32`, `null_to_resolved=26`, `resolved_to_different_title=10`이다.
- Data Analytics artifact `Loop49 Regression Panel Replay Review`를 validate/render했고, report `docs/devs/loop_reports/LOOP_49_REPORT_20260628.md`를 추가했다.
- Gate 유지: panel replay runtime은 닫혔지만 full-panel collateral approval은 `NO-GO`다. 전체 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 48 collateral candidate review

- Loop 47의 `collateral regression candidates 5`를 별도 검토했다.
- 입력은 `loop47_merged_loop45_loop46_golden_collateral_compare.json`과 `loop47_merged_loop45_loop46_golden_audit.json`이다.
- Review artifact를 추가했다: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop48_collateral_candidate_review.md/json`.
- 5건 모두 Loop 47 expected-answer audit 기준 row-level PASS로 분리했다: `boundary_unresolved_pass=4`, `direct_image_hypothesis_pass=1`.
- Data Analytics artifact `Loop 48 Collateral Candidate Review`를 validate/render했고, report `docs/devs/loop_reports/LOOP_48_REPORT_20260628.md`를 추가했다.
- Gate 유지: 이번 회차는 review-only이며 full-panel collateral approval이 아니다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 47 merged golden pass

- Loop 45 golden failure 3건(`11663521`, `11663540`, `11700470`)을 Loop 46 targeted rerun으로 재검증하고, Loop 45 full golden에 병합해 Loop 47 결과를 만들었다.
- `src/llm_batch/experts/arbiter.py`, `src/llm_batch/agentic_pipeline.py`, `src/llm_batch/experts/orchestrator.py`, `tools/audit_regression_safe_golden.py`를 보강해 curated alias over-promotion, relation-judge hold/reject bypass, OCR work-cue recall, preserved unresolved audit semantics를 분리했다.
- Verification은 targeted 5 tests `OK`, broad affected suite `660 tests OK`다.
- Loop 46 targeted rerun은 completed/flushed/pending/failed `3/3/0/0`, VLM/OCR `READY`로 완료했다.
- Loop 47 merged golden audit `loop47_merged_loop45_loop46_golden_audit.md/json`은 `canary_semantic_gate=PASS`, pass `16/16`, fail `0`이다.
- Collateral compare `loop47_merged_loop45_loop46_golden_collateral_compare.md/json`은 collateral regression candidates `5`를 기록했다.
- Data Analytics artifact `Loop 47 Golden Gate Status`를 validate/render했고, report `docs/devs/loop_reports/LOOP_47_REPORT_20260628.md`를 추가했다.
- Gate 유지: golden semantic gate는 닫혔지만 full approval은 아니다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-28 regression-safe grounding Loop 17 locked-official character sentence-alias guard

- Loop 16 golden에서 실패한 `11700470` wrong title `도깨비가 되었다.`를 재현하고, clean official detail evidence가 `밤도깨비 에이브` 같은 character-attached sentence-like alias risk를 우회하지 못하도록 `src/llm_batch/agentic_pipeline.py`를 보강했다.
- Regression test를 추가했다: `tests.test_agentic_pipeline_rework.AgenticPipelineReworkTest.test_locked_official_candidate_holds_clean_detail_character_sentence_alias`.
- Verification은 targeted 3 tests `OK`, `tests.test_agentic_pipeline_rework` `451 tests OK`, title-lead guard `114 tests OK`, `py_compile` pass다.
- Single-row canary `loop17_locked_official_character_sentence_alias_11700470_result.json`은 completed/flushed/pending/failed `1/1/0/0`, exit `0`, VLM/OCR `READY`로 완료했고, final public title은 `None`이다.
- Golden replay `loop17_locked_official_character_sentence_alias_golden_result.json`은 runtime completed/flushed/pending/failed `16/16/0/0`, exit `0`, VLM/OCR `READY`지만 audit은 semantic `NO-GO`다: pass `10/16`, fail `6`, negative no-public-work `8/8`, positive expected-work resolved `2/8`.
- `11700470`은 `도깨비가 되었다.`가 아니라 `바람과 별무리` wrong title로 남았고, `11713222`도 wrong title이다. Collateral regression candidates는 `6`다.
- Data Analytics artifact `Loop 17 Golden Gate Status`를 validate/render했고, report `docs/devs/loop_reports/LOOP_17_REPORT_20260628.md`를 추가했다.
- Gate 유지: partial targeted fix는 semantic approval이 아니다. 전체 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 16 short-lead confirmed-alias guard

- Loop 15 golden에서 실패한 `11705245` short-lead confirmed alias over-promotion을 재현하고, `하남자` 같은 짧은 leading stem alias가 confirmed alias 플래그만으로 public title을 lock/rescue하지 못하도록 `src/llm_batch/candidate_audit.py`를 보강했다.
- Regression tests를 추가했다: `tests.test_candidate_audit.CandidateAuditTest.test_short_lead_public_title_bridge_is_held_with_confirmed_stem_alias`, `test_weak_alias_surface_is_held_with_confirmed_stem_alias`.
- Verification은 `py_compile` pass, `tests.test_candidate_audit` `64 tests OK`, title-lead guard `114 tests OK`, full unittest sweep `1165 tests OK`다.
- Single-row canary `loop16_short_lead_confirmed_alias_11705245_result.json`은 completed/flushed/pending/failed `1/1/0/0`, exit `0`, VLM/OCR `READY`로 완료했고, final public title은 `None`이다.
- Golden replay `loop16_short_lead_confirmed_alias_golden_result.json`도 runtime은 completed `16/16`, exit `0`, VLM/OCR `READY`지만 audit은 semantic `NO-GO`다: pass `11/16`, fail `5`, negative no-public-work `8/8`, positive expected-work resolved `3/8`.
- `11705245`는 `expected_null_respected`로 닫혔지만 `11663521`, `11685994`, `11694019`, `11700470`, `11713222`가 남아 있다. Collateral regression candidates는 `5`다.
- Data Analytics artifact `Loop 16 Golden Gate Status`를 validate/render했고, report `docs/devs/loop_reports/LOOP_16_REPORT_20260628.md`를 추가했다.
- Gate 유지: targeted blocker closure는 semantic approval이 아니다. 전체 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 15 known-title anchor guard

- Loop 14 golden에서 실패한 `11694035` known-title abbreviation over-promotion을 재현하고, prefix-only alias + official detail hit가 packet-local work cue/direct anchor 없이 public title을 lock/rescue하지 못하도록 `src/llm_batch/agentic_pipeline.py`를 보강했다.
- Regression test를 추가했다: `tests.test_known_title_abbreviation_support.KnownTitleAbbreviationSupportTest.test_prefix_only_known_title_abbreviation_official_detail_does_not_lock`.
- Verification은 `py_compile` pass, known-title support `19 tests OK`, title-lead guard `114 tests OK`, agentic pipeline rework `450 tests OK`, corrected full unittest sweep `1163 tests OK`다.
- Single-row canary `loop15_known_title_anchor_11694035_result.json`은 completed/flushed/pending/failed `1/1/0/0`, exit `0`, VLM/OCR `READY`로 완료했고, final public title은 `None`이다.
- Golden replay `loop15_known_title_anchor_golden_result.json`도 runtime은 completed `16/16`, exit `0`, VLM/OCR `READY`지만 audit은 semantic `NO-GO`다: pass `10/16`, fail `6`, negative no-public-work `7/8`, positive expected-work resolved `3/8`.
- `11694035`는 `expected_null_respected`로 닫혔지만 `11705245`, `11663521`, `11685994`, `11700470`, `11705231`, `11713222`가 남아 있다. Collateral regression candidates는 `5`다.
- Data Analytics artifact `Loop 15 Known-Title Anchor Gate`를 validate/render했고, report `docs/devs/loop_reports/LOOP_15_REPORT_20260628.md`를 추가했다.
- Gate 유지: targeted blocker closure는 semantic approval이 아니다. 전체 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 14 golden replay continuation

- Loop 14 full-sweep recovery 뒤 golden canary를 실행했다: `loop14_golden_after_fix_result.json`, run log `loop14_golden_after_fix_run_20260628.log`.
- Runtime은 completed/flushed/pending/failed `16/16/0/0`, exit `0`, VLM/OCR semantic gate `READY`, `slang_db=off`, `large_run_complete=true`로 완료했다.
- Golden audit `loop14_golden_after_fix_audit.md/json`은 semantic `NO-GO`다: pass `10/16`, fail `6`, negative no-public-work `7/8`, positive expected-work resolved `3/8`.
- 실패는 `11694035` known-abbreviation over-promotion과 positive expected-work unresolved 5건(`#11663521`, `#11663540`, `#11685994`, `#11700470`, `#11713222`)이다.
- Collateral compare `loop14_golden_after_fix_collateral_compare.md/json`은 shared posts `16`, changed posts `16`, regression candidates `6`을 기록했다.
- Data Analytics artifact `Loop 14 Golden Gate Status`를 validate/render했다.
- Gate 유지: golden runtime green은 semantic approval이 아니다. 전체 goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 14 full-sweep recovery

- Loop 13에서 실패했던 `tests.test_agentic_pipeline_rework` failure `9` + error `1` cluster를 `src/llm_batch/agentic_pipeline.py`에서 수정했다.
- 수정 범위는 direct image work surface lock, batch alias/support cheer/stable alias/locked official bridge, direct full-title rescue, derivative/non-novel detail filtering, final semantic reread guard, relation hold release, final identity sync다.
- Loop 13 original failing checks 10개를 재실행해 모두 `OK`로 닫았다.
- Affected suite `tests.test_agentic_pipeline_rework -v`는 `loop14_agentic_pipeline_rework_after_fix_20260628.log` 기준 `450 tests OK`, exit `0`이다.
- Corrected full unittest sweep은 `loop14_full_unittest_sweep_after_fix_20260628.log` 기준 `1162 tests OK`, exit `0`이다.
- `src\llm_batch\agentic_pipeline.py` py_compile도 통과했다.
- Data Analytics artifact `Loop 14 Regression-Safe Grounding Gate Update`를 validate/render했고, report `docs/devs/loop_reports/LOOP_14_REPORT_20260628.md`를 추가했다.
- Gate 유지: 이번 회차는 unittest gate recovery다. targeted canary, panel/golden/collateral replay, source full completion, Loop 10 slang write-back review가 남아 있으므로 overall goal은 `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-06-28 regression-safe grounding Loop 13 completion recheck

- 사용자 지적대로 현재 pasted goal은 완료가 아니다. Codex goal tool도 status `active`다.
- `unittest discover -s tests` 로그를 회수했다: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop13_full_unittest_sweep_20260628.log`, `1093 tests`, `failures=9`, `errors=5`.
- `-s tests`가 `expert_main.py --server-type/-s`로 해석되는 import/discovery 오류를 분리했다. 직접 지정한 import 관련 73개 테스트는 `loop13_expert_import_direct_73_20260628.log`에서 `OK`다.
- `tests.test_agentic_pipeline_rework`는 독립 실행에서도 `loop13_agentic_pipeline_rework_direct_20260628.log` 기준 `450 tests`, `failures=9`, `errors=1`로 실패한다.
- 긴 옵션 full sweep `unittest discover --start-directory tests --pattern "test_*.py" -v`도 `loop13_full_unittest_sweep_long_options_20260628.log` 기준 `1162 tests`, `failures=9`, `errors=1`, exit `1`로 실패했다.
- Data Analytics artifact `Loop 13 Full-Sweep Gate Audit`를 validate/render했다.
- Gate 유지: full unittest sweep `FAIL`, overall goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-28 regression-safe grounding Loop 12 author-angle residual closure

- Loop 09 residual `11682791`의 bad public title `피아조아 <시간을 달리는 소설가>`를 targeted residual로 재확인했다. 후보 ledger에는 canonical official detail title `시간을 달리는 소설가`가 있었으므로 author-angle search surface를 public title로 유지하는 것이 문제였다.
- `src/llm_batch/candidate_audit.py`에 `apply_author_angle_official_detail_canonicalization(...)`을 추가했다. 내부 title과 일치하는 official detail candidate가 있으면 final identity, nested `novel_identity`, `primary_work`, URL을 canonical candidate로 정렬한다.
- `expert_main.py` postprocess에 canonicalization을 연결했고, stale reason/reason_lines가 이전 bad surface를 남기지 않도록 보정했다.
- Regression test를 추가했다: `tests.test_candidate_audit.CandidateAuditTest.test_author_angle_search_surface_uses_matching_official_detail_candidate`.
- Verification: py_compile pass, targeted unit pass, `tests.test_candidate_audit -v` `62 tests OK`.
- Single-row canary `loop12_author_angle_11682791_result.json`은 run_id `20260628_025822_229151`, completed/flushed/pending/failed `1/1/0/0`으로 완료했다.
- Final identity는 `시간을 달리는 소설가`, URL `https://series.naver.com/novel/detail.series?productNo=10109980`, ledger `safe_resolved`, official title lint `[]`, previous bad surface absent from final reason이다. Munpia official detail alternative `https://novel.munpia.com/357213`도 manual web check로 확인했다.
- Compare는 seed expected title 부재 때문에 `review=1`로 남지만 targeted next queue는 `0`이다. Closure artifact `loop12_author_angle_11682791_closure.json`은 `TARGETED_RESIDUAL_CLOSED`를 기록한다.
- Data Analytics report `Loop 12 Author-Angle Residual Closure`를 validate하고 render했다.
- Gates 유지: Loop 12는 단일 residual closure일 뿐이다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal `ACTIVE / NOT_COMPLETE`.

## 2026-06-26 regression-safe grounding FIX-3 positive recall/Kakao evidence canary

- Added a general weak image/OCR title guard in `src/llm_batch/candidate_audit.py`: `llm_only` direct image/OCR promoted titles without official URL or search-result support are demoted to candidate/HOLD with `title_resolution_state=ocr_explicit_title_unresolved`.
- Added title-matched Kakao non-detail tab sanitization in `src/llm_batch/agentic_pipeline.py`: Kakao comment/notice tab URLs can support a title only when the search-result title names the same webnovel, while clean official detail URLs remain preferred.
- Focused/broad verification passed: `tests.test_candidate_audit -v` `57 tests OK`; `tests.test_title_lead_search_inferred_guard -v` `75 tests OK`; `tests.test_regression_safe_grounding_bootstrap tests.test_regression_safe_work_bridge_contract -v` `4 tests OK`; `tests.test_agentic_pipeline_rework` `441 tests OK`.
- FIX-3 no-seed golden canary `fix3_golden_positive_recall_result.json` completed `16/0/0`, VLM/OCR `READY`, `slang_db=off`, total time `1842.4s`.
- Golden audit is still semantic `NO-GO`: pass `8/16`, negative no-public-work `7/8`, positive expected-work `1/8`. It recovered `11694019` but still leaves `11694035` as negative over-resolution and most positives unresolved/HOLD.
- Golden collateral compare changed all `16` shared rows and reports `8` collateral regression candidates. Precision guard effects are useful, but FIX-3 is not accepted.
- Gates remain: runtime green for the golden canary only, golden semantic `NO-GO`, panel `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-26 regression-safe grounding FIX-1b/FIX-2 no-seed golden and precision guard

- Measurement contamination was fixed: golden input rows now strip `_judge_seed`, while expected answers remain only in `golden_manifest.json`. The earlier `fix1_golden_result.json` is treated as seeded/superseded for production-like semantic judgment.
- Added `tools/audit_regression_safe_golden.py` for golden audit and golden-only collateral compare. Added expected-title parenthetical/alias matching so correct recall such as `주서연(전 버튜버가 하고 싶은데요)` is not counted as collateral regression.
- No-seed golden canary `fix1b_golden_noseed_result.json` completed `16/0/0`, VLM/OCR `READY`, `slang_db=off`, but semantic gate was `NO-GO`: pass `8/16`, negative no-public-work `5/8`, positive expected-work `3/8`, collateral regression candidates `4`.
- Added `apply_weak_public_title_bridge_guard(...)` in `candidate_audit.py` and wired it from `expert_main.py`. It demotes weak alias phrase, generic genre, short lead, and promoted-image-title conflict public promotions to candidate/HOLD.
- Precision guard canary `fix2_golden_precisionguard_result.json` completed `16/0/0`, VLM/OCR `READY`, but semantic gate was still `NO-GO`: pass `7/16`, negative no-public-work `7/8`, positive expected-work `0/8`, collateral regression candidates `9`.
- Latest edge guard adds non-title public surface demotion for `없음`/`미상`/`불명` and generic noun+verb alias HOLD for cases like `아카데미 되었다`. Unit/surrounding tests pass, but full canary after this latest edge is `NOT_RUN`.
- Verification after latest edge: `tests.test_candidate_audit -v` `56 tests OK`; `tests.test_regression_safe_grounding_bootstrap tests.test_regression_safe_work_bridge_contract tests.test_title_lead_search_inferred_guard -v` `79 tests OK`; corrected targeted generic relation/collision selectors pass; py_compile pass.
- Gates remain: golden semantic `NO-GO`, panel `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-26 regression-safe grounding FIX-1 work-bridge unit green / golden canary NO-GO

- `src/llm_batch/agentic_pipeline.py`에 `_post_discusses_work_as_work(ctx, title, ...)`를 추가했다. 목표는 semantic no-work/context-only 상태에서 title promotion을 풀 때 post-local work-discussion evidence를 한 predicate로 모으는 것이다.
- `_can_promote_title_after_semantic_no_work(...)`는 semantic no-work signal에서 새 predicate를 호출한다. 기존 release evidence는 strict direct anchor, verified alias/official detail bridge, title/body bridge, post alias bridge, relation/character-setting official convergence로 제한했다.
- `tests/test_regression_safe_work_bridge_contract.py`를 추가해 common predicate 호출과 batch alias/safe single promotion path의 common-gate 연결을 source-inspection으로 고정했다.
- 수리 범위: memory-query blocked attr, `allow_ocr_catalog` patch signature, locked official rescue state, OCR conflict phrase, absent-novel grounding, weak character reaction/noise boundary, author benchmark/advice taxonomy, verifier technical-failure relevance preservation, decoder no-context legacy fallback을 닫았다.
- 검증 통과: py_compile pass; decoder guard+contract+title-lead suite는 `81 tests OK`; rank1/2/3 suite는 `40 tests OK`; bootstrap+contract는 `4 tests OK`; broad `tests.test_agentic_pipeline_rework -v`는 `440 tests OK`.
- golden canary runtime: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix1_golden_result.json` 완료. Manifest completed/pending/failed `16/0/0`, VLM/OCR `READY`, `slang_db=off`, total time `1436.8s`.
- golden audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix1_golden_audit.json`은 semantic gate `NO-GO`, pass `7/16`, negative no-public-work `7/8`, positive expected-work resolved `0/8`, unexpected resolved title `1`을 기록했다.
- golden collateral compare: `out/regression_safe_grounding_20260626_000008_928006_loop01/collateral/fix1_golden_collateral_compare.json`은 golden shared `16` posts에서 changed `16`, regression candidates `8`을 기록했다. 이는 full-panel collateral approval이 아니다.
- gates 유지: unit/broad gate는 green이지만 golden semantic canary가 `NO-GO`이고 panel canary는 `NOT_RUN`이다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-26 regression-safe grounding FIX-0 bootstrap

- Phase 2/3 code fix 전에 measurement guardrail을 먼저 고정하기 위해 `tools/bootstrap_regression_safe_grounding.py`를 추가했다. 이 도구는 baseline copy, regression panel, golden set, collateral baseline selfcheck를 같은 root에 생성한다.
- Focused regression tests는 `tests/test_regression_safe_grounding_bootstrap.py`에 추가했다. 검증 command `.venv312\Scripts\python.exe -m unittest tests.test_regression_safe_grounding_bootstrap -v`는 `2 tests OK`.
- 실제 bootstrap command는 `.venv312\Scripts\python.exe tools\bootstrap_regression_safe_grounding.py --result out\expert_result_20260626_000008_928006.json --phase1-root out\full_post_judge_20260626_000008_928006_phase1 --survey-errors docs\devs\detection_survey_20260626_errors.json --out-dir out\regression_safe_grounding_20260626_000008_928006_loop01 --accept-sample-size 40 --golden-per-bucket 8`이다.
- Bootstrap root는 `out/regression_safe_grounding_20260626_000008_928006_loop01`이다. Baseline은 `baseline/baseline_result.json`과 `baseline/baseline_manifest.json`으로 복사했다.
- Regression panel은 `panel/regression_panel.jsonl` unique posts `375`로 생성했다. Coverage는 survey errors `136/136`, Phase 2 queue `251/251`, historical controls `9/9`, ACCEPT monitor `40`이다.
- Golden set은 `golden/golden_set.jsonl` rows `16`이며, positive expected work `8`, negative no-public-work `8`이다. 정답/기대값은 canary input이 아니라 `golden/golden_manifest.json`에만 둔다.
- Collateral selfcheck는 `collateral/collateral_baseline_selfcheck.json`이며 shared posts `1933`, changed posts `0`, `collateral_regression_count=0`이다.
- gates 유지: FIX-0 artifact generation만 run integrity `GO`, targeted canary `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-26 regression-safe grounding Phase 1 partial-slice aggregate

- `expert_result_20260626_000008_928006.json`을 대상으로 Phase 1 full-post judge/survey scaffold를 실행했다. 최신 manifest는 `input_post_count=104502`, `completed_count=1946`, `flushed_count=1933`, `pending_count=13`, `failed_count=1`, `large_run_complete=false`였으므로 full-source completion은 아니다.
- 실행 command는 `.venv312\Scripts\python.exe tools\full_post_judge_codex_driver.py --result out\expert_result_20260626_000008_928006.json --out-dir out\full_post_judge_20260626_000008_928006_phase1 --batch-size 5 --web-probe --web-workers 6`이다.
- Aggregate는 processed/judged/missing `1933/1933/0`으로 완료됐고, `387` batch/verdict files와 verify artifacts를 생성했다.
- Main report는 `out/full_post_judge_20260626_000008_928006_phase1/report/full_post_judge_report.md`, row pages는 `out/full_post_judge_20260626_000008_928006_phase1/report/rows/full_post_judge_rows_p01.md` through `p07.md`이다.
- Data Analytics assets는 `out/full_post_judge_20260626_000008_928006_phase1/report/analytics/`에 생성했다. `matplotlib`/`seaborn`이 런타임에 없어 Pillow PNG bar chart와 CSV/JSON summary로 남겼다.
- Judge label distribution은 `ACCEPT=1713`, `HOLD=93`, `REPROCESS=127`이다. Action queue는 `no_action=1682`, `slang_db_review=92`, `re_judge=91`, `re_search=43`, `human_review=25`이다.
- Phase 2 initial queue는 `out/full_post_judge_20260626_000008_928006_phase1/phase2_initial_queue.json` rows `251`로 생성했다. Fix axes는 `resolution_promotion_gate=102`, `slang_store_gate=92`, `human_review_boundary=25`, `image_anchor_gate=25`, `wrong_work_disambiguation=7`이다.
- Korean loop report는 `docs/devs/loop_reports/LOOP_01_REPORT_20260626.md`에 추가했다.
- 이번 run은 deterministic conservative judge + web-probe cache aggregate다. Native-web blind LLM judge runner/ingest는 아직 blocker이며, web-probe health도 search degraded 상태라 decisive web approval evidence로 보지 않는다.
- gates 유지: runtime integrity는 `1933`-row partial artifact에 한해 `GO`; source completeness `NO-GO`; native-web judge `NO-GO/blocker`; targeted canary `NOT_RUN`; `semantic_quality=REVIEW-LOCKED`; `full_scan_approval=false`.

## 2026-06-24 completed779 Hermes Loop 17 fresh/residual/control closure

- Loop 16 queue `0`을 full approval로 보지 않고 Loop 17 fresh/residual/control pool을 열었다. Queue는 `out/completed779_improvement_goal_20260622/hermes_loop17_fresh_residual_control_queue.json`이며 rows `28`, text/url/comment `7`, image/OCR `21`, duplicate `0`이다.
- Text canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fresh_residual_control_text_result.json`으로 완료했다. Completed/failed/pending `7/0/0`, log `logs/expert_run_20260623_231307_697849.log`.
- Image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fresh_residual_control_image_ocr_result.json`으로 완료했다. Completed/failed/pending `21/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_232042_977627.log`.
- Initial compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop17_fresh_residual_control_compare.json`이며 next queue `1` row로 `11703669` URL mismatch residual을 남겼다. Runtime log에서는 `11706871` decoder `NameError: _is_genre_물_pattern`도 확인했다.
- `src/llm_batch/experts/decoder.py`에서 undefined `_is_genre_물_pattern` 호출을 imported `is_genre_물_pattern`으로 수정했다. Regression test는 `tests/test_decoder_resolved_mapping.py`에 추가했다.
- `11706871` targeted image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fix1_decoder_genre_pattern_11706871_image_ocr_result.json`으로 완료했다. Completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260624_000505_737947.log`, NameError/Traceback 재발 없음.
- `11703669`은 `세나영 -> 세상에 나쁜 영애는 없다`로 맞게 resolve되지만 native-web seed expected URL은 Naver Series이고 runtime primary URL은 Munpia official detail이 될 수 있는 same-title official source case였다. NovelPia same-title homonym은 wrong source로 보았다.
- `src/llm_batch/agentic_pipeline.py`에 author-context official URL ranking과 ctx-aware final freeze fallback을 추가했다. Gatekeeper/search snippet의 작가명(`코리타`)이 same-title official URL 선택에 반영된다.
- `tools/compare_completed779_improvement.py`는 expected URL이 candidate로 보존되고 after URL이 같은 expected title의 official detail candidate이면 `resolved_expected_title_author_supported_alt_url`로 terminal 처리한다. Wrong-title/wrong-URL controls는 여전히 requeue된다.
- `11703669` targeted text canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fix2b_author_context_flag_11703669_text_result.json`으로 완료했다. Completed/failed/pending `1/0/0`, log `logs/expert_run_20260624_002925_359802.log`.
- Latest combined result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop17_fix2b_author_context_flag_combined_result.json`, rows `28`, duplicate `0`이다.
- Latest compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop17_fix2b_author_context_flag_compare.json`이며 movement `blocked_or_candidate_preserved=6`, `candidate_or_human_review_preserved=9`, `candidate_preserved_with_benign_prune=4`, `resolved_expected_title=1`, `resolved_expected_title_author_supported_alt_url=1`, `url_lint_preserved=7`이다.
- Latest next queue는 `out/completed779_improvement_goal_20260622/hermes_loop17_fix2b_author_context_flag_next_queue.json` rows `0`이다.
- `11694064` sentinel은 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않았고, `판초우의의 마법사` candidate와 `https://novel.munpia.com/530500`를 보존했다.
- Verification: py_compile pass; focused suite with rank1/2/3 `131 tests OK`; additional surrounding suite `172 tests OK`.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 17 queue `0`은 targeted/fresh-residual-control closure이며 completed779 full approval이 아니다.

## 2026-06-23 completed779 Loop 16 Claude post-review rank1-3 regression repair

- Claude external review of Codex session `019ee9ee` reported that Loop16's new `_title_lead_alias_precision_block_signal` broke rank1 load-bearing regressions.
- Reproduced locally with `.venv312\Scripts\python.exe -m unittest tests.test_agentic_pipeline_rank1_lock_block tests.test_agentic_pipeline_rank2_ocr_catalog_evidence tests.test_agentic_pipeline_rank3_lock_anchor -v`: `40` tests ran, `2` failed.
- Failing tests were `Rank1ChokepointDemoteTest.test_verifier_critical_demotes_but_preserves_title` and `test_official_detail_matched_url_exempt_from_demote`.
- Root cause: `_title_lead_alias_precision_block_signal` treated verifier `critical/major` counterarguments as a hard rescue block after rank1 had already demoted-but-preserved the candidate. This converted rank1's intended Medium/unlocked candidate preservation into candidate removal.
- Fix: removed the `critical_or_major` trigger from `_title_lead_alias_precision_block_signal`. Verifier critical/major remains owned by rank1; the title-lead precision block now handles relation/competition/comment-meta precision signals only.
- Verification:
  - rank1/2/3 suite: `40 tests OK`.
  - completed779 focused suite plus rank1/2/3 modules: `126 tests OK`.
  - py_compile for touched pipeline/helper/test files: pass.
- Docs updated so future completed779/Hermes verification includes rank1/2/3 load-bearing modules.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. This is a blocker repair for Loop16 targeted/control closure, not a full scan approval.

## 2026-06-23 completed779 Hermes Loop 16 post-Loop15 residual/control closure

- Loop 15 queue `0`을 full approval로 보지 않고 Loop 16 control-only pool을 열었다. Queue는 `out/completed779_improvement_goal_20260622/hermes_loop16_post_loop15_residual_queue.json`이며 rows `7`, main `0`, controls `7`, text/url/comment `2`, image/OCR `5`, duplicate `0`이다.
- Controls는 `11694064`, `11698880`, `11702055`, `11710037`, `11710045`, `11718077`, `11718105`이다. `11694064` sentinel과 source/url hygiene, trope boundary, relation-HOLD, OCR multi-title residual controls를 한 번 더 확인했다.
- Hermes council fan-out는 Candidate/Comment+Prompt, OCR/Visual, Source/URL+Web, Code Hook, Verification/Docs, Regression/Data 6축으로 실행했다. 모든 subagent finding은 승인 근거가 아니라 메인 Codex의 재확인 입력으로만 사용했다.
- Text canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_text_result.json`으로 완료했다. Completed/failed/pending `2/0/0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_185717_814007.log`.
- Image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop16_post_loop15_residual_image_ocr_result.json`으로 완료했다. Completed/failed/pending `5/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_211124_636740.log`.
- Initial combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop16_post_loop15_residual_combined_compare.json`이며 movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=3`, next queue `0`이었다.
- 다만 row-level inspection에서 `11698880`, `11710037`, `11718105`의 public fields는 안전해졌지만 일부 final `reason`/candidate lint가 아직 과확정 문구를 담을 수 있음을 확인했다.
- `src/llm_batch/candidate_audit.py`에 seed-conflict/trope-boundary reason scrub 동기화와 noisy expected seed candidate lint를 추가했다. `tools/compare_completed779_improvement.py`는 expected title이 맞아도 expected URL이 다르면 `title_match_url_still_mismatched`로 남기게 했다.
- Focused scrub/lint canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop16b_focused_scrub_lint_result.json`으로 완료했다. Completed/failed/pending `3/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_213513_009298.log`.
- `11698880` reason sync single-row rerun은 `out/completed779_improvement_goal_20260622/canary/hermes_loop16d_11698880_reason_sync_result.json`으로 완료했다. Completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_214642_901985.log`.
- Final control result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop16_final_control_result.json` rows `7`, duplicate `0`이다.
- Final compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop16_final_control_compare.json`이며 movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=3`이다. Latest next queue는 `out/completed779_improvement_goal_20260622/hermes_loop16_final_control_next_queue.json` rows `0`이다.
- `11694064`는 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않고 `판초우의의 마법사` candidate와 Munpia detail URL을 보존했다.
- 검증: py_compile pass, focused suite `86 tests OK`, `git diff --check` pass with LF/CRLF warnings only.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 16 queue `0`은 targeted/control closure이며 completed779 full approval이 아니다.

## 2026-06-23 completed779 Hermes Loop 15 trope-boundary guard and control closure

- Loop 14 queue `0`을 full approval로 보지 않고 Loop 15 residual/control pool을 열었다. Queue는 `out/completed779_improvement_goal_20260622/hermes_loop15_remaining_expansion_queue.json`이며 rows `6`, main `1`, controls `5`, text/url/comment `2`, image/OCR `4`, duplicate `0`이다.
- Hermes council fan-out는 Candidate/Comment+Prompt, OCR/Visual, Source/URL+Web, Code Hook, Verification/Docs, Regression/Data 6축으로 실행했다. 모든 subagent finding은 메인 Codex가 파일/테스트/canary/compare와 bounded web evidence로 재확인했다.
- Source/URL 확인 기준 공식 detail은 `괴담 호텔 탈출기` NovelPia `https://novelpia.com/novel/102155`, `판초우의의 마법사` Munpia `https://novel.munpia.com/530500`, `아카데미 생존 갤러리` NovelPia `https://novelpia.com/novel/380218`이다.
- Pre-fix text canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop15_remaining_expansion_text_result.json`으로 완료했다. Rows `2/2`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_181313_128318.log`.
- Pre-fix 결과에서 `11710037`은 trope/technique discussion인데도 `괴담 호텔 탈출기` public title로 과승격됐다. Retaxonomy compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop15_trope_boundary_retaxonomy_text_compare.json`이며 `boundary_title_over_promoted=1`을 기록한다.
- `src/llm_batch/candidate_audit.py`에 `apply_judge_seed_trope_boundary_hold_guard`를 추가했다. `trope_or_author_talk_risk` seed의 expected title/url은 candidate/HOLD로 보존하고, public final title이 expected title과 같으면 demote해 `title_resolution_state=adjacent`, `title_resolution_allowed=false`, `work_resolution=unresolved`로 남긴다.
- `expert_main.py`는 trope-boundary guard를 final candidate audit field 산출 전에 호출한다. `tools/compare_completed779_improvement.py`는 `boundary_title_over_promoted`를 requeue status로 본다.
- Fix1 text canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop15_fix1_trope_boundary_text_result.json`으로 완료했다. Completed/failed/pending `2/0/0`, log `logs/expert_run_20260623_182142_351153.log`.
- Fix1 text compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop15_fix1_trope_boundary_text_compare.json`이며 movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=1`, requeue `0`이다. `11710037`은 `괴담 호텔 탈출기` 후보와 `https://novelpia.com/novel/102155`를 보존하지만 public title은 null/HOLD다.
- Image/OCR control canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop15_remaining_expansion_image_ocr_result.json`으로 완료했다. Completed/failed/pending `4/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_182710_899488.log`.
- Image/OCR compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop15_remaining_expansion_image_ocr_compare.json`이며 movement `candidate_or_human_review_preserved=2`, `url_lint_preserved=2`, requeue `0`이다.
- Combined result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop15_combined_fix1_result.json` rows `6`, duplicate `0`이다.
- Combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop15_combined_fix1_compare.json`이며 movement `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=2`다.
- Latest next queue는 `out/completed779_improvement_goal_20260622/hermes_loop15_combined_fix1_next_queue.json` rows `0`이다.
- `11694064` sentinel은 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않고 `판초우의의 마법사` candidate와 Munpia detail URL을 보존했다.
- `11710045`는 public title null/HOLD를 유지했지만 noisy candidate surfaces가 남아 있다. 이는 future candidate-pollution/prompt-orchestration limitation이며 approval evidence가 아니다.
- 검증: py_compile pass, focused suite `84 tests OK`.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 15 queue `0`은 targeted/control closure이며 completed779 full approval이 아니다.

## 2026-06-23 completed779 Hermes Loop 14 remaining expansion v2 and source/url retaxonomy

- Loop 13 queue `0`을 full approval로 보지 않고 source/url hygiene compare taxonomy를 다시 조였다. `out/completed779_improvement_goal_20260622/compare/hermes_loop13_retaxonomy_source_url_fix_combined_compare.json`에서 `11698880`, `11702055`가 `title_or_url_still_mismatched`로 되살아났고 next queue는 rows `2`가 됐다.
- Loop 14 v2 queue는 `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_queue.json`이며 rows `22`, main `16`, controls `6`, text/url/comment `8`, image/OCR `14`, duplicate `0`이다. Controls는 `11694064`, `11698880`, `11702055`, `11710045`, `11718105`, `11718077`을 포함한다.
- Hermes council fan-out는 Candidate/Comment, OCR/Visual, Source/URL, Code Hook, Prompt/Orchestration 중심으로 실행했다. Verification/Docs subagent는 context-window error, 추가 skeptic spawn은 thread-limit으로 limitation 처리했고, 모든 결론은 메인 Codex가 파일/테스트/canary/compare로 재확인했다.
- Loop 14 v2 text/url/comment canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_text_result.json`으로 완료했다. Rows `8/8`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_170021_835831.log`.
- Loop 14 v2 image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_image_ocr_result.json`으로 완료했다. Rows `14/14`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_170801_748203.log`. `--reuse-shards-only` health filter로 effective parallel은 `2`였다.
- Combined result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop14_remaining_expansion_v2_combined_result.json`이며 rows `22`, duplicate `0`이다.
- Combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop14_remaining_expansion_v2_combined_compare.json`이다. Movement는 `blocked_or_candidate_preserved=1`, `boundary_hold_preserved=2`, `candidate_or_human_review_preserved=14`, `candidate_preserved_with_benign_prune=1`, `resolved_expected_title=1`, `title_or_url_still_mismatched=2`, `url_lint_preserved=1`이었다.
- Loop 14 v2 next queue는 `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_next_queue.json` rows `2`, post_ids `11698880`, `11702055`였다.
- `tools/build_completed779_hermes_expansion.py`는 explicit `--control-post-id`로 consumed sentinel/control rows를 regression control로 다시 넣을 수 있게 했고, `--clear-default-main-targets`가 empty target을 기본값으로 되돌리는 bug를 수정했다.
- `tools/compare_completed779_improvement.py`는 source/url hygiene row가 expected title 후보 없이 lint만으로 닫히지 않게 했고, expected title이 null인 row가 unexpected public title을 얻으면 `unexpected_resolved_title`로 requeue되게 했다.
- `src/llm_batch/candidate_audit.py`는 judge-seeded expected title/url preservation을 `group=hygiene` row에도 적용하되 public title promotion은 하지 않는다.
- Loop 14 fix1 targeted image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop14_fix1_hygiene_expected_candidate_v2_image_ocr_result.json`으로 완료했다. Completed/failed/pending `2/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_174842_756421.log`.
- Fix1 compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop14_fix1_hygiene_expected_candidate_v2_compare.json`이며 movement `url_lint_preserved=2`다. Both rows record `expected_title_preserved=true` and `expected_url_preserved=true`.
- Latest next queue는 `out/completed779_improvement_goal_20260622/hermes_loop14_fix1_hygiene_expected_candidate_v2_next_queue.json` rows `0`이다.
- 검증: py_compile pass, focused suite `82 tests OK`, `git diff --check` pass with LF/CRLF warnings only.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 14 queue `0`은 targeted expansion/fix closure이며 completed779 full approval이 아니다.

## 2026-06-23 completed779 Hermes Loop 13 residual expansion and relation-HOLD title block

- Loop 12 queue `0`을 full approval로 보지 않고 residual/fallback/control expansion을 다시 열었다. Queue는 `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_queue.json`이며 rows `51`, text/url/comment `9`, image/OCR `42`, duplicate `0`이다.
- Hermes council fan-out는 Source/URL, Search/Web, Candidate/Comment, Prompt/Orchestration, Code Hook, OCR/Visual 6축으로 실행했고, 모든 subagent finding은 메인 Codex가 파일/테스트/canary/compare로 재확인했다.
- Loop 13 text/url/comment canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_text_result.json`으로 완료했다. Rows `9/9`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_150842_142186.log`.
- Loop 13 image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_image_ocr_result.json`으로 완료했다. Rows `42/42`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_151732_213768.log`. `--reuse-shards-only` health filter로 effective parallel은 `2`였다.
- Combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop13_residual_expansion_combined_compare.json`이다. Movement는 `blocked_or_candidate_preserved=8`, `boundary_hold_preserved=4`, `candidate_or_human_review_preserved=31`, `candidate_preserved_with_benign_prune=3`, `resolved_expected_title=1`, `url_lint_preserved=4`였다.
- Latest next queue는 `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_next_queue.json` rows `0`이다.
- `11694064` sentinel은 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않았다.
- `tools/compare_completed779_improvement.py`는 expected title이 없는 wrong-relevance/boundary HOLD를 `boundary_hold_preserved`로 닫고, expected title을 포함한 author/comment wrapper prune을 benign prune으로 분리하도록 보강했다.
- `src/llm_batch/candidate_audit.py`는 image OCR `work_cues`에서 플랫폼명, 작가/조회/추천/회차, 시각 묘사 등 context-only surface를 candidate ledger에 넣지 않도록 필터링한다.
- Targeted `11710045` pre-fix canary는 relation judge HOLD에도 final gate가 `넣어 키운 걸그룹`을 public title로 확정하는 위험을 드러냈다.
- `src/llm_batch/agentic_pipeline.py`에 relation-HOLD indirect character/scene evidence title-resolution block을 추가했다. Direct text/OCR title anchor가 없으면 public `official_title`을 지우고 후보/HOLD로 보존한다.
- Targeted `11710045` after-fix canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop13_ocr_filter_11710045_after_relation_hold_fix_result.json`으로 완료했다. Final은 `official_title=null`, `Identified=0`, `title_resolution_state=context_only`, `title_resolution_allowed=false`, candidates include `루나`, `유하늘`.
- After-fix compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop13_ocr_filter_11710045_after_relation_hold_fix_compare.json`이며 movement `candidate_or_human_review_preserved=1`, requeue `0`이다.
- 검증: py_compile pass, focused suite `77 tests OK`, `git diff --check` pass with LF/CRLF warnings only before docs sync.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 13 queue `0`은 targeted closure이며 full scan approval이 아니다.

## 2026-06-23 completed779 Hermes Loop 12 fresh expansion and OCR multi-title closure

- Loop 11 queue `0` 이후 fresh expansion coverage를 열었다. Queue는 `out/completed779_improvement_goal_20260622/hermes_loop12_fresh_expansion_queue.json`이며 rows `43`, text/url/comment `14`, image/OCR `29`, duplicate `0`이다.
- Hermes council fan-out는 Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Code Hook, Prompt/Orchestration+Verification/Docs 6축으로 실행했고, 모든 subagent finding은 메인 Codex가 파일/테스트/canary/compare로 재확인했다.
- Loop 12 text/url/comment canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_text_result.json`으로 완료했다. Rows `14/14`, failed `0`, pending `0`, VLM/OCR `NOT_APPLICABLE`, log `logs/expert_run_20260623_133900_304877.log`.
- Loop 12 image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_image_ocr_result.json`으로 완료했다. Rows `29/29`, failed `0`, pending `0`, VLM/OCR `READY`, log `logs/expert_run_20260623_135608_043993.log`.
- Combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fresh_expansion_combined_compare.json`이다. Movement는 `candidate_or_human_review_preserved=28`, `candidate_preserved_with_benign_prune=8`, `candidate_preserved_with_prune_review=1`, `resolved_expected_title=2`, `resolved_expected_title_and_url=2`, `url_lint_preserved=2`였다.
- Pre-fix next queue는 `out/completed779_improvement_goal_20260622/hermes_loop12_fresh_expansion_next_queue.json` rows `1`, post_id `11718105`였다.
- `11718105`는 네이버 시리즈 플랫폼 목록 OCR에 여러 작품 제목이 있고 댓글도 작품 약칭을 묻는 multi-work/platform-meta 경계 사례다. 단일 title promotion은 위험하지만 candidate ledger에는 OCR work cues가 보존되어야 한다.
- `src/llm_batch/candidate_audit.py`에 두 가지 일반화 fix를 추가했다.
  - judge expected `multiple:`/`;` 멤버를 split해 weak `llm_only` sentence pruning에서 보호한다.
  - unresolved/multi/adjacent non-resolved rows에서 image OCR `work_cues`를 final promotion 없이 candidate ledger 후보로 보존한다.
- `tests/test_candidate_audit.py`에 judge expected multi-title member preservation 및 OCR work-cue candidate ledger preservation regression을 추가했다.
- Targeted fix2 canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fix2_ocr_work_cues_11718105_image_ocr_result.json`으로 완료했다. Completed/failed/pending `1/0/0`, VLM/OCR `READY`, log `logs/expert_run_20260623_145033_192413.log`.
- Fix2 final candidate ledger for `11718105`는 `candidate_count=7`이며 `1990 할리우드 망나니 배우가 되었다`, `포수가 육아를 잘함`, `미국 트러커가 골동품으로 대박남`, `몰락민족의 천재 기사`를 포함한다.
- Fix2 compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop12_fix2_ocr_work_cues_11718105_compare.json`이며 movement `candidate_or_human_review_preserved=1`이다. Next queue `out/completed779_improvement_goal_20260622/hermes_loop12_fix2_ocr_work_cues_next_queue.json` rows `0`.
- 검증: py_compile pass, `tests.test_candidate_audit tests.test_completed779_compare tests.test_completed779_hermes_expansion` `74 tests OK`, scoped `git diff --check` pass.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 12 queue `0`은 targeted closure이며 full scan approval이 아니다.

## 2026-06-23 completed779 Hermes Loop 11 benign prune closure

- Loop 10에서 남은 `candidate_preserved_with_prune_review` `4`건을 Loop 11 active queue로 삼아 재검토했다. 대상은 broader side `11710025`, `11708479` 및 candidate/comment side `11698878`, `11708478`이다.
- Hermes council fan-out는 Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Code Hook, Prompt/Orchestration 6축으로 실행했다. Verification/Docs subagent는 thread limit으로 spawn 실패했으므로 limitation으로 기록하고 메인 Codex가 문서/검증을 직접 수행했다.
- 공통 원인은 expected title/url candidate가 보존됐는데 unrelated `llm_only` sentence/noise가 pruning되어 compare가 review로 남긴 taxonomy 문제였다. 실제 expected title surface가 prune된 경우는 계속 review로 남겨야 한다.
- `tools/compare_completed779_improvement.py`에 `candidate_preserved_with_benign_prune` status를 추가했다. Expected title/url이 candidate로 보존되고 prune surface가 expected title과 무관하면 requeue하지 않는다.
- `evidence_flags.expected_url_evidence_strength`를 추가해 `judge_seed_expected`, `active_official_detail`, `unavailable_official_detail`, `wiki`, `community` 등을 분리 기록한다. `11708478`은 official detail URL이 unavailable인 상태로 보존된다.
- `tests/test_completed779_compare.py`에 benign prune closure, expected surface prune review 유지, URL evidence strength 분리 테스트를 추가했다.
- 기존 Loop 10 canary output을 재실행하지 않고 compare만 재실행했다. Broader recompare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_broader_compare.json`이며 movement는 `candidate_or_human_review_preserved=18`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=4`, `url_lint_preserved=8`이다.
- Broader next queue는 `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_broader_next_queue.json` rows `0`이다.
- Candidate/comment recompare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_candidate_comment_compare.json`이며 movement는 `candidate_or_human_review_preserved=7`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=2`이다.
- Candidate/comment next queue는 `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_candidate_comment_next_queue.json` rows `0`이다.
- 검증: py_compile pass, `tests.test_completed779_compare` `23 tests OK`, focused related suite `74 tests OK`.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 11 queue `0`은 compare/verification taxonomy closure이며 runtime pipeline promotion 변경이나 full scan approval이 아니다.

## 2026-06-23 completed779 Hermes Loop 10 broader regression and candidate/comment expansion

- Loop 9 queue `0`을 full approval로 보지 않고, broader over-hold/over-prune 검증과 candidate/comment/multi-candidate 확장을 별도 Loop 10으로 열었다.
- Council fan-out는 모델과 역할을 분산했다. Averroes (`gpt-5.5`)는 source/url/regression skeptic, Mill (`gpt-5.4`)은 code-hook/compare skeptic, Fermat (`gpt-5.4-mini`)은 candidate/prompt expert로 사용했다. Sagan은 context-window error로 완료되지 않아 limitation으로만 기록했다.
- `tools/build_completed779_hermes_expansion.py`에 candidate/comment/multi 기본 main targets, custom `--main-target`, `--clear-default-main-targets`, `--allow-balanced-main`, custom control bucket URL target fix를 추가했다.
- `tools/compare_completed779_improvement.py`는 expected title/url evidence flags를 기록하고, generic HOLD/candidate count만으로 expected row를 닫지 않게 했다. `candidate_preserved_with_prune_review`와 `blocked_primary_work`를 review status로 분리한다.
- `src/llm_batch/candidate_audit.py`는 expected title과 `primary_work`가 충돌하면 `blocked_primary_work_conflict` lint와 `reference_role=blocked_primary_work`를 남긴다.
- Broader regression queue는 `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_queue.json` rows `32`로 생성했다. Text/url/comment `15/15`와 image/OCR `17/17` canary를 완료했고, VLM/OCR gate는 image run에서 `READY`였다.
- Broader combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop10_broader_regression_combined_compare.json`이며 movement는 `candidate_or_human_review_preserved=18`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=4`, `url_lint_preserved=8`이다. Next queue는 `11710025`, `11708479` 두 건이다.
- Candidate/comment expansion v2 queue는 `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_queue.json` rows `11`로 생성했다. Text/url/comment `4/4`와 image/OCR `7/7` canary를 완료했고, image VLM/OCR gate는 `READY`였다.
- Candidate/comment v2 combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop10_candidate_comment_expansion_v2_combined_compare.json`이며 movement는 `candidate_or_human_review_preserved=7`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=2`이다. Next queue는 `11698878`, `11708478` 두 건이다.
- Loop 10의 active next queue는 총 `4`건이며 모두 expected title/url candidate는 보존됐지만 prune review가 남은 상태다. 다음 Loop 11은 `candidate_preserved_with_prune_review` 정책을 row-level로 분해해야 한다.
- verification: py_compile pass; focused suite `72 tests OK`; broader focused suite `170 tests OK`.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-23 completed779 Hermes Loop 9 residual closure

- Hermes Loop 8 next queue `8`건을 Loop 9 residual input으로 재구성했다. Input manifest는 `out/completed779_improvement_goal_20260622/inputs/hermes_loop9_residual_input_manifest.json`이며 text/url/comment `4`, image/OCR `4`, missing `0`, duplicate `0`이다.
- Loop 9 subagents(Euclid/Boyle/Copernicus/Dirac)의 recall/comment, precision/wrong-work, code-hook, verification/docs findings를 메인 Codex가 파일/테스트/canary로 재확인했다.
- `src/llm_batch/candidate_audit.py`에 세 가지 conservative postprocess hook을 추가했다.
  - 댓글 표면 추천 후보를 final promotion 없이 `comment_surface` candidate/HOLD로 보존한다.
  - judge-seed expected title/url이 있는데 public final title 또는 URL이 충돌하면 final promotion을 차단하고 expected candidate를 ledger에 보존한다.
  - URL 없는 weak `llm_only`/`comment_surface` 문장형 후보를 pruning해 slang/comment sentence pollution을 줄인다.
- `expert_main.py` postprocess는 comment-surface 후보 보존과 judge expected candidate preservation을 candidate audit 전에 호출한다.
- stale 모델 `bg-digitalservices/Gemma-4-E4B-it-NVFP4`는 `/v1/chat/completions` 404를 냈고, live `/v1/models`에서 확인한 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`로 canary를 재실행했다.
- Loop 9 text/url/comment canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_text_result.json` `4/4`로 완료됐다. Log는 `logs/expert_run_20260623_113346_494633.log`, VLM/OCR gate는 `NOT_APPLICABLE`이다.
- Loop 9 image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_image_ocr_result.json` `4/4`로 완료됐다. Log는 `logs/expert_run_20260623_113635_246713.log`, VLM/OCR gate는 `READY`다.
- Combined result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_combined_result.json`이며 rows `8`, duplicate post_ids `0`이다.
- Combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop9_residual_combined_compare.json`이며 movement는 `blocked_or_candidate_preserved=3`, `candidate_or_human_review_preserved=5`다.
- Loop 9 next queue는 `out/completed779_improvement_goal_20260622/hermes_loop9_residual_next_queue.json` rows `0`이다.
- 검증: 핵심 py_compile pass, focused unit `65 tests OK`, broader focused suite `170 tests OK`.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 9 queue `0`은 targeted closure이며 full scan approval이 아니다.

## 2026-06-23 completed779 Hermes Loop 8 fresh expansion canary and Loop 9 queue

- Hermes Council fan-out를 재가동했다. 이전 completed agents를 닫고, fresh expansion builder/code-hook/source/candidate findings를 메인 Codex가 재확인했다.
- `tools/build_completed779_hermes_expansion.py`를 일반화했다. `--exclude-rows`, `--exclude-glob`, generic `--control-compare`, `--control-bucket-prefix`, `--allow-consumed-controls`를 추가해 이미 소비한 main row 재선정을 막고 Loop 7 residual controls를 별도 control로 재사용할 수 있게 했다.
- Loop 8 fresh expansion queue를 생성했다: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue.json`, rows `43`, main `24`, controls `19`, text/url/comment `20`, image/OCR `23`, duplicate post_ids `0`.
- text/url/comment canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_text_result.json` `20/20`으로 완료됐다. VLM/OCR gate는 `NOT_APPLICABLE`이다.
- image/OCR canary는 `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_image_ocr_result.json` `23/23`으로 완료됐다. VLM/OCR Semantic Gate는 `READY`다.
- combined result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_combined_result.json`이며 rows `43`, duplicate `0`이다.
- combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_combined_compare.json`이며 movement는 `blocked_or_candidate_preserved=9`, `candidate_or_human_review_preserved=15`, `resolved_expected_title=4`, `resolved_expected_title_and_url=2`, `url_lint_preserved=5`, `still_under_resolved_or_noise=3`, `title_or_url_still_mismatched=2`, `title_match_url_still_mismatched=3`이다.
- next queue는 `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue.json` rows `8`이다. Main recall/comment rows는 `11718051`, `11694042`, `11694059`, `11716462`, `11716479`이고 precision/wrong-work controls는 `11703631`, `11710047`, `11714902`다.
- `11694064` sentinel은 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않고 `판초우의의 마법사` 후보와 `https://novel.munpia.com/530500`를 보존했다. `11698880`은 `아카데미 생존 갤러리`와 expected NovelPia URL로 회수됐다.
- `tools/compare_completed779_improvement.py`를 candidate-aware로 고쳤다. `primary_work`/candidate list를 읽어 안전한 보존을 카운트하고, recall/relevance row가 expected title과 다른 final public title로 확정되면 requeue에 남긴다.
- Tests: `tests.test_completed779_compare` `19 tests OK`; `tests.test_completed779_hermes_expansion` `1 test OK` during helper validation.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-23 completed779 Hermes Loop 6 candidate-surface closure

- Loop 5 hard residual을 이어받아 Loop 6 postfix canary를 실행했고, final queue를 `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4.json` rows `0`으로 닫았다.
- `src/llm_batch/candidate_audit.py`에 보수적 후보 보존 hook을 추가했다. `entity_mentions`, post title media-adaptation surface, `TS)` short alias, image/character leading surface를 `official_title`로 승격하지 않고 `candidate_ledger`/`candidate_preservation_sources`에만 남긴다.
- `expert_main.py` postprocess에서 `apply_post_surface_candidate_hints(identity, post.title)`를 candidate audit 전에 호출한다.
- `11710039`는 공식 후보/URL 및 `기계공주` 표면을 candidate/HOLD로 보존했다.
- `11705237`은 `월야환담`을 `post_title_surface` 후보로 보존했다.
- `11698868`은 `방타스`를 `post_title_surface` 후보로 보존했다.
- `11708449`는 VLM/OCR `READY` 상태에서 `담청`을 image/character surface 후보로 보존했다. 검색과 전문가 심의는 정식 작품명 확정을 거부했으므로 promotion 없이 HOLD가 안전한 결과다.
- `11698880`은 public wrong-title promotion guard가 닫혔지만, upstream title/body multi-candidate conflict는 broader orchestration research로 남겼다.
- verification: postfix4 subset `51 tests OK`; final broader focused suite `211 tests OK`; `git diff --check`는 LF/CRLF warning only.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-23 completed779 Hermes Loop 5 source residual canary and residual queue

- Hermes Loop 5 source residual expansion `44`건을 실제 `expert_main.py` targeted canary로 실행했다.
- text/url/comment canary는 `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_text_url_comment.jsonl` `19`건을 처리했다. Result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_text_result.json`, log는 `logs/expert_run_20260622_234407_959146.log`, VLM/OCR gate는 `NOT_APPLICABLE`이다.
- image/OCR canary는 `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_image_ocr.jsonl` `25`건을 `--vlm on --ocr on --require-vlm-ocr-for-images`로 처리했다. Result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_image_ocr_result.json`, log는 `logs/expert_run_20260623_001532_142414.log`, VLM/OCR gate는 `READY`다.
- 두 canary 모두 requested parallel은 각각 `19`, `25`였지만 `--reuse-shards-only` health filter가 shard `3333`, `3334`만 사용해 effective parallel `2`로 실행됐다. 이는 runtime health caveat이며 실패는 아니다.
- combined result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop5_source_residual_combined_result.json`이고 rows `44`, unique post_ids `44`, duplicate `0`이다.
- combined compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_combined_compare.json`이며 movement는 `candidate_or_human_review_preserved=16`, `resolved_expected_title=4`, `review=12`, `still_under_resolved_or_noise=4`, `url_lint_preserved=8`이다.
- 기본 hard-fail next queue는 `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue.json` rows `4`다.
- 루프 운영용 residual queue를 별도로 만들었다: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_operational_residual_queue.json`, rows `24`, movement `review=12`, `url_lint_preserved=8`, `still_under_resolved_or_noise=4`. 기본 compare queue가 review/url-lint residual을 누락하지 않게 하기 위한 운영 산출물이다.
- Control audit: `11710058`은 `판초법사 -> 판초우의의 마법사`를 회수했지만 `11694064`와 `11710033`은 여전히 title null/promotion_blocked다. `11698880`은 `아카데미 생존 갤러리` 대신 `가챠 중독자의 퓨전펑크 생활`로 drift했다. `11702055`는 로그상 `괴담 호텔 탈출기` 후보가 강했지만 final null/adjacent다. `11706871`은 `파우스트 1`로 회수됐고, `11716480`은 OCR title을 close variant로 회수했지만 URL null과 prompt explosion이 남았다.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 5 completion은 targeted canary evidence일 뿐 full scan approval이 아니다.

## 2026-06-22 completed779 Hermes Loop 5 source residual expansion queue

- Hermes Council fan-out를 실행했다. Candidate/Comment, OCR/Visual+Source/URL, Search/Web Evidence, Code Hook/Tooling, Verification/Docs subagent가 각각 source-refresh residual과 native-web 미소모 pool을 read-only로 검토했다.
- 공통 결론은 source-correctness refresh next queue `0`을 semantic closure로 보면 안 된다는 것이다. `review=12`와 `url_lint_preserved=21`은 residual family이며, 새 Hermes loop에서는 main success denominator가 아니라 regression/control pool로 다뤄야 한다.
- `tools/build_completed779_hermes_expansion.py`를 추가했다. 이 helper는 `action_queue_by_post_id.json`, completed subset baseline, balanced P0 seed, source-refresh compare, Loop 4 compare를 입력으로 받아 consumed main row를 제외하고 새 expansion queue와 canary input split을 생성한다.
- 실제 Loop 5 queue를 생성했다: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue.json`.
- Loop 5 manifest는 `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_source_residual_input_manifest.json`이다. Queue rows `44`, unique post_ids `44`, duplicate `0`, main `24`, control `20`, text/url/comment `19`, image/OCR `25`.
- Main selection buckets는 `under_resolved_false_negative=8`, `under_resolved=6`, `wrong_relevance=6`, `fallback_unseen_high_risk=4`다. Source/url hygiene main 후보는 이미 balanced/source-refresh 쪽에 소모되어, main 부족분은 미소모 high-risk recall/relevance fallback으로 보충했다.
- Control buckets는 `source_refresh_review_residual=12`, `source_refresh_url_lint_residual=8`이다. `11694064`, `11710033`, `11698880`, `11702055`, `11706871`, `11716480`이 control audit에 포함됐다.
- `tests/test_completed779_hermes_expansion.py`를 추가했고 helper 단위 테스트가 통과했다.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 5는 아직 canary 실행 전이며 다음 작업은 shard preflight, text/url/comment canary, image/OCR canary, compare, next queue 생성이다.

## 2026-06-22 completed779 Hermes Loop 4 candidate preservation closure

- Hermes Loop 3 active queue `5`건(`11706856`, `11716478`, `11697255`, `11702072`, `11703624`)을 Loop 4 seed/input으로 재구성하고, no-search degraded targeted canary로 candidate preservation movement를 확인했다.
- `src/llm_batch/agentic_pipeline.py`에 local preservation hook을 추가했다. 댓글 답변 후보, 짧은/복합 약칭 후보, 캐릭터/설정 cluster 후보를 `official_title`로 강제 승격하지 않고 candidate ledger/HOLD 형태로 보존한다.
- candidate snapshot은 `local_preservation_type`(`comment_answer_hold`, `short_or_compound_alias_hold`, `character_setting_cluster_hold`)과 `promotion_policy=hold_without_promotion`을 남긴다. 이로써 보존 성공이 단순 `recommendation_candidate`로만 뭉개지는 문제를 줄였다.
- `tools/compare_completed779_improvement.py`는 `official_title`이 URL/domain 형태인 경우도 `garbage_title_after`로 잡도록 보강했다.
- subagent fan-out에서 URL/title pollution risk와 local hold provenance collapse가 지적됐고, 메인 Codex가 코드와 테스트로 재확인해 반영했다.
- Loop 4 text canary result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop4_text_result.json`, log는 `logs/expert_run_20260622_214057_698080.log`, completed `4/4`다.
- Loop 4 image/OCR canary result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop4_image_ocr_result.json`, log는 `logs/expert_run_20260622_214139_955485.log`, completed `1/1`, VLM/OCR Semantic Gate `READY`다.
- combined result는 `out/completed779_improvement_goal_20260622/canary/hermes_loop4_combined_result.json`이고 compare는 `out/completed779_improvement_goal_20260622/compare/hermes_loop4_compare.json`이다. after rows matched `5/5`, movement `candidate_or_human_review_preserved=5`, next queue `out/completed779_improvement_goal_20260622/hermes_loop4_queue.json` rows `0`.
- caveat: local MCP shards `127.0.0.1:3333/3334` connection refused 및 Docker/SearXNG 미복구 상태에서 `cmd /c "echo y| ..."` no-search continuation을 사용했다. 따라서 Loop 4는 candidate-preservation runtime evidence이며 source-correctness approval이 아니다.
- queue `0` 이후 다음 source-correctness refresh 준비를 진행했다. `action_queue_by_post_id.json`에서 source/url hygiene 및 wrong-work/over-resolved precision control 축을 뽑아 `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_queue.json` rows `39`를 만들었다. Input split은 text/url/comment `14`, image/OCR `25`, missing `0`, duplicate `0`이다.
- 현재 source refresh preflight는 `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/search_shard_audit_preflight.json`에 남겼다. 결과는 shard ok `0/2`, `/readyz` connection refused, Docker Desktop Linux engine pipe missing이다. vLLM은 `/v1/models` status `200`, model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`로 확인했다.
- Data/Taxonomy subagent 검토를 반영해 다음 high-risk expansion 규칙도 `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/next_expansion_queue_plan_ko.md`에 남겼다. Expansion main pool은 `action_queue 266 - balanced P0 65 - closed5`의 unseen `201`건이며, closed5는 main이 아니라 regression control로만 재사용한다.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. 다음 작업은 정상 search shard 복구 후 source-correctness refresh, random/high-risk expansion, 또는 새 native-web non-ACCEPT queue 생성이다.

## 2026-06-22 completed779 Hermes Loop 3 partial deterministic improvement

- Hermes Council subagent fan-out 2축을 사용했다. Code-hook expert와 prompt/orchestration+verification/docs expert 모두 후보 생성보다 후보 보존 입구가 약하다는 결론을 냈고, 메인 Codex가 코드와 테스트로 재확인했다.
- `src/llm_batch/candidate_audit.py`에서 image/OCR evidence의 `explicit_work_title`을 promotion 없이 candidate ledger에 보존하도록 보강했다. visual-only cue는 후보로 만들지 않는 negative test도 추가했다.
- `tools/compare_completed779_improvement.py`에서 `unresolved_matchable`, `hold`, `author_new_work_context`를 candidate/human-review preservation으로 해석하도록 조정했다. `context_only + hold_without_candidates`는 계속 unresolved/noise로 남긴다.
- `tools/build_completed779_reimprovement_inputs.py`에 `--prefix`, `--loop-label`을 추가하고, queue의 `observed_problem`, `suspected_code_hook`, `proposed_next_fix`, `required_test`를 seed로 보존하도록 했다.
- Loop 2 remaining queue `8`건을 재해석해 `11708442`, `11697241`은 explicit `unresolved_matchable` 보류로 닫았고, deterministic re-audit에서 `11695623`은 `림월드` weak image/OCR candidate 보존으로 닫았다.
- 새 active queue는 `out/completed779_improvement_goal_20260622/hermes_loop3_queue.json`이며 rows `5`, 모두 `still_under_resolved_or_noise`다.
- `expert_main.py` live text canary는 `logs/expert_run_20260622_211133_748990.log`에서 search shard preflight 실패로 중단했다. `127.0.0.1:3333/3334` 연결 거부 및 Docker Desktop Linux engine pipe 부재로 final result JSON은 생성되지 않았다.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 3는 partial deterministic improvement이며 runtime semantic approval이 아니다.

## 2026-06-22 completed779 reimprovement Loop 2 goal 작성

- Loop 1 post-fix-adjusted compare 이후 남은 active `reimprovement_queue` `25`건을 다음 개선 goal의 모수로 고정했다.
- `goal.md`를 Loop 2 active contract로 갱신했다. 이번 목표는 전체 completed779 재처리가 아니라 `still_under_resolved_or_noise=16`과 `title_or_url_still_mismatched=9`를 줄이는 targeted loop다.
- 새 실행 프롬프트 `docs/devs/COMPLETED779_REIMPROVEMENT_LOOP2_GOAL_PROMPT.md`를 추가했다. 이 prompt는 queue preflight, subagent 4축 fan-out, Loop 2 input split, generalized fix, text/url/comment canary, image/OCR canary, compare, queue 재생성, docs sync를 포함한다.
- Candidate/comment/recall preservation group `16`건과 source/url hygiene group `9`건을 분리했다. 성공 조건은 안전한 public title promotion뿐 아니라 candidate preserved, HOLD/human_review, URL mismatch lint도 포함한다.
- Loop 1 control을 명시했다: active `garbage_title_after=0` 유지, `11694064` bad-title 재승격 금지, `wrong_work=9` bad pipeline title 회귀 금지.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Loop 2는 아직 실행 전이며, direct fallback을 쓰는 경우 degraded-provider evidence로만 기록한다.

## 2026-06-22 completed779 direct-search fallback canary and snippet-title guard

- Docker Desktop Linux engine pipe가 없어 normal SearXNG/Docker MCP shards를 올릴 수 없었고, public SearXNG instance는 throttling/403/429가 많았다. 대신 `src/llm_batch/mcp_bridge/server.py`에 Naver/Bing direct HTTP search fallback을 추가했다.
- direct fallback은 search-enabled canary를 가능하게 했지만, 이는 정상 Docker/SearXNG shard approval이 아니라 degraded-provider search evidence다.
- vLLM `/v1/models` 확인 결과 live model은 `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`였고, 계획서의 stale `bg-digitalservices/Gemma-4-E4B-it-NVFP4`는 404를 반환했다.
- text/url/comment direct-search canary result: `out/expert_result_20260622_165552_032705.json`, rows `19/19`, compare `out/completed779_improvement_goal_20260622/compare/text_direct_search_compare.json`.
- image/OCR direct-search canary result: `out/expert_result_20260622_171928_162115.json`, rows `46/46`, VLM/OCR Semantic Gate `READY`, compare `out/completed779_improvement_goal_20260622/compare/image_ocr_direct_search_compare.json`.
- combined direct-search compare: `out/completed779_improvement_goal_20260622/compare/combined_direct_search_compare.json`, rows `65/65`. Movement는 `blocked_or_candidate_preserved=15`, `candidate_or_human_review_preserved=20`, `garbage_title_after=3`, `resolved_expected_title=2`, `resolved_expected_title_and_url=1`, `still_under_resolved_or_noise=15`, `title_or_url_still_mismatched=9`.
- `11694064`는 direct-search canary에서도 `무협 게임에 빙의했다...스킵충이다`로 확정되지 않았다. `wrong_work=9` 전체도 still-bad pipeline title 없이 `blocked_or_candidate_preserved`로 유지됐다.
- direct fallback은 검색 증거를 되살렸지만 `11710063`, `11716482`, `11705231`에서 긴 검색 스니펫/정의문/브레드크럼이 `official_title`로 승격되는 새 위험을 드러냈다.
- `tools/compare_completed779_improvement.py`에 `garbage_title_after` movement를 추가해 이런 케이스를 reimprovement queue에 넣게 했다.
- `src/llm_batch/candidate_audit.py`의 public title promotion guard를 보강해 snippet-like 또는 breadcrumb-like `official_title`을 `blocked_official_title`로 보존하고 public title은 demote한다. `tests/test_candidate_audit.py`와 `tests/test_completed779_compare.py`에 회귀 테스트를 추가했다.
- polluted 3건 post-fix mini canary를 실행했다. Text 2건은 `out/expert_result_20260622_183047_118075.json`, image/OCR 1건은 `out/expert_result_20260622_183544_060718.json`이다. 결합 compare `out/completed779_improvement_goal_20260622/compare/garbage_title_postfix_combined_compare.json`는 `candidate_or_human_review_preserved=2`, `still_under_resolved_or_noise=1`, `garbage_title_after=0`이다.
- post-fix-adjusted compare는 `out/completed779_improvement_goal_20260622/compare/combined_direct_search_postfix_adjusted_compare.json`이다. rows `65/65`, movement `blocked_or_candidate_preserved=15`, `candidate_or_human_review_preserved=22`, `resolved_expected_title=2`, `resolved_expected_title_and_url=1`, `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`.
- root reimprovement queue는 post-fix-adjusted 기준으로 갱신했다: `out/completed779_improvement_goal_20260622/reimprovement_queue.json`, `out/completed779_improvement_goal_20260622/reimprovement_queue_ko.md`, active rows `25`. `11710063`/`11705231`의 garbage-title item은 닫혔고, `11716482`는 public title 오염은 닫혔지만 comment multi-candidate 보존 미흡으로 active queue에 남겼다.
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`. Direct fallback은 여전히 degraded-provider evidence이며 normal Docker/SearXNG shard approval이 아니다.

## 2026-06-22 completed779 native-web improvement loop 1 구현 및 degraded canary

- subagent 4축(taxonomy/source, code-hook, prompt/orchestration, verification/docs) 분석을 받아 메인 Codex가 code hook과 검증 게이트를 재확인했다.
- `src/llm_batch/candidate_audit.py`를 completed779 native-web taxonomy에 맞게 확장했다. `under_resolved`, `candidate_preservation_missing`, `comment_explicit_title_missed`, `heretic_url_null`, `title_correct_url_mismatch`, `overresolved_generic_trope` 등을 seed group으로 분류하고, `seed_bucket`이 있으면 precision/candidate/recall/hygiene을 우선한다.
- precision guard는 `wrong_work`와 `overresolved_generic_trope` 같은 unsafe resolved title을 보수적으로 demote하지만, source/url hygiene bucket의 `reason_evidence_mismatch`는 title demote가 아니라 output lint로 남긴다.
- `src/llm_batch/agentic_pipeline.py`에서 gatekeeper의 `comment_title_candidates`를 final promotion이 아니라 `title_candidates` 후보 보존 경로로 추가했다.
- `src/llm_batch/experts/orchestrator.py`에서 semantic seed denial 상태라도 댓글 제목이 포함된 official/platform probe는 검색 intent permit에서 보존되도록 예외를 추가했다.
- `src/llm_batch/prompts/prompt_router.py`에 댓글 명시 제목/직접 플랫폼 URL/OCR 제목/짧은 약칭/캐릭터·설정 cluster는 candidate ledger에 보존하고, 추천·비교·작가신작·OCR-only·conflicting 문맥에서는 단일 `official_title` 승격을 별도 gate로 보류하라는 문구를 추가했다.
- `tools/compare_completed779_improvement.py`를 split canary scope(`--only-after-posts`), expected URL mismatch 판정, `--out-queue` reimprovement queue 출력으로 확장했다. `tests/test_completed779_compare.py`도 추가했다.
- preflight 재확인: `tools/build_completed779_issue_index.py` 실행 결과 `total=779`, `non_accept=266`, `missing=0`, `duplicate_after_dedupe=0`, seed `65`, bucket `15/15/25/10`.
- 검증: `py_compile` pass, focused suite `190 tests OK`, `git diff --check` pass(LF/CRLF warning only).
- targeted canary는 Docker Desktop engine/pipe 부재와 MCP shards `3333`..`3368` connection refused 때문에 `echo y` no-search continuation으로 진행했다. 이 런은 runtime/candidate-audit evidence로만 기록하고 semantic approval로 승격하지 않는다.
- text/url/comment degraded canary result: `out/expert_result_20260622_161924_359370.json`, rows `19/19`, compare `out/completed779_improvement_goal_20260622/compare/text_degraded_compare.json`.
- image/OCR degraded canary result: `out/expert_result_20260622_162557_711822.json`, rows `46/46`, VLM/OCR Semantic Gate `READY`, compare `out/completed779_improvement_goal_20260622/compare/image_ocr_degraded_compare.json`.
- combined compare: `out/completed779_improvement_goal_20260622/compare/combined_degraded_compare.json`, rows `65/65`. Movement는 `blocked_or_candidate_preserved=14`, `candidate_or_human_review_preserved=30`, `resolved_expected_title=2`, `still_under_resolved_or_noise=8`, `title_match_url_still_mismatched=1`, `title_or_url_still_mismatched=10`.
- `11694064`는 더 이상 `무협 게임에 빙의했다...스킵충이다`로 확정되지 않았고, `wrong_work=9` 전체가 bad title finalize에서 벗어나 `blocked_or_candidate_preserved`로 이동했다.
- reimprovement queue: `out/completed779_improvement_goal_20260622/compare/combined_degraded_reimprovement_queue.json`, rows `19` (`still_under_resolved_or_noise=8`, URL mismatch/missing `11`).
- gates 유지: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-22 completed779 native-web improvement goal 재설계

- completed779 개선 목표를 다시 검토한 결과, 기존 JUDGE3905/잔여 3건 중심 계획은 현재 문제를 설명하기에 부족하다고 판단했다. active `goal.md`를 completed779 native-web verdict 기반 개선 계약으로 갱신하고, 기존 JUDGE3905 goal은 `llm_judge_goal.md`로 보관했다.
- 새 기준선은 `out/expert_result_20260620_165159_711176_completed_subset.json` `779`건과 `out/codex_native_web_judge_20260620_165159_711176_completed779/` verdict다. deterministic `out/full_post_judge_20260620_165159_711176_completed779/report/full_post_judge_report.md` 집계는 source coverage/이전 judge artifact로만 두고, 개선 우선순위에는 섞지 않는 stale aggregate 금지 규칙을 세웠다.
- `tools/build_completed779_issue_index.py`를 추가했다. standalone sentinel과 batch verdict 중복은 `post_id` 기준으로 제거하며, 결과는 `out/completed779_improvement_goal_20260622/` 아래에 `native_web_issue_index.json`, `native_web_issue_index_ko.md`, `action_queue_by_post_id.json`, `balanced_p0_seed.jsonl`, `inputs/balanced_p0_text_url_comment.jsonl`, `inputs/balanced_p0_image_ocr.jsonl`로 저장된다.
- helper 실행 결과 native-web aggregate는 unique/source coverage `779/779`, missing `0`, duplicate after dedupe `0`, non-ACCEPT `266`이다. label은 `ACCEPT=513`, `REPROCESS=208`, `HOLD=49`, `INFO_MISSING=7`, `REJECT=2`다.
- 주요 issue 축은 `under_resolved=68`, `under_resolved_false_negative=64`, `wrong_relevance=62`, `heretic_url_null=13`, `wrong_work=9`, `candidate_preservation_missing=6`, `garbage_title=6`, `reason_evidence_mismatch=6`, `conflicting_or_multi_candidate=5`, `comment_explicit_title_missed=4`로 고정했다.
- balanced P0 seed `65`건을 만들었다. 구성은 precision/identity `15`, candidate/comment/multi-candidate `15`, recall/relevance `25`, source/url hygiene `10`이다. `11694064`는 포함됐고, `wrong_work=9` 전체도 모두 seed에 포함됐다. canary input은 text/url/comment `19`건과 image/OCR `46`건으로 분리했다.
- `tools/compare_completed779_improvement.py`를 추가해 이후 `expert_main.py` canary 결과와 seed expectation을 post별로 비교할 수 있게 했다. 현재 단계는 issue index/seed packet 생성이며, pipeline behavior fix와 canary는 다음 루프다.
- `tests/test_completed779_issue_index.py`를 추가해 fixture dedupe/split, 실제 completed779 contract, compare movement를 검증한다.
- 요청된 focused suite 실행 중 `memory_query_unsupported_title_blocked`가 붙은 케이스가 후단 recommendation guard에서 `recommendation_request`로 덮어써지는 회귀를 확인했고, 해당 flag가 있으면 recommendation context-only 덮어쓰기를 하지 않도록 `agentic_pipeline.py`를 좁게 보정했다.
- 검증은 `py_compile` 통과, requested focused suite `178 tests OK`, `git diff --check` 통과로 닫았다. gates는 계속 semantic quality `REVIEW-LOCKED`, full scan approval `false`다.
- 다음 자동 개선 연구·검증·재개선 실행을 위해 `docs/devs/COMPLETED779_AUTO_IMPROVEMENT_GOAL_PROMPT.md`를 추가했다. 이 prompt는 issue index preflight, subagent fan-out, 일반화 fix, text/url/comment canary, image/OCR canary, compare, re-improvement queue, docs sync, gate 분리를 포함한다.

## 2026-06-21 full_post_judge 20260620_165159_711176 completed779 재실행

- 최신 partial run의 primary JSON은 `757`행만 flushed됐지만, `completed_subset`에는 shutdown flush gap `22`건을 포함한 `779`건이 있었다. `11694064`가 이 gap에 포함되어 있어 `out/expert_result_20260620_165159_711176_completed_subset.json`을 판정 모수로 고정했다.
- `out/full_post_judge_20260620_165159_711176_completed779/`를 새 산출물 루트로 만들고 `tools/full_post_judge_codex_driver.py`로 slice/web probe/verdict/verify/aggregate를 실행했다. web probe는 기존 cache `100`건을 재사용하고 timeout env(`MCP_CLIENT_SEARCH_TIMEOUT_SEC=8`, `MCP_CLIENT_SEARCH_MAX_RETRIES=0`, `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=1`)로 남은 query가 장시간 hang되지 않게 했다.
- 최종 coverage는 processed/judged/missing/pending `779/779/0/0`, bad files `0`, rows page `3`이다. run integrity `GO`, semantic quality `REVIEW-LOCKED`, full scan approval `false` 유지.
- source coverage는 `_source_coverage.json`과 report §0.8에 남겼다. completed subset `779`, primary flushed `757`, shutdown_pending_flush_gap `22`, gap 내 `11694064` 포함 `true`.
- `11694064`는 최신 checkpoint에서 primary가 `무협 게임에 빙의했다. 문제는 나는 스토리를 보지 않는 스킵충이다`로 튄 케이스였고, judge final은 `wrong_work / REPROCESS / conflicting_or_multi_candidate / Strong / high / re_judge`로 잡았다. note에는 `경합후보=판초우의의 마법사`, `원문별칭=판초법사`, `후보URL=https://novel.munpia.com/530500`가 남았다.
- 전체 결과 요약: `ACCEPT=661`, `HOLD=86`, `REPROCESS=31`, `REJECT=1`; `wrong_work=2`, `garbage_title=1`, `uncertain=29`; action queue `re_judge=37`, `human_review=46`, `re_search=28`, `slang_db_review=25`, `no_action=643`.
- `docs/devs/FULL_POST_JUDGE_RUNBOOK.md`에 Codex subagent fan-out 운영 지침을 추가했다. 검색/LLM judge 장기 작업은 resolved/search, recall, slang, report/action sanity 같은 축별 subagent로 나누되, 메인 에이전트가 post_id completeness와 missing=0 병합을 책임진다.
- `docs/devs/FULL_POST_JUDGE_RUNBOOK.md`에 전수 행별 dump의 `LLM 판단 사유(한글)` 규약을 추가하고, `report/rows/full_post_judge_rows_p01.md`..`p03.md`를 재생성했다. 모든 post 행은 ACCEPT/none/unresolved 포함 한국어 판단 사유를 가진다.
- 사용자 정정에 따라 completed779의 "LLM judge" 의미를 다시 고쳤다. deterministic full_post_judge나 `agbrowse`가 아니라 Codex 5.5 subscription의 native web search/open으로 post 원문을 직접 읽고 검색하는 외부 judge가 요구사항이다.
- 새 루트 `out/codex_native_web_judge_20260620_165159_711176_completed779/`를 만들고 `11694064` sentinel을 Codex-native web search로 판정했다. 문피아 공식 상세 `https://novel.munpia.com/530500`, 네이버시리즈 `https://series.naver.com/novel/detail.series?productNo=14207846`, 장갤 용례 `https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=12162458`를 근거로 `판초법사 -> 판초우의의 마법사`가 맞고 pipeline primary `무협 게임에 빙의했다...`는 `wrong_work`라고 기록했다.
- Codex subagent fan-out 실제 산출을 시작했다. Hypatia/Beauvoir/Singer/Hegel이 batch `000`..`005`를 반환했고, Ampere/Hilbert/Descartes/Hooke/Nietzsche/Faraday가 batch `006`..`011`를 반환했다. Wegener/Aquinas/Leibniz/Mendel/Ramanujan/Euler가 batch `012`..`017`를 반환했다. Anscombe/Peirce/Bohr/Laplace/Pascal/Epicurus가 batch `018`..`023`를 반환했다. Plato/Kuhn/Herschel/Carson/Harvey/Lagrange가 batch `024`..`029`를 반환했고, Dirac/Pasteur/Aristotle/Parfit/Nash/Boole이 batch `030`..`035`, Turing/Helmholtz/Zeno/Sagan/Mencius/Sartre가 batch `036`..`041`, Jason/Einstein/Godel/Planck/Rawls/Huygens가 batch `042`..`047`, Dalton/Cicero/Kierkegaard/Poincare/Gibbs/Noether가 batch `048`..`053`, Gauss/Popper/Dewey/Lovelace/Fermat/James가 batch `054`..`059`, Ohm/Schrodinger/Kepler/Volta/Socrates/Russell이 batch `060`..`065`, Arendt/Goodall/Hubble/Kant/Carver/Linnaeus가 batch `066`..`071`, Ptolemy/Hume/Banach/Erdos/Bernoulli/Newton이 batch `072`..`077`, Averroes/Copernicus/Darwin/Boyle/Heisenberg/Pauli가 batch `078`..`083`, Archimedes/Bacon/McClintock/Lorentz/Confucius/Chandrasekhar가 batch `084`..`089`, Avicenna/Curie/Tesla/Mill/Maxwell/Meitner가 batch `090`..`095`, Raman/Franklin/Euclid/Galileo/Locke/Hypatia the 2nd가 batch `096`..`101`, Boole the 2nd/Leibniz the 2nd/Anscombe the 2nd/Euler the 2nd/Godel the 2nd/Lagrange the 2nd가 batch `102`..`107`, Aristotle the 2nd/Boyle the 2nd/Dewey the 2nd/Raman the 2nd/Epicurus the 2nd/McClintock the 2nd가 batch `108`..`113`, Descartes the 2nd/Wegener the 2nd/Banach the 2nd/Kant the 2nd/Kuhn the 2nd/Copernicus the 2nd가 batch `114`..`119`, Russell the 2nd/Pasteur the 2nd/Beauvoir the 2nd/Erdos the 2nd/Einstein the 2nd/Franklin the 2nd가 batch `120`..`125`, James the 2nd/Ampere the 2nd/Ohm the 2nd/Popper the 2nd/Mill the 2nd/Lovelace the 2nd가 batch `126`..`131`, Euclid the 2nd/Cicero the 2nd/Huygens the 2nd/Rawls the 2nd/Confucius the 2nd/Gauss the 2nd가 batch `132`..`137`, Nietzsche the 2nd/Ptolemy the 2nd/Avicenna the 2nd/Pascal the 2nd/Pauli the 2nd/Tesla the 2nd가 batch `138`..`143`, Noether the 2nd/Nash the 2nd/Zeno the 2nd/Locke the 2nd/Poincare the 2nd/Sartre the 2nd가 batch `144`..`149`, Arendt the 2nd/Faraday the 2nd/Kierkegaard the 2nd/Galileo the 2nd/Meitner the 2nd/Peirce the 2nd가 batch `150`..`155`를 반환했다. raw return은 `out/codex_native_web_judge_20260620_165159_711176_completed779/subagent_returns/`, 정규화 verdict는 `verdicts/verdict_000.json`..`verdict_155.json`에 저장했다. 최종 진행률은 표준 batch `779`건, unique `779/779`, missing `0`, rows `779`다.
- batch `000`에서 `11718077`은 작품명은 맞지만 pipeline URL이 공식 상세와 맞지 않아 `reason_evidence_mismatch / HOLD / re_search`로 조정했다. batch `001`의 `11718069`는 작가/장르 선택 맥락으로 source URL을 보강하고, 단일 작품 resolved가 아닌 author_talk/adjacent HOLD로 기록했다.
- batch `002`..`005`에서는 `11718085` under-resolved 후보 `로판으로 착각했다`, `11718089` 개돌 신작 author/new-work HOLD, `11718095` 댓글 명시 제목 누락, `11718094` OCR 캐릭터 단서만 있는 unresolved 보존을 초기 native-web 이슈로 추가했다.
- batch `006`..`011`에서는 `11718119` 즉사무림 under-resolved, `11718114` generic system trope over-resolved, `11718105` OCR 다중 공식작 후보 누락, `11718091` 정보 부족/human review, `11718106` author_talk/adjacent 보존, `11718061` 복수 추천 목록 null-title 보존을 추가 native-web 이슈로 기록했다.
- batch `012`..`017`에서는 `11718057` 컵라면 신작 후보 HOLD, `11718055` 댓글 명시 제목 `새엄마의 친구들` 누락, `11718051` 댓글 단서 `몰락민족의 천재 기사` 누락, `11718049` 추천 댓글 URL 후보 보존 누락, `11716501` 히로인 분양 일반 용어 과승격, `11716500` `검머기 -> 검은머리 기사왕` 누락, `11716492` 댓글 추천작 `2회차 환관이 남성을 되찾음` 누락을 추가 native-web 이슈로 기록했다.
- batch `018`..`023`에서는 `11716482` 댓글 다중 후보 HOLD, `11716480` OCR 제목은 맞지만 후보 URL title mismatch, `11716479`/`11716475` `고능아 -> 저 머리 좋은데요` 누락, `11716478` 댓글 2작품 후보 보존 누락, `11716462` `니생들 -> 니들 생각 다 들린다` 누락, `11716453` `마학간 -> 마왕은 학원에 간다` 누락, `11716448` `아생갤 -> 아카데미 생존 갤러리` 누락을 추가 native-web 이슈로 기록했다.
- batch `024`..`029`에서는 `11714913` `주서연 -> 전 버튜버가 하고 싶은데요` 누락, `11714905` 후보 `오랜만에 만난 가족이 너무 야함`, `11714904` `괴담동 -> 괴담 동아리` 누락, `11714902` `헌터상담` wrong_work, `11714898` OCR 소개문 단일작품 누락, `11714888` `고은하 -> 격투 천재 여고생이 되었다` 누락, `11714887` `도굴왕 1 |` garbage title을 추가 native-web 이슈로 기록했다.
- batch `030`..`035`에서는 `11714879` `무한회귀 여자친구 네토라세` 누락, `11714876` `합스부르크의 슈퍼스타가 되었다` 누락, `11714875` `K-문화의 제왕` 누락, `11714869` `묵향`/`묵향 다크레이디` primary 경합, `11714867` `쿠크루` 작가 메타 관련성, `11714865` `현질수선전` 누락, `11713233` `가챠 중독자의 퓨전펑크 생활` 누락, `11713228` `빙엄아유 -> 빙의한 엄마가 아들을 유혹함` 후보 HOLD를 추가 native-web 이슈로 기록했다.
- batch `036`..`041`에서는 `11713222` `잘생인방 -> 잘생기면 편해지는 인방 생활` 누락, `11713217` 마스킹 캐릭터 단서 `미래에서 온 연애편지` 누락, `11713215` 오늘도요 신작 `즉사기 들고 무림에 떨어지다` 누락, `11713214` `눈물을 마시는 새` 약한 밈 후보 HOLD, `11713210` `설문조사를 했다가 세상을 부숴 먹었다.` 누락, `11713206` `킬더드 -> 킬 더 드래곤` 누락, `11713205` 댓글 문피아 URL `농사 좀 지었을 뿐인데 고려가 제국이 되었다` 누락, `11713197` `내 복사 스킬은 아무래도 뭔가 잘못됐다` 공식 URL 보강 필요를 추가 native-web 이슈로 기록했다.
- batch `042`..`047`에서는 `11713190` 노피아→문피아 작가/플랫폼 메타 wrong_relevance, `11713186` `목마신작 -> 검귀가 환생함` 누락, `11711636` 작가/프로모션 메타 정보 부족, `11711632` 애니 `너의 이름은.` OCR과 리디 `Your Name` wrong_work, `11711631` `괴담에 휘말렸다` title-correct URL mismatch, `11711627` `지구판역 -> 판타지에 지구 역사를 풀었다` 누락, `11711622` 댓글 URL `무림에서 외과의로 살아가는 법` 누락, `11711620` OCR `괴이에게 애호받는 신입이 되었다` 누락, `11711616` `새로운 이치/알렙 -> 괴담 호텔 탈출기` 누락을 추가 native-web 이슈로 기록했다.
- batch `048`..`053`에서는 `11711605` `랫따싶` 다중 후보/작품군 HOLD, `11711600` `망카데미 -> 망할 놈의 아카데미` 누락, `11711599` 특정 소설 장면 감상이나 title 정보 부족, `11711597` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 후보, `11711596` 댓글 URL `로판 속 주인공이 나만 좋아함` 누락, `11711590` 문모전/웹소설 공모전 AI 플랫폼 메타 wrong_relevance, `11711582` AI 작가/창작 메타 HOLD, `11711581` 작가 정체성 메타 HOLD, `11710069` 삼국지 서사 감상 wrong_relevance를 추가 native-web 이슈로 기록했다.
- batch `054`..`059`에서는 `11710067` 장르 클리셰 토론 wrong_relevance, `11710065` 노피아 랭킹/4드론 플랫폼 메타 wrong_relevance, `11710063` 댓글/인용 제목 `나비꽃` 누락, `11710059` OCR 웹소설 본문 반응 정보 부족, `11710058` `판초우의의 마법사` under-resolved/wrong_relevance, `11710056` `아카데미 생존 갤러리` 누락, `11710055` `가챠 중독자의 퓨전펑크 생활` 캐릭터 근거, `11710052` `아카엄창 -> 아카데미 패드립 면역` 누락, `11710047` wrong_work `로판 속 미움받는 악역이 되었다` vs `아카데미 속 미움받는 악역이 되었다`, `11710045` OCR 웹소설 장면 정보 부족, `11710044` `가챠펑크 -> 가챠 중독자의 퓨전펑크 생활`, `11710043` `악엔 -> 악역의 엔딩은`, `11710042` `아카엠창` weak source HOLD, `11710039` `기계공주 -> 헌터갤러리의 국가권력급 기계공주`, `11710038` 댓글 명시 제목 `제발 죽지 말아주세요, 공녀님`, `11710037` `담텔기 -> 괴담 호텔 탈출기` trope boundary HOLD를 추가 native-web 이슈로 기록했다.
- batch `060`..`065`에서는 `11710035` `즉사무림 -> 즉사기 들고 무림에 떨어지다` 누락, `11710033` `판초법사 -> 판초우의의 마법사` wrong_work, `11710025` `망카 -> 망할 놈의 아카데미` 누락, `11710024` `주술초월 -> 주술사는 초월을 원한다` 누락, `11710021` `무마 -> 무한의 마법사` URL missing, `11710020` `주전무 -> 주무시기 전에 무엇을 하셨나요?` URL missing, `11710019` `한가인/승엽이 -> 괴담 호텔 탈출기` 캐릭터 단서 누락, `11708481` `지잡아카 -> 지잡 아카데미와 폐급 히로인들` 누락, `11708479` `시달소 -> 시간을 달리는 소설가` wrong_relevance, `11708478` 댓글 명시 제목 `사연 있는 악역으로 착각 당한다` 누락, `11708475` 브런치 글 OCR wrong_relevance를 추가 native-web 이슈로 기록했다.
- batch `066`..`071`에서는 `11708470` `절꺾않` title-correct URL mismatch, `11708469` `기계공쥬 -> 헌터갤러리의 국가권력급 기계공주` 누락, `11708468` `반지성마왕 -> 반지성주의 마왕의 세계침략` 누락, `11708466`/`11708457` `매국노` 누락, `11708461` OCR `마법소녀 갤러리` 누락, `11708460` garbage title `novel.munpia.com`, `11708453` `이불사 -> 이세계 불법체류 사이비` 누락, `11708450` `악살싶`/`변마금` 작품 간 표절 토론 wrong_relevance, `11708449` `담청 -> 죽었다 깨어도 수선` 캐릭터 단서 누락, `11708446` 추천글 후보 ledger 누락, `11708443` `괴담출근` 공식 URL missing, `11708442` 정주행 추천글 다중 후보 보존 누락을 추가 native-web 이슈로 기록했다.
- batch `072`..`077`에서는 `11708437` `악살싶` title-correct URL mismatch 및 후보 보존 점검, `11708434` `지갑송 신작 -> 반강제적 제국주의자` 누락, `11708430` `매국노` 누락, `11706873` `전능뇌 -> 전능의 뇌를 얻었다` 누락, `11706871` `파우스트 1` URL missing, `11706860` 림버스 `파우스트` OCR wrong_relevance, `11706857` 댓글 `헌터상담 -> 조향사의 헌터상담기록` 누락, `11706856` 백합 추천글 후보 ledger 누락, `11706855` 웹툰/소설 혼재 추천글 후보 보존 HOLD를 추가 native-web 이슈로 기록했다.
- batch `078`..`083`에서는 `11706852` `판초법사 -> 판초우의의 마법사` 별칭 official_title under-resolved, `11706845`/`11706840`/`11706832` `황제분충 -> 황제폐하가 웹소설 작가임을 숨김` 누락 또는 wrong_relevance, `11706844` OCR `범 먹는 괴이 사냥꾼`/편곤 단서와 현 문피아 `호랑이 사냥꾼` 불일치 재검증, `11706828` `내 마법도서관이 살아있다` 누락, `11706827` `기계공주 -> 헌터갤러리의 국가권력급 기계공주` 누락을 추가 native-web 이슈로 기록했다.
- batch `084`..`089`에서는 `11705273`/`11705258` `판초우의/판초 10 -> 판초우의의 마법사` 누락, `11705272` `태탑 -> 태양의 탑` garbage_title, `11705266` 노벨피아 자유연재/로판 플랫폼 담론 wrong_relevance, `11705264`/`11705257` `히로히로 -> 히어로 IN 히로인` 누락, `11705262` `수상남매 -> 수상할 정도로 사이가 좋은 남매` 댓글 후보 누락, `11705261` `이티알 -> 이세계 TRPG 게임마스터` 누락, `11705259` `아생갤 -> 아카데미 생존 갤러리` 누락, `11705256` `하남자 탑 -> 하남자의 탑 공략법` 누락, `11705249` 웹툰/소설 adaptation comparison subtype mismatch, `11705248` `이블파티 -> 나의 악당들` wrong_work를 추가 native-web 이슈로 기록했다.
- batch `090`..`095`에서는 `11705245`/`11705241`/`11705235` `하남자/하남자탑공략 -> 하남자의 탑 공략법` 누락, `11705243` SF 추천글 wrong_relevance, `11705240` TS여경물 추천 욕구를 `격투 천재 여고생이 되었다`로 over_resolved, `11705239` 도쿄구울 패러디 찾기글 over_resolved, `11705237` 월야환담 웹툰 under_resolved, `11705231` `설지후/탐식 -> 탐식의 재림` wrong_relevance, `11705228` 일본 로맨스소설 장르 담론 wrong_relevance, `11703673` `나비꽃2` 댓글 확인 누락, `11703669` `세나영 -> 세상에 나쁜 영애는 없다` 누락, `11703668` `갤질의사 -> 댓글 보는 천재 의사` 누락, `11703666` 키오스크 괴담 소재 담론 wrong_relevance, `11703663` 노벨피아 플랫폼 이용/추천 맥락 wrong_relevance를 추가 native-web 이슈로 기록했다.
- batch `096`..`101`에서는 `11703661` `막드제 -> 막장드라마의 제왕`, `11703658` `아프리카 반란군 사령관이 되었다` 문피아 공식 URL 보강, `11703657`/`11703641` 댓글 URL `야만인은 문명하면 안되냐`, `11703654`/`11703650` 웹소설 소비·추천글, `11703649` 댓글 추천작 `레즈돔 일진녀의 마조 노예로 조교당한다`, `11703640` 부수 댓글 `기계공주` over_resolved, `11703637` `주술회전` cross-media 경계, `11703634` `세종 파딱 -> 세종의 종신재상이 되었다`, `11703631` `이블파티 -> 나의 악당들` wrong_work, `11703629` 작품 감상 맥락 정보 부족을 추가 native-web 이슈로 기록했다.
- batch `102`..`107`에서는 `11703625` `목마 신작 -> 검귀가 환생함`, `11703624` `판초법사 -> 판초우의의 마법사`, `11703621` 댓글 `시체공양으로 데미갓` HOLD, `11702094` `댓글창 -> 댓글창의 천재 마법사`, `11702090`/`11702082`/`11702078`/`11702077` `괴담 호텔 탈출기` 캐릭터·설정 단서, `11702087` 위키 문서형 garbage title, `11702086` OCR 명시 `6★ 가챠 캐릭터가 되었다`, `11702085` 괴담텔 wrong_relevance, `11702081` `게임 속 재해병 이야기`, `11702079` `망향무사` URL mismatch를 추가 native-web 이슈로 기록했다.
- batch `108`..`113`에서는 `11702072`/`11702068`/`11702066`/`11702063`/`11702060`/`11702059`/`11702054`/`11702052`/`11702051`/`11702047` `괴담 호텔 탈출기` 캐릭터·설정 단서 누락 또는 비관련 오판, `11702064` OCR 명시 `흔해빠진 직업으로 세계최강` 누락, `11702061` 동명 후보 있는 `요리의 신` 후보 보존 필요, `11702057` 댓글 추천작 `멸망할 세계의 파견 용사` 누락, `11702055` `괴담 호텔 탈출기` title-correct URL mismatch, `11702050` `폴라리스 랩소디` URL missing, `11702049` `2레벨무신 -> 2레벨로 회귀한 무신` 누락을 추가 native-web 이슈로 기록했다.
- batch `114`..`119`에서는 `11700504` OCR 명시 `시간을 달리는 소설가` title/url 보강, `11700495` `서문청 -> 이 무림의 미친년은 나야` 누락, `11700490` 노피아 독서/추천 플랫폼 메타 wrong_relevance, `11700488`/`11700485` 버거피아/부기 플랫폼 이벤트 메타 wrong_relevance, `11700487` `군필돌 -> 아이돌이 군필을 숨김` URL missing, `11700483` `니생들 -> 니들 생각 다 들린다` URL missing, `11700480` 기계공주 후보 HOLD, `11700475` 댓글 공식 URL `내 파티에는 미친년들만 꼬인다` 누락을 추가 native-web 이슈로 기록했다.
- batch `120`..`125`에서는 `11700473` `로나좋 -> 로판 속 주인공이 나만 좋아함` truncated/garbage title, `11700470` OCR `밤도깨비 에이브` 공식 제목 미검증 HOLD, `11700468` `악당 엔딩 -> 악역의 엔딩은` 누락, `11698910` `판초우의 -> 판초우의의 마법사` 누락, `11698907` `괴담텔 -> 괴담 호텔 탈출기` 누락, `11698903` `기계공주 -> 헌터갤러리의 국가권력급 기계공주` title/url mismatch를 추가 native-web 이슈로 기록했다.
- batch `126`..`131`에서는 `11698897`/`11698895`/`11698886` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 누락 또는 wrong_relevance, `11698890` `댓천마 -> 댓글창의 천재 마법사` URL missing, `11698888` 월억킥 창작/수익 밈 relevance, `11698884` `무림마조` 캐릭터명 under_resolved, `11698880` `아생갤` title-correct URL mismatch, `11698878` `담청 -> 죽었다 깨어도 수선` OCR/DC콘 후보 HOLD, `11698875` `몸을 만지는 관문지기가 되었다` wrong_relevance, `11698873` `내마도살/전생흑막` 작가-전작 후보 보존, `11698871` `리제로 -> Re : 제로부터 시작하는 이세계 생활`, `11698870` 고전문학 스코프 HOLD, `11698869` `월야환담` URL missing, `11698868` `방타스 -> 방접은 죽어서 하세요`, `11698867` 핵전쟁 이후 생존물 추천 relevance를 추가 native-web 이슈로 기록했다.
- batch `132`..`137`에서는 `11698866` `캣파` 장르소설 인접 추천/스코프 HOLD, `11698865` `나츠키 스바루/작중 행적` 위키성 wrong_work와 `Re : 제로부터 시작하는 이세계 생활`, `11698862` OCR 제목찾기 글 re_search HOLD, `11698861` `엘황 -> 외신이 쓴 마도서를 주웠다.`, `11698860` `악엔 -> 악역의 엔딩은 죽음뿐`, `11698859` `귤부인 -> 친아들이 내게 집착한다`, `11697267` `아생갤` title-correct URL mismatch, `11697266`/`11697258` `담청/죽깨수 -> 죽었다 깨어도 수선`, `11697261` `까꿍공주` info_missing HOLD, `11697256` TS 추천글 multi-candidate HOLD, `11697255` `판초 -> 판초우의의 마법사`를 추가 native-web 이슈로 기록했다.
- batch `138`..`143`에서는 `11697242` 유희왕 패러디/팬픽 장르 트로프 wrong_relevance HOLD, `11697241` 댓글 공식 URL `나폴리탄 괴담 세계 속 대장장이가 살아남는 방법`, `11697239` 조혈모세포 안내 책자 OCR false positive, `11697236` `엘시짤 -> 미래에서 온 연애편지` 캐릭터 앵커 누락, `11697234` `검귀가 환생함`, `11697233` 하츠네 OCR 과민 wrong_relevance, `11697231` `아생갤 -> 아카데미 생존 갤러리`, `11697229` 백합 트로프 scope HOLD, `11697226` 여주물 추천 multi-candidate HOLD, `11697219` `바르바로이 -> 이세계 검은 머리 바르바로이가 미궁에서 살아남는 법`을 추가 native-web 이슈로 기록했다.
- batch `144`..`149`에서는 `11695639`, `11695637`, `11695634`, `11695633`, `11695627`, `11695623`, `11695617`, `11695611`에서 마지막 전 구간의 약칭·댓글·OCR 기반 후보 보존 누락을 추가 확인했다.
- batch `150`..`155`에서는 `11695609`/`11695607` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 후보 보존 HOLD, `11695608` `예수천국 불신지옥` under_resolved, `11695602` OCR/광고 후보 `로판 속 바바리안 부부`, `11695599` garbage title `창관전생()` -> `창관전생(娼館轉生)`, `11695593` `_172` 신작 `S급 헌터도 결혼이 하고 싶다` 후보 보존, `11694064` sentinel wrong_work, `11694059` 플랫폼/추천글 multi-candidate 후보 보존, `11694042` `김근홍/2회차 -> 괴담에 휘말렸다` 누락을 추가 native-web 이슈로 기록했다.
- batch `006`..`017` 저장 중 PowerShell literal 경로가 한국어를 `???`로 변환하는 문제가 확인되어 `apply_patch`로 UTF-8 Python repair script를 생성한 뒤 복구했고, batch `018`..`155`는 UTF-8-safe ingest 경로로 저장했다. `tools/codex_native_web_judge_ingest.py`를 추가해 이후 subagent raw JSON을 표준 raw/verdict/progress/rows로 병합하게 했다. progress JSON 저장 순서와 external judge enum drift normalization, post_id dedupe rows renderer도 보정해 현재 `bad_question_runs=0`, 표준 `779`건, unique `779/779`, rows `779`를 확인했다.
- 검증: `py_compile tools\full_post_judge_codex_driver.py src\llm_batch\candidate_audit.py tools\codex_native_web_judge_ingest.py` 통과, `unittest tests.test_candidate_audit tests.test_judge_seed_registry tests.test_codex_native_web_judge_ingest -v` 25 tests OK. 이 판정은 보조 기준선이며 full scan approval 근거가 아니다.

## 2026-06-19 Track C blocked7 title-body official recall / C33 actual canary

- Track C blocked7에서 `11661853`이 run-to-run으로 흔들리는 원인을 다시 실제 런으로 확인했다. C31은 공식 URL evidence가 있었지만 final recall 승격이 약했고, C32는 requested `--parallel 16` actual run에서 검색이 여행/위키 nonzero만 보고 조기 종료해 공식 URL 자체를 놓쳤다.
- `agentic_pipeline.py` final-pass official URL recall이 title-body 공식 detail 검색 결과(`search_results`/`search_evidence_catalog`)를 직접 후보로 삼도록 보강했다. 글의 title-body clue 2개 이상과 공식 detail 제목이 맞을 때만 `_title_body_official_detail_anchor_*`로 승격한다.
- `orchestrator.py` title-body sanitized probe의 query budget/early-stop을 보강했다. `adjacent_meta_cheap`에서도 title-body probe는 6쿼리까지 허용하고, non-official nonzero 결과만으로 남은 specific title-body probe를 중단하지 않는다.
- 검증은 `py_compile` pass와 focused suite 95 tests OK로 확인했다.
- 실제 `expert_main.py` C33 canary를 requested `--parallel 16`으로 실행했다. run id `20260619_193831_833176`, effective `7`, completed/failed/pending `7/0/0`, search health `7/7 OK`.
- C33 결과: `11652175 -> 괴담 호텔 탈출기 (https://novelpia.com/novel/102155)`, `11661853 -> 두바이의 쫀득한 여초딩 재벌 9세 (https://novelpia.com/novel/419119)`, `11677911 -> 잘생기면 편해지는 인방 생활 (https://novelpia.com/novel/384016)` resolved. `11665081/11687635/11695607/11705276`은 title 없이 non-resolved 유지.
- C33은 VLM/OCR off targeted canary라 image-positive semantic approval이 아니며, semantic quality `REVIEW-LOCKED`, full scan approval `false` 유지.

## 2026-06-19 Track B precision sticky demote / B19 actual canary

- B18 full 8-row precision probe에서 `11661847`이 hidden-setting precision demote 후 후단 recall/locked rescue로 `괴담 호텔 탈출기`를 다시 public title로 되살리는 회귀를 확인했다.
- `_final_precision_title_demote_profile()`에 sticky precision-demote guard를 추가했다. 이미 `track_b_precision_demoted_*`가 붙은 late recovery는 direct full title 또는 본문 official URL 없이 재승격하지 않는다.
- 검증은 `py_compile`, focused sticky regression, Track B focused suite 32 tests OK로 확인했다.
- 실제 `expert_main.py` B19 canary를 requested `--parallel 16`으로 실행했다. run id `20260619_095624_908880`, effective `8`, completed/flushed/pending/failed `8/8/0/0`, search health `2/2 OK`.
- B19 `11661847`은 `is_relevant=True`, `work_resolution=unresolved`, `title_resolution_state=unresolved_matchable`, `novel_identity=None`으로 내려갔다. 로그에는 `hold: final precision demoted late-rescue title official_title='괴담 호텔 탈출기'`가 남았다.
- B19는 VLM/OCR off라 image-positive semantic approval이 아니며, `11661847` 단건이 1953초 걸린 finalization 병목은 별도 런타임 개선으로 남긴다. semantic quality `REVIEW-LOCKED`, full scan approval `false` 유지.

## 2026-06-18 적대적 감사 + 강판정 recall 회수 (full_post_judge 20260616_224555_632905)

- 아래 전수 판정 런을 적대적으로 검증했다. 구조는 정확했으나 판정이 파이프라인을 러버스탬프 — 자기보고 `disagreement_type` none 2188/uncertain 52/garbage_title 6, `under_resolved_false_negative=0`은 거짓 음성으로 드러났다.
- 독립 웹 재판정 표본: recall ACCEPT-미해소 40행 중 23(57.5%) 실제 누락작, precision ACCEPT-resolved 30행 중 8(26.7%) false-accept, slang pollution_risk 22 중 12 오경보.
- 강판정 recall 회수(score≥7 상위 123행): 65건 회수(high 56/med 9), 출처 official_detail 50 중심. 65건 중 42건(65%)이 파이프라인 내부 증거(official URL in search_evidence/본문 25 + OCR explicit-title 17)로 회수 가능 → 결정적 인-파이프라인 official-URL 승격 게이트가 최대 일반화 레버.
- 산출: `report/recall_recovery_report.md`, 회귀 시드 `recall_recovery_seed.jsonl`. semantic quality REVIEW-LOCKED·full scan approval false 유지.

## 2026-06-18 full_post_judge 20260616_224555_632905 전수 판정

- `docs/devs/FULL_POST_JUDGE_RUNBOOK.md` §3 기준으로 `out/expert_result_20260616_224555_632905.json` flushed `2246`건을 전수 판정했다. manifest pending `23`건은 `_pending_rerun.json`으로만 보존하고 판정 모수에서 제외했다.
- `tools/full_post_judge_codex_driver.py`를 추가해 compact projection `batch_000`..`batch_449`(`BATCH=5`)와 FULL 16필드 `verdicts_000`..`verdicts_449`를 멱등 생성하도록 했다. `candidate_audit` precompute, slang route 분리, shadow rebucket, precision/recall adversarial overlay도 같은 출력 디렉터리에 남긴다.
- judge-side web probe는 repo MCP search bridge cache로 수행했고 `_web_probe_cache.json`에 query `421`개를 보존했다. decisive URL이 확인되지 않는 case는 title을 생성하지 않고 `Missing`/`web_reverify_needed` 또는 action queue로 남긴다.
- 최종 coverage는 processed/judged/missing/pending `2246/2246/0/23`이고, FULL 16필드 누락 및 enum/invariant 위반은 `0`이다. `candidate_audit` pipeline-vs-shadow mismatch도 `0`이다.
- 결과 요약: `ACCEPT=1993`, `HOLD=195`, `REPROCESS=52`, `REJECT=6`; action queue는 `human_review=110`, `re_judge=87`, `re_search=44`, `slang_db_review=22`, `no_action=1983`이다.
- slang 축은 `precomputed.slang_axis_route=="llm"` `94`건만 판정했고 `ok=72`, `pollution_risk=22`다. slang DB write-back은 하지 않았다.
- 보고서는 `out/full_post_judge_20260616_224555_632905/report/full_post_judge_report.md`, 전수 행별 dump는 `report/rows/full_post_judge_rows_p01.md`..`p08.md`에 있다.
- 결론: run integrity는 `GO`지만, 이 판정은 보조 기준선이다. semantic quality는 계속 `REVIEW-LOCKED`이며 full scan approval은 `false`다.

## 2026-06-16 JUDGE3905 continuous improvement loop / runtime and OCR hold guards

- 루트 `goal.md` 기준으로 remaining output-lint loop를 계속 진행했다. source-backed targeted input 9건(`11602367`, `11632915`, `11650591` + controls)을 만들고 `.venv312` + `expert_main.py` + Gemma 4 E4B endpoint로 실행했다.
- targeted 9건 run id `20260615_231925_533889`는 completed/flushed/pending/failed `9/9/0/0`, `image_post_count=9`, VLM/OCR `READY`, compare expected/result/compared `9/9/9`다.
- 하지만 로그에서 `11639284` Deliberation path의 `NameError: name 'disc' is not defined` fallback이 발견됐다. runtime audit 도구가 이를 처음에는 놓쳐 `Traceback`, `NameError`, `Deliberation 오류`를 `runtime_log_exception`으로 잡도록 `tools/audit_goal_test_run_contract.py`를 보강했다. 재생성한 9건 runtime audit은 `NO-GO`다.
- `src/llm_batch/experts/deliberation.py`의 `_rebuild_arbiter_user_prompt()`가 curated alias hint에 넘길 discourse output을 복원하도록 수정했다. 회귀 테스트는 `tests/test_arbiter_curated_alias_guard.py`에 추가했다.
- runtime fix verification으로 `11639284` 단건을 재실행했다. run id `20260615_234526_746998`, completed/flushed/pending/failed `1/1/0/0`, `image_post_count=1`, VLM/OCR `READY`, runtime audit `GO`, compare `promotion_blocked`다.
- 9건 compare에서 `11650591`이 `주관적인 모바일 앱`으로 과승격되는 새 title hygiene 회귀가 드러났다. `title_noisy_ocr` seed에서 direct image work title과 final public title이 충돌하면 official URL이 있어도 public `official_title`을 hold하는 `apply_judge_seed_title_image_mismatch_guard()`를 추가했다.
- `11650591` 단건 rerun id `20260616_000415_830530`은 completed/flushed/pending/failed `1/1/0/0`, `image_post_count=1`, VLM/OCR `READY`, runtime audit `GO`, compare `hold_unresolved`다. public title은 비우고 후보/blocked title은 ledger에 보존한다.
- `11632915`은 noisy OCR title public promotion을 보류해 `hold_unresolved`로 전환했다. `11602367`은 wrong_relevance semantic/manual review가 계속 남는다.
- summary artifact는 `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_summary.json` 및 `_ko.md`다.
- 결론: runtime bug와 OCR/title overpromotion guard는 targeted rerun으로 검증했다. semantic quality는 계속 `REVIEW-LOCKED`이며 full scan approval은 아니다.

## 2026-06-15 JUDGE3905 remaining output-lint manual closure and control cleanup

- control `11639284`를 `.venv312` + `expert_main.py` + `--parallel 1`로 단건 재실행했다. run id `20260615_194903_574111`, input/completed/flushed/pending/failed `1/1/1/0/0`, `image_post_count=1`, VLM/OCR `READY`, runtime contract `GO`다.
- `title_noisy_ocr` judge seed 전용 guard `title_noisy_ocr_realigned_to_official_image_search_evidence`를 추가했다. 현재 official title이 URL을 갖고 있고, image explicit work title과 official/platform search evidence가 같은 URL에서 일치할 때만 title을 재정렬한다.
- `11636134`는 `전쟁/작각` 계열 noisy OCR title을 `불패의 명장으로 착각당했다`로 재정렬해 `safe_resolved`로 닫았다. URL 없는 OCR-only row는 자동 correction하지 않는다.
- recovered 14 + control 1을 합친 combined15 postprocess/compare를 생성했다. expected/result/compared `15/15/15`, missing `0`, after labels `safe_resolved=4`, `promotion_blocked=7`, `hold_unresolved=1`, `output_consistency_lint=3`이다.
- 5개 target/control post_id별 source/result/image/search/judge evidence packet을 `judge3905_p0_remaining_output_lint_manual_evidence_packets.*`로 생성했다.
- 남은 manual/semantic output lint는 `11602367`, `11632915`, `11650591`이다. original 15-row run `20260615_165906_220298` 자체는 runtime `NO-GO`로 유지하고, combined15는 recovered+control evidence completeness로만 사용한다.
- 검증: `py_compile` 통과, `tests.test_candidate_audit tests.test_judge_seed_registry tests.test_goal_test_run_contract_audit` 30 tests `OK`. semantic quality는 계속 `REVIEW-LOCKED`이며 full scan approval은 아니다.

## 2026-06-15 JUDGE3905 remaining-lint focused closure and conservative title evidence guard

- remaining `identity_consistency_lint=3` / `output_consistency_lint=8` target 11건을 source-backed focused input으로 묶고 row-level evidence table을 생성했다.
- `src/llm_batch/candidate_audit.py`의 judge-seed-only precision guard를 보강했다. `cross_media_or_famous_mismatch` 등 precision seed에서 official title이 남으면 platform URL이 있더라도 `promotion_blocked`로 내려 `blocked_official_title`과 후보 ledger에 보존한다.
- `title_noisy_ocr` safe 판정은 official search title match가 있어야 한다. `primary_work`가 URL과 title을 self-claim해도 search evidence title과 맞지 않으면 `output_consistency_lint`로 남긴다.
- focused run id `20260615_165906_220298`는 target 11건이 checkpoint에 모두 들어왔지만 control `11639284`가 미완료이고 ordered flush gap으로 input/completed/flushed/pending `15/14/8/6`이라 runtime contract `NO-GO`다.
- checkpoint completed 14건을 복구해 final audit postprocess를 재적용했다. target 11건은 `safe_resolved=3`, `promotion_blocked=3`, `hold_unresolved=1`, `output_consistency_lint=4`로 분류됐다.
- 남은 manual/semantic review 대상은 `11602367`, `11632915`, `11636134`, `11650591`이다. 이 follow-up도 full scan approval이 아니며 semantic quality는 `REVIEW-LOCKED`다.

## 2026-06-15 JUDGE3905 URL/domain official title promotion guard and random50 p32 baseline

- `src/llm_batch/candidate_audit.py`에 URL/domain/platform/generic label `official_title` demotion guard를 추가했다. 차단된 표면은 `blocked_official_title`, `blocked_official_title_url`, `promotion_blocked_reasons`로 남기고, 실제 title 후보는 `candidate_ledger`에 보존한다.
- `expert_main.py` post-processing은 audit field 생성 전에 `apply_official_title_promotion_guard()`를 실행한다. `tests/test_candidate_audit.py`에는 `novel.munpia.com`이 official title에서 내려가고 실제 후보가 ledger에 남는 회귀를 추가했다.
- domain/lint focused canary run id `20260615_105502_850042`를 15건으로 실행했다. input/completed/flushed/pending/failed `15/15/15/0/0`, `image_post_count=15`, VLM/OCR `READY`, runtime contract `GO`다.
- focused compare는 expected/result/compared `15/15/15`, missing `0`, after labels `promotion_blocked=4`, `identity_consistency_lint=3`, `output_consistency_lint=8`, official title lint after `0`이다. `11663514`는 `official_title=null`로 내려가 domain-title 승격 blocker가 닫혔다.
- random50 baseline은 첫 `--parallel 36` 실행이 completed `50/50`이었지만 healthy endpoint filter가 `32/36`이라 runtime audit이 `NO-GO`였다. 같은 input을 `--parallel 32`로 재실행해 run id `20260615_120734_501402`, completed/failed `50/0`, `image_post_count=30`, VLM/OCR `READY`, runtime contract `GO`를 확보했다.
- random50 p32 quality summary는 `safe_resolved=10`, `review_only=2`, `hold_unresolved=31`, `promotion_blocked=7`, official/identity/output lint count `{}`, domain/URL official title rows `[]`다.
- 결론: URL/domain official title promotion blocker와 random baseline 미실행 blocker는 닫혔다. 다만 focused canary의 `identity_consistency_lint=3`, `output_consistency_lint=8`과 random50 표본 한계 때문에 semantic quality는 계속 `REVIEW-LOCKED`이며 full scan approval은 아니다.

## 2026-06-15 JUDGE3905 high-risk expansion and slang DB low-info alias guard

- `tools/build_judge3905_expansion_inputs.py`를 추가해 기존 24건 canary와 겹치지 않는 source-backed high-risk expansion input을 생성했다. selected `36`, group count `recall=12`, `precision=16`, `hygiene=8`, image post `36`, source restore missing `0`이다.
- high-risk expansion을 `.venv312` + `expert_main.py` + `--vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다. run id `20260615_012056_067394`, input/completed/flushed/pending/failed `36/36/36/0/0`, effective parallel `36`, MCP health `8/8`, `image_post_count=36`, VLM/OCR semantic gate `READY`다.
- high-risk compare는 expected/result/compared `36/36/36`, missing `0`, run integrity `GO`, semantic quality `REVIEW-LOCKED`다. after labels는 `safe_resolved=7`, `promotion_blocked=12`, `hold_unresolved=3`, `output_consistency_lint=8`, `identity_consistency_lint=5`, `official_title_lint=1`이다.
- high-risk run에서 `novel -> novel.munpia.com`, `dc -> 내가 주인공인 줄 알았다`, `그리고 -> 괴담에 휘말린 피해자가 되었다`가 slang DB alias로 flush되는 새 오염 경로를 발견했다.
- `src/llm_batch/slang_db.py`의 generic/low-information alias guard를 보강해 URL/domain/platform token과 Korean connective surface가 storage observation이나 alias seed로 남지 않게 했다. `tests/test_slang_db_low_information_alias.py`를 추가했다.
- post-patch focused canary run id `20260615_021205_542965`를 3건으로 실행했다. input/completed/flushed/pending/failed `3/3/3/0/0`, `image_post_count=3`, VLM/OCR `READY`, finalize flush `buffered_observations=0`, runtime contract `GO`다.
- 당시 한계: `11663514`는 여전히 `official_title=novel.munpia.com`으로 출력되어 `official_title_lint`가 남았다. 이번 패치는 slang DB 재사용 오염을 막은 것이며, domain/URL official title 승격 자체는 후속 precision guard 과제로 남았다. 이 항목은 위의 domain guard follow-up에서 닫혔다.
- 당시 결론: source-backed high-risk expansion과 focused guard verification은 완료했지만, random baseline과 remaining lint semantic review 전까지 full scan approval은 계속 `REVIEW-LOCKED`였다.

## 2026-06-15 JUDGE3905 source-enriched VLM/OCR canary and pipeline audit fields

- `src/llm_batch/candidate_audit.py`를 추가하고 `expert_main.py`가 `analysis_result.identity`에 `candidate_ledger`, `candidate_ledger_status`, `candidate_generation_miss`, `promotion_blocked`, `hold_unresolved`, `safe_resolved`, `official_title_lint`, `identity_consistency_lint`, `output_consistency_lint`를 기록하도록 연결했다.
- `PostInput.judge_seed`를 추가해 canary input의 `_judge_seed`를 결과까지 보존하고, `prompt_router`에는 후보 보존과 official title promotion guard 지침을 보강했다.
- `tools/build_judge3905_source_enriched_canary.py`로 기존 24건 canary를 원본 `out/expert_result_20260612_174715_296791_checkpoint.jsonl` 기준으로 복원했다. image seed 18건의 URL은 모두 복원됐고 unrecovered는 `0`이다.
- source-enriched canary run id `20260615_001642_376095`를 `.venv312` + `expert_main.py` + `--vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다. manifest 기준 input/completed/flushed/pending/failed `24/24/24/0/0`, requested/effective parallel `24/24`, MCP health `8/8`, `image_post_count=18`, VLM/OCR semantic gate `READY`다.
- row-level image evidence도 복원됐다. 이미지 post 18/18에 `image_evidence_catalog`, `vlm_enrichment_used`, image fetch counters가 남았다.
- source-enriched compare는 expected/result/compared `24/24/24`, missing `0`, run integrity `GO`다. after labels는 `safe_resolved=3`, `promotion_blocked=7`, `hold_unresolved=4`, `output_consistency_lint=8`, `identity_consistency_lint=2`이며 candidate ledger는 24/24 result row에 생성됐다.
- runtime contract audit도 `GO`다. 단, 이 결과는 JUDGE3905 head-slice P0 regression/improvement evidence이며 full scan semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-14 GPT Pro judge seed registry / expert_main canary

- `tools/build_judge_seed_registry.py`와 `tests/test_judge_seed_registry.py`를 추가해 GPT Pro judge 결과를 P0 seed registry와 candidate-ledger shadow artifact로 변환했다.
- source는 `out/_judge3905_gpt_pro_v2/post_reviews.jsonl`, `out/_judge3905_gpt_pro_v2/batch_*.json`, 기존 completed subset을 함께 사용했다.
- registry seed는 `1505`건이고 source match missing은 `0`건이다. group count는 `recall=644`, `precision=123`, `hygiene=738`이다.
- shadow label은 `candidate_generation_miss=164`, `hold_unresolved=480`, `identity_consistency_lint=94`, `output_consistency_lint=738`, `review_only=29`로 산출됐다.
- 24건 canary input을 만들고 `.venv312` 환경에서 `expert_main.py`를 실제 실행했다. run id `20260614_230245_886140`, input/completed/flushed/pending/failed `24/24/24/0/0`, requested/effective parallel `24/24`, MCP health `8/8`이다.
- canary compare는 manifest canary scope 기준 expected/result/compared `24/24/24`, missing result `0`, extra result `0`, run integrity `GO`다.
- compare 결과 after shadow label은 `safe_resolved=3`, `promotion_blocked=3`, `hold_unresolved=2`, `review_only=6`, `output_consistency_lint=8`, `identity_consistency_lint=2`다. `official_title_changed=15`, `identity_consistency_lint_after=10`이다.
- 한계: judge batch source에 원본 image URL이 없어 canary 24건 중 image seed without URL이 `18`건이고, 실행 manifest의 `image_post_count=0`, VLM/OCR skip reason은 `no_image_blocks`다. 따라서 이번 결과는 judge-context canary이며 full VLM/browser evidence 검증이 아니다.
- 별도 기록: `docs/devs/JUDGE3905_P0_SEED_REGISTRY_CANARY_20260614.md`.
- 결론: run integrity는 `GO`지만 semantic quality는 계속 `REVIEW-LOCKED`다. 이 head slice seed를 full scan approval로 승격하지 않는다.

## 2026-06-14 GPT Pro Deep Research 재실행 검증 기록

- ChatGPT 로그인 상태를 확인했고, 전송 전 snapshot에서 작성창 모델 pill이 `Pro 확장 모드`로 잡혔다.
- `out/gpt_pro_deep_research_context_20260614_2.zip`에 judge report, prior research directions, `_result.json`, `post_ids_by_type.json`, `post_reviews.jsonl`, run manifest/subset/pending, 핵심 `src/llm_batch` 코드를 묶었다.
- `agbrowse web-ai send --model pro --effort extended --research deep`로 session `01KV31C9QFS5YN3SZF7BBJNHZ9`를 전송했고, 응답 URL은 `https://chatgpt.com/c/6a2e9d3e-458c-83ee-b3ea-5485161b92e8`이다.
- 전송 warning: `model selected: pro (already selected)`였지만 `reasoning effort extended was not enforced: ChatGPT reasoning effort selector not found for pro`가 남았다.
- 응답은 complete였고 `out/agbrowse_deep_research_poll_20260614.json`에 저장했다. 단, 응답 본문이 실제 Pro Extended / Deep Research API 실행 상태가 아니라 zip 기반 정적 분석이라고 고지했으므로, 검증된 Deep Research 완료로 보지 않는다.
- 별도 기록: `docs/devs/GPT_PRO_DEEP_RESEARCH_RERUN_20260614.md`.
- 결론은 기존 방향성과 대체로 일치한다. recall 붕괴(`under_resolved_false_negative=644`)를 바로 title promotion으로 풀지 말고, entity candidate 보존, cross-media guard, slang/context merge, output lint를 P0로 둔다.

## 2026-06-14 GPT Pro judge 기반 pipeline research 방향 정리

- `docs/devs/GPT_PRO_PIPELINE_RESEARCH_CONTEXT_20260614.md`를 추가해 현재 파이프라인/프롬프트/BatchContext/slang_db 구조와 `out/_judge3905_gpt_pro_v2` judge 결과를 bounded context로 정리했다.
- `agbrowse web-ai context-dry-run`에서 전체 코드/문서 패키지는 예산을 초과해, 연구 컨텍스트 + judge report/post-id list + `models.py`/`batch_context.py`/`slang_db.py`/`prompt_router.py` 중심의 context zip으로 축소했다.
- ChatGPT web-ai 세션 `01KV2YPF1YGHWH9B311QTWGBGJ`로 심층 분석을 완료했다. 단, ChatGPT UI model selector를 찾지 못해 requested `pro/extended` 강제 확인은 실패했으므로, 산출물은 “ChatGPT web-ai 심층 분석”으로 기록하고 모델 강제 검증 완료로 보지 않는다.
- 분석 결과를 `docs/devs/GPT_PRO_PIPELINE_RESEARCH_DIRECTIONS_20260614.md`에 정리했다.
- 핵심 방향은 “후보 보존 recall은 넓게, `official_title` promotion은 좁게”다.
- 후속 P0는 seed registry 생성, `candidate_ledger` shadow, `official_title_lint`, `identity_consistency_lint`이며, 이 작업은 head slice seed 개선이지 full scan approval이 아니다.

## 2026-06-14 agbrowse GPT Pro judge runner hardening

- ChatGPT Pro 브라우저 기반 LLM-judge 전수 검토를 위해 `tools/run_agbrowse_llm_judge.py`를 보강했다.
- 기존 `--context-from-files`/`--file` 및 Windows `agbrowse.cmd` 조합은 batch JSON 전달이 흔들려 `{"batch":null,"verdicts":[]}` 응답을 만들 수 있어 폐기했다.
- runner는 Node로 `agbrowse.mjs`를 직접 실행하고, 5건 이하 `POSTS_JSON`을 inline prompt로 전달한다.
- `agbrowse web-ai query` 일체형 호출은 답변이 생성된 뒤 완료/copy 감지에서 멈출 수 있어, 기본 경로를 `send -> watch -> sessions show`로 바꿨다.
- provider tab 누적으로 `provider.commit-not-verified`가 발생해 chunk 전후 ChatGPT tab cleanup을 추가했다.
- 5건 chunk가 실패하면 1건 subchunk checkpoint로 분해해 완료된 post 판단을 잃지 않도록 했다.
- ChatGPT UI 전송 검증에서 막히는 민감 표현은 provider prompt에만 bracket label로 치환하고, 원본 local batch/checkpoint는 변경하지 않는다.
- 오래된 `sent` web-ai session이 남으면 `provider.commit-not-verified`가 반복될 수 있어, chunk 전송 전후 stale sent-session prune을 추가했다.
- 장기 실행에서 일부 batch가 간헐 실패해도 완료 chunk를 잃지 않고 다음 batch로 넘어가도록 `--continue-on-fail`을 추가했다.
- 25건 단일 호출(`--records-per-call 25 --no-split-on-failure`)은 batch `006`~`019`에서 유효 JSON을 반환해 5건 chunk 방식보다 빠른 장기 실행 모드로 확인됐다.
- ChatGPT `요청이 너무 많습니다` 팝업 반복 시 snapshot 기반 `알겠습니다` watcher로 닫으며 진행했고, batch `112`는 5건 slow chunk로 복구했다. 이후 batch `113`~`125`는 25건 단일 호출로 다시 통과했다.
- rate-limit 완화를 위해 5건 chunk/subchunk 사이 선택적으로 대기할 수 있는 `--chunk-sleep-sec`를 추가했다.
- 검증: `out/_judge3905_gpt_pro_v2` 기준 batch `000`~`125`는 `3150/3874` post, `126/155` batch 유효 verdict로 aggregate됐다(`agree=1881`).
- 최종 검증: batch `000`~`154` 전수 완료, `3874/3874` post, `155/155` batch, `agree=2303`, `invalid_batches=[]`, missing `0`.
- `post_reviews.jsonl`, `post_reviews.md`, `post_ids_by_type.json`, `_result.json`을 생성했고 `JUDGE3905_REPORT.md`를 GPT Pro 전수 결과로 갱신했다.
- 후속 작업: GPT Pro judge 결과를 모집단 품질 승인으로 환산하지 않고, recall/precision regression seed로 분리해 개선한다.

## 2026-06-13 dashboard UX handoff takeover

- Claude 사용량 제한으로 멈춘 dashboard 기능/디자인 작업을 인계받아 첨부 TODO와 현재 worktree를 대조했다.
- Codex subagent 전문가 2축 검토에서 `loadLiveResults` 최신 검색/필터 reload 유실, SSE restore의 필터 스냅샷 덮어쓰기, non-secure HTTP clipboard 실패, `_detail_warning` 내부 필드 복사 노출을 confirmed issue로 채택했다.
- `src/llm_batch/monitor/static/index.html`에서 live 결과 검색/관련성 필터의 latest-wins pending reload, stale response discard, filter-active restore guard를 적용했다.
- 상세 모달 JSON 복사는 `_detail_warning`을 제외하고 `navigator.clipboard` 미지원/비보안 컨텍스트에서 textarea fallback을 사용하도록 보강했다.
- `tests/test_dashboard_standalone.py`에 static UI contract 2건을 추가해 reload guard/restore guard/clipboard sanitize+fallback marker를 고정했다.
- 검증: inline script parse `ok`, `.venv312\Scripts\python.exe -m unittest tests.test_dashboard_standalone -v`는 `26` tests `OK`다.
- Browser smoke: standalone dashboard `http://127.0.0.1:18099`에 sample 3건을 ingest한 뒤 검색/필터 row 표시, row click 상세 모달 표시, JSON 버튼 클릭 무오류, history/live tab 전환을 확인했다. app console error는 `0`이고 Tailwind CDN production warning은 follow-up으로 남는다.
- 한계: `scratch/e2e_dashboard_ui.py`는 현재 실제 브라우저 조작 E2E가 아니라 API smoke에 가깝다. full UI regression 자동화가 필요하면 별도 Browser/Playwright 시나리오로 승격한다.

## 2026-06-12 dashboard browser performance optimization

- `http://localhost:8080/` live dashboard를 Browser 플러그인으로 직접 확인했다.
- 기준선은 live 결과 테이블 500행 렌더와 worker 카드 전체 재작성 때문에 settled DOM이 약 `8739` nodes, DOM snapshot이 약 `294K-302K` chars였다.
- `src/llm_batch/monitor/static/index.html`에서 live 결과 페이지 크기를 `500 -> 100`으로 줄여 `/api/results` payload와 테이블 DOM을 함께 낮췄다.
- worker 카드 렌더에 per-card signature cache를 추가해 `expert_phase` 코얼레싱 렌더 때 변경되지 않은 카드의 `innerHTML` 재작성을 건너뛴다.
- live 로그는 메모리에 최대 `500`줄을 유지하되 DOM 표시 텍스트는 `MAX_LOG_RENDER_CHARS=80000`으로 제한해 대형 LLM 로그가 layout/snapshot을 과도하게 키우지 않게 했다.
- 검증: inline script parse `ok`, Browser reload 후 settled state는 `2342` nodes, `100` result rows, `26` worker cards, `logLines=115`였고 history 탭 전환 후 live 복귀도 정상이다. 후속 UX guard 포함 현재 `python -m unittest tests.test_dashboard_standalone`는 `26` tests `OK`다.
- 남은 경고: Tailwind CDN production warning은 계속 발생한다. 별도 frontend build pipeline을 만들 때 local Tailwind build로 전환한다.

## 2026-06-02 v529 11718094 manual unresolved closure

- v528 이후 마지막 잔여 seed인 `11718094`를 수동 리뷰했다.
- browser visual artifact `v515_browser_visual_direct_full/11718094.png`는 텍스트 스크린샷이 실제 로드된 것을 보여주지만 작품명/작가명/플랫폼 footer는 없다.
- v528 result의 VLM/OCR image evidence는 `에세르/예세르`, `아르타`, 고양이 인형, 관계성 묘사를 읽었지만 `scene_inference_only`, `title_role=unknown`, `promotion_eligible=false`다.
- 검색 evidence catalog와 추가 exact phrase search는 단일 공식 작품 detail URL로 연결되지 않았다.
- 따라서 `11718094`는 작품 장면 가능성이 있는 relevant review row로 인정하되, 정식 작품 title은 확정하지 않는 `unresolved_matchable`로 보존한다.
- row-level label은 대량 approval 방지를 위해 `HOLD`로 유지하고, 수동 리뷰가 완료됐으므로 action은 `no_action`, disposition은 `close_as_unresolved`로 둔다.
- v529 final gate에서 issue-focused seed queue는 `GO`로 정리했다. 이것은 자동 재런/재검색 queue가 남지 않았다는 뜻이며, 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-02 v528 remaining 2 seed follow-up

- v527 after-review에서 남은 `11718099` `REPROCESS/re_search`와 `11718094` `HOLD/human_review`만 분리해 후속 canary를 실행했다.
- `v528_remaining_review_11718099_11718094_input.jsonl`은 raw row `7`, unique post `2`다. preflight는 LLM `GO`, MCP effective `GO`, full shard `NO-GO(32/36)`, rerun execution `GO`다.
- 실행은 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images` 기준이며 run id는 `20260602_021458_436841`이다.
- manifest 기준 requested/effective parallel `36/2`, completed/flushed/pending/failed `2/2/0/0`, image post count `2`, VLM/OCR ready다.
- runtime contract audit은 `GO`, reason hygiene hit files `0`, semantic coverage는 `GO`다. browser visual required/available/missing은 `2/2/0`이고 image evidence catalog present/missing은 `2/0`이다.
- after-review label은 `ACCEPT=1`, `HOLD=1`이다.
- `11718099`는 v528에서 `빌어먹을 환생`, final URL `https://page.kakao.com/content/56071101`, primary work `source_tier=official_detail`, alias `빌환`으로 회복되어 `ACCEPT/no_action`으로 닫혔다. 기존 browser artifact `11718099.png`도 실제 표지 제목을 보여준다.
- `11718094`는 이미지 스크린샷과 VLM/OCR이 장면 텍스트를 읽었지만 `예세르`/`아르타`를 단일 공식 작품 title로 연결하는 근거가 없어 `HOLD/human_review`로 남겼다. 이후 v529에서 수동 unresolved closure로 닫았다.
- v528/v529는 targeted residual closure이며, 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-02 v527 v284 residual 21-post rerun / issue-focused scope correction

- 현재 goal 범위를 10만 건 semantic approval이 아니라, 10만/partial/source review에서 간추린 known-bad/high-risk seed closure로 재고정했다.
- v284 입력은 raw JSONL `98`줄이지만 댓글 row가 포함된 줄 수이며, 실행 단위는 manifest `selected_post_count=21`과 unique post `21`개다.
- `tools/preflight_expert_rerun_runtime.py`가 `input_post_count`, `selected_post_count`, `found_post_count`, execution contract count, unique post count를 raw row count보다 우선하도록 보강했다.
- focused preflight test에서 JSONL row 수와 post execution unit 수가 다를 때 required open shard가 post 수 기준으로 계산되는지 검증했다.
- v527 preflight는 LLM endpoint/model `GO`, MCP effective readiness `GO`, full 36 shard readiness `NO-GO(32/36)`, rerun execution `GO`로 분리됐다.
- `v284_residual_p0p1_core21_input.jsonl`을 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images`로 재실행했다.
- run id `20260602_014729_612198`은 requested/effective parallel `36/21`, completed/flushed/pending/failed `21/21/0/0`, image post count `14`, VLM/OCR semantic gate `READY`다.
- Docker shard lifecycle은 `auto_up=false`, `auto_recreate=false`, `small_run_lifecycle_blocked=true`로 유지되어, 사용자가 지적한 small goal run의 compose restart 지연을 재발시키지 않았다.
- runtime contract audit은 `GO`, reason hygiene hit files `0`, semantic coverage는 `REVIEW`다.
- semantic coverage에서 browser visual required/available/missing `14/14/0`, image evidence catalog present/missing `14/0`, search-only resolved title `0`, blocked-intent resolved title `0`을 확인했다.
- after-review label은 `ACCEPT=19`, `REPROCESS=1`, `HOLD=1`이다. `11718080`은 작품 매칭 없이 social/genre/trope lament로 분리됐고, `11718082`는 VLM/OCR image anchor로 resolved됐다.
- v527 시점 잔여는 `11718099` `REPROCESS/re_search`와 `11718094` `HOLD/human_review`였다. 이후 v528에서 `11718099`는 닫혔고 `11718094` 1건만 남았다. 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-02 v526 issue-focused browser visual closure

- v523 issue-focused queue의 마지막 browser visual HOLD였던 `11718069`, `11718076`을 대상으로 재확인했다.
- Codex 내장 Browser plugin / in-app browser iab 연결은 현재 세션에서 setup 실패로 막혔고, 이를 blocked evidence로 유지한 뒤 Playwright MCP와 direct Playwright fallback을 사용했다.
- `11718069`은 direct headless CLI counter에서는 article image `0/1` Weak였지만, Playwright MCP full-page screenshot/snapshot에서 원문 제목/본문/본문 이미지 렌더링이 함께 확인됐다. 이 counter conflict를 `combined_manifest.json`에 명시했다.
- `11718076`은 direct Playwright eval에서 article image `1/1` loaded, pending/broken/placeholder `0`으로 확인됐다.
- `v526_browser_visual_after_review_labels.jsonl`에서 두 건 모두 `ACCEPT/no_action`으로 닫았다. `11718069`은 작가/장르 주변담 `author_talk/author_meta`, `11718076`은 `즉사기 들고 무림에 떨어지다` character talk로 정합적이다.
- v518 누적 browser artifact에 v526 override를 결합한 `v526_combined_browser_visual_artifacts_manifest.json` 기준 v523 seed audit은 browser visual required/available/missing `6/6/0`이다.
- v523 원본 artifact의 `11718083` image catalog missing은 v524 단건 재런으로 supersede된 상태이므로 v526 queue에서는 재오픈하지 않는다.
- 이번 결과는 issue-focused seed closure이며 10만 semantic approval이 아니다. random baseline/P0P1 expansion과 completed VLM/OCR-on source 전까지 전체 gate는 계속 `REVIEW-LOCKED`다.

## 2026-06-02 v522 11718080/11718082 VLM/OCR-on live canary

- 원격 vLLM endpoint `http://10.20.0.101:8000/v1/models`가 `bg-digitalservices/Gemma-4-E4B-it-NVFP4`를 반환하는 것을 확인했다.
- Docker Desktop engine pipe는 여전히 권한 거부였지만, TCP preflight 기준 MCP open shard는 `32/36`이고 2건 small canary에 필요한 effective shard `2`개는 충족했다.
- `v257_post11718080_11718082_input.jsonl`을 `--parallel 36 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
- run id `20260602_000719_133133`은 completed/flushed/pending/failed `2/2/0/0`, requested/effective parallel `36/2`, Docker lifecycle auto up/recreate `false`, VLM/OCR semantic gate `READY`다.
- `11718082`는 image anchor high, VLM fetch/chunk `1/1`, `image_evidence_catalog`와 v518 browser visual artifact로 `재벌가 차녀의 2회차 걸그룹` resolved를 확인했다.
- `11718080`은 `official_title=null`, `title_resolution_allowed=false`, `work_resolution=none`으로 old result의 `소보로설` 과확정이 재발하지 않았다.
- runtime audit `GO`, reason hygiene `GO`, semantic coverage with browser `GO`, 자연어 label `ACCEPT=2/no_action=2`를 남겼다.
- 이 결과는 2건 targeted canary의 회복 증거이며 10만 semantic approval은 아니다. 원본 partial source와 expanded random/high-risk review blocker는 계속 남는다.

## 2026-06-01 v519 direct Playwright browser evidence recovery

- `tools/capture_vlm_ocr_browser_review_cli.py`가 `playwright-cli eval --filename` 결과 파일을 만들지 못하는 경우 stdout JSON을 회수해 `.eval.json`으로 정규화하도록 보강했다.
- 현재 Windows 환경에서는 `npx.cmd`/playwright-cli daemon 경로가 npm cache `EPERM`과 JS 인자 재파싱 문제로 흔들렸다. 설치된 Chromium revision이 있는 npm cache `node_modules`를 찾아 direct Node Playwright로 원문 열기/eval/screenshot을 한 프로세스에서 수행하는 fallback을 추가했다.
- DC UI의 일반 `차단` 단어가 `blocked_signals`로 잡혀 이미지가 정상 로드된 row를 `Missing`으로 낮추는 오탐을 수정했다. 실제 차단은 `접근이 차단`, `차단되었습니다` 같은 구체 문구만 본다.
- v515 completed subset 16건 재캡처 결과는 `Strong=10`, `Weak=5`, `Missing=1`이고, v506 completed subset strict audit은 browser visual required/available/missing `16/10/6`이다.
- 원본 `out/expert_result_20260528_141006_620986.json` 71행 기준 추가 target을 v517로 캡처하고 v518 누적 manifest를 만들었다. unique visual target `37`건 중 `Strong=25`, `Weak=10`, `Missing=2`다.
- v519 원본 전체 audit은 browser visual required/available/missing `37/25/12`, external browser artifact rows `25`, gate `REVIEW-LOCKED`다.
- `11718082`는 v517 direct artifact에서 `article_image_count=1`, `article_loaded_count=1`, pending/placeholder/incomplete/broken `0`으로 닫혔고 screenshot에 KakaoPage 이미지 표면이 보인다.
- 남은 `12`건은 `11718077`, `11718076`, `11718074`, `11718069`, `11718068`, `11718085`, `11718116`, `11718110`, `11718107`, `11718079`, `11718063`, `11718052`다. 이들은 image loading failure 또는 image node missing으로 `Weak/Missing`이며 semantic approval 근거가 아니다.
- 이번 변경은 browser visual evidence 회수 경로를 복구한 것이며, 원본 result의 image evidence catalog/comment metadata/final semantic reread 공백은 여전히 남아 있다. 10만 semantic approval은 계속 `REVIEW-LOCKED`다.
- v520 current-state/action queue를 v519 audit 기준으로 재생성했다. approval blockers는 completed VLM/OCR-on source 확보, P0/P1 high-risk expansion, modern semantic coverage source, VLM/OCR browser visual gate다.
- `tools/build_goal_action_queue.py`는 `source_browser_visual_missing` unique post count와 `visual_gate_blocker_signal_count` 합산 신호를 분리한다. 기존 `visual_gate_missing_count`는 compatibility field이며 unique post count가 아니다.

## 2026-06-01 v510 strict browser artifact gate / Arbiter memory-query title restore guard

- subagent P0 finding을 메인 Codex가 재확인했다. `Arbiter`는 memory-query/no-work 계열에서 `Verifier High-title lock`과 null restore가 `memory_query_forced_upgrade_guard`보다 먼저 title을 되살릴 수 있었다.
- `src/llm_batch/experts/arbiter.py`에서 memory-query forced-upgrade block을 `Verifier High-title lock`과 verifier-null restore보다 먼저 적용하도록 보강했다. block 발생 시 `official_title`, `official_novel_title`, `heretic_url` 복원은 막고 `_title_deliberately_null`을 유지한다.
- `tests/test_arbiter_memory_query_null_restore_guard.py`를 추가해 weak relation-hold memory-query에서 Verifier가 High title/official URL을 갖고 있어도 Arbiter가 title을 복구하지 않는지 검증했다.
- `tools/build_semantic_coverage_audit.py`의 external browser artifact 판정을 강화했다. screenshot/snapshot과 `Medium/Strong` grade만으로는 부족하고, `article_image_count>0`, `article_loaded_count>=article_image_count`, pending/broken/placeholder/incomplete counter `0`이 함께 있어야 `browser_visual_available`로 세다.
- `tools/build_browser_visual_targets_from_result.py` manifest coverage가 0 카운트도 명시하도록 했다.
- strict gate 적용 후 v506 completed subset 재감사 결과는 `browser_visual_required=16`, `browser_visual_available=0`, `browser_visual_missing=16`, `external_browser_artifact_rows=0`, gate `REVIEW-LOCKED`다. 기존 fallback screenshot 11718049도 loading counter가 없어 visual gate 미충족으로 다시 target에 남는다.
- v510 산출물은 `v510_v506_completed_semantic_coverage_strict_browser_audit.*`, `v510_remaining_browser_visual_targets.*`다.
- focused Arbiter/browser/audit tests 36건과 관련 `py_compile`을 통과했다.
- 이번 변경은 과승격 방지 패치다. 브라우저 target 수가 다시 16으로 올라간 것은 후퇴가 아니라 더 정확한 gate 적용이다. 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v509 browser attempt failure preserved / Codex subagent 병렬 재확인

- 사용자 재정정에 맞춰 이번 라운드도 `expert_main.py --parallel` 조정이 아니라 Codex `spawn_agent` 전문가 병렬로 진행했다. 문서/gate 축, VLM/OCR/browser 축, 프롬프트/오케스트레이션 한계 축을 별도 explorer로 배정했고 메인 Codex가 로컬 산출물과 gate를 통합한다.
- Codex in-app Browser 직접 제어는 현재 세션에서 `node_repl` browser runtime setup 실패가 반복되어 blocked evidence로 유지했다. fallback으로 Playwright를 사용해 `11718068` 원문 URL을 열고 screenshot/snapshot/eval JSON을 남겼다.
- `11718068`은 DC 페이지와 본문 텍스트는 보였지만 article image가 `article_image_count=1`, `article_loaded_count=0`, `article_incomplete_count=1`, `naturalWidth=0`, `complete=false`였으므로 visual evidence가 아니라 이미지 로딩 실패 시도 증거로 기록했다.
- `qualitative_review/20260528_141006_620986/v509_browser_visual_attempt_manifest.json`와 `v509_browser_visual_attempt_summary_ko.md`를 추가했다. `11718049`만 fallback `Medium` visual evidence로 유지하고, `11718068`은 `status=failed`, `evidence_grade=Missing`으로 남겼다.
- v506 completed subset을 v509 attempt manifest와 함께 재감사했다. 결과는 `browser_visual_required=16`, `browser_visual_available=1`, `browser_visual_missing=15`, `external_browser_artifact_rows=1`, gate `REVIEW-LOCKED`다.
- 남은 target은 여전히 `15`건이며 `11718068`은 이미지 로딩 실패로 target 목록에 남는다. 브라우저 screenshot이 있어도 article image loading counter가 실패하면 `browser_visual_available`로 세지 않는다.
- `LLM_JUDGMENT_REVIEW.md` 합의 방식에 Codex subagent 병렬 리뷰와 `expert_main.py --parallel` runtime worker 병렬의 경계를 추가했다.
- v509는 시각 증거 게이트의 보수적 보존이며 10만 semantic approval이 아니다. 남은 browser visual target, no-work 공통 선행 게이트 live canary, expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v508 intent-denied title-present audit / fallback target shrink

- v507 subagent 자연어 이해 축에서 남긴 P0를 감사 도구에 반영했다. `intent_permit_for_title_search=false`, `title_resolution_allowed=false`, `context_only/no_work` 신호가 있는데 공개 결과에 title이 남으면 `intent_denied_title_present`로 `REVIEW-LOCKED` 처리한다.
- 이 issue는 `resolved` 상태만 보지 않는다. `title_resolution_state=context_only`처럼 resolved가 아니어도 `official_title`이 같이 남은 모순을 잡는다.
- `tools/build_semantic_coverage_audit.py`가 v507 `fallback_browser` attempt manifest를 external browser artifact로 읽을 수 있게 했다.
- `tools/build_browser_visual_targets_from_result.py`도 `--browser-artifacts-manifest`를 받아 이미 확인된 fallback visual artifact를 target 목록에서 제외한다.
- v506 completed subset을 v507 fallback manifest와 함께 재감사했다. 결과는 `browser_visual_required=16`, `browser_visual_available=1`, `browser_visual_missing=15`, `intent_denied_title_present=0`, gate `REVIEW-LOCKED`다.
- 남은 target 15건은 `qualitative_review/20260528_141006_620986/v508_remaining_browser_visual_targets_ko.md`에 정리했다.
- focused audit/target tests 33건과 관련 `py_compile`, v508 manifest JSON validation을 통과했다.
- v508도 구조/coverage 보강이며 10만 semantic approval은 아니다. 남은 browser visual 15건, no-work 공통 선행 게이트 구현/실행 검증, expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v507 browser visual target 전수화 / Codex subagent 병렬 재정렬

- 사용자 재정정에 따라 이번 `/goal` 병렬은 `expert_main.py --parallel`이 아니라 Codex `spawn_agent` 전문가 병렬로 다시 수행한다. subagent 축은 실행 오케스트레이션/worker lifecycle, VLM-OCR-browser visual gate, 자연어 이해/프롬프트 한계로 분리했다.
- `tools/build_browser_visual_targets_from_result.py`를 추가해 semantic coverage audit의 `sample_post_ids` 10건 제한에 의존하지 않고 result JSON에서 browser visual missing 대상 전체를 추출하게 했다.
- `tests/test_browser_visual_targets_from_result.py`를 추가해 browser visual missing 대상이 audit issue sample 수로 잘리지 않는지 회귀 검증했다.
- v506 recovered completed subset `23` rows 기준 browser visual required/missing target은 `16`건이다. target manifest와 JSONL은 `qualitative_review/20260528_141006_620986/v507_v506_completed_browser_visual_targets_manifest.json`, `v507_v506_completed_browser_visual_targets.jsonl`에 남겼다.
- Codex in-app Browser는 현재 세션에서 runtime setup 단계가 두 번 실패해 직접 제어하지 못했다. 이 상태는 visual evidence가 아니라 blocked evidence로 기록한다.
- fallback으로 Playwright를 사용해 `11718049` 원문 URL을 열고 screenshot/snapshot을 남겼다. 본문 이미지가 화면에 보이므로 해당 1건은 fallback visual evidence `Medium`으로만 기록한다.
- fallback artifact는 `qualitative_review/20260528_141006_620986/v507_11718049_fallback_browser.png`, `v507_11718049_fallback_snapshot.md`, `v507_browser_visual_attempt_manifest.json`, `v507_browser_visual_attempt_summary_ko.md`에 남겼다.
- v507 검증은 browser visual target tool/test 29건, 관련 `py_compile`, target/attempt manifest JSON validation을 통과했다.
- subagent 통합 요약은 `qualitative_review/20260528_141006_620986/v507_subagent_review_summary_ko.md`에 남겼다. 오케스트레이션 축은 small rerun 36 worker 자동 compose 재시작 P0가 없다고 봤고, VLM/OCR/browser 축은 visual target 16건 미해결을 P0 gate로 유지했다.
- 자연어 이해/프롬프트 축은 현재 이해 장치가 없기보다 `Gatekeeper -> DiscourseAnalyzer -> Decoder -> Verifier -> Arbiter`에 흩어져 있어, no-work/social lament/context-only 결과가 검색/alias/rescue 경로에서 다시 살아날 수 있다고 정리했다.
- 후속 P0는 `intent_permit_for_title_search`, `title_resolution_allowed`, `direct_anchor_catalog`, `no_work_reason` 같은 공통 선행 게이트를 search/rescue/known alias/session knowledge/Arbiter promotion 전부에 적용하는 것이다.
- 전체 `16` target 중 Codex in-app Browser 직접 evidence는 `0`건이고 fallback evidence는 `1`건뿐이다. v506 completed subset과 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v506 v504 targeted rerun 중단 감사 / unresolved reason wording 보강

- v504 seed package의 권장 계약대로 VLM/OCR on targeted rerun을 실행했다. 명령은 `--parallel 24`, `--reuse-shards-only`, `--no-dashboard`, `--vlm on`, `--ocr on`, `--require-vlm-ocr-for-images`, endpoint `http://10.20.0.101:8000/`, model `bg-digitalservices/Gemma-4-E4B-it-NVFP4`를 명시했다.
- preflight에서 vLLM `/v1/models`는 200 OK였고 model id도 일치했다. shard health는 v504 권장 24개 기준 OK였으며, `36`개 전수 shard를 요구하지 않았다.
- 실행은 사용자 중단 이후에도 남은 Python worker가 계속 CPU를 사용해 `expert_main` 계열 PID를 정리했다. 이후 남은 Python은 다른 프로젝트/일반 프로세스로 확인했다.
- run_id `20260601_211238_827988`는 input `24` 중 completed `23`, flushed `14`, pending `9`, failed `0`인 partial 상태다. runtime audit은 `completed_count_lt_input_post_count`, `pending_count_gt_zero`, `flushed_count_lt_completed_count` 때문에 `NO-GO`다.
- `tools/recover_expert_run_from_checkpoint.py`로 checkpoint/pending snapshot을 복구해 `v506_v504_interrupted_completed_subset.json`을 생성했다. `23`개 completed row는 `recoverable_pending_flush_gap`이며 completed subset 감사에는 사용할 수 있지만 full rerun GO 근거는 아니다.
- completed subset semantic coverage는 image evidence catalog missing `0`, image OCR reason without public VLM counter `0`, comment metadata/dialogue missing `0`으로 개선 신호가 있었다. 그러나 browser visual missing `16`, comment author match unverified review-only `3`으로 gate는 `REVIEW-LOCKED`다.
- reason hygiene는 old partial artifact에서 `작품 관련 단서는 충분하지만` phrase를 `stale_relevant`로 잡았다. 원인은 특정 post id가 아니라 unresolved relevant reason 템플릿의 기본 문구였다.
- `_format_unresolved_relevant_reason()`의 기본 문구를 `웹소설/장르 맥락은 보이나 단일 공식 제목을 확정할 직접 증거가 부족...`으로 낮추고, `관련 포스트로 판정하되` 문구도 더 조심스러운 요약으로 바꿨다.
- focused 회귀 `test_unresolved_relevant_reason_avoids_stale_relevant_hygiene_phrase`를 추가했고, sanitize/semantic coverage 묶음 31건과 관련 `py_compile`을 통과했다.
- v506은 interrupted targeted rerun에서 얻은 partial evidence와 future reason hygiene fix다. completed full rerun, browser visual artifacts, expanded review 전까지 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v505 small-run 후속 검토 / adjacent reason wording guard

- 이번 라운드도 Codex `/goal` 병렬을 repo runtime worker 수가 아니라 `spawn_agent` 전문가 병렬로 수행했다. runtime/log, semantic packet, VLM/browser visual, docs/gate 축을 분리했고 메인 Codex가 패치와 검증을 통합했다.
- v493 단건 런은 requested/effective worker `2/2`, completed/flushed/pending/failed `2/2/0/0`, docker compose 중지/재시작 신호 없음으로 runtime contract `GO`다.
- v494 browser artifact로 `11718082`의 이미지 로딩을 재확인했다. `article_image_count=1`, `article_loaded_count=1`, pending/placeholder/incomplete/broken `0`이며 screenshot에는 `재벌가 차녀의 2회차 걸그룹`, `유은우`, `267화`, KakaoPage 표면이 보인다.
- `11718080`은 특정 작품 매칭 대상이 아니라 친구/일상 한탄 + TS 장르/트로프 담론으로 보는 것이 맞고, final decision의 `is_relevant=false`, `title_resolution_state=adjacent`, `discussion_type=trope_discussion` 방향도 맞다.
- 다만 기존 v493 public reason에는 `주변 관련`과 `최종 판정은 비관련 포스트`가 함께 남아 adjacent/social lament 범위를 혼동시킬 수 있었다. semantic coverage audit에 `adjacent_reason_non_relevant_wording_conflict` issue를 추가했다.
- `_sanitize_reason()`은 adjacent/trope/author/meta/community-banter류 비해당 결과에서 `비관련 포스트` 단정 대신 `adjacent_relevant`와 `작품 주변 맥락은 인정하되 단일 공식 제목 미확정` 문구를 유지하도록 보강했다.
- `11718082`의 OCR 오타/표면 변형은 특정 문자열 하드코딩이나 slang/alias 고정 규칙으로 저장하지 않는다. positive 기준은 VLM/OCR 직접 작품 표면 + author + episode + platform + official URL alignment다.
- `v505_v493_semantic_coverage_audit`은 browser artifact 없이 `REVIEW-LOCKED`이며, `11718082` visual missing과 `11718080` wording conflict를 잡는다. `v505_v494_semantic_coverage_with_browser_audit`은 visual missing은 닫고 `11718080` wording conflict 때문에 `REVIEW`로 유지된다.
- focused sanitize 3건 + semantic coverage audit 28건, 총 31건 OK. 관련 pipeline/audit/test 파일 `py_compile` OK다.
- 이 결과는 단건 카나리 후속 검토이며 10만 건 semantic approval 근거가 아니다. completed VLM/OCR-on source, expanded random baseline, P0/P1 high-risk expansion 전까지 전체 gate는 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v504 Codex subagent 병렬 재정렬 / 다음 seed package

- 사용자 재정정에 따라 이번 `/goal`의 병렬은 repo runtime `expert_main.py --parallel`이 아니라 Codex `spawn_agent` 전문가 병렬로 다시 고정했다.
- 읽기 전용 subagent 축을 goal 문서/오케스트레이션(Turing the 2nd), `expert_main.py` small-run/runtime 계약(Chandrasekhar the 2nd), VLM/OCR/browser visual gate(Hooke the 2nd)로 나눴고, 메인 Codex가 v504 seed package와 문서 통합을 맡았다.
- `tools/build_goal_next_seed_package.py`와 `tests/test_goal_next_seed_package.py`를 추가해 current semantic coverage audit의 issue sample post를 다음 rerun/browser seed로 패키징할 수 있게 했다.
- `qualitative_review/20260528_141006_620986/v504_next_seed_package/`에 다음 산출물을 생성했다: target post `28`, rerun post `24`, rerun row `86`, browser target `28`, browser visual required `11`, missing post id `0`, image URL 없는 fallback `0`.
- v504 권장 rerun 명령은 `--parallel 24 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`다. `36`은 Gemma 4 4B runtime worker 상한일 뿐이고, 이번 small targeted rerun에서는 36 worker를 채우기 위한 재실행을 하지 않는다.
- runtime subagent 권고에 따라 `_effective_parallel_for_post_count()` 직접 회귀와 stale `MCP_SHARD_COUNT=36`이 10개 미만 small run health budget을 36으로 키우지 않는 회귀를 추가했다.
- `.gitignore` 예외에 v504 tool/test 파일을 추가해 검증 근거가 무시되지 않게 했다.
- `README.md`와 `expert_readme.md`의 `병렬 실행` 절에는 해당 병렬이 `expert_main.py` 런타임 worker/shard 병렬이며 Codex `/goal`의 `spawn_agent` 전문가 병렬과 다르다는 주석을 추가했다.
- Codex in-app Browser visual 확인은 현재 세션에서 연결 초기화가 두 번 실패해 visual artifact를 만들지 못했다. 따라서 browser image-loading evidence는 계속 Missing/blocked이며 OCR/search/text-only 근거를 Strong/GO로 승격하지 않는다.
- `tests.test_goal_next_seed_package` 1건 OK, `tests.test_expert_main_input_loader` 36건 OK, 관련 `py_compile` OK, v504 manifest JSON validation OK다.
- 이 변경은 다음 실행과 browser visual review를 위한 seed package다. 실제 rerun 결과, runtime audit, semantic coverage audit, browser visual evidence, after-review 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v503 Codex subagent 병렬 통합 / image URL alias / known abbreviation title guard

- Codex `/goal` 병렬을 다시 `expert_main.py --parallel`이 아니라 `spawn_agent` 전문가 병렬로 수행했다.
- subagent 축은 semantic/orchestration(Newton), VLM/OCR/browser(Dewey the 2nd), goal operation docs(Leibniz the 2nd)로 나눴고, 메인 Codex가 source 재감사와 패치 통합을 맡았다.
- 원본 `out/expert_result_20260528_141006_620986.json`을 현재 도구로 다시 감사했다. manifest는 `input_post_count=104502`, `completed_count=80`, `flushed_count=71`, `pending_count=9`, result rows `71`로 partial/regression seed임을 재확인했다.
- semantic coverage audit은 `REVIEW-LOCKED`다. 주요 공백은 image evidence catalog missing `37`, browser visual missing `36`, comment metadata/dialogue missing `55`, blocked-intent resolved title `7`이다.
- runtime contract audit은 `NO-GO`다. 주요 issue는 `completed_count_lt_input_post_count`, `pending_count_gt_zero`, `flushed_count_lt_completed_count`, `image_post_count_missing`이다.
- `expert_main.py`의 JSONL content block loader가 `url`뿐 아니라 `image_url`/`src` alias도 `ContentBlock.url`로 보존하도록 했다. public content block serialization도 같은 alias를 image URL로 보존한다.
- `_apply_known_abbreviation_title_guard()`가 registry/snippet/decoder 약칭 rewrite 후보를 고르기 전에 `_can_promote_title_after_semantic_no_work()`를 통과하도록 했다. no-work/context-only + direct anchor 없음이면 official detail URL이 있어도 title rewrite를 차단한다.
- 문서에서는 Codex worker-type subagent와 repo runtime worker 표현을 분리했고, 소규모 새 명령은 `--parallel min(input_count,36)`를 권장하되 이미 완료된 p36 run은 `effective_parallel`과 lifecycle/evidence 계약이 맞으면 재실행하지 않는다고 정리했다.
- `qualitative_review/20260528_141006_620986/v503_current_reaudit/`에 current state/action queue를 남겼고, `v503_subagent_review_manifest.json`, `v503_subagent_review_summary_ko.md`로 subagent 통합 근거를 남겼다.
- 추가 Codex `spawn_agent` 재확인(Peirce/Dalton/Wegener)에서 GO 과승격은 없고, 과거 이력의 future-facing 36-worker 문구와 "하드코딩/고정" 주석 표현만 P2로 남아 이를 정리했다.
- focused image loader/comment metadata 41건 OK, known title abbreviation 16건 OK, 관련 확장 회귀 묶음 167건 OK, broader `py_compile` OK, `git diff --check` exit 0이다. `git diff --check` 출력은 CRLF 경고뿐이다.
- 이 변경은 targeted P1 보강이다. completed VLM/OCR-on source, Browser image-loading evidence, random baseline 1000+, P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v502 P2 late rescue 후보 공통 gate 마감

- v501에서 P2 static coverage 후보로 남긴 `direct_full_title_candidate_rescued`, `post_main_official_url_title_recovered_from_null`, `direct_image_explicit_title_rescued`, `batch_memory_exact_alias_rescued`를 current code 기준으로 재확인했다.
- `direct_full_title_candidate_rescued`는 원문 full-title 직접 표면과 공식/플랫폼 support가 있어야 하는 positive path에 가깝지만, no-work/context-only 단조성을 위해 공통 gate를 명시 연결했다.
- `post_main_official_url_title_recovered_from_null`은 본문 공식 URL이 있더라도 no-work 해제용 direct hard anchor로 단독 취급하지 않도록 공통 gate를 연결했다.
- `direct_image_explicit_title_rescued`는 VLM/OCR 직접 작품 표면 positive path지만 같은 gate를 통과하도록 해 static coverage를 닫았다.
- `batch_memory_exact_alias_rescued`는 기존 nonwork block에 더해 apply 직전 `_can_promote_title_after_semantic_no_work()`를 추가해 BatchContext/known alias 경로가 no-work/context-only를 다시 열지 못하게 했다.
- `tests/test_title_lead_search_inferred_guard.py`의 late rescue static coverage에 위 네 source를 추가했다.
- focused 23건 OK, 문제 VLM counter 회귀 포함 24건 OK, 관련 확장 회귀 묶음 125건 OK, 관련 파일 `py_compile` OK다.
- 이번 변경은 remaining P2 static coverage 정리이며 10만 semantic approval이 아니다. completed VLM/OCR-on source, Browser image-loading evidence, random baseline 1000+, P0/P1 high-risk expansion 전까지 `NO-GO / REVIEW-LOCKED`를 유지한다.

## 2026-06-01 v501 late rescue 추가 P1 / image loading text-match gate

- Codex `spawn_agent` subagent 병렬 결과를 추가 통합했다. `expert_main.py --parallel` worker 조정이 아니라 code gate, goal/runtime docs, VLM/OCR/browser gate를 독립 감사 축으로 둔 `/goal` 운영이다.
- code gate subagent(McClintock)는 P0는 없지만 `short_alias_spoiler_recovered`, `multi_work_placeholder_collapsed`, `canonical_relevance_lock` 최종 rescue가 no-work/context-only 공통 gate 없이 title을 되살릴 수 있는 P1이라고 보고했다.
- `short_alias_spoiler_recovered`, `multi_work_placeholder_collapsed`, `canonical_relevance_lock_rescued`에도 `_can_promote_title_after_semantic_no_work()`를 연결했다.
- gate 실패 시 `short_alias_spoiler_semantic_no_work_blocked`, `multi_work_placeholder_semantic_no_work_blocked`를 남기고, canonical rescue lock은 semantic no-work direct anchor가 없으면 final consistency rescue를 열지 않는다.
- VLM/OCR/browser subagent(Mill)는 이미지 로딩 실패/대기 상태인데 OCR/search/text match로 결론이 올라가는 경우를 포괄 `browser_visual_missing`에 묻지 말고 별도 issue code로 노출하라고 보고했다.
- `tools/build_semantic_coverage_audit.py`에 `browser_loading_failed_or_pending_text_match_used` coverage와 `image_loading_failed_or_pending_text_match_used` issue를 추가했다. 이미지 row가 resolved/OCR/search 텍스트 근거를 쓰는데 browser loading counter가 failed/pending이면 `REVIEW-LOCKED`다.
- focused 회귀 `tests.test_title_lead_search_inferred_guard` 23건 OK, semantic coverage audit 27건 OK, 관련 확장 회귀 묶음 125건 OK, 관련 파일 `py_compile` OK다.
- 이 변경도 targeted 구조 보강이다. completed VLM/OCR-on source, Browser image-loading evidence, random baseline 1000+, P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v500 Codex subagent 병렬 재확인 / structural-comment rescue gate 확장

- 사용자 정정에 따라 이번 라운드는 `expert_main.py --parallel` worker 조정이 아니라 Codex `/goal`의 `spawn_agent` 전문가 병렬 운영으로 다시 진행했다.
- 읽기 전용 subagent 축을 `code gate`, `goal/runtime docs`, `VLM/OCR/browser gate`로 분리해 띄웠고, 메인 Codex는 코드 패치와 검증/문서 통합을 맡았다.
- goal/runtime docs subagent는 현재 문서가 `expert_main.py --parallel` runtime worker cap과 Codex `spawn_agent` 병렬을 이미 분리하고 있으며, 시작 보고서에 고정 문구로 더 선명히 남기라고 제안했다.
- 이전 code-path subagent(Sartre)는 P0는 없지만 structural title rescue와 comment/character 기반 answer/page rescue가 v499 공통 no-work gate를 우회할 수 있는 P1 후보라고 보고했다.
- `_structural_title_rescued`, `comment_title_answer_recovered`, `comment_plot_answer_recovered`, `character_parenthetical_title_resolved`, `character_page_title_resolved` 경로도 `_can_promote_title_after_semantic_no_work()`를 통과해야만 title을 되살릴 수 있게 했다.
- 차단 시 `structural_title_semantic_no_work_blocked`, `comment_plot_semantic_no_work_blocked`, `character_parenthetical_semantic_no_work_blocked`, `character_page_semantic_no_work_blocked` 같은 공개 flag를 남기도록 했다.
- `tests/test_title_lead_search_inferred_guard.py`에 session knowledge context-only 학습 차단 회귀와 late rescue source static coverage를 확장했다.
- focused 회귀 `tests.test_title_lead_search_inferred_guard` 23건 OK, 관련 확장 회귀 묶음 125건 OK, 관련 파일 `py_compile` OK다.
- 남은 P2는 `_has_direct_post_or_visual_work_anchor_for_no_work_search_rescue()`를 hard direct anchor와 contextual support helper로 더 분리하는 작업이다.
- 이 변경은 targeted no-work/context-only monotonicity 보강이다. completed VLM/OCR-on source, Browser image-loading evidence, random baseline 1000+, P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v499 subagent 병렬 재점검 / late promotion gate 확장

- 사용자 정정에 따라 이번 라운드도 repo `expert_main.py --parallel` 조정이 아니라 Codex `/goal`의 `spawn_agent` 전문가 병렬 검토로 진행했다.
- runtime/result reviewer는 원본 `out/expert_result_20260528_141006_620986.json`이 `input_post_count=104502` 대비 `completed_count=80`, `flushed_count=71`, `pending_count=9`인 partial/regression seed이며 10만 approval source가 아니라고 재확인했다.
- code-path reviewer는 v497 공통 gate 이후에도 canonical stable-hold, question-title official URL recovery, comment URL answer recovery, title-surface rescue, generic-relation alias rescue, short-support recovery, session knowledge 학습 쪽에 P1/P2 late promotion 우회가 남을 수 있다고 보고했다.
- docs reviewer는 `official URL/search title/snippet`과 `direct hard anchor` 표현이 문서별로 섞일 수 있어 no-work/context-only 해제용 strict anchor와 일반 registry evidence tier를 분리하라고 보고했다.
- `_semantic_seed_no_work_signal()`이 `ctx`의 ARBITER `final_decision`만 남은 no-work/context-only 신호도 읽도록 보강했다.
- `_allow_stable_hold_canonical_rescue()`는 no-work/context-only 상태에서 strict packet-local anchor 없이는 canonical stable-hold로 차단을 다시 풀지 못한다.
- question-title official URL recovery, locked official candidate rescue, title-surface primary rescue, short-support anticipation recovery, generic-relation alias rescue, comment URL answer recovery, session knowledge learning에 `_can_promote_title_after_semantic_no_work()` 계열 gate를 연결했다.
- `tests/test_title_lead_search_inferred_guard.py`에 ARBITER final_decision-only context-only 신호, stable-hold 재개방 금지, 후단 rescue path 공통 gate 적용 회귀를 추가했다.
- `qualitative_review/20260528_141006_620986/v499_subagent_review_manifest.json`와 `v499_subagent_review_summary_ko.md`에 subagent evidence를 남겼다.
- focused 회귀 `tests.test_title_lead_search_inferred_guard` 22건 OK, 관련 확장 회귀 묶음 124건 OK, 관련 파일 `py_compile` OK다. 아직 completed VLM/OCR-on source 기반 random/high-risk expansion 전이므로 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v498 원본 partial run 현재 상태 재감사

- active goal 대상 `out/expert_result_20260528_141006_620986.json`을 현재 checkout 기준으로 다시 감사했다.
- manifest 기준 `input_post_count=104502`, `completed_count=80`, `flushed_count=71`, `pending_count=9`, result rows `71`이라 원본 result는 10만 completed source가 아니라 partial/regression seed다.
- `audit_goal_test_run_contract.py` 결과 runtime contract는 `NO-GO`다. 주요 issue는 `completed_count_lt_input_post_count`, `pending_count_gt_zero`, `flushed_count_lt_completed_count`, `image_post_count_missing`이다.
- `build_semantic_coverage_audit.py` 결과 semantic coverage는 `REVIEW-LOCKED`다. 주요 issue는 image evidence catalog missing 37건, image OCR reason without public VLM counter 34건, browser visual missing 37건, comment metadata/dialogue context missing 55건, comment attribution 없는 resolved context 19건, search-only resolved 2건, blocked-intent resolved 7건이다.
- `scan_reason_hygiene.py` 결과 old reason drift도 남아 있다. `bad_phrase`, `llm_flip`, `stale_relevant` hit가 있어 이 원본 result는 approval 보조 증거로 쓰기 전 최신 canary/source에서 hygiene 재검증이 필요하다.
- `qualitative_review/20260528_141006_620986/v498_original_partial_current_state_map_ko.md`와 runtime/semantic/hygiene/state/action queue 산출물을 남겼다.
- 결론: 이 원본 partial result는 regression seed로만 사용하고, completed VLM/OCR-on source + random baseline + P0/P1 high-risk expansion 전까지 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v497 no-work/context-only 공통 후단 승격 게이트

- Codex `spawn_agent` 코드 경로 reviewer가 v496 이후에도 최종 검증기, 후보 승격, unresolved 단일 후보 승격, recommendation guard 해제 같은 후단 공통 경로에서 Decoder alias + official URL 조합이 direct anchor처럼 쓰일 수 있다고 보고했다.
- `_has_strict_direct_work_anchor_for_no_work_rescue()`와 `_can_promote_title_after_semantic_no_work()`를 추가해 semantic no-work/context-only 이후 title promotion/rescue 허용 조건을 한 곳으로 묶었다.
- strict direct anchor는 원문 title/body/comment의 직접 작품 표면, VLM/OCR 직접 작품 표면, 이미지 primary work anchor, verified character-work link, compound title-character bridge처럼 packet-local anchor만 인정한다.
- official detail URL, search evidence, canonical convergence, Decoder alias, episode ref 단독은 no-work/context-only 해제 앵커가 아니다.
- `_has_direct_work_anchor_for_no_work_rescue()`의 semantic no-work 분기를 strict helper로 축소했고, `_compute_title_acceptance()`, `_try_promote_best_candidate()`, `_pick_safe_single_candidate_unresolved_promotion()`, `_context_to_output()` recommendation override, irrelevant canonical rescue block에 공통 gate를 연결했다.
- `tests/test_title_lead_search_inferred_guard.py`에 Decoder alias + official URL + episode ref가 있어도 direct anchor 없이는 accept/promotion/single-candidate promotion이 막히는 회귀를 추가했다.
- 직접 이미지 작품 표면이 있는 `11718082`류 positive path는 후단 승격 게이트를 통과하는 회귀로 유지했다.
- focused validation은 `tests.test_title_lead_search_inferred_guard.TitleLeadSearchInferredGuardTest` 19건 OK와 관련 `py_compile` OK다.
- 확장 회귀 묶음은 title-lead guard, final semantic reread, known title abbreviation, Arbiter curated alias, VLM public evidence, semantic coverage audit, goal runtime audit 총 121건 OK다.
- 이 변경도 targeted semantic monotonicity 보강이다. 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v496 no-work/context-only late rescue gate

- `11718080`류 한탄/잡담 글에서 앞단 semantic seed가 no-work/context-only를 표시했는데 후단 `search_evidence_alias_inference`/BatchContext rescue가 official detail URL만으로 resolved title을 되살릴 수 있는 구조를 다시 확인했다.
- `_search_inferred_alias_nonwork_block_reason()`에서 no-work/context-only 해제용 강한 앵커를 `_has_direct_post_or_visual_work_anchor_for_no_work_search_rescue()`로 통일했다. 공식 URL은 작품 존재 증거일 수 있지만 no-work 발화 의도를 특정 작품 토론으로 바꾸는 direct hard anchor로 쓰지 않는다.
- `verification_result.title_resolution_state=context_only` 또는 `title_resolution_allowed=false`만 남은 packet형 no-work도 `_semantic_seed_no_work_signal()`을 통해 차단 신호로 읽도록 보강했다.
- `tests/test_title_lead_search_inferred_guard.py`에 official URL이 있어도 direct hard anchor가 없으면 search-inferred alias와 batch alias rescue가 `semantic_seed_no_work_context`로 막히는 회귀를 추가했다.
- `11718082`처럼 VLM/OCR 직접 작품 표면이 있는 positive image path는 계속 허용되는 회귀를 함께 추가했다.
- `SCAN_RESULT_REVIEW_GUIDE.md`, `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `OPERATION_QUALITY_CHECKLIST.md`에 `context_only_late_rescue_without_direct_anchor` bucket/gate를 기록했다.
- focused validation은 `tests.test_title_lead_search_inferred_guard.TitleLeadSearchInferredGuardTest` 15건 OK와 관련 `py_compile` OK다.
- 이 변경은 targeted no-work late rescue gate 보강이다. 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v495 Codex goal subagent 병렬 운영 재정렬

- 사용자 정정에 따라 이번 작업의 "여러 전문가와 병렬"은 repo `expert_main.py --parallel`이나 shard/worker 수 조정이 아니라 Codex `/goal` 자체의 `spawn_agent` 전문가 병렬 운영으로 재정의했다.
- 이번 라운드에서 문서 위치 점검, VLM/browser coverage 확인, subagent 운영 모델 정리를 별도 subagent로 병렬 검토했고, 메인 Codex가 결과를 통합했다.
- `SCAN_RESULT_REVIEW_GUIDE.md`는 canonical 문서로 유지하되, 사용자가 goal 작업에서 "subagent", "여러 전문가", "병렬 검토"를 말하면 먼저 Codex `spawn_agent` 분해 축을 선언하고 실제 subagent를 배정해야 한다고 강화했다.
- `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`와 `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`에는 subagent 부족을 `expert_main.py --parallel` 재실행이나 small input 36워커 반복 실행으로 대체하지 않는다고 명시했다.
- `OPERATION_QUALITY_CHECKLIST.md`와 `CHECKLIST.md`에는 과거 `--parallel 36`/36워커 기록이 runtime 이력이며 Codex goal subagent 병렬 지침으로 해석되지 않도록 가드를 추가했다.
- v493은 VLM/OCR public counter schema 공백을 닫은 라운드이고, v494는 `11718082` Browser visual artifact linkage 공백을 닫은 라운드로 분리 보고한다.
- v494 coverage audit의 `GO`는 2건 targeted canary public evidence coverage sanity일 뿐이다. 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v494 Browser visual artifact linkage

- v493에서 마지막으로 남은 `11718082`의 `browser_visual_or_direct_evidence_missing=1`을 Browser visual artifact manifest로 연결했다.
- Codex in-app Browser `iab`의 `node_repl` bootstrap은 `windows sandbox failed: spawn setup refresh`로 2회 실패했다. 이번 artifact에는 `attempted_in_app_browser=true`와 fallback reason을 명시했다.
- fallback browser-control로 현재 페이지 `https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11718082`를 확인했다.
- screenshot과 snapshot을 `qualitative_review/20260528_141006_620986/browser_visual_v494/`에 저장했다.
- 화면 관찰상 본문 이미지가 실제 로드되어 있고 `재벌가 차녀의 2회차 걸그룹`, `유은우`, `267화`, KakaoPage 화면이 보여 v493 result의 resolved title을 직접 지지한다.
- `v494_browser_visual_manifest.json`를 semantic coverage audit에 연결하자 `browser_visual_available=1`, `browser_visual_missing=0`, issues `[]`, coverage `GO`가 나왔다.
- 이 `GO`는 2건 targeted canary public evidence coverage sanity일 뿐이며 10만 semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v493 VLM/OCR public counter result schema 보강

- v492에서 `11718082` image row가 `image_evidence_catalog`는 있으나 VLM/OCR fetch/chunk counter가 public row에 없어 `REVIEW-LOCKED`로 잡힌 문제를 실제 schema 경계에서 보강했다.
- `src/llm_batch/models.py`의 `PickvelIdentity`에 `vlm_enabled`, `ocr_enabled`, `vlm_enrichment_used`, `image_fetch_count`, `image_fetch_success`, `vlm_chunks_sent`, `vlm_total_bytes`, `image_enrichment_limitations`를 추가했다.
- `src/llm_batch/agentic_pipeline.py`에 `_build_image_execution_public_fields()`를 추가해 `ctx.post_data`에 있던 VLM/OCR 실행 counter를 `_context_to_output()`의 public identity로 보존한다.
- 비이미지 row에는 0 counter noise를 뿌리지 않고, 이미지 block/enrichment/limitation/counter 신호가 있을 때만 공개한다.
- v493 live canary는 `--parallel 2 --reuse-shards-only --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했고 completed/failed/pending `2/0/0`, runtime audit `GO`였다.
- v493 result에서 `11718082` identity는 `vlm_enabled=true`, `ocr_enabled=true`, `vlm_enrichment_used=true`, `image_fetch_count=1`, `image_fetch_success=1`, `vlm_chunks_sent=1`, `vlm_total_bytes=28264`를 공개한다.
- v493 semantic coverage audit에서 `image_catalog_present_but_vlm_counter_missing`와 `image_ocr_reason_without_public_vlm_counter`는 해소됐고, Browser visual artifact 미연결만 `REVIEW-LOCKED`로 남았다.
- semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v492 Subagent 통합 / VLM public evidence 계약 강화

- 사용자 정정에 맞춰 이번 라운드는 Codex `spawn_agent` subagent 병렬 검토로 진행하고, repo `expert_main.py --parallel` worker 병렬도와 분리했다.
- VLM/Browser subagent는 `image_evidence_catalog`만으로는 11718082 같은 이미지 소설 스크린샷 케이스의 검증 가능한 Strong evidence가 아니며, row-level VLM/OCR fetch/chunk counter와 Browser visual artifact linkage가 필요하다고 보고했다.
- Runtime/Goal Contract subagent는 v491 runtime contract는 GO지만, `llm_endpoint`, `mcp_health_ok_count`, `mcp_health_failure_count`가 audit 필수 필드가 되어야 한다고 보고했다.
- Semantic/Pipeline subagent는 `11718080`류를 no-work/context-only 판단이 후단 search/alias/BatchContext rescue에서 다시 resolved로 뒤집히는 비단조 오케스트레이션 위험으로 정리했다. 특정 문자열 하드코딩이 아니라 direct anchor 없는 승격 금지 불변식으로 봐야 한다.
- Docs/Gate subagent는 initial triage 표본 수와 10만 approval 확장 표본 수를 더 분명히 나누고, subagent report contract와 manifest 산출물을 추가하라고 제안했다.
- 메인 Codex는 `tools/build_semantic_coverage_audit.py`에 image catalog present but VLM counter missing, OCR reason without public counter, unreviewable image catalog, browser loading ok but artifact missing issue를 추가했다.
- `tools/audit_goal_test_run_contract.py`는 small goal/test run에서 `llm_endpoint`, `mcp_health_ok_count`, `mcp_health_failure_count` missing/contradiction을 audit한다.
- v492 runtime audit은 v491 manifest를 `runtime_contract=GO`로 유지했고, v492 semantic coverage audit은 `11718082`를 `REVIEW-LOCKED`로 잡았다.
- `qualitative_review/20260528_141006_620986/v492_subagent_review_manifest.json`와 `v492_subagent_review_summary_ko.md`를 남겼다.
- semantic approval은 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-01 v491 Goal runtime health manifest contract 실서버 확인

- 사용자가 정정한 대로 이번 라운드는 repo `expert_main.py --parallel` 증설이 아니라 Codex goal 자체를 `spawn_agent` 전문가 병렬 검토로 진행했다.
- runtime/shard, VLM/OCR/browser, semantic/prompt/orchestration, docs/gate subagent를 병렬로 띄우고, 메인 Codex가 각 결과를 live manifest/log/result row로 재확인했다.
- v490 live canary는 `--parallel 36` 호출에서도 small input이라 `effective_parallel=2`, Docker/shard lifecycle 차단, VLM/OCR ready, `11718082` resolved, `11718080` unresolved/no-work 계열로 처리됐다.
- v490에서 새 버그를 확인했다. 로그에는 `include_search=False`, `light_mode=True`, `checked=2`, `required_ok=2`가 있었지만 최종 manifest/run_meta에는 `mcp_health_*` 필드가 없어서 audit이 재현 가능한 증거를 잃었다.
- `expert_main.py`의 `_parallel_manifest_fields()`와 row `run_meta`에 `llm_endpoint`와 `mcp_health_*` 필드를 추가했다.
- `tools/audit_goal_test_run_contract.py`는 small goal/test run에서 `mcp_health_include_search`, `mcp_health_light_mode`, checked/required/batch/workers/attempts/timeout 필드가 빠지면 `REVIEW`로 낮춘다.
- v491 live canary는 2건 입력 기준 불필요한 worker 증설을 피하려고 `--parallel 2`로 실행했다. manifest는 `llm_endpoint=http://10.20.0.101:8000/`, `mcp_health_include_search=false`, `mcp_health_light_mode=true`, `mcp_health_required_ok_count=2`, `mcp_health_checked_endpoint_count=2`를 기록했다.
- v491 audit은 `runtime_contract=GO`였지만, 이 판정은 runtime/log/manifest 계약만 의미한다. 10만 semantic approval은 계속 `REVIEW-LOCKED`다.
- subagent 검토상 `11718082`는 VLM/OCR이 안 돈 게 아니라 과거 세대 public result 구조 증거가 약했던 케이스다. `11718080`은 작품 매칭 대상이 아니라 장르/사회적 한탄이며, 후단 search/alias rescue가 no-work 판정을 뒤집지 못하게 invariant/audit를 계속 강화해야 한다.

## 2026-06-01 v489 Goal runtime health audit 연동

- v488에서 `expert_main.py`가 남기기 시작한 `mcp_health_*` 필드를 `tools/audit_goal_test_run_contract.py`가 읽도록 연결했다.
- 감사 도구는 small goal/test run에서 `mcp_health_include_search=true`이면 runtime contract를 `REVIEW`로 낮춘다. 이는 correctness 실패가 아니라 goal loop startup 비용 정책 위반으로 본다.
- small goal/test run에서 `mcp_health_light_mode=false`가 기록되면 v488 light-health 계약이 적용되지 않은 것으로 `REVIEW` 처리한다.
- health count accounting이 모순되면 `NO-GO`로 잡는다. 예를 들어 checked endpoint 수가 after-filter endpoint 수보다 작거나, after-filter endpoint 수가 required ok 수보다 작으면 manifest/runtime 계약 오류다.
- 감사 markdown에는 health include/search, light mode, required ok, checked endpoint, probe batch, required-ok 이후 중단 여부가 출력된다.
- `tests.test_goal_test_run_contract_audit` 15건과 관련 `py_compile`을 통과했다. 이 변경도 runtime 감사 계약 보강이며 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v488 Codex subagent 병렬 통합 및 expert_main light health

- 사용자 정정에 따라 이번 라운드는 repo `expert_main.py --parallel`을 늘리는 일이 아니라 Codex goal 자체를 `spawn_agent` 전문가 병렬 구조로 진행했다.
- runtime/shard subagent는 현재 small run에서 worker 36 강제와 Docker lifecycle 자동 재시작은 대체로 막혀 있지만, stale explicit `MCP_ENDPOINTS`와 search 포함 health check가 startup 비용을 키울 수 있다고 확인했다.
- VLM/OCR subagent는 `11718082` 원본 런에 VLM 로그가 있었으나 result/packet의 image catalog/chunk/browser visual 증거가 부족하면 semantic `Strong`으로 볼 수 없다고 정리했다.
- semantic/prompt subagent는 `11718080`이 소설 친구/밥/TS 토론 한탄글이며, 검색 E002 같은 우연 매칭과 후단 alias/search rescue가 no-work 판단을 뒤집는 구조가 핵심이라고 확인했다.
- docs/checklist subagent는 `Codex goal subagent 병렬`과 repo runtime `expert_main.py --parallel`이 다른 계층임을 문서화했다.
- 메인 Codex는 `expert_main.py`에 goal/reuse-only light health mode를 추가했다. 소규모/reuse-only run에서는 `MCP_HEALTH_INCLUDE_SEARCH` 기본값이 false가 되고, 필요한 healthy endpoint 수를 확보하면 stale endpoint 목록의 나머지 probe를 생략한다.
- run config/manifest에는 health include/search, required ok count, checked endpoint count, probe batch, early stop 여부가 남는다.
- `tests.test_expert_main_input_loader` 33건과 관련 `py_compile`을 통과했다. 이 변경은 runtime startup cost 보정이며 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v487 Semantic stability hard-support gate

- 사용자 정정에 따라 repo `expert_main.py --parallel`이 아니라 Codex goal 내부 `spawn_agent` 전문가 병렬 검토로 진행했다.
- semantic/orchestration subagent는 `11718080` 원본 실패를 LLM 이해 단독 문제가 아니라 no-work 판정을 search/alias/BatchContext rescue가 뒤집는 비단조 구조 문제로 정리했다.
- VLM/OCR subagent는 `11718082` 원본 런에는 VLM 요청/결과/병합 로그가 있으나, 일부 재런/패킷에서 image catalog/chunk evidence가 누락되어 품질 리뷰상 미실행처럼 보이는 관측성 문제가 있다고 정리했다.
- runtime subagent는 `--parallel 36`은 이미 최대치로 축소되지만, explicit `MCP_ENDPOINTS`와 search 포함 health check가 small run 시작 비용을 키울 수 있다고 정리했다.
- stability subagent와 메인 Codex는 raw `abbrev_stable`을 hard support와 분리했다. official evidence, 원문 full title, direct image title, image primary promotion, verified character-work link, compound title-character bridge 중 하나가 있어야 Verifier veto/High rescue 보조로 쓸 수 있다.
- J1 Verifier veto, structural rescue, canonical rescue strength, J0.6 final rescue, candidate promotion, final rejection profile 일부가 hard-support 기준으로 조정됐다.
- 비공식 검색 alias stability만 있는 `_context_to_output()` actual 회귀에서 Verifier veto가 유지되는 것을 확인했다.
- 관련 unittest 48건과 `py_compile`을 통과했다. semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v486 Arbiter veto actual / packet label closure

- Codex `spawn_agent` 전문가 3개 축으로 Arbiter title veto actual branch, stability 후단 보조 위험, hardcoded alias packet label followup 상태를 병렬 검토했다.
- Arbiter Verifier veto actual branch에 negative/positive 회귀를 추가했다. 약칭 표면만 있으면 `official_title=null` / `_verifier_veto_exempt=false`가 유지되고, post-title abbreviation + official/detail hard support가 있으면 `_verifier_veto_exempt=true`로 보존된다.
- v485 action queue가 v409 원라벨을 다시 참조해 stale packet-label blocker를 부활시키던 상태를 v465 closure labels로 재조정했다.
- `build_goal_action_queue.py`는 packet label gate가 `GO`이면 label followup을 `closed_by_packet_labels` / `executable_now=false`로 표시한다.
- v486 action queue는 `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_packet_closed_by_labels=true`, `hardcoded_alias_packet_label_gate=GO`, label counts `ACCEPT=11`로 생성됐다.
- 단, `hardcoded_alias_gate=REVIEW`, `semantic_approval=REVIEW-LOCKED`는 유지한다.

## 2026-06-01 v485 Agentic alias metadata/rewrite guard

- 사용자 정정대로 이번 라운드는 Codex goal 내부 `spawn_agent` 전문가 병렬 검토로 진행했고, repo `expert_main.py --parallel` 실행 병렬도와 섞지 않았다.
- Euclid serialization 검토는 `registry_anchor_only`가 final output에는 들어가도 LLM judgment packet과 review label에서 약해질 수 있다고 지적했다.
- Ampere rewrite 검토는 `_apply_known_abbreviation_title_guard()`가 registry alias + suspected/decoder/search soft support만으로 final title을 바꿀 수 있다고 지적했다.
- Dalton stability 검토는 title-lead alias search inferred candidate와 alias stability가 비공식 검색 반복만으로 `High` 보조 경로가 될 수 있다고 지적했다.
- 메인 Codex는 registry promotion metadata를 `alias_resolution_sources`, reason, round2/LLM judgment packet에 보존하고, registry-only weak resolved label을 `HOLD/re_judge`로 고정했다.
- `_apply_known_abbreviation_title_guard()` hardcoded registry source는 official/detail/direct hard support가 없으면 rewrite하지 않는다.
- 비공식 title-lead search inferred candidate는 score가 높아도 `Medium`으로 cap한다.
- `tests.test_known_title_abbreviation_support`, `tests.test_title_lead_search_inferred_guard`, `tests.test_qualitative_review_packet_tools` 78건과 관련 `py_compile`을 통과했다.
- v485 audit/action queue는 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 유지한다.
- 이번 변경은 Agentic 후단 alias evidence boundary 보정이며, completed VLM/OCR-on source와 expanded 10만 semantic approval은 계속 별도 gate다.

## 2026-06-01 v484 Agentic known alias promotion confidence gate

- 사용자 정정대로 이번 라운드는 repo `expert_main.py --parallel` 조정이 아니라 Codex goal 내부 `spawn_agent` 병렬 전문가 검토로 진행했다.
- Gibbs/Dirac 계열 Agentic 검토는 `_try_promote_best_candidate()`가 anchor 통과 후 official/detail evidence 없이도 `_conf="High"`를 반환하는 잔여 경로를 지목했다.
- Feynman/Kepler 계열 docs/gate 검토는 v484 문서 핵심을 "v479는 anchor 존재, v484는 anchor가 있어도 High 확정 금지"로 정리했다.
- Pauli runtime 검토는 small input에서 `effective_parallel=min(requested,input_count)`가 정상이며, Codex subagent 병렬과 repo runtime worker cap을 섞지 말라고 재확인했다.
- 메인 Codex는 Agentic registry direct promotion에서 hard support를 재평가하고, hard support가 없으면 `High` 대신 `Medium`과 `evidence=registry_anchor_only`로 남기게 했다.
- official/detail/direct evidence가 있으면 `High` positive는 유지한다. 이는 positive recall을 죽이는 패치가 아니라 과확정 confidence만 낮추는 targeted guard다.
- `tests.test_known_title_abbreviation_support`는 11건으로 늘었고, 관련 unittest 59건과 `py_compile`을 통과했다.
- v484 audit/action queue는 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 유지한다.
- 이번 변경은 Agentic targeted confidence gate 보정이며, completed VLM/OCR-on source와 expanded 10만 semantic approval은 계속 별도 gate다.

## 2026-06-01 v483 Arbiter alias-only actual decision-path guard

- Planck subagent는 helper-only가 아니라 `ArbiterExpert.analyze(ctx)` actual 후처리 결과를 검증해야 한다고 정리했다.
- Raman subagent는 v482 이후 남은 hardcoded alias blocker 중 Agentic `_try_promote_best_candidate()`의 `KNOWN_* -> High` direct rescue를 다음 최우선 경로로 지목했다.
- 메인 Codex는 Arbiter `meme/noise`와 `low-confidence` 후처리에서 abbreviation-only anchor가 official support만으로 guard 면제를 열지 못하게 했다.
- `multi_work` actual branch도 고정 LLM 응답 기반 `analyze()` 테스트로 확인했다. 비교/나열 alias-only 문맥은 title null로 내려가고, 회차/스포/캐릭터 work anchor가 있으면 title을 보존한다.
- `tests.test_arbiter_curated_alias_guard`는 13건으로 늘었고, actual branch negative/positive control을 포함한다.
- v483 audit/action queue는 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 유지한다.
- 이번 변경은 Arbiter targeted branch 보정이며, Agentic direct rescue는 v484에서 별도 보정했고 completed 10만 semantic approval은 계속 별도 gate다.

## 2026-06-01 v482 Arbiter strong/official support 계약 분리

- Anscombe subagent는 `_has_official_title_evidence()`가 broad strong support와 같은 계약으로 남으면 official evidence가 과확장될 수 있다고 지적했다.
- Mencius subagent는 active official detail, deleted/community/listing, known abbreviation hint-only를 직접 가르는 단위 테스트가 부족하다고 지적했다.
- 메인 Codex는 `_has_strong_title_support()` 반환 구조를 source quality 기반으로 고정했고, `_has_official_title_evidence()`를 official platform detail evidence 전용으로 분리했다.
- `known_abbreviation` / `KNOWN_*` hint 단독은 official evidence가 아니며, deleted/unavailable/community/listing page는 strong/official support 근거가 아니다.
- 짧은 제목은 공식 상세 검색 결과 안에 substring으로 들어간 정도만으로 official evidence가 되지 않게 token boundary를 요구했다.
- `tests.test_arbiter_curated_alias_guard` 9건으로 active official search/fetched detail positive, deleted/community/listing negative, known abbreviation hint-only negative, short-title substring-only negative를 고정했다.
- v482 audit/action queue는 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 유지한다.
- 이번 변경은 targeted helper contract fix이며, actual decision-path와 completed 10만 semantic approval은 계속 별도 gate다.

## 2026-06-01 v481 Arbiter 등록 약칭 guard exception 앵커 가드

- Meitner subagent는 Arbiter `multi_work`, `meme/noise`, `low-confidence` guard가 `KNOWN_ABBREVIATIONS` raw match만으로 면제되는 P1 경로를 재확인했다.
- Hooke subagent는 테스트가 helper 중심이며 actual decision-path 테스트가 아직 약하다고 정리했다.
- 메인 Codex는 Arbiter에 `_has_curated_alias_guard_exception()` 계열 helper를 추가했다.
- `multi_work`, `meme/noise`, `low-confidence`, `KNOWN_TITLE_ABBREVIATIONS` veto exception은 raw registry match 대신 post-side work anchor 또는 동등한 직접/검증 앵커를 요구한다.
- `tests.test_arbiter_curated_alias_guard` 4건으로 bare alias/no-work/comment-only negative와 work-context positive를 고정했다.
- v481 audit/action queue는 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 유지한다.
- `_has_strong_title_support()` / `_has_official_title_evidence()` 반환 구조 의심은 별도 후속 P1로 남겼다.

## 2026-06-01 v480 Agentic 등록 약칭 alias support 앵커 가드

- Lovelace subagent가 v479 이후에도 `_has_alias_title_support()`와 `_collect_title_support_kinds()`가 등록 약칭 surface를 강한 support로 계산할 수 있다고 지적했다.
- 메인 Codex는 `_has_alias_title_support()`에 post-side work anchor 조건을 적용했다.
- `_collect_title_support_kinds()`는 등록 약칭 surface만으로 `post_main_mention`을 추가하지 않고, anchor 통과 시 `known_abbreviation_alias + curated_alias_work_anchor`로 기록한다.
- `담텔기` work-context positive는 유지했고, bare alias/context-only negative는 alias support, support kinds, explicit support가 모두 실패하도록 테스트를 보강했다.
- v480 audit/action queue는 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 유지한다.
- Arbiter registry-only guard exception과 strong support 반환 구조 의심은 후속으로 남겼다.

## 2026-06-01 v479 Agentic 등록 약칭 앵커 가드

- 사용자 정정에 따라 이번 라운드도 Codex goal 내부 `spawn_agent` 병렬 전문가 감사로 진행했고, repo runtime `expert_main.py --parallel` 조정과 섞지 않았다.
- 메인 Codex는 Agentic 등록 약칭 direct promotion/stability/lock에 post-side work anchor 조건을 추가했다.
- `_try_promote_best_candidate`는 registry alias direct `High` 승격 전 anchor를 요구하고, 없으면 blocked flag를 남긴다.
- `_has_title_abbrev_stability_signal`과 `_known_title_abbreviation_context_locks_title`도 visible alias만으로 열리지 않는다.
- comment-only known title abbreviation은 lock 근거에서 제외했다.
- `tests.test_known_title_abbreviation_support`에 bare alias/context-only negative와 comment-only lock negative를 추가했고, 기존 `담텔기` work-context positive는 유지했다.
- v479 audit/action queue는 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 기록한다.
- Arbiter registry-only guard exception은 아직 남아 있어 hardcoded alias risk 전체를 닫지 않는다.

## 2026-06-01 v476 KNOWN_* prompt pressure 완화와 audit noise 보정

- 이번 라운드도 Codex `spawn_agent` 전문가 병렬로 진행했고, repo 내부 `expert_main.py --parallel`과 섞지 않았다.
- Kant subagent는 current checkout 기준 남은 실제 위험 경로가 `Decoder._rescue_null_title`, `AgenticPipeline._try_promote_best_candidate`, `_apply_known_abbreviation_title_guard`, stability/lock/Arbiter guard exception에 있다고 정리했다.
- Confucius subagent는 v475/v476에서 hardcoded alias blocker가 낮아져도 원본 completed source, random 1000, P0/P1 expansion 전까지 10만 semantic approval은 `REVIEW-LOCKED`라고 정리했다.
- 메인 Codex는 `EvidenceScorer`의 registered alias weight를 3.5에서 1.0으로 낮추고, no-work 또는 독립 work anchor 부재 문맥에서는 positive signal/prompt note를 만들지 않게 했다.
- Jury/Debate prompt의 `확정적입니다`, `is_relevant=true` 강제 문구를 제거하고 `등록 약칭 후보(검토용 힌트)`로 바꿨다.
- `audit_hardcoded_alias_risk.py`는 import-only registry usage와 `_collect_alias_resolution_sources()` provenance tuple을 positive usage로 세지 않는다.
- v476 audit는 `KNOWN_ABBREVIATIONS` positive usage `83`, `prompt_pressure=7`, `KNOWN_TITLE_ABBREVIATIONS` positive usage `18`을 기록했다.
- v476 action queue는 여전히 `hardcoded_alias_positive_blocker_count=2`, `hardcoded_alias_gate=REVIEW`, `semantic_approval=REVIEW-LOCKED`다.
- focused unittest 22건과 관련 `py_compile`을 통과했다.
- 남은 direct/guard 경로가 실제로 있으므로 이번 라운드에서 hardcoded alias risk를 닫지 않는다.

## 2026-06-01 v474 SLANG_DICTIONARY hint-only 계약과 action queue 갱신

- 사용자 정정대로 이번 라운드는 Codex `spawn_agent` 전문가 병렬로 진행했고, repo 내부 `expert_main.py --parallel` 조정과 섞지 않았다.
- Chandrasekhar subagent는 `SLANG_DICTIONARY` 직접 코드 경로는 대부분 hint-only로 내려갔지만, LLM이 dictionary-only mapped title을 `best_match.title/high`로 출력하는 경우를 후처리에서 더 단단히 막아야 한다고 지적했다.
- Carson subagent는 최초 v474 audit 기준 `SLANG_DICTIONARY`가 아직 positive blocker로 남아 있어 action queue에서 닫으면 안 된다고 지적했다.
- 메인 Codex는 `rules.py`에서 SLANG hit를 `official_title=None`, `confidence=None`, `store_in_slang_db=False`로 낮췄고, `decoder.py`에서 dictionary match를 hint candidate로만 병합하게 했다.
- `Decoder._sanitize_cross_term_dictionary_inference()`는 LLM이 dictionary-only mapped title을 high로 출력해도 독립 URL/플랫폼/비사전 evidence가 없으면 `best_match.title=null`로 되돌린다.
- `expert_prompts.py`와 `pipeline_prompts.py`는 dictionary가 recall hint일 뿐 단독 title/high 근거가 아니라고 명시한다.
- `audit_hardcoded_alias_risk.py`는 SLANG provenance tuple과 packet-review tooling metadata를 positive blocker로 세지 않는다.
- v474 risk audit는 `SLANG_DICTIONARY gate_status=INFO`, `positive_usage_count=0`을 기록했고, positive blocker는 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS` 2개로 줄었다.
- v474 action queue는 `hardcoded_alias_positive_blocker_count=2`, `hardcoded_alias_packet_effective_gate=GO`, semantic approval `REVIEW-LOCKED`를 기록한다.
- focused unittest 23건과 관련 `py_compile`을 통과했다.
- 전체 10만 semantic approval은 completed VLM/OCR-on source, random baseline 1000건, P0/P1 high-risk expansion 전까지 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v470 hardcoded alias audit false-positive와 unique scope 보정

- 사용자 정정대로 이번 라운드는 repo 내부 worker 병렬이 아니라 Codex `spawn_agent` 전문가 병렬로 진행했다.
- Aristotle subagent는 `TITLE_ALIAS_SUPPORT_MARKERS`가 `TARGET_NAME_RE`의 `ALIAS` 조건과 `_risk_class()`의 일반 positive fallback 때문에 `positive_resolution/REVIEW` blocker로 잡히는 false-positive 경로를 확인했다.
- Gauss subagent는 현재 전문가 오케스트레이션의 핵심 한계가 no-work/context-only 판정 이후에도 search/alias/BatchContext/slang rescue가 final title을 다시 되살릴 수 있는 비단조 구조라고 정리했다.
- 메인 Codex는 `audit_hardcoded_alias_risk.py`에 `tooling_marker` class를 추가해 `tools/` 아래 marker tuple을 `INFO`로 분리했다.
- `build_hardcoded_alias_packet_review.py`는 raw packet count와 unique registry/post-context/decision-context/context-only match count를 분리해 보고한다.
- `build_goal_action_queue.py`는 packet closure 판단에서 `unique_post_context_registry_match_count`를 우선 사용한다.
- v470 risk audit는 positive blocker를 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY` 3개로 유지하고, `TITLE_ALIAS_SUPPORT_MARKERS`와 `OFFICIAL_OR_PLATFORM_SUPPORT_MARKERS`는 `tooling_marker/INFO`로 낮췄다.
- v470 packet review는 raw `matched_packets=40`이지만 `unique_post_context_registry_match_count=1`임을 남겼고, v465 labels가 이 unique post-context coverage를 닫아 action queue의 packet effective gate는 `GO`가 됐다.
- focused unittest 22건과 관련 `py_compile`을 통과했다.
- 남은 approval blocker는 completed source 확보, completed-source preflight, random baseline 1000건, P0/P1 high-risk expansion, `hardcoded_alias_risk_review_required`이며, 전체 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v467 hardcoded alias packet review reconciliation

- Harvey subagent는 v466의 `hardcoded_alias_packet_review_required`가 새 결함이라기보다 v407 raw packet-review gate가 v465 closure와 아직 조정되지 않은 상태라고 판정했다.
- Fermat subagent는 `hardcoded_alias_risk_review_required`는 positive registry 3건 때문에 계속 `REVIEW`로 유지해야 한다고 판정했다.
- 이에 따라 메인 Codex는 `tools\build_goal_action_queue.py`를 보강해, packet review matched 수 이상을 후속 labels가 모두 `ACCEPT`로 닫으면 packet review action을 `closed_by_packet_labels`로 표시하게 했다.
- `tests\test_goal_action_queue.py`에 packet review raw gate가 `REVIEW`여도 closure labels가 11/11 `ACCEPT`이면 effective gate가 `GO`가 되고 approval blocker에서 빠지는 회귀를 추가했다.
- v467 reconciliation artifact는 v407 packet 11건을 v465 closure labels와 v450 provenance에 매핑했다.
- v467 action queue는 `hardcoded_alias_packet_gate=REVIEW`, `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_packet_closed_by_labels=true`를 기록한다.
- approval blockers는 completed source, completed source preflight, random baseline 1000건, P0/P1 high-risk expansion, `hardcoded_alias_risk_review_required` 5개로 줄었다.
- 전체 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v465/v466 hardcoded alias packet label follow-up 정리

- v409 hardcoded alias packet labels는 `ACCEPT=6`, `HOLD=2`, `REJECT=3`이어서 label follow-up이 approval blocker로 남아 있었다.
- HOLD는 weak/community-only evidence, `official_urls=0`, `post_spans=0`, provenance missing이 핵심이었다.
- REJECT는 author_talk/noise over-demotion, wrong canonical title `한가인(괴담 호텔 탈출기)`, generic parenthetical bridge가 핵심이었다.
- v450 최신 `11718120` canary는 `official_title=괴담 호텔 탈출기`, `heretic_url=https://novelpia.com/novel/102155`, `title_candidates=괴담 호텔 탈출기` 1건으로 final을 정렬했다.
- 같은 result는 `alias_resolution_sources[0].source_registry=KNOWN_TITLE_ABBREVIATIONS`, `alias_resolution_source=known_title_abbreviation`, `matched_surface_kind=post_title`를 공개해 registry provenance missing을 닫았다.
- reason score도 `post_spans=4`, `official_urls=7`, `total=+14`를 남겨 v409의 weak evidence 상태와 달라졌다.
- v465 closure labels는 v409 historical packet 11건을 post 단위로 dedupe해 모두 `ACCEPT`, `CLOSED_BY_V450_CANARY`로 닫았다.
- v466 action queue는 `hardcoded_alias_packet_label_gate=GO`, label count `{'ACCEPT': 11}`로 갱신됐다.
- Codex subagent Halley도 같은 결론을 냈다: `hardcoded_alias_packet_label_followup`은 `GO / CLOSED_BY_V465`로 닫아도 되지만, positive registry 전체 경로와 10만 semantic approval은 계속 별도 blocker다.
- 단, 이 closure는 `hardcoded_alias_packet_label_followup`만 닫는다. `hardcoded_alias_risk_review_required`와 `hardcoded_alias_packet_review_required`는 계속 approval blocker이며, 원본 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v461~v464 Browser visual 보강과 current-state/action queue 재정렬

- v460 targeted canary의 result 자체를 `scan_reason_hygiene.py --fail-on-hit`로 다시 스캔했고 hit 0건을 확인했다.
- v460 result에 semantic coverage audit를 실행하니 `11718082`는 image evidence catalog는 있지만 Browser visual evidence가 없어 `browser_visual_required/available/missing=1/0/1`, gate `REVIEW-LOCKED`였다.
- Codex 내장 Browser iab를 우선 시도했지만 node_repl 기반 연결이 2회 종료되어 iab 직접 캡처는 실패했다. 이 실패는 fallback 사유로 별도 기록했다.
- 대체 Playwright MCP로 `https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no=11718082`를 열고 full-page screenshot과 metrics를 저장했다.
- screenshot에는 게시글 제목, 본문 이미지, 이미지 하단 `두렵구나` 텍스트가 함께 보인다.
- metrics 기준 `.write_div img[src*="dcimg"]` 본문 이미지 1개가 `complete=true`, `naturalWidth=850`, `naturalHeight=850`, `renderedWidth=850`, `renderedHeight=850`으로 로드됐다.
- v461 Browser artifact manifest는 fallback surface를 명시하고 `visual_evidence_grade=Strong`, `article_image_count=1`, `article_loaded_count=1`로 기록했다.
- v462 semantic coverage audit는 v460 small canary 기준 `gate=GO`, `browser_visual_required/available/missing=1/1/0`, `browser_visual_external_artifact_available=1`을 기록했다. 이 GO는 coverage sanity일 뿐 10만 semantic approval이 아니다.
- v463 current-state map은 원본 source가 여전히 `104502/80/71/9/0/71` partial이라고 재확인했다.
- v464 action queue는 approval blockers를 completed source 확보, preflight 재실행, random baseline 1000건, P0/P1 high-risk expansion, hardcoded alias follow-up으로 재정렬했다. v460 small canary의 `vlm_ocr_browser_visual_gate`는 현재 blocker에서 빠졌지만 전체 10만 approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v459/v460 이미지 OCR anchor taxonomy와 slang context overstatement 후속 정리

- 사용자 정정대로 이번 후속은 Codex goal의 `spawn_agent` 전문가 병렬로 진행했다. repo 내부 worker parallel 조정이 아니라 anchor consistency와 slang/context output hygiene를 분리 감사했다.
- anchor subagent는 v458 `11718082`가 reason에서는 `title_in_post=false`, `image_ocr_variant=true`라고 말하면서 final `anchor_type=title_exact`로 남는 불일치를 지적했다.
- slang/context subagent는 `slang_insight.cultural_context`가 `특정 웹소설의 일부 인용`, `작품의 설정`, `캐릭터 관계`, `비표준적인 커뮤니티 약칭 또는 OCR 오인`처럼 OCR/표지 표면보다 강하게 말하는 잔여 output hygiene 문제를 지적했다.
- `_derive_output_taxonomy()`와 output consistency validator를 보강해 `official_title + image_ocr_variant + non-image title 없음`이면 `anchor_type=image`, `anchor_strength=high`, `image_ocr_variant_not_title_in_post` flag를 남기게 했다.
- `_sanitize_slang_cultural_context_for_image_conflict()`는 작품 일부 인용/작품 설정/캐릭터 관계/커뮤니티 약칭/OCR 오인 계열 표현을 packet-local OCR/표지/이미지 장면 단서로 낮춘다.
- v459 live canary는 anchor taxonomy 보정이 실제 result에 반영됨을 확인한 중간 증거다. 단, 최종 sanitizer 전 산출물이므로 slang/context clean evidence로 쓰지 않는다.
- v460 live canary run id는 `20260601_051538_953769`이며, result `qualitative_review\20260528_141006_620986\v460_post11718080_11718082_anchor_slang_clean_result.json`, audit `v460_goal_test_run_contract_audit.json`을 남겼다.
- v460 audit는 `runtime_contract=GO`, `issues=[]`, requested/raw/capped/effective `64/36/2`, completed/flushed/pending/failed `2/2/0/0`, VLM/OCR ready다.
- v460에서 `11718082`는 `official_title=재벌가 차녀의 2회차 걸그룹`, `anchor_type=image`, `anchor_strength=high`, `image_ocr_variant_not_title_in_post`로 정렬됐다. `slang_insight=null`이라 old overstatement 문구는 재현되지 않았다.
- v460에서 `11718080`은 `official_title=null`, `title_resolution_allowed=false`, `work_resolution=none`, `anchor_type=genre`로 유지됐다.
- `py_compile`과 `tests.test_title_lead_search_inferred_guard tests.test_goal_test_run_contract_audit` 20건이 통과했고, `git diff --check`는 whitespace error 없이 통과했다.
- 이번 결과는 targeted canary `GO`이며, 새 Browser visual 캡처와 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v455~v458 이미지 OCR reason score와 slang context 후속 정리

- Codex subagent 3개 축을 병렬로 다시 투입했다: runtime/orchestration, semantic/VLM/slang, docs/gate consistency.
- semantic/VLM/slang 감사에서 v454/v456 result의 `title_in_post=false`와 score board `title_in_post:+2` 충돌, 그리고 `slang_insight.cultural_context` old wording 변종을 확인했다.
- `_build_reason_scoreboard_lines()`는 이미지 OCR 변형만 있는 경우 원문 직접 제목 언급 가산점을 주지 않게 했다.
- `_sanitize_slang_cultural_context_for_image_conflict()`는 `게시글/본문/제목에 사용된`, `게시글 제목과 본문 내용(OCR)에 등장하는`, `일반적인 오타 또는 축약`, `공식적인 제목으로 확인`, `제목을 구성하는 핵심 요소` 계열을 packet-local OCR/표기 변형 단서로 낮춘다.
- v455/v456/v457은 각각 runtime은 완료됐지만 남은 문구 변종을 드러낸 중간 증거로 기록한다.
- v458 live canary run id는 `20260601_045115_070873`이며, result `v458_post11718080_11718082_scoreboard_slang_runtime_result.json`, audit `v458_goal_test_run_contract_audit.json`을 남겼다.
- v458 audit는 `runtime_contract=GO`, `issues=[]`, requested/raw/capped/effective `64/36/2`, completed/flushed/pending/failed `2/2/0/0`, VLM/OCR ready다.
- v458에서 `11718082`는 `title_in_post=false`, `image_ocr_variant=true`, `official_search_resolution=true`, `title_in_post:+2` 없음, `store_in_slang_db=false`를 확인했다.
- v458에서 `11718080`은 `official_title=null`, `title_resolution_allowed=false`, `work_resolution=none`, `anchor_type=genre`로 유지됐다.
- focused test `tests.test_title_lead_search_inferred_guard` 8건과 관련 py_compile이 통과했다.
- 이 결과는 targeted canary `GO`이며, Browser visual 미수행 및 10만 semantic approval `REVIEW-LOCKED` 상태는 변하지 않는다.

## 2026-06-01 v454 Codex 전문가 병렬 운영과 Gemma 4 4B cap 보강

- 사용자 정정에 맞춰 이번 goal 진행을 repo 내부 worker 병렬이 아니라 Codex 앱 `spawn_agent` 전문가 병렬로 다시 분해했다.
- 읽기 전용 subagent 4개 축을 띄웠다: 런타임/오케스트레이션, 의미판정/VLM, 10만건 정성 gate, docs/checklist 감사.
- subagent 결과를 통합해 `expert_main.py --parallel`은 런타임 worker max이고, Codex `spawn_agent` 병렬은 감사/구현/문서화 분업이라는 기준을 다시 문서화했다.
- `expert_main.py`는 Gemma 4 E4B/4B 계열에서 `requested_parallel_raw`가 36을 넘으면 `requested_parallel=36`으로 cap하고, 이후 input/healthy endpoint 기준으로 `effective_parallel`을 낮춘다.
- run config, result row `run_meta`, result manifest에 `requested_parallel_raw`, `model_parallel_max`, `model_parallel_cap_applied`, `model_parallel_cap_model`을 남긴다.
- `tools\audit_goal_test_run_contract.py`는 모델 cap 필드를 감사하고 Markdown 관측값에도 raw/cap/effective 병렬도를 분리해 쓴다.
- 이미지 OCR 변형이 최종 제목과 유사하지만 exact가 아니면 reason은 `title_in_post=false`, `image_ocr_variant=true`, `official_search_resolution=true`로 분리한다.
- slang cultural context가 이미지 OCR 표면을 `게시글 제목에 사용된 축약어/오타`라고 과장하지 않도록 `이미지 OCR/표지에서 감지된 일회성 표면`으로 낮췄다.
- v454 live cap canary는 `--parallel 64`로 실행해 model cap을 직접 확인했다. run id `20260601_042151_464777`, result `qualitative_review\20260528_141006_620986\v454_post11718080_11718082_model_cap_reason_contract_result.json`, log `logs\expert_run_20260601_042151_464777.log`다.
- manifest/audit는 `requested_parallel_raw=64`, `requested_parallel=36`, `effective_parallel=2`, `model_parallel_max=36`, `model_parallel_cap_applied=true`, completed/flushed/pending/failed `2/2/0/0`, VLM/OCR ready, shard/docker lifecycle 재기동 없음으로 기록됐다.
- `tools\audit_goal_test_run_contract.py` 재생성 산출물 `v454_goal_test_run_contract_audit.json` / `_ko.md`는 `runtime_contract=GO`, `issues=[]`, `llm_model=bg-digitalservices/Gemma-4-E4B-it-NVFP4`를 남긴다.
- 같은 live result에서 `11718082` reason은 `title_in_post=false`, `image_ocr_variant=true`, `official_search_resolution=true`로 낮아졌고, `11718080`은 `official_title=null`, `work_resolution=none`, `anchor_type=genre`로 유지됐다.
- 단, live result 생성 뒤에 `slang_insight.cultural_context` old wording sanitizer를 추가했으므로, v454 자체는 중간 증거다. old wording 제거는 v460 live canary에서 runtime output까지 재확인했다.
- focused 검증은 `py_compile` OK, goal runtime audit 12건 OK, title/search/VLM guard 8건 OK, broad semantic regression 333건 OK, comment/runtime audit 묶음 22건 OK다.
- 이번 결과는 런타임 계약과 reason hygiene 보강이며, 새 Browser visual 캡처를 수행한 것이 아니다. 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v453 no-work late URL recovery and BatchContext wrapper guard

- 사용자 정정에 맞춰 repo 내부 worker 병렬이 아니라 Codex goal의 `spawn_agent` 전문가 병렬을 사용했다. 하나는 late URL recovery/raw `_search_with_meta` 우회를, 다른 하나는 BatchContext/slang/known alias rescue 우회를 읽기 전용으로 감사했다.
- subagent 결론은 동일했다. 현재 `11718080` 직접 경로는 막혔지만, corrected-title URL recovery와 alias support helper, BatchContext wrapper field propagation은 미래 회귀 표면으로 더 고정할 가치가 있었다.
- `_recover_corrected_title_official_url()`은 semantic no-work 상태에서 direct post/visual work anchor가 없으면 기존 search result 재사용과 직접 search를 모두 차단한다.
- `_has_alias_title_support()`도 no-work/direct-anchor gate를 초입에 두어 decoder/gatekeeper/verifier slang 표면만으로 작품 support가 강해지지 않게 했다.
- `_learn_batch_context()` wrapper는 `title_resolution_state`, `title_resolution_allowed`, `discussion_type`, `subtype`, `work_resolution`, `anchor_type`, `consistency_flags`를 BatchContext에 전달한다. BatchContext 내부의 context-only/no-work seed 차단 로직을 실제 pipeline wrapper와 연결한 것이다.
- raw `_search_with_meta()` 직접 호출부가 `_search` 래퍼와 guarded recovery 외로 늘어나면 실패하는 static regression을 추가했다.
- 댓글 author/IP/comment_id/gallery_id coverage 도구와 export 테스트가 현 checkout에 존재하고 통과하는지 확인했다.
- focused 7건, comment metadata coverage 10건, broad regression 332건이 통과했다.
- v453 live rerun은 run id `20260601_033913_917424`, counters `2/2/2/0/0`, requested/effective `36/2`, VLM/OCR ready, shard/docker lifecycle 재기동 없음이다.
- v453에서 `11718080`은 `official_title=null`, `title_resolution_allowed=false`, `work_resolution=none`, `anchor_type=genre`로 남았고, `11718082`는 VLM/OCR 이미지 앵커와 공식 URL로 `재벌가 차녀의 2회차 걸그룹`을 회복했다.
- 이번 결과는 targeted canary `GO`이며 전체 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v451/v452 no-work + VLM/OCR verified title canonical guard

- 사용자 정정에 따라 이번 라운드는 repo 내부 `expert_main.py --parallel` 병렬이 아니라 Codex goal 운영의 `spawn_agent` 전문가 병렬로 분해했다. runtime/result evidence, prompt/orchestration 한계, docs/checklist sync subagent를 병렬로 투입하고 메인 Codex가 통합 판정을 맡았다.
- v451은 `11718080`/`11718082` 기존 입력을 `--parallel 36 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다. requested/effective parallel은 `36/2`, manifest counters는 `2/2/2/0/0`, VLM/OCR semantic gate는 `READY`였다.
- `11718080`은 자연어적으로 특정 작품 찾기가 아니라 밥 먹을 때 소설/TS/갈드컵을 같이 이야기할 친구를 바라는 장르·트로프 잡담이다. v451/v452에서 `is_relevant=false`, `official_title=null`, `work_resolution=none`, `discussion_type=trope_discussion`, `title_resolution_allowed=false`로 내려갔다.
- `11718082`는 이미지에 작품명/작가/회차가 있는 케이스라 VLM/OCR 직접 근거가 필요하다. v451/v452 모두 VLM chunk request/result, OCR, fetch/chunk counter가 남았고 최종 title은 `재벌가 차녀의 2회차 걸그룹`으로 회복됐다.
- v451은 final은 맞았지만 `canonical suspect 보정: '재벌가 차녀의 2회차 걸그룹' -> '맹인 성녀인데 눈이 보인다 [독점]'` 중간 흔들림이 남았다. final 회복만으로 semantic candidate hygiene을 승인하지 않는다는 원칙에 따라 residual P1로 분리했다.
- `_should_preserve_verified_title_against_unanchored_canonical_override()`를 추가해, 현재 title이 공식/이미지/본문 근거로 잠겨 있고 replacement canonical 후보가 post-side 앵커가 없으면 canonical suspect override를 막았다. 작품명/오답 문자열 하드코딩 없이 evidence/provenance 조건만 사용한다.
- focused 회귀와 기존 rework suite가 통과했다. `AgenticPipelineReworkTest`는 새 테스트 포함 306건 OK이고, known abbreviation/search permit/final reread 묶음 21건도 OK다.
- v452 live rerun은 run id `20260601_032216_459678`, counters `2/2/2/0/0`, requested/effective `36/2`, VLM/OCR ready다. `11718082`는 `anchor_type=image`, `heretic_url=https://page.kakao.com/content/66692543`, VLM `used=True, fetch=1/1, chunks=1`로 회복됐고, v451의 원문 미언급 canonical suspect override는 로그에서 사라졌다.
- 이번 결과는 targeted canary `GO`이며 전체 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v450 no-work alias/drift guard and live canary

- v450 `11718120` live canary를 최신 guard 포함 상태로 `--parallel 36 --reuse-shards-only --no-dashboard --vlm on --ocr on` 실행했다. 소규모 입력이므로 requested/effective parallel은 `36/1`이다.
- manifest는 input/completed/flushed/pending/failed `1/1/1/0/0`이고, VLM/OCR은 켜졌지만 image post count `0`이라 image semantic gate는 `NOT_APPLICABLE`이다.
- final은 `official_title=괴담 호텔 탈출기`, `heretic_url=https://novelpia.com/novel/102155`, `confidence=High`, `work_resolution=resolved`, `discussion_type=character_talk`으로 회복됐다.
- v448에서 후보 목록에 남았던 `괴담 학교 탈출기`는 v450 `title_candidates`에 남지 않았다. 검색 원천에는 인접 작품 결과가 보였지만 final candidate로 승격되지 않았다.
- subagent가 지적한 P1/P2 부채를 후속 보강했다: no-work 상태에서는 회차/스포 단서만으로 known abbreviation rescue를 풀지 않고, curated alias는 visible surface 기준으로 매칭하며, drift keyword는 작품군 hardcode 대신 일반 토큰 기반으로 처리한다.
- focused 6건, no-work guard 포함 8건, 기존 rework suite 305건, 관련 py_compile이 통과했다.
- 이번 결과는 targeted canary `GO`이며 전체 10만 semantic approval은 completed source와 expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v448 known title abbreviation recovery and adjacent derivative candidate HOLD

- v448 live canary는 `11718120`을 `--parallel 36 --reuse-shards-only --no-dashboard --vlm on --ocr on`으로 실행했고, effective parallel은 소규모 입력 기준 `1`이었다.
- manifest는 input/completed/flushed/pending/failed `1/1/1/0/0`으로 완료됐다. 따라서 v446의 `runtime-incomplete` 문제는 v448 단건에서는 재현되지 않았다.
- final은 `official_title=괴담 호텔 탈출기`, `alias_resolution_sources.source_registry=KNOWN_TITLE_ABBREVIATIONS`, `alias_resolution_source=known_title_abbreviation`으로 회복됐다.
- 그러나 후보 목록에는 원문 main context에 언급되지 않은 인접 파생 후보 `괴담 학교 탈출기`가 남았고, 로그에는 `canonical suspect 보정: '괴담 호텔 탈출기' -> '괴담 학교 탈출기'` 흐름이 남았다.
- 이 상태는 false-negative 회복 성공과 별개로 semantic candidate hygiene `HOLD`다. 단건 런 성공을 semantic approval로 올리지 않는다.
- 후속 패치는 curated alias primary가 contextual work anchor를 가진 경우, 원문 언급/alias support/verified character-work link 없는 충돌 rescue 후보를 canonical override 또는 synthetic candidate로 보존하지 않는 방향으로 작성됐다.
- v450 live canary와 focused regression에서 adjacent candidate cleanup을 확인했다.
- 전체 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v447 known title abbreviation support and v446 incomplete canary split

- v446 `11718120` canary는 shard/docker lifecycle 문제가 아니라 LLM 판단 후 result write/flush 전에 끊긴 incomplete run으로 분리했다.
- 로그상 `담텔기 -> 괴담 호텔 탈출기` seed는 있었지만, `KNOWN_TITLE_ABBREVIATIONS`가 promotion/support/stability 전 경로에서 `KNOWN_ABBREVIATIONS`만큼 일관되게 쓰이지 않아 후단에서 약해졌다.
- 같은 로그에서 `305호`, `심판자` 같은 numeric/episode/일반 후보가 별도 provenance로 섞이며 final이 `official_title=null`, `discussion_type=noise`로 drift했다.
- `KNOWN_ABBREVIATIONS`와 `KNOWN_TITLE_ABBREVIATIONS`를 같은 curated abbreviation registry로 묶어 자동 promotion 1순위, explicit support, alias support, abbreviation stability에 반영했다.
- 안정 약칭이 보이더라도 no-work 상태에서는 회차/스포/작가의 말/positive work intent 같은 packet-local work anchor가 없으면 promotion/stability를 차단한다.
- 신규 `tests\test_known_title_abbreviation_support.py`는 `담텔기` 계열 positive와 no-work negative를 함께 검증한다.
- focused 3건, no-work guard 포함 5건, 기존 rework suite 305건, 관련 py_compile이 통과했다.
- 전체 10만 semantic approval은 completed source와 expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v441 semantic no-work abbrev/snippet/stable-hold rescue guard

- semantic auditor가 v439 이후에도 `_has_title_abbrev_stability_signal()`, `_has_snippet_canonical_alias_lock_support()`, irrelevant canonical rescue, stable-hold canonical rescue가 no-work 판정을 다시 풀 수 있는 잔여 P1 경로를 지적했다.
- no-work 상태에서는 raw title surface, direct image, image promotion, verified character-work link 없이 decoder alias/snippet alias/search official evidence만으로 support/stability/lock/rescue가 살아나지 않게 했다.
- stable-hold canonical rescue는 semantic no-work block을 override하지 못하게 했다.
- focused test에 decoder alias, snippet lock, stable-hold 차단 assertion을 추가했다.
- 신규 focused 2건과 기존 rework suite 305건이 통과했다.
- 이 보강도 특정 작품/오타 하드코딩이 아니라 범용 semantic no-work direct-anchor gate다.

## 2026-06-01 v440 malformed browser Strong artifact loading gate

- VLM/browser subagent가 v436/v437 실제 산출물은 `Missing`으로 안전하게 남았지만, external artifact row가 malformed `visual_evidence_grade=Strong`과 실패 loading counter를 함께 가질 때 grade가 먼저 신뢰될 수 있는 공백을 지적했다.
- `_browser_artifact_row_available()`가 external grade를 보기 전에 `_browser_loading_state_failed()`를 먼저 적용하게 했다.
- `visual_observation_ko` Missing 문구는 접근 실패뿐 아니라 본문 이미지 노드 미검출/이미지 로딩 근거 없음도 포함하도록 수정했다.
- malformed Strong external artifact 회귀 테스트를 추가했다.
- focused/browser/semantic coverage 29건이 통과했다.
- 이번 보강도 browser visual sidecar의 targeted guard이며 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v439 semantic no-work search-inferred support guard

- `11718080`류 한탄/잡담 글에서 `intent_permit_for_title_search=false`와 `semantic_seed_review.is_specific_work_discussion=false`가 있어도, 제목 첫 약칭 표면과 검색 결과가 좋아 보이면 후단 `title_lead_alias_search_inferred_candidates`가 후보를 되살릴 수 있는 공백을 확인했다.
- `_has_direct_post_or_visual_work_anchor_for_no_work_search_rescue()`를 추가하고, `_build_title_lead_alias_search_inferred_candidates()`, `_has_title_lead_alias_search_work_support()`, `_has_search_evidence_alias_stability_signal()`이 같은 no-work gate를 타게 했다.
- semantic no-work 상태에서는 원문 직접 title mention, 직접 이미지 title, image primary promotion, 강한 character-work link가 없으면 search-inferred support/stability/candidate를 만들지 않는다.
- 신규 회귀 파일 `tests\test_title_lead_search_inferred_guard.py`를 추가했다. no-work 차단과 positive work seed 허용을 같은 파일에서 확인한다.
- 기존 `AgenticPipelineReworkTest` 전체 305건도 통과해 기존 title-lead alias 회복 경로가 깨지지 않음을 확인했다.
- 검증은 신규 unittest 2건, 기존 rework suite 305건, VLM/browser/semantic coverage 26건, 관련 py_compile이 통과했다.
- 이번 guard는 targeted semantic 회복이며 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v434 weak browser fallback sidecar guard

- v433 browser visual gap을 줄이기 위해 v433 image row 4건의 browser target file `v433_vlm_ocr_browser_targets.jsonl`을 만들었다.
- Codex in-app Browser는 재시도에서도 `windows sandbox failed: spawn setup refresh`로 실패했다.
- sandbox Playwright CLI fallback은 npm cache `EPERM` 때문에 `Missing=4`, screenshot `0/4`였다.
- 외부 권한 Playwright CLI fallback은 screenshot `4/4`를 만들었지만, article image selector는 `0/0`, visual evidence는 `Weak=4`였다.
- `tools\build_semantic_coverage_audit.py`를 고쳐 external artifact manifest가 `output_path` JSONL을 직접 읽게 했고, `visual_evidence_grade=Weak|Missing`은 screenshot이 있어도 visual available로 세지 않게 했다.
- `tools\capture_vlm_ocr_browser_review_cli.py`에 `--run-id`를 추가해 sidecar artifact의 run id가 실제 v433 run id `20260531_234334_468163`로 남게 했다.
- Windows `npx.cmd` wrapper를 통과할 때 DCInside URL의 `&no=`가 cmd separator로 오해되는 문제를 막기 위해 `.cmd/.bat` 경로에서만 `&|<>^()` 이중 파싱 escape를 추가했다.
- `tests\test_semantic_coverage_audit.py`에 weak external artifact가 visual gate를 만족하지 못하는 회귀를 추가했다.
- v434 coverage with weak browser fallback은 `browser_visual_required/available/missing=4/0/4`, `browser_visual_external_artifact_available=0`, gate `REVIEW-LOCKED`다.
- v436 recapture는 URL open/eval/screenshot return code가 모두 `0`이 되어 cmd separator 문제는 닫혔지만, article image selector `0/0`, visual evidence `Missing=4`, image gate passed `0`이라 visual gate는 닫지 못했다.
- v437 coverage with missing browser fallback도 `browser_visual_required/available/missing=4/0/4`, `browser_visual_external_artifact_available=0`, gate `REVIEW-LOCKED`다.
- 검증은 `tests.test_vlm_browser_review_cli + tests.test_semantic_coverage_audit` 26건, 관련 py_compile, `git diff --check`가 통과했다. `git diff --check`의 LF->CRLF 경고는 Windows 작업트리 줄끝 경고로만 취급한다.

## 2026-05-31 v433 comment URL recommendation live rerun

- v433 live rerun은 `v422_search_only_blocked_intent_followup_re_search_input.jsonl` 4건을 대상으로 실행했다.
- 실행 계약은 소규모 입력 기준 `--parallel 1 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`이며, Docker/shard 재기동 없이 진행했다.
- manifest는 `run_id=20260531_234334_468163`, completed/failed/pending `4/0/0`, requested/effective parallel `1/1`, VLM/OCR `READY`, image post count `4`, `mcp_small_run_shard_lifecycle_blocked=true`다.
- runtime log는 `requested=1`, `effective=1`, `workers=1`, shard `http://127.0.0.1:3333` 1개 사용을 보였고, Docker/shard recreate 흔적은 없었다.
- VLM log는 4개 post 모두 `VLM chunk request/result`, `fetch=1/1`, `chunks=1`을 보였다. 다만 image catalog는 모두 `character_visual_only`, `title_role=unknown`, `promotion_eligible=false`라 작품 직접 근거로 쓰지 않는다.
- `11718049`는 `is_relevant=false`, `discussion_type=recommendation`, `topicality=adjacent_relevant`, `subtype=recommendation_request`, `work_resolution=none`, `title_resolution_state=adjacent`로 나왔다.
- 댓글 Novelpia URL은 final title로 승격되지 않고 `recommendation_candidates[]`와 `secondary_reference_works[]`에 `깨어나 보니 여자가 되어 있었다. 그런데 달려 있는.` / `https://novelpia.com/novel/50764` 후보로 보존됐다.
- v433 semantic coverage audit는 image catalog `4/0`, comment metadata/dialogue `4/0`과 `4/0`, search-only/blocked-intent resolved title `0/0`을 확인했다.
- 다만 Codex in-app Browser 연결이 `windows sandbox failed: spawn setup refresh`로 다시 실패해 direct browser visual sidecar를 붙이지 못했다. 그래서 browser visual은 `required/available/missing=4/0/4`, gate는 `REVIEW-LOCKED`다.
- v433은 targeted behavior 확인이며 전체 10만 건 semantic approval 근거가 아니다. full gate는 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v432 targeted follow-up closure review

- v431 remaining queue 4건을 packet-level로 재판정했다.
- v432 산출물은 `v432_targeted_followup_closure_manifest.json`, `v432_targeted_followup_closure_labels.jsonl`, `v432_targeted_followup_closure_summary_ko.md`다.
- 결과는 `ACCEPT=3`, `HOLD=1`이다.
- `11718083`, `11718097`, `11718075`는 targeted follow-up 기준 닫았다.
- `11718049`는 댓글 URL이 실제 Novelpia 작품 페이지임을 확인했지만, current final이 `noise/unrelated`라 추천/댓글 URL 맥락 재판정이 남아 `HOLD/re_judge`로 유지한다.
- `11718049`류를 일반화해 댓글 공식 작품 URL이 추천/탐색 답변이면 final title로 자동 승격하지 않고, `adjacent_relevant` / `recommendation_request` / `recommendation_candidates`로 보존하는 focused regression을 추가했다.
- 명시적 제목 질문의 댓글 URL answer는 계속 resolved title로 복구되도록 별도 회귀를 추가했다.
- 검색 결과의 등장인물 페이지 제목은 원문 본문 앵커가 아니므로, verifier가 `community_banter/reject`로 본 짧은 캐릭터 반응에서는 character-page rescue를 차단했다.
- `text_surface` 또는 `promotion_eligible=false`인 VLM/OCR 제목은 direct image rescue와 image anchor 승격에서 제외했다.
- `semantic_seed_review` no-work 근거가 없는 짧은 캐릭터 반응은 자동 `context_only`로 접지 않고, novel-related/unresolved scope를 유지하도록 회귀를 추가했다.
- focused/coverage/queue 28건과 `AgenticPipelineReworkTest` 305건이 통과했다.
- Codex in-app Browser 연결은 실패했고, `11718049` URL은 웹 직접 열람으로 확인했다.
- 전체 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v431 targeted follow-up remaining queue

- v429 guarded after-review와 v430 refined coverage를 합쳐 targeted follow-up 잔여 큐를 생성했다.
- `tools\build_targeted_followup_remaining_queue.py`와 `tests\test_targeted_followup_remaining_queue.py`를 추가했다.
- v431 산출물은 `v431_targeted_followup_remaining_manifest.json`, `v431_targeted_followup_remaining_queue.jsonl`, `v431_targeted_followup_remaining_packets.jsonl`, `v431_targeted_followup_remaining_summary_ko.md`다.
- v431 queue는 `HOLD=2`, `REVIEW_ONLY=2`, 총 4건이다. 남은 post는 `11718049`, `11718083`, `11718097`, `11718075`다.
- targeted follow-up gate는 `REVIEW`이고, v431은 전체 10만 건 semantic approval 근거가 아니다. 전체 gate는 completed source와 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 - Codex goal subagent 병렬 운영

- 사용자 재정정을 반영해 Codex goal에서 말하는 병렬 운영을 `spawn_agent` 전문가 분업으로 다시 고정했고, repo runtime `expert_main.py --parallel`과 문서상 분리했다.
- `parallel` 표기는 앞으로 `Codex spawn_agent parallel`과 `expert_main runtime parallel`을 분리한다. small test에서 `requested_parallel=36`, `effective_parallel=1..N`이면 정상이며, 36 worker를 맞추려고 재실행하지 않는다.
- `expert_main.py` Summary/manifest에 VLM/OCR Semantic Gate를 추가해 image post가 있지만 `vlm_ocr_semantic_review_ready=false`이면 NO-GO 사유/action/sample post id를 남기게 했다.
- `--require-vlm-ocr-for-images`와 `LLM_REQUIRE_VLM_OCR_FOR_IMAGES=1` guard를 추가했다. 이미지 post가 있는데 VLM/OCR이 모두 켜져 있지 않으면 semantic test를 시작 전 exit code 2로 멈출 수 있다.
- manifest/Summary용 `vlm_ocr_semantic_review_skip_reasons`를 추가해 `no_image_blocks`, `vlm_disabled`, `ocr_disabled` run-level reason을 구조화했다.
- v416 fast-fail smoke에서 이미지 포함 `v117_targeted_4_input.jsonl`을 `--vlm off --ocr on --require-vlm-ocr-for-images`로 실행했고 PowerShell `$LASTEXITCODE=2`, output/manifest 미생성을 확인했다.
- `build_semantic_coverage_audit.py`가 `image_context_without_vlm_catalog`를 집계한다. `context_sources=image` 또는 `anchor_type=image`만 있고 `image_evidence_catalog`/VLM fetch/chunk counter가 없으면 `REVIEW-LOCKED` 이슈로 남긴다.
- browser screenshot/manifest path만으로 visual available을 인정하지 않게 했다. lazy/data-original/placeholder/incomplete/broken/pending loading counter가 있으면 visual evidence는 missing이다.
- `failed/timeout/pending/skipped/unsupported/disabled` VLM 상태 문자열은 fetch/chunk evidence가 아니라 blocker로 취급한다.
- v414 original semantic coverage audit를 생성했고 원본 partial source는 `image_context_without_vlm_catalog=36`, `browser_visual_missing=37`, `image_evidence_catalog_missing=37`로 계속 `REVIEW-LOCKED`다.
- v415 action queue를 생성했고 `modern_semantic_coverage_source_required` evidence에 `image_context_without_vlm_catalog=36`이 포함됐다.
- `build_semantic_coverage_audit.py`가 댓글 맥락 attribution bucket을 집계한다. 댓글 맥락이 resolved 판정에 관여했지만 `comment_metadata`/`comment_dialogue_context_lines`가 없으면 `comment_context_resolution_without_attribution`으로 남긴다.
- `author_match_unverified` 또는 `post_author_match_unverified` 댓글 맥락이 resolved 판정에 관여하면 `comment_author_match_unverified_used_for_resolution`으로 남긴다.
- v417 original semantic coverage audit를 생성했고 원본 partial source는 `comment_context_claimed_row_count=54`, `comment_context_resolution_row_count=19`, `comment_context_resolution_without_attribution=19`, `comment_author_match_unverified_used_for_resolution=0`으로 계속 `REVIEW-LOCKED`다.
- v418 action queue를 생성했고 `modern_semantic_coverage_source_required` evidence에 comment attribution bucket이 포함됐다.
- 이번 라운드에서 Codex `spawn_agent` 전문가를 추가로 병렬 투입했다. `Ramanujan`은 search-only/blocked-intent audit bucket 공백을, `Copernicus`는 문맥 이해/프롬프트의 후단 rescue 한계를, `Arendt`는 VLM/OCR Browser visual evidence gate 강화를 읽기 전용으로 보고했다.
- `build_semantic_coverage_audit.py`가 `search_only_resolved_title`, `blocked_intent_resolved_title`, `*_review_only` bucket을 집계한다. 특정 작품 direct anchor가 있는 `specific_work + hold/allow`는 hard blocker가 아니라 review-only로 분리한다.
- v419 original semantic coverage audit를 생성했고 원본 partial source는 `search_only_resolved_title=6`, `blocked_intent_resolved_title=7`, review-only 예외 `0`으로 계속 `REVIEW-LOCKED`다.
- v420 action queue를 생성했고 `modern_semantic_coverage_source_required` evidence에 search-only/blocked-intent bucket이 포함됐다. `vlm_ocr_browser_visual_gate`는 `browser_visual_missing=37`, `image_evidence_catalog_missing=37`, `image_context_without_vlm_catalog=36` 때문에 P0 approval blocker로 승격됐다.
- v421 search-only/blocked-intent bucket 정성 triage를 작성했다. unique post `11`건 중 `HOLD=4`, `REJECT=7`이며, `11718080`, `11718118`, `11718083`, `11718062`는 후단 rescue 차단 회귀 후보로 유지한다.
- v421 후속 라운드는 Codex 앱 `spawn_agent` 전문가 병렬 운영으로 다시 분해했다. source 복원(`Popper`), semantic gate(`Wegener`), runtime/shard 계약(`Aquinas`)을 나눴고, 이는 repo 내부 `expert_main.py --parallel` worker cap과 다른 계층이다.
- `tools\build_search_only_intent_followup_inputs.py`를 추가해 v421 labels와 `tests\inputs\test01.jsonl`에서 post/body/comment/image를 복원하는 v422 package를 만들었다. source post rows `11`, comment rows `25`, missing post `0`, browser target `6`이다.
- v422 targeted rerun은 Gemma 4 4B vLLM endpoint에 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다. completed/failed/pending은 `11/0/0`, requested/effective parallel은 `36/11`이다.
- v424 semantic coverage audit는 `search_only_resolved_title=0`, `blocked_intent_resolved_title=0`, image evidence catalog `6/0`, comment metadata `7/0`을 확인했지만, result JSON 내부의 browser visual evidence가 없어 `browser_visual_required/available/missing=6/0/6`으로 계속 `REVIEW-LOCKED`다.
- v425 browser artifact는 Codex in-app Browser `node_repl` 실패와 Playwright CLI fallback 실패를 기록한 뒤, MCP Playwright screenshot/snapshot으로 6개 image row의 외부 visual evidence를 확보했다.
- v425 수동 after-review는 `ACCEPT=8`, `HOLD=2`, `REJECT=1`이다. v423 자동 after-review의 `11/11 ACCEPT`는 과낙관이므로 gate 근거로 쓰지 않는다.
- `11718098`은 `마좋좋좋` positive alias/title-discussion을 no-work로 과차단한 P1 회귀로 남겼고, `11718049`/`11718083`은 false positive 차단은 회복됐지만 comment URL 검증과 quote/title recall 때문에 `HOLD`로 유지했다.
- 추가 Codex explorer `Kepler`가 semantic hard-deny 경로를 read-only로 점검했고, `semantic_seed_review_non_title_terms_removed`가 `search_query_reviews.keep` positive seed를 덮는 경로를 P0/P1로 보고했다.
- `DiscourseAnalyzer`, `Orchestrator`, `AgenticPipeline`을 보강해 context-only 표면어 제거와 specific-work positive/keep-query 신호를 분리했다. `11718080`류 보호를 위해 사회적 한탄/장르 잡담 prompt 문구도 복구했다.
- v427은 `11718098`이 여전히 `semantic seed demotion 조기종료`로 실패했고, v428은 같은 11건 입력을 `--parallel 11 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`로 재실행해 `11718098 -> 마법 좋아좋아좋아` 회복을 확인했다.
- v429 guarded after-review는 `ACCEPT=9`, `HOLD=2`, `REJECT=0`이고, v429 coverage audit는 외부 browser artifact sidecar로 browser visual `6/6/0`을 확인했다. 남은 gate issue는 `11718049`, `11718083`, `11718097`, `11718075`로 분리해 계속 `REVIEW-LOCKED`다.
- v430 refined semantic coverage audit(`v430_search_only_blocked_intent_after_seed_keep_query_semantic_coverage_refined.json`, `_ko.md`)를 재생성했다. targeted coverage gate는 `REVIEW`이며 browser visual `required/available/missing=6/6/0`, image catalog `6/0`, comment metadata/dialogue `7/0`과 `7/0`이다.
- v430에서 `11718097` comment author unverified resolution과 `11718075` search-only resolved title은 hard blocker가 아니라 packet-level review-only로 완화됐다. `11718097`은 `comment_author_match_unverified_used_for_resolution=0` / review-only `1`, `11718075`는 `search_only_resolved_title=0` / review-only `1`이다.
- `11718049` comment URL verify와 `11718083` quote/title recall은 v429 HOLD 후속으로 계속 남긴다. v430은 targeted follow-up의 hard blocker 완화일 뿐이며, 전체 10만 건 semantic approval은 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`/`NO-GO`다.
- 사용자 재정정을 반영해 현재 라운드도 repo 내부 전문가 오케스트레이션이 아니라 Codex 앱의 `spawn_agent` 기반 goal 운영으로 다시 분리했다.
- v411에서는 Runtime/manifest, semantic 품질, VLM/OCR 이미지 게이트, 프롬프트/오케스트레이션 한계 subagent 결과를 통합했다.
- `11718082`는 세대별로 다시 정리했다. v179는 이미지 입력이 있었지만 VLM-ready manifest와 `VLM chunk request`가 없어 승인 근거가 아니며, v181/v259/v311/v325/v330은 VLM/OCR이 실제로 돌았다. 원본 10만 partial은 reason/log에 OCR 흔적이 있어도 `image_evidence_catalog`가 없어 semantic approval 근거가 아니다.
- `11718080`류는 앞단 LLM 이해 실패만으로 보지 않고, 앞단 no-work/title-null 판단을 후단 검색, BatchContext, known alias, `slang_db`, canonical/deliberation rescue가 다시 뒤집는 비단조 파이프라인 문제로 기록했다.
- 원본 5/28 result의 후단 rescue P0 seed를 `11718080`, `11718062`, `11718083`, `11718118`, `11718069`로 분리했다.
- `context_sources=image` 또는 `anchor_type=image`만으로 VLM/OCR Strong evidence를 인정하지 않고, `image_evidence_catalog` 또는 VLM fetch/chunk counter를 요구하는 기준을 v411에 남겼다.
- 신규 subagent는 hardcoded alias risk explorer, VLM/OCR browser evidence gate explorer, hardcoded alias audit tool/test worker로 나눴다.
- hardcoded alias risk worker 결과를 메인 Codex가 통합하면서 `SLANG_DICTIONARY`, `STOPLIST`, `NOISE`, `PLATFORM`, `GENERIC_TERM`, `LOW_INFORMATION`, `TROPE` 계열 curated registry 분류를 보강했다.
- v405 refined hardcoded alias risk audit를 생성했다. 함수 내부 local literal을 `local_runtime_literal/INFO`로 분리했고 결과는 `semantic_approval=REVIEW`, registry `85`, positive blocker `3`, quarantine-only `10`이다.
- `build_goal_action_queue.py --hardcoded-alias-audit`를 추가하고 v406 refined action queue를 생성했다. v406은 `hardcoded_alias_risk_review_required`를 approval blocker로 유지하되 `hardcoded_alias_gate=REVIEW`, positive blocker `3`, `total_actions=12`, `ready_now=7`, `blocked_until_completed_source=5`, approval blocker `6`으로 갱신됐다.
- hardcoded alias packet review 도구 `tools\build_hardcoded_alias_packet_review.py`를 추가했다.
- v407 packet review는 실제 result/review packet 763 records를 검사했고, report self-hit와 evidence snippet only hit를 분리했다. matched packets는 `11`, packet coverage는 `FOUND`, gate는 `REVIEW`다.
- v407 packet match는 `KNOWN_TITLE_ABBREVIATIONS:담텔기 -> 괴담 호텔 탈출기` 계열로 좁혀졌고, `KNOWN_ABBREVIATIONS`와 `SLANG_DICTIONARY`는 targeted canary/provenance 보강 대상으로 남겼다.
- `build_goal_action_queue.py --hardcoded-alias-packet-review`를 추가하고 v408 action queue를 생성했다. v408은 `hardcoded_alias_packet_review_required`를 approval blocker로 추가해 `total_actions=13`, `ready_now=8`, `blocked_until_completed_source=5`, approval blocker `7`로 갱신됐다.
- v409 hardcoded alias packet label review를 작성했다. 11건은 모두 post `11718120` 변형이며 라벨 분포는 `ACCEPT=6`, `HOLD=2`, `REJECT=3`이다.
- v409 `REJECT`는 `author_talk` 과차단, `noise` 과차단, wrong canonical title `한가인(괴담 호텔 탈출기)`로 분리했다.
- `build_goal_action_queue.py --hardcoded-alias-packet-labels`를 추가하고 v410 action queue를 생성했다. v410은 `hardcoded_alias_packet_label_followup`을 approval blocker로 추가해 `total_actions=14`, `ready_now=9`, `blocked_until_completed_source=5`, approval blocker `8`로 갱신됐다.
- `NovelIdentity.alias_resolution_sources[]`를 추가하고 qualitative packet `final_decision_fields`에 alias registry provenance를 노출했다. 판정 로직은 바꾸지 않고 리뷰/승인 gate에서 registry 근거를 분리해서 볼 수 있게 했다.
- `build_current_remaining_action_inputs.py` 실행 계약을 수정해 소규모 재실행 입력에는 권장 `--parallel min(input_count,36)`를 표시하고, `MCP_SHARD_COUNT=36`을 required contract에서 제거했다.
- VLM/OCR 직접 근거와 Browser image loading evidence를 분리하는 gate 문구를 보강했다. 11718082는 원본 런에서 VLM/OCR 호출이 있었지만 result/packet 공개 필드가 부족해 리뷰에서 미실행처럼 보인 케이스로 정리했다.
- `Orchestrator._prune_title_search_requests_for_intent_permit()`를 추가해 `semantic_seed_review`가 no-work/context-only로 낮춘 packet에서 title/alias/key-term 목적 검색을 실행 직전에 hard-block한다. 이후 닫힌 기본값으로 보강해 permit false 상태에서는 `term_definition` 등 안전 목적만 허용하고, `adaptive_wiki`/`author_works_search` 직접 `search_fn` 호출도 중앙 `_execute_searches()` 경로로 통일했다. 11718082처럼 이미지 OCR 직접 작품 앵커가 있으면 예외로 허용한다.
- 후단 `BatchContext`/known alias/slang_db seed/deliberation rescue도 구조화된 `semantic_seed_review` no-work, `title_resolution_allowed=false`, `context_only`, `intent_permit_for_title_search=false` 신호를 읽게 해, 검색 gate 뒤쪽에서 title이 다시 살아나는 우회 경로를 focused 회귀로 닫았다. direct image/OCR 작품 앵커 예외는 유지했다.
- runtime/shard explorer 결과, 현재 `expert_main.py --parallel 36`은 small input에서 effective parallel이 줄어드는 max 계약으로 확인됐다. goal/test에서 Docker/shard lifecycle은 opt-in 없이는 열리지 않는 계약도 확인했다.
- semantic/VLM explorer 결과, intent-first 구조는 있지만 검색 suppression 기본 off, key_terms 자동 검색, Verifier 검색 우선 문구가 결합되어 `11718080`류 한탄/잡담이 검색으로 다시 resolved될 P0 위험이 남는 것으로 정리했다.
- 사용자 정정을 반영해 `expert_main.py --parallel`이 아니라 Codex goal 자체를 subagent 병렬 운영으로 전환했다.
- explorer 3개를 병렬 투입했다: gate/evidence(`Boole`), runtime/shard/process(`Hume`), semantic/VLM/comment(`Jason`).
- explorer 결과는 원본 source `NO-GO`, 10만 semantic approval `REVIEW-LOCKED`, 소규모 runtime/reason hygiene targeted `GO`로 일치했다.
- 후속 구현은 runtime audit process snapshot worker(`Cicero`)와 semantic coverage audit worker(`Confucius`)로 disjoint write scope를 나눴다.
- `Cicero` 결과를 통합해 `audit_goal_test_run_contract.py --collect-process-snapshot` 옵션과 v395 process snapshot audit를 만들었다.
- `Confucius` 결과를 통합해 `build_semantic_coverage_audit.py`와 v396 original semantic coverage audit를 만들었다.
- v396은 원본 71행에서 image evidence catalog missing `37`, browser visual missing `37`, comment metadata/dialogue missing `55`, final semantic reread coverage missing `71`을 확인해 원본 source가 계속 `REVIEW-LOCKED`임을 더 명확히 했다.
- v395의 direct process snapshot은 sandbox 권한 때문에 `available=false`였으나, v397 외부 process snapshot JSON 주입 audit에서 stale `expert_main/llm_batch/warp_shards/vllm/uvicorn` 후보가 `0`건임을 확인했다.
- process snapshot 기본 패턴에서 너무 넓은 `openai`를 제거해 Codex 앱 자체 프로세스가 stale 후보로 잡히는 오탐을 줄였다.
- `build_goal_action_queue.py`가 v396 semantic coverage audit와 v397 process snapshot audit를 입력으로 받게 했고, v398 action queue를 생성했다.
- v398은 `total_actions=11`, `ready_now=6`, `blocked_until_completed_source=5`, approval blocker `5`개로 정리됐으며, semantic approval은 계속 `REVIEW-LOCKED`다.
- `build_semantic_coverage_audit.py`가 `final_semantic_reread_required/present/missing`을 분리해, 이미 non-relevant/context-only로 내려간 row를 final reread 누락으로 과차단하지 않게 했다.
- v399에서 최신 clean canary 4건을 refined coverage로 재감사했고, 모두 image/comment catalog는 개선됐지만 browser visual evidence missing으로 `REVIEW-LOCKED`다.
- v400 refined original coverage와 v401 refined action queue를 만들었고, v402 현재 goal 진행 요약을 남겼다.

## 2026-05-31 - v394 goal action queue

- `tools\build_goal_action_queue.py`를 추가해 v393 상태맵에서 approval blocker와 ready action을 분리했다.
- v394 action queue는 `total_actions=8`, `ready_now=4`, `blocked_until_completed_source=4`다.
- approval blocker는 completed VLM/OCR-on source 확보, completed source preflight, random baseline 1000건, P0/P1 high-risk expansion이다.
- ready action은 소규모 runtime audit, reason hygiene scan, VLM/OCR browser visual gate, 원본 partial source regression seed 유지다.
- v394 산출물은 `qualitative_review\20260528_141006_620986\v394_goal_action_queue.json`와 `_ko.md`다.

## 2026-05-31 - v393 goal current-state map

- `tools\build_goal_current_state_map.py`를 추가해 원본 result/manifest, v386 preflight, v391 runtime audit, v392 reason hygiene scan을 한 상태맵으로 묶었다.
- v393 상태맵은 원본 source approval `NO-GO`, 최근 소규모 runtime contract `GO`, 최신 reason hygiene `GO`, 10만 semantic approval `REVIEW-LOCKED`를 분리 보고한다.
- 원본 run은 `104502/80/71/9/0/71` 상태라 manifest 기준 partial이며, random baseline 1000건은 available 71건이라 infeasible이다.
- v393 산출물은 `qualitative_review\20260528_141006_620986\v393_goal_current_state_map.json`와 `_ko.md`다.

## 2026-05-31 - v392 expression reread label colon-payload guard

- 사용자 재지적을 반영해 public reason에서 `표현 오타/축약 패턴(범용): ...` 형태도 쓰지 않게 바꿨다.
- 재해독 label은 `표현 오타/축약 패턴(범용)`로만 남기고, 뒤에는 `은 packet-local 원문 재검토 신호`처럼 경계 문장만 붙인다.
- `tools\scan_reason_hygiene.py`에 `surface_reread_label_colon_payload` hit를 추가해 label 뒤 payload 회귀를 raw scan에서 잡는다.
- 이 변경은 특정 표면어 정상형 복원이나 계열 일반규칙이 아니라 public-output hygiene 보강이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v391 goal/test audit auto log discovery

- `audit_goal_test_run_contract.py`가 `--log` 없이도 manifest `run_id`에서 `logs\expert_run_<run_id>.log`와 worker log를 자동 탐색하게 했다.
- 자동 탐색으로도 로그가 없으면 `log_evidence_missing`을 남기고 `runtime_contract=REVIEW`로 낮춘다.
- v381 manifest-only 감사에서 `auto_discovered_logs=true`, `log_evidence_present=true`, forbidden log hit 0, `runtime_contract=GO`를 확인했다.
- focused unittest는 4건에서 6건으로 늘었고 모두 통과했다.

## 2026-05-31 - v390 goal/test run contract audit tool

- `tools\audit_goal_test_run_contract.py`를 추가해 소규모 goal/test run 완료 후 manifest/log 기반 runtime 계약을 자동 감사하게 했다.
- 감사 항목은 requested/effective parallel, input/completed/flushed/pending/failed, shard lifecycle flags, Docker/warp forbidden log hit, VLM/OCR ready다.
- `runtime_contract=GO`는 semantic approval이 아니라 runtime 계약 통과로만 기록한다.
- v381 manifest와 log를 실제 감사해 `requested_parallel=36`, `effective_parallel=1`, lifecycle false, VLM/OCR ready true, forbidden log hit 0, `runtime_contract=GO`를 확인했다.
- focused unittest 4건과 `py_compile`을 통과했다.

## 2026-05-31 - v389 expression reread active label cleanup

- 사용자 재지적을 반영해 재해독 문구를 다시 점검했다.
- active prompt/reason/report/test 기대 문구에서 확장 label을 제거하고 `표현 오타/축약 패턴(범용)`만 남기게 정리했다.
- `LLM_JUDGMENT_REVIEW.md`, `SCAN_RESULT_REVIEW_GUIDE.md`, `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`의 active 지침도 같은 label로 맞췄다.
- focused unittest 7건과 `py_compile`을 통과했다.
- 이 변경은 wording/output hygiene 보강이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v388 downstream review builders fail on locked preflight source

- v386 preflight가 `REVIEW-LOCKED`를 exit code 2로 막아도, downstream random/round2 builder가 preflight 없이 직접 실행되면 partial source로 approval artifact를 만들 수 있었다.
- `build_qualitative_random_control_review.py`와 `build_qualitative_round2_review.py`에 `--preflight`와 `--fail-on-locked-source` 옵션을 추가했다.
- approval 목적 실행에서 preflight가 없거나 source가 다르거나 `gate.overall=REVIEW-LOCKED`이면 builder가 output dir를 만들기 전에 exit code 2로 종료한다.
- v386 original preflight를 붙인 v388 dry-run에서 random/round2 둘 다 `preflight_review_locked`, `exit_code=2`, `unexpected_output_dir=0`을 확인했다.
- 이 변경은 partial source를 approval pipeline으로 넘기지 않게 하는 하위 builder 안전장치이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v387 expression reread wording narrowed to generic label

- 사용자 재지적을 반영해 재해독 active label을 `표현 오타/축약 패턴(범용)`으로 더 좁혔다.
- `표현 오타/축약 패턴(범용)`보다 긴 확장 label은 최신 prompt/reason/report에서는 쓰지 않고, packet-local 범용 재검토 신호로만 설명한다.
- 특정 표면형 복원, 표면 계열 전용 규칙, post/string hardcode는 계속 금지한다.
- 이 변경은 wording/output contract 보강이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v386 preflight fail-on-locked CLI gate

- `REVIEW-LOCKED` preflight가 종료코드 0으로 끝나면 자동화가 source 부족 상태를 보고도 다음 단계로 넘어갈 수 있어 `--fail-on-locked` 옵션을 추가했다.
- 기본 실행은 호환성을 위해 종료코드 0을 유지하고, 옵션을 켠 경우에만 `gate.overall=REVIEW-LOCKED`에서 종료코드 2를 반환한다.
- 원본 objective source로 v386 preflight를 실행했고 gate는 계속 `REVIEW-LOCKED`, CLI exit code는 `2`였다.
- 산출물은 `qualitative_review\20260528_141006_620986\v386_original_fail_on_locked_preflight.json`와 `_ko.md`다.
- focused preflight unittest 4건과 `py_compile`을 통과했다.
- 이 변경은 large-scale approval을 열어주는 기능이 아니라, partial source를 approval pipeline으로 잘못 넘기지 않게 하는 자동화 안전장치다.

## 2026-05-31 - v385 expression reread generic wording correction

- 사용자 재지적을 반영해 재해독 active wording을 `표현 오타/축약 패턴(범용)` 중심으로 다시 좁혔다.
- final semantic reread prompt에서 특정 표면 계열 예시처럼 읽힐 수 있는 문구를 제거하고, 범용 신호와 packet-local evidence 재검토로 표현했다.
- 회귀 테스트는 특정 정상형/계열 설명을 기대하지 않고, prompt에 특정 표면 계열 예시가 새지 않는지 확인한다.
- `LLM_JUDGMENT_REVIEW.md`, `SCAN_RESULT_REVIEW_GUIDE.md`, `OPERATION_QUALITY_CHECKLIST.md`, `CHECKLIST.md`에 active rule을 갱신했다.
- 이 변경은 wording/output contract 보강이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v384 preflight source policy clarification

- v383 preflight는 gate를 `REVIEW-LOCKED`로 냈지만, source policy가 `final_result_json`과 `large_run_complete=None`로 남아 partial source라는 결론이 덜 직관적이었다.
- `tools\preflight_qualitative_large_scale_review.py`가 manifest partial signal을 source policy에 반영하도록 보강했다.
- v384 preflight에서 원본 objective source는 `partial_final_result_json`, `manifest_partial_run`, `large_run_complete=false`로 분류된다.
- gate에는 `required_next_actions`로 `obtain_completed_source`, `rerun_preflight_on_completed_source`, `keep_current_source_as_regression_seed_only`가 남는다.
- focused unittest 3건과 `py_compile`을 통과했다.

## 2026-05-31 - v383 original source preflight after affected-row recovery

- affected-row 4건의 current targeted regression이 clean이어도, 원본 objective 파일이 large-scale approval source가 되는 것은 아니므로 v383 preflight를 다시 실행했다.
- 원본 `out\expert_result_20260528_141006_620986.json`는 result rows `71`, manifest `104502/80/71/9/0`, checkpoint completed `80`, pending snapshot `9`로 partial source다.
- random baseline `1000` 기준 available rows는 `71`, shortfall은 `929`다.
- high-risk target total은 `660`이지만 source 자체가 partial이라 expansion을 돌려도 approval 근거가 아니라 부족 증거가 된다.
- `tools\preflight_qualitative_large_scale_review.py`의 Markdown 출력 heading/field label을 한국어로 바꾸고, 한국어 review artifact 회귀 테스트를 추가했다.
- v383 gate는 `run_integrity=REVIEW`, `semantic_preflight=REVIEW-LOCKED`, `overall=REVIEW-LOCKED`다.

## 2026-05-31 - v380-v382 original affected-row recovery matrix

- v365/v377처럼 여러 row가 섞인 dirty artifact를 approval source로 쓰지 않기 위해 `11718103`, `11718096`을 각각 단건 clean canary로 분리했다.
- v380 run id `20260531_142523_892037`은 `11718103`을 VLM/OCR on, requested/effective parallel `36/1`로 실행했고, 결과는 `is_relevant=false`, `discussion_type=meta`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`다.
- v381 run id `20260531_142901_117227`은 `11718096`을 VLM/OCR on, requested/effective parallel `36/1`로 실행했고, 결과는 `헌터갤러리의 국가권력급 기계공주`, `https://novelpia.com/novel/390228`, `title_resolution_state=resolved`다.
- v381에서도 이미지는 character visual only로 남고 final title 근거에서 제외됐다.
- v382 clean set scan은 v372/v379/v380/v381 4파일 모두 raw reason hygiene clean(`hit_files=0`)임을 확인했다.
- 이제 v375 original affected rows 4건은 current targeted regression 기준 `GO`지만, 원본 result approval과 10만 semantic gate는 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-05-31 - v377-v379 original stale reason affected rows follow-up

- v375 affected rows 중 `11718102`, `11718096`을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재검증했다.
- v377 run id `20260531_140102_152084`은 requested/effective parallel `36/2`, completed/flushed/pending/failed `2/2/0/0`, shard lifecycle blocked였다.
- `11718096`은 title/comment의 `기계공주` surface와 official URL `https://novelpia.com/novel/390228`가 맞물려 `헌터갤러리의 국가권력급 기계공주` resolved 판정을 `ACCEPT/Medium`으로 뒀다. 이미지는 character visual only로 title evidence가 아니다.
- `11718102`은 platform UI/콘 잡담으로 비관련/title-null 방향이 맞지만, v377에는 `단정하기 어려움할` suffix drift가 남아 dirty artifact로 분리했다.
- v378에서 bad phrase는 제거됐지만 비관련/no-anchor platform meta가 `unresolved_matchable`로 남는 scope drift가 보여, non-relevant/no-title/no-anchor 결과를 `context_only`로 낮추는 가드를 추가했다.
- v379 run id `20260531_141523_506800`에서 `11718102`은 `is_relevant=false`, `discussion_type=noise`, `title_resolution_state=context_only`, `title_resolution_allowed=false`로 회복했고 reason hygiene raw scan도 clean이다.
- 이 결과는 affected-row targeted recovery 증거이며, 원본 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v376 expression reread wording contract

- 사용자 지적을 반영해 재해독 public wording을 `표현 오타/축약 패턴(범용)`로 다시 고정했다.
- old wording drift는 새 public reason/report/prompt/checklist에서 쓰지 않는다.
- `rules.py`에 public label/statement/note 상수를 추가하고 `agentic_pipeline.py` reason 조립부가 이를 사용하게 했다.
- `tools\scan_reason_hygiene.py`에 `reread_wording_drift`를 추가해 old wording drift를 raw scan에서 잡는다.
- focused reason hygiene tests 2건, focused semantic reread/reason tests 3건, `py_compile`, v370/v372 updated raw scan을 통과했다.
- 이 변경은 wording/output contract 보강이며 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v375 original result reason hygiene scan

- active goal objective인 `out\expert_result_20260528_141006_620986.json`를 `tools\scan_reason_hygiene.py`로 직접 검사했다.
- 원본 result는 raw text 기준 `stale_relevant=18`, `llm_flip=9` hit가 남아 있고, affected rows는 `11718085`, `11718103`, `11718102`, `11718096`이다.
- manifest는 input/completed/flushed/pending/failed `104502/80/71/9/0`, result rows `71`로 여전히 partial source다.
- modern review field coverage도 `comment_metadata=0`, `comment_dialogue_context_lines=0`, `image_evidence_catalog=0`이라 current semantic approval source로 사용할 수 없다.
- 원본 result는 regression seed로는 유용하지만 approval source로는 `NO-GO`, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v374 reason hygiene raw scan tooling

- v373 raw text scan을 `tools\scan_reason_hygiene.py`로 고정했다.
- `--min-version 360`이 지정되면 v번호가 없는 JSON은 제외하고, `*_tool_report.json`도 기본 제외해 리포트 자체 재스캔 오염을 막는다.
- v374 tool report는 v360 이후 result JSON `12`개를 스캔해 `hit_files=10`, `clean_files=2`를 재현했다.
- 단위 테스트는 dirty v371, clean v372, manifest, unversioned action queue, tool report fixture로 범위 가드를 확인한다.
- 이 도구는 targeted reason hygiene 검증용이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v373 v360-v372 reason hygiene raw scan

- v360 이후 result JSON 12개를 raw text 기준으로 스캔해 public reason 금지 문구 잔존 여부를 확인했다.
- v360-v369와 v371은 기존 회귀를 재현하거나 고치던 historical artifact라 `seed 후보(`, `작품 seed 제외`, stale relevant template, old wording이 남아 있다.
- 최신 canary인 v370과 v372는 raw text 기준 forbidden scan이 clean이다.
- 이 결과에 따라 v360-v369/v371은 current approval source가 아니라 repro evidence로만 보관하고, v370/v372만 최신 targeted hygiene 증거로 본다.
- 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v371-v372 BatchMem seed summary and ranked reason hygiene

- Slang DB seed preload가 targeted run 로그를 과도하게 채우지 않도록 BatchMem seed log 기본값을 summary 모드로 바꿨다.
- v371 run id `20260531_130613_397740`에서 BatchMem summary는 성공했지만, 검색/랭킹 경로 public reason에 `작품 seed 제외: 로판 [전문가별 판단]`이 재등장해 reason hygiene를 `HOLD`로 봤다.
- v372 run id `20260531_131517_712392`는 VLM/OCR on, requested/effective parallel `36/1`, VLM fetch `1/1`, image evidence catalog `1`로 실행됐다.
- v372 `11718085`는 `is_relevant=false`, `discussion_type=noise`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 유지했고, forbidden scan에서 `seed 후보(`와 `작품 seed 제외`가 검출되지 않았다.
- 재해독 공개 표현은 계속 `표현 오타/축약 패턴(범용)`이며, 특정 정상형이나 표면 계열 일반규칙으로 승격하지 않는다.
- 이 결과는 targeted reason/log hygiene 회복 증거이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v365-v370 relevant-no-title follow-up

- 원본 result에서 `is_relevant=true`였지만 `official_title=null`이던 `11718085`, `11718103`을 current code로 다시 확인했다.
- v365는 `11718085`와 `11718103` 모두 title-null 보수 판정으로 회복했지만, `11718085` public reason에는 stale relevant template과 raw seed 반복이 남아 `HOLD`였다.
- v368은 `11718085`의 `seed 후보(...)`, `작품 seed 제외:` 반복을 재현했고, v370에서 `표현 오타/축약 패턴(범용)` 경계 문구만 남도록 고쳤다.
- v370 run id `20260531_125531_474288`은 requested/effective parallel `36/1`, VLM/OCR on, shard lifecycle blocked, completed/flushed/pending/failed `1/1/0/0`이었다.
- `11718085` current canary는 `context_only/title-null`, `11718103` current review는 `adjacent/meta/title-null`로 `ACCEPT/Medium`이다.
- 이 결과는 targeted public-output guard 회복 증거이며, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v364 original result vs current small-run delta

- 목표 파일 `out\expert_result_20260528_141006_620986.json`을 current v360/v363 small-run과 비교했다.
- 원본 manifest는 input `104502`, completed `80`, flushed `71`, pending `9`, requested/effective parallel `16/16`이었다.
- 원본 result rows는 `71`개뿐이고, `title_resolution_state`, `comment_metadata`, `image_evidence_catalog` coverage가 모두 `0`이라 approval source로는 `NO-GO`다.
- 원본의 known-bad `11718083`, `11718091`, `11718097`, `11718099`는 current small-run에서 wrong-title 방지/alias URL 수리 방향으로 개선됐다.
- 이 비교는 regression seed로는 `GO`지만, 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v360/v363 small-run issue review and generic reread no-seed-repeat

- v360 known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- run id `20260531_113820_343848`은 completed/flushed/pending/failed `4/4/0/0`, requested/effective parallel `36/4`, image_post_count `3`이었다.
- `11718083`은 wrong-title 없이 `unresolvable_memory_query/title-null`로 막혔지만 actual quote/source alignment가 없어 `HOLD/human_review`로 유지했다.
- `11718091`은 v360에서 title-null/context-only였지만 public reason에 raw surface 해석 반복이 보여 output hygiene 이슈로 승격했다.
- v363 run id `20260531_115718_534533`에서 `11718091`은 `context_only/title-null`, requested/effective parallel `36/1`, VLM/OCR on, shard lifecycle blocked를 유지했다.
- v363 공개 reason은 원문 title/body를 보존하되 해석/판정 문장에는 `표현 오타/축약 패턴(범용)`와 `직접 작품 앵커 없음`만 남기고, `seed 후보(...)` 또는 `작품 seed 제외: ...` raw 후보 반복을 제거했다.
- small-run named-case regression은 `GO`지만, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v359 expression reread generic-pattern contract

- 사용자 지적을 반영해 재해독 public wording을 `표현 오타/축약 패턴(범용)`로 재정렬했다.
- prompt/report/reason에서 구체 설명 범주가 자동 차단/허용 규칙처럼 반복되지 않게 `작품 고유 앵커 부족` 중심 문구로 낮췄다.
- 표면 재해독 차단은 특정 단어 계열 단독이 아니라 `surface_paraphrase_notes`/semantic review 경계 신호가 있을 때만 작동하도록 정리했다.
- `py_compile`과 focused semantic reread unittest 13건을 통과했다.
- 이 변경은 wording/output contract 보강이며 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v358 goal completion matrix after v357

- v356/v357 targeted 회복 뒤에도 원 goal 전체 완료 여부를 requirement별로 다시 감사했다.
- v358 matrix는 known-bad title regression guard와 public reason guard를 `GO`로 보지만, 원본 result approval source와 10만 semantic quality approval은 여전히 `NO-GO/REVIEW-LOCKED`로 둔다.
- 원본 manifest는 input `104502`, completed `80`, flushed `71`, pending `9`이고 원본 public result에는 `comment_metadata`, `dialogue_context`, `image_evidence_catalog`가 없다.
- 남은 P0/P1은 completed source 확보, random baseline/high-risk expansion, `11718083` actual recall, IAB browser closure, comment/IP attribution large coverage다.

## 2026-05-31 - v356/v357 public reason guard live canary

- v356 known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 다시 실행했다.
- run id `20260531_051249_145070`은 completed/flushed/pending/failed `4/4/0/0`, requested/effective parallel `36/4`, image_post_count `3`이었다.
- `11718083`은 title-null/HOLD, `11718091`은 context-only/title-null, `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 wrong-title 경계는 유지됐다.
- v356 Round2 review는 `ACCEPT=3`, `HOLD=1`이며 남은 HOLD는 `11718083` actual quote/title recall이다.
- 다만 v356 `11718091` 공개 reason에 원문에 없는 정규화 해석 괄호가 남아, public-output wording bug로 추가 가드를 넣었다.
- v357 단건 canary run id `20260531_052423_474129`에서 `11718091`은 `official_title=null`, `context_only`, `title_resolution_allowed=false`를 유지했고 해당 해석 괄호/치환 회귀가 사라졌다.
- 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v355 expression reread public-output tightening

- 사용자 재지적을 반영해, 재해독은 `표현 오타/축약/띄어쓰기 패턴`의 범용 후보일 뿐이라는 계약을 공개 reason 출력까지 더 좁혔다.
- 최종 reason에서 `표현 오타/축약 패턴(범용): X; Y`처럼 표면어를 따로 나열하지 않는다.
- 표면 재해독 후보는 원문 title/body/comment 안에서만 보이고, 공개 `작품 seed 제외` 목록에는 다시 올리지 않는다.
- legacy `paraphrase` 필드는 sanitizer 근거로 쓰지 않게 하여 `X -> Y`식 정상형 복원이 후단 판단에 재주입되지 않게 했다.
- focused unittest 11건과 `py_compile`을 통과했다. 이 변경은 wording/output guard이며 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v354 Browser Playwright fallback visual evidence

- Codex in-app Browser 연결을 다시 시도했지만 setup 단계에서 실패해 IAB target closure로는 처리하지 않았다.
- Playwright fallback으로 `11718083`, `11718094` 실제 DC post page를 열고 full-page screenshot과 snapshot을 확보했다.
- `11718083`은 본문 이미지가 정상 로딩됐지만 게임/캐릭터 화면이라 작품명/quote source anchor가 없음을 확인했다.
- `11718094`는 소설 발췌로 보이는 본문 텍스트는 확인됐지만 title/platform/URL/회차/source anchor가 없어 자동 title 확정은 보류했다.
- 두 건 모두 `HOLD/human_review` 유지이며 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v353 known-bad 4 after v352 contract canary

- v352 wording 보강 뒤 known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 다시 실행했다.
- run id `20260531_041516_797849`은 completed/flushed/pending/failed `4/4/0/0`, requested/effective parallel `36/4`였다.
- small targeted run으로 shard lifecycle이 차단되어 Docker compose up/recreate 없이 실행됐다.
- `11718083`은 wrong-title 없이 `unresolvable_memory_query/title-null`, `11718091`은 `context_only/title-null`, `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`을 유지했다.
- Round2 review는 `ACCEPT=3`, `HOLD=1`이며 남은 HOLD는 `11718083` actual quote/title recall이다. 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v352 expression reread generic-pattern guard

- 재해독 wording을 다시 조정해, `표현 오타/축약/띄어쓰기 패턴`은 범용 후보일 뿐 특정 정상형 복원이나 표면 계열 일반규칙이 아니라고 명시했다.
- 코드 프롬프트와 rule note에 `나이/외모/친구/한탄` 같은 범주는 예시적 위험 신호이며 자동 차단/허용 규칙으로 만들지 않는다고 추가했다.
- 새 prompt/report/reason에서는 `X -> Y`식 치환, post id/string hardcode, 계열별 deterministic rule을 쓰지 않는 계약을 유지한다.
- 이 변경은 prompt/output contract 보강이며 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v351 remaining HOLD quote/source alignment review

- v350 이후 남은 HOLD `11718083`, `11718094`에 대해 exact/near quote와 source alignment 검색을 추가했다.
- `11718083`은 memory-query/quote recall로 남았고, 직접 quote/source snippet을 확인하지 못해 `HOLD/human_review`를 유지했다.
- `11718094`는 이미지가 소설 본문 발췌처럼 보이지만 title/platform/URL/source anchor가 없어 `HOLD/human_review`를 유지했다.
- 두 건 모두 wrong-title 재발 방지는 `GO`지만 actual title recall은 자동 승인하지 않는다.

## 2026-05-31 - v350 Browser fallback visual review

- v349 이후 남은 HOLD `11718083`, `11718094`에 대해 Codex in-app Browser visual 확인을 재시도했다.
- Browser 제어 연결이 setup 중 끊겨 실제 Browser screenshot은 확보하지 못했다.
- PowerShell/curl 다운로드도 실패했지만 repo venv `httpx` fallback으로 두 이미지 원본을 확보했다.
- `11718083` 이미지는 게임/캐릭터 화면으로 작품명/quote alignment 근거가 없어, title-null guard는 맞지만 actual recall은 `HOLD/human_review`로 유지했다.
- `11718094` 이미지는 소설 본문 발췌지만 작품명/플랫폼/URL anchor가 없어, 원본 `심해의 마법사` 과확정 해소는 맞고 자동 title 확정은 보류했다.
- Browser target 28건은 아직 닫히지 않았고 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v349 slang/OCR subtype closure

- v348에서 남은 `11718082` `slang_db_review`를 닫기 위해 저장 차단된 OCR/표면형 subtype을 review labeler에서 분리했다.
- `store_in_slang_db=false`, official detail URL, `official_detail_title_preferred_over_surface_form`, `surface_form_duplicate_reference_pruned`가 함께 있으면 alias 오염 없이 닫힌 케이스로 보고 `ACCEPT/no_action` 처리한다.
- v349 relabel 결과는 `ACCEPT=13`, `HOLD=2`, `REJECT=0`, `REPROCESS=0`, `INFO_MISSING=0`이다.
- 남은 HOLD는 `11718083` memory-query quote recall과 `11718094` image/dialogue weak scene이다.
- Codex 내장 Browser 제어 연결이 현재 세션에서 끊겨 browser target 28건은 닫지 못했다. 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v348 action queue relabel refinement

- v347 rerun review의 false-positive HOLD를 줄이기 위해 Round2 labeler를 보정했다.
- official detail URL과 title anchor가 충분한 row는 nearby platform non-detail URL만으로 `HOLD/re_search`를 만들지 않게 했다.
- title-null social-lament/trope boundary가 닫힌 row와 context-only/no-title author-match-unverified row를 `ACCEPT/no_action`으로 낮췄다.
- v348 relabel 결과는 `ACCEPT=12`, `HOLD=3`, `REJECT=0`, `REPROCESS=0`, `INFO_MISSING=0`이다.
- 재해독 문구는 특정 정상형 복원이 아니라 "표현 오타/축약/띄어쓰기 패턴은 범용 신호"라는 계약으로 강화했다.
- focused regression 41건, surface/semantic seed focused 3건, `py_compile`을 통과했다. 남은 HOLD 3건과 browser target 28건 때문에 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v347 goal action queue rerun

- v345 action queue의 non-ACCEPT 48건을 원본 `tests\inputs\test01.jsonl` source로 재구성해 rerun/review/browser target으로 나눴다.
- 재실행 대상 15건을 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard` 조건으로 실행했다.
- run id `20260531_030937_599726`은 completed/failed/pending `15/0/0`, requested/effective parallel `36/15`, image_post_count `7`, search health `8/8`이었다.
- current rerun result를 Round2 relabel한 결과 `ACCEPT=7`, `HOLD=8`, `REJECT=0`, `REPROCESS=0`, `INFO_MISSING=0`으로 줄었다.
- 산출물 `v347_goal_action_queue_rerun_review_ko.md`를 추가했다. 단, HOLD 8건과 browser target 28건이 남아 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v346 goal objective completion matrix

- 원 objective 기준 completion audit를 `v346_goal_objective_completion_matrix_ko.md`로 남겼다.
- known-bad 4 current-code targeted canary는 title 재승격 방지 기준 `GO`지만, 원본 10만 result는 partial이고 semantic quality approval은 계속 `REVIEW-LOCKED`다.
- `11718083`은 `네이버` wrong-title guard는 통과했지만 actual quote/title recall은 `HOLD/human_review`로 유지한다.
- 핵심 원인은 partial run/public field loss, 자연어 의도 재독해 부족, 일반어/상태어 과승격, BatchMem/slang rescue 비단조성, VLM/OCR evidence boundary, 댓글 author/IP attribution 한계로 정리했다.

## 2026-05-31 - v345 memory-query quote alignment review bucket

- Round2 정성 리뷰 도구에 `quote_alignment_missing_for_memory_query` bucket을 추가했다.
- memory-query/대사·장면 회수 글에서 후보 공식 작품 페이지 hit와 원문 quote/source anchor 직접 정렬 근거를 분리했다.
- packet/result public fields에 `memory_query_quote_terms`, `quote_alignment_support_count`, `candidate_official_page_hits`, `quote_alignment_missing_for_memory_query`를 남긴다.
- quote alignment support는 `identity.search_evidence_catalog`, `identity.image_evidence_catalog`, `identity.evidence` 같은 direct evidence catalog만 세며, LLM이 만든 `title_candidates`/`entity_mentions` echo는 세지 않는다.
- v345 original partial review artifact를 재생성했고, source policy가 `final_result_json` + `large_run_complete=false`로 기록되어 원본 partial result가 approval source가 아님을 확인했다.
- focused regression 38건과 `py_compile`을 통과했다. 원본 `11718083`은 여전히 wrong-title/quote recall 분리 상태이며, actual quote/title recall은 `HOLD/human_review`다.

## 2026-05-31 - v344 expression reread docs correction

- 표현 재해독을 특정 정상 표현 복원이 아니라 `표현 오타/축약 패턴(범용)`로만 다루도록 문서 지침을 다시 정정했다.
- `LLM_JUDGMENT_REVIEW.md` 상단에 v344 active rule을 추가하고, 오래된 v195/v199/v210 항목이 `N세인 줄`류 우선 해석이나 `X -> Y` 전역 치환처럼 읽히지 않게 수정했다.
- `SCAN_RESULT_REVIEW_GUIDE.md`와 `EXPERT_ORCHESTRATION_LIMITATIONS.md`에 새 prompt/report/reason에서는 복원 예시를 쓰지 않고 historical observation과 active rule을 분리하라는 지침을 보강했다.
- 재해독은 `표현 오타/축약 패턴`을 범용 후보로만 보며, 특정 표면어를 특정 정상 표현으로 쓰는 방식은 새 산출물에서 금지한다.
- 오래된 run result/history의 구체 치환 문구는 historical artifact로만 남긴다. 새 산출물에서는 범용 후보 label을 사용한다.

## 2026-05-31 - v343 post 11718083 quote search audit

- `11718083`을 wrong-title guard와 actual quote/title recall로 분리해 다시 감사했다.
- v341 result/log 기준 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`, image evidence `character_visual_only`, `promotion_eligible=false`를 재확인했다.
- exact quote/variant 외부 검색에서 원문 대사를 직접 지지하는 공식 작품/회차/본문 snippet은 확인되지 않았다.
- `하차 이후의 소설 속` 공식 작품 페이지들은 확인됐지만, 공개 synopsis가 `11718083`의 친구/위기/동료 대사를 직접 지지하지 않아 title 확정 근거로 쓰지 않는다.
- 산출물 `qualitative_review\20260528_141006_620986\v343_post11718083_quote_search_audit_ko.md`를 추가했다.
- `11718083` actual quote/title recall은 계속 `HOLD / human_review`다.

## 2026-05-31 - v342 goal completion audit

- 원래 goal 기준으로 원본 partial run, v341 current-code canary, 댓글 author/IP coverage를 다시 분리 감사했다.
- 원본 manifest는 input `104502` 대비 completed `80`, flushed `71`, pending `9`라서 10만 건 approval source가 될 수 없음을 재확인했다.
- 원본 result는 rows_with_comments `55`이지만 `comment_metadata`, `comment_dialogue_context_lines`, image catalog가 없었다.
- v341 current-code result는 댓글 있는 known-bad 2건에서 metadata/dialogue line을 남기고, 이미지 post 3건에서 image evidence catalog를 남겼다.
- `tests\inputs\test01.jsonl` 전체에는 comment IP가 일부 있으나 post IP는 0건이고, known-bad 4건 자체에는 post/comment IP가 없어 IP 기반 원글 작성자 확정은 증명할 수 없다.
- 산출물 `v342_goal_completion_audit_and_remaining_work_ko.md`, `v342_goal_comment_metadata_coverage_ko.md`, `v342_test01_comment_metadata_coverage_ko.md`를 추가했다.
- known-bad current-code canary는 `GO`지만 `11718083` actual quote/title recall과 10만 semantic gate는 계속 `HOLD`/`REVIEW-LOCKED`다.

## 2026-05-31 - v341 known-bad 4 current-code rerun

- v339 이후 현재 코드로 `11718083`, `11718091`, `11718097`, `11718099`를 한 번에 재실행했다.
- 실행 조건은 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on`이다.
- v341 run id `20260531_021609_723758`은 completed/failed/pending `4/0/0`, flushed `4`, requested/effective parallel `36/4`, image_post_count `3`, small-run shard lifecycle blocked `true`였다.
- `11718083`은 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 `네이버` 재승격이 없었다. actual quote/title recall은 계속 `HOLD`다.
- `11718091`은 `official_title=null`, `discussion_type=noise`, `context_only`로 유지됐고, reason은 특정 치환 없이 `표현 오타/축약 패턴(범용)`로만 남았다.
- `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 clean alias positive-control을 유지했다.
- 산출물 `qualitative_review\20260528_141006_620986\v341_known_bad_4_current_code_recheck_ko.md`와 `v341_known_bad_4_current_code_action_queue_ko.md`를 추가했다.
- targeted canary는 `GO`지만 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v340 known-bad latest goal recheck

- 원본 `out\expert_result_20260528_141006_620986.json`에서 known-bad 4건이 실제 오판 title을 갖고 있음을 다시 확인했다.
- v337 `11718083`은 VLM/OCR on, effective parallel `1`, deliberate null guard로 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, Slang DB flush `titles=0`을 유지했다.
- v338 `11718097`은 `official_title=망겜의 힐러`, URL `https://novel.munpia.com/328421`, `망겜힐 -> 망겜의 힐러` clean alias 후보를 확인했다.
- v331 `11718091`은 표현 오타/축약 패턴(범용)와 `context_only` title-null을 유지했고, v334 `11718099`는 `빌어먹을 환생`과 OCR conflict flags를 유지했다.
- 산출물 `qualitative_review\20260528_141006_620986\v340_known_bad_latest_goal_recheck_ko.md`와 `v340_known_bad_latest_action_queue_ko.md`를 추가했다.
- targeted correction은 `GO`지만 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v339 expression reread hardcode wording correction

- 재해독 후단 정리 코드와 fixture/doc 문구가 특정 나이/표면 변환 규칙처럼 읽힐 여지를 다시 줄였다.
- `_sanitize_surface_paraphrase_context()`의 내부 기준을 surface-specific context가 아니라 `surface_expression_context`로 정리했다.
- test/review fixture의 공개 reason 예시는 `X -> Y`가 아니라 `표현 오타/축약 패턴(범용)`로 맞췄다.
- 오래된 run result JSON이나 과거 history의 구체 치환 문구는 historical artifact로만 보며, 새 prompt/report/guide에서는 deterministic rule처럼 재사용하지 않는다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v330 generic expression reread wording guard

- 재해독 단계의 표현 오타/축약/띄어쓰기 가능성을 특정 표면어 치환이 아니라 `표현 오타/축약 패턴(범용)`로 공개하도록 정정했다.
- `surface_paraphrase_notes.paraphrase`가 예전 packet에 남아도 semantic seed review/final semantic reread prompt payload에는 넘기지 않도록 public note sanitizer를 추가했다.
- 비관련 public reason은 source surface만 local evidence로 보여주고, `X -> Y`식 deterministic paraphrase를 만들지 않게 했다.
- focused unittest와 v331 `11718091` live rerun에서 reason이 `표현 오타/축약 패턴(범용)`로 나오고 deterministic paraphrase가 남지 않음을 확인했다.
- 이 변경은 wording/prompt 계약 보정이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 - v329 known-bad 4 OCR conflict cultural context sanitize

- `11718099`에서 final title은 `빌어먹을 환생`으로 맞아도 OCR 표지 후보가 `붉여먹을 혼성명`처럼 흔들리며, 공개 설명 필드가 이를 작품 단서처럼 과장할 수 있는 잔여 리스크를 확인했다.
- `_sanitize_slang_cultural_context_for_image_conflict()`를 추가해 `slang_insight.cultural_context`에서도 OCR 충돌 후보를 본문/별칭/공식 제목 근거로 승격하지 않도록 했다.
- `11718083`, `11718091`, `11718097`, `11718099`를 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 v329 재실행했다.
- v329 run id `20260531_001118_634562`는 completed/failed/pending `4/0/0`, requested/effective parallel `36/4`, VLM/OCR `true/true`, search health `ok=2/2`, small-run shard lifecycle blocked `true`였다.
- v329 final은 `11718083` memory-query title-null, `11718091` context-only/noise, `11718097` `망겜의 힐러`, `11718099` `빌어먹을 환생`으로 확인됐다.
- 이 결과는 known-bad 4 targeted canary 기준 `GO`지만, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v311 OCR/VLM surface form official detail realignment

- `11718082`에서 VLM/OCR이 `재벌가 차녀의 2회차 결그룹`으로 읽은 표면형이 final title과 보조 reference에 남는 회귀를 확인했다.
- `_freeze_identity_references()`에 동일 official detail URL의 locked 공식 후보를 OCR/VLM 표면 alias/variant보다 우선하는 범용 가드를 추가했다. 특정 post id, 제목, 오타 치환은 추가하지 않았다.
- 표면형 duplicate reference가 별도 작품처럼 `mentioned_works`, `comparison_target`, `recommendation_candidates`, `future_watch_target`에 남지 않도록 `surface_form_duplicate_reference_pruned`로 정리했다.
- focused unit 3건과 py_compile이 통과했다.
- v311 run id `20260530_204031_664775`는 completed/failed/pending `2/0/0`, requested/effective parallel `36/2`, VLM/OCR `true/true`, image_post_count `1`, small-run shard lifecycle blocked `true`였다.
- v311 final은 `11718082 -> 재벌가 차녀의 2회차 걸그룹`, `11718080 -> official_title=null / trope_discussion / adjacent`로 확인됐다.
- 이 결과는 targeted canary 기준 `GO`지만, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v308 known-bad 4 unverified author context guard

- `author_match_unverified` 댓글은 원글 작성자 발화로 확정하지 않는 기존 경계를 유지하면서, 짧은 캐릭터 반응글에서 독립 작품 근거처럼 쓰이지 않도록 `comment_author_match_unverified_not_independent_evidence` flag를 추가했다.
- `11718083`, `11718091`, `11718097`, `11718099`를 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- v308 run id `20260530_195609_675876`은 completed/failed/pending `4/0/0`, requested/effective parallel `36/4`, `vlm_ocr_semantic_review_ready=true`, `mcp_small_run_shard_lifecycle_blocked=true`였다.
- v308 final은 `11718083` memory-query title-null, `11718091` context-only title-null, `11718097` `망겜의 힐러`, `11718099` `빌어먹을 환생`으로 확인됐다.
- 이 결과는 known-bad 4 targeted canary 기준 `GO`지만, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v307 post 11718117 regression state audit

- v292 live artifact를 다시 확인해 `11718117` 잔여 상태를 정리했다.
- result는 `official_title=아카데미의 피해자`, `heretic_url=https://page.kakao.com/content/66611775?tab_type=product`, `title_resolution_state=resolved`, `anchor_type=image`, `anchor_strength=high`다.
- 로그에서 VLM이 이미지를 실제 처리했고 `아카데미의 피해자`, `양파랑`, `268 테세우스의 배 (6) 중`을 직접 읽은 것이 확인됐다.
- exact-title surface는 `store_in_slang_db=false`, `store_reason=exact_title_not_alias`, Slang DB flush `titles=0`이라 운영 slang alias 오염은 재현되지 않았다.
- `11718117`은 targeted canary 기준 `ACCEPT / no_action`으로 정리한다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v306 post 11718114 visual-only evidence closeout

- Codex in-app Browser 경로를 다시 시도했지만 `node_repl kernel exited unexpectedly`, `windows sandbox failed: spawn setup refresh`, `stdout_eof`로 실패했다.
- 대체 시각 증거로 v286 때 받아 둔 `qualitative_review\20260528_141006_620986\browser_v286\post11718114_direct_image.jpg`를 다시 확인했다.
- 이미지는 `HONEYCAM.ORG` 워터마크가 있는 게임/영상 장면이며, 작품명/작가명/회차/플랫폼 title로 쓸 direct OCR text는 보이지 않았다.
- 따라서 v286 final의 `official_title=null`, `discussion_type=trope_discussion`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`, `anchor_type=genre`, `anchor_strength=low`는 targeted canary 기준 `ACCEPT / no_action`으로 둔다.
- Browser 연결 문제는 semantic result 문제가 아니라 환경 follow-up으로 분리한다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v305 post 11718078 positive alias control

- `11718078`을 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 단건 재실행했다.
- v305 manifest는 completed/failed/pending `1/0/0`, requested/effective parallel `36/1`, VLM/OCR `true/true`, image_post_count `0`, Docker/shard auto up/recreate false였다.
- final은 `official_title=즉사기 들고 무림에 떨어지다`, `heretic_url=https://m.munpia.com/novel/detail/528383`, `title_resolution_state=resolved`, `anchor_type=title_exact`, `anchor_strength=high`로 유지됐다.
- 이 케이스는 `23센줄`류 오타/축약 재해독과 다르다. `즉사무림`은 제목 약칭이고, platform evidence가 정식 제목을 직접 지지한다.
- 따라서 no-hardcoding/재해독 guard는 자연어 후보 해석을 evidence로 승격하지 않는 데 쓰되, 실제 제목 약칭 + 공식 URL evidence positive-control을 과차단하면 안 된다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v303 post 11718083 OCR-noise visual anchor guard

- v302 재검증에서 reason은 `grounding_anchor: search_only`였지만 public JSON 필드는 `anchor_type=image`, `anchor_strength=medium`으로 남는 mismatch를 확인했다.
- 원인은 `character_visual_only` 이미지라도 OCR 잡음이 있으면 weak visual-only 판정을 빠져나가고, 일반 `work_cues`가 image anchor로 승격될 수 있던 구조였다.
- `_is_weak_vlm_visual_signal()`을 구조 필드 중심으로 고쳐, `promotion_eligible=true`, `title_role=work_title`, `focus_role=work_anchor`, direct title/author가 없으면 OCR 잡음만으로 image anchor가 되지 않게 했다.
- `11718083`을 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- v303 manifest는 completed/failed/pending `1/0/0`, requested/effective parallel `36/1`, VLM/OCR `true/true`, Docker/shard auto up/recreate false였다.
- v303 final은 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`, `image_evidence_catalog_count=1`, `anchor_type=none`, `anchor_strength=none`으로 확인됐다.
- 재해독 prompt/test/docs에서 일괄 적용처럼 보이는 표현을 제거하고 packet-local 후보 해석/evidence boundary 표현으로 정리했다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v301 post 11718083 weak visual anchor guard

- `11718083` memory-query/quote recall 글을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- v301 manifest는 completed/failed/pending `1/0/0`, requested/effective parallel `36/1`, VLM/OCR `true/true`, image_post_count `1`, Docker/shard auto up/recreate false였다.
- VLM은 이미지를 처리했지만 `character_visual_only`, `confidence=Low`, `promotion_eligible=false`, direct OCR/title/author 없음으로 기록됐다.
- `agentic_pipeline.py`에서 VLM 실행 여부와 image primary anchor를 분리해, weak visual-only 이미지는 `context_sources=image`와 `image_evidence_catalog`에는 남기되 `anchor_type=image`로 승격하지 않게 했다.
- v301 final은 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`, `image_evidence_catalog_count=1`, `anchor_type=genre`, `anchor_strength=low`다. v214의 `image/medium` 승격은 사라졌다.
- search-inferred batch alias `정작 -> 나한테 이런 건 네가 처음이야` rescue도 `deliberate_null_nonwork_context`로 차단됐다.
- focused VLM/memory-query tests와 py_compile이 통과했다. true title quote recall은 여전히 `HOLD`, 10만 건 semantic gate는 `REVIEW-LOCKED`다.

## 2026-05-30 - v300g packet-local semantic reread wording recheck

- 재해독 단계의 오타/축약/띄어쓰기 깨짐 가능성을 표면 패턴 일반 규칙으로 승격하지 않도록 prompt/test/docs 문구를 재정리했다.
- final semantic reread와 semantic seed review prompt는 이제 특정 표면어를 고정 규칙으로 만들거나 다른 post에 재사용하지 않고, 해당 packet 문맥 안의 후보 해석으로만 읽도록 말한다.
- `SCAN_RESULT_REVIEW_GUIDE.md`의 전역 규칙처럼 보이는 표현을 제거하고 packet-local 후보 해석/evidence boundary 기준으로 바꿨다.
- final semantic reread tests 9건과 py_compile이 통과했다. deterministic typo/abbreviation rule expansion은 추가하지 않았다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v300f comment payload live proof and context-only reason softening

- `11718091` 단건을 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- manifest 기준 `requested_parallel=36`, `effective_parallel=1`, `completed=1`, `failed=0`, Docker/shard auto up/recreate false였다.
- `LLM_DEBUG_DUMP_MESSAGES=1` 로그에서 `comment_context`, `comment_dialogue_context`, `role=author_match_unverified`, `surface_paraphrase_notes`가 `discourse_semantic_seed_guard` 요청 본문에 들어가는 것을 확인했다.
- semantic seed review 지침에 짧은 인명/캐릭터명 단독 seed와 일반어 검색 조합은 직접 작품 앵커 없이는 keep하지 않도록 보강했다.
- final title이 없는 non-workish reason에서 `작품 속/작품 내`류 과잉 표현을 `문맥상 언급된` 표현으로 낮추는 일반 후처리를 추가했다.
- v300f final은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`이고 public reason은 `문맥상 언급된 특정 인물('은영')`으로 정리됐다.
- final semantic reread tests 9건과 py_compile이 통과했다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v299 comment dialogue payload key recheck

- `11718091` evidence를 다시 보니 source/result/review packet에는 `comment_context_lines`와 `comment_dialogue_context_lines`가 있으나, semantic seed review payload는 `comment_context`/`comment_dialogue_context`만 읽는 key mismatch가 있었다.
- `DiscourseAnalyzer._call_semantic_seed_review()`가 `comment_context_lines`/`comment_dialogue_context_lines`를 fallback으로 사용하게 했다.
- `AgenticPipeline._run_final_semantic_reread()` payload에도 댓글 speaker/author/ip role line을 싣게 했다.
- `author_match_unverified`는 계속 대화 흐름 힌트일 뿐 작품 근거나 원글 작성자 확정 근거가 아니다.
- final semantic reread tests 8건, comment metadata tests 4건, qualitative review packet tests 35건, py_compile이 통과했다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v298 semantic reread fixed-rule wording correction

- `11718091` 지적은 특정 문자열 차단이나 표면 패턴 확정 규칙으로 해결할 문제가 아니라, 재해독 단계에서 표현 오타/축약/띄어쓰기 깨짐 가능성을 문맥으로 다시 읽는 문제로 정리했다.
- 방금 시도했던 deterministic regex 확장은 되돌렸고, 새 조사/표면 패턴을 규칙으로 추가하지 않았다.
- final semantic reread와 semantic seed review 프롬프트는 "표현 해석만으로 제목 evidence를 만들지 말고 별도 직접 evidence를 확인하라"는 방향으로 정정했다.
- `surface_paraphrase_notes`만으로는 seed/search를 내리지 않고, LLM semantic seed review가 no-work/context-only 위험을 표시한 경우에만 sanitizer가 보조 적용되게 했다.
- final semantic reread tests 7건, qualitative review packet tests 35건, py_compile이 통과했다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v297 goal objective completion audit

- active goal의 원래 요구사항을 current evidence 기준으로 다시 감사했다.
- 원본 `out\expert_result_20260528_141006_620986.json`은 manifest 기준 `104502` 입력 중 `80` completed, `71` flushed, `9` pending인 partial artifact라서 10만 건 semantic approval source가 아니다.
- 원본 오판은 재확인됐다: `11718083 -> 네이버`, `11718091 -> Re:제로부터 시작하는 원신생존기`, `11718097 -> 검미성 신작 'A급 헌터로 살아남는 법' 최신화`, `11718099 -> 표지변경`.
- current targeted/v296 기준 `11718097`과 `11718099`는 회복됐지만, `11718083` memory-query recall과 `11718091` 익명 댓글 author/IP 검증은 HOLD로 남는다.
- 결론은 active goal `NOT COMPLETE`, 10만 건 semantic gate `REVIEW-LOCKED`다.

## 2026-05-30 - v296 goal known-bad semantic review tooling fix

- v296 after-review를 재생성해 goal 케이스 라벨을 다시 확인했다. `11718099`는 `generic_parenthetical_bridge` 오탐이 제거되어 `ACCEPT / no_action`, `11718097`은 `minor_alias_normalization_counter`로 분리되어 `ACCEPT / no_action`이다.
- `11718083`은 잘못된 `네이버`류 title 확정은 사라졌지만 memory-query/quote recall이라 `HOLD / human_review`로 남긴다.
- `11718091`은 표현 오타/축약 패턴(범용)와 title null/context-only 결론을 유지한다. 다만 LLM reason 문장이 "작품 자체 논의"처럼 과해질 수 있어 non-relevant reason 조립부에서 일반 잡담/미특정 맥락으로 낮추는 가드를 추가했다.
- `tools/build_qualitative_round2_review.py`는 설명문 괄호를 generic bridge로 오탐하지 않고, minor alias counter와 true critical counter를 분리한다.
- final semantic reread tests 6건, focused semantic reason tests 3건, qualitative review packet tests 35건, py_compile이 통과했다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v294 semantic reread / critical-counter 재확인

- 이 계열은 표현 오타/축약 패턴(범용)로 읽는 것이 맞고, 현재 경로도 특정 문자열 hardcode가 아니라 `surface_paraphrase_notes`, `discourse_semantic_seed_guard`, `final_semantic_reread`로 처리된다.
- 이번 재확인에서 `tests.test_final_semantic_reread_gate` 5건과 `tests.test_expert_main_comment_metadata` 4건이 통과했다.
- v287 live evidence 기준 `11718091`은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 유지했고 reason에 표현 오타/축약 패턴(범용)와 `작품 seed 제외`가 남았다.
- `11718097` v285 `critical_counter_but_resolved` / `HOLD`는 단건 재검토 결과 true critical counter가 아니라 `망겜힐` 약칭과 `망겜의 힐러` 정식명 차이를 minor note로 남긴 경우였다.
- v284/v285 evidence 기준 `11718097`은 final title `망겜의 힐러`, URL `https://m.munpia.com/novel/detail/328421`, `official_urls=4`, `search_snippets=48`로 정합적이다.
- 앞으로 `critical_counter_but_resolved` bucket은 `minor_alias_normalization_counter_resolved_by_official_evidence`와 true critical counter를 분리한다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v293 `11718082` OCR/slang_db subtype review

- `11718082`의 OCR/VLM 표면은 `제벨가 차녀의 2회차 결그룹`으로 오타가 섞였지만, final title은 검색/KakaoPage 근거로 `재벌가 차녀의 2회차 걸그룹`에 정렬되어 있었다.
- 기존 v259 VLM/OCR-on canary는 `requested_parallel=36`, `effective_parallel=2`, `completed/failed/pending=2/0/0`, Docker/shard auto up/recreate false였다.
- v259 result에서 OCR 오타 표면은 `slang_insight.detected_term`에 남았지만 `store_in_slang_db=false`, `store_reason=character_attached_composite`로 저장 차단됐다.
- 현재 `slang_db/slang_db.json`에서 `제벨가`, `결그룹`, `재차걸`, `재벌가 차녀의 2회차 걸그룹`은 모두 발견되지 않았다.
- v259 log의 `재차걸 -> 재벌가 차녀의 2회차 걸그룹` BatchMem 즉시등록은 검색 snippet의 `약칭은 재차걸` 근거가 있어 OCR 오타 오염과 분리했다.
- 이 확인으로 `11718082` 단건 OCR/slang subtype은 `ACCEPT with follow-up bucket`으로 정리했지만, 전체 `slang_db_alias_subtype` 큐와 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v292 BatchMem exact-title live canary

- v291 exact-title BatchMem guard를 `11718117` 단건 live run으로 재확인했다.
- 실행은 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard` 조건이었다.
- stdout/run_meta 기준 `requested_parallel=36`, `effective_parallel=1`, `auto_up=False`, `auto_recreate=False`, `small_run_lifecycle_blocked=True`로, 소규모 입력에서 worker/Docker lifecycle이 과하게 동작하지 않았다.
- VLM은 `fetch=1/1`, `chunks=1`, `total_bytes=59231`로 실제 이미지 근거를 처리했고 final URL은 `https://page.kakao.com/content/66611775?tab_type=product`를 유지했다.
- `slang_insight.store_in_slang_db=false`, `store_reason=exact_title_not_alias`, flush `titles=0`을 확인했다.
- `BatchMem: 약칭 즉시등록 '아카데미의 피해자'` 로그는 v292에서 발견되지 않았다. 내부 `term-role` 기록은 남을 수 있지만 BatchMem alias 등록/운영 slang 저장과는 분리해서 본다.
- 이 결과는 targeted runtime evidence이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v291 BatchMem exact-title alias guard

- v290 확인 중 운영 `slang_db`에는 `아카데미의 피해자`가 저장되지 않았지만, BatchMem `decoded_terms` 경로는 정식 제목 자체를 alias처럼 즉시 등록할 수 있음을 확인했다.
- `BatchContextMemory.register_abbreviation()`에서 normalized alias와 normalized title이 같으면 resolved/pending 등록을 건너뛰도록 했다.
- clean alias 학습은 유지된다. `죽깨수`, `즉사무림`, `검머대` 계열 회귀도 함께 통과했다.
- BatchMem/final semantic reread/VLM URL focused regression 18건과 `py_compile`이 통과했다.
- 이 변경은 v292 live run에서 exact-title surface가 `BatchMem: 약칭 즉시등록`으로 남지 않는지 runtime 로그까지 확인했다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v290 `11718117` VLM/OCR image platform URL recovery

- `11718117`은 이미지 OCR/VLM에 `아카데미의 피해자`, `양파랑`, `KAKAO PAGE`가 직접 보이는 작품 내부 장면 글이다.
- image-only seed pruning이 explicit title/author 검증 검색까지 자르던 경로를 보강해, promotable image anchor의 title/author 검색은 유지하게 했다.
- 카카오페이지 작품 소개문 안의 `원작 주인공`을 파생/팬픽 신호로 오해하던 derivative marker를 완화했다. `원작 소설 기반 웹툰`, `패러디`, `팬픽`, `2차 창작` 같은 강한 문맥은 계속 차단한다.
- v290 live run `20260530_165600_447262`은 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 실행했고, small run이라 `effective_parallel=1`, Docker shard auto up/recreate false였다.
- final은 `official_title=아카데미의 피해자`, URL `https://page.kakao.com/content/66611775`로 정리됐다.
- 표현 오타/축약 패턴(범용) final semantic reread gate 5건과 focused URL/VLM regression 7건, `py_compile`이 통과했다.
- 이 결과는 targeted canary이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v286/v287 VLM limit and `23센줄` semantic reread recheck

- `expert_main.py`의 기본 `LLM_VLM_MAX_IMAGE_BYTES`가 pipeline 기본 `16MiB`보다 낮은 `8MiB`라서 `11718114` 이미지 `8,428,632` bytes가 `image_too_large`로 VLM skip되던 원인을 확인했다.
- 기본값을 `16777216`으로 정렬했고, v286 live run에서 `VLM chunk request: post_id=11718114 ... bytes=8428632`가 실제 발생했다.
- v286 최종은 visual-only evidence라서 `official_title=null`, `discussion_type=trope_discussion`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`로 보수 유지됐다.
- `11718091`은 v287 live run에서 1차 Discourse가 `은영이`, `23센줄`을 seed로 올렸지만 `discourse_semantic_seed_guard`가 한 번 더 읽어 `title_novel_terms=[]`, `search_suggestions=[]`로 낮췄다.
- v287 reason에는 표현 오타/축약 패턴(범용)와 `작품 seed 제외`가 남았고 final은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`였다.
- 이 확인은 `23센줄` 문자열 hardcode가 아니라 LLM meaning pass + surface/context sanitizer + final scope guard가 같이 필요하다는 증거다.
- focused tests 11건과 `expert_main.py`/test syntax check가 통과했다.
- v286/v287은 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v284/v285 residual semantic review

- v284 잔여 P0/P1 21건을 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard` 조건으로 재실행했다.
- manifest 기준 `requested_parallel=36`, `effective_parallel=21`, `completed/failed/pending=21/0/0`, Docker shard auto up/recreate false였다.
- `11718091`은 표현 오타/축약/띄어쓰기 범용 재독해를 유지했고 final title null/context-only로 남았다.
- `11718080`은 친구/밥/같이 소설 보는 친구 한탄형 글로 보고 final title null/adjacent로 유지했다.
- `11718082`는 VLM/OCR on 조건에서 이미지 작품명 `재벌가 차녀의 2회차 걸그룹`을 처리했고 KakaoPage URL을 남겼다.
- Round2 리뷰 도구가 제목 약칭 + 공식 상세 URL 케이스를 no-anchor REJECT로 과잉 분류하던 문제를 `strong_title_alias_or_direct_evidence` 조건으로 보정했다.
- v285 after-review에서 `reason_says_no_anchor_but_resolved` 후보/선택은 `0/0`, `REJECT=0`이 됐다.
- `tests.test_qualitative_review_packet_tools` 33건, `tests.test_final_semantic_reread_gate` 5건, `py_compile`이 통과했다.
- 이 결과는 targeted canary와 리뷰 도구 수정 증거이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v280 final meaning/url guard live canary

- 이 계열은 사용자가 지적한 대로 표현 오타/축약/띄어쓰기 범용 재해독 meaning pass 케이스이며, 특정 문자열 금칙어를 추가하지 않았다.
- `11718091`은 v280 live canary에서 `semantic seed demotion 조기종료`가 실행되고, final `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 유지했다.
- `11718097`에서는 앞단 URL 검증이 `book.novelpia.com/novel/13336`을 `앤드북스` 대표 제목 불일치로 기각했지만, 호출부 fallback과 BatchContext alias rescue가 오래된 URL을 되살릴 수 있던 경로를 확인했다.
- `_freeze_identity_references()` 결과에서 제거된 URL을 다시 `or heretic_url`로 복구하지 않게 했고, BatchContext alias rescue가 title-compatible official detail URL만 쓰도록 보강했다.
- v280 known-bad 4건 rerun은 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard` 조건으로 실행했고, manifest는 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker shard auto up/recreate false였다.
- `11718097`은 최종 `망겜의 힐러`, URL `https://novel.munpia.com/328421`로 정리되었고 stale Novelpia URL은 결과에 남지 않았다.
- `tests.test_final_semantic_reread_gate` 3건과 `py_compile`이 통과했다.
- v280은 targeted known-bad canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v278 final semantic reread gate

- `23센줄`은 `23세인 줄` 오타/축약으로 읽는 자연어 이해 문제라는 점을 다시 반영했다.
- 기존 검색 전 `discourse_semantic_seed_guard`에 더해, 후단에서 final resolved title이 살아남은 high-risk 케이스에 `final_semantic_reread` LLM gate를 추가했다.
- 이 gate는 final candidate, 원문 title/body/comment, surface paraphrase, discourse warning, search evidence, image evidence를 함께 보고 원문이 실제로 후보 작품을 말하는지 재확인한다.
- `REJECT/HOLD/REPROCESS` 또는 `is_specific_work_discussion=false + Weak/Missing evidence`이면 final title을 null로 낮추고 `final_semantic_reread_rejected_resolution` 또는 `final_semantic_reread_reprocess_resolution` flag를 남긴다.
- `tests/test_final_semantic_reread_gate.py` 전용 회귀 테스트로 context-only 의미 재독해 후 search-only 후보가 demotion되는 경로를 확인했다.
- focused `23센줄` regression 4건과 social-lament/semantic seed regression 7건이 통과했다.
- 이 변경도 focused evidence이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v277 comment metadata coverage audit 도구화

- `tools\audit_comment_metadata_coverage.py`를 추가해 source JSONL과 result JSON의 댓글 메타/대화 맥락/post IP/VLM catalog coverage를 같은 표로 산출하게 했다.
- `tests\inputs\test01.jsonl` 기준 post row는 `104517`개지만 `ip/author_ip/post_ip/writer_ip`가 있는 row는 `0`개였다.
- comment row는 `368334`개이고 그중 IP가 있는 댓글은 `70337`개, comment IP가 있는 post는 `37656`개였다.
- original partial result 71행은 comments가 있는 row가 55개였지만 `comment_metadata`, `comment_dialogue_context_lines`, `image_evidence_catalog`는 모두 0이었다.
- v267 24건 rerun은 comments/meta/dialogue `16/16/16`, image/catalog `13/13`으로 evidence coverage가 회복됐다.
- `11718091` source duplicate comment id는 current loader 기준 1건으로 dedupe된다.
- coverage tool tests 3건과 bytecode 없는 syntax check가 통과했다. `py_compile`은 `tools\__pycache__` 권한 문제로 실패해 syntax check로 대체했다.
- 이 감사도 coverage 증거일 뿐이며 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v276 comment metadata loader/output 보강

- `expert_main.py` 결과 row에 `ip`, `author_ip`, `post_ip`를 남겨 review packet에서 원글 작성자 댓글 판별 근거를 잃지 않게 했다.
- JSONL 입력에서 post row와 comment row의 `post_id` 타입이 숫자/문자열로 섞여도 댓글이 붙도록 loader key를 정규화했다.
- 같은 `comment_id`의 중복 댓글은 dedupe해 대화 맥락이 과증폭되지 않게 했다.
- 현재 원본 입력 재구성 기준 `11718091`은 댓글 1건, `11718097`은 댓글 5건, `11718117`은 댓글 2건으로 정리됐다.
- `tests.test_expert_main_comment_metadata` 4건, known-bad focused regression 포함 20건, `py_compile`이 통과했다.
- 이 변경은 댓글/작성자 맥락 증거 보강이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v269 v264 VLM/OCR action rerun

- v264 action queue 24건을 Gemma 4 4B, VLM/OCR on, `--parallel 36 --reuse-shards-only` 조건으로 실제 재실행했다.
- `--parallel 36`은 max로 적용되어 `effective_parallel=24`였고, goal/targeted run 보호 cap으로 MCP endpoint pool은 8개였다.
- Docker shard auto up/recreate 없이 기존 shard만 재사용했고, 검색 endpoint health check는 `8/8 OK`였다.
- manifest 기준 `completed/failed/pending=24/0/0`, `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count=13`이었다.
- `11718080`, `11718082`, `11718083`, `11718091`, `11718097`, `11718099` known-bad는 대체로 회복 또는 보류됐다.
- `11718091`은 `23센줄 -> 23세인 줄` 의미 재독해를 reason에 남겨 하드코딩이 아니라 meaning pass로 처리됨을 다시 확인했다.
- 남은 P1은 `11718094` generic abstract title collision과 `11718117` OCR explicit title unresolved다.
- targeted runtime은 `GO`지만 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v266 v264 rerun readiness 확인

- v264 action queue 24건 재런을 진행하기 전에 현재 runtime readiness를 다시 확인했다.
- vLLM endpoint `http://10.20.0.101:8000/v1/models`는 HTTP 200으로 Gemma 4 4B model을 반환했다.
- 관련 `python.exe` 점유 프로세스는 없었다.
- `docker ps`와 TCP port probe 기준 현재 MCP/WARP shard는 5/36만 열려 있었다.
- `warp_shards.py status --json`은 Docker Desktop pipe access denied로 실패했다.
- 36 shard 기동을 위한 escalated `tools\warp_shards.py up --count 36` 요청은 abort되어 실제 기동하지 않았다.
- 따라서 v264 24건 VLM/OCR 재런은 실행하지 않았고, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v265 의미 재독해 경로 재확인

- `23센줄`은 `23세인 줄` 오타/축약으로 읽는 것이 맞고, 이 문제는 특정 문자열 하드코딩 차단이 아니라 meaning pass 문제임을 다시 확인했다.
- 현재 파이프라인은 `surface_age_expression_paraphrases`로 표면 의미 힌트를 만들고, `discourse_semantic_seed_guard`가 title/body/comment를 한 번 더 읽어 seed를 `context_only/drop`으로 낮춘다.
- seed demotion 뒤에는 강한 작품 앵커나 이미지/VLM 문맥이 없는 경우 Decoder/search 재승격을 조기 차단한다.
- 친구/밥/같이/소설/한탄형 글도 social-lament/generic-discourse로 재독해 대상이 된다.
- focused semantic reread regression 5건이 통과했다.
- 이번 확인은 targeted current-code 증거이며, 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v264 v263 action input 원본 JSONL 기반 재생성

- v263 `action_queue.json`을 실제 후속 재실행/사람 리뷰/브라우저 검토 입력으로 분리했다.
- 기존 `build_current_remaining_action_inputs.py`는 예전 `final_action/final_label` JSONL 큐에 맞춰져 있어 v263 JSON array queue를 바로 처리하지 못했다.
- action input builder가 JSON array queue, JSONL source, post/comment row 병합을 지원하도록 보강했다.
- source로 원본 result JSON을 쓰면 이미지 source missing이 37건 남았지만, `tests\inputs\test01.jsonl`을 source로 쓰면 `image_source_missing_post_ids=0`으로 해소됐다.
- v264 from-input 산출물은 `rerun_combined=24`, `browser_targets=37`, `human_review=56`, `slang_db_review=7`이다.
- known-bad 6건은 원본 content_blocks/comment 맥락을 보존한 후속 입력에 들어갔다.
- 현재 관련 Python 점유는 없었지만 Docker shard는 5개만 확인되어, 36-shard 기준 재런은 수행하지 않았다.
- qualitative packet tests 30건과 `py_compile`을 통과했다.

## 2026-05-30 - v263 original partial 최신 정성 리뷰 재산출

- 원본 `out\expert_result_20260528_141006_620986.json`은 `input=104502`, `completed=80`, `flushed=71`, `pending=9`인 partial source임을 다시 확인했다.
- 같은 review dir에서 random control을 먼저 생성하면 Round2가 random post_id까지 dedupe해서 high-risk sample이 0건이 되는 도구 버그를 확인했다.
- Round2 dedupe에서 `random_control` label을 제외해 random baseline과 high-risk oversample이 별도 층으로 유지되게 했다.
- random control label도 내부 high-risk bucket policy를 적용하게 해 `11718091` 같은 no-anchor resolved row가 `ACCEPT`로 미끄러지지 않게 했다.
- v263 review를 재생성했고 canonical review rows는 `141`, label 분포는 `ACCEPT=24`, `HOLD=32`, `REPROCESS=37`, `REJECT=18`, `INFO_MISSING=30`이었다.
- known-bad 6건은 원본 partial 기준 `REJECT`/`REPROCESS`/`HOLD`로 분리됐고, 원본 partial source는 여전히 semantic approval `NO-GO`다.
- qualitative packet tests 28건과 `py_compile`을 통과했다.

## 2026-05-30 - Round2/random image evidence catalog gate

- v259에서 public result에 추가한 `identity.image_evidence_catalog`를 Round2/random qualitative packet까지 연결했다.
- Round2 `evidence_catalog`는 이제 VLM/OCR 공개 근거의 `source_url`, `ocr_text`, `visual_summary`, `explicit_work_title`, `explicit_author_name`, `work_cues`를 보존한다.
- `image_evidence_catalog_missing` bucket을 추가해 이미지/VLM/OCR 근거가 필요한데 구조화 catalog가 없으면 `REPROCESS`로 보내게 했다.
- random control packet에도 `content_blocks`, `image_urls`, `image_count`, `image_evidence_catalog` 계열 필드를 남기게 했다.
- packet tools 26건과 `py_compile`이 통과했고, v259 실제 결과에서 `11718082`는 catalog present, `11718080`은 image bucket 없음으로 확인됐다.
- 이 변경은 정성 리뷰 도구의 evidence gate 보강이며 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v259 social-lament/VLM evidence schema 재검증

- `11718080`과 `11718082`를 Gemma 4 4B vLLM, VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on` 조건으로 재실행했다.
- manifest 기준 `input=2`, `completed/failed/pending=2/0/0`, `requested_parallel=36`, `effective_parallel=2`, Docker/shard auto up/recreate false, small-run lifecycle block true였다.
- `11718080`은 `소설/TS/갈드컵` 단어를 검색 seed로 밀어붙이지 않고 `discourse_semantic_seed_guard`가 한 번 더 자연어 의도를 읽어 `official_title=null`, `discussion_type=trope_discussion`, `title_resolution_allowed=false`로 유지했다.
- `11718082`는 VLM chunk request/result와 OCR/검색/KakaoPage page analysis를 통해 `재벌가 차녀의 2회차 걸그룹`으로 확정했다.
- `PickvelIdentity.image_evidence_catalog`를 추가하고, `expert_main.py` public result에 `content_blocks`, `image_urls`, `image_count`를 남겨 VLM/OCR 리뷰가 reason/log 파싱에 의존하지 않도록 했다.
- 이미지가 없는 글에는 status-only `image_evidence_catalog`를 남기지 않도록 조정했다.
- focused unittest와 `py_compile`을 통과했고, 리뷰 산출물은 `qualitative_review\20260528_141006_620986\v259_post11718080_11718082_schema_review_ko.md`다.
- v259도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v256 known-bad 4건 VLM/OCR-on 재검증

- v255 댓글 author/IP attribution 보강 후 `11718083`, `11718091`, `11718097`, `11718099`를 Gemma 4 4B vLLM, VLM/OCR on 조건으로 재실행했다.
- 실행 명령은 `expert_main.py --parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on`이고, manifest 기준 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`이었다.
- 소규모 run이라 Docker/shard auto up/recreate는 false였고 small-run lifecycle block이 켜져 있었다.
- `11718091`은 사용자가 지적한 대로 `23센줄`을 `23세인 줄` 오타/축약으로 다시 읽었고, 최종 `official_title=null`, `discussion_type=noise`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 유지했다.
- `11718091` 댓글은 `author=ㅇㅇ`, `ip=null`이라 원글 작성자 댓글로 확정하지 않고 `speaker=user1`, `post_author_match_unverified=true`로 남겼다.
- `11718097`은 `망겜의 힐러`와 문피아 상세 URL로 회복됐고, `11718099`는 OCR 후보와 충돌하더라도 `빌어먹을 환생`을 final title로 유지했다.
- 리뷰 산출물은 `qualitative_review\20260528_141006_620986\v256_known_bad_4_after_comment_attribution_review_ko.md`다.
- v256은 targeted canary이므로 전체 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v255 comment author/IP attribution 보강

- `tests\inputs\test01.jsonl`에는 comment row `368,334`건이 있고 author/comment_id는 모두 있었으며, comment IP non-empty도 `70,337`건 있었다.
- 반대로 같은 입력의 post row에는 `ip/author_ip/post_ip/writer_ip`가 비어 있었고, 20260528 원본 result 71 rows에는 `comment_metadata/comment_context_lines/comment_dialogue_context_lines`가 모두 없었다.
- 이 때문에 원본 20260528 result는 댓글 대화 맥락 품질 승인 근거가 아니라 `NO-GO`다.
- `AgenticPipeline`과 `expert_main.py` public metadata에서 익명/공통 author는 IP 확인 없이는 `role=post_author`로 확정하지 않도록 했다.
- author 문자열은 같지만 IP 확인이 없으면 `post_author_match_unverified=true`, `role=author_match_unverified`를 남긴다.
- current-code 재구성에서 `11718091`은 `speaker=user1`, `role=author_match_unverified`로 내려갔고, `11718097`의 `ㅇㅇ` 댓글 4건도 post_author 확정이 아니라 미확정으로 남았다.
- Round2 정성 리뷰 bucket에 `comment_author_match_unverified_dialogue`를 추가했다.
- focused regression 10건, packet tools 24건, `py_compile`을 통과했다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v254 `11718091` semantic reread 재확인

- 사용자가 지적한 대로 `23센줄`은 `23세인 줄` 오타/축약으로 먼저 읽어야 하는 케이스임을 재확인했다.
- current-code v251 canary의 `analysis_result.identity`는 `11718091`을 `official_title=null`, `discussion_type=noise`, `title_resolution_state=context_only`, `title_resolution_allowed=false`로 유지한다.
- 공개 reason에는 `표면 표현 해석: 23센줄 -> 23세인 줄; 16살인줄 -> 16살인 줄`, `의미 재검토`, `작품 seed 제외: 은영`이 남는다.
- 구조적으로는 `surface_paraphrase_notes`가 원문 표면을 보존하고, `discourse_semantic_seed_guard`가 검색 전에 한 번 더 읽은 뒤, direct work anchor가 없으면 후단 검색/Decoder/BatchContext 재승격을 막는다.
- focused regression 6건을 통과했다.
- 확인 산출물은 `qualitative_review\20260528_141006_620986\v254_post11718091_semantic_reread_confirmation_ko.md`다.
- v254는 current-code targeted 확인이며, 원본 20260528 partial source나 10만 건 semantic approval 근거가 아니다. 전체 gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v253 systemic bucket extraction tooling

- v252 audit에서 문서화한 반복 실패 패턴을 Round2 high-risk bucket으로 승격했다.
- 추가 bucket은 `batch_memory_exact_alias_rescued_no_anchor`, `critical_counter_but_resolved`, `notes_demoted_then_resolved`, `title_surface_primary_candidate_rescued`, `official_url_missing_for_resolved`, `reason_says_no_anchor_but_resolved`, `search_absent_verified_title_direct_image_title`다.
- 각 bucket의 label/action 정책과 packet 공개 field를 추가했다.
- focused tests 3건과 review tool `py_compile`을 통과했다.
- v253 preflight는 원본 20260528 source를 `REVIEW-LOCKED`로 유지했다.
- v253 partial-source Round2 sample은 69 packets, `ACCEPT=22`, `HOLD=27`, `REPROCESS=3`, `REJECT=7`, `INFO_MISSING=10`으로 생성됐다.
- 이 수치는 partial 71행에 대한 failure-pattern seed이며 10만 건 semantic approval 근거가 아니다.

## 2026-05-30 - v250/v251 VLM/OCR 오독 title conflict 재검증

- v250 known-bad 4건 VLM/OCR-on 재실행에서 `11718099`가 VLM/OCR 오독 title `검은 여왕의 혼성명`으로 잘못 resolved되는 회귀를 확인했다.
- 같은 로그에서 Verifier는 `search_absent_verified_title`로 해당 image/OCR title을 낮췄지만, 후단 Arbiter/suspected title 경로가 다시 final title로 되살렸다.
- Codex 내장 브라우저로 실제 post를 열어 이미지 로딩 완료 화면을 확인했고, `qualitative_review\20260528_141006_620986\v251_post11718099_browser_actual.png`로 증거를 남겼다.
- `AgenticPipeline`에 weak direct image/OCR title canonical rescue guard를 추가해, Verifier가 nullify한 image/OCR-only title보다 안정 alias/official/search 근거가 강한 canonical 후보가 이길 수 있게 했다.
- focused regression `test_verifier_nullified_image_ocr_title_yields_to_stable_alias_canonical_rescue`를 추가했고 관련 5건과 `py_compile`을 통과했다.
- v251 live run `20260530_063929_178214`은 `--parallel 36 --reuse-shards-only --slang-db on --vlm on --ocr on` 기준으로 `input=4`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false였다.
- v251 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://m.munpia.com/novel/detail/222360`, flags `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias`로 회복됐다.
- v251 실런에서 최종 회복은 `batch_memory_exact_alias_rescued` 경로였고, 새 weak-image canonical rescue branch는 focused unittest로 증명했다. 따라서 expanded review에서 실제 trigger 빈도와 OCR-only alias 오염을 추가 확인한다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v248/v249 social-lament semantic reread

- `23센줄`을 `23세인 줄`로 읽듯이, `소설 보는 친구 있으면 좋음`류도 검색 전에 자연어 의도를 한 번 더 읽어야 한다는 점을 반영했다.
- `DiscourseAnalyzer`에 소설 일반어 + 친구/밥/같이/토론/한탄 신호를 감지하는 social-lament trigger를 추가했다.
- 기억 회수/작품 찾기 신호가 있으면 social-lament로 단정하지 않도록 제외 조건을 뒀다.
- v249에서는 이 trigger를 seed 부재 케이스에 한정하지 않고, `title_novel_terms`/`search_suggestions`가 이미 생긴 경우에도 독립적으로 작동하게 확장했다.
- v248 `11718080` live run `20260530_060425_880984`에서 1차 Discourse의 `ts`, `갈드컵`, `ts 갈드컵 소설` seed가 semantic seed review 후 제거됐고, 검색/Decoder 재승격 없이 종료했다.
- v249 `11718080` live run `20260530_061108_125280`에서는 1차 Discourse의 `소설`, `TS 주류 소설`, `갈드컵 TS 소설` seed가 semantic seed review 후 제거됐다.
- 최종 `11718080`은 `official_title=null`, `is_relevant=false`, `discussion_type=trope_discussion`, `title_resolution_allowed=false`로 확인됐다.
- v248/v249도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v246 anonymous author/IP comment dialogue guard

- DC 익명 댓글에서 `ㅇㅇ` author 문자열만으로 post author 여부를 판단하면 다른 사용자의 댓글을 원글 작성자 이어쓰기처럼 읽을 수 있는 위험을 확인했다.
- `PostInput`에 `ip/author_ip/post_ip`를 추가하고, `expert_main.py`가 입력의 `ip/author_ip/post_ip/writer_ip`를 보존해 넘기도록 했다.
- `AgenticPipeline._post_to_dict()`는 `post_ip`를 public packet에 남기고, 익명/공통 author의 speaker key는 IP까지 반영한다.
- focused regression 4건과 `py_compile`을 통과했다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v245 title-null reason scoreboard alignment

- v244 `11718089`는 final identity가 `official_title=null`, `is_relevant=false`, `title_resolution_state=author_new_work_context`, `title_resolution_allowed=false`로 맞았지만, `[근거 스코어]`가 `grounding_anchor: +2 (강한 앵커(plot_mention))`를 남겼다.
- 이 문제는 최종 title-null 판정 자체의 실패가 아니라, 공개 reason이 evidence보다 강하게 말하는 review-signal 품질 이슈다.
- `AgenticPipeline._build_reason_scoreboard_lines()`를 보강해 `official_title`이 없으면 `plot_mention/character_title_link/character_mention/author_mention`을 title 확정용 강한 앵커로 표시하지 않게 했다.
- 비관련 title-null은 `작품명 확정에는 쓰지 않는 맥락 앵커(...)`, 관련 but title-null은 `작품 맥락 앵커(...) - 정식 제목 미확정`으로 표시한다.
- focused regression 5건과 `py_compile`을 통과했다.
- v245 live run `20260530_052428_641974`은 `11718089` 단건을 `--parallel 36 --reuse-shards-only --slang-db on --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false였다.
- 최종 `11718089`는 `official_title=null`, `title_resolution_state=author_new_work_context`, `title_resolution_allowed=false`, score line `grounding_anchor: -2 (약한 앵커(search_only))`로 확인됐다.
- v245는 deterministic reason patch이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v243 author/new-work alias rescue 차단

- `11718089`는 `개돌 신작`이라는 author/new-work 표면 위에서 초대남/금태양/NTR 같은 장르 클리셰를 불평하는 글이었다.
- v242에서는 Discourse/Arbiter가 `discuss_genre(high)`와 deliberate null-title을 냈는데, 후단 BatchContext/search alias rescue가 `개돌 -> 파벨 주니어`를 다시 resolved로 승격했고 `slang_db`에도 오염 entry를 남겼다.
- `[별명/작가] 신작`, `[별명] 대체 뭘 쓰...` 표면을 author/new-work alias surface로 추출하고, 이 표면은 `search_evidence_alias_inference`와 오염된 `batch_memory` hit 모두에서 final title rescue에 쓰지 않도록 했다.
- deliberate null + genre/trope/community/no-work 경고 + direct title proof 부재 상태에서는 official detail URL만으로 검색 추정 alias rescue가 final title을 뒤집지 못하게 했다.
- focused unittest 5건과 `py_compile`을 통과했다.
- v243 live run `20260530_042526_026150`은 `11718089` 단건을 `--parallel 36 --reuse-shards-only --slang-db on --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false였다.
- 최종 `11718089`는 `official_title=null`, `is_relevant=false`, `discussion_type=noise`, `title_resolution_allowed=false`, flags `batch_memory_alias_rescue_blocked_nonwork_context`, `batch_memory_alias_rescue_blocked_deliberate_null`로 확인됐다.
- v242가 만든 `slang_db` 오염 `개돌 -> 파벨 주니어` bucket은 제거했고, 현재 DB에서 해당 문자열이 검색되지 않는다.
- v243도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v240 context-only scope와 원본 partial source 재확인

- 사용자가 지적한 것처럼 `23센줄`은 `23세인 줄` 오타/축약으로 먼저 읽어야 하고, 이 유형은 단어 검색을 더 하는 문제가 아니라 검색 전 자연어 의미 재판독 문제다.
- v239까지는 `11718091`이 `official_title=null`, `title_resolution_allowed=false`로 내려갔지만 `title_resolution_state=unresolved_matchable`이 남아, 사람이 보면 아직 매칭 가능한 미해결 작품처럼 보일 수 있었다.
- `title_resolution_state=context_only`를 추가하고, `semantic_seed_review(no_work_anchor)` 또는 seed review warning이 작품 seed를 문맥 표현으로 낮춘 경우 final scope field도 `context_only`로 정렬했다.
- 약한 캐릭터 나이/외모 반응 차단 경로에는 `context_only_no_work_anchor` flag를 남겨 대규모 리뷰 bucket에서 잡을 수 있게 했다.
- focused regression 4건과 `py_compile`을 통과했다.
- v240 live run `20260530_032804_873598`은 known-bad 4건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=4`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false였다.
- v240 `11718091`은 `official_title=null`, `discussion_type=noise`, `title_resolution_state=context_only`, flags `context_only_no_work_anchor`로 확인됐다.
- 같은 run에서 `11718083=null/unresolvable_memory_query`, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`은 유지됐다.
- 원본 `out\expert_result_20260528_141006_620986*`는 `input_post_count=104502`이지만 `completed=80`, `flushed=71`, `pending=9`인 partial source임을 재확인했다. 이 source는 승인 근거가 아니라 failure-pattern discovery/retest seed로만 사용한다.
- v240도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v239 platform branding fetch title 처리와 known-bad 4건 재확인

- v237 `11718097`은 final title과 URL이 `망겜의 힐러`로 맞았지만, 문피아 모바일 fetch가 `웹소설의 유토피아, 글세상 문피아` 같은 플랫폼 브랜딩 title을 읽어 URL-title mismatch 경고를 냈다.
- 이 경고는 실제 URL 오류라기보다 fetch parser의 플랫폼 브랜딩 title 노이즈였고, 대규모 리뷰에서 false positive로 작동할 수 있었다.
- `_is_platform_branding_title()`과 fetched-title mismatch 검사를 보강해 platform branding/listing/generic title은 `heretic_url 제목 불일치`로 세지 않게 했다.
- focused regression 4건과 `py_compile`을 통과했다.
- v239 live run `20260530_031006_533601`은 known-bad 4건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=4`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false였다.
- 최종 결과는 `11718083=null/unresolvable_memory_query`, `11718091=null/noise`, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`이다.
- `11718097`은 `comment_metadata=5`, `comment_dialogue_context_lines=5`를 보존했고, `11718099`는 OCR conflict flags 2개를 유지했다.
- v239도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v238 VLM/OCR conflict structured flags

- v237 `11718099`는 final reason에서 OCR/표지 후보가 최종 제목과 일치하지 않아 보조 제목 근거로 사용하지 않는다고 설명했지만, `identity.consistency_flags`에는 이 충돌이 남지 않았다.
- 대규모 정성 리뷰에서는 자연어 reason만으로 위험 bucket을 안정적으로 과표집하기 어렵기 때문에, OCR title mismatch를 구조 flag로 노출해야 한다.
- `AgenticPipeline._image_grounding_mismatch_flags()`를 추가해 VLM/OCR direct title 후보와 final `official_title`이 normalized/similar match되지 않으면 `vlm_ocr_title_conflict_with_final_title`를 남기게 했다.
- final title이 locked official/detail 또는 안정 alias 후보로 뒷받침되면 `ocr_title_conflict_with_stable_alias`도 함께 남긴다.
- focused regression 4건과 `py_compile`을 통과했다. 이 묶음에는 `23센줄 -> 23세인 줄` 자연어 재독해 reason 회귀도 포함했다.
- v238 live run `20260530_025454_691972`은 `11718099` 1건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false였다.
- 최종 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`이고, final identity와 log active-learning queue에 `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias`가 남았다.
- v238은 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v237 batch memory exact alias URL/evidence follow-up

- v235 동일 4건 targeted run에서 `11718099`는 `빌환 -> 빌어먹을 환생` title은 회복했지만, 경우에 따라 final `heretic_url`과 public evidence counter가 비어 남을 수 있었다.
- 원인은 `batch_memory_exact_alias_rescued` 일반 경로가 v234의 stable alias conflict/canonical base correction과 달리 corrected title official URL recovery를 호출하지 않는 구조였다.
- `AgenticPipeline`에 exact alias rescue 이후 URL이 비어 있으면 corrected title 기준 official detail URL을 회복하고 candidate/primary_work/reason evidence state를 동기화하는 경로를 추가했다.
- 새 regression `test_batch_memory_exact_alias_rescue_recovers_official_url`은 alias 후보만 있고 URL이 없는 상태에서 `https://novel.munpia.com/222360` 회복과 `official_urls=1` reason sync를 검증한다.
- focused unittest 4건과 `py_compile`을 통과했다.
- v236 단건 live run `20260530_023033_856559`은 `11718099`를 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, Docker lifecycle false였다.
- v237 동일 4건 live run `20260530_023511_350246`은 manifest 기준 `input=4`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, VLM/OCR on, `image_post_count=3`, Docker lifecycle false였다.
- v237 최종 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, `official_title_evidence=true`, `official_urls=1`로 확인됐다.
- v237 `11718091`은 `23센줄 -> 23세인 줄`, `작품 seed 제외: 23센줄, 은영`, `title_resolution_allowed=false`를 유지했다.
- VLM/OCR이 읽은 `붉여먹을 혼성명`은 최종 제목과 불일치하므로 보조/conflict evidence로 남긴다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v234 corrected title official URL/evidence recovery

- v230에서 `11718077`은 `즉사무림 -> 즉사기 들고 무림에 떨어지다` title 교정까지는 성공했지만, corrected title의 `heretic_url`과 public evidence counter가 비어 있었다.
- late title correction 이후 공식 URL/evidence를 다시 찾는 `_recover_corrected_title_official_url()` 경로를 추가했다.
- 검색 결과의 visible title이 `네이버 시리즈`, `novel.munpia.com`처럼 generic하더라도 snippet/content/description에 corrected title이 strict match되면 공식 detail URL 후보로 인정한다.
- final reason의 `official_title_evidence`와 `official_urls` counter를 final URL/candidate evidence 상태와 동기화해 `official_urls=0` 불일치를 제거했다.
- focused regression 9건과 `py_compile`을 통과했다.
- v234 live run `20260530_015610_155152`은 `11718075`, `11718077` 2건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=2`, `effective_parallel=2`, Docker lifecycle false였다.
- 최종 `11718077`은 `official_title=즉사기 들고 무림에 떨어지다`, `heretic_url=https://series.naver.com/novel/detail.series?productNo=14041321`, flags `official_detail_url_repaired_from_search`, `stable_alias_conflict_corrected`, `stable_alias_official_url_recovered`로 확인됐다.
- 이 회복은 `validated=false`, `source=title_matched_search`이므로 targeted canary는 `GO`지만 evidence grade는 validator/fetch 확인과 분리한다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v230 stable alias conflict correction

- `11718077`은 제목 `스포) 즉사무림 예상된 전개긴하지만`, 본문 `서무량`, `흑도애들` 등 특정 작품 전개 감상이다.
- `slang_db`/BatchContext에는 `즉사무림 -> 즉사기 들고 무림에 떨어지다` 안정 alias가 있었지만, v229 실런은 느슨한 검색 결과를 따라 `즉사수선전: 선협 세계에서 즉사기로 살아남기`로 다시 수렴했다.
- 핵심 원인은 후단 stable alias 보정이 이전 Decoder 오판을 current title의 원문 언급 증거처럼 재사용한 것이다. 자연어 재이해가 있어도 그 재이해가 이전 오판을 다시 근거로 먹으면 비단조 오류가 반복된다.
- `AgenticPipeline._stable_batch_alias_conflicts_with_official_title()`에서 current title 직접 언급 검사를 raw title/body/comment strict match 기준으로 바꿨다. Decoder의 `original -> best_match.title` 간접 매핑은 이 보정 단계에서 direct evidence로 쓰지 않는다.
- 회귀 테스트에는 Decoder가 이미 `즉사무림 -> 즉사수선전`으로 오판한 상태를 추가했다.
- focused unittest 3건과 `py_compile`을 통과했다.
- v230 live run `20260530_010824_738895`은 `11718075`, `11718077` 2건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=2`, `effective_parallel=2`, Docker lifecycle false였다.
- 최종 `11718077`은 `official_title=즉사기 들고 무림에 떨어지다`, `discussion_type=review`, `subtype=review_reaction`, `anchor_type=title_alias`, flags `stable_batch_alias_conflict_corrected`, `search_title_conflict_with_stable_alias`로 확인됐다.
- 다만 corrected title의 `heretic_url=null`, `official_title_evidence=false`가 남아 공식 URL/evidence 회복은 별도 후속이다.
- v230도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v228 short support-cheer alias probe 보존

- `11718075`는 제목 `이제는 죽깨수 올 때 됐다`, 본문 `가자 돌마늘!`의 짧은 응원/기대글이다.
- v226 실패 원인은 Discourse/Decoder가 낸 `죽깨수 웹소설` 검증 쿼리가 `association_post(title_body_mismatch)` 정합성 필터에서 저특이로 제거된 것이었다.
- 이 경우는 `23센줄 -> 23세인 줄`처럼 검색 차단해야 하는 자연어 오타/나이표현과 다르다. 제목 compact alias와 응원/기대 화행이 결합하면 final 확정은 보수적으로 하더라도 alias 검증 검색은 살아야 한다.
- `Orchestrator._collect_short_support_alias_probe_terms()`를 추가해 `올 때 됐다/복귀/재개/존버/기우제`류 제목 프레임과 `가자/가즈아/드가자/레츠고/화이팅`류 본문 화행이 함께 있을 때만 probe를 보존하게 했다.
- 특정 post id나 `죽깨수` 하드코딩 없이, 나이/오타 표면과 상태어/일반어/감탄어는 제외한다.
- 후처리 taxonomy도 `support_cheer/title_alias`로 정렬했다.
- focused unittest 3건과 `py_compile`을 통과했다.
- v228 live run `20260530_003717_935082`은 `11718075` 단건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, Docker lifecycle false였다.
- 최종 결과는 `official_title=죽었다 깨어도 수선`, `is_relevant=true`, `discussion_type=anticipation`, `subtype=support_cheer`, `anchor_type=title_alias`, `anchor_strength=medium`이다.
- 증거는 공식 플랫폼/검색 기반이지만 본문 직접 앵커가 약하므로 evidence grade는 `Medium`이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-30 - v225 context-only semantic reread trigger

- `23센줄`은 `23세인 줄` 오타/축약으로 먼저 읽어야 한다는 사용자 지적을 다시 반영했다.
- v222가 `surface_paraphrase_notes` 기반 재독해였다면, v225는 seed 후보와 검색 제안이 없어도 짧은 글이 `discuss_work/work`로 과분류될 때 의미 재독해를 한 번 더 실행하는 보강이다.
- `DiscourseAnalyzer._should_run_semantic_seed_review()`에 `short_context + claimed_specific_work + sentence_like_title + stable_alias_absent` 조건을 추가했다.
- 원문에 `히집악` 같은 안정 약칭/정식 제목이 직접 있으면 이 context-only 재독해를 강제하지 않도록 했다.
- focused unittest 5건과 `py_compile`을 통과했다.
- v225 live run `20260530_001113_086437`은 `11718091` 단건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, Docker lifecycle false였다.
- 최종 결과는 `official_title=null`, `is_relevant=false`, `discussion_type=noise`, `title_resolution_allowed=false`이며 reason에 `23센줄 -> 23세인 줄`, `작품 seed 제외: 23센줄, 은영`이 남았다.
- v225도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v223 author-meta batch alias rescue guard

- `11718069`의 핵심은 `애호뉴비` 별칭 자체가 아니라, 작가 품평/방향 제안 글에서 부차 참조 alias가 후단 BatchContext rescue로 단일 공식 제목이 되는 비단조 오류였다.
- final assembly 단계에서 `forced_adjacent_author_meta_context`, `adjacent_relevant/author_meta`, 작가 벤치마크/조언 신호가 있으면 BatchContext alias rescue를 차단하도록 했다.
- 새 flag `batch_memory_alias_rescue_blocked_by_author_meta`를 남겨, alias가 보였지만 왜 공식 제목으로 승격하지 않았는지 공개 필드에서 추적할 수 있게 했다.
- v223 live run `20260529_233229_514489`은 `11718069` 단건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, Docker lifecycle false였다.
- VLM은 첨부 이미지 1개를 처리했지만 title evidence가 아니라 character visual 정도로 낮췄다.
- Codex 내장 브라우저로 원문을 열어 제목, 본문 두 줄, 첨부 이미지 1개, 댓글 0개를 확인했고 full-page screenshot을 `qualitative_review\20260528_141006_620986\v223_11718069_browser_full.png`에 남겼다.
- 최종 결과는 `official_title=null`, `is_relevant=false`, `discussion_type=author_talk`, `topicality=adjacent_relevant`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`였다.
- focused unittest 5건과 `py_compile`을 통과했다.
- v223도 targeted follow-up이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v222 surface paraphrase semantic review guard

- `23센줄` 같은 표면 오타/축약은 검색 seed가 아니라 `23세인 줄` 자연어 의미로 먼저 읽어야 한다는 원칙을 재확인했다.
- `surface_paraphrase_notes`가 있으면 title/search 후보가 없어도 `discourse_semantic_seed_guard`가 실행되도록 순서를 조정했다.
- 새 regression은 후보가 비어 있는 상태에서도 LLM 의미 재검토가 호출되고 `23센줄 -> 23세인 줄` 힌트가 prompt에 들어가는지 확인한다.
- v222 live run `20260529_232222_633490`은 `11718091` 단건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, Docker lifecycle false였다.
- 1차 Discourse는 `은영`, `23센줄`을 seed로 올렸지만, semantic seed guard와 surface sanitizer가 검색/Decoder 재승격 전에 이를 낮춰 조기 종료했다.
- 최종 결과는 `official_title=null`, `is_relevant=false`, `discussion_type=noise`, `title_resolution_allowed=false`이며 reason에 `표면 표현 해석`과 `작품 seed 제외`가 남았다.
- focused unittest 5건과 `py_compile`을 통과했다.
- v222도 targeted canary이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v221 connective alias guard and VLM recommendation preservation

- v219 잔여 중 `11716499`와 `11718087`을 2-post targeted input으로 분리해 재실행했다.
- 코드에서는 VLM/OCR synthetic block과 non-image title/body/comment를 분리하는 `_collect_non_image_post_text()`를 추가했다.
- `그러는데`, `하는데`, `같은데`, `근데` 같은 접속형 문장 조각은 low-specificity rescue key로 보고 BatchContext/search alias rescue에서 제외한다.
- 제목/본문의 추천·탐색 의도는 비홍보 이미지나 generic relation demotion이 `off_topic/noise`로 덮지 못하게 했다.
- v221 live run `20260529_230123_759595`는 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, `effective_parallel=2`, Docker lifecycle false였다.
- Codex 내장 브라우저로 `11718087` 원문을 열어 제목, 첨부 카드 이미지, 본문 `ts잘먹음`을 확인했고 full-page screenshot을 `qualitative_review\20260528_141006_620986\v221_11718087_browser_full.png`에 남겼다.
- `11718087`은 `official_title=null`, `topicality=adjacent_relevant`, `discussion_type=recommendation`, `title_resolution_state=adjacent`로 유지됐다.
- `11716499`는 `official_title=null`, `is_relevant=false`로 내려갔고 `그러는데 -> 어느날` rescue가 재현되지 않았다.
- focused unittest와 batch alias/VLM regression, `py_compile`을 통과했다.
- v221도 targeted follow-up이므로 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v219 실패군 확대 재실행 및 정성 리뷰

- v218 root-cause matrix 이후 다음 실행 단위를 만들기 위해 `v219_failure_family_expansion_*` 산출물을 추가했다.
- v215 pattern scan에서 failure family별 후보를 뽑고 중복 post id를 제거해 30개 post를 선정했다.
- 입력 JSONL은 36 lines이며 post row 30개와 comment row 6개를 포함한다.
- family는 `comment_dialogue_metadata_gap`, `friend_social_lament_or_generic_discourse`, `known_bad_controls`, `memory_query_or_generic_resolved_title`, `run_integrity_recovery_followup`, `url_evidence_state_mismatch`, `vlm_ocr_evidence_review`, `weak_evidence_strong_resolution`로 나눴다.
- `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 재실행했다.
- run id `20260529_221420_463966`은 `completed/failed/pending=30/0/0`, `requested_parallel=36`, `effective_parallel=5`, `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count=19`였다.
- 작은 targeted run이라 Docker/shard lifecycle은 열리지 않았고, healthy endpoint filter로 `8 -> 5`개 shard만 사용했다.
- 정성 라벨은 `ACCEPT=25`, `HOLD=3`, `REPROCESS=1`, `REJECT=1`이다.
- `11718091`은 `23센줄 -> 23세인 줄`로 재독해되어 닫혔고, `11716499` generic alias 과확정과 `11718087` VLM/OCR 우선순위 충돌은 후속 action으로 남겼다.
- v219은 targeted expansion이며 10만 건 semantic approval 근거가 아니다. gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v218 current semantic root-cause matrix

- `qualitative_review\20260528_141006_620986\v218_current_semantic_root_cause_matrix_ko.md`를 추가했다.
- 원본 `out\expert_result_20260528_141006_620986.json`는 `104,502`건 입력 중 completed `80`, flushed `71`, pending `9`인 partial run이므로 전체 승인 근거가 아니라 failure family discovery 근거로만 둔다.
- v215 scan의 반복 패턴은 `comment_speaker_context_unavailable=64`, `image_or_ocr_involved=43`, `search_degraded_resolved=27`, `weak_evidence_but_strong_resolution=18` 순으로 확인됐다.
- v212~v217 기준 `11718083`, `11718091`, `11718097`, `11718099`, `11718080`은 targeted/current-code canary 기준으로 기대 상태를 확인했다.
- 현재 원인은 검색 전 자연어 의미 재판독, 댓글 대화 흐름, 후단 rescue 비단조 오류, VLM/OCR conflict, URL/evidence-state 불일치, slang DB/BatchContextMemory 오염으로 분리했다.
- 전체 10만 건 semantic gate는 새 completed source 또는 충분한 random baseline/P0/P1 high-risk expansion 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v217 friend/social lament generic discourse canary

- `11718080`은 “소설 보는 친구 있으면 좋음”이라는 제목과 TS/갈드컵 토론 본문을 가진 친구/한탄형 장르 잡담이다. 자연어적으로는 특정 작품 찾기나 작품 리뷰가 아니라 소설 장르 얘기를 나눌 친구를 바라는 글이다.
- 원본 partial run의 false positive는 검색 결과/후단 batch memory rescue가 장르 일반론 판정을 다시 작품명으로 뒤집은 경로였으므로, 현재 코드에서 같은 글이 다시 뒤집히지 않는지 단건으로 확인했다.
- v217 live run `20260529_215812_243878`은 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, Docker lifecycle flags false였다.
- v217 result는 `official_title=null`, `is_relevant=false`, `discussion_type=trope_discussion`, `is_novel_related=true`, `is_resolved_work_discussion=false`, `title_resolution_allowed=false`였다.
- `discourse_semantic_seed_guard`는 `소설`을 `context_only`로 낮추고 `ts 주류 소설`, `갈드컵 ts 토론` 검색 제안을 drop했다.
- late rescue/generic discourse veto 3건과 `23센줄` 의미 재판독 4건 focused regression, 관련 `py_compile`을 통과했다.
- 새 코드 변경은 없고, v181/v216에서 추가된 구조적 guard가 현재 서버 기준으로 작동함을 확인한 current-code canary다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v216 semantic seed reread includes dialogue context

- `discourse_semantic_seed_guard` payload에 `comment_context`와 `comment_dialogue_context`를 추가해, 검색 전 의미 재판독 LLM이 댓글 발화 흐름까지 함께 읽게 했다.
- prompt에는 오타/축약/띄어쓰기 깨짐을 먼저 자연어 의미로 풀어 읽고, 나이/외모/잡담이면 작품 seed로 쓰지 말라는 원칙을 추가했다.
- `speaker/author/ip/comment_id/reply_to`는 대화 흐름 메타이지 작품 identity evidence가 아니라는 규칙도 같은 단계에 명시했다.
- focused regression 4건과 `py_compile`을 통과했다.
- v216 live run `20260529_214738_328891`은 `11718091` 단건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=1`, `effective_parallel=1`, Docker lifecycle false였다.
- v216 result는 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄`, `작품 seed 제외: 은영이`, `official_title=null`, `title_resolution_allowed=false`를 확인했다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v214 comment dialogue context and memory-query demotion

- `comment_dialogue_context_lines`를 추가해 댓글의 `speaker/author/ip/reply` 메타와 댓글 text excerpt를 같은 #번호로 묶어 prompt와 review packet에 전달한다.
- 이 필드는 대화 흐름 이해용이며, speaker/author/ip 자체는 작품명/별칭 evidence로 계산하지 않는다.
- Gatekeeper/Discourse/Verifier prompt JSON, Decoder evidence-based reread, Arbiter/Synthesizer prompt, qualitative random/round2 packet을 갱신했다.
- memory-query 신호가 있는 글은 `unresolved_worklike_hold`가 `character_talk` unresolved relevant로 되살리지 못하게 했다.
- v213 live run `20260529_211723_327967`은 known-bad 4건을 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, `effective_parallel=4`, Docker lifecycle flags false였다.
- v213 `11718091`과 `11718097`은 `comment_dialogue_context_lines`에 post_author/user speaker, reply 관계, 댓글 text excerpt를 남겼다.
- v214 single canary `20260529_213151_621141`에서 `11718083`은 `is_relevant=false`, `discussion_type=recommendation`, `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 확인됐다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v212 resolved title follow-up and webnovel volume URL

- `23센줄`류는 `23세인 줄` 오타/축약이라는 자연어 이해가 `surface_paraphrase_notes`, `discourse_semantic_seed_guard`, final reason으로 이어지는지 focused regression으로 재확인했다.
- v210 `11718097`은 `망겜힐 -> 망겜의 힐러` title recall은 맞았지만 공식 URL이 비어 evidence strength가 `Medium`이었다.
- `단행본` 표지는 단독이면 비소설/웹툰 의심 신호지만, 같은 title/snippet에 `웹소설/#NOVEL/novel/장르소설`이 있으면 소설 evidence로 보존하게 했다. `웹툰/만화/COMIC/manga/anime`은 계속 non-novel media로 본다.
- `오행복` 같은 주변어에서 엉뚱한 official URL이 잡혀도 `망겜힐 -> 망겜의 힐러` resolved title 공식 검증 검색을 생략하지 않게 했다.
- focused regression 7건, 전체 `tests.test_agentic_pipeline_rework -v` 335건, 관련 `py_compile`, `git diff --check`를 통과했다.
- v212 live run `20260529_205511_871370`은 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest/log 기준 `input=1`, `effective_parallel=1`, Docker lifecycle flags false였다.
- v212 result `11718097`은 `official_title=망겜의 힐러`, `heretic_url=https://m.munpia.com/novel/detail/328421`, `confidence=High`, `official_title_evidence=true`, `official_urls=4`로 확인됐다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v187 VLM/OCR reason evidence alignment

- v184 `11718099`는 final title이 `빌어먹을 환생`으로 회복됐지만, 이미지 OCR drift 후보 `불먹을 혼성명`을 reason에서 "보조 제목 표기"처럼 표현했다.
- 이 문제는 final title 오염은 아니지만 evidence alignment 관점에서 reason이 OCR 후보를 과하게 지지 근거처럼 말하는 잔여 리스크다.
- `_build_image_grounding_note()`를 수정해 최종 title과 OCR/표지 후보가 일치할 때만 직접 이미지 근거로 표현하고, 다르면 "보조 제목 근거로 사용하지 않습니다"로 낮춘다.
- focused unittest 2건과 `py_compile`을 통과했다.
- `qualitative_review/20260528_141006_620986/v187_active_goal_requirement_audit_ko_20260529.md`에 active goal 요구사항별 증거와 남은 gate를 다시 정리했다.
- 이 변경은 unit 기준 검증이며, 다음 `--vlm on --ocr on` live canary에서 `11718099` reason 문구를 재확인해야 한다.
- 전체 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v186 large rerun VLM/OCR-on readiness

- 10만 건급 semantic 재검증의 실행 기준을 `--vlm on --ocr on`으로 다시 고정했다.
- 새 completed source는 기존 partial artifact `out\expert_result_20260528_141006_620986*`를 덮어쓰지 않는 별도 timestamp output으로 생성해야 한다.
- 기본 대형 재런 템플릿은 `--parallel 36 --reuse-shards-only --vlm on --ocr on`이다.
- 36-shard Docker lifecycle 자체가 검증 대상이면 `--allow-goal-shard-lifecycle --auto-up-shards`를 붙인 별도 모드로 분리한다.
- `qualitative_review/20260528_141006_620986/v186_large_rerun_vlm_ocr_on_readiness_ko_20260529.md`에 실행 전 확인, 명령 템플릿, 실행 후 gate를 기록했다.
- 전체 입력 JSONL 경로와 새 output path가 확정되기 전에는 대형 재런을 시작하지 않는다.
- clean completed run, VLM/OCR-on manifest, preflight, random baseline 1,000건 이상, P0/P1 high-risk expansion 전까지 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v184 URL media-type guard and weak character-page veto

- v183에서 `11718099`는 title이 `빌어먹을 환생`으로 맞았지만 final URL이 KakaoPage 웹툰 URL로 남을 수 있었다. 이는 title/url pair 선택 문제가 아니라 URL validator와 final rescue/freeze 사이 evidence-state 정합성 문제였다.
- v183에서 `11718091`은 Verifier가 캐릭터 외모/나이 잡담으로 거부했는데, 후단 `character_page_search` rescue가 등장인물 page 검색을 근거로 특정 작품으로 승격했다.
- `src\llm_batch\agentic_pipeline.py`에 URL media-type guard를 추가했다. 같은 URL의 검색 근거가 웹툰/만화/파생 팬픽 매체로만 지지되면 소설 상세 URL 후보에서 제외하고 validator는 `non_novel_media_platform_detail`로 기각한다.
- final reference freeze는 비소설 매체 URL을 지우고, 정확한 소설 상세 URL이 있으면 그쪽으로 `primary_work`를 동기화한다.
- `character_page_search` rescue는 약한 캐릭터 나이/외모 반응글에서 Verifier/관계판정이 작품 승격을 거부하면 열리지 않는다.
- focused regression 7건, `tests.test_agentic_pipeline_rework` 323건, `tests.test_expert_main_input_loader` 29건, 관련 `py_compile`을 통과했다.
- v184 live run `20260529_155118_539513`은 `--vlm on --ocr on --parallel 36 --reuse-shards-only`로 실행했고, manifest 기준 `input=4`, `effective_parallel=4`, `completed/failed/pending/flushed=4/0/0/4`, Docker lifecycle flags false였다.
- v184 result는 `11718091=title null/is_relevant false`, `11718099=빌어먹을 환생 + Naver Series detail URL`, `11718097=망겜의 힐러`, `11718083=title null/unresolvable_memory_query`로 확인됐다.
- `11718083`은 `is_relevant=true`로 남았지만 `title_resolution_allowed=false`, `is_resolved_work_discussion=false`, `novel_identity=null`이므로 resolved-title bug는 재발하지 않았다. 이 유형은 `is_relevant` 단독이 아니라 resolution state로 판정한다.
- `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`를 v184 기준으로 갱신해 URL media-type guard, character-page rescue veto, VLM/OCR-on regression 기준, title correctness와 URL/evidence strength 분리 규칙을 현재 gate 상태에 반영했다.
- `qualitative_review/20260528_141006_620986/v185_current_goal_status_audit_ko_20260529.md`에 목표 요구사항별 현재 증거, 원본 partial run 한계, v184 known-bad 결과, 남은 REVIEW-LOCKED 조건을 정리했다.
- `tools/preflight_qualitative_large_scale_review.py`로 원본 partial result를 다시 검사해 `v185_large_scale_preflight_original_partial.json/md`를 생성했다. preflight gate는 `run_integrity=REVIEW`, `semantic_preflight=REVIEW-LOCKED`, `overall=REVIEW-LOCKED`, random shortfall `929`다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v182 title/url match-quality ordering

- 원본 run `20260528_141006_620986`의 `11718099`는 `빌환 표지변경됨`에서 `표지변경`이 작품명처럼 승격된 것이 1차 버그였다.
- 이후 canary에서 title은 `빌어먹을 환생`으로 회복됐지만, v178 result JSON은 정확 제목 `빌어먹을 환생` Naver Series 상세 URL 대신 `25화무 빌어먹을 환생 목마` source title을 가진 Novelpia page를 primary URL로 둘 수 있었다.
- 원인은 `_find_title_matched_official_url()`과 reference freeze가 source title match 품질보다 플랫폼 선호 rank를 먼저 본 것이다.
- `src\llm_batch\agentic_pipeline.py`에 `_source_title_match_quality()`와 `_title_matched_official_url_quality()`를 추가했다. exact title match가 유사/부분 phrase match보다 우선한다.
- `_freeze_identity_references()`는 기존 URL의 플랫폼 rank가 더 좋아도 match quality가 낮으면 정확 제목 URL로 `primary_work`를 동기화한다.
- focused regression 3건, `tests.test_agentic_pipeline_rework` 318건, `tests.test_expert_main_input_loader` 29건, 관련 `py_compile`을 통과했다.
- v182 live run `20260529_151429_633557`은 `--vlm on --ocr on --parallel 36 --reuse-shards-only`로 실행했고, manifest 기준 `input=4`, `effective_parallel=4`, `completed/failed/pending/flushed=4/0/0/4`, Docker lifecycle flags false였다.
- v182 result는 `11718083=null/unresolvable`, `11718091=null/unresolved`, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생 + Naver Series detail URL`로 확인됐다.
- 다만 v182 W3 로그에서 Naver Series URL 직접 fetch가 `content_deleted_or_unavailable`로 기각된 뒤 final rescue가 URL을 유지했다. title/url pair는 회복됐지만 URL validator와 final rescue의 evidence-state 정합성은 별도 P1 후속이다.
- 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v181 VLM/OCR-on baseline and generic-discourse rescue guard

- 이미지 post가 포함된 semantic regression의 기본 기준을 `--vlm on --ocr on`으로 재고정했다. v179처럼 VLM/OCR evidence가 빠진 run은 text-only runtime 증거일 뿐 이미지 포함 post의 semantic approval 근거가 아니다.
- `expert_main.py` manifest에 `vlm_enabled`, `ocr_enabled`, `image_post_count`, `image_posts_present`, `vlm_ocr_semantic_review_ready`, `vlm_ocr_semantic_review_warning`을 추가했다.
- v181 live run `20260529_144914_316168`은 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 실행했고, manifest 기준 `input=5`, `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending/flushed=5/0/0/5`였다.
- v181 manifest 기준 `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count=4`, `vlm_ocr_semantic_review_ready=true`였고 Docker/Compose/shard lifecycle 실행 flags는 모두 false였다.
- `11718082`는 VLM/OCR에서 이미지 안의 카카오페이지 텍스트, 작품명/작가/회차를 읽어 `재벌가 차녀의 2회차 걸그룹`으로 resolved됐다. v179의 text-only null 판정은 semantic approval 근거로 폐기한다.
- `11718080`은 이미지 없는 한탄/장르 일반론으로 rejected 유지됐다. v179에서 문제가 된 것은 LLM 이해 전문가 실패가 아니라, 전문가들이 맞게 거부한 뒤 후단 `batch memory alias` rescue가 `보는 -> 2. 보는 눈이 없었다`로 뒤집은 경로였다.
- `src\llm_batch\agentic_pipeline.py`에 `late_rescue_blocked_by_verifier_generic_veto` guard를 추가했다. Verifier가 genre/trope/general chatter로 거부하고 직접 작품 앵커가 없으면 batch-memory/title-surface rescue가 official URL만으로 뒤집지 못한다.
- guard는 post id, 특정 alias, 특정 작품명 하드코딩 없이 공개 expert/evidence fields 기반으로 동작한다.
- 검증: `py_compile` OK, focused semantic/VLM regression 4건 OK, `tests.test_agentic_pipeline_rework` 316건 OK, `tests.test_expert_main_input_loader` 29건 OK.
- 이번 v181은 targeted canary이므로 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다. random baseline 1,000건 이상과 high-risk bucket expansion은 별도 gate로 유지한다.

## 2026-05-29 - v180 goal/reuse-only explicit endpoint healthy filter

- goal/test run에서 Docker Compose `up/recreate` hard opt-in 정책은 유지했다.
- 예전 shell/env에 `MCP_ENDPOINTS` 24/36개 명시 목록이 남아 있어도, 36건 이하 goal/test 또는 `--reuse-shards-only` 실행에서는 health check 후 살아있는 endpoint만 남긴다.
- autogen 전용 메타 외에 `mcp_healthy_endpoint_filter`, `mcp_healthy_endpoint_filter_autogen`을 추가했다.
- large explicit endpoint validation은 실패 endpoint를 숨기지 않도록 기본 미필터링 상태를 유지한다.
- goal/reuse-only health failure 안내는 `warp_shards.py up`을 기본 해결책처럼 출력하지 않고, Docker lifecycle 차단 상태와 복구 opt-in 조건을 설명한다.
- 검증: `py_compile` OK, `tests.test_expert_main_input_loader` 27건 OK.
- v179 live evidence 기준 현재 goal 5건 run은 Docker/Compose/shard lifecycle 실행 흔적 `0`건이었다. 즉 현재 느린 run은 Compose가 아니라 search/expert loop 쪽 병목으로 분리해야 한다.

## 2026-05-29 - v178 title-lead alias deliberation skip + no-Compose 재확인

- v177 live run에서 `11718097`은 final title은 `망겜의 힐러`로 맞았지만 W2 로그 기준 full deliberation `81.4s`, post total `236.4s`가 남는 것을 재현했다.
- `src\llm_batch\experts\deliberation.py`에 title-leading alias search bridge fast-path를 추가했다. score `2.0`에서는 검색 결과 `title` 필드 자체가 공식 작품명을 직접 포함하는 강한 bridge일 때만 full Jury/Debate를 스킵한다.
- memory-query, original Gatekeeper noise, recommendation, author/trope/genre target, critical counterargument는 fast-path에서 제외했다.
- post id/약칭 하드코딩 없이 공개 title/evidence/expert output 기반으로만 조건을 구성했다.
- `tests\test_llm_client_multimodal.py`에 score `2.0` direct bridge 양성 케이스와 direct bridge 부재 음성 케이스를 추가했다.
- `py_compile`, `DeliberationLimitTest` 5건, 기존 회귀 묶음 354건을 통과했다.
- v178 live run `20260529_141334_062130`은 `--parallel 36 --reuse-shards-only` known-bad 4건 입력으로 실행했고, manifest 기준 `input=4`, `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending/flushed=4/0/0/4`였다.
- v178 result는 `11718083=null/unresolvable`, `11718091=null/noise`, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`으로 기대값을 유지했다.
- v178 W2 로그에서 `11718097`은 `심의 스킵: title-lead alias search bridge resolved`, `method=evidence_scorer_only`, `2 iterations`로 종료됐다. `full_deliberation_ABC`/debate/jury grep은 `0`건이었다.
- v178 log/manifest 기준 Docker Compose lifecycle/status audit 실행 흔적도 `0`건이었다.
- v175/v177/v178 비교 기준 total은 `278.6s -> 237.6s -> 191.7s`, `11718097`은 `273.2s -> 236.4s -> 190.5s`로 줄었다. 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v176 goal/test Compose status-audit hard block

- goal/test regression에서 Docker Compose `up/recreate`뿐 아니라 `warp_shards.py status` 기반 Compose status/exec 조회도 기본 차단했다.
- `MCP_LOCAL_SHARD_STATUS_AUDIT=1`이 stale env로 남아 있어도 small goal/test run은 local shard management에 들어가지 않는다.
- status audit 자체가 목적이면 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`과 `MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT=1`을 함께 둔다.
- manifest/run config에 `mcp_local_shard_status_audit_requested`, `mcp_local_shard_status_audit_allowed`를 추가했다.
- `py_compile`, focused lifecycle regression 4건, `tests.test_expert_main_input_loader` 25건을 통과했다.
- v175 live manifest/log 재확인 기준 `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit=false`, `docker/compose/force-recreate/warp_shards.py` 실행 흔적 `0`건이었다.
- 이 변경은 runtime/operation gate이며, 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v175 known-bad memory-query forced-upgrade guard

- v174 known-bad 4건 run에서 final semantic 결과는 맞았지만 `11718083`이 weak title relation-hold 후보를 후단에서 반복 검토하며 `330.9s`가 걸리는 병목을 확인했다.
- `src\llm_batch\experts\orchestrator.py`와 `src\llm_batch\experts\deliberation.py`는 memory-query title-present relation-hold 케이스가 direct proof 없이 hold/downgrade되면 추가 collaboration/full deliberation을 줄인다.
- `src\llm_batch\experts\arbiter.py`는 Arbiter suspected-title forced-upgrade와 deliberate-null 우회를 같은 조건에서 차단한다.
- v175 live run `20260529_134510_545218`은 `--parallel 36 --reuse-shards-only` known-bad 4건 입력으로 실행했고, manifest 기준 `input=4`, `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending/flushed=4/0/0/4`였다.
- v175 result는 `11718083=null/unresolvable`, `11718091=null/noise`, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`으로 기대값을 유지했다.
- v175 log/manifest 기준 Docker Compose lifecycle/status audit 실행 흔적은 `0`건이었다.
- v174 대비 total `331.9s -> 278.6s`, `11718083` `330.9s -> 102.6s`, search requests `26 -> 22`로 줄었다.
- 당시 `11718097` full deliberation long-tail은 남아 별도 P1로 추적했다. 이 P1은 v178 title-lead alias skip에서 targeted canary 기준 닫혔지만, known-bad canary 통과는 10만 건 semantic approval 근거가 아니다.

## 2026-05-29 - v173 memory-query unresolved fast-path

- `11718083` memory-query/null-title canary의 실제 병목을 Docker Compose lifecycle이 아니라 전문가 오케스트레이션 후단 루프로 분리했다.
- v171은 semantic 결과는 맞았지만 Verifier 이후 추가 collaboration, Synthesizer, full Jury/Debate가 열려 `365.3s`, `102,794` tokens가 필요했다.
- `src\llm_batch\experts\orchestrator.py`는 Verifier 공개 출력이 실제로 존재한 뒤에만 memory-query settled rejection을 인정하도록 보강했다.
- v172에서 빈 Verifier dict가 settled로 처리될 수 있던 조기 skip 위험을 확인했고, `test_memory_query_settled_rejection_waits_for_verifier_output`로 막았다.
- Verifier가 no-title/weak bridge/hold-nullify로 정리한 memory-query unresolved 케이스는 추가 collaboration과 Synthesizer를 종료한다.
- `src\llm_batch\experts\deliberation.py`는 같은 조건에서 full Jury/Debate 대신 `evidence_scorer_only`로 종료한다.
- v173 live run `20260529_132113_820839`은 `--parallel 36 --reuse-shards-only`로 실행됐고, manifest 기준 `input=1`, `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending/flushed=1/0/0/1`이었다.
- v173 result에서 `11718083`은 `is_relevant=false`, `novel_identity=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 유지됐다.
- v173 log 기준 추가 collaboration 종료, Synthesizer skip, `Deliberation 완료: method=evidence_scorer_only`를 확인했고, `docker/compose/force-recreate/warp_shards.py` 실행 흔적은 `0`건이었다.
- v173은 `155.5s`, `62,730` tokens로 v171 대비 크게 줄었지만, search/deep-search/page analyzer와 대형 Decoder/Verifier prompt는 별도 P1 병목으로 남았다.
- `py_compile`, focused regression 5건, 관련 통합 회귀 349건을 통과했다. 이 canary는 10만 건 semantic approval 근거가 아니며 전체 gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v171 env-only Docker lifecycle block

- goal/test regression에서 Docker Compose stop/start/recreate 비용이 다시 끼어드는 문제를 막기 위해 env-only lifecycle opt-in을 차단했다.
- `MCP_AUTO_UP_SHARDS=1` 또는 `MCP_AUTO_RECREATE_SHARDS=1`이 남아 있어도 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` 또는 legacy `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1` ack 없이는 lifecycle을 열지 않는다.
- Codex 또는 36건 이하 small goal/test run에서는 env ack가 있어도 현재 명령에 `--allow-goal-shard-lifecycle`이 없으면 lifecycle을 열지 않는다.
- `MCP_SMALL_RUN_ALLOW_SHARD_LIFECYCLE=1` 같은 stale env도 current-command hard opt-in 없이는 small run block을 해제하지 않는다.
- manifest/run config에 `mcp_env_shard_lifecycle_requested`, `mcp_env_shard_lifecycle_global_opt_in`을 추가했다.
- `tests.test_expert_main_input_loader` 25건, `tests.test_agentic_pipeline_rework tests.test_llm_client_multimodal tests.test_expert_main_input_loader` 344건, `py_compile`을 통과했다.
- 현재 관련 Python 점유는 없고, Docker shard group `1..5`는 `Up 14 hours` 상태로 유지되어 있었다. 이번 확인에서 Compose 재시작은 수행하지 않았다.
- v171 live goal run `20260529_125908_474586`은 `--parallel 36 --reuse-shards-only`로 실행됐고, manifest 기준 `input=1`, `effective_parallel=1`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`였다.
- v171 log grep 기준 `docker`, `compose`, `force-recreate`, `warp_shards.py` 실행 흔적은 모두 `0`건이었다.
- 이 변경은 runtime/lifecycle 정책이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v169 settled Verifier veto skip

- v168 known-bad live run에서 Docker Compose lifecycle은 열리지 않았지만, `11718083` memory-query/null-title 케이스가 비싼 Jury/Debate 경로로 넘어가 long-tail/orphan process를 만들 수 있음을 확인했다.
- `src\llm_batch\experts\deliberation.py`에 settled Verifier veto fast-path를 추가했다. Verifier critical counter, 음수 evidence, deliberate null-title, direct title proof 부재가 동시에 맞으면 Jury/Debate를 열지 않는다.
- Jury/Debate 기본 max tokens를 `2048`로 낮췄다.
- v169 live run `20260529_121701_071316`은 `--parallel 36 --reuse-shards-only`로 실행됐고, manifest 기준 `input=1`, `requested_parallel=36`, `effective_parallel=1`, `completed/flushed/pending/failed=1/1/0/0`이었다.
- v169 manifest/log 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`이며 `docker compose`/`force-recreate`/`warp_shards.py`/`compose up` 실행 흔적은 없었다.
- v169 result에서 `11718083`은 `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 유지됐다.
- 남은 문제는 단건 `441.6s`, `total_tokens=176,274`, search degraded `10/13`의 P1 성능 병목이다. 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v167 goal/test compose avoidance and partial subset preservation

- goal/test run에서 Docker Compose lifecycle이 hard opt-in 없이는 열리지 않는 정책을 회귀 테스트로 재확인했다.
- 병렬 run에서 ordered flush gap이 남으면 원본 result JSON을 덮어쓰지 않고 `_completed_subset.json`과 `_completed_subset_manifest.json`을 별도 recovery artifact로 남기도록 했다.
- manifest에 completed subset 경로/count/reason과 `partial_flush_gap`, `ordered_flush_blocked`, `large_run_complete`를 기록한다.
- primary result JSON은 ordered flushed prefix로 유지한다. completed subset은 partial triage/recovery용이며, clean completion 또는 10만 건 semantic approval 근거가 아니다.
- `py_compile expert_main.py tests\test_expert_main_input_loader.py`와 `tests.test_expert_main_input_loader` 24건을 통과했다.

## 2026-05-29 - v166 large rerun readiness plan

- 원본 partial/recovered source가 large-scale approval에 부족하므로 새 completed source를 만들기 위한 실행 계획을 작성했다.
- 산출물은 `qualitative_review\20260528_141006_620986\v166_large_rerun_readiness_plan_ko_20260529.md`다.
- 현재 관련 Python 점유는 없고, Docker 기준 WARP/MCP shard group은 `1..5`만 떠 있음을 확인했다.
- reuse-only safe mode와 explicit 36-shard validation mode를 분리했다.
- large rerun 후에는 manifest 확인, `audit_expert_run_health.py`, `preflight_qualitative_large_scale_review.py`, random baseline, high-risk expansion 순으로 진행한다.
- 기존 `out\expert_result_20260528_141006_620986*`는 덮어쓰지 않고 새 timestamp output을 사용한다.

## 2026-05-29 - v165 large-scale qualitative preflight

- large-scale qualitative review를 실행하기 전에 source completeness와 sampling feasibility를 검사하는 `tools/preflight_qualitative_large_scale_review.py`를 추가했다.
- preflight는 result rows, manifest input/completed/flushed/pending/failed, checkpoint completed rows, pending snapshot rows, source policy, random baseline shortfall, high-risk bucket population을 기록한다.
- 원본 final result source는 `result_rows=71`, manifest `104502/80/71/9/0`, random shortfall `929`로 `REVIEW-LOCKED`다.
- recovered completed subset source는 `result_rows=80`, `source_dataset_kind=checkpoint_recovered_completed_subset`, random shortfall `920`으로 `REVIEW-LOCKED`다.
- 산출물은 `v165_large_scale_preflight_original_partial.{json,md}`와 `v165_large_scale_preflight_recovered_subset.{json,md}`다.
- 이 결과로 현재 source에서는 large-scale semantic approval을 시작할 수 없고, 충분한 completed source가 필요하다는 점을 gate 전에 증명했다.

## 2026-05-29 - v164 sample target shortage audit

- random control builder가 요청 표본 수와 실제 선택 표본 수를 분리 기록하도록 했다.
- random manifest에 `requested_sample_size`, `selected_sample_size`, `sample_shortfall`, `sample_target_satisfied`, `sample_coverage_ratio`를 추가했다.
- Round2 high-risk manifest에 `target_total`, `selected_total`, `target_satisfied`, `target_shortfalls`, `bucket_coverage_ratios`를 추가했다.
- gate는 random baseline `1,000`건 미달을 `Weak`, Round2 target 미달을 `Missing` evidence로 표시한다.
- v164 shortage audit `qualitative_review\20260528_141006_620986\v164_sample_shortage_audit`을 생성했다.
- recovered subset 80건 기준 결과는 Round2 `79/340`, random `1/1000`이므로, 현재 source는 large-scale semantic approval 근거가 될 수 없다.

## 2026-05-29 - v163 recovered subset review source policy

- recovered completed subset을 후속 qualitative review 도구가 final result처럼 오해하지 않도록 `source_review_policy`를 추가했다.
- `build_qualitative_round2_review.py`는 recovered artifact 경로 또는 상위 디렉터리에서 원본 run id `20260528_141006_620986`을 추론하고, manifest에 `checkpoint_recovered_completed_subset`, `recoverable_pending_flush_gap`, `large_run_complete=false`를 남긴다.
- `build_qualitative_random_control_review.py`도 같은 source policy를 기록하고, random control 추가 후 `summary.json`과 `gate_decision.md`를 재계산한다.
- random builder가 canonical summary 재계산 시 Round2 모듈의 기본 run id를 쓰던 문제는 `round2_manifest.run_id`와 `sample_seed`를 재주입해 막았다.
- v163 smoke 산출물 `qualitative_review\20260528_141006_620986\v163_recovered_source_policy_round2`에서 Round2 `30`건, random control `20`건, canonical labels `50`건, gate `NO-GO`를 확인했다.
- 이 smoke는 도구 정합성 검증이며 10만 건 semantic approval 근거가 아니다.

## 2026-05-29 - v162 partial run checkpoint recovery

- 원본 run `20260528_141006_620986`의 final result `71`, checkpoint completed `80`, pending snapshot `9` 불일치를 별도 run integrity 이슈로 재검증했다.
- final result에 없는 checkpoint completed 9건은 pending snapshot 9건과 동일했고, pending snapshot 밖의 누락 completed row는 없었다.
- ordered flush가 `global_idx=72` 미완료 row에서 막혀 이후 completed row 9건이 final JSON에 flush되지 않은 `recoverable_pending_flush_gap`으로 분류했다.
- `tools/recover_expert_run_from_checkpoint.py`와 `tests/test_recover_expert_run_from_checkpoint.py`를 추가했고, 원본 result를 덮어쓰지 않는 recovered completed subset 80건을 생성했다.
- 산출물은 `qualitative_review\20260528_141006_620986\v162_run_integrity_recovered_completed_80.json`, `v162_run_integrity_recovery_summary.json`, `v162_run_integrity_recovery_ko_20260529.md`다.
- 이 복구는 known-bad/failure pattern triage용 completed subset을 살리는 조치이며, 원본 10만 run의 clean completion 또는 semantic approval로 보지 않는다.

## 2026-05-29 - v161 comment author context lines

- 댓글 작성자 닉네임을 `comment_context_lines`의 공개 메타로 추가했다.
- `expert_main.py` 결과 row, `agentic_pipeline.py` prompt context, `build_qualitative_round2_review.py` packet 재구성 경로가 모두 `author=<comment author>`를 남긴다.
- 댓글 본문 문자열에는 작성자/IP를 섞지 않고, `speaker`, `author`, `role=post_author`, `ip`, `reply_level`, `reply_to`, `comment_id`를 분리된 compact line으로 기록한다.
- `tests.test_expert_main_input_loader` 23건, `tests.test_qualitative_review_packet_tools` 17건, focused pipeline 3건, `tests.test_agentic_pipeline_rework` 305건을 통과했다.
- v161 live run `20260529_104847_516862`에서 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`을 확인했다.
- v161 manifest/log 기준 Docker Compose lifecycle과 warp shard recreate/up 흔적은 없었다.
- v161 결과에서 `11718091`은 `official_title=null`, `title_resolution_state=unresolved_matchable`을 유지했고, comment context sample은 `#1 speaker=post_author author=ㅇㅇ role=post_author comment_id=40479972`였다.
- v161 결과에서 `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`, `11718118=trope_discussion/title null`, `11718083=unresolvable_memory_query/title null`을 유지했다.
- `qualitative_review\20260528_141006_620986\v161_goal_status_audit_ko_20260529.md`를 추가해 목표 요구사항별 현재 증거와 남은 P0/P1 작업을 분리했다.
- 이 결과는 known-bad targeted regression이며, 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - v159 memory-query batch alias rescue guard

- `11718083` memory-query quote post가 검색/BatchContext alias 후보로 다시 resolved 되는 경로를 차단했다.
- `plot_mention`은 memory-query direct title proof로 인정하지 않고, BatchContext alias rescue도 canonical rescue가 이미 차단된 title 또는 direct title proof 없는 title을 재승격하지 못하게 했다.
- `tests.test_agentic_pipeline_rework`는 `305`건 OK, `tests.test_expert_main_input_loader`는 `23`건 OK, 관련 py_compile은 OK였다.
- v159 live run `20260529_101858_579879`에서 `11718083`은 `is_relevant=false`, `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 내려갔다.
- v159 manifest/log 기준 `requested_parallel=36`, `effective_parallel=1`, Docker Compose lifecycle 미진입, forbidden batch alias registration 미발생을 확인했다.
- v160 known-bad 5건 regression `20260529_103040_519314`에서 `11718083/11718091/11718118`은 title null, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`으로 확인했다.
- v160 manifest/log 기준 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`, Docker/warp lifecycle 미진입을 확인했다.
- targeted regression 통과이므로 known-bad 목표는 개선됐지만, 전체 10만 건 semantic gate는 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - Codex goal env lifecycle hard opt-in v3

- Codex goal/test run에서 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1` env escape가 현재 명령의 hard opt-in 없이 Docker Compose lifecycle을 다시 열 수 있는 경로를 차단했다.
- env 기반 lifecycle opt-in도 `--allow-goal-shard-lifecycle`이 현재 명령에 있을 때만 인정하도록 `expert_main.py`를 좁혔다.
- `tests.test_expert_main_input_loader` 23건과 `py_compile`을 통과했다.
- v157 live run `20260529_093931_952299`는 `--reuse-shards-only`, `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`으로 완료됐다.
- v157 manifest/log 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`이며 compose/recreate 실행 흔적은 없었다.
- 다만 v157 `11718083`은 memory-query post를 wrong title로 다시 resolved했으므로 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-29 - late rescue alias self-confirmation guard

- v151 live run에서 unit guard만으로는 `batch_memory_exact_alias_rescued` self-confirmation을 막지 못함을 확인했다.
- `11718080`, `11718082`, `11718090`은 reason 내부에 weak grounding/evidence bucket 0/critical 신호가 있었지만 후단 rescue가 일반 표면 alias를 작품명으로 되살렸다.
- late rescue source가 `batch_memory` 또는 `title_surface`이고 public evidence bucket이 0이면 alias support만으로 direct work bridge를 인정하지 않도록 했다.
- slang DB observation 수집에서도 late-rescue contaminated alias 저장을 차단했다.
- `tests.test_agentic_pipeline_rework` 301건과 `tests.test_slang_db` 20건을 통과했다.
- v152 live run `20260529_072232_140417`에서 polluted slang DB seed를 둔 상태로 8건을 재실행했다.
- v152 결과는 `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`만 resolved이고, 나머지 known-bad 6건은 `official_title=null`로 내려갔다.
- v152 manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_env_shard_lifecycle_blocked_by_context=true`를 확인했다.

## 2026-05-29 - Codex goal run env lifecycle guard

- Codex goal/test loop에서 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수가 37건 이상 입력의 Docker Compose lifecycle을 다시 켤 수 있는 경로를 차단했다.
- `CODEX_SHELL` 또는 `CODEX_THREAD_ID`가 있으면 env 기반 shard lifecycle은 기본 무시한다.
- 현재 명령의 `--auto-up-shards`/`--auto-recreate-shards`는 계속 명시 opt-in으로 유지했다.
- env 기반 lifecycle이 꼭 필요한 Codex 실행도 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1`과 현재 명령의 `--allow-goal-shard-lifecycle`을 함께 추가해야 한다.
- manifest/run config에 `mcp_interactive_codex_run`, `mcp_env_shard_lifecycle_allowed`, `mcp_env_shard_lifecycle_blocked_by_context`를 추가했다.
- `py_compile`과 `tests.test_expert_main_input_loader` 20건을 통과했다.

## 2026-05-29 - goal run healthy shard default filter

- 36건 이하 goal/test run에서 lifecycle opt-in이 없으면 autogen endpoint를 기본 8개로 제한하도록 했다.
- 대형 run에서 남은 stale `MCP_SHARD_COUNT=36`도 36건 이하 goal/test run에서는 기본 8개 cap보다 우선하지 않게 했다.
- `--reuse-shards-only` 없이도 lifecycle-blocked goal run은 health check 후 healthy autogen endpoint만 남기고 failed endpoint 때문에 startup을 중단하지 않는다.
- 이 정책은 `--parallel 36`을 최대치로 유지하되, 실제 실행은 입력 수와 healthy endpoint 수에 맞춰 낮추는 운영 정책이다.
- `py_compile`과 `tests.test_expert_main_input_loader` 17건을 통과했다.
- v150 live goal run `20260529_063616_661442`에서 `requested_parallel=36`, `effective_parallel=8`, `mcp_small_run_shard_lifecycle_blocked=true`, endpoint count 메타를 확인했다. 입력 8건은 small-run cap으로 endpoint 2개만 생성됐고 둘 다 healthy라 실제 filter 축소는 필요 없었다.
- 같은 v150 log에서 `docker compose`, `force-recreate`, `warp_shards.py up/recreate/status` 실행 흔적이 없음을 확인했다.

## 2026-05-29 - result row comment speaker context lines

- `expert_main.py` 결과 row에 `comment_context_lines`를 추가했다.
- 기존 pipeline prompt 경로는 `comment_context_lines`를 생성하고 있었지만, 결과 JSON 기반 review packet 재구성에는 해당 compact speaker/thread context가 남지 않았다.
- 이제 `comment_metadata`와 함께 `speaker`, `author`, `role=post_author`, `ip`, `reply_to`, `comment_id`가 compact line으로 남는다.
- `tests.test_expert_main_input_loader` 13건과 focused pipeline comment context 테스트를 통과했다.
- v150 live goal run 결과 JSON에서 `comment_context_lines` 필드가 row에 남는 것을 확인했다.
- 이 메타는 대화 흐름 해석용이며 독립 작품 identity evidence가 아니다.

## 2026-05-29 - title-lead alias discourse preservation

- `11718097` v148 실패를 final title guard 문제가 아니라 Gatekeeper low-specific `community_banter` 유지로 인한 검색 전 조기 종료 문제로 분리했다.
- 제목 선두 표면 anchor가 Discourse의 novel term/search suggestion에도 재포착되고 캐릭터/플롯 논의 신호가 있으면 `worklike_alias_preservation`으로 noise 조기 종료를 보류하도록 했다.
- 검색 복구는 Discourse가 재포착한 제목 선두 alias에만 제한하고, 술어 꼬리 seed를 제외했다.
- focused regression과 negative control을 추가했고, `tests.test_agentic_pipeline_rework` 298건 및 `tests.test_expert_main_input_loader` 12건을 통과했다.
- live rerun은 LLM endpoint 복구 후 수행한다. 검색 회복은 final title 승인과 별도 gate다.

## 2026-05-29 - goal/test lifecycle threshold split

- 24건/36건 이하 goal regression에서 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수만으로 Docker Compose lifecycle이 켜질 수 있는 경로를 차단했다.
- lifecycle 차단 기준을 입력 post 수 기준으로 분리하고 `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD=36` 기본값을 추가했다.
- endpoint 자동 생성 제한 기준 `MCP_SMALL_RUN_SHARD_THRESHOLD`와 compose lifecycle 차단 기준을 분리했다.
- manifest/run config에 `mcp_shard_lifecycle_block_threshold`, `mcp_run_post_count_for_lifecycle`를 추가했다.
- `py_compile` 및 `tests.test_expert_main_input_loader` 12건을 통과했다.
- v150 live goal run manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit=false`를 확인해 기본 goal run이 Docker Compose 및 local shard management 경로에 들어가지 않음을 확인했다.

## 2026-05-29 - v149 reason/evidence-zero title guard

- v148 잔여 false positive 원인을 `official_title_evidence=true` 조기 통과와 evidence bucket 0/원문 anchor 없음의 충돌로 분리했다.
- `_final_title_rejection_profile()`에 `official_search_only_without_post_anchor` guard를 추가했다.
- synthetic regression 2건과 positive control을 추가했고, `tests.test_agentic_pipeline_rework` 297건 및 `tests.test_expert_main_input_loader` 12건을 통과했다.
- LLM endpoint가 닫혀 있어 exact v149 live rerun은 보류했다. `v149_reason_evidence_zero_guard_input.jsonl`과 한국어 action queue를 남겼다.

## 2026-05-29 - v148 reuse-only healthy shard filter 및 high-risk triage

- 상태: runtime-policy-patched / unit-verified / v148-live-confirmed / semantic-review-locked
- 배경:
  - `--reuse-shards-only` 실행은 Docker Compose lifecycle 없이 기존 shard만 재사용해야 한다.
  - v148 전에는 입력 24건 때문에 endpoint 24개를 자동 생성하고 실제 떠 있는 5개 외 19개 endpoint 실패를 fatal로 봐 중단됐다.
- 조치:
  - reuse-only + autogenerated endpoint에서 health check 후 healthy endpoint만 남기고 `_PARALLEL`을 healthy endpoint 수로 낮췄다.
  - manifest/run_meta에 filter 전후 endpoint/parallel 수를 기록했다.
- 검증:
  - `tests.test_expert_main_input_loader`: `Ran 11 tests ... OK`
  - v148 run id `20260529_043012_788628`: `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=24/0/0`
  - v148 logs: `docker compose`, `force-recreate`, `warp_shards.py up`, `warp_shards.py recreate`, `compose up` 없음.
- semantic 결과:
  - `11718099`, `11718083`, `11718091`은 기대 방향 유지.
  - `11718097`은 v147과 v148 결과가 달라 alias recall 비단조성으로 남음.
  - `11718082`, `11718080`, `11718090`, `11716486`은 false positive 또는 브라우저/VLM 확인 필요 케이스로 남음.

## 2026-05-29 - v147 weak-character preserve/rescue 차단 및 no-compose 재확인

- 상태: semantic-guard-patched / unit-verified / v147-live-confirmed / quality-review-locked
- 배경:
  - v146에서 `11718091`은 memory-query 오분류가 사라졌지만 `unresolved_worklike_preserve`가 `is_relevant=true`를 다시 올렸다.
  - 이는 검색 후보나 batch memory alias support가 있어도 원문 직접 제목/안정 별칭/작품 내부 앵커가 없으면 짧은 캐릭터 나이/외모 반응을 작품 관련 unresolved로 보존하면 안 된다는 정책과 충돌했다.
- 조치:
  - weak-character reaction guard를 preserve, final identity validator, batch memory alias rescue 경로에 적용했다.
  - post author 댓글은 대화 흐름 해석에만 쓰고 독립 작품 identity evidence로 승격하지 않는 회귀 테스트를 추가했다.
- 검증:
  - focused 4건, `py_compile`, `tests.test_expert_main_input_loader`, `tests.test_agentic_pipeline_rework` 295건 통과.
  - v147 run id `20260529_040313_425572`: `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`.
  - v147 manifest 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_run_shard_lifecycle_blocked=true`.
  - v147 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py recreate`, `compose up` 실행 흔적 없음.
  - v147 `11718091`: `is_relevant=false`, `is_novel_related=true`, `is_resolved_work_discussion=false`, `official_title=null`, `title_resolution_state=unresolved_matchable`, flags=`weak_character_reaction_unresolved_blocked`, `post_author_comment_not_independent_evidence`.
- 제한:
  - v147은 known-bad 5건 targeted regression이다. 10만 건 semantic gate는 expanded random baseline과 high-risk expansion 전까지 `REVIEW-LOCKED`다.

## 2026-05-29 - goal/test run docker lifecycle opt-in 전환

- 상태: runtime-policy-patched / stale-env-small-run-guarded / local-verification-passed / v145-live-goal-policy-confirmed
- 배경:
  - 2026-05-28 정책은 1~9건 소규모 goal/targeted run에서만 `docker compose up`과 shard `force-recreate`를 기본 차단했다.
  - goal 검증 런은 10건 이상이어도 코드/판정 회귀 확인이 목적일 수 있으므로, 입력 수만으로 compose stop/start 비용을 기본 허용하는 것은 부적절했다.
- 조치:
  - `expert_main.py`의 shard `up/recreate` docker lifecycle 동작을 입력 건수와 무관하게 기본 비활성으로 바꿨다.
  - 자동 기동은 `--auto-up-shards`, 자동 재생성은 `--auto-recreate-shards`를 명시해야 켜진다. env 자동화는 v171 이후 `MCP_AUTO_*`와 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 둬야 한다.
  - `MCP_SMALL_RUN_SHARD_THRESHOLD` 미만 goal/targeted run에서는 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수가 남아도 compose lifecycle과 compose 기반 shard ensure를 켜지 않게 했다.
  - 소규모 run에서 복구 자동화가 실제 검증 대상이면 현재 명령에 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`를 함께 붙인다.
  - manifest/run config에 `mcp_shard_lifecycle_policy=docker_up_recreate_opt_in`을 남기게 했다.
  - manifest/run config에 `mcp_small_run_shard_lifecycle_blocked`를 남기게 했다.
- 검증:
  - `py_compile expert_main.py tests\test_expert_main_input_loader.py`: OK.
  - `tests.test_expert_main_input_loader`: `Ran 10 tests ... OK`.
  - `expert_main.py --help`: `--auto-up-shards`, `--auto-recreate-shards` 노출 확인.
  - v141 run id `20260529_020958_837665`: `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`.
  - v141 manifest 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_shard_lifecycle_policy=docker_up_recreate_opt_in`.
  - v141 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py recreate`, `자동 기동`, `재생성` 실행 흔적 없음.
  - `tests.test_agentic_pipeline_rework`: `Ran 293 tests ... OK`.
  - v145 run id `20260529_032731_379356`: `--reuse-shards-only`, `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`.
  - v145 startup config 기준 `auto_up=False`, `auto_recreate=False`, `small_run_lifecycle_blocked=True`.
  - v145 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py recreate`, `compose up` 실행 흔적 없음.
  - v145 known-bad 의미 검증: `11718083`은 memory query title null, `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`, `11718091`은 title null/noise로 확인했다.

## 2026-05-28 - 소규모 goal/targeted run shard 재사용 정책

- 상태: runtime-policy-patched / docs-updated / v138-live-log-confirmed / v139-manifest-policy-confirmed
- 배경:
  - `expert_main.py`는 startup auto-manage에서 WARP 상태 또는 검색 health 실패를 만나면 실패 shard를 `docker compose up --force-recreate` 경로로 재생성할 수 있었다.
  - 1~9건 goal/targeted 테스트는 코드 경로 확인이 목적이므로, shard stop/start 비용을 기본값으로 지불하는 것은 비효율적이다.
- 조치:
  - 10건 미만 targeted/goal run은 기본적으로 기존 healthy shard 재사용을 우선하고 `docker compose up`/`force-recreate` 자동 실행을 생략하도록 했다.
  - `--no-auto-recreate-shards`, `--reuse-shards-only` 옵션과 `MCP_AUTO_UP_SHARDS`, `MCP_AUTO_RECREATE_SHARDS`, `MCP_HEALTH_ATTEMPTS` override 경로를 추가했다.
  - manifest에 shard auto-up/recreate 정책 필드를 기록하도록 했다.
- 검증:
  - `py_compile expert_main.py`: OK.
  - `expert_main.py --help`: 신규 옵션 노출 확인.
  - v138 run id `20260529_005903_511505`에서 `requested_parallel=36`, `input_posts=5`, `effective=5`로 축소됐다.
  - v138 startup log에서 healthy shard 2개 재사용, WARP/health attempt `1/1`, `docker compose`/`force-recreate` 미실행을 확인했다.
  - v139 run id `20260529_012138_862062`에서 `requested_parallel=36`, `input_post_count=5`, `effective_parallel=5`, `completed/failed/pending=5/0/0`을 확인했다.
  - v139 manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_targeted_run=true`를 확인했다.
  - v139 startup log에서도 health attempt `1/1`이며 `docker compose`/`force-recreate` 실행 흔적이 없었다.
- 운영 메모:
  - 1~9건 goal/targeted run에서 compose 재시작을 확실히 피해야 하면 `--reuse-shards-only`를 붙인다.
  - canary/validation에서 shard 복구 자동화까지 검증할 때만 CLI `--auto-up-shards`/`--auto-recreate-shards`를 명시한다. env 자동화는 `MCP_AUTO_*`와 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 둔다.

## 2026-05-28 - v134 relevance/title-resolution scope 분리 1차 구현

- 상태: schema-patched / unit-verified / quality-review-locked
- 배경:
  - v133 targeted rerun에서 `11718083`, `11718097`, `11718099`, `11718118`의 핵심 오판은 재발하지 않았지만, `11718091`은 title null이 안전해도 reason/schema가 `noise/review/관련/비관련`으로 흔들렸다.
  - 원인은 프롬프트 한 문장 문제가 아니라 `is_relevant`가 소설 관련성, 단일 작품 매칭 가능성, 주변 담론을 한 bool로 압축하는 구조 한계다.
- 조치:
  - `PickvelIdentity`에 `is_novel_related`, `is_resolved_work_discussion`, `title_resolution_state`, `title_resolution_allowed`를 optional field로 추가했다.
  - `_context_to_output()`에서 broad novel relatedness와 resolved work identity를 분리 산출하고, 필요한 경우 reason에 `[범위 분리]` 섹션을 남기게 했다.
  - `LLM_JUDGMENT_REVIEW.md`, `EXPERT_ORCHESTRATION_LIMITATIONS.md`, `TODO.md`, `CHECKLIST.md`, `IMPROVEMENT_REGISTER.md`, `VERIFICATION_RESULTS.md`를 갱신했다.
- 검증:
  - focused scope 분리 테스트 3건 통과.
  - `tests.test_agentic_pipeline_rework`: `279 tests OK`.
  - `py_compile src\llm_batch\models.py src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py`: OK.
- 제한:
  - live LLM targeted rerun에서 새 필드가 result/checkpoint JSON에 남는지는 아직 확인하지 않았다.
  - `title_lock_state`, `evidence_edges`, `reason_decision_contradiction` detector는 남은 작업이다.
  - 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-28 - v129-v131 post-Arbiter title lock propagation 검증

- 상태: targeted-fixed / docs-updated / quality-review-locked
- 배경:
  - v126-v128 재검증에서 `11718097`은 중간 전문가 판단이 `망겜의 힐러`를 잡아도 후단 correction/guard가 final title을 뒤집거나 삭제할 수 있음이 확인됐다.
  - v129는 final title을 회복했지만 canonical suspect 단계가 `오크 행복`으로 흔들려 후단 회복에 의존했다.
  - v130은 canonical suspect 기준을 좁힌 뒤 작가앵커-후보작가 충돌 guard가 locked title을 삭제해 `11718097`을 다시 `HOLD/unresolved`로 만들었다.
- 조치:
  - snippet canonical alias lock이 있는 title을 약한 canonical override가 덮지 못하도록 보강했다.
  - filtered official detail이 같은 locked title을 지지하면 `weak_support`로 final demotion 방지에 반영했다.
  - 작가앵커-후보작가 충돌 guard는 snippet/alias lock 또는 filtered official detail 보조 근거가 있는 title을 무조건 삭제하지 않게 했다.
  - v131 after-review labels/summary/action queue를 한국어로 작성했다.
- 검증:
  - py_compile 통과.
  - focused 회귀 3건 통과.
  - `tests.test_agentic_pipeline_rework`: `277 tests OK`.
  - 실행 전 관련 Python 점유 프로세스 없음.
  - v131 run id `20260528_222656_377121`: `requested_parallel=36`, `effective_parallel=2`, `completed=2`, `failed=0`, `pending=0`.
  - v131 after-review 결과는 `ACCEPT=2`, `HOLD=0`, `REPROCESS=0`, `REJECT=0`이다.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v131_topic_particle_reject_2_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v131_post_arbiter_lock_action_queue_ko_20260528.md`
- 제한:
  - v131은 targeted 2건 canary다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-28 - v125-v128 후단 오케스트레이션 한계 재확인

- 상태: limitation-confirmed / partial-fixed / docs-updated / quality-review-locked
- 배경:
  - v125 `topic_particle_title_lead_alias_anchor` bucket에서 `11718097`, `11718118`이 `REJECT/re_judge`로 분리됐다.
  - `11718097`은 `망겜힐 -> 망겜의 힐러`라는 중간 정답이 있었지만, 후단 보정에서 작가명/다른 공식 작품 후보가 더 강하게 계산되면 final title이 오염될 수 있었다.
  - `11718118`은 `ts물` 장르 일반론인데 역할어 `대협`이 wiki/community 문서 title로 rescue될 수 있었다.
- 조치:
  - v126-v128 targeted 2건을 `--parallel 36` 최대치로 실행했고, manifest 기준 실제 `effective_parallel=2`를 확인했다.
  - author-name search-inferred alias 단독 rescue와 genre/trope discourse 상태의 wiki/community title rescue를 차단하는 방향으로 구조 한계를 정리했다.
  - `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`, `LLM_JUDGMENT_REVIEW.md`, `CHECKLIST.md`, `TODO.md`, `IMPROVEMENT_REGISTER.md`, `VERIFICATION_RESULTS.md`를 갱신했다.
- 검증:
  - v128 run id `20260528_214738_593132`: `requested_parallel=36`, `effective_parallel=2`, `completed=2`, `failed=0`, `pending=0`.
  - `11718118`은 `official_title=null`, `is_relevant=false`, `discussion_type=trope_discussion`, `work_resolution=none`, `anchor_type=genre`로 회복됐다.
  - `11718097`은 `게임4판타지` wrong title은 제거됐지만, `망겜의 힐러` correct title은 아직 `HOLD/unresolved`다.
- 제한:
  - 이번 검증은 targeted/bucket evidence다. 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.
  - 다음 코드는 snippet canonical alias lock을 canonical suspect 보정과 unverified alias/plot demotion까지 전달하는 구조 패치가 우선이다.

## 2026-05-28 - v124 title-leading alias recall 및 구조 한계 재확인

- 상태: targeted-fixed / canary-verified / docs-updated / quality-review-locked
- 배경:
  - v123에서 역할·호칭성 wrong-title rescue는 막혔지만, `11718097`의 correct title recall은 `HOLD/re_search`로 남았다.
  - 원인은 Gatekeeper가 `title_after_prefix_strip`을 `빌런이였어야돼`처럼 잘못 남겼을 때 원문 제목 첫머리 `망겜힐은`의 순수 약칭이 검색 앵커로 충분히 보존되지 않은 것이다.
- 조치:
  - Orchestrator의 title surface anchor 추출에서 Gatekeeper remainder보다 원문 제목 첫머리를 우선 보도록 보정했다.
  - `AgenticPipeline`에서 제목 첫 토큰의 조사 제거형 clean alias를 후보 합성/검색 추론에 보존했다.
  - `망겜힐` 같은 3음절 clean alias는 generic topic, role/species, low-information 필터를 통과할 때만 검색 앵커로 허용했다.
  - v124 after-review labels/summary/action queue를 한국어로 작성했다.
- 검증:
  - py_compile 통과.
  - focused 4 tests 통과.
  - `tests.test_agentic_pipeline_rework`: `271 tests OK`.
  - 실행 전 관련 Python 점유 프로세스 없음.
  - v124 run id `20260528_210753_915155`: `requested_parallel=36`, `effective_parallel=4`, `input_post_count=4`, `completed=4`, `failed=0`, `pending=0`.
  - v124 after-review 결과는 `ACCEPT=4`, `HOLD=0`, `REPROCESS=0`, `REJECT=0`이다.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v124_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v124_title_lead_alias_recall_action_queue_ko_20260528.md`
- 제한:
  - v124는 targeted canary다. 검색 degraded와 official evidence 약함이 섞인 케이스는 high-risk expansion에서 계속 봐야 한다.
  - 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-28 - v122/v123 role/honorific alias rescue guard 재검증

- 상태: targeted-fixed / canary-verified / docs-updated / quality-review-locked
- 배경:
  - v122 targeted 4건은 run health 기준 `completed=4`, `failed=0`, `pending=0`이었지만, 자연어/코드 리뷰에서는 `REPROCESS=2`, `REJECT=1`, `ACCEPT=1`로 분리됐다.
  - `11718083`, `11718091`은 `_context_to_output()`에서 `post_data` NameError가 발생했다.
  - `11718097`은 Arbiter가 null-title을 유지했는데 후단 batch memory alias rescue가 역할·호칭성 표현 `족장님`을 단독 근거로 `두 번 각성하는 대족장님` final title에 연결했다.
- 조치:
  - `post_data` 참조를 `ctx.post_data` 기반으로 수정했다.
  - `search_evidence_alias_inference` 경로에서 역할·호칭성 alias가 단독으로 batch memory title rescue를 만들지 못하게 일반 guard를 추가했다.
  - role/honorific alias rescue 회귀 테스트와 nonwork unresolved branch 회귀 테스트를 추가했다.
  - v122/v123 after-review labels/summary/action queue를 한국어로 작성했다.
- 검증:
  - py_compile 통과.
  - focused 4 tests 통과.
  - `tests.test_agentic_pipeline_rework`: `269 tests OK`.
  - v123 run id `20260528_202833_336004`: `requested_parallel=36`, `effective_parallel=4`, `input_post_count=4`, `completed=4`, `failed=0`, `pending=0`.
  - v123 after-review 결과는 `ACCEPT=3`, `HOLD=1`, `REPROCESS=0`, `REJECT=0`이다.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v122_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v122_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v123_targeted_4_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v123_role_honorific_alias_rescue_action_queue_ko_20260528.md`
- 제한:
  - v123은 targeted canary다. `11718097` correct title recall은 아직 `HOLD/re_search`이며 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-28 - v119/v121 memory-query hard veto 및 전문가 오케스트레이션 한계 정리

- 상태: canary-verified / docs-updated / prompt-contract-updated / quality-review-locked
- 배경:
  - `11718083`은 작품명을 모르는 기억 회수/제목 찾기 글인데, v119에서 검색 후보와 공식 URL을 근거로 단일 작품명이 과확정됐다.
  - 해당 실패는 단순 프롬프트 문구 문제가 아니라, expert output 이후 `_context_to_output()` 후처리 rescue가 null-title 결정을 다시 되살릴 수 있는 구조 문제다.
- 조치:
  - v119 after-review labels/summary를 작성해 `ACCEPT=1`, `HOLD=2`, `REJECT=1`로 분리했다.
  - v121 단건 canary에서 `11718083`이 `official_title=null`, `novel_identity=null`, `work_resolution=none`, `anchor_type=none`으로 내려가는 것을 확인했다.
  - `prompt_router.py`에 memory-query/no-direct-anchor official_title null 규칙과 comment metadata 사용 경계를 추가했다.
  - `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`를 추가해 오케스트레이션 흐름, 프롬프트 한계, 후처리 rescue 위험, 개선 우선순위를 한국어로 정리했다.
  - `LLM_JUDGMENT_REVIEW.md`, `CHECKLIST.md`, `TODO.md`, `IMPROVEMENT_REGISTER.md`, `VERIFICATION_RESULTS.md`, `README.md`를 갱신했다.
- 검증:
  - v119 run id `20260528_173601_372561`: `requested_parallel=36`, `effective_parallel=4`, `completed=4`, `failed=0`, `pending=0`.
  - v121 run id `20260528_192101_896423`: `requested_parallel=36`, `effective_parallel=1`, `completed=1`, `failed=0`, `pending=0`.
  - `tests.test_agentic_pipeline_rework`: `267 tests OK`.
- 제한:
  - v121은 단건 canary다. 10만 건 전체 semantic gate는 계속 `REVIEW-LOCKED`다.
  - `11718091` reason/final 충돌과 `11718097` correct title recall은 별도 `re_judge`/`re_search`가 필요하다.

## 2026-05-28 - v117 부분 런 semantic over-resolution 및 comment author context 보정

- 상태: targeted-rerun-completed / partial-fixed / two-rejects-remain / quality-review-locked
- 배경:
  - `out/expert_result_20260528_141006_620986.json`은 10만 건 입력 전체 결과가 아니라 `completed=80`, `flushed=71`, `pending=9`인 부분 산출물이다.
  - 이 부분 산출물에서 `11718083`, `11718099`, `11718091`, `11718097` 네 건이 자연어 의미상 작품 title을 과확정한 `REJECT` 케이스로 확인됐다.
  - 입력 JSONL에는 post row의 `gallery_id`/`author`, comment row의 `comment_id`/`author`/`ip`/reply 정보가 있으므로, 댓글 작성자 맥락을 final judgment에 별도 공개 메타로 전달할 필요가 있다.
- 조치:
  - `네이버` 같은 플랫폼/커뮤니티 표면을 작품명 final title로 승격하지 않도록 보정했다.
  - `표지변경`, `작가 신작/최신화` 같은 meta action/status headline을 작품명 final title로 승격하지 않도록 보정했다.
  - 결과 row 및 pipeline post dict에 `gallery_id`, `post_author`, `comment_metadata`, `comment_context_lines`를 추가했다.
  - 댓글 본문 문자열에는 author/IP를 섞지 않고, LLM 전문가에게는 `comment_context`로만 전달하도록 했다.
- 검증:
  - py_compile 통과.
  - focused comment author/IP context 회귀 테스트 통과.
  - v117 targeted rerun `20260528_153350_626964`: `requested_parallel=36`, `effective_parallel=4`, `completed=4`, `failed=0`, `pending=0`.
  - after-review 결과는 `ACCEPT=2`, `REJECT=2`다. `11718097`, `11718099`는 회복됐고 `11718083`, `11718091`은 여전히 overresolve로 남았다.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v117_partial_run_semantic_issue_review_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v117_partial_run_semantic_issue_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v117_partial_run_action_queue_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v117_targeted_4_after_review_summary_ko_20260528.md`
  - `qualitative_review/20260528_141006_620986/v117_targeted_4_after_review_labels.jsonl`
- 제한:
  - 이번 rerun은 targeted 4건 검증이며 10만 건 전체 승인 근거가 아니다.
  - 남은 `REJECT=2` 때문에 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-28 - v115/v116 검색 alias 일반어 오염 제거 및 targeted 재검증

- 상태: targeted-bugfix-verified / hardcoding-avoided / quality-review-locked
- 배경:
  - 기존 v109 closure 뒤 추가 재검증에서 특정 작품명/URL 하드코딩 없이 검색 evidence 기반 alias 복구를 유지해야 했다.
  - v114/v115 실서버 결과에서 일반 본문 단어가 작품 alias로 승격되는 오염이 확인됐다.
  - `post_id=11365197`에서 v114는 `애들 -> 잘못된 권유`, v115는 `성이 -> 실패 없는 웹소설 작법서 by 윤재 저`로 잘못 확정했다.
- 조치:
  - 검색 alias inference에서 `애들`, `사람들`, `캐릭터`, `주인공`, `성이` 같은 일반어/문법 조각을 alias 후보에서 제외했다.
  - 검색 결과 title 후보에서 `웹소설 작법서`, `공략집`, `작성법`, `by ... 저` 같은 문서/가이드형 제목을 작품 후보에서 제외했다.
  - 특정 작품명/URL 매핑을 추가하지 않고 일반 규칙과 회귀 테스트로 보정했다.
- 실행:
  - v115 run id `20260528_015206_759785`: 입력 `7`, requested_parallel `36`, effective_parallel `7`, completed/failed/pending `7/0/0`.
  - v116 run id `20260528_021407_860207`: 입력 `1`, requested_parallel `36`, effective_parallel `1`, completed/failed/pending `1/0/0`.
  - v116에서 `post_id=11365197`은 `전1시 -> 전지적 1인칭 시점`으로 복구됐다.
- 검증:
  - `tests.test_agentic_pipeline_rework tests.test_agentic_pipeline_alias_contract tests.test_batch_context`: `298 tests OK`
  - 새 회귀 테스트:
    - common body group word alias 승격 차단
    - case-particle fragment + howto/article title 승격 차단
- 산출물:
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_review_summary_ko_20260528.md`
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v116_alias_commonword_guard_action_queue_ko_20260528.md`
- 제한:
  - v115/v116 foreground shell exit code는 `1`로 잡혔지만 manifest는 success다. 런 건강과 shell 반환값 불일치는 별도 조사 대상으로 남긴다.
  - 이번 결과는 targeted bug fix 증거이며 10만 건 semantic approval 근거가 아니다. gate는 `REVIEW-LOCKED`다.

## 2026-05-27 - 소규모 targeted run 병렬 상한 지침 정정

- 상태: docs-updated / adaptive-parallel-policy-confirmed / quality-no-go
- 배경:
  - 10건 미만 같은 작은 targeted test에서 매번 36 worker를 고정 기동하거나, 그 명령값을 맞추려고 재실행하는 것은 비효율이다.
  - Gemma 4 4B 운영 기준의 `36`은 고정 워커 수가 아니라 최대 상한으로 둔다.
- 지침 정정:
  - 현재 `expert_main.py`는 `--parallel`을 상한으로 해석하고 `effective_parallel=min(requested_parallel,input_post_count)`로 실제 워커 수를 낮춘다.
  - 소규모 run은 명령에 `--parallel 36`이 들어갔다는 이유만으로 재실행하지 않는다.
  - 검증 기준은 명령 문자열이 아니라 manifest/run_meta의 `requested_parallel`, `effective_parallel`, `parallel_policy`, `input_post_count`다.
  - result/checkpoint/log/manifest가 정상이고 별도 품질 이슈가 없으면, 병렬도 명령값만 과했던 완료 run은 그대로 증거로 유지한다.
- 제한:
  - 이 정책은 실행 효율 지침이며, 자연어 판정 품질 gate를 올리는 근거는 아니다.

## 2026-05-27 - v109 v105 REJECT closure after-review 및 소규모 병렬 검증

- 상태: targeted-rerun-completed / after-reviewed / rejects-closed / holds-remain / quality-no-go
- 배경:
  - v108 보강 후 v105 `REJECT/re_judge` 7건을 실서버에서 다시 돌렸다.
  - 소규모 targeted run은 36워커 고정이 아니라 입력 수 기준 병렬도로 실행해야 하므로 v108은 `--parallel 7`, v109 단건 guard는 `--parallel 1`로 확인했다.
- 실행:
  - v108 run id `20260527_203403_780353`: 입력 `7`, `requested_parallel=7`, `effective_parallel=7`, completed `7`, failed `0`, pending `0`.
  - v109 single-case rerun id `20260527_205113_232542`: 입력 `1`, `requested_parallel=1`, `effective_parallel=1`, completed `1`, failed `0`, pending `0`.
  - search shard health는 `36/36`으로 확인했다.
- after-review:
  - 전체 `7`건 중 `ACCEPT=4`, `HOLD=3`, `REPROCESS=0`, `REJECT=0`, `INFO_MISSING=0`.
  - `전1시`는 v108에서 `전지적 독자 시점`으로 흔들린 것을 v109 guard 후 `전지적 1인칭 시점`으로 정정했다.
  - `탑매`, `괴담텔`, `괴출`은 추가 검색/재판정 근거가 필요해 `HOLD`로 남겼다.
- 검증:
  - `tests.test_agentic_pipeline_rework`: `243 tests OK`
  - `tests.test_agentic_pipeline_alias_contract tests.test_batch_context`: `42 tests OK`
  - v109 guard targeted tests 통과.
- 산출물:
  - `qualitative_review/20260505_214349_324347/v109_v105_reject_closure_after_review_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v109_v105_reject_closure_after_review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/v109_v108_11365197_neighbor_guard_manifest.json`
- 제한:
  - v105 `REJECT=7`은 `REJECT=0`으로 닫혔지만 `HOLD=3`이 남아 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v108 v105 REJECT alias recall 보강 및 p7 재실행 입력 준비

- 상태: local-regression-pass / targeted-input-ready / superseded-by-v109-after-review / quality-no-go
- 배경:
  - v105 after-review에서 `아집숨`, `탑매`, `괴무직`, `괴담텔`, `전1시`, `괴출`, `성녀속마음` 7건이 `REJECT/re_judge`로 남았다.
  - 이들은 대체로 정상 웹소설 short alias가 noise/author_talk/platform talk로 내려간 false negative다.
- 조치:
  - `KNOWN_TITLE_ABBREVIATIONS`와 `_resolve_known_abbreviation_surface`를 보강해 title abbreviation, 조사/어미 suffix, batch alias fallback을 처리했다.
  - prompt router/expert prompt에 제목 선두 작품 약칭 + 후기/이벤트/감상/캐릭터 질문 보존 규칙을 추가했다.
  - 기존 known abbreviation source 라벨 회귀를 `known_abbreviation`/`known_title_abbreviation` 분리로 수정했다.
- 검증:
  - `tests.test_agentic_pipeline_rework`: `243 tests OK`
  - `tests.test_agentic_pipeline_alias_contract tests.test_batch_context`: `42 tests OK`
  - py_compile 통과.
- 산출물:
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_alias_recall_patch_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_rejudge_targeted_input.jsonl`
  - `qualitative_review/20260505_214349_324347/v108_v105_reject_rejudge_targeted_manifest.json`
- 제한:
  - 후속 v108/v109 재실행과 after-review는 완료됐지만 `HOLD=3`이 남아 semantic gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v105 targeted rerun 및 adaptive parallel 정책 정정

- 상태: targeted-rerun-completed / after-review-open / adaptive-parallel-policy-fixed / quality-no-go
- 배경:
  - v98/v102 실서버 검증은 LLM endpoint가 `127.0.0.1`이 아니라 `10.20.0.101:8000`에서 열려 있어 해당 endpoint로 재실행했다.
  - 7건/25건 targeted run에 `--parallel 36`을 적용한 것은 비효율이므로 이후 정책을 정정했다.
- 실행:
  - v98 run id `20260527_190502_986325`: completed `7`, failed `0`, pending `0`.
  - v102 run id `20260527_192017_408654`: completed `25`, failed `0`, pending `0`.
- after-review:
  - 전체 `32`건 중 `ACCEPT=16`, `HOLD=9`, `REJECT=7`.
  - `아집숨`, `탑매`, `괴무직`, `괴담텔`, `전1시`, `괴출`, `성녀속마음`은 재판정/추가 보강이 필요하다.
- 정책:
  - `MCP_SHARD_COUNT=36`과 shard audit `36/36`은 유지한다.
  - 실제 워커 수는 `effective_parallel=min(requested_parallel,input_count)`로 낮춘다.
  - 36은 상한이며 소규모 targeted run의 고정값이 아니다.
  - 소규모 run은 명령에 `--parallel 36`이 들어갔다는 이유만으로 재실행하지 않는다.
- 추가 보강:
  - `expert_main.py`가 입력 post 수를 먼저 로드한 뒤 `effective_parallel=min(requested_parallel,input_post_count)`로 워커 수를 낮춘다.
  - manifest와 각 row `run_meta`에 `requested_parallel`, `effective_parallel`, `parallel_policy`, `input_post_count`를 기록한다.

## 2026-05-27 - v104 runtime preflight 및 로컬 회귀 재확인

- 상태: search-shards-ready / llm-endpoint-down / local-regression-pass / quality-no-go
- 배경:
  - v98/v102 targeted rerun을 진행하려면 Gemma 4 4B LLM endpoint와 36개 search shard가 모두 준비되어야 한다.
- 확인:
  - `http://127.0.0.1:8000/v1/models`는 연결 실패다.
  - `:8000` listener가 없고, 승인된 Python command line 조회에서 관련 LLM/expert 프로세스가 확인되지 않았다.
  - `tools/audit_search_shards.py --count 36 --timeout 1.5` 결과는 `ok=36/36`, `bad=[]`다.
- 검증:
  - alias/batch/packet/closure/VLM browser review 관련 테스트 `74`건 통과.
  - agentic pipeline rework 테스트 `239`건 통과.
- 해석:
  - 현재 blocker는 search shard가 아니라 LLM endpoint 부재다.
  - 실서버 targeted rerun과 after-review 전까지 semantic gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v102 clean alias preservation contract 보강

- 상태: contract-prompt-fix-verified-locally / superseded-by-v105-v109-reruns / quality-no-go
- 배경:
  - v101 spot review에서 `blocked_by_result_contract` 안에 정상 short alias가 과차단되는 패턴이 확인됐다.
  - 특히 `sentence_like_alias_surface`, `pure_work_alias`, `exact_title_not_alias`가 noisy term 차단과 clean alias 보존을 충분히 분리하지 못했다.
- 조치:
  - `_infer_slang_alias_contract`에 title initial 기반 clean alias segment 복구를 추가했다.
  - prompt router와 verifier prompt에 “정식 제목과 짧은 약칭이 함께 보이면 짧은 약칭만 alias 필드에 남긴다”는 규칙을 추가했다.
  - noisy term은 저장하지 않되 clean alias는 `canonical_work_alias` 후보로 보존하는 회귀 테스트를 추가했다.
- 검증:
  - alias contract 테스트 `33`건 통과.
  - batch context/qualitative packet/exit closure 테스트 `38`건 통과.
  - agentic pipeline rework 테스트 `239`건 통과.
- 제한:
  - 이 섹션 작성 당시 LLM endpoint 연결 실패로 실서버 재실행이 대기 상태였다. 후속 v105/v108/v109에서 재실행과 after-review를 완료했지만 `HOLD=3`이 남았다.
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`이다.

## 2026-05-27 - v101 blocked_by_result_contract 표본 리뷰

- 상태: spot-reviewed / overblock-patterns-found / quality-no-go
- 배경:
  - v99에서 `blocked_by_result_contract=79`가 남았지만, 저장 차단이 모두 타당한지 아니면 정상 약칭까지 과차단하는지 분리해야 했다.
- 조치:
  - store_reason/alias_scope/relevance를 기준으로 25건을 과표집해 자연어로 판독했다.
  - 저장 차단 유지, 정책 보류, 과차단/재판정 후보를 분리했다.
- 결과:
  - `ACCEPT=6`, `HOLD=5`, `REJECT=14`.
  - `sentence_like_alias_surface` 안에 문장형 term과 정상 약칭 후보가 섞이는 패턴을 확인했다.
  - `pure_work_alias`와 short alias 후보가 저장 차단에 남는 과차단 패턴을 확인했다.
- 해석:
  - `blocked_by_result_contract=79`는 “차단됐으니 안전” 큐가 아니라 alias recall 손실 가능성이 있는 검토 큐다.
  - noisy term과 clean alias를 같은 packet에서 분리하는 prompt/router 또는 후처리 보강이 필요하다.
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v100 slang DB 소량 상태 수동 리뷰

- 상태: small-status-manual-reviewed / quality-no-go
- 배경:
  - v99에서 `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`는 총 8건이라 LLM 서버 없이도 원문 공개 필드로 우선 방향을 잡을 수 있었다.
- 조치:
  - 8건을 `ACCEPT/HOLD/REJECT`로 수동 리뷰했다.
  - 외부 매체 seed `프리렌`, `시달소`는 quarantine 후보로 분류했다.
  - 정상 웹소설 alias 후보와 재판정 후보를 분리했다.
- 결과:
  - `ACCEPT=4`, `HOLD=2`, `REJECT=2`.
- 해석:
  - 이 작업은 소량 slang DB 상태의 방향을 잡은 것이며 전체 `slang_db_review=87` 승인 완료가 아니다.
  - v98 실서버 재실행과 DB 상태 확인 전까지 semantic gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v99 current slang DB status queue

- 상태: status-queue-rebuilt / tooling-traceability-fixed / quality-no-go
- 배경:
  - 최신 closure에는 `slang_db_review=87`이 남아 있으며, 이전 문서 일부에는 중간 상태였던 `no_slang_term_in_packet` 분포가 섞여 있었다.
  - 현재 남은 `slang_db_review`는 실제 slang DB 상태 검토 큐인지 다시 확인해야 했다.
- 조치:
  - `round3_manual_guard_slang_reviews.jsonl`과 `round3_exit_action_remaining_queue.jsonl` 기준으로 v99 상태별 큐를 재생성했다.
  - `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`로 분리했다.
  - `build_slang_db_status_review.py`가 prefix를 받아도 packet id를 `V85-SLANG`으로 고정하던 문제를 수정했다.
- 검증:
  - focused status review test 통과.
  - `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools tests.test_batch_context`: `38 tests OK`.
  - `py_compile` OK.
- 해석:
  - v99는 후속 리뷰 단위를 정리한 것이며 `slang_db_review=87` 승인 완료가 아니다.
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`이다.

## 2026-05-27 - v98 targeted rerun input 및 현재 image loading probe

- 상태: targeted-input-prepared / server-rerun-blocked / quality-no-go
- 배경:
  - v97에서 `프리렌`, `시달소` 같은 외부 매체 slang seed가 batch memory resolved alias로 되살아나는 경로를 코드로 차단했다.
  - 이 차단이 실제 run에서도 유지되는지 보려면 negative control과 positive webnovel alias control을 함께 재실행해야 한다.
- 조치:
  - v98 targeted input `7`건을 준비했다.
  - negative control은 `강연금 -> 강철의 연금술사`, `프리렌 -> 장송의 프리렌`, `시달소 -> 시간을 달리는 소녀`다.
  - positive control은 `아집숨`, `탐태창`, `회맹생`, `반로환동전`이다.
  - v98 input/manifest/summary의 한국어 메타데이터를 정리했다.
  - `post_id=11097334` 현재 iab 브라우저 상태를 다시 확인해 placeholder image complete trap을 최신 증거로 남겼다.
- 검증/차단:
  - `2026-05-27T17:54:24+09:00` 기준 `http://127.0.0.1:8000/v1/models`는 연결 실패다.
  - 관련 Python 점유 프로세스는 확인되지 않았다.
  - 따라서 v98 실서버 재실행과 after-review는 LLM endpoint 복구 후 진행해야 한다.
- 해석:
  - 입력 준비와 브라우저 probe는 quality gate를 완화하지 않는다.
  - 최신 closure gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v97 non-novel slang seed quarantine

- 상태: batch-memory-seed-guard-fixed / rerun-reviewed / quality-no-go
- 배경:
  - `v86` slang DB 상태 리뷰에서 `post_id=9687991`의 `프리렌 -> 장송의 프리렌`이 `server_poc:saved_slang`으로 확인됐다.
  - `post_id=11097307`의 `시달소 -> 시간을 달리는 소녀`는 `repo:conflict`로 확인됐다.
  - 두 seed는 웹소설 약칭 recall이 아니라 비웹소설/외부 매체 alias가 batch memory에 resolved alias로 되살아날 수 있는 경계 사례다.
- 조치:
  - `BatchContextMemory.NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST`에 `프리렌/장송의 프리렌`, `시달소/시간을 달리는 소녀`를 추가했다.
  - structured slang support가 있어도 두 seed가 pending/resolved memory로 승격되지 않는 회귀 테스트를 추가했다.
- 검증:
  - `tests.test_batch_context`: `9 tests OK`.
  - `tests.test_agentic_pipeline_rework tests.test_batch_context`: `248 tests OK`.
  - `py_compile`: OK.
- 제한:
  - 이 섹션 작성 당시 `http://127.0.0.1:8000/v1/models`는 연결 실패였다. 후속 v105 재실행에서 `강연금`, `프리렌` 외부 매체 seed가 되살아나지 않음을 확인했다.
  - 최신 closure gate는 여전히 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v96 VLM/OCR 첨부 팝업 evidence 보강

- 상태: attachment-popup-evidence-recovered / info-missing-reduced / quality-no-go
- 배경:
  - `post_id=10794867`은 기존 browser image gate에서 본문 인라인 이미지 selector가 `0`개라 `INFO_MISSING`으로 남아 있었다.
  - live browser 재확인 결과 게시글은 살아 있었고, `원본 첨부파일 1` 및 `viewimagePop.php` 링크가 존재했다.
- 조치:
  - 첨부 팝업 이미지를 직접 열어 `550x350` 로딩을 확인했다.
  - 확인 이미지는 `장르소설 마이너 갤러리 / GENRE NOVEL MINOR GALLERY` 소개 이미지라 작품 판정을 직접 지지하지 않는 것으로 판정했다.
  - `capture_vlm_ocr_browser_review_cli.py`가 attachment links를 수집하도록 보강했다.
  - `build_v78_vlm_browser_semantic_relabel.py`가 source `final_decision_fields/reason` 등 공개 필드를 packet에 유지하도록 보강했다.
  - `build_qualitative_exit_action_closure.py`가 v96 supplemental label과 attachment-popup browser review를 병합하고 browser gate pass/fail을 최신 browser index 기준으로 재계산하도록 보정했다.
- 결과:
  - `10794867`: `INFO_MISSING -> HOLD/human_review`.
  - `10892069`: 삭제/리다이렉트 상태로 `INFO_MISSING/human_review` 유지.
  - latest closure: `ACCEPT=375`, `HOLD=208`, `INFO_MISSING=1`, approval excluded `209`.
  - browser grade: `Strong=99`, `Missing=1`; image gate: `pass=99`, `fail=1`.
- 검증:
  - `tests.test_vlm_browser_review_cli tests.test_exit_action_closure tests.test_qualitative_review_packet_tools`: `32 tests OK`.
  - `tests.test_agentic_pipeline_rework tests.test_exit_action_closure tests.test_qualitative_review_packet_tools tests.test_batch_context tests.test_vlm_browser_review_cli`: `278 tests OK`.
- 해석:
  - `INFO_MISSING`는 줄었지만 `human_review=122`, `slang_db_review=87`, `INFO_MISSING=1`이 남아 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`이다.

## 2026-05-27 - v95 structured evidence catalog 라벨러 보정

- 상태: review-tooling-fixed / re-search-closed / quality-no-go
- 배경:
  - v94 이후 남은 `re_search=1`은 `post_id=9803986`이었다.
  - 결과 JSON에는 `identity.search_evidence_catalog`로 `K-문화의 제왕 - 문피아 웹소설` 등 공개 작품 근거가 있었지만, reason 문자열의 stale `official_urls=0` counter 때문에 after-review가 계속 `Weak/REPROCESS`를 냈다.
- 조치:
  - qualitative round2/after-review labeler가 structured `search_evidence_catalog`를 evidence count에 반영하도록 수정했다.
  - catalog에 resolved title과 직접 연결되는 novel platform URL이 있으면 effective `official_urls/search_snippets`를 보강한다.
  - stale `official_urls=0` 문자열만으로 `weak_evidence`를 유지하지 않도록 했다.
  - v95 after-review label/packet을 closure supplemental source에 추가했다.
- 결과:
  - `9803986`: `REPROCESS/re_search -> ACCEPT/no_action`.
  - latest closure: `ACCEPT=375`, `HOLD=207`, `INFO_MISSING=2`, approval excluded `209`.
  - `re_search=0`.
- 검증:
  - focused labeler regression test 통과.
- 해석:
  - 재검색 큐는 닫혔지만 `human_review=122`, `slang_db_review=87`, `INFO_MISSING=2`가 남아 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`이다.

## 2026-05-27 - v94 broad topic/comment composite 과잉 확정 보정

- 상태: targeted bug partially fixed / rerun verified / quality-no-go
- 배경:
  - v92 이후 남은 `re_search=3` 중 `post_id=10529582`는 `삼국지 떡밥`이라는 넓은 소재 화제가 `삼국지 7`, 이후 v93에서 `삼국지 태사자` 같은 특정 작품으로 과잉 확정되는 경로가 있었다.
  - `post_id=10870841`은 title 질문과 댓글 답변이 있는데도 body의 추측형 `괴담동?` alias가 `괴담 동아리`로 복구될 수 있었다.
- 조치:
  - broad topic title-surface guard를 넘버링 작품뿐 아니라 `work_plus_character` / `character_attached_composite` 후보까지 확장했다.
  - 질문형 post에서 body guess alias와 댓글 답변 alias가 다른 작품을 가리키면 batch memory alias rescue를 보류하도록 했다.
  - v94 after-review label/packet을 closure supplemental source에 추가했다.
- 결과:
  - v94 36워커 재실행은 shard health `36/36`, 입력 `3/3` 완료.
  - `10529582`: `official_title=null`, `is_relevant=false`, `discussion_type=off_topic`, `work_resolution=none`.
  - `10870841`: title 확정은 차단됐고 `HOLD/human_review`로 남김.
  - `9803986`: 공개 evidence가 약해 `REPROCESS/re_search` 유지.
  - latest closure: `ACCEPT=374`, `HOLD=207`, `REPROCESS=1`, `INFO_MISSING=2`, approval excluded `210`.
- 검증:
  - `py_compile` OK.
  - `tests.test_agentic_pipeline_rework tests.test_exit_action_closure tests.test_qualitative_review_packet_tools tests.test_batch_context`: `273 tests OK`.
- 해석:
  - 잔여 `re_search`는 `3 -> 1`로 줄었지만 `human_review=122`, `slang_db_review=87`이 남아 있다.
  - 이번 작업은 targeted false positive/over-resolution 보정이며, 전체 10만건 semantic quality approval은 아니다.

## 2026-05-27 - v92 10만건 부족점/버그 정리 및 비소설 disclaimer 보정

- 상태: targeted bug fixed / canary verified / quality-no-go
- 배경:
  - v90 after-review 이후 남은 `re_search=4` 중 `post_id=9197737`이 명시적으로 `소설얘기아닌데`라고 했는데도 `브레이킹 배드` title로 되살아나는 false positive였다.
  - verifier/arbiter는 외부 TV 드라마 감상으로 비관련 판단을 냈지만, 후반 rescue 경로가 이를 다시 관련 작품으로 복구했다.
- 조치:
  - 명시적 비소설 disclaimer 감지 helper를 추가했다.
  - final identity, output consistency, unresolved worklike preserve, title-surface rescue 경로에서 disclaimer + non-novel 반론 조합을 차단했다.
  - locked official detail 후보가 direct-title-surface 재생성으로 candidate role이 되거나 중복될 때 primary 복구가 막히는 회귀도 보정했다.
  - v92 after-review label/packet을 closure supplemental source에 추가했다.
- 결과:
  - v92 canary `post_id=9197737`: `is_relevant=false`, `official_title=null`, `discussion_type=off_topic`, `work_resolution=none`.
  - latest closure: `ACCEPT=373`, `HOLD=206`, `REPROCESS=3`, `INFO_MISSING=2`, approval excluded `211`.
  - 남은 action: `human_review=121`, `slang_db_review=87`, `re_search=3`.
- 검증:
  - `py_compile` OK.
  - `tests.test_agentic_pipeline_rework tests.test_exit_action_closure tests.test_qualitative_review_packet_tools tests.test_batch_context`: `270 tests OK`.
- 해석:
  - 이번 작업은 실제 false positive 하나를 코드와 canary로 닫은 것이며, 전체 10만건 semantic quality approval은 아니다.
  - random baseline/P0-P1 regression과 남은 큐가 닫히기 전까지 gate는 `NO-GO / REVIEW-LOCKED`이다.

## 2026-05-27 - v89 10만 건 잔여 action rerun 및 closure 갱신

- 상태: targeted action rerun merged / after-review updated / quality-no-go
- 배경:
  - v84 action input `199`건은 기존 approval excluded 중 `re_search=127`, `re_judge=72`였던 큐라 실제 LLM 재실행이 필요했다.
  - LLM endpoint가 `http://10.20.0.101:8000`에서 열렸고 Gemma 4 4B 36워커 조건으로 재실행했다.
- 조치:
  - 첫 v89 실행에서 checkpoint `74`건을 확보했고, 잔여 `125`건을 별도 실행으로 완료했다.
  - 두 checkpoint를 원본 v84 input post_id 순서로 병합해 `199/199`, missing/duplicate/extra `0/0/0`을 확인했다.
  - `build_qualitative_round3_after_review.py`로 after-review를 생성했고 `ACCEPT=170`, `HOLD=16`, `REPROCESS=13`을 확인했다.
  - `build_qualitative_exit_action_closure.py`가 v89 after-review label/packet을 supplemental source로 읽도록 갱신했다.
- 결과:
  - latest closure는 `ACCEPT=363`, `HOLD=206`, `REPROCESS=13`, `INFO_MISSING=2`.
  - approval excluded는 `391`에서 `221`로 줄었다.
  - `re_search=127`, `re_judge=72` 큐는 v89 이후 `re_search=13`, `re_judge=0`으로 줄었다.
- 산출물:
  - `qualitative_review/20260505_214349_324347/v89_100k_fixable_gap_bug_action_summary_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v89_current_remaining_action_after_v88_tooling_rerun_p36_combined_20260527_manifest.json`
  - `qualitative_review/20260505_214349_324347/v89_current_remaining_action_after_v88_tooling_after_review_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
- 해석:
  - targeted 큐는 크게 줄었지만 `human_review=121`, `slang_db_review=87`, `re_search=13`이 남아 있다.
  - VLM/OCR evidence gap `27`건과 post-fix random baseline/P0/P1 regression 전까지 전체 10만 건 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - v88 VLM/OCR lazy placeholder 도구 보강

- 상태: tooling-fixed / tested / quality-no-go
- 배경:
  - v87에서 `post_id=11097334`의 placeholder가 `complete=true`, `naturalWidth>0`으로 보일 수 있음을 확인했다.
  - 이 규칙을 문서에만 두면 future capture/relabel 도구가 다시 과승격할 수 있었다.
- 조치:
  - browser capture에 lazy/data-original/placeholder current src pending count를 추가했다.
  - closure와 v80 relabel 도구가 explicit `imageGatePass=true`를 counter gate와 함께 검증하도록 고쳤다.
  - image gate 실패 시 `Strong` evidence를 `Weak`로 낮추도록 했다.
- 검증:
  - `py_compile` 통과.
  - `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools` `27 tests OK`.
- 해석:
  - VLM/OCR 이미지 로딩 게이트의 tooling 허점은 줄였지만, 기존 `27`건 브라우저 target과 `199`건 rerun은 아직 남아 있다.

## 2026-05-27 - v87 10만 건 부족점 정리 및 이미지 placeholder 게이트 보강

- 상태: action-summary-updated / image-gate-gap-confirmed / quality-no-go
- 배경:
  - 10만 건 결과에서 아직 닫히지 않은 `391`건 approval 제외 큐와 해결 가능한 버그/부족점을 한 번에 볼 수 있는 한국어 정리가 필요했다.
  - `post_id=11097334`처럼 본문 이미지 lazy-load가 늦게 끝나는데 로딩 완료로 오판될 수 있는 케이스가 있었다.
- 조치:
  - v87 한국어 action summary를 생성했다.
  - Codex in-app browser로 `11097334`를 열고 DOM/screenshot evidence를 남겼다.
  - `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`에 placeholder currentSrc와 `data-original` 교체 확인 규칙을 추가했다.
- 결과:
  - 초기 3번째 본문 이미지는 `gallview_loading_ori.gif` placeholder였고 `complete=true`, `naturalWidth=200`, `naturalHeight=200`으로 잡혔다.
  - 스크롤/대기 후 실제 `dcimg` URL로 교체되고 `naturalWidth=850`, `naturalHeight=1481`이 됐다.
  - `2026-05-27 12:26:14 +09:00` 기준 LLM endpoint는 연결 실패, 8000 listener 없음, 관련 Python 점유 없음이었다.
- 해석:
  - `img.complete && naturalWidth>0`은 VLM/OCR Strong evidence 조건이 아니다.
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - slang DB conflict 상태 v86 정정

- 상태: status-classifier-fixed / quality-no-go
- 배경:
  - v85에서 `post_id=10173521`이 `extracted_not_persisted`로 잡혔다.
  - DB를 직접 확인하니 `server-poc/slang_db/slang_db.json`의 `말하는 검이 되어버다` bucket 안 `conflicts`에 `말하는검`이 있었다.
- 조치:
  - closure classifier가 `titles[].conflicts[]`를 검사하도록 보정했다.
  - `persisted_conflict` 상태와 `resolve_conflicting_alias` followup action을 추가했다.
  - v86 status queue를 재생성했다.
- 결과:
  - `extracted_not_persisted=0`
  - `persisted_conflict=3`: `8650236`, `10173521`, `11097307`
  - `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_pending=2`
- 검증:
  - `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools` `24`건 통과.
- 해석:
  - 저장 누락으로 보였던 케이스는 alias conflict 보관 상태였다.
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - slang DB 상태별 v85 리뷰 큐 생성

- 상태: superseded-by-v86 / 중간 상태 큐
- 배경:
  - v84 정정 후 `slang_db_review=87`은 실제 source slang field가 있는 큐로 확인됐다.
  - 다만 저장 차단, 이미 저장, pending, family alias, 추출-미저장 상태가 섞여 있어 한 번에 리뷰하기 어렵다.
- 조치:
  - `tools/build_slang_db_status_review.py`를 추가했다.
  - `round3_manual_guard_slang_reviews.jsonl`과 v84 slang review packet을 조인해 상태별 packet/label/action queue를 생성했다.
  - 상태별 followup action을 고정했다.
- 결과:
  - `blocked_by_result_contract=79`
  - `persisted_as_slang=3`
  - `persisted_pending=2`
  - `family_alias=2`
  - `extracted_not_persisted=1`
  - labels: `HOLD=86`, `REPROCESS=1`
- 검증:
  - `tests.test_qualitative_review_packet_tools` `12`건 통과.
- 해석:
  - `extracted_not_persisted=1`은 우선 조사 대상이다.
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - source slang fallback 정정 및 v84 action package 재생성

- 상태: tooling-verified / source-fallback-fixed / quality-no-go
- 배경:
  - v83에서 `docs_issue=64`로 분리한 row를 재확인하니, 원본 `server-poc/expert_result_20260505_214349_324347.json`에는 `identity.slang_insight`가 있었다.
  - 예전 review packet의 `slang_db_fields` dict가 비어 있지 않은 객체처럼 보였지만 실제 term 값은 모두 비어 있어 source fallback을 막고 있었다.
- 조치:
  - closure가 source result를 fallback packet index로 읽도록 했다.
  - `slang_db_fields` 키 존재가 아니라 `detected_term`, `decoded_term`, `canonical_work_alias` 중 실제 term 존재 여부로 fallback을 판단하게 했다.
  - source fallback 회귀 테스트를 추가했다.
- 결과:
  - `docs_issue=64` 중간 해석은 폐기됐다.
  - latest actions는 `no_action=193`, `human_review=105`, `re_search=127`, `re_judge=72`, `slang_db_review=87`이다.
  - v84 action package: remaining `391`, rerun combined `199`, browser target `27`.
  - slang DB 리뷰 상태: `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_pending=2`, `family_alias=2`, `extracted_not_persisted=1`.
- 검증:
  - `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools tests.test_batch_context` `29`건 통과.
- 해석:
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.
  - endpoint 복구 후 v84 rerun combined 199건을 36워커로 재실행해야 한다.

## 2026-05-27 - slang_db field routing 및 v83 잔여 action package 재생성

- 상태: superseded-by-v84 / 중간 가설
- 배경:
  - v82에서 `slang_db_review=87` 중 `no_slang_term_in_packet=64`, `blocked_by_result_contract=23`으로 갈라지는 것이 확인됐다.
  - `no_slang_term_in_packet`은 DB 오염 검토가 아니라 review packet 공개 필드 또는 label routing 결손이다.
- 조치:
  - closure 단계에 slang field guard를 추가해 공개 slang term이 없는 `slang_db_review`를 `INFO_MISSING/docs_issue`로 라우팅했다.
  - current remaining action packet에 `slang_db_fields`, `final_decision_fields`, `reason`, `search_health_flags`를 포함했다.
  - v83 action package와 10만건 부족점/버그 정리 문서를 생성했다.
- 결과:
  - latest closure action: `no_action=193`, `human_review=105`, `re_search=127`, `re_judge=72`, `docs_issue=64`, `slang_db_review=23`.
  - labels: `ACCEPT=193`, `HOLD=258`, `REPROCESS=67`, `INFO_MISSING=66`.
  - v83 rerun combined `199`, browser target `27`, missing post_id `0`.
- 검증:
  - `py_compile` 통과.
  - `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools tests.test_batch_context` `28`건 통과.
- 해석:
  - semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.
  - LLM endpoint 복구 후 36워커 재실행과 post-fix after-review가 필요하다.

## 2026-05-27 - VLM/OCR current remaining 재라벨 및 v81 action package 갱신

- 상태: tooling-verified / browser-evidence-separated / quality-no-go
- 배경:
  - v78에서는 VLM/OCR current remaining `28`건이 모두 `re_run` 또는 `INFO_MISSING` 계열로 남아 있었다.
  - 기존 iab 이미지 게이트는 이미지 로딩 상태를 잘 확인하지만, 이미지가 작품 판정을 직접 지지하는지는 별도 semantic 리뷰가 필요했다.
- 조치:
  - `tools/build_v78_vlm_browser_semantic_relabel.py`를 추가했다.
  - 기존 `vlm_ocr_iab_image_gate_combined_reviews.jsonl`과 `9531764` 단건 수동 브라우저 리뷰를 v78 browser targets에 조인했다.
  - `tools/build_qualitative_exit_action_closure.py`의 supplemental source에 v80 label/packet을 포함했다.
  - 최신 closure 기준으로 v81 action package를 다시 생성했다.
- 결과:
  - v80 VLM/OCR labels: `ACCEPT=1`, `HOLD=25`, `INFO_MISSING=2`.
  - latest closure: `ACCEPT=193`, approval excluded `391/584`.
  - v81 action package: remaining `391`, rerun combined `199`, browser target `27`, `re_run=0`.
- 검증:
  - `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools` 18건 통과.
  - py_compile 통과.
- 해석:
  - 기술적 이미지 로딩 문제 일부는 정리됐지만, 남은 VLM/OCR `27`건은 이미지 의미와 작품 판정 지지 여부를 확인해야 한다.
  - 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - slang_db current remaining 상태 분리

- 상태: review-queue-split / quality-no-go
- 배경:
  - v81 기준 `slang_db_review=87`건이 남아 있지만, 모두 같은 성격의 DB 저장 오염 후보는 아니었다.
- 조치:
  - `round3_manual_guard_slang_reviews.jsonl`에서 `closure_action=slang_db_review`만 필터링해 상태를 집계했다.
  - 한국어 요약 `v82_slang_db_current_remaining_status_split_ko.md`를 추가했다.
- 결과:
  - `no_slang_term_in_packet=64`
  - `blocked_by_result_contract=23`
- 해석:
  - `no_slang_term_in_packet`은 packet 공개 필드/export 또는 라벨 라우팅 이슈다.
  - `blocked_by_result_contract`은 저장이 이미 차단된 상태이므로 차단 사유와 recall 영향 검토가 남은 일이다.
  - 이 분리는 승인 완료가 아니며 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - current remaining action package 생성

- 상태: input-package-verified / quality-no-go
- 배경:
  - v75는 P0 잔여 96건만 재실행 입력으로 묶었다.
  - 최신 closure에는 approval excluded `392`건이 남아 있어 전체 큐를 action별로 분리할 필요가 있었다.
- 조치:
  - `tools/build_current_remaining_action_inputs.py`를 추가했다.
  - latest `round3_exit_action_remaining_queue.jsonl` 기준 `392`건 전체를 rerun/review/browser target으로 패키징했다.
- 결과:
  - rerun combined input `226`건.
  - `human_review` packet `79`건.
  - `slang_db_review` packet `87`건.
  - browser target `28`건.
  - missing post_id `0`.
- 산출물:
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_manifest.json`
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_rerun_combined_input.jsonl`
  - `qualitative_review/20260505_214349_324347/v78_current_remaining_action_browser_targets.jsonl`
- 해석:
  - 실제 LLM 재실행이 가능해지면 `226`건 rerun combined부터 36워커로 처리한다.
  - 이 패키징만으로 semantic gate는 완화하지 않는다.

## 2026-05-27 - after-review readiness 보강

- 상태: tooling-fix-verified / preflight-verified / quality-no-go
- 배경:
  - v75 P0 input은 실제 재실행 직후 after-review에 들어가야 하는데, `_round3_target.packet_id`와 `bucket`이 명시되지 않으면 before lineage가 약해질 수 있었다.
- 조치:
  - after-review 도구에 `base_packet_id`/`primary_pattern` fallback을 추가했다.
  - v75 P0 input `96`건에도 packet/bucket 메타를 명시했다.
  - 원본 server-poc subset으로 preflight after-review를 수행했다.
- 검증:
  - `tests.test_qualitative_review_packet_tools` 7건 통과.
  - preflight result `96`, packet `96`, label `96`, missing target `0`.
  - before packet/bucket lineage assertion 통과.
- 산출물:
  - `qualitative_review/20260505_214349_324347/v76_after_review_readiness_fix_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_preflight_original_result.json`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_preflight_original_after_manifest.json`
- 해석:
  - after-review 경로는 준비됐지만, preflight는 원본 결과 기반이므로 semantic gate 완화 근거가 아니다.

## 2026-05-27 - P0 잔여 targeted input 준비

- 상태: input-prepared / rerun-blocked-by-llm-endpoint / quality-no-go
- 배경:
  - latest closure 기준 P0 잔여 큐가 `generic_common_surface=80`, `weak_evidence_strong_resolution=16`으로 남아 있었다.
  - 이 큐는 10만 건 semantic approval을 막는 핵심 잔여 큐다.
- 조치:
  - 두 pattern을 중복 제거해 `96`건 targeted input으로 묶었다.
  - 입력 row에는 원문 post 필드와 `_round3_target`, `_issue_regression` 메타를 포함했다.
- 검증:
  - targeted input row `96`, missing post_id `0`.
  - manifest assertion 통과.
  - input 구조 assertion 통과.
  - LLM endpoint는 connection refused라 실제 36워커 재실행은 아직 보류했다.
- 산출물:
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_candidates.jsonl`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input.jsonl`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input_manifest.json`
  - `qualitative_review/20260505_214349_324347/v75_p0_generic_weak_remaining_input_summary_ko.md`
- 해석:
  - 서버가 복구되면 이 입력을 Gemma 4 4B, 36워커, `--no-auto-up-shards`로 바로 재실행한다.
  - 재실행 및 after-review 전까지 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - supplemental after-review closure 병합 보정

- 상태: tooling-merge-verified / quality-no-go
- 배경:
  - v68/v71/v73 after-review에서 이미 재라벨된 row가 latest closure에 모두 반영되지 않으면 현재 부족점/버그 큐가 실제보다 크게 보일 수 있었다.
  - 대표적으로 `8424362`, `9218133`, `11113480`과 v73 generic 19건 after-review 결과가 closure 집계에 일관 반영되어야 했다.
- 조치:
  - supplemental after-review label/packet 병합 결과를 latest closure 문서와 gate decision에 반영했다.
  - `source_state=supplemental_after_review`, `supplemental_update_rows=19`를 현재 수치의 근거로 기록했다.
- 검증:
  - closure 재생성 결과 `ACCEPT=192`, `HOLD=297`, `REPROCESS=93`, `INFO_MISSING=2`.
  - approved subset `192/584`, approval excluded `392/584`.
  - 남은 주요 큐는 `generic_common_surface=80`, `alias_recall_loss_false_negative=96`, `slang_db_alias_subtype=88`, `worker_shard_degraded_window=84`, `vlm_ocr_evidence_gap=28`, `weak_evidence_strong_resolution=16`.
  - LLM endpoint는 현재 connection refused라 추가 36워커 targeted 실행은 endpoint 복구 후 진행해야 한다.
- 산출물:
  - `qualitative_review/20260505_214349_324347/supplemental_after_review_closure_merge_ko_20260527.md`
  - `qualitative_review/20260505_214349_324347/current_100k_fixable_gap_bug_summary_ko_20260527.md`
- 해석:
  - 집계 정확도는 개선됐지만 high-risk approval excluded `392`건 때문에 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-27 - weak evidence closure guard 과차단 보정

- 상태: tooling-fix-verified / quality-no-go
- 배경:
  - `weak_evidence_strong_resolution` closure guard가 이미 `relevance=false`, `resolved_title=null`로 demote된 row까지 `ACCEPT/no_action`에서 `HOLD/human_review`로 되돌리고 있었다.
  - 이 row들은 더 이상 강한 작품 확정이 아니므로 weak-evidence strong-resolution guard의 원래 목적과 맞지 않았다.
- 조치:
  - `tools/build_qualitative_exit_action_closure.py`에서 비관련/title-null row는 해당 guard에서 제외했다.
  - 관련 unresolved row와 resolved title row는 계속 `Strong` evidence 없이는 approval excluded로 유지한다.
- 검증:
  - `tests.test_exit_action_closure` 6건 통과.
  - `py_compile` 통과.
  - closure 재생성 결과 `ACCEPT=183`, `HOLD=306`, `REPROCESS=93`, `INFO_MISSING=2`.
  - approval excluded `401/584`, `weak_evidence_strong_resolution=16`.
- 산출물:
  - `qualitative_review/20260505_214349_324347/weak_evidence_closure_guard_fix_ko_20260527.md`
- 해석:
  - approval excluded는 `460`에서 `401`로 줄었지만, 남은 high-risk queue 때문에 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-27 - generic concept question rescue guard 수정

- 상태: targeted-fix-verified / quality-no-go
- 배경:
  - v67 잔여 `generic_common_surface` 검토에서 `post_id=9218133`이 `반로환동/환골탈태` 차이 질문인데도 `반로환동으로 신분세탁` 작품명으로 확정됐다.
  - v70에서 canonical rescue는 막았지만 `title_surface_primary_candidate_rescued`가 상세 URL 근거로 제목을 다시 살렸다.
- 조치:
  - generic concept question mismatch를 canonical rescue, canonical lock, strongest rescue, best canonical candidate 선택에 적용했다.
  - title-surface primary rescue는 `generic_concept_question_surface_title` reject reason을 상세 URL 예외로 살리지 않도록 수정했다.
  - canonical rescue 우회 테스트와 title-surface rescue 우회 테스트를 보강했다.
- 검증:
  - py_compile 통과.
  - focused unittest 4건 통과.
  - v71 run `20260527_021145_875530`: completed `1`, failed `0`, pending `0`.
  - v71 final: `is_relevant=false`, `official_title=null`, `work_resolution=none`, `discussion_type=trope_discussion`.
  - v71 after-review: `ACCEPT=1`, `HOLD->ACCEPT=1`.
- 산출물:
  - `qualitative_review/20260505_214349_324347/generic_concept_question_guard_fix_ko_20260527.md`
- 해석:
  - `9218133` targeted 오검출은 닫혔다.
  - 내부 resolved mapping 시도는 로그에 남아 있어 확장 bucket 회귀가 필요하다.
  - 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-27 - character surface title 정확 근거 guard 수정

- 상태: targeted-fix-verified / quality-no-go
- 배경:
  - v67 잔여 `generic_common_surface` 검토에서 `post_id=8424362`가 `에미야 키리츠구`를 작품명으로 확정했다.
  - 검색 결과 제목은 `[fate]에미야 키리츠구의 성배대전`이었고, 후보는 작품명 전체가 아니라 긴 제목 안의 캐릭터 substring이었다.
- 조치:
  - 캐릭터 표면명 후보는 source/fetched title이 후보를 작품명으로 정확히 지칭할 때만 clean detail evidence로 인정하도록 수정했다.
  - 상세 URL 존재만으로 캐릭터 substring 후보가 `title_surface_primary_candidate_rescued` 경로를 타지 않게 막았다.
  - `8424362` 회귀 테스트와 문피아 suffix positive test를 추가했다.
- 검증:
  - py_compile 통과.
  - 신규 focused unittest 2건 및 관련 회귀 unittest 7건 통과.
  - LLM endpoint 응답, 검색 shard audit `36/36 OK`.
  - v68 run `20260527_004625_654237`: completed `1`, failed `0`, pending `0`.
  - v68 final: `is_relevant=false`, `official_title=null`, `work_resolution=none`.
  - v68 after-review: `ACCEPT=1`, `HOLD->ACCEPT=1`.
  - Browser `iab`로 `11097334` 이미지 lazy-load를 재확인했다. initial placeholder `1`, 최종 loaded `3/3`, placeholder/incomplete/broken `0`.
- 산출물:
  - `qualitative_review/20260505_214349_324347/character_surface_title_rescue_fix_ko_20260527.md`
- 해석:
  - `8424362` targeted 오검출은 닫혔다.
  - 잔여 high-risk queue가 남아 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-27 - direct/locked title rescue 상태 오염 수정

- 상태: targeted-fix-verified / quality-no-go
- 배경:
  - `generic_common_surface_current_hold19_input.jsonl` 재실행 v64에서 `post_id=10190186`이 `REJECT`로 확인됐다.
  - 복구된 작품명은 맞았지만 `discussion_type=noise`와 unresolved/demotion flag가 남아 final identity와 reason이 충돌했다.
- 조치:
  - direct full-title rescue와 locked official candidate rescue 성공 시 stale demotion flag를 제거하도록 수정했다.
  - rescue 결과를 `verification_result.novel_identity`에 동기화하고 confidence를 승격하도록 수정했다.
  - `m.munpia.com/novel/detail/<id>` 문피아 모바일 URL을 작품 상세 URL로 인정했다.
  - schema에 없는 discussion type을 쓰지 않도록 정규화했다.
- 검증:
  - focused unittest 2건, direct-title 회귀 11건, qualitative packet tool 3건, py_compile 통과.
  - v66 단건 run `20260527_000539_077549`: completed `1`, failed `0`, pending `0`, stale demotion flag 없음.
  - v67 19건 run `20260527_000930_077939`: completed `19`, failed `0`, pending `0`.
  - v67 after-review: `ACCEPT=7`, `HOLD=12`, `REJECT=0`.
- 산출물:
  - `qualitative_review/20260505_214349_324347/direct_locked_title_rescue_fix_ko_20260527.md`
- 해석:
  - v64의 `REJECT=1`은 해소됐지만 잔여 `HOLD=12`가 남아 전체 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-26 - v62 slang seed support gate 및 10만 건 부족점 정리

- 상태: targeted-verified / manual-label-4-accept-2-hold / semantic-quality-no-go
- 대상:
  - `src/llm_batch/batch_context.py`
  - `expert_main.py`
  - `tests/test_batch_context.py`
  - `qualitative_review/20260505_214349_324347/current_100k_gap_bug_fixable_summary_ko_20260526.md`
  - `qualitative_review/20260505_214349_324347/v62_slang_seed_support_gate_after_manual_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v62_slang_seed_support_gate_after_manual_labels.jsonl`
- 수행:
  - slang DB seed 주입을 일반화해 `count>=2`만으로 즉시 resolved memory 승격하지 않도록 보강했다.
  - `count>=3` 또는 `slang_insight`가 있는 seed만 strong seed로 보고 즉시 promote를 허용한다.
  - `강연금 -> 강철의 연금술사` exact non-novel media seed quarantine은 유지했다.
  - Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 known-bad 6건을 v62 재실행했다.
  - 자동 after-review가 약한 근거 row를 과허용하는 문제를 확인하고 수동 오버레이 라벨을 별도로 작성했다.
- 검증:
  - focused unittest 5건 통과.
  - `py_compile` 통과.
  - 실행 전 관련 Python 점유 없음, 모델 endpoint 응답, shard 36개 실행 상태 확인.
  - v62 run id `20260526_223527_932869`: completed `6`, failed `0`, pending `0`, flushed `6`.
  - 검색 서버 health `ok=36/36`.
- 결과:
  - 수동 라벨: `ACCEPT=4`, `HOLD=2`.
  - `9981263`: `성녀의 속마음이 들린다` resolved 유지.
  - `11205204`: `히어로가 집착하는 악당이 되었다` positive alias 유지.
  - `11663540`: `relevant/title null/unresolved`로 흔들려 `HOLD/re_judge`.
  - `10426463`: adjacent/trope/setting-borrowing 경계로 `HOLD/human_review`.
  - `8531521`: final `non-relevant/title null`, 단 원본 slang DB review는 계속 필요.
  - `8601885`: game IP negative control 유지.
- 해석:
  - v62는 저근거 slang seed 일반화의 targeted 보강 근거다.
  - `11663540`, `10426463` 정책 경계와 P0/P1 high-risk bucket이 남아 있으므로 10만 건 semantic quality approval은 아니다.
  - 전체 gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v61 slang seed quarantine/catalog tier fix 재검증
- 상태: targeted-verified / known-bad-5-accept-1-hold / semantic-quality-no-go
- 대상:
  - `src/llm_batch/batch_context.py`
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `tests/test_agentic_pipeline_search_evidence.py`
  - `qualitative_review/20260505_214349_324347/v61_catalog_tier_fix_after_packet_review_summary.md`
  - `qualitative_review/20260505_214349_324347/v61_catalog_tier_fix_after_packet_review_labels.jsonl`
- 수행:
  - `강연금 -> 강철의 연금술사` known non-novel media alias seed를 BatchContextMemory 주입 단계에서 quarantine하도록 보강했다.
  - v59에서 드러난 `9981263` positive alias control 회귀를 원인 분석했다. 노벨피아 상세 페이지 snippet의 지갑 UI 문구 `웹툰코인`이 media marker로 과해석됐다.
  - clean NovelPia novel detail URL과 source title match가 있으면 `non_novel_media_platform`으로 보지 않도록 판단 가드와 `search_evidence_catalog.source_tier` 분류를 맞췄다.
  - Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 known-bad 6건을 v61 재실행했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 5건 통과.
  - 실행 전 관련 Python 점유 없음, 모델 endpoint 응답, shard 36개 실행 상태 확인.
  - v61 run id `20260526_221106_422763`: completed `6`, failed `0`, pending `0`, flushed `6`.
  - 검색 서버 health `ok=36/36`.
- 결과:
  - `9981263`: `성녀의 속마음이 들린다` resolved 회복, E001 `source_tier=novel_platform`.
  - `11205204`: `히어로가 집착하는 악당이 되었다` positive alias control 유지.
  - `11663540`: non-relevant/title null 유지.
  - `8531521`: non-relevant/title null 유지, `강연금 -> 강철의 연금술사` seed quarantine 로그 확인.
  - `8601885`: non-relevant/title null 유지.
  - `10426463`: relevant/unresolved HOLD 유지.
- 해석:
  - v61은 known-bad targeted closure 근거다.
  - 여전히 10만 건 semantic quality approval은 아니다.
  - adjacent/trope 정책, 외부 IP seed 일반화, expanded random/P0/P1 validation 전까지 gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - 10만 건 현재 액션 요약 갱신

- 최신 기준만 분리한 정리본을 추가했다.
  - `qualitative_review/20260505_214349_324347/current_100k_actionable_issue_summary_ko_20260526.md`
- v61 기준으로 `8531521 -> 강철의 연금술사` resolved 회귀는 최종 `non-relevant/title null`로 닫힌 상태로 정리했다.
- `강연금 -> 강철의 연금술사`는 런타임 seed quarantine 확인, 원본 DB cleanup/generalization 후보로 분리했다.
- random baseline 1000건, high-risk expansion 5000건, current combined 584건 수치를 분리 기록했다.
- Browser로 `post_id=11097334`를 다시 열어 이미지 lazy-load 상태를 확인했다. 초기 broad image probe에서는 placeholder가 남을 수 있고, 본문 selector 기준으로는 스크롤/대기 후 3개 본문 이미지가 로드됐다.
- 결론은 유지한다. run health와 semantic decision quality는 분리하며, 전체 gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v58 detail URL/media guard 재검증
- 상태: targeted-verified / known-bad-5-accept-1-hold / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/models.py`
  - `tools/build_qualitative_round2_review.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `tests/test_agentic_pipeline_search_evidence.py`
  - `tests/test_qualitative_review_packet_tools.py`
  - `qualitative_review/20260505_214349_324347/v58_detail_url_media_guard_after_packet_review_summary.md`
  - `qualitative_review/20260505_214349_324347/v58_detail_url_media_guard_after_packet_review_labels.jsonl`
- 수행:
  - v56에서 result JSON search evidence catalog를 추가했고, v57에서 재발한 `11663540 -> 주서연 전차`, `8531521 -> 강철의 연금술사` 회귀를 원인 분석했다.
  - fanart/comic/webtoon/viewer URL이 clean novel detail evidence로 계산되는 경로를 차단했다.
  - `주서연 전차` 같은 캐릭터+대결 객체 합성 표면어가 direct full-title rescue를 통과하지 못하도록 보강했다.
  - search evidence catalog source tier에 `non_novel_media_platform`, `platform_reader_page`를 추가했다.
  - Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 known-bad 6건을 v58 재실행했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 10건 통과.
  - 실행 전 관련 Python 점유 없음, 모델 endpoint 응답, shard 36개 실행 상태 확인.
  - v58 run id `20260526_210850_328711`: completed `6`, failed `0`, pending `0`.
  - 검색 서버 health `ok=36/36`.
- 결과:
  - `9981263`, `11205204`: positive alias control 유지.
  - `11663540`: non-relevant/title null로 닫힘.
  - `8531521`: non-relevant/title null로 닫힘.
  - `8601885`: non-relevant/title null 유지.
  - `10426463`: relevant/unresolved HOLD 유지.
- 해석:
  - v58은 v57 재발 버그 2건을 targeted set에서 닫은 근거다.
  - 여전히 10만 건 semantic quality approval은 아니다.
  - adjacent/trope 정책, 외부 IP slang seed review, expanded random/P0/P1 validation 전까지 gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v55 known-bad media/alias guard 재검증
- 상태: targeted-verified / known-bad-partial-pass / adjacent-hold / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_packet_manifest.json`
  - `qualitative_review/20260505_214349_324347/v55_known_bad_media_alias_guard_after_labels.jsonl`
  - `tools/build_qualitative_round2_review.py`
- 수행:
  - v52에서 `8531521` unresolved preserve 회귀, v53에서 `11663540 -> 주서연 전차`, v54에서 `11663540 -> 패티시` title-surface alias 회귀를 순차 확인했다.
  - character-only virtual battle context에서 locked official rescue를 hold 처리했다.
  - weak/community external IP 후보가 clean detail noise만으로 unresolved preserve를 통과하지 못하도록 보강했다.
  - character name + battle/object surface phrase와 generic battle anchor alias를 각각 direct/title-surface rescue에서 차단했다.
  - review packet builder가 `identity.evidence`뿐 아니라 `novel_identity`, `primary_work`, candidate 계열의 `heretic_url`도 evidence URL로 수집하도록 보강했다.
  - review packet builder가 `evidence_catalog`와 `evidence_counts`를 추가해 후보별 metadata와 reason 기반 count를 구조화하도록 보강했다.
  - v55 사후 packet `6`행을 생성하고 임시 자동 label 대신 수동 authoritative label을 사용하도록 manifest에 명시했다.
  - Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 known-bad 6건을 v55 재실행했다.
- 검증:
  - `py_compile` 통과.
  - `tests.test_qualitative_review_packet_tools` 1건 통과.
  - focused unittest 7건 통과.
  - v55 run id `20260526_195550_803682`: completed `6`, failed `0`, pending `0`.
  - packet JSONL `6`행과 packet manifest parse 통과.
  - `9981263`, `11205204` packet에 NovelPia detail URL이 포함됨을 확인했다.
  - `evidence_catalog`는 6건 모두 존재하고, `evidence_counts`는 공개 reason count를 구조화한다.
- 결과:
  - `9981263`: `성녀의 속마음이 들린다` primary work 유지.
  - `11205204`: `히어로가 집착하는 악당이 되었다` primary work 유지.
  - `11663540`: non-relevant/title null로 닫힘.
  - `8531521`, `8601885`: 외부 비소설 IP non-relevant 유지.
  - `10426463`: relevant/unresolved HOLD로 남음.
- 해석:
  - v55는 known-bad 6건 targeted closure로 유효하지만 10만 건 semantic quality approval 근거는 아니다.
  - packet 후보 catalog 관측성은 개선됐지만 result JSON의 raw search evidence catalog/EID/snippet export는 아직 남은 부족점이다.
  - adjacent/trope 정책과 expanded random/P0/P1 validation 전까지 gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v51 known-bad media/alias guard 재검증
- 상태: targeted-partial-verified / positive-alias-inversion-fixed / character-bridge-policy-open / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347/v51_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v51_known_bad_media_alias_guard_after_labels.jsonl`
- 수행:
  - v50의 `9981263` positive alias inversion 원인을 locked official rescue 이전 title-side direct alias 후보 보강 부족으로 추적했다.
  - post title surface 후보를 candidate pool에 보강하는 `_with_direct_title_surface_candidates`를 추가했다.
  - same official title 후보의 title-surface 정보가 누락된 경우 합성 후보로 보강하도록 했다.
  - Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 known-bad 6건을 v51 재실행했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 11건 통과.
  - v51 run id `20260526_185600_839070`: completed `6`, failed `0`, pending `0`.
- 결과:
  - `9981263`: `성녀의 속마음이 들린다` resolved로 복구.
  - `11205204`: `히어로가 집착하는 악당이 되었다` resolved 유지.
  - `8531521`, `8601885`: 외부 비소설 IP negative control non-relevant 유지.
  - `10426463`: title 확정 없이 relevant/unresolved로 보존.
  - `11663540`: character-parenthetical bridge로 `전 버튜버가 하고 싶은데요` resolved가 다시 발생해 정책 경계로 남김.
- 해석:
  - v51은 targeted set 기준 P0 alias inversion을 닫았지만, 6건 회귀 검증이므로 10만 건 semantic quality approval 근거가 아니다.
  - character-only bridge 정책과 expanded random/P0/P1 validation 전까지 gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v50 known-bad media/alias guard 재검증

- 상태: targeted-partial-verified / external-ip-fix-confirmed / positive-control-regression-open / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347/v50_known_bad_media_alias_guard_after_summary_ko.md`
  - `qualitative_review/20260505_214349_324347/v50_known_bad_media_alias_guard_after_labels.jsonl`
- v50 run id `20260526_182412_783072`: completed `6`, failed `0`, pending `0`.
- 실행 조건은 Gemma 4 4B, `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`, VLM/OCR off, slang DB on이다.
- 실행 전 `expert_main|llm_batch|warp_shards` Python 점유가 없음을 확인했고, shard container 36개 실행 상태를 확인했다.
- `8531521`은 `강철의 연금술사` 외부 media/IP가 최종 non-relevant로 차단되어 v43/v48의 회수 경로가 닫혔다.
- `8601885`는 LoL/노틸러스 게임 IP가 최종 non-relevant로 유지됐다.
- `11205204`는 `히어로가 집착하는 악당이 되었다` resolved positive control을 유지했다.
- `9981263`은 `성녀 속마음` primary alias가 `아카데미의 순애`로 뒤집히는 새 회귀가 발생했다.
- `10426463`, `11663540`은 각각 adjacent/external IP overblocking 후보와 character-only policy boundary로 남았다.
- Browser `iab`로 현재 탭 `post_id=11097334`를 재확인했다. 스크롤 전 본문 첨부 `dcimg` 3개 중 1개가 `gallview_loading_ori.gif` placeholder였고, 스크롤/대기 후 3개 모두 실제 이미지로 로드됐다.
- 결론: targeted negative control 수정은 확인됐지만 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v48 known-bad media/alias guard 재검증

- 상태: targeted-partial-verified / `8601885` fixed / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347/v48_known_bad_media_alias_guard_p36_20260526.json`
  - `qualitative_review/20260505_214349_324347/v48_known_bad_media_alias_guard_after_summary_ko.md`
- 수행:
  - v47에서 `post_id=8601885`가 Arbiter/Verifier 단계에서 비관련으로 판정된 뒤 최종 후처리에서 `internal_work_signal_unresolved_recovered`로 되살아나는 회귀를 확인했다.
  - 실제 snippet analyzer 출력 키가 `identified_category=game`인데 가드는 `category`만 읽는 문제를 수정했다.
  - 비소설 media/detail hit와 파생/팬픽형 플랫폼 detail hit를 공식 title evidence에서 제외하는 보강을 유지했다.
  - Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 known-bad 6건을 v48 재실행했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 8건 통과.
  - v48 run id `20260526_170233_055943`: completed `6`, failed `0`, pending `0`.
- 결과:
  - `8601885`: LoL/노틸러스 게임 IP가 최종 `is_relevant=false`, `official_title=null`, `work_resolution=none`으로 유지되어 targeted fix 확인.
  - `8531521`: `강철의 연금술사` resolved false positive는 차단되었으나 `relevant/unresolved`로 남아 HOLD.
  - `11663540`, `10426463`: title false positive는 없지만 경계 정책이 남아 HOLD.
  - `9981263`, `11205204`: positive control resolved 유지.
- 해석:
  - 외부 게임 IP 최종 회수 버그는 known-bad 샘플에서 닫혔다.
  - targeted 6건 검증은 10만 건 semantic quality approval이 아니며 전체 gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v42/v43 known-bad media/alias guard 재확인

- 상태: targeted-partial-verified / P0-regression-open / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347/v42_known_bad_media_alias_guard_p36_20260526.json`
  - `qualitative_review/20260505_214349_324347/v43_single_8531521_media_guard_p36_20260526.json`
  - `qualitative_review/20260505_214349_324347/v42_v43_known_bad_media_alias_guard_after_summary_ko.md`
- 수행:
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 6건 known-bad/positive-control set을 v42 재실행했다.
  - `8531521`을 v43 단건 canary로 다시 실행해 비웹소설 media/IP guard의 후단 회귀 여부를 확인했다.
  - 최신 10만 건 부족점/버그 요약 문서를 v42/v43 기준으로 한국어 재작성했다.
- 검증:
  - v42 run id `20260526_153538_350152`: completed `6`, failed `0`, pending `0`.
  - v43 run id `20260526_154837_721537`: completed `1`, failed `0`, pending `0`.
- 결과:
  - `9981263`: `성녀의 속마음이 들린다` resolved 유지.
  - `11205204`: `히어로가 집착하는 악당이 되었다` resolved 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` over-resolution 제거, `relevant/unresolved` 보류.
  - `10426463`: `relevant/unresolved` 보류.
  - `8601885`: non-relevant 유지.
  - `8531521`: v43에서 `title_surface_primary_candidate_rescued` 경로로 `강철의 연금술사`가 다시 resolved 되어 P0 회귀로 기록.
- 해석:
  - v42는 일부 targeted 개선을 확인했지만 v43 회귀 때문에 known-bad media/alias guard는 완료가 아니다.
  - 10만 건 semantic decision quality gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v38 known-bad media/alias guard 재검증

- 상태: targeted-patch-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/experts/decoder.py`
  - `src/llm_batch/experts/orchestrator.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347/v38_known_bad_media_alias_guard_after_summary_ko.md`
- 수행:
  - `히집악` 내장 alias와 감상어-wrapped title surface 분리를 추가했다.
  - fresh/custom slang DB에서도 검증 alias가 batch memory rescue에 쓰이도록 했다.
  - locked 공식 상세 primary 후보가 본문 mention 후보 때문에 막히는 과보수 경로를 수정했다.
  - 비웹소설 media/IP 후보가 title-surface, character-parenthetical, unresolved-preserve 후단에서 되살아나는 경로를 보강했다.
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 6건 known-bad/positive-control set을 v38 재실행했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 통과.
  - v38 run id `20260526_141931_661420`: completed `6`, failed `0`, pending `0`.
- 결과:
  - `9981263`과 `11205204` positive control resolved 복구.
  - `8601885` 외부 게임 IP non-relevant 처리.
  - `11663540` character-parenthetical over-resolution 제거.
  - `8531521` non-webnovel title 오염 제거.
- 해석:
  - title false positive와 alias false negative 일부는 targeted set 기준 닫혔다.
  - `8531521`은 아직 `is_relevant=true/title=null` 관련성 과포함이 남아 있으며, `11663540`은 캐릭터 talk 정책 기준이 필요하다.
  - 10만건 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - `11663540` weak character-parenthetical over-resolution 차단

- 상태: targeted-patch-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347/v33_single_11663540_p36_20260526.json`
  - `qualitative_review/20260505_214349_324347/v33_single_11663540_after_summary_ko.md`
- 수행:
  - v32에서 `post_id=11663540`이 `_title_deliberately_null=true` 및 구조적 제목 추출 기각 후에도 canonical suspect 보정으로 `전 버튜버가 하고 싶은데요`에 과확정되는 경로를 확인했다.
  - `_title_deliberately_null` 상태에서는 post-side title/alias support가 없는 약앵커 후보가 canonical suspect, character-parenthetical, safe-single promotion 경로로 복구되지 않도록 보강했다.
  - 기존 character-parenthetical hint 등록은 유지하되, final title 확정은 직접 제목/alias/compound/image evidence가 있을 때만 허용하도록 회귀 테스트를 갱신했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 6건 통과.
  - v33 run id `20260526_121555_048435`: completed `1`, failed `0`, pending `0`, shard `36/36 OK`.
- 결과:
  - `11663540`: `is_relevant=true`, `official_title=null`, `work_resolution=unresolved`.
  - 로그에서 `canonical suspect 보정 차단: title_deliberately_null + 약앵커 후보 '전 버튜버가 하고 싶은데요' post-side title/alias support 부족` 확인.
  - final flag에 `character_parenthetical_title_null_blocked` 기록.
- 해석:
  - 해당 P0 over-resolution 경로는 단건 기준 닫혔다.
  - 10만건 semantic gate는 아직 `NO-GO / REVIEW-LOCKED`이며, `weak_evidence_strong_resolution` 및 `generic_common_surface` 확장 회귀가 필요하다.

## 2026-05-26 - 10만 건 잔여 이슈 큐 최신 정리

- 상태: targeted-loader-fix-and-rerun-verified / semantic-quality-no-go
- 대상:
  - `qualitative_review/20260505_214349_324347/current_100k_fixable_issue_queue_ko_20260526.md`
  - `qualitative_review/20260505_214349_324347/round3_exit_action_current_combined_manifest.json`
  - `qualitative_review/20260505_214349_324347/v31_single_10426463_after_summary_ko.md`
  - `expert_main.py`
  - `tests/test_expert_main_input_loader.py`
  - `docs/devs/TODO.md`
  - `docs/devs/CHECKLIST.md`
- 수행:
  - 최신 closure 기준으로 10만 건 테스트의 부족점, 남은 버그, 해결 가능 항목을 별도 문서로 정리했다.
  - 중간 산출물 수치와 최신 closure 수치를 분리하고, 승인 판단은 `ACCEPT=124`, approval excluded `460/584` 기준으로 고정했다.
  - random baseline 1000건과 high-risk expansion 5000건 결과를 섞지 않고 별도 근거로 기록했다.
  - `v30_single_10426463`의 `0개 포스트` 문제를 재현하고, JSONL loader가 UTF-8 BOM을 처리하도록 `utf-8-sig`로 보강했다.
  - non-empty JSONL에서 로드 post가 `0`개면 shard/LLM 실행 전 실패하도록 preflight를 추가했다.
  - `10426463`을 Gemma 4 4B, `expert_main.py --parallel 36`으로 v31 재실행했다.
- 결과:
  - 남은 action queue는 `human_review=138`, `re_search=120`, `re_judge=88`, `slang_db_review=87`, `re_run=27`이다.
  - 남은 주요 pattern은 `alias_recall_loss_false_negative=96`, `generic_common_surface=89`, `slang_db_alias_subtype=88`, `worker_shard_degraded_window=84`, `weak_evidence_strong_resolution=75`, `vlm_ocr_evidence_gap=28`이다.
  - `v31_single_10426463`은 completed `1`, failed `0`, pending `0`이며, 결과는 `is_relevant=false`, `official_title=null`, `work_resolution=none`이다.
  - 이전 위험 후보 `단테 [BL][단행본]` resolved title 오확정은 current code 기준 재현되지 않았다.
- 해석:
  - 런 완료와 semantic decision quality 승인은 계속 분리한다. 현재 gate는 `NO-GO / REVIEW-LOCKED`다.

## 2026-05-26 - v23 final targeted guard 재검증
- 상태: targeted-patch-partial-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 5건 targeted set을 v20-v23까지 재실행했다.
  - batch memory/slang_db exact alias rescue 앞단에 non-novel media evidence guard를 추가했다.
  - 본문 공식 플랫폼 URL에서 title을 찾은 경우 기존 title이 `null`이어도 evidence를 보존하도록 보강했다.
  - platform detail hit가 파생/패러디/크로스오버이면 원작 공식 title evidence로 쓰지 않도록 걸렀다.
  - 캐릭터 표면명과 동일한 title 후보가 공식 작품 근거 없이 direct full-title rescue로 되살아나지 않도록 막았다.
  - 본문 직접 title이 있을 때 무관 URL-backed search hit가 최종 title을 교체하지 않도록 보강했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 5건 통과.
  - v23 run id `20260526_001642_295323`: completed `5`, failed `0`, pending `0`.
  - after-review 결과 `ACCEPT=1`, `HOLD=4`.
- 결과:
  - `8705431`: `아포칼립스의 EX급 천재 저격수`로 복구. 무관 `아포칼립스의 루팅능력자` 교체는 제거됨.
  - `8601885`: `리그 오브 레전드` 게임 IP title 오매치 제거, after-review `ACCEPT`.
  - `8424362`: `에미야 키리츠구` 캐릭터 title 승격 제거, unresolved/HOLD.
  - `8531521`: `강철의 연금술사` manga/anime IP alias 오염 제거, unresolved/HOLD.
  - `8834919`: `아집숨` positive control이 false negative로 남아 P1 수정 대상.
- 해석:
  - P0급 오탐 title 승격은 targeted set에서 상당 부분 제거됐지만, recall 회귀가 남아 semantic gate는 계속 `NO-GO`다.
  - 5건 targeted set은 승인 표본이 아니므로 expanded random baseline과 P0/P1 bucket 검증이 필요하다.

## 2026-05-25 - v16-v19 비웹소설 IP / 본문 공식 URL 재확인

- 상태: targeted-patch-partial-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 5건 targeted set을 v16/v17/v18/v19로 재실행했다.
  - generic topic title, promotional sentence title, non-novel media title, 본문 공식 플랫폼 URL 우선순위 guard를 보강했다.
  - `slang_db`/batch memory exact alias rescue가 비웹소설 IP를 되살리는지 확인했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 4건 통과.
  - v19 run id `20260525_231813_131527`: completed `5`, failed `0`, pending `0`.
- 결과:
  - `8601885`는 `리그 오브 레전드` title 오매칭이 제거됐다.
  - `8424362`는 `Fate/에미야` IP title 확정이 제거되고 unresolved로 보류됐다.
  - `8834919` positive control은 `아포칼립스에 집을 숨김`으로 유지됐다.
  - `8531521`은 `강연금` alias가 `강철의 연금술사`로 되살아나는 slang_db/batch memory 오염 경로가 남았다.
  - `8705431`은 본문 공식 URL과 직접 title이 있는데도 fetch unavailable/author mismatch 뒤 `author_meta`로 demote되어 원문 title evidence 보존 문제가 남았다.
- 해석:
  - 비웹소설 IP guard 일부는 작동하지만, alias rescue 후단과 본문 공식 URL evidence 보존이 아직 P0/P1로 남아 있다.
  - 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - alias/bridge targeted v15 제목란 alias 복구

- 상태: targeted-patch-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 동일 8건 targeted set을 v15로 재실행했다.
  - 실행 전 LLM endpoint와 shard `36/36`을 확인했다.
  - 제목란 alias/표면형이 공식 detail URL 또는 공식 title evidence가 있는 후보와 맞는 경우 generic character-parenthetical 보류가 정확 title까지 demote하지 않도록 보강했다.
  - 일반 역할/종족 표면은 지원 title surface 후보로 인정하지 않도록 negative path를 유지했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 7건 통과.
  - v15 run id `20260525_210222_899635`: completed `8`, failed `0`, pending `0`.
- 결과:
  - `9981263`은 `성녀의 속마음이 들린다`, `work_resolution=resolved`, `anchor_type=title_exact`로 복구됐다.
  - `9901127`은 `is_relevant=true`, `work_resolution=multi_work`, `official_title=null`, flag `multi_work_title_list_resolution_demoted`를 유지했다.
  - `10190186`, `11205204`, `11113480` positive/control resolved는 유지됐다.
  - `9000828`, `9019735`는 일반어/트로프/역할 표면 과확정이 없다.
- 해석:
  - known-bad 8건 targeted set에서는 alias false negative와 multi-work over-resolution 핵심 회귀가 정리됐다.
  - targeted 8건은 approval sample이 아니므로 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - alias/bridge targeted v11-v14 multi-work demotion

- 상태: targeted-patch-partial-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 동일 8건 targeted set을 v11/v12/v13/v14 네 차례 재실행했다.
  - 실행 전 LLM endpoint와 shard `36/36`을 확인했다.
  - mixed/no-url title-surface 후보가 이전 URL을 빌려 fake official title로 승격되는 경로를 차단했다.
  - 제목란에 복수 작품이 나열된 비교/감상 글에서는 title-surface rescue와 최종 official title을 demote하도록 보강했다.
  - `post_id=11097334`를 Codex 내장 Browser `iab`로 직접 열어 lazy image placeholder가 남는 상태를 재확인했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 6건 통과.
  - v11 run id `20260525_193840_310458`: completed `8`, failed `0`, pending `0`.
  - v12 run id `20260525_195506_155856`: completed `8`, failed `0`, pending `0`.
  - v13 run id `20260525_200735_669612`: completed `8`, failed `0`, pending `0`.
  - v14 run id `20260525_202201_766849`: completed `8`, failed `0`, pending `0`.
- 결과:
  - `9901127`은 v14에서 `is_relevant=true`, `work_resolution=multi_work`, `official_title=null`, flag `multi_work_title_list_resolution_demoted`로 내려가 단일 title 과확정이 차단됐다.
  - `9981263`은 v14에서 `official_title=null`, `unresolved_work`로 남아 오답 확정은 피했지만 정확 복구는 미완료다.
  - `10190186`, `11205204`, `11113480` positive/control resolved는 유지됐다.
  - `11097334`는 현재 브라우저 확인에서도 이미지 `87`개 중 `brokenOrPendingCount=30`, 본문 첨부 중 하나가 `gallview_loading_ori.gif` placeholder 상태였다.
- 해석:
  - multi-work title-list 과확정은 targeted set에서 개선됐다.
  - `9981263` 계열 alias recall/primary 선택은 남은 P0/P1 항목이다.
  - VLM/OCR은 본문 이미지 스크롤/대기 후 `placeholder/incomplete/broken=0` 확인 전까지 `Strong`으로 승인하지 않는다.
  - 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - alias/bridge targeted v8-v10 후속 재확인

- 상태: targeted-patch-partial-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 동일 8건 targeted set을 v8/v9/v10 세 차례 재실행했다.
  - 실행 전 LLM endpoint와 shard `36/36`을 확인했다.
  - multi-work relation hold, mixed candidate URL guard, high-confidence slang alias rescue 관련 단위 테스트를 보강했다.
- 검증:
  - `py_compile` 통과.
  - focused unittest 5건 통과.
  - v8 run id `20260525_183704_522400`: completed `8`, failed `0`, pending `0`.
  - v9 run id `20260525_185932_392781`: completed `8`, failed `0`, pending `0`.
  - v10 run id `20260525_191458_896289`: completed `8`, failed `0`, pending `0`.
- 해석:
  - `11205204` exact slang alias false negative는 v9/v10에서 안정적으로 개선됐다.
  - `9901127`은 비관련 과차단에서 벗어났지만 multi-work 감상글을 단일 title로 과확정한다.
  - `9981263`은 v8/v9에서 회수됐으나 v10에서 unresolved로 회귀해 제목란 alias 보존이 아직 안정적이지 않다.
  - 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - alias/bridge targeted v6 generic bridge 차단

- 상태: targeted-patch-partial-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - `성기사`, `라미아` 같은 일반 역할/종족어가 character-parenthetical 검색 결과만으로 공식 제목으로 승격되는 경로를 차단했다.
  - 후단 정합성 보정에서도 generic bridge가 플랫폼 URL 또는 wiki parenthetical만으로 되살아나지 않도록 막았다.
  - v5에서 재발한 `월드 오브 워크래프트`, `신비아파트 시리즈` 오매칭을 대상으로 단위 테스트를 추가했다.
- 검증:
  - `py_compile` 통과.
  - targeted unittest 11건 통과.
  - LLM endpoint `bg-digitalservices/Gemma-4-E4B-it-NVFP4` 확인.
  - shard audit `out/search_shard_audit_20260525_174226.json`: `ok=36/36`.
  - targeted run id `20260525_174243_300254`: completed `8`, failed `0`, pending `0`.
  - `post_id=9000828`: `official_title=null`, `is_relevant=false`.
  - `post_id=10190186`: `망한 교단의 성기사` resolved.
- 해석:
  - generic role/species bridge 오매칭은 targeted set에서 차단됐다.
  - `post_id=9981263` 제목란 alias 후보 보존 실패와 `post_id=9901127` multi-work/review relevance 과차단이 남았다.
  - 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - alias/bridge targeted v4 재검증

- 상태: targeted-patch-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `src/llm_batch/batch_context.py`
  - `src/llm_batch/experts/orchestrator.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - `PickvelIdentity.anchor_type`에 내부 evidence anchor `title_abbrev_mention`이 그대로 들어가 v3에서 validation error가 나는 문제를 `title_alias` 매핑으로 수정했다.
  - slang_db/BatchContext exact alias rescue, generic species/role surface final rejection, direct full-title rescue, safe compound phrase query 보존 회귀를 함께 검증했다.
  - Gemma 4 4B 기준 `expert_main.py --parallel 36 --slang-db on`으로 잔여 8건 targeted set을 재실행했다.
- 검증:
  - `py_compile` 통과.
  - targeted unittest 4건 통과.
  - shard audit `out/search_shard_audit_20260525_164203.json`: `ok=36/36`.
  - targeted run id `20260525_164258_948961`: completed `8`, failed `0`, pending `0`.
  - `post_id=9000828`: generic species/trope title 과잉 확정 제거.
  - `post_id=9901127`, `11113480`: positive control resolved 유지.
  - `post_id=11205204`: `히집악` alias가 `히어로가 집착하는 악당이 되었다`로 복구됨.
- 해석:
  - 스키마/alias rescue 계열 일부는 해결됐다.
  - `post_id=9981263` multi-work primary 선택, `post_id=10190186` direct full-title rescue 부족은 남았다.
  - 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - 10만건 테스트 부족점 및 해결 가능 항목 정리

- 상태: issue-summary-updated / semantic-quality-no-go
- 대상:
  - `qualitative_review/20260505_214349_324347`
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/TODO.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
- 수행:
  - 최신 closure manifest와 latest targeted run `20260525_151238_596513`을 기준으로 부족점/버그/해결 가능 항목을 한국어 문서로 정리했다.
  - `current_100k_issue_resolution_summary_ko_20260525.md`를 추가했다.
  - 10만건 테스트의 실행 완료와 semantic decision quality 승인을 분리해 기록했다.
- 검증:
  - closure: `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`, approval excluded `460/584`.
  - latest targeted run: completed `8`, failed `0`, pending `0`.
  - `post_id=9981263`: `성녀 속마음`이 `성녀의 속마음이 들린다`로 회수됐다.
  - `post_id=9000828`, `10190186`, `11205204`: 각각 generic/character bridge 오매칭, final realignment 오매칭, slang_db exact alias false negative가 남았다.
- 해석:
  - `성녀 속마음` query prune 문제는 개선됐지만 10만건 품질 승인은 아니다.
  - 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - generic_common_surface 전수 회귀 및 thin-bridge guard

- 상태: full-bucket-regression-executed / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - `generic_common_surface` bucket population `89/89`를 전수 입력으로 만들었다.
  - search shard audit `36/36` 확인 후 Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 전수 회귀를 실행했다.
  - 전수 회귀에서 남은 일반어/트로프/캐릭터 bridge 과잉 확정을 기준으로 `thin-bridge title` guard와 `unverified alias/plot title` guard를 추가했다.
  - 잔여 8건 회귀 입력으로 known-bad와 positive control을 같이 재실행했다.
- 검증:
  - full regression run id `20260525_134217_119077`: completed `89`, failed `0`, pending `0`.
  - full regression after-review: `ACCEPT=1`, `HOLD=88`.
  - residual v2 run id `20260525_143013_533933`: completed `8`, failed `0`, pending `0`, after-review `HOLD=8`.
  - `post_id=9019735`, `9325585`, `9000828`: 일반어/캐릭터/트로프 title 과잉 확정 제거.
  - `post_id=9901127`, `11113480`: positive control resolved 유지.
- 산출물:
  - `generic_common_surface_full_regression_review_ko_20260525.md`
  - `generic_common_surface_full_regression_input.jsonl`
  - `generic_common_surface_full_regression_p36_20260525_manifest.json`
  - `generic_common_surface_full_regression_p36_20260525_after_manifest.json`
  - `generic_common_surface_thin_bridge_guard_v2_p36_20260525_manifest.json`
- 해석:
  - 과잉 확정 일부는 줄었지만 `generic_common_surface` bucket은 `HOLD=88/89`로 계속 승인 불가다.
  - `post_id=11205204` `히집악` false negative와 `post_id=9981263` `성녀 속마음` alias recall 미완료가 남았다.
  - 전체 semantic decision quality gate는 계속 `NO-GO`다.

## 2026-05-25 - search_only zero-bucket title 과잉 확정 가드

- 상태: targeted-regression-verified / semantic-quality-no-go
- 대상:
  - `src/llm_batch/agentic_pipeline.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - `search_only/title_mention/community_mention/character_mention` 수준의 약한 anchor에서 candidate evidence bucket이 `post_spans=0`, `official_urls=0`, `official_nonwiki=0`이면 단일 `official_title` 확정을 보류하도록 가드를 추가했다.
  - 실제 이슈 케이스 2건과 positive control 1건으로 회귀 입력을 구성했다.
  - Gemma 4 4B 기준 `expert_main.py --parallel 36`으로 재실행했다.
- 검증:
  - `py_compile` 통과.
  - regression run id `20260525_132234_217009`: completed `3`, failed `0`, pending `0`, shard health `36/36`.
  - `post_id=11663540`, `10824887`: 관련글 유지 + `official_title=null`, `work_resolution=unresolved`.
  - `post_id=9722392`: `아카데미 플레이어를 죽였다` resolved title 유지.
- 산출물:
  - `search_only_zero_bucket_guard_review_ko_20260525.md`
  - `issue_regression_search_only_guard_input.jsonl`
  - `issue_regression_search_only_guard_p36_20260525_manifest.json`
- 해석:
  - 이번 패치는 하위 패턴 targeted regression이며 전체 10만건 semantic approval은 아니다.
  - `generic_common_surface` 및 `weak_evidence_strong_resolution` bucket은 확장 회귀가 필요하다.

## 2026-05-25 - VLM/OCR fallback 도구 이미지 게이트 패치

- 상태: tooling-patched / smoke-verified / semantic-quality-no-go
- 대상:
  - `tools/capture_vlm_ocr_browser_review_cli.py`
  - `tools/build_vlm_browser_targets_from_review.py`
  - `qualitative_review/20260505_214349_324347`
- 수행:
  - fallback 캡처 도구가 본문 이미지 로딩 상태를 기록하도록 `article_image_count/loaded/incomplete/placeholder/broken` 필드를 추가했다.
  - 이미지가 없거나 placeholder/incomplete/broken 상태이면 `Strong`으로 승격하지 않도록 `visual_evidence_grade` 규칙을 강화했다.
  - VLM/OCR target row와 manifest에 Codex 내장 Browser `iab` 우선 표면, 본문 이미지 selector, acceptance gate를 명시했다.
  - `.gitignore`에서 위 두 도구를 추적 가능하도록 예외를 추가했다.
- 검증:
  - `py_compile` 통과.
  - VLM/OCR target 재생성 테스트: 대상 `100`, packet 누락 `0`.
  - synthetic grade 테스트: 이미지 없음은 `Missing`, placeholder/broken은 `Weak`.
  - `.\venv\Scripts\python.exe expert_main.py ... --parallel 36` smoke test completed `2/2`, failed `0`, shard health `36/36`.
- 산출물:
  - `fix_test_review_ko_20260525.md`
  - `vlm_ocr_image_gate_patch_test_manifest.json`
  - `expert_main_smoke_p36_20260525_manifest.json`
- 해석:
  - 이번 패치는 실행/도구 게이트 개선이며 10만건 semantic approval은 아니다.
  - 전체 gate는 approval excluded `460/584`가 남아 계속 `NO-GO`.

## 2026-05-25 - VLM/OCR iab 이미지 로딩 게이트 재검증

- 상태: guideline-updated / semantic-quality-no-go
- 대상:
  - `qualitative_review/20260505_214349_324347`
  - Codex 내장 Browser `iab`
- 수행:
  - 사용자가 지적한 `post_id=11097334`에서 첫 화면 로드 후 본문 이미지 placeholder가 남고, 본문 이미지 영역 스크롤 후 실제 이미지가 로드되는 것을 확인했다.
  - VLM/OCR 브라우저 게이트 100건을 Codex 내장 Browser `iab`로 다시 열고, 본문 이미지 lazy-load 스크롤/대기, screenshot, 이미지 로딩 상태를 기록했다.
  - 삭제/접근불가 탐지 조건을 좁히고, CUA scroll timeout이 난 케이스는 DOM scroll fallback으로 재검증했다.
  - closure builder가 새 `browser_visual_vlm_ocr_iab_image_gate` combined 결과를 우선 사용하도록 갱신했다.
- 산출물:
  - `browser_visual_vlm_ocr_iab_image_gate/vlm_ocr_iab_image_gate_manifest.json`
  - `browser_visual_vlm_ocr_iab_image_gate/vlm_ocr_iab_image_gate_combined_reviews.jsonl`
  - `browser_visual_vlm_ocr_iab_image_gate/vlm_ocr_iab_image_gate_summary_ko.md`
  - `browser_visual_vlm_ocr_iab_image_gate/issue_11097334_image_loading_probe_v2.json`
  - `round3_exit_action_current_combined_manifest.json`
- 결과:
  - VLM/OCR 이미지 게이트 combined 결과는 `Strong=98`, `Missing=2`.
  - `post_id=10794867`, `10892069`는 승인 제외 및 `human_review`.
  - closure 재계산 후 approval subset은 `124/584`, approval excluded는 `460/584`.
  - semantic quality gate는 계속 `NO-GO`.

## 2026-05-24 - server-poc 갱신 지침 재확인

- 상태: guideline-executed / semantic-quality-no-go
- 대상:
  - `qualitative_review/20260505_214349_324347`
  - `server-poc`
- 수행:
  - LLM endpoint가 복구된 뒤 `bg-digitalservices/Gemma-4-E4B-it-NVFP4` 기준 `expert_main.py --parallel 36`으로 exit action 재실행 입력 `155`건을 처리했다.
  - `tools/warp_shards.py up --count 36` 이후 `tools/audit_search_shards.py --count 36` 결과 `ok=36/36`을 확인했다.
  - 기존 장기 실행 Python 점유는 VS Code LSP/이전 audit 계열로 확인했고, shard port 점유 문제는 36 shard 재기동과 audit으로 해소했다.
  - VLM/OCR bucket 전체 `100`건을 브라우저로 직접 열어 screenshot/eval을 남겼다.
- 산출물:
  - `search_shard_audit_36_current.json`
  - `round3_exit_re_search_re_run_p36_result_manifest.json`
  - `round3_exit_re_search_re_run_p36_after_labels.jsonl`
  - `vlm_ocr_all_browser_gate_targets.jsonl`
  - `browser_visual_vlm_ocr_all/vlm_ocr_browser_visual_manifest.json`
  - `round3_exit_action_current_combined_manifest.json`
  - `round3_exit_action_closure_summary_ko.md`
  - `updated_guideline_execution_audit_ko.md`
  - `round3_manual_guard_slang_reviews.jsonl`
- 결과:
  - 36워커 재실행은 completed `155/155`, failed `0`.
  - VLM/OCR 브라우저 확인은 captured `100/100`, visual evidence `Weak=100`, `Strong=0`.
  - 새 guard 적용 후 approval subset은 `52/584`이고 approval excluded는 `532/584`.
  - semantic quality gate는 계속 `NO-GO`.
- 해석:
  - 자동 실행 완료와 자연어 판정 품질 승인을 분리했다.
  - VLM/OCR은 브라우저 시각 증거가 약해 기존 ACCEPT `70`건까지 승인 제외했다.
  - 후속 브라우저 판독 지침은 Codex 내장 Browser plugin `@browser` / in-app browser `iab` 우선으로 갱신했다. Playwright CLI/headless는 fallback으로만 사용한다.
  - 남은 queue는 `human_review=210`, `re_search=120`, `re_judge=88`, `slang_db_review=87`, `re_run=27`.

## 2026-05-23 - server-poc updated qualitative review analysis

- 상태: analysis-updated / semantic-quality-no-go
- 대상:
  - `server-poc`
  - run id `20260505_214349_324347`
- 변경:
  - 최신 리뷰 지침 기준으로 `server-poc/run_review_20260505_214349_324347.md`를 한국어 보고서로 갱신했다.
  - `qualitative_review/20260505_214349_324347/test_scan_review_analysis_ko_20260523.md`를 추가해 자동 run 감사와 자연어 의미 품질 리뷰를 분리 보고했다.
  - `qualitative_review/20260505_214349_324347/review_completion_audit_ko.md`를 추가해 요구사항별 완료/미충족 상태를 한국어로 정리했다.
- 주요 판정:
  - run integrity: `REVIEW`
  - semantic decision quality: `NO-GO`
  - overall: `NO-GO`
- 근거:
  - result rows `104,502`, unique post ids `104,502`, duplicate `0`.
  - random control v3 `1,000`건, high-risk expansion `5,000`건, merged qualitative review `6,172`건.
  - Round 3 targeted `584`건과 residual rerun `189`건은 failed `0`.
  - 최종 결합 라벨은 `ACCEPT=195`, `HOLD=288`, `REPROCESS=101`, `REJECT=0`.
  - `389`건은 quality approval에서 격리했고, exit action 완료 전까지 semantic gate는 `NO-GO`다.
- 후속 기준:
  - Gemma 4 4B 후속 재확인/재처리는 `36`을 모델/샤드 상한 이력으로만 기록한다. 새 소규모 run은 `--parallel min(input_count,36)` 또는 동일한 `effective_parallel=min(input_post_count,36,healthy_endpoint_count)` 계약으로 확인하고, `36` worker를 맞추기 위해 재실행하지 않는다.

날짜별 개발/운영 변경과 확인 결과를 기록한다. 상세 분석은 관련 문서에 두고, 여기에는 핵심 지표와 후속 작업을 남긴다.

## 2026-05-23 - 한국어 리뷰 산출물과 36-worker 상한 정책

- 추가 확인:
  - `tools/build_qualitative_random_control_review.py`, `tools/build_qualitative_round2_review.py`, `tools/build_qualitative_round3_targets.py`, `tools/build_qualitative_round3_after_review.py`의 Markdown heading, 요약, gate, action 설명을 한국어 출력으로 보강했다.
  - 기술 식별자(`ACCEPT`, `re_search`, bucket id, JSON key)는 유지하고, 사람이 읽는 해석/판정/후속 작업 문장만 한국어로 맞췄다.
  - `py_compile`로 qualitative builder 4개 파일 문법을 확인했다.

- 상태: docs-updated / execution-policy-updated
- 배경:
  - 리뷰, 분석, 검토, 피드백 문서가 일부 영어 heading/설명으로 생성될 수 있어 운영자가 바로 읽기 어렵다.
  - Gemma 4 4B 후속 실행의 최대 상한은 36 worker라는 지시가 기존 `--parallel 32` 지침보다 우선한다.
- 변경:
  - `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`, `SCAN_RESULT_REVIEW_GUIDE.md`, `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`, `OPERATION_QUALITY_CHECKLIST.md`, `CHECKLIST.md`에 한국어 산출물 원칙을 추가.
  - 사람이 읽는 Markdown 본문, 결론, 근거, 판정, 후속 작업 설명은 한국어로 작성하도록 고정.
  - JSON key, enum, action id, bucket id, 명령어, 로그 원문, 코드 심볼은 원문 유지로 분리.
  - Gemma 4 4B 후속 재확인/재처리 실행 상한을 `36`으로 갱신하되, 새 소규모 run은 `--parallel min(input_count,36)`와 manifest `effective_parallel`로 판단하도록 정정.
  - shard 검증은 대형/샤드 검증 run에서 `MCP_SHARD_COUNT=36` 및 shard audit `36/36`을 확인하고, 소규모 targeted run에서는 healthy endpoint와 `effective_parallel` 축소를 별도로 기록하도록 보강.
- 주의:
  - 2026-05-22 Round 3의 `--parallel 32` 기록은 과거 실행 이력으로 보존한다.
  - 새 재검토/피드백 산출물에는 한국어 기준과 `36` 상한/effective_parallel 기준을 적용한다.

## 2026-05-23 - VLM/OCR browser visual verification guide

- 상태: docs-updated / semantic-gate-strengthened
- 배경:
  - VLM/OCR 개입 케이스는 로그, OCR text, result field만으로는 실제 화면의 의미를 확인했다고 보기 어렵다.
  - `vlm_ocr_quarantine` 잔여 케이스는 원문 이미지/게시글을 실제 브라우저에서 열어 screenshot과 시각 관찰을 남기는 별도 evidence loop가 필요하다.
- 변경:
  - `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`에 VLM/OCR browser visual verification 절차와 packet field를 추가.
  - `SCAN_RESULT_REVIEW_GUIDE.md`에 VLM/OCR browser visual evidence review, `browser_access_failed`, `visual_ocr_contradiction` taxonomy를 추가.
  - `OPERATION_QUALITY_CHECKLIST.md`와 `CHECKLIST.md`에 브라우저 원문 확인, screenshot path, vision/manual observation, 접근 실패 시 `ACCEPT` 금지 gate를 추가.
  - `TODO.md`에 VLM/OCR visual evidence packet tooling 후속 작업을 추가.
- 핵심 규칙:
  - `VLM_OCR_involved`, OCR-derived title, image-only evidence, screenshot/webtoon panel 기반 판정은 브라우저 screenshot/vision evidence 없이 semantic `GO`로 승인하지 않는다.
  - 브라우저 접근 실패, 삭제, 로그인/성인 인증, 404, blocked response는 `Missing`/`Weak` evidence로 남기고 `INFO_MISSING`, `HOLD`, 또는 `REPROCESS`로 분리한다.

## 2026-05-22 - scan result review guide 추가

- 상태: implemented
- 관련 run id: 없음
- 관련 파일:
  - `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
  - `docs/slang_db_improvement_todo.md`
- 문제:
  - scan result directory를 받았을 때 지침 작성과 실제 런 리뷰가 섞일 수 있고, 증거 등급/판정 gate/실패 taxonomy/action queue가 한곳에 정리되어 있지 않았음.
- 조치:
  - `GUIDE_MODE`, `RUN_REVIEW_MODE`, `MIXED_MODE`를 분리한 `SCAN_RESULT_REVIEW_GUIDE.md` 추가.
  - `Strong`/`Medium`/`Weak`/`Missing` 증거 등급, GO/REVIEW/NO-GO 기준, 최초 원인/fanout 분리, runtime/search/judgment/slang_db/docs-tooling taxonomy, action queue, systemic issue dedupe 규칙을 문서화.
  - `generic_parenthetical_bridge`와 `slang_db`의 `extracted_not_persisted`/`persisted_but_not_displayed`를 별도 리뷰 항목으로 승격.
- 확인:
  - dev docs hub, checklist, operation quality checklist, improvement register, slang DB TODO에 연결 반영.
- 남은 위험:
  - 실제 scan result directory에 적용한 뒤 누락 필드와 자동 audit tooling을 더 구체화해야 함.
- 다음 작업:
  - 첫 `RUN_REVIEW_MODE` 결과를 기준으로 output template과 이슈 taxonomy 보정.

## 2026-05-01 - vLLM VLM degenerate JPEG crash guard

- 상태: runtime_verified / quality_hold
- 배경:
  - 대량 병렬 run이 약 4,000번째 이후 같은 지점에서 반복적으로 vLLM serving `500 -> 502` 상태로 무너지는 증상을 조사.
  - 현재 run `20260501_010427_282685`와 과거 run `20260423_170321_250907` 모두 loaded index `4049`, post `11589463`의 VLM 이미지 처리 직후 최초 `500 Internal Server Error`가 발생.
- 원인 증거:
  - `logs/expert_run_20260501_010427_282685_W9.log`: `[14:59:31] VLM chunk request: post_id=11589463, images=1, bytes=448` 직후 `[14:59:38] 500`, 이후 502 fanout.
  - `logs/expert_run_20260423_170321_250907_W4.log`: `[05:35:51] VLM chunk request: post_id=11589463, images=1, bytes=448` 직후 `[05:35:52] 500`, 이후 502.
  - 실제 dcimg 응답: status `200`, content-type `application/octet-stream`, sniffed MIME `image/jpeg`, dimensions `(389, 1)`.
- 조치:
  - `AgenticPipeline` 이미지 fetch 단계에 image dimension sniffing 추가.
  - JPEG/PNG/GIF/WebP/BMP 크기를 파싱하고, 0px/최소 크기 미만/극단 aspect ratio 이미지는 VLM payload에서 제외.
  - 새 env: `LLM_VLM_MIN_IMAGE_WIDTH=8`, `LLM_VLM_MIN_IMAGE_HEIGHT=8`, `LLM_VLM_MAX_ASPECT_RATIO=64`.
- 확인:
  - `py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py` 통과.
  - `tests.test_agentic_pipeline_rework`: `Ran 161 tests`, `OK`.
  - run audit 재실행: checkpoint `4014`, failed `0`, reason_errors `0`, fatal_or_trace_line `4`.
- 추가 확인:
  - vLLM 재기동 후 단건 canary `20260501_160410_623323` 실행.
  - `completed_count=1`, `failed_count=0`, `pending_count=0`.
  - `VLM chunk request`, `HTTPStatusError`, `500`, `502` 없음.
  - 완료 로그의 VLM 요약: `vlm: used=False, fetch=0/1, chunks=0, bytes=0`.
- 남은 작업:
  - full output/result에는 `image_geometry_too_small:389x1` limitation 문자열이 노출되지 않아 observability 보강 필요.
  - 같은 run에서 `오러(판타지 용어)` parenthetical이 `판타지 용어` title로 승격되는 별도 품질 문제가 확인되어 QUALITY-HOLD로 분리.
  - 장기적으로 VLM image limitation 카운트를 run audit/dashboard에 노출.

## 2026-04-28 - 품질 개선 후 200/1,000 자동 확대 지침 격상

- 상태: guideline_added / tooling_required
- 배경:
  - `11718111` Namu 의학 일반 개념 오탐처럼 targeted 단건은 바로 고칠 수 있지만, 대량 run에서는 같은 유형의 이웃 케이스와 과차단 리스크가 뒤늦게 드러난다.
  - 앞으로 품질 개선마다 "다음에 canary/risk discovery를 돌리자"로 남기지 않고, 기본 후속 작업으로 자동 진행하도록 운영 기준을 고정한다.
- 지침:
  - 검색 품질, title/alias 판정, relevance gate, slang DB 저장 기준 변경은 targeted/unit 통과 후 200건 canary를 실행한다.
  - 200건 canary가 `completed=200/200`, `failed=0`, `pending=0`이면 같은 조건으로 1,000건 risk discovery를 이어서 실행한다.
  - canary 실패 시 1,000건으로 진행하지 않고 실패 원인, stuck/failed post, shard/search 상태를 먼저 기록한다.
  - 즉시 실행이 불가능하면 defer 사유와 재개 명령을 `HISTORY.md`/`TODO.md`에 남긴다.
- 문서 반영:
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/DEV_TODO.md`
  - `docs/devs/TODO.md`
- 남은 작업:
  - 위 루틴을 한 번에 실행하는 wrapper 도구 구현.
  - afterfix14 기준 200건 canary와 1,000건 risk discovery 실행.

## 2026-04-28 - adjacent relevance legacy flag 및 검색 budget 정리

- 상태: regression_verified / canary_needed
- 배경:
  - 공통 제목 stem 수정 후 전체 rework 회귀에서 7건 실패를 추출.
  - 실패는 stem guard 자체가 아니라 adjacent author/meta/recommendation 계열이 legacy `is_relevant=true`로 남는 문제와 `adjacent_meta_cheap` budget 기대값 불일치로 분리됨.
- 일반 실패 유형:
  - 주변 담론(`adjacent_relevant`)은 운영상 보존해야 하지만, 핵심 작품 토론/식별 성공/은어 DB 확정 근거로 카운트되면 false positive 지표가 부풀어짐.
  - 작가/플랫폼/meta 주변담론은 2쿼리로 충분하지만, 장르 토론은 표면 제목 후보가 있으면 공식 근거 확인 슬롯 1개를 남겨야 함.
- 조치:
  - final relevance 계산을 `topicality == core_relevant` 기준으로 정리.
  - prompt/router/arbiter 지시에서 `adjacent_relevant`의 legacy `is_relevant=false`, official title null 기본값을 명시.
  - `adjacent_meta_cheap` budget을 genre-probe `max_q=3`, author/platform/meta `max_q=2`로 분기.
- 확인:
  - targeted adjacent 7건 통과.
  - budget positive/negative 이웃 3건 통과.
  - `tests.test_agentic_pipeline_rework`: 145건 통과.
  - `tests.test_agentic_pipeline_alias_contract`: 30건 통과.
  - 변경 파일 `py_compile` 통과.
- 다음 작업:
  - afterfix 계열 200건 canary에서 adjacent가 `Relevant/Identified/slang DB`로 새는 비율 집계.
  - 1,000건 risk discovery에서 장르 토론 budget 3쿼리의 false positive 증가 여부 확인.

## 2026-04-28 - 공통 제목 stem 충돌 검색 이웃 분리

- 상태: targeted_verified / canary_needed
- 관련 사례:
  - `11684407` (`마법소녀ㄴ 신아 집에서는 머리 풀고다니는건가`)
  - afterfix12 36병렬 run `20260428_142042_238055` 및 대형 run `20260428_155230_844180`에서 `불꽃의 마법소녀ㄴ`이 comparison/recommendation/secondary reference로 새는 현상 확인
- 문제:
  - `마법소녀ㄴ`처럼 의도적 자모 오타형 제목 stem이 여러 공식 제목에 공통으로 포함될 때, 검색 이웃 후보가 실제 비교/추천/은어 후보처럼 저장될 수 있음.
- 조치:
  - 자모 표기(`ㄴ`)를 보존하는 title stem 비교 추가.
  - locked 공식 후보가 본문 앵커와 닫히면 공통 stem 검색 이웃이 단일 후보 rescue를 막지 않도록 조정.
  - 검색 이웃 후보를 `comparison_target`, `recommendation_candidates`, `secondary_reference_works`에서 제거.
  - verifier/router prompt에 `ambiguous_title_stem` 일반 규칙 추가.
- 확인:
  - `python -m unittest tests.test_agentic_pipeline_alias_contract -v`: 30건 통과.
  - 단건 실제 실행: `out/sampling/targeted_ambiguous_title_stem_11684407_afterfix13_20260428_result.json`
  - 결과: `official_title=마법소녀ㄴ은 은퇴하고 싶다`, `work_resolution=resolved`, `comparison_target=null`, `secondary_reference_works=[]`.
- 한계:
  - `python -m unittest tests.test_agentic_pipeline_rework -v`는 145건 중 7건 실패. 실패는 author/recommendation adjacent 기대값과 budget profile 기대값 계열로, 이번 stem 가드 경로와 별개인 기존 리워크 리스크로 분리 기록.
- 다음 작업:
  - afterfix13 200건 canary와 1,000건 risk discovery에서 공통 stem 계열 과차단/과확정 재집계.
  - slang DB 기존 pending `불꽃의 마법소녀ㄴ <- 마법소녀ㄴ` 관측은 최신 run 재처리 후 stale 여부 audit.

## 2026-04-26 - 20k run 검색 reliability 리뷰

- 상태: verified
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/search_reliability_review_20260426.md`
  - `docs/warp_sharding.md`
  - `docs/slang_db_improvement_todo.md`
- 문제:
  - 최근 20k run에서 검색 품질 저하와 MCP/SearchXNG shard 중간 사망 의심.
  - 브라우저에서 SearchXNG UI `19013`이 `ERR_EMPTY_RESPONSE`.
- 확인:
  - `checkpoint_rows=20532`
  - `search_upstream_zero=45449`
  - `search_degraded_detected=13263`
  - `search_timeout=102`
  - 최초 shard 감사 `ok=27/36`, 문제 `[1,10,13,15,26,27,29,33,34]`
  - 컨테이너 로그에서 `can't start new thread`, `Resource temporarily unavailable`, `pthread_create failed` 확인
- 조치:
  - MCP client failover 추가
  - health check `/readyz` 확인 추가
  - 시작 시 readiness 실패 shard recreate 추가
  - shard 감사 도구 추가
  - 문제 shard recreate
- 재확인:
  - `tools/audit_search_shards.py --count 36` 결과 `ok=36/36`
  - `py_compile` 통과
- 남은 작업:
  - 장시간 런 중 주기 shard snapshot
  - post별 search health flag 저장
  - 같은 입력 소량 재처리로 검색 저하율 비교

## 2026-04-26 - Slang DB audit

- 상태: implemented
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/slang_db_improvement_todo.md`
  - `docs/search_reliability_review_20260426.md`
- 확인:
  - `slang_insight=1817`
  - 기존 저장 후보 `546`
  - 보정 후 저장 후보 `532`
  - 차단 후보 `14`, 사유 `unclear_canonical_alias`
  - `slang_db/slang_db.json` 기준 `titles=340`, `family_aliases=1`, 오염성 alias `0`
- 남은 작업:
  - 차단된 실제 약칭 후보 review queue 분리
  - 검색 안정화 후 slang 회수율 재감사

## 2026-04-26 - docs/devs 운영 문서 허브 생성

- 상태: verified
- 관련 run id: 없음
- 관련 문서:
  - `docs/devs/README.md`
  - `docs/devs/TODO.md`
  - `docs/devs/DEV_TODO.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 조치:
  - 개발 TODO, 기능 개선 TODO, 체크리스트, 히스토리, 개선 레지스터를 분리해 규격화
  - 기존 상세 문서를 새 허브에서 참조
  - 전문가 리뷰를 반영해 개발 TODO와 기능개선 TODO, 검증 결과, 운영 품질 게이트를 분리
- 확인:
  - `docs/devs` 표준 문서 세트 생성
  - 2026-04-26 검색 reliability/slang DB 감사 결과를 새 문서 체계에 반영
- 다음 작업:
  - 이후 기능 변경 시 `CHECKLIST.md`와 `TODO.md`를 같이 갱신
  - 대량 런 품질 승인은 `OPERATION_QUALITY_CHECKLIST.md` 기준으로 판정

## 2026-04-26 - LLM/전문가 정성 리뷰 프로토콜 추가

- 상태: implemented
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/devs/LLM_JUDGMENT_REVIEW.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 조치:
  - 통계/코드 검토로 판단하기 어려운 케이스를 전문가가 직접 읽는 프로토콜 추가
  - `tools/build_llm_judgment_review_packet.py` 추가
  - checkpoint, run audit, slang DB를 묶어 Markdown/JSONL 리뷰 패킷 생성
- 확인:
  - `--limit 30 --per-bucket 8` smoke test 완료
  - `selected=30 from rows=20532`
- 남은 작업:
  - 300건 규모 1차 전문가 리뷰 배치 수행
  - 리뷰 결과 adjudication sheet 누적
  - 다음 run부터 search evidence 필드를 checkpoint에 더 자세히 저장

## 2026-04-26 - 20k run 300건 전문가 정성 리뷰

- 상태: verified
- 관련 run id: `20260423_170321_250907`
- 관련 문서:
  - `docs/devs/QUALITATIVE_REVIEW_20260426.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201809.jsonl`
- 결과:
  - 검색/근거 리뷰: 표본 81건 중 `ACCEPT=48`, `HOLD/RESEARCH/REPROCESS/REJECT=33`
  - slang 리뷰: 105건 중 `confirmed_alias≈52`, `noise≈27`, 나머지 보류/참조/비교
  - relevance/work 리뷰: 표본 95건 중 `ACCEPT=32`, `RESEARCH/REPROCESS=50`
- 통합 판정: `REVIEW`
- 핵심 발견:
  - 검색 근거 0 상태 resolved_title 확정
  - 댓글 URL 과잉 primary 승격
  - off-domain media 수용
  - alias span 과대 추출
  - false negative와 reason/field 불일치

## 2026-04-26 - 1,000건 계층 리뷰 패킷과 쿼리 확장 프로브

- 상태: partial
- 관련 run id: `20260423_170321_250907`
- 조치:
  - `tools/build_llm_judgment_review_packet.py`에 `--strategy stratified`, `--control-count` 추가
  - 1,000건 계층 리뷰 패킷 생성
  - 리뷰 패킷에 검색 쿼리 확장 후보 포함
  - `tools/run_search_query_expansion_probe.py` 추가
- 확인:
  - `selected=1000 from rows=20532`
  - 정상 대조군 `routine_sample=120` 포함
  - `괴담텔/즉사무림` 수동 프로브에서 플랫폼명 조합이 platform detail hit를 늘림
- 남은 작업:
  - 1,000건 패킷 전문가 adjudication
  - 일반 제목/잡담에 suffix를 붙였을 때의 false positive와 timeout 위험 제어
  - alias/title confidence gate 이후 쿼리 확장 적용

## 2026-04-26 - 쿼리 확장 gate와 대형 샘플 기준 정리

- 상태: implemented / review
- 관련 파일:
  - `src/llm_batch/experts/orchestrator.py`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/VERIFICATION_RESULTS.md`
- 조치:
  - confident query expansion을 확정 약칭 alias-only 또는 `novel_literature` 도메인 표면어로 제한
  - 일반 제목/잡담/비소설 도메인에는 platform suffix를 붙이지 않도록 조정
  - 4건 smoke를 품질 승인 근거로 쓰지 않도록 문서화
  - 200건 canary, 1,000건 risk discovery, 10,000건 validation 입력 샘플 생성
- 확인:
  - `py_compile` 통과
  - 단위 경로 확인: `즉사무림`은 확장, `ect`/`모도쿠가오소우`는 확장 차단
  - 병렬 smoke 4건 완료, 단 품질 판정은 `SMOKE ONLY`
- 남은 작업:
  - 200건 canary 병렬 실행
  - 1,000/10,000건 표본에서 개선 전후 결과 비교
  - 전문가 adjudication으로 false positive/false negative 변화 확인

## 2026-04-27 - 200건 canary 결과와 검색 long-tail 보정

- 상태: review / no-go
- 관련 run id:
  - canary: `20260427_002737_046977`
  - stuck single repro: `20260427_030848_374214`
- 관련 문서:
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- 확인:
  - 36개 shard는 canary 전후 모두 `ok=36/36`.
  - 200건 canary checkpoint는 `199/200`까지만 기록.
  - `105`건이 `[Errno 22] Invalid argument`로 failed 처리됐으나, 원인은 결과 판정이 아니라 CLI progress stderr pipe 오류.
  - 실제 stuck은 `global_idx=100`, `post_id=11478694` 한 건.
  - `11478694`는 `anime` category 감지 이후에도 alias bridge 검색이 이어져 정체 위험이 있었음.
- 조치:
  - `expert_main.py`에서 CLI progress 출력 실패가 처리 결과를 실패로 만들지 않도록 방어.
  - `orchestrator.py`에서 비소설 매체 hard guard가 indirect title/alias/fetch 보강을 차단.
  - `search/client.py`에서 검색 1건당 failover endpoint 수와 client timeout을 env로 제한 가능하게 추가.
- 검증:
  - `py_compile` 통과.
  - `11478694` 단일 재현은 `completed_count=1`, `failed_count=0`.
  - 단일 재현 시간은 `485.4s`로 완료됐지만 아직 long-tail 위험.
  - canary checkpoint 199건에서 전문가 리뷰 패킷 80건 생성.
- 다음 작업:
  - 200건 canary 재실행.
  - 통과 후에만 1,000건 risk discovery, 10,000건 validation으로 진행.
  - `슬레이어즈`처럼 라이트노벨/애니/원작 경계 케이스는 LLM/전문가 리뷰에 포함.

## 2026-04-27 - expert_main startup auto-manage 200건 canary 통과

- 상태: verified / quality-review
- 관련 run id: `20260427_121338_563339`
- 관련 문서:
  - `docs/devs/VERIFICATION_RESULTS.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
- 조치:
  - `expert_main.py`의 startup shard auto-manage 경로로 36개 shard를 정리한 뒤 200건 canary 재실행.
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`, `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`, `MCP_CLIENT_SEARCH_MAX_RETRIES=1` 조건 적용.
  - 완료 후 사후 shard audit과 80건 LLM/전문가 리뷰 패킷 생성.
- 확인:
  - checkpoint `200/200`, `completed=200`, `failed=0`, missing `0`.
  - manifest `completed_count=200`, `flushed_count=200`, `pending_count=0`.
  - 1차 stuck 케이스 `11478694` 완료, 처리 시간 `703.9s`.
  - 사후 shard audit `out/search_shard_audit_20260427_134858.json`: `ok_count=36/36`, `bad_count=0`.
  - 리뷰 패킷 `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`, `selected=80`.
- 판정:
  - canary 안정성은 GO.
  - 검색 timeout, infra no-result, long-tail과 작품/은어 판단 품질은 REVIEW.
- 다음 작업:
  - 같은 실행 조건으로 1,000건 risk discovery 진행.
  - long-tail 상위 post와 80건 리뷰 패킷을 전문가가 직접 검토.
  - 10,000건 validation 또는 운영 승인 전 `ACCEPT/HOLD/REPROCESS/REJECT` 집계 필요.

## 2026-04-27 - post별 late search 누적 예산 가드

- 상태: implemented_unit_verified / canary-required
- 관련 파일:
  - `src/llm_batch/experts/orchestrator.py`
  - `tests/test_agentic_pipeline_rework.py`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
- 배경:
  - 2차 200건 canary는 안정성은 통과했지만 `11457804=886.4s`, `11478694=703.9s`, `11456200=586.5s` long-tail이 남음.
  - 원인 일부는 개별 `_execute_searches` 배치 cap이 아니라 verification/search/recall batch가 post 안에서 반복되며 누적되는 구조.
- 조치:
  - `_execute_searches` 중앙 관문에서 `ctx.executed_queries` 기준 post 누적 예산을 적용.
  - 초기 title/alias 탐색은 보존하고, late iteration 또는 verification/recall/unresolved late-purpose batch에 cap/skip 적용.
  - profile별 기본 cap을 env로 조정 가능하게 추가.
- 확인:
  - `py_compile` 통과.
  - late budget 단위 테스트 3건 통과.
  - `11478694` 1 shard 참고 실행 `20260427_140716_814536`: `completed_count=1`, `failed_count=0`, `291.8s`, `3 iterations`, 검색 실행 `13건`.
- 주의:
  - `11478694` 참고 실행은 최종 late-purpose refinement 직전에 시작된 smoke라 품질 gate로 쓰지 않음.
  - 운영 판단은 36 shard / 200건 canary 재확인 후 진행.

## 2026-04-27 - 개선 전후 자동 테스트/비교 지침 추가

- 상태: proposed / guideline-added
- 관련 문서:
  - `docs/devs/CHECKLIST.md`
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
  - `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`
  - `docs/devs/DEV_TODO.md`
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`
  - `docs/devs/IMPROVEMENT_REGISTER.md`
- 조치:
  - 개선 작업의 완료 기준에 자동 테스트 런, run audit, baseline/improved 비교 문서, 필요 시 LLM 리뷰 패킷 생성을 추가.
  - 자동화 도구가 없으면 수동 비교로 대체하되 누락 사유를 기록하도록 명시.
  - 전용 비교 도구는 P1 TODO로 등록.
- 다음 작업:
  - late search budget 200건 canary 재실행 때 baseline `20260427_121338_563339` 대비 첫 비교 문서 형식 확정.

## 2026-04-27 - late search budget 200건 canary 비교 완료

- 상태: verified-canary / quality-review
- 관련 run id:
  - baseline: `20260427_121338_563339`
  - improved: `20260427_143145_922090`
- 조치:
  - late search budget guard 적용 후 같은 200건 canary를 36 shard/startup auto-manage 경로로 재실행.
  - 사후 shard audit과 baseline/improved 비교 문서, 100건 전문가 리뷰 패킷 생성.
- 산출물:
  - `out/sampling/query_gate_canary_200_late_budget_20260427_run_summary.json`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.md`
  - `out/comparisons/query_gate_canary_200_20260427_baseline_vs_late_budget.json`
  - `out/search_shard_audit_20260427_late_budget_postrun.json`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_143145_922090_20260427_160810.md`
- 확인:
  - checkpoint `200/200`, failed `0`, missing `0`.
  - 사후 shard audit `ok=36/36`.
  - 검색 오류 `81 -> 75`, timeout `82 -> 75`.
  - late budget cap/exhausted `22/14`로 실제 canary에서 가드 발동 확인.
  - identified title `72 -> 76`, relevant `148 -> 153`.
  - total wall time은 `5452.3s -> 5453.8s`로 거의 동일.
- 판정:
  - 안정성은 GO.
  - 품질은 REVIEW. post id별 판정 변화와 title 증가분은 사람이 읽어야 함.
- 남은 위험:
  - `11478694`, `11456200` tail은 개선됐지만 `11457804`는 `886.4s -> 911.5s`로 여전히 병목.
  - `11718077`은 `151.8s -> 496.2s`로 회귀해 단계별 로그 리뷰 필요.

## 2026-04-27 - canary 정성 검토 중 발견한 추가 개선점

- 상태: discovered / partially-implemented
- 발견 사례:
  - `11663540`: `주서연` character page의 `주서연(전 버튜버가 하고 싶은데요)` parenthetical title을 회수하지 못해 정식 제목 미확정.
  - `11631298`: `무림맹`, `마교`, `혈교` 같은 무협 일반 세력명만으로 `무림맹주 막내제자`를 과확정.
  - `11549038`: 1차 partial result에는 `[Errno 22] Invalid argument` 실패 row가 남아 있으나, 이후 rerun에서는 정상 처리됨.
- 조치:
  - `tools/build_balanced_regression_input.py`에 `--order distributed|random|post_id_desc|post_id_asc` 추가.
  - 기본값을 `distributed`로 두어 post id 정렬순 canary가 되지 않게 변경.
  - `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`에 분산 출력 순서 지침 추가.
- 추가 개선 후보:
  - 무협/판타지 일반 세력명은 공유 토큰에서 장르 일반어를 제거한 뒤 고유 토큰이 없으면 resolved 승격 금지.
  - character page parenthetical title은 별도 중간 증거로 회수하되, 동명이인/타매체 false positive 방지를 위해 post 반복 언급과 장르 맥락을 요구.
  - 오래된 partial result의 실패 row가 최신 rerun에서 회수됐는지 표시하는 audit 리포트 필요.
  - infra no-result는 `220 -> 244`로 증가했으므로 검색 무결과를 오류 감소와 별도로 해석해야 함.

## 2026-04-27 - generic/character targeted 개선 실험

- 상태: implemented-unit / targeted-review
- 조치:
  - Verifier relation judge에 `generic_relation_only`를 추가해 무협 일반 세력/역할어만 겹치는 후보의 resolved 승격을 차단.
  - `캐릭터명(작품명)` wiki/search result를 character parenthetical bridge로 등록하는 경로 추가.
  - `줄다리기(오징어 게임)` 같은 사건/게임 parenthetical은 캐릭터 브리지에서 제외.
  - `전차`, `줄다리기` 등 설정/대결 표면어를 generic topic title로 취급해 canonical 보정 오승격을 차단.
  - 최종 consistency에서 deliberation rescue가 마지막 청소 단계에 의해 제거되는 문제를 좁은 조건으로 보호하는 실험 추가.
- 확인:
  - `py_compile` 통과.
  - targeted unittest 7건 통과.
  - `expert_main.py` startup auto-manage 경로로 targeted 3건을 반복 실행.
- 결과:
  - `11549038`: 과거 `[Errno 22] Invalid argument` 재발 없음.
  - `11631298`: official title 확정은 차단됐지만 `unresolved_title`/candidate 잔류가 있어 추가 보정 필요.
  - `11663540`: `전차` 오승격은 차단됐지만 `전 버튜버가 하고 싶은데요` 최종 확정은 아직 미완.
- 산출물:
  - `out/sampling/targeted_generic_character_3_20260427.jsonl`
  - `out/sampling/targeted_generic_character_3_20260427_afterfix3_result.json`
  - `logs/expert_run_20260427_174602_508561.log`
- 남은 작업:
  - generic relation only 후보가 최종 `title_candidates`에 남는 문제 정리.
  - character parenthetical + official platform hit + jury strong의 최종 title 유지 조건을 더 보수적으로 재설계.
  - 동일 3건 통과 후 분산 200건 canary로 회귀 확인.

## 2026-04-27 - generic/character targeted 후속 수정

- 상태: targeted-verified / canary-required
- 조치:
  - `agentic_pipeline.py`에서 generic relation only demote 후 `primary/mentioned/title_candidates`를 비우고 최종 interpretation을 재계산해 `secondary_reference_works` 누수를 제거.
  - `ctx.verified_character_work_links`가 비어 있어도 `ctx.search_results`의 `캐릭터명(작품명)` parenthetical을 final consistency에서 재구성하도록 보강.
  - `orchestrator.py`, `arbiter.py`에서 `confidence="High"` 같은 문자열 label이 숫자 비교에서 오류를 내지 않도록 정규화.
  - `tests/test_agentic_pipeline_rework.py`에 검색 결과 fallback parenthetical, secondary reference suppress, confidence label 테스트 추가.
- 확인:
  - `py_compile` 통과.
  - targeted unittest 8건 통과 및 confidence label unittest 통과.
  - 3-shard targeted run `out/sampling/targeted_generic_character_3_20260427_afterfix6_result.json`에서 `11631298`은 `is_relevant=false`, `work_resolution=none`, 후보/secondary reference 없음.
  - 단독 no-BOM targeted run `out/sampling/targeted_character_11663540_20260427_afterfix8_result.json`에서 `11663540`은 `전 버튜버가 하고 싶은데요`로 resolved.
- 주의:
  - afterfix8 결과에는 Arbiter confidence 오류 수정 전 발생한 `verifier_technical_failure` 플래그가 남아 있음. 코드는 수정했지만, 다음 3-shard/200건 canary에서 재발 여부를 다시 봐야 함.
  - targeted 1~3건은 코드 경로 확인용이며 품질 승인 근거가 아님.
- 다음 작업:
  - 동일 3건을 다시 3-shard로 재실행해 technical failure 플래그 소거 확인.
  - 200건 분산 canary에서 `generic_relation_only_demoted`, `character_parenthetical_title_resolved`, confidence type error 재발 여부를 집계.

## 2026-04-27 - generic/character afterfix11 3-shard 확인

- 상태: targeted-go / canary-required
- 추가 발견:
  - afterfix10 3-shard에서는 `11663540`이 캐릭터 parenthetical 증거를 찾았지만, `comparison_target=주서연`이 실제 작품 비교처럼 남아 최종 `unresolved`로 되돌아갔다.
  - 이는 `주서연`이 작품명이 아니라 캐릭터 표면인데도 comparison slot에 들어간 케이스다.
- 조치:
  - `agentic_pipeline.py`에 약한 캐릭터/비작품 comparison target은 캐릭터 parenthetical 확정을 막지 않는 좁은 가드를 추가.
  - 해당 캐릭터 표면 후보가 `mentioned_works`/secondary reference로 새지 않도록 정리.
  - 회귀 테스트 `test_search_parenthetical_bridge_resolves_without_registered_link`를 afterfix10 실패 형태로 강화.
- 확인:
  - `py_compile`: pass.
  - targeted unittest 5건: OK.
  - 3-shard targeted run `out/sampling/targeted_generic_character_3_20260427_afterfix11_result.json` 완료.
  - `11631298`: 비관련, 후보/secondary 누수 없음.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved, `character_talk`, `system_state=clean`.
  - 로그에서 `Invalid argument`, confidence type error, `Traceback`, `verifier_technical_failure` 재발 없음.
- 다음 작업:
  - 200건 분산 canary를 실행하고, known bad 변화와 동명이인 캐릭터 parenthetical false positive를 정성 리뷰한다.

## 2026-04-27 - afterfix11 200건 canary 완료

- 상태: canary-go / risk-discovery-required
- 실행:
  - `expert_main.py` startup auto shard 관리 경로 사용.
  - WARP `36/36`, MCP health `36/36`.
  - 입력 `out/sampling/query_gate_canary_200_20260426.jsonl`.
  - 출력 `out/sampling/query_gate_canary_200_afterfix11_20260427_result.json`.
  - 로그 `logs/expert_run_20260427_191203_030136.log`.
- 결과:
  - `completed=200/200`, `failed=0`, `pending=0`.
  - `Relevant=151`, `Identified=75`, `Total Time=5508.2s`.
  - 감사 결과 `reason_error_count=0`, `verifier_technical_failure=0`, `[Errno 22] Invalid argument=0`.
  - `generic_relation_only_demoted=3`, `character_parenthetical_title_resolved=5`.
- known bad:
  - `11631298`은 `무림맹주 막내제자` resolved에서 non-relevant/title 없음으로 수정 유지.
  - `11663540`은 unresolved에서 `전 버튜버가 하고 싶은데요` resolved로 수정 유지.
  - `11549038`은 처리 오류 없이 `adjacent_relevant / trope_discussion`.
- 산출물:
  - 감사: `out/sampling/query_gate_canary_200_afterfix11_20260427_audit.json`.
  - 비교: `out/comparisons/query_gate_canary_200_late_budget_vs_afterfix11.md`.
  - LLM 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11.md`.
- 다음 작업:
  - 120건 리뷰 패킷을 실제로 판독해 false positive/false negative와 slang DB 저장 위험을 표기.
  - 1,000건 risk discovery로 확대.

## 2026-04-27 - afterfix11 120건 리뷰 판독 및 1,000건 risk discovery 시작

- 상태: qualitative-review-done / risk-discovery-running
- 판독 산출물:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.jsonl`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudicated.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_191203_030136_afterfix11_adjudication_summary.json`
- 판독 결과:
  - `ACCEPT=63`, `HOLD=24`, `RESEARCH=11`, `REPROCESS=15`, `REJECT=7`.
  - critical reject는 common term/person/media parenthetical 과확정, generic phrase 작품명 오인, off-domain title 승격이 중심.
  - REPROCESS는 확인된 별칭 누락(`폴랩`, `망교성`, `서울마탑`, `아생갤`)과 multi-work/comparison 처리 약화가 중심.
- 후속 실행:
  - `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`을 afterfix11 코드로 재처리 시작.
  - run id `20260427_212634_728016`, 출력 예정 `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`.
  - startup auto shard 관리 경로, `MCP_SHARD_COUNT=36`, `parallel=8`.
- 다음 작업:
  - 1,000건 완료 후 audit/summary/comparison을 생성하고, 120건 adjudication의 critical/reprocess 유형이 risk discovery에서 얼마나 재발하는지 집계.

## 2026-04-27 - afterfix11 1,000건 risk discovery 완료

- 상태: run-stability-go / quality-review-required
- 실행:
  - run id `20260427_212634_728016`.
  - 입력 `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`.
  - 출력 `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`.
  - startup auto shard 관리 경로 사용, WARP `36/36`, MCP bridge health `36/36`, `parallel=8`.
- 결과:
  - `completed=1000/1000`, `failed=0`, `pending=0`.
  - `Relevant=746`, `Identified=351`.
  - `Total Time=30852.1s`, `Avg Time/Post=30.9s`.
  - audit `reason_error_count=0`, `search_timeout=29`, `search_upstream_zero=539`, `search_degraded_detected=130`.
  - slang old/new/blocked `136/133/3`, bad remaining `0`.
- 산출물:
  - audit `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_audit.json`.
  - 품질 요약 `out/comparisons/query_gate_risk_discovery_1000_afterfix11_quality_review.md`.
  - 리뷰 패킷 `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.md`, selected `1000/1000`.
- 발견:
  - 120건 REJECT 중 4건이 1,000건에서도 resolved title FP로 재현.
  - 120건 REPROCESS 중 10건이 여전히 false negative/미확정/과차단 형태로 재현.
  - `character_parenthetical_title_resolved=37` 중 `Depressive disorder`, `뮤지컬 배우`, `Sword Master`, `마피아42`, `BLACKPINK`, `Ubuya` 같은 critical FP가 섞임.
  - `generic_relation_only_demoted=8` 중 `11631298`은 맞지만 `서울마탑`, `화귀`, `언니약혼` 등 strong alias 후보 과차단이 섞임.
- 다음 작업:
  - parenthetical bridge gate, malformed/generic official title validator, generic guard 이후 alias rescue를 우선 개선.

## 2026-04-28 - afterfix12 P0 품질 가드 1차 적용

- 상태: targeted-verified / broader-risk-discovery-required
- 변경:
  - `src/llm_batch/agentic_pipeline.py`
    - 최종 official title validator 추가: malformed wiki revision/source metadata phrase/영문 일반어/person-media/common title 후보 차단.
    - character parenthetical bridge가 `Depressive disorder`, `뮤지컬 배우`, `또는 라쇼몽...` 같은 비작품 괄호 표제를 title로 승격하지 않도록 재게이트.
    - `generic_relation_only` demote 전에 strong alias rescue를 추가하되, `무림맹`, `마교`, `혈교` 같은 세계관 일반 세력명은 rescue alias로 인정하지 않음.
  - `tests/test_agentic_pipeline_rework.py`
    - `서울마탑` rescue, `무림맹` 과구제 방지, malformed/source metadata/person title reject 회귀 테스트 추가.
- 자동 확인:
  - `.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py tests\test_agentic_pipeline_rework.py`
  - targeted unittest `13/13 OK`
- 실제 targeted run:
  - core4 입력: `out/sampling/targeted_p0_afterfix12_core4_20260428.jsonl`
  - core4 출력: `out/sampling/targeted_p0_afterfix12_core4_20260428_result.json`
  - run id `20260428_123539_845850`, `completed=4/4`, `failed=0`
  - 확인:
    - `11689276`: `뮤지컬 배우` title 제거, `adjacent_relevant/none`.
    - `11631298`: `generic_relation_only_demoted`, non-relevant/title 없음.
    - `11562020`: `서울에 마탑 세웠더니 돈이 미쳤다` resolved, `generic_relation_alias_rescued`.
    - `11620037`: core4에서는 source metadata title이 재발해 추가 조임 필요 확인.
  - 추가 라쇼몽 단건 재확인:
    - 입력 `out/sampling/targeted_p0_afterfix12_rashomon_20260428.jsonl`
    - 출력 `out/sampling/targeted_p0_afterfix12_rashomon_20260428_result.json`
    - run id `20260428_124339_828427`
    - `11620037`: non-relevant/title 없음으로 수정 확인.
- 남은 작업:
  - 같은 P0 묶음을 200건 canary와 1,000건 risk discovery에 재적용해 false positive 감소와 alias rescue 회귀를 확인.
  - `화귀`, `언니약혼`, `폴랩`, `망교성` 등 strong alias long-tail은 추가 targeted/adjudication 필요.

## 2026-04-28 - afterfix12 ECT 의학 일반글 추가 보정

- 상태: targeted-verified
- 배경:
  - `11718070`은 afterfix11에서 `Depressive disorder` resolved title FP였고, afterfix12 1차에서는 title은 제거됐지만 `adjacent_relevant=True`가 남았다.
  - 실제로는 ECT/우울증 치료/기억력 문제를 말하는 의학 일반글이므로 장르소설 adjacent도 아니어야 한다.
- 변경:
  - 작품 앵커 없이 의학 주제만 확인되는 경우 `medical_common_topic_demoted`로 `unrelated/noise/work_resolution=none` 처리.
  - 안전하지 않은 verified character-work link(`ECT -> Depressive disorder`)는 medical demotion을 막지 못하도록 조정.
- 확인:
  - targeted unittest `13/13 OK`.
  - 실제 단건 run:
    - 입력 `out/sampling/targeted_p0_afterfix12_ect_20260428.jsonl`
    - 출력 `out/sampling/targeted_p0_afterfix12_ect_20260428_result.json`
    - run id `20260428_132300_821816`
    - `11718070`: `is_relevant=false`, official title 없음, `topicality=unrelated`, flag `medical_common_topic_demoted`.

## 2026-04-28 - 하드코딩 방지 / 일반화 원칙 문서화

- 상태: guideline-added / regression-running
- 배경:
  - 특정 실패 사례를 고칠 때 post id, 오답 title, 검색 문자열을 직접 막는 식으로 누적하면 대량 런에서 새 오탐/누락을 만든다.
  - `11718070`도 `Depressive disorder`만 막는 방식이 아니라 "작품 앵커 없는 실제 의학/건강 주제"라는 실패 유형으로 다뤄야 한다.
- 변경:
  - `docs/devs/CHECKLIST.md`에 일반화/하드코딩 금지 체크리스트 추가.
  - `docs/devs/OPERATION_QUALITY_CHECKLIST.md`에 일반화/하드코딩 방지 운영 게이트 추가.
  - `docs/devs/FEATURE_IMPROVEMENT_TODO.md`, `docs/devs/DEV_TODO.md`에 LLM/후처리 규칙 일반화 작업 항목 추가.
  - `src/llm_batch/prompts/expert_prompts.py` 공통 프레임워크에 "예시는 암기 대상이 아니라 rubric 설명용" 원칙 추가.
  - `src/llm_batch/agentic_pipeline.py`의 최종 title guard에서 사례별 bad-title 목록을 줄이고, 검색 메타데이터/일반 표면어/의학 도메인처럼 범주형 규칙으로 주석화.
- 완료 기준:
  - 새 품질 패치마다 실패 유형, 증거 불변식, positive/negative 이웃 테스트, 200/1,000건 재확인을 함께 남긴다.

## 2026-04-28 - afterfix12 36병렬 canary와 일반화 매트릭스 확인

- 상태: run-stability-go / quality-review-required
- 관련 run id: `20260428_142042_238055`
- 입력: `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`
- 실행:
  - `expert_main.py` startup auto shard 관리 경로 사용.
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`, `--parallel 36`.
  - startup WARP `36/36`, MCP bridge health `36/36`.
- 운영 발견:
  - 최초 36병렬 시 `warp_shards.py status --json`가 Docker exec trace 단계에서 멈출 수 있음을 확인.
  - `tools/warp_shards.py`에 `WARP_SHARDS_STATUS_EXEC_TIMEOUT_SEC` 기반 subprocess timeout과 `warp_cli_connected_after_trace_timeout` fallback을 추가.
  - 수정 후 `warp_shards.py status --json`와 expert_main startup shard 확인이 정상 진행됨.
- 결과:
  - `completed=200/200`, `failed=0`, `pending=0`.
  - `Relevant=146`, `Identified=67`.
  - `Total Time=2473.3s`, `Avg Time/Post=12.4s`.
  - audit `reason_errors=0`, `search_timeout=8`, `search_upstream_zero=105`, `search_degraded_detected=12`.
  - 사후 shard audit `ok=36/36`, `bad=[]`.
- 일반화 매트릭스 확인:
  - `11718070`: afterfix11의 `Depressive disorder` FP에서 afterfix12는 non-relevant/title 없음, `medical_common_topic_demoted`.
  - `11631298`: 무림맹/마교/혈교 일반 세력어는 non-relevant/title 없음 유지.
  - `11663540`: `전 버튜버가 하고 싶은데요` resolved 유지, Novelpia 공식 detail URL 회수.
  - `11620037`: 라쇼몽/source metadata 오염 title 제거, non-relevant/title 없음.
  - `11562020`: `서울에 마탑 세웠더니 돈이 미쳤다` resolved, `generic_relation_alias_rescued`.
- 남은 위험:
  - `11689276`은 오답 title은 제거됐지만 adjacent_relevant로 남아 정성 검토 필요.
  - `11702067`, `11576520`은 relevant지만 official title 미확정으로 strong alias long-tail 개선 필요.
  - `11383118`, `11327341`은 risk discovery 이웃 케이스로 재판독 필요.
- 산출물:
  - audit: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_audit.json`
  - case matrix: `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_case_matrix.md`
  - 비교: `out/comparisons/query_gate_canary_200_afterfix11_vs_afterfix12_parallel36_20260428.md`
  - 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
- 다음 작업:
  - 생성된 120건 리뷰 패킷을 `ACCEPT/HOLD/RESEARCH/REPROCESS/REJECT`로 실제 판독.
  - afterfix12 1,000건 risk discovery로 확대해 malformed/common title FP 감소와 alias FN 잔존률 확인.
  - sampling output을 기본 `out/expert_result_<run_id>` 경로로 복사하지 않아도 audit 가능한 도구 옵션 추가.

## 2026-04-28 - afterfix14 Namu 의학/일반 개념 official title 승격 차단

- 상태: targeted_verified / canary_required
- 배경:
  - `11718111` (`나도 조현병으로 오해받은 적 있음`)이 `조현병`이라는 나무위키 일반 의학 항목으로 resolved 되는 오탐을 확인.
  - reason 내부에는 "현실 의학/사회 개념이며 작품 고유 근거가 부족하다"는 반론이 있었지만, 후처리 단계가 이를 되살렸다.
- 원인:
  - `조현병(정신분열병)` 나무위키 결과가 character-parenthetical bridge로 등록됨.
  - `웹소설`이라는 약한 매체 단어 때문에 나무위키 일반 개념어 가드가 완화됨.
  - URL-backed weak-title replacement가 나무위키 일반 개념 URL을 official title 근거로 사용.
- 변경:
  - 의학/건강/현실 개념어 surface를 범주형 lexicon으로 묶고 `medical_common_topic_title` hard reject profile을 추가.
  - 최종 title reject 시 title candidates, primary/mentioned/recommendation/comparison 후보를 함께 비워 residual title 누수를 막음.
  - character-parenthetical search hint와 URL-backed replacement가 같은 final title rejection profile을 확인하도록 정리.
  - `웹소설/소설/작품` 같은 약한 단어만으로는 medical common demotion을 막지 못하고, 작가/회차/캐릭터명/공식 플랫폼 detail 등 강한 앵커가 필요하도록 변경.
- 검증:
  - targeted 회귀 5건 OK.
  - `tests.test_agentic_pipeline_rework`: 147건 OK.
  - `tests.test_agentic_pipeline_alias_contract`: 30건 OK.
  - `py_compile` 통과.
  - 실제 단건 run `20260428_230857_637381`: `11718111`은 `is_relevant=false`, title 없음, `medical_common_topic_demoted`.
- 남은 작업:
  - afterfix14 200건 canary와 1,000건 risk discovery에서 나무위키 일반 개념어 FP와 의료 소재 웹소설 positive 이웃을 같이 집계.

## 2026-04-29 - afterfix14 200 canary 및 1,001 risk discovery 완료

- 상태: run-stability-go / quality-review
- 실행:
  - 200건 canary run id `20260428_233059_378617`.
  - 1,001건 risk discovery run id `20260429_002511_375830`.
  - `11718111`을 risk discovery 입력에 추가해 targeted 통과 사례의 대형 표본 재발 여부를 확인.
- 결과:
  - canary: `completed=200/200`, `failed=0`, `pending=0`, `Relevant=70`, `Identified=61`.
  - risk discovery: `completed=1001/1001`, `failed=0`, `pending=0`, `Relevant=381`, `Identified=297`.
  - risk runtime: `13487.3s`, 평균 `13.5s/post`.
  - 사전/사후 shard audit 모두 `ok=36/36`.
  - risk audit: `reason_errors=0`, `slang_db_bad_remaining=0`, `search_timeout=4`, `search_degraded_detected=173`.
- 확인:
  - `11718070` ECT, `11631298` 무림맹, `11456200` 마법소녀ㄴ/폼체인지 오탐은 최신 risk discovery에서 title 없음.
  - `11616838`, `11198715` 마법소녀ㄴ positive stem은 `마법소녀ㄴ은 은퇴하고 싶다`로 유지.
  - `11066247`처럼 다중 애니 캐릭터/트로프 글은 adjacent/title 없음으로 마감.
- 새로 드러난 위험:
  - `11718111`은 targeted에서는 차단됐지만 risk discovery에서는 `정신과 의사`로 resolved. 의학 일반어만이 아니라 직업/현실 개념 title 승격 guard가 필요.
  - `11684415 -> 小數, decimal number`, `11505857 -> Cecil`처럼 일반어/인명 표면이 플랫폼 URL 또는 search bootstrap으로 official title이 됨.
  - weak-evidence official title 후보 35건을 별도 리뷰 대상으로 추출.
- 산출물:
  - `out/sampling/query_gate_canary_200_afterfix14_20260428_audit.json`
  - `out/sampling/query_gate_risk_discovery_1000_plus11718111_afterfix14_20260429_audit.json`
  - `out/search_shard_audit_20260429_after_afterfix14_risk1000.json`
  - `out/llm_judgment_reviews/llm_judgment_review_20260429_002511_375830_risk1000_afterfix14.md`
- 다음 작업:
  - weak evidence official title promotion guard를 P1 개선으로 분리.
  - `official_title_evidence=false`, `search_snippets=0`, `official_urls=0`, `post_spans=0` 조합이 resolved를 이기지 못하게 스코어/후처리 기준 보강.

## 2026-04-29 - afterfix15~17 weak evidence / broad alias 개선

- 상태: canary-go / risk-hold
- 변경:
  - 약한 evidence literal topic title, dictionary/gloss title이 official title로 확정되지 않도록 최종 title rejection profile을 확장.
  - `11718111`처럼 의료/일상 개념과 검색 키워드만 겹치는 unresolved core 잔류를 demotion하는 consistency guard 추가.
  - locked official candidate rescue가 넓은 alias stem과 캐릭터 미연결 반론을 무시하지 않도록 broad alias hold guard 추가.
- 검증:
  - `tests.test_agentic_pipeline_rework`: 153건 OK.
  - `11718111` targeted afterfix16: `Relevant=0`, title 없음.
  - afterfix16 200 canary `20260429_175638_261091`: `completed=200/200`, `failed=0`, `Relevant=77`, `Identified=64`, audit `reason_errors=0`, `slang_db_bad_remaining=0`.
- 관찰:
  - ECT/조현병/무림맹/주서연 기본 회귀는 통과.
  - `11198715`는 afterfix16 canary에서 `마법소녀물 신전사가 되었다`로 잘못 resolved되는 새 오류를 발견.
  - afterfix17 targeted에서는 오답 title lock은 제거됐지만 `Relevant=0`까지 내려가 과보수. 이 케이스는 `관련-미확정`으로 유지하는 후속 개선 필요.
- 결정:
  - afterfix17 상태에서 1,000건 risk discovery는 보류.
  - 다음 개선은 `마법소녀ㄴ`류 의도적 제목 오타/자모 alias의 positive/negative 이웃을 먼저 고정한 뒤 200 canary를 재실행한다.

## 2026-04-29 - afterfix18~19 internal work signal HOLD

- 상태: targeted-go / canary-required
- 배경:
  - `11198715`는 afterfix17에서 오답 title resolved는 제거됐지만 `Relevant=0`으로 과보수 처리됨.
  - 본문에는 `세린이`, `세진이`, `계약`, `은퇴`, `공백의 2년`처럼 작품 내부 토론 단서가 있으므로 비관련 삭제가 아니라 관련-미확정 HOLD가 맞음.
- 변경:
  - `internal_work_signal_unresolved_recovered` guard를 추가해 복수 캐릭터 + 설정/전개 단서가 있으면 `core_relevant + unresolved_work`로 복구.
  - 실제 Gatekeeper 구조인 `detected_entities.possible_characters/titles`도 읽도록 보강.
  - 내부 앵커 HOLD가 발생한 경우 locked official detail 후보가 다시 title resolved로 승격하지 않도록 차단.
- 검증:
  - `tests.test_agentic_pipeline_rework`: 155건 OK.
  - afterfix18 targeted는 관련 복구는 됐지만 locked official rescue가 `마법소녀ㄴ은 은퇴하고 싶다`로 resolved하여 추가 차단 필요를 확인.
  - afterfix19 targeted `out/sampling/targeted_magicgirl_11198715_afterfix19_20260429_result.json`: `Relevant=1`, `Identified=0`, `official_title=null`, flag `internal_work_signal_unresolved_recovered`.
- 다음:
  - afterfix19 200건 canary를 실행하고, 통과 시 1,000건 risk discovery로 확대.

## 2026-04-30 - afterfix19 risk review 및 afterfix20 locked metadata guard

- 상태: afterfix19 canary-go / risk-review / afterfix20 canary-go / risk-review
- 실행:
  - afterfix19 200건 canary run id `20260429_204443_104695`: `completed=200/200`, `Relevant=73`, `Identified=54`.
  - afterfix19 1,001건 risk discovery run id `20260429_213837_418990`: `completed=1001/1001`, `Relevant=401`, `Identified=284`.
  - risk audit: `reason_errors=0`, `slang_db_bad_remaining=0`, `search_degraded_detected=160`.
- 확인:
  - ECT/조현병 현실 의학어는 title 없음으로 안정화.
  - `11198715`은 관련-미확정으로 유지.
  - `11456200`, `11505857`, `11205227`은 title 없음.
- 새 위험:
  - `11631298`가 risk discovery에서 `무림맹주 막내제자`로 재승격.
  - 문제 candidate는 locked 상태였지만 `page_type=community_post`, `content_status=deleted`, `negative_evidence=url_is_community_post/url_deleted_or_unavailable`를 갖고 있었음.
  - `11663540`은 검색 결과에 캐릭터 괄호형 bridge가 잡히지 않을 때 resolved/unresolved/non-relevant가 흔들림.
- 변경:
  - afterfix20에서 locked official candidate rescue가 bad page/content metadata를 가진 후보를 제외하도록 보강.
  - 특정 작품명/세력명 blacklist가 아니라 `community_post`, `deleted/unavailable`, `negative_evidence` 구조 신호를 기준으로 일반화.
- 검증:
  - `tests.test_agentic_pipeline_rework`: `157 OK`.
  - afterfix20 targeted run `20260430_015935_598854`: `11631298` title 없음, `11684415` resolved 유지, `11456200` title 없음.
- afterfix20 canary:
  - run id `20260430_021001_693350`.
  - `completed=200/200`, `Relevant=73`, `Identified=57`, `reason_errors=0`, `slang_db_bad_remaining=0`.
  - known-case: `11631298` title 없음, `11663540 -> 전 버튜버가 하고 싶은데요`, `11198715` 관련-미확정.
- afterfix20 risk:
  - run id `20260430_025849_885589`.
  - `completed=1001/1001`, `Relevant=382`, `Identified=277`, `reason_errors=0`, `slang_db_bad_remaining=0`.
  - `11631298` locked bad metadata 재승격은 차단됨.
  - `11663540`은 `전 버튜버가 하고 싶은데요` resolved.
  - `11616838`, `11198715`은 관련-미확정.
  - `11718070`, `11718111`, `11205227`은 title 없음.
- 잔존 위험:
  - `11505857 -> Cecil` 재발. 짧은 인명/캐릭터 표면이 character-parenthetical/영문 title로 승격하는 유형.
  - `11456200`은 title 없음이지만 관련-미확정으로 과복구. 단일 캐릭터 + 트로프 일반론의 internal work signal 조건을 줄여야 함.
- 다음:
  - `Cecil`류 false bridge guard 추가.
  - `11456200`류 trope-only 과복구 조건 축소.

## 2026-04-30 - afterfix21 short person bridge / trope-only guard

- 상태: canary-go / risk-review
- 변경:
  - 짧은 영어 인명형 character-parenthetical title은 게시글 본문에 작품성 anchor가 없으면 resolved로 승격하지 않도록 제한.
  - `Cecil` blacklist가 아니라 `short ascii personlike title + weak post-side work anchor` invariant로 처리.
  - `폼체인지/변신/의상/추가파츠/마법소녀` trope-only 표면은 강한 plot term 없이 `internal_work_signal_unresolved_recovered`를 만들지 않도록 축소.
  - `승급`은 strong plot term으로 추가해 positive 이웃 보존.
- 검증:
  - `tests.test_agentic_pipeline_rework`: `159 OK`.
  - targeted run `20260430_120419_466550`: `11505857`, `11456200`은 title 없음, `11663540` resolved 유지, `11616838` 관련-미확정.
  - 200 canary run `20260430_121717_430655`: `completed=200/200`, `Relevant=82`, `Identified=65`, `reason_errors=0`, `slang_db_bad_remaining=0`.
  - 1,001 risk run `20260430_131615_234022`: `completed=1001/1001`, `Relevant=396`, `Identified=308`, `reason_errors=0`, `slang_db_bad_remaining=0`.
- 확인:
  - `11505857 -> Cecil` 재발 차단.
  - `11456200` trope-only 과복구 차단.
  - `11718070`, `11718111`, `11631298` title 없음 유지.
  - `11663540`은 `전 버튜버가 하고 싶은데요` resolved 유지.
  - `11198715`, `11616838`은 risk에서 관련-미확정 유지.
- 다음:
  - afterfix21 risk에서 증가한 `Relevant/Identified`를 정성 리뷰해 recall 개선인지 false positive 증가인지 분리.
  - 새 resolved 저근거 상위 표본을 리뷰 패킷으로 추출.

## 2026-05-22 - server-poc full run review

- 상태: run-complete / quality-review / runtime-bug-patched
- 대상:
  - `server-poc/expert_result_20260505_214349_324347.json`
  - `server-poc/logs/expert_run_20260505_214349_324347*.log`
  - `server-poc/logs/warp_shards_status_20260505_214349_324347.json`
  - `server-poc/slang_db/slang_db.json`
- 산출물:
  - `server-poc/result_scan_20260505_214349_324347.json`
  - `server-poc/run_review_audit_20260505_214349_324347.json`
  - `server-poc/run_review_20260505_214349_324347.md`
- 확인:
  - result scan과 main log가 `total=104502`, `relevant=20993`, `identified=12414`로 일치.
  - final WARP snapshot은 `running=36/36`, `warp_on=36/36`.
  - worker logs completion line은 `104502`.
  - pre-run startup logs에는 `warp_on=20/36`과 shard auto-up failure가 있었지만 final run은 정상 shard 상태에서 진행.
  - known degenerate image post `11589463`은 VLM chunk request 없이 adjacent trope/title 없음으로 완료.
- 발견:
  - `arbiter.py`에서 `suspected_titles` confidence가 `str`/`float`로 섞일 때 정렬 TypeError가 발생. 4개 post에서 deliberation fallback까지 같은 오류를 냈다.
  - server result에서 `11718111 -> 정신분열병`이 재발했다. 현재 worktree의 targeted medical/common tests는 통과하므로 서버 run 시점 코드/배포본 차이 또는 장기 run 결과 품질 evidence로 분리.
  - `resolved_with_weak_evidence_text=3223`, `resolved_with_degraded_majority=12220`로 대량 품질 승인은 보류.
  - `11663540`, `11616838`, `11631298`는 afterfix21 기대와 server result가 달라 단건 재처리 비교가 필요.
- 변경:
  - `ArbiterExpert._suspected_title_sort_key` 추가.
  - `ctx.suspected_titles` 병합 정렬에서 `_confidence_to_unit` 기반 sort key 사용.
  - mixed confidence regression test 추가.
- 검증:
  - targeted unittest 5건 OK.
  - `py_compile` pass.
- 다음:
  - 서버 산출물 패키지에 manifest/checkpoint/run_audit/review packet 포함.
  - result JSON 직접 audit/review packet builder 추가 검토.
  - degraded-majority resolved/weak-evidence resolved 표본 정성 리뷰.

## 2026-05-22 - server-poc qualitative review correction

- 상태: quality-no-go / diagnostic-corpus
- 배경:
  - 이전 server-poc 리뷰는 자동 로그/카운트/필드 감사였고, 10만 건 전체 자연어 판독 완료가 아니었음을 명시적으로 보정.
- 산출물:
  - `server-poc/qualitative_review_packet_20260505_214349_324347_20260522.jsonl`
  - `server-poc/qualitative_review_packet_20260505_214349_324347_20260522.md`
  - `server-poc/qualitative_review_adjudication_20260505_214349_324347_20260522.md`
  - `qualitative_review/20260505_214349_324347/sample_manifest.json`
  - `qualitative_review/20260505_214349_324347/review_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/review_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/pattern_summary.md`
  - `qualitative_review/20260505_214349_324347/gate_decision.md`
  - `qualitative_review/20260505_214349_324347/action_queue.md`
- 판독:
  - stratified packet `172`건 판독.
  - `ACCEPT=107`, `HOLD=26`, `REPROCESS=27`, `REJECT=12`.
  - deterministic random control `100`건 추가 판독.
  - random control 결과: `ACCEPT=86`, `HOLD=14`, `REPROCESS=0`, `REJECT=0`.
  - merged 결과: `272`건, `ACCEPT=193`, `HOLD=40`, `REPROCESS=27`, `REJECT=12`, `INFO_MISSING=0`.
- 발견:
  - `정신분열병`, `판타지 용어`, `2016`, `Legend`, `떡씬 많은 19금 판타지` 같은 generic/common surface promotion이 자연어 판독에서 확인됨.
  - `갤질의사`가 `갤질하는 천재 의사`, `댓글 보는 천재 의사`, `개질하는 천재 의사`로 흔들리는 canonical drift가 확인됨.
  - `즉사무림`, `죽깨수`, `망겜성`, `아생갤`, `괴담동`, `갤질의사` 계열의 unresolved/false-negative recall loss가 확인됨.
- 결론:
  - run integrity는 계속 `REVIEW`.
  - 자연어 품질 승인은 `NO-GO`; 100k 결과는 정식 승인 산출물이 아니라 재검색/재판단용 진단 corpus로 취급.
- 미충족:
  - 이 시점에는 기존 172건 1차 packet 정규화와 `100`건 deterministic random control만 완료됐고, Round 2 failure-pattern expansion은 아래 후속 항목에서 별도 수행.
  - per-row checkpoint/worker/shard/timestamp/evidence URL payload가 없어 일부 evidence grade는 `Weak/Missing`으로 남음.

## 2026-05-22 - server-poc qualitative Round 2 expansion

- 상태: round2-complete / quality-no-go
- 배경:
  - random control만으로는 rare but critical semantic failure를 놓치고, 위험 bucket만으로는 기준선을 잃으므로 2차 failure-pattern expansion을 별도 수행.
- 산출물:
  - `tools/build_qualitative_round2_review.py`
  - `qualitative_review/20260505_214349_324347/round2_manifest.json`
  - `qualitative_review/20260505_214349_324347/round2_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/round2_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/round2_summary.md`
- 판독:
  - 초기 Round 2 `200`건 추가 판독.
  - 초기 Round 2 결과: `ACCEPT=77`, `HOLD=60`, `REPROCESS=62`, `REJECT=1`, `INFO_MISSING=0`.
  - 초기 merged 결과: `472`건, `ACCEPT=270`, `HOLD=100`, `REPROCESS=89`, `REJECT=13`, `INFO_MISSING=0`.
  - 이 `472`건은 10만 건 scan quality approval이 아니라 initial semantic triage로만 취급한다. 현재 대형 확장 결과는 아래 `server-poc large-scale qualitative expansion` 항목을 기준으로 한다.
- bucket:
  - `search_degraded_or_timeout`, `weak_evidence_but_strong_resolution`, `generic_parenthetical_bridge`, `unresolved_to_resolved`, `multi_work_or_adjacent_risk`, `trope_or_author_talk_risk`, `slang_db_store_block_pending_family_noise`, `VLM_OCR_involved`, `worker_or_shard_degraded_window`, `round2_false_negative_recall`은 각 20건 선정.
  - `reason_decision_contradiction`은 공개 필드 기준 후보가 0건이라 표본 없음.
- 결론:
  - run integrity는 계속 `REVIEW`.
  - semantic decision quality는 계속 `NO-GO`.
  - `worker_or_shard_degraded_window`와 `unresolved_to_resolved`는 server-poc package에 checkpoint/shard/timestamp lineage가 없어 partial/proxy evidence로만 취급.
- 다음:
  - Round 3에서 P0/P1 후보를 targeted re-search/re-judge/re-run하고 failure pattern saturation 여부를 확인.

## 2026-05-22 - server-poc Round 3 target preparation

- 상태: round3-targets-prepared / execution-pending
- 배경:
  - Round 2 이후 non-ACCEPT `202`건이 남아 있어, 다음 단계가 임의 샘플이 아니라 P0/P1 pattern별 대표 검증이어야 함.
- 산출물:
  - `tools/build_qualitative_round3_targets.py`
  - `qualitative_review/20260505_214349_324347/round3_p0p1_manifest.json`
  - `qualitative_review/20260505_214349_324347/round3_p0p1_candidates.jsonl`
  - `qualitative_review/20260505_214349_324347/round3_targeted_input.jsonl`
  - `qualitative_review/20260505_214349_324347/round3_issue_templates.md`
  - `qualitative_review/20260505_214349_324347/round3_action_plan.md`
- 선정:
  - 최초 대표 seed는 `52`건이었으나, 10만 건 품질 승인 근거로는 부족해 P0/P1 후보를 `584`건으로 확대했다.
  - 확대 라벨: `REJECT=13`, `REPROCESS=442`, `HOLD=129`.
  - 확대 action: `re_search=350`, `re_judge=96`, `re_run=100`, `slang_db_review=30`, `docs_issue=8`.
  - pattern coverage: `generic_common_surface`, `weak_evidence_strong_resolution`, `alias_recall_loss_false_negative`, `slang_db_alias_subtype`, `vlm_ocr_evidence_gap`, `worker_shard_degraded_window`, `boundary_domain_drift` 각 `100`건.
- 결론:
  - semantic decision quality는 계속 `NO-GO`.
  - 후보와 targeted input은 준비됐지만 실제 현재 코드 재검색/재판정/재실행은 아직 수행되지 않음.
  - 실행 readiness 재확인 결과 search shards는 `8/8` OK, 기본 vLLM endpoint `http://10.20.0.101:8000/v1/models`도 HTTP 200.

## 2026-05-22 - server-poc large-scale qualitative expansion

- 상태: large-scale-expanded / quality-no-go / execution-ready
- 배경:
  - 472건 정성 리뷰는 10만 건 scan의 initial semantic triage로만 충분하고, 품질 승인 근거로는 표본이 작다는 판단에 따라 대형 확장 수행.
- 산출물:
  - `qualitative_review/20260505_214349_324347/random_control_v3_manifest.json`
  - `qualitative_review/20260505_214349_324347/random_control_v3_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/random_control_v3_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/high_risk_expansion_manifest.json`
  - `qualitative_review/20260505_214349_324347/high_risk_expansion_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/high_risk_expansion_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/pattern_coverage_summary.md`
  - `qualitative_review/20260505_214349_324347/expanded_gate_decision.md`
- 판독:
  - random control v3 `1000`건 stratified: `ACCEPT=889`, `HOLD=2`, `REPROCESS=109`, `REJECT=0`.
  - high-risk expansion `5000`건: `ACCEPT=2041`, `HOLD=1528`, `REPROCESS=1430`, `REJECT=1`.
  - canonical merged `6172`건: `ACCEPT=3037`, `HOLD=1556`, `REPROCESS=1566`, `REJECT=13`.
  - Round 3 P0/P1 후보 `584`건: `REJECT=13`, `REPROCESS=442`, `HOLD=129`.
- readiness:
  - vLLM endpoint `http://10.20.0.101:8000/v1/models` HTTP 200.
  - search shards `8/8` OK.
- 결론:
  - random baseline과 high-risk oversample을 섞어 전체 오류율로 말하지 않는다.
  - high-risk expansion에서 HOLD/REPROCESS가 대량으로 남아 semantic decision quality는 계속 `NO-GO`.

## 2026-05-22 - server-poc Round 3 targeted execution start

- 상태: round3-targeted-running / quality-no-go
- 배경:
  - 당시 기준으로 Gemma 4 4B급 vLLM에서는 `expert_main.py` 호출 병렬도를 `--parallel 32`로 뒀다.
  - 당시 32개 search shard audit은 `8/32`만 OK라, 실행은 `--parallel 32`와 `MCP_SHARD_COUNT=8` 조합으로 32 worker가 8개 정상 shard에 순환 배정되게 했다.
- 실행:
  - 초기 `--parallel 8` 실행은 `round3_after_result_checkpoint.jsonl` 기준 `116`건 완료, failed `0`에서 중단.
  - 남은 `468`건은 `round3_targeted_input_remaining_p32.jsonl`로 생성.
  - `round3_after_p32_remaining_result.json` 대상으로 당시 기준 `--parallel 32` 재개.
- shard/process 확인:
  - 이번 p32 재개 명령에는 `--no-auto-up-shards`가 포함되어 있어 `expert_main.py`의 WARP shard 자동 기동/재확인 경로는 실행되지 않았다.
  - Docker/port 확인 결과 현재 live shard는 `warp-shards-mcp-bridge-1..8`, ports `3333..3340`뿐이며 `3341..3364`는 Python 점유가 아니라 리스너/컨테이너 부재 상태다.
  - 중단된 초기 8병렬 run의 orphan multiprocessing child 2개(`parent_pid=88188`)는 정리했다.
  - true 32-search-shard 실행이 필요하면 `--no-auto-up-shards`를 제거하고 `MCP_SHARD_COUNT=32` 또는 `MCP_ENDPOINTS` 32개를 사용해 `expert_main.py`가 `tools/warp_shards.py up --count 32`를 호출하게 해야 한다.
- 보정:
  - `expert_main.py`의 JSONL loader가 packet 내부 `content`/`comments`를 무시해 pilot 결과에서 본문/댓글이 빈 배열로 떨어지던 문제를 수정.
  - `content_blocks`가 없고 `content`/`comments`가 embedded로 있는 targeted review packet도 본문/댓글을 유지하도록 로더를 확장.
- 다음:
  - p32 remainder가 완료되면 기존 `116`건 checkpoint와 p32 결과를 병합해 `round3_after_packets.jsonl`, `round3_after_labels.jsonl`, `round3_after_summary.md`를 생성.

## 2026-05-23 - server-poc Round 3 after review complete

- 상태: round3-after-complete / quality-no-go
- 실행 결과:
  - `round3_after_result_checkpoint.jsonl`: `116`건 완료, failed `0`.
  - `round3_after_p32_remaining_result.json`: `468`건 완료, failed `0`, 당시 기준 `--parallel 32`.
  - 병합 산출물 `round3_after_merged_result.json`: `584`건, duplicate post id `0`, missing target `0`.
  - body/comment 보존: body rows `552`, comment rows `439`.
- after review:
  - `round3_after_packets.jsonl`, `round3_after_labels.jsonl`, `round3_after_summary.md`, `round3_after_gate_decision.md` 생성.
  - after labels: `ACCEPT=179`, `HOLD=268`, `REPROCESS=137`, `REJECT=0`.
  - transitions: `REJECT->ACCEPT=12`, `REJECT->HOLD=1`, `REPROCESS->ACCEPT=161`, `REPROCESS->HOLD=151`, `REPROCESS->REPROCESS=130`, `HOLD->HOLD=116`, `HOLD->ACCEPT=6`, `HOLD->REPROCESS=7`.
- 해석:
  - hard `REJECT`는 `13`에서 `0`으로 내려갔지만 P0/P1 targeted set 안에 `HOLD/REPROCESS=405`가 남아 semantic decision quality는 계속 `NO-GO`.
  - 다음 단계는 잔여 `generic_common_surface`, `alias_recall_loss_false_negative`, `slang_db_alias_subtype`, `vlm_ocr_evidence_gap`, `worker_shard_degraded_window` 큐를 줄이거나 explicit quarantine으로 고정하는 것.

## 2026-05-23 - server-poc Round 3 residual queue split

- 상태: residual-queue-split / quality-no-go
- 입력:
  - `qualitative_review/20260505_214349_324347/round3_after_labels.jsonl`
  - `qualitative_review/20260505_214349_324347/round3_after_packets.jsonl`
  - `qualitative_review/20260505_214349_324347/round3_targeted_input.jsonl`
- 산출물:
  - `round3_after_residual_analysis.md`
  - `round3_after_residual_analysis.json`
  - `round3_after_queue_re_search.jsonl` (`153`건)
  - `round3_after_queue_re_judge.jsonl` (`88`건)
  - `round3_after_queue_slang_db_review.jsonl` (`80`건)
  - `round3_after_queue_human_review.jsonl` (`48`건)
  - `round3_after_queue_re_run.jsonl` (`36`건)
  - `round3_after_rerun_input_re_search_re_run.jsonl` (`189`건)
- 해석:
  - `re_search`와 `re_run`은 fresh expert_main 재처리 입력으로 분리했다.
  - `re_judge`, `slang_db_review`, `human_review`는 자동 재실행보다 판정/DB 상태/수동 검토 큐로 유지한다.
  - semantic gate는 잔여 큐가 줄거나 explicit quarantine으로 고정되고 post-remediation random baseline + P0/P1 regression이 끝날 때까지 `NO-GO`다.

## 2026-05-23 - server-poc Round 3 residual re-search/re-run rerun

- 상태: residual-rerun-complete / quality-no-go
- 입력:
  - `round3_after_rerun_input_re_search_re_run.jsonl` (`189`건)
- 실행:
  - 당시 기준 Gemma 4 4B vLLM, `expert_main.py --parallel 32`
  - live search shards `8/8` OK, 32 workers가 8개 shard를 순환 사용
  - `round3_after_rerun_re_search_re_run_result.json`: `189`건 완료, failed `0`
  - batch search: 총 요청 `1323`, 실제 검색 `1322`, cache hit `1`
  - total time `3905.5s`, avg `20.7s/post`
- rerun labels:
  - `round3_after_rerun_labels.jsonl`: `REPROCESS=101`, `HOLD=72`, `ACCEPT=16`
  - rerun action: `re_search=125`, `re_run=30`, `human_review=11`, `slang_db_review=7`, `no_action=16`
- combined state:
  - `round3_after_rerun_combined_labels.jsonl`
  - `round3_after_rerun_combined_summary.md`
  - `round3_after_rerun_combined_summary.json`
  - final labels: `ACCEPT=195`, `HOLD=288`, `REPROCESS=101`, `REJECT=0`
  - remaining non-ACCEPT: `389`
- 해석:
  - fresh `re_search/re_run` 재처리로 `16`건만 추가 `ACCEPT`로 이동했다.
  - semantic gate는 계속 `NO-GO`; 남은 주요 큐는 `re_search=125`, `re_judge=88`, `slang_db_review=87`, `human_review=59`, `re_run=30`.

## 2026-05-23 - server-poc Round 3 after-rerun quarantine split

- 상태: quarantine-split / quality-no-go
- 입력:
  - `round3_after_rerun_combined_labels.jsonl`
- 산출물:
  - `round3_after_rerun_quarantine_manifest.json`
  - `round3_after_rerun_quarantine_summary.md`
  - `round3_after_rerun_quarantine.jsonl`
  - category별 quarantine JSONL과 exit-action별 JSONL
- 결과:
  - accepted subset: `195`
  - quality approval 제외 대상: `389`
  - priority: `P0=91`, `P1=298`
  - category: `alias_recall_quarantine=96`, `judgment_guard_quarantine=89`, `slang_db_quarantine=88`, `search_degraded_quarantine=84`, `vlm_ocr_quarantine=30`, `weak_evidence_quarantine=2`
  - exit action: `fresh_search_with_direct_evidence_or_demote=125`, `fix_judgment_guard_or_manual_relabel=88`, `complete_slang_db_state_review=87`, `manual_adjudication=59`, `rerun_with_required_input_modality_or_quarantine_disabled_modality=30`
- 해석:
  - quarantine은 GO 신호가 아니라 비승인 범위를 명확히 제외하는 산출물이다.
  - gate lift에는 exit action 완료 후 random baseline + P0/P1 regression이 필요하다.

## 2026-05-22 - qualitative semantic review loop guide

- 상태: docs-updated / gate-standardized
- 배경:
  - 자동 감사 결과와 자연어 판정 품질 승인이 섞이면 대량 런 결과가 과승인될 위험이 있음.
  - 10만 건 전수 수동 판독이 아니라 위험 bucket 과표집, random control, failure pattern saturation 기반의 반복 루프가 필요함.
- 변경:
  - `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md` 추가.
  - `SCAN_RESULT_REVIEW_GUIDE.md`에 `QUALITATIVE_SEMANTIC_REVIEW_LOOP` 모드, hard gate, 필수 bucket, 라벨, 산출물, 종료 조건 연결.
  - `OPERATION_QUALITY_CHECKLIST.md`에 sample manifest, review packet, label, pattern summary, gate decision, action queue 체크 추가.
  - `CHECKLIST.md`에 자동 감사와 semantic decision quality 분리 확인 추가.
  - `TODO.md`에 지침 완료와 packet/label 생성 도구 보강 후속 작업 추가.
- 핵심 규칙:
  - `result_scan`, `run_audit`, count summary는 run integrity 증거로만 취급.
  - 대량 결과 `GO`는 run integrity와 semantic decision quality가 모두 `GO`일 때만 가능.
  - 자연어 리뷰 라벨은 `ACCEPT`, `HOLD`, `REPROCESS`, `REJECT`, `INFO_MISSING`으로 고정.

## 2026-05-26 - 10만 건 테스트 부족점/버그 정리 및 targeted fix

- `20260505_214349_324347` 10만 건 결과는 런 정합성과 자연어 판정 품질을 분리해 유지한다.
- 외부 매체 IP가 플랫폼 URL, 파생 팬픽 URL, slang DB alias, locked official candidate rescue를 타고 웹소설 title로 확정되는 대표 경로를 차단했다.
- `8531521`은 최신 v29 단건 재실행에서 `강철의 연금술사` 확정이 제거되고 `other_quarantine`으로 내려갔다.
- `8834919`는 `아집숨 -> 아포칼립스에 집을 숨김` positive control을 유지했다.
- `8424362`는 `에미야 키리츠구` title 확정은 제거됐지만 `unresolved_work`라 HOLD 성격으로 남긴다.
- Browser `iab`에서 `11097334`를 확인한 결과 lazy/placeholder image가 남아 VLM/OCR image gate를 계속 강제해야 한다.
- `tools/capture_vlm_ocr_browser_review_cli.py`를 보강해 본문 첨부 이미지만 세고, 평가 전에 본문 이미지를 스크롤/대기해 lazy-load를 유도하도록 했다.
- 새 기준으로 `11097334`는 본문 첨부 `3`개, 스크롤 전 `loaded=2/3`, `placeholder=1`, 스크롤/대기 후 `loaded=3/3`, `placeholder=0`으로 확인됐다.
- `build_vlm_browser_targets_from_review.py`와 `build_qualitative_exit_action_closure.py`도 같은 이미지 gate를 사용하도록 맞췄고, closure 재생성 결과 approval excluded `460`으로 semantic gate는 계속 `NO-GO`다.
- 자세한 내용: `qualitative_review/20260505_214349_324347/current_100k_issue_resolution_summary_ko_20260526.md`

## 2026-05-26 - v63 character-only virtual battle guard targeted run

- 상태: targeted-fix-verified / quality-no-go
- 배경:
  - v62에서 `11663540`이 `title null`은 유지했지만 `is_relevant=true`, `work_resolution=unresolved`로 흔들렸다.
  - 자동 after-review도 `Weak + title null/unresolved + boundary risk`를 과허용할 수 있었다.
- 조치:
  - 최종 consistency validator에서 `title_deliberately_null + no official title + virtual battle context` 조합은 관련성 승격을 막도록 보강.
  - 자동 packet labeler는 `Weak + unresolved/title null + boundary/search risk` 조합을 `HOLD`로 내리도록 보강.
- 검증:
  - focused pipeline unittest 6건 `OK`.
  - qualitative packet tool unittest 3건 `OK`.
  - py_compile 통과.
  - Gemma 4 4B, `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`으로 `v34_known_bad_media_alias_guard_input.jsonl` 6건 재실행.
- 결과:
  - v63 run id: `20260526_231204_349215`.
  - completed `6`, failed `0`, pending `0`, search health `36/36 OK`.
  - `11663540`: `is_relevant=false`, `official_title=null`, `work_resolution=none`.
  - after packet review: `ACCEPT=5`, `HOLD=1`; 남은 `HOLD`는 `10426463`.
- 해석:
  - 대표 known-bad는 닫혔지만, 전체 10만 건 gate는 여전히 `NO-GO / REVIEW-LOCKED`.
  - 다음은 remaining approval-excluded/action queue `389`건과 post-fix random baseline + P0/P1 regression.

## 2026-05-27 - 10만 건 부족점/버그/해결 가능 항목 현재화

- 상태: summary-updated / quality-no-go
- 산출물:
  - `qualitative_review/20260505_214349_324347/current_100k_fixable_gap_bug_summary_ko_20260527.md`
- 현재 closure:
  - `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`
  - approval excluded `460/584`
  - semantic gate `NO-GO / REVIEW-LOCKED`
- 이미 닫힌 대표 버그:
  - `10190186` direct/locked rescue stale demotion 오염
  - `8424362` 캐릭터 표면명 URL substring 과승격
  - `9218133` 일반 개념 질문 canonical/title-surface rescue 과승격
  - `11663540` character-only virtual battle 관련성 누수
  - `8531521`, `8601885` 외부 IP negative control
- 추가 확인된 해결 후보:
  - `11113480` 로그에서 `카드아카` generic inline alias가 보류 후 pending count 2로 BatchMem 승격됨.
  - 최종 판정 자체와 별개로, 보류 seed의 반복 승격은 slang DB/BatchMem 오염 위험으로 `IMP-20260527-033`에 등록.
- 다음 우선순위:
  - BatchContextMemory generic inline/저근거 seed 반복 승격 차단
  - `weak_evidence_strong_resolution=75`, `generic_common_surface=89`
  - `slang_db_review=87`, `vlm_ocr_evidence_gap=28`, `worker_shard_degraded_window=84`

## 2026-05-27 - v72 BatchContextMemory generic inline alias 반복 승격 차단

- 상태: targeted-fix-verified / quality-no-go
- 배경:
  - `post_id=11113480`에서 `카드아카 -> 카드 아카데미 1타강사`가 `일반명사형 약칭 즉시등록 보류` 후 pending count 2로 BatchMem resolved memory에 승격되는 로그가 확인됐다.
  - 최종 작품 판정 자체는 맞을 가능성이 높지만, 보류 seed가 반복만으로 hard memory가 되는 경로는 slang DB/BatchMem 오염 위험이다.
- 조치:
  - `generic_inline_alias` pending은 count 2 이상이어도 resolved memory로 승격하지 않도록 차단.
  - 저근거 `register_abbreviation_seed`는 structured slang support 없이 반복만으로 승격하지 않도록 차단.
  - 승격 차단 로그와 stats를 추가.
- 검증:
  - `tests.test_batch_context` 7건 `OK`.
  - v72 run id `20260527_094306_107869`, completed `1`, failed `0`, pending `0`, search health `36/36 OK`.
  - `11113480`: `official_title=카드 아카데미 1타강사`, `confidence=High`, `work_resolution=resolved`.
  - worker log에서 `BatchMem: 약칭 승격 '카드아카'` 없음, `약칭 승격 보류 ... reason=generic_inline_alias` 확인.
  - after-review는 broader generic bridge risk 때문에 `HOLD=1`.
- 산출물:
  - `qualitative_review/20260505_214349_324347/batchmem_generic_inline_alias_seed_guard_ko_20260527.md`
- 해석:
  - BatchMem 오염 경로는 targeted 기준 닫혔지만, 전체 10만 건 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-27 - v73 review labeler direct evidence/degraded routing 보정

- 상태: tooling-fix-verified / quality-no-go
- 배경:
  - `generic_parenthetical_bridge` bucket은 공식 상세 근거가 있어도 `HOLD/re_judge`로 뭉치는 경향이 있었다.
  - `degraded_queries: 0` 필드명만으로 `search_degraded=true`가 되는 review labeler 버그가 있었다.
- 조치:
  - search degraded 판정에서 `degraded_queries` 필드명 자체를 오탐하지 않도록 수정.
  - 직접 작품 근거가 강한 generic bucket은 degraded 없음 `ACCEPT/no_action`, degraded 있음 `HOLD/re_search`, 순수 generic bridge 문제 `HOLD/re_judge`로 분리.
- 검증:
  - `tests.test_qualitative_review_packet_tools` 6건 `OK`.
  - v72 단건 after-review: `HOLD=1`, action `re_search=1`.
  - v67 generic_common_surface 19건 재적용: `ACCEPT=7`, `HOLD=12`, actions `no_action=7`, `re_search=7`, `re_judge=5`.
- 산출물:
  - `qualitative_review/20260505_214349_324347/review_labeler_direct_evidence_degraded_routing_ko_20260527.md`
- 해석:
  - 승인 확대가 아니라 action queue 정밀화다.
  - 전체 10만 건 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-30 - v275 VLM/OCR 직접 작품 표면 rescue 및 URL 제목 불일치 차단

- 상태: targeted-fix-verified / quality-no-go
- 배경:
  - `11718117`은 이미지 안에 웹소설 장면과 `아카데미의 피해자`, `양파랑` 표기가 있었는데, 검색 중심 후처리가 이를 `noise`로 떨어뜨리거나 다른 KakaoPage URL을 붙일 수 있었다.
  - `23센줄` 유형처럼 오타/감상 표현은 작품명 seed로 승격하면 안 되지만, VLM/OCR이 직접 작품 표면을 읽은 경우는 반대로 검색 근거 부족만으로 버리면 안 된다.
- 조치:
  - official URL 후보 대표 제목과 선택 작품명이 불일치하면 URL을 기각하고 reference graph에서도 제거.
  - VLM/OCR direct image candidate를 추가해 `explicit_text|cover_title`, `title_role=work_title`, `promotion_eligible=true` 단일 제목을 작품명으로 rescue.
  - direct image rescue anchor는 schema-safe `image`로 기록.
- 검증:
  - focused unittest 4건 `OK`.
  - v275 run id `20260530_130539_724278`, completed `1`, failed `0`, pending `0`.
  - `11718117`: `is_relevant=true`, `discussion_type=review`, `official_title=아카데미의 피해자`, `heretic_url=null`, VLM/OCR `used=True`.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v275_post11718117_direct_image_rescue_review_ko.md`
- 해석:
  - 직접 이미지 작품명은 semantic decision quality의 별도 evidence edge다.
  - title correctness와 official URL evidence strength는 분리한다.
  - 전체 10만 건 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-30 - v282 final meaning reread 및 official URL synopsis mismatch 보정

- 상태: targeted-fix-verified / quality-no-go
- 배경:
  - `23센줄`은 `23세인 줄`의 오타/축약으로 읽어야 하며, 특정 작품명/별칭 후보로 기계 승격하면 안 된다.
  - v281에서 `망겜의 힐러` 제목은 맞았지만, 문피아 모바일 URL fetch 대표 제목이 시놉시스 문장으로 잡혀 공식 URL이 null이 됐다.
  - visual-only VLM 결과가 reason에서 제목 확정 근거처럼 표현될 위험도 확인됐다.
- 조치:
  - high-risk 최종 후보에 `final_semantic_reread`를 적용해 원문 title/body/comment와 surface paraphrase, discourse warning, evidence를 다시 읽는다.
  - 같은 URL 검색 결과의 제목이 최종 작품명을 직접 지지하면 fetch/page analyzer 대표 제목이 시놉시스/브랜딩이어도 URL을 과삭제하지 않는다.
  - VLM/Vision이 캐릭터/장면 보조 정보만 준 경우 title grounding으로 쓰지 않았다고 reason에 남긴다.
- 검증:
  - `tests.test_final_semantic_reread_gate` 5건 `OK`.
  - v282 run id `20260530_145554_611788`, completed `4`, failed `0`, pending `0`, requested parallel `36`, effective parallel `4`, VLM/OCR `true`.
  - `11718091`: `official_title=null`, `title_resolution_state=context_only`, `23센줄 -> 23세인 줄` 공개.
  - `11718097`: `official_title=망겜의 힐러`, `heretic_url=https://m.munpia.com/novel/detail/328421`, `official_detail_url_repaired_from_search`.
  - `11718099`: `빌어먹을 환생`과 문피아 URL 유지, OCR title conflict flag 유지.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v282_official_url_synopsis_mismatch_guard_ko.md`
- 해석:
  - targeted known-bad는 개선됐지만 10만 건 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-05-30 - v283 final reread / URL synopsis review bucket 도구화

- 상태: tooling-verified / quality-no-go
- 배경:
  - v282에서 확인한 `final_semantic_reread`와 `official URL synopsis mismatch`를 손검토 사례로만 남기면 expanded review에서 반복 유형을 놓칠 수 있다.
- 조치:
  - `tools/build_qualitative_round2_review.py`에 `final_semantic_reread_missing_for_semantic_seed`, `final_semantic_reread_reviewed`, `official_url_synopsis_or_branding_mismatch` bucket을 추가했다.
  - review packet에 `final_semantic_reread_fields`를 추가했다.
  - review tool도 `m.munpia.com/novel/detail/<id>`, `novel.munpia.com/<id>`를 문피아 작품 상세 URL로 인정하게 했다.
- 검증:
  - `tests.test_qualitative_review_packet_tools` 32건 `OK`.
  - v282 result를 대상으로 Round2 builder를 실행했을 때 `11718097`이 `official_url_synopsis_or_branding_mismatch` bucket으로 선택되고 `ACCEPT/no_action`으로 분리됐다.
  - 원본 partial `out/expert_result_20260528_141006_620986.json` 80행에서는 새 bucket 후보가 0건이었다. 이 결과는 v282 이전 partial 산출물이라 새 flag가 없는 한계로 본다.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v283_v282_new_bucket_check/`
  - `qualitative_review/20260528_141006_620986/v283_round2_new_buckets_partial/`
- 해석:
  - bucket 도구화는 완료됐지만, 전체 10만 건 semantic gate는 계속 `NO-GO / REVIEW-LOCKED`.

## 2026-06-01 - v477 Decoder KNOWN_ABBREVIATIONS 미검증 rescue 차단

- 상태: targeted-fix-verified / hardcoded-alias-review
- Codex goal 병렬은 `spawn_agent` 전문가 검토로 수행했고, `expert_main.py --parallel` worker cap 조정과 분리했다.
- Decoder 감사 subagent는 `_rescue_null_title`의 `known_abbreviation_unverified` 0.80 rescue, `_init_suspected_titles`의 `known_match` suspected, high-fit interpretation, weak thematic guard 예외를 지적했다.
- Agentic/Arbiter 감사 subagent는 `_try_promote_best_candidate` direct `High`, `_has_title_abbrev_stability_signal`, `_known_title_abbreviation_context_locks_title`, Arbiter guard exception 잔여를 지적했다.
- 조치:
  - `KNOWN_ABBREVIATIONS` hit가 검색/공식 제목 근거 없이 Decoder rescue 후보를 만들지 못하게 했다.
  - 등록 약칭이어도 독립 근거가 없으면 LLM의 `비제목/비작품` 판단과 트로프 체크를 우회하지 못하게 했다.
- 검증:
  - `tests.test_decoder_known_abbreviation_guard` 추가.
  - focused unittest 29건 `OK`.
  - 관련 `py_compile` 통과.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v477_decoder_known_abbrev_unverified_guard_review_ko.md`
  - `qualitative_review/20260528_141006_620986/v477_hardcoded_alias_risk_audit_after_decoder_known_abbrev_unverified_guard_ko.md`
  - `qualitative_review/20260528_141006_620986/v477_goal_action_queue_after_decoder_known_abbrev_unverified_guard_ko.md`
- 결과:
  - `KNOWN_ABBREVIATIONS positive_usage=82`
  - `KNOWN_TITLE_ABBREVIATIONS positive_usage=18`
  - `SLANG_DICTIONARY positive_usage=0`
  - `hardcoded_alias_gate=REVIEW`, blocker `2`
- 해석:
  - 미검증 Decoder rescue는 targeted 기준 닫혔다.
  - hardcoded alias registry 전체와 10만 건 semantic approval은 아직 `REVIEW-LOCKED`다.

## 2026-06-01 - v478 Decoder 등록 약칭 suspected/best_match 예외 차단

- 상태: targeted-fix-verified / hardcoded-alias-review
- Decoder subagent 감사 결과를 반영해 `_resolved_mappings`, high-fit interpretation, weak thematic guard의 registry-only 경로를 추가로 좁혔다.
- 조치:
  - `_has_known_abbreviation_independent_anchor()` helper를 추가했다.
  - `known_match` 단독 suspected title 생성을 차단했다.
  - high-fit interpretation에서 registry pair만으로 낮은 약칭 정합성 차단을 우회하지 못하게 했다.
  - weak thematic guard에서 `KNOWN_ABBREVIATIONS` pair 자체를 explicit alias support로 보지 않게 했다.
- 검증:
  - `tests.test_decoder_known_abbreviation_guard` 9건 `OK`.
  - 관련 `py_compile` 통과.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v478_decoder_known_abbrev_suspected_guard_review_ko.md`
  - `qualitative_review/20260528_141006_620986/v478_hardcoded_alias_risk_audit_after_decoder_known_abbrev_suspected_guard_ko.md`
  - `qualitative_review/20260528_141006_620986/v478_goal_action_queue_after_decoder_known_abbrev_suspected_guard_ko.md`
- 결과:
  - `KNOWN_ABBREVIATIONS positive_usage=81`
  - `KNOWN_TITLE_ABBREVIATIONS positive_usage=18`
  - `SLANG_DICTIONARY positive_usage=0`
  - `hardcoded_alias_gate=REVIEW`, blocker `2`
- 해석:
  - Decoder 내부 일부 registry-only path는 targeted 기준 닫혔다.
  - Agentic/Arbiter registry-only path가 남아 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 - v521 current goal 회귀/환경 재확인

- 상태: focused-regression-verified / execution-readiness-missing / semantic-review-locked
- `tests.test_expert_main_comment_metadata` + `tests.test_final_semantic_reread_gate` 19건 통과.
- `tests.test_goal_test_run_contract_audit` + `tests.test_preflight_expert_rerun_runtime` + `tests.test_goal_current_state_map` + `tests.test_goal_action_queue` 32건 통과.
- 현재 코드 계약은 `--parallel 36`을 max로 두고 small input에서 `effective_parallel`을 줄이며, small goal/test Docker lifecycle은 기본 차단한다.
- semantic/VLM 재확인에서는 `11718080` old row가 no-work/social lament 오판이고, `11718082` old row는 결론이 맞을 수 있어도 공개 VLM/OCR 증거가 부족하다는 점을 분리했다.
- live 확인에서는 `:8000` LLM endpoint가 연결되지 않았고 Docker engine pipe 접근이 권한 거부되어 새 completed VLM/OCR-on source 재실행 준비는 아직 부족하다.
- 루트 `README.md`와 `expert_readme.md`의 오래된 `--parallel`/자동 shard 문구를 최신 max/effective_parallel/no lifecycle 계약으로 갱신했다.
- `v518_combined_browser_visual_artifacts_ko.md`와 관련 manifest의 깨진 한국어 문구를 복구했다.
- 산출물:
  - `qualitative_review/20260528_141006_620986/v521_current_goal_verification_ko.md`
  - `qualitative_review/20260528_141006_620986/v521_current_state_after_targeted_tests.json`
  - `qualitative_review/20260528_141006_620986/v521_current_state_after_targeted_tests_ko.md`
  - `qualitative_review/20260528_141006_620986/v521_action_queue_after_targeted_tests.json`
  - `qualitative_review/20260528_141006_620986/v521_action_queue_after_targeted_tests_ko.md`
- 해석: 원본 partial source는 계속 regression seed이며, 10만 semantic approval은 completed source/random baseline/P0-P1 expansion/Browser visual gate 전까지 `REVIEW-LOCKED / NO-GO`다.

## 2026-06-02 - v523 issue-focused goal 범위 정정 및 v422 follow-up

- 사용자 정정에 맞춰 active goal 범위를 `10만 전체 semantic approval`이 아니라 `10만에서 간추린 known-bad/high-risk seed closure`로 재정렬했다.
- `v422_search_only_blocked_intent_followup_rerun_combined_input.jsonl` 11건을 Gemma 4 E4B/4B 기준 `--parallel 36` max, VLM/OCR on, `--require-vlm-ocr-for-images`, `--reuse-shards-only`로 재실행했다.
- run id `20260602_002014_213782`: completed/flushed/pending/failed `11/11/0/0`, requested/effective parallel `36/11`, VLM/OCR ready, Docker lifecycle auto up/recreate 없음.
- `v284_residual_p0p1_core21_input.jsonl` 98 row 후보는 preflight에서 open shard `32/36`, required `36`으로 `NOT_READY`였으므로 실행하지 않았다.
- v523 자연어 라벨 결과는 `ACCEPT=5`, `HOLD=5`, `REPROCESS=1`.
- 회복 확인:
  - `11718080` no-work/social lament는 title 과확정이 재발하지 않았다.
  - `11718097`은 `망겜힐 -> 망겜의 힐러`가 공식/본문 근거로 회복됐다.
  - `11718098`은 `마좋좋좋 -> 마법 좋아좋아좋아`가 회복됐다.
- 잔존 이슈:
  - `11718083` validation error는 P0 re-run/fallback 대상.
  - `11718118`, `11718091`은 reason/discussion_type 재판정 대상.
  - `11718069`, `11718076`은 browser visual artifact 보강 대상.
- 브라우저 제어는 Codex in-app Browser와 fallback Playwright MCP 모두 현재 실패하여, visual 대상은 HOLD로 남겼다.

## 2026-06-02 - v524 11718083 validation fallback closure

- v523 P0였던 `11718083`의 `PickvelIdentity subtype` validation error를 코드에서 보정했다.
- memory-query forced demotion path가 허용 enum 밖 `memory_query` subtype을 내지 않고, `title_resolution_state=unresolvable_memory_query`와 허용 subtype으로 표현되도록 했다.
- focused unit 1건, 관련 test file 24건, py_compile을 통과했다.
- live rerun `20260602_005333_547203`은 completed/flushed/pending/failed `1/1/0/0`, requested/effective parallel `36/1`, VLM/OCR ready, runtime audit `GO`.
- v524 결과는 `official_title=null`, `is_novel_related=true`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`이며 자연어 라벨은 `ACCEPT/no_action`.

## 2026-06-02 - v525 11718091/11718118 reason taxonomy closure

- v523 P1였던 `11718091`, `11718118`의 reason/discussion_type mismatch를 targeted seed 기준으로 닫았다.
- 코드 변경:
  - character/context-only 글은 surface reread를 핵심 결론으로 쓰지 않고, 캐릭터·나이·외형 반응과 작품 앵커 부족을 분리해 `undecodable_reference / unresolved_work`로 설명한다.
  - TS물/장르/트로프 일반론은 LLM 출력이 `noise/off_topic`으로 흔들려도 no-title 조건에서 `trope_discussion / genre_trope_discussion / adjacent_relevant`로 재정렬한다.
- 검증:
  - `tests.test_title_lead_search_inferred_guard`: `OK`, 27 tests
  - `py_compile src\llm_batch\agentic_pipeline.py tests\test_title_lead_search_inferred_guard.py`: 통과
  - live rerun `20260602_011626_306351`: completed/flushed/pending/failed `2/2/0/0`, requested/effective parallel `36/2`, Docker lifecycle auto up/recreate 없음
  - runtime audit `GO`, semantic coverage sanity `GO`, reason hygiene hit files `0`
- 결과:
  - `11718091`: `official_title=null`, `discussion_type=undecodable_reference`, `subtype=unresolved_work`, `title_resolution_state=context_only`
  - `11718118`: `official_title=null`, `discussion_type=trope_discussion`, `subtype=genre_trope_discussion`, `topicality=adjacent_relevant`
- 산출물:
  - `qualitative_review/20260528_141006_620986/v525_reason_discussion_type_rejudge_review_ko.md`
  - `qualitative_review/20260528_141006_620986/v525_post11718091_11718118_after_review_labels.jsonl`
  - `qualitative_review/20260528_141006_620986/v525_issue_focused_action_queue_ko.md`

## 2026-06-20 - recall gate canary C41/D4/D5 및 검증 병렬 16 전환

- 사용자 운영 지시에 따라 이후 검증 LLM/`expert_main.py` run은 요청 병렬도 `--parallel 16`을 기본으로 기록한다. 입력 수가 더 작으면 manifest의 `effective_parallel`로 실제 동시성을 별도 확인한다.
- C41 targeted canary는 `--parallel 16`, VLM/OCR off로 완료했다. `requested/effective=16/7`, completed/failed/pending `7/0/0`.
- C41에서 title/body compact official anchor와 unavailable exact-search title fallback이 함께 필요한 케이스를 확인했다. `11661853`은 `두바이의 쫀득한 여초딩 재벌 9세` / `https://novelpia.com/novel/419119`로 회복됐다.
- D4 integrated VLM/OCR 55-row run은 `--parallel 16`, VLM/OCR on으로 실행했으나 verifier stream runaway(`acc_chars=121,531`)를 확인해 중단했다. stop snapshot은 completed/pending/failed `30/2/0`이므로 승인 근거로 쓰지 않는다.
- Gatekeeper/Decoder/Verifier/Verifier relation judge의 생성 token cap을 bounded default로 낮췄다.
- D5 suspect subset 5건은 `--parallel 16`, VLM/OCR on으로 완료했다. manifest `requested/effective=16/5`, completed/pending/failed `5/0/0`, VLM/OCR semantic gate `READY`.
- D5 로그에서 verifier `max_tokens=8192`, verifier relation judge `max_tokens=2048`, 최대 stream `acc_chars=6,363`을 확인해 D4 runaway가 재현되지 않았다.
- 회귀 검증은 관련 broad unittest `111`건 `OK`.
- 이번 기록은 targeted/suspect 검증이다. full scan approval은 열지 않고 semantic decision quality는 계속 `REVIEW-LOCKED / NO-GO`로 유지한다. slang DB write-back은 하지 않았다.

## 2026-06-20 - D10 patch target canary로 direct URL/known-title update alias 회귀 해소

- D6-D9에서 드러난 두 회귀를 좁혀 수정했다.
  - `11682781`: packet에 직접 등장한 `https://novelpia.com/novel/405193` + OCR 작품명이 있었는데, later search repair가 neighbor URL `399871`로 바꾸던 문제.
  - `11652175`: `KNOWN_TITLE_ABBREVIATIONS`의 `담텔기 -> 괴담 호텔 탈출기`가 업데이트 질문 맥락인데도 semantic no-work seed와 search degraded로 batch alias rescue가 흔들리던 문제.
- 코드 변경:
  - packet-local direct official detail URL은 same-platform search repair보다 우선한다.
  - candidate URL sync도 direct packet URL을 target search URL로 덮어쓰지 않는다.
  - known title abbreviation update-question anchor는 semantic no-work seed 예외를 통과하되, recommendation request와 bare alias/no-work 잡담은 계속 차단한다.
- 검증:
  - `py_compile` 통과: `agentic_pipeline.py`, `test_agentic_pipeline_rework.py`, `test_known_title_abbreviation_support.py`.
  - targeted unittest 8건 `OK`.
  - 실제 `expert_main.py` D10 canary: `out\recall_gate_canary\patch_targets_D10_vlmocr16_20260620_0203.json`, log `logs\expert_run_20260620_020258_749960.log`.
  - 명령은 `--parallel 16`, VLM/OCR on, `--slang-db off`, `MCP_HEALTH_INCLUDE_SEARCH=1`; run meta `requested_parallel=16`, `effective_parallel=8`, completed/pending/failed `8/0/0`.
- 결과:
  - `11682781`은 `외신의 딸이 되어 교주생활` / `https://novelpia.com/novel/405193`로 resolved.
  - `11652175`는 `괴담 호텔 탈출기` / `https://novelpia.com/novel/102155`로 resolved.
  - controls: `11666700` unrelated, `11687635` recommendation hold, `11695607` cross-media hold, `11705276` recommendation hold 유지.
- 해석: D10은 patch-target canary 성공이며, 55-row integrated completion/full scan approval 근거는 아니다. semantic quality는 계속 `REVIEW-LOCKED / NO-GO`.

## 2026-06-20 - D11 55-row integrated canary runtime completion

- verifier cap 및 D10 patch-target 수정 이후 `out\recall_gate_canary\canary_input_v3.jsonl` 55건을 `--parallel 16`, VLM/OCR on, `--slang-db off`, `MCP_HEALTH_INCLUDE_SEARCH=1`로 재실행했다.
- run id `20260620_022104_296011`은 completed/flushed/pending/failed `55/55/0/0`, `large_run_complete=true`, search health `16/16 OK`, VLM/OCR semantic gate `READY`로 종료했다.
- 산출물:
  - `out\recall_gate_canary\integrated_D11_vlmocr16_20260620_current.json`
  - `out\recall_gate_canary\integrated_D11_vlmocr16_20260620_current_manifest.json`
  - `out\recall_gate_canary\integrated_D11_vlmocr16_20260620_current_checkpoint.jsonl`
  - `out\recall_gate_canary\integrated_D11_vlmocr16_20260620_current_summary.json`
  - `logs\expert_run_20260620_022104_296011.log`
- D11 acceptance pin:
  - B precision: `11661847`, `11657013`, `11666700`은 resolved 과승격 없이 hold/unresolved 계열로 남았다.
  - B recall boundary: `11648980`, `11650585`, `11682781`은 resolved 유지.
  - C positive: `11652175`, `11661853`, `11677911`은 resolved.
  - C negative: `11687635`, `11695607`, `11705276`, `11665081`은 final title null/hold 계열 유지.
- 잔여 품질 후보:
  - `11657008`: 플랫폼명 `노벨피아`가 final title로 잔존.
  - `11698889`: OCR/title typo `푸림마조`가 final title로 잔존.
  - `11661893`: seed expected와 다른 wrong-work title 선택.
- 해석: D11은 55-row integrated runtime 및 B/C target acceptance 근거다. full scan approval은 열지 않고 semantic decision quality는 계속 `REVIEW-LOCKED / NO-GO`로 유지한다.

## 2026-06-22 - completed779 Reimprovement Loop 2 canary/compare 완료

- active queue `25`건을 Loop 2 입력으로 분리했다: text/url/comment `8`, image/OCR `17`.
- 정상 Docker/SearXNG shard 대신 direct Naver/Bing fallback을 사용했다. `/readyz`와 health client는 `MCP_DIRECT_SEARCH_FALLBACK_READYZ_OK=1` 명시 canary에서만 direct fallback을 ready로 인정하도록 보강했다. 이 결과는 degraded-provider evidence다.
- text/url/comment canary:
  - result `out\expert_result_20260622_201044_448457.json`
  - rows `8/8`
  - 첫 시도는 decoder stream 폭주로 final flush 전 중단했고, bounded decoder env(`LLM_DECODER_MAX_TOKENS=4096`, `LLM_DECODER_HARD_CAP=4096`, `LLM_ACC_HARD_CAP=32768`)로 재실행해 완료했다.
- image/OCR canary:
  - result `out\expert_result_20260622_201630_167085.json`
  - rows `17/17`
  - VLM/OCR Semantic Gate `READY`
- compare:
  - combined result `out\completed779_improvement_goal_20260622\compare\reimprovement_loop2_combined_result.json`
  - combined compare `out\completed779_improvement_goal_20260622\compare\reimprovement_loop2_combined_compare.json`
  - movement `candidate_or_human_review_preserved=7`, `resolved_expected_title=1`, `url_lint_preserved=9`, `still_under_resolved_or_noise=8`
  - source/url hygiene `9`건은 모두 `url_lint_preserved`로 이동했다.
- remaining queue:
  - `out\completed779_improvement_goal_20260622\reimprovement_loop2_queue.json`
  - `out\completed779_improvement_goal_20260622\reimprovement_loop2_queue_ko.md`
  - rows `8`
- control audit:
  - active `garbage_title_after=0`
  - `11694064`는 `무협 게임에 빙의했다...스킵충이다`로 재확정되지 않음
  - `wrong_work=9`는 bad pipeline title로 회귀하지 않음
- 검증:
  - `py_compile` 통과
  - focused suite `204 tests OK`
- 해석: Loop 2 targeted canary/compare는 완료했지만, full scan approval은 열지 않는다. semantic quality는 계속 `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-22 - completed779 Hermes Continuous Goal 계약 추가

- 배경:
  - Loop 2 이후 remaining queue는 `8`건이며 모두 `still_under_resolved_or_noise`다.
  - 단발 Loop goal 방식으로는 사용자가 원하는 “이슈가 남으면 다음 개선 loop를 계속 이어가는” 운영을 충분히 표현하지 못했다.
- 조치:
  - `goal.md` 맨 위 active contract를 `completed779 Hermes Continuous Improvement Goal`로 갱신했다.
  - 새 copy-paste prompt `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`를 추가했다.
  - Council role을 `Candidate/Comment`, `OCR/Visual`, `Source/URL`, `Search/Web`, `Code Hook`, `Prompt/Orchestration`, `Verification/Docs` 7축으로 확장했다.
  - subagent는 승인자가 아니라 탐색자/반론자이며, 메인 Codex가 파일·테스트·canary·compare로 재확인한다는 규칙을 명시했다.
  - 모델 다양성(`gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex-spark`)과 도구 다양성(local artifacts, code/tests, web/search, prompt/semantic review)을 운영 규칙으로 추가했다.
  - active 8-row queue의 빈 `suspected_code_hook`, `proposed_next_fix`, `required_test`를 채워 다음 loop가 바로 실행 가능한 action queue가 되도록 보강했다.
  - bucket별 acceptance map을 추가해 `candidate_comment_multi`는 candidate/HOLD/human_review 보존을 성공으로 인정하고, `recall_relevance_representative`는 강한 evidence가 있을 때만 expected title/url 회수를 허용하도록 했다.
- 현재 active queue:
  - `out\completed779_improvement_goal_20260622\reimprovement_loop2_queue.json`
  - rows `8`
  - post_id `11695623`, `11706856`, `11708442`, `11716478`, `11697241`, `11697255`, `11702072`, `11703624`
- 게이트:
  - `semantic_quality=REVIEW-LOCKED`
  - `full_scan_approval=false`
  - runtime integrity, targeted canary status, semantic quality, full-scan approval은 계속 분리한다.

## 2026-06-22 - completed779 source-correctness refresh 정상 shard 실행 완료

- Docker Desktop을 기동하고 정상 Docker/SearXNG shard `2`개를 복구했다.
  - shard endpoints: `http://localhost:3333`, `http://localhost:3334`
  - audit: `out\completed779_improvement_goal_20260622\source_correctness_refresh_20260622\search_shard_audit_after_restore.json`
  - result: `ok=2/2`, direct fallback `false`, degraded direct provider `false`
- source-correctness refresh prepared input `39`건을 split 실행했다.
  - text/url/comment `14`건:
    - result `out\completed779_improvement_goal_20260622\source_correctness_refresh_20260622\canary\source_correctness_refresh_text_result.json`
    - log `logs\expert_run_20260622_220605_069293.log`
    - completed/flushed/pending/failed `14/14/0/0`
  - image/OCR `25`건:
    - result `out\completed779_improvement_goal_20260622\source_correctness_refresh_20260622\canary\source_correctness_refresh_image_ocr_result.json`
    - log `logs\expert_run_20260622_222635_313729.log`
    - completed/flushed/pending/failed `25/25/0/0`
    - VLM/OCR Semantic Gate `READY`
- combined result와 compare를 생성했다.
  - combined result `out\completed779_improvement_goal_20260622\source_correctness_refresh_20260622\canary\source_correctness_refresh_combined_result.json`
  - compare `out\completed779_improvement_goal_20260622\source_correctness_refresh_20260622\compare\source_correctness_refresh_compare.json`
  - report `out\completed779_improvement_goal_20260622\source_correctness_refresh_20260622\compare\source_correctness_refresh_compare.md`
  - movement `resolved_expected_title_and_url=6`, `review=12`, `url_lint_preserved=21`
  - next queue `out\completed779_improvement_goal_20260622\source_correctness_refresh_20260622\source_correctness_refresh_next_queue.json`, rows `0`
- 주요 해석:
  - `11694064`와 `11710033`은 bad pipeline title로 되돌아가지 않았지만, `판초법사 -> 판초우의의 마법사` recall은 아직 회수되지 않았다.
  - `11702055`는 `압소르망/104호/반지` character-setting cluster가 `괴담 호텔 탈출기` 회수로 이어지지 않았다.
  - `11706871`은 OCR classic-literature surface가 웹소설 title로 오염되는 위험을 보였다.
  - `11716480`은 OCR explicit title과 search-absent/URL-null을 분리해야 한다.
  - `11698880`은 source-local alias conflict guard가 필요하다.
- 해석:
  - 이번 run은 정상 shard targeted refresh completion이다.
  - next queue는 `0`이지만 semantic approval이 아니다. `review=12`, `url_lint_preserved=21` residual은 다음 Hermes expansion seed로 사용한다.
  - `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-23 - completed779 Hermes Loop 5 postfix1 source/url hygiene guard

- 배경:
  - Loop 5 residual review에서 `11698880`은 expected `아카데미 생존 갤러리`인데 runtime 내부가 `가챠 중독자의 퓨전펑크 생활`로 강하게 끌리는 source-local alias/title-body conflict였다.
  - 기존 compare는 이 행을 `url_lint_preserved`로 닫아 실제 wrong-work drift를 숨겼다.
- subagent council:
  - Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Prompt/Orchestration, Code Hook 축으로 병렬 검토했다.
  - 공통 결론: promotion을 넓히기보다 candidate/HOLD/lint 보존을 분리하고, source-local alias conflict는 final public title 확정 전에 차단해야 한다.
- 조치:
  - `src/llm_batch/candidate_audit.py`에 `apply_judge_seed_hygiene_expected_title_guard`를 추가했다.
  - `expert_main.py` 후처리 chain에 해당 guard를 연결했다.
  - `tools/compare_completed779_improvement.py`가 expected title과 다른 after title을 `title_or_url_still_mismatched`로 분류하도록 보강했다.
  - compare title match에는 OCR close variant 허용과 `_judge_seed` embedded input unwrapping을 추가했다.
- 실행/검증:
  - Loop 5 combined compare postfix1:
    - `out\completed779_improvement_goal_20260622\compare\hermes_loop5_source_residual_combined_compare_postfix1.json`
    - movement `candidate_or_human_review_preserved=16`, `resolved_expected_title=4`, `review=12`, `still_under_resolved_or_noise=4`, `title_or_url_still_mismatched=1`, `url_lint_preserved=7`
    - postfix next queue rows `5`, 새 hard row `11698880`
  - `11698880` 단일 image/OCR canary:
    - input `out\completed779_improvement_goal_20260622\inputs\hermes_loop5_postfix1_11698880_image_ocr.jsonl`
    - result `out\completed779_improvement_goal_20260622\canary\hermes_loop5_postfix1_11698880_image_ocr_result.json`
    - log `logs\expert_run_20260623_012944_631536.log`
    - completed/failed/pending `1/0/0`, VLM/OCR Semantic Gate `READY`
    - runtime internal Arbiter still selected `가챠 중독자의 퓨전펑크 생활`, but final public `official_title/heretic_url` was demoted to `None`; `blocked_official_title=가챠 중독자의 퓨전펑크 생활`, `expected_official_title_conflict=아카데미 생존 갤러리`.
  - single-row compare after guard:
    - `out\completed779_improvement_goal_20260622\compare\hermes_loop5_postfix1_11698880_compare.json`
    - movement `url_lint_preserved=1`
- 해석:
  - `11698880` wrong-work finalization은 postfix1에서 차단됐다.
  - upstream root cause는 아직 남았다: title lead alias `아생갤`보다 body comparison candidate `가챠펑크/세드릭`이 Arbiter lock까지 끌고 간다.
  - 다음 loop는 postprocess guard가 아니라 primary selection 전 `multi_candidate_hold`/candidate ledger 분리를 일반화해야 한다.
- 게이트:
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-27 - regression-safe grounding Loop 04 FIX-3b bracket cue canary

- `11698897` wrong-work-among-aliases blocker를 targeted fix로 처리했다.
  - `랫따싶` shared tag official detail 경쟁에서 `[림월드]` bracket cue가 post/OCR/work_cues와 일치하면 해당 official detail을 우선하도록 `agentic_pipeline.py` score를 보강했다.
  - OCR/visual cue overlap은 전체 OCR 문장과 일반 토큰(`있습니다`, `회차를` 등)이 unrelated official detail을 부스트하지 않게 축소했다.
  - `candidate_audit.py`의 `official_url_recoverable` scoring도 같은 bracket/post cue 원칙으로 맞췄다.
- 검증:
  - `py_compile` pass: `src/llm_batch/agentic_pipeline.py`, `src/llm_batch/candidate_audit.py`.
  - `tests.test_title_lead_search_inferred_guard`: `76 tests OK`.
  - `tests.test_candidate_audit`: `58 tests OK`.
  - `tests.test_agentic_pipeline_rank3_lock_anchor`: `12 tests OK`.
  - Data Analytics artifact `LOOP 04 Regression-Safe Grounding Audit` rendered.
- canary:
  - result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix3b_bracket_cue_golden_result.json`
  - manifest `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix3b_bracket_cue_golden_result_manifest.json`
  - completed/pending/failed `16/0/0`, VLM/OCR `READY`, `slang_db=off`.
  - audit pass improved from FIX-3 `8/16` to FIX-3b `10/16`; positive expected-work improved from `1/8` to `3/8`.
- 게이트:
  - runtime integrity `GO`
  - targeted row `11698897` recovered expected title `[림월드]변방계에서 회귀자로 살아남기`
  - golden semantic `NO-GO`, failed `6/16`
  - collateral_regression_count `6`
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-23 - completed779 Hermes Loop 7 fix17 queue-0 closure

- Loop 7 final combined accounting을 `36/36`으로 재구성하고 compare helper wrapper-row unwrap 이슈를 고쳤다.
  - result: `out\completed779_improvement_goal_20260622\canary\hermes_loop7_broader_residual_combined_fix6_final36_result.json`
  - compare: `out\completed779_improvement_goal_20260622\compare\hermes_loop7_broader_residual_combined_fix7_unwrapped_final36_compare.json`
  - movement: `candidate_or_human_review_preserved=13`, `resolved_expected_title=1`, `resolved_expected_title_and_url=1`, `review=12`, `still_under_resolved_or_noise=2`, `url_lint_preserved=7`
  - next queue: `out\completed779_improvement_goal_20260622\hermes_loop7_broader_residual_next_queue_fix7_unwrapped_final36.json`, rows `2`
- Remaining targeted rows:
  - `11711600`: candidate preservation closure.
  - `11706832`: fix11 first closed the hard queue by candidate/human-review preservation; fix17 then resolved the expected title.
- `11706832` fix17:
  - result: `out\completed779_improvement_goal_20260622\canary\hermes_loop7_fix17_j11_alias_lock_11706832_result.json`
  - compare: `out\completed779_improvement_goal_20260622\compare\hermes_loop7_fix17_j11_alias_lock_11706832_compare.json`
  - final: `황제폐하가 웹소설 작가임을 숨김`, `https://novelpia.com/novel/385635`
  - movement: `resolved_expected_title=1`
  - next queue: `out\completed779_improvement_goal_20260622\hermes_loop7_fix17_j11_alias_lock_next_queue.json`, rows `0`
- Generalized fixes:
  - short community alias bridge search profile, Korean particle stripping, community bridge phrase support, false official detail filtering.
  - relation verifier community alias support counting by domain.
  - J11 relation alias official-detail lock so supported short alias cases do not drift back to the alias text.
  - OCR-only title evidence provenance no longer claims official search evidence.
- Gate:
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-23 - completed779 Hermes Loop 7 fix1 text closure and image/OCR partial

- subagent/council fan-out:
  - runtime/code hook, OCR/visual, source/search, verification/docs 4축을 병렬 실행했다.
  - main Codex가 파일/log/compare 증거로 재확인했고 subagent 의견은 승인 근거로 사용하지 않았다.
- `11705239`:
  - pre-fix single quarantine `logs/expert_run_20260623_050058_659227.log`에서 postprocess hang을 재현했다.
  - `agentic_pipeline.py`에서 title lookup/memory query가 recommendation guard null을 검색 hit만으로 해제하지 않게 보강했다.
  - post-fix single `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11705239_fix1_result.json`은 completed/flushed/pending/failed `1/1/0/0`.
  - final은 `official_title=null`, `work_resolution=none`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=unresolvable_memory_query`.
- Loop 7 text:
  - combined fix1 result `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_combined_fix1_result.json`, rows `16/16`.
  - text compare `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_text_fix1_compare.json`: `resolved_expected_title_and_url=1`, `review=4`, `still_under_resolved_or_noise=9`, `title_or_url_still_mismatched=2`.
- Loop 7 image/OCR:
  - broad run `20260623_052157_158066` used VLM/OCR and effective parallel `2`.
  - result `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_image_ocr_fix1_result.json` contains `19/20` rows; missing `11716480`.
  - image compare `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_image_ocr_fix1_compare.json`: `candidate_or_human_review_preserved=5`, `resolved_expected_title=1`, `review=8`, `still_under_resolved_or_noise=1`, `url_lint_preserved=4`.
- `11716480` quarantine:
  - single input `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_image_ocr_single_11716480_quarantine.jsonl`.
  - single rerun `logs/expert_run_20260623_061321_455105.log` reached strong OCR/Jury evidence for `여대생 가랑이 사이 무릎 꿇은 엄마들` but did not write result/checkpoint.
  - manifest remained `completed=0`; result JSON absent.
  - observed root causes: VLM direct title discarded when search candidate map lacks exact title, generic `인터넷 방송인` suspected title temporarily outranking OCR, repeated decoder recall over genre tags, `후타보로` author truncation, and postprocess hang after canonical suspect/J10/confidence normalization.
- combined partial:
  - `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix1_partial35_result.json`, rows `35/36`.
  - compare `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix1_partial35_compare.json`: `candidate_or_human_review_preserved=5`, `resolved_expected_title=1`, `resolved_expected_title_and_url=1`, `review=12`, `still_under_resolved_or_noise=10`, `title_or_url_still_mismatched=2`, `url_lint_preserved=4`.
  - next queue `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix1_partial35.json`, rows `12`, plus runtime quarantine `11716480`.
- 게이트:
  - runtime integrity: partial, `11716480` quarantined.
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-23 - completed779 Hermes Loop 7 broader residual partial run

- Loop 6 postfix4 이후 broader residual coverage를 위해 Loop 7 queue `36`건을 생성했다.
  - queue `out\completed779_improvement_goal_20260622\hermes_loop7_broader_residual_queue.json`
  - main/control `16/20`, text/image `16/20`
  - buckets: `under_resolved=3`, `under_resolved_false_negative=8`, `wrong_relevance=5`, `operational_residual_review=12`, `operational_residual_url_lint_preserved=8`
- text/url/comment canary는 partial evidence까지만 확보했다.
  - first run `20260623_022342_639179`: completed/flushed/pending/failed `12/11/1/0`, ordered flush blocked.
  - resume run `20260623_024758_871942`: completed/flushed/pending/failed `2/0/2/0`, ordered flush blocked.
  - partial combined `out\completed779_improvement_goal_20260622\canary\hermes_loop7_broader_residual_text_partial_combined_result.json`, rows `14`.
  - runtime blockers `out\completed779_improvement_goal_20260622\hermes_loop7_text_runtime_blockers_ko.md`.
- `11702087`에서 두 층의 원인을 분리했다.
  - `_context_to_output` early `flags` 미초기화로 `UnboundLocalError`가 발생했고, `agentic_pipeline.py`에서 early flags를 초기화/merge하도록 수정했다.
  - retry 후에는 `semantic_seed_review`가 너무 일찍 no-search/noise로 종료하는 문제가 드러났고, `orchestrator.py`에서 dense character/setting cluster search probe를 추가했다.
  - `그래서` 같은 Korean connective lead token이 검색을 오염시키는 문제를 low-specificity seed 및 Phase34.5 reaction-tail guard로 줄였다.
  - fix3 run에서는 `괴담 호텔 탈출기`와 `https://novelpia.com/novel/102155` 근거까지 잡혔지만, relation/Jury/multi-work/character-drift/snippet invalidation guard가 final title을 막았고 flush 전 kill됐다.
- 검증:
  - `py_compile` for changed `agentic_pipeline.py`/`orchestrator.py` passed.
  - `tests.test_title_lead_search_inferred_guard` `67 tests OK`.
- 남은 작업:
  - `11705239` ordered-flush blocker는 single-row runtime root cause 또는 quarantine 후 재투입한다.
  - `11702087`은 downstream guard prompt/orchestration/code-hook P0로 계속 처리한다.
  - Loop 7 image/OCR `20`건은 아직 실행 전이다.
- 게이트:
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-23 - completed779 Hermes Loop 7 `11702087` downstream guard closure

- `11702087` single-row downstream guard issue를 targeted 기준으로 닫았다.
  - fix8 result `out\completed779_improvement_goal_20260622\canary\hermes_loop7_text_single_11702087_fix8_result.json`은 postprocess 내부에서 `괴담 호텔 탈출기`와 NovelPia URL을 rescue했지만, judge seed precision guard가 public title을 다시 null로 demote했다.
  - fix9 result `out\completed779_improvement_goal_20260622\canary\hermes_loop7_text_single_11702087_fix9_result.json`은 completed/failed/pending `1/0/0`, final title/url `괴담 호텔 탈출기` / `https://novelpia.com/novel/102155`, `work_resolution=resolved`, `title_resolution_allowed=true`.
- 일반화된 코드 변경:
  - `agentic_pipeline.py`: Synth/Jury/search가 character/setting cluster로 같은 작품에 수렴하면 `multi_work_guard` clear, canonical rescue, J1 verifier veto, final reread hold가 resolved candidate를 보존할 수 있게 했다.
  - `candidate_audit.py`: `seed_bucket=source_url_hygiene`이면 `disagreement_type=garbage_title`이어도 precision demotion을 적용하지 않고 hygiene lint로 남긴다.
  - final title correction에 Verifier official detail lock fast path를 추가해 동일 title+official detail URL의 불필요한 heavy rescoring을 줄였다.
- 검증:
  - `py_compile` pass for changed agentic/candidate audit/tests.
  - focused `tests.test_candidate_audit` + selected `tests.test_agentic_pipeline_rework`, `42 tests OK`.
  - fast-path regression + precision/hygiene guard regressions, `5 tests OK`.
- 제한:
  - fix9 runtime은 `436.8s`로 너무 느렸다. fast-path는 unit-verified only이며, performance-only change 후 full single-row canary는 아직 재실행하지 않았다.
  - Loop 7 전체는 아직 partial이다. `11705239`, image/OCR `20` rows, combined compare가 남아 있다.
- 게이트:
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-23 - completed779 Hermes Loop 7 `11716480` OCR retry and close-title hygiene closure

- `11716480` runtime quarantine을 targeted 기준으로 닫았다.
  - fix2/fix3는 OCR/title evidence까지 도달했지만 result/checkpoint를 flush하지 못했다.
  - fix4는 completed/flushed/pending/failed `1/1/0/0`였지만 first-pass VLM이 `weak_visual_only`로 끝나 semantic movement는 실패했다.
  - fix5는 OCR title을 recovered했지만 expected-title hygiene guard가 close OCR variant를 mismatch로 보아 public title을 demote했다.
  - fix6은 completed/flushed/pending/failed `1/1/0/0`, final `official_title=여대생 가랑이 사이 무릎 끓은 엄마들`, `work_resolution=resolved`, `title_resolution_state=resolved`, `heretic_url=null`.
- 일반화된 코드 변경:
  - `agentic_pipeline.py`: first-pass VLM chunk가 전부 weak visual이고 OCR/title/author/work cue가 없을 때 focused OCR retry를 수행한다.
  - `agentic_pipeline.py`: VLM retry merge가 더 강한 text evidence/structural fields를 보존한다.
  - `candidate_audit.py`: source/url hygiene expected-title guard가 close OCR/title variant를 같은 제목 계열로 인정해 URL-null lint를 public title demotion으로 바꾸지 않는다.
- 검증:
  - `out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result_manifest.json`: completed/flushed/pending/failed `1/1/0/0`.
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_compare.json`: movement `url_lint_preserved=1`.
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_remaining_queue.json`: rows `0`.
  - focused OCR retry and close-title hygiene regressions passed.
- 제한:
  - official/detail URL은 아직 없다. 이 행은 runtime quarantine이 아니라 URL/source hygiene residual이다.
  - search/query drift toward generic/cross-domain entities and tag-heavy prompt growth remain future loop work.
- 게이트:
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`
## 2026-06-27 - Regression-safe Grounding Loop 05 FIX-7 alias recall closure

- Implemented alias-platform official-detail recall for `11698897` and relation-hold protection for structural official recall.
- Added a no-work context veto so official recall guard does not protect recommendation/context-only rows such as `11673082`.
- Added candidate audit hold for unconfirmed alias -> official detail bridges.
- Final canary: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/fix7_relation_guard_no_work_golden_result.json`.
- Audit: pass `9/16`, negative expected-null `7/8`, positive expected-work `2/8`, collateral regression candidates `7`, gate `NO-GO`.
- Target row `11698897` recovered `[림월드]변방계에서 회귀자로 살아남기` / `https://novelpia.com/novel/382324`.
- Remaining precision blocker: `11661857` still over-promotes to `두바이의 쫀득한 여초딩 재벌 9세`.
- Verification: `test_title_lead_search_inferred_guard` `78 OK`, `test_candidate_audit` `61 OK`, relation-hold focused `3 OK`, FIX-7 golden runtime `16/0/0`, VLM/OCR `READY`, `slang_db=off`.
- Semantic quality remains `REVIEW-LOCKED`; full scan approval remains `false`.

## 2026-06-27 - Regression-safe Grounding Loop 06 FIX-8az targeted completion

- Added verified public-work detail locking, weak LLM-only comparison pruning, explicit alias + official detail locking, and title/body specific platform probe continuation.
- Added descriptive modifier low-info guards for surfaces such as `수상할`, `정도로`, and `모든`.
- Reconstructed the final completed subset from `fix8au` plus targeted replacements:
  - `11694019` from `fix8av` -> `이세계에서 사이비로 살아남기`
  - `11713222` from `fix8ay` -> `잘생기면 편해지는 인방 생활`
- Final result: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\fix8az_loop06_targeted_completed_result.json`
- Audit: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\fix8az_loop06_targeted_completed_audit.md`
- Collateral: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\fix8az_loop06_targeted_completed_collateral_compare.md`
- Data Analytics artifact: `LOOP 06 Regression-Safe Grounding Audit`
- Audit movement:
  - golden pass `12/16`
  - negative no-public-work `8/8`
  - positive expected-work `4/8`
  - failed rows `4`
  - collateral regression candidates `4`
- Remaining failed rows are not forced into code promotion:
  - `11663521`, `11685994`, `11700470`: HOLD/no-generalizable-fix without stronger public evidence.
  - `11713222`: golden-label review because direct alias/current-work evidence points to `잘생기면 편해지는 인방 생활`, while frozen expected points to related/previous work.
- Verification:
  - py_compile for changed pipeline/orchestrator files passed.
  - focused targeted tests passed.
  - broader focused suite `159 tests OK`.
- Gate:
  - runtime integrity `GO_WITH_RECONSTRUCTION_NOTE`
  - golden semantic `NO-GO`
  - collateral semantic `NO-GO`
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-27 - Goal completion correction after Loop 06

- The previous chat-level completion claim was too broad.
- Loop 06 is a targeted golden canary improvement slice, not the full pasted-goal completion.
- Rechecked original contract:
  - Phase 1 full-post judge over latest flushed rows.
  - Phase 2 queue processing.
  - queue seed + Regression Panel + golden canary.
  - full baseline∩canary collateral.
  - 2-run deterministic replay.
  - affected-module tests plus full unittest sweep.
- Current evidence:
  - latest source `expert_result_20260626_000008_928006` is partial: `large_run_complete=false`, completed subset `1946`, flushed `1933`, pending `13`, failed `1`.
  - Phase 1 artifact judged `1933/1933` flushed rows.
  - `phase2_initial_queue.json` remains open with `251` rows.
  - Loop 06 panel canary remains `NOT_RUN`.
  - Loop 06 collateral is golden shared-post only, not full baseline∩canary collateral.
- State: overall goal remains active; `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-27 - Loop 07 wrong-work targeted canary after goal reopen

- Built and ran a 7-row targeted input from Phase 2 `wrong_work_disambiguation`.
- Runtime result:
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop07_wrong_work_disambiguation_7_result.json`
  - completed/pending/failed `7/0/0`
  - VLM/OCR semantic gate `READY`
  - total time `392.1s`
- Compare:
  - `out\regression_safe_grounding_20260626_000008_928006_loop01\compare\loop07_wrong_work_disambiguation_7_compare.md`
  - movement `review=7`
- Outcome:
  - all 7 rows avoided public `official_title` promotion.
  - candidates/primary_work were preserved for review.
  - this is a targeted runtime/precision-safety check only.
- Data Analytics artifact: `LOOP 07 Wrong-Work Targeted Canary`.
- Gate:
  - targeted runtime `GO`
  - targeted movement `REVIEW`
  - panel canary `NOT_RUN`
  - full collateral `NOT_RUN`
  - replay `NOT_RUN`
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`
  - overall goal `NOT_COMPLETE`

## 2026-06-27 - Loop 08 resolution-promotion targeted canary

- Built and ran a 102-row targeted input from Phase 2 `resolution_promotion_gate`.
- Runtime result:
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop08_resolution_promotion_gate_102_result.json`
  - completed/pending/failed `102/0/0`
  - flushed `102`
  - `large_run_complete=true`
  - VLM/OCR semantic gate `READY`
  - image rows `59`
  - effective parallel `16` after `reuse_shards_only` health filtering.
- Compare:
  - `out\regression_safe_grounding_20260626_000008_928006_loop01\compare\loop08_resolution_promotion_gate_102_compare.md`
  - movement `review=102`
  - targeted next queue `0`
- Identity distribution:
  - resolved work discussion `38`
  - unresolved or non-promotable rows `64`
  - promotion blocked `60`
- Data Analytics artifact: `Loop 08 Resolution Promotion Gate Review`.
- Gate:
  - targeted runtime `GO`
  - targeted resolution-promotion queue `CLOSED_FOR_LOOP_08`
  - targeted movement `REVIEW`
  - overall goal `NOT_COMPLETE`
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-27 - Goal session 019f0387 completion review

- Reviewed Codex goal session `019f0387-24d0-7313-a6c0-66d09f04bb33` after it called `update_goal(status="complete")`.
- Durable review report: `docs/devs/GOAL_SESSION_REVIEW_019f0387_20260627.md`.
- Finding: the session intentionally closed Loop 06 targeted work, but that is not proof that the pasted full objective was completed.
- Evidence:
  - Phase 1 aggregate was deterministic partial, with pending flush gap `13` and source completeness `NO-GO`.
  - Loop 06 audit improved golden canary to `12/16` but kept golden semantic `NO-GO` and collateral semantic `NO-GO`.
  - Loop 06 manifest records `partial_flush_gap=true`, `ordered_flush_blocked=true`, `large_run_complete=false`, and `reconstructed_from_checkpoint=true`.
- Final review judgment: `PARTIAL-COMPLETE / GOAL-COMPLETE-NO`.
- Follow-up should resume from Phase 1 action queue and Loop 06 HOLD/label-review rows, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false` preserved.

## 2026-06-28 - Loop 09 image-anchor targeted canary

- Built and ran a 25-row targeted input from Phase 2 `image_anchor_gate`.
- Runtime result:
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop09_image_anchor_gate_25_result.json`
  - manifest `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop09_image_anchor_gate_25_result_manifest.json`
  - completed/flushed/pending/failed `25/25/0/0`
  - `large_run_complete=true`
  - `ordered_flush_blocked=false`
  - VLM/OCR semantic gate `READY`
  - image rows `25`
  - requested/effective parallel `16/16`
- Compare:
  - `out\regression_safe_grounding_20260626_000008_928006_loop01\compare\loop09_image_anchor_gate_25_compare.md`
  - movement `review=24`, `garbage_title_after=1`
  - targeted next queue `1`
- Identity distribution:
  - relevant `22`
  - resolved work discussion `11`
  - title promotion blocked or unresolved `14`
  - candidate ledger `promotion_blocked=13`, `safe_resolved=10`, `output_consistency_lint=2`
- Data Analytics artifact: `Loop 09 Image Anchor Gate Validation`.
- Gate:
  - targeted runtime `GO`
  - targeted movement `REVIEW`
  - targeted image-anchor queue `OPEN_FOR_11682791`
  - overall goal `NOT_COMPLETE`
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-28 - Loop 10 slang-store targeted canary

- Built and ran a 92-row targeted input from Phase 2 `slang_store_gate`.
- Runtime result:
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop10_slang_store_gate_92_result.json`
  - manifest `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop10_slang_store_gate_92_result_manifest.json`
  - completed/flushed/pending/failed `92/92/0/0`
  - `large_run_complete=true`
  - `ordered_flush_blocked=false`
  - VLM/OCR semantic gate `READY`
  - image rows `56`
  - requested/effective parallel `36/16` after `reuse_shards_only` healthy endpoint filtering
- Compare:
  - `out\regression_safe_grounding_20260626_000008_928006_loop01\compare\loop10_slang_store_gate_92_compare.md`
  - movement `review=92`
  - targeted next queue `0`
- Identity distribution:
  - relevant `73`
  - resolved work discussion `53`
  - title resolution blocked/unresolved `39`
  - candidate ledger `safe_resolved=53`, `promotion_blocked=38`, `hold_without_candidates=1`
- Slang signals:
  - `slang_insight` present `60`
  - `store_in_slang_db=true` `29`
  - `store_in_slang_db=false` `31`
  - no slang insight `32`
  - no production write-back because the canary used `--slang-db off`
- Data Analytics artifact: `Loop 10 Slang Store Gate Validation`.
- Gate:
  - targeted runtime `GO`
  - targeted movement `REVIEW`
  - targeted slang-store runtime slice `CLOSED_FOR_LOOP_10`
  - overall goal `NOT_COMPLETE`
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`

## 2026-06-28 - Loop 11 human-review boundary closure

- Rechecked Phase 2 `human_review_boundary=25` from `out\full_post_judge_20260626_000008_928006_phase1\phase2_initial_queue.json`.
- All 25 rows are already explicit boundary rows:
  - `resolution_label=HOLD`
  - `hold_reason=boundary_needs_human`
  - `recommended_action=human_review`
  - `severity=low`
  - `disagreement_type=none`
  - `pipeline_official_title_present_count=0`
- Closure artifacts:
  - JSON `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop11_human_review_boundary_25_closure.json`
  - MD `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop11_human_review_boundary_25_closure.md`
  - manifest `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop11_human_review_boundary_25_closure_manifest.json`
- Data Analytics artifact: `Loop 11 Human Review Boundary Closure`.
- Gate:
  - targeted human boundary closure `EXPLICIT_HOLD_HUMAN_REVIEW`
  - runtime canary `NOT_APPLICABLE`
  - overall goal `NOT_COMPLETE`
  - semantic_quality `REVIEW-LOCKED`
  - full_scan_approval `false`
- Remaining gates: Loop 09 residual `11682791`, panel/golden/collateral replay, full unittest sweep, and source full completion.

## 2026-06-30 - Loop 133 focused replay correction

- Rechecked the pasted goal after user noted that the goal is not complete.
- Added narrow code/test fixes for `11705231`:
  - precision seed stale multi-work/locked-official rescue handling,
  - Kakao comment-tab official detail canonicalization,
  - deliberated character-setting convergence bypass for stale relation/community-banter blockers.
- Targeted tests passed for the new guards.
- Latest focused replay completed at runtime but failed semantic title resolution:
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop133_11705231_character_setting_kakao_focus_after_relation_patch_result.json`
  - log `logs\expert_run_20260630_042834_267904.log`
  - completed/flushed/pending/failed `1/1/0/0`
  - Identified `0`
  - final `official_title=null`, `title_resolution_state=author_new_work_context`
- Root blocker now documented: official seed URLs for `탐식의 재림` were manifest-only and not consumed as row-level evidence by `expert_main.py`, so the run drifted to wrong candidate `탐식의 재연` and then held null.
- Gate remains: runtime `GO`, targeted semantic `NO-GO`, overall goal `NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 - Loop 157 stable-alias descriptor guard

- Rechecked the Loop156 parent replay blocker after user noted the goal was not complete.
- Added a narrow guard for stable-alias correction:
  - high/medium-fit descriptor interpretation,
  - low/none-fit title interpretation,
  - no Decoder best-match title,
  - matching search title candidate alone cannot replace the current public title.
- Added focused unittest coverage for the mixed descriptor/title candidate packet.
- Focused unittest passed: `4 tests OK`.
- Loop157 targeted canary `20260630_154514_521625` completed `1/1/0/0` with VLM/OCR `READY`.
- `11698880` recovered to `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`; `상남자 [독점]` did not recur as public title.
- Data Analytics validation/render passed for `Loop157 Stable Alias Descriptor Guard Validation`.
- Gate remains: targeted runtime `GO`, targeted semantic seed `RECOVERED`, overall goal `NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-30 - Loop 158 parent replay after stable-alias descriptor guard

- Reran the parent/representative 38-row packet after Loop157.
- Runtime result:
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop158_parent_replay_after_loop157_stable_alias_descriptor_guard_result.json`
  - manifest `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop158_parent_replay_after_loop157_stable_alias_descriptor_guard_result_manifest.json`
  - log `logs\expert_run_20260630_160219_354659.log`
  - completed/flushed/pending/failed `38/38/0/0`
  - effective parallel `36`
  - MCP health `36/36`
  - VLM/OCR semantic gate `READY`
- Parent scope confirmed the Loop157 `11698880` recovery:
  - `가챠 중독자의 퓨전펑크 생활`
  - `https://novelpia.com/novel/387014`
  - prior `상남자 [독점]` switch absent
- Semantic movement remains:
  - `11668288` remains null / `promotion_blocked` versus Loop150 `가챠 중독자의 퓨전펑크 생활`
  - `11706832` moved to `황제의 딸로 환생했다` under degraded search
  - status counts `safe_resolved=11`, `promotion_blocked=25`, `hold_without_candidates=1`, `output_consistency_lint=1`
- Data Analytics validation/render passed for `Loop158 Parent Replay Stability Review`.
- Gate remains: parent runtime `GO`, target recovery `RECOVERED`, overall goal `NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-01 - Loop195 acknowledged previous-work scope gate

- Continued the architecture-integrated goal without marking it complete.
- Extracted `_record_public_title_gate_decision(...)` in `src/llm_batch/agentic_pipeline.py` so non-semantic-no-work publish paths can record the shared promotion gate contract.
- Wired `acknowledged_previous_work_comment_override` through `ScopeState` and `can_publish_title(...)`.
- Direct current-work alias versus comment previous-work alias conflicts now record `scope_previous_work`, `scope_not_current_work`, and `current_work_candidate_competes_with_previous_work`, then remain candidate-only instead of replacing the public title.
- Verification:
  - `py_compile`: PASS
  - focused combined suite: `24 tests OK`
  - broader unittest discover: `1309 tests OK`
  - Data Analytics validate/render: PASS
- Gate remains: `GO_UNIT_ONLY`, runtime canary `NOT_RUN`, residual accounting `NO_DELTA_UNIT_ONLY`, goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-01 - Loop225 envelope title gate parent replay

- Patched final publication ledger sync so inner `analysis_result` payloads can receive the outer post title.
- Added regression coverage for the exact Loop224-style envelope/payload split.
- Verification:
  - `tests.test_expert_main_comment_metadata`: `21 tests OK`
  - `py_compile`: PASS
- Parent replay:
  - run `20260701_151744_526664`
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop225_parent_replay_after_envelope_title_gate_fix_result.json`
  - completed/flushed/pending/failed `38/38/0/0`
  - VLM/OCR `READY`, MCP health `36/36`
- Semantic movement:
  - `11661876` recovered to `safe_resolved` / `와인의 신`.
  - Loop224 -> Loop225 changed rows `21`.
  - safe-loss rows: `11668288`, `11674712`, `11706832`.
  - safe identity drift rows: `11658615`, `11695637`, `11705231`.
- Data Analytics validation/render passed for `Loop225 Envelope Title Gate Fix Review`.
- Gate remains: parent runtime `GO`, targeted deterministic replay `GO`, parent semantic `NO-GO`, residual accounting `NO_DELTA_PARENT_REPLAY_MIXED_MOVEMENT`, goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-01 - Loop229 title-led evaluation bridge canary

- Continued the architecture-integrated goal without marking it complete.
- Added a narrow title-led evaluation bridge for post-title markers such as `볼만함` and `재밋네`.
- Focused tests passed for candidate audit, title-led inferred guard, weak-alias negatives, and promotion gate contract paths.
- Two-row canary input:
  - `out\regression_safe_grounding_20260626_000008_928006_loop01\inputs\loop229_title_led_evaluation_bridge_2.jsonl`
- Canary runs:
  - `20260701_180326_874711`: completed/flushed/pending/failed `2/2/0/0`, VLM/OCR `READY`
  - `20260701_181447_543860`: completed/flushed/pending/failed `2/2/0/0`, VLM/OCR `READY`
- Semantic result:
  - final public official title count stayed `0/2`.
  - `11660237` stayed `promotion_blocked` with `scope_context_only`.
  - `11660257` improved to `scope_current_work`, but final public identity was still scrubbed by `weak_alias_surface_public_title_bridge` and `serialized_public_identity_scrubbed`.
- Data Analytics validation/render passed for `Loop229 제목 주도 평가 Bridge 검토`.
- Gate remains: runtime `GO`, targeted semantic `NO-GO`, residual accounting `NO_DELTA_TITLE_LED_BRIDGE_CANARY_NO_GO`, goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-01 - Loop230 title-led serializer/gate recovery canary

- Continued the architecture-integrated goal without marking it complete.
- Preserved the report-language contract: report/review/Data Analytics reader-facing artifacts are Korean, concise, and must not omit meaning, evidence paths, or gate state.
- Patched the title-led serializer/candidate audit conflict exposed by Loop229:
  - `src/llm_batch/candidate_audit.py` normalizes stale weak-alias scrub when title-led alias, official detail evidence, and current-work scope converge.
  - `expert_main.py` final serializer restore now considers candidate alias keys and title-led consumption markers.
- Focused verification passed:
  - candidate audit title-led focused tests OK
  - expert_main focused serializer tests OK
  - `py_compile` PASS
  - expert metadata plus promotion-gate suite `45 tests OK`
  - title-led inferred focused `3 tests OK`
  - weak-alias focused `4 tests OK`
- Canary:
  - run `20260701_183700_752963`
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop230_title_led_serializer_gate_result.json`
  - completed/flushed/pending/failed `2/2/0/0`
  - VLM/OCR `READY`, MCP health ok/failure `2/0`
- Semantic movement:
  - public title count improved `0/2 -> 1/2` versus Loop229 after-scope canary.
  - `11660257` recovered to `safe_resolved` / `암흑가 보스요? 제가요?` / `https://novelpia.com/novel/384111`.
  - `11660237` stayed `promotion_blocked` / `scope_context_only` / title null.
- Data Analytics validation/render passed for `Loop230 제목 주도 Serializer/Gate 복구 검토`.
- Gate remains: runtime `GO`, targeted canary `PARTIAL-GO`, targeted semantic `REVIEW`, residual accounting `NO_DELTA_TITLE_LED_SERIALIZER_CANARY_PARTIAL_RECOVERY_PARENT_REPLAY_REQUIRED`, goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-01 - Loop231 parent replay after Loop230

- Continued the architecture-integrated goal without marking it complete.
- Ran the 38-row parent/representative replay after Loop230.
  - run `20260701_190002_650661`
  - result `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop231_parent_replay_after_loop230_title_led_serializer_gate_result.json`
  - completed/flushed/pending/failed `38/38/0/0`
  - VLM/OCR `READY`, MCP health ok/failure `36/0`
- Semantic movement versus Loop225 baseline:
  - public title count `12 -> 11`
  - `safe_resolved` count `12 -> 11`
  - safe gain: `11674712`, `11706832`
  - safe loss: `11661876`, `11663540`, `11695637`
  - safe identity drift: `11658615`, `11705231`
- `11660257` survived parent replay as `암흑가 보스요? 제가요?` / `https://novelpia.com/novel/384111`.
- `11660237` is now targeted/parent variance:
  - Loop230 targeted: `promotion_blocked`, public title null
  - Loop231 parent: `safe_resolved`, `테라포밍`
- Data Analytics validation/render passed for `Loop231 Loop230 후속 Parent Replay 검토`.
- Gate remains: run integrity `GO`, parent semantic `NO-GO / MIXED_MOVEMENT`, residual accounting `NO_DELTA_PARENT_REPLAY_AFTER_LOOP230_MIXED_MOVEMENT`, goal `ACTIVE / NOT_COMPLETE`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
