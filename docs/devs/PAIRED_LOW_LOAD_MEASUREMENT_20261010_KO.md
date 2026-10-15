# 저부하 paired 계측 개발 기록

> 현재 상태는 [현재 상태 문서](CURRENT_STATUS_KO.md)를 따른다. 날짜별 기록과 `out/`·`logs/` 링크는 로컬 보존 자료이며 Git checkout에 포함되지 않을 수 있다.

<!-- r5-resolution-current:start -->

## 현재 상태 안내 — 2026-10-15

현재80 범위 개발·검증과 Goal 완료 상태는 [현재 상태와 남은 작업](CURRENT_STATUS_KO.md)에서 관리한다. 전체 의미 `REVIEW`·기존5개 실패·독립 평가/R7 보류·새 분기 실측 미관측을 함께 확인한다. 아래 날짜별 실행·시험·미완료 표기는 당시 이력이다.

<!-- r5-resolution-current:end -->

<!-- paired-low-load-current:start -->

## 2026-10-14 현재: 잔여 수리 754 PASS·source454 적용·R5 실패 유지

**R5 실제 완료 상태는 바뀌지 않았다.** 완료 reference24와 [BEFORE exit1·FAILED/DRAINED](../../out/r5_actual24_pair_after_failure_repair_001/end_observation_001/receipt.json), AFTER 미시작을 보존한다. fresh reference와 arm의 후보/결정 차이를 기존 strict 동일 WAL 계약이 거절했다. guard 완화·참조 재봉인·실행 반복으로 paired 성공을 만들지 않으며 formal KPI는 **NOT_ESTIMABLE**다. 같은 release/config/input/source/WAL·QPC 계약과 과거 병렬1 본문은 유지한다.

별도 잔여 기능은 [29전체파일754 PASS·하위22 PASS](../../out/r5_attempt_failure_validation_v1/run_final44_65_ui_history_v4_001/receipt.json) 후 [19파일 정확 적용](../../out/source_final_application_v1/application_001/receipt.json)했다. 제품6·시험9·fixture4, 신규14·기존5백업·gitignore 예외9·index 보존이며 현재 **source454**다. [적용 보고서](../../out/source_final_application_v1/application_001/REPORT_KO.md)에 구현·적용 범위를 기록했다. [적용 후 검사](../../out/source_final_application_v1/application_001/post_apply_check.json)도 통과했다. 44 화자/부정, [65 관계 후보의 후단 보존과 반증](../../out/source65_candidate_preservation_review_v4/REPORT_KO.md), 사건 카드/exporter와 캐시 이력 탐색이 범위다. [Node94 PASS·기존 선택3 SKIP](../../out/source_context_event_state_ui_validation_v2/node_001/receipt.json)와 중간566/610/100을 합산하거나 paired 개선량으로 사용하지 않는다.

[현재 디스크 release](../../out/source_final_application_v1/application_001/source_binding.json)는 `19de4b231ece83ec9c780f722433cdda501be12d7a450232eefc2a919e52df6d`이며 모델 runtime 측정은 없다. [적용 후 실제 화면 확인](../../out/source_final_ui_validation_v1/receipt.json)에서 dashboard18868의 최근80·24 이력과 80건 상세, 과거44 카드 표시를 확인했다. 목록75·전체 탐색 상한 안내는 유지되고 과거 결과를 재계산하지 않았다. 콘솔 오류·경고 관측0이며 모델 재시도가 아니다. [과거 source440 actual12 ready](../../out/source_remaining12_launch_prep_v1/launch_plan.ready.json)는 역사 준비물로 보존하고 현재 실행 명세로 쓰지 않는다.

[12건 시작 명령은 자동 승인 검토의 `blocked by policy`로 거절](../../out/source_remaining12_launch_prep_v1/rejected_attempt_001.json)됐고 세부 이유는 제공되지 않았다. **실제12 미시작**, 기존 사용자 승인 유지·재승인 요청·우회·재시도 없음이다. 요청 parallel12·dashboard ON·저부하 원칙을 유지하지만 새 실행의 실제 parallel/run/scope 관측은 없다. 이 12건 계획은 R5 reference/BEFORE/AFTER가 아니다.

