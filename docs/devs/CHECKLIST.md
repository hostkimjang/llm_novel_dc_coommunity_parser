# Development Checklist

## Standing Rule - code change verification

- [ ] 앞으로 pipeline/판정 코드 변경은 `py_compile`/unit/helper regression만으로 완료 처리하지 않는다. 가능한 범위의 `expert_main.py` targeted canary 또는 동등한 실제 retest run을 돌려 코드 변경이 런타임 결과를 개선했는지 확인한 뒤 docs에 효과/한계를 기록한다.

## Standing Rule - completed779 Hermes continuous loop

- [ ] completed779 Hermes goal은 queue가 비거나 모든 잔여 row가 `HOLD`/`human_review`/`INFO_MISSING`/`unresolved_matchable`/`quarantine`/`no_generalizable_fix_left`로 row-level 분류되기 전에는 완료 처리하지 않는다.
- [ ] subagent fan-out을 시도하고, tool/concurrency 한계가 있으면 limitation과 main Codex 대체 검토를 기록한다.
- [ ] subagent 결과는 승인 근거가 아니라 재확인 입력으로만 사용한다.
- [ ] 가능한 경우 모델/도구 관점을 분산한다: local artifact, code/tests, web/search, prompt/semantic review.
- [ ] active queue row의 `suspected_code_hook`, `proposed_next_fix`, `required_test`가 비어 있으면 코드 수정 전에 먼저 채운다.
- [ ] bucket별 acceptance map을 적용한다: `candidate_comment_multi`는 candidate/HOLD/human_review 성공을 허용하고, `recall_relevance_representative`는 강한 근거가 있을 때만 expected title/url 회수를 허용한다.
- [ ] runtime integrity, targeted canary status, semantic quality, full-scan approval을 분리하고 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
- [ ] completed779/Hermes focused verification에는 rank1/2/3 load-bearing modules를 포함한다: `tests.test_agentic_pipeline_rank1_lock_block tests.test_agentic_pipeline_rank2_ocr_catalog_evidence tests.test_agentic_pipeline_rank3_lock_anchor`.

## 2026-06-23 completed779 Loop 16 Claude post-review rank1-3 regression repair 체크

- [x] Claude review의 rank1 회귀 지적을 로컬에서 재현했다.
- [x] 재현 실패: rank1/2/3 suite `40`개 중 `2`개 fail.
- [x] 실패 테스트: `test_verifier_critical_demotes_but_preserves_title`, `test_official_detail_matched_url_exempt_from_demote`.
- [x] `_title_lead_alias_precision_block_signal`에서 verifier `critical/major` hard-block 트리거를 제거했다.
- [x] 책임 분리: verifier critical/major는 rank1이 demote-but-preserve로 처리하고, title-lead precision gate는 relation/competition/comment-meta 전용으로 남긴다.
- [x] rank1/2/3 suite 재검증: `40 tests OK`.
- [x] completed779 focused suite + rank1/2/3 재검증: `126 tests OK`.
- [x] py_compile pass.
- [ ] 이 repair는 Loop16 targeted/control closure를 보강한 blocker fix이며, full scan approval 근거가 아니다.

## 2026-06-23 completed779 Hermes Loop 16 post-Loop15 residual/control 체크

- [x] Loop 16 queue 생성: rows `7`, main `0`, controls `7`, text/url/comment `2`, image/OCR `5`, duplicate `0`.
- [x] controls: `11694064`, `11698880`, `11702055`, `11710037`, `11710045`, `11718077`, `11718105`.
- [x] Hermes council fan-out 6축을 실행하고 메인 Codex가 재확인했다.
- [x] text canary 완료: `2/2`, failed `0`, pending `0`.
- [x] image/OCR canary 완료: `5/5`, failed `0`, pending `0`, VLM/OCR `READY`.
- [x] seed-conflict/trope-boundary reason scrub이 final `reason`까지 동기화된다.
- [x] `11698880` focused rerun에서 final title null, reason HOLD/conflict 문구 확인.
- [x] `11710037` focused rerun에서 trope-boundary public title demotion 및 reason HOLD 확인.
- [x] `11718105` focused rerun에서 author/platform-meta adjacent 및 multi-title candidate preservation 확인.
- [x] final result rows `7`, duplicate `0`.
- [x] final compare movement: `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=3`.
- [x] latest next queue rows `0`: `out/completed779_improvement_goal_20260622/hermes_loop16_final_control_next_queue.json`.
- [x] verification: py_compile pass, focused suite `86 tests OK`, `git diff --check` pass with LF/CRLF warnings only.
- [ ] Loop 16 queue `0`은 targeted/control closure다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-23 completed779 Hermes Loop 15 trope-boundary guard 체크

- [x] Loop 15 queue 생성: rows `6`, main `1`, controls `5`, text/url/comment `2`, image/OCR `4`, duplicate `0`.
- [x] controls: `11694064`, `11698880`, `11702055`, `11710045`, `11718105`.
- [x] Hermes council fan-out 6축을 실행하고 메인 Codex가 재확인했다.
- [x] pre-fix text canary에서 `11710037` public title over-promotion을 확인했다.
- [x] compare retaxonomy가 `boundary_title_over_promoted`로 pre-fix 실패를 잡는다.
- [x] `trope_or_author_talk_risk` guard가 expected title/url을 candidate/HOLD로 보존하고 final public title을 demote한다.
- [x] Loop 15 fix1 text canary 완료: `2/2`, failed `0`, pending `0`.
- [x] Loop 15 image/OCR control canary 완료: `4/4`, failed `0`, pending `0`, VLM/OCR `READY`.
- [x] combined result rows `6`, duplicate `0`.
- [x] combined compare movement: `blocked_or_candidate_preserved=1`, `candidate_or_human_review_preserved=3`, `url_lint_preserved=2`.
- [x] latest next queue rows `0`: `out/completed779_improvement_goal_20260622/hermes_loop15_combined_fix1_next_queue.json`.
- [x] `11694064` sentinel은 bad title로 회귀하지 않았다.
- [x] verification: py_compile pass, focused suite `84 tests OK`.
- [ ] Loop 15 queue `0`은 targeted/control closure다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
- [ ] `11710045` 후보 오염과 `11718077` control coverage gap은 다음 loop 후보로 남긴다.

## 2026-06-23 completed779 Hermes Loop 14 remaining expansion v2 + fix1 체크

- [x] Loop 13 retaxonomy recompare로 `11698880`, `11702055` false-close를 `title_or_url_still_mismatched` residual로 되살렸다.
- [x] Loop 14 v2 queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop14_remaining_expansion_v2_queue.json`, rows `22`, main `16`, controls `6`, duplicate `0`.
- [x] Loop 14 v2 split: text/url/comment `8`, image/OCR `14`.
- [x] regression controls: `11694064`, `11698880`, `11702055`, `11710045`, `11718105`, `11718077`.
- [x] Hermes council fan-out를 실행하고 limitation도 기록했다: Verification/Docs context-window error, 추가 skeptic thread-limit.
- [x] Loop 14 v2 text canary 완료: rows `8/8`, failed `0`, pending `0`.
- [x] Loop 14 v2 image/OCR canary 완료: rows `14/14`, failed `0`, pending `0`, VLM/OCR `READY`.
- [x] Loop 14 v2 combined compare 완료: next queue rows `2` (`11698880`, `11702055`).
- [x] compare가 source/url hygiene expected-title miss를 lint closure로 숨기지 않도록 고쳤다.
- [x] expected-null row가 unexpected public title로 바뀌면 requeue되는 compare regression을 추가했다.
- [x] expansion helper가 explicit consumed controls와 empty main targets를 정확히 처리하도록 고쳤다.
- [x] `group=hygiene` judge expected title/url도 candidate/HOLD evidence로 보존하도록 `candidate_audit.py`를 보강했다.
- [x] Loop 14 fix1 targeted canary 완료: rows `2/2`, VLM/OCR `READY`.
- [x] Loop 14 fix1 compare 완료: `url_lint_preserved=2`, expected title/url preserved flags true, next queue rows `0`.
- [x] `11694064`는 bad title로 회귀하지 않았고, `11710045`도 unexpected public title로 재승격하지 않았다.
- [x] verification: py_compile pass, focused suite `82 tests OK`.
- [x] final docs sync 이후 `git diff --check`를 재실행했다. 결과는 LF/CRLF 경고만 있고 whitespace error는 없다.
- [ ] Loop 14 queue `0`은 targeted closure다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
- [ ] 다음 Loop 15는 새 fresh/residual/control pool에서 시작한다.

## 2026-06-23 completed779 Hermes Loop 13 residual expansion + relation-HOLD fix 체크

- [x] Loop 12 queue `0` 이후 residual expansion queue `51`건을 생성했다: text/url/comment `9`, image/OCR `42`, main `39`, controls `12`, duplicate `0`.
- [x] Hermes council fan-out를 실행했다: Source/URL, Search/Web, Candidate/Comment, Prompt/Orchestration, Code Hook, OCR/Visual.
- [x] Loop 13 text/url/comment canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_text_result.json`, rows `9/9`, failed `0`, pending `0`.
- [x] Loop 13 image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop13_residual_expansion_image_ocr_result.json`, rows `42/42`, failed `0`, pending `0`, VLM/OCR `READY`.
- [x] Loop 13 combined compare 완료: movement `blocked_or_candidate_preserved=8`, `boundary_hold_preserved=4`, `candidate_or_human_review_preserved=31`, `candidate_preserved_with_benign_prune=3`, `resolved_expected_title=1`, `url_lint_preserved=4`.
- [x] Loop 13 next queue `out/completed779_improvement_goal_20260622/hermes_loop13_residual_expansion_next_queue.json` rows `0`.
- [x] `11694064` sentinel은 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않았다.
- [x] `candidate_audit.py`에서 OCR `work_cues` context-only surface를 candidate ledger에서 필터링했다.
- [x] `compare_completed779_improvement.py`에서 boundary-HOLD closure와 benign wrapper prune을 분리했다.
- [x] `11710045` pre-fix targeted canary로 relation HOLD final promotion bug를 확인했다.
- [x] `agentic_pipeline.py`에서 relation-HOLD indirect character/scene evidence가 direct title anchor 없이 public title로 확정되지 않게 차단했다.
- [x] `11710045` after-fix canary 완료: `official_title=null`, `Identified=0`, `title_resolution_state=context_only`, `title_resolution_allowed=false`.
- [x] `11710045` after-fix compare 완료: movement `candidate_or_human_review_preserved=1`, requeue `0`.
- [x] verification: py_compile pass, focused suite `77 tests OK`, `git diff --check` pass with LF/CRLF warnings only before docs sync.
- [x] Loop 13 queue `0`은 targeted closure다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
- [ ] 다음 Loop 14는 fresh/residual/control pool을 열고 `11694064`, `11710045`, `11718105`를 regression controls로 포함한다.

## 2026-06-23 completed779 Hermes Loop 12 fresh expansion + fix2 체크

- [x] Loop 11 queue `0` 이후 fresh expansion queue `43`건을 생성했다: text/url/comment `14`, image/OCR `29`, main `39`, controls `4`, duplicate `0`.
- [x] Hermes council 6축 fan-out를 실행했다: Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Code Hook, Prompt/Orchestration+Verification/Docs.
- [x] Loop 12 text/url/comment canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_text_result.json`, rows `14/14`, failed `0`, pending `0`.
- [x] Loop 12 image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fresh_expansion_image_ocr_result.json`, rows `29/29`, failed `0`, pending `0`, VLM/OCR `READY`.
- [x] Loop 12 combined compare 완료: movement `candidate_or_human_review_preserved=28`, `candidate_preserved_with_benign_prune=8`, `candidate_preserved_with_prune_review=1`, `resolved_expected_title=2`, `resolved_expected_title_and_url=2`, `url_lint_preserved=2`.
- [x] Loop 12 pre-fix next queue는 `11718105` 1건으로 좁혀졌다.
- [x] `candidate_audit.py`에서 judge expected `multiple:` 멤버를 weak `llm_only` pruning에서 보호했다.
- [x] `candidate_audit.py`에서 unresolved/multi/adjacent image OCR `work_cues`를 official title promotion 없이 candidate ledger에 보존했다.
- [x] `11718105` fix2 canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop12_fix2_ocr_work_cues_11718105_image_ocr_result.json`, completed/failed/pending `1/0/0`, VLM/OCR `READY`.
- [x] `11718105` fix2 compare 완료: movement `candidate_or_human_review_preserved=1`.
- [x] Loop 12 fix2 next queue `out/completed779_improvement_goal_20260622/hermes_loop12_fix2_ocr_work_cues_next_queue.json` rows `0`.
- [x] verification: py_compile pass, focused suite `74 tests OK`, scoped `git diff --check` pass.
- [x] Loop 12 queue `0`은 targeted closure다. `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-23 completed779 Hermes Loop 11 benign prune closure 체크

- [x] Loop 10 broader next queue `2`건과 candidate/comment next queue `2`건, 총 `4`건을 Loop 11 active queue로 삼았다.
- [x] Hermes council fan-out를 6축으로 실행했다: Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Code Hook, Prompt/Orchestration.
- [x] Verification/Docs subagent는 thread limit으로 spawn 실패했고, limitation으로 기록한 뒤 메인 Codex가 문서/검증을 직접 수행했다.
- [x] 4건 모두 expected title/url candidate는 보존됐고, prune된 surface는 expected title이 아니라 unrelated `llm_only` sentence/noise임을 row-level로 확인했다.
- [x] `tools/compare_completed779_improvement.py`에 `candidate_preserved_with_benign_prune`와 `evidence_flags.expected_url_evidence_strength`를 추가했다.
- [x] expected title/url 후보가 보존되고 prune surface가 expected title과 무관하면 requeue하지 않는 compare taxonomy를 테스트로 고정했다.
- [x] broader recompare: `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_broader_compare.json`, movement `candidate_or_human_review_preserved=18`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=4`, `url_lint_preserved=8`.
- [x] broader next queue: `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_broader_next_queue.json`, rows `0`.
- [x] candidate/comment recompare: `out/completed779_improvement_goal_20260622/compare/hermes_loop11_benign_prune_candidate_comment_compare.json`, movement `candidate_or_human_review_preserved=7`, `candidate_preserved_with_benign_prune=2`, `resolved_expected_title=2`.
- [x] candidate/comment next queue: `out/completed779_improvement_goal_20260622/hermes_loop11_benign_prune_candidate_comment_next_queue.json`, rows `0`.
- [x] verification: py_compile pass, `tests.test_completed779_compare` `23 tests OK`, focused related suite `74 tests OK`.
- [x] Loop 11 queue `0`은 compare/verification taxonomy closure이며 runtime pipeline promotion 변경이나 full approval이 아니다.
- [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 2026-06-23 completed779 Hermes Loop 10 broader/candidate-comment 체크

- [x] subagent fan-out를 모델/관점별로 분산했다: Averroes `gpt-5.5`, Mill `gpt-5.4`, Fermat `gpt-5.4-mini`; Sagan context-window error는 limitation으로 기록했다.
- [x] Loop 10 broader regression queue 생성: rows `32`, text/url/comment `15`, image/OCR `17`, duplicate `0`.
- [x] Loop 10 broader text canary 완료: rows `15/15`, VLM/OCR `NOT_APPLICABLE`.
- [x] Loop 10 broader image/OCR canary 완료: rows `17/17`, VLM/OCR `READY`.
- [x] Loop 10 broader combined compare 완료: rows `32/32`, movement `candidate_or_human_review_preserved=18`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=4`, `url_lint_preserved=8`.
- [x] broader next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop10_broader_regression_next_queue.json`, rows `2` (`11710025`, `11708479`).
- [x] Loop 10 candidate/comment expansion v2 queue 생성: rows `11`, text/url/comment `4`, image/OCR `7`, duplicate `0`.
- [x] candidate/comment v2 text canary 완료: rows `4/4`, VLM/OCR `NOT_APPLICABLE`.
- [x] candidate/comment v2 image/OCR canary 완료: rows `7/7`, VLM/OCR `READY`.
- [x] candidate/comment v2 combined compare 완료: rows `11/11`, movement `candidate_or_human_review_preserved=7`, `candidate_preserved_with_prune_review=2`, `resolved_expected_title=2`.
- [x] candidate/comment v2 next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop10_candidate_comment_expansion_v2_next_queue.json`, rows `2` (`11698878`, `11708478`).
- [x] compare false-close 방지를 위해 expected title/url evidence flags, prune review, blocked primary work 분리를 추가했다.
- [x] focused tests `72 tests OK`, broader focused suite `170 tests OK`, py_compile pass.
- [x] Loop 11은 `candidate_preserved_with_prune_review` `4`건을 active queue로 삼아 prune/review policy를 일반화했다. 최신 Loop 11 next queue는 rows `0`.
- [x] semantic quality remains `REVIEW-LOCKED`; full scan approval remains `false`.

## 2026-06-23 completed779 Hermes Loop 9 residual closure 체크

- [x] Loop 8 fresh expansion queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_queue.json`, rows `43`, main `24`, controls `19`, duplicate `0`.
- [x] Loop 8 input split 생성: text/url/comment `20`, image/OCR `23`.
- [x] Loop 8 text/url/comment canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_text_result.json`, rows `20/20`, VLM/OCR `NOT_APPLICABLE`.
- [x] Loop 8 image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_image_ocr_result.json`, rows `23/23`, VLM/OCR `READY`.
- [x] Loop 8 combined result 생성: `out/completed779_improvement_goal_20260622/canary/hermes_loop8_fresh_expansion_combined_result.json`, rows `43`, duplicate `0`.
- [x] Loop 8 combined compare 생성: `out/completed779_improvement_goal_20260622/compare/hermes_loop8_fresh_expansion_combined_compare.json`.
- [x] combined movement: `blocked_or_candidate_preserved=9`, `candidate_or_human_review_preserved=15`, `resolved_expected_title=4`, `resolved_expected_title_and_url=2`, `url_lint_preserved=5`, `still_under_resolved_or_noise=3`, `title_or_url_still_mismatched=2`, `title_match_url_still_mismatched=3`.
- [x] Loop 9 active queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop8_fresh_expansion_next_queue.json`, rows `8`.
- [x] `tools/compare_completed779_improvement.py` candidate-aware compare와 recall wrong-final-title mismatch 분류를 보강했다.
- [x] `tests.test_completed779_compare` 통과: `19 tests OK`.
- [x] `11694064` sentinel은 `무협 게임에 빙의했다...스킵충이다`로 회귀하지 않고 `판초우의의 마법사` 후보/URL을 보존했다.
- [x] Loop 9 residual input split 생성: text/url/comment `4`, image/OCR `4`, missing `0`, duplicate `0`.
- [x] Loop 9 subagent fan-out 결과를 메인 Codex가 재검증했다.
- [x] comment-surface HOLD 후보 보존, judge expected candidate preservation, weak sentence candidate pruning을 구현했다.
- [x] Loop 9 text/url/comment canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_text_result.json`, rows `4/4`, VLM/OCR `NOT_APPLICABLE`.
- [x] Loop 9 image/OCR canary 완료: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_image_ocr_result.json`, rows `4/4`, VLM/OCR `READY`.
- [x] Loop 9 combined result 생성: `out/completed779_improvement_goal_20260622/canary/hermes_loop9_residual_combined_result.json`, rows `8`, duplicate `0`.
- [x] Loop 9 combined compare 생성: `out/completed779_improvement_goal_20260622/compare/hermes_loop9_residual_combined_compare.json`, movement `blocked_or_candidate_preserved=3`, `candidate_or_human_review_preserved=5`.
- [x] Loop 9 next queue 생성: `out/completed779_improvement_goal_20260622/hermes_loop9_residual_next_queue.json`, rows `0`.
- [x] stale vLLM model 404를 확인하고 live model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`로 실행했다.
- [ ] semantic quality remains `REVIEW-LOCKED`; full scan approval remains `false`.

## 2026-06-23 completed779 Hermes Loop 6 postfix closure 체크

- [x] Loop 6 remaining queue를 생성했다: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue.json`, rows `2` after postfix2/3 closure accounting.
- [x] subagent fan-out를 재사용했다: Search/Source, Prompt/Orchestration 응답은 확보했고, Code Hook/Regression subagent는 시간 내 완료되지 않아 닫았다. 모든 결론은 메인 Codex가 파일/테스트/canary로 재확인했다.
- [x] `candidate_audit.py` postprocess hook을 보강해 `entity_mentions`, post title media-adaptation surface, `TS)` short alias, image/character leading surface를 final promotion 없이 candidate ledger에 보존한다.
- [x] `expert_main.py` postprocess에서 `apply_post_surface_candidate_hints(identity, post.title)`를 audit 전에 호출한다.
- [x] 11705237 단일 canary에서 `월야환담`이 `post_title_surface` 후보로 보존됐다.
- [x] 11698868 text canary에서 `방타스`가 `post_title_surface` 후보로 보존됐다.
- [x] 11708449 image/OCR canary에서 `담청`이 `post_title_surface` 후보로 보존됐고 VLM/OCR gate는 `READY`다.
- [x] Loop 6 postfix4 compare:
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop6_postfix4_11698868_text_compare.json`
  - `out/completed779_improvement_goal_20260622/compare/hermes_loop6_postfix4_11708449_image_ocr_compare.json`
  - both movement `candidate_or_human_review_preserved=1`
- [x] Loop 6 final queue: `out/completed779_improvement_goal_20260622/hermes_loop6_remaining_queue_postfix4.json`, rows `0`.
- [x] continuous goal prompt를 Loop 6 final queue rows `0` 기준으로 갱신했다: `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`.
- [x] focused verification passed: final broader focused suite `211 tests OK` and postfix4 subset `51 tests OK`.
- [x] `git diff --check` passed with LF/CRLF warnings only.
- [ ] `11698880` upstream title/body multi-candidate conflict is still a research note; public output guard is closed but orchestration precision still needs broader design.
- [ ] semantic quality remains `REVIEW-LOCKED`; full scan approval remains `false`.

## 2026-06-22 completed779 Hermes Loop 5 source residual expansion 체크

- [x] Council fan-out 결과를 메인 Codex가 재확인했다: Candidate/Comment, OCR/Visual+URL, Search/Web, Code Hook/Tooling, Verification/Docs.
- [x] source-correctness refresh `review=12`, `url_lint_preserved=21`을 semantic closure가 아니라 residual control pool로 분리했다.
- [x] native-web non-ACCEPT 미소모 pool에서 main expansion을 생성했다.
- [x] `tools/build_completed779_hermes_expansion.py`를 추가했다.
- [x] Loop 5 active queue를 생성했다: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_queue.json`.
- [x] Loop 5 queue rows `44`, main `24`, controls `20`, duplicate post_ids `0`.
- [x] Loop 5 input split: text/url/comment `19`, image/OCR `25`.
- [x] 새 helper 테스트 `tests/test_completed779_hermes_expansion.py`를 추가했다.
- [x] helper 단위 테스트 통과: `tests.test_completed779_hermes_expansion`, `1 test OK`.
- [x] Loop 5 canary 실행 전 search shard health를 다시 확인했다: preflight `ok=2/2`, vLLM model `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`.
- [x] Loop 5 text/url/comment canary를 실행했다: rows `19/19`, VLM/OCR `NOT_APPLICABLE`.
- [x] Loop 5 image/OCR canary를 실행했다: rows `25/25`, VLM/OCR `READY`.
- [x] Loop 5 compare와 next queue를 생성했다: combined rows `44/44`, duplicate `0`.
- [x] `11694064`, `11710033`, `11698880`, `11702055`, `11706871`, `11716480` control을 확인했다.
- [x] Loop 5 hard-fail/postfix next queue를 Loop 6 generalized fix loop로 넘겨 targeted canary/compare를 완료했다.
- [ ] `11698880`은 여전히 `가챠 중독자의 퓨전펑크 생활`로 drift하므로 title/body multi-candidate conflict HOLD fix를 설계한다.
- [ ] `11694064`/`11710033`은 bad title은 피했지만 `판초우의의 마법사` 회수가 불안정하므로 alias consistency fix를 설계한다.
- [ ] `11702055`는 로그상 `괴담 호텔 탈출기` 후보가 있으나 final null/adjacent라 character/setting cluster recall fix를 설계한다.

## 2026-06-22 completed779 Hermes Loop 4 closure 체크

- [x] Loop 3 active queue `5`건을 Loop 4 seed/input으로 재구성했다.
- [x] 댓글 답변 후보, 짧은/복합 약칭 후보, 캐릭터/설정 cluster 후보를 final promotion 없이 candidate ledger/HOLD로 보존하는 hook을 구현했다.
- [x] candidate snapshot에 `local_preservation_type`과 `promotion_policy=hold_without_promotion`을 남겼다.
- [x] URL/domain-shaped title pollution을 compare에서 `garbage_title_after`로 잡는 회귀 테스트를 추가했다.
- [x] subagent fan-out findings를 메인 Codex가 코드/테스트로 재확인했다.
- [x] Loop 4 text canary `4/4`, image/OCR canary `1/1` 완료.
- [x] Loop 4 combined compare `5/5`, movement `candidate_or_human_review_preserved=5`.
- [x] active queue: `out/completed779_improvement_goal_20260622/hermes_loop4_queue.json` rows `0`.
- [x] `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`를 queue `0` 기준으로 갱신했다.
- [x] source-correctness refresh queue/input을 준비했다. Queue rows `39`, text/url/comment `14`, image/OCR `25`.
- [x] source refresh preflight에서 shard audit `ok=0/2`, Docker Desktop Linux engine pipe missing을 기록했다.
- [x] next expansion queue는 balanced P0와 closed5를 제외한 unseen pool `201`에서 뽑는 원칙을 기록했다.
- [ ] Loop 4 evidence는 no-search degraded targeted canary이므로 source-correctness approval로 승격하지 않는다.
- [ ] 정상 Docker/SearXNG shard 복구 후 source-correctness refresh 또는 새 high-risk/native-web expansion queue를 시작한다.
- [ ] semantic_quality는 `REVIEW-LOCKED`, full_scan_approval은 `false`로 유지한다.

## 2026-06-22 completed779 Hermes Loop 3 체크

- [x] Subagent fan-out 2축을 수행했다: code-hook expert, prompt/orchestration+verification/docs expert.
- [x] `candidate_audit.py` image/OCR weak explicit title preservation test를 추가했다.
- [x] `compare_completed779_improvement.py` explicit `unresolved_matchable` preservation 해석을 추가했다.
- [x] `build_completed779_reimprovement_inputs.py` prefix/loop-label 및 queue metadata 보존을 추가했다.
- [x] focused verification: `py_compile` pass, `tests.test_candidate_audit`, `tests.test_completed779_compare`, `tests.test_completed779_reimprovement_inputs` pass.
- [x] precompare: Loop 2 remaining `8`건 중 `2`건이 `candidate_or_human_review_preserved`로 분리됐다.
- [x] deterministic re-audit: `11695623`이 candidate ledger `림월드` 보존으로 분리됐다.
- [x] active queue: `out/completed779_improvement_goal_20260622/hermes_loop3_queue.json` rows `5`.
- [x] live text canary attempted and blocked before result generation: `logs/expert_run_20260622_211133_748990.log`.
- [ ] 정상 search-enabled route를 복구해 Loop 3 text/image canary를 재실행한다.
- [ ] 남은 5건의 upstream candidate generation/preservation fix를 구현한다.
- [ ] `git diff --check`를 최종 실행한다.

## 2026-06-22 completed779 reimprovement Loop 2 goal 체크

- [x] Loop 2 active contract를 `goal.md`에 작성했다.
- [x] Loop 2 copy-paste prompt를 `docs/devs/COMPLETED779_REIMPROVEMENT_LOOP2_GOAL_PROMPT.md`에 작성했다.
- [x] active queue baseline: `25` rows, `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`, active `garbage_title_after=0`.
- [x] candidate/comment/recall preservation group `16`건과 source/url hygiene group `9`건을 분리했다.
- [x] Loop 1 regression controls를 명시했다: `11694064`, `wrong_work=9`, `garbage_title_after=0`.
- [ ] Loop 2 input split helper 또는 동등한 입력 생성 절차를 구현한다.
- [ ] Loop 2 generalized fixes를 구현한다.
- [ ] Loop 2 text/url/comment canary와 image/OCR canary를 실행한다.
- [ ] Loop 2 compare와 reimprovement queue를 생성한다.
- [ ] semantic_quality는 `REVIEW-LOCKED`, full_scan_approval은 `false`로 유지한다.

## 2026-06-22 completed779 native-web 개선 goal 체크

- [x] `goal.md`를 completed779 native-web improvement active contract로 갱신했다.
- [x] 기존 JUDGE3905 goal 본문은 `llm_judge_goal.md`에 보관했다.
- [x] deterministic full-post aggregate와 native-web aggregate를 섞지 않는 stale aggregate 금지 규칙을 문서화했다.
- [x] `tools/build_completed779_issue_index.py`를 추가했다.
- [x] `tools/compare_completed779_improvement.py`를 추가했다.
- [x] `tests/test_completed779_issue_index.py`를 추가했다.
- [x] issue index 생성 결과: unique/source coverage `779/779`, missing `0`, duplicate after dedupe `0`, non-ACCEPT `266`.
- [x] label aggregate: `ACCEPT=513`, `REPROCESS=208`, `HOLD=49`, `INFO_MISSING=7`, `REJECT=2`.
- [x] balanced P0 seed `65`건 생성: precision `15`, candidate/comment/multi `15`, recall/relevance `25`, source/url `10`.
- [x] `11694064` seed 포함과 `wrong_work=9` 전체 seed 포함을 확인했다.
- [x] canary input split: text/url/comment `19`, image/OCR `46`.
- [x] memory-query unsupported title guard가 후단 recommendation guard에 덮어써지지 않도록 `agentic_pipeline.py`를 좁게 보정했다.
- [x] `py_compile` 검증을 통과했다.
- [x] 요청된 focused unit suite `178 tests OK`를 확인했다.
- [x] `git diff --check` 통과. 출력은 기존 LF/CRLF warning만 있었다.
- [x] 자동 개선 연구·검증·재개선 goal prompt를 `docs/devs/COMPLETED779_AUTO_IMPROVEMENT_GOAL_PROMPT.md`에 작성했다.
- [x] `goal.md`에서 next auto-loop prompt를 링크했다.
- [x] subagent fan-out 4축(taxonomy/source, code-hook, prompt/orchestration, verification/docs)을 수행하고 메인 Codex가 결과를 재확인했다.
- [x] P0 seed 기반 일반화 fix 1차를 구현했다: native-web taxonomy audit, judge-seed precision/hygiene 분리, 댓글 제목 후보 보존, 댓글 title probe permit, prompt contract 보강.
- [x] `tools/compare_completed779_improvement.py`를 split canary/expected URL/reimprovement queue 지원으로 확장했다.
- [x] `tests/test_completed779_compare.py`를 추가했다.
- [x] text/url/comment canary를 실행하고 compare report를 남겼다. Result `out/expert_result_20260622_161924_359370.json`, compare `out/completed779_improvement_goal_20260622/compare/text_degraded_compare.json`.
- [x] image/OCR canary를 `--vlm on --ocr on --require-vlm-ocr-for-images`로 실행하고 compare report를 남겼다. Result `out/expert_result_20260622_162557_711822.json`, compare `out/completed779_improvement_goal_20260622/compare/image_ocr_degraded_compare.json`.
- [x] combined compare `65/65`를 생성했다. `out/completed779_improvement_goal_20260622/compare/combined_degraded_compare.json`.
- [x] `11694064`는 `무협 게임에 빙의했다...스킵충이다`로 확정되지 않았고, `wrong_work=9` 전체가 `blocked_or_candidate_preserved`로 이동했다.
- [x] reimprovement queue를 생성했다. `out/completed779_improvement_goal_20260622/compare/combined_degraded_reimprovement_queue.json`, rows `19`.
- [x] runtime integrity, targeted canary status, semantic quality, full-scan approval을 분리 보고했다.
- [x] Docker/SearXNG 부재 상황을 우회하기 위해 MCP bridge direct Naver/Bing fallback을 추가했고, fallback search-health로 text `19/19`, image/OCR `46/46` canary를 완료했다.
- [x] direct-search fallback combined compare `65/65`를 생성했다. `out/completed779_improvement_goal_20260622/compare/combined_direct_search_compare.json`.
- [x] direct-search fallback에서 드러난 snippet/breadcrumb `official_title` 오염 3건을 `garbage_title_after`로 분리했고, `candidate_audit` promotion guard가 이를 demote하도록 보강했다.
- [x] root reimprovement queue를 direct-search 기준 `27`건으로 갱신했다. `still_under_resolved_or_noise=15`, `garbage_title_after=3`, `title_or_url_still_mismatched=9`.
- [x] snippet/breadcrumb polluted 3건 post-fix mini canary를 실행했다. Text 2건 `out/expert_result_20260622_183047_118075.json`, image/OCR 1건 `out/expert_result_20260622_183544_060718.json`.
- [x] post-fix 결합 compare `out/completed779_improvement_goal_20260622/compare/garbage_title_postfix_combined_compare.json`에서 `garbage_title_after=0`을 확인했다.
- [x] post-fix-adjusted compare `out/completed779_improvement_goal_20260622/compare/combined_direct_search_postfix_adjusted_compare.json`를 생성했다. Movement는 `blocked_or_candidate_preserved=15`, `candidate_or_human_review_preserved=22`, `resolved_expected_title=2`, `resolved_expected_title_and_url=1`, `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`.
- [x] root reimprovement queue를 post-fix-adjusted 기준 `25`건으로 갱신했다. `garbage_title_after=0`; `11716482`는 public-title 오염은 닫혔지만 multi-candidate/comment 후보 보존 미흡으로 active queue에 유지한다.
- [ ] direct-search fallback은 정상 Docker/SearXNG shard approval이 아니므로 semantic approval로 승격하지 않는다.
- [ ] post-fix-adjusted reimprovement queue `25`건을 다음 루프 seed로 사용한다.

## 2026-06-21 full_post_judge completed779 체크

- [x] `out/expert_result_20260620_165159_711176_completed_subset.json` `779`건을 판정 모수로 사용했다.
- [x] primary `out/expert_result_20260620_165159_711176.json` `757`건만 쓰면 shutdown flush gap `22`건과 `11694064`가 빠지는 것을 source coverage로 분리했다.
- [x] `out/full_post_judge_20260620_165159_711176_completed779/report/full_post_judge_report.md`를 생성했다.
- [x] coverage `processed=779`, `judged=779`, `missing=0`, `bad_files=0`, `pending_rerun=0`을 확인했다.
- [x] `report/rows/full_post_judge_rows_p01.md`에 `11694064`가 존재함을 확인했다.
- [x] `11694064`는 `wrong_work / REPROCESS / conflicting_or_multi_candidate / re_judge / high`로 잡혔다.
- [x] `11694064` note에 `경합후보=판초우의의 마법사`, `원문별칭=판초법사`, `후보URL=https://novel.munpia.com/530500`가 남았다.
- [x] `docs/devs/FULL_POST_JUDGE_RUNBOOK.md`에 Codex subagent fan-out 운영 지침을 추가했다.
- [x] `docs/devs/FULL_POST_JUDGE_RUNBOOK.md`에 전수 행별 dump의 `LLM 판단 사유(한글)` 필수 규약을 추가했다.
- [x] `report/rows/full_post_judge_rows_p01.md`..`p03.md`를 새 규약으로 재생성했다. 모든 post 행은 GPT/Claude/vLLM judge 판단 사유를 한국어 문장으로 가진다.
- [x] rows dump 검증: pages `3`, rows `779`, Korean reason weak rows `0`, `11694064` sentinel reason에 `판초우의의 마법사`/`판초법사`/`현재 primary보다 직접적인 근거` 포함.
- [x] LLM judge 요구를 정정했다. completed779 외부 judge 기본 경로는 `agbrowse`나 API key가 아니라 Codex 5.5 native web search/open이다.
- [x] `out/codex_native_web_judge_20260620_165159_711176_completed779/verdicts/verdict_000_sentinel11694064.json`에 Codex-native web sentinel verdict를 저장했다.
- [x] `11694064` Codex-native web verdict는 source URLs `novel.munpia.com/530500`, `series.naver.com/...14207846`, `gall.dcinside.com/...12162458`를 근거로 `wrong_work / REPROCESS / conflicting_or_multi_candidate`를 유지한다.
- [x] Codex-native web judge batch `000`..`155` subagent return을 `subagent_returns/`에 raw 보존하고, 표준 verdict `verdict_000.json`..`verdict_155.json`으로 정규화했다.
- [x] Codex-native web progress artifact 기준 표준 batch `779`건, unique `779/779`, missing `0`, `full_scope_complete=true`를 기록했다. `11718069`는 source URL 보강 후 author_talk/adjacent HOLD로 분리했다.
- [x] 초기 native-web 추가 이슈: `11718085` under-resolved, `11718089` author/new-work HOLD, `11718095` 댓글 명시 제목 누락, `11718094` OCR-only unresolved 보존.
- [x] 추가 native-web 이슈: `11718119` 즉사무림 under-resolved, `11718114` generic system trope over-resolved, `11718105` OCR 다중 공식작 후보 누락, `11718091` 정보 부족/human review, `11718106` author_talk/adjacent 보존, `11718061` 복수 추천 목록 null-title 보존.
- [x] 추가 native-web 이슈: `11718057` 컵라면 신작 후보 HOLD, `11718055` 댓글 명시 제목 누락, `11718051` 댓글 단서 제목 누락, `11718049` 추천 댓글 URL 후보 보존 누락, `11716501` 히로인 분양 일반 용어 과승격, `11716500` 검머기 title 누락, `11716492` 댓글 추천작 누락.
- [x] 추가 native-web 이슈: `11716482` 댓글 다중 후보 HOLD, `11716480` OCR 제목은 맞지만 후보 URL title mismatch, `11716479`/`11716475` `고능아 -> 저 머리 좋은데요` 누락, `11716478` 댓글 2작품 후보 보존 누락, `11716462` `니생들 -> 니들 생각 다 들린다` 누락, `11716453` `마학간 -> 마왕은 학원에 간다` 누락, `11716448` `아생갤 -> 아카데미 생존 갤러리` 누락.
- [x] 추가 native-web 이슈: `11714913` `주서연 -> 전 버튜버가 하고 싶은데요` 누락, `11714905` 근친 태그 글 후보 `오랜만에 만난 가족이 너무 야함`, `11714904` `괴담동 -> 괴담 동아리` 누락, `11714902` `헌터상담` wrong_work, `11714898` OCR 소개문 단일작품 누락, `11714888` `고은하 -> 격투 천재 여고생이 되었다` 누락, `11714887` `도굴왕 1 |` garbage title.
- [x] 추가 native-web 이슈: `11714879` `무한회귀 여자친구 네토라세` 누락, `11714876` `합스부르크의 슈퍼스타가 되었다` 누락, `11714875` `K-문화의 제왕` 누락, `11714869` `묵향`/`묵향 다크레이디` primary 경합, `11714867` `쿠크루` 작가 메타 관련성, `11714865` `현질수선전` 누락, `11713233` `가챠 중독자의 퓨전펑크 생활` 누락, `11713228` `빙엄아유 -> 빙의한 엄마가 아들을 유혹함` 후보 HOLD.
- [x] 추가 native-web 이슈: `11713222` `잘생인방 -> 잘생기면 편해지는 인방 생활` 누락, `11713217` 마스킹 캐릭터 단서 `미래에서 온 연애편지` 누락, `11713215` 오늘도요 신작 `즉사기 들고 무림에 떨어지다` 누락, `11713214` `눈물을 마시는 새` 약한 밈 후보 HOLD, `11713210` `설문조사를 했다가 세상을 부숴 먹었다.` 누락, `11713206` `킬더드 -> 킬 더 드래곤` 누락, `11713205` 댓글 문피아 URL `농사 좀 지었을 뿐인데 고려가 제국이 되었다` 누락, `11713197` 공식 URL 보강 필요 `heretic_url_null`.
- [x] 추가 native-web 이슈: `11713190` 노피아→문피아 작가/플랫폼 메타 wrong_relevance, `11713186` `목마신작 -> 검귀가 환생함` 누락, `11711636` 작가/프로모션 메타 정보 부족, `11711632` 애니 `너의 이름은.` OCR을 리디 `Your Name` 웹소설로 흡수한 wrong_work, `11711631` `괴담에 휘말렸다` title-correct URL mismatch, `11711627` `지구판역 -> 판타지에 지구 역사를 풀었다` 누락, `11711622` 댓글 URL `무림에서 외과의로 살아가는 법` 누락, `11711620` OCR `괴이에게 애호받는 신입이 되었다` 누락, `11711616` `새로운 이치/알렙 -> 괴담 호텔 탈출기` 누락.
- [x] 추가 native-web 이슈: `11711605` `랫따싶` 다중 후보/작품군 HOLD, `11711600` `망카데미 -> 망할 놈의 아카데미` 누락, `11711599` 특정 소설 장면 감상이나 title 정보 부족, `11711597` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 후보, `11711596` 댓글 URL `로판 속 주인공이 나만 좋아함` 누락, `11711590` 문모전/웹소설 공모전 AI 플랫폼 메타 wrong_relevance, `11711582` AI 작가/창작 메타 HOLD, `11711581` 작가 정체성 메타 HOLD, `11710069` 삼국지 서사 감상 wrong_relevance.
- [x] 추가 native-web 이슈: `11710067` 장르 클리셰 토론 wrong_relevance, `11710065` 노피아 랭킹/4드론 플랫폼 메타 wrong_relevance, `11710063` 댓글/인용 제목 `나비꽃` 누락, `11710059` OCR 웹소설 본문 반응 정보 부족, `11710058` `판초우의의 마법사` under-resolved/wrong_relevance, `11710056` `아카데미 생존 갤러리` 누락, `11710055` `가챠 중독자의 퓨전펑크 생활` 캐릭터 근거, `11710052` `아카엄창 -> 아카데미 패드립 면역` 누락, `11710047` wrong_work `로판 속 미움받는 악역이 되었다` vs `아카데미 속 미움받는 악역이 되었다`, `11710045` OCR 웹소설 장면 정보 부족, `11710044` `가챠펑크 -> 가챠 중독자의 퓨전펑크 생활`, `11710043` `악엔 -> 악역의 엔딩은`, `11710042` `아카엠창` weak source HOLD, `11710039` `기계공주 -> 헌터갤러리의 국가권력급 기계공주`, `11710038` 댓글 명시 제목 `제발 죽지 말아주세요, 공녀님`, `11710037` `담텔기 -> 괴담 호텔 탈출기` trope boundary HOLD.
- [x] 추가 native-web 이슈: `11710035` `즉사무림 -> 즉사기 들고 무림에 떨어지다` 누락, `11710033` `판초법사 -> 판초우의의 마법사` wrong_work, `11710025` `망카 -> 망할 놈의 아카데미` 누락, `11710024` `주술초월 -> 주술사는 초월을 원한다` 누락, `11710021` `무마 -> 무한의 마법사` title-correct URL missing, `11710020` `주전무 -> 주무시기 전에 무엇을 하셨나요?` URL missing, `11710019` `한가인/승엽이 -> 괴담 호텔 탈출기` 캐릭터 단서 누락, `11708481` `지잡아카 -> 지잡 아카데미와 폐급 히로인들` 누락, `11708479` `시달소 -> 시간을 달리는 소설가` wrong_relevance, `11708478` 댓글 명시 제목 `사연 있는 악역으로 착각 당한다` 누락, `11708475` 브런치 글 OCR을 웹소설 unresolved로 본 wrong_relevance.
- [x] 추가 native-web 이슈: `11708470` `절꺾않` title-correct URL mismatch, `11708469` `기계공쥬 -> 헌터갤러리의 국가권력급 기계공주` 누락, `11708468` `반지성마왕 -> 반지성주의 마왕의 세계침략` 누락, `11708466`/`11708457` `매국노` 누락, `11708461` OCR `마법소녀 갤러리` 누락, `11708460` garbage title `novel.munpia.com`, `11708453` `이불사 -> 이세계 불법체류 사이비` 누락, `11708450` `악살싶`/`변마금` 작품 간 표절 토론 wrong_relevance, `11708449` `담청 -> 죽었다 깨어도 수선` 캐릭터 단서 누락, `11708446` 추천글 후보 ledger 누락, `11708443` `괴담출근` 공식 URL missing, `11708442` 정주행 추천글 다중 후보 보존 누락.
- [x] 추가 native-web 이슈: `11708437` `악살싶` title-correct URL mismatch 및 후보 보존 점검, `11708434` `지갑송 신작 -> 반강제적 제국주의자` 누락, `11708430` `매국노` 누락, `11706873` `전능뇌 -> 전능의 뇌를 얻었다` 누락, `11706871` `파우스트 1` URL missing, `11706860` 림버스 `파우스트` OCR wrong_relevance, `11706857` 댓글 `헌터상담 -> 조향사의 헌터상담기록` 누락, `11706856` 백합 추천글 후보 ledger 누락, `11706855` 웹툰/소설 혼재 추천글 후보 보존 HOLD.
- [x] 추가 native-web 이슈: `11706852` `판초법사 -> 판초우의의 마법사` 별칭 official_title under-resolved, `11706845`/`11706840`/`11706832` `황제분충 -> 황제폐하가 웹소설 작가임을 숨김` 누락 또는 wrong_relevance, `11706844` OCR `범 먹는 괴이 사냥꾼`/편곤 단서와 현 문피아 `호랑이 사냥꾼` 불일치 재검증, `11706828` `내 마법도서관이 살아있다` 누락, `11706827` `기계공주 -> 헌터갤러리의 국가권력급 기계공주` 누락.
- [x] 추가 native-web 이슈: `11705273`/`11705258` `판초우의/판초 10 -> 판초우의의 마법사` 누락, `11705272` `태탑 -> 태양의 탑` garbage_title, `11705266` 노벨피아 자유연재/로판 플랫폼 담론 wrong_relevance, `11705264`/`11705257` `히로히로 -> 히어로 IN 히로인` 누락, `11705262` `수상남매 -> 수상할 정도로 사이가 좋은 남매` 댓글 후보 누락, `11705261` `이티알 -> 이세계 TRPG 게임마스터` 누락, `11705259` `아생갤 -> 아카데미 생존 갤러리` 누락, `11705256` `하남자 탑 -> 하남자의 탑 공략법` 누락, `11705249` 웹툰/소설 adaptation comparison subtype mismatch, `11705248` `이블파티 -> 나의 악당들` wrong_work.
- [x] 추가 native-web 이슈: `11705245`/`11705241`/`11705235` `하남자/하남자탑공략 -> 하남자의 탑 공략법` 누락, `11705243` SF 추천글 wrong_relevance, `11705240` TS여경물 추천 욕구를 `격투 천재 여고생이 되었다`로 over-resolved, `11705239` 도쿄구울 패러디 찾기글 over_resolved, `11705237` 월야환담 웹툰 under-resolved, `11705231` `설지후/탐식 -> 탐식의 재림` wrong_relevance, `11705228` 일본 로맨스소설 장르 담론 wrong_relevance, `11703673` `나비꽃2` 댓글 확인 누락, `11703669` `세나영 -> 세상에 나쁜 영애는 없다` 누락, `11703668` `갤질의사 -> 댓글 보는 천재 의사` 누락, `11703666` 키오스크 괴담 소재 담론 wrong_relevance, `11703663` 노벨피아 플랫폼 이용/추천 맥락 wrong_relevance.
- [x] 추가 native-web 이슈: `11703661` `막드제 -> 막장드라마의 제왕` 누락, `11703658` `아프리카 반란군 사령관이 되었다` 문피아 공식 URL 보강, `11703657`/`11703641` 댓글 URL `야만인은 문명하면 안되냐` 누락, `11703654`/`11703650` 웹소설 소비·추천글 wrong_relevance, `11703649` 댓글 추천작 `레즈돔 일진녀의 마조 노예로 조교당한다` 누락, `11703640` 부수 댓글 `기계공주` over_resolved, `11703637` `주술회전` cross-media 경계, `11703634` `세종 파딱 -> 세종의 종신재상이 되었다` 누락, `11703631` `이블파티 -> 나의 악당들` wrong_work, `11703629` 작품 감상 맥락 정보 부족.
- [x] 추가 native-web 이슈: `11703625` `목마 신작 -> 검귀가 환생함` 누락, `11703624` `판초법사 -> 판초우의의 마법사` 누락, `11703621` 댓글 `시체공양으로 데미갓` HOLD, `11702094` `댓글창 -> 댓글창의 천재 마법사` 누락, `11702090`/`11702082`/`11702078`/`11702077` `괴담 호텔 탈출기` 캐릭터·설정 단서 누락, `11702087` 위키 문서형 garbage title, `11702086` OCR 명시 `6★ 가챠 캐릭터가 되었다` 누락, `11702085` 괴담텔 wrong_relevance, `11702081` `게임 속 재해병 이야기` wrong_relevance, `11702079` `망향무사` URL mismatch.
- [x] 추가 native-web 이슈: `11702072`/`11702068`/`11702066`/`11702063`/`11702060`/`11702059`/`11702054`/`11702052`/`11702051`/`11702047` `괴담 호텔 탈출기` 캐릭터·설정 단서 누락 또는 비관련 오판, `11702064` OCR 명시 `흔해빠진 직업으로 세계최강` 누락, `11702061` 동명 후보 있는 `요리의 신` 후보 보존 필요, `11702057` 댓글 추천작 `멸망할 세계의 파견 용사` 누락, `11702055` `괴담 호텔 탈출기` title-correct URL mismatch, `11702050` `폴라리스 랩소디` URL missing, `11702049` `2레벨무신 -> 2레벨로 회귀한 무신` 누락.
- [x] 추가 native-web 이슈: `11700504` OCR 명시 `시간을 달리는 소설가` title/url 보강, `11700495` `서문청 -> 이 무림의 미친년은 나야` 누락, `11700490` 노피아 독서/추천 플랫폼 메타 wrong_relevance, `11700488`/`11700485` 버거피아/부기 플랫폼 이벤트 메타 wrong_relevance, `11700487` `군필돌 -> 아이돌이 군필을 숨김` URL missing, `11700483` `니생들 -> 니들 생각 다 들린다` URL missing, `11700480` 기계공주 후보 HOLD, `11700475` 댓글 공식 URL `내 파티에는 미친년들만 꼬인다` 누락.
- [x] 추가 native-web 이슈: `11700473` `로나좋 -> 로판 속 주인공이 나만 좋아함` truncated/garbage title, `11700470` OCR `밤도깨비 에이브` 공식 제목 미검증 HOLD, `11700468` `악당 엔딩 -> 악역의 엔딩은` 누락, `11698910` `판초우의 -> 판초우의의 마법사` 누락, `11698907` `괴담텔 -> 괴담 호텔 탈출기` 누락, `11698903` `기계공주 -> 헌터갤러리의 국가권력급 기계공주` title/url mismatch.
- [x] 추가 native-web 이슈: `11698897`/`11698895`/`11698886` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 누락 또는 wrong_relevance, `11698890` `댓천마 -> 댓글창의 천재 마법사` URL missing, `11698888` 월억킥 창작/수익 밈 relevance, `11698884` `무림마조` 캐릭터명 under_resolved, `11698880` `아생갤` title-correct URL mismatch, `11698878` `담청 -> 죽었다 깨어도 수선` OCR/DC콘 후보 HOLD, `11698875` `몸을 만지는 관문지기가 되었다` wrong_relevance, `11698873` `내마도살/전생흑막` 작가-전작 후보 보존, `11698871` `리제로 -> Re : 제로부터 시작하는 이세계 생활`, `11698870` 고전문학 스코프 HOLD, `11698869` `월야환담` URL missing, `11698868` `방타스 -> 방접은 죽어서 하세요`, `11698867` 핵전쟁 이후 생존물 추천 relevance.
- [x] 추가 native-web 이슈: `11698866` `캣파` 장르소설 인접 추천/스코프 HOLD, `11698865` `나츠키 스바루/작중 행적` 위키성 wrong_work와 `Re : 제로부터 시작하는 이세계 생활`, `11698862` OCR 제목찾기 글 re_search HOLD, `11698861` `엘황 -> 외신이 쓴 마도서를 주웠다.`, `11698860` `악엔 -> 악역의 엔딩은 죽음뿐`, `11698859` `귤부인 -> 친아들이 내게 집착한다`, `11697267` `아생갤` title-correct URL mismatch, `11697266`/`11697258` `담청/죽깨수 -> 죽었다 깨어도 수선`, `11697261` `까꿍공주` info_missing HOLD, `11697256` TS 추천글 multi-candidate HOLD, `11697255` `판초 -> 판초우의의 마법사`.
- [x] 추가 native-web 이슈: `11697242` 유희왕 패러디/팬픽 장르 트로프 wrong_relevance HOLD, `11697241` 댓글 공식 URL `나폴리탄 괴담 세계 속 대장장이가 살아남는 방법`, `11697239` 조혈모세포 안내 책자 OCR을 리디 작품으로 흡수한 false positive, `11697236` `엘시짤 -> 미래에서 온 연애편지` 캐릭터 앵커 누락, `11697234` OCR/목마 단서 `검귀가 환생함`, `11697233` 하츠네 OCR 과민 wrong_relevance, `11697231` `아생갤 -> 아카데미 생존 갤러리`, `11697229` 백합 장르 트로프 scope HOLD, `11697226` 여주물 추천 multi-candidate HOLD, `11697219` 댓글 `바르바로이 -> 이세계 검은 머리 바르바로이가 미궁에서 살아남는 법`.
- [x] 추가 native-web 이슈: `11695639`/`11695637`/`11695634`/`11695633`/`11695627`/`11695623`/`11695617`/`11695611`에서 마지막 전 구간의 약칭·댓글·OCR 기반 후보 보존 누락을 추가 확인했다.
- [x] 추가 native-web 이슈: `11695609`/`11695607` `랫따싶 -> [림월드]변방계에서 회귀자로 살아남기` 후보 보존 HOLD, `11695608` `예수천국 불신지옥` under_resolved, `11695602` OCR/광고 후보 `로판 속 바바리안 부부`, `11695599` garbage title `창관전생()` -> `창관전생(娼館轉生)`, `11695593` `_172` 신작 `S급 헌터도 결혼이 하고 싶다` 후보 보존, `11694064` sentinel wrong_work, `11694059` 플랫폼/추천글 multi-candidate 후보 보존, `11694042` `김근홍/2회차 -> 괴담에 휘말렸다` 누락.
- [x] `tools/codex_native_web_judge_ingest.py`를 추가해 subagent raw JSON을 raw/verdict/progress/rows로 표준 병합하는 coordinator helper를 만들었다.
- [x] `tools/codex_native_web_judge_ingest.py` progress JSON 저장 순서를 보정하고 external judge enum drift(`independent`, `missed_official_work`, `High`, `set_official_title_and_url`) normalization을 추가해 `rows_written=779`, `bad_question_runs=0`이 파일에도 남도록 했다.
- [x] `tools/codex_native_web_judge_ingest.py` rows renderer를 post_id 기준으로 dedupe해 standalone sentinel과 표준 batch `153`의 `11694064` 중복이 전수행 dump를 `780`행으로 부풀리지 않게 했다.
- [x] batch `006`..`155` 표준 verdict/raw/rows의 한국어 사유 인코딩을 복구/보존했고, `???` replacement run `0`, rows `779`를 확인했다.
- [x] `py_compile tools\full_post_judge_codex_driver.py src\llm_batch\candidate_audit.py tools\codex_native_web_judge_ingest.py` 통과.
- [x] `unittest tests.test_candidate_audit tests.test_judge_seed_registry tests.test_codex_native_web_judge_ingest -v` 25 tests OK.
- [x] `git diff --check` exit `0` 확인. CRLF 변환 warning만 출력됐고 whitespace error는 없었다.
- [ ] `wrong_work=2`와 `conflicting_or_multi_candidate=2`를 후속 primary-selection fix seed로 packet화한다.
- [x] completed779 전체 Codex-native web judge는 표준 verdict `779`건, unique `779/779`, rows `779`, missing `0`, bad question runs `0`으로 닫았다.

## 2026-06-19 Track C blocked7 recall 체크

- [x] `11661853` C31/C32 변동 원인을 분리했다. 공식 URL이 들어온 런은 final recall 승격이 약했고, 공식 URL이 안 들어온 C32는 title-body 검색이 여행/위키 nonzero에서 조기 종료됐다.
- [x] `agentic_pipeline.py` final-pass official URL recall이 title-body 공식 detail 검색 결과를 회수하도록 보강했다.
- [x] `orchestrator.py` title-body sanitized probe 검색 예산과 조기 종료 조건을 보강했다. non-official nonzero만으로 남은 specific title-body probe를 중단하지 않는다.
- [x] `py_compile` 통과, 관련 focused suite `95` tests OK.
- [x] 실제 `expert_main.py` C33 blocked7 canary를 요청 `--parallel 16`으로 실행했다. manifest `requested_parallel=16`, `effective_parallel=7`, `completed/failed/pending=7/0/0`, `large_run_complete=true`, search health `7/7 OK`.
- [x] C33에서 `11652175 -> 괴담 호텔 탈출기`, `11661853 -> 두바이의 쫀득한 여초딩 재벌 9세`, `11677911 -> 잘생기면 편해지는 인방 생활`이 공식 detail URL과 함께 resolved 됐다.
- [x] C33에서 `11665081/11687635/11695607/11705276`은 public title 없이 non-resolved 유지했다.
- [ ] C33은 VLM/OCR off targeted canary다. image-positive semantic approval 또는 full scan approval로 승격하지 않는다.

## 2026-06-19 Track B precision sticky demote 체크

- [x] B18 실패 원인을 확인했다. `11661847`은 hidden-setting precision demote 후 후단 official-url recall/locked rescue가 다시 `괴담 호텔 탈출기`를 public title로 살리는 경로였다.
- [x] `_final_precision_title_demote_profile()`에 sticky precision-demote guard를 추가했다. 이미 `track_b_precision_demoted_*`가 붙은 late recovery는 direct full title/main official URL 없이 재승격하지 않는다.
- [x] 회귀 테스트를 추가했다. `official_url_recall_gate_recovered + confirmed_alias + track_b_precision_demoted_hidden_setting_surface` 조합은 `sticky_precision_demote_after_late_recall`로 demote된다.
- [x] `py_compile` 통과, focused sticky regression OK, Track B focused suite `32` tests OK.
- [x] 실제 `expert_main.py` B19 full 8-row canary를 요청 `--parallel 16`으로 실행했다. manifest `requested_parallel=16`, `effective_parallel=8`, `completed/flushed/pending/failed=8/8/0/0`, `large_run_complete=true`.
- [x] B19에서 `11661847`은 `is_relevant=True`, `work_resolution=unresolved`, `title_resolution_state=unresolved_matchable`, `novel_identity=None`으로 확인됐다.
- [x] B19 나머지 probe도 기대 경계 유지: `11666700/11660235` unresolved, `11682781` resolved, `11657013/11655387/11648980/11650585` non-resolved.
- [ ] B19는 VLM/OCR off라 image-positive semantic approval 증거가 아니다. image 경로 검증은 VLM/OCR 또는 browser review가 안정화된 뒤 별도 수행한다.
- [ ] `11661847` 단건 postprocess가 `1953.0s` 걸렸다. 장시간 finalization/official evidence scan 병목은 별도 런타임 개선으로 추적한다.

## 2026-06-18 GOAL_RECALL_URL_GATE Phase B/A 체크

- [x] `docs/devs/GOAL_RECALL_URL_GATE.md` Required Reading와 guardrail(과승격 금지, no-work 단조성, candidate 보존, post_id 하드코딩 금지)을 확인했다.
- [x] Phase B를 먼저 수행해 score>=5 high_recovery `629`건 중 기존 `123`건 제외 `506`건을 compact projection 기준으로 전부 판정했다.
- [x] Phase B 결과 high_recovery missing `0`, 새 회수 `59`, 새 deterministic_catchable `59`를 확인했다.
- [x] `recall_recovery_seed.jsonl`을 `124`행, deterministic_catchable `101`행으로 확대했다.
- [x] `candidate_audit.official_url_recoverable()` helper를 추가하고 official DETAIL URL + 강한 제목/post 단서(full title/OCR/confirmed alias/제목 약칭/본문 URL) 일치 조건으로 제한했다.
- [x] `agentic_pipeline`에 official URL recall gate를 연결해 `DetectedTitle`, `primary_work`, `title_candidates`, `verification_result.novel_identity`를 함께 동기화했다.
- [x] viewer/search/listing/community/review/comment tab URL, no-work/context-only/memory-query/nonwork state, semantic no-work guard 미통과 경로를 차단했다.
- [x] seed 회귀에서 mismatch가 나온 공식 page tag/희귀 토큰/괄호 tag 단독 anchor는 자동승격에서 제외했다.
- [x] `mm.munpia.com/?menu=novel&id=...` 모바일 문피아 detail query를 `https://m.munpia.com/novel/detail/...`로 정규화했다.
- [x] 후보 보존, post_id 하드코딩 금지, slang DB write-back 금지, semantic quality `REVIEW-LOCKED`, full scan approval `false`를 유지했다.
- [x] seed regression: deterministic seed `101`, official URL gate eligible `93`, compact projection missing `0`, gate promoted/title matched `47`, exact title+URL matched `46`.
- [x] focused tests: `py_compile`과 `tests.test_candidate_audit tests.test_judge_seed_registry` `21` tests OK.
- [x] search-health gate 보강 후 실제 `expert_main.py` retest를 수행했다. A4/A5 text-only probe는 requested `--parallel 16`, effective `4`, health OK, `completed/flushed/pending/failed=4/4/0/0`, `large_run_complete=true`.
- [ ] 55-row controlled canary는 A2에서 health 16/16 OK까지 확인했으나 본체가 `completed=14/55` partial에서 정지했다. A3 image probe도 `completed=1/2` partial이라 VLM/image 장시간 이슈로 분리해 추적한다.
- [ ] 실제 런타임 47 승격 set over-promotion 감사는 파이프라인 재실행 후 닫는다.
- [ ] full expert_main 대규모 재실행과 full-scan approval은 별도 승인 전까지 열지 않는다.

## 2026-06-18 full_post_judge 20260616_224555_632905 체크

- [x] `docs/devs/FULL_POST_JUDGE_RUNBOOK.md` §3 절차와 §4.3b FULL 16필드 스키마를 기준으로 작업 범위를 확인했다.
- [x] `out/expert_result_20260616_224555_632905.json` flushed result `2246`건을 판정 모수로 잡고, manifest pending `23`건은 `_pending_rerun.json`으로만 분리했다.
- [x] `candidate_audit` 기반 compact projection을 `BATCH=5`로 생성해 `batches/batch_000.json`..`batch_449.json` 총 `450`개를 만들었다.
- [x] `official_search_supports_title`, lint flags, slang audit route, `suggested_search_grade` precompute를 LLM 없이 채웠다.
- [x] FULL verdict `450`개를 생성했고, `likely_correct` enum은 runbook 기준 `pipeline/claude/both_unclear`로 정규화했다.
- [x] repo MCP search bridge 기반 web probe cache `421` query를 만들고, 확인 URL이 없는 행은 작품명을 생성하지 않고 `Missing`/재검증 큐로 남겼다.
- [x] slang 축은 `slang_axis_route=="llm"` `94`건만 판정했고, slang DB write-back은 하지 않았다.
- [x] 병합 후 `judged=2246`, `missing=0`, bad files `0`, FULL 16필드 누락 `0`, invariant 위반 `0`을 확인했다.
- [x] `candidate_audit` shadow 재버킷 mismatch `0`을 확인했다.
- [x] 정밀 overlay `vverdicts` `449`개와 hold/unresolved 15% 층화표본 recall overlay `rhold_vverdicts` `42`개를 생성했다.
- [x] `full_post_judge_report.md`, `full_post_judge_metrics.json`, 전수 rows `p01`..`p08`을 산출했다.
- [x] run integrity는 `GO`, semantic quality는 `REVIEW-LOCKED`, full scan approval은 `false`로 기록했다.
- [ ] action queue 후속: `human_review=110`, `re_judge=87`, `re_search=44`, `slang_db_review=22`를 pipeline fix 또는 사람 검수 단위로 분해한다.
- [ ] search correctness 후속: resolved `351`건 중 `Missing=132`와 `heretic_url_null while resolved=72`를 우선 re_search 대상으로 좁힌다.
- [ ] slang 후속: `pollution_risk=22` 및 store=true pollution risk `11`건은 slang DB 반영 없이 별도 검수한다.

## 2026-06-14 agbrowse GPT Pro judge 실행 보정 체크

- [x] ChatGPT Pro 로그인 상태와 `agbrowse web-ai query` smoke를 확인했다.
- [x] `--context-from-files`/`--file` 전달과 Windows `agbrowse.cmd` wrapper 조합에서 `{"batch":null,"verdicts":[]}` 빈 응답이 발생함을 확인했다.
- [x] runner를 `node %APPDATA%\npm\node_modules\agbrowse\bin\agbrowse.mjs` 직접 실행 + `POSTS_JSON` inline 방식으로 변경했다.
- [x] 25건 batch는 내부 5건 sub-call로 나누고, post_id 집합 검증 후 `verdict_<batch>.json` 하나로 병합하도록 했다.
- [x] smoke 5건에서 post_id 누락 없는 유효 JSON verdict를 저장했다.
- [x] `query` 완료 감지 hang을 피하기 위해 기본 호출을 `send -> watch -> sessions show` 세션 경로로 바꿨다.
- [x] ChatGPT provider tab 누적에 따른 `provider.commit-not-verified`를 줄이기 위해 chunk 호출 전후 tab cleanup을 추가했다.
- [x] 5건 chunk 실패 시 1건 subchunk checkpoint로 자동 분해하는 fallback을 추가했다.
- [x] ChatGPT UI 전송 단계에서 막히는 성적/연령 민감 표현은 provider prompt에서만 bracket label로 치환하고, 원본 batch/checkpoint는 보존하도록 했다.
- [x] stale `sent` web-ai session이 누적될 때 `provider.commit-not-verified`가 반복되는 것을 줄이기 위해 오래된 sent-session prune을 추가했다.
- [x] 장기 pass에서 일부 batch가 간헐 실패해도 checkpoint를 보존하고 다음 batch로 넘어가도록 `--continue-on-fail`을 추가했다.
- [x] 25건 단일 호출(`--records-per-call 25 --no-split-on-failure`)이 batch `006`~`019`에서 유효 JSON을 반환해 장기 실행 기본 모드로 승격했다.
- [x] `out/_judge3905_gpt_pro_v2` batch `000`~`099` 기준 `2500/3874` post, `100/155` batch 검증을 통과했다.
- [x] ChatGPT `요청이 너무 많습니다` 팝업이 반복될 때 snapshot 기반 `알겠습니다` watcher로 닫으며 진행하고, 필요 시 5건 chunk 사이 `--chunk-sleep-sec`를 둘 수 있게 했다.
- [x] `out/_judge3905_gpt_pro_v2` batch `000`~`125` 기준 `3150/3874` post, `126/155` batch 검증을 통과했다.
- [x] `out/_judge3905_gpt_pro_v2`에서 ChatGPT Pro judge 기준 batch `126`~`154` 전수 판정을 완료했다.
- [x] 최종 aggregate 기준 `3874/3874` post, `155/155` batch, `agree=2303`, missing `0`, `invalid_batches=[]`를 확인했다.
- [x] `post_reviews.jsonl`, `post_reviews.md`, `post_ids_by_type.json`, `_result.json`을 생성하고 `JUDGE3905_REPORT.md`를 GPT Pro 전수 결과 기준으로 갱신했다.
- [x] 파이프라인 구조/프롬프트/BatchContext/slang_db와 judge 결과를 묶은 연구 컨텍스트 문서를 작성했다.
- [x] ChatGPT web-ai 심층 분석 결과를 `GPT_PRO_PIPELINE_RESEARCH_DIRECTIONS_20260614.md`로 정리했다. 단, ChatGPT UI model selector 미검출로 `pro/extended` 강제 확인은 실패했음을 기록했다.
- [x] `--research deep` 재실행을 보냈고 session `01KV31C9QFS5YN3SZF7BBJNHZ9`, URL `https://chatgpt.com/c/6a2e9d3e-458c-83ee-b3ea-5485161b92e8`, 응답 JSON `out/agbrowse_deep_research_poll_20260614.json`을 남겼다.
- [x] 재실행 caveat를 `GPT_PRO_DEEP_RESEARCH_RERUN_20260614.md`에 기록했다. UI는 `Pro 확장 모드`였지만, `agbrowse` effort selector 강제와 Deep Research 활성은 검증 완료로 보지 않는다.
- [x] GPT Pro judge의 high/med seed를 seed registry로 묶고 recall/precision 우선순위별 patch-ready regression set을 만들었다.
- [x] P0 `candidate_ledger` shadow, `official_title_lint`, `identity_consistency_lint`를 dry-run artifact로 생성했다.
- [x] 24건 `expert_main` canary를 실제 실행했다. run id `20260614_230245_886140`, input/completed/flushed/pending/failed `24/24/24/0/0`.
- [x] canary compare는 manifest scope 기준 expected/result/compared `24/24/24`, missing `0`, run integrity `GO`다.
- [x] semantic quality는 `REVIEW-LOCKED`로 유지했다. 이번 canary는 head-slice seed evidence이며 full scan approval이 아니다.
- [x] judge batch source의 원본 image URL 누락 때문에 `image_post_count=0`, VLM/OCR semantic gate `no_image_blocks`로 skip된 한계를 source-enriched canary로 보완했다.
- [x] shadow artifact를 실제 pipeline-level candidate ledger / promotion policy instrumentation으로 연결했다.
- [x] source-enriched canary input은 24건 중 image seed 18건의 URL을 모두 복원했고 unrecovered `0`이다.
- [x] source-enriched run id `20260615_001642_376095`는 input/completed/flushed/pending/failed `24/24/24/0/0`, `image_post_count=18`, VLM/OCR `READY`, runtime contract `GO`다.
- [x] source-enriched compare는 expected/result/compared `24/24/24`, missing `0`, after labels `safe_resolved=3`, `promotion_blocked=7`, `hold_unresolved=4`, `output_consistency_lint=8`, `identity_consistency_lint=2`다.
- [x] non-overlapping high-risk expansion input 36건을 만들었다. group count `recall=12`, `precision=16`, `hygiene=8`, image post `36`, source restore missing `0`이다.
- [x] high-risk expansion run id `20260615_012056_067394`는 input/completed/flushed/pending/failed `36/36/36/0/0`, effective parallel `36`, MCP health `8/8`, `image_post_count=36`, VLM/OCR `READY`, runtime contract `GO`다.
- [x] high-risk compare는 expected/result/compared `36/36/36`, missing `0`, after labels `safe_resolved=7`, `promotion_blocked=12`, `hold_unresolved=3`, `output_consistency_lint=8`, `identity_consistency_lint=5`, `official_title_lint=1`이다.
- [x] `src/llm_batch/slang_db.py`가 low-information/domain alias surface(`novel`, `dc`, `그리고`, domain/URL label)를 storage observation에서 차단하도록 보강됐다.
- [x] slang guard focused canary run id `20260615_021205_542965`는 input/completed/flushed/pending/failed `3/3/3/0/0`, `image_post_count=3`, VLM/OCR `READY`, finalize flush `buffered_observations=0`, runtime contract `GO`다.
- [x] URL/domain official title promotion guard를 추가해 `11663514`류 domain/platform label이 `official_title`로 남지 않게 했다.
- [x] domain/lint focused canary run id `20260615_105502_850042`는 input/completed/flushed/pending/failed `15/15/15/0/0`, `image_post_count=15`, VLM/OCR `READY`, runtime contract `GO`다.
- [x] domain/lint focused compare는 expected/result/compared `15/15/15`, missing `0`, after labels `promotion_blocked=4`, `identity_consistency_lint=3`, `output_consistency_lint=8`, official title lint after `0`이다.
- [x] random50 baseline p32 run id `20260615_120734_501402`는 input/completed/flushed/pending/failed `50/50/50/0/0`, `image_post_count=30`, VLM/OCR `READY`, runtime contract `GO`다.
- [x] random50 p32 quality summary는 `safe_resolved=10`, `review_only=2`, `hold_unresolved=31`, `promotion_blocked=7`, official/identity/output lint counts 모두 `{}`, domain/URL official title rows `[]`다.
- [x] remaining-lint focused input 15건을 생성했다. target 11건과 positive/control 4건을 포함하며 `image_post_count=15`다.
- [x] remaining-lint focused run id `20260615_165906_220298`를 실행했다. checkpoint 기준 target 11건은 모두 완료됐지만 전체 run은 input/completed/flushed/pending `15/14/8/6`이라 runtime contract `NO-GO`다.
- [x] checkpoint completed 14건을 `recover_expert_run_from_checkpoint.py`로 복구하고 final audit postprocess를 재적용했다.
- [x] precision seed official title은 URL/platform evidence가 있어도 judge-seed focused run에서는 `promotion_blocked`로 내려 후보 ledger에 보존한다.
- [x] `title_noisy_ocr` safe 판정은 official search title match가 있어야 하며, `primary_work` self-claim만으로는 safe 처리하지 않는다.
- [x] remaining-lint quality summary 기준 target 11건은 `safe_resolved=3`, `promotion_blocked=3`, `hold_unresolved=1`, `output_consistency_lint=4`로 분류됐다.
- [x] control `11639284` 단건 rerun id `20260615_194903_574111`은 input/completed/flushed/pending/failed `1/1/1/0/0`, runtime contract `GO`다.
- [x] `11636134`는 `title_noisy_ocr_realigned_to_official_image_search_evidence` guard로 `불패의 명장으로 착각당했다`에 재정렬되어 `safe_resolved`가 됐다.
- [x] combined15 closure compare는 expected/result/compared `15/15/15`, missing `0`, after labels `safe_resolved=4`, `promotion_blocked=7`, `hold_unresolved=1`, `output_consistency_lint=3`이다.
- [x] target/control 5건 evidence packet은 `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_manual_evidence_packets.json` / `_ko.md`에 있다.
- [x] focused canary의 remaining identity/hygiene lint와 small baseline의 표본 한계 때문에 full scan approval은 열지 않고 semantic quality는 계속 `REVIEW-LOCKED`로 유지했다.
- [x] continuous loop targeted 9건 run id `20260615_231925_533889`를 실행했다. input/completed/flushed/pending/failed `9/9/9/0/0`, `image_post_count=9`, VLM/OCR `READY`, compare expected/result/compared `9/9/9`.
- [x] targeted 9건 run의 Deliberation `NameError: disc` fallback을 runtime audit `NO-GO`로 잡도록 audit 도구를 보강했다.
- [x] Deliberation prompt rebuild `disc` NameError를 수정하고 단건 control `11639284` rerun id `20260615_234526_746998`로 runtime audit `GO`, compare `promotion_blocked`를 확인했다.
- [x] `title_noisy_ocr` direct image title mismatch guard를 추가했고 `11650591` 단건 rerun id `20260616_000415_830530`에서 runtime audit `GO`, compare `hold_unresolved`를 확인했다.
- [x] `11632915`과 `11650591`은 public `official_title` 과승격을 막고 후보/blocked title을 ledger에 보존하는 상태로 전환했다.
- [ ] remaining target semantic/output review는 `11602367` wrong_relevance다. `11632915`, `11650591`은 full semantic accept가 아니라 conservative hold 상태다.

## 2026-06-13 dashboard UX handoff 체크

- [x] Claude 중단 인계 텍스트를 확인하고, 서버 `/api/results` 검색/관련성 필터와 프론트 결과 테이블 UX 개선 범위를 재확인했다.
- [x] Codex subagent 전문가 2축으로 race/restore/clipboard 안정성과 테스트/문서 stale 여부를 병렬 검토했다.
- [x] live 검색/관련성 필터 중 기존 로딩 응답이 최신 검색어/필터를 덮어쓰지 않도록 latest-wins pending reload와 stale response discard를 적용했다.
- [x] 검색/필터 활성 중 SSE restore/gap 재조회가 필터 스냅샷을 덮어쓰지 않도록 guard를 추가했다.
- [x] 상세 모달 JSON 복사에서 내부 `_detail_warning` 필드를 제외하고, secure-context가 아닌 LAN/localhost HTTP에서도 textarea fallback으로 복사할 수 있게 했다.
- [x] inline script parse 검증을 통과했다.
- [x] `.venv312\Scripts\python.exe -m unittest tests.test_dashboard_standalone -v` 기준 `26` tests `OK`를 확인했다.
- [x] standalone dashboard `http://127.0.0.1:18099`에 sample 3건을 주입하고 Browser로 검색/필터 row, 상세 모달, history/live tab 전환, app console error `0`을 확인했다.
- [ ] `scratch/e2e_dashboard_ui.py`는 현재 API smoke 성격이므로, 실제 브라우저 UI E2E로 승격하려면 별도 Playwright/Browser 시나리오를 추가한다.
- [ ] Tailwind CDN production warning은 남아 있다. dashboard에 frontend build pipeline을 둘 때 local Tailwind build로 전환한다.

## 2026-06-12 dashboard browser performance 체크

- [x] Browser 플러그인으로 `http://localhost:8080/` live dashboard를 직접 열어 page identity, nonblank 화면, console 상태를 확인했다.
- [x] 기준선 settled DOM이 약 `8739` nodes이고 live 결과 테이블이 `500` rows를 렌더링하는 것을 확인했다.
- [x] `LIVE_PAGE_SIZE`를 `100`으로 낮춰 live 결과 fetch limit과 테이블 DOM을 줄였다.
- [x] worker 카드별 render signature를 추가해 변경 없는 카드의 `innerHTML` 재작성 비용을 제거했다.
- [x] live 로그 DOM 표시를 `MAX_LOG_RENDER_CHARS=80000`으로 제한했다. 로그 배열 보존 한도 `MAX_LOG_LINES=500`은 유지한다.
- [x] inline script parse 검증을 통과했다.
- [x] Browser 재검증에서 settled DOM `2342` nodes, result rows `100`, worker cards `26`, history -> live 탭 전환 정상, app console error `0`을 확인했다.
- [x] `.venv312\Scripts\python.exe -m unittest tests.test_dashboard_standalone` 기준 후속 UX guard 포함 `26` tests `OK`를 확인했다.
- [ ] Tailwind CDN production warning은 남아 있다. dashboard에 frontend build pipeline을 둘 때 local Tailwind build로 전환한다.

## 2026-06-02 v527 v284 residual 21-post rerun 체크

- [x] 현재 goal 범위를 10만 semantic approval이 아니라 known-bad/high-risk issue seed closure로 분리했다.
- [x] raw JSONL row `98`과 실행 post unit `21`을 분리했다.
- [x] preflight는 manifest `selected_post_count`/unique post count를 우선하고 raw row count는 fallback/evidence로만 남긴다.
- [x] v527 preflight 기준 LLM readiness `GO`, MCP effective readiness `GO`, full shard readiness `NO-GO(32/36)`를 분리했다.
- [x] `--parallel 36`은 상한으로만 사용하고 실제 effective parallel은 `21`로 확인했다.
- [x] `--reuse-shards-only`로 Docker compose up/recreate/status audit을 실행하지 않았다.
- [x] VLM/OCR on, image post count `14`, VLM/OCR semantic gate `READY`를 확인했다.
- [x] runtime audit은 completed/flushed/pending/failed `21/21/0/0`으로 `GO`다.
- [x] reason hygiene hit files `0`이다.
- [x] semantic coverage는 browser visual required/available/missing `14/14/0`, image catalog present/missing `14/0`, comment metadata present/missing `13/0`을 확인했다.
- [x] after-review는 `ACCEPT=19`, `REPROCESS=1`, `HOLD=1`로 기록했다.
- [x] `11718099`는 v528 후속에서 공식/detail 근거 보강 후 `ACCEPT/no_action`으로 닫았다.
- [ ] `11718094`는 작품 출처 사람 검토 전까지 `HOLD/human_review`로 유지한다.
- [ ] v527 targeted rerun을 10만 semantic approval로 승격하지 않는다.

## 2026-06-02 v528 remaining seed follow-up 체크

- [x] `11718099`, `11718094` 잔여 2건만 새 input으로 분리했다.
- [x] preflight는 raw row `7`, unique post `2`, rerun execution `GO`로 확인했다.
- [x] `--parallel 36`은 상한이고 effective parallel은 `2`다.
- [x] Docker compose up/recreate 없이 `--reuse-shards-only`로 실행했다.
- [x] VLM/OCR ready, completed/flushed/pending/failed `2/2/0/0`을 확인했다.
- [x] runtime contract audit `GO`, reason hygiene clean, semantic coverage `GO`.
- [x] `11718099`는 official/detail URL과 browser visual evidence로 `ACCEPT/no_action`이다.
- [x] `11718094`는 text screenshot/OCR evidence는 있으나 title source가 없어 `HOLD/human_review`다.
- [x] `11718094`는 v529 수동 리뷰에서 `HOLD/no_action`, `close_as_unresolved`로 닫았다.
- [ ] `11718094`를 임의 title/alias로 승격하지 않는다.
- [ ] v528 residual canary를 10만 semantic approval로 승격하지 않는다.

## 2026-06-02 v529 manual unresolved closure 체크

- [x] `11718094`의 image evidence는 scene text만 있고 title/author/platform footer가 없음을 확인했다.
- [x] result decision은 `is_relevant=true`, `resolved_title=null`, `work_resolution=unresolved`로 보수적이다.
- [x] 댓글 author match unverified 신호는 title resolution에 쓰이지 않았다.
- [x] exact OCR phrase / character name search로 공식 작품 detail을 찾지 못했음을 기록했다.
- [x] `HOLD` label은 대량 approval 방지용으로 보존하고, action은 `no_action`으로 닫았다.
- [x] issue-focused seed queue final gate는 `GO`로 기록했다.
- [ ] 10만 semantic approval은 expanded random/high-risk review 전까지 계속 `NO-GO / REVIEW-LOCKED`다.

## 2026-06-02 v522 11718080/11718082 live canary 체크

- [x] LLM endpoint `http://10.20.0.101:8000/v1/models`와 Gemma 4 E4B model readiness를 확인했다.
- [x] Docker compose 접근 권한 거부와 MCP full shard `32/36` 상태를 runtime readiness에서 분리했다.
- [x] 2건 canary는 effective shard `2`개만 필요하므로 preflight `GO`로 진행했다.
- [x] 실행 명령은 `--parallel 36` max, `--reuse-shards-only`, `--vlm on --ocr on --require-vlm-ocr-for-images` 기준이다.
- [x] manifest 기준 requested/effective parallel `36/2`, completed/flushed/pending/failed `2/2/0/0`, VLM/OCR `READY`를 확인했다.
- [x] Docker lifecycle auto up/recreate는 `false`이며 small run lifecycle blocked는 `true`다.
- [x] runtime audit `GO`, reason hygiene `GO`, semantic coverage with browser `GO`를 남겼다.
- [x] `11718080`은 title null/no-work adjacent로 유지되고 `소보로설` overresolve가 재발하지 않았다.
- [x] `11718082`는 image evidence catalog, VLM counter, browser visual artifact로 resolved를 확인했다.
- [x] 자연어 labels `ACCEPT=2/no_action=2`를 남겼다.
- [ ] 이 2건 canary를 10만 semantic approval로 승격하지 않는다.
- [ ] completed VLM/OCR-on source, random baseline 1000건, P0/P1 high-risk expansion 전까지 전체 gate는 `REVIEW-LOCKED`다.

## 2026-06-01 v519 direct Playwright browser evidence 체크

- [x] `playwright-cli eval` return code가 0이어도 `eval_path=null`이면 stdout/stderr를 기록하고 stdout JSON fallback을 시도한다.
- [x] Windows `npx.cmd`/daemon 경로가 깨지면 설치된 Chromium revision이 있는 cached Playwright `node_modules`를 찾아 direct Node Playwright fallback을 사용한다.
- [x] fallback manifest는 `browser_surface=fallback_playwright_node`와 `preferred_browser_surface=codex_in_app_browser_iab`를 함께 남긴다.
- [x] DC 페이지 UI의 일반 `차단` 단어만으로 blocked 처리하지 않는다.
- [x] v515 completed subset 기준 browser visual required/available/missing은 `16/10/6`이다.
- [x] v519 원본 71행 기준 browser visual required/available/missing은 `37/25/12`이다.
- [x] `11718082`는 `article_image_count=1`, `article_loaded_count=1`, pending/placeholder/incomplete/broken `0`과 screenshot으로 닫혔다.
- [x] v520 action queue는 `source_browser_visual_missing=12`와 `visual_gate_blocker_signal_count=85`를 분리한다.
- [ ] 남은 `12`건은 image loading failure 또는 image node missing이므로 ACCEPT/GO 근거로 쓰지 않는다.
- [ ] browser `Strong` row도 final decision/reason/evidence 자연어 alignment 없이는 semantic ACCEPT로 승격하지 않는다.

## 2026-06-01 v510 strict browser artifact / Arbiter memory-query 체크

- [x] memory-query weak relation-hold에서는 `Verifier High-title lock`이 `official_title`을 복구하지 못한다.
- [x] verifier-null restore보다 `memory_query_forced_upgrade_guard`를 먼저 적용한다.
- [x] memory-query guard가 걸리면 `official_title`, `official_novel_title`, `heretic_url`은 null로 유지한다.
- [x] external browser artifact는 screenshot/snapshot과 `Medium/Strong` grade만으로 `browser_visual_available`이 되지 않는다.
- [x] `article_image_count>0`, `article_loaded_count>=article_image_count`, pending/broken/placeholder/incomplete counter `0`이 있어야 external visual artifact를 인정한다.
- [x] 0 카운트도 browser target manifest coverage에 명시한다.
- [x] strict gate 재산출 기준 v506 completed subset browser visual required/available/missing은 `16/0/16`이다.
- [ ] 남은 visual target `16`건을 실제 loading counter + screenshot/observation으로 닫기 전까지 semantic approval은 열지 않는다.

## 2026-06-01 v509 browser attempt failure / subagent 병렬 체크

- [x] 이번 `/goal` 병렬은 Codex `spawn_agent` 전문가 병렬로 수행한다. repo runtime `expert_main.py --parallel` worker 수와 섞지 않는다.
- [x] Codex in-app Browser 직접 실패는 visual evidence가 아니라 blocked evidence로 기록한다.
- [x] fallback browser를 쓰면 fallback임을 명시하고 screenshot/snapshot/eval JSON을 남긴다.
- [x] `11718068`은 본문 텍스트가 보여도 article image loading counter가 실패했으므로 `browser_visual_available`로 세지 않는다.
- [x] screenshot이 있어도 `article_loaded_count < article_image_count` 또는 incomplete/broken/pending counter가 있으면 visual gate를 열지 않는다.
- [x] v509 재감사 기준 browser visual required/available/missing은 `16/1/15`이며 gate는 `REVIEW-LOCKED`다.
- [ ] 남은 browser visual target `15`건을 실제 image-loaded artifact로 닫기 전까지 OCR/search/text-only 근거를 Strong으로 승격하지 않는다.
- [ ] Codex subagent 결과는 메인 Codex가 파일/line/post_id 근거를 재확인한 뒤에만 gate에 반영한다.

## 2026-06-01 v508 intent-denied title-present / fallback target 체크

- [x] `intent_permit_for_title_search=false`인데 title이 남은 row를 `intent_denied_title_present`로 잡는다.
- [x] `title_resolution_allowed=false` 또는 `context_only/no_work` 상태와 `official_title` 공존도 resolved 여부와 무관하게 blocker로 본다.
- [x] title이 없는 context-only/no-work row는 blocker로 오탐하지 않는다.
- [x] v507 `fallback_browser` attempt manifest를 semantic coverage audit external artifact로 읽는다.
- [x] browser visual target builder는 `--browser-artifacts-manifest`를 받아 이미 확인된 fallback target을 제외한다.
- [x] v506 completed subset + v507 fallback 기준 browser visual missing은 `15`건으로 재산출됐다.
- [x] focused audit/target tests와 `py_compile`을 통과했다.
- [ ] `intent_denied_title_present` 발생 시 direct hard anchor 없이 search/rescue/alias/session knowledge가 title을 되살린 경로인지 확인한다.
- [ ] 남은 browser visual target `15`건을 닫기 전까지 semantic approval은 열지 않는다.

## 2026-06-01 v507 browser visual target / Codex subagent 병렬 체크

- [x] Codex `/goal` 병렬은 `spawn_agent` 전문가 병렬로 추적한다. repo runtime `expert_main.py --parallel` worker 병렬과 섞지 않는다.
- [x] subagent 축은 실행 오케스트레이션, VLM-OCR-browser visual gate, 자연어 이해/프롬프트 한계로 나눈다.
- [x] browser visual missing 대상은 semantic coverage issue의 sample list가 아니라 result JSON 전체에서 다시 추출한다.
- [x] browser visual target manifest에는 population/target count와 gate 상태를 남긴다.
- [x] Codex in-app Browser 직접 제어 실패는 visual evidence가 아니라 blocked evidence로 기록한다.
- [x] fallback browser를 쓰면 Codex in-app Browser 성공으로 과장하지 않는다.
- [x] fallback visual artifact에는 URL, page title, screenshot path, snapshot path, visible observation, evidence grade를 남긴다.
- [x] v506 completed subset 기준 target `16`건 중 fallback `1`건만 확인했고 전체 gate는 `REVIEW-LOCKED`로 유지했다.
- [x] 오케스트레이션/VLM-browser/natural-language subagent 보고를 통합 요약으로 남겼다.
- [x] browser visual target 도구/테스트와 semantic coverage audit을 함께 검증했다.
- [ ] 남은 target `15`건을 visual artifact로 닫기 전까지 OCR/search/text-only 근거를 Strong으로 승격하지 않는다.
- [ ] no-work/social lament/context-only 결과는 직접 작품 anchor 없이 search/rescue/alias/session knowledge/Arbiter promotion으로 되살아나지 않아야 한다.
- [ ] VLM/OCR OCR variant는 packet-local evidence로만 쓰고 global slang/alias로 저장하지 않는다.
- [ ] comment author/comment id/dialogue context는 대화 귀속과 작품 근거를 분리한 evidence role로 기록한다.
- [ ] 오타/축약/말장난 재해독은 `surface_reread_candidates[]` 범용 패턴으로 기록하고 특정 표현 고정 규칙으로 만들지 않는다.

## 2026-06-01 v506 interrupted rerun 체크

- [x] 사용자 중단 후 남은 `expert_main` 계열 프로세스를 확인하고 정리한다.
- [x] partial manifest는 full run GO로 보지 않는다.
- [x] ordered flush gap이 있으면 checkpoint/pending snapshot으로 completed subset을 별도 복구해 원본 result와 구분한다.
- [x] completed subset 감사는 full rerun approval이 아니라 partial evidence review로 표기한다.
- [x] runtime audit에서 completed/input, pending, flushed/completed 불일치가 있으면 `NO-GO`다.
- [x] VLM/OCR catalog와 comment metadata가 채워져도 browser visual required가 남으면 semantic gate는 `REVIEW-LOCKED`다.
- [x] unresolved relevant reason은 `작품 관련 단서는 충분하지만` 같은 과한 템플릿 문구를 쓰지 않는다.
- [x] future run reason hygiene clean 여부를 별도 확인한다. old partial artifact hit는 old output으로 남긴다.
- [ ] browser visual required target을 visual artifact로 닫기 전까지 OCR/search/text-only 근거를 Strong으로 승격하지 않는다.

## 2026-06-01 v505 small-run 후속 검토 체크

- [x] Codex `/goal` 병렬은 `spawn_agent` 전문가 병렬로 추적한다. repo runtime `expert_main.py --parallel` worker 병렬과 섞지 않는다.
- [x] v493 small run의 runtime contract는 `GO`로 확인했다.
- [x] v494 browser visual artifact로 `11718082` image loading/evidence를 확인했다.
- [x] image row는 `article_image_count`, `article_loaded_count`, pending/placeholder/incomplete/broken counter, screenshot 또는 VLM/OCR direct evidence를 함께 본다.
- [x] `11718080`류 adjacent/trope/social lament는 단일 작품 제목 확정 불가로 표현하고, `비관련 포스트` 단정 문구와 섞지 않는다.
- [x] 기존 artifact의 public reason wording conflict는 semantic coverage audit issue로 남긴다.
- [x] OCR 오타/표면 변형은 특정 문자열 하드코딩이나 전역 alias/slang 규칙으로 고정하지 않는다.
- [x] focused sanitize 회귀와 semantic coverage audit을 통과했다.
- [ ] 단건 카나리 evidence를 10만 semantic approval로 승격하지 않는다. expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-06-01 v504 Codex subagent 병렬 / 다음 seed package 체크

- [x] 이번 `/goal` 병렬은 Codex `spawn_agent` 전문가 병렬로 수행한다. repo runtime `expert_main.py --parallel` worker 수와 섞지 않는다.
- [x] subagent 축을 goal 문서/오케스트레이션, small-run/runtime 계약, VLM/OCR/browser visual gate로 분리했다.
- [x] 다음 seed package 생성 도구와 회귀 테스트를 추가했다.
- [x] v504 package는 target post `28`, rerun post `24`, rerun row `86`, browser target `28`, browser visual required `11`을 기록한다.
- [x] small targeted rerun 권장 병렬도는 `min(input_post_count,36)=24`다. 36 worker를 맞추기 위한 재실행은 하지 않는다.
- [x] `_effective_parallel_for_post_count()`는 `36`을 고정 worker 수가 아니라 상한으로 취급한다.
- [x] stale `MCP_SHARD_COUNT=36`이 남아 있어도 10개 미만 small run의 health required/batch budget은 입력 수 기준으로 제한된다.
- [x] v504 tool/test 파일은 `.gitignore` 예외에 포함되어 추적 가능하다.
- [x] `README.md`/`expert_readme.md`의 runtime 병렬 섹션은 Codex `spawn_agent` 병렬과 분리됐다고 안내한다.
- [x] Codex in-app Browser 연결 초기화 실패로 이번 visual artifact는 Missing/blocked로 유지한다.
- [x] OCR/search/text-only 근거는 browser image-loading evidence 없이 Strong/GO로 승격하지 않는다.
- [x] `tests.test_goal_next_seed_package`, `tests.test_expert_main_input_loader`, 관련 `py_compile`, v504 manifest JSON validation OK.
- [ ] v504 rerun/runtime audit/semantic coverage/reason hygiene/browser visual artifact 확보 전까지 10만 semantic approval은 열지 않는다.

## 2026-06-01 v503 Codex subagent 병렬 통합 체크

- [x] 이번 라운드의 병렬 검토는 Codex `spawn_agent` subagent로 수행했고, `expert_main.py --parallel` worker 증설로 대체하지 않았다.
- [x] 원본 partial source는 approval source가 아니라 regression seed로 유지한다.
- [x] JSONL 입력 loader는 image content block의 `url`, `image_url`, `src`를 모두 VLM/OCR image gate용 URL로 보존한다.
- [x] public review artifact의 `content_blocks`/`image_urls`도 `image_url`/`src` alias를 보존한다.
- [x] known abbreviation title guard rewrite는 no-work/context-only 공통 gate를 통과해야 한다.
- [x] 소규모 새 명령 템플릿은 `--parallel min(input_count,36)`를 권장하되, 이미 완료된 p36 run은 `effective_parallel`과 lifecycle/evidence 계약이 맞으면 재실행하지 않는다.
- [x] 추가 Codex `spawn_agent` 재확인에서 GO 과승격 없음, reason/comment/search-only blocker 유지, docs/code wording P2 cleanup 필요를 확인했다.
- [x] 과거 이력의 future-facing `--parallel 36` 문구와 "하드코딩/고정" 주석 표현을 한국어/evidence-gated 계약으로 정리했다.
- [x] focused image loader/comment metadata 41건, known abbreviation 16건, 관련 `py_compile` OK.
- [x] 관련 확장 회귀 묶음 167건, broader `py_compile`, `git diff --check` OK. `git diff --check` 출력은 CRLF 경고뿐이다.
- [ ] completed VLM/OCR-on source 기반 high-risk expansion 전까지 10만 semantic approval은 열지 않는다.

## 2026-06-01 v502 P2 late rescue 후보 공통 gate 체크

- [x] `direct_full_title_candidate_rescued`는 `_can_promote_title_after_semantic_no_work()`를 통과해야 한다.
- [x] `post_main_official_url_title_recovered_from_null`은 공식 URL 단독으로 no-work/context-only를 열 수 없다.
- [x] `direct_image_explicit_title_rescued`는 VLM/OCR 직접 작품 표면 positive path라도 공통 gate를 통과한다.
- [x] `batch_memory_exact_alias_rescued`는 BatchContext/known alias 후보 반환 전에 공통 gate를 통과해야 한다.
- [x] focused 23건, VLM counter 포함 24건, 확장 회귀 125건, 관련 파일 `py_compile` OK.
- [ ] completed VLM/OCR-on source 기반 high-risk expansion 전까지 10만 semantic approval은 열지 않는다.

## 2026-06-01 v501 late rescue 추가 P1 / image loading text-match gate 체크

- [x] Codex `spawn_agent` subagent 추가 보고를 메인 Codex가 통합했고, repo runtime worker 병렬과 섞지 않았다.
- [x] `short_alias_spoiler_recovered`는 no-work/context-only 상태에서 strict packet-local anchor 없이는 title을 되살릴 수 없다.
- [x] `multi_work_placeholder_collapsed` 두 경로는 `_can_promote_title_after_semantic_no_work()`를 통과해야 한다.
- [x] final consistency canonical rescue lock은 `canonical_relevance_lock_rescued` gate를 통과해야 한다.
- [x] 이미지 로딩 실패/대기 상태에서 resolved/OCR/search 텍스트 매칭이 쓰이면 `image_loading_failed_or_pending_text_match_used` issue로 드러난다.
- [x] focused 23건, semantic coverage audit 27건, 확장 회귀 125건, 관련 파일 `py_compile` OK.
- [ ] completed VLM/OCR-on source 기반 high-risk expansion 전까지 10만 semantic approval은 열지 않는다.

## 2026-06-01 v500 Codex subagent 병렬 / structural-comment rescue gate 체크

- [x] 이번 라운드도 Codex `/goal` 병렬을 `expert_main.py --parallel` worker 수가 아니라 `spawn_agent` 전문가 축으로 수행했다.
- [x] code gate, goal/runtime docs, VLM/OCR/browser gate subagent를 독립 읽기 전용 축으로 배정했다.
- [x] structural title rescue는 no-work/context-only 상태에서 strict packet-local anchor 없이는 title을 되살릴 수 없다.
- [x] comment title answer, comment plot answer, character parenthetical, character page title rescue는 `_can_promote_title_after_semantic_no_work()`를 통과해야 한다.
- [x] session knowledge는 context-only/no-work 결과를 alias knowledge로 학습하지 않는다.
- [x] focused 회귀 `tests.test_title_lead_search_inferred_guard` 23건 OK.
- [x] 관련 확장 회귀 묶음 125건과 관련 파일 `py_compile` OK.
- [ ] hard direct anchor helper와 contextual support helper 분리 P2를 후속 처리한다.
- [ ] completed VLM/OCR-on source 기반 high-risk expansion 전까지 10만 semantic approval은 열지 않는다.

## 2026-06-01 v499 subagent 병렬 재점검 / late promotion gate 확장 체크

- [x] Codex `/goal` 작업의 병렬 검토를 repo worker 수가 아니라 `spawn_agent` 전문가 축으로 수행했다.
- [x] subagent 보고를 메인 Codex가 통합했고, 각 보고를 runtime/result, code-path, docs/checklist 근거로 분리했다.
- [x] ARBITER `final_decision`만 남은 `title_resolution_allowed=false` / `title_resolution_state=context_only`도 semantic no-work signal로 읽는다.
- [x] canonical stable-hold는 strict packet-local anchor 없이 no-work/context-only block을 다시 열 수 없다.
- [x] question-title official URL, locked official candidate, title-surface primary, short-support anticipation, generic-relation alias, comment URL answer recovery는 `_can_promote_title_after_semantic_no_work()` gate를 통과해야 한다.
- [x] session knowledge는 no-work/context-only + direct anchor 없음 결과를 `resolved_slang`/pending knowledge로 학습하지 않는다.
- [x] official detail URL/search title/snippet/canonical convergence/episode ref 단독은 no-work 해제용 direct hard anchor가 아니라고 문서 표현을 맞춘다.
- [x] focused 회귀 `tests.test_title_lead_search_inferred_guard` 22건 OK.
- [x] 관련 확장 회귀 묶음 124건과 관련 파일 `py_compile` OK.
- [ ] completed VLM/OCR-on source 기반 high-risk expansion 전까지 10만 semantic approval은 열지 않는다.

## 2026-06-01 v497 no-work/context-only 공통 후단 승격 게이트 체크

- [x] Codex subagent 코드 경로 reviewer가 v496 이후 남은 최종 검증기/후보 승격/단일 후보 승격/output override 위험을 확인했다.
- [x] no-work/context-only 이후 후단 title 승격/rescue는 `_can_promote_title_after_semantic_no_work()` 공통 gate를 통과해야 한다.
- [x] strict direct anchor는 raw post title/body/comment 직접 작품 표면, VLM/OCR 직접 작품 표면, image primary work anchor, verified character-work link, compound title-character bridge로 제한했다.
- [x] official detail URL, search evidence, canonical convergence, Decoder alias, episode ref 단독은 no-work/context-only 해제 앵커가 아니다.
- [x] `_compute_title_acceptance()`에서 no-work/context-only + direct anchor 없음이면 `semantic_no_work_block=true`, `decision=reject`를 반환한다.
- [x] candidate promotion과 single-candidate unresolved promotion이 Decoder alias + official URL만으로 title을 되살리지 않는 회귀를 추가했다.
- [x] `11718082`류 direct image work anchor는 공통 후단 승격 게이트를 통과한다.
- [ ] v497 targeted 통과를 10만 semantic approval로 승격하지 않는다. expanded high-risk bucket에서 후단 canonical/deliberation rescue 재발률을 따로 확인한다.

## 2026-06-01 v496 no-work/context-only late rescue gate 체크

- [x] `11718080`류 no-work/context-only 이후 후단 search/alias/BatchContext rescue가 official URL만으로 resolved를 되살릴 수 있는 경로를 확인했다.
- [x] `_search_inferred_alias_nonwork_block_reason()`에서 official evidence를 no-work 해제용 direct anchor로 보지 않고, direct post/visual work anchor helper만 사용하도록 조정했다.
- [x] `verification_result.title_resolution_state=context_only` 또는 `title_resolution_allowed=false`만 남은 packet형 no-work도 block reason으로 읽도록 보강했다.
- [x] official detail URL이 있어도 direct hard anchor가 없으면 `search_evidence_alias_inference`/batch alias rescue가 `semantic_seed_no_work_context`로 차단되는 회귀를 추가했다.
- [x] `11718082`류 direct image work anchor는 no-work seed가 있어도 positive rescue가 유지되는지 확인했다.
- [ ] 이 targeted gate 통과를 10만 semantic approval로 승격하지 않는다. `context_only_late_rescue_without_direct_anchor` bucket 확장 검토가 필요하다.

## 2026-06-01 v495 Codex goal subagent 병렬 운영 재정렬 체크

- [x] 사용자 정정을 `expert_main.py --parallel`이 아니라 Codex `/goal`의 `spawn_agent` 전문가 병렬 운영 지침으로 해석했다.
- [x] 이번 라운드에서 문서 위치 점검, VLM/browser coverage 확인, 운영 모델 정리를 별도 subagent로 병렬 검토했다.
- [x] `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`를 canonical로 두고, goal에서 "여러 전문가/병렬 검토"가 나오면 먼저 `spawn_agent` 축을 선언하고 실제 subagent를 배정하도록 강화했다.
- [x] `docs/devs/SAMPLING_AND_PARALLEL_TEST_GUIDE.md`는 `expert_main.py` runtime worker/shard 병렬도 전용 문서로 유지하고, subagent 부족을 worker 재실행으로 해결하지 않는다고 명시했다.
- [x] 과거 `--parallel 36`/36워커 기록은 runtime 이력으로만 해석하며 Codex goal subagent 병렬 지침으로 읽지 않는 해석 가드를 추가했다.
- [x] v494 Browser visual coverage `GO`는 targeted coverage sanity이며 10만 semantic approval이 아님을 다시 분리했다.
- [ ] 다음 대형 goal 시작 시 `spawn_agent_axes`와 subagent별 read/write scope를 먼저 보고서에 남긴다.

## 2026-06-01 v494 Browser visual artifact 체크

- [x] `11718082` 원문 페이지의 본문 이미지가 실제 로드된 screenshot을 확보했다.
- [x] screenshot/snapshot/browser manifest를 `qualitative_review/20260528_141006_620986/browser_visual_v494/`에 저장했다.
- [x] manifest에 `attempted_in_app_browser=true`와 fallback reason을 기록했다.
- [x] `visual_evidence_grade=Strong`, `article_image_count=1`, `article_loaded_count=1`, pending/broken/incomplete counter 0을 남겼다.
- [x] v494 semantic coverage audit에서 `browser_visual_available=1`, `browser_visual_missing=0`, issues `[]`를 확인했다.
- [x] v494 coverage `GO`를 10만 semantic approval로 승격하지 않는다.
- [ ] `node_repl` 기반 in-app Browser bootstrap 실패는 별도 환경 이슈로 추적한다.

## 2026-06-01 v493 VLM/OCR public counter 체크

- [x] `PickvelIdentity` public schema에 VLM/OCR execution counter를 추가했다.
- [x] `_context_to_output()`에서 `ctx.post_data`의 VLM/OCR counter를 `analysis_result.identity`로 보존한다.
- [x] 비이미지 row에는 0 counter noise를 공개하지 않는다.
- [x] v493 live canary에서 `11718082` identity에 `image_fetch_count=1`, `image_fetch_success=1`, `vlm_chunks_sent=1`, `vlm_total_bytes=28264`가 남았다.
- [x] v493 semantic coverage audit에서 VLM counter 관련 `REVIEW-LOCKED` issue가 사라졌다.
- [x] v493 runtime audit은 `GO`, issues `[]`다.
- [x] 관련 unittest 60건과 `py_compile`을 통과했다.
- [x] Browser visual/direct evidence artifact linkage가 아직 없어 semantic coverage는 `REVIEW-LOCKED` 유지다. v494에서 targeted artifact 연결으로 해소했다.
- [ ] 10만 semantic approval로 승격하지 않는다.

## 2026-06-01 v492 Subagent 통합 / VLM public evidence 계약 체크

- [x] 이번 goal 라운드에서 Codex `spawn_agent` subagent 병렬과 repo runtime `expert_main.py --parallel` worker 병렬을 분리해 운용했다.
- [x] subagent별 `role`, `scope`, `write_scope`, `gate_effect`, `main_codex_action`을 `qualitative_review/20260528_141006_620986/v492_subagent_review_manifest.json`에 남겼다.
- [x] 사람이 읽는 통합 요약은 한국어로 작성하고, JSON key/enum/파일명/명령어/코드 심볼만 원문을 유지했다.
- [x] 이미지 row에서 `image_evidence_catalog`만 있고 VLM/OCR fetch/chunk counter가 없으면 `REVIEW-LOCKED`로 잡는다.
- [x] reason/public text가 이미지 OCR을 언급하지만 공개 VLM/OCR counter가 없으면 `REVIEW-LOCKED`로 잡는다.
- [x] 브라우저 image loading counter와 screenshot/snapshot/direct visual review linkage를 분리해 audit한다.
- [x] small goal/test runtime audit는 `llm_endpoint`, `mcp_health_ok_count`, `mcp_health_failure_count`까지 확인한다.
- [x] v492 runtime audit에서 v491 manifest는 `runtime_contract=GO`, semantic coverage audit은 `REVIEW-LOCKED`로 분리됐다.
- [x] subagent 제안 gate를 메인 Codex가 원본 파일/line/post_id/run_id로 재확인하기 전에는 최종 gate에 반영하지 않는다.
- [ ] 10만 건 approval에는 initial triage 표본 수가 아니라 random 1000+, P0/P1 bucket 200~500, Browser visual/image-loading gate를 요구한다.

## 2026-06-01 v491 Goal runtime health manifest contract 체크

- [x] Codex goal 병렬 검토는 `spawn_agent` 전문가 병렬이며 repo runtime `expert_main.py --parallel` worker 수와 분리했다.
- [x] v490 live canary에서 light-health는 로그에 있었지만 manifest/run_meta에 `mcp_health_*`가 없던 증거 공백을 확인했다.
- [x] `expert_main.py` 최종 manifest와 row `run_meta`에 `llm_endpoint` 및 `mcp_health_*` 필드를 남긴다.
- [x] `audit_goal_test_run_contract.py`는 small goal/test run에서 health manifest field missing을 `REVIEW`로 잡는다.
- [x] v491 live canary는 2건 입력 기준 `--parallel 2`로 실행했고 `requested_parallel=2`, `effective_parallel=2`를 확인했다.
- [x] v491 manifest에서 `mcp_health_include_search=false`, `mcp_health_light_mode=true`, `mcp_health_required_ok_count=2`, `mcp_health_checked_endpoint_count=2`, `mcp_health_probe_batch_size=2`, `mcp_health_workers=2`를 확인했다.
- [x] v491 post-run audit에서 `runtime_contract=GO`, issues `[]`를 확인했다.
- [x] `11718082`는 VLM/OCR 미실행이 아니라 과거 public result 구조 증거 부족 문제로 분리했다.
- [x] `11718080`은 작품 resolved 대상이 아니라 장르/사회적 한탄으로 `official_title=null`, `title_resolution_allowed=false`가 맞음을 재확인했다.
- [ ] Browser visual artifact와 row-level VLM chunk/fetch counters는 후속 result/manifest 조인 개선 대상으로 유지한다.
- [ ] runtime `GO`와 targeted canary `GO`를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v489 Goal runtime health audit 체크

- [x] `audit_goal_test_run_contract.py`가 v488 `mcp_health_*` manifest 필드를 관측값으로 읽는다.
- [x] small goal/test run에서 `mcp_health_include_search=true`이면 runtime contract를 `REVIEW`로 낮춘다.
- [x] small goal/test run에서 `mcp_health_light_mode=false`이면 v488 light-health 계약 미적용으로 `REVIEW` 처리한다.
- [x] checked/requested/after-filter/required-ok health count 모순은 `NO-GO`로 잡는다.
- [x] 감사 markdown에 health include/search, light mode, required ok, checked endpoint count, probe batch, early-stop 여부가 출력된다.
- [x] `tests.test_goal_test_run_contract_audit` 15건과 관련 `py_compile`을 통과했다.
- [ ] 다음 live small run 후 이 감사 도구로 실제 manifest/log를 확인한다.
- [ ] v489 audit 보정을 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v488 Codex subagent 병렬 / light health 체크

- [x] Codex goal 병렬은 `spawn_agent` 전문가 감사로 수행하고, repo runtime `expert_main.py --parallel`과 섞지 않는다.
- [x] runtime/shard, VLM/OCR/browser, semantic/prompt/orchestration, docs/checklist 축을 병렬 검토했다.
- [x] 메인 Codex가 subagent 결론을 그대로 승인하지 않고 파일/line/post_id/run_id/manifest 근거를 재확인했다.
- [x] small goal/reuse-only run은 `MCP_HEALTH_INCLUDE_SEARCH` 기본값을 false로 두어 Bridge `/readyz` 중심 health를 사용한다.
- [x] stale explicit `MCP_ENDPOINTS`가 길어도 필요한 healthy endpoint 수를 확보하면 남은 probe를 생략한다.
- [x] manifest/run config에 health include/search, required ok, checked endpoint count, probe batch, early stop 여부를 기록한다.
- [x] `tests.test_expert_main_input_loader` 33건과 관련 `py_compile`을 통과했다.
- [ ] 다음 live small run에서 `include_search=False`와 `mcp_health_checked_endpoint_count<=mcp_health_required_ok_count`를 확인한다.
- [ ] v488 runtime 보정을 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 Codex goal 전문 subagent 병렬 검토 체크

- [ ] 10만 건/대량 품질검토에서는 메인 에이전트가 통합/결정권을 갖고 `runtime/shard`, `VLM/OCR/browser`, `semantic/prompt`, `docs/checklist/gate` 전문 subagent를 병렬로 배정했는지 확인한다.
- [ ] 메인 에이전트가 subagent 보고의 파일 경로, line, `post_id`, `run_id`, manifest/checkpoint/review packet 근거를 직접 재확인한 뒤에만 `GO/REVIEW/NO-GO` gate에 반영한다.
- [ ] random baseline과 high-risk oversample은 표본 수, 오류율, HOLD/REPROCESS/REJECT 집계를 분리 보고한다.
- [ ] 브라우저/VLM 사례는 이미지 로딩 상태와 직접 시각 증거를 별도 gate로 확인하고, 텍스트/OCR 문자열만으로 `Strong` 또는 semantic `GO`를 열지 않는다.

## 2026-06-01 v487 Semantic stability hard-support 체크

- [x] Codex goal 내부 subagent 병렬 검토를 repo runtime `--parallel 36` 실행과 분리해서 진행했다.
- [x] `11718080`류 의미판정 문제를 search/alias/BatchContext rescue가 no-work를 뒤집는 오케스트레이션 문제로 기록했다.
- [x] `11718082`류 VLM/OCR 문제를 “원본 미실행”이 아니라 “일부 재런/패킷의 이미지 catalog/chunk 증거 누락”으로 분리했다.
- [x] raw `abbrev_stable`과 hard support를 분리하는 helper가 있다.
- [x] J1 Verifier veto actual path는 비공식 검색 alias stability만으로 `is_relevant=True`를 유지하지 않는다.
- [x] canonical rescue strength는 soft alias stability만으로 `strong=True`가 되지 않는다.
- [x] J0.6 final rescue/candidate promotion/final rejection profile은 soft alias stability 단독을 강한 작품 근거로 쓰지 않는다.
- [x] focused 관련 unittest 48건과 관련 `py_compile`을 통과했다.
- [ ] 이미지 입력이 있는 packet은 `image_count`, `image_urls`, `image_evidence_catalog`, VLM chunk, browser visual load 상태가 없으면 `ACCEPT`하지 않는다.
- [ ] small goal/test run은 worker max 36보다 endpoint health/search readiness 비용을 먼저 줄인다.
- [ ] v487 targeted hard-support 보정을 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v486 Arbiter veto actual / packet label closure 체크

- [x] Codex `spawn_agent` 전문가 3개 축으로 Arbiter title veto actual 공백, stability 후단 보조 위험, hardcoded alias packet label 후속 상태를 병렬 검토했다.
- [x] Verifier `is_relevant=false` actual branch에서 약칭 표면만 있고 hard support가 없으면 `official_title=null` / `_verifier_veto_exempt=false`가 유지된다.
- [x] Verifier `is_relevant=false` actual branch에서 post-title abbreviation + official/detail hard support가 있으면 `_verifier_veto_exempt=true`와 resolved title이 유지된다.
- [x] v465 closure labels를 사용한 v486 action queue에서 `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_packet_closed_by_labels=true`, `hardcoded_alias_packet_label_gate=GO`를 확인했다.
- [x] packet label gate가 GO이면 `hardcoded_alias_packet_label_followup`은 `closed_by_packet_labels` / `executable_now=false`로 표시된다.
- [x] focused unittest 22건과 관련 `py_compile`을 통과했다.
- [ ] stability boolean이 J1 override, structural rescue, canonical rescue에서 hard support 없이 High/lock 보조가 되지 않는지 후속 actual path 회귀를 추가한다.
- [ ] v486 targeted 회귀/queue 정리를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v485 Agentic alias metadata/rewrite guard 체크

- [x] Codex `spawn_agent` 전문가 3개 축으로 serialization, 후단 rewrite, stability/lock risk를 병렬 검토했다.
- [x] `registry_anchor_only` / `confidence_demoted_without_hard_evidence`가 최종 `alias_resolution_sources`로 직렬화된다.
- [x] registry-only reason은 `Strong` 근거로 쓰지 않고 `Medium/HOLD` 경계를 명시한다.
- [x] J11 title drift는 curated alias lock + 같은 promotion title이면 registry-only provenance를 지우지 않는다.
- [x] `_apply_known_abbreviation_title_guard()`는 hardcoded registry source에 official/detail/direct hard support 없이는 title rewrite하지 않는다.
- [x] title-lead search inferred 후보는 비공식 search/wiki/community support만으로 `High`가 되지 않는다.
- [x] round2 qualitative label은 `registry_anchor_only` weak resolved packet을 `HOLD/re_judge`로 보낸다.
- [x] LLM judgment review packet도 `alias_resolution_sources`를 보존한다.
- [x] v485 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [x] focused 관련 unittest 78건과 관련 `py_compile`을 통과했다.
- [x] Arbiter title veto actual branch는 v486에서 후속 회귀 테스트를 추가했다.
- [ ] stability signal이 `High` 보조로 쓰이는 잔여 경로는 official/detail/direct hard support 기준으로 계속 검토한다.
- [ ] v485 targeted metadata/rewrite guard를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v484 Agentic known alias promotion confidence gate 체크

- [x] Codex `spawn_agent` 전문가 3개 축으로 Agentic direct promotion, docs/gate, runtime/subagent 분리를 병렬 검토했다.
- [x] `_try_promote_best_candidate()`는 registry hit + work anchor만으로 `confidence=High`를 반환하지 않는다.
- [x] registry + work anchor만 있는 positive는 `confidence=Medium`, `evidence=registry_anchor_only`로 남긴다.
- [x] official/detail/direct hard support가 있으면 registry promotion `High`를 유지한다.
- [x] no-work/bare alias/comment-only/substring negative는 기존처럼 차단한다.
- [x] v484 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [x] focused 관련 unittest 59건과 관련 `py_compile`을 통과했다.
- [x] `_apply_known_abbreviation_title_guard()` 후단 final title rewrite는 v485에서 registry soft-support 차단으로 1차 고정했다.
- [ ] `_has_title_abbrev_stability_signal()` 증폭 경로와 Arbiter title veto actual branch는 후속으로 남긴다.
- [ ] v484 targeted confidence gate를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v483 Arbiter alias-only actual decision-path 체크

- [x] Codex `spawn_agent` 전문가 2개 축으로 Arbiter actual branch seam과 남은 hardcoded alias 우선순위를 병렬 검토했다.
- [x] `multi_work` 비교/나열 문맥에서 alias-only 단일 title 강제승격이 `official_title=null`로 내려가는지 actual `analyze()`로 확인했다.
- [x] work anchor가 있는 등록 약칭은 `multi_work` guard에서 title을 보존하는 positive control로 확인했다.
- [x] `meme/noise` guard는 abbreviation-only anchor + official search support만으로 면제되지 않는다.
- [x] `low-confidence` guard는 abbreviation-only anchor + official search support만으로 면제되지 않는다.
- [x] v483 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [ ] Arbiter title veto actual branch는 후속 회귀 테스트가 필요하다.
- [x] Agentic `_try_promote_best_candidate()`의 `KNOWN_* -> High` direct rescue는 v484에서 confidence/evidence tier 계약으로 낮췄다.
- [ ] v483 actual branch 보정을 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v482 Arbiter strong/official support 계약 체크

- [x] Codex goal 병렬 subagent 감사에서 Arbiter `strong support`와 `official evidence` 계약 분리 필요성을 재확인했다.
- [x] `_has_strong_title_support()`는 source quality 반환 구조까지 정상 도달한다.
- [x] active official detail/search hit는 strong/official support positive로 확인했다.
- [x] deleted/unavailable, community post, listing page는 strong/official support negative로 확인했다.
- [x] `known_abbreviation` hint 단독은 strong support도 official evidence도 아니다.
- [x] 짧은 제목 substring-only official evidence 오탐을 token boundary 테스트로 막았다.
- [x] v482 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [ ] Arbiter actual decision-path 테스트는 아직 helper-only 테스트보다 약하다.
- [ ] `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS` positive registry blocker는 계속 남아 있다.
- [ ] v482 targeted helper 계약 보정을 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v481 Arbiter 등록 약칭 guard exception 앵커 체크

- [x] Codex goal 병렬 subagent 감사에서 Arbiter `multi_work`, `meme/noise`, `low-confidence`, title veto registry-only 예외를 재확인했다.
- [x] Arbiter guard exception은 등록 약칭 surface만으로 열리지 않고 `_has_curated_alias_guard_exception()`을 요구한다.
- [x] bare alias/no-work/comment-only alias는 guard exception을 열지 않는다.
- [x] work-context 등록 약칭 positive는 유지한다.
- [x] v481 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [ ] Arbiter actual decision-path 테스트는 아직 helper-only 테스트보다 약하다.
- [ ] `_has_strong_title_support()` / `_has_official_title_evidence()` 반환 구조 의심은 별도 P1로 남긴다.
- [ ] v481 targeted guard를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v480 Agentic 등록 약칭 alias support 앵커 체크

- [x] Codex goal 병렬 subagent 감사에서 나온 Agentic support helper P1을 메인 스레드에서 후속 처리했다.
- [x] `_has_alias_title_support()`는 등록 약칭 surface만으로 `True`를 반환하지 않는다.
- [x] 등록 약칭 support에는 post-side work anchor 또는 compound title-character bridge가 필요하다.
- [x] `_collect_title_support_kinds()`는 alias surface만으로 `post_main_mention`을 추가하지 않는다.
- [x] `담텔기` work-context positive는 `known_abbreviation_alias + curated_alias_work_anchor`로 유지한다.
- [x] bare alias/context-only negative는 alias support, support kinds, explicit support가 모두 실패한다.
- [ ] Arbiter multi_work/meme/low-confidence guard exception은 아직 registry-only 후속 blocker다.
- [ ] v480 targeted support guard를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v479 Agentic 등록 약칭 promotion/stability/lock 앵커 체크

- [x] Codex goal 병렬은 `spawn_agent` 전문가 감사로 수행하고, repo runtime `expert_main.py --parallel`과 섞지 않는다.
- [x] Agentic 등록 약칭 direct promotion은 post-side work anchor 또는 compound title-character bridge 없이는 열리지 않는다.
- [x] visible known alias만으로 abbreviation stability signal을 `True`로 반환하지 않는다.
- [x] comment-only known title abbreviation은 title lock 근거가 아니다.
- [x] bare alias/context-only negative는 promotion/stability/lock이 모두 막힌다.
- [x] `담텔기`처럼 work discussion, 회차/스포/작가의 말/캐릭터 맥락이 있는 positive는 유지한다.
- [x] v479 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [ ] Arbiter registry-only guard exception 경로는 아직 남아 있다.
- [ ] v479 targeted guard를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v478 Decoder 등록 약칭 suspected/best_match 예외 체크

- [x] Codex goal 병렬은 `spawn_agent` 전문가 검토로 수행했고, `expert_main.py --parallel` 조정과 섞지 않았다.
- [x] Decoder subagent가 지적한 `_resolved_mappings`, high-fit interpretation, weak thematic guard registry-only 경로를 반영했다.
- [x] `_init_suspected_titles`는 `known_match` 단독으로 `confidence=0.92` suspected title을 만들지 않는다.
- [x] high-fit `novel_title` interpretation은 registry pair만으로 낮은 약칭 정합성 차단을 우회하지 않는다.
- [x] weak thematic guard는 `KNOWN_ABBREVIATIONS` pair 자체를 `explicit_alias_support`로 보지 않는다.
- [x] focused unittest 9건과 관련 `py_compile`을 통과했다.
- [x] v478 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [ ] Agentic direct `High`, stability/lock, Arbiter guard exception 경로는 아직 남아 있다.
- [ ] v478 targeted guard를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v477 Decoder KNOWN_ABBREVIATIONS 미검증 rescue 체크

- [x] Codex goal 병렬은 `spawn_agent` 전문가 검토로 수행했고, `expert_main.py --parallel` 조정과 섞지 않았다.
- [x] Decoder subagent 감사에서 `_rescue_null_title`의 `known_abbreviation_unverified` 0.80 rescue 경로를 확인했다.
- [x] Agentic/Arbiter subagent 감사에서 direct `High`, stability/lock, guard exception 잔여 blocker를 분리했다.
- [x] `KNOWN_ABBREVIATIONS` hit는 검색/공식 제목 근거 없이 `best_title/best_score`를 세우지 않는다.
- [x] 등록 약칭이어도 독립 근거가 없으면 LLM의 `비제목/비작품` 판단을 뒤집지 않는다.
- [x] 트로프 체크 우회도 `등록 약칭 + 독립 근거 있음`일 때만 허용한다.
- [x] `tests.test_decoder_known_abbreviation_guard`를 추가해 미검증 hint-only, LLM 비제목 존중, 검색 근거 positive rescue를 함께 확인했다.
- [x] focused unittest 29건과 관련 `py_compile`을 통과했다.
- [x] v477 audit/action queue를 생성했고 `hardcoded_alias_gate=REVIEW`, positive blocker `2`, semantic approval `REVIEW-LOCKED`를 확인했다.
- [ ] `_init_suspected_titles`, high-fit interpretation, weak thematic guard의 registry-only suspected/best_match/예외 경로를 계속 줄인다.
- [ ] Agentic `_try_promote_best_candidate`, `_has_title_abbrev_stability_signal`, `_known_title_abbreviation_context_locks_title`에 독립 work anchor 조건을 적용한다.
- [ ] Arbiter multi_work/meme/low-confidence guard exception이 registry-only로 열리지 않게 한다.
- [ ] v477 targeted guard를 10만 semantic approval로 오독하지 않는다.

## 2026-06-01 v476 KNOWN_* prompt pressure / audit noise 체크

- [x] Codex goal 병렬은 `spawn_agent` 전문가 검토로 수행했고, `expert_main.py --parallel` 조정과 섞지 않았다.
- [x] `EvidenceScorer`의 registered alias 신호는 강한 확정 근거가 아니라 recall hint다.
- [x] no-work 또는 독립 work anchor 부재 문맥에서는 등록 약칭 signal/prompt note를 만들지 않는다.
- [x] Jury/Debate prompt는 `KNOWN_ABBREVIATIONS 매칭 = 확정`으로 쓰지 않고, `등록 약칭 후보(검토용 힌트)`로만 쓴다.
- [x] import-only registry usage와 provenance tuple은 audit positive blocker가 아니다.
- [x] v476 audit/action queue를 생성했고, `hardcoded_alias_positive_blocker_count=2` 유지와 `semantic_approval=REVIEW-LOCKED`를 확인했다.
- [x] focused unittest 22건과 관련 `py_compile`을 통과했다.
- [ ] `Decoder._rescue_null_title`, `_try_promote_best_candidate`, Arbiter guard exception 경로는 아직 blocker다.
- [ ] prompt pressure 감소를 hardcoded alias risk 전체 closure로 오독하지 않는다.
- [ ] completed source와 expanded qualitative review 전까지 10만 semantic approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v474 SLANG_DICTIONARY hint-only 체크

- [x] Codex goal 병렬은 `spawn_agent` 전문가 검토로 수행했고, `expert_main.py --parallel` 조정과 섞지 않았다.
- [x] `SLANG_DICTIONARY` hit는 `official_title`, `resolved_title`, `best_match.title`, `confidence=High`를 단독 생성하지 않는다.
- [x] Decoder는 dictionary match를 `slang_dictionary_hint` candidate로만 보존한다.
- [x] LLM 출력이 dictionary mapped title을 high로 올려도 독립 URL/플랫폼/비사전 evidence가 없으면 후처리에서 null 처리한다.
- [x] prompt는 dictionary를 recall hint로만 설명하고, 단독 확정 근거로 쓰지 말라고 명시한다.
- [x] hardcoded alias risk audit는 SLANG provenance tuple과 tooling metadata usage를 positive blocker로 세지 않는다.
- [x] v474 audit에서 `SLANG_DICTIONARY=INFO`, `positive_usage_count=0`, positive blocker 2개를 확인했다.
- [x] v474 action queue에서 `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_positive_blocker_count=2`를 확인했다.
- [x] focused unittest 23건과 관련 `py_compile`을 통과했다.
- [ ] `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`는 계속 registry risk blocker다.
- [ ] SLANG_DICTIONARY blocker 해소를 hardcoded alias 전체 승인이나 10만 semantic approval로 오독하지 않는다.
- [ ] completed source와 expanded qualitative review 전까지 10만 semantic approval은 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v470 hardcoded alias audit/tooling marker 체크

- [x] Codex goal 병렬은 `spawn_agent` 전문가 검토로 수행했고, `expert_main.py --parallel` 조정과 섞지 않았다.
- [x] `TITLE_ALIAS_SUPPORT_MARKERS`와 `OFFICIAL_OR_PLATFORM_SUPPORT_MARKERS`는 coverage/audit 도구 marker이며 runtime positive alias registry가 아님을 확인했다.
- [x] audit 도구에서 `tools/` 아래 `*_MARKERS` tuple은 `tooling_marker/INFO`로 분리한다.
- [x] `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY`는 여전히 `positive_resolution/REVIEW` blocker다.
- [x] hardcoded alias packet review는 raw artifact 중복 count와 unique post-context registry match count를 함께 보고한다.
- [x] action queue closure는 raw duplicate packet 수가 아니라 `unique_post_context_registry_match_count`를 우선 기준으로 삼는다.
- [x] v470 queue에서 `hardcoded_alias_packet_effective_gate=GO`, `hardcoded_alias_packet_closed_by_labels=True`, `hardcoded_alias_packet_unique_post_context_matches=1`을 확인했다.
- [x] focused unittest 22건과 관련 `py_compile`을 통과했다.
- [ ] packet effective GO를 hardcoded alias registry 전체 GO로 오독하지 않는다.
- [ ] no-work/context-only 이후 후단 search/alias/BatchContext rescue 재승격은 P0 구조 리스크로 계속 추적한다.
- [ ] 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v467 hardcoded alias packet review reconciliation 체크

- [x] v407 packet review raw gate가 `REVIEW`인 이유는 matched packet을 라벨링하라는 요구였음을 확인했다.
- [x] v465 closure labels가 v407 matched packet 11건 이상을 모두 `ACCEPT`로 닫는지 확인했다.
- [x] v450 latest canary의 공개 provenance field가 `source_registry`, `alias_resolution_source`, `matched_surface_kind`를 포함하는지 확인했다.
- [x] v467 action queue에서 `hardcoded_alias_packet_review_required`가 `closed_by_packet_labels`로 내려갔다.
- [x] v467 action queue에서 `hardcoded_alias_packet_review_required`는 더 이상 approval blocker가 아니다.
- [ ] `hardcoded_alias_risk_review_required`는 계속 approval blocker다.
- [ ] packet effective GO를 hardcoded alias registry 전체 GO로 오독하지 않는다.

## 2026-06-01 v465/v466 hardcoded alias packet label follow-up 체크

- [x] v409 historical packet labels의 HOLD/REJECT 원인을 weak evidence, missing provenance, over-demotion, wrong canonical, generic bridge로 재분류했다.
- [x] v450 최신 canary에서 `담텔기 -> 괴담 호텔 탈출기` provenance가 `KNOWN_TITLE_ABBREVIATIONS` / `known_title_abbreviation` / `post_title`로 공개되는지 확인했다.
- [x] v450 final 후보가 `괴담 호텔 탈출기` 1건으로 좁혀지고 wrong canonical/adjacent candidate가 final candidate에 남지 않는지 확인했다.
- [x] v465 label follow-up JSONL 11건은 모두 `ACCEPT`와 `CLOSED_BY_V450_CANARY`로 parse된다.
- [x] v466 action queue에서 `hardcoded_alias_packet_label_gate=GO`로 내려갔다.
- [ ] `hardcoded_alias_gate=REVIEW`와 `hardcoded_alias_packet_gate=REVIEW`는 별도 blocker이므로 아직 hardcoded alias 전체를 닫지 않는다.
- [ ] completed 10만 source, random baseline 1000건, P0/P1 high-risk expansion 전까지 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v461~v464 Browser visual / action queue 체크

- [x] v460 result reason hygiene scan은 hit 0건이다.
- [x] v461 최초 coverage audit에서 `11718082` Browser visual missing이 확인됐다.
- [x] Codex 내장 Browser iab를 먼저 시도했다.
- [x] iab 연결은 node_repl 런타임 종료로 2회 실패했으므로, fallback 사유를 artifact manifest에 기록했다.
- [x] 대체 Playwright MCP full-page screenshot을 저장했다: `qualitative_review\20260528_141006_620986\v461_browser_visual_post11718082_playwright_fullpage.png`.
- [x] metrics에서 `.write_div img[src*="dcimg"]` 본문 이미지 1개가 `complete=true`, `naturalWidth=850`, `naturalHeight=850`으로 로드됨을 확인했다.
- [x] v462 coverage audit에서 v460 small canary 기준 `browser_visual_required/available/missing=1/1/0`, `gate=GO`로 확인됐다.
- [x] v463 current-state map과 v464 action queue를 재생성했다.
- [x] v464에서 `vlm_ocr_browser_visual_gate`는 v460 small canary 기준 approval blocker가 아니다.
- [ ] fallback Playwright MCP 증거는 iab 직접 증거가 아니다. iab가 복구되면 같은 post를 다시 캡처한다.
- [ ] 원본 10만 run은 partial source라 전체 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v459/v460 이미지 OCR anchor/slang 최종 체크

- [x] 이번 follow-up은 Codex `spawn_agent` subagent 병렬 검토로 수행했다. repo 내부 `expert_main.py --parallel` 조정과 분리했다.
- [x] anchor consistency subagent는 v458 `11718082`의 `title_in_post=false`, `image_ocr_variant=true`, `anchor_type=title_exact` 불일치를 지적했다.
- [x] slang/context subagent는 v458 `slang_insight.cultural_context`의 작품 설정/커뮤니티 약칭/OCR 오인 단정 문구를 `HOLD/REVIEW` output hygiene로 지적했다.
- [x] 이미지 OCR 변형만 있고 non-image title 직접 언급이 없으면 final `anchor_type=image`로 정렬한다.
- [x] 같은 경우 `image_ocr_variant_not_title_in_post` consistency flag를 남긴다.
- [x] slang/context는 OCR/표지 표면을 작품 설정, 캐릭터 관계, 커뮤니티 약칭, 지속 alias처럼 말하지 않는다.
- [x] v460 targeted canary에서 `11718082`는 `anchor_type=image`, `anchor_strength=high`, `image_ocr_variant_not_title_in_post`, `slang_insight=null`로 확인됐다.
- [x] v460 targeted canary에서 `11718080`은 `official_title=null`, `work_resolution=none`, `anchor_type=genre`로 확인됐다.
- [x] v460 runtime audit는 `runtime_contract=GO`, `issues=[]`, requested/raw/capped/effective `64/36/2`, VLM/OCR ready를 남겼다.
- [x] `py_compile`과 focused unittest 20건이 통과했다.
- [ ] v460도 새 Browser visual 캡처가 아니다. 이미지 row semantic approval은 Browser visual/loading evidence가 필요하다.
- [ ] v460은 targeted canary다. 10만 semantic approval은 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-06-01 v455~v458 이미지 OCR reason/slang 후속 체크

- [x] Codex subagent 병렬 축으로 runtime, semantic/VLM/slang, docs/gate consistency를 다시 확인했다.
- [x] 이미지 OCR 변형이 있으면 `[근거 요약]`뿐 아니라 reason score board에서도 `title_in_post:+2`를 주지 않는다.
- [x] `slang_insight.cultural_context`는 이미지 OCR 표면을 `게시글/제목에 사용된`, `일반적인 오타 또는 축약`, `공식적인 제목`, `고유 명칭`처럼 지속 alias/원문 직접 title 근거로 말하지 않는다.
- [x] v458 targeted canary에서 `11718082`는 `title_in_post=false`, `image_ocr_variant=true`, `official_search_resolution=true`, `title_in_post:+2` 없음, `store_in_slang_db=false`를 확인했다.
- [x] v458 runtime audit는 `runtime_contract=GO`, `issues=[]`, requested/raw/capped/effective `64/36/2`, VLM/OCR ready를 남겼다.
- [x] v458에서 `11718080`은 `official_title=null`, `work_resolution=none`, `anchor_type=genre`로 유지됐다.
- [ ] v458도 새 Browser visual 캡처가 아니다. 이미지 row semantic approval은 계속 Browser visual/loading evidence가 필요하다.
- [ ] v458은 targeted canary다. 10만 semantic approval은 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-06-01 v454 Codex 전문가 병렬과 런타임 cap 분리

- [x] 이번 라운드는 Codex `spawn_agent` 4개 전문가 축으로 진행했다: runtime/orchestration, semantic/VLM, 100k qualitative gate, docs/checklist.
- [x] `expert_main.py --parallel` 조정으로 Codex subagent 병렬 요청을 대체하지 않는다는 점을 보고/문서에서 분리했다.
- [x] Gemma 4 E4B/4B 계열은 `requested_parallel_raw`가 36을 넘으면 `requested_parallel=36`으로 cap한다.
- [x] small input은 cap 이후에도 `effective_parallel=input_post_count` 또는 healthy endpoint 수까지 낮아지는 것이 정상이다.
- [x] manifest/run_meta에 `requested_parallel_raw`, `model_parallel_max`, `model_parallel_cap_applied`, `model_parallel_cap_model`을 남긴다.
- [x] runtime contract audit가 모델 cap 필드를 읽고 raw/cap/effective 병렬도를 분리 확인한다.
- [x] 이미지 OCR 변형은 `title_in_post=true`로 과장하지 않고 `image_ocr_variant=true`와 `official_search_resolution=true`로 분리한다.
- [x] 이미지 OCR/표지 표면을 slang context에서 `게시글 제목에 사용된 축약어/오타`라고 쓰지 않는다.
- [x] 검증: `py_compile` OK, focused 12건/8건 OK, broad 333건 OK, comment/runtime audit 22건 OK.
- [x] v454 live cap canary에서 `--parallel 64` 요청이 Gemma 4 E4B/4B cap으로 `requested_parallel_raw=64`, `requested_parallel=36`, `effective_parallel=2`가 되는지 확인했다.
- [x] v454 runtime audit는 `runtime_contract=GO`, `issues=[]`, `llm_model=bg-digitalservices/Gemma-4-E4B-it-NVFP4`를 남겼다.
- [x] v454 live semantic spot에서 `11718082`는 이미지 anchor resolved, `11718080`은 `official_title=null` no-work/genre anchor로 유지됐다.
- [x] v454 live result 뒤 추가한 `slang_insight.cultural_context` old wording sanitizer는 v460 live canary에서 runtime output까지 확인했다.
- [ ] v454는 새 Browser visual 캡처가 아니다. 이미지 row semantic approval은 Browser loading counter 또는 packet-level image evidence가 붙을 때까지 `REVIEW-LOCKED`다.

## 2026-06-01 v453 no-work late URL recovery / BatchContext guard

- [x] 이번 라운드는 Codex `spawn_agent` 전문가 병렬로 late-search/raw URL recovery와 BatchContext/slang/known alias rescue를 분리 감사했다.
- [x] `_recover_corrected_title_official_url()`이 semantic no-work + direct post/visual work anchor 부재 상태에서 기존 검색 결과 재사용과 직접 `_search_with_meta()` 호출을 차단하는지 확인했다.
- [x] direct image work anchor가 있는 경우에는 corrected-title URL recovery가 계속 검색/공식 URL 회복을 허용하는 positive control을 추가했다.
- [x] `_has_alias_title_support()`는 decoder alias/gatekeeper title/verifier slang 표면만으로 no-work 판정을 뒤집지 않는다.
- [x] `_learn_batch_context()` wrapper가 `title_resolution_state/title_resolution_allowed/consistency_flags` 등 차단 필드를 BatchContext로 전달한다.
- [x] raw `_search_with_meta()` 직접 호출부가 `_search` 래퍼와 guarded recovery 외로 늘어나면 실패하는 static regression을 추가했다.
- [x] 댓글 author/IP/comment_id/gallery_id coverage 도구와 export 테스트가 현 checkout에 존재하고 통과하는지 확인했다.
- [x] focused 7건, comment metadata coverage 10건, broad regression 332건, 관련 py_compile을 통과했다.
- [x] v453 targeted rerun에서 `11718080`은 `official_title=null`, `title_resolution_allowed=false`, `work_resolution=none`, `anchor_type=genre`로 유지됐다.
- [x] v453 targeted rerun에서 `11718082`는 VLM/OCR `fetch=1/1 chunks=1`, `anchor_type=image`, `official_title=재벌가 차녀의 2회차 걸그룹`으로 회복됐다.
- [ ] `_search_with_meta()`는 context-free raw search wrapper다. 새 직접 호출부가 필요하면 static regression allowlist 갱신 전에 no-work/intent permit guard와 direct-anchor 예외를 focused test로 증명한다.
- [ ] 이 결과는 targeted canary다. 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v451/v452 no-work + VLM/OCR verified title canonical guard

- [x] Codex goal 병렬은 `spawn_agent` 전문가 분업이고, `expert_main.py --parallel` worker cap과 다른 계층임을 이번 라운드에 적용했다.
- [x] `11718080`/`11718082` targeted rerun은 `--parallel 36 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다.
- [x] small targeted run에서 requested/effective parallel `36/2`를 정상으로 보고 36 worker를 맞추기 위한 재실행을 하지 않았다.
- [x] shard/docker lifecycle은 재기동하지 않았다. manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_run_shard_lifecycle_blocked=true`를 확인했다.
- [x] v451에서 `11718080` no-work/잡담형이 `official_title=null`, `title_resolution_allowed=false`로 내려감을 확인했다.
- [x] v451에서 `11718082` VLM/OCR fetch/chunk/OCR 직접 근거가 실제로 남는지 확인했다.
- [x] v451 final은 맞지만 원문 미언급 canonical suspect override가 남아 candidate hygiene residual로 분리했다.
- [x] verified title lock + unanchored replacement canonical 후보 guard를 범용 evidence/provenance 조건으로 추가했다.
- [x] focused tests와 기존 rework suite를 통과했다.
- [x] v452에서 `11718082` final `재벌가 차녀의 2회차 걸그룹`, `heretic_url=https://page.kakao.com/content/66692543`, `anchor_type=image`, VLM `fetch=1/1 chunks=1`을 확인했다.
- [x] v452 로그에서 v451의 원문 미언급 canonical suspect override가 사라졌는지 확인했다.
- [ ] 이 결과는 targeted canary다. 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-06-01 v448/v449/v450 curated abbreviation adjacent candidate guard

- [x] v448 `11718120`은 result/manifest/checkpoint 기준 완료 산출물이 있으며 input/completed/flushed/pending/failed `1/1/1/0/0`이다.
- [x] v448는 `담텔기 -> 괴담 호텔 탈출기` known title abbreviation이 final `official_title=괴담 호텔 탈출기`까지 회복됨을 보여준다.
- [x] v448는 단건 런 정합성 `GO`와 semantic candidate hygiene `HOLD`를 분리해야 한다.
- [x] v448의 `title_candidates`에 원문 main context 미언급 인접 파생 후보 `괴담 학교 탈출기`가 남은 문제를 P1 adjacent candidate pollution으로 기록했다.
- [x] 후속 패치의 focused regression을 실행하고 결과를 `VERIFICATION_RESULTS.md`에 기록했다.
- [x] v450 live canary에서 final `괴담 호텔 탈출기` 유지와 `heretic_url=https://novelpia.com/novel/102155` 회복을 확인했다.
- [x] v450 `title_candidates`에는 `괴담 호텔 탈출기` 1건만 남고, `괴담 학교 탈출기`는 최종 후보에 남지 않았다.
- [x] no-work 상태에서 회차/스포 cue 하나로 known title abbreviation promotion이 풀리지 않는 회귀를 추가했다.
- [x] curated alias visible-surface 매칭과 generic keyword drift 회귀를 추가했다.
- [ ] v450은 targeted canary다. 10만 semantic approval은 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 Codex goal subagent 병렬 운영

- [x] v447에서 `KNOWN_TITLE_ABBREVIATIONS`를 `KNOWN_ABBREVIATIONS`와 같은 curated abbreviation promotion/support/stability 경로에 태웠다.
- [x] v447에서 안정 약칭이 post title/body에 있고 회차/스포/작가의 말/positive work intent 같은 packet-local work anchor가 있을 때만 no-work rescue 예외를 허용하도록 했다.
- [x] v447에서 no-work/잡담글은 known title abbreviation 표면만으로 promotion/stability가 살아나지 않는 회귀를 추가했다.
- [x] v446 `11718120` canary는 result JSON/checkpoint completed row가 없어 `REPROCESS/runtime-incomplete`로 분리했고, shard/docker lifecycle 문제와 semantic drift 문제를 따로 기록했다.
- [x] `tests\test_known_title_abbreviation_support.py` 3건, no-work guard 포함 5건, 기존 `AgenticPipelineReworkTest` 305건을 통과했다.
- [x] `11718120`은 v450에서 targeted canary `GO`까지 확인했다. 다만 이는 단건 검증이므로 expanded review 전까지 10만 approval source로 보지 않는다.
- [ ] `담텔기`류 known title abbreviation positive와 `305호`류 numeric/episode 후보는 expanded P0/P1 regression에서 provenance를 분리 검토한다.
- [x] v441에서 semantic no-work 상태의 decoder abbreviation stability, snippet canonical alias lock, canonical stable-hold rescue가 direct post/visual anchor 없이 작품 판정을 되살리지 못하게 했다.
- [x] v441에서 no-work rescue용 direct title mention을 decoder alias mapping이 아니라 raw title surface 기준으로 좁혔다.
- [x] v440에서 external browser artifact가 `visual_evidence_grade=Strong`이어도 본문 이미지 loading counter 실패가 있으면 visual gate를 만족하지 못하게 했다.
- [x] v440에서 Missing browser observation 문구에 본문 이미지 노드 미검출/이미지 로딩 근거 없음도 포함했다.
- [x] v439에서 semantic no-work/intent permit denied가 있으면 title-lead search-inferred support/stability/candidate를 만들지 않도록 보강했다.
- [x] `tests\test_title_lead_search_inferred_guard.py`를 추가했다. v439 회귀는 검색 결과가 충분해도 no-work 한탄/잡담형이면 support/stability가 `False`이고 candidate가 빈 배열이며, 실제 작품 반응형 positive control은 계속 회복됨을 확인했다.
- [x] v434에서 external browser artifact loader가 `output_path` JSONL을 읽도록 보강했다.
- [x] v434에서 `visual_evidence_grade=Weak|Missing` fallback screenshot은 `browser_visual_available`로 세지 않는 회귀를 추가했다.
- [x] v433 fallback browser capture는 external 권한에서 screenshot `4/4`를 만들었지만 article image selector `0/0`, visual grade `Weak=4`라 visual gate를 닫지 못했다.
- [x] v434 coverage는 weak fallback sidecar를 붙여도 `browser_visual_required/available/missing=4/0/4`, `browser_visual_external_artifact_available=0`, gate `REVIEW-LOCKED`임을 확인했다.
- [x] Windows `npx.cmd` wrapper에서 DCInside URL `&no=`가 cmd separator로 깨지는 문제를 `.cmd/.bat` 전용 escape로 막고 회귀 테스트를 추가했다.
- [x] v436 fallback recapture는 open/eval/screenshot return code `0`으로 command hygiene는 회복했지만, article image selector `0/0`, visual evidence `Missing=4`, image gate passed `0`이라 visual gate는 여전히 닫지 못했다.
- [x] v437 coverage는 v436 missing sidecar를 붙여도 `browser_visual_required/available/missing=4/0/4`, `browser_visual_external_artifact_available=0`, gate `REVIEW-LOCKED`임을 확인했다.
- [x] v432 targeted follow-up closure review를 작성했다. v431 4건 중 `ACCEPT=3`, `HOLD=1`이다.
- [x] `11718083`, `11718097`, `11718075`는 targeted follow-up 기준 닫았다.
- [x] `11718049` 댓글 URL `https://novelpia.com/novel/50764`가 실제 작품 페이지임을 확인했다.
- [x] `11718049`는 valid comment recommendation URL이 있는데 source final이 `noise/unrelated`라 `HOLD/re_judge`로 남긴다.
- [x] 댓글 URL 추천 답변은 단일 final title로 승격하지 않더라도 `recommendation_request`/`adjacent_relevant` 또는 recommendation candidate로 보존하는지 focused regression으로 점검했다.
- [x] 검색 결과의 등장인물 페이지 제목은 원문 본문 앵커가 아니므로, verifier가 `community_banter/reject`로 본 짧은 캐릭터 반응에서는 character-page rescue가 차단되는지 focused regression으로 점검했다.
- [x] `text_surface` 또는 `promotion_eligible=false` VLM/OCR 이미지 제목은 direct image title rescue와 image anchor 승격에서 제외되는지 focused regression으로 점검했다.
- [x] `semantic_seed_review` no-work 근거가 없는 짧은 캐릭터 반응은 `context_only`로 과접지하지 않고 `unresolved_matchable` scope를 유지하는지 focused regression으로 점검했다.
- [x] `11718049` live rerun에서 `comment_url_recommendation_candidate_preserved`, `topicality=adjacent_relevant`, `discussion_type=recommendation`, `recommendation_candidates[]`가 실제 result에 남는지 확인했다.
- [ ] v433 live rerun 4건의 browser visual artifact는 아직 result/coverage sidecar에 연결되지 않았다. Codex in-app Browser 연결 재실패 때문에 `browser_visual_required/available/missing=4/0/4`로 유지한다.
- [x] v431 targeted follow-up remaining queue를 생성했다. v429 `HOLD=2`와 v430 `REVIEW_ONLY=2`를 합쳐 총 4건의 packet-level 잔여 항목으로 분리했다.
- [x] v431 산출물은 manifest, queue JSONL, packet JSONL, 한국어 summary로 남겼다.
- [x] v431 queue는 `11718049` comment URL verify, `11718083` quote/title recall human review, `11718097` comment author unverified review-only, `11718075` search-only/title evidence review-only를 포함한다.
- [x] v431 queue 4건은 v432/v433에서 packet-level 또는 live rerun으로 재확인했다. 다만 v433 browser visual sidecar가 없어 targeted coverage gate는 `REVIEW-LOCKED`로 유지한다.
- [ ] v431 queue가 닫혀도 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.
- [x] 사용자 재정정에 따라 현재 goal 작업을 Codex 앱 `spawn_agent` 병렬 운영으로 다시 분리했다.
- [x] `Codex spawn_agent parallel`과 `expert_main.py --parallel`을 다른 계층으로 문서화했다. 전자는 goal 검토/구현 분업, 후자는 repo 런타임 worker cap이다.
- [x] goal 시작 시 분해 축을 먼저 선언하는 운영 원칙을 추가했다: `run integrity/manifest`, `runtime/shard/process`, `semantic/VLM/browser/comment`, `slang_db/BatchContext`, `prompt/orchestration/hardcode`, `docs/checklist`.
- [x] 10만 건 semantic review/targeted rerun의 Codex 전문가 subagent 기본 축을 고정했다: `source/preflight`, `runtime/shard/process`, `semantic/gate`, `VLM/OCR/browser/comment`, `slang_db/BatchContext`, `prompt/orchestration/hardcode`, `docs/checklist/gate`.
- [x] `expert_main.py --parallel` 조정이나 내부 LLM 전문가 호출 수 증가는 Codex `spawn_agent` 전문가 병렬 운영이 아니라는 체크포인트를 추가했다.
- [x] subagent는 evidence packet을 제공할 뿐 최종 승인자가 아니며, 메인 Codex가 통합 gate를 한 번만 판정한다는 기준을 고정했다.
- [x] 이번 라운드도 Codex `spawn_agent` 전문가 4개 축으로 재분해했다: runtime/orchestration, VLM-OCR/browser visual gate, semantic/prompt orchestration, docs/gate consistency.
- [x] small test에서 `requested_parallel=36`, `effective_parallel=1..N`이면 정상이며, 36 worker를 맞추기 위해 재실행하지 않는 기준을 문서화했다.
- [x] v411에서 Runtime/manifest, semantic 품질, VLM/OCR 이미지 게이트, 프롬프트/오케스트레이션 한계 subagent 결과를 통합했다.
- [x] `11718082`는 세대별로 구분했다. v179는 VLM-ready/log가 없어 승인 근거가 아니고, v181/v259/v311/v325/v330은 VLM/OCR이 돌았으며, 원본 10만 partial은 catalog 부재로 승인 근거가 아니다.
- [x] `11718080`류는 앞단 이해 실패만이 아니라 후단 `BatchContext`/known alias/search rescue가 no-work 판단을 뒤집는 비단조 파이프라인 문제로 기록했다.
- [x] 원본 5/28 result의 `batch_memory_exact_alias_rescued` P0 seed를 분리했다: `11718080`, `11718062`, `11718083`, `11718118`, `11718069`.
- [x] `context_sources=image` 또는 `anchor_type=image`만으로 VLM/OCR Strong evidence를 인정하지 않고, `image_evidence_catalog` 또는 VLM fetch/chunk counter를 요구하는 기준을 v411에 기록했다.
- [x] `hardcoded alias risk`, `VLM/OCR browser evidence gate`, `hardcoded alias audit tool/test`를 서로 다른 subagent 역할로 분리했다.
- [x] subagent 결과를 메인 Codex가 통합 검토하고, hardcoded alias/VLM evidence gate 산출물과 검증 결과를 갱신했다.
- [x] `tools\audit_hardcoded_alias_risk.py`와 `tests\test_hardcoded_alias_risk_audit.py`를 추가했다.
- [x] v405 refined hardcoded alias risk audit를 생성했다: `semantic_approval=REVIEW`, positive blocker `3`, quarantine-only `10`.
- [x] `build_goal_action_queue.py --hardcoded-alias-audit` 통합과 v406 refined action queue를 생성했다.
- [x] v406 action queue는 `total_actions=12`, `ready_now=7`, `blocked_until_completed_source=5`, approval blocker `6`이다.
- [x] `tools\build_hardcoded_alias_packet_review.py`와 `tests\test_hardcoded_alias_packet_review.py`를 추가했다.
- [x] v407 hardcoded alias packet review를 생성했다: scanned files `388`, scanned records `763`, matched packets `11`, packet coverage `FOUND`, gate `REVIEW`.
- [x] v407은 audit/report self-hit를 제외하고, evidence snippet only alias hit를 context-only로 분리한다.
- [x] v408 action queue에 `--hardcoded-alias-packet-review`를 통합했다.
- [x] v408 action queue는 `total_actions=13`, `ready_now=8`, `blocked_until_completed_source=5`, approval blocker `7`이다.
- [x] v409 hardcoded alias packet label review를 작성했다: 11건 중 `ACCEPT=6`, `HOLD=2`, `REJECT=3`.
- [x] v409 REJECT는 author/meta 과차단, noise 과차단, wrong canonical title 변형으로 분리했다.
- [x] `build_goal_action_queue.py --hardcoded-alias-packet-labels`를 추가하고 v410 action queue에 통합했다.
- [x] v410 action queue는 `total_actions=14`, `ready_now=9`, `blocked_until_completed_source=5`, approval blocker `8`이다.
- [x] `NovelIdentity.alias_resolution_sources[]`를 추가하고 qualitative packet `final_decision_fields`에 alias provenance를 노출했다.
- [x] `build_current_remaining_action_inputs.py` 실행 계약은 현재 재실행 입력 수 기준 권장 parallel을 표시하고, 소규모 reuse-only goal/test에서 `MCP_SHARD_COUNT=36`을 required contract로 쓰지 않는다.
- [x] VLM/OCR 직접 근거와 Browser image loading evidence를 분리한다. lazy/data-original/placeholder/incomplete/broken pending이 남으면 visual evidence는 `Strong`이 아니다.
- [x] `intent_permit_for_title_search=false` 상태에서는 실행 직전 검색 gate가 title/alias/key-term 목적 검색을 막는다. 닫힌 기본값으로 `term_definition` 등 안전 목적만 허용하며, 이미지 OCR 직접 작품 앵커는 예외로 둔다.
- [x] 후단 `BatchContext`/known alias/slang_db seed/deliberation rescue 경로도 `semantic_seed_review` no-work, `title_resolution_allowed=false`, `context_only` 신호를 독립 작품 evidence처럼 되살리지 않도록 회귀를 추가했다.
- [x] runtime/shard explorer 결과 기준으로 `--parallel 36`은 max이고 small input에서 effective worker가 줄어드는 현 계약을 재확인했다.
- [x] semantic/VLM explorer 결과 기준으로 intent-first 구조는 있으나, search suppression 기본 off + key_terms 자동 검색 + Verifier 검색 우선 조합이 P0 위험임을 기록했다.
- [x] `intent_permit_for_title_search` 또는 동등한 구조 필드로 검색 전 intent permit을 강제한다.
- [ ] `search_only` evidence는 weak로 남기고, `trope_discussion/community_banter/author_talk/recommendation` intent에서 `resolved_title` 확정을 막는다.
- [x] 위 항목의 completed-source 회귀 감지를 위해 `search_only_resolved_title`, `blocked_intent_resolved_title`, `*_review_only` semantic coverage bucket을 추가했다.
- [x] comment author/IP/context는 focused export/coverage 테스트 기준 대화 흐름 힌트로 분리된다. 단, 10만 expanded review에서 독립 작품 evidence 승격 여부는 계속 확인한다.
- [x] `image_post_count>0`인데 `vlm_ocr_semantic_review_ready=false`인 run은 결과 요약과 manifest에 NO-GO 사유, action, sample post id를 남긴다.
- [x] 이미지 semantic test에서 `--vlm on --ocr on` 누락을 빠르게 실패 처리할 수 있도록 `--require-vlm-ocr-for-images`와 `LLM_REQUIRE_VLM_OCR_FOR_IMAGES=1` guard를 추가했다.
- [x] VLM/OCR semantic review skip reason을 `no_image_blocks`, `vlm_disabled`, `ocr_disabled`로 구조화해 manifest/Summary에 남긴다. `fetch_failed`, `geometry_skip` 같은 per-image status는 후속 세분화로 둔다.
- [x] Gemma 4 4B 모델별 parallel hard cap `36`을 코드/manifest/run_meta에 명시적으로 남긴다.
- [x] active goal을 `gate/evidence`, `runtime/shard/process`, `semantic/VLM/comment` explorer 3개로 병렬 분해했다.
- [x] 이번 semantic rescue 라운드도 메인 Codex가 blocking patch/test를 맡고, subagent 2개가 후단 우회 감사와 운영 문서 위치 감사를 병렬로 맡는 방식으로 진행했다.
- [x] explorer 결과에서 원본 source `NO-GO`, 10만 semantic approval `REVIEW-LOCKED`, runtime/hygiene targeted `GO`를 분리 확인했다.
- [x] 후속 구현은 `runtime audit process snapshot` worker와 `semantic coverage audit` worker로 disjoint write scope를 나눴다.
- [x] `tools\audit_goal_test_run_contract.py`에 선택형 process snapshot 수집을 통합했다.
- [x] `tools\build_semantic_coverage_audit.py`를 추가해 image/comment/final semantic reread coverage를 별도 감사하게 했다.
- [x] v395 process snapshot audit와 v396 original semantic coverage audit 산출물을 생성했다.
- [x] `--process-snapshot-json` 외부 snapshot 주입 경로를 추가하고, v397 외부 process snapshot audit에서 stale `expert_main/llm_batch/warp_shards/vllm/uvicorn` 후보 `0`건을 확인했다.
- [x] v396 semantic coverage와 v397 process snapshot을 v398 action queue에 통합했다.
- [x] v398 action queue는 `total_actions=11`, `ready_now=6`, `blocked_until_completed_source=5`, approval blocker `5`개로 분리됐다.
- [x] `final_semantic_reread_required/present/missing`을 추가해 final reread 요구 row와 단순 부재 row를 분리했다.
- [x] `expert_main.py` summary/manifest에 VLM/OCR Semantic Gate와 `image_post_sample_post_ids`를 추가했다.
- [x] `build_semantic_coverage_audit.py`에 `image_context_without_vlm_catalog` bucket을 추가했다. `context_sources=image` 또는 `anchor_type=image`가 있지만 `image_evidence_catalog`와 VLM fetch/chunk counter가 없으면 `REVIEW-LOCKED` 이슈로 남긴다.
- [x] browser screenshot/manifest path만으로 visual available을 인정하지 않고, lazy/data-original/placeholder/incomplete/broken/pending loading counter가 있으면 missing으로 낮추는 회귀를 추가했다.
- [x] `failed/timeout/pending/skipped/unsupported/disabled` VLM 상태 문자열을 positive fetch/chunk evidence로 세지 않는 회귀를 추가했다.
- [x] v414 original semantic coverage audit를 재생성했다. 원본 partial source는 `image_context_without_vlm_catalog=36`, `image_evidence_catalog_missing=37`, `browser_visual_missing=37`로 계속 `REVIEW-LOCKED`다.
- [x] v415 action queue를 재생성해 `modern_semantic_coverage_source_required` evidence에 `image_context_without_vlm_catalog=36`을 포함했다.
- [x] 댓글 맥락이 resolved 판정에 관여했지만 `comment_metadata`/`comment_dialogue_context_lines` attribution이 없는 케이스를 `comment_context_resolution_without_attribution`으로 감사한다.
- [x] `author_match_unverified`/`post_author_match_unverified` 댓글 맥락이 resolved 판정에 관여하면 `comment_author_match_unverified_used_for_resolution`으로 감사한다.
- [x] v417 original semantic coverage audit를 생성했다. 원본 partial source는 `comment_context_resolution_without_attribution=19`, `comment_author_match_unverified_used_for_resolution=0`으로 계속 `REVIEW-LOCKED`다.
- [x] v418 action queue를 생성해 `modern_semantic_coverage_source_required` evidence에 comment attribution bucket을 포함했다.
- [x] v419 original semantic coverage audit를 생성했다. 원본 partial source는 `search_only_resolved_title=6`, `blocked_intent_resolved_title=7`, `*_review_only=0`으로 계속 `REVIEW-LOCKED`다.
- [x] v420 action queue를 생성했다. `modern_semantic_coverage_source_required` evidence에 search-only/blocked-intent bucket을 포함했고, `vlm_ocr_browser_visual_gate`는 P0 approval blocker로 승격됐다.
- [x] v421 search-only/blocked-intent bucket 정성 triage를 작성했다. unique post `11` 중 `HOLD=4`, `REJECT=7`이며, 전체 10만 오류율이 아니라 후속 re_search/re_judge 우선순위로만 사용한다.
- [x] 이번 v422 후속 라운드도 Codex `spawn_agent` 전문가 병렬 운영으로 진행했다. `Popper`는 source 복원, `Wegener`은 semantic gate, `Aquinas`는 runtime/shard 계약을 읽기 전용으로 분리 검토했다.
- [x] v422 follow-up 입력 package를 생성했다. source post rows `11`, comment rows `25`, missing post `0`, image/browser target `6`이며, 중복 post row는 post 기준으로 dedupe했다.
- [x] v422 targeted rerun을 `--parallel 36 --reuse-shards-only --no-dashboard --vlm on --ocr on --require-vlm-ocr-for-images`로 실행했다. 결과는 completed/failed/pending `11/0/0`, requested/effective parallel `36/11`, VLM/OCR `READY`다.
- [x] v423 자동 after-review의 `11/11 ACCEPT`는 과낙관으로 보고 gate 근거에서 제외했다.
- [x] v424 coverage audit를 생성했다. `search_only_resolved_title=0`, `blocked_intent_resolved_title=0`, image catalog `6/0`, comment metadata `7/0`이지만 `browser_visual_required/available/missing=6/0/6`으로 gate는 계속 `REVIEW-LOCKED`다.
- [x] v425 browser artifact를 확보했다. Codex in-app Browser `node_repl`과 Playwright CLI fallback은 실패했지만 MCP Playwright로 6개 DC 원문 screenshot/snapshot을 남겼다.
- [x] v425 수동 라벨을 작성했다. `ACCEPT=8`, `HOLD=2`, `REJECT=1`이며 `11718098` positive alias 과차단은 P1 회귀로 남긴다.
- [x] v425 외부 browser artifact를 v426/v429 semantic coverage audit sidecar manifest로 연결해 targeted follow-up coverage에서 `browser_visual_required/available/missing=6/6/0`을 확인했다.
- [x] `11718098` positive alias/title-discussion 과차단은 v428에서 `semantic_seed_review_non_title_terms_removed`와 keep-query positive seed를 분리해 재검증했다. 결과는 `마법 좋아좋아좋아` resolved, `is_relevant=true`, confidence `Medium`이다.
- [x] v429 guarded after-review를 생성했다. `ACCEPT=9`, `HOLD=2`, `REJECT=0`이며, 자동 label은 coverage gate와 분리해 해석한다.
- [x] v429 coverage audit는 browser visual `6/6/0`, image catalog `6/0`, comment metadata `7/0`을 확인했다. 남은 REVIEW-LOCKED 이슈는 `11718097` comment author unverified resolution과 `11718075` search_only resolved title이다.
- [x] v430 refined semantic coverage audit를 생성했다. targeted coverage gate는 `REVIEW`로 내려갔고, browser visual `6/6/0`, image catalog `6/0`, comment metadata/dialogue `7/0`과 `7/0`을 확인했다.
- [x] v430에서 `11718097`은 `comment_author_match_unverified_used_for_resolution=0` / review-only `1`, `11718075`는 `search_only_resolved_title=0` / review-only `1`로 재분류됐다. 두 건은 hard blocker가 아니라 packet-level review-only로 남긴다.
- [x] `11718049` comment URL 후보는 최신 코드 live rerun에서 adjacent recommendation candidate로 보존됨을 확인했다.
- [ ] `11718083` quote/title recall은 HOLD queue로 유지한다.
- [x] v399에서 최신 clean canary 4건을 refined semantic coverage audit로 재확인했다.
- [x] v400 refined original coverage와 v401 refined action queue를 생성했다.
- [x] v402 현재 goal 진행 요약을 남겼다.
- [x] focused combined unittest `26`건과 `git diff --check`를 통과했다. 줄끝 변환 경고만 있었다.
- [x] worker 산출물을 메인 Codex가 통합 검토하고 docs/verification을 갱신했다.
- [ ] v430 targeted coverage gate 완화는 전체 승인 근거가 아니다. 10만 semantic approval은 completed VLM/OCR-on source와 expanded review 전까지 계속 `REVIEW-LOCKED`/`NO-GO`로 분리 유지한다.

## 2026-05-31 v394 goal action queue

- [x] `tools\build_goal_action_queue.py`를 추가해 v393 상태맵에서 실행 큐를 생성하게 했다.
- [x] v394 action queue는 `total_actions=8`, `ready_now=4`, `blocked_until_completed_source=4`로 분리됐다.
- [x] approval blocker는 `obtain_completed_vlm_ocr_source`, `rerun_large_scale_preflight_on_completed_source`, `expanded_random_baseline_1000`, `p0_p1_high_risk_expansion`이다.
- [x] ready action은 소규모 runtime audit, reason hygiene scan, VLM/OCR browser visual gate, 원본 partial source regression seed 유지다.
- [ ] approval blocker 4개가 끝나기 전 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v393 goal current-state map

- [x] `tools\build_goal_current_state_map.py`를 추가해 원본 source, preflight, runtime audit, reason hygiene를 한 상태맵으로 묶었다.
- [x] v393 상태맵에서 원본 source approval은 `NO-GO`, 최근 소규모 runtime contract는 `GO`, 최신 reason hygiene는 `GO`, 10만 semantic approval은 `REVIEW-LOCKED`로 분리했다.
- [x] 원본 manifest partial signals `completed_count_lt_input_post_count`, `pending_count_gt_zero`, `flushed_count_lt_completed_count`, `result_rows_lt_completed_count`를 blocker로 고정했다.
- [x] v393 산출물: `qualitative_review\20260528_141006_620986\v393_goal_current_state_map.json`, `_ko.md`.
- [ ] 이후 goal 보고에서는 runtime/canary `GO`만으로 10만 semantic approval을 닫지 않는다.

## 2026-05-31 v392 expression reread colon-payload guard

- [x] public reason의 재해독 안내를 `표현 오타/축약 패턴(범용): ...`가 아니라 `표현 오타/축약 패턴(범용)은 ...` 문장형으로 바꿨다.
- [x] reason hygiene scanner가 `표현 오타/축약 패턴(범용):` 회귀를 `surface_reread_label_colon_payload`로 잡게 했다.
- [x] 재해독은 특정 정상형 복원, 표면값 나열, 계열 일반규칙이 아니라 packet-local 범용 재검토 신호임을 문서에 다시 고정했다.
- [x] latest clean canary 4건 raw reason hygiene scan에서 `surface_reread_label_colon_payload` hit가 없음을 확인했다.
- [ ] 10만 semantic gate는 completed source와 expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v391 goal/test audit auto log discovery

- [x] 감사 도구가 manifest `run_id`로 expert run log를 자동 발견하게 했다.
- [x] 자동 발견 로그가 없으면 `log_evidence_missing`으로 `runtime_contract=REVIEW`를 남긴다.
- [x] v381 manifest-only 감사에서 자동 발견 log와 `runtime_contract=GO`를 확인했다.
- [x] focused unittest 6건과 `py_compile`을 통과했다.
- [ ] 이후 완료 보고에서 manifest-only `GO`를 쓰지 않고 log evidence present를 함께 확인한다.

## 2026-05-31 v390 goal/test run contract audit

- [x] post-run manifest/log 감사 도구 `tools\audit_goal_test_run_contract.py`를 추가했다.
- [x] 감사 도구가 `requested_parallel=36` max, `effective_parallel`, Docker/shard lifecycle flags, forbidden log hit, VLM/OCR ready를 함께 확인한다.
- [x] v381 clean canary manifest/log로 v390 audit artifact를 생성했다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [ ] `runtime_contract=GO`를 10만 semantic approval로 해석하지 않는다.

## 2026-05-31 v389 expression reread active label cleanup

- [x] active prompt/reason/report/test 기대 문구에서 재해독 label을 `표현 오타/축약 패턴(범용)`으로만 맞췄다.
- [x] 재해독을 특정 정상형 복원, 계열 일반규칙, 검색 seed, 작품명/별칭 근거처럼 설명하지 않게 다시 정리했다.
- [x] `LLM_JUDGMENT_REVIEW.md`, `SCAN_RESULT_REVIEW_GUIDE.md`, `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`의 active 지침을 갱신했다.
- [x] focused unittest 7건과 `py_compile`을 통과했다.
- [ ] 10만 semantic gate는 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v388 downstream builder locked-source gate

- [x] random control builder에 `--preflight`와 `--fail-on-locked-source`를 추가했다.
- [x] round2 high-risk builder에 `--preflight`와 `--fail-on-locked-source`를 추가했다.
- [x] preflight missing/source mismatch/`REVIEW-LOCKED` helper 테스트를 추가했다.
- [x] v386 locked preflight를 붙인 random dry-run이 exit code 2로 멈추고 output dir를 만들지 않는지 확인했다.
- [x] v386 locked preflight를 붙인 round2 dry-run이 exit code 2로 멈추고 output dir를 만들지 않는지 확인했다.
- [ ] approval 목적 자동화에서는 preflight 뒤 downstream builder에도 반드시 `--preflight <json> --fail-on-locked-source`를 붙인다.
- [ ] 10만 semantic gate는 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v387 expression reread generic label narrowing

- [x] 재해독 public label을 `표현 오타/축약 패턴(범용)`으로 좁혔다.
- [x] prompt/reason/report에서 `표현 오타/축약 패턴(범용)`보다 긴 확장 label을 쓰지 않게 정리했다.
- [x] 특정 정상형 복원, 표면 계열 전용 규칙, post/string hardcode 금지를 다시 확인했다.
- [ ] 최신 canary 또는 expanded review 전 raw reason hygiene로 old wording drift를 다시 확인한다.
- [ ] 10만 semantic gate는 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v386 preflight fail-on-locked CLI gate

- [x] preflight CLI에 `--fail-on-locked` 옵션을 추가했다.
- [x] 기본 실행은 종료코드 0을 유지하고, `REVIEW-LOCKED`를 실패로 다루는 동작은 옵션으로만 켠다.
- [x] `--fail-on-locked` 사용 시 `gate.overall=REVIEW-LOCKED`이면 종료코드 2를 반환한다.
- [x] 원본 objective source v386 preflight에서 `exit_code=2`를 확인했다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [ ] 10만 semantic gate는 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v385 expression reread generic wording correction

- [x] final semantic reread prompt의 특정 계열 예시 문구를 `표현 오타/축약 패턴(범용)` 중심으로 낮췄다.
- [x] 회귀 테스트 기대 문구를 특정 정상형/계열 설명이 아니라 범용 label 계약으로 맞췄다.
- [x] 운영/리뷰 문서 상단에 새 active rule을 추가해 과거 표면형 복원 기록은 historical observation으로만 보게 했다.
- [x] `py_compile`과 focused final semantic reread unittest 9건을 통과했다.
- [ ] 최신 canary 또는 expanded review 전에는 raw reason hygiene로 old wording drift를 다시 확인한다.
- [ ] 10만 semantic gate는 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v384 preflight source policy clarity

- [x] manifest partial signal이 source policy에 반영되도록 preflight 도구를 보강했다.
- [x] 원본 source가 `partial_final_result_json`, `manifest_partial_run`, `large_run_complete=false`로 분류되는지 확인했다.
- [x] gate에 `required_next_actions`가 기록되는지 확인했다.
- [x] v384 preflight 산출물을 생성했다.
- [x] focused unittest 3건과 `py_compile`을 통과했다.
- [ ] completed source 확보 전까지 원본 source는 regression seed로만 사용한다.

## 2026-05-31 v383 original source preflight

- [x] v382 affected-row recovery 이후 원본 objective source를 다시 preflight했다.
- [x] 원본 manifest `104502/80/71/9/0`, result rows `71`, checkpoint completed rows `80`, pending snapshot rows `9`를 확인했다.
- [x] random baseline `1000` 기준 available rows `71`, shortfall `929`를 확인했다.
- [x] v383 gate가 `run_integrity=REVIEW`, `semantic_preflight=REVIEW-LOCKED`, `overall=REVIEW-LOCKED`임을 확인했다.
- [x] preflight Markdown 산출물 heading/field label을 한국어 기준으로 고쳤다.
- [x] focused unittest로 한국어 heading 회귀를 막았다.
- [ ] original source는 approval source가 아니라 regression seed로만 사용한다.
- [ ] completed source 확보 전까지 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v380-v382 affected-row recovery matrix

- [x] `11718103` v380 단건 canary를 VLM/OCR on으로 실행했다.
- [x] v380 manifest 기준 requested/effective parallel `36/1`, completed/flushed/pending/failed `1/1/0/0`, shard lifecycle blocked를 확인했다.
- [x] `11718103`은 `discussion_type=meta`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`로 확인했다.
- [x] `11718096` v381 단건 canary를 VLM/OCR on으로 실행했다.
- [x] v381 manifest 기준 requested/effective parallel `36/1`, completed/flushed/pending/failed `1/1/0/0`, shard lifecycle blocked를 확인했다.
- [x] `11718096`은 `헌터갤러리의 국가권력급 기계공주`, official URL `https://novelpia.com/novel/390228`, `title_resolution_state=resolved`로 확인했다.
- [x] v372/v379/v380/v381 clean set reason hygiene scan에서 `hit_files=0`, `clean_files=4`를 확인했다.
- [ ] original result approval은 계속 `NO-GO`, 10만 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v377-v379 원본 stale reason affected rows

- [x] v377 `11718102`, `11718096`을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 실행했다.
- [x] v377 manifest 기준 requested/effective parallel `36/2`, completed/flushed/pending/failed `2/2/0/0`, shard lifecycle blocked를 확인했다.
- [x] fallback visual evidence에서 `11718102` 이미지는 platform catalog/background listing, `11718096` 이미지는 character visual only로 분리했다.
- [x] `11718096`은 `헌터갤러리의 국가권력급 기계공주`, official URL `https://novelpia.com/novel/390228`, `title_resolution_state=resolved`로 확인했다.
- [x] v377 `11718102` dirty reason의 `단정하기 어려움할` suffix drift를 scanner로 잡았다.
- [x] v379 `11718102`은 `is_relevant=false`, `title_resolution_state=context_only`, `title_resolution_allowed=false`로 회복했다.
- [x] v379 reason hygiene raw scan에서 `hit_files=0`, `clean_files=1`을 확인했다.
- [ ] v377/v378은 historical repro evidence로만 보관하고 approval source로 쓰지 않는다.
- [ ] 10만 semantic gate는 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v376 expression reread wording contract

- [x] 재해독 public label을 `표현 오타/축약 패턴(범용)`로 고정했다.
- [x] public reason 경계 문구를 `표현 오타/축약 패턴(범용)은 작품명/별칭 근거가 아니다`로 고정했다.
- [x] old wording drift를 current source/test/core review docs의 active contract에서 제거했다.
- [x] reason hygiene scanner에 `reread_wording_drift`를 추가했다.
- [x] focused tests와 `py_compile`을 통과했다.
- [x] v370/v372 latest canary raw scan이 updated `reread_wording_drift` 기준에서도 clean이다.
- [ ] 10만 semantic gate는 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v375 original result reason hygiene scan

- [x] objective 원본 result를 `tools\scan_reason_hygiene.py`로 직접 검사했다.
- [x] raw scan에서 `hit_files=1`, `clean_files=0`, `stale_relevant=18`, `llm_flip=9`를 확인했다.
- [x] affected rows `11718085`, `11718103`, `11718102`, `11718096`을 기록했다.
- [x] manifest 기준 original result가 partial source임을 재확인했다.
- [x] modern review field coverage 부족을 approval `NO-GO` 근거로 다시 기록했다.
- [ ] original result는 regression seed로만 쓰고, current approval source로 쓰지 않는다.
- [ ] 10만 semantic gate는 completed source와 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v374 reason hygiene raw scan tooling

- [x] `tools\scan_reason_hygiene.py`를 추가해 raw text forbidden pattern scan을 재현 가능하게 했다.
- [x] `--min-version` 사용 시 unversioned JSON을 제외한다.
- [x] `*_tool_report.json`을 기본 제외해 리포트 자체 재스캔 오염을 막는다.
- [x] `.gitignore` 예외로 `tools\scan_reason_hygiene.py`를 추적 가능하게 열었다.
- [x] v374 tool report에서 v360 이후 result JSON 12개, hit 10개, clean 2개를 재현했다.
- [x] focused unittest와 `py_compile`을 통과했다.
- [ ] 이 도구 결과는 targeted public-output hygiene 보조 증거이며 10만 semantic gate는 별도 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 v373 v360-v372 reason hygiene raw scan

- [x] v360 이후 result JSON 12개를 raw text 기준으로 검사했다.
- [x] v360-v369와 v371은 pre-fix/historical repro artifact라 current approval source로 쓰지 않도록 분리했다.
- [x] v370과 v372는 raw text forbidden scan에서 clean임을 확인했다.
- [x] v373 raw scan 산출물과 labels JSONL을 남겼다.
- [ ] historical repro artifact가 포함된 폴더 전체를 무차별 `GO` 근거로 쓰지 않는다.
- [ ] 10만 semantic gate는 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v371-v372 BatchMem 로그 축약 및 ranked reason hygiene

- [x] BatchMem seed preload 로그를 기본 summary 모드로 줄였다.
- [x] `PIPELINE_BATCHMEM_SEED_LOG_MODE=summary|full|off` 동작을 focused unittest로 확인했다.
- [x] v371에서 BatchMem summary는 성공했지만 public reason의 `작품 seed 제외:` 회귀를 `HOLD`로 분리했다.
- [x] v372 단건 canary를 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 실행했다.
- [x] v372 manifest/run meta 기준 requested/effective parallel `36/1`, `image_evidence_catalog=1`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 확인했다.
- [x] v372 forbidden scan에서 `seed 후보(`, `작품 seed 제외`, stale relevant template 계열이 검출되지 않았다.
- [ ] 10만 semantic gate는 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v365-v370 relevant-no-title follow-up

- [x] v365에서 `11718085`, `11718103`을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재확인했다.
- [x] v365 run manifest 기준 requested/effective parallel `36/2`, completed/flushed/pending/failed `2/2/0/0`, shard lifecycle blocked를 확인했다.
- [x] v368에서 `11718085` public reason의 `seed 후보(...)`, `작품 seed 제외:` 반복을 재현했다.
- [x] v370에서 `11718085` public reason이 `표현 오타/축약 패턴(범용)`와 `작품명/별칭 근거가 아니다`만 공개하는지 확인했다.
- [x] v370 result scan에서 `seed 후보(`, `작품 seed 제외`, `단정하기 어려움하기에는`, `최종 판정은 관련 포스트`, `LLM(False)→최종(True)`가 검출되지 않았다.
- [x] focused unittest 5건과 `py_compile`을 통과했다.
- [ ] 10만 semantic gate는 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v364 원본 result 대비 current small-run delta

- [x] 목표 파일 `out\expert_result_20260528_141006_620986.json`과 manifest를 current state에서 직접 확인했다.
- [x] 원본 manifest의 input/completed/flushed/pending/failed `104502/80/71/9/0`을 기록했다.
- [x] 원본 result rows `71`, relevant `29`, irrelevant `42`, official_title rows `27`을 기록했다.
- [x] 원본 result의 `title_resolution_state`, `comment_metadata`, `image_evidence_catalog` coverage가 `0`임을 확인했다.
- [x] `11718083`, `11718091`, `11718097`, `11718099`의 원본-v360/v363 delta를 산출물로 남겼다.
- [ ] 원본 result는 approval source가 아니라 regression seed source로만 사용한다.
- [ ] 10만 semantic gate는 modern field coverage와 expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v360/v363 소규모 테스트런 및 재해독 raw 후보 반복 제거

- [x] v360 known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 실행했다.
- [x] v360 run manifest 기준 requested/effective parallel `36/4`, completed/flushed/pending/failed `4/4/0/0`, shard lifecycle blocked를 확인했다.
- [x] `11718091` v360 public reason의 surface/seed 후보 반복을 output hygiene 이슈로 기록했다.
- [x] v363 `11718091` 단건 canary에서 requested/effective parallel `36/1`, VLM/OCR on, shard lifecycle blocked를 확인했다.
- [x] v363 public reason은 원문 title/body 밖에서 `seed 후보(...)`, `작품 seed 제외: ...` raw 후보를 반복하지 않는다.
- [x] focused unittest와 `py_compile`을 통과했다.
- [ ] `11718083` actual quote/source alignment는 아직 `HOLD/human_review`다.
- [ ] 10만 semantic gate는 expanded random/high-risk review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v359 재해독 범용 패턴 문구 재정렬

- [x] public reason label을 `표현 오타/축약 패턴(범용)`로 맞췄다.
- [x] prompt/report/reason에서 구체 설명 범주를 자동 차단/허용 규칙처럼 반복하지 않게 했다.
- [x] 표면 재해독 차단은 특정 단어 계열 regex 단독이 아니라 `surface_paraphrase_notes`/semantic review 경계 신호를 요구한다.
- [x] `py_compile`과 focused semantic reread unittest 13건을 통과했다.
- [ ] v359은 wording/contract 보강이며 10만 semantic gate는 expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v358 goal completion audit

- [x] 원 goal을 current evidence 기준으로 requirement-by-requirement 재감사했다.
- [x] targeted known-bad guard와 10만 semantic approval을 분리했다.
- [x] 원본 result가 partial이고 public metadata/VLM catalog coverage가 부족해 approval source가 아님을 다시 확인했다.
- [x] v358 matrix와 remaining action queue를 남겼다.
- [ ] completed source, expanded random/high-risk review, `11718083` actual recall, IAB closure 전까지 goal complete를 선언하지 않는다.

## 2026-05-31 v356/v357 공개 reason live canary

- [x] v356 known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 실행했다.
- [x] v356 run manifest에서 requested/effective parallel `36/4`, completed/flushed/pending/failed `4/4/0/0`, shard lifecycle restart 없음, VLM/OCR on을 확인했다.
- [x] `11718083` title-null/HOLD, `11718091` context-only/title-null, `11718097` `망겜의 힐러`, `11718099` `빌어먹을 환생`을 확인했다.
- [x] v356에서 발견된 공개 reason 정규화 괄호 회귀를 v357 단건 canary로 보정 확인했다.
- [x] v357 `11718091`은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`이며 공개 reason에 `23세/16세`, `X -> Y`, `작품 seed 제외: ..., 23센줄` 계열 회귀가 없다.
- [ ] `11718083` actual recall과 10만 expanded review 전까지 semantic gate는 `REVIEW-LOCKED`다.

## 2026-05-31 v355 재해독 공개 reason 표면어 재열거 금지

- [x] 최종 reason에서 `표현 오타/축약 패턴(범용): X; Y` 형태를 쓰지 않게 했다.
- [x] 표면 재해독 후보는 원문 title/body/comment 확인용으로만 두고, 공개 `작품 seed 제외` 목록에 다시 섞지 않게 했다.
- [x] legacy `paraphrase` 필드를 sanitizer 근거로 쓰지 않게 했다.
- [x] focused unittest 11건과 `py_compile`을 통과했다.
- [ ] 과거 history에 남은 `X -> Y` 기록은 historical observation일 뿐, 최신 prompt/reason/report 규칙으로 재사용하지 않는다.
- [ ] 10만 semantic gate는 expanded review 전까지 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v354 Browser Playwright fallback visual evidence

- [x] Codex in-app Browser 연결을 재시도했지만 setup 단계에서 실패해 IAB target closure로 올리지 않았다.
- [x] Playwright fallback으로 `11718083`, `11718094` 실제 DC post page screenshot/snapshot을 확보했다.
- [x] `11718083`은 본문 이미지가 로딩됐지만 작품명/플랫폼/URL/quote source anchor가 없음을 확인했다.
- [x] `11718094`는 소설 발췌처럼 보이는 본문 텍스트는 있으나 title/platform/URL/회차/source anchor가 없음을 확인했다.
- [ ] 두 건 모두 `HOLD/human_review` 유지이며 IAB target closure와 expanded review 전까지 semantic gate는 `REVIEW-LOCKED`다.

## 2026-05-31 v353 known-bad 4 after v352 contract canary

- [x] known-bad 4건을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- [x] run manifest 기준 completed/flushed/pending/failed `4/4/0/0`, requested/effective parallel `36/4`, shard lifecycle blocked를 확인했다.
- [x] `11718083`은 `네이버` wrong-title 재발 없이 `official_title=null`, `unresolvable_memory_query`를 유지했다.
- [x] `11718091`은 deterministic paraphrase 없이 범용 label과 `context_only/title-null`을 유지했다.
- [x] `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 유지했다.
- [x] v353 Round2 review에서 `ACCEPT=3`, `HOLD=1`을 확인했다.
- [ ] 남은 `11718083` actual title recall과 10만 expanded review 전까지 semantic gate는 `REVIEW-LOCKED`다.

## 2026-05-31 v352 재해독 표면 계열 일반규칙 금지

- [x] 코드 프롬프트와 rule note에 `표현 오타/축약/띄어쓰기 패턴`은 범용 후보일 뿐, 표면 계열 일반규칙으로 승격하지 않는다고 명시했다.
- [x] `나이/외모/친구/한탄` 같은 범주는 예시적 위험 신호이며 자동 차단/허용 규칙이 아니라고 문서화했다.
- [x] 새 prompt/report/reason에서는 `X -> Y`식 정상형 복원, post id/string hardcode, 계열별 deterministic rule을 쓰지 않는다고 재확인했다.
- [ ] 이 변경은 wording/contract 보강이며 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v351 남은 HOLD quote/source alignment

- [x] `11718083`, `11718094`에 대해 exact/near quote 및 character-pair source alignment를 추가 확인했다.
- [x] 두 건 모두 직접 quote/source/title/platform anchor를 확인하지 못해 `HOLD/human_review`를 유지했다.
- [x] v351 산출물과 manifest를 남겼다.
- [ ] 두 건은 사람 검토 또는 더 강한 full-text/source evidence 전까지 자동 ACCEPT하지 않는다.

## 2026-05-31 v350 Browser fallback visual review

- [x] Codex in-app Browser 연결을 재시도하고 실패 상태를 기록했다.
- [x] `11718083`, `11718094` 이미지 원본을 repo venv `httpx` fallback으로 확보했다.
- [x] `11718083` visual evidence가 작품명/quote alignment를 직접 지지하지 않음을 확인했다.
- [x] `11718094` visual evidence가 소설 본문 발췌지만 작품명/플랫폼/URL anchor를 제공하지 않음을 확인했다.
- [x] 두 건 모두 `HOLD/human_review` 유지로 기록했다.
- [ ] Codex in-app Browser screenshot 확보 전까지 Browser visual review는 `PENDING`이다.
- [ ] browser target 28건과 expanded review 전까지 semantic gate는 `REVIEW-LOCKED`다.

## 2026-05-31 v349 slang/OCR subtype closure

- [x] 저장 차단된 OCR/표면형이 official detail URL과 final title로 정리된 경우 `slang_db_subtype_closed`로 분리했다.
- [x] `11718082`는 `store_in_slang_db=false`, `character_attached_composite`, official detail URL, surface form pruned flag를 확인해 `ACCEPT/no_action`으로 닫았다.
- [x] v349 relabel에서 `ACCEPT=13`, `HOLD=2`를 확인했다.
- [x] focused regression 42건과 `py_compile`을 통과했다.
- [x] `11718083`, `11718094`는 fallback visual evidence 후에도 `HOLD` 유지가 맞음을 확인했다.
- [ ] 실제 Browser screenshot 또는 human/full-text source 전까지 두 건은 자동 ACCEPT하지 않는다.
- [ ] browser target 28건을 닫기 전까지 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 v348 action queue relabel refinement

- [x] v347 rerun review의 false-positive HOLD를 줄이는 Round2 labeler 보정을 적용했다.
- [x] `platform_non_detail_url_used_near_official_evidence`, `round2_false_negative_recall`, `comment_author_match_unverified_dialogue`의 승인 가능한 경계를 분리했다.
- [x] v348 relabel에서 `ACCEPT=12`, `HOLD=3`, `REJECT=0`, `REPROCESS=0`, `INFO_MISSING=0`을 확인했다.
- [x] 재해독은 `표현 오타/축약 패턴(범용)` label과 "패턴은 범용 후보" 설명으로만 보고, `X -> Y`식 정상형 복원을 쓰지 않게 했다.
- [x] focused regression 41건, surface/semantic seed focused 3건, `py_compile`을 통과했다.
- [ ] 남은 HOLD 3건과 browser target 28건을 닫기 전까지 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 v347 action queue rerun

- [x] v345 action queue를 원본 JSONL source에서 post/comment/image source missing 없이 재구성했다.
- [x] combined rerun 15건을 VLM/OCR on, effective parallel `15`, shard lifecycle blocked 상태로 실행했다.
- [x] run manifest에서 completed/failed/pending `15/0/0`, image_post_count `7`, VLM/OCR `true/true`를 확인했다.
- [x] rerun Round2 relabel에서 `ACCEPT=7`, `HOLD=8`, `REJECT=0`, `REPROCESS=0`, `INFO_MISSING=0`을 확인했다.
- [ ] HOLD 8건과 browser target 28건을 닫기 전까지 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 v346 goal objective completion matrix

- [x] 원 objective를 current evidence 기준으로 완료 감사했다.
- [x] known-bad 4 current-code targeted canary와 10만 semantic approval을 분리했다.
- [x] 원본 result/manifest가 full approval source가 아니라 partial source임을 gate에 반영했다.
- [x] 남은 P0/P1 작업을 completed source 확보, expanded review, action queue 재처리, `11718083` human review로 정리했다.
- [ ] goal complete는 full/large source와 expanded semantic review가 증명되기 전까지 선언하지 않는다.

## 2026-05-31 v345 memory-query quote alignment bucket

- [x] `quote_alignment_missing_for_memory_query` bucket을 Round2 정성 리뷰 도구에 추가했다.
- [x] 후보 공식 페이지 hit와 원문 quote/source anchor 직접 정렬 근거를 분리해 `memory_query_quote_terms`, `quote_alignment_support_count`, `candidate_official_page_hits`로 남기게 했다.
- [x] LLM이 만든 `title_candidates`/`entity_mentions` 원문 echo는 quote alignment support로 세지 않게 했다.
- [x] focused regression 38건과 `py_compile`을 통과했다.
- [x] v345 original partial review artifact를 재생성해 source policy가 `final_result_json`, `large_run_complete=false`로 남는지 확인했다.
- [ ] expanded review에서 해당 bucket의 population/coverage/action 분포를 별도 집계한다.

## 2026-05-31 v344 표현 재해독 범용 후보 지침 재정정

- [x] `LLM_JUDGMENT_REVIEW.md`의 오래된 v195/v199/v210 항목을 현재 계약에 맞춰 `표현 오타/축약 패턴(범용)` 기준으로 정정했다.
- [x] `SCAN_RESULT_REVIEW_GUIDE.md`에 새 재검토 문서에서는 `X -> Y` 복원 예시를 쓰지 않는다는 지침을 추가했다.
- [x] `EXPERT_ORCHESTRATION_LIMITATIONS.md` 상단에 historical observation과 active rule을 분리하는 보강을 추가했다.
- [x] 재해독은 `표현 오타/축약 패턴`을 범용 후보로만 보고, 특정 표면어의 정상형을 새 reason/report에 쓰지 않는다고 재확인했다.
- [ ] 과거 깊은 history/result에 남은 구체 치환 문구는 historical artifact로만 두고, 새 prompt/report/reason에는 복원 예시로 재사용하지 않는다.

## 2026-05-31 v343 `11718083` strong quote search

- [x] `11718083` 원문 title/body, v341 result, VLM/OCR image evidence, search evidence catalog를 다시 확인했다.
- [x] exact quote와 변형 query로 외부 strong quote search를 수행했다.
- [x] `하차 이후의 소설 속` 공식 작품 페이지 후보는 존재하지만, 공개 synopsis가 `11718083`의 친구/위기/동료 대사를 직접 지지하지 않음을 확인했다.
- [x] `11718083`은 `official_title=null`, `unresolvable_memory_query`, `title_resolution_allowed=false` 유지가 현재 증거상 맞다고 정리했다.
- [ ] 실제 원작 회수는 자동 확정이 아니라 `human_review` 또는 더 강한 quote/full-text source가 필요하다.

## 2026-05-31 v342 목표 충족 감사

- [x] 원본 `out\expert_result_20260528_141006_620986_manifest.json`이 input `104502` 대비 completed `80`, flushed `71`, pending `9`인 partial run임을 재확인했다.
- [x] 원본 result는 rows_with_comments `55`이지만 `comment_metadata`, `comment_dialogue_context_lines`, image catalog가 모두 0인 것을 확인했다.
- [x] v341 current-code result는 댓글 있는 known-bad 2건에서 `comment_metadata`/`comment_dialogue_context_lines`를 보존하고, 이미지 post 3건에서 image catalog를 남긴 것을 확인했다.
- [x] `tests\inputs\test01.jsonl` 전체는 comment IP가 일부 있으나 post IP는 0건이고, known-bad 4건 자체에는 post/comment IP가 없음을 확인했다.
- [x] IP가 없는 동일 닉 댓글은 `author_match_unverified`로만 두고 독립 작품 evidence로 승격하지 않는 current-code 경계를 확인했다.
- [ ] `11718083` actual quote/title recall은 아직 `HOLD`이므로 strong quote search 또는 human review로 분리한다.
- [ ] 원본 partial run은 10만 semantic approval source로 쓰지 않는다.

## 2026-05-31 v341 known-bad 4 current-code 재실행

- [x] known-bad 4건 입력을 `v341_known_bad_4_current_code_input.jsonl`로 묶어 현재 코드 기준으로 다시 실행했다.
- [x] 실행 조건은 Gemma 4 4B, VLM/OCR on, `--parallel 36`, `--reuse-shards-only`, `--no-dashboard`, `--slang-db on`으로 기록했다.
- [x] manifest에서 completed/failed/pending `4/0/0`, requested/effective parallel `36/4`, `effective_parallel=min(requested_parallel,input_post_count)`를 확인했다.
- [x] small targeted run에서 Docker compose/shard lifecycle 재시작이 차단됐고 기존 shard `2/2`를 재사용했다.
- [x] `11718083`은 `네이버` 재승격 없이 `official_title=null`, `unresolvable_memory_query`, `title_resolution_allowed=false`를 유지했다.
- [x] `11718091`은 특정 치환 없이 `표현 오타/축약 패턴(범용)`로 남고 `context_only` title-null을 유지했다.
- [x] `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 clean alias positive-control을 유지했다.
- [ ] `11718083` actual quote/title recall은 strong quote search 또는 human review queue로 유지한다.
- [ ] 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 v340 known-bad 최신 goal 재확인

- [x] 원본 10만 결과에서 `11718083=네이버`, `11718091=Re:제로부터 시작하는 원신생존기`, `11718097=검미성 신작...`, `11718099=표지변경` 오판을 다시 확인했다.
- [x] v337 `11718083` 최신 run에서 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`, Slang DB flush `titles=0`을 확인했다.
- [x] v338 `11718097` 최신 run에서 `망겜의 힐러`, `https://novel.munpia.com/328421`, `망겜힐 -> 망겜의 힐러` clean alias 저장 후보를 확인했다.
- [x] v331 `11718091`은 범용 표현 재해독 후보 wording과 `context_only` title-null을 유지했다.
- [x] v334 `11718099`는 `빌어먹을 환생`과 문피아 URL을 유지하고 OCR conflict flags를 남겼다.
- [ ] `11718083`은 actual quote/title recall이 남아 있으므로 strong quote search 또는 human review queue로 유지한다.
- [ ] 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 유지한다.

## 2026-05-31 v339 표현 재해독 hardcode wording 재정렬

- [x] `_sanitize_surface_paraphrase_context`의 후단 정리 조건을 surface-specific context가 아니라 `surface_expression_context`로 정리했다.
- [x] 검색 제안 제거도 특정 `23세` 치환이 아니라 semantic review가 context-only/no-work로 낮춘 표현 재해독 후보와 generic surface probe 기준으로 동작하게 했다.
- [x] test fixture와 review packet fixture에서 `X -> Y`식 reason 문구를 제거하고 `표현 오타/축약 패턴(범용)`로 맞췄다.
- [x] 운영 지침 문서의 현재 규칙은 특정 표면어 변환이 아니라 packet-local 범용 표현 재독해 신호라는 표현으로 갱신했다.
- [ ] 기존 오래된 run result JSON/과거 이력에 남은 `X -> Y` 문구는 historical artifact로만 취급하고, 새 산출물/guide에는 deterministic rule처럼 재사용하지 않는다.

## 2026-05-31 v336 VLM/OCR direct title 말머리·exact-title slang guard

- [x] 검색 결과 제목 `스포) ... 리뷰 - 장르소설 마이너 갤러리`에서 게시글 말머리와 리뷰/커뮤니티 꼬리를 제거해 정식 작품명 후보가 오염되지 않게 했다.
- [x] exact-title surface는 작품 별칭이 아니므로 `slang_insight` 공개 출력에서 제외하고 Slang DB 저장도 하지 않는다.
- [x] `양파랑`처럼 VLM/OCR/Verifier가 작가명으로 식별한 surface는 BatchMem abbreviation으로 승격하지 않고 author mapping으로만 유지한다.
- [x] 대시보드에서는 저장 차단된 문장형/합성형 slang 후보를 `슬랭 후보(저장 차단)`으로 표시하고 정제 alias 후보와 원문 표면을 분리한다.
- [x] v336 `11718117` VLM/OCR-on live rerun에서 `아카데미의 피해자`, KakaoPage URL, `slang_insight=null`, Slang DB flush `titles=0`을 확인했다.
- [ ] expanded review에서 `title_prefix_contamination`, `exact_title_not_alias`, `author_surface_as_alias` bucket을 분리 집계한다.

## 2026-05-31 v334 OCR conflict notes overstatement guard

- [x] `analysis.notes`에서도 OCR 충돌 후보를 공식/비공식 별칭처럼 과장하지 않게 했다.
- [x] `11718099` v334에서 `빌환 -> 빌어먹을 환생`은 저장 후보로 유지하고 OCR/표지 충돌 후보는 본문/별칭/공식 제목 근거로 승격하지 않음을 확인했다.
- [x] v334 manifest에서 requested/effective parallel `36/1`, VLM/OCR `true/true`, small-run shard lifecycle blocked를 확인했다.
- [ ] expanded review에서 `analysis.notes`, `reason`, `slang_insight.cultural_context`의 OCR conflict 과장 여부를 같은 bucket으로 묶어 감사한다.

## 2026-05-31 v330 표현 오타/축약 범용 재해독 wording

- [x] public prompt payload에서 `surface_paraphrase_notes.paraphrase`를 숨기고 source surface + 범용 pattern scope만 전달하게 했다.
- [x] final semantic reread와 semantic seed review 지침에 `X -> Y`식 deterministic rewrite 금지를 명시했다.
- [x] 비관련 public reason 라벨을 `표현 오타/축약 패턴(범용)`로 바꿨다.
- [x] focused unittest와 `11718091` v331 live rerun에서 public reason/prompt에 deterministic paraphrase가 남지 않는지 확인했다.
- [ ] expanded review에서 `surface_expression_reread_candidate`는 특정 표면어 규칙이 아니라 범용 후보 bucket으로 집계한다.

## 2026-05-31 v329 OCR conflict cultural context 중화

- [x] final title과 충돌하는 OCR/표지 후보를 `reason`에서 보조 제목 근거 제외로 표시했다.
- [x] 같은 충돌 후보가 `slang_insight.cultural_context`에서 "본문에 병기된 다른 제목" 또는 "해당 작품 설정/2차 창작 단서"처럼 과장되지 않게 했다.
- [x] 처리는 특정 OCR 오타 문자열 치환이 아니라 final title과 image direct title 후보 mismatch 기반으로 동작한다.
- [x] `11718099` v329에서 `빌환 -> 빌어먹을 환생`은 유지하고 OCR 후보 `붉여먹을 혼성명`은 승격하지 않음을 확인했다.
- [x] `11718091` v329에서 deterministic paraphrase가 공개 reason에 남지 않음을 확인했다. v330부터 공개 reason 라벨은 범용 후보 표현으로 정정한다.
- [x] v329 manifest에서 completed/failed/pending `4/0/0`, requested/effective parallel `36/4`, VLM/OCR `true/true`, small-run shard lifecycle blocked를 확인했다.
- [ ] expanded review에서 OCR conflict flag와 `slang_insight` 문구 과장 여부를 함께 점검한다.

## 2026-05-30 v325 범용 재해독 힌트 / title prefix alias 오염 방지

- [x] 표현 오타/축약/띄어쓰기 재해독에서 코드가 특정 표면어의 deterministic paraphrase를 생성하지 않게 했다.
- [x] `surface_paraphrase_notes`는 packet-local `expression_typo_abbreviation_or_spacing_candidate` 힌트만 남기며, 작품명/별칭 evidence로 쓰지 않는다.
- [x] Orchestrator의 검색 pruning은 age 전용 규칙이 아니라 `surface_expression_reread` 후보와 semantic review 경계를 기준으로 동작한다.
- [x] 긴 OCR/VLM 제목 표면 변형과 공식 제목 prefix를 BatchMem alias로 학습하지 않게 했다.
- [x] 실제 제목 약칭 positive-control인 `즉사무림`은 계속 alias로 학습되는지 확인했다.
- [x] v325 `11718080/11718082` VLM/OCR on canary를 `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- [x] v325 `11718082`는 공식 제목 `재벌가 차녀의 2회차 걸그룹`으로 유지되고, `재벌가 차녀의 2회차`/`결그룹` alias 즉시등록 신호가 없음을 확인했다.
- [x] v325 `11718080`은 title null/adjacent로 유지됐다.
- [ ] expanded review에서 `surface_expression_reread_candidate`, `final_semantic_reread_*`, `abbreviation_title_variant_surface_skipped`를 분리 집계한다.

## 2026-05-30 v311 OCR/VLM 표면형 official detail 재정렬

- [x] `11718082`에서 OCR/VLM 표면형 `재벌가 차녀의 2회차 결그룹`이 locked official detail 후보보다 우선되는 회귀를 확인했다.
- [x] 특정 제목/오타 하드코딩 없이, 동일 official detail URL의 locked 공식 후보가 OCR/VLM 표면 alias/variant보다 우선되도록 했다.
- [x] 같은 URL의 표면형 duplicate reference가 `mentioned_works`, `comparison_target`, `recommendation_candidates`, `future_watch_target`에 별도 작품처럼 남지 않게 했다.
- [x] `11718080/11718082`를 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- [x] v311 manifest에서 completed/failed/pending `2/0/0`, requested/effective parallel `36/2`, small-run shard lifecycle blocked를 확인했다.
- [x] v311 결과에서 `11718082`는 `재벌가 차녀의 2회차 걸그룹` resolved, `11718080`은 trope/social-lament title-null로 유지됨을 확인했다.
- [ ] expanded review에서 `official_detail_title_preferred_over_surface_form`과 `surface_form_duplicate_reference_pruned` flag를 VLM/OCR 표면형 오염 bucket으로 분리 집계한다.

## 2026-05-30 v308 known-bad 4 unverified author context

- [x] `author_match_unverified` 댓글을 원글 작성자 댓글로 확정하지 않는 기존 경계를 유지했다.
- [x] 동시에 `author_match_unverified`만 있는 짧은 캐릭터 반응 댓글은 독립 작품 evidence로 강화하지 않도록 `comment_author_match_unverified_not_independent_evidence` flag를 추가했다.
- [x] `11718083`, `11718091`, `11718097`, `11718099`를 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 재실행했다.
- [x] manifest에서 completed/failed/pending `4/0/0`, requested/effective parallel `36/4`, `vlm_ocr_semantic_review_ready=true`, small-run shard lifecycle blocked를 확인했다.
- [x] v308 결과에서 `11718083`은 memory-query title-null, `11718091`은 context-only title-null, `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 확인했다.
- [ ] expanded review에서 `author_match_unverified` 댓글이 독립 작품 evidence처럼 사용되는지 별도 bucket으로 감시한다.

## 2026-05-30 v307 `11718117` regression state audit

- [x] v292 result/log/manifest를 재확인해 `11718117`이 resolved 상태인지 확인했다.
- [x] VLM/OCR direct image evidence가 작품명 `아카데미의 피해자`, 작가 `양파랑`, 회차 `268 테세우스의 배 (6)`를 읽었음을 로그로 확인했다.
- [x] final이 KakaoPage URL `https://page.kakao.com/content/66611775?tab_type=product`, `anchor_type=image`, `anchor_strength=high`를 유지함을 확인했다.
- [x] exact-title surface는 `store_in_slang_db=false`, `store_reason=exact_title_not_alias`, Slang DB flush `titles=0`로 alias 오염이 재현되지 않음을 확인했다.
- [ ] expanded review에서 direct image explicit title bucket은 weak visual-only bucket과 분리 집계한다.

## 2026-05-30 v306 `11718114` visual-only evidence closeout

- [x] Codex in-app Browser 경로를 재시도했으나 `windows sandbox failed: spawn setup refresh`로 연결이 다시 실패함을 확인했다.
- [x] v286에서 받은 직접 이미지 파일 `browser_v286\post11718114_direct_image.jpg`를 다시 시각 확인했다.
- [x] 이미지는 게임/영상 장면 + `HONEYCAM.ORG` 워터마크이며, 작품명/작가명/회차/OCR title direct evidence가 없음을 확인했다.
- [x] v286 result의 `official_title=null`, `title_resolution_state=adjacent`, `title_resolution_allowed=false`, `anchor_type=genre`, `anchor_strength=low`를 semantic 결과로 수용했다.
- [ ] Browser tool health는 semantic issue와 분리해 환경 follow-up으로 추적한다.

## 2026-05-30 v305 `11718078` positive alias control

- [x] `11718078`을 VLM/OCR on, `--parallel 36 --reuse-shards-only --no-dashboard`로 단건 재실행했다.
- [x] manifest에서 completed/failed/pending `1/0/0`, requested/effective parallel `36/1`, Docker/shard auto up/recreate `false/false`를 확인했다.
- [x] final이 `즉사기 들고 무림에 떨어지다`, `title_resolution_state=resolved`, `anchor_type=title_exact`, `anchor_strength=high`로 유지됨을 확인했다.
- [x] `즉사무림`은 packet-local 오타/축약 후보 해석이 아니라 제목 약칭 + 공식 URL evidence가 있는 positive-control로 분리했다.
- [ ] expanded review에서 title alias positive-control과 context-only/no-work 재해독 bucket을 계속 분리 집계한다.

## 2026-05-30 v304 재해독 표현 범위 정정

- [x] final semantic reread prompt에서 전역 규칙처럼 읽힐 수 있는 표현을 제거하고, 특정 표면어를 다른 post에 재사용하지 않는다고 명시했다.
- [x] semantic seed review prompt도 `해당 packet 문맥 안의 후보 해석`으로 좁혔다.
- [x] 회귀 테스트가 `후보 해석`, `다른 post에 재사용하지 않음` 문구를 확인하도록 갱신했다.
- [x] `tests.test_final_semantic_reread_gate` 9건과 py_compile을 통과했다.
- [ ] expanded review에서 후보 해석이 `slang_db` alias/search seed/title evidence로 승격되는 오염을 계속 감시한다.

## 2026-05-30 v303 OCR-noise visual-only image anchor guard

- [x] v302에서 reason은 `grounding_anchor=search_only`인데 public JSON이 `anchor_type=image`, `anchor_strength=medium`으로 남는 mismatch를 확인했다.
- [x] OCR 잡음이 있는 `character_visual_only` 이미지도 `promotion_eligible=false`, direct title/author 없음이면 weak visual-only로 유지되게 했다.
- [x] v302 형태의 `ocr_text` + `work_cues` + `focus_role=supporting_text`를 VLM anchor regression에 반영했다.
- [x] v303 live canary에서 `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`, `anchor_type=none`, `anchor_strength=none`을 확인했다.
- [x] v303 manifest에서 requested/effective parallel `36/1`, VLM/OCR `true/true`, Docker/shard auto up/recreate `false/false`를 확인했다.
- [x] 재해독 prompt/test/docs에서 일괄 적용처럼 보이는 표현을 제거하고 packet-local 후보 해석/evidence boundary 표현으로 정리했다.
- [ ] expanded review에서 `weak_visual_only_promoted_to_image_anchor`, `ocr_noise_visual_anchor_mismatch`, `image_evidence_catalog_missing`을 분리 집계한다.
- [ ] `11718083` quote recall true-title 회수는 strong quote search 또는 human review 전까지 `HOLD`로 유지한다.

## 2026-05-30 v301 weak visual-only image anchor guard

- [x] `11718083` v214에서 final title은 null인데 `anchor_type=image`, `anchor_strength=medium`이 남는 field mismatch를 확인했다.
- [x] VLM 실행 여부와 image primary anchor를 분리했다.
- [x] `character_visual_only`/OCR-title 없음/`promotion_eligible=false` 이미지는 작품 grounding anchor로 승격하지 않게 했다.
- [x] v301 live canary에서 VLM/OCR on, title null, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`를 확인했다.
- [x] v301 result에 `image_evidence_catalog_count=1`이 남고 `anchor_type=image`가 사라진 것을 확인했다.
- [x] VLM anchor regression, VLM 주변 회귀, memory-query focused regression, py_compile을 통과했다.
- [ ] expanded review에서 `weak_visual_only_promoted_to_image_anchor` bucket을 감시한다.
- [ ] `11718083`의 실제 원작 quote/title 회수는 strong quote search 또는 human review 없이는 계속 `HOLD`로 둔다.

## 2026-05-30 v300g packet-local semantic reread wording

- [x] 오타/축약/띄어쓰기 깨짐 가능성을 표면 패턴 일반 규칙으로 승격하지 않도록 prompt 문구를 정정했다.
- [x] final semantic reread prompt에 특정 표면어를 고정 규칙으로 만들거나 다른 post에 재사용하지 않는다고 명시했다.
- [x] semantic seed review prompt에 해당 packet 문맥 안에서만 후보 해석으로 검토한다고 명시했다.
- [x] `SCAN_RESULT_REVIEW_GUIDE.md`의 전역 규칙처럼 보이는 표현을 packet-local 후보 해석/evidence boundary 기준으로 교체했다.
- [x] final semantic reread tests 9건과 py_compile을 통과했다.
- [ ] expanded review에서 packet-local meaning-pass가 과차단/미차단을 만들지 않는지 계속 감시한다.

## 2026-05-30 v300f live prompt/reason proof

- [x] `LLM_DEBUG_DUMP_MESSAGES=1` live canary로 `discourse_semantic_seed_guard` 실제 요청 본문을 확인했다.
- [x] `comment_context`, `comment_dialogue_context`, `role=author_match_unverified`, `surface_paraphrase_notes`가 prompt payload에 포함됐다.
- [x] 짧은 인명/캐릭터명 단독 seed와 일반어 검색 조합은 직접 작품 앵커 없이 keep하지 않도록 prompt/test/docs를 보강했다.
- [x] 직접 작품 앵커 없는 public reason에서 `작품 속/작품 내`류 표현을 약한 문맥 표현으로 낮추는 일반 후처리를 추가했다.
- [x] v300f final은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 유지했다.
- [x] final semantic reread tests 9건과 py_compile을 통과했다.
- [ ] expanded review에서 `reason_overstates_context_only`와 `character_name_only_search_keep`를 high-risk bucket으로 감시한다.

## 2026-05-30 v299 comment dialogue payload key

- [x] `comment_context_lines`/`comment_dialogue_context_lines`가 semantic seed review payload에 전달되는지 확인했다.
- [x] `comment_context`/`comment_dialogue_context`가 없으면 `*_lines`를 fallback으로 쓰게 했다.
- [x] final semantic reread payload에도 댓글 speaker/author/ip role line을 포함했다.
- [x] `author_match_unverified`는 대화 흐름 힌트이며 작품 근거나 원글 작성자 확정 근거가 아님을 유지했다.
- [x] final semantic reread tests 8건, comment metadata tests 4건, qualitative review packet tests 35건, py_compile을 통과했다.
- [x] v300f live canary에서 실제 vLLM payload/log 기준으로 comment dialogue line 포함 여부를 재확인했다.

## 2026-05-30 v298 semantic reread fixed-rule wording

- [x] `11718091` 회귀 입력을 특정 문자열 차단이나 표면 패턴 확정 규칙으로 고정하지 않도록 prompt wording을 정정했다.
- [x] 표현 오타/축약/띄어쓰기 깨짐은 해당 packet의 title/body/comment 안에서만 세우는 가설이며, 그 해석만으로 작품명 evidence를 만들지 않는다고 명시했다.
- [x] 짧은 인명/캐릭터명 단독 seed와 일반어 검색 조합은 작품 식별 근거가 아니며, 직접 작품 앵커가 없으면 재해독에서 context-only/drop으로 보게 했다.
- [x] 직접 작품 앵커가 없을 때 reason이 `작품 속` 같은 표현으로 작품 존재를 확정하지 않도록 지침을 추가했다.
- [x] `surface_paraphrase_notes`만으로는 seed/search를 내리지 않고, LLM semantic seed review가 no-work/context-only 위험을 표시한 경우에만 sanitizer가 보조 적용되게 했다.
- [x] deterministic regex 확장은 되돌려 새 표면 패턴 규칙을 추가하지 않았다.
- [x] final semantic reread tests는 v300f 기준 9건, qualitative review packet tests 35건, py_compile을 통과했다.
- [ ] expanded semantic review에서 meaning-pass 과차단/미차단을 분리 확인한다.

## 2026-05-30 v297 goal objective completion audit

- [x] 원본 `out\expert_result_20260528_141006_620986.json`이 partial artifact인지 manifest로 재확인했다.
- [x] 원본 wrong-title 4건과 current targeted/v296 결과를 요구사항별로 대조했다.
- [x] `11718097`과 `11718099`는 targeted review 기준 회복됐음을 확인했다.
- [x] `11718083`과 `11718091`은 wrong-title 방어는 됐지만 각각 memory-query recall, author/IP unverified dialogue로 HOLD임을 분리했다.
- [ ] `11718083` quote recall과 `11718091` author/IP dialogue bucket이 남아 있으므로 active goal을 complete로 닫지 않는다.
- [ ] 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v296 goal known-bad semantic review tooling

- [x] v296 after-review를 재생성해 `11718099`가 `ACCEPT / no_action`으로 정리됐는지 확인했다.
- [x] `설정(캐릭터 구성, 장르)` 같은 reason 설명문 괄호를 `generic_parenthetical_bridge`로 오탐하지 않게 했다.
- [x] `11718097`의 minor alias counter를 true critical contradiction과 분리했다.
- [x] `23센줄`류 non-relevant reason에서 "작품 자체에 대한 논의" 과잉 표현이 남지 않게 가드를 추가했다.
- [x] final semantic reread tests 6건, focused semantic reason tests 3건, qualitative review packet tests 35건, py_compile을 통과했다.
- [ ] `11718083` memory-query recall과 `11718091` author/IP unverified dialogue는 expanded review/human review queue로 유지한다.
- [ ] 10만 건 semantic gate는 계속 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v294 semantic reread / critical-counter 재확인

- [x] `23센줄`류 표면은 표현 오타/축약 패턴(범용)로 먼저 읽는 계약을 재확인했다.
- [x] 현재 경로가 `surface_paraphrase_notes`, `discourse_semantic_seed_guard`, `final_semantic_reread`의 세 층으로 동작함을 확인했다.
- [x] `tests.test_final_semantic_reread_gate` 5건을 통과했다.
- [x] `tests.test_expert_main_comment_metadata` 4건을 통과했다.
- [x] v287 `11718091` live evidence에서 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`가 유지됨을 재확인했다.
- [x] `11718097`의 `critical_counter_but_resolved`는 true critical counter가 아니라 `망겜힐` 약칭과 `망겜의 힐러` 정식명 차이를 minor note로 남긴 경우임을 확인했다.
- [x] `critical_counter_but_resolved` bucket을 minor alias normalization과 true critical counter로 분리했다.
- [ ] 10만 건 semantic gate는 계속 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v291 BatchMem exact-title alias guard

- [x] v290 `11718117`은 운영 `slang_db` 저장이 아니라 BatchMem 내부 exact-title alias 등록 노이즈였음을 분리했다.
- [x] normalized alias와 normalized title이 같으면 resolved/pending BatchMem alias로 등록하지 않게 했다.
- [x] clean alias 학습이 유지되는지 BatchMem 회귀 테스트로 확인했다.
- [x] final semantic reread와 VLM URL focused regression도 함께 통과했다.
- [x] v292 live run에서 exact-title surface가 `BatchMem: 약칭 즉시등록` 로그로 남지 않는지 확인했다.
- [x] v292에서 VLM/OCR direct evidence와 KakaoPage URL recovery가 유지되는지 확인했다.
- [ ] 이 변경만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-30 v290 `11718117` image platform URL recovery

- [x] `11718117` VLM/OCR direct evidence가 작품명 `아카데미의 피해자`, 작가 `양파랑`, 플랫폼 `KAKAO PAGE`를 포함하는지 확인했다.
- [x] promotable image title/author 검증 검색이 image-only seed pruning에서 제거되지 않게 했다.
- [x] `원작 주인공`은 웹소설 소개문 안의 서사 표현일 수 있으므로 단독 derivative marker로 보지 않게 했다.
- [x] 기존 `원작 소설 기반 웹툰`류 non-novel media 차단 테스트가 유지되는지 확인했다.
- [x] v290 run에서 `novel_identity.heretic_url`과 `primary_work.heretic_url`이 `https://page.kakao.com/content/66611775`로 맞는지 확인했다.
- [x] `23센줄 -> 23세인 줄` final semantic reread regression 5건을 통과했다.
- [x] 10만 건 semantic gate는 targeted canary만으로 올리지 않고 `REVIEW-LOCKED`로 유지했다.

## 2026-05-30 v286/v287 VLM limit / meaning pass recheck

- [x] `11718114` 이미지 `8428632` bytes가 `expert_main.py` 8MiB 기본값 때문에 VLM skip되던 원인을 확인했다.
- [x] `expert_main.py` 기본 `LLM_VLM_MAX_IMAGE_BYTES`를 pipeline 기본 `16777216`과 맞췄다.
- [x] v286 `11718114` rerun에서 VLM chunk request가 발생하고 visual-only/title-null 판단이 유지됨을 확인했다.
- [x] v287 `11718091` rerun에서 `--parallel 36` 요청이 입력 1건 기준 `effective_parallel=1`로 줄고 Docker shard auto up/recreate가 꺼져 있음을 확인했다.
- [x] v287 `11718091`에서 1차 Discourse의 `은영이`, `23센줄` seed와 `은영이 23세 소설` 검색 제안이 2차 meaning pass 뒤 제거됨을 확인했다.
- [x] final public reason에 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄`, `작품 seed 제외: 23센줄, 은영이`가 남는지 확인했다.
- [x] `11718091` final은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 유지했다.
- [x] `11718117` direct image title + author에서 official URL missing/플랫폼 URL 불일치 경로를 v290에서 닫았다.
- [ ] expanded review에서 meaning-pass 과차단/미차단 bucket을 분리 확인한다.
- [ ] 10만 건 semantic gate는 계속 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v284/v285 residual semantic review

- [x] v284 residual P0/P1 21건을 VLM/OCR on, `--parallel 36`, `--reuse-shards-only`로 재실행했다.
- [x] manifest에서 `effective_parallel=21`, Docker Compose auto up/recreate false, completed/failed/pending `21/0/0`을 확인했다.
- [x] `11718091`은 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄` 의미 재독해와 final title null/context-only를 유지했다.
- [x] `11718080`은 친구/밥/같이 소설 보는 친구 한탄형 글로 보고 title null/adjacent 유지됨을 확인했다.
- [x] Round2 리뷰 도구가 제목 약칭 + 공식 상세 URL 케이스를 `reason_says_no_anchor_but_resolved` REJECT로 과잉 분류하지 않게 수정했다.
- [x] `tests.test_qualitative_review_packet_tools` 33건, `tests.test_final_semantic_reread_gate` 5건, `py_compile`을 통과했다.
- [ ] `11718114` image too-large/weak VLM state를 Browser visual evidence 또는 downscale/fetch 처리로 닫는다.
- [x] `11718117` direct image title의 official URL missing을 v290 re_search/live canary로 닫았다.
- [x] `11718082` OCR/slang_db alias pollution 여부를 v293 subtype review로 확인했다. OCR 오타 표면은 public evidence에 남지만 운영 `slang_db` 저장은 없었다.
- [x] `11718097` `critical_counter_but_resolved`는 v294에서 minor alias normalization counter로 분리했다.
- [ ] expanded random/high-risk review 전까지 10만 건 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-30 v280 final meaning/url guard

- [x] `11718091`의 `23센줄`은 `23세인 줄` meaning pass로 처리하고 문자열 하드코딩 차단을 추가하지 않았다.
- [x] `11718091` v280 live canary에서 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 확인했다.
- [x] final freeze가 제거한 stale `heretic_url`을 호출부가 `or heretic_url`로 다시 복구하지 않게 했다.
- [x] BatchContext alias rescue가 candidate/existing URL을 쓰기 전에 title-compatible official detail URL인지 검사하게 했다.
- [x] `11718097` v280 live canary에서 wrong URL `https://book.novelpia.com/novel/13336`이 재오염되지 않고 `https://novel.munpia.com/328421`로 정리됨을 확인했다.
- [x] `tests.test_final_semantic_reread_gate` 3건과 `py_compile`을 통과했다.
- [x] v280 manifest에서 `--parallel 36`이 입력 4건 기준 `effective_parallel=4`로 줄고 Docker shard auto up/recreate가 꺼져 있음을 확인했다.
- [ ] expanded review에서 `batch_memory_alias_stale_official_url_cleared`, `official_detail_url_title_mismatch_cleared`, `official_detail_url_repaired_from_search` bucket을 분리 집계한다.
- [ ] v280은 targeted known-bad canary다. 10만 건 semantic approval로 승격하지 않는다.

## 2026-05-30 v278 final semantic reread gate

- [x] `23센줄`류는 검색 seed 문제가 아니라 자연어 의도 재독해 문제임을 재확인했다.
- [x] 검색 전 `discourse_semantic_seed_guard`와 별도로, 후단에서 final title이 살아남은 high-risk resolved output에 `final_semantic_reread` gate를 추가했다.
- [x] `semantic_seed_review`/`surface_paraphrase`/`context_only_no_work_anchor` risk가 있으면 final candidate, title/body/comment, evidence, image evidence를 함께 LLM에 전달한다.
- [x] `REJECT/HOLD/REPROCESS` 또는 `is_specific_work_discussion=false + Weak/Missing evidence`이면 final title을 null로 낮추고 `final_semantic_reread_rejected_resolution` 또는 `final_semantic_reread_reprocess_resolution` flag를 남긴다.
- [x] 원문 직접 title+official evidence, direct image/VLM title promotion은 별도 강한 앵커로 보아 불필요한 재흔들림을 피한다.
- [x] `tests/test_final_semantic_reread_gate.py` 전용 회귀 테스트로 `23센줄 -> 23세인 줄` context-only 재독해 후 search-only 후보 demotion을 확인했다.
- [x] focused semantic reread 4건과 social-lament/semantic seed regression 7건을 통과했다.
- [ ] expanded review에서 `final_semantic_reread_reviewed`, `final_semantic_reread_rejected_resolution`, `final_semantic_reread_accepted_resolution` bucket의 과차단/미차단을 별도 집계한다.
- [ ] v278은 focused regression이다. 10만 건 semantic approval로 승격하지 않는다.

## 2026-05-30 v277 comment metadata coverage audit

- [x] `tools\audit_comment_metadata_coverage.py`를 추가했다.
- [x] source JSONL의 post/comment IP coverage와 duplicate comment id를 산출했다.
- [x] result JSON의 `comment_metadata`, `comment_dialogue_context_lines`, `post_ip`, `image_evidence_catalog` coverage를 산출했다.
- [x] `tests\inputs\test01.jsonl` 기준 post row IP가 `0/104517`임을 확인했다.
- [x] comment row IP는 `70337/368334`, comment IP가 있는 post는 `37656`개임을 확인했다.
- [x] original partial 71행은 comments 55행이 있어도 comment metadata/dialogue/image catalog가 0임을 확인했다.
- [x] v267 24행은 comments/meta/dialogue `16/16/16`, image/catalog `13/13`으로 개선됐음을 확인했다.
- [x] `11718091` duplicate comment id가 source에는 1건 있으나 current loader에서는 1건으로 dedupe되는지 확인했다.
- [x] coverage tool tests 3건과 syntax check를 통과했다.
- [ ] post IP가 필요한 "원글 작성자 댓글 확정"은 crawler/source 단계에서 post IP 확보 가능성을 별도 확인한다.
- [ ] 새 completed source에서 v277 coverage audit를 다시 실행한다.

## 2026-05-30 v276 comment metadata loader/output

- [x] `expert_main.py` public result row에 `ip`, `author_ip`, `post_ip`를 남기게 했다.
- [x] `load_jsonl_posts()`가 post/comment `post_id` 숫자/문자열 혼합에도 댓글을 연결하도록 정규화했다.
- [x] comment row는 `comment_id` 우선으로 중복 제거한다.
- [x] `11718091` 원본 입력 재구성에서 중복 댓글이 2건이 아니라 1건으로 정리되는지 확인했다.
- [x] `11718097` 원본 입력 재구성에서 댓글 5건과 dialogue context가 보존되는지 확인했다.
- [x] `11718117` 원본 입력 재구성에서 IP 있는 익명 댓글과 IP 없는 익명 댓글을 다른 speaker로 분리하는지 확인했다.
- [x] `tests.test_expert_main_comment_metadata` 4건, known-bad focused regression 포함 20건, `py_compile`을 통과했다.
- [ ] 새 completed source에서 `comment_metadata`, `post_ip`, `comment_dialogue_context_lines` 누락률을 다시 산출한다.
- [ ] 결과 row에 post/comment metadata가 있어도 작성자/IP 자체를 작품 identity evidence로 승격하지 않는다.

## 2026-05-30 v269 v264 VLM/OCR action rerun

- [x] v268 preflight가 `--parallel 36`을 max로 보고 `endpoint_count_expected=8`, `mcp_full_shard_readiness=NO-GO`를 분리하도록 고쳤다.
- [x] preflight tests 3건과 `py_compile`을 통과했다.
- [x] v264 rerun combined 24건을 Gemma 4 4B, `--parallel 36 --reuse-shards-only --no-dashboard --server-type vllm --slang-db on --vlm on --ocr on`으로 실행했다.
- [x] manifest에서 `requested_parallel=36`, `effective_parallel=24`, `mcp_requested_endpoint_count_before_health_filter=8`, `completed/failed/pending=24/0/0`을 확인했다.
- [x] manifest에서 `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count=13`, `vlm_ocr_semantic_review_ready=true`를 확인했다.
- [x] `11718080`은 사회적 한탄/장르 잡담으로 읽고 특정 작품으로 확정하지 않았다.
- [x] `11718082`는 VLM/OCR image catalog를 통해 `재벌가 차녀의 2회차 걸그룹`으로 회복했다.
- [x] `11718083`은 대사 기억 회수 요청으로 두고 임의 title 확정을 막았다.
- [x] `11718091`은 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄` 의미 재독해를 reason에 남기고 작품 seed를 제외했다.
- [x] `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 회복했다.
- [ ] `11718094`의 generic abstract title collision을 P1 bucket으로 분리한다.
- [ ] `11718117`의 OCR explicit title unresolved를 P1 bucket으로 분리한다.
- [ ] v269는 targeted 24건 재런이다. 10만 건 semantic approval로 승격하지 않는다.

## 2026-05-30 v266 v264 rerun readiness

- [x] v264 rerun combined input 24건 manifest를 다시 확인했다.
- [x] vLLM endpoint `http://10.20.0.101:8000/v1/models`가 Gemma 4 4B model을 반환함을 확인했다.
- [x] 관련 `python.exe` 점유 프로세스가 없음을 확인했다.
- [x] Docker/TCP 기준 MCP ports `3333..3337`만 열려 있고 `3338..3368`은 닫혀 있어 `OPEN_COUNT=5/36`임을 확인했다.
- [x] `warp_shards.py status --json`은 Docker Desktop pipe access denied로 실패함을 기록했다.
- [x] `tools\warp_shards.py up --count 36` escalated 실행 요청은 abort되어 shard 기동하지 않았음을 기록했다.
- [ ] 36 shard 준비 전까지 v264 24건 재런 결과를 36-shard 품질 검증으로 쓰지 않는다.
- [ ] 36 shard 준비 후 v264 rerun combined 24건을 VLM/OCR on으로 실행한다.

## 2026-05-30 v265 의미 재독해 경로 재확인

- [x] `23센줄`은 `23세인 줄` 오타/축약으로 먼저 읽어야 하며 작품명/별칭 seed가 아님을 재확인했다.
- [x] 현재 경로가 `surface_paraphrase_notes`를 만들고 `discourse_semantic_seed_guard`를 한 번 더 실행하는 구조임을 확인했다.
- [x] semantic guard가 context-only/drop으로 낮춘 seed는 `title_novel_terms`와 `search_suggestions`에서 제거되는지 확인했다.
- [x] 강한 작품 앵커나 이미지/VLM 문맥이 없으면 Decoder/search 재승격이 조기 차단되는 구조를 확인했다.
- [x] 사회적 한탄/장르 잡담도 meaning pass 대상임을 focused regression으로 확인했다.
- [x] focused regression 5건을 통과했다.
- [x] v265 한국어 확인 산출물 `qualitative_review\20260528_141006_620986\v265_semantic_reread_reconfirmation_ko.md`를 작성했다.
- [ ] v265는 targeted 확인이다. 10만 건 semantic approval로 승격하지 않는다.
- [ ] action queue 재판정 시 `re_judge` 실행 전에 title/body/comment/comment_context 기반 의미 재독해 packet을 먼저 본다.

## 2026-05-30 v264 v263 action input 준비

- [x] v263 `action_queue.json`을 새 action input builder로 읽을 수 있게 했다.
- [x] action queue JSON array와 기존 JSONL remaining queue를 모두 지원하게 했다.
- [x] 원본 result JSON source에서 이미지 source 누락 37건이 발생하는 것을 확인했다.
- [x] `tests\inputs\test01.jsonl` source에서 post `content_blocks`와 comment row를 복원하게 했다.
- [x] from-input v264 action inputs를 생성했고 `image_source_missing_post_ids=0`을 확인했다.
- [x] `rerun_combined=24`, `browser_targets=37`, `human_review=56`, `slang_db_review=7`을 확인했다.
- [x] related Python 점유 프로세스가 없음을 확인했다.
- [x] Docker shard는 현재 5개만 떠 있음을 확인했다.
- [x] qualitative packet tests 30건과 `py_compile`을 통과했다.
- [ ] 36 shard 준비 후 `v264_v263_action_from_input_rerun_combined_input.jsonl`을 VLM/OCR on으로 재실행한다.
- [ ] `v264_v263_action_from_input_browser_targets.jsonl` 37건을 Codex in-app Browser 또는 동등 시각 증거로 확인한다.

## 2026-05-30 v263 original partial 최신 정성 리뷰 재산출

- [x] 원본 `out\expert_result_20260528_141006_620986.json` manifest를 재확인했다.
- [x] `input_post_count=104502`, `completed_count=80`, `flushed_count=71`, `pending_count=9`라서 원본 source가 partial임을 다시 확인했다.
- [x] `random_control`을 먼저 만든 뒤 Round2를 돌려도 high-risk sample이 0건으로 사라지지 않게 했다.
- [x] `random_control` label이 내부 high-risk bucket policy를 적용하도록 했다.
- [x] v263 preflight와 review 산출물을 생성했다.
- [x] v263에서 known-bad 6건이 `REJECT`/`REPROCESS`/`HOLD`로 분리되는지 확인했다.
- [x] qualitative packet tests 28건과 `py_compile`을 통과했다.
- [ ] v263은 원본 partial 71행 재분류다. 10만 건 semantic approval로 승격하지 않는다.
- [ ] 새 completed source에서 v263과 같은 bucket policy로 random/high-risk coverage를 다시 산출한다.

## 2026-05-30 Round2/random image evidence catalog gate

- [x] Round2 `evidence_catalog`가 `identity.image_evidence_catalog`를 구조화 evidence로 포함하게 했다.
- [x] `image_evidence_catalog_missing` high-risk bucket을 추가했다.
- [x] 이미지/VLM/OCR 근거가 필요한데 catalog가 없으면 `REPROCESS`/`re_run` 또는 `human_review`로 가도록 label 정책을 추가했다.
- [x] Round2 packet에 `content_blocks`, `image_urls`, `image_count`, `image_evidence_catalog` 계열 필드를 남기게 했다.
- [x] random control packet에도 같은 VLM/OCR 공개 필드를 남기게 했다.
- [x] focused tests 2건, packet tools 26건, `py_compile`을 통과했다.
- [x] v259 실제 결과에서 `11718082`는 catalog present, `11718080`은 image bucket 없음으로 확인했다.
- [ ] 새 completed source에서 `image_evidence_catalog_missing` population과 selected coverage를 다시 산출한다.
- [ ] 이 tooling 검증만으로 10만 건 semantic gate를 `GO`로 올리지 않는다.

## 2026-05-30 v259 social-lament/VLM evidence schema 재검증

- [x] `11718080/11718082` 2건을 Gemma 4 4B vLLM, VLM/OCR on 조건으로 재실행했다.
- [x] `--parallel 36`을 상한으로 호출하되 입력 2건에서 `effective_parallel=2`로 줄어드는지 확인했다.
- [x] `--reuse-shards-only` 기준 Docker/shard auto up/recreate가 꺼져 있고 small-run lifecycle block이 켜져 있음을 manifest로 확인했다.
- [x] `11718080`에서 `discourse_semantic_seed_guard`가 한 번 더 실행되고, `TS/갈드컵/소설` 검색 seed가 특정 작품으로 승격되지 않는지 확인했다.
- [x] `11718080` 최종이 `official_title=null`, `discussion_type=trope_discussion`, `title_resolution_allowed=false`로 유지됨을 확인했다.
- [x] `11718082`에서 VLM chunk request/result가 실제로 발생하고, 이미지 OCR/검색으로 `재벌가 차녀의 2회차 걸그룹`을 확정함을 확인했다.
- [x] 결과 JSON에 `content_blocks`, `image_urls`, `image_count`, `identity.image_evidence_catalog`가 남는지 확인했다.
- [x] 이미지 없는 글에는 status-only `image_evidence_catalog`를 남기지 않게 했다.
- [x] focused unittest와 `py_compile`을 통과했다.
- [x] v259 한국어 리뷰 산출물 `qualitative_review\20260528_141006_620986\v259_post11718080_11718082_schema_review_ko.md`를 작성했다.
- [ ] v259는 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.
- [ ] expanded review에서 `VLM_OCR_involved`와 `image_evidence_catalog_missing`을 함께 집계한다.

## 2026-05-30 v256 known-bad 4건 VLM/OCR-on 재검증

- [x] Gemma 4 4B vLLM 기준 `expert_main.py --parallel 36`을 상한으로 호출했다.
- [x] 입력 4건에서 `effective_parallel=4`로 줄어드는지 manifest로 확인했다.
- [x] `--reuse-shards-only` 기준 Docker/shard auto up/recreate가 꺼져 있음을 확인했다.
- [x] VLM/OCR on 상태에서 `11718083`, `11718091`, `11718097`, `11718099`를 재실행했다.
- [x] `11718091`은 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄`로 자연어 재독해되고 title null/context-only로 유지됨을 확인했다.
- [x] `11718091` 댓글은 IP 확인이 없으므로 `post_author`가 아니라 `author_match_unverified`로 남는지 확인했다.
- [x] `11718097`은 `망겜의 힐러`, `11718099`는 `빌어먹을 환생`으로 회복됨을 확인했다.
- [x] `11718099`는 OCR title conflict를 final title 근거로 쓰지 않고 구조 flag로 남김을 확인했다.
- [x] v256 한국어 리뷰 산출물 `qualitative_review\20260528_141006_620986\v256_known_bad_4_after_comment_attribution_review_ko.md`를 작성했다.
- [ ] v256은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.
- [ ] `search_degraded_or_timeout`, `VLM_OCR_involved`, `context_only_no_work_anchor`, `comment_author_match_unverified_dialogue` bucket을 새 completed source에서 다시 집계한다.

## 2026-05-30 v255 comment author/IP attribution

- [x] `tests\inputs\test01.jsonl` 원본 입력에서 post/comment row와 comment author/IP 분포를 계측했다.
- [x] 20260528 원본 result 71 rows에서 댓글이 있는 row 55건 모두 `comment_metadata/comment_context_lines/comment_dialogue_context_lines`가 없음을 확인했다.
- [x] 익명/공통 author는 IP 확인 없이는 `role=post_author`로 확정하지 않게 했다.
- [x] author 문자열은 같지만 IP 확인이 없으면 `post_author_match_unverified=true`, `role=author_match_unverified`를 남기게 했다.
- [x] `11718091` current-code 재구성에서 `speaker=user1`, `role=author_match_unverified`, `is_post_author=false`를 확인했다.
- [x] `11718097` current-code 재구성에서 `ㅇㅇ` 댓글 4건은 미확정, `리세`는 별도 user로 분리됨을 확인했다.
- [x] Round2 bucket `comment_author_match_unverified_dialogue`를 추가했다.
- [x] focused regression 10건, packet tools 24건, `py_compile`을 통과했다.
- [ ] 새 completed source 또는 recovered subset에서 댓글 메타 high-risk bucket을 expanded review로 다시 집계한다.
- [ ] crawler/input 단계에서 post IP 또는 원글 작성자 표시를 확보할 수 있는지 확인한다.
- [ ] 20260528 원본 partial result는 댓글 맥락 품질 승인 근거로 쓰지 않는다.

## 2026-05-30 v254 `11718091` semantic reread confirmation

- [x] `23센줄`은 `23세인 줄` 오타/축약으로 먼저 읽어야 하는 자연어 이해 케이스임을 재확인했다.
- [x] current-code v251 canary의 `analysis_result.identity`에서 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`를 확인했다.
- [x] reason에 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄`, `작품 seed 제외: 은영`이 공개 필드로 남는 것을 확인했다.
- [x] `surface_paraphrase_notes`와 `discourse_semantic_seed_guard`가 검색 전에 한 번 더 읽는 구조임을 확인했다.
- [x] focused regression 6건을 통과했다.
- [x] v254 확인 산출물 `qualitative_review\20260528_141006_620986\v254_post11718091_semantic_reread_confirmation_ko.md`를 작성했다.
- [ ] v254는 current-code targeted 확인이다. 원본 20260528 partial source나 10만 건 semantic approval로 승격하지 않는다.
- [ ] expanded review에서 `context_only_no_work_anchor`와 semantic seed demotion bucket의 과차단/미차단을 별도 집계한다.

## 2026-05-30 v253 systemic bucket extraction

- [x] Round2 high-risk bucket에 `batch_memory_exact_alias_rescued_no_anchor`를 추가했다.
- [x] Round2 high-risk bucket에 `critical_counter_but_resolved`, `notes_demoted_then_resolved`, `title_surface_primary_candidate_rescued`를 추가했다.
- [x] Round2 high-risk bucket에 `official_url_missing_for_resolved`, `reason_says_no_anchor_but_resolved`, `search_absent_verified_title_direct_image_title`를 추가했다.
- [x] 각 bucket의 label/action 정책을 `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING` 체계에 맞춰 추가했다.
- [x] packet `evidence_counts`와 `result_public_fields`에 systemic flag를 노출했다.
- [x] focused tests 3건과 review tool `py_compile`을 통과했다.
- [x] v253 preflight에서 원본 source가 `REVIEW-LOCKED`임을 재확인했다.
- [x] v253 Round2 partial-source sample 69 packets를 별도 디렉토리에 생성했다.
- [ ] v253 수치는 partial 71행 기준이므로 전체 10만 건 오류율처럼 말하지 않는다.
- [ ] 새 completed source 또는 recovered completed subset에서 같은 bucket을 다시 실행한다.

## 2026-05-30 v250/v251 weak VLM/OCR title conflict guard

- [x] VLM/OCR direct title 후보가 Verifier의 `search_absent_verified_title`/critical/nullify 반론을 받은 경우, 그 후보를 Strong title evidence로 취급하지 않는다.
- [x] image/OCR-only title이 비이미지 원문에 없고 official evidence도 없으면, 안정 별칭/공식 URL/검색 hit가 있는 canonical 후보가 final title을 이길 수 있게 했다.
- [x] OCR/VLM 후보와 final title이 다르면 `vlm_ocr_title_conflict_with_final_title`를 남긴다.
- [x] final title이 안정 alias/official detail URL로 뒷받침되면 `ocr_title_conflict_with_stable_alias`를 남긴다.
- [x] focused unittest 5건과 `py_compile`을 통과했다.
- [x] v250에서 `11718099`가 `검은 여왕의 혼성명`으로 잘못 resolved되는 회귀를 확인했다.
- [x] Codex 내장 브라우저로 실제 이미지 로딩 완료 화면을 확인하고 `v251_post11718099_browser_actual.png`로 남겼다.
- [x] v251 known-bad 4건 VLM/OCR-on canary에서 `11718099 -> 빌어먹을 환생`, `11718091 -> context_only/title-null`을 확인했다.
- [ ] `search_absent_verified_title + direct_image_title` bucket은 expanded high-risk review에서 별도 집계한다.
- [ ] OCR-only/title-identical alias가 batch memory/slang DB에 저장되는 오염 경로를 별도 감사한다.
- [ ] v251은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v248/v249 social-lament semantic reread

- [x] `23센줄`류는 `23세인 줄`처럼 자연어로 먼저 읽고, 특정 작품 seed가 아니면 검색으로 확장하지 않는다.
- [x] `소설 보는 친구 있으면 좋음`, `밥 먹으며 TS/갈드컵 얘기`처럼 소설 일반어 + 친구/밥/같이/토론/한탄 신호가 같이 있으면 semantic seed review를 한 번 더 실행한다.
- [x] memory-query/작품 찾기 신호가 있는 글은 social-lament 트리거에서 제외한다.
- [x] social-lament trigger는 seed가 없는 경우뿐 아니라 `title_novel_terms`나 `search_suggestions`가 이미 있는 경우에도 독립적으로 작동한다.
- [x] semantic seed review가 `ts`, `갈드컵` 같은 장르/커뮤니티 용어를 `context_only/drop`으로 낮추면 `title_novel_terms`와 `search_suggestions`에서 제거한다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [x] v248/v249 `11718080` live canary에서 `official_title=null`, `discussion_type=trope_discussion`, `title_resolution_allowed=false`를 확인했다.
- [ ] `friend_social_lament_or_generic_discourse`는 expanded high-risk review에서 false positive/false negative를 별도 집계한다.
- [ ] v248은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v246 익명 author/IP 댓글 dialogue guard

- [x] `ㅇㅇ` 같은 익명 author는 author 문자열만으로 동일 화자로 묶지 않는다.
- [x] post IP와 comment IP가 모두 있고 서로 다르면 익명 author match만으로 `role=post_author`를 부여하지 않는다.
- [x] 익명 author + IP 조합은 speaker key를 분리해 다른 `ㅇㅇ` 댓글이 같은 `userN`으로 합쳐지지 않게 했다.
- [x] `post_ip`를 pipeline public packet에 남긴다.
- [x] `expert_main.py`가 입력의 `ip/author_ip/post_ip/writer_ip`를 `PostInput`으로 전달한다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [x] Round 2 qualitative review에 `comment_author_ip_mismatch_dialogue`, `post_author_comment_not_independent_evidence`, `comment_answer_side_conversation` bucket을 추가했다.
- [x] v247 preflight에서 원본 partial source의 댓글 메타 부족 bucket을 확인했다.
- [ ] 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v245 title-null reason scoreboard alignment

- [x] `official_title=null`이고 최종 title 확정이 금지된 경우 `plot_mention`류를 `강한 앵커`로 표시하지 않는다.
- [x] `is_relevant=false` + title-null이면 score line은 `작품명 확정에는 쓰지 않는 맥락 앵커(...)`로 남긴다.
- [x] `author_new_work_context` 같은 scope field와 reason scoreboard가 서로 모순되지 않게 했다.
- [x] focused unittest 5건과 `py_compile`을 통과했다.
- [x] v245 vLLM canary `20260530_052428_641974`에서 실제 결과 JSON score line이 `grounding_anchor: -2 (약한 앵커(search_only))`로 내려간 것을 확인했다.
- [ ] 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v243 author/new-work alias rescue monotonicity

- [x] `개돌 신작`류는 먼저 `[작가/별명] 신작` author/new-work 문맥인지 확인한다.
- [x] 앞단 Arbiter가 deliberate null을 설정하고 `discuss_genre/trope/community/no_work_anchor` 경고가 있으면 후단 검색 추정 alias rescue가 단독으로 final title을 뒤집지 못한다.
- [x] author/new-work 표면은 `search_evidence_alias_inference`뿐 아니라 이미 오염된 `batch_memory` hit에서도 차단한다.
- [x] 차단은 post id나 `개돌` 하드코딩이 아니라 공개 문맥 패턴, deliberate null, direct title proof 부재, strong anchor 부재 조건으로 수행한다.
- [x] focused unittest 5건과 `py_compile`을 통과했다.
- [x] v243 단건 canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v243 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v243 `11718089`은 `official_title=null`, `is_relevant=false`, `title_resolution_allowed=false`로 확인했다.
- [x] v242가 만든 `slang_db` 오염 `개돌 -> 파벨 주니어`를 제거했다.
- [ ] `author_new_work_alias_rescue_blocked`는 expanded high-risk review에서 false positive/false negative를 별도 집계한다.
- [ ] v243은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v240 context-only no-work-anchor scope

- [x] `23센줄`류는 `23세인 줄` 오타/축약이라는 자연어 이해를 먼저 적용한다.
- [x] 의미 재독해가 seed를 `context_only/drop`으로 낮추고 직접 작품 앵커가 없으면 `unresolved_matchable`로 남기지 않는다.
- [x] final `title_resolution_state=context_only`를 사용해 "소설/캐릭터 맥락일 수는 있어도 단일 작품 매칭 근거는 없음"을 분리한다.
- [x] `context_only_no_work_anchor` flag를 남겨 대규모 정성 리뷰 bucket에서 과표집할 수 있게 했다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [x] v240 known-bad 4건 canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v240 manifest에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v240 `11718091`은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`로 확인했다.
- [x] 원본 20260528 out 파일은 10만 건 completed source가 아니라 `completed=80`, `flushed=71`, `pending=9` partial source임을 별도 요약으로 남겼다.
- [ ] `context_only_no_work_anchor`는 expanded high-risk review에서 false negative/false positive를 별도 집계한다.
- [ ] v240은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v239 platform branding fetch-title handling

- [x] 문피아 모바일/desktop fetch title `웹소설의 유토피아, 글세상 문피아`류는 platform branding으로 본다.
- [x] platform branding/listing/generic fetched title은 `heretic_url 제목 불일치`로 세지 않는다.
- [x] 같은 URL의 검색 title/snippet이 final title을 직접 지지하면 그 evidence를 우선한다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [x] v239 known-bad 4건 canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v239 manifest에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v239 `11718097`은 `망겜의 힐러`, `https://novel.munpia.com/328421`, 댓글 dialogue 5건으로 확인했다.
- [x] v239 log에서 `11718097`의 `heretic_url 제목 불일치` false warning이 사라진 것을 확인했다.
- [ ] `platform_branding_fetch_title`은 expanded review에서 false positive/false negative를 별도 집계한다.
- [ ] v239는 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v238 VLM/OCR conflict structured flags

- [x] OCR/표지 후보와 final title이 다를 때 자연어 reason만 보고 끝나지 않도록 구조 flag를 추가했다.
- [x] `vlm_ocr_title_conflict_with_final_title`는 VLM/OCR direct title 후보가 final official title과 normalized/similar match되지 않을 때만 남긴다.
- [x] `ocr_title_conflict_with_stable_alias`는 final title이 locked official/detail 또는 안정 alias 후보로 뒷받침될 때만 남긴다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [x] v238 단건 canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v238 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v238 `11718099` final identity와 log active-learning queue에 `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias`가 남았다.
- [x] `23센줄 -> 23세인 줄` reason regression을 같이 확인했다.
- [ ] VLM/OCR conflict flag는 대규모 정성 리뷰에서 high-risk bucket으로 과표집한다.
- [ ] v238은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v237 batch memory alias URL/evidence follow-up

- [x] `batch_memory_exact_alias_rescued` 후 URL이 비어 있는 구조를 별도 회귀 테스트로 재현했다.
- [x] exact alias rescue 일반 경로도 corrected title official URL recovery를 호출하도록 수정했다.
- [x] URL 회복 시 `heretic_url`, candidate, `primary_work`, `source_tier=official_detail`, `page_type=novel_page`를 동기화한다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [x] v236 단건 canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v236 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v236 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, `official_urls=4`로 확인했다.
- [x] v237 동일 4건 canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v237 manifest에서 `requested_parallel=36`, `effective_parallel=4`, `completed/failed/pending=4/0/0`, Docker lifecycle false, VLM/OCR on, `image_post_count=3`을 확인했다.
- [x] v237 `11718099`는 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, `official_urls=1`로 확인했다.
- [x] v237 `11718091`은 `23센줄 -> 23세인 줄` 의미 재독해와 `title_resolution_allowed=false`를 유지했다.
- [ ] VLM/OCR conflict 후보 `붉여먹을 혼성명`은 final title strong evidence로 승격하지 않는지 expanded review에서 계속 확인한다.
- [ ] v237은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v234 corrected title 공식 URL/evidence 회복

- [x] v230의 `11718077` corrected title URL/evidence 누락을 후속 이슈로 분리했다.
- [x] late-corrected title 기준 공식 URL recovery를 추가했다.
- [x] stable alias conflict/canonical base correction 이후 URL이 비어 있으면 recovery를 호출한다.
- [x] 검색 결과 title이 generic해도 snippet/content/description의 strict title match를 공식 detail URL 후보로 인정한다.
- [x] final `reason`의 `official_title_evidence`와 `official_urls` counter를 final URL 상태와 동기화한다.
- [x] focused unittest 9건과 `py_compile`을 통과했다.
- [x] v234 live canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v234 manifest에서 `requested_parallel=36`, `effective_parallel=2`, `completed/failed/pending=2/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v234 `11718077`은 `official_title=즉사기 들고 무림에 떨어지다`, `heretic_url=https://series.naver.com/novel/detail.series?productNo=14041321`, `official_urls=1`로 확인했다.
- [ ] `validated=false` URL recovery는 expanded high-risk review에서 evidence grade를 분리한다.
- [ ] v234는 targeted canary다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v230 `11718077` stable alias conflict 보정

- [x] v229 실패 원인이 stable alias 보정 부재가 아니라 Decoder 오판을 current title 원문 언급 증거로 재사용한 구조임을 확인했다.
- [x] `stable_batch_alias_conflicts_with_official_title`는 raw title/body/comment의 current title strict direct match만 보도록 수정했다.
- [x] Decoder가 `즉사무림 -> 즉사수선전`으로 이미 오판한 상태를 회귀 테스트에 추가했다.
- [x] focused unittest 3건과 `py_compile`을 통과했다.
- [x] v230 live canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v230 manifest에서 `requested_parallel=36`, `effective_parallel=2`, `completed/failed/pending=2/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v230 `11718077`은 `official_title=즉사기 들고 무림에 떨어지다`, `discussion_type=review`, `subtype=review_reaction`, `anchor_type=title_alias`로 확인했다.
- [x] v219 잔여 action 중 `11718077` alias collision은 targeted 기준으로 닫았다.
- [x] corrected title의 `heretic_url=null`, `official_title_evidence=false` 후속은 v234 targeted 기준으로 닫았다.
- [ ] v230은 targeted canary다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v228 `11718075` short support alias probe

- [x] `11718075` v226 실패 원인을 `죽깨수 웹소설` verification query가 association/low-specific 필터에서 제거된 것으로 확인했다.
- [x] short support/anticipation context에서 제목 compact alias 검증 쿼리를 보존하는 구조적 helper를 추가했다.
- [x] `23센줄` 같은 나이/오타 표면은 새 alias probe 경로에서 제외했다.
- [x] `verification_search` 정합성 필터가 `죽깨수 웹소설`류 쿼리를 제거하지 않고 domain suffix query를 먼저 실행하도록 했다.
- [x] 복구된 결과 taxonomy를 `subtype=support_cheer`, `anchor_type=title_alias`, `anchor_strength=medium`으로 정렬했다.
- [x] focused unittest 3건과 `py_compile`을 통과했다.
- [x] v228 live canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v228 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v228 `11718075`는 `official_title=죽었다 깨어도 수선`, `is_relevant=true`, `discussion_type=anticipation`, `subtype=support_cheer`로 확인했다.
- [x] v219 잔여 action 중 `11718075`는 targeted 기준으로 닫았다.
- [ ] `short_support_alias_probe` bucket은 expanded high-risk review에서 과승격/과차단을 확인한다.
- [x] v219 잔여 action 중 `11718077` alias collision은 v230 targeted 기준으로 닫았다.
- [ ] v228은 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v225 seed 없는 짧은 work 과분류 의미 재독해

- [x] seed 후보나 검색 제안이 없어도 짧은 글이 `discuss_work/work`로 과분류되면 `discourse_semantic_seed_guard`가 한 번 더 읽도록 했다.
- [x] `23센줄 -> 23세인 줄` 같은 surface note 경로와 별도로, "후보 없음 + work 과분류" 경로도 context-only 재독해 대상으로 분리했다.
- [x] 원문에 안정 약칭/정식 제목이 직접 보이면 새 재독해가 불필요하게 덮지 않도록 했다.
- [x] focused unittest 5건과 `py_compile`을 통과했다.
- [x] v225 live canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v225 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v225 `11718091`은 `23센줄 -> 23세인 줄`, `작품 seed 제외: 23센줄, 은영`을 reason에 남기고 `official_title=null`, `is_relevant=false`, `title_resolution_allowed=false`를 유지했다.
- [ ] `context_only_short_reaction`, `short_banter_seed_demoted`, `surface_paraphrase_specific_work_denied` bucket은 expanded sample에서 과차단/미차단을 확인한다.
- [ ] v225는 targeted canary다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v223 `11718069` author-meta batch alias rescue 차단

- [x] `11718069`을 단건 targeted input으로 분리했다.
- [x] 실행 전 Docker shard는 기존 컨테이너 재사용 상태이고, 관련 Python 점유 프로세스가 없음을 확인했다.
- [x] v223은 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v223 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] VLM used `true`, image fetch `1/1`, chunks `1`을 확인했다.
- [x] Codex 내장 브라우저로 `11718069` 페이지를 열어 제목/본문/첨부 이미지/댓글 0개를 확인하고 full-page screenshot을 남겼다.
- [x] author-meta/adjacent 판정 이후 BatchContext alias rescue가 부차 별칭을 공식 제목으로 되살리지 못하게 했다.
- [x] `11718069`은 `official_title=null`, `is_relevant=false`, `discussion_type=author_talk`, `topicality=adjacent_relevant`, `title_resolution_allowed=false`를 유지했다.
- [x] focused unittest 5건과 `py_compile`을 통과했다.
- [x] v219 잔여 action 중 `11718069`은 targeted 기준으로 닫았다.
- [x] v219 잔여 action 중 `11718075`는 v228 targeted 기준으로 닫았다.
- [x] v219 잔여 action 중 `11718077` alias collision은 v230 targeted 기준으로 닫았다.
- [ ] v223은 targeted follow-up이다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v222 `23센줄` surface paraphrase 의미 재검토 강제

- [x] `surface_paraphrase_notes`가 있으면 title/search 후보가 없어도 `discourse_semantic_seed_guard`가 실행되도록 했다.
- [x] `23센줄`은 `23세인 줄`, `16살인줄`은 `16살인 줄`로 읽는 자연어 표면 해석을 final reason에 남긴다.
- [x] LLM 의미 재검토가 일부 과확정하더라도, seed가 제거되고 직접 작품 앵커가 없으면 final은 `official_title=null`, `title_resolution_allowed=false`로 둔다.
- [x] focused unittest 5건과 `py_compile`을 통과했다.
- [x] v222 live canary는 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on`으로 실행했다.
- [x] v222 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/failed/pending=1/0/0`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] v222 `11718091`은 `official_title=null`, `is_relevant=false`, `discussion_type=noise`, `work_resolution=none`, `title_resolution_allowed=false`를 유지했다.
- [ ] `short_banter_seed_demoted`, `surface_paraphrase_specific_work_denied` bucket은 expanded sample에서 과차단/미차단을 확인한다.
- [ ] v222는 targeted canary다. 10만 건 semantic gate는 expanded review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v221 `11716499`/`11718087` semantic follow-up

- [x] `11716499`, `11718087` 2건만 분리한 targeted input을 만들었다.
- [x] 실행 전 Docker shard는 기존 컨테이너 재사용 상태이고, 관련 Python 점유 프로세스가 없음을 확인했다.
- [x] v221은 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] v221 로그에서 `requested_parallel=36`, `effective_parallel=2`, Docker lifecycle false, VLM/OCR on을 확인했다.
- [x] Codex 내장 브라우저로 `11718087` 페이지를 열어 제목/첨부 카드 이미지/본문 `ts잘먹음`을 확인하고 full-page screenshot을 남겼다.
- [x] `11716499`는 `그러는데` 접속형 조각을 작품 alias로 승격하지 않고 `official_title=null`, `is_relevant=false`로 내려갔다.
- [x] `11718087`은 VLM/OCR 카드 이미지가 있어도 제목의 추천 요청을 보존해 `topicality=adjacent_relevant`, `discussion_type=recommendation`, `official_title=null`로 유지했다.
- [x] focused unittest 4건, batch alias/VLM regression 7건, `py_compile`을 통과했다.
- [x] v219 잔여 action 중 `11716499`, `11718087`은 targeted 기준으로 닫았다.
- [x] `11718069`은 v223에서 author-meta alias rescue 차단으로 targeted 기준 닫았다.
- [x] `11718075`: short support alias probe는 v228에서 `support_cheer`로 닫았다.
- [x] v219 잔여 action 중 `11718077` alias collision은 v230 targeted 기준으로 닫았다.
- [ ] v221은 targeted follow-up이다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v219 실패군 확대 재실행 및 정성 리뷰

- [x] v215 pattern scan에서 failure family별 후보를 추출했다.
- [x] 중복 post id를 제거해 30개 post를 선정했다.
- [x] metadata-preserved input이 있는 known-bad는 enriched row/comment row를 우선 사용했다.
- [x] `v219_failure_family_expansion_input.jsonl`은 `36` lines, `30` posts, `6` comments로 JSON parse를 통과했다.
- [x] `v219_failure_family_expansion_manifest.json`, `summary_ko.md`, `action_queue_ko.md`를 생성했다.
- [x] v219 권장 명령으로 재실행했다.
- [x] manifest에서 `requested_parallel=36`, `effective_parallel=5`, `vlm_enabled=true`, `ocr_enabled=true`, Docker lifecycle false를 확인했다.
- [x] `completed_count=30`, `failed_count=0`, `pending_count=0`을 확인했다.
- [x] `v219_failure_family_expansion_result_review_ko.md`와 `v219_failure_family_expansion_review_labels.jsonl`을 생성했다.
- [x] v219은 targeted expansion이므로 10만 건 semantic approval로 승격하지 않는다.
- [x] `11718075`는 v228 targeted 기준으로 닫았다.
- [x] `11718077` alias collision 후속 action은 v230 targeted 기준으로 닫았다. `11716499`, `11718087`은 v221 targeted 기준으로 닫았고, `11718069`은 v223 targeted 기준으로 닫았다.

## 2026-05-29 v218 현재 semantic root-cause matrix

- [x] 원본 `out\expert_result_20260528_141006_620986.json`이 10만 건 완료 산출물이 아니라 partial run임을 다시 기록했다.
- [x] v215 pattern scan의 상위 반복 패턴을 root-cause matrix에 반영했다.
- [x] v212~v217 targeted/current-code 결과를 known-bad 현재 상태 표로 정리했다.
- [x] 원인 축을 자연어 의미 재판독, 댓글 대화 흐름, 후단 rescue, VLM/OCR conflict, URL/evidence-state, slang DB/BatchContextMemory 오염으로 분리했다.
- [x] `qualitative_review\20260528_141006_620986\v218_current_semantic_root_cause_matrix_ko.md`를 생성했다.
- [ ] 새 completed source 또는 random baseline/P0/P1 high-risk expansion 전까지 10만 건 semantic approval은 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v217 `11718080` 친구/한탄형 장르 잡담 재검증

- [x] `11718080`을 단건 input으로 분리해 현재 코드/현재 vLLM에서 다시 확인했다.
- [x] 단건 run은 `--parallel 36 --reuse-shards-only --no-dashboard --slang-db on --vlm on --ocr on` 기준으로 실행했다.
- [x] manifest 기준 `input_post_count=1`, `requested_parallel=36`, `effective_parallel=1`, `completed_count=1`, `failed_count=0`, `pending_count=0`을 확인했다.
- [x] manifest 기준 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_small_run_shard_lifecycle_blocked=true`를 확인했다.
- [x] 결과에서 `official_title=null`, `is_relevant=false`, `discussion_type=trope_discussion`, `is_resolved_work_discussion=false`, `title_resolution_allowed=false`를 확인했다.
- [x] `discourse_semantic_seed_guard`가 `소설`을 context-only로 낮추고 TS/갈드컵 검색 제안을 drop해 특정 작품 seed를 열지 않는 것을 확인했다.
- [x] late rescue/generic discourse veto 3건 + `23센줄` 의미 재판독 4건 focused regression을 통과했다.
- [x] 관련 `py_compile`을 통과했다.
- [ ] v217은 current-code 단건 canary다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v216 검색 전 의미 재판독에 댓글 dialogue context 포함

- [x] `discourse_semantic_seed_guard` 입력 payload에 `comment_context`와 `comment_dialogue_context`를 추가했다.
- [x] 의미 재검토 프롬프트에 오타/축약/띄어쓰기 깨짐을 먼저 자연어 의미로 풀어 읽고, 나이/외모/잡담이면 작품 seed로 쓰지 말라는 원칙을 명시했다.
- [x] `comment_dialogue_context`의 speaker/author/ip/comment_id/reply_to는 대화 흐름 메타이지 작품명·별칭·공식 근거가 아님을 의미 재검토 단계에도 명시했다.
- [x] focused unittest 4건과 `py_compile`을 통과했다.
- [x] v216 single canary는 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 실행했고, manifest 기준 `input_post_count=1`, `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] v216 `11718091`은 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄`을 reason에 남기고 `official_title=null`, `is_relevant=false`, `title_resolution_allowed=false`를 유지했다.
- [ ] v216은 단건/targeted semantic correction이다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v214 댓글 발화 재구성 / memory-query 재승격 차단

- [x] result row와 pipeline post dict에 `comment_dialogue_context_lines`를 추가했다. 기존 `comment_context_lines`가 speaker/author/ip만 담는 반면, 새 필드는 `#번호 + speaker/author/ip + 댓글 text excerpt`를 함께 담아 본문 작성자가 댓글에서 이어 말하는 흐름을 LLM이 직접 읽을 수 있게 한다.
- [x] `comment_dialogue_context_lines`는 prompt/review용 공개 맥락이며, speaker/author/ip 자체를 작품명·별칭 근거로 쓰지 않는 규칙을 prompt overlay에 유지했다.
- [x] Gatekeeper/Discourse/Verifier prompt JSON, Decoder evidence-based reread, Arbiter/Synthesizer 최종 판단 prompt, qualitative random/round2 packet에 dialogue context를 전달하도록 했다.
- [x] `11718083`처럼 “대사만 기억나고 무슨 소설인지 모르겠다”는 memory-query는 `unresolved_worklike_hold`가 `character_talk`로 되살리지 못하게 했다.
- [x] v213 targeted 4건은 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 실행했고, manifest/log 기준 `effective_parallel=4`, Docker lifecycle flags false였다.
- [x] v213 result: `11718091`은 `comment_dialogue_context_lines`에 `#1 speaker=post_author author=ㅇㅇ role=post_author ... text=ㄹㅇ 머리도 안올렷잖아 더어린줄`을 남겼다.
- [x] v213 result: `11718097`은 댓글 5건의 post_author/user speaker, reply 관계, 댓글 text excerpt를 dialogue context로 남겼고 `망겜의 힐러` 공식 URL을 유지했다.
- [x] v214 single canary: `11718083`은 `is_relevant=false`, `discussion_type=recommendation`, `official_title=null`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 확인됐다.
- [ ] v214는 known-bad targeted correction이다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v212 `23센줄` 의미 이해 재확인 / `11718097` 공식 URL 보강

- [x] `23센줄`류는 단순 문자열 차단이 아니라 `surface_paraphrase_notes` + `discourse_semantic_seed_guard`가 `23세인 줄` 자연어 해석을 남기고 seed를 낮추는 구조임을 focused unittest로 재확인했다.
- [x] `11718097`에서 `단행본` 표지가 들어간 `망겜의 힐러 [단행본] - 웹소설 - 카카오페이지`를 비소설 매체로 오분류하지 않게 했다.
- [x] `오행복` 같은 주변어에서 엉뚱한 공식 URL이 먼저 잡혀도 `망겜힐 -> 망겜의 힐러` resolved title 공식 검증 검색을 생략하지 않게 했다.
- [x] v212 live run은 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 실행했고, manifest/log 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] v212 result `11718097`: `official_title=망겜의 힐러`, `heretic_url=https://m.munpia.com/novel/detail/328421`, `confidence=High`, `official_title_evidence=true`, `official_urls=4`.
- [x] v212 evidence catalog에 `망겜의 힐러 [단행본] - 웹소설 - 카카오페이지`, 문피아, 네이버 시리즈 등 공식 플랫폼 URL이 남았다.
- [x] focused unittest 7건, 전체 `tests.test_agentic_pipeline_rework -v` 335건, 관련 `py_compile`, `git diff --check`를 통과했다.
- [ ] v212는 known-bad targeted correction이다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v210 `23센줄` 의미 해석 재확인 / 저정보 slang alias cleanup

- [x] v210 known-bad 4건은 `--parallel 36 --reuse-shards-only --vlm on --ocr on` 기준으로 실행했고, manifest 기준 `effective_parallel=4`, Docker lifecycle flags false였다.
- [x] `11718091`은 `23센줄 -> 23세인 줄`, `16살인줄 -> 16살인 줄` 자연어 해석을 reason에 남기고 `official_title=null`, `discussion_type=noise`, `title_resolution_allowed=false`를 유지했다.
- [x] `11718083`은 `unresolvable_memory_query/title null`로 유지했지만, 기존 DB의 `너에겐 -> 너 따위에겐 절대X3...` 저정보 alias 오염을 확인했다.
- [x] slang DB 저장/cleanup 단계에 대명사+조사, 일반 술어, 담화 표면 alias 차단을 추가했다.
- [x] `title_resolution_allowed=false` 및 `unresolvable_memory_query`인 기억 회수 글은 slang DB observation 자체를 남기지 않는다.
- [x] 실제 `slang_db/slang_db.json`에서 `너에겐`, `너 따위에겐 절대X3` match 0건을 확인했다.
- [x] `tests.test_slang_db -v` `25`건, `tests.test_agentic_pipeline_rework -v` `333`건, `py_compile`을 통과했다.
- [ ] v210은 known-bad targeted correction이다. 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-29 v209 `11718099` OCR-only conflicting query prune

- [x] BatchContext alias를 stable direct seed로 사용해 title-lead alias를 보존한다.
- [x] OCR/image-only 후보 수집 범위에 Discourse/search suggestion/image enrichment를 포함한다.
- [x] `alias_bridge_search`, `abbreviation_verification`, `decoder_recall_verification` 등 long-tail purpose에서도 OCR-only conflict query를 pruning한다.
- [x] `_execute_searches()` 직전에도 OCR-only title seed pruning을 재적용한다.
- [x] v209 live run은 `--vlm on --ocr on --parallel 36 --reuse-shards-only` 기준으로 실행했고, manifest 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] v209 result에서 `11718099`는 `official_title=빌어먹을 환생`, `url=https://novel.munpia.com/222360`으로 확인됐다.
- [x] `tests.test_agentic_pipeline_rework -v` `333`건과 관련 `py_compile`을 통과했다.
- [x] `slang_db`에 `불먹을`, `검은 여왕`, `따먹을 환생`, `있어`, `있어도` 신규 오염이 없음을 확인했다.
- [ ] OCR-only 후보가 전문가 prompt/reason/deliberation support에서 Strong title evidence로 쓰이지 않게 더 이른 단계에서 낮춘다.
- [ ] v209 targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v208 `11718099` title-lead alias/status/OCR conflict

- [x] `빌환 표지변경됨`에서 제목 선두 안정 alias `빌환`은 보존한다.
- [x] `표지변경됨` 같은 상태어는 standalone 작품 seed와 compact query suffix로 쓰지 않는다.
- [x] `있어`, `있어도`, `없어` 계열 술어 조각은 search-evidence alias inference에서 차단한다.
- [x] episode/detail variant title은 안정 alias의 canonical base로 보정한다.
- [x] v207이 남긴 `있어 -> 따먹을 환생` slang_db 오염을 제거하고 JSON 유효성을 확인했다.
- [x] v208 live run은 `--vlm on --ocr on --parallel 36 --reuse-shards-only` 기준으로 실행했고, manifest 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] Codex 내장 브라우저로 `11718099` 본문 이미지 로딩 완료(`850x1190`)와 표지 제목 `빌어먹을 환생`을 확인했다.
- [x] `tests.test_agentic_pipeline_rework -v` `333`건을 통과했다.
- [ ] v208은 title targeted recovery일 뿐이다. VLM/OCR conflict와 595.8s long-tail이 남아 semantic evidence quality는 `REVIEW`로 둔다.
- [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v204 `23센줄` 오타/의미 재검토 reason

- [x] semantic seed review 프롬프트는 `surface_paraphrase_notes`의 `non_title_semantic_context`를 원문 이해 힌트로 우선 반영한다.
- [x] `23센줄`은 `23세인 줄` 오타/축약으로 reason에 표시한다.
- [x] final reason은 `표면 표현 해석`, `의미 재검토`, `작품 seed 제외`, `공식 제목 미확정`을 함께 말한다.
- [x] 마지막 seed가 surface sanitizer에서 제거되면 `semantic_seed_review.is_specific_work_discussion=false`로 내부 flag도 낮춘다.
- [x] `seed 후보(...)는` 문구로 조사 깨짐을 피한다.
- [x] v204 live run은 `--vlm on --ocr on --parallel 36 --reuse-shards-only` 기준으로 실행했고, manifest 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] v204 result에서 `11718091`은 `official_title=null`, `is_relevant=false`, `discussion_type=noise`, `title_resolution_allowed=false`로 확인됐다.
- [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v201 semantic seed review reason 반영

- [x] `semantic_seed_review.content_interpretation/post_intent`가 final reason에 들어간다.
- [x] `semantic_seed_review_context_terms`는 `작품 seed 제외`로 노출된다.
- [x] reason은 캐릭터/나이/외모 감상이라는 자연어 해석과 공식 제목 미확정을 함께 말한다.
- [x] v201 live run은 `--vlm on --ocr on --parallel 36 --reuse-shards-only` 기준으로 실행했고, manifest 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] v201 result에서 `11718091`은 `official_title=null`, `is_relevant=false`, `reason_has_semantic=true`, `reason_has_seed=true`로 확인됐다.
- [ ] reason 품질 targeted 개선만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v199 LLM semantic seed review / no-anchor 조기종료

- [x] 표면 규칙만으로 처리하지 않고 LLM seed review가 post intent와 seed 의미를 한 번 더 읽는다.
- [x] `title_novel_terms`가 작품명/별칭이 아니라 자연어 문맥어이면 `semantic_seed_review_context_terms`로 낮춘다.
- [x] demoted seed에서 나온 `search_suggestions`와 Orchestrator auto search seed는 실행 전에 제거한다.
- [x] known alias 또는 strong work anchor가 있으면 semantic seed review만으로 무조건 drop하지 않는다.
- [x] 이미지/OCR/VLM이 있는 post는 no-anchor early-exit로 막지 않고 시각 evidence 경로를 유지한다.
- [x] 이미지/OCR/VLM이 없고 strong work anchor도 없으면 Decoder/search rescue가 demoted seed를 재승격하지 않는다.
- [x] v199 live run은 `--vlm on --ocr on --parallel 36 --reuse-shards-only` 기준으로 실행했고, manifest 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] v199 result에서 `11718091`은 실제 검색/Decoder 실행 없이 `is_relevant=false`, `official_title=null`, `discussion_type=noise`로 종료했다.
- [x] `tests.test_agentic_pipeline_rework -v` `329`건을 통과했다.
- [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v195 표면 오타/나이 감상 문맥 가드

- [x] `23센줄`을 `23세인 줄` 자연어 오타/축약으로 보고 `surface_paraphrase_notes`에 `non_title_semantic_context`로 남긴다.
- [x] Discourse raw output이 `은영`, `23센줄`을 title term으로 내도 sanitizer가 `title_novel_terms=[]`로 낮춘다.
- [x] Discourse raw `은영 23세` 검색 제안은 sanitizer에서 제거한다.
- [x] Orchestrator가 `은영이 정식 제목`, `은영이 캐릭터`, `소신발언은영`, `23센 줄 몰랐음 소설` 같은 파생 검색을 제거한다.
- [x] v195 live run은 `--vlm on --ocr on --parallel 36 --reuse-shards-only` 기준으로 실행했고, manifest 기준 `effective_parallel=1`, Docker lifecycle flags false였다.
- [x] v195 result에서 `11718091`은 실제 검색 실행 없이 `is_relevant=false`, `official_title=null`, `discussion_type=noise`로 종료했다.
- [x] `tests.test_agentic_pipeline_rework -v` `327`건을 통과했다.
- [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v187 VLM/OCR reason evidence alignment

- [x] v184 `11718099`의 final title은 맞지만 OCR drift 후보가 reason에서 보조 제목 근거처럼 표현되는 잔여 리스크를 확인했다.
- [x] 최종 title과 OCR/표지 후보가 다르면 보조 근거로 쓰지 않는다고 reason을 낮추도록 했다.
- [x] `test_image_grounding_note_softens_nonmatching_ocr_title`와 `test_ocr_drift_title_is_vetoed_and_alias_bundle_recovers_correct_primary_work`를 통과했다.
- [x] `src\llm_batch\agentic_pipeline.py`와 `tests\test_agentic_pipeline_rework.py` `py_compile`을 통과했다.
- [x] v187 active goal requirement audit 문서를 추가했다.
- [ ] 다음 VLM/OCR-on live canary에서 새 reason 문구를 확인한다.

## 2026-05-29 v186 large rerun VLM/OCR-on readiness

- [x] 10만 건급 semantic 재검증의 기본 기준은 `--vlm on --ocr on`으로 재확인했다.
- [x] 새 completed source는 기존 `out\expert_result_20260528_141006_620986*` partial artifact를 덮어쓰지 않는다.
- [x] 기본 명령 템플릿은 `--parallel 36 --reuse-shards-only --vlm on --ocr on`으로 기록했다.
- [x] 36-shard Docker lifecycle 검증은 `--allow-goal-shard-lifecycle --auto-up-shards`가 붙은 별도 모드로 분리했다.
- [x] v186 readiness 문서에 실행 전 확인, 실행 템플릿, 실행 후 gate를 남겼다.
- [ ] 전체 입력 JSONL과 새 output path가 확정되기 전에는 대형 재런을 시작하지 않는다.
- [ ] 대형 재런 후 manifest `vlm_enabled=true`, `ocr_enabled=true`, `vlm_ocr_semantic_review_ready=true`를 확인한다.
- [ ] clean completion과 expanded semantic review 전까지 10만 건 gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 v184 URL media-type / weak character-page guard

- [x] v183 `11718099`의 잔여 문제는 title 자체가 아니라 final URL이 validator에서 기각된 웹툰/비소설 매체 URL로 남는 evidence-state 불일치였다.
- [x] v183 `11718091`의 잔여 문제는 Verifier가 약한 캐릭터 외모/나이 잡담으로 거부한 뒤, 후단 등장인물 page 검색 rescue가 작품명을 승격한 과확정이었다.
- [x] 검색 결과가 웹툰/만화/파생 팬픽 매체로만 지지하는 URL은 소설 상세 URL 후보에서 제외한다.
- [x] final reference freeze는 비소설 매체 URL을 지우고, 정확한 소설 상세 URL이 있으면 그 URL로 동기화한다.
- [x] 약한 캐릭터 반응글은 등장인물 page 검색 결과만으로 작품명 확정하지 않는다.
- [x] post id, 특정 약칭, 특정 URL 하드코딩 없이 공개 evidence/Verifier field 기반으로 처리했다.
- [x] v184 live run은 `--vlm on --ocr on --parallel 36 --reuse-shards-only`로 실행했고, manifest 기준 `effective_parallel=4`, `completed/failed/pending/flushed=4/0/0/4`, Docker lifecycle flags false였다.
- [x] v184 result에서 `11718091`은 title null/비관련, `11718099`는 `빌어먹을 환생 + Naver Series detail URL`, `11718097`은 `망겜의 힐러`, `11718083`은 title null/unresolvable memory query로 확인했다.
- [x] `EXPERT_ORCHESTRATION_LIMITATIONS.md`의 현재 gate 상태를 v184 기준으로 갱신해 `is_relevant` 단독 판정 금지, URL media-type guard, weak character-page veto, VLM/OCR-on 기준을 반영했다.
- [x] `v185_current_goal_status_audit_ko_20260529.md`에 원본 partial run 상태, v184 known-bad 결과, 요구사항별 완료/미완료 상태를 분리 기록했다.
- [x] `v185_large_scale_preflight_original_partial.json/md`를 생성해 원본 partial source가 random baseline 1,000건에 `929`건 부족하고 gate가 `REVIEW-LOCKED`임을 자동 preflight로 재확인했다.
- [ ] targeted 4건 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v182 title/url match-quality ordering

- [x] 원본 run `20260528_141006_620986`의 `11718099`는 `빌환 -> 빌어먹을 환생` title은 맞아야 하지만 `표지변경`이 title로 승격된 버그였다.
- [x] 최신 v178 canary에서는 title은 `빌어먹을 환생`으로 회복됐지만, result JSON의 URL이 정확 제목 Naver Series 상세가 아니라 `book.novelpia.com/novel/19205` 같은 embedded-title page로 흔들릴 수 있음을 확인했다.
- [x] `_find_title_matched_official_url`은 이제 플랫폼 선호보다 source title match 품질을 먼저 본다. 정확 제목 match가 episode/부제/작가명이 붙은 embedded match보다 우선한다.
- [x] `_freeze_identity_references`의 `primary_work` URL 동기화도 같은 match-quality 기준을 사용한다.
- [x] post id/특정 작품 URL 하드코딩 없이 title/url pair 정합성 기준으로 회귀 테스트를 추가했다.

## 2026-05-29 v181 semantic/VLM baseline 재고정

- [x] 이미지가 있는 post의 semantic 품질 검증 기준은 `--vlm on --ocr on`으로 재고정한다.
- [x] `expert_main.py` manifest에 `vlm_enabled`, `ocr_enabled`, `image_post_count`, `vlm_ocr_semantic_review_ready`, `vlm_ocr_semantic_review_warning`을 남기도록 했다.
- [x] 이미지 post가 있는데 VLM/OCR이 완전히 켜지지 않은 run은 품질 승인 근거가 아니라 `INFO_MISSING` 또는 `REPROCESS` 증거로 취급한다.
- [x] v179 `11718082` text-only 판정은 이미지 안의 작품명/회차를 읽지 못했으므로 semantic approval 근거로 쓰지 않는다.
- [x] `11718082`와 `11718080` known-bad는 `--vlm on --ocr on --parallel 36 --reuse-shards-only` 기준으로 다시 재실행했다. v181 `20260529_144914_316168` 기준 `11718082`는 이미지 OCR/VLM 근거로 `재벌가 차녀의 2회차 걸그룹` resolved, `11718080`은 작품 특정 불가 한탄/장르 일반론으로 rejected 유지.
- [x] `11718080`은 전문가가 장르/한탄글로 맞게 거부한 뒤 후단 `batch memory alias rescue`가 뒤집은 문제를 별도 semantic guard로 막았다. `late_rescue_blocked_by_verifier_generic_veto` 회귀 테스트를 추가했고, 특정 post id나 alias 하드코딩 없이 Verifier generic-discourse veto와 공개 evidence 조건으로 차단한다.

## 2026-05-29 v180 goal/reuse-only explicit endpoint healthy filter

- [x] goal/test run의 Docker Compose `up/recreate` hard opt-in 정책은 유지했다.
- [x] `MCP_ENDPOINTS`가 명시 endpoint 목록이어도 36건 이하 goal/test 또는 `--reuse-shards-only`에서는 healthy endpoint subset으로 줄이도록 했다.
- [x] autogen 전용 메타와 별도로 `mcp_healthy_endpoint_filter`, `mcp_healthy_endpoint_filter_autogen`을 남기도록 했다.
- [x] large explicit endpoint validation은 기본적으로 실패 endpoint를 그대로 드러내도록 회귀 테스트로 분리했다.
- [x] goal/reuse-only health failure 안내에서 `warp_shards.py up`을 기본 해결책처럼 제시하지 않고, Docker lifecycle 차단과 명시 opt-in 조건을 안내하도록 했다.
- [x] `py_compile`과 `tests.test_expert_main_input_loader` 27건을 통과했다.
- [ ] 다음 live goal run manifest에서 explicit endpoint 필터가 필요한 경우 `mcp_healthy_endpoint_filter=true`, Docker/Compose 실행 흔적 `0`건을 확인한다.

## 2026-05-29 v178 title-lead alias deliberation skip

- [x] `11718097` long-tail 원인이 Docker Compose가 아니라 `Decoder=None but Verifier=relevant` 충돌 후 full Jury/Debate로 들어가는 전문가 오케스트레이션 비용임을 v177에서 재확인했다.
- [x] 제목 첫 토큰 alias가 검색 결과 `title` 필드에서 동일 작품명으로 직접 닫히는 경우에만 score `2.0`에서도 full deliberation을 스킵하도록 했다.
- [x] memory-query, Gatekeeper original noise, recommendation, author/trope/genre target, critical counterargument는 이 fast-path에서 제외한다.
- [x] 조건은 post id/약칭 하드코딩 없이 공개 title/evidence/expert fields 기반으로 구성했다.
- [x] `py_compile`, `DeliberationLimitTest` 5건, 기존 회귀 묶음 354건을 통과했다.
- [x] v178 live run `20260529_141334_062130`에서 `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`, `11718083/11718091` title null을 확인했다.
- [x] v178 W2 로그에서 `11718097`이 `심의 스킵: title-lead alias search bridge resolved`, `method=evidence_scorer_only`, `2 iterations`로 종료됐다.
- [x] v178 통합/워커 로그에서 `full_deliberation_ABC`/debate/jury와 Docker/Compose/shard lifecycle 실행 흔적이 모두 `0`건임을 확인했다.
- [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v176 goal/test Compose status-audit hard block

- [x] goal/test regression에서 Docker Compose `up/recreate`뿐 아니라 `warp_shards.py status` 기반 Compose status/exec 조회도 기본 차단했다.
- [x] `MCP_LOCAL_SHARD_STATUS_AUDIT=1`만 남아 있는 stale env로는 small goal/test run의 local shard management에 들어가지 않는다.
- [x] status audit 자체가 목적이면 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`과 `MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT=1`을 함께 둔다.
- [x] manifest/run config에 `mcp_local_shard_status_audit_requested`, `mcp_local_shard_status_audit_allowed`를 남긴다.
- [x] `py_compile`과 `tests.test_expert_main_input_loader` 25건을 통과했다.
- [x] v175 live manifest/log에서 `mcp_local_shard_management_enabled=false`, `mcp_local_shard_status_audit=false`, Compose 관련 로그 `0`건을 재확인했다.
- [x] v178 live run에서도 shard lifecycle/status audit 관련 opt-in 없이 `--reuse-shards-only`로 Compose 관련 로그 `0`건을 재확인했다.
- [ ] 이 변경은 runtime/operation gate이며, 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-29 v175 memory-query weak-title forced-upgrade guard

- [x] memory-query 글에서 direct proof가 없고 relation judge가 hold/downgrade한 weak title candidate는 추가 collaboration/full deliberation으로 끌고 가지 않는다.
- [x] Arbiter suspected-title forced-upgrade와 deliberate-null 우회를 같은 조건에서 차단한다.
- [x] 조건은 post id 하드코딩 없이 공개 필드, direct anchor, relation/evidence flags로만 구성했다.
- [x] v175 live run `20260529_134510_545218`에서 known-bad 4건이 모두 semantic 기대값으로 유지됐다.
- [x] `11718083`은 v174 `330.9s`에서 v175 `102.6s`로 줄었다.
- [x] v175 manifest/log 기준 Docker Compose lifecycle/status audit 실행 흔적 `0`건을 확인했다.
- [x] `py_compile`과 focused memory-query regression 5건을 통과했다.
- [x] `11718097` full deliberation long-tail은 v178 title-lead alias deliberation skip으로 targeted canary 기준 닫았다.
- [ ] targeted canary 통과만으로 10만 건 semantic gate를 올리지 않는다.

## 2026-05-29 v173 memory-query unresolved fast-path

- [x] Verifier 출력이 없는 상태에서는 memory-query settled fast-finalize를 열지 않는다.
- [x] Verifier가 no-title/weak bridge/hold-nullify로 정리한 memory-query unresolved 케이스는 추가 collaboration을 종료한다.
- [x] 위 조건에서는 Synthesizer를 열지 않고 finalizer로 넘긴다.
- [x] 위 조건에서는 full Jury/Debate 대신 `evidence_scorer_only`로 Deliberation을 종료한다.
- [x] direct quote/source, official URL, character/title link, direct title anchor가 있으면 fast-path를 열지 않는다.
- [x] v172의 빈 Verifier 조기 skip 위험은 `test_memory_query_settled_rejection_waits_for_verifier_output`로 차단했다.
- [x] v173 live run `20260529_132113_820839`에서 Decoder/Verifier 각 1회 뒤 Synthesizer/Jury/Debate가 열리지 않음을 확인했다.
- [x] v173 result에서 `11718083`은 `is_relevant=false`, `novel_identity=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`로 유지됐다.
- [x] v173 manifest/log에서 Docker Compose lifecycle 실행 흔적 `0`건을 확인했다.
- [x] `py_compile`, focused regression 5건, 관련 통합 회귀 349건을 통과했다.
- [ ] v173은 targeted canary이므로 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.
- [ ] search/deep-search/page analyzer/대형 Decoder prompt 잔여 병목은 별도 P1로 줄인다.

## 2026-05-29 v171 env-only Docker lifecycle block

- [x] `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수만으로는 Docker Compose `up/recreate`가 열리지 않도록 했다.
- [x] env 기반 lifecycle은 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` 또는 legacy `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1` ack를 요구한다.
- [x] Codex 또는 36건 이하 goal/test run에서는 env ack가 있어도 현재 명령의 `--allow-goal-shard-lifecycle` 없이는 lifecycle을 열지 않는다.
- [x] `MCP_SMALL_RUN_ALLOW_SHARD_LIFECYCLE=1` 같은 stale env만으로 small goal/test run block을 해제하지 않는다.
- [x] manifest/run config에 `mcp_env_shard_lifecycle_requested`, `mcp_env_shard_lifecycle_global_opt_in`을 기록한다.
- [x] `tests.test_expert_main_input_loader` 25건, 관련 통합 회귀 344건, `py_compile`을 통과했다.
- [x] 현재 관련 Python 점유가 없고 Docker shard group `1..5`가 기존 상태로 유지되는 것을 확인했다.
- [x] v171 live goal run `20260529_125908_474586`에서 `requested_parallel=36`, `effective_parallel=1`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`를 확인했다.
- [x] v171 log grep 기준 `docker`, `compose`, `force-recreate`, `warp_shards.py` 실행 흔적은 모두 `0`건이었다.
- [ ] shard lifecycle 자체를 검증할 때만 현재 명령에 `--allow-goal-shard-lifecycle --auto-up-shards` 또는 `--allow-goal-shard-lifecycle --auto-recreate-shards`를 함께 붙인다.
- [ ] 이 변경은 runtime/lifecycle 정책이며, 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-29 v169 settled Verifier veto skip

- [x] Verifier critical veto + 음수 evidence + `official_title=null` 상태에서는 Jury/Debate를 열지 않는 fast-path를 추가했다.
- [x] direct title proof가 본문에 있는 경우에는 fast-path가 심의를 스킵하지 않도록 회귀 테스트를 추가했다.
- [x] Jury/Debate 기본 max tokens를 `2048`로 낮췄다.
- [x] v169 단건 live run에서 `11718083`이 `is_relevant=false`, `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`로 유지되는지 확인했다.
- [x] v169 manifest에서 `requested_parallel=36`, `effective_parallel=1`, `completed/flushed/pending/failed=1/1/0/0`을 확인했다.
- [x] v169 log에서 `심의 스킵: Verifier critical veto + 음수 evidence로 비관련 확정`과 `method=evidence_scorer_only`를 확인했다.
- [x] v169 log/manifest에서 Docker Compose lifecycle 미진입을 확인했다.
- [ ] v169 단건 `441.6s`/`176,274` tokens/search degraded `10/13` 성능 병목은 별도 P1로 최적화한다.
- [ ] v169는 targeted canary이므로 10만 건 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-29 v167 goal/test compose avoidance and partial subset preservation

- [x] goal/test run의 Docker lifecycle은 `--allow-goal-shard-lifecycle` 없는 기본 경로에서 차단되는지 회귀 테스트로 재확인했다.
- [x] `--parallel 36`은 최대치이며, 소규모 입력에서 worker/shard를 맞추기 위해 compose를 재시작하지 않는다는 운영 규칙을 유지했다.
- [x] 병렬 ordered flush gap이 남으면 `_completed_subset.json`과 `_completed_subset_manifest.json`을 별도 산출물로 남기도록 했다.
- [x] primary result JSON은 ordered flushed prefix로 보존하고, recovery artifact와 approval source를 분리했다.
- [x] manifest에 `partial_flush_gap`, `ordered_flush_blocked`, `completed_subset_written`, `completed_subset_count`, `large_run_complete`를 기록한다.
- [x] `tests.test_expert_main_input_loader` 24건과 `py_compile`을 통과했다.
- [ ] 실제 다음 large rerun manifest에서 `large_run_complete=true`, `pending_count=0`, `flushed_count=completed_count=input_post_count`를 확인하기 전까지 10만 건 run completion은 승인하지 않는다.

## 2026-05-29 v166 large rerun readiness plan

- [x] 원본 partial/recovered source가 아니라 새 completed source가 필요하다는 실행 계획을 남겼다.
- [x] reuse-only safe mode는 Docker lifecycle 없이 현재 healthy shard만 쓰는 모드로 분리했다.
- [x] explicit 36-shard validation mode는 shard lifecycle 의도를 명시해야 하는 모드로 분리했다.
- [x] 현재 Docker 상태는 shard group `1..5`만 확인됐으므로, 36 worker 처리량을 기대하려면 shard 준비가 별도 필요하다고 기록했다.
- [x] large rerun 후 `audit_expert_run_health.py`, `preflight_qualitative_large_scale_review.py`, random baseline, high-risk expansion 순서를 기록했다.
- [ ] 실제 rerun은 기존 `out\expert_result_20260528_141006_620986*`를 덮어쓰지 않는 새 output으로만 실행한다.

## 2026-05-29 v165 large-scale qualitative preflight

- [x] large-scale review 전에 source completeness와 sampling feasibility를 검사하는 preflight 도구를 추가했다.
- [x] preflight는 manifest `input_post_count/completed_count/flushed_count/pending_count/failed_count`를 분리 검사한다.
- [x] preflight는 checkpoint completed rows와 pending snapshot rows를 함께 기록한다.
- [x] preflight는 random baseline 1,000건 feasibility와 shortfall을 계산한다.
- [x] preflight는 high-risk bucket target/population을 기록한다.
- [x] 원본 final result source는 `result_rows=71`, `random_shortfall=929`, partial signals 때문에 `REVIEW-LOCKED`다.
- [x] recovered subset source는 `result_rows=80`, `source_is_checkpoint_recovered_subset`, `random_shortfall=920` 때문에 `REVIEW-LOCKED`다.
- [ ] preflight `REVIEW-LOCKED` source에서 생성된 리뷰 결과는 large-scale semantic approval 근거로 쓰지 않는다.

## 2026-05-29 v164 sample target shortage audit

- [x] random control manifest는 `requested_sample_size`와 `selected_sample_size`를 분리한다.
- [x] random control manifest는 `sample_shortfall`, `sample_target_satisfied`, `sample_coverage_ratio`를 기록한다.
- [x] Round2 manifest는 high-risk bucket `target_total`, `selected_total`, `target_satisfied`, `target_shortfalls`를 기록한다.
- [x] gate는 random baseline 1,000건 미달과 Round2 target 미달을 `Weak/Missing` evidence로 표시한다.
- [x] v164 audit에서 recovered subset 80건 기준 Round2 `selected=79/target=340`, random `selected=1/requested=1000`으로 표본 부족을 확인했다.
- [ ] current recovered subset 기반 산출물은 large-scale semantic approval 근거로 쓰지 않는다.

## 2026-05-29 v163 recovered subset review source policy

- [x] Round2 review builder가 recovered artifact 경로에서 원본 run id `20260528_141006_620986`을 추론한다.
- [x] Round2 manifest/sample manifest/gate에 `source_review_policy.source_dataset_kind=checkpoint_recovered_completed_subset`을 남긴다.
- [x] `source_review_policy.large_run_complete=false`와 `approval_policy`로 recovered subset이 10만 건 approval 근거가 아님을 명시한다.
- [x] random control builder도 source policy를 남기고, random 추가 후 canonical summary/gate를 재계산한다.
- [x] random control builder가 canonical summary 재계산 시 Round2 manifest의 run id/seed를 재주입해 gate 제목/seed 오염을 막는다.
- [x] v163 smoke: recovered subset 80건에서 Round2 30건, random 20건, canonical labels 50건, gate `NO-GO`를 확인했다.
- [ ] v163은 도구 검증용 소표본이므로 expanded random/high-risk review 전까지 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 v162 partial run checkpoint recovery

- [x] 원본 run `20260528_141006_620986`의 final result `71`, checkpoint completed `80`, pending snapshot `9` 차이를 재검증했다.
- [x] final에 없는 checkpoint completed post 9건이 pending snapshot 9건과 정확히 일치함을 확인했다.
- [x] ordered flush가 `global_idx=72` 미완료 row에서 막혀 이후 completed row가 pending snapshot에 남은 `recoverable_pending_flush_gap`으로 분류했다.
- [x] `tools/recover_expert_run_from_checkpoint.py`로 checkpoint completed subset 80건을 원본 덮어쓰기 없이 복구했다.
- [x] `tests.test_recover_expert_run_from_checkpoint`와 관련 `py_compile`을 통과했다.
- [ ] 원본 10만 run은 `pending_count=9`, `flushed_count<completed_count`, clean completion summary 부재로 계속 전체 run approval 근거에서 제외한다.
- [x] 후속 review builder는 final result-only, recovered subset, checkpoint+pending explanation 중 어떤 기준을 썼는지 `source_review_policy`로 manifest에 남긴다.

## 2026-05-29 v161 comment author context lines

- [x] result row `comment_context_lines`에 `author=<comment author>`를 포함한다.
- [x] pipeline prompt용 `comment_context_lines`에도 `author=`를 포함한다.
- [x] qualitative review packet 재구성 경로도 `comment_metadata.author`에서 `author=`를 복원한다.
- [x] 댓글 본문 문자열에는 작성자/IP를 합치지 않고, 공개 메타 필드로만 분리한다.
- [x] v161 live regression에서 `11718091`은 `#1 speaker=post_author author=ㅇㅇ role=post_author comment_id=40479972`를 남겼다.
- [x] v161 live regression에서 `11718097`은 5개 comment context line에 post author/user speaker와 `author=`를 남겼다.
- [x] v161 manifest/log에서 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`, Docker/warp lifecycle 미진입을 확인했다.
- [x] `qualitative_review\20260528_141006_620986\v161_goal_status_audit_ko_20260529.md`에 요구사항별 완료/미완료/증거부족 상태를 분리 기록했다.
- [x] 원본 partial run `104,502` 입력 중 completed `80`, final rows `71`, pending `9` 상태는 v162에서 복구 가능한 pending flush gap으로 분류했으며, 전체 run approval 근거로 쓰지 않는다.
- [ ] v161은 targeted regression이므로 10만 건 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 v159 memory-query batch alias rescue guard

- [x] `11718083` memory-query quote post에서 `plot_mention`은 direct title proof로 승격하지 않는다.
- [x] BatchContext alias rescue는 `memory_query_canonical_rescue_blocked_title` 또는 direct title proof 없는 memory-query title을 다시 official title로 만들지 않는다.
- [x] `test_memory_query_batch_alias_rescue_does_not_override_blocked_canonical_title`를 추가했다.
- [x] `tests.test_agentic_pipeline_rework` 305건, `tests.test_expert_main_input_loader` 23건, py_compile을 통과했다.
- [x] v159 live run에서 `11718083`은 `is_relevant=false`, `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`로 내려갔다.
- [x] v159 manifest/log에서 `requested_parallel=36`, `effective_parallel=1`, Docker Compose lifecycle 미진입, forbidden batch alias registration 미발생을 확인했다.
- [x] v160 known-bad 5건 묶음 regression에서 `11718083/11718091/11718118`은 title null, `11718097=망겜의 힐러`, `11718099=빌어먹을 환생`으로 확인했다.
- [x] v160 manifest/log에서 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`, Docker/warp lifecycle 미진입을 확인했다.
- [ ] v159/v160은 targeted regression이므로 expanded random/high-risk review 전까지 10만 건 semantic gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 Codex goal env lifecycle hard opt-in v3

- [x] Codex goal/test run에서는 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1`이 있어도 현재 명령에 `--allow-goal-shard-lifecycle`이 없으면 Docker Compose `up/recreate`를 열지 않는다.
- [x] env 기반 lifecycle이 정말 필요한 Codex 실행은 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1`과 현재 명령의 `--allow-goal-shard-lifecycle`을 함께 요구한다.
- [x] `tests.test_expert_main_input_loader`에 env-only 차단과 env+command hard opt-in 허용 회귀 테스트를 분리했다.
- [x] v157 metadata-preserved known-bad live run에서 `--reuse-shards-only`, `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`을 확인했다.
- [x] v157 manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`, `mcp_env_shard_lifecycle_allowed=false`를 확인했다.
- [x] v157 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py`, `compose up/down` 실행 흔적이 없음을 확인했다.
- [x] v157 `11718083` wrong-title resolved 재발은 v159 memory-query quote/source-title guard와 batch alias rescue guard로 단건 canary 기준 차단했다.

## 2026-05-29 official URL evidence bucket detail-only filter

- [x] v153 `11718097`에서 `heretic_url=null`인데 reason `official_urls=5`가 남는 evidence accounting 불일치를 확인했다.
- [x] `ridibooks.com/author/...`, search/list/ranking/genre URL, Kakao `tab_type=comment`는 `official_urls` 강근거로 카운트하지 않도록 했다.
- [x] Verifier 저장 경로와 pipeline bucket 읽기 경로를 모두 detail-only로 막았다.
- [x] focused regression 3건을 통과했다.
- [x] `tests.test_agentic_pipeline_rework` 304건을 통과했다.
- [x] v154 live run에서 `11718097`은 `official_urls=0`, `heretic_url=null`, `official_title_evidence=false`로 reason/final alignment가 맞는 것을 확인했다.
- [x] v154 live run에서 `11718099`는 Naver Series 작품 상세 URL로 유지되는 것을 확인했다.
- [ ] expanded high-risk review에서 `official_urls>0`인데 `heretic_url=null` 또는 작가/목록 URL만 있는 케이스를 별도 bucket으로 추출한다.

## 2026-05-29 unresolvable memory query slang pending guard

- [x] `11718083` v153 결과에서 `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`인데 `secondary_reference` pending이 저장되던 경로를 확인했다.
- [x] memory-query/recommendation 컨텍스트에서는 `secondary_reference`, `mentioned_work`, `recommendation_candidate`, `comparison_target`를 slang DB pending으로 저장하지 않도록 했다.
- [x] 기존 polluted confirmed alias가 다음 run의 BatchContextMemory seed로 들어가지 않도록 seed 주입 안전성 필터를 추가했다.
- [x] v153 slang DB의 `네이버/네가` confirmed alias가 seed unsafe로 판정되는 것을 확인했다.
- [x] DB flush/finalize cleanup에서 polluted confirmed/pending entry를 제거하도록 했다.
- [x] v153 slang DB 사본 cleanup에서 title count `373 -> 354`, `네이버/네가`, `너에겐` 제거를 확인했다.
- [x] `adjacent_meta`와 `trope_discussion` pending 분류는 유지되는 focused regression을 통과했다.
- [x] `tests.test_slang_db` 23건을 통과했다.
- [x] v153 `11718083` exact row를 현재 추출기에 통과시켜 `observation_count=0`을 확인했다.
- [ ] 기존 polluted slang DB 파일을 seed로 재사용할 때는 cleanup/review queue를 별도로 적용한다.

## 2026-05-29 high-risk bucket expansion v156

- [x] v155에서 발견한 신규 high-risk flag를 Round 2 bucket으로 승격했다.
- [x] run id가 `20260505_214349_324347`로 고정되는 builder 오염을 제거하고 `20260528_141006_620986`로 기록되는지 확인했다.
- [x] rare bucket 선점 순서와 `covered_counts`를 추가해 중복 post dedupe 때문에 bucket coverage가 0처럼 보이는 문제를 줄였다.
- [x] v156 `round2_packets.jsonl`, `round2_labels.jsonl`, `sample_manifest.json`, `pattern_summary.md`, `gate_decision.md`, `action_queue.md`를 생성했다.
- [x] known-bad `11718083`, `11718091`, `11718097`, `11718099`가 v156 packet에 포함되는지 확인했다.
- [x] v156b packet에 `gallery_id`, `post_author`, `comment_metadata`, `comment_context_lines`, `comment_context_source`를 포함하도록 했다.
- [x] `comments_without_author_metadata` selected 5건은 `INFO_MISSING/human_review`로 승인 제외했다.
- [ ] v156 packet은 자동 label이므로 실제 자연어 정성 검토 완료로 취급하지 않는다.

## 2026-05-29 original partial run semantic pattern scan v155

- [x] 원본 result, checkpoint, manifest, pending snapshot을 함께 인벤토리했다.
- [x] manifest `input_post_count=104502`와 completed `80`, final rows `71`, pending `9`를 분리 보고했다.
- [x] 10만 전체 완료 결과가 아니라 partial run triage 근거로만 취급하도록 기록했다.
- [x] known-bad 4건의 원본 오판 title과 반복 flag를 확인했다.
- [x] 댓글 author metadata 누락, weak-evidence resolved, image/OCR 개입, platform non-detail URL 근거 혼선 bucket을 후속 review 대상으로 올렸다.

## 2026-05-29 small goal/test run shard lifecycle hard opt-in v2

- [x] 36건 이하 goal/test 실행은 Codex 여부와 무관하게 `--auto-up-shards`/`--auto-recreate-shards`만으로 Docker Compose `up/recreate`가 켜지지 않는다.
- [x] 36건 이하에서 shard 복구 자동화 자체를 검증할 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 사용한다.
- [x] 일반 PowerShell에서 실수로 `--auto-*`가 붙어도 36건 이하에서는 hard opt-in 없이는 local shard management가 비활성으로 남는다.
- [x] `tests.test_expert_main_input_loader`에 non-Codex small goal run 차단 회귀 테스트를 추가했다.

## 2026-05-29 Codex goal run shard lifecycle hard opt-in

- [x] Codex goal/test 실행에서는 `--auto-up-shards`/`--auto-recreate-shards`만으로 Docker Compose `up/recreate`가 켜지지 않는다.
- [x] shard 복구 자동화 자체가 검증 대상일 때만 `--allow-goal-shard-lifecycle`과 `--auto-up-shards` 또는 `--auto-recreate-shards`를 함께 사용한다.
- [x] manifest/run config에 `mcp_allow_goal_shard_lifecycle`, `mcp_command_shard_lifecycle_allowed`를 남긴다.
- [x] `py_compile`과 `tests.test_expert_main_input_loader` 21건을 통과했다.
- [x] `expert_main.py --help`에서 `--allow-goal-shard-lifecycle` 노출을 확인했다.

## 2026-05-29 late rescue alias self-confirmation guard

- [x] v151에서 `grounding_anchor:none`, `evidence_bucket=0`, `critical`인데도 `batch_memory_exact_alias_rescued`가 title을 되살린 경로를 확인했다.
- [x] `batch_memory`/`title_surface` late rescue는 alias support만으로 direct work bridge를 만들 수 없게 했다.
- [x] evidence bucket 0 + weak grounding + critical 신호에서는 public work anchor가 없으면 title rescue를 차단한다.
- [x] late-rescue contaminated 결과는 slang DB `primary_work`/`title_candidate` alias observation으로 저장하지 않는다.
- [x] `tests.test_agentic_pipeline_rework` 301건과 `tests.test_slang_db` 20건을 통과했다.
- [x] v152 live run에서 polluted slang DB seed를 둔 상태로도 known-bad false positives가 `official_title=null`로 내려갔다.
- [ ] expanded high-risk review에서 같은 패턴의 재발률을 확인한다.

## 2026-05-29 Codex goal run env lifecycle guard

- [x] Codex 실행 환경에서는 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` env만으로 Docker Compose `up/recreate`가 켜지지 않는다.
- [x] 37건 이상 goal/test 입력도 Codex env guard 적용 대상이다.
- [x] Codex goal/test 실행에서는 `--auto-up-shards`/`--auto-recreate-shards`만으로 부족하고 `--allow-goal-shard-lifecycle`까지 요구한다.
- [x] env 기반 lifecycle opt-in은 `MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1`과 현재 명령의 `--allow-goal-shard-lifecycle`을 함께 요구한다.
- [x] manifest/run config에 `mcp_interactive_codex_run`, `mcp_env_shard_lifecycle_allowed`, `mcp_env_shard_lifecycle_blocked_by_context`를 남긴다.
- [x] `py_compile`과 `tests.test_expert_main_input_loader` 20건을 통과했다.
- [x] v152 live goal/test run manifest에서 Codex env guard 메타와 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`를 확인했다.
- [x] v152 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py up/recreate`, `compose up` 실행 흔적이 없음을 확인했다.

## 2026-05-29 goal run healthy shard 기본 필터

- [x] 36건 이하 goal/test run은 lifecycle opt-in이 없으면 autogen endpoint를 기본 8개로 제한한다.
- [x] lifecycle-blocked goal/test run은 `--reuse-shards-only`가 없어도 healthy autogen endpoint만 남기고 failed endpoint 때문에 중단하지 않는다.
- [x] stale `MCP_SHARD_COUNT=36`/`MCP_AUTO_SHARD_LIMIT=36`도 lifecycle opt-in 없는 36건 이하 goal/test run에서는 기본 8개 cap을 따른다.
- [x] healthy endpoint filter 후 effective parallel은 healthy endpoint 수 이하로 낮춘다.
- [x] Codex goal/test에서 shard 복구 자동화까지 검증할 때는 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`를 함께 요구한다.
- [x] `py_compile`과 `tests.test_expert_main_input_loader` 17건을 통과했다.
- [x] v150 live goal run manifest/log에서 `mcp_goal_run_health_filtered`, `mcp_healthy_autogen_endpoint_filter`, endpoint count 메타를 확인했다.

## 2026-05-29 result row comment speaker context lines

- [x] `expert_main.py` 결과 row에 `comment_metadata`뿐 아니라 `comment_context_lines`도 남기도록 했다.
- [x] `comment_context_lines`는 `speaker`, `author`, `role=post_author`, `ip`, `reply_level`, `reply_to`, `comment_id`를 compact하게 포함한다.
- [x] 댓글 본문에는 author/IP를 섞지 않고 공개 메타 필드로 분리한다.
- [x] `tests.test_expert_main_input_loader` 13건과 focused pipeline comment context 테스트를 통과했다.
- [x] v150 live goal run 결과 JSON에서 `comment_context_lines` 필드가 실제 row에 남는지 확인했다.
- [x] 질적 리뷰 packet 생성 시 결과 row의 `comment_context_lines` 누락 여부를 `INFO_MISSING`/packet completeness 기준에 포함한다.

## 2026-05-29 title-lead alias discourse preservation

- [x] `11718097` v148 alias recall 비단조성을 검색 전 noise 조기 종료 문제로 분리했다.
- [x] 제목 선두 alias가 Discourse novel term/search suggestion에도 재포착되고 캐릭터/플롯 논의 신호가 있으면 `worklike_alias_preservation`으로 noise 조기 종료를 보류한다.
- [x] noise override 직후 검색 복구는 Discourse가 재포착한 제목 선두 alias만 대상으로 제한한다.
- [x] `빌런이였어야돼` 같은 술어 꼬리는 제목표면 검색 seed에서 제외한다.
- [x] weak single-token/vent 계열은 기존처럼 noise로 남는 negative control을 유지했다.
- [x] `tests.test_agentic_pipeline_rework` 298건과 `tests.test_expert_main_input_loader` 12건을 통과했다.
- [x] v178에서 `11718097` 포함 known-bad set live rerun으로 actual output을 확인했다.
- [x] 검색 회복과 final title 승인을 분리해 확인했다. `11718097`은 `망겜의 힐러`로 resolved지만 공식 URL 근거가 약하므로 evidence strength는 `Medium` 축으로 유지한다.

## 2026-05-29 v149 reason/evidence-zero title guard

- [x] 공식 플랫폼 검색 hit 단독으로 final title을 확정하는 경로를 재검토했다.
- [x] evidence bucket이 비어 있고 원문 anchor/alias bridge/strong character-work link가 없으며 verifier가 critical 또는 thematic/absent grounding을 낸 경우 `official_search_only_without_post_anchor`로 demotion하도록 했다.
- [x] 영화/이미지 의존/일반 토론 계열을 synthetic regression으로 고정했다.
- [x] 공식 플랫폼 근거와 실제 post/evidence bucket이 함께 있는 positive control은 유지했다.
- [x] `tests.test_agentic_pipeline_rework` 297건과 `tests.test_expert_main_input_loader` 12건을 통과했다.
- [x] v149 targeted input과 한국어 검토 노트/action queue를 남겼다.
- [ ] LLM endpoint 복구 후 v149 targeted rerun으로 exact post 결과를 확인한다.
- [ ] v149도 targeted regression이므로 expanded random baseline 전까지 10만 건 semantic `GO` 근거로 쓰지 않는다.

## 2026-05-29 goal/test run local shard management 차단 보강

- [x] 기본 goal/targeted run에서 `docker compose up`/`force-recreate`뿐 아니라 `warp_shards.py status/ensure` 관리 경로도 들어가지 않도록 `_can_auto_manage_local_shards()`를 좁혔다.
- [x] 36건 이하 goal/test regression에서는 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수가 남아도 up/recreate가 켜지지 않도록 lifecycle 차단 기준을 입력 post 수 기준으로 분리했다.
- [x] lifecycle 차단 기준은 `MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD` 기본 `36`으로 기록하고, endpoint 자동 생성 제한용 `MCP_SMALL_RUN_SHARD_THRESHOLD`와 분리했다.
- [x] shard status 감사만 필요할 때는 `MCP_LOCAL_SHARD_STATUS_AUDIT=1`로 명시 opt-in 하도록 했다.
- [x] `--auto-up-shards`, `--auto-recreate-shards`는 복구 자동화 검증용 opt-in으로 유지했다. env `MCP_AUTO_*`는 v171 이후 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1` ack가 있어야 인정한다.
- [x] `test_default_goal_run_does_not_enter_local_shard_management` 회귀 테스트를 추가했다.
- [x] manifest/run config에 `mcp_local_shard_management_enabled`, `mcp_local_shard_status_audit`를 남기도록 했다.
- [x] `py_compile` 및 `tests.test_expert_main_input_loader` 12건 재검증을 통과했다.
- [x] v150 live goal run manifest/log에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `docker compose`/`warp_shards.py status` 관리 경로 미진입을 확인했다.

## 2026-05-29 v148 reuse-only healthy shard filter 및 high-risk 24건

- [x] `--reuse-shards-only` 상태에서 자동 생성 endpoint 24개 중 healthy 5개만 사용하도록 `expert_main.py`를 수정했다.
- [x] healthy endpoint filter 후 `_PARALLEL`이 `24 -> 5`로 낮아지는 회귀 테스트를 추가했다.
- [x] `tests.test_expert_main_input_loader`가 `Ran 11 tests ... OK`로 통과했다.
- [x] v148 run id `20260529_043012_788628`에서 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=24/0/0`을 확인했다.
- [x] v148 manifest에서 `mcp_reuse_shards_only_health_filtered=true`, `mcp_healthy_endpoint_count=5`를 확인했다.
- [x] v148 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py up`, `warp_shards.py recreate`, `compose up` 실행 흔적이 없음을 확인했다.
- [x] v148 semantic labels와 live review를 한국어 산출물로 남겼다.
- [x] `11718097` alias recall 비단조성은 v178 live rerun에서 `망겜의 힐러` resolved 및 title-lead alias deliberation skip으로 targeted canary 기준 닫았다.
- [ ] `11718082`, `11718080`, `11718090` false positive 계열을 reason-final contradiction bucket으로 승격한다.
- [ ] `11716486` 같은 이미지 의존 generic word 케이스는 브라우저/VLM 직접 확인 없이는 Strong evidence로 승격하지 않는다.
- [ ] v148 targeted 24건은 10만 건 semantic `GO` 근거가 아니므로 gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 v147 goal 테스트런 / weak-character preserve 차단

- [x] v146 live 결과에서 `11718091`의 memory-query 오분류는 사라졌지만 `unresolved_worklike_preserve`가 `is_relevant=true`를 다시 올리는 문제를 확인했다.
- [x] weak-character reaction guard를 `unresolved_worklike_preserve`, final identity validator, batch memory alias rescue에 적용했다.
- [x] 검색 후보/alias support가 있어도 원문이 캐릭터 나이/외모 짧은 반응이고 Verifier가 `community_banter/reject`이면 title rescue를 차단한다.
- [x] post author 댓글은 대화 흐름에는 쓰되 독립 작품 identity evidence로 승격하지 않는 정책을 회귀 테스트로 고정했다.
- [x] focused 4건 테스트, `py_compile`, `tests.test_expert_main_input_loader`, `tests.test_agentic_pipeline_rework` 295건을 통과했다.
- [x] v147 live run id `20260529_040313_425572`에서 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`을 확인했다.
- [x] v147 manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_run_shard_lifecycle_blocked=true`를 확인했다.
- [x] v147 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py recreate`, `compose up` 실행 흔적이 없음을 확인했다.
- [x] v147 `11718091`은 `is_relevant=false`, `official_title=null`, `title_resolution_state=unresolved_matchable`, flags=`weak_character_reaction_unresolved_blocked`, `post_author_comment_not_independent_evidence`로 확인했다.
- [ ] v147도 5건 targeted regression이므로 10만 건 semantic `GO` 근거로 쓰지 않는다. expanded random baseline과 P0/P1 high-risk review 전까지 gate는 `REVIEW-LOCKED`로 유지한다.

## 2026-05-29 goal/test run docker lifecycle opt-in 정책

- [x] `expert_main.py`의 `docker compose up` 자동 실행을 입력 건수와 무관하게 기본 비활성으로 바꿨다.
- [x] WARP/search 실패 shard `force-recreate` 자동 실행을 입력 건수와 무관하게 기본 비활성으로 바꿨다.
- [x] 자동 기동이 필요하면 `--auto-up-shards`를 명시하거나, env 자동화에서는 `MCP_AUTO_UP_SHARDS=1`과 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 둔다.
- [x] 자동 재생성이 필요하면 `--auto-recreate-shards`를 명시하거나, env 자동화에서는 `MCP_AUTO_RECREATE_SHARDS=1`과 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 둔다.
- [x] `MCP_SMALL_RUN_SHARD_THRESHOLD` 미만 goal/targeted run은 stale `MCP_AUTO_UP_SHARDS=1`/`MCP_AUTO_RECREATE_SHARDS=1` 환경변수가 남아 있어도 compose lifecycle과 compose 기반 shard ensure를 켜지 않게 했다.
- [x] 소규모 Codex goal/test run에서 shard 복구 자동화가 검증 대상이면 `--allow-goal-shard-lifecycle`과 `--auto-up-shards`/`--auto-recreate-shards`를 함께 명시한다.
- [x] `--reuse-shards-only`는 CLI/env opt-in보다 우선해 완전 재사용 모드로 동작하게 유지했다.
- [x] manifest/run config에 `mcp_small_run_shard_lifecycle_blocked`를 기록한다.
- [x] v141 goal live run manifest에서 `mcp_shard_lifecycle_policy=docker_up_recreate_opt_in`, `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`를 확인했다.
- [x] v141 goal live run log에서 `docker compose`, `force-recreate`, shard recreate 실행 흔적이 없음을 확인했다.
- [x] v145 known-bad goal run을 `--reuse-shards-only --parallel 36`으로 재실행해 `requested_parallel=36`, `effective_parallel=5`, `completed/failed/pending=5/0/0`을 확인했다.
- [x] v145 startup config에서 `auto_up=False`, `auto_recreate=False`, `small_run_lifecycle_blocked=True`를 확인했다.
- [x] v145 통합/워커 로그에서 `docker compose`, `force-recreate`, `warp_shards.py recreate`, `compose up` 실행 흔적이 없음을 확인했다.

## 2026-05-28 소규모 goal/targeted run shard 재사용 정책

- [x] 10건 미만 targeted/goal run은 기존 healthy shard 재사용을 기본으로 두고 `docker compose up` 자동 실행을 생략하도록 했다.
- [x] 10건 미만 targeted/goal run은 WARP/search 실패 shard `force-recreate` 자동 실행을 기본 생략하도록 했다.
- [x] 대형 canary/validation에서 자동 기동/재생성이 필요하면 CLI `--auto-up-shards`/`--auto-recreate-shards`를 우선 사용하고, env 자동화는 `MCP_AUTO_*`와 `MCP_ALLOW_ENV_SHARD_LIFECYCLE=1`을 함께 두도록 문서화했다.
- [x] `--no-auto-recreate-shards`, `--reuse-shards-only` 옵션을 추가했다.
- [x] `expert_main.py --help`에서 신규 옵션 노출을 확인했다.
- [x] v138 소규모 live run에서 `requested_parallel=36`, `effective_parallel=5`, healthy shard 2개 재사용, WARP/health attempt `1/1`을 로그로 확인했다.
- [x] v138 log에서 `docker compose`, `force-recreate`, shard recreate 실행 흔적이 없음을 확인했다.
- [x] v139 소규모 live run manifest에서 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_small_targeted_run=true`를 확인했다.
- [x] goal 테스트런에서 compose 재시작을 확실히 피해야 하면 `--reuse-shards-only`를 붙이는 운영 지침을 확인했다.

## 2026-05-28 v134 전문가 오케스트레이션/프롬프트 한계 감사

- [x] LLM 자연어 이해, 작품 identity, 후처리/구조 보정, 리뷰/승인 책임을 분리해 확인했다.
- [x] 프롬프트 보강만으로는 후단 rescue/demotion 비단조 오류를 막을 수 없음을 문서화했다.
- [x] `is_relevant` legacy bool이 소설 관련성, 단일 작품 매칭 가능성, 주변 담론을 함께 압축하는 한계를 재확인했다.
- [x] `PickvelIdentity`에 필요한 분리 필드(`is_novel_related`, `is_resolved_work_discussion`, `title_resolution_state`, `title_resolution_allowed`)가 없던 구조 한계를 확인했다.
- [x] 위 분리 필드를 backward-compatible optional field로 추가했다.
- [x] `_context_to_output()`에서 범위 분리 필드를 산출하고 reason에 `[범위 분리]` 공개 섹션을 붙이는 1차 구현을 추가했다.
- [x] `11718091`은 null-title 방어 성공과 별개로 reason/schema 혼선이 남아 `HOLD/docs_issue`로 유지한다.
- [x] `11718091` synthetic context에서 `is_novel_related=true`, `is_resolved_work_discussion=false`, `title_resolution_state=unresolved_matchable`, `title_resolution_allowed=false`를 검증했다.
- [x] `11718083` memory-query/no-anchor synthetic context에서 `title_resolution_state=unresolvable_memory_query`, `title_resolution_allowed=false`를 검증했다.
- [ ] 다음 구현에서는 reason-final contradiction detector를 고정한다.
- [ ] `title_lock_state`와 `evidence_edges`를 후처리 단계 및 review packet에 공개하는 설계를 진행한다.
- [ ] 구조 분리 전 targeted 성공만으로 10만 건 semantic `GO`를 내지 않는다.

## 2026-05-28 v133 metadata-preserved known-bad rerun

- [x] `tests/inputs/test01.jsonl`에서 known-bad 5건과 연결 comment row 6건을 추출해 `v133_known_bad_metadata_preserved_input.jsonl`을 작성했다.
- [x] 입력 로더 검증에서 `11718097` 댓글 5건, `11718091` 댓글 1건의 `comment_id`/`author`/`reply_to_comment_id`가 보존됨을 확인했다.
- [x] Gemma 4 4B vLLM 기준 `expert_main.py --parallel 36` 상한 run을 수행했다.
- [x] v133 manifest 기준 `requested_parallel=36`, `effective_parallel=5`, `completed=5`, `failed=0`, `pending=0`을 확인했다.
- [x] v133 after-review label은 `ACCEPT=4`, `HOLD=1`로 기록했다.
- [x] `11718083`, `11718097`, `11718099`, `11718118` known-bad 핵심 오판은 재발하지 않았다.
- [x] `11718091`은 `official_title=null`은 안전하지만 `noise/review/관련/비관련` reason 혼선이 남아 `HOLD/docs_issue`로 추적한다.
- [x] 10건 미만 소규모 targeted run은 자동 endpoint 생성 shard를 기본 2개로 제한하고 healthy shard 재사용을 우선하도록 `expert_main.py`를 보강했다.
- [x] `tests.test_expert_main_input_loader` 5건과 `py_compile expert_main.py tests\test_expert_main_input_loader.py`를 통과했다.
- [ ] v133은 5건 targeted regression이므로 10만 건 semantic `GO` 근거로 쓰지 않는다.
- [x] `11718091` 유형은 `is_novel_related`와 `is_resolved_work_discussion` 분리 필드의 synthetic regression으로 다뤘다.
- [x] `11718091` 유형은 v145 live LLM targeted rerun에서 `is_novel_related=true`, `is_resolved_work_discussion=false`, `title_resolution_state=unresolvable_memory_query`, `official_title=null`이 결과 JSON에 남는지 확인했다.
- [ ] `11718091`의 reason/flag taxonomy는 live 결과에서 `title null/noise`로 안전해졌지만 weak-character 전용 flag가 항상 노출되지는 않으므로 reason-final contradiction detector와 함께 후속 정리한다.

## 2026-05-28 v132 context metadata carrier audit

- [x] v132 `topic_particle_title_lead_alias_anchor` context audit packet을 재생성했다.
- [x] v132 감사에서 `11718097`, `11718118` packet의 `gallery_id`/`comment_metadata`/`comment_context_lines`가 없음을 확인했다.
- [x] v131 targeted canary는 title lock 회복 증거로만 보고, author/comment 대화 맥락 승인 근거로 쓰지 않도록 분리했다.
- [x] `expert_main.py` loader가 입력 row의 `comment_metadata`를 문자열 댓글에 index 기준으로 재부착하도록 보강했다.
- [x] targeted/review input builder가 원본 row의 `gallery_id`, `post_author`, `comments_raw`, `comment_metadata`, `comment_context_lines`를 보존하도록 보강했다.
- [x] `tests.test_expert_main_input_loader` 3건과 관련 py_compile을 통과했다.
- [x] 원본 crawl/input에서 실제 comment row 메타가 살아있는 source로 known-bad 5건을 다시 구성해 v133 dialogue-context 포함 targeted rerun을 수행했다.
- [ ] context metadata가 없는 packet은 자연어 대화 맥락 품질 승인에서 `INFO_MISSING` 또는 `REVIEW-LOCKED`로 둔다.

## 2026-05-28 v125-v131 post-Arbiter lock propagation re-check

- [x] v125 `topic_particle_title_lead_alias_anchor` bucket 7건을 재스캔해 `ACCEPT=5`, `REJECT=2`로 initial semantic triage했다.
- [x] `11718097`, `11718118` 두 REJECT를 v126-v128 targeted input으로 재실행했다.
- [x] v126에서 전문가/스니펫/Deliberation이 `망겜의 힐러`를 잡아도 후단 `final evidence-based title correction`과 batch memory author alias rescue가 `게임4판타지`로 뒤집는 것을 확인했다.
- [x] v127에서 `11718118` 장르/트로프 일반론이 `대협 -> 장르소설 마이너 갤러리/밈`으로 batch rescue되는 false positive를 확인했다.
- [x] v128에서 `11718118`은 `official_title=null`, `discussion_type=trope_discussion`, `anchor_type=genre`로 회복됐다.
- [x] v128에서 `11718097`은 wrong title final 삽입은 제거됐지만, `망겜의 힐러` correct title은 `HOLD/unresolved`로 남아 있음을 기록했다.
- [x] v129에서 `11718097` final title은 `망겜의 힐러`로 회복됐지만 canonical suspect 단계가 `오크 행복`으로 흔들리는 중간 비단조성을 확인했다.
- [x] v130에서 canonical suspect 기준을 좁힌 뒤 작가앵커-후보작가 충돌 guard가 locked title을 삭제해 `11718097`이 다시 `HOLD/unresolved`가 되는 실패를 회귀로 기록했다.
- [x] v131에서 snippet/alias lock, filtered official detail, title abbreviation stability를 author conflict guard보다 강한 보존 근거로 인정해 `11718097`과 `11718118` 모두 targeted `ACCEPT`로 닫았다.
- [x] 전문가 오케스트레이션/프롬프트 한계 문서에 v126-v128 증거와 후단 비단조 오류를 추가했다.
- [x] `11718097`은 snippet canonical alias lock을 canonical suspect 보정, unverified alias/plot demotion, author conflict guard가 공통으로 존중하게 보강했다.
- [x] filtered official detail(`token_mismatch:official`)은 snippet/alias lock과 같은 후보를 지지할 때 `weak_support`로 고려하도록 보강했다.
- [ ] v125-v131은 targeted/bucket evidence이므로 10만 건 semantic `GO` 근거로 쓰지 않는다.

## 2026-05-28 v124 title-leading alias recall

- [x] 기존 Python 점유 프로세스가 없는 상태에서 targeted rerun을 시작했다.
- [x] `망겜힐은` 같은 제목 첫 토큰 + 조사 패턴을 순수 약칭 `망겜힐`로 분리해 검색 앵커로 보존했다.
- [x] `망겜힐` 보존은 final title 하드코딩이 아니라 검색 후보 회수용 앵커이며, 최종 확정은 evidence edge를 요구한다.
- [x] 역할·호칭성 표현(`족장님` 등)은 여전히 단독 title rescue 근거로 쓰지 않는다.
- [x] focused 4 tests를 통과했다.
- [x] `tests.test_agentic_pipeline_rework` 전체 `271`건을 통과했다.
- [x] v124 targeted 4건 실서버 재실행에서 `requested_parallel=36`, `effective_parallel=4`, `completed=4`, `failed=0`, `pending=0`을 확인했다.
- [x] v124 after-review labels를 작성해 `ACCEPT=4`, `HOLD=0`, `REPROCESS=0`, `REJECT=0`, `INFO_MISSING=0`으로 분리했다.
- [ ] topic-particle title lead alias 보강은 high-risk expansion에서 false positive 증가 여부를 확인한다.
- [ ] v124 targeted canary만으로 10만 건 semantic `GO`를 내지 않는다.

## 2026-05-28 v122/v123 role/honorific alias rescue guard

- [x] v122 targeted 4건의 run health와 semantic/code label을 분리했다.
- [x] v122 `11718083`, `11718091`의 `post_data` NameError를 semantic 오판이 아니라 후처리 코드 오류 `REPROCESS`로 분류했다.
- [x] v122 `11718097`의 `족장님 -> 두 번 각성하는 대족장님` 확정을 역할·호칭성 search-inferred alias rescue 오삽입으로 분류했다.
- [x] 특정 작품명 하드코딩 없이 역할·호칭성 alias가 단독 title rescue 근거가 되지 않도록 일반 guard를 추가했다.
- [x] `_context_to_output()`의 `post_data` 참조가 `ctx.post_data` 기반으로 동작하도록 수정했다.
- [x] focused 4건 회귀와 전체 `tests.test_agentic_pipeline_rework` 269건을 통과했다.
- [x] v123 targeted 4건 실서버 재실행에서 `requested_parallel=36`, `effective_parallel=4`, `completed=4`, `failed=0`, `pending=0`을 확인했다.
- [x] v123 after-review labels를 작성해 `ACCEPT=3`, `HOLD=1`, `REPROCESS=0`, `REJECT=0`, `INFO_MISSING=0`으로 분리했다.
- [x] `11718097`은 wrong-title final 삽입 차단 성공과 correct title recall 미해결을 분리해 `HOLD/re_search`로 남겼다.
- [ ] `role_or_honorific_alias_rescue_blocked`를 high-risk expansion bucket에 추가하고, targeted canary 외 대형 표본에서 반복 여부를 검증한다.
- [ ] v123 targeted canary만으로 10만 건 semantic `GO`를 내지 않는다.

## 2026-05-28 v117 partial run semantic over-resolution guard

- [x] `out/expert_result_20260528_141006_620986_manifest.json` 기준 현재 산출물이 `input_post_count=104502`, `completed=80`, `flushed=71`, `pending=9`인 부분 런임을 분리 기록했다.
- [x] `11718083`, `11718099`, `11718091`, `11718097` 4건을 자연어 판정 오버리졸브 `REJECT` 케이스로 라벨링했다.
- [x] `네이버` 같은 플랫폼/커뮤니티 표면을 작품명 final title로 승격하지 않도록 guard를 보강했다.
- [x] `표지변경`, `작가 신작/최신화` 같은 meta action/status headline을 작품명 final title로 승격하지 않도록 guard를 보강했다.
- [x] 입력 post row의 `gallery_id`/`author`와 comment row의 `comment_id`/`author`/`ip`/reply 메타를 결과 및 전문가 context에 분리 보존하도록 보정했다.
- [x] 댓글 본문 문자열에는 작성자/IP를 섞지 않고 `comment_metadata`/`comment_context_lines`로만 전달하는 회귀 테스트를 추가했다.
- [x] py_compile과 focused comment author/IP context 테스트를 통과했다.
- [x] 4건 targeted rerun을 Gemma 4 4B 기준 `--parallel 36` 최대치로 수행하고, 실제 `effective_parallel=min(input_post_count,36)`을 manifest로 확인했다.
- [x] targeted rerun 후 after-review labels를 작성했고 `ACCEPT=2`, `REJECT=2`로 semantic gate를 계속 `NO-GO / REVIEW-LOCKED`로 유지했다.
- [x] v119 after-review를 작성해 `ACCEPT=1`, `HOLD=2`, `REJECT=1`로 분리하고, `11718083` memory-query 과확정과 `11718091` reason/final 충돌을 구조 이슈로 승격했다.
- [x] v121 단건 canary에서 `11718083`이 `official_title=null`, `novel_identity=null`, `work_resolution=none`, `anchor_type=none`으로 내려가는 것을 확인했다.
- [x] 전문가 오케스트레이션/프롬프트 한계 문서를 `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`로 추가했다.
- [x] prompt router에 memory-query/no-direct-anchor hard rule과 comment metadata 사용 경계를 추가했다.
- [ ] `11718091` reason/final 충돌과 unresolved preserve audit noise를 live 재검증한다.
- [ ] `11718097`은 틀린 title drift 제거와 별개로 `망겜의 힐러` correct title recall/HOLD를 추가 `re_search`로 닫는다.
- [ ] memory-query/no-anchor 패턴을 expanded high-risk bucket에서 검증하기 전까지 10만 건 semantic `GO`를 내지 않는다.

## 2026-05-28 v115/v116 alias common-word guard

- [x] 새 특정 작품명/URL 하드코딩 없이 검색 alias inference 보정을 진행했다.
- [x] `애들`, `사람들`, `성이` 같은 일반어/문법 조각이 작품 alias 후보로 승격되지 않도록 차단했다.
- [x] `웹소설 작법서`, `공략집`, `작성법`, `by ... 저` 같은 문서/가이드형 검색 결과 title을 작품 후보에서 제외했다.
- [x] v115 7건 targeted run에서 requested_parallel `36`, effective_parallel `7`, completed/failed/pending `7/0/0`을 확인했다.
- [x] v116 단건 targeted run에서 requested_parallel `36`, effective_parallel `1`, completed/failed/pending `1/0/0`을 확인했다.
- [x] v116에서 `post_id=11365197`이 `전1시 -> 전지적 1인칭 시점`으로 복구되는 것을 확인했다.
- [x] 관련 회귀 `298`건을 통과했다.
- [x] 한국어 review labels/summary/action queue를 생성했다.
- [ ] v115/v116 foreground shell exit code `1`과 manifest success 불일치를 후속 조사한다.
- [ ] `아집숨`, `탑매`, `괴출`, `성녀속마음 subtype` 잔여 HOLD/REPROCESS를 닫기 전까지 semantic `GO`를 내지 않는다.

## 2026-05-27 v108/v109 v105 REJECT alias recall closure

- [x] v105 `REJECT/re_judge` 7건의 원문 title/body/comments를 targeted input으로 재구성했다.
- [x] `아집숨`, `탑매`, `괴무직`, `괴담텔`, `전1시`, `괴출`, `성녀속마음` known title abbreviation 보강을 적용했다.
- [x] 조사/어미 suffix가 붙은 약칭 surface와 `KNOWN_TITLE_ABBREVIATIONS` fallback을 테스트했다.
- [x] source 라벨을 `known_abbreviation`과 `known_title_abbreviation`으로 분리했다.
- [x] `tests.test_agentic_pipeline_rework` `243`건과 alias/batch context `42`건을 통과했다.
- [x] v108 p7 targeted input/manifest를 생성했다.
- [x] LLM/shard preflight 후 v108 7건을 `--parallel 7`로 실서버 재실행했다.
- [x] v108 manifest에서 `requested_parallel=7`, `effective_parallel=7`, `input_post_count=7`을 확인했다.
- [x] v109 단건 neighbor guard를 `--parallel 1`로 재실행하고 `effective_parallel=1`을 확인했다.
- [x] v109 after-review label을 생성했고 `ACCEPT=4`, `HOLD=3`, `REJECT=0`을 확인했다.
- [ ] `탑매`, `괴담텔`, `괴출` HOLD 3건을 `re_search`/`re_judge`로 닫기 전까지 semantic `GO`를 내지 않는다.

## 2026-05-27 v105 targeted rerun 및 adaptive parallel

- [x] `http://10.20.0.101:8000/v1/models`에서 `bg-digitalservices/Gemma-4-E4B-it-NVFP4`를 확인했다.
- [x] v98 7건 실서버 run `20260527_190502_986325` completed `7`, failed `0`, pending `0`.
- [x] v102 25건 실서버 run `20260527_192017_408654` completed `25`, failed `0`, pending `0`.
- [x] v105 after-review labels `32`건을 생성했다.
- [x] after-review 분포 `ACCEPT=16`, `HOLD=9`, `REJECT=7`을 확인했다.
- [x] 소규모 targeted run 병렬도 정책을 `effective_parallel=min(requested_parallel,input_count)`로 정정했다.
- [x] `expert_main.py`가 `--parallel`을 고정 워커 수가 아니라 상한으로 해석하도록 보강했다.
- [x] manifest/run_meta에 `requested_parallel`, `effective_parallel`, `parallel_policy`, `input_post_count`를 남기도록 했다.
- [x] `REJECT/re_judge` 7건을 우선 재분석했다.
- [x] 다음 36건 미만 targeted run manifest에서 `effective_parallel=input_post_count`를 확인했다.
- [x] 소규모 run은 `--parallel 36` 명령값만 과했다는 이유로 재실행하지 않고, manifest의 `effective_parallel` 기준으로 판단하도록 지침을 정정했다.
- [ ] 남은 `HOLD`와 기존 10만 건 remaining queue closure 전까지 semantic `GO`를 내지 않는다.

## 2026-05-27 v104 runtime preflight 및 로컬 회귀

- [x] `http://127.0.0.1:8000/v1/models` 연결 실패를 재확인했다.
- [x] `:8000` listener가 없음을 확인했다.
- [x] 승인된 Python command line 조회에서 관련 LLM/expert 프로세스가 없음을 확인했다.
- [x] search shard audit `ok=36/36`, `bad=[]`를 확인했다.
- [x] `out/search_shard_audit_20260527_185927.json`을 생성했다.
- [x] 핵심 회귀 `74`건을 통과했다.
- [x] agentic pipeline rework `239`건을 통과했다.
- [x] LLM endpoint 확인 후 v98 7건과 v102 25건을 실서버로 재실행했다.
- [x] 다음 36건 미만 targeted run은 `--parallel 36`이 들어와도 `effective_parallel=input_post_count`로 자동 축소되는지 manifest로 확인한다.
- [ ] 실서버 result/checkpoint/log/manifest와 after-review label 전까지 semantic `GO`를 내지 않는다.

## 2026-05-27 v103 현재 10만 건 부족점/버그 정리

- [x] 최신 closure 기준 `ACCEPT=375`, `HOLD=208`, `INFO_MISSING=1`을 확인했다.
- [x] action 기준 잔여 큐 `human_review=122`, `slang_db_review=87`을 확인했다.
- [x] 현재 부족점/버그/해결 가능 항목을 `v103_current_100k_remaining_gap_bug_resolution_plan_ko_20260527.md`로 분리 정리했다.
- [x] v102 clean alias preservation targeted input `25`건을 생성했고 `missing_count=0`을 확인했다.
- [x] v105에서 v98 7건과 v102 25건을 Gemma 4 4B, `MCP_SHARD_COUNT=36`, `--no-auto-up-shards` 조건으로 실서버 재실행했다. 이후 36건 미만 targeted rerun은 `--parallel`을 상한으로 두고 `effective_parallel=input_post_count`를 확인한다.
- [ ] `human_review=122`, `slang_db_review=87`, `INFO_MISSING=1` closure 전까지 semantic `GO`를 내지 않는다.
- [ ] random baseline `1000+`와 P0/P1 high-risk expansion 전까지 10만 건 전체 품질 승인으로 해석하지 않는다.

## 2026-05-27 v102 clean alias preservation targeted input

- [x] v101 blocked contract spot review `25`건을 targeted rerun input으로 생성했다.
- [x] decision 분포 `BLOCK_TOO_STRONG=14`, `BLOCK_OK=6`, `NEEDS_CANONICAL_ALIAS_REVIEW=3`, `MISSING_SHORT_ALIAS_EXTRACTION=1`, `NEEDS_ALIAS_EVIDENCE=1`을 manifest에 기록했다.
- [x] `tools/build_v102_clean_alias_targeted_input.py` py_compile을 통과했다.
- [ ] LLM endpoint 복구 후 targeted result와 after-review label을 생성한다.
- [ ] result packet에서 noisy phrase 차단과 clean alias 보존이 동시에 성립하는지 확인한다.

## 2026-05-27 v100 slang DB small-state manual review

- [x] `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2` 총 8건을 수동 리뷰했다.
- [x] v100 label JSONL row `8`과 라벨 분포 `ACCEPT=4`, `HOLD=2`, `REJECT=2`를 확인했다.
- [x] 외부 매체 seed `프리렌`, `시달소`를 quarantine 후보로 분류했다.
- [x] 정상 웹소설 alias 후보 `탐태창`, `회맹생`, `시천살`, `반로환동전`을 분리했다.
- [x] `검머외`, `말하는검`은 재판정/충돌 검토 후보로 남겼다.
- [ ] v98 실서버 재실행 후 v100 판정과 결과를 대조한다.
- [ ] v100만으로 DB를 바로 수정하지 않는다. source DB 상태와 canonical title 후보를 별도 확인한다.

## 2026-05-27 v99 current slang DB status queue

- [x] 최신 `slang_db_review=87`을 상태별 큐로 다시 생성했다.
- [x] `blocked_by_result_contract=79`를 확인했다.
- [x] `persisted_as_slang=3`을 확인했다.
- [x] `persisted_conflict=3`을 확인했다.
- [x] `persisted_pending=2`를 확인했다.
- [x] `v99_current_slang_db_status_review_*` 산출물을 생성했다.
- [x] status review packet id가 prefix를 반영하도록 도구를 수정했다.
- [x] 관련 38개 테스트를 통과했다.
- [ ] `persisted_as_slang=3`, `persisted_conflict=3`, `persisted_pending=2`를 우선 자연어 리뷰로 닫는다.
- [ ] `blocked_by_result_contract=79`의 차단 사유와 alias recall 영향을 표본 리뷰한다.

## 2026-05-27 v98 targeted rerun input 및 image loading probe

- [x] v98 targeted input `7`건을 생성했다.
- [x] known-bad negative control `3`건을 포함했다: `강연금`, `프리렌`, `시달소`.
- [x] positive webnovel alias control `4`건을 포함했다: `아집숨`, `탐태창`, `회맹생`, `반로환동전`.
- [x] v98 manifest/input의 깨진 한국어 메타데이터를 바로잡았다.
- [x] `http://127.0.0.1:8000/v1/models` 연결 실패를 재확인했다.
- [x] 관련 Python 점유 프로세스가 없음을 확인했다.
- [x] `post_id=11097334` 현재 iab 탭에서 placeholder 이미지도 `complete=true`, `naturalWidth>0`으로 잡히는 것을 재확인했다.
- [x] v105에서 v98 `7`건을 Gemma 4 4B, `MCP_SHARD_COUNT=36`, `--no-auto-up-shards` 조건으로 실서버 재실행했다. 후속 7건 재확인은 `--parallel 7`로 실행한다.
- [ ] v98 after-review 전까지 v97 patch를 10만건 품질 승인 근거로 쓰지 않는다.
- [ ] VLM/OCR row는 `placeholder_current_src_count=0`과 `data_original_pending_count=0` 확인 전까지 `Strong`으로 올리지 않는다.

## 2026-05-27 v97 non-novel slang seed quarantine

- [x] `post_id=9687991` `프리렌 -> 장송의 프리렌`이 server-poc saved slang seed로 남아 있음을 확인했다.
- [x] `post_id=11097307` `시달소 -> 시간을 달리는 소녀`가 conflict seed로 남아 있음을 확인했다.
- [x] `BatchContextMemory.NON_NOVEL_MEDIA_ALIAS_SEED_BLOCKLIST`에 두 known-bad seed를 추가했다.
- [x] structured slang support가 있어도 해당 seed가 pending/resolved memory로 승격되지 않도록 테스트를 추가했다.
- [x] 웹소설 positive alias control (`죽깨수`, `검머대`, `히집악`)이 유지되는 것을 확인했다.
- [x] `tests.test_batch_context` 9건, `tests.test_agentic_pipeline_rework tests.test_batch_context` 248건 통과.
- [ ] LLM endpoint 복구 전후와 관계없이 result/checkpoint/manifest/after-review가 확인되기 전까지 실서버 재실행은 완료로 표시하지 않는다. 36건 미만 targeted run은 명령값보다 manifest의 `effective_parallel=input_post_count` 여부를 우선 확인한다.
- [ ] `human_review=122`, `slang_db_review=87`, `INFO_MISSING=1`을 닫기 전 semantic `GO`를 내지 않는다.

## 2026-05-27 v96 VLM/OCR attachment popup evidence

- [x] `post_id=10794867` live browser 재확인에서 본문 인라인 이미지 `0`개와 `원본 첨부파일 1`을 구분했다.
- [x] `10794867`의 `viewimagePop.php` 첨부 이미지가 `550x350`으로 로드되는 것을 확인했다.
- [x] 첨부 이미지는 갤러리 소개 이미지라 작품 직접 근거가 아니므로 `INFO_MISSING -> HOLD/human_review`로 재라벨했다.
- [x] `post_id=10892069`은 삭제/리다이렉트 상태라 `INFO_MISSING/human_review` 유지.
- [x] capture/relabel/closure 도구에 attachment link count와 source 공개 필드 보존을 반영했다.
- [x] latest closure: `ACCEPT=375`, `HOLD=208`, `INFO_MISSING=1`, approval excluded `209`.
- [x] browser grade: `Strong=99`, `Missing=1`; image gate: `pass=99`, `fail=1`.
- [x] 관련 32개 테스트와 넓은 278개 테스트 통과.
- [ ] `human_review=122`, `slang_db_review=87`, `INFO_MISSING=1`을 닫기 전 semantic `GO`를 내지 않는다.

## 2026-05-27 v95 structured evidence catalog relabel

- [x] `post_id=9803986` v94 result에 `identity.search_evidence_catalog` 공식/플랫폼 근거가 있음을 확인했다.
- [x] reason 문자열의 stale `official_urls=0` counter만으로 `Weak` 라벨이 유지되는 라벨러 문제를 확인했다.
- [x] qualitative labeler가 catalog 기반 `catalog_official_urls`, `catalog_search_snippets`를 effective evidence count에 반영하도록 보정했다.
- [x] stale `official_urls=0` counter가 있어도 catalog에 direct novel platform URL이 있으면 `weak_evidence`가 true로 남지 않도록 했다.
- [x] v95 after-review에서 `ACCEPT=2`, `HOLD=1`, `REPROCESS=0` 확인.
- [x] latest closure: v95 기준 `ACCEPT=375`, `HOLD=207`, `INFO_MISSING=2`, approval excluded `209`, `re_search=0`.
- [x] v96 기준 `INFO_MISSING=1`로 축소됐다.
- [ ] `human_review=122`, `slang_db_review=87`, `INFO_MISSING=1`를 닫기 전 semantic `GO`를 내지 않는다.

## 2026-05-27 v94 broad topic/comment composite guard

- [x] `post_id=10529582`에서 `삼국지 떡밥` broad topic이 `삼국지 태사자`로 과잉 확정되는 실패를 재현했다.
- [x] `work_plus_character` / `character_attached_composite` slang insight가 넓은 화제어 뒤 특정 캐릭터 결합 title로 승격되는 경로를 차단했다.
- [x] `post_id=10870841`에서 body guess `괴담동?`보다 댓글 답변 `악엔/악역의 엔딩은`이 강한 경우 title 확정을 보류하도록 했다.
- [x] Gemma 4 4B, `MCP_SHARD_COUNT=36`, `--parallel 36`, `--no-auto-up-shards` 조건으로 잔여 `re_search=3`을 v94 재실행했다.
- [x] v94 after-review: `ACCEPT=1`, `HOLD=1`, `REPROCESS=1`.
- [x] latest closure: `ACCEPT=374`, `HOLD=207`, `REPROCESS=1`, `INFO_MISSING=2`, approval excluded `210`.
- [x] `py_compile` 및 `273`개 관련 테스트 통과.
- [x] 남은 `re_search=1` (`9803986`)은 v95에서 structured evidence catalog 보정 후 `ACCEPT/no_action`으로 닫았다.
- [ ] `human_review=122`, `slang_db_review=87`, VLM/OCR gap을 닫기 전 semantic `GO`를 내지 않는다.

## 2026-05-27 v92 10만건 부족점/버그 정리

- [x] `post_id=9197737`에서 명시적 비소설 disclaimer를 무시하고 `브레이킹 배드`를 작품 title로 복구하는 실패를 재현했다.
- [x] final identity, output consistency, unresolved worklike preserve, title-surface rescue 경로에 disclaimer 차단을 반영했다.
- [x] v92 canary에서 `is_relevant=false`, `official_title=null`, `discussion_type=off_topic`, `work_resolution=none`을 확인했다.
- [x] v92 after-review 및 closure를 갱신해 approval excluded를 `211`로 줄였다.
- [x] locked official detail 후보 중복/role 변환 회귀를 보정했다.
- [x] `py_compile` 및 `270`개 회귀 테스트를 통과했다.
- [x] 남은 `re_search=3`을 닫았다: `10529582`, `10870841`은 v94, `9803986`은 v95.
- [ ] `human_review=121`, `slang_db_review=87`, VLM/OCR gap `27`을 닫기 전 semantic `GO`를 내지 않는다.

## 2026-05-27 v89 10만 건 잔여 action rerun

- [x] v84 action input `199`건을 Gemma 4 4B, `--parallel 36`, `MCP_SHARD_COUNT=36` 조건으로 재실행했다.
- [x] timeout된 첫 실행 checkpoint `74`건과 잔여 실행 `125`건을 병합했다.
- [x] 병합 결과 missing/duplicate/extra post_id `0/0/0`을 확인했다.
- [x] v89 after-review `ACCEPT=170`, `HOLD=16`, `REPROCESS=13`을 생성했다.
- [x] latest closure `ACCEPT=363`, `HOLD=206`, `REPROCESS=13`, `INFO_MISSING=2`, approval excluded `221`로 갱신했다.
- [x] `v89_100k_fixable_gap_bug_action_summary_ko_20260527.md`에 부족점/버그/해결 가능 항목을 한국어로 정리했다.
- [ ] `re_search=13`을 재검색해 evidence 직접성을 확인한다.
- [ ] `slang_db_review=87`과 VLM/OCR evidence gap `27`건을 별도 큐로 닫는다.
- [ ] post-fix random baseline/P0/P1 regression 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지.

## 2026-05-27 v88 VLM/OCR lazy placeholder tooling

- [x] `capture_vlm_ocr_browser_review_cli.py`가 lazy/data-original/placeholder current src pending count를 기록한다.
- [x] `build_qualitative_exit_action_closure.py`가 explicit `imageGatePass=true`만으로 VLM/OCR `ACCEPT`를 허용하지 않는다.
- [x] `build_v78_vlm_browser_semantic_relabel.py`가 image counter fail이면 `Strong`을 `Weak`로 낮춘다.
- [x] placeholder complete trap 회귀 테스트를 추가했다.
- [x] `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools` `27`건 통과.
- [ ] VLM/OCR `27`건을 새 필드 포함 browser packet으로 다시 닫는다.

## 2026-05-27 v87 10만 건 부족점 정리 및 이미지 placeholder 게이트

- [x] 10만 건 테스트의 부족점/버그/해결 가능 항목을 한국어 action summary로 정리했다.
- [x] `post_id=11097334`을 Codex in-app browser로 열어 이미지 lazy-load 상태를 재확인했다.
- [x] 초기 placeholder `gallview_loading_ori.gif`도 `complete=true`, `naturalWidth>0`으로 잡힐 수 있음을 기록했다.
- [x] 스크롤/대기 후 `data-original` 실제 `dcimg` URL로 교체되는 것을 확인했다.
- [x] `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`에 `data-original` 교체 확인, `placeholder_current_src_count`, `data_original_pending_count` 기록 규칙을 추가했다.
- [x] `2026-05-27 12:26:14 +09:00` 기준 `127.0.0.1:8000` listener 없음, LLM endpoint 연결 실패, 관련 Python 점유 없음 확인.
- [ ] VLM/OCR `27`건 리뷰에서 `img.complete`만으로 `Strong`을 주지 않는지 확인한다.
- [ ] endpoint 복구 후 v84 rerun combined `199`건을 36워커로 재실행한다.

## 2026-05-27 v86 slang DB conflict status

- [x] `post_id=10173521`의 `말하는검`이 저장 누락이 아니라 `server_poc:conflict`임을 확인했다.
- [x] closure `find_term_state()`가 `titles[].conflicts[]`를 검사하도록 보정했다.
- [x] `persisted_conflict` status와 `resolve_conflicting_alias` followup action을 추가했다.
- [x] latest slang status queue를 재생성해 `extracted_not_persisted=0`, `persisted_conflict=3`을 확인했다.
- [x] conflict 대표 row `8650236`, `10173521`, `11097307`을 확인했다.
- [x] 관련 테스트 `24`건을 통과했다.
- [ ] `persisted_conflict=3` alias 충돌 해소 리뷰를 진행한다.
- [ ] endpoint 복구 후 v84 rerun combined `199`건을 36워커로 재실행한다.

## 2026-05-27 v85 slang DB status queue

- [x] v86에서 `extracted_not_persisted=1`이 `persisted_conflict`로 정정됐다.
- [x] `slang_db_review=87`을 상태별 packet/label/action queue로 분리했다.
- [x] `blocked_by_result_contract=79`를 `confirm_block_reason_and_recall_impact`로 분리했다.
- [x] `persisted_as_slang=3`을 `verify_saved_alias_not_pollution`으로 분리했다.
- [x] `persisted_pending=2`를 `confirm_pending_or_promote`로 분리했다.
- [x] `family_alias=2`를 `verify_family_alias_display_recall`로 분리했다.
- [x] `extracted_not_persisted=1`을 `REPROCESS/investigate_persistence_gap`으로 분리했다.
- [x] `tools/build_slang_db_status_review.py`와 테스트를 추가했다.
- [x] `tests.test_qualitative_review_packet_tools` `12`건 통과.
- [ ] `post_id=10173521` persistence gap을 우선 확인한다.
- [ ] endpoint 복구 후 v84 rerun combined `199`건을 36워커로 재실행한다.

## 2026-05-27 v84 source slang fallback

- [x] v83의 `docs_issue=64`가 source field 결손이 아니라 closure source fallback 누락임을 확인했다.
- [x] 빈 `slang_db_fields` dict가 있더라도 실제 term이 없으면 원본 `identity.slang_insight`를 fallback하도록 보정했다.
- [x] latest closure를 재생성해 `docs_issue=0`, `slang_db_review=87`을 확인했다.
- [x] v84 action package를 재생성해 rerun combined `199`, browser target `27`, missing post_id `0`을 확인했다.
- [x] `slang_db_review=87` 상태 분포를 확인했다: `blocked_by_result_contract=79`, `persisted_as_slang=3`, `persisted_pending=2`, `family_alias=2`, `extracted_not_persisted=1`.
- [x] 관련 테스트 `29`건을 통과했다.
- [ ] endpoint 복구 후 v84 rerun combined `199`건을 36워커로 재실행한다.
- [ ] `slang_db_review=87`은 상태별 자연어 근거와 recall 영향을 리뷰한다.
- [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate는 `NO-GO / REVIEW-LOCKED`로 유지한다.

## 2026-05-27 v83 slang DB field routing

- [x] v84에서 source fallback 누락으로 정정되어 `docs_issue=64` 최종 해석은 폐기했다.
- [x] `slang_db_review` 중 공개 `slang_db_fields`가 없는 row를 `docs_issue`로 분리했다.
- [x] `slang_db_review` 실제 DB 차단 계약 검토 대상을 `23`건으로 좁혔다.
- [x] latest closure를 재생성해 `ACCEPT=193`, `HOLD=258`, `REPROCESS=67`, `INFO_MISSING=66`을 확인했다.
- [x] v83 action package를 재생성해 `docs_issue=64`, `slang_db_review=23`, rerun combined `199`, browser target `27`을 확인했다.
- [x] review packet에 `slang_db_fields`, `final_decision_fields`, `reason`, `search_health_flags`를 포함했다.
- [x] action package summary 생성 문구를 정상 한국어로 보정했다.
- [x] `py_compile` 및 `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools tests.test_batch_context` `28`건을 통과했다.
- [ ] endpoint 복구 후 v83 rerun combined `199`건을 36워커로 재실행한다.
- [ ] `docs_issue=64`는 packet/export 결손 issue로 원인 분류한다.
- [ ] `slang_db_review=23`은 차단 사유와 recall 영향만 검토한다.
- [ ] post-fix random baseline과 P0/P1 regression 전까지 semantic gate는 `NO-GO / REVIEW-LOCKED`로 유지한다.

## 2026-05-27 v81 VLM/OCR current remaining 재라벨

- [x] v80에서 VLM/OCR current remaining `28`건을 기존 iab 이미지 게이트와 단건 수동 브라우저 리뷰에 조인했다.
- [x] 이미지 로딩 `Strong`만으로는 `ACCEPT`하지 않고 `HOLD/human_review`로 유지하는 회귀 테스트를 추가했다.
- [x] `9531764` 단건은 Codex in-app browser 수동 리뷰 근거로 `ACCEPT/no_action` 처리했다.
- [x] latest closure에 v80 supplemental label/packet을 병합했다.
- [x] closure 최신 결과 `ACCEPT=193`, `HOLD=322`, `REPROCESS=67`, `INFO_MISSING=2` 확인.
- [x] approval excluded `391/584` 확인.
- [x] v81 action package 생성: rerun combined `199`, browser target `27`, `re_run=0`.
- [x] `tests.test_exit_action_closure tests.test_qualitative_review_packet_tools` 18건 통과.
- [x] slang DB 잔여 `87`건을 `no_slang_term_in_packet=64`, `blocked_by_result_contract=23`으로 1차 분리했다.
- [ ] VLM/OCR 남은 `27`건은 이미지 로딩이 아니라 이미지 의미와 작품 판정 지지 여부를 확인한다.
- [ ] slang DB `no_slang_term_in_packet=64`는 packet 공개 필드/export 또는 라벨 라우팅 이슈로 처리한다.
- [ ] endpoint 복구 후 v81 rerun combined `199`건을 36워커로 실행한다.
- [ ] semantic gate는 계속 `NO-GO / REVIEW-LOCKED`로 유지한다.

## 2026-05-27 v78 current remaining action package

- [x] latest remaining queue `392`건 전체를 action별로 분리했다.
- [x] rerun combined input `226`건 생성.
- [x] `re_search=127`, `re_judge=72`, `re_run=27` 분리 확인.
- [x] `human_review=79`, `slang_db_review=87` review packet 분리 확인.
- [x] browser target `28`건 분리 확인.
- [x] missing post_id `0`, duplicate 제거 `0` 확인.
- [x] action split 회귀 테스트 추가 및 통과.
- [ ] endpoint 복구 후 rerun combined input을 36워커로 실행한다.
- [ ] post-fix 결과와 preflight/original 결과를 혼동하지 않는다.

## 2026-05-27 v77 after-review readiness

- [x] v75 P0 input의 `_round3_target.packet_id` 누락을 보강했다.
- [x] v75 P0 input의 `_round3_target.bucket` 누락을 보강했다.
- [x] after-review 도구에 `base_packet_id`/`primary_pattern` fallback을 추가했다.
- [x] preflight original result `96`건으로 after-review packet/label 생성 경로를 검증했다.
- [x] missing target `0`, before packet/bucket lineage assertion 통과.
- [ ] preflight label을 semantic gate 완화 근거로 쓰지 않는다.
- [ ] 실제 post-fix 재실행 결과가 나오면 같은 output-prefix가 아니라 post-fix 전용 prefix로 after-review를 생성한다.

## 2026-05-27 v76 P0 remaining targeted input

- [x] `generic_common_surface=80` 전체를 targeted input에 포함했다.
- [x] `weak_evidence_strong_resolution=16` 전체를 targeted input에 포함했다.
- [x] 중복 제거 후 targeted input `96`건, missing post_id `0` 확인.
- [x] generated input/manifest 구조 검증 통과.
- [x] `expert_main.py --help`로 36워커 실행에 필요한 CLI 플래그 확인.
- [x] LLM endpoint connection refused 상태를 기록했다.
- [ ] endpoint 복구 후 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36`, `--no-auto-up-shards`로 재실행한다.
- [ ] 재실행 후 after-review labels를 생성해 P0 큐 closure를 갱신한다.

## 2026-05-27 v75 supplemental after-review closure merge

- [x] v68/v71/v73 supplemental after-review label/packet을 latest closure에 병합했다.
- [x] `round3_exit_action_current_combined_manifest.json`에 `supplemental_update_rows=19`를 기록했다.
- [x] closure 최신 결과 `ACCEPT=192`, `HOLD=297`, `REPROCESS=93`, `INFO_MISSING=2` 확인.
- [x] approval excluded `392/584` 확인.
- [x] 남은 action queue `human_review=79`, `re_search=127`, `re_judge=72`, `slang_db_review=87`, `re_run=27` 확인.
- [x] current summary와 gate decision 문서를 최신 수치로 갱신했다.
- [x] LLM endpoint는 현재 connection refused라 추가 36워커 실행 전에 복구/포트 확인이 필요함을 기록했다.
- [ ] `generic_common_surface=80`과 `alias_recall_loss_false_negative=96` 후속 처리 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지.

## 2026-05-27 v74 weak evidence closure guard

- [x] `weak_evidence_strong_resolution` guard가 비관련/title-null ACCEPT를 다시 HOLD로 잠그는 과차단을 확인했다.
- [x] `relevance=false`, `resolved_title=null` row는 해당 guard 대상에서 제외했다.
- [x] 관련 unresolved row와 resolved title row는 계속 `Strong` evidence 없이는 approval excluded로 유지하도록 테스트했다.
- [x] `tests.test_exit_action_closure` 6건 통과.
- [x] closure 재생성 결과 `ACCEPT=183`, `HOLD=306`, `REPROCESS=93`, `INFO_MISSING=2` 확인.
- [x] approval excluded `401/584` 확인.
- [x] `weak_evidence_strong_resolution=16` (`HOLD=15`, `REPROCESS=1`) 확인.
- [ ] `generic_common_surface=89`와 `alias_recall_loss_false_negative=96` 후속 처리 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지.

## 2026-05-27 v73 review labeler direct evidence/degraded routing

- [x] `degraded_queries: 0` 필드명만으로 `search_degraded=true`가 되는 review labeler 버그를 확인했다.
- [x] 직접 작품 근거 조건을 `official_title_evidence=true`, `official_urls>0`, `title_in_post=true`, `source_tier=official_detail|novel_platform`로 고정했다.
- [x] 직접 작품 근거가 있고 degraded가 없으면 `ACCEPT/no_action`, degraded가 있으면 `HOLD/re_search`로 라우팅한다.
- [x] `tests.test_qualitative_review_packet_tools` 6건 통과.
- [x] v72 단건 after-review 재생성에서 `11113480`이 `HOLD/re_search`로 라우팅됨을 확인했다.
- [x] v67 generic_common_surface 19건 재적용 결과 `ACCEPT=7`, `HOLD=12`, actions `no_action=7`, `re_search=7`, `re_judge=5`를 확인했다.
- [ ] 새 라벨러를 전체 Round 3 closure에 적용하기 전 기존 gate와 비교 manifest를 남긴다.
- [ ] post-fix random baseline과 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지.

## 2026-05-27 v72 BatchContextMemory generic inline alias guard

- [x] `post_id=11113480`에서 `카드아카 -> 카드 아카데미 1타강사`가 보류 후 count 2로 BatchMem 승격되던 로그를 확인했다.
- [x] `generic_inline_alias` pending entry는 count 2 이상이어도 resolved memory로 승격하지 않도록 수정했다.
- [x] 저근거 `register_abbreviation_seed`는 structured slang support 없이 반복만으로 승격하지 않도록 수정했다.
- [x] `tests.test_batch_context` 7건 통과.
- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v72 수행.
- [x] v72 `20260527_094306_107869`: completed `1`, failed `0`, pending `0`, search health `36/36 OK`.
- [x] v72 worker log에서 `BatchMem: 약칭 승격 '카드아카'` 제거 및 `약칭 승격 보류 ... reason=generic_inline_alias` 확인.
- [x] 최종 작품 판정은 `카드 아카데미 1타강사` resolved로 유지.
- [ ] after-review는 `HOLD`이므로 broader `generic_parenthetical_bridge` re_judge queue는 계속 유지한다.
- [ ] post-fix random baseline과 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지.

## 2026-05-27 v71 generic concept question guard

- [x] `post_id=9218133`에서 무협 개념 질문이 `반로환동으로 신분세탁` 작품으로 과확정되던 원인을 canonical/title-surface rescue 우회로 특정했다.
- [x] generic concept question mismatch를 canonical rescue, canonical lock, strongest rescue, best candidate 선택에 적용했다.
- [x] `generic_concept_question_surface_title` reject reason은 상세 URL 예외로 title-surface primary rescue하지 않도록 수정했다.
- [x] canonical rescue 우회와 title-surface rescue 우회를 회귀 테스트로 고정했다.
- [x] focused unittest 4건, py_compile 통과를 확인했다.
- [x] v71 단건 run에서 completed `1`, failed `0`, pending `0`을 확인했다.
- [x] v71 final에서 `is_relevant=false`, `official_title=null`, `work_resolution=none`, `discussion_type=trope_discussion`을 확인했다.
- [x] v71 after-review에서 `ACCEPT=1`, `HOLD->ACCEPT=1`을 확인했다.
- [ ] 같은 guard가 `generic_common_surface`, `weak_evidence_strong_resolution`, `slang_db_review` bucket에서 과차단/과승격 없이 동작하는지 P0/P1 regression으로 확인한다.
- [ ] post-fix random baseline과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v68 character surface title 정확 근거 guard

- [x] `post_id=8424362`에서 `에미야 키리츠구`가 작품명으로 승격되던 원인을 상세 URL substring evidence 과승격으로 특정했다.
- [x] 캐릭터 표면명 후보는 source/fetched title이 후보를 작품명으로 정확히 지칭할 때만 clean detail evidence로 인정하도록 수정했다.
- [x] `[fate]에미야 키리츠구의 성배대전`처럼 후보가 긴 제목의 일부인 경우 `generic_character_surface_title` rejection을 유지하는 테스트를 추가했다.
- [x] 문피아 suffix가 붙은 실제 작품 제목은 계속 clean detail evidence로 인정하는 positive test를 추가했다.
- [x] 신규 focused unittest 2건, 관련 회귀 unittest 7건, py_compile 통과를 확인했다.
- [x] 검색 shard audit `36/36 OK`를 확인했다.
- [x] v68 단건 run에서 completed `1`, failed `0`, pending `0`을 확인했다.
- [x] v68 final에서 `is_relevant=false`, `official_title=null`, `work_resolution=none`을 확인했다.
- [x] v68 after-review에서 `ACCEPT=1`, `HOLD->ACCEPT=1`을 확인했다.
- [x] Browser `iab`에서 `11097334` 이미지 lazy-load를 재확인했다. 최종 loaded `3/3`, placeholder/incomplete/broken `0`.
- [ ] 같은 guard가 `generic_common_surface` 잔여 HOLD와 `weak_evidence_strong_resolution` bucket에서 과차단/과승격 없이 동작하는지 P0/P1 regression으로 확인한다.
- [ ] post-fix random baseline과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-27 v67 direct/locked title rescue 상태 오염 확인

- [x] v64에서 `10190186`이 `REJECT`가 된 원인을 rescue 후 stale demotion/noise 상태 오염으로 특정했다.
- [x] direct full-title rescue와 locked official candidate rescue에서 stale demotion flag를 제거했다.
- [x] rescue 후 `verification_result.novel_identity`와 final confidence를 동기화했다.
- [x] `m.munpia.com/novel/detail/<id>`를 문피아 모바일 작품 상세 URL로 인정했다.
- [x] direct/locked rescue 단위 테스트와 direct-title 회귀 묶음을 통과했다.
- [x] v66 단건 run에서 `10190186` stale demotion flag 제거를 확인했다.
- [x] v67 19건 run에서 completed `19`, failed `0`, pending `0`을 확인했다.
- [x] v67 after-review에서 `REJECT=0`을 확인했다.
- [ ] 잔여 `generic_common_surface HOLD=12`를 별도 원인 패턴으로 분리한다.
- [ ] post-fix random baseline과 P0/P1 high-risk regression 전까지 semantic gate `GO` 금지.

## 2026-05-26 v63 character-only virtual battle guard / 10만 건 부족점 정리

- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v62 수행
- [x] v62 `20260526_223527_932869`: completed `6`, failed `0`, pending `0`, flushed `6`
- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v63 수행
- [x] v63 `20260526_231204_349215`: completed `6`, failed `0`, pending `0`, flushed `6`
- [x] 검색 shard health `36/36 OK` 확인
- [x] 저근거 slang seed 즉시 승격 보류 로그 확인: `폰무림`, `마법소녀`, `21세기`, `crpg속` 등
- [x] `강연금 -> 강철의 연금술사` exact non-novel media seed quarantine 유지
- [x] positive alias `히집악` 복구 유지
- [x] v62 자동 after-review 생성 후 수동 오버레이 라벨 작성: `v62_slang_seed_support_gate_after_manual_labels.jsonl`
- [x] 최신 부족점/버그/해결 가능 항목 한국어 정리본 갱신: `current_100k_gap_bug_fixable_summary_ko_20260526.md`
- [x] Browser `iab` 현재 URL `11097334` 본문 이미지 state 확인: article image `3/3` loaded, placeholder `0`
- [x] `post_id=11663540` character-only virtual battle 대표 케이스는 `non-relevant/title null/none`으로 정책 반영
- [ ] `post_id=10426463` adjacent/trope/setting-borrowing 정책 확장 검증
- [x] 자동 after-review 라벨러의 `Weak + unresolved/title null + boundary risk` 과허용 수정
- [ ] character-only virtual battle pattern의 P0/P1 regression 이웃 케이스 검증
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v61 slang seed quarantine/catalog tier fix

- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v61 수행
- [x] 실행 전 `expert_main|llm_batch|warp_shards` Python 점유 없음 확인
- [x] LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` endpoint 응답 확인
- [x] shard container 36개 실행 상태 확인
- [x] 검색 shard health `36/36 OK` 확인
- [x] v61 `20260526_221106_422763`: completed `6`, failed `0`, pending `0`, flushed `6`
- [x] `py_compile` 및 focused unittest 5건 통과
- [x] after-review packet/labels/summary 생성 및 수동 보정: `v61_catalog_tier_fix_after_packet_review_*`
- [x] `post_id=8531521` `강연금 -> 강철의 연금술사` seed quarantine 로그 확인
- [x] `post_id=9981263` positive alias 회복 및 E001 `source_tier=novel_platform` 확인
- [x] `post_id=11663540`, `post_id=8601885` non-relevant/title null 유지 확인
- [x] `post_id=11205204` positive alias control 유지 확인
- [ ] `post_id=10426463` adjacent/trope 관련성 보존 정책 확장 검증
- [ ] 외부 IP seed quarantine을 exact blocklist에서 일반화 규칙으로 확장 검증
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 10만 건 현재 액션 요약

- [x] 최신 기준만 분리한 한국어 정리본 작성: `qualitative_review/20260505_214349_324347/current_100k_actionable_issue_summary_ko_20260526.md`
- [x] v61 기준 `8531521 -> 강철의 연금술사` resolved 회귀는 최종 `non-relevant/title null`로 닫힌 상태로 정리
- [x] `강연금 -> 강철의 연금술사`는 런타임 seed quarantine 확인, 원본 DB cleanup/generalization 후보로 분리
- [x] random baseline, high-risk expansion, current combined review 수치를 분리 기록
- [x] Browser 확인에서 `post_id=11097334` 이미지 lazy placeholder가 초기 로딩에서 남을 수 있고, 본문 selector 스크롤/대기 후 이미지 로딩 상태를 별도로 봐야 함을 기록
- [ ] `weak_evidence_strong_resolution=75`, `generic_common_surface=89` 확장 회귀 재검증
- [ ] `slang_db_review=87` 상태별 분리 및 외부 IP seed quarantine 일반화
- [ ] VLM/OCR `28`건 Browser image gate와 semantic evidence 재라벨
- [ ] `10426463` 유사 adjacent/trope bucket 정책 확정
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v58 detail URL/media guard

- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v58 수행
- [x] 실행 전 `expert_main|llm_batch|warp_shards` Python 점유 없음 확인
- [x] LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` endpoint 응답 확인
- [x] shard container 36개 실행 상태 확인
- [x] 검색 shard health `36/36 OK` 확인
- [x] v58 `20260526_210850_328711`: completed `6`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 10건 통과
- [x] after-review packet 산출물 생성: `v58_detail_url_media_guard_after_packet_review_packets.jsonl`
- [x] after-review labels/summary 수동 보정: `v58_detail_url_media_guard_after_packet_review_labels.jsonl`, `v58_detail_url_media_guard_after_packet_review_summary.md`
- [x] `post_id=11663540` `주서연 전차` false positive 차단 확인
- [x] `post_id=8531521` `강철의 연금술사` 외부 media/IP false positive 차단 확인
- [x] `post_id=9981263`, `post_id=11205204` positive alias control 유지 확인
- [x] `post_id=8601885` LoL/노틸러스 게임 IP non-relevant 유지 확인
- [x] result JSON `search_evidence_catalog` 구조화 export 확인
- [x] fanart/comic/webtoon/viewer URL의 clean detail evidence 오인 차단 확인
- [ ] `post_id=10426463` adjacent/trope 관련성 보존 정책 확장 검증
- [ ] `강연금 -> 강철의 연금술사` slang seed 오염 review
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v55 known-bad media/alias guard

- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v55 수행
- [x] 실행 전 `expert_main|llm_batch|warp_shards` Python 점유 없음 확인
- [x] LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` endpoint 응답 확인
- [x] shard container 36개 실행 상태 확인
- [x] v55 `20260526_195550_803682`: completed `6`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 7건 통과
- [x] after-review 산출물 생성: `v55_known_bad_media_alias_guard_after_summary_ko.md`, `v55_known_bad_media_alias_guard_after_labels.jsonl`
- [x] review packet 산출물 생성: `v55_known_bad_media_alias_guard_after_packets.jsonl`, `v55_known_bad_media_alias_guard_after_packet_manifest.json`
- [x] packet JSONL `6`행과 packet manifest parse 확인
- [x] packet evidence URL 확인: `9981263`, `11205204` NovelPia detail URL 포함
- [x] packet `evidence_catalog` 확인: 6건 모두 후보별 metadata 존재
- [x] packet `evidence_counts` 확인: reason 기반 evidence count 구조화
- [x] `tests.test_qualitative_review_packet_tools` 통과
- [x] `post_id=9981263` positive alias control 유지 확인
- [x] `post_id=11205204` 히집악 alias positive control 유지 확인
- [x] `post_id=11663540` character-only 가상 대결 resolved 우회 경로 차단 확인
- [x] `post_id=8531521` 외부 만화/애니 IP 최종 non-relevant 유지 확인
- [x] `post_id=8601885` LoL/노틸러스 게임 IP 최종 non-relevant 유지 확인
- [ ] `post_id=10426463` adjacent/trope 관련성 보존 정책 확장 검증
- [ ] result JSON에 row별 raw search evidence catalog/EID/URL/snippet 전체 export
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v51 known-bad media/alias guard

- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v51 수행
- [x] 실행 전 `expert_main|llm_batch|warp_shards` Python 점유 없음 확인
- [x] LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` endpoint 응답 확인
- [x] shard container 36개 실행 상태 확인
- [x] v51 `20260526_185600_839070`: completed `6`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 11건 통과
- [x] after-review 산출물 생성: `v51_known_bad_media_alias_guard_after_summary_ko.md`, `v51_known_bad_media_alias_guard_after_labels.jsonl`
- [x] `post_id=9981263` positive alias inversion 수정 확인
- [x] `post_id=8531521` 외부 만화/애니 IP 최종 non-relevant 유지 확인
- [x] `post_id=8601885` LoL/노틸러스 게임 IP 최종 non-relevant 유지 확인
- [x] `post_id=11205204` 히집악 alias positive control 유지 확인
- [x] `post_id=10426463` adjacent/external IP 글 relevant/unresolved 보존 확인
- [ ] `post_id=11663540` character-parenthetical bridge resolved 정책 결정
- [ ] character-only bridge high-risk bucket 확장 검증
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v50 known-bad media/alias guard

- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v50 수행
- [x] 실행 전 `expert_main|llm_batch|warp_shards` Python 점유 없음 확인
- [x] LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` endpoint 응답 확인
- [x] shard container 36개 실행 상태 확인
- [x] v50 `20260526_182412_783072`: completed `6`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 8건 통과
- [x] after-review 산출물 생성: `v50_known_bad_media_alias_guard_after_summary_ko.md`, `v50_known_bad_media_alias_guard_after_labels.jsonl`
- [x] `post_id=8531521` 외부 만화/애니 IP 최종 non-relevant 차단 확인
- [x] `post_id=8601885` LoL/노틸러스 게임 IP 최종 non-relevant 유지 확인
- [x] `post_id=11205204` 히집악 alias positive control 유지 확인
- [ ] `post_id=9981263` positive alias inversion 회귀 수정
- [ ] `post_id=10426463` adjacent/external IP overblocking 후보 정책 결정
- [ ] `post_id=11663540` character-only policy boundary 결정
- [ ] 수정 후 v51 known-bad 6건 재실행
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v48 known-bad media/alias guard

- [x] Gemma 4 4B 기준 `MCP_SHARD_COUNT=36`, `expert_main.py --parallel 36` targeted run v48 수행
- [x] 실행 전 `expert_main|llm_batch|warp_shards` Python 점유 없음 확인
- [x] LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` endpoint 응답 확인
- [x] 검색 shard health `36/36 OK` 확인
- [x] v48 `20260526_170233_055943`: completed `6`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 8건 통과
- [x] after-review 산출물 생성: `v48_known_bad_media_alias_guard_after_summary_ko.md`, `v48_known_bad_media_alias_guard_after_labels.jsonl`
- [x] `post_id=8601885` `identified_category=game` 기반 외부 게임 IP 최종 회수 차단 확인
- [x] `post_id=8531521` `강철의 연금술사` resolved title false positive 차단 확인
- [x] `post_id=9981263`, `post_id=11205204` positive control resolved 유지 확인
- [ ] `post_id=8531521` 외부 IP가 `relevant/unresolved`로 남는 정책 경계 정리
- [ ] `post_id=11663540` character-only virtual battle 관련성 정책 정리
- [ ] `post_id=10426463` 설정 차용/인접 IP bucket 확대 검토
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v42/v43 known-bad media/alias guard

- [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` targeted run v42 수행
- [x] v42 `20260526_153538_350152`: completed `6`, failed `0`, pending `0`
- [x] v43 `8531521` 단건 canary `20260526_154837_721537`: completed `1`, failed `0`, pending `0`
- [x] after-review 산출물 생성: `v42_v43_known_bad_media_alias_guard_after_summary_ko.md`, `v42_v43_known_bad_media_alias_guard_after_labels.jsonl`
- [x] `post_id=9981263` 제목란 alias positive control resolved 유지
- [x] `post_id=11205204` `히집악` alias positive control resolved 유지
- [x] `post_id=11663540` 캐릭터 가상 대결 title over-resolution 제거 확인
- [x] `post_id=8601885` 외부 게임 IP non-relevant 유지 확인
- [ ] `post_id=8531521` v43 회귀 처리: `title_surface_primary_candidate_rescued`가 `강철의 연금술사`를 되살리는 경로 차단
- [ ] wiki/media/영화/단행본/OTT/파생 hit를 웹소설 `official_title_evidence`로 세지 않는 회귀 테스트 추가
- [ ] title-surface primary rescue 직전에 non-novel media/IP guard 재적용
- [ ] 수정 후 known-bad 6건과 `8531521` canary를 다시 `expert_main.py --parallel 36`으로 재실행
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v38 known-bad media/alias guard

- [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` targeted run v38 수행
- [x] 실행 전 이전 `expert_main`/`llm_batch`/`warp_shards` Python 잔존 없음 확인
- [x] 실행 전 LLM model `bg-digitalservices/Gemma-4-E4B-it-NVFP4` 확인
- [x] 실행 전 search shard audit `36/36` 확인
- [x] v38 `20260526_141931_661420`: completed `6`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 통과
- [x] after-review 산출물 생성: `v38_known_bad_media_alias_guard_after_summary_ko.md`, `v38_known_bad_media_alias_guard_after_labels.jsonl`
- [x] `post_id=9981263` 제목란 primary alias + NovelPia detail 후보 복구 확인
- [x] `post_id=11205204` fresh/custom slang DB에서 `히집악` 내장 alias 복구 확인
- [x] `post_id=8601885` 외부 게임 IP non-relevant 처리 확인
- [x] `post_id=11663540` weak character-parenthetical title over-resolution 제거 확인
- [x] `post_id=8531521` `강철의 연금술사` title 오염 제거 확인
- [ ] `post_id=8531521` 비웹소설 IP가 `is_relevant=true/title=null`로 남는 관련성 과포함 처리
- [ ] `post_id=11663540` 캐릭터 talk의 `non_relevant` vs `relevant/unresolved` 정책 기준 정리
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 10만건 테스트 부족점/버그 최신 정리

- [x] 최신 closure manifest 기준으로 부족점/버그/해결 가능 항목을 새 한국어 문서로 정리
- [x] 정리본 경로 기록: `qualitative_review/20260505_214349_324347/current_100k_gap_bug_fixable_summary_ko_20260526.md`
- [x] 최신 gate 기준 기록: `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`, approval excluded `460/584`
- [x] action queue 기록: `human_review=138`, `re_search=120`, `re_judge=88`, `slang_db_review=87`, `re_run=27`
- [x] pattern queue 기록: `weak_evidence_strong_resolution=75`, `generic_common_surface=89`, `alias_recall_loss_false_negative=96`, `slang_db_alias_subtype=88`, `worker_shard_degraded_window=84`, `vlm_ocr_evidence_gap=28`
- [ ] P0 `weak_evidence_strong_resolution=75`와 `generic_common_surface=89` targeted regression 재검증
- [ ] known-bad/positive-control `9981263`, `11205204`, `11663540`, `10426463` 포함 후 Gemma 4 4B `expert_main.py --parallel 36` 재실행
- [ ] VLM/OCR `28`건은 Browser `iab` screenshot과 image loaded count를 packet에 붙인 뒤 재라벨
- [ ] approval excluded `460/584` 처리 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 최신 10만 건 잔여 이슈 큐

- [x] 최신 closure manifest 기준으로 부족점/버그/해결 가능 항목을 분리 정리
- [x] 승인 가능 `124/584`, 승인 제외 `460/584`를 최신 gate 기준으로 기록
- [x] random baseline과 high-risk oversample 결과를 분리 기록
- [x] action queue `human_review=138`, `re_search=120`, `re_judge=88`, `slang_db_review=87`, `re_run=27` 확인
- [x] pattern queue `alias_recall_loss_false_negative=96`, `generic_common_surface=89`, `slang_db_alias_subtype=88`, `worker_shard_degraded_window=84`, `weak_evidence_strong_resolution=75`, `vlm_ocr_evidence_gap=28` 확인
- [x] `expert_main.py` JSONL loader가 UTF-8 BOM 포함 입력을 읽도록 `utf-8-sig` 적용
- [x] non-empty JSONL에서 로드 post `0`개이면 shard/LLM 실행 전 실패하도록 preflight 추가
- [x] `10426463` targeted rerun v31: completed `1`, failed `0`, pending `0`
- [x] `10426463` current result는 `is_relevant=false`, `official_title=null`, `work_resolution=none`으로 weak title 오확정 없음
- [x] `11663540` v33 targeted rerun: completed `1`, failed `0`, pending `0`
- [x] `11663540` current result는 `is_relevant=true`, `official_title=null`, `work_resolution=unresolved`, `character_parenthetical_title_null_blocked`로 weak character-parenthetical title 과확정 없음
- [x] `_title_deliberately_null` 상태에서 post-side title/alias support 없는 약앵커 후보가 canonical suspect/character-parenthetical/safe-single 경로로 복구되지 않도록 guard 추가
- [ ] `weak_evidence_strong_resolution`과 `generic_common_surface` 확장 bucket에서 v33 guard가 false positive를 줄이고 positive control을 깨지 않는지 확인
- [ ] slang_db 상태는 저장/차단/pending/family/noise/display를 섞지 않고 별도 라벨링
- [ ] VLM/OCR row는 Browser `iab` image gate pass와 semantic ACCEPT를 분리
- [ ] 남은 approval excluded `460/584` 처리 전까지 semantic gate `NO-GO / REVIEW-LOCKED` 유지

## 2026-05-26 v23 final targeted guard 재확인
- [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` targeted run v23 수행
- [x] v23 `20260526_001642_295323`: completed `5`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 5건 통과
- [x] after-review 산출물 생성: `v23_final_targeted_guard_after_summary.md`, `v23_final_targeted_guard_after_labels.jsonl`
- [x] `post_id=8705431` 무관 search hit `아포칼립스의 루팅능력자` 교체 차단 및 본문 공식 URL title 복구 확인
- [x] `post_id=8601885` `리그 오브 레전드` 게임 IP title 오매치 제거 확인
- [x] `post_id=8424362` `에미야 키리츠구` 캐릭터 표면 title 승격 제거 확인
- [x] `post_id=8531521` `강연금 -> 강철의 연금술사` manga/anime IP alias 오염 제거 확인
- [x] `post_id=8834919` `아집숨` positive control false negative 회귀는 v29 `20260526_104800_163466`에서 resolved 복구 확인
- [ ] v23은 5건 targeted 검증이므로 random baseline 및 P0/P1 high-risk bucket 확장 전까지 semantic gate `NO-GO` 유지
- [ ] VLM/OCR row는 Codex 내장 Browser `iab`에서 이미지 `placeholder/incomplete/broken=0` 스크린샷 근거 없으면 승인 제외

변경 작업마다 이 체크리스트를 확인한다. 필요 없는 항목은 히스토리에 `해당 없음`으로 남긴다.

## 2026-05-25 v16-v19 비웹소설 IP / 본문 공식 URL 재확인

- [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` targeted run v16/v17/v18/v19 수행
- [x] v19 `20260525_231813_131527`: completed `5`, failed `0`, pending `0`
- [x] `py_compile` 및 focused unittest 4건 통과
- [x] `post_id=8601885`는 `리그 오브 레전드` 웹소설 title 오매칭 제거 확인
- [x] `post_id=8424362`는 `Fate/에미야` IP title 확정 제거 및 unresolved 보류 확인
- [x] `post_id=8834919` positive control `아포칼립스에 집을 숨김` resolved 유지 확인
- [ ] `post_id=8531521` `강연금 -> 강철의 연금술사` exact alias rescue 오염 차단
- [ ] `post_id=8705431` 본문 공식 URL+직접 title evidence가 fetch unavailable/author mismatch로 버려지는 경로 보강
- [ ] VLM/OCR image row는 Codex 내장 Browser `iab`에서 `placeholder/incomplete/broken=0` 스크린샷 전까지 승인 제외 유지
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO` 유지

## 2026-05-25 alias/bridge v15 제목란 alias 복구 재확인

- [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` targeted run v15 수행
- [x] v15 전 LLM endpoint `bg-digitalservices/Gemma-4-E4B-it-NVFP4` 및 shard audit `36/36` 확인
- [x] v15 `20260525_210222_899635`: completed `8`, failed `0`, pending `0`
- [x] `post_id=9981263`은 v15에서 `성녀의 속마음이 들린다`, `work_resolution=resolved`, `anchor_type=title_exact`로 복구 확인
- [x] `post_id=9901127`은 v15에서 `is_relevant=true`, `work_resolution=multi_work`, `official_title=null`, `multi_work_title_list_resolution_demoted` 유지 확인
- [x] `post_id=10190186`, `11205204`, `11113480` positive/control resolved 유지 확인
- [x] `post_id=9000828`, `9019735` generic/common surface 과확정 없음 확인
- [x] 제목란 official detail 후보가 generic character-parenthetical 보류에 의해 과보수 demote되지 않도록 단위 테스트 추가
- [x] 일반 역할/종족 표면 `성기사`, `라미아`는 지원 title surface 후보로 취급하지 않는 negative test 추가
- [ ] `alias_recall_loss_false_negative=96` 확장 bucket에서 v15 보정 전이 확인
- [ ] `multi_work_or_adjacent_risk`, `weak_evidence_but_strong_resolution` bucket에서 `multi_work_title_list_resolution_demoted` 과보수/과확정 회귀 확인
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO` 유지

## 2026-05-25 alias/bridge v11-v14 후속 재확인

- [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` targeted run v11/v12/v13/v14 수행
- [x] v14 전 LLM endpoint `bg-digitalservices/Gemma-4-E4B-it-NVFP4` 및 shard audit `36/36` 확인
- [x] v11 `20260525_193840_310458`: completed `8`, failed `0`, pending `0`
- [x] v12 `20260525_195506_155856`: completed `8`, failed `0`, pending `0`
- [x] v13 `20260525_200735_669612`: completed `8`, failed `0`, pending `0`
- [x] v14 `20260525_202201_766849`: completed `8`, failed `0`, pending `0`
- [x] `post_id=9901127`은 v14에서 `is_relevant=true`, `work_resolution=multi_work`, `official_title=null`, `multi_work_title_list_resolution_demoted`로 단일 title 과확정 차단 확인
- [x] mixed/no-url title-surface 후보가 URL만 빌려 가짜 title로 승격되는 경로 차단 확인
- [x] multi-work title-list 최종 demotion 단위 테스트 추가 및 focused unittest 통과
- [x] `post_id=9981263`은 v14에서 오답 확정은 피했지만 `official_title=null`, `unresolved_work`로 남는 것을 확인
- [x] `post_id=11097334` 직접 브라우저 재확인: 본문 이미지 lazy placeholder가 남을 수 있어 `placeholder/incomplete/broken=0` 전까지 VLM/OCR `Strong` 금지 유지
- [x] `post_id=9981263` 제목란 alias `성녀 속마음`을 v15에서 `성녀의 속마음이 들린다`로 복구 확인
- [ ] multi-work title-list demotion을 `multi_work_or_adjacent_risk`, `weak_evidence_but_strong_resolution` bucket에서 확장 회귀
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO` 유지

## 2026-05-25 alias/bridge v8-v10 후속 재확인

- [x] Gemma 4 4B 기준 `expert_main.py --parallel 36` 후속 targeted run v8/v9/v10 수행
- [x] v8 `20260525_183704_522400`: completed `8`, failed `0`, pending `0`
- [x] v9 `20260525_185932_392781`: completed `8`, failed `0`, pending `0`
- [x] v10 `20260525_191458_896289`: completed `8`, failed `0`, pending `0`
- [x] v10 전 LLM endpoint `bg-digitalservices/Gemma-4-E4B-it-NVFP4` 및 shard audit `36/36` 확인
- [x] `post_id=11205204` `히집악` exact alias rescue는 v9/v10에서 유지 확인
- [x] `post_id=9000828`, `10190186`, `11113480` 핵심 control은 최신 후속 run에서 치명 회귀 없음
- [x] `post_id=9981263`은 v8/v9 통과 후 v10에서 `unresolved_work`로 회귀한 뒤 v15에서 제목란 alias primary 보존 안정화 확인
- [ ] `post_id=9901127`은 v9/v10에서 relevant로 살아났지만 `나 혼자만 솔플러` 단일 title 과확정이므로 multi-work unresolved hold 필요
- [ ] `post_id=9325585`는 v10에서 adjacent/non-relevant 방향으로 흔들리므로 author/character boundary 샘플로 별도 추적
- [ ] 후속 patch 전까지 전체 semantic gate `NO-GO` 유지

## 2026-05-25 10만건 테스트 부족점 및 해결 가능 항목 정리

- [x] `current_100k_issue_resolution_summary_ko_20260525.md`에 현재 부족점/버그/해결 가능 항목 정리
- [x] 최신 closure 기준 `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`, approval excluded `460/584` 확인
- [x] 최신 targeted run `20260525_174243_300254`: completed `8`, failed `0`, pending `0`, shard `36/36`
- [x] `post_id=9000828` `라미아` 일반 종족/트로프 표면이 title처럼 남는 generic surface 오매칭 targeted 차단 확인
- [x] `post_id=10190186` `성기사 -> 월드 오브 워크래프트` generic role bridge 오매칭 차단 및 `망한 교단의 성기사` direct full-title rescue 확인
- [x] `post_id=11205204` `히집악` slang_db exact alias false negative 및 `anchor_type` schema 매핑 버그 처리
- [x] `post_id=9981263` `성녀 속마음`이 최신 v15 slang/bridge run에서 제목란 alias 후보로 보존되는지 재확인
- [ ] `post_id=9901127` 여러 작품 감상 비교 글이 단일 title 미확정 때문에 `non_relevant/noise`로 과차단되는 회귀 처리
- [ ] 위 known-bad와 positive control을 포함해 `expert_main.py --parallel 36` targeted 재실행
- [ ] targeted 재실행 후 `generic_common_surface`, `weak_evidence_strong_resolution`, `alias_recall_loss_false_negative` 확장 회귀
- [ ] post-fix random baseline 및 P0/P1 regression validation 전까지 semantic gate `NO-GO` 유지

## 2026-05-25 generic_common_surface 전수 회귀 확인

- [x] `generic_common_surface` population `89/89` 전수 입력 생성
- [x] shard audit `36/36` 확인 후 `expert_main.py --parallel 36`으로 full bucket regression 수행
- [x] full regression completed `89`, failed `0`, pending `0`
- [x] after-review 결과 `ACCEPT=1`, `HOLD=88`을 승인 근거가 아니라 잔여 HOLD 근거로 기록
- [x] `thin-bridge title` guard로 일반어/트로프/캐릭터 표면 bridge 과잉 확정 제거
- [x] `unverified alias/plot title` guard로 공식 evidence 없는 LLM-only alias/비교작 확정 보류
- [x] 잔여 8건 v2 회귀 completed `8`, failed `0`, pending `0`
- [x] residual v2 기준 positive control `9901127`, `11113480` resolved 유지 확인
- [x] 최신 slang/bridge run에서 `9901127`이 resolved로 복구됐는지 재확인
- [x] `post_id=11205204` `히집악` false negative alias recall 처리 및 v4 재확인
- [x] `post_id=9981263` `성녀 속마음` alias 후보가 본문 비교작 후보에 밀리던 원인 처리 및 v15 재확인
- [x] `post_id=9981263` fix를 최신 targeted run에서 재확인
- [ ] `generic_common_surface`를 `ACCEPT`로 올리지 않고 `HOLD` 유지

## 2026-05-25 search_only zero-bucket guard 확인

- [x] 약한 anchor에서 `post_spans=0`, `official_urls=0`, `official_nonwiki=0`이면 단일 작품명 확정을 보류함
- [x] 실제 이슈 케이스 `post_id=11663540`이 `official_title=null`, `work_resolution=unresolved`로 내려감
- [x] 약한 근거/캐릭터 혼선 케이스 `post_id=10824887`이 `official_title=null`, `work_resolution=unresolved`로 내려감
- [x] positive control `post_id=9722392`의 별칭 resolved title은 유지됨
- [x] Gemma 4 4B 회귀런은 `expert_main.py --parallel 36` 기준으로 수행함
- [x] population `89/89` 전수 회귀로 해당 guard만으로는 `generic_common_surface` 전체 승인에 부족함을 확인
- [ ] guard print 직접 발화는 synthetic/unit fixture로 별도 확인

## 2026-05-25 VLM/OCR fallback 도구 패치 확인

- [x] `tools/capture_vlm_ocr_browser_review_cli.py`가 본문 이미지 로딩 상태를 packet에 남김
- [x] 이미지 없음/placeholder/incomplete/broken 상태가 `Strong`으로 승격되지 않음
- [x] `tools/build_vlm_browser_targets_from_review.py` target row에 `acceptance_gate`와 selector 조건이 포함됨
- [x] VLM/OCR target 재생성 테스트: `100`건, packet 누락 `0`
- [x] synthetic evidence grade 테스트: `Missing/Weak/Strong` 분기 확인
- [x] Gemma 4 4B `expert_main.py --parallel 36` smoke test: completed `2/2`, failed `0`
- [x] 시스템 `python` 대신 `.\venv\Scripts\python.exe`를 사용해야 함을 기록
- [ ] `re_search/re_judge/slang_db/re_run/human_review` queue 후속 처리

## 2026-05-25 iab 이미지 로딩 게이트 확인

- [x] Codex 내장 Browser plugin `@browser` / in-app browser `iab`로 VLM/OCR 100건 재검증
- [x] 본문 이미지 lazy-load를 고려해 스크롤/대기 후 `placeholder/incomplete/broken` 상태 기록
- [x] `post_id=11097334`에서 스크롤 전 placeholder가 남고 스크롤 후 실제 이미지가 로드되는 문제 재현
- [x] VLM/OCR combined 결과 `Strong=98`, `Missing=2`로 재집계
- [x] closure 재계산: `ACCEPT=124`, `HOLD=365`, `REPROCESS=93`, `INFO_MISSING=2`
- [x] `post_id=10794867`은 v96 attachment popup review로 `HOLD/human_review` 전환
- [ ] `post_id=10892069`은 삭제/리다이렉트 `INFO_MISSING/human_review`로 남아 source image URL 복구 가능성 확인 필요
- [ ] v96 기준 approval excluded `209`건에 대한 후속 slang_db/human review 처리

## 2026-05-24 적용 확인

- [x] 관련 docs/TODO/checklist 확인 및 갱신
- [x] Gemma 4 4B 재확인 실행은 `expert_main.py --parallel 36` 기준으로 수행
- [x] `MCP_SHARD_COUNT=36` 및 shard audit `36/36` 기록
- [x] VLM/OCR 개입 row는 브라우저로 직접 열고 screenshot/eval/visual evidence grade 기록
- [x] 리뷰/분석/검토/피드백 Markdown 본문은 한국어로 작성
- [x] 자동 실행 완료와 semantic quality 승인을 분리해 `NO-GO` 유지
- [ ] approval excluded `532/584`에 대한 후속 re_search/re_judge/slang_db/human/re_run 처리
- [x] 다음 VLM/OCR 브라우저 판독은 Codex 내장 Browser plugin `@browser` / in-app browser `iab`를 1순위로 진행
- [ ] Playwright CLI/headless fallback을 쓰면 내장 브라우저 사용 불가 사유와 fallback 증거를 manifest에 기록

## 변경 전

- [ ] 기존 docs/TODO/checklist에서 관련 항목 확인
- [ ] 변경 대상 파일의 현재 사용자/기존 변경 여부 확인
- [ ] 관련 run id, 로그, output, DB 경로 확인
- [ ] scan result directory 리뷰라면 `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`의 작업 모드와 증거 등급 확인
- [ ] 대량 테스트 런 검증이라면 `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md` 적용 여부 확인
- [ ] 실패 증상과 확인된 사실을 분리해서 기록

## 구현 중

- [ ] 기존 패턴과 환경변수 이름을 우선 사용
- [ ] 대량 런에 영향을 주는 변경은 fail-open/fail-closed 정책 명시
- [ ] 검색/MCP 변경은 timeout, retry, backoff, failover 동작 확인
- [ ] slang DB 변경은 저장 기준과 오염 차단 기준을 함께 확인
- [ ] 새 도구는 `--help` 또는 기본 실행 경로가 명확해야 함
- [ ] 4~20건 스모크와 품질 검증 샘플을 혼동하지 않도록 표본 단계 명시

## 일반화 / 하드코딩 금지

- [ ] 특정 `post_id`, 특정 작품명, 특정 오답 문자열만 막는 조건을 추가하지 않음
- [ ] 새 실패 사례는 먼저 실패 유형, 증거 불변식, 허용/차단 기준으로 일반화해서 기록
- [ ] LLM 프롬프트 예시는 원리 설명용으로만 사용하고, 예시 문자열을 특수 규칙으로 만들지 않음
- [ ] 코드 lexicon이 필요하면 `의학/건강`, `장르 일반어`, `검색 메타데이터`, `타매체`처럼 범주 단위로 이름 붙이고 주석/문서에 근거를 남김
- [ ] 회귀 테스트는 해당 사례 1건만이 아니라 같은 실패 유형의 positive/negative 이웃 케이스를 포함
- [ ] 예외 rescue를 추가할 때는 과차단되는 정상 케이스와 과확정되는 오답 케이스를 함께 검증
- [ ] curated/hardcoded alias registry hit는 독립 evidence가 아니며 검색/공식/원문/VLM-OCR/작품 맥락 anchor 없이 final title, `High`, stability/lock, guard exception을 열지 않음

## 검증

- [ ] scan result directory 리뷰: inventory, 핵심 파일 누락, 증거 등급, 최초 원인/fanout 분리 확인
- [ ] 서버 run 디렉터리 리뷰라면 result/logs 외 manifest, checkpoint JSONL, run audit JSON, review packet 포함 여부 확인
- [ ] 자동 감사/result_scan/run_audit/count summary를 자연어 품질 승인으로 쓰지 않음
- [ ] Python 문법 확인: `.venv312\Scripts\python.exe -m py_compile <files>`
- [ ] 대량 런 감사: `.venv312\Scripts\python.exe tools\audit_expert_run_health.py --run-id <RUN_ID>`
- [ ] shard 감사: `.venv312\Scripts\python.exe tools\audit_search_shards.py --count <N>`
- [ ] 병렬 smoke: 4~20건, 판정은 `SMOKE ONLY`
- [ ] 병렬 canary: 최소 200건, timeout/degraded/worker 로그 확인
- [ ] Gemma 4 4B 후속 재확인/재처리는 `MCP_SHARD_COUNT=36`과 shard audit `36/36`을 기록하되, `--parallel 36`은 상한으로 두고 manifest의 `effective_parallel=min(requested_parallel,input_post_count)`를 검증한다.
- [ ] risk discovery: 최소 1,000건, 위험 bucket 과표집
- [ ] validation: 최소 10,000건 또는 전체 run 100% 자동 감사와 결합
- [ ] slang DB 오염 지표 확인
- [ ] slang DB 후보 상태를 `saved_*`, `blocked_*`, `not_extracted`, `extracted_not_persisted`, `persisted_but_not_displayed`로 구분
- [ ] `blocked_by_result_contract`는 저장 차단 완료로 승인하지 않고 `sentence_like_alias_surface`, `pure_work_alias`, `exact_title_not_alias` 과차단/short alias 누락 여부를 표본 리뷰
- [ ] noisy detected term과 clean alias가 같은 packet에 있으면 noisy term 차단과 clean alias 후보 보존을 분리
- [ ] 정식 제목과 짧은 약칭이 함께 보이면 `detected_term/canonical_work_alias`에는 짧은 약칭만 남고 정식명은 `decoded_term/official_title`에 남는지 확인
- [ ] clean alias 보존 보강 후에는 `탑매`, `환암검천`류 positive와 외부 매체 negative control을 같은 targeted run에서 확인
- [ ] LLM/전문가 정성 리뷰 필요 여부 확인
- [ ] VLM/OCR 개입 정성 리뷰는 원문/이미지/evidence URL을 브라우저로 열어 screenshot path와 visual observation을 packet/label에 남김
- [ ] 브라우저 접근 실패, 삭제, 로그인/성인 인증, 404, blocked response는 `Missing`/`Weak` evidence로 기록하고 `ACCEPT` 금지
- [ ] VLM/OCR이 `explicit_text|cover_title`, `title_role=work_title`, `promotion_eligible=true`로 단일 작품 표면을 읽으면 검색 URL 부족만으로 `noise` 처리하지 않고 direct image evidence edge로 별도 검토
- [ ] direct image evidence로 title을 복구해도 official detail URL은 대표 제목이 일치할 때만 붙이고, URL 불일치 시 title correctness와 URL evidence strength를 분리 보고
- [ ] 표현 오타/축약/띄어쓰기 붕괴가 작품명 후보가 아니라 자연어 문장/감상 표현으로 해석되는 경우 final semantic reread가 최종 후보까지 다시 낮추는지 확인. 특정 표면어/숫자 패턴을 확정 차단 규칙으로 만들지 않고 packet-local `surface_paraphrase_notes`와 `semantic_seed_review` 결과를 함께 본다.
- [ ] 공식 상세 URL fetch/page analyzer title이 플랫폼 브랜딩이나 시놉시스 문장으로 잡힌 경우, 같은 URL 검색 title/snippet이 최종 작품명을 직접 지지하는지 확인하고 stale URL 제거와 URL 과삭제를 구분
- [ ] VLM/Vision이 캐릭터/장면 visual-only 정보만 준 경우 reason에서 제목 확정 근거처럼 표현하지 않는지 확인
- [ ] Round2/expanded review packet builder가 `final_semantic_reread_missing_for_semantic_seed`, `final_semantic_reread_reviewed`, `official_url_synopsis_or_branding_mismatch` bucket을 생성하는지 확인
- [ ] `KNOWN_ABBREVIATIONS` 또는 `KNOWN_TITLE_ABBREVIATIONS` 변경/사용 시 registry-only positive 경로를 `audit_hardcoded_alias_risk.py`로 재확인
- [ ] 등록 약칭 positive control과 no-work/context-only negative control을 같은 테스트 묶음에서 확인
- [ ] 필요 시 `tools/build_llm_judgment_review_packet.py --run-id <RUN_ID>` 실행
- [ ] 자연어 리뷰가 필요하면 random control과 high-risk bucket packet을 모두 생성
- [ ] Round 2 failure-pattern expansion이 필요하면 `tools/build_qualitative_round2_review.py` 또는 동등한 seed 고정 builder로 `round<N>_manifest/packets/labels/summary`를 생성
- [ ] Round 3 P0/P1 검증이 필요하면 `tools/build_qualitative_round3_targets.py` 또는 동등한 방식으로 대표 후보와 targeted input을 생성
- [ ] packet에 title/body/comment/evidence/reason/final decision이 포함됨
- [ ] `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING` 라벨과 action queue 기록
- [ ] `qualitative_review/<run_id>/sample_manifest.json`, `review_packets.jsonl`, `review_labels.jsonl`, `pattern_summary.md`, `gate_decision.md`, `action_queue.md` 산출물 확인
- [ ] 테스트 실행 가능 여부 확인. `pytest`가 없으면 그 사실을 기록

## 품질 개선 후 자동 확대 루틴

검색 품질, title/alias 판정, relevance gate, slang DB 저장 기준처럼 대량 런 품질에 영향을 주는 개선은 targeted 검증으로 끝내지 않는다.

- [ ] targeted/unit 검증이 통과하면 같은 턴의 기본 후속 작업으로 200건 canary를 실행
- [ ] 200건 canary가 `completed=200/200`, `failed=0`, `pending=0`을 만족하면 1,000건 risk discovery를 이어서 실행
- [ ] 200건 canary가 실패하면 1,000건으로 진행하지 않고 실패 원인, stuck/failed post, shard/search 상태를 먼저 기록
- [ ] canary/risk discovery는 `expert_main.py` startup shard discovery/health 또는 명시 shard audit을 사용. docker lifecycle 복구가 검증 대상일 때만 `--auto-up-shards`, `--auto-recreate-shards`를 붙인다.
- [ ] 각 run마다 result/checkpoint/manifest/audit/review packet 경로를 `VERIFICATION_RESULTS.md`에 남김
- [ ] known bad, positive neighbor, negative neighbor의 판정 변화를 별도 기록
- [ ] canary에서 새 과보수/과확정 품질 회귀가 발견되면 1,000건으로 확대하지 않고 HOLD 사유와 단건 재현 결과를 문서화
- [ ] 시간/비용/인프라 문제로 즉시 실행하지 못하면 `HISTORY.md`와 `TODO.md`에 defer 사유와 재개 명령을 남김

## 개선 전후 자동 비교

기능/품질 개선은 구현만으로 완료하지 않는다. 같은 입력과 같은 shard/env 조건으로 개선 전후를 비교할 수 있어야 한다.

- [ ] baseline run id, 입력 JSONL, shard/env/worker 설정을 기록
- [ ] 개선 후 같은 입력으로 200건 canary를 자동 실행
- [ ] canary 통과 후 1,000건 risk discovery를 자동 실행
- [ ] canary 이상에서는 `expert_main.py` startup shard discovery/health 또는 명시 shard audit을 사용. docker lifecycle 복구가 검증 대상일 때만 `--auto-up-shards`, `--auto-recreate-shards`를 붙인다.
- [ ] run audit을 baseline과 개선 run 양쪽에 실행
- [ ] checkpoint/manifest, failed/pending, search timeout/degraded, top latency를 표로 비교
- [ ] known bad post id의 판정 변화와 reason 변화를 별도 기록
- [ ] LLM 판단이 필요한 경우 개선 후 review packet을 생성
- [ ] 비교 결과 Markdown/JSON 경로를 `VERIFICATION_RESULTS.md`에 남김
- [ ] 자동화 스크립트가 없으면 수동 비교로 대체하되, 누락 사유를 `HISTORY.md`에 남김

## 문서 갱신

- [ ] `docs/devs/TODO.md` 색인 상태 갱신
- [ ] `docs/devs/DEV_TODO.md` 또는 `FEATURE_IMPROVEMENT_TODO.md` 상태 갱신
- [ ] `docs/devs/IMPROVEMENT_REGISTER.md` 개선 상태 갱신
- [ ] `docs/devs/HISTORY.md`에 결과/검증 추가
- [ ] `docs/devs/VERIFICATION_RESULTS.md`에 실행 명령과 판정 추가
- [ ] 관련 상세 문서 갱신 (`warp_sharding`, `slang_db`, run review 등)
- [ ] 리뷰/분석/검토/피드백 Markdown의 사람이 읽는 본문이 한국어인지 확인
- [ ] JSON key, enum, action id, bucket id, 명령어, 로그 원문은 원문 유지, 해석/판정/후속 작업 설명은 한국어로 작성
- [ ] 스캔 결과 리뷰에서 새 실패 유형이 드러나면 `SCAN_RESULT_REVIEW_GUIDE.md`, `OPERATION_QUALITY_CHECKLIST.md`, `IMPROVEMENT_REGISTER.md` 반영 필요 여부 확인
- [ ] 자연어 리뷰 루브릭/라벨/종료 조건이 바뀌면 `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md` 반영

## 완료 기준

- [ ] 문제 재현 또는 감사 결과가 문서화됨
- [ ] 조치 내용이 코드/설정/문서에 반영됨
- [ ] 검증 명령과 결과가 남음
- [ ] 개선 전후 비교 run 또는 비교 불가 사유가 남음
- [ ] 남은 위험과 다음 작업이 TODO에 남음
- [ ] run integrity와 semantic decision quality가 분리되어 `GO`, `REVIEW`, `NO-GO` 중 하나로 기록됨
- [ ] VLM/OCR 개입 케이스는 브라우저 screenshot/vision evidence 없이 semantic `GO`로 승인하지 않음
- [x] 10만 건 targeted known-bad 재검증은 Gemma 4 4B 기준 병렬 상한을 지키고, 소규모 run에서는 manifest의 `effective_parallel <= input_count/healthy_endpoint_count`와 no lifecycle 계약을 확인했는가
- [x] 외부 매체 IP가 플랫폼 URL/파생 팬픽 URL/slang DB alias를 통해 웹소설 title로 승격되는 대표 경로를 테스트로 고정했는가
- [x] `8531521`, `8834919`, `8424362`의 최신 단건 결과를 파일 경로와 함께 기록했는가
- [x] Browser `iab`로 `11097334` 이미지 lazy-load/pending 상태를 직접 확인했는가
- [x] VLM/OCR 브라우저 fallback 캡처 도구가 본문 첨부 이미지만 세고 lazy-load를 스크롤/대기 후 재평가하도록 했는가
- [x] VLM/OCR browser target builder와 closure builder가 같은 본문 이미지 gate를 사용하도록 맞췄는가
- [x] v62에서 흔들린 `11663540` character-only virtual battle 케이스를 v63 `--parallel 36` targeted run으로 재검증했는가
- [x] 자동 after-review 라벨러가 `Weak + title null/unresolved + boundary risk`를 `ACCEPT`로 올리지 않도록 packet 테스트를 추가했는가
- [x] `11718117`처럼 VLM/OCR이 직접 작품 표면을 읽은 post가 검색 URL 부족만으로 `noise`가 되지 않도록 targeted run으로 재검증했는가
- [x] official URL 후보 대표 제목이 선택 작품명과 다르면 `primary_work/title_candidates` URL까지 제거하는 회귀 테스트를 추가했는가
- [x] `11718091`처럼 표면 표현이 `23세인 줄`류 자연어 감상으로 읽히는 post가 search-only 후보로 재승격되지 않도록 final semantic reread targeted run으로 확인했는가
- [x] `11718097`처럼 공식 URL fetch 대표 제목이 시놉시스 문장으로 잡히더라도 같은 URL 검색 title/snippet이 작품명을 직접 지지하면 URL을 과삭제하지 않도록 targeted run으로 확인했는가
- [x] visual-only VLM 정보가 reason에서 title grounding으로 과장되지 않도록 targeted run으로 확인했는가
- [x] Round2 review builder가 `official_url_synopsis_or_branding_mismatch` bucket으로 v282 `11718097`을 선택하고 `ACCEPT/no_action`으로 분리하는지 확인했는가
- [x] Round2 review builder가 final semantic reread 누락/검토 bucket을 만들고 packet public fields에 기록하는지 단위 테스트로 확인했는가
- [x] Decoder `KNOWN_ABBREVIATIONS`가 검색/공식 근거 없이 `known_abbreviation_unverified` rescue 후보를 만들지 못하도록 테스트로 고정했는가
- [x] v521에서 comment metadata/final semantic reread와 small goal runtime contract 회귀 테스트를 현재 worktree 기준으로 재확인했는가
- [x] v521에서 `README.md`/`expert_readme.md`의 `--parallel`/자동 shard 설명을 max/effective_parallel/no lifecycle 계약으로 동기화했는가
- [x] v518 browser visual 한국어 요약/manifest의 mojibake 문구를 복구했는가
- [x] v523에서 active goal 범위를 10만 전체 semantic approval이 아니라 known-bad/high-risk seed closure로 정정해 문서화했는가
- [x] v523 `v422` 11건 issue-focused rerun을 `--parallel 36` max, VLM/OCR on, no lifecycle로 실행하고 runtime audit `GO`를 남겼는가
- [x] v523 자연어 라벨 `ACCEPT/HOLD/REPROCESS`와 action queue를 한국어 산출물로 남겼는가
- [x] v523 `11718083` validation error를 코드/프롬프트/fallback으로 재발 방지했는가
- [x] v523 `11718118`/`11718091` reason/discussion_type mismatch를 v525 재판정으로 닫았는가
- [x] v523 browser visual HOLD 대상 `11718069`, `11718076`에 screenshot/visual observation을 연결했는가
- [x] v526에서 `11718069` CLI counter Weak와 Playwright MCP full-page visual Strong 충돌을 manifest에 분리 기록했는가
- [x] v526에서 v518 누적 browser artifact에 `11718069`/`11718076` override를 결합하고 v523 seed 기준 browser visual missing `0`을 확인했는가
- [ ] Agentic/Arbiter의 `KNOWN_TITLE_ABBREVIATIONS` direct `High`, stability/lock, guard exception 경로도 독립 work anchor를 요구하도록 고쳤는가
- [ ] VLM/OCR 필요 post가 placeholder/lazy image 상태이면 `ACCEPT`하지 않고 `REPROCESS/INFO_MISSING`로 보내는 packet 규칙을 모든 review builder에 반영했는가
- [ ] 10만 건 semantic gate를 올리기 전에 remaining non-ACCEPT `389`건 또는 승인 제외 quarantine이 action별로 닫혔는가
- [ ] post-fix random baseline `500~1000`건과 P0/P1 high-risk regression을 다시 돌렸는가

## 2026-06-20 recall gate / verifier cap 실제 런 체크

- [x] 이후 검증 LLM/`expert_main.py` 실행은 요청 병렬도 `--parallel 16`으로 기록한다는 운영 규칙을 문서화했다.
- [x] C41 targeted canary를 `--parallel 16`으로 완료했다. manifest `requested/effective=16/7`, completed/failed/pending `7/0/0`.
- [x] C41에서 unavailable exact search title fallback으로 `11661853`의 `https://novelpia.com/novel/419119`가 stale/unavailable 대표 제목 때문에 삭제되지 않는 것을 확인했다.
- [x] D4 integrated VLM/OCR 55-row run을 `--parallel 16`으로 실제 실행했고, verifier runaway `acc_chars=121,531`을 확인한 뒤 완료 근거가 아니라고 분리했다.
- [x] verifier/relation judge bounded cap을 추가하고 D5 suspect subset을 `--parallel 16`으로 재실행했다.
- [x] D5 manifest `requested/effective=16/5`, completed/pending/failed `5/0/0`, VLM/OCR semantic gate `READY`, `large_run_complete=true`를 확인했다.
- [x] D5 로그에서 `verifier max_tokens=8192`, `verifier_relation_judge max_tokens=2048`, 최대 `acc_chars=6,363`을 확인했다.
- [x] 관련 회귀 테스트 `111`건 `OK`를 확인했다.
- [x] 이번 변경은 targeted/suspect canary 검증이며 full scan approval이 아니다. semantic quality는 `REVIEW-LOCKED / NO-GO`, slang DB write-back 금지를 유지한다.
- [x] D10 8-row patch target canary를 `--parallel 16`, VLM/OCR on, `--slang-db off`, `MCP_HEALTH_INCLUDE_SEARCH=1`로 완료했다.
- [x] D10 run meta `requested_parallel_raw=16`, `requested_parallel=16`, `effective_parallel=8`, completed/pending/failed `8/0/0`, VLM/OCR semantic gate `READY`를 확인했다.
- [x] D10에서 `11682781` direct packet URL `https://novelpia.com/novel/405193`이 search-repaired neighbor URL로 교체되지 않음을 확인했다.
- [x] D10에서 `11652175` `담텔기` update-question alias가 `괴담 호텔 탈출기` / `https://novelpia.com/novel/102155`로 회수됨을 확인했다.
- [x] D4 55-row integrated canary는 verifier cap 이후 D11로 새로 끝까지 재실행해 completed/pending/failed `55/0/0` 여부를 확인했다.
- [x] D11 run meta `requested_parallel_raw=16`, `requested_parallel=16`, `effective_parallel=16`, search health `16/16 OK`, VLM/OCR semantic gate `READY`, `large_run_complete=true`를 확인했다.
- [x] D11에서 B precision pin `11661847`, `11657013`, `11666700`은 resolved 과승격 없이 hold/unresolved 계열로 남고, B recall boundary `11648980`, `11650585`, `11682781`은 resolved 유지됨을 확인했다.
- [x] D11에서 C positive `11652175`, `11661853`, `11677911`은 resolved, C negative `11687635`, `11695607`, `11705276`, `11665081`은 final title null/hold 계열로 유지됨을 확인했다.
- [x] D11 비교표와 잔여 품질 후보를 `integrated_D11_vlmocr16_20260620_current_summary.json` 및 `VERIFICATION_RESULTS.md`에 기록했다.
- [x] D11 이후 현재 worktree 기준 `py_compile`과 targeted unittest 6건 `OK`를 재확인했다.
- [x] D11은 integrated canary runtime/target acceptance 근거이며 full scan approval이 아니고 semantic quality `REVIEW-LOCKED / NO-GO`, slang DB write-back 금지를 유지한다.

## 2026-06-22 completed779 Loop 2 체크

- [x] authoritative contract `goal.md`와 `COMPLETED779_REIMPROVEMENT_LOOP2_GOAL_PROMPT.md`를 기준으로 실행했다.
- [x] active queue preflight: rows `25`, split `still_under_resolved_or_noise=16`, `title_or_url_still_mismatched=9`, active `garbage_title_after=0`.
- [x] Loop 2 input split: text/url/comment `8`, image/OCR `17`, missing `0`, duplicate `0`.
- [x] direct fallback health gate는 `MCP_DIRECT_SEARCH_FALLBACK_READYZ_OK=1` 명시 시에만 ready로 인정하도록 보강했다.
- [x] text/url/comment canary `8/8` 완료: `out/expert_result_20260622_201044_448457.json`.
- [x] image/OCR canary `17/17` 완료: `out/expert_result_20260622_201630_167085.json`, VLM/OCR Semantic Gate `READY`.
- [x] combined compare `25/25` 생성: `candidate_or_human_review_preserved=7`, `resolved_expected_title=1`, `url_lint_preserved=9`, `still_under_resolved_or_noise=8`.
- [x] remaining queue `8`건 생성: `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue.json`, `out/completed779_improvement_goal_20260622/reimprovement_loop2_queue_ko.md`.
- [x] control audit: active `garbage_title_after=0`, `11694064` bad title 미재확정, `wrong_work=9` bad pipeline title 회귀 없음.
- [x] 검증: `py_compile` pass, focused suite `204 tests OK`.
- [x] semantic quality는 `REVIEW-LOCKED`, full scan approval은 `false`로 유지했다.

## 2026-06-22 completed779 Hermes Continuous Loop 체크

- [x] Loop 2 remaining queue `8`건을 active queue로 확인했다.
- [x] active queue는 모두 `still_under_resolved_or_noise`이며 post_id는 `11695623`, `11706856`, `11708442`, `11716478`, `11697241`, `11697255`, `11702072`, `11703624`다.
- [x] `goal.md` 맨 위에 Hermes Continuous active contract를 추가했다.
- [x] 새 copy-paste prompt `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`를 추가했다.
- [x] Council role을 7축으로 확장했다: Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Code Hook, Prompt/Orchestration, Verification/Docs.
- [x] subagent/model/tool diversity rule을 문서화했다.
- [x] completion 기준을 queue empty 또는 row-level HOLD/human_review/INFO_MISSING/quarantine/no_generalizable_fix_left로 고정했다.
- [x] Loop 2 prompt는 실행 완료된 과거 prompt로 표시하고, 다음 prompt는 Hermes prompt로 연결했다.
- [x] active 8-row queue의 `suspected_code_hook`, `proposed_next_fix`, `required_test`를 채워 다음 loop 실행 입력으로 보강했다.
- [x] bucket별 acceptance map과 `unresolved_matchable` terminal taxonomy를 goal/prompt/checklist에 반영했다.

## 2026-06-22 completed779 source-correctness refresh 체크

- [x] Docker/SearXNG shard를 복구하고 audit `ok=2/2`를 확인했다.
  - audit: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/search_shard_audit_after_restore.json`
  - direct fallback: `false`
  - degraded direct provider: `false`
- [x] text/url/comment source refresh canary `14/14`를 완료했다.
  - result: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_text_result.json`
  - manifest completed/pending/failed: `14/0/0`
- [x] image/OCR source refresh canary `25/25`를 완료했다.
  - result: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_image_ocr_result.json`
  - manifest completed/pending/failed: `25/0/0`
  - VLM/OCR Semantic Gate: `READY`
- [x] combined result와 compare를 생성했다.
  - combined: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/canary/source_correctness_refresh_combined_result.json`
  - compare: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/compare/source_correctness_refresh_compare.json`
  - after matched: `39/39`
  - movement: `resolved_expected_title_and_url=6`, `review=12`, `url_lint_preserved=21`
- [x] next queue `0`을 확인했다.
  - queue: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_next_queue.json`
  - queue report: `out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_next_queue_ko.md`
- [x] controls를 확인했다.
  - `11694064`: bad pipeline title 재확정 없음, but `판초우의의 마법사` recall 미회수
  - `11710033`: `판초법사` alias title null / promotion blocked
  - `wrong_work` controls: bad pipeline title로 되돌아가지 않음
- [x] semantic gate를 분리했다.
  - runtime integrity: targeted canary completed
  - semantic quality: `REVIEW-LOCKED`
  - full scan approval: `false`
- [ ] 다음 Hermes expansion queue를 새로 만든다.
  - 기존 39건 재실행이 아니라 residual `review=12`, `url_lint_preserved=21`, native-web unused non-ACCEPT에서 seed를 만든다.
  - 우선 축: 판초 alias recall, 괴담호텔 character/setting cluster, OCR explicit title/search absent, cross-domain OCR pollution, source-local alias conflict.

## 2026-06-23 completed779 Hermes Loop 5 postfix1 체크

- [x] subagent council fan-out 결과를 수집하고 완료 agent를 닫았다.
  - axes: Candidate/Comment, OCR/Visual, Source/URL, Search/Web, Prompt/Orchestration, Code Hook.
  - 결론: subagent는 승인 근거가 아니라 main Codex 재확인 입력으로만 사용했다.
- [x] `11698880` source/url hygiene expected-title conflict를 코드 hook으로 분리했다.
  - `source_url_hygiene` seed에서 expected title과 after title이 다르면 final `official_title/heretic_url`을 비우고 `blocked_official_title` 및 `expected_official_title_conflict`를 남긴다.
  - post_id/title 하드코딩 없음.
- [x] compare helper가 `_judge_seed` embedded input row를 seed로 해석하도록 보강했다.
- [x] Loop 5 combined compare postfix1을 생성했다.
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop5_source_residual_combined_compare_postfix1.json`
  - movement: `candidate_or_human_review_preserved=16`, `resolved_expected_title=4`, `review=12`, `still_under_resolved_or_noise=4`, `title_or_url_still_mismatched=1`, `url_lint_preserved=7`
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop5_source_residual_next_queue_postfix1.json`, rows `5`
- [x] `11698880` 단일 image/OCR runtime canary를 실행했다.
  - input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop5_postfix1_11698880_image_ocr.jsonl`
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop5_postfix1_11698880_image_ocr_result.json`
  - log: `logs/expert_run_20260623_012944_631536.log`
  - completed/failed/pending `1/0/0`, VLM/OCR Semantic Gate `READY`
  - internal arbiter still selected `가챠 중독자의 퓨전펑크 생활`, but final public title was demoted to `None` with lint/HOLD evidence.
- [x] focused verification completed.
  - `py_compile`: `expert_main.py`, `src/llm_batch/candidate_audit.py`, `tools/compare_completed779_improvement.py`
  - unittest first pass: `tests.test_candidate_audit tests.test_completed779_compare`, `45 tests OK`
  - broadened focused suite: `tests.test_candidate_audit tests.test_completed779_compare tests.test_judge_seed_registry tests.test_title_lead_search_inferred_guard tests.test_agentic_pipeline_alias_contract tests.test_final_semantic_reread_gate tests.test_expert_main_comment_metadata tests.test_expert_main_input_loader`, `205 tests OK`
  - `git diff --check`: exit `0`, LF->CRLF warnings only
- [ ] upstream title/body multi-candidate orchestration fix remains open.
  - `11698880` still demonstrates that body comparison/secondary candidate can dominate before postprocess guard.
  - next fix should create `multi_candidate_hold`/candidate ledger preservation before Arbiter lock.

## 2026-06-23 completed779 Hermes Loop 7 체크

- [x] Loop 7 broader residual queue `36`건을 생성했는가
  - queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_queue.json`
  - split: main `16`, control `20`, text/url/comment `16`, image/OCR `20`
- [x] Loop 7 text partial runtime 상태를 완료로 과장하지 않고 기록했는가
  - first run `20260623_022342_639179`: completed/flushed/pending/failed `12/11/1/0`
  - resume run `20260623_024758_871942`: completed/flushed/pending/failed `2/0/2/0`
  - partial combined rows `14`, missing text rows `11702087`, `11705239`
- [x] `11702087` flags runtime error와 search-seed/orchestrator 1차 수정이 테스트로 고정됐는가
  - `agentic_pipeline.py` early flags merge
  - `orchestrator.py` internal work cluster search probe
  - `orchestrator.py` Korean connective low-specificity lead-token guard
  - `tests.test_title_lead_search_inferred_guard` `67 tests OK`
- [x] Loop 7 runtime blocker report를 별도 산출물로 남겼는가
  - `out/completed779_improvement_goal_20260622/hermes_loop7_text_runtime_blockers_ko.md`
- [x] `11705239`를 broad parallel text canary에 재투입하기 전 single-row runtime root cause 또는 quarantine note를 남겼는가
  - post-fix single result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11705239_fix1_result.json`
  - completed/flushed/pending/failed `1/1/0/0`
  - semantic state: `official_title=null`, `work_resolution=none`, `title_resolution_state=unresolvable_memory_query`
- [x] `11702087` downstream relation/Jury/multi-work/character-drift/snippet invalidation guard를 subagent/council 분석 후 generalized fix로 좁혔는가
  - `agentic_pipeline.py`: deliberated character/setting work convergence가 있으면 `multi_work_guard` title clear/J1 verifier veto/final reread hold에서 rescue 가능.
  - `candidate_audit.py`: `source_url_hygiene` seed bucket은 `garbage_title` disagreement라도 precision demotion을 적용하지 않고 hygiene lint로 유지.
  - canary: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11702087_fix9_result.json`, completed/failed/pending `1/0/0`, title/url `괴담 호텔 탈출기` / `https://novelpia.com/novel/102155`.
  - limitation: fix9 runtime `436.8s`; verifier official-detail fast path was unit-verified after the canary, full rerun after this performance-only change is still pending.
- [x] Loop 7 image/OCR `20`건을 VLM/OCR gate `READY`로 별도 실행/격리했는가
  - broad image/OCR은 `19/20`으로 partial이었고, missing `11716480`은 single-row fix6로 `1/1` 완료했다.
- [x] Loop 7 combined compare와 next queue를 생성하면서 runtime integrity와 semantic movement를 분리했는가
  - final combined `36/36`: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix6_final36_result.json`
  - fix7 compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix7_unwrapped_final36_compare.json`
  - fix7 next queue rows `2`, fix17 next queue rows `0`
- [x] subagent/model/tool diversity를 실제 실행 또는 limitation으로 기록했는가
  - Pascal/Raman subagents informed root cause and docs/code-hook review; main Codex rechecked and implemented.
  - model/tool diversity is partial in this slice; no additional external provider full rerun after fix9.
- [x] `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, `slang_db write-back 금지`를 유지했는가

## 2026-06-23 completed779 Hermes Loop 7 fix1 체크

- [x] subagent council 4축을 병렬 실행하고 main Codex가 재확인했는가
  - runtime/code hook, OCR/visual, source/search, verification/docs
  - subagent output은 승인 근거가 아니라 evidence triage 입력으로만 사용
- [x] `11705239` broad text blocker를 single-row로 격리했는가
  - pre-fix hang: `logs/expert_run_20260623_050058_659227.log`
  - post-fix result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_text_single_11705239_fix1_result.json`
  - semantic state: title null, `promotion_blocked`, `unresolvable_memory_query`
- [x] Loop 7 text canary를 `16/16`으로 결합하고 compare했는가
  - combined result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_text_combined_fix1_result.json`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_text_fix1_compare.json`
- [~] Loop 7 image/OCR canary를 실행하고 partial status를 과장하지 않았는가
  - broad run: `20260623_052157_158066`, effective parallel `2`
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_image_ocr_fix1_result.json`
  - status: `19/20`, missing `11716480`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_image_ocr_fix1_compare.json`
- [x] `11716480` single-row quarantine attempt를 남겼는가
  - input: `out/completed779_improvement_goal_20260622/inputs/hermes_loop7_image_ocr_single_11716480_quarantine.jsonl`
  - log: `logs/expert_run_20260623_061321_455105.log`
  - result status: result JSON absent, checkpoint `0`, manifest `completed=0`
  - observed: OCR/Jury recovered `여대생 가랑이 사이 무릎 꿇은 엄마들`, but postprocess did not flush
- [x] combined partial compare를 만들고 next queue를 생성했는가
  - combined partial: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_broader_residual_combined_fix1_partial35_result.json`, rows `35/36`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_broader_residual_combined_fix1_partial35_compare.json`
  - next queue: `out/completed779_improvement_goal_20260622/hermes_loop7_broader_residual_next_queue_fix1_partial35.json`, rows `12`
- [x] `11716480` postprocess hang을 single-row targeted fix6로 닫았는가
  - fix2/fix3: result/checkpoint flush 실패
  - fix4: runtime `1/1` but semantic weak_visual_only failure
  - fix5: OCR recovered but close-title hygiene mismatch demoted
  - fix6: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_image_ocr_single_11716480_fix6_result.json`, completed/flushed/pending/failed `1/1/0/0`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_compare.json`, movement `url_lint_preserved=1`
  - remaining queue: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_image_ocr_single_11716480_fix6_remaining_queue.json`, rows `0`
  - final title is a close OCR variant; `heretic_url=null` remains a source/url hygiene lint
- [ ] image/OCR final combined compare를 `36/36`으로 재생성했는가
- [x] runtime integrity, targeted canary status, semantic quality, full scan approval을 분리했는가
  - runtime integrity: Loop 7 broad image/OCR remains partial `19/20`, but `11716480` single-row runtime quarantine is fix6-closed
  - targeted canary status: text `16/16`, image/OCR broad `19/20`, `11716480` single `1/1`
  - semantic quality: `REVIEW-LOCKED`
  - full scan approval: `false`

## 2026-06-23 completed779 Hermes Loop 7 fix17 체크

- [x] fix7 compare helper wrapper-row 문제를 고치고 final `36/36` compare를 재생성했는가
  - compare movement: `candidate_or_human_review_preserved=13`, `resolved_expected_title=1`, `resolved_expected_title_and_url=1`, `review=12`, `still_under_resolved_or_noise=2`, `url_lint_preserved=7`
- [x] fix7 hard next queue `2` rows를 targeted loop로 닫았는가
  - `11711600`: candidate preservation closure
  - `11706832`: fix11 candidate preservation, fix17 resolved expected title
- [x] `11706832` short community alias가 J11 title drift로 되돌아가지 않는가
  - result: `out/completed779_improvement_goal_20260622/canary/hermes_loop7_fix17_j11_alias_lock_11706832_result.json`
  - final: `황제폐하가 웹소설 작가임을 숨김`, `https://novelpia.com/novel/385635`
  - compare: `out/completed779_improvement_goal_20260622/compare/hermes_loop7_fix17_j11_alias_lock_11706832_compare.json`, movement `resolved_expected_title=1`
- [x] subagent/model/tool diversity 원칙을 다음 prompt에 반영했는가
  - `docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md` records model/tool diversity as variance reduction, not voting.
- [x] Loop 7 hard queue가 `0`이고 다음 작업이 새 expansion/source-correctness queue임을 기록했는가
