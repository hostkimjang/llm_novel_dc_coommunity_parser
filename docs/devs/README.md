# 개발 문서 허브

## Architecture V2 읽는 순서

1. [시스템 아키텍처](../ARCHITECTURE.md): 현재 공개 경로와 기본 OFF인 shadow·측정 계층
2. [Architecture V2 내부 재감사](ARCHITECTURE_V2_INTERNAL_REAUDIT_KO_20260713.md): 내부 통합 범위와 검증 근거
3. [Actual packet 입력 인벤토리](ACTUAL_PACKET_INPUT_INVENTORY_KO_20260712.md): 실제 효과 검증의 external blocker와 재개 조건
4. [검증 결과](VERIFICATION_RESULTS.md): 실행한 테스트와 증거 경계
5. [실제 입력 준비와 출시 판정 런북](LAUNCH_READINESS_RUNBOOK_KO.md): packet, preflight, fresh pair 순서
6. [LLM 파이프라인 개선 현황](LLM_PIPELINE_IMPROVEMENT_STATUS_KO_20260712.md): P2/P3/P4 계보와 정확도·비용 지표 설명
7. [2026-07-14 라이브 런 중간 감사](LIVE_PIPELINE_RUN_REVIEW_KO_20260714.md): 현재 104,502행 실행의 적용 경로, 검색 저하, 의미 blocker, bounded stop/repair 판정
8. [2026-07-14 Slang DB 오염 감사](SLANG_DB_POLLUTION_AUDIT_KO_20260714.md): 일반명사·비별칭 work delta, exact alias-pair write/seed fail-close, 중앙 승격 gate
9. [Goal 코드 산출물 정리 정책](CODE_ARTIFACT_CLEANUP_POLICY_KO.md): 일회성 smoke/builder 수명주기, Git allowlist 승격 기준, 2026-07-15 정리 결과
10. [`src/llm_batch` 소스 구조](SOURCE_LAYOUT_KO.md): 기능별 패키지 경계, import 이동 표, 한국어 주석·프롬프트 규칙
11. [동결 2,712건 회귀 cohort·bundle 계약](FROZEN_2712_REGRESSION_COHORTS_KO_20260716.md): exact cohort, 결정적 실행 bundle, paired transition 지표와 현재 게이트
12. [동결 2,712건 개선 BEFORE/AFTER](LIVE_RUN_2712_BEFORE_AFTER_REPORT_20260716_KO.md): P0a actual GO, P0b 격리 NO-GO·rollback, 검색·router·runtime·full-scan 분리 판정
13. [동결 2,712건 recovery sidecar 구현·검증](LIVE_RUN_2712_RECOVERY_SIDECAR_IMPLEMENTATION_REPORT_20260717_KO.md): 기존 공개 projection 불변, direct OCR review-only provenance, 남은 fresh/search/activation 게이트
14. [동결 2,712건 recovery sidecar 실제 묶음 검증](LIVE_RUN_2712_RECOVERY_SIDECAR_GROUPED_AB_REPORT_20260718_KO.md): 32행 양 arm 각 3회, 192 receipt·실제 WAL 비간섭, 개선·회귀·변동성, 자동 activation NO-GO
15. [동결 2,712건 남은 개선 BEFORE/SHADOW-AFTER](LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_REPORT_20260718_KO.html): exact 2,712 paired receipt, 새 32행×3회 release-candidate 관측, router/P1/search/P2 분리 판정
16. [2,712건 개선 아키텍처 전문가 회의](ARCHITECTURE_IMPROVEMENT_EXPERT_COUNCIL_REPORT_20260719_KO.html): 실제 Terra/Opus/Luna 전문가 의견, 현 아키텍처·개선/미미/실패 분류, 기존 정답 보존 우선 P0/P1/P2 연구 순서
17. [계측 완결성 개선과 다음 아키텍처 계획](MEASUREMENT_USAGE_DRAIN_IMPROVEMENT_REPORT_20260720_KO.html): hard-cap 뒤 provider usage drain-only 구현, 과거 문제 2행 실제 canary 2/2 GO, 2,712행 replay, PublicationFinalizer·ObservationEnvelope 다음 계획
18. [구조·계측 후속 구현과 3회 묶음 회귀](NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_REPORT_20260722_KO.html): Synth quarantine·verifier shape guard·repeat-stop usage drain, 32행×양 arm×3회 runtime/measurement/semantic 분리 판정, 2,712행 최종 replay
19. [v7 qualified 최종 BEFORE/AFTER 보고서](NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_REPORT_20260723_KO.html): 사전 고정 semantic-blind replacement를 포함한 exact `192/192` 계측, cohort별 개선·미미·실패, 실제 호출·토큰·시간, 2,712 contract replay와 semantic/full-scan `NO-GO` 경계. [검증문](NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_VALIDATION_20260723_KO.md)과 [portable artifact](NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_ARTIFACT_20260723.json)를 함께 본다.
20. [로컬 LLM grounding 벤치마크 심층 연구](LOCAL_LLM_GROUNDING_BENCHMARK_RESEARCH_20260901_KO.md): MTEB/MIRACL/NoMIRACL/KLUE/EL·selective prediction 사례를 현 P3 계약에 대조하고, domain gold schema·stage metric·표본 수·정답 회수 개선 A/B와 승격 gate를 제안한다. 커뮤니티 축약어·은어·용어집 8개 source 감사와 `소설 매칭 / 커뮤니티 이해` 투트랙 silver-mining 설계를 포함한다. 새 actual run은 없으며 `FROZEN_ACTUAL NOT_READY`, semantic/full-scan `NO-GO`를 유지한다.