[이전80 A39/H33/R8/I0](../../out/p4_quality_followup_20261013/actual80_current_followup_parallel12_v1/final_review_80_v1/REPORT_KO.md)은 의미 REVIEW다. HUMAN_GOLD0·권리UNKNOWN·training ready0·독립 holdout0, 49진단2·69진단10 미완료를 보존한다. Goal blocked·R2–R6 실제 수용 미완료·R7 보류·formal KPI NOT_ESTIMABLE이다. 새로운 완벽 재생·전체80 자동 재실행 gate를 추가하지 않는다. [v33 원형](../../out/p4_quality_followup_20261013/docs_integration_update_v33_followup_v1/REPORT_KO.md)과 CURRENT 밖 기록을 보존하며 [v34 보고서](../../out/p4_quality_followup_20261013/docs_integration_update_v34/REPORT_KO.md)에 근거를 결속한다.

2026-10-14 같은 미해결 실행 차단과 자료 조건을 세 목표 턴 연속 확인해 Goal을 blocked로 전환했다. 추가로 진행할 확정 로컬 수리는 확인되지 않았다. 사용자 승인은 유지하며, [재개 조건과 보존 근거](../../out/goal_blocked_20261014_v1/HANDOFF_KO.md)를 따른다. 구현·로컬 시험·저장 화면 확인과 실제 모델·연구 평가의 미완료를 구분한다.

<!-- paired-low-load-current:end -->

2026-10-10. **LOCAL_CONTRACTS_VERIFIED_ACTUAL_PAIRED_MEASUREMENT_PENDING**. 승인 계획 R5의 저부하 비교 정책, 실행 관측, RunSpec v3 판독과 계획 생성, 대시보드 표시를 구현했다. 최종 통합 회귀와 독립 반례 검증을 통과했다. 실제 BEFORE/AFTER 모델 실행·비용·품질 평가는 미실행이다. 당시 P4 새80 실행은 자동 승인 검토로 차단돼 있었다. 후속 재승인 실행과 현재 관측 상태는 [P4 운영 인계](P4_REAPPROVAL_RUN_20261010_KO.md)를 따른다. 그 단일80 실행을 R5의 적격 BEFORE/AFTER paired 실측으로 바꾸지 않는다.

## 실행 계약

| 구분 | 기존 v1/v2 | 새 v3 |
|---|---|---|
| 요청 병렬도 | 16 | 1 |
| 검색 health | 정상16 이상, 실패0 | 고정 pool을 직렬 검사, 정상1 이상·실패0·search 포함 |
| 정책 결속 | 기존 shared binding | 별도 policy 파일의 raw SHA·self SHA·유효 설정 SHA |
| 자원 | 기존 계약 유지 | Windows BelowNormal16384·affinity2·CPU1·수치 스레드5종=1 |
| 관측 | 기존 관측 | 실행 및 행 START/END, 같은 PID·시도·시간 순서·정책·원장 결속 |
| 가변 문맥 | 기존 계약 유지 | FROZEN_OFF·batch context OFF·중앙 Slang 쓰기 OFF |

`low-load-validation` 프로필 이름만으로 통과하지 않는다. `expert_main`이 실제 설정과 코드·prompt·generation 지문을 다시 읽으며 정책 파일 변경도 검사한다. 실제 worker의 모델·endpoint·generation 설정을 소비한다. START/END 중 자원이나 설정이 달라지거나 health가 오래되면 적격 관측을 만들지 않는다. 중간의 연속 자원 유지와 원격 서버 내부 모델 가중치 불변까지 증명하는 기능은 아니다.

이번 실행 경로는 **Slang OFF만 지원**한다. 순수 policy/reader 계약에는 READ_ONLY 지문 형식이 남아 있으나 main과 plan 생성기는 READ_ONLY 실행을 거절한다. R2 후보 회수·R3 지식·R4 재정렬도 모두 OFF로 고정한다. 기존 BEFORE/AFTER의 source-only 처리 비교를 계측하는 범위이며 일반적인 학습 모델 A/B 기능으로 확장하지 않는다.

## 원본 참조와 새 실행의 구분

