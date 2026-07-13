# P0 검색 미복구 공개 차단: 개선 전·후 하네스 보고서 (2026-07-11)

## 결과

실제 Loop643 Golden18 저장 결과에서 **필수 검색이 미복구인데 작품명이 공개된 행**을 `1→0`으로 줄이는 정적 전·후 투영을 완료했다. 대상 5건의 후보 자료 누락은 `0`이다. 다만 검색 근거 자체는 `5→5`로 복구되지 않았고 실제 개선 후 모델 실행도 하지 않았으므로, 종합 판정은 `PARTIAL_SAFETY_IMPROVEMENT_NOT_RUNTIME_VALIDATED`다.

`semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## 무엇을 구현했나

- `src/llm_batch/promotion_gate.py`
  - 검색 상태를 정해진 형식으로 받는 `RetrievalState(required/attempted/recovered/hard_blocked)`를 추가했다.
  - 기본값 `None` 또는 빈 상태에서는 기존 v2 판정과 입력 지문을 바꾸지 않는다.
  - 필수 검색이 미복구이거나 강제 차단 상태면 기존 공개 검사의 `search_evidence_missing` 또는 `search_blind_condition` 차단 경로를 사용한다.
  - JSON으로 저장했다가 다시 읽을 때 검색 상태가 사라지지 않게 역직렬화를 추가하고, boolean이 아닌 값은 조용히 통과시키지 않는다.
- `tools/run_pipeline_improvement_harness.py`
  - 입력·결과·manifest·runtime plan·integrity·검색 gate와 현재 하네스·공개 검사 코드 지문을 변경 불가 실행 명세에 묶는다.
  - 18행 전부의 모델·endpoint·프롬프트·설정·실행 지문·병렬·검색 계약이 같은지 확인한다.
  - 대상 5건은 먼저 `검색 상태 없음`으로 저장 baseline 결정을 `5/5` 재현한 뒤, 같은 상태·근거에 `RetrievalState`만 추가해 실제 `can_publish_title()` 결과를 비교한다.
  - 게시글 번호 누락·추가·중복, 출처 SHA 불일치, 혼합 실행, 후보 자료 누락을 닫힌 기본값으로 차단한다.

## 실제 저장 결과 기준 개선 전·후

| 지표 | 개선 전 | 개선 후 정적 투영 | 해석 |
| --- | ---: | ---: | --- |
| 입력/결과 게시글 | 18/18 | 18/18 | 순서·집합·중복 검사 통과 |
| 현재 게이트의 baseline 재현 | - | 5/5 | 검색 상태 추가 전 저장 판정과 정확히 일치 |
| 필수 검색 미복구 대상 | 5 | 5 | 검색 장애 자체는 해결하지 않음 |
| 대상 중 작품명 공개 | 1 | 0 | 미복구 상태의 공개 1건 차단 |
| 최종 판정 상태 변경 | - | 1 | `publish → candidate_only` |
| 후보 자료 누락 | - | 0 | 5건 모두 재판단 자료 보존 |
| 정확도 퍼센트 | 없음 | 없음 | `NOT_AVAILABLE_UNCALIBRATED`, 임의 숫자 생성 안 함 |

여기서 공개 `1→0`은 필수 검색 hard blocker 5건 범위의 수치다. Loop643 전체 18행의 공개행 수를 뜻하지 않는다. 실제 개선 후 runtime 결과가 아니라 저장 artifact에 현재 게이트를 적용한 정적 투영이다.

## 합성 계약 시험

별도 합성 7행은 위험 5행과 정상 공개 대조 2행으로 구성했다.

- 검색 상태를 주지 않은 개선 전 계약: unsafe publish `5`
- 같은 상태에 typed 검색 정보를 준 개선 후 계약: unsafe publish `0`
- 정상 공개: `2→2`, lost correct `0`
- 시나리오 지문: `d0ed5555886ceb81607e6d01f267fbcaed33f968265cbcd29b12152c4ed6b831`
- 두 번 생성한 결과 파일 SHA 일치: `e4c876012b6602dec3bd723dc4e4448538d656ec5cf2f595641d6d155ee61106`

합성 `5→0`은 실제 저장 결과의 `1→0`과 다른 증거이며 서로 더하지 않는다.

## 검증

- `py_compile`: 공개 검사, 두 하네스, 두 회귀 시험 통과
- focused + 공개 계약: `119 tests OK`
  - `tests.test_pipeline_improvement_harness`
  - `tests.test_retrieval_state_fail_close`
  - `tests.test_promotion_gate_contract`
- 복합 검색·후보·공개 수렴: `156 tests OK`
  - `tests.test_build_search_recovery_composite_gate`
  - `tests.test_candidate_audit`
  - `tests.test_publication_contract_convergence_audit`
- 총 결정적 회귀 시험: `275 tests OK`

## 산출물

- 정본 실행 명세: `out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/run_spec.json`
- 전·후 비교 JSON: `out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/before_after_comparison.json`
- 사람이 읽는 전·후 보고서: `out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/before_after_comparison.md`
- 합성 결과: `docs/devs/loop_reports/search_fail_close_probe_20260711.json`
- 목표 프롬프트: `docs/devs/GOAL_PIPELINE_IMPROVEMENT_TESTDRIVEN_20260711.md`

`retrieval_failclose_v1`~`v4`는 하네스 자체의 fail-close 결함을 독립 감사로 보강하는 과정에서 생성한 개발 산출물이다. 현재 정본은 `v5`다.

## 게이트와 다음 단계

| 게이트 | 상태 |
| --- | --- |
| artifact·실행 명세 무결성 | `GO` |
| 게시글 번호 완전성 | `GO` |
| baseline gate 인과 재현 | `GO / 5 of 5` |
| 검색 실패 공개 차단 | `GO_STATIC_PROJECTION` |
| 검색 근거 복구 | `NO-GO / 5` |
| 실제 개선 후 runtime | `NOT_RUN_STATIC_PROJECTION / BLOCKED_ACTIVE_PRODUCTION_RUN` |
| 정확도 퍼센트 | `NOT_AVAILABLE_UNCALIBRATED` |
| 의미 품질 | `REVIEW-LOCKED` |
| 운영 전체 승인 | `false` |

진행 중인 104,502건 실행에는 코드나 설정을 주입하지 않았고, 새 LLM/MCP runtime도 시작하지 않았다. 이 실행이 끝난 뒤 실제 검색 상태를 `GroundingState.retrieval`로 연결하고, 별도 출력·병렬 16·대시보드·속어 저장 끔 조건에서 동일 입력 개선 후 runtime을 검증한다. 그 전에는 P1 여러 후보·작품 없음 비교를 shadow 계약과 정적/합성 하네스 범위에서만 진행할 수 있다.