현재 상태는 범위별로 다르다.

| 범위 | 상태 | 설명 |
| --- | --- | --- |
| 아키텍처 통합 | `COMPLETE_SAFE_TERMINAL / ARCHITECTURE_V2_INTEGRATED` | Stage runtime adapter, DecisionLedgerV2 dual-write/rollback, CandidateSet/NIL, typed confidence 계약과 reader, packet 도구의 내부 통합을 닫았다. |
| 실제 효과·M2 | `ACTUAL_BLOCKED_HANDOFF / NOT_COMPLETE` | policy v3, source-backed DEV/CAL/FROZEN, 10+6 packet, fresh pair가 없어 동일 external blocker가 3회 확인됐다. |
| 실제 지표 | `null / NOT_ESTIMABLE` | 정확도·비용·지연 개선률을 주장할 actual artifact가 없다. |
| 운영 승인 | `REVIEW-LOCKED / full_scan_approval=false` | cheap routing과 전체 스캔은 열지 않는다. |
| 2026-07-14 라이브 런 | `RUNNING_DEGRADED / NO-GO` | 저장 무결성은 진행 중 정합이지만 검색 저하와 의미·비용 blocker 때문에 현재 full run 계속은 권고하지 않는다. |
| current Slang work artifact | `NO-GO / QUARANTINE` | 중앙 DB는 미변경이며 patched fresh canary 전에는 work artifact를 승격하지 않는다. |
| 동결 2,712건 targeted 개선 | `P0a GO / P0b ROLLED_BACK` | 3회 exact consensus에서 P0a systematic regression 0, P0b regression 1·신규 unsafe 1. search/router/P1/P2/full scan은 미승인이다. |
| 동결 2,712건 recovery sidecar | `DETERMINISTIC GO / REVIEW-ONLY / SEMANTIC NO-GO` | 공개 WAL·192 receipt 비간섭, proposal `68`·provenance 100%. 실제 32행 3회에서 source 반복 회귀 2행, search/router/measurement NO-GO라 자동 publish와 P1/P2는 미승인이다. |
| 동결 2,712건 남은 개선 | `INTEGRITY GO / SHADOW-AFTER / AUTO-ACTIVATION NO-GO` | router/P1 receipt `2,712/2,712`, public drift `0`; 새 grouped majority `17→18`이지만 measurement `4/6`, router recall `74.2%`, normal false-review `20.0%`, search degraded로 P2 188건은 미실행이다. |
| 2026-07-19 아키텍처 회의 | `P0 RESEARCH READY / IMPLEMENTATION NOT STARTED` | 권고안은 byte-equivalent `PublicationFinalizer`, 공통 `ObservationEnvelope`, shadow intervention simulator다. 새 Pro 답변은 recovery lock으로 미확보했고 자동 activation/full scan은 계속 NO-GO다. |
| 2026-07-20 계측 P0 | `TARGETED MEASUREMENT GO / SEMANTIC NO-GO` | HTTP vLLM hard-cap usage drain-only를 구현했다. 과거 unlinked 2행의 새 canary는 measurement `2/2 GO`, provider usage `27/27`, public drift `0`, 2,712 deterministic normal→abnormal `0`이다. 기존 32행×3회 전체 재실행·semantic/search/router/P2는 미승인이고 `full_scan_approval=false`다. |
| 2026-07-22 구조·계측 후속 | `RUNTIME 6/6 GO / MEASUREMENT 4/6 NO-GO / SEMANTIC NO-GO` | v6 192행은 runtime 실패 0·public WAL 비간섭이지만 usage link `190/192`, majority compliant `19→17`, systematic regression 2다. Synth quarantine·shape guard·repeat-stop drain은 focused 31·인접 263·실 canary·2,712 replay를 통과했으나 자동 activation과 full scan은 미승인이다. |
| 2026-09-01 grounding benchmark·community silver 연구 | `RESEARCH COMPLETE / EXTRACTOR NOT_IMPLEMENTED / PRODUCTION NO-GO` | 공개 benchmark는 component smoke로만 쓴다. 커뮤니티 목록은 `work_alias_registry`와 `community_lexicon`의 silver seed이며 gold나 중앙 DB write가 아니다. 실제 승인은 source-backed DEV/CAL/FROZEN과 문맥 gold가 필요하고, P3 headline은 계속 `null/NOT_EVALUABLE`이다. |