완료된 원본 manifest와 authoritative WAL은 `REFERENCE_WAL_ONLY_NOT_A_MEASURED_ARM`이다. 원본은 입력 바이트·순서·전체 공개 WAL, 모델·endpoint·VLM/OCR·이미지 검토·대시보드와 공개 설정·환경·release·Slang 상태를 결속한다. v3 원본도 병렬1·검색 health 조건을 충족해야 한다.

원본에 새 v3 arm의 REQUIRED 장부·FROZEN_OFF·START/END를 요구하면, 원본이 있어야 만들 수 있는 RunSpec을 원본 실행 전에 요구하는 순환이 생긴다. 이를 피하기 위해 원본 참조에는 새 arm 관측을 요구하지 않는다. 대신 실제 BEFORE와 AFTER에는 정책 projection과 START/END, claim PID, 행 attempt·입력 좌표·실행 시간 구간, dispatch/terminal/seal/link와 provider 사용량을 모두 검산한다. 과거 원본의 비용·자원·health를 새 실행의 실측으로 승격하지 않는다. [초기 준비 계약](../../out/development_plan_20261010/r5_implementation_contract_KO.md)은 당시 설계 기록이며 이 원본 역할 구분이 후속 확정 사항이다.

## 코드와 준비 순서

| 파일 | 책임 |
|---|---|
| `src/llm_batch/measurement/paired_execution_policy.py` | strict 정책·설정 projection·자원/health 관측과 검산, 로컬 정책 파일 exclusive 생성 |
| `src/llm_batch/runtime/paired_execution.py` | 실행과 행의 START/END 수명, 고유 attempt, 정책·설정 변화 거절 |
| `expert_main.py` | provider 전 정책·대시보드·endpoint 검사와 실제 worker/장부/저장 연결 |
| `tools/run_paired_measurement_readback.py` | RunSpec 고정과 두 arm 사후 판독 |
| `tools/build_low_load_paired_plan.py` | 고정 v3를 재생해 새 out 폴더에 계획 JSON만 생성 |
| `tools/run_independent_plan.py` | 새 batch/envelope v2의 실행 전 결속·fresh output·종료 관측 검산 |

1. 완료된 원본 manifest·WAL과 입력을 고정한다. 실제 모델·prompt·설정·source 지문과 고정 endpoint pool을 명시해 `execution_config_projection`, `build_low_load_policy`, `write_execution_policy` API로 정책 파일을 생성한다. 예시 SHA나 합성 fixture를 실제 정책 자료로 사용하지 않는다. 정확한 인자와 필드는 [정책 API](../../out/development_plan_20261010/r5_policy_api_KO.md)를 따른다.
2. `tools/run_paired_measurement_readback.py --freeze-run-spec <새 RunSpec 경로> --input <입력> --source-manifest <원본 manifest> --pair-id <고유 pair> --run-spec-schema paired-pipeline-measurement-runspec-v3 --execution-policy <정책 파일>`로 명시적으로 v3를 만든다. CLI 기본값 v1은 유지한다.
3. `tools/build_low_load_paired_plan.py --run-spec <RunSpec> --source-manifest <원본 manifest> --input <입력> --python <인터프리터> --output-root <repo/out 아래 새 폴더> --mcp-endpoint <고정 endpoint>`로 계획만 만든다. 추가 환경은 `--environment-json`으로 명시하며 비밀값·고정 정책 override는 거절한다. 이 도구는 모델·health·서버·child를 실행하지 않는다.
4. 실제 실행이 가능해진 뒤 기존 independent runner 경로로 수행하고 두 manifest를 `--run-spec`, `--before-manifest`, `--after-manifest`, `--output-json`, `--output-md` 인자로 판독한다. 현재는 실제 실행을 시작하지 않았다.

생성 명령은 `--reuse-shards-only --parallel 1 --execution-profile low-load-validation --decision-call-ledger REQUIRED`를 포함한다. 자동 shard 관리와 endpoint failover를 끄며 실행 중에도 실제 client의 failover 값을 확인한다. health 시각은 직렬 검사 시작 기준이므로 긴 검사의 오래된 결과를 종료 시각으로 바꿔 신선하게 보이게 하지 않는다.

