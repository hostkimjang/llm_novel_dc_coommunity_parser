# Adjudicated Re-baseline Contract

> 2026-07-10 semantic convergence override: `adjusted_drift_count`는 판결 baseline 대비 runtime 변화 감지 diagnostic으로 보존한다. Stochastic 변화 자체를 exact-output 실패로 만들지 않는다. `adjusted_full375_collateral=GO`는 drift union을 전수 판결하는 deterministic builder+validator가 통과하고 `unreviewed_adjusted_rows=0`, `true_semantic_regression_count=0`일 때와 동치다. Unsafe publish, wrong-work, golden positive loss는 면제하지 않는다. Builder/validator, always-on 연동, unit tests가 구현되기 전에는 자가 작성 JSON으로 새 metric을 선언하지 않고 gate를 `NOT_IMPLEMENTED / NO-GO`로 둔다. 아래 기존 `adjusted_drift_count=0` 문구는 이 semantic adjudication gate로 supersede하며 historical tool behavior 설명으로만 읽는다. 상세는 `docs/devs/REGRESSION_SAFE_GROUNDING_BOUNDED_CONVERGENCE_PROTOCOL.md`를 따른다.

> 2026-07-10 implementation audit: 초기 구현의 compare/packet/map/receipt 신뢰 경계를 독립 negative control로 깨고 보강했다. 현재 validator는 actual source/baseline/after/golden 375 scope, `drift_id` multi-variant union, source allow-list packet, packet/map canonical hash와 option origin, actual serialized publication, golden hard safety, terminal 필수 필드, validator code/artifact receipt를 재계산한다. Always-on은 이 receipt를 readback하고 runtime `375/375/0/0`을 요구한다. 관련 검증은 `loop641_gate_tool_independent_audit.json/.md`, focused `86 tests PASS`다.

## 목적

Loop620/Loop621 계열 full375 결과의 raw diff는 2026-06-26 bootstrap baseline 대비 변화이므로, 정당한 FP 제거와 의도된 recall/wrong-work 복구가 모두 판결된 뒤에도 raw가 0이 될 필요가 없다. 전 행 판결이 끝나면 판결된 결과를 새 baseline으로 재동결해 이후 collateral을 "옛 버그 대비 변화"가 아니라 "올바른 행동 대비 drift"로 측정한다.

## Re-baseline 허용 조건

- 최신 full375 survey/search split의 true triage 전 행이 `ACCEPT`, `REPROCESS`, `HOLD`, `expected_fp_removal_exempt`, `fixed` 등 명시 decision으로 닫혀야 한다. Loop620/621 계열 최초 기준은 `true triage 57`이고, 최신 Loop629 기준 수량은 `true triage 64`다.
- intended recovery blind/title correctness 판정이 전 행 끝나야 한다. 제목 정답성 미판정 행은 re-baseline 대상에 넣지 않는다.
- Loop620/621 계열 최초 기준 intended recovery는 전 행 판결 뒤 재동결 대상이며, 최신 Loop629 기준 intended recovery blind/title correctness 수량은 `21`이다.
- current search non-ok hard blocker가 `0`이어야 한다. `SEARCH_DEGRADED`, unrecovered degraded, required-search/publication 행의 `MISSING search_health`가 남은 결과는 re-baseline source가 아니다. 검색을 쓰지 않고 공개 제목도 없는 null/FP 제거 관측은 hard blocker가 아니라 별도 observation으로 회계한다.
- publication contract가 `GO`여야 한다.
- source/baseline/after missing, duplicate post_id, runtime count mismatch가 없어야 한다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 상태는 re-baseline 준비 중 계속 유지한다.

## 재동결 산출물

- `adjudicated_baseline_result`: 판결 반영 후 375행 결과.
- `adjudication_ledger`: 각 post_id의 decision, 근거 파일, exemption/fix 이유, reviewer/source.
- `adjusted_baseline_manifest`: source run id, projection id, commit, row count, search/publication gate, ledger hash.
- `historical_raw_compare`: 2026-06-26 baseline 대비 raw diff. 참고용이며 완료 blocker가 아니다.

## 현재 적용 상태

