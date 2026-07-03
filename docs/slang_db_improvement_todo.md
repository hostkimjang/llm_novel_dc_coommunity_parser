# Slang DB Improvement TODO

## 2026-07-04 Loop374 signal-idle golden18 slang 주의사항

- [x] 이번 회차는 slang DB write-back이 아니라 runtime stall guard와 golden18 runtime proof다.
- [x] `--slang-db off` 조건으로 실행했다.
- [x] `11660237`은 `테라포밍`으로 resolved/pass지만 단일 런 결과만으로 hard-hold 완화를 선언하지 않는다.
- [x] `11698880`은 `가챠 중독자의 퓨전펑크 생활` evidence preserved unresolved/pass지만 public title은 `null`이다.
- [ ] search recovery와 expected-answer 실패 5건을 닫기 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, golden18 runtime `GO / 18 of 18`, golden expected-answer `NO-GO / 13 of 18`, golden shared collateral `NO-GO / 8 regressions`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop366 golden18 rerun slang caveat

- [x] 이번 회차는 slang DB write-back이 아니라 current HEAD golden18 runtime/semantic 증거 갱신이다.
- [x] `--slang-db off` 조건으로 실행했다.
- [x] `11713222` expected correction은 current rerun에서도 유지됐다.
- [x] `11660237`은 `테라포밍`으로 통과했지만, 단일 런 결과만으로 alias/slang hard-hold 완화를 선언하지 않는다.
- [x] `11698880`은 로그상 `가챠 중독자의 퓨전펑크 생활` 앵커를 보았지만 최종 public title은 `아카데미 생존 갤러리`라 실패로 남았다.
- [ ] search degraded와 golden expected-answer 실패 7건을 닫기 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, golden18 runtime `GO / 18 of 18`, golden expected-answer `NO-GO / 11 of 18`, golden shared collateral `NO-GO / 9 regressions`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop365 source-native expected correction caveat

- [x] 이번 회차는 slang DB write-back이 아니라 `11713222` frozen golden expected 교정이다.
- [x] `잘생인방`은 본문 직접 표면으로 current work `잘생기면 편해지는 인방 생활`을 가리킨다.
- [x] `잘생인편`은 댓글의 `전작도 ...`, `안봐서 ...` 문맥상 previous/mentioned work `잘생기면 인생이 편하다`다.
- [x] R1 하드코딩 cue 리스트 확장은 하지 않았다.
- [x] 기존 Loop363 결과 재감사로 expected-answer pass가 `13/18 -> 14/18`로 개선됐지만 `canary_semantic_gate=NO-GO`는 유지했다.
- [ ] search degraded와 남은 golden expected-answer 실패 4건을 닫기 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, golden expected-answer `NO-GO / 14 of 18`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop364 shared gate / slang caveat

- [x] 이번 회차는 slang DB write-back이 아니라 shared promotion gate wrong-publish 보정이다.
- [x] R1 하드코딩 cue 리스트 확장은 하지 않았다.
- [x] `11694019`, `11700470`은 public title `null`로 wrong publish 차단을 확인했다.
- [x] `11713222`는 Loop365에서 slang/alias 추가 없이 blind/source-native 판정으로 정당 publish 및 golden expected 교정을 완료했다.
- [ ] search degraded와 남은 expected-answer 실패를 닫기 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, code contract `GO_UNIT`, targeted runtime `GO / 3 of 3`, wrong-publish closure `PARTIAL_GO / 2 of 3`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop363 golden18 runtime proof caveat

- [x] 이번 회차는 slang DB write-back이 아니라 golden18 runtime production proof다.
- [x] golden18 runtime은 `18/18`로 완주했지만 expected-answer audit은 `NO-GO / 13 of 18`이다.
- [x] Search evidence는 `REVIEW / search_degraded_observed`, `unrecovered_degraded_total=19`로 남았다.
- [x] `11660237`, `11698880`은 runtime completed지만 public title `null`이라 safe-loss hard-hold 완화 근거가 아니다.
- [ ] search degraded와 golden expected-answer 실패 5건을 닫기 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, golden18 runtime `GO / 18 of 18`, golden expected-answer `NO-GO / 13 of 18`, collateral active lane `REVIEW-LOCKED / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop360 background watchdog caveat

- [x] 이번 회차는 slang DB write-back이 아니라 background watchdog hardening이다.
- [x] Loop359 completion `0/0/0/0`과 LLM watchdog pause를 분리 기록했다.
- [x] N5/runner watchdog-off 계약은 alias/slang 승격 판단을 바꾸지 않는다.
- [ ] N5 `15/15`, golden18 `18/18`, full375/bounded completion 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, background runtime `STALLED_LLM_WATCHDOG / NOT_APPROVAL`, collateral active lane `REVIEW-LOCKED / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop359 current HEAD evidence refresh caveat

- [x] 이번 회차는 slang DB write-back이 아니라 current HEAD runtime evidence refresh 재발주다.
- [x] N5/golden18/full375/bounded1200 모두 `slang-db off`와 search 포함 non-light 조건으로 발주했다.
- [x] active loop를 대형 run 완료 대기가 아니라 collateral residual `105` lane으로 분리했다.
- [ ] N5 `15/15`, golden18 `18/18`, full375/bounded completion 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, dispatch `GO_CURRENT_HEAD_BACKGROUND_DISPATCH`, runtime completion `IN_PROGRESS / NOT_APPROVAL`, collateral active lane `REVIEW-LOCKED / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop358 LLM stream stall guard caveat

- [x] 이번 회차는 slang DB write-back이 아니라 LLM stream runtime harness guard다.
- [x] `11666713` image-free replay에서 search `GO`와 runtime flush 실패를 분리했다.
- [x] `LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS`, `LLM_STREAM_IDLE_TIMEOUT_SECONDS` 계약은 alias/slang 승격 판단을 바꾸지 않는다.
- [ ] timeout env 후속 replay 전까지 alias/slang 품질 승인 또는 residual closure로 세지 않는다.
- Gate: slang DB write-back 아님, runtime `ABORTED_LLM_STREAM_STALL`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop357 known-alias comparison boundary caveat

- [x] 이번 회차는 slang DB write-back이 아니라 known-title abbreviation comparison boundary 계약 보정이다.
- [x] `괴담텔` primary alias release와 `괴담동` comparison target 차단을 분리했다.
- [ ] runtime replay 전까지 alias/slang 품질 승인 또는 residual closure로 세지 않는다.
- Gate: slang DB write-back 아님, code contract `GO_UNIT`, runtime replay `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop356 current HEAD evidence refresh caveat

