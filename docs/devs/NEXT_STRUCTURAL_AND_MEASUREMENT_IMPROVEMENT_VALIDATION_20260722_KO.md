# 다음 구조·계측 개선 검증 보고서

## 결론

**구조 경계와 저장 계약은 검증됐지만, v6 grouped run은 아직 전체 승격할 수 없다.** v6는 runtime `6/6 GO`, noninterference `6/6 GO`, linked `190/192`였고 measurement는 `4/6`으로 `NO-GO`다. 의미 consensus도 `REVIEW_REQUIRED_SYSTEMATIC_REGRESSION`/`NO-GO`이며 systematic regression은 `11718097`, `11716480` 두 건이다. 따라서 `public_apply=false`, `full_scan_approval=false`를 유지한다.

이 보고서의 JSON 정본은 [NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_ARTIFACT_20260722.json](/home/kimjang/llm_novel_dc_coommunity_parser/docs/devs/NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_ARTIFACT_20260722.json)이다. canonical renderer validation/package는 `passed`, browser verification은 설치된 Chromium headless-shell 부재로 `structural_only`다. source interaction과 viewport QA는 `not_verified`다.

## 정본 범위

| run | 범위 | 결과 |
|---|---|---|
| v4 | [measurement_grouped_ab_v4.../run_summary.json](/home/kimjang/llm_novel_dc_coommunity_parser/out/regression_safe_2712_next_improvements_20260722/measurement_grouped_ab_v4_bounded_drain_code_frozen_20260722_162638/run_summary.json) | runtime `6/6`, measurement `3/6`, linked `189/192` |
| v5b | [grouped_ab_v5b_synth_quarantine_20260722_190141](/home/kimjang/llm_novel_dc_coommunity_parser/out/regression_safe_2712_next_improvements_20260722/grouped_ab_v5b_synth_quarantine_20260722_190141) | repeat2 BEFORE `post_id=11718061`의 `slang_insight` list `AttributeError`; 이후 shape guard 적용 |
| v6 | [grouped_ab_v6.../run_summary.json](/home/kimjang/llm_novel_dc_coommunity_parser/out/regression_safe_2712_next_improvements_20260722/grouped_ab_v6_shape_guard_20260722_202616/run_summary.json) | runtime `6/6`, measurement `4/6`, linked `190/192`, noninterference `6/6` |

모든 grouped arm은 동일한 `32행×3회` RunSpec이다. `runtime GO`와 `measurement GO`는 서로 다른 게이트이며, linked 수의 분모는 call `192`건이다.

## 구조 개선과 검증 경계

| 변경 | 검증 상태 | 경계 |
|---|---|---|
| client hard-cap bounded drain | 코드/회귀 테스트 통과 | hard-cap 뒤 usage만 drain; 의미 출력 동결 |
| Synth 기본 `2048` + trusted-terminal quarantine | Synth canary `GO` | runaway 억제 관측이지 의미 개선 증거가 아님 |
| verifier dict shape guard | shape canary `GO` | list shape `AttributeError` fail-close 방어 |
| repeat-stop bounded usage drain 기본 ON | deterministic branch 테스트 통과 | kill-switch `LLM_DRAIN_USAGE_AFTER_EARLY_STOP=0` |
| PublicationFinalizer / ObservationEnvelope | isolated tests만 존재 | production runtime wiring 미구현 |

최종 테스트 집계는 focused `31`, adjacent `263`이다. [client.py](/home/kimjang/llm_novel_dc_coommunity_parser/src/llm_batch/llm/client.py)와 `tests/`의 결과를 합산한 값이며, 실패·오류 0을 의미한다.

## 계측·비간섭 게이트

| 게이트 | v4 | v6 | 판정 해석 |
|---|---:|---:|---|
| runtime | 6/6 | 6/6 | 실행 완료만 의미 |
| measurement | 3/6 | 4/6 | 전체 grouped 승격 조건 미충족 |
| linked call measurement | 189/192 | 190/192 | `192` calls 분모, 100% 아님 |
| noninterference | 정본 요약 확인 범위 | 6/6 | `public_apply=false`, WAL 비간섭 |