- Loop638에서 true triage/intended recovery 계열 판결을 59행 `adjudication_ledger`로 닫고 `loop638_adjudicated_rebaseline_result.json`을 새 baseline으로 재동결했다.
- 이후 Loop639/640 collateral은 2026-06-26 bootstrap raw 변화가 아니라 판결 baseline 대비 `adjusted_drift_count`로 평가한다.
- Raw `105`는 정당 FP 제거와 의도된 복구가 반영된 historical diagnostic이다. Raw가 0이 되지 않아도 완료 blocker가 아니며, 매 run raw row를 다시 triage하거나 재소송하지 않는다.
- 완료 gate는 raw count가 아니라 adjusted full375 collateral `GO`, search non-light `GO`, publication contract `GO`, full_scan path 검증을 함께 요구한다.

## 도구 필드 계약

- `tools/build_adjusted_collateral_blind_packet.py`는 before/after/status/golden/`_judge_seed`를 숨긴 source-only anonymous A/B packet과 private option map을 분리 생성한다.
- `tools/build_adjusted_collateral_adjudication.py`는 judge의 atomic blind choice를 before/after와 재결합해 5분류를 결정적으로 유도하며, 입력의 자가 작성 gate/count/class는 승인값으로 신뢰하지 않는다.
- `tools/validate_adjusted_collateral_adjudication.py`는 compare/verdict/result/golden/packet/map을 다시 열고 hash, union, 분류, terminal contract를 재계산한다.
- `tools/evaluate_always_on_regression_gates.py`는 adjudicated mode에서 validator artifact가 없으면 fail-closed한다. Completion metric은 `adjudicated_semantic_gate`이며 `adjusted_drift_count`는 diagnostic이다.
- `adjusted_full375_collateral=GO`는 validator/semantic `GO`, `unreviewed_adjusted_rows=0`, `true_semantic_regression_count=0`, `actionable_unfixed_count=0`일 때만 가능하다.

- 판결 baseline을 비교 기준으로 쓸 때 `tools/compare_projection_collateral.py`는 `--baseline-mode adjudicated_rebaseline`로 실행한다.
- 이 모드의 산출물은 `baseline_mode=adjudicated_rebaseline`, `collateral_measure=adjusted_drift`, `adjusted_drift_count=<판결 baseline 대비 drift>`를 남긴다.
- 2026-06-26 bootstrap 대비 raw 수치는 `historical_raw_collateral_regression_count` 또는 `historical_raw_compare`에만 둔다. 이 값은 설명용이며 완료 gate metric이 아니다.
- 과거 always-on의 `gate_metric=adjusted_drift_count` 동작은 superseded다. 현재는 validated semantic adjudication을 gate로 쓰고 historical raw와 adjusted drift 모두 diagnostic으로만 보존한다.

## 이후 Collateral 판정

- 완료 gate와 매 run blocker는 `adjusted_drift` 기준으로 판단한다.
- `raw_vs_20260626`은 역사적 이동량과 회계 설명용으로만 남긴다. 6/26 baseline 대비 raw는 정당 제거/복구 때문에 영구히 0이 아닐 수 있다.
- re-baseline 적용 후에는 6/26 raw row를 매 run마다 다시 triage하거나 재소송하지 않는다. 새 run에서 확인할 대상은 판결 baseline 대비 drift, unreviewed adjusted row, search hard blocker, publication contract violation이다.
- raw가 0이 아니어도 adjusted drift가 0이고 runtime/search/publication/full_scan 조건이 닫히면 collateral raw 자체는 완료 blocker가 아니다.
- re-baseline 이후 새 run에서 `adjusted_drift > 0`, unreviewed adjusted row, search hard blocker, publication contract violation이 나오면 `NO-GO`다.
- re-baseline 이전에는 raw를 approval blocker처럼 쓰지 말고, raw 행을 expected FP removal, intended recovery, search hold, true triage로 분해한 adjusted 회계로만 다룬다.

## 완료 Gate 문구

완료 기준은 `full375 collateral GO + full_scan 경로 검증`이지만, collateral GO의 수치는 re-baseline 전후 모두 adjusted 기준이다. Raw count는 2026-06-26 bootstrap 대비 참고 수치이며, full_scan approval을 여닫는 기준이 아니다.