- [x] 이번 회차는 slang DB write-back이 아니라 current HEAD runtime evidence refresh 발주다.
- [x] N5/golden18/full375/bounded1200 모두 `slang-db off`와 search 포함 non-light 조건으로 발주했다.
- [ ] N5 `15/15`, golden18 `18/18`, full375/bounded completion 전 alias/slang 품질 승인 또는 hard-hold 완화를 선언하지 않는다.
- Gate: slang DB write-back 아님, dispatch `GO_CURRENT_HEAD_BACKGROUND_DISPATCH`, runtime completion `IN_PROGRESS / NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop355 wrong-work alias contract caveat

- [x] `댓천마`, `전1시`, `탐재`는 slang DB write-back이 아니라 `KNOWN_TITLE_ABBREVIATIONS` 기반 work bridge 계약으로만 다뤘다.
- [x] registry 단독 승격이 아니라 작품 내부 cue + official detail recall 조건을 테스트했다.
- [ ] post-patch runtime replay 전까지 alias/slang 품질 승인 또는 residual closure로 세지 않는다.
- Gate: slang DB write-back 아님, contract `GO_UNIT_CONTRACT_ONLY`, runtime closure `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop354 current residual alias/runtime caveat

- [x] current residual action lane에서 alias/runtime 관련 잔여를 다시 확인했다.
  - residual `105`, `REPROCESS=77`, `HOLD=28`
  - `known_alias_runtime_replay_required=3`: `11706827`, `11708443`, `11714907`
  - `repair_safe_loss=72`, `repair_after_wrong_work=5`
- [x] forced non-light N5/full375/bounded1200/golden18은 alive/partial snapshot일 뿐 slang/alias 품질 승인 근거가 아니다.
- [ ] `known_alias_runtime_replay_required=3`은 unit contract와 current runtime flush를 분리해 재검증한다.
- [ ] N5 `15/15`, golden18 `18/18`, full375/bounded completion 전 hard-hold 완화 또는 2026-06-28 golden GO 대체 판단을 하지 않는다.
- Gate: slang DB write-back 아님, forced action lane `GO_QUEUE_RESHAPE_NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop347 known alias contract / runtime caveat

- [x] `11706827`, `11714907`은 slang DB write-back이 아니라 shared curated-alias work cue 계약으로만 보강했다.
  - `기계공주 -> 헌터갤러리의 국가권력급 기계공주`: 제목의 `일상물` 작품 톤 cue.
  - `아생갤 -> 아카데미 생존 갤러리`: 작가/정실/라나 character-relation cue.
- [x] `11708443`은 기존 Loop324/325 계약이 있으나 Loop347 runtime flush 증거는 없다.
- [x] Loop347 runtime replay는 search health `2/2 OK` 후 VLM chunk에서 멈췄고 manifest `0/0/0/0`이라 approval 근거가 아니다.
- [ ] `11706827`, `11708443`, `11714907`은 runtime/search recovery 또는 policy review로 계속 유지한다.
- Gate: slang DB write-back 아님, code contract `GO_UNIT_CONTRACT_ONLY`, runtime replay `ABORTED_VLM_STALL`, residual `123`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop341 known alias seed / slang caveat

- [x] Loop340 `known_alias_runtime_replay_required=6` 중 slang/alias registry로 일반화 가능한 2건만 반영했다.
  - `판초법사 -> 판초우의의 마법사`
  - `창월야 -> 월야환담 창월야`
- [x] 이번 변경은 slang DB write-back이 아니라 shared `KNOWN_TITLE_ABBREVIATIONS`와 work-cue code contract다.
- [x] 검증은 py_compile PASS, safe-loss contract `9`, abbreviation support `29`, arbiter curated alias guard `21` PASS다.
- [ ] targeted runtime replay 전까지 slang/alias 품질 승인 또는 residual closure로 세지 않는다.
- [ ] `11705230`, `11706827`, `11708443`, `11714907`은 runtime/search recovery 또는 policy review로 유지한다.
- Gate: slang DB write-back 아님, code contract `GO_UNIT`, runtime replay `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=126`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop332 collateral183 queue / slang caveat

- [x] `collateral183` source-native verdict 전체를 합산해 safe-loss/alias 관련 잔여 큐를 다시 고정했다.
  - 전체 `183/183`, validation issues `0`
  - safe-loss bucket `147`: `ACCEPT=42`, `REPROCESS=76`, `HOLD=29`
  - 전체 action queue: `ACCEPT=57`, `REPROCESS=95`, `HOLD=31`
- [x] 이번 회차는 slang DB write-back이 아니라 gate accounting/repair queue 산출물이다.
  - summary `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop332_collateral183_combined_source_native_queue.json`
  - report `docs\devs\loop_reports\LOOP_332_REPORT_20260703.md`
- [x] `REPROCESS=95` 중 slang/alias registry로 일반화 가능한 일부를 별도 후보로 올렸다.
  - Loop340에서 residual action queue 분해는 완료했다: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop340_collateral183_residual_action_queue.json`
  - Loop341에서 `known_alias_runtime_replay_required=6` 중 2건만 code contract seed로 반영했다.
- [ ] `ACCEPT=57`은 gate accounting 배선 전 regression count에서 차감하지 않는다.
- Gate: slang DB write-back 아님, collateral queue `REVIEW-LOCKED / COMPLETE_183_OF_183 / NOT_APPROVAL`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop331 current HEAD partial runtime / slang caveat

- [x] post-patch `11668283` current HEAD result를 분석했다.
  - `official_title=null`, `blocked_official_title=중세`, `promotion_blocked`, `title_resolution_state=adjacent`
  - `SEARCH_DEGRADED`, degraded `15/15` queries
- [x] safe-loss N5 partial review를 생성했다.
  - observed `1/15`
  - `11674712` r01 only, blind judge expected match false/incomplete
- [ ] N5 `15/15` 완료 전 slang/alias hard-hold 완화를 하지 않는다.
- [ ] golden18 `18/18` 완료 전 2026-06-28 golden GO를 current HEAD 증거로 대체하지 않는다.
- Gate: slang DB write-back 아님, targeted `11668283` `NO-GO`, N5 `REVIEW / PARTIAL`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop328 exact-title guard / slang caveat

- [x] `11668283 / 게임 마인드의 중세 현대인 좋았다...` non-light replay에서 `게임 마인드` slang insight는 생성됐지만 public title은 weak-source guard로 hold된 것을 확인했다.
- [x] 이번 수리는 slang DB write-back이 아니라 `candidate_audit.py` public title guard 계약이다.
- [x] `known_abbreviation_title_guard:*` current-work scope + exact title surface + work consumption marker 조건만 weak-source guard를 면제한다.
- [ ] guard patch 후 runtime replay 전까지 slang/alias 품질 승인으로 세지 않는다.
- Gate: slang DB write-back 아님, code contract `GO_UNIT`, runtime replay `PRE_PATCH_REPRODUCED_OVERBLOCK / NOT_APPROVAL`, post-patch runtime `NOT_RUN_AFTER_GUARD_PATCH`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop326 current HEAD runtime dispatch / slang caveat

