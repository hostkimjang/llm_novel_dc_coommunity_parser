# 일반 분석 이후의 제한된 native 복구

> 현재 상태는 [현재 상태 문서](CURRENT_STATUS_KO.md)를 따른다. 날짜별 기록과 `out/`·`logs/` 링크는 로컬 보존 자료이며 Git checkout에 포함되지 않을 수 있다.

<!-- r5-resolution-current:start -->

## 현재 상태 안내 — 2026-10-15

현재80 범위 개발·검증과 Goal 완료 상태는 [현재 상태와 남은 작업](CURRENT_STATUS_KO.md)에서 관리한다. 전체 의미 `REVIEW`·기존5개 실패·독립 평가/R7 보류·새 분기 실측 미관측을 함께 확인한다. 아래 날짜별 실행·시험·미완료 표기는 당시 이력이다.

<!-- r5-resolution-current:end -->

## 2026-10-14 실제 JSONL 입력 호환성

일반 JSONL에서는 게시물의 `comments` 필드가 생략되고 댓글이 별도 행에 있을 수 있다. 복구 입력 판독도 필드가 **없는 경우에만** `comments_raw` 목록 또는 빈 내장 목록을 사용한다. 별도 댓글의 원시행·부모·ID·순서·빈 문자열과 SHA는 보존한다. 명시적인 null·숫자·문자열 등의 비목록 값과 `JSON_ARRAY_V1`의 기존 계약은 그대로 거절한다.

승인80 원문은 게시물80·댓글193·원시행273이며 일반 main loader와 투영이 일치했다. source 고정 후 native batch·입력 호환2파일56개 시험을 통과했다. 첫 실제 ON 실행의 입력 오류는 보존했고, 수정 후 실제 ON 실행·종료 판독 상태는 [현재 연구 기록](../../out/research_completion_20261014_v1/REPORT_KO.md)을 따른다. 로컬 통과를 실제 복구 성공률로 해석하지 않는다. 아래 기록은 당시 이력이다.

## 2026-10-10 최신 진행: 전체 진입점과 완료 표시

80건 검토 자료 준비를 유지하면서 일반 `expert_main` 전체 진입점의 합성 입력 OFF·재생 ON·최초 분석 ON을 검증했다. 최초 ON은 provider1회·native7회를 거쳐 원래 HOLD와 별도 결과를 보존했다. 대시보드의 완료 상태·부분집합·실패·저장 대기와 이력 건수 표시를 수리했다.

관련 Python 3파일은 **71 passed, 40 subtests passed in 10.17s**, **Node 84개 통과·실패 0개·skip 0개**다. 일반 CLI 검증과 이후 UI/API 변경의 시험 범위를 분리한다. [현재 검증·남은 개발](EXPERT_ENTRY_COMPLETION_REVIEW_20261010_KO.md)을 따른다. 아래 수치와 당시 미완료 설명은 이전 단계 기록이다.

후속으로 semantic NIL/CAL→actual readback·baseline 연결을 구현하고 합성 로컬 검증을 마쳤다. **271 passed, 9 subtests passed in 167.12s (0:02:47)**이며 [R4 연결 검증](R4_ACTUAL_BRIDGE_20261010_KO.md)에 범위와 한계를 기록했다. 적격 실제 자료의 전체 성공 경로, 실제80·새 브라우저·사람 판정·실자료 품질·R5 실측은 미완료다. Goal active·formal KPI NOT_ESTIMABLE·R7 보류를 유지한다.

## 이전 검증: 기존 회귀 수리와 80건 검토 준비

기존 rework 실패 33개는 이름 변경 대응표와 실제 JUnit을 대조해 모두 통과했다. 마지막 3개 파일 실행은 **494 passed, 55 subtests passed in 181.10s (0:03:01)**다. 앞선 9개 파일 실행의 **5 failed, 578 passed, 64 subtests passed in 572.95s (0:09:32)**에서 시험 의존 파일 누락 4건과 최종 후보 단계의 기대 불일치 1건을 확인하고 보완했다. 제품 소스는 두 실행 사이에 그대로이며, 앞선 나머지 6개 파일의 통과를 따로 보존한다. 서로 다른 실행 수치를 합산하지 않으며 전체 저장소 회귀나 전체 CLI 검증 완료로 해석하지 않는다. [현재 수리 기록](LEGACY_REWORK_REPAIR_20261010_KO.md)과 [최종 실행 검산](../../out/development_plan_20261010/r6_rework_phase4_reconciled.json)을 따른다.

