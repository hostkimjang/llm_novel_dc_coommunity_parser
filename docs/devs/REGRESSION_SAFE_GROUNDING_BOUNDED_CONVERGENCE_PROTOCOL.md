# Regression-Safe Grounding Bounded Convergence Protocol

> 2026-07-11 strict blocked 적용 기록: 원 i7 handoff, prior continuation `2/3`, 이번 automatic continuation의 세 별도 goal turn에서 동일 user-authority blocker가 재확인됐다. Safe material action은 0이고 reset 사유가 없어 §7 strict 조건에 따라 `BLOCKED_HANDOFF`로 전환했으며 `update_goal(blocked)` 호출이 성공했다. Complete/GO가 아니며 `REVIEW-LOCKED`, production `full_scan_approval=false`다. 근거: `loop642_blocked_handoff_20260711_025714.json`.

> 2026-07-11 continuation 재감사 기록: i7 fingerprint와 SHA-bound exact-once runtime은 변하지 않았고 hard unsafe `11698880`은 adjudication-only safe terminal 불가다. Golden 파일은 Windows `ReadOnly=false`이므로 OS-level immutable이 아니라 SHA/no-rerun 계약 봉인으로 표현한다. 새 architecture/model goal 권한이 열리지 않아 같은 사용자 권한 blocker를 `2/3`회로 기록했다. Threshold 전이므로 `update_goal(blocked)`는 호출하지 않았고 docs-only sync는 progress에서 제외했다. 근거: `loop642_limit_reached_continuation_reaudit_20260711_024832.json`.

> 2026-07-11 적용 기록: 마지막 정상 개입 i7의 exact-once Golden에서 hard unsafe 1건이 재발해 본 protocol의 `PLATEAU_AUDIT_ONLY` 분기를 실행했다. 잔여 `1/1`은 `generalizable_fix`로 판결됐고 safe terminal이 아니므로 `LIMIT_REACHED_HANDOFF`다. Strict 3-turn external blocker가 아니어서 `update_goal(blocked)`는 호출하지 않았다. N=5/fresh375는 Golden hard GO 미충족으로 미실행·미승인이다.