- [x] Loop325 commit `1095d447` 기준으로 safe-loss N5, full375, bounded1200, golden18을 새 output 경로에 발주했다.
- [x] full375/bounded1200/golden18 초기 health는 search 포함 non-light다.
- [ ] 완료 전 slang/alias 품질 승인으로 세지 않는다.
- [ ] N5 `15/15`와 golden18 완료 전 hard-hold 완화 또는 6/28 golden GO 대체 판단을 하지 않는다.
- Gate: slang DB write-back 아님, launch health `GO_SEARCH_NONLIGHT_INITIAL`, runtime `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop325 curated alias work-cue contract / slang caveat

- [x] Loop324 `11708443 / 괴담출근` 회귀를 slang DB write-back 문제가 아니라 Pipeline/Arbiter 작품 담론 cue 불일치로 분리했다.
- [x] `_has_curated_alias_work_discussion_cue`를 추가해 curated alias 주변의 작품 담론 cue를 shared helper로 본다.
- [x] `괴담출근` 독창성/SCP cue와 `빌환` 표지변경 cue는 계약 테스트로 고정했다.
- [x] `괴담텔 ... 괴담동` comparison-only 음성 control은 계속 blocked다.
- [ ] Loop325는 slang/alias 품질 승인 근거가 아니다. current patch runtime replay 전까지 residual closure로 세지 않는다.
- [ ] search degraded 복구 전 `promotion_blocked`는 계속 `search-blind conditional`로 해석한다.
- Gate: slang DB write-back 아님, code contract `GO_UNIT_AND_BROADER_214`, runtime replay `NOT_RUN_CURRENT_PATCH`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-03 Loop324 non-light alias replay / slang caveat

- [x] Loop322 alias 7건을 `8c4ec326` 기준 search 포함 non-light로 재실행했다.
  - run `20260702_235904_452705`
  - completed/flushed/pending/failed `7/7/0/0`
  - `mcp_health_include_search=true`, `mcp_health_light_mode=false`
- [x] Loop323 light caveat를 대체할 non-light targeted evidence를 만들었다.
  - 산출물 `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop324_loop322_alias_targeted_nonlight_review.json`
  - summary `safe_resolved=2/7`, `promotion_blocked=5/7`, search degraded rows `5/7`
- [x] `절꺾않`은 safe-resolved로 개선됐다.
- [ ] Loop324는 slang/alias 품질 승인 근거가 아니다.
  - `괴담출근`은 Loop323 safe-resolved에서 Loop324 promotion_blocked로 회귀했다.
  - `빌환`, `지구온라인`, `성좌안무서움`은 아직 publication 수렴이 아니다.
- [ ] Loop314 N5/full375/bounded1200은 background 감시만 유지한다. 완료돼도 `8c4ec326` 이전 stale evidence로 태깅한다.
- Gate: slang DB write-back 아님, targeted replay `NO-GO`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.

## 2026-07-02 Loop322 safe-loss alias contract / slang caveat

- [x] Loop321 `repair_safe_loss=76` 중 7건을 shared `KNOWN_TITLE_ABBREVIATIONS` unit contract로 올렸다.
  - added `괴담출근`, `절꺾않`, `무마`, `아카엄창`, `성좌안무서움`, `빌환`, `지구온라인`
  - work cue added `표절`, `보러감`
- [x] `주전무`는 shared cue 폭 확장 위험 때문에 이번 slang/alias registry 승격에서 보류했다.
- [x] negated recommendation control `기계공주는 ㄴㄴ`는 registry hit가 있어도 release하지 않는 계약을 유지했다.
- [ ] Loop322 alias 7건은 targeted runtime replay 전까지 residual closure로 세지 않는다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다. 현재 Loop314 `4/15`.
- Gate: slang DB write-back 아님, code/unit contract `GO_UNIT_CONTRACT_ONLY`, runtime replay `NOT_RUN`, source-native review `REVIEW-LOCKED / COMPLETE_SOURCE_NATIVE_QUEUE`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop321 safe-loss source-native / slang caveat

- [x] `safe_loss_resolved_to_null` source-native review가 `147/147`까지 완료됐다.
  - delta `REPROCESS=15`, `ACCEPT=9`, `HOLD=4`
  - cumulative `REPROCESS=76`, `ACCEPT=42`, `HOLD=29`
- [x] `괴담출근`, `절꺾않`, `주전무`, `무마`, `아카엄창`, `아생갤`, `고능아`, `마녀도시`, `빌환`, `지구온라인` 등 직접 약칭 row는 repair 후보로 분리했다.
- [x] `이불사`, `랫따싶`, `기계공주`, `컵라면`, `시스템 딸깍`은 wrong-before/부정 추천/작가 표면/generic trope라 slang/alias registry repair로 세지 않았다.
- [x] 이미지/OCR/source 확인이 필요한 `따옴표`, `유어 네임`, `전생마왕`, `포티햄` 계열은 HOLD로 유지했다.
- [ ] `repair_safe_loss=76` 중 slang/alias registry로 일반화 가능한 항목만 shared gate/runtime replay 후보로 올린다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다. 현재 Loop314 `3/15`.
- Gate: slang DB write-back 아님, source-native review `REVIEW-LOCKED / COMPLETE_SOURCE_NATIVE_QUEUE`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop320 safe-loss source-native / slang caveat

- [x] `safe_loss_resolved_to_null` source-native review가 `119/147`까지 진행됐다.
  - delta `REPROCESS=8`, `ACCEPT=5`, `HOLD=2`
  - cumulative `REPROCESS=61`, `ACCEPT=33`, `HOLD=25`
- [x] `괴담 호텔 탈출기`, `판초법사`, `월야환담`, `창월야`, `기계공주`, `탐식의 재림` 직접/캐릭터 bridge row는 repair 후보로 분리했다.
- [x] `이블파티 -> 나의 악당들`, `아프리카 의 독재자가 되었다 .`, `도굴꾼`, `삼국지 마대 가 되었다`는 wrong-before 또는 prior-work/동음 후보라 slang/alias registry repair로 세지 않았다.
- [x] `11706844`는 OCR/canonical title mismatch가 있어 native image/canonical review 전까지 HOLD한다.
- [ ] `repair_safe_loss=61` 중 slang/alias registry로 일반화 가능한 항목만 shared gate/runtime replay 후보로 올린다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다. 현재 Loop314 `3/15`.
- Gate: slang DB write-back 아님, source-native review `REVIEW-LOCKED / PARTIAL`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop318 safe-loss source-native / slang caveat

- [x] `safe_loss_resolved_to_null` source-native review가 `104/147`까지 진행됐다.
  - delta `REPROCESS=5`, `ACCEPT=7`, `HOLD=3`
  - cumulative `REPROCESS=53`, `ACCEPT=28`, `HOLD=23`
- [x] `아생갤`, `랫따싶`, `니생들`, `괴담텔` 직접 약칭/작품 내부 맥락 row는 repair 후보로 분리했다.
- [x] `버거피아` 이벤트, Re:Zero 캐릭터 페이지, `타락` generic 추천어, `스페이스 오페라` wrong-title은 slang/alias registry repair로 세지 않았다.
- [x] `11698880`은 `가챠펑크` bridge가 있어도 known variance/secondary comparison control이라 registry write-back이나 hard-hold 완화 근거로 쓰지 않는다.
- [ ] `repair_safe_loss=53` 중 slang/alias registry로 일반화 가능한 항목만 shared gate/runtime replay 후보로 올린다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다. 현재 Loop314 `3/15`.
- Gate: slang DB write-back 아님, source-native review `REVIEW-LOCKED / PARTIAL`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop317 safe-loss source-native / slang caveat

- [x] `safe_loss_resolved_to_null` source-native review가 `89/147`까지 진행됐다.
  - delta `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`
  - cumulative `REPROCESS=48`, `ACCEPT=21`, `HOLD=20`
- [x] `엑칼뽑`, `괴담텔`, `격투천재`, `판초법사`, `아생갤`, `여신애호` 등 직접 약칭 row는 repair 후보로 분리했다.
- [x] `류서란(perfect)`는 로컬 character bridge 근거가 없어 slang/alias registry repair가 아니라 HOLD로 유지했다.
- [x] `혼후순결` plot element, `유희왕` generic franchise row는 alias/slang repair로 세지 않았다.
- [ ] `repair_safe_loss=48` 중 slang/alias registry로 일반화 가능한 항목만 shared gate/runtime replay 후보로 올린다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다. 현재 Loop314 `3/15`.
- Gate: slang DB write-back 아님, source-native review `REVIEW-LOCKED / PARTIAL`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop316 safe-loss source-native / slang caveat

- [x] `safe_loss_resolved_to_null` source-native review가 `74/147`까지 진행됐다.
  - delta `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`
  - cumulative `REPROCESS=41`, `ACCEPT=15`, `HOLD=18`
- [x] `21세기무림`, `갤질의사`, `아생갤`, `판초법사`, `김괴라리`, `전툴루` 등 직접 약칭 row는 repair 후보로 분리했다.
- [x] `마도줍 -> 소설 속 엑스트라`, 댓글 조롱 예시 `전독시`, cross-media `블아`는 slang/alias registry repair로 세지 않았다.
- [ ] `repair_safe_loss=41` 중 slang/alias registry로 일반화 가능한 항목만 shared gate/runtime replay 후보로 올린다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다.
- Gate: slang DB write-back 아님, source-native review `REVIEW-LOCKED / PARTIAL`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop314 current-HEAD runtime / slang caveat

- [x] Loop313 이후 이전 N5/full375/bounded/golden18 증거를 stale 또는 mixed evidence로 분리했다.
- [x] 현 HEAD `64864278` 기준 N5/golden18/full375/bounded1200을 새 경로로 발주했다.
- [x] golden18은 계속 rows `18`이고 `11660237`, `11698880`을 포함한다.
- [x] 새 full375/bounded/golden18/N5 first manifest는 `mcp_health_include_search=true`, `mcp_health_light_mode=false`다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다. 현재 Loop314 `3/15`.
- [ ] golden18 완료 후 6/28 golden GO를 현 HEAD 18행 기준으로 대체 가능한지 다시 판단한다.
- Gate: slang DB write-back 아님, N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, golden18 approval `NOT_OPEN`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop313 safe-loss alias contract / slang caveat

- [x] `악살싶` canonical title을 `악당은 살고 싶다`로 정정했다.
- [x] `전독시` -> `전지적 독자 시점`을 known-title abbreviation에 추가했다.
- [x] `전독시 영화 나왔었지` 같은 adaptation 논의를 work-cue로 인정했다.
- [x] `악신총애`는 동음 후보 위험 때문에 slang/alias registry 추가를 보류했다.
- [x] `회귀수선전`은 Loop315에서 character-setting bridge 계약 테스트로 고정했다. slang/alias registry write-back은 하지 않는다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다. 현재 Loop314 `3/15`.
- Gate: slang DB write-back 아님, code/unit contract `GO_UNIT`, runtime replay `NOT_RUN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop312 safe-loss source-native / slang caveat