### 현재 계약을 읽을 때의 구분

- `confidence_percentage`: 행별 보정 확률. 전체 정확도가 아니다.
- `ARCHITECTURE_V2_INTEGRATED`: 내부 코드·rollback·비간섭·clean-export 완료. 실제 성능 승인이 아니다.
- `WAITING_EXTERNAL_INPUT`: external blocker를 처음 확인한 역사 상태다. 최신 actual lane은 `ACTUAL_BLOCKED_HANDOFF`다.
- `FULL_EXPERT_REQUIRED`/`CHEAP_RULE_ELIGIBLE`: shadow 관측 값이며 운영 라우팅 허가가 아니다.
- 실제 run은 `--parallel 16`, dashboard ON을 기본으로 하고 manifest의 requested/effective parallel을 함께 확인한다.

이 디렉터리는 개발 TODO, 기능 개선, 런 리뷰, 체크리스트, 검증 결과를 추적하는 문서 허브다. 최신 독자용 정본은 위 1~18번이며, `LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`는 P3/P4 v14 시점의 역사적 설명으로만 사용한다.

## 이전 개선 상태 — 2026-07-12 P4 선택적 비용 라우팅 그림자 v3

- 기능: 기존 공개 판정을 바꾸지 않고 각 행이 전체 전문가 경로를 요구하는지 그림자로 관측
- Golden18: `FULL_EXPERT_REQUIRED 18 / CHEAP_RULE_ELIGIBLE 0`, 공개 결과·CandidateSet `18/18` 불변
- 실제 KPI: safe auto coverage, calls/post, call avoidance, after wall time 모두 `null/NOT_ESTIMABLE`; escalation `1.0`은 shadow 경로 분포일 뿐 절감률이 아님
- 진단 로그: expert prompt `191`, VLM `14`, token `2,269,227`; canonical 행별 비용 영수증이 아니므로 KPI 승격 금지
- 합성 검증: 호출 산술 `16→8`, 50% 회피는 `SYNTHETIC_CONTRACT_ONLY_NOT_ACTUAL_SAVINGS`
- 공격 검증: `20/20`, false cheap `0`; 구현 집합 축소+재해시 공격 차단; P4 집중 `30/30`, publication `33/33`
- 현재와의 차이: typed expert call event·독립 reader·P3 actual readback 계산 기반은 이후 구현됐다. 다만 실제 artifact와 fresh paired runtime이 없어 actual cheap route는 계속 fail-close한다.
- 판정: `GO_P4_SHADOW_CONTRACT_FOUNDATION_ONLY / NOT_RUN / REVIEW-LOCKED / full_scan_approval=false / ACTIVE_NOT_COMPLETE`
- 기능 중심 한국어 보고서: `loop_reports/LOOP_P4_SELECTIVE_COMPUTE_SHADOW_20260712.md`
- 정본 실행 명세·비교: `../../out/selective_compute_shadow_harness_20260712/v3/run_spec.json`, `comparison.md`

## 이전 개선 상태 — 2026-07-11 P3 정확도 퍼센트 계약 기반 v4(역사)

- 기능: 후보 작품 ID들과 `작품 없음(NIL)`에 확률을 나누되, 근거 없는 숫자·분할 누수·저장본 위조는 숫자를 만들기 전에 차단
- Golden18: 생산 완료·분리 평가 자료가 없어 실제 headline 지표 전부 `null`, 후보 재현율 `NOT_EVALUABLE`
- 개선 전·후: 무결속 보정 숫자 claim `1→0`; 기존 공개 결과 `18/18` 불변
- 합성 검증: 공격 `20/20`, false GO `0`; 합성 4행 수치는 수식 방향 시험이며 실제 모델 성능 아님
- 회귀: 계약 `15`, 하네스 `5`, 합계 `20 tests OK`; Sol 시간차 Mapping·검색 blocker·보고서 승인 위조 3건 재공격 차단
- 현재와의 차이: 파일 바이트·producer coverage·prediction payload 재판독과 그룹 bootstrap 계산 기반은 P3 v7 이후 구현됐다. 실제 DEV/CAL/FROZEN 자료·실행·배포 구간 판정은 여전히 없다.
- 판정: `GO_P3_CONTRACT_FOUNDATION_ONLY / NOT_RUN / REVIEW-LOCKED / full_scan_approval=false / ACTIVE_NOT_COMPLETE`
- 기능 중심 한국어 보고서: `loop_reports/LOOP_P3_CALIBRATION_CONTRACT_FOUNDATION_20260711.md`
- 재결속 정본 비교: `../../out/candidate_set_calibration_shadow_harness_20260711/v4/comparison.md`