v6의 fresh observation은 실제 sidecar apply가 아니다. [sidecar_grouped/report.json](/home/kimjang/llm_novel_dc_coommunity_parser/out/regression_safe_2712_next_improvements_20260722/grouped_ab_v6_shape_guard_20260722_202616/grouped_analysis_v6/sidecar_grouped/report.json)의 `causal_warning`처럼 AFTER는 fresh stochastic observation이므로 sidecar 인과효과로 말하지 않는다.

## 의미·검색·라우터 관측

| 지표 | BEFORE | AFTER | 분모/범위 | 해석 |
|---|---:|---:|---|---|
| majority compliant | 19 | 17 | post 32 | 2건 감소, causal claim 금지 |
| majority noncompliant | 13 | 15 | post 32 | systematic regression gate를 닫음 |
| systematic regression | 0 | 2 | post majority | `11718097`, `11716480` |
| correct-title majority | 2 | 0 | eligible 11 | 회복 0 |
| HOLD | 5/5 | 5/5 | eligible 5 | 유지 |
| false positive | 0 | 0 | eligible 3 | 유지 |
| wrong-work unrecovered | 3/5 | 3/5 | eligible 5 | 미해결 |
| pass majority | 1/2 | 1/2 | eligible 2 | 유지 |
| unsafe/wrong-title any-run | 0 | 2 | 전체 post 32 | AFTER any-run 관측, majority unsafe 0 |
| router high-risk recall | 44/66 (66.7%) | 51/66 (77.3%) | high-risk 66 | false-review도 7/30→8/30 |
| search unrecovered | 192 | 204 | analysis 집계 | 원인 attribution 없음 |

정량 근거는 [repeat_consensus_summary.json](/home/kimjang/llm_novel_dc_coommunity_parser/out/regression_safe_2712_next_improvements_20260722/grouped_ab_v6_shape_guard_20260722_202616/grouped_analysis_v6/repeat_consensus_summary.json) 및 위 sidecar report다. `exact32x3` 비교에서 개선 `0`이며, 게이트는 `REVIEW_REQUIRED_SYSTEMATIC_REGRESSION`/`NO-GO`다.

## Canary와 frozen replay

* [early_stop_drain_canary summary](/home/kimjang/llm_novel_dc_coommunity_parser/out/regression_safe_2712_next_improvements_20260722/early_stop_drain_canary_20260722_225400/summary.json): `GO`, `linked 1/1`, drift `0`, WAL unchanged, `public_apply=false`. 실제 canary에서는 repeat-stop이 발동하지 않았으므로 해당 branch의 실환경 발동을 주장하지 않는다.
* [final publish-contract replay](/home/kimjang/llm_novel_dc_coommunity_parser/out/regression_safe_2712_next_improvements_20260722/frozen2712_publish_contract_replay_early_stop_drain_final/publish_contract_replay_summary.json): `GO`, `2712/2712`, contract mismatch `0`, normal→abnormal `0`. 이는 저장된 publish contract의 deterministic 보존만 검증하며 LLM 의미 효과가 아니다.

## 승인 상태와 다음 게이트

| 항목 | 상태 | 다음 조건 |
|---|---|---|
| v6 runtime/noninterference | `GO` | 유지 |
| v6 measurement | `NO-GO` | 동일 32×3 grouped에서 6/6, linked 192/192 |
| semantic/search/router | `NO-GO` | systematic regression 0 및 별도 품질 게이트 green |
| PublicationFinalizer/ObservationEnvelope | `DESIGN READY` | façade/additive wrapper golden equivalence 후 runtime 연결 |
| P2 early-route/full scan | `NO-GO` | 상위 게이트 전부 green 뒤 별도 canary·승인 검토; 현재 `full_scan_approval=false` |

measurement 미-green으로 decision-call tokens/cost는 `NOT_ESTIMABLE`이다. 수치가 부분 관측으로 존재하더라도 비용 개선률이나 인과효과를 계산하지 않는다. self-contained HTML은 [NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_REPORT_20260722_KO.html](/home/kimjang/llm_novel_dc_coommunity_parser/docs/devs/NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_REPORT_20260722_KO.html)이며, 시각/browser 상호작용 검증 한계는 위 `structural_only` 경계로 보존한다.