- [x] `safe_loss_resolved_to_null` source-native review가 `59/147`까지 진행됐다.
  - delta `REPROCESS=7`, `ACCEPT=3`, `HOLD=5`
  - cumulative `REPROCESS=34`, `ACCEPT=9`, `HOLD=16`
- [x] `악살싶`, `전독시`, `기계공주`, `악신총애` 등 직접 약칭 row는 repair 후보로 분리했다.
- [x] multi-work row는 단일 slang/alias public title로 승격하지 않고 `ACCEPT`/after-hold preferred로 분리했다.
- [ ] `repair_safe_loss=34` 중 slang/alias registry로 일반화 가능한 항목만 shared gate/runtime replay 후보로 올린다.
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다.
- Gate: slang DB write-back 아님, N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, source-native review `REVIEW-LOCKED / PARTIAL`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop311 runtime refresh / slang caveat

- [x] search shard `/api/health`는 `3333/3334` 모두 HTTP 200으로 재확인했다.
- [x] N5 safe-loss plan은 background runner PID `90532`로 발주했다.
  - report 시점 result JSON `0/15`
  - 완료 전 flip rate 갱신이나 hard-hold 완화 근거로 쓰지 않는다.
- [x] golden18은 rows `18`이고 `11660237`, `11698880`을 포함한다.
  - tracked 상태지만 golden approval은 `NOT_OPEN`
- [x] full375/bounded1200은 search 포함 non-light이나 아직 approval 근거가 아니다.
  - full375 checkpoint/result `135/105`, pending `30`
  - bounded1200 checkpoint/result `205/188`, pending `17`
  - blockers `search_timeout_observed`, `search_degraded_observed`
- [ ] N5 result JSON `15/15` 완료 후 slang/alias 안정성 caveat를 새 flip 분석으로 갱신한다.
- Gate: slang DB write-back 아님, N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, golden18 approval `NOT_OPEN`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop300 publication alias support caveat

- [x] `unsafe_promotion_from_hold=26` 전체 source-native verdict를 닫았다.
  - `REPROCESS=14`, `ACCEPT=12`, validation issues `0`
  - summary `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop300_unsafe_promotion_from_hold_full_source_native_review.*`
- [x] slang/alias support는 source 직접 지지 여부와 분리했다.
  - 순수 작품 alias가 원문 title/source에서 직접 지지되면 URL이 없어도 보존한다.
  - sentence-like/meme/pronoun alias는 direct source support로 세지 않는다.
  - official title 전체 토큰이 약한 단어 support로 새는 경로를 막았다.
- [ ] golden18 완료 후 alias/slang 안정성 caveat를 다시 갱신한다.
- Gate: slang DB write-back 아님, golden18 approval `NOT_OPEN`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop297 background health / alias gate caveat

- [x] golden18 search-included replay가 아직 alias/slang 품질 승인 근거가 아님을 확인했다.
  - manifest snapshot `18/16/12/4/0`
  - `large_run_complete=false`
  - `mcp_health_light_mode=true`
  - blockers `manifest_light_health_only`, `search_degraded_observed`
- [x] `11660237`, `11698880` golden 편입은 유지하되, replay 완료 전 6/28 golden GO를 대체하지 않는다.
- [x] search degraded 복구 전 `promotion_blocked`는 `search-blind conditional`로만 해석한다.
- [ ] golden18 완료 후 alias/slang 안정성 caveat를 다시 갱신한다.
- Gate: slang DB write-back 아님, golden18 approval `NOT_OPEN`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop296 safe-loss N5 wrapper / alias 안정성 후속