## 이전 개선 상태 — 2026-07-11 P2 최종 공개 판정 한 번만 기록 v4

- 기능: 같은 실행 범위·같은 게시글은 첫 정상 공개 판정과 결과 행을 WAL에 한 번만 확정하고 재시도는 그 정본을 재사용
- 막는 문제: 재시도 덮어쓰기, 다른 입력·설정·코드 범위 혼합, `HOLD/ERROR_HOLD` 중첩 필드의 작품명·주소 누출, 저장 중 끊긴 마지막 줄의 오인
- Golden18 저장본: 유효 판정 영수증 `0→18`, 신규 기록 `18`, 재시작 무쓰기 `18`, 공개 결과·전체 행 `18/18` 불변
- 공격 검증: 합성 `21/21`, false GO `0`; 16개 동시 기록자는 신규 commit `1`, WAL line `1`
- 검증: P2 집중 묶음 `169 tests OK`, publication `33`, recovery `36`
- 증거 분리: 저장본·합성 `GO`; 실제 runtime `NOT_RUN`; 의미 품질 `REVIEW-LOCKED`; production `full_scan_approval=false`
- 기능 중심 한국어 보고서: `loop_reports/LOOP_P2_PUBLICATION_EXACT_ONCE_20260711.md`
- 재결속 정본 비교: `../../out/publication_exact_once_harness_20260711/v4/comparison.md`

## 최신 개선 상태 — 2026-07-11 P1 상류 검색·fetch 완료 증명 v6

- 기능: 실행 전에 고정한 query/search/fetch 계획과 실제 작업 영수증을 대조해 후보 생성 앞단이 정해 둔 범위를 빠짐없이 수행했는지 증명
- `COMPLETE` 의미: 계획한 bounded 범위를 손실 없이 끝냈다는 뜻이며 웹 전체 후보를 모두 열거했다는 뜻은 아님
- 합성 결과: 사전 고정 정상 search+fetch `COMPLETE 1`, cache provenance 미결합·영수증 누락·저하/오류·조기 종료 `UNKNOWN 4`, raw `11→10` 손실 `TRUNCATED 1`, 거짓 `COMPLETE 0`
- 실제 Golden18: 새 producer receipt가 없는 과거 저장본이므로 `UNKNOWN`, 후보 재현율 `NOT_EVALUABLE`
- 공개 비간섭: 작품명·주소·판정 `18/18` 불변, 확률 전부 `null`
- fail-close: explicit completion 누락, 부분 엔진 실패, generic error/blocked/malformed, fetch fallback, posthoc direct plan, required producer 축소를 완료로 인정하지 않음
- 검증: P1 v8, completeness v6, 집중 `62/62`, 영향 범위 `529/529 tests OK`
- 실제 runtime: `NOT_RUN`; 배선 상태 `IMPLEMENTED_NOT_RUNTIME_VALIDATED`; 의미 품질 `REVIEW-LOCKED`; production `full_scan_approval=false`
- 기능 중심 보고서: `loop_reports/LOOP_P1_PRODUCER_COMPLETION_PROOF_20260711.md`
- P1 구조 정본: `../../out/candidate_set_nil_shadow_harness_20260711/v8/comparison.md`
- 완료 증명 정본: `../../out/candidate_generation_completeness_harness_20260711/v6/comparison.md`

## 이전 개선 상태 — 2026-07-11 P1 후보 생성 잘림·전문가 단계 영수증 v4