원형 본문에 결속된 별칭은 비권한 후보로 보존하고, 일반 화자 발화는 명시적인 작성자 복귀 전까지 보류한다. URL·시각 예외, OCR 작가 검색, 추천 보류와 최종 설명 봉인을 검증했다. 후보 제목·URL 보존과 최종 공개 title/URL을 따로 확인하며, 검색 후보만으로 공개 권한을 만들지 않는다.

[80건 검토 자료](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)는 원문·저장 관측 112개와 참조를 연결했고 [독립 재판독](../../out/development_plan_20261010/r6_rework_actual80_preparation_readback_v1_KO.md)에서 원문·참조 52개 파일의 존재와 SHA 일치를 확인했다. 사람 정답 0건·학습 준비 0건·전 행 개발 노출·권한 UNKNOWN이며 후보 누락 3행, 미검토 이미지 25개는 남아 있다.

현재 상태는 **REWORK_LOCAL_VERIFIED_ACTUAL_PENDING**이다. 아래 자동 복구 수치와 33개 실패·NOT_PASS 표기는 이전 단계 이력이다. 실제80 모델 실행·새 브라우저는 자동 승인 검토의 `blocked by policy` 거절 이후 재시도하지 않았다. 실제 품질·사람 판정·적격 분할 자료·R5 실측·formal KPI는 미완료이며 formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다.

현재 상태는 **AUTOMATIC_NATIVE_LOCAL_VERIFIED_ACTUAL_AND_LEGACY_REWORK_PENDING**이다. 합성 HTTP 응답을 사용하는 실제 전문가·guard·AST로 추출한 main 함수 본문·원장·API·Node 표시를 검증했다. 전체 CLI 기동·실제 브라우저·실자료 품질 검증은 별도로 남아 있다.

## 실행 순서와 보존 대상

`--native-recovery ON`은 입력 순서의 처음 N행에만 같은 호출의 최종화 직전 문맥을 보관한다. 기본값 OFF는 정책 파일과 native 실행 모듈을 읽지 않는다. worker가 반환한 비공개 carrier는 해당 행과 함께 이동하며 다른 worker의 마지막 문맥을 가져오지 않는다. 원장 재생 행에는 새 문맥을 만들지 않는다.

main은 원래 결과의 공개 guard, publication commit, 실제 원장 재판독, AUDIT_ONLY 제안 기록을 먼저 끝낸다. 전체 결과와 최종 manifest를 저장한 뒤에만 복구를 직렬 실행한다. 지원 대상은 현재 구현에서 원문과 결속된 단일 direct OCR 제안, HOLD 공개 판정, REVIEW_REQUIRED 검토 영수증을 모두 갖춘 행이다. 일반 HOLD 전체를 자동으로 검색하거나 과거 JSON을 native 문맥으로 복원하지 않는다.

provider가 추가 증거를 저장하면 전용 pipeline에서 Decoder·Verifier·Synthesizer·Arbiter와 기존 공개 guard를 실행한다. 결과는 별도 publication scope와 원장에 저장한다. 원래 결과·manifest·원장은 고치지 않는다. `PUBLISH`가 나와도 원래 결과에 자동 적용하지 않으며 `public_apply`, `publication_authority`, `central_db_write`는 계속 false다.

이미지 원문의 `content_blocks` 또는 구조형 `content`는 main이 저장하는 텍스트·블록·이미지 URL 목록으로 검산한다. 원문 bytes를 바꾸지 않으며 서로 충돌하는 두 alias, 모호한 블록, 변경된 이미지 출처는 거절한다. 기존 문자열 `content`의 정확 비교 경로도 유지한다.

검토 라우터의 새 `strict_evidence_v2`는 최종 HOLD에 남은 적격 direct OCR 제안을 기존 추출기로 확인한다. 제목을 담지 않는 제안 수·catalog/제안 지문을 검토 source view에 결속하며, 과거 중간 플래그가 없어도 근거가 남은 보류 건을 `REVIEW_REQUIRED`로 분류한다. 억제·배경 목록·비적격 OCR는 이 경로로 추가하지 않는다. 복수 제목은 검토 대상이 될 수 있지만 자동 batch는 계속 단일 제안만 허용한다. 기존 `strict_evidence_v1` 영수증은 기존 규칙과 지문으로 판독하며 새 규칙으로 재해석하지 않는다. 이 변경은 공개 제목이나 guard를 고치지 않는다. 수리 영향 시험과 기존 v1 판독·변조 거부를 로컬 검증했다.

