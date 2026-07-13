# Architecture V2 내부 재감사 — 2026-07-13

## 결론

Goal `019f4f3f-4f46-78d1-8418-50834da44924`의 종료 판정은 `COMPLETE_SAFE_TERMINAL / ARCHITECTURE_V2_INTEGRATED / ACTUAL_EFFECT_WAITING_EXTERNAL_INPUT`이다. exact Git closure와 staged-tree clean export까지 통과했다. 과거 `M1_SHADOW_FOUNDATION_COMPLETE`는 역사적 기반이다. source-backed 자료 부재는 C 실제 효과만 `NOT_ESTIMABLE`로 남기며 운영은 `REVIEW-LOCKED / full_scan_approval=false`다. production `20260711_113712_379597`은 읽기 전용으로 유지했다.

## 실제 흐름 전·후

```text
기존: input -> AgenticPipeline -> legacy DecisionCallLedgerRegistry -> public result
V2 목표: input -> AgenticPipeline -> [기본 OFF shadow adapter]
                              -> StageBudget/cache/singleflight receipt
                              -> legacy writer + V2 dual-write compare
                              -> CandidateSet/NIL -> typed confidence report
                              -> public result (변경 없음)
```

한 행의 trace는 다음과 같다. producer가 `UNKNOWN`이면 CandidateSet recall은 `NOT_EVALUABLE_GENERATION_UNKNOWN`이고, NIL label은 후보와 별도 클래스다. 이 상태에서 typed report는 probability와 percentage를 모두 `null`, action은 `ABSTAIN`, public effect는 `NONE_SHADOW_ONLY`로 남긴다. producer가 `COMPLETE`이고 source-backed FROZEN label·calibration artifact가 모두 결속될 때만 행별 `confidence_percentage`를 기록할 수 있다. 이 퍼센트는 모델의 그 행 확률이지 정확도 퍼센트가 아니다. 여러 `FROZEN_ACTUAL` 행만 reader에 넣어야 accuracy/ECE/Brier/log loss/selective risk/AURC가 산출된다.

## 이번 구현과 검증

- `src/llm_batch/pipeline_stage_runtime_adapter.py`: search stage에만 명시 주입되는 기본 OFF limiter/cache/singleflight adapter다. 구형 checkpoint의 미주입 상태는 legacy 경로로 유지한다.
- `src/llm_batch/decision_ledger_dual_write.py`: legacy 우선 dual-write, V2-root coordination lock, restart reconcile, one-way rollback latch, cross-adapter rollback, receipt identity coverage를 제공한다. 자동 production enable은 금지한다.
- `src/llm_batch/confidence_report.py`: `typed_confidence_report_v1`은 producer completion, CandidateSet recall readiness, NIL 포함 확률 공간, percentage 의미와 source/label/calibration/prediction artifact 결속을 validation한다.
- `tools/read_typed_confidence_metrics.py`: JSONL을 무쓰기 재독해 policy threshold 없이 지표를 계산한다. non-actual/synthetic/uncalibrated input은 `NOT_ESTIMABLE`로 닫는다.
- `tests/fixtures/typed_confidence_source_less_contract_v1.jsonl`: source-less reader 계약 fixture다. 결과는 `NOT_ESTIMABLE_NOT_FROZEN_ACTUAL`이며 실제 개선 효과가 아니다.
- `tools/validate_launch_packet_intake.py`: 실제 실행 없이 packet·manifest·정책·동일 frozen input의 BEFORE/AFTER 명령을 점검하고 미입력은 `WAITING_EXTERNAL_INPUT`으로 닫는다.
- 로컬 회귀: confidence/candidate/stage `187`, ledger/publication `113`, stage foundation `53`, launch/paired/selective `197` tests가 PASS했다. clean export 증거는 P0에서 별도 기록한다.

## 남은 내부 순서와 게이트

| 순서 | 산출물 | 현재 상태 | gate |
| --- | --- | --- | --- |
| P0 | V2 source/tests/tools/docs Git 추적 및 staged-tree clean export | `PASS / 137 paths / 181 tests` | local PASS와 clean export PASS를 분리 |
| P1 | Stage runtime adapter, DecisionLedger dual-write/rollback | `PASS` | 기본 OFF, legacy 비간섭, crash/restart/rollback/receipt coverage |
| P2 | CandidateSet/NIL/producer와 typed confidence reader | `PASS` | source-less `NOT_ESTIMABLE`, actual artifact 의미 결속 |
| P3 | intake validator, operator template, paired command plan | `PASS` | no-write, dashboard ON, requested `--parallel 16` |

외부 C는 내부 순서가 아니다. source-backed DEV/CAL/FROZEN·policy v3·10+6 packet·fresh pair가 도착한 뒤에만 actual metric과 paired CI를 산출한다.

외부 input이 없는 지금 C 지표는 `null/NOT_ESTIMABLE`이다. `REVIEW-LOCKED / full_scan_approval=false`를 유지한다.