- 기능: 작품 후보 여러 개 + `NIL` 사건을 보존하고, 제목 순위 cap 6·serializer cap 24·전문가 후보 상태 cap 7곳의 잘림을 서로 다른 장부/진단 영수증으로 기록
- Golden18: post_id·후보 무결성·공개 계약 불변 `18/18 GO`
- 라벨 원장: 작품 후보 `9`, NIL `6`, 단일 정답 미지정 `3`
- 구조 검사: 작품 후보 정답의 사건 후보 내 관측 `9/9`, NIL 정답 원장 행의 공통 NIL 선택지 `6/6`; 정확도 검사가 아님
- 후보 구성: 작품 사건 `34`, 비사건 약칭 `13`, 후반 관측 표면 `6`
- 확률: 모두 `null`, `NOT_AVAILABLE_UNCALIBRATED`
- 후보 생성: 제목 고유 7개 `TRUNCATED 7→6`, serializer 고유 25개 `TRUNCATED 25→24`; cap 이하·중복 제거 cap 이하는 `UNKNOWN`, `COMPLETE` 생성 금지
- 전문가 단계: Gatekeeper1·Decoder1·Verifier2·Arbiter3 cap+1 `7/7 TRUNCATED`, 경계 오탐 `0`, 유지 출력 `9/9`; CandidateSet·확률·공개 판정에는 미합성
- 후보 목록 재현율: cap 6/24의 로컬 잘림은 보이지만 상류 producer 완전성이 미증명이라 `NOT_EVALUABLE`
- 영향 회귀: 집중 `71 tests OK`, candidate generation/P1 harness/promotion/retrieval/P0 harness/publication/serializer/Decoder/Arbiter 묶음 `518 tests OK`; broader 554의 선행 red 2는 별도 부채
- 실제 runtime: `NOT_RUN`; 의미 품질 `REVIEW-LOCKED`; production `full_scan_approval=false`
- 기능 중심 설명: `LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`
- P1 구조 정본: `../../out/candidate_set_nil_shadow_harness_20260711/v6/comparison.md`
- 잘림 탐지 정본: `../../out/candidate_generation_completeness_harness_20260711/v4/comparison.md`
- 루프 보고서: `loop_reports/LOOP_P1_CANDIDATE_GENERATION_COMPLETENESS_20260711.md`

## 최신 개선 상태 — 2026-07-11 P0 검색 미복구 공개 차단 하네스 v5

- 게이트 기능: typed `RetrievalState` 구현, 기본 no-op, live 검색 상태 배선은 `NOT_WIRED`
- 실제 저장본 정적 비교: baseline gate replay `5/5`, unsafe publish `1→0`, candidate missing `0`
- 합성 계약 시험: unsafe publish `5→0`, correct publish `2→2`; 실제 저장본 수치와 합산하지 않음
- 검색 근거: hard blocker `5→5`, `NO-GO`
- 실제 개선 후 runtime: `NOT_RUN_STATIC_PROJECTION / BLOCKED_ACTIVE_PRODUCTION_RUN`
- 정확도 퍼센트: `NOT_AVAILABLE_UNCALIBRATED`
- 결정적 회귀 시험: `275 tests OK`
- 정본 실행 명세: `../../out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/run_spec.json`
- 보고서: `loop_reports/LOOP_P0_RETRIEVAL_FAILCLOSE_HARNESS_20260711.md`
- 목표 프롬프트: `GOAL_PIPELINE_IMPROVEMENT_TESTDRIVEN_20260711.md`
- 의미 품질 `REVIEW-LOCKED`, production `full_scan_approval=false`

## 최신 상태 — 2026-07-11 Loop643 limit handoff

- 판정: `LIMIT_REACHED_HANDOFF`
- Golden18: run `20260711_062543_156139`, runtime `18/18/18/0/0`, semantic `18/18 PASS`
- search: required hard blocker `5`, terminal `4`, unreviewed `0`
- N=5/fresh375: `NOT_RUN_AFTER_GOLDEN_HARD_FAIL`
- production `full_scan_approval=false`
- 요약: `loop_reports/LOOP_643_REPORT_20260711.md`
- convergence: `loop643_convergence_state.json/.md`
- resume: `loop643_limit_reached_handoff_20260711_071812.json`

## 문서 맵