> 적용 범위: Loop640 이후 regression-safe grounding continuation goal.
> 목적: 품질·승인 게이트를 낮추지 않으면서 동일 packet, 동일 full375, 문서-only 회차가 영구 반복되는 것을 막는다.
> 상태: `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 기본으로 유지한다.

## 1. 완료 범위 정규화

- 이 goal에서 `full_scan path`는 **current-head homogeneous regression panel375 runtime 1회와 그 결과에 대한 integrity/search/publication/golden/collateral/always-on gate 체인**이다.
- 성공한 homogeneous panel375를 별도 이름의 full_scan으로 다시 실행하지 않는다.
- 779/1933/full 10만 production scan과 production `full_scan_approval`은 이 개선 goal의 완료 범위가 아니다. 필요하면 별도 goal로 분리한다.
- 최종 보고에는 `harness_panel375_gate`와 `production_full_scan_approval`을 반드시 분리한다.

## 2. 의미 기준과 검색 기준

- 2026-06-26 raw `105` 및 historical raw diff는 diagnostic이다. 0 강제나 매 run 재소송 대상이 아니다.
- runtime `adjusted_drift_count`는 우선 변화 감지값으로 보존한다. stochastic resolved/null/title 변화 자체를 exact-output 실패로 단정하지 않는다.
- drift 전 행을 source-native/blind adjudication해 `intended_recovery`, `legitimate_fp_removal`, `same_work_canonical_change`, `safe_no_public_terminal`, `true_semantic_regression`으로 분류한다.
- `adjusted_full375_collateral=GO`는 drift union을 전수 adjudicate한 deterministic builder+validator가 통과하고 `unreviewed_adjusted_rows=0`, `true_semantic_regression_count=0`일 때와 동치다. 기존 `adjusted_drift_count`는 diagnostic으로 함께 남긴다.
- 위 builder/validator와 unit tests가 구현되기 전에는 새 metric을 자가 작성 JSON으로 선언하지 않고 gate를 `NOT_IMPLEMENTED / NO-GO`로 둔다. Canonical `ADJUDICATED_REBASELINE_CONTRACT.md`도 같은 의미로 갱신해야 한다.
- Unsafe public promotion, wrong-work, golden positive loss는 terminal HOLD로 면제할 수 없다.
- `search_gate=GO`는 publish/release 의존 행의 `required_search_hard_blocker=0`이고, 그 밖의 degraded/missing 행 전부가 safe no-public terminal로 adjudicate되어 `unreviewed_search_rows=0`일 때와 동치다. 이는 global 미검토 search debt를 숨기는 gate 완화가 아니다.
- 삭제·로그인·성인인증·외부 provider timeout으로 확인 불가능한 개별 행은 public identity를 세우지 않고 evidence-backed terminal 상태로 닫는다. 불완전한 search에 의존해 publish된 행은 hard `NO-GO`다.

## 3. Relevant fingerprint와 progress ledger

각 의미 있는 회차는 `convergence_state.json/.md`를 만들고 다음을 기록한다.

- `relevant_fingerprint`: runtime 영향 code/prompt/config diff, input hash, adjudicated baseline hash, runtime model, search/VLM/OCR/slang 계약. docs-only diff, loop/run id, timestamp는 제외한다.
- `blocker_signature`: gate, post_id, failure bucket, reason code를 정규화한다. run id, loop 번호, 시각은 제외한다.
- `progress_vector`:
  - `integrity_defect_count`
  - `terminal_evidence_missing_count`
  - `actionable_unfixed_count`
  - `publication_golden_test_flip_failure_count`
  - `required_search_vlm_blocker_count`
  - `true_semantic_regression_count`
  - `unreviewed_adjusted_rows`
  - `panel375_proof_debt`
- `expected_information_gain`, `selected_action`, `changed_files`, `tests`, `before_after`, `next_unblock_condition`.
- `goal_turn_id`, `same_blocker_goal_turn_streak`, `last_counted_goal_turn_id`, `streak_reset_reason`.

Material progress는 모든 hard-safety component가 non-increase이고 적어도 하나가 strict decrease일 때다. `unreviewed`가 evidence-backed `actionable` 또는 `terminal`로 이동하는 전이는 총 proof debt가 줄고 기존 hard PASS를 깨지 않을 때만 허용한다. 새 일반화 계약은 trace+test+runtime으로 검증되어야 한다. 다음은 progress가 아니다.

- 문서만 갱신하거나 loop/run 번호만 증가
- bucket 이름 변경 또는 같은 blocker 재서술
- 동일 artifact를 새 파일명으로 복사
- 동일 fingerprint에서 우연한 0을 기다리는 반복 실행

## 4. 실행 예산과 동일 재실행 금지

- 동일 `relevant_fingerprint`의 packet/full375 단순 재실행은 금지한다.
- flip 측정이 필요한 targeted+control packet은 fingerprint당 **한 번의 bounded N=5 probe**만 허용한다. 5회 outcome union을 전수 adjudicate하며 unsafe publish, wrong-work, golden positive loss가 한 번이라도 있으면 `FAIL`이다. Benign variance만 있고 union unreviewed가 0인 경우에만 `publish_allowed=false`인 `variance_quarantine`을 허용한다.
- complete full375는 release-candidate fingerprint당 1회만 허용한다. full375를 flip 측정 수단으로 사용하지 않는다.
- interrupted run은 immutable checkpoint 복구+residual 실행으로 완성하며 같은 output을 처음부터 재실행하지 않는다.
- 새 full375 전에는 예상 감소 blocker/post_id, 새 relevant fingerprint, publication0, golden18, affected tests+전체 sweep, targeted/parent replay, flip probe, search16/VLM preflight를 기록한다.
- pipeline code가 바뀌지 않은 docs-only HEAD drift는 새 runtime fingerprint가 아니다.

## 5. Terminal ledger

안전하지만 본질적으로 모호하거나 현재 근거로 일반화 fix가 불가능한 행은 `terminal_hold_ledger.json/.md`로 닫을 수 있다.

허용 label:

- `HOLD`
- `human_review`
- `INFO_MISSING`
- `unresolved_matchable`
- `variance_quarantine`
- `no_generalizable_fix_left`

각 행 필수 필드:

- `post_id`, `terminal_label`, `row_rationale`, `evidence_refs`
- `source_hash`, `input_hash`, `before_after`, `blind_verdict`
- `promotion_decision`, `publish_contract_trace`, `test_replay_artifacts`
- `attempted_lanes`, `missing_or_conflicting_evidence`
- `official_title=null` 또는 안전한 비공개 상태
- `publish_allowed=false`, `bypassed_gate=false`
- `candidate_preserved=true` 또는 보존 불가 사유
- `publication_violation=false`
- `unblock_condition`, `independent_review`

Terminal ledger 행은 actionable residual과 true-regression gate에서 제외할 수 있지만 raw drift와 제외 이유를 숨기지 않는다. 여러 행을 같은 상투 문구로 일괄 terminal 처리하는 것은 금지한다. Golden positive loss, wrong-work public title, unsafe publish는 terminal 면제 대상이 아니다.

## 6. Plateau 감사

다음 중 하나면 `PLATEAU_AUDIT`로 전환하고 동일 lane 실행을 중단한다.

- 같은 `blocker_signature`에 서로 다른 안전한 개입 2개를 적용했지만 progress vector가 감소하지 않음
- 같은 state signature가 재등장하거나 A→B→A cycle이 관측됨
- 두 연속 의미 회차가 docs/bucket 변화 외 material progress를 만들지 못함

Plateau 감사 순서:

1. 추가 full375를 발주하지 않는다.
2. 독립 explorer/challenger가 remaining 전 행을 `generalizable_fix`, `safe_terminal`, `external_blocker`로 재분류한다. 승인권은 메인에게 있다.
3. root-cause family별로 아직 시도하지 않은 일반화 fix가 있으면 fingerprint를 바꾸고 1회 검증한다.
4. 안전한 fix가 없고 terminal 요건을 충족하면 row-level terminal ledger로 닫는다.
5. repo 내부에서 수행할 안전한 material action이 없고, 사용자 입력·권한 또는 외부 상태/새 capability 없이는 해소할 수 없는 동일 blocker가 3 consecutive goal turns에서 재확인되면 strict blocked audit을 적용한다.

한 turn 안의 반복 관측으로 blocked streak를 여러 번 올리지 않는다. progress vector 감소, blocker signature 변경, blocked goal 재개 시 streak를 0으로 재설정한다.

## 7. Goal 최종 상태

항상 다음 셋 중 하나로 귀결한다. 진척 없는 `ACTIVE / NOT_COMPLETE`를 무기한 유지하지 않는다.

### `COMPLETE_GO`

- homogeneous panel375 runtime과 모든 harness/semantic/safety gate가 통과했다.
- actionable residual과 true semantic regression이 0이다.
- `update_goal(status="complete")` 전에 원 objective를 requirement-by-requirement 감사한다.

### `COMPLETE_SAFE_TERMINAL`

- hard publication/golden/integrity gate가 통과했다.
- actionable residual과 unreviewed adjusted row가 0이고 잔여는 계약을 만족하는 safe terminal ledger뿐이다.
- 이 개선 goal의 stop condition은 충족하지만 `semantic_quality=REVIEW-LOCKED`, production `full_scan_approval=false`를 유지할 수 있다. 이를 production GO로 표현하지 않는다.
- 원 objective가 terminal closure를 완료로 허용하는지 다시 감사한 뒤에만 `update_goal(status="complete")`를 검토한다.

### `BLOCKED_HANDOFF`

- vLLM endpoint/model, search/VLM/OCR, 필수 source, 사용자 정책·권한, 검증된 model/architecture capability ceiling처럼 현재 repo 내부 작업만으로 해소할 수 없는 동일 blocker가 3 consecutive goal turns에서 재현되고 안전한 내부 대안이 없다.
- immutable artifacts, 영향 post_id, 실패 증거, 정확한 resume command와 unblock condition을 남긴다.
- 이 조건에서만 `update_goal(status="blocked")`를 호출하며 GO나 complete로 표현하지 않는다.

개별 삭제/인증 source는 전체 external blocker가 아니라 row-level terminal 후보다. 내부 generalizable fix가 남아 있으면 blocked가 아니라 `CONTINUE`이며, 다음 action은 반드시 새 information gain 또는 새 relevant fingerprint를 가져야 한다.

## 8. 회차 보고 필수 항목

- before/after progress vector
- relevant fingerprint와 blocker signature
- 이번 action의 information gain
- identical replay 여부와 실행 예산 사용량
- terminal ledger 신규/변경 행
- plateau streak와 reset 사유
- `CONTINUE`, `COMPLETE_GO`, `COMPLETE_SAFE_TERMINAL`, `BLOCKED_HANDOFF` 중 현재 판정
- runtime integrity, targeted status, semantic quality, harness panel375 gate, production full-scan approval의 분리 표기