- [x] 진짜 `N>=5` flip probe wrapper를 만들었다.
  - `tools\safe_loss_flip_rate_probe.py build-run-plan`
  - plan manifest `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop296_safe_loss_independent_n5_run_plan.json`
  - repeat_count_by_post `11674712=5`, `11660237=5`, `11698880=5`
- [x] slang/alias 판단에는 Loop288 실제 N5 증거를 유지한다.
  - `11660237` stable blind judge confirmed
  - `11674712`, `11698880` flip_rate `0.4`, `nondeterminism_unresolved`
- [ ] Loop296 15개 단일행 run을 실제 발주하면 alias 안정성 판단을 새 결과로 다시 갱신한다.
- Gate: slang DB write-back 아님, wrapper `GO_UNIT`, safe-loss current evidence `NO-GO`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop293 alias runtime / scope-order 후속

- [x] Loop293에서 `댓천마 -> 댓글창의 천재 마법사` registry 보강의 targeted runtime을 확인했다.
  - `11698890`은 public title resolved, `candidate_ledger_status=safe_resolved`, `scope=current_work`.
  - 단, `SEARCH_DEGRADED`라 alias 품질 승인이나 full approval 근거는 아니다.
- [x] `아생갤`은 alias 자체보다 final publication scope-order 문제가 더 컸음을 분리했다.
  - `11716448`은 `아카데미 생존 갤러리` 후보/URL이 보존됐지만 pre-patch runtime trace는 `context_only`.
  - `expert_main.py`에서 `current_work` scope를 먼저 평가하도록 계약을 보강했다.
- [ ] search degraded 복구 후 `아생갤` scope-order smoke를 다시 실행한다.
- [x] 진짜 `N>=5` flip probe wrapper를 만들었다. 현재 slang/alias 안정성 판단은 Loop288 N5 실제 결과 기준으로 유지한다.
- Gate: slang DB write-back 아님, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-02 Loop292 source-native strong alias code-registry 보강

- [x] Loop291 `REPROCESS` 근거 중 source-native strong alias를 production write-back 없이 code registry에만 반영했다.
  - `댓천마 -> 댓글창의 천재 마법사`
  - `전1시 -> 전지적 1인칭 시점`
  - `탐재 -> 탐식의 재림`