- `TODO.md`: 개발/기능개선 TODO 전체 색인
- `DEV_TODO.md`: 코드, 인프라, 테스트, 도구 중심 개발 TODO
- `FEATURE_IMPROVEMENT_TODO.md`: 검색 품질, slang DB, 대시보드 UX 같은 기능 개선 TODO
- `CHECKLIST.md`: 변경 전/중/후에 반드시 확인할 공통 체크리스트
- `OPERATION_QUALITY_CHECKLIST.md`: 대량 런 품질 승인용 GO/REVIEW/NO-GO 게이트
- `SCAN_RESULT_REVIEW_GUIDE.md`: scan result directory를 받았을 때의 리뷰 모드, 증거 등급, 실패 taxonomy, action queue 지침
- `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`: 자동 감사와 분리된 자연어 판정 품질 리뷰 루프, 라벨, packet 산출물 규격
- `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`: 수백만 건 운영을 위한 smoke/canary/risk/validation 샘플 규모 기준
- `LLM_JUDGMENT_REVIEW.md`: LLM/전문가가 결과를 직접 읽고 판단하는 정성 리뷰 프로토콜
- `EXPERT_ORCHESTRATION_LIMITATIONS.md`: 전문가 오케스트레이션, 후처리 rescue, 프롬프트 계약 한계와 개선 우선순위
- `GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`: regression-safe grounding loop의 현재 운영 계약과 완료 조건
- `GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`: Loop176 이후 아키텍처 보강을 active goal에 편입한 최신 실행 계약
- `ARCHITECTURE_PROMOTION_GATE_MIGRATION.md`: 기존 title promotion/rescue 구조와 추가 `GroundingState`/`PromotionDecision`/`can_publish_title` 구조를 Mermaid로 비교한 migration 설계
- `REGRESSION_SAFE_GROUNDING_BOUNDED_CONVERGENCE_PROTOCOL.md`: fingerprint, progress vector, 실행 예산, terminal ledger, plateau, 최종 상태 계약
- `loop643_convergence_state.json/.md`: Loop643 새 fingerprint Golden exact-once, search hard blocker, terminal consensus, limit handoff state
- `loop_reports/LOOP_643_REPORT_20260711.md`: multi-work subject conflict 구현, exact-once Golden, PLATEAU_AUDIT_ONLY 최종 보고
- `loop641_convergence_state.json/.md`: Loop640 immutable recovery와 Loop641 residual continuation의 fingerprint/progress/blocker state
- `loop641_gate_tool_independent_audit.json/.md`: merge/adjudication/search/always-on fail-open 재현과 actual artifact/hash/readback 보강, focused 86 tests 근거
- `loop_reports/LOOP_641_REPORT_20260710.md`: recovered75/residual300 실행과 deterministic merge/adjudication/search gate 도구 보고
- `LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md`: 처음 읽는 사람용 0~5장과 개발자용 기술 부록을 분리한 최신 아키텍처 보고서. 가상의 다작품·검색 실패 글이 현재와 개선 구조에서 어떻게 처리되는지 보여 주고, 개선 기능 9개를 `하는 일 / 예시 / 기대 효과` 순서로 한국어 설명
- `GOAL_PIPELINE_IMPROVEMENT_TESTDRIVEN_20260711.md`: 동일 입력의 개선 전·후 비교를 반복하는 복사·붙여넣기용 목표 프롬프트와 P0~P5 상태
- `loop_reports/LOOP_P0_RETRIEVAL_FAILCLOSE_HARNESS_20260711.md`: 실제 Loop643 저장본 정적 비교와 합성 계약 시험을 분리한 P0 v5 보고서
- `loop_reports/LOOP_P1_PRODUCER_COMPLETION_PROOF_20260711.md`: query/search/fetch 계획·영수증의 bounded 완료 증명, 합성 `1/4/1/false0`, 실제 runtime·확률·승인 경계를 한국어로 설명한 P1 v6 보고서
- `loop_reports/LOOP_P3_CALIBRATION_CONTRACT_FOUNDATION_20260711.md`: 정확도 퍼센트의 분자·분모, readiness v2, 무쓰기 actual preflight, source/replay 구조 결속, 6개 paired CI 정책 판정과 실제 자료 부재를 설명한 P3 v18 보고서
- `loop_reports/LOOP_P3_P4_DENOMINATOR_EXECUTION_ENVELOPE_20260712.md`: P3 actual policy v3 ABSTAIN 분모 hash-binding, P4 source-bound batch execution envelope·p50/p95 paired CI, reference-copy 제외와 P3 v19/P4 v20 정본을 설명한 최신 addendum
- `P3_ACTUAL_POLICY_DECISION_KO_20260712.md`: 실제 결과를 보기 전에 고정해야 할 정확도·위험·비열화 숫자의 A/B 선택안, 표본 산식, 미판정 3행 유지 근거
- `loop_reports/LOOP_P4_SELECTIVE_COMPUTE_SHADOW_20260712.md`: 선택적 비용 라우팅, parent/label lineage, 물리 호출 독립 재판독, recovered-arm witness, paired source replay, reference-copy 비실측 경계와 다음 actual runtime 조건을 설명한 P4 v19 보고서
- `LLM_IMPROVEMENT_ARCHITECTURE_REVIEW_20260710.md`: Claude 공동설계 provenance, 현재 shared gate의 단일-writer/확률·NIL/투영-런타임 한계, Loop640 partial drift 증거, 단계별 개선·검증 체크리스트
- `CODEX_KICKOFF_SURVEY_AND_LOOP.md`: Codex 세션 시작 시 현재 상태/다음 loop를 재구성하는 kickoff 절차
- `FULL_POST_JUDGE_RUNBOOK.md`: full-post judge 실행, 재시작, 산출물 계약
- `COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`: completed779 remaining queue를 subagent/model/tool fan-out으로 반복 개선하는 copy-paste goal prompt
- `loop_reports/`: loop별 실행 보고서와 gate 판정 기록
- `QUALITATIVE_REVIEW_20260426.md`: 20k run 300건 전문가 정성 리뷰 결과
- `IMPROVEMENT_REGISTER.md`: 개선안의 문제 정의, 결정, 결과, 후속 검증 기록
- `VERIFICATION_RESULTS.md`: 감사 명령, 지표, 판정, 재검증 결과 누적
- `HISTORY.md`: 날짜별 개발/운영 히스토리와 확인 결과