대시보드는 실제 `/api/health` 응답을 확인한다. 내장 서버는 자기 PID와 서비스 식별값이 맞아야 하며, standalone 포워딩은 빈 ingest 배치로 인증 경로도 확인한다. 서버 스레드 시작 요청만으로 준비 완료로 처리하지 않는다. 일반 실행의 기존 동작은 유지한다.

## 저장과 화면

manifest와 행 `run_meta`에 `paired_execution_runtime_fields`, `paired_execution_observation`을 저장한다. 두 키는 공개 판정의 stable payload 계산에서 제외해 관측 때문에 공개 WAL 판정이 달라지지 않도록 한다. 실패한 행이나 끝나지 않은 실행에는 END를 만들어 넣지 않는다. 원래 관측이 없는 복구 결과는 v3 적격 실측으로 인정하지 않는다.

화면은 행 관측과 실행 종료 관측을 따로 보여 준다. PID·우선순위·CPU·수치 스레드·search health·시도 ID를 표시하고, 종료 누락은 `관측 미완료`로 남긴다. `시작·종료 관측 저장`은 정책 검산 PASS가 아니다. 세부 지문은 원본 JSON에서도 확인할 수 있다.

`REFERENCE_COPY_COST_ONLY`는 원본을 복사한 경로의 비용 범주이며 production 절감률에 합산하지 않는다. provider 사용량 미기록이나 추정치는 실제 비용으로 바꾸지 않는다. 가격 자료·동일 품질 기준·실제 두 arm이 없으므로 금액·품질 개선과 formal KPI는 `NOT_ESTIMABLE`이다.

## 검증 근거와 남은 게이트

전달 점검에서 P1/P3 선별 회귀시험17개가 미추적 상태로 Git 제외 규칙에 걸려 있음을 확인해 명시 예외를 추가했다. R5 신규 시험5개와 계획 생성기1개의 예외도 포함했다. 시험 내용은 바꾸지 않았고 stage·commit은 수행하지 않았다. [전달 점검 수령증](../../out/development_plan_20261010/r5_test_delivery_fix_receipt.json)을 참조한다.

현재 개별 policy83개, reader40개＋하위63개, runtime34개 시험이 통과했다. runner 최초54개＋하위2개 PASS 뒤 main 연결 시험에서 reuse-only 누락과 잘못된 ACK 타입을 찾아 수리했다. 최초 실패 로그와 수령증은 보존한다. 검증은 **Python51파일·1147개 시험·210개 하위 시험과 Node26개 PASS, reader 행 결속 보강 후 영향9파일·269개 시험·97개 하위 시험 PASS**이며 각 시험 중 외부 socket0·소스 변경0이다. 전수 회귀 뒤 v3 reader의 행간 시간 중첩·attempt 재사용 거절을 보강했으므로 전수와 영향 범위 후속 시험을 구분하며 수치를 합산하지 않는다. UI 변경은 없어 Node·브라우저 증거를 재사용한다. main/runner/plan 후속88개＋하위2개, 독립 main 반례18개가 통과했다. pytest 임시 디렉터리 정리 경고는 원본 로그에 보존한다. [통합 시험 수령증](../../out/development_plan_20261010/r5_final_validation_receipt.json), [reader 보강 후속 수령증](../../out/development_plan_20261010/r5_reader_followup_validation_receipt.json), [독립 검토](../../out/development_plan_20261010/r5_runtime_independent_final_review_KO.md)를 참조한다.

[브라우저 수령증](../../out/development_plan_20261010/r5_browser_receipt.json)은 합성 설정·health와 실제 로컬 자원으로 live·완료 history·종료 누락 history를 확인한 기록이다. 실제 모델·검색 요청은 0회이며 콘솔 오류·경고0, viewport1280에서 문서 너비1270이다. 시험 서버와 탭은 종료했다. 첫 fixture의 scope SHA 형식 오류는 실패 출력으로 보존하고 새 v2 폴더에서 수리했다.

실제 최종80·의미 검토, 적격 원본과 실제 BEFORE/AFTER 계측, 비용·품질 평가를 완료하기 전에는 전체 목표를 완료로 바꾸지 않는다. R2/R3 실제 자료 평가, R4 learned backend·학습/평가, R6 구현과 R7 보류 상태는 별도 개발 기록을 따른다.