## 명시 정책과 실행 조건

옵션은 `--native-recovery ON`, `--native-recovery-policy <정책 JSON 경로>`, `--native-recovery-policy-sha256 <파일 SHA-256>`다. 대응 환경변수는 `EXPERT_NATIVE_RECOVERY`, `EXPERT_NATIVE_RECOVERY_POLICY`, `EXPERT_NATIVE_RECOVERY_POLICY_SHA256`다. CLI가 우선하며 정책은 strict JSON과 raw bytes 지문을 함께 검산한다.

대시보드 ON, `RECOVERY_ACTIVATION_MODE=AUDIT_ONLY`, Slang DB OFF가 필요하다. mutable batch/session learning과 active learning queue는 동결한다. 별도 recovery-only 명령, source-only early route, paired/FRESH 측정 실행과 동시에 켤 수 없다. 현재 프로젝트의 사용자 승인 검증 조건은 병렬 1·저부하 프로필이다.

정책 schema는 `recovery_native_batch_policy_v1`이며 다음 필드를 모두 명시한다.

| 필드 | 의미 |
|---|---|
| `max_capture_rows` | worker 시작 전에 정하는 처음 N행. 최대 64행이며 빈자리를 다음 행으로 바꾸지 않음 |
| `max_batch_calls` | provider와 native의 행별 최대 호출 수를 합산한 batch 예약 한도 |
| `max_batch_elapsed_ms` | 복구 drain의 경과 시간 및 행별 최대 시간 예약 한도 |
| `max_batch_response_bytes` | 두 실행기의 최대 누적 응답량을 합산한 예약 한도 |
| `provider_policy`, `native_policy` | 호출·시간·요청 timeout·단일/누적 응답량의 기존 transport 5개 필드 |
| `provider_endpoint` | 추가 증거 검색 endpoint. native MCP_SEARCH와 같아야 함 |
| `native_config` | endpoint와 모델의 실제 wire 설정 전체 |

provider 호출 한도는 1이며 native 호출 한도는 최대 128이다. 예약은 영속 저장 후 발송하고 실패하더라도 환불하지 않는다. 예산 0, 취소, 입력/원장 변경, 지원하지 않는 제안, capture 부재는 미실행 또는 불완전 사유로 남긴다. 문맥 직렬화의 8 MiB 상한을 실제 메모리 사용량으로 해석하지 않는다.

`native_config`에는 `endpoints`, `model`, `max_tokens`, `temperature`, `top_p`, `server_type`, `min_p`, `repeat_penalty`, `enable_thinking`, `temperature_by_tag`, `vllm_top_k`, `vllm_presence_penalty`를 모두 기록한다. vLLM 설정은 wire에서 `repetition_penalty`, `top_k`, `presence_penalty`로 반영되며 다른 backend에는 vLLM 두 설정을 null로 둔다. 모델의 기본값이나 실행 중 환경을 암묵적으로 다시 읽지 않는다.

## 결과와 대시보드

원래 결과가 `result.json`이면 실행 자료는 `result_native_recovery/`, 화면 집계는 `result_recovery_native_view.json`에 저장한다. 전체 입력 행을 유지하며 capture 제외·재생·미실행·불완전·native 완료를 구분한다. 같은 scope의 복구 batch는 출력 폴더나 정책만 바꿔 다시 시작할 수 없다.

provider의 `GUARD_NOT_EVALUATED`와 native의 별도 `PUBLISH|HOLD`를 구분해 표시한다. native 수령증이 없는 불완전 실행은 provider의 알려진 호출 수만으로 전체 호출량을 표시하지 않는다. 전체 미확정 호출 수는 null이며 원격 서버의 실제 dispatch와 가격도 확인되지 않은 값이다.

GET 판독은 `FILE_AND_BASE_BINDING_ONLY` 범위다. 저장 파일, typed 행, 원래/별도 scope, 지문을 확인하며 키를 읽거나 실행기·원장 수리를 호출하지 않는다. 실시간 진행 이벤트는 기본 post/token 카운터와 별개이고, 완료 이벤트와 재접속 snapshot에 복구 상태를 보존한다. 정적 화면·API 회귀는 실제 브라우저 검증을 대신하지 않는다.