- [x] 이 반영은 `slang_db/slang_db.json` write-back이 아니다. `KNOWN_TITLE_ABBREVIATIONS`가 low-specific guard의 search 제거를 막고, public publish는 work-cue / official URL recall / promotion gate가 별도로 결정한다.
- [x] `아생갤`은 이미 registry에 있었고, Loop292에서는 `히로인/괴이/인간/정체/설정` 내부 토론을 work-cue로 인정하는 계약만 추가했다.
- [ ] post-patch 5-row runtime replay 후 alias registry 보강이 wrong-work 오귀결 없이 `repair_after_wrong_work`를 줄이는지 확인한다.
- Gate: slang DB 품질 승인 아님, full collateral approval `NOT_OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-06-28 regression-safe grounding Phase 2 slang-store gate

- [x] Phase 2 `slang_store_gate=92` 대상 입력을 `loop10_slang_store_gate_92.jsonl`로 생성했다.
- [x] Loop 10 canary를 `--slang-db off`로 실행해 production write-back 없이 결과만 산출했다.
- [x] runtime 완료: `loop10_slang_store_gate_92_result.json`, completed/flushed/pending/failed `92/92/0/0`, VLM/OCR `READY`.
- [x] compare 완료: movement `review=92`, targeted next queue `0`.
- [x] 결과에서 `slang_insight` present `60`, `store_in_slang_db=true=29`, `store_in_slang_db=false=31`, no slang insight `32`로 분리했다.
- [x] Loop61에서 `store_in_slang_db=true=29`를 review-only/no-writeback packet으로 분리했다: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop61_slang_writeback_review.md/json`.
- [x] Loop61에서 current DB cross-check를 수행했다: 19 unique terms 모두 기존 DB에 존재, 6 terms는 multi-title/bucket, `slang_db/slang_db.json` 수정 없음.
- [x] Loop61 결론: `CLOSED_AS_REVIEW_ONLY_NO_WRITEBACK`; production slang DB write-back은 승인/실행하지 않았다.
- [x] Loop62에서 full-panel residual map을 만들며 남은 P0 `slang_pollution_public_title=7`을 별도 targeted lane 후보로 기록했다: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop62_full_panel_residual_map.md/json`.
- [x] Loop63에서 `P0C_slang_pollution_public_title=7` targeted rerun을 완료했다: `DEMOTED_TO_NULL=4`, `VERIFIED_SAME_PUBLIC_TITLE=3`, VLM/OCR `READY`.
- [x] Loop64에서 P0E wrong-title-switch lane의 slang-axis 교차 row `11716448`은 public title `null`로 demote/promotion-blocked 처리됐다. 이 결과는 P0E targeted review evidence일 뿐 slang DB approval은 아니다.
- [ ] Loop 10 next queue `0`을 slang DB 품질 승인이나 full scan approval로 쓰지 않는다.
- [ ] Loop63 P0C targeted review를 slang DB 품질 승인, full-panel collateral approval, 또는 full scan approval로 쓰지 않는다.
- [ ] Loop64 P0E targeted review를 slang DB 품질 승인, full-panel collateral approval, 또는 full scan approval로 쓰지 않는다.
- [ ] 2026-06-18 queue(`94` route / `22` pollution_risk)와 이번 Phase 2 queue(`92` slang_db_review)는 서로 다른 source/run 기준이므로 count를 합산하지 않는다.

## 2026-06-18 full_post_judge slang axis review queue

- [x] `out/full_post_judge_20260616_224555_632905` 전수 판정에서 slang axis를 `precomputed.slang_axis_route=="llm"` 행으로 제한했다.
- [x] slang route 대상은 `94`건이고, deterministic `na`는 `2152`건이다.
- [x] LLM-route slang verdict는 `ok=72`, `pollution_risk=22`로 집계됐다.
- [x] 이번 작업은 `slang_db` write-back 없이 산출물과 queue만 생성했다.
- [ ] `slang_db_review=22`는 DB 반영 전 사람 검수 packet으로 분리한다.
- [ ] store=true인데 `pollution_risk`인 `11`건(`11652206`, `11660238`, `11674694`, `11676359`, `11679537`, `11694044`, `11694049`, `11703674`, `11706838`, `11716448`, `11718077`)은 오염 가능성 우선순위로 검토한다.
- [ ] resolved title search `Missing`과 slang decode/store true가 겹치는 case는 title 확정과 alias 저장을 분리해 재판정한다.

## 2026-06-01 image OCR variant public context overstatement

- [x] v458 `11718082`에서 `store_in_slang_db=false`여도 `slang_insight.cultural_context`가 작품 설정/캐릭터 관계/커뮤니티 약칭/OCR 오인처럼 과장될 수 있음을 확인했다.
- [x] v460 보강에서 이미지 OCR 변형 표면은 final anchor를 `image`로 남기고, slang context는 packet-local OCR/표지/이미지 장면 단서로만 낮추도록 했다.
- [x] v460 result에서 `11718082`는 `slang_insight=null`, Slang DB flush `titles=0`으로 old context overstatement가 재현되지 않았다.
- [ ] expanded review에서 `image_ocr_variant_not_title_in_post` flag가 있는 packet의 `slang_insight` public context가 저장 차단과 별개로 과장되지 않는지 별도 bucket으로 확인한다.

## 2026-05-31 exact-title / author surface / 문장형 후보 표시 정리

- [x] exact-title surface만 있는 경우 `slang_insight`를 공개 출력하지 않고 Slang DB 저장도 하지 않는다.
- [x] `양파랑`처럼 author role로 식별된 surface는 BatchMem abbreviation alias로 승격하지 않고 author mapping으로만 유지한다.
- [x] 문장형/합성형 surface는 저장 차단 상태와 정제 alias 후보를 분리해 대시보드에 표시한다.
- [x] v336 `11718117`에서 `slang_insight=null`, Slang DB flush `titles=0`, `BatchMem: 약칭 즉시등록 '양파랑'` 없음으로 확인했다.
- [ ] expanded review에서 `exact_title_not_alias`, `author_surface_as_alias`, `sentence_like_alias_surface`를 같은 저장 차단으로 묶지 말고 subtype별 recall/precision 영향을 분리한다.

## 2026-05-31 OCR conflict 후보의 slang context 과장 차단

- [x] v329 `11718099`에서 `빌환 -> 빌어먹을 환생` 같은 안정 alias는 유지하면서, OCR 충돌 후보 `붉여먹을 혼성명`은 `slang_insight.cultural_context`에서 본문/별칭/공식 제목 근거로 승격하지 않도록 했다.
- [x] 이 처리는 특정 OCR 문자열을 alias 차단 목록에 넣는 방식이 아니라 final title과 image evidence candidate mismatch를 기준으로 evidence role을 낮춘다.
- [ ] expanded review에서 `vlm_ocr_title_conflict_with_final_title`가 있는 packet 중 OCR 후보가 `slang_db` confirmed/pending alias로 저장된 케이스를 별도 감사한다.
- [ ] `slang_insight.cultural_context`가 OCR 후보를 작품 설정/2차창작 단서처럼 과장하는 케이스는 `ocr_conflict_context_overstated`로 분류한다.

## 2026-05-30 exact-title BatchMem alias 차단

- [x] v290 `11718117`에서 운영 `slang_db` 저장은 막혔지만 BatchMem 내부에서 `아카데미의 피해자 -> 아카데미의 피해자` exact-title alias가 즉시등록될 수 있음을 확인했다.
- [x] `BatchContextMemory.register_abbreviation()`가 normalized alias와 normalized title이 같으면 resolved/pending 등록을 건너뛰게 했다.
- [x] `abbreviation_exact_title_skipped` 통계를 추가했다.
- [x] `tests.test_batch_context`에 exact-title surface가 BatchMem alias로 남지 않는 회귀 테스트를 추가했다.
- [x] v292 live run에서 exact-title surface가 BatchMem 즉시등록 로그로 남지 않는지 확인했다.
- [x] v292 live run에서 `store_reason=exact_title_not_alias`, flush `titles=0`을 확인했다.
- [ ] `exact_title_not_alias` 차단과 clean short alias 보존 사이의 recall 영향은 expanded review에서 별도 확인한다.

## 2026-05-30 `11718082` OCR 오타 subtype 리뷰

- [x] v259 VLM/OCR-on result에서 OCR 표면 `제벨가 차녀의 2회차 결그룹`이 `store_in_slang_db=false`, `store_reason=character_attached_composite`로 차단됨을 확인했다.
- [x] 현재 운영 `slang_db/slang_db.json`에서 `제벨가`, `결그룹`, `재차걸`, `재벌가 차녀의 2회차 걸그룹`이 저장되지 않았음을 확인했다.
- [x] v259 BatchMem의 `재차걸 -> 재벌가 차녀의 2회차 걸그룹`은 검색 snippet의 `약칭은 재차걸` 근거가 있어 OCR 오타 저장 오염과 분리했다.
- [ ] expanded review에서 `ocr_typo_surface_blocked`, `character_attached_composite`, `clean_alias_from_search_snippet` subtype을 분리 집계한다.

## 2026-05-30 author/new-work alias 오염 차단

- [x] v242 `11718089`에서 `개돌 신작 ...` author/new-work 문맥이 `개돌 -> 파벨 주니어` confirmed slang처럼 저장된 오염을 확인했다.
- [x] v243에서 `[별명/작가] 신작`, `[별명] 대체 뭘 쓰...` 표면은 단일 작품 alias 저장/재승격 근거가 아니라고 분리했다.
- [x] 오염된 `batch_memory` hit도 author/new-work 표면이면 final title rescue하지 않도록 회귀 테스트를 추가했다.
- [x] 운영 `slang_db/slang_db.json`에서 v242 run `20260530_034933_089876`이 만든 `파벨 주니어 / 개돌` entry와 example을 제거했다.
- [x] 제거 후 `개돌`, `파벨 주니어` 문자열이 현재 slang DB에서 검색되지 않음을 확인했다.
- [ ] `slang_db_author_alias_pollution`, `author_new_work_alias_rescue_blocked` bucket을 large-scale qualitative expansion에 포함한다.
- [ ] author/new-work 표면이 clean title alias와 충돌하는 false negative가 없는지 random/high-risk sample에서 확인한다.

## 2026-05-29 memory-query pending 오염 차단

- [x] `11718083`처럼 본문이 "예전에 본 대사가 어느 소설인지 기억나지 않는다"는 기억 회수/탐색 글일 때, 단일 작품명을 확정하지 않는 것이 맞음을 확인했다.
- [x] `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`, `work_resolution=none`, `recommendation_request/recommendation` 조합에서는 reference 계열 후보를 slang DB `pending`으로 저장하지 않도록 했다.
- [x] 기존 polluted confirmed alias도 batch memory seed로 주입되지 않도록 seed 안전성 필터를 추가했다.
- [x] DB flush/finalize cleanup에서 matching example이 모두 polluted 신호인 confirmed/pending entry를 제거하도록 했다.
- [x] `secondary_reference`, `mentioned_work`, `recommendation_candidate`, `comparison_target` 저장 차단을 `tests.test_slang_db` 회귀 테스트로 고정했다.
- [x] v153 slang DB의 `네이버/네가` entry가 seed unsafe로 판정되는 것을 확인했다.
- [x] v153 slang DB 사본 cleanup에서 `네이버/네가`, `너에겐` 계열 entry가 제거되는 것을 확인했다.
- [x] 기존 `adjacent_meta`와 `trope_discussion` pending 수집은 유지했다.
- [ ] 운영 DB에 cleanup을 실제 적용할 때는 원본 백업 후 finalize/cleanup 결과를 검토한다.

## 2026-05-27 v108 반영

- [x] v105 `REJECT/re_judge` 7건 중 정상 웹소설 short alias false negative를 우선 보강했다.
- [x] `아집숨`, `탑매`, `괴무직`, `괴담텔`, `전1시`, `괴출`, `성녀속마음`을 known title abbreviation recall 대상으로 고정했다.
- [x] clean alias가 noise/author_talk/platform talk로 사라지지 않도록 prompt/router 예시를 추가했다.
- [x] v108 p7 targeted input과 manifest를 생성했다.
- [x] v108 실서버 p7 재실행과 v109 after-review를 완료해 `REJECT=0`, `HOLD=3`을 확인했다.
- [ ] `탑매`, `괴담텔`, `괴출` HOLD 3건은 slang/search/evidence 상태를 추가로 확인한다.
- [ ] HOLD 3건과 기존 slang DB review queue가 닫히기 전까지 slang DB 관련 row를 품질 승인 완료로 보지 않는다.

## 2026-05-27 v102 반영

- [x] noisy/composite surface 저장 차단과 clean short alias 보존을 분리하는 계약을 보강했다.
- [x] `탑매/탑 매니지먼트`는 phrase 자체를 저장하지 않되 `탑매`를 `canonical_work_alias` 후보로 보존하도록 테스트했다.
- [x] `탑매`처럼 clean initial alias가 `exact_title_not_alias`로 과차단된 경우 `pure_work_alias`로 복구하도록 테스트했다.
- [x] `환암검천 후기`처럼 문장형 surface에 clean alias가 포함된 경우 phrase 저장을 막고 `환암검천`을 보존하도록 테스트했다.
- [x] prompt/router와 verifier prompt에 정식 제목/짧은 약칭 분리 규칙을 추가했다.
- [x] v101 overblock 대표 row `25`건을 v102 targeted input으로 생성했고 `missing_count=0`을 확인했다.
- [x] LLM endpoint 확인 후 v98 7건과 v102 25건을 실서버로 재실행했다.
- [x] 이번 재실행은 `--parallel 36`으로 수행됐지만, 이후 소규모 targeted run은 `--parallel=min(input_count, 36)`으로 실행한다.
- [x] `expert_main.py` 런타임에서 `--parallel`을 상한으로 해석해 입력 post 수보다 많은 워커 생성을 막았다.
- [ ] 실서버 result packet에서 `canonical_work_alias` 보존과 `store_in_slang_db` 차단/저장 상태가 의도대로 나뉘는지 확인한다.

## 2026-05-27 v101 반영

- [x] `blocked_by_result_contract=79` 중 25건을 store_reason/alias_scope/relevance 기준으로 spot review했다.
- [x] v101 라벨은 `ACCEPT=6`, `HOLD=5`, `REJECT=14`로 확인했다.
- [x] `sentence_like_alias_surface` 안에 문장형 term과 정상 약칭 후보가 섞이는 과차단 패턴을 확인했다.
- [x] `pure_work_alias`인데 저장 차단에 남은 row가 alias recall false negative로 이어질 수 있음을 확인했다.
- [x] `exact_title_not_alias`에서 정식명 차단과 short alias 추출 누락이 섞이는 패턴을 확인했다.
- [ ] noisy detected term과 clean alias가 한 packet에 같이 있을 때 clean alias를 별도 후보로 보존하는 계약을 prompt/router 또는 후처리에서 보강한다.
- [ ] `BLOCK_TOO_STRONG` row를 alias candidate pool 보존 또는 re-judge queue로 이동한다.
- [ ] `MISSING_SHORT_ALIAS_EXTRACTION` row는 short alias 추출 누락 회귀 테스트를 만든다.
- [x] v101은 spot review이므로 전체 `blocked_by_result_contract=79` 승인 근거로 쓰지 않는다고 문서화했다.

## 2026-05-27 v100 반영

- [x] v99 소량 상태 8건을 자연어로 수동 리뷰했다.
- [x] `프리렌`, `시달소`를 외부 매체 seed quarantine 후보로 분류했다.
- [x] `탐태창`, `회맹생`, `시천살`, `반로환동전`을 정상 웹소설 alias 후보로 분류했다.
- [x] `검머외`, `말하는검`은 재판정/충돌 검토 후보로 남겼다.
- [ ] source slang DB에서 `프리렌`, `시달소`의 saved/conflict 상태를 제거 또는 quarantine 처리할지 별도 반영안을 작성한다.
- [ ] `탐태창`, `시천살`은 pending/conflict 해소 기준을 확인한 뒤 승격 여부를 결정한다.
- [ ] `검머외`, `말하는검`은 final relevance/canonical title 충돌을 먼저 해결한다.

## 2026-05-27 v99 반영

- [x] 최신 current `slang_db_review=87`을 상태별로 재생성했다.
- [x] `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`로 분리했다.
- [x] `v99_current_slang_db_status_review_manifest.json`, `summary_ko.md`, `action_queue.md`, `labels.jsonl`, `packets.jsonl`을 생성했다.
- [x] `build_slang_db_status_review.py`의 packet id prefix 고정 문제를 수정했다.
- [x] 관련 테스트를 통과했다.
- [ ] `persisted_as_slang=3`: `프리렌`, `회맹생`, `반로환동전` 중 외부 매체/정상 웹소설 alias를 분리 확정한다.
- [ ] `persisted_conflict=3`: `시천살`, `말하는검`, `시달소` conflict를 확정/보류/차단으로 정리한다.
- [ ] `persisted_pending=2`: `탐태창`, `검머외`를 승격/보류/차단 중 하나로 정한다.
- [x] `blocked_by_result_contract=79`: v101에서 차단 사유와 recall 영향만 표본 리뷰했다.

## 2026-05-27 v98 반영

- [x] v97 seed quarantine 확인용 targeted input `7`건을 준비했다.
- [x] known-bad 외부 매체 seed negative control `3`건을 포함했다: `강연금`, `프리렌`, `시달소`.
- [x] 정상 웹소설 약칭 positive control `4`건을 포함했다: `아집숨`, `탐태창`, `회맹생`, `반로환동전`.
- [x] v98 manifest/input/summary의 깨진 한국어 메타데이터를 정리했다.
- [x] 현재 `127.0.0.1:8000` LLM endpoint 연결 실패와 관련 Python 점유 없음 상태를 확인했다.
- [x] v98 `7`건을 실서버로 재실행했다.
- [ ] v98 after-review에서 negative control seed와 positive alias recall 결과를 판정한다.
- [ ] negative control seed가 batch memory resolved alias로 되살아나지 않는지 확인한다.
- [ ] positive control alias recall이 같이 죽지 않는지 확인한다.

## 2026-05-27 v97 반영

- [x] `post_id=9687991`의 `프리렌 -> 장송의 프리렌`이 `server_poc:saved_slang`으로 남아 있음을 확인했다.
- [x] `post_id=11097307`의 `시달소 -> 시간을 달리는 소녀`가 conflict seed로 남아 있음을 확인했다.
- [x] 두 seed를 `BatchContextMemory.NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST`에 추가해 batch memory resolved alias 승격을 차단했다.
- [x] structured slang support가 있어도 `프리렌`, `시달소 -> 시간을 달리는 소녀`가 pending/resolved memory로 들어가지 않는 회귀 테스트를 추가했다.
- [x] 웹소설 positive alias control (`죽깨수`, `검머대`, `히집악`)은 유지되는 것을 확인했다.
- [x] LLM endpoint 확인 후 targeted rerun으로 실제 결과 산출물을 생성했다.
- [ ] 다음 36건 미만 targeted rerun은 `--parallel=input_count`로 실행한다.
- [ ] `persisted_conflict=3`, `persisted_as_slang=3`, `persisted_pending=2`를 상태별 자연어 리뷰로 계속 닫는다.

## 2026-05-27 v86 정정

- [x] `post_id=10173521`의 `말하는검`이 저장 누락이 아니라 `server_poc:conflict` 상태임을 확인했다.
- [x] `titles[].conflicts[]`를 `persisted_conflict`로 분류하도록 보정했다.
- [x] `extracted_not_persisted=0`, `persisted_conflict=3`으로 정정했다.
- [x] conflict row `8650236`, `10173521`, `11097307`을 확인했다.
- [ ] `persisted_conflict=3`은 충돌 후보 title 중 어느 쪽으로 확정/보류할지 리뷰한다.
- [ ] dashboard/API에서 `conflicts` bucket도 saved/pending/family와 함께 표시되는지 확인한다.

## 2026-05-27 v85 반영

- [x] v86에서 `extracted_not_persisted=1`이 `persisted_conflict`로 정정됐다.
- [x] `slang_db_review=87`을 상태별 packet/label/action queue로 분리했다.
- [x] `blocked_by_result_contract=79`는 차단 사유와 recall 영향 확인 큐로 분리했다.
- [x] `persisted_as_slang=3`은 저장 alias 오염/중복 확인 큐로 분리했다.
- [x] `persisted_pending=2`는 pending 승격/보류/차단 확인 큐로 분리했다.
- [x] `family_alias=2`는 표시/검색 recall 확인 큐로 분리했다.
- [x] `extracted_not_persisted=1`은 저장 누락/차단 누락 조사 큐로 분리했다.
- [ ] `post_id=10173521`의 `extracted_not_persisted` 원인을 우선 확인한다.
- [x] `blocked_by_result_contract=79` 중 `pure_work_alias`인데 저장 차단된 케이스를 v101에서 별도 spot review했다.

## 2026-05-27 v84 정정

- [x] v83의 `docs_issue=64`가 source field 결손이 아니라 closure source fallback 누락임을 확인했다.
- [x] review packet의 빈 `slang_db_fields` dict가 원본 `identity.slang_insight` fallback을 막던 문제를 고쳤다.
- [x] latest current remaining 기준 `docs_issue=0`, `slang_db_review=87`로 정정했다.
- [x] `slang_db_review=87` 상태를 `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_pending=2`, `family_alias=2`, `extracted_not_persisted=1`로 재분류했다.
- [x] `blocked_by_result_contract=79`는 v101에서 차단 사유와 alias recall 영향만 별도 리뷰했다.
- [ ] `extracted_not_persisted=1`은 저장 누락인지 차단 누락인지 우선 확인한다.
- [ ] dashboard/API에서도 source fallback과 review packet 필드 결손을 구분해 표시한다.

## 2026-05-27 v83 반영

- [x] v84에서 source fallback 누락으로 정정되어 `docs_issue=64` 최종 해석은 폐기했다.
- [x] 10만건 current remaining에서 `slang_db_review=87`을 상태별로 재분류했다.
- [x] 공개 `slang_db_fields`가 없는 `64`건은 DB 오염 검토가 아니라 packet/export 결손이므로 `INFO_MISSING/docs_issue`로 라우팅했다.
- [x] 실제 `blocked_by_result_contract` 검토 대상은 `23`건으로 좁혔다.
- [x] 잔여 action packet에 `slang_db_fields`, `final_decision_fields`, `reason`, `search_health_flags`를 포함했다.
- [ ] `docs_issue=64`의 원인을 packet export 누락, label routing 누락, source result 결손으로 다시 나눈다.
- [ ] `blocked_by_result_contract=23`은 차단 사유와 alias recall 영향만 별도 리뷰한다.
- [ ] slang DB dashboard/API에서도 `blocked`, `pending`, `family`, `noise`, `field_missing` 상태가 섞이지 않게 표시한다.

정식 소설명 기준 은어 추출 품질을 유지하면서, `slang_db`가 대시보드와 운영 관점에서 더 읽기 쉽게 보이도록 정리하는 작업 메모다.

개발 TODO와 품질 게이트는 `docs/devs/FEATURE_IMPROVEMENT_TODO.md`, `docs/devs/OPERATION_QUALITY_CHECKLIST.md`에서도 함께 추적한다.

## 이번 반영

- [x] `slang_db` 기본 저장을 포스트 단위 즉시 flush로 변경
- [x] flush 로그에 `term -> title -> bucket` preview 추가
- [x] `family_aliases` 자동 승격 시 원본 source role 집계를 유지하도록 수정
- [x] 강한 단일 confirmed alias가 추정/보류 title 때문에 `family_alias/conflict`로 희석되지 않도록 보정
- [x] 20k 런 기준 slang audit 수행 (`20260423_170321_250907`)
- [x] 감사 스크립트가 대형 로그를 streaming으로 읽도록 보강
- [x] scan result review guide에 `slang_db` 후보 처리 상태 세분화 기준 추가

## 다음 우선순위

- [ ] 대시보드 API/화면에서 `titles[].slang/pending` 뿐 아니라 `examples.bucket`, `family_aliases`를 함께 보여주기
- [ ] `pending`를 단일 버킷으로 두지 말고 `pending_alias`, `secondary_reference`, `comparison_only` 같은 하위 성격으로 분리할지 검토
- [ ] 작품명이 아닌 일반 라벨성 title이 `pending`에 남는 패턴을 더 강하게 차단할지 검토
- [ ] `family_aliases` 승격 조건을 실데이터 기준으로 재조정
- [ ] `slang_db` 품질 검사용 샘플 리포트 스크립트 또는 audit 명령 추가
- [ ] `unclear_canonical_alias`로 차단된 실제 약칭 후보를 review queue로 분리
- [ ] 검색 안정화 후 slang 회수율이 올라가는지 같은 샘플로 재감사
- [ ] `extracted_not_persisted`와 `persisted_but_not_displayed`를 audit/dashboard에서 구분할 수 있는 지표 검토

## 관찰 메모

- 현재 DB는 `정식 작품 은어 사전`과 `보류/주변 참조 관측`이 섞인 구조다.
- 그래서 웹 대시보드가 `titles[].slang/pending`만 보면 실제보다 적게 보일 수 있다.
- `family_aliases`는 모호한 약칭을 숨기는 효과가 있어서, 조회 레이어가 이를 같이 보여주지 않으면 “저장이 안 된 것처럼” 보인다.
- 2026-04-26 감사 기준 `slang_insight=1817`, 저장 후보는 보정 전 `546`에서 보정 후 `532`로 줄었다.
- 현재 `slang_db/slang_db.json`은 `titles=340`, `family_aliases=1`, 문장형/작품명 동일 alias 오염 `0`으로 확인됐다.
- 차단된 14건은 모두 `unclear_canonical_alias`이며, 일부는 실제 약칭으로 보이는 표본이라 검색 안정화 후 재검토가 필요하다.