개별 상세 문서는 기존 위치를 유지한다. 예를 들어 검색 shard 사건은 `docs/search_reliability_review_20260426.md`, WARP 구성은 `docs/warp_sharding.md`, slang DB 작업은 `docs/slang_db_improvement_todo.md`에 상세를 둔다.

현재 active operating contract는 repository root의 `goal.md`, `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`, 그리고 최신 변경 계약인 `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`를 기준으로 한다. 아래 Loop179 설명은 2026-06-30 공통 promotion gate 도입 시점의 역사적 확정 기록이며, 현재 상태는 이 문서 맨 위의 Loop643/P0 v5 항목을 우선한다. Loop179은 Loop176 broader unittest failure cluster를 아키텍처 보강 phase로 흡수해 `src/llm_batch/promotion_gate.py`의 공통 `GroundingState`/`EvidenceRecord`/`PromotionDecision`/`GateReport`/`can_publish_title` layer를 추가했고, selected high-risk public-title publish paths를 shared gate로 배선했다. Loop179 authoritative broader unittest result는 `.venv312\Scripts\python.exe -m unittest discover --start-directory tests` 기준 `1299` tests, `0` failures, `0` errors, `OK`다. Artifacts는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_review.md/json`, Data Analytics artifact `loop179_promotion_gate_architecture_data_analytics_artifact.json`, report `docs/devs/loop_reports/LOOP_179_REPORT_20260630.md`다. 이것은 architecture-phase unittest gate 통과이며 semantic/full-scan approval이 아니다. Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal completion `NOT_COMPLETE`를 유지한다.

2026-07-01 최신 focused runtime/code-test patch는 Loop236이다. Loop236은 Loop235가 노출한 URL-title mismatch를 `url_title_verified_official_detail` publish precondition으로 좁혔다. 원 canary `20260701_212908_967986`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`였지만 wrong public title `두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)` / URL `https://novelpia.com/novel/427233` publish 가능성을 드러냈다. 새 가드의 resync preview는 같은 산출물을 `promotion_blocked`로 내렸고, patched canary `20260701_214126_569050`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, public title `전 버튜버가 하고 싶은데요`, URL `https://novelpia.com/novel/275975`, `candidate_ledger_status=safe_resolved`다. Report는 `docs/devs/loop_reports/LOOP_236_REPORT_20260701.md`, review는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_review.md/json`, Data Analytics artifact는 `loop236_url_title_direct_support_guard_data_analytics_artifact.json`이다. Residual accounting은 `NO_DELTA_TARGETED_URL_TITLE_DIRECT_SUPPORT_GUARD`이며 active goal은 계속 `NOT_COMPLETE`다.

2026-07-01 최신 source/native review는 Loop232다. Loop232는 Loop231 이후 focus 5건을 review-only로 분해했고 `11661876`/`11663540`은 다음 architecture patch 후보, `11695637`은 old `도네하지 마라` 복구 금지/retarget open, `11660237`은 targeted/parent variance, `11706832`은 Loop145 caveat 재개방으로 기록했다. Report는 `docs/devs/loop_reports/LOOP_232_REPORT_20260701.md`, review는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_review.md/json`, Data Analytics artifact는 `loop232_loop231_safe_loss_variance_data_analytics_artifact.json`이다. Residual accounting은 `NO_DELTA_SOURCE_NATIVE_VARIANCE_REVIEW_ONLY`이며 active goal은 계속 `NOT_COMPLETE`다.