`batch_report_ref`로 최종 batch 상태·사유·예약 예산을 보존한다. 행의 guard가 정상 완료됐어도 마지막 제어 검사에서 취소·시간 초과가 확인되면 batch는 `INCOMPLETE`다. 관측 시간은 마지막 drain 제어 검사까지이며 보고서 발행 I/O는 제외한다. 보호 원본·키·anchor 검산 실패는 새 집계 발행을 중단한다.

원장에서 재사용한 행의 과거 owner run ID 때문에 일반 manifest가 `MISMATCH`인 경우 그 판정은 유지한다. 복구 화면은 `recovery_native_export_manifest`와 native 집계의 현재 export 결속을 따로 검산해 표시한다. 과거 행을 새 실행에서 분석한 것처럼 바꾸지 않는다.

## 검증 상태

- [x] 기본 HTTP 분석의 OCR→HOLD→실제 main commit/AUDIT→복구→별도 guard·원장·집계를 연결해 검증했다.
- [x] OFF·재생·복수 worker·예산/중단·원본 변경·불완전 호출 수를 묶어 검증했다.
- [x] live/history API 응답을 Node 표시 시험에 그대로 전달해 확인했다.
- [x] 독립 검토에서 발견한 재생 행의 실행 ID 표시와 최종 원본/제어 실패 보존을 수정하고 정적으로 재검토했다. 실행 검증도 위 묶음 시험에서 확인했다.
- [ ] 실제 브라우저와 승인된 80건의 최종 코드 실행·의미 품질·비용 검증을 완료한다.

실제 80건은 [준비 자료 검토 안내](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)에 있다. 현재 사람 정답과 적격 TRAIN/CAL/FROZEN 자료는 없으며 이 자동 연결이 그 선행 조건을 해결하지 않는다. 기존 rework 33개 실패도 별도 미해결이다. 실제 모델과 Chrome 실행의 자동 승인 차단은 재시도하지 않았다. 품질은 미평가, formal KPI는 NOT_ESTIMABLE이며 Goal은 active다.

관련 구현 계약은 [batch 메모](../../out/development_plan_20261010/r6_auto_batch_notes_KO.md), [wire 설정 메모](../../out/development_plan_20261010/r6_auto_runtime_notes_KO.md), [화면 메모](../../out/development_plan_20261010/r6_auto_dashboard_notes_KO.md)를 따른다. 최초 묶음의 485개 통과·44개 실패·하위 시험 18개와 Node 69개 통과·1개 실패·2개 skip은 [실패 분석](../../out/development_plan_20261010/r6_auto_initial_analysis_KO.md)에 보존했다. 수리 후 7파일은 127개 통과·1개 실패이며 Node 70개 통과·2개 skip이다. [2차 결과와 남은 수리](../../out/development_plan_20261010/r6_auto_repair_analysis_KO.md)에 실제 OCR 분석의 HOLD가 `NO_REVIEW`로 분류되는 결함과 원시 근거를 기록했다. 그 뒤 최종 OCR 근거를 검토 대상으로 연결하고 타입 검산과 시험 저장 순서를 수리했다. 실행별 결과는 아래와 같으며 합산하지 않는다.

| 실행 | Python 원시 결과 | Node |
|---|---|---|
| initial | 44 failed, 485 passed, 18 subtests passed in 344.17s (0:05:44) | 69 통과·1 실패·2 skip |
| repair | 1 failed, 127 passed in 1833.74s (0:30:33) | 70 통과·0 실패·2 skip |
| router | 2 failed, 324 passed, 87 subtests passed in 558.90s (0:09:18) | 70 통과·0 실패·2 skip |
| final | 210 passed, 87 subtests passed in 327.16s (0:05:27) | 70 통과·0 실패·2 skip |

최초 실패 기록은 그대로 보존하며 각 실패의 후속 통과는 [재조정 수령증](../../out/development_plan_20261010/r6_auto_reconciled_receipt.json)에 연결했다. 마지막 수리 뒤 최초 전체 파일을 모두 다시 실행한 결과는 아니다. Node skip 2개는 별도 자료가 필요한 이전 일반 입력 추론·provider 연결 시험이며 새 native API 연결 시험은 통과했다. 이번 단계 시작 전 `.gitignore`와 `tests/test_monitor_event_bus.py`의 raw 백업은 확보하지 못했다. 두 파일은 신규 추가로 분류하지 않고 현재 검증 지문과 백업 누락 한계를 전달 수령증에 남긴다.