2026-07-01 최신 parent replay report는 Loop231이다. Loop231은 Loop230 title-led serializer/gate 복구를 38-row parent/representative packet에서 재검증했고 runtime은 `GO`, completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, MCP health `36/36`이다. `11660257`은 `암흑가 보스요? 제가요?`로 parent survival을 확인했지만, Loop225 대비 public title count가 `12->11`로 줄고 safe loss `11661876`, `11663540`, `11695637`이 생겨 parent semantic result는 `NO-GO / MIXED_MOVEMENT`다. Report는 `docs/devs/loop_reports/LOOP_231_REPORT_20260701.md`, review는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop231_parent_replay_after_loop230_title_led_serializer_gate_review.md/json`, Data Analytics artifact는 `loop231_parent_replay_after_loop230_title_led_serializer_gate_data_analytics_artifact.json`이다. Residual accounting은 `NO_DELTA_PARENT_REPLAY_AFTER_LOOP230_MIXED_MOVEMENT`이며 active goal은 계속 `NOT_COMPLETE`다.

## 운영 원칙

- 기능 변경, 검색/런 품질 개선, slang DB 규칙 변경 시 `DEV_TODO.md` 또는 `FEATURE_IMPROVEMENT_TODO.md`와 관련 상세 문서를 함께 갱신한다.
- 대량 런 후에는 `HISTORY.md`에 run id, 핵심 지표, 문제, 조치, 재검증 결과를 남긴다.
- 4~20건 테스트는 `SMOKE ONLY`로만 기록한다. 품질 승인에는 100% 자동 감사와 10,000건 이상 validation 샘플 또는 그에 준하는 대형 표본이 필요하다.
- 기능/품질 개선은 구현 후 자동 테스트 런, run audit, 개선 전후 비교 문서, 필요 시 LLM 리뷰 패킷까지 한 묶음으로 남긴다.
- 완료 처리 전에는 `CHECKLIST.md`와 `OPERATION_QUALITY_CHECKLIST.md`의 관련 항목을 확인하고, 확인한 명령/결과를 `VERIFICATION_RESULTS.md`에 적는다.
- scan result directory를 리뷰할 때는 `SCAN_RESULT_REVIEW_GUIDE.md`의 `GUIDE_MODE`/`RUN_REVIEW_MODE`/`MIXED_MODE`, 증거 등급, action queue를 먼저 적용한다.
- `result_scan`, `run_audit`, count summary는 run integrity 증거로만 취급하고, 대량 판정 품질 승인은 `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md` 기준 semantic review 산출물까지 있어야 한다.
- 통계 감사만으로 판단할 수 없는 케이스는 `LLM_JUDGMENT_REVIEW.md` 절차에 따라 정성 리뷰 패킷을 만든다.
- 전문가 판단과 최종 JSON이 충돌하는 케이스는 `EXPERT_ORCHESTRATION_LIMITATIONS.md`의 후처리 rescue/프롬프트 한계 기준으로 검토한다.
- targeted canary에서 final JSON이 회복됐더라도 중간 후처리 guard가 title을 흔들거나 삭제한 로그가 있으면 별도 회귀 seed와 action queue로 남긴다.
- 단건 post fix 후에는 바로 다음 단건으로 넘어가지 않는다. parent lane/representative mini-lane, recent controls, golden controls, affected tests, collateral movement를 확인한 뒤 residual accounting을 줄인다.
- 역할/호칭성 alias, memory-query/no-anchor, generic bridge처럼 후단 rescue가 오삽입을 만들 수 있는 패턴은 targeted canary 통과 후에도 high-risk bucket에서 재검증한다.
- 큰 개선은 `IMPROVEMENT_REGISTER.md`에 먼저 등록하고 상태를 `proposed -> in_progress -> verified` 순서로 이동한다.
- 문서에는 추측과 확인 결과를 분리해서 쓴다. 확인한 숫자에는 run id와 생성 파일 경로를 붙인다.
- 신규/갱신 보고서, loop report, review Markdown, Data Analytics reader-facing 산출물은 한국어로 작성한다. 간략하게 쓰되 의미, 근거, 산출물 경로, 게이트 상태는 생략하지 않는다.

## 상태 규격

- `proposed`: 문제와 방향만 정리됨
- `in_progress`: 코드/설정/문서 변경 진행 중
- `implemented`: 변경은 반영됐지만 충분한 검증 전
- `verified`: 명령 또는 재런으로 개선 확인
- `deferred`: 지금은 보류
- `rejected`: 검토 후 채택하지 않음

## 품질 판정 규격

- `GO`: shard 100% 정상, run audit 정합성 통과, slang 오염 0, 필요한 정성 리뷰 완료, semantic decision quality 승인, 문서/검증 결과 갱신 완료
- `REVIEW`: 운영은 가능하지만 검색 저하율 상승, 실제 약칭 후보 미검토, pending/flush 차이, LLM/전문가 정성 리뷰 필요
- `NO-GO`: bad shard 존재, `/readyz` 실패, SearchXNG UI 실패, fatal traceback 증가, slang DB 오염 발생

## 변경 기록 템플릿

```markdown
## YYYY-MM-DD - 짧은 제목

- 상태: proposed | in_progress | implemented | verified | deferred | rejected
- 관련 run id:
- 관련 파일:
- 문제:
- 조치:
- 확인:
- 남은 위험:
- 다음 작업:
```
