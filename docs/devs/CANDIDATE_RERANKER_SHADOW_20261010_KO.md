# 고정 후보 재정렬과 학습 자료 분리 운영 기록

## 2026-10-10 현재 화면 검증: 의미 관측 6화면

Goal은 `get_goal` 확인 기준 active로 재개됐고 실제80은 진행 중이다. 기존 합성 저장 의미 관측 3사례의 live/history 6화면을 현재 IAB에서 확인했다. 정상 관측·미실행·capture 실패, API=저장값, 콘솔 오류·경고0을 확인한 [수령증](../../out/development_plan_20261010/p4_reapproval_v1/semantics_browser_v1/receipt.json)을 따른다. 새 producer 실행·의미 모델 소비 성공·실자료 품질·전체 UI 검증으로 확대하지 않는다. P3 저장 진단·설정 2화면과 41개 기술 검사도 [별도 근거](../../out/development_plan_20261010/p4_reapproval_v1/p3_browser_v1/REPORT_KO.md)로 보존한다. 아래 미실행·차단 설명은 각 단계 당시 기록이다.

후속으로 [일반 추론 2화면](../../out/development_plan_20261010/p4_reapproval_v1/inference_browser_v1/REPORT_KO.md), [native 복구 2화면](../../out/development_plan_20261010/p4_reapproval_v1/native_browser_v1/REPORT_KO.md), [R5 complete/partial 4화면](../../out/development_plan_20261010/p4_reapproval_v1/r5_browser_v1/REPORT_KO.md), [독립 provider 2화면](../../out/development_plan_20261010/p4_reapproval_v1/provider_browser_v1/REPORT_KO.md)을 확인해 현재 합성 저장자료 18화면을 기록했다. 일반 추론·native는 저장 API payload 표시이며 provider는 row/bound와 합성 표시 manifest를 이용했다. 새 producer·원래 생산 API/원장 결속을 재검증한 것이 아니다. R5 partial의 END는 null·미완료이고 실제 paired 비용/품질은 미평가다. 의미 모델 소비 성공·실자료 품질·전체 UI·실제80 종료 및 최종 결과 화면은 별도다. [통합 검산](../../out/development_plan_20261010/p4_reapproval_v1/browser_round_v1/REPORT_KO.md)은 source417·fixture48 보존과 소유 preview 7개 종료를 확인했다. 강제 종료 코드1·연결 해제 trace는 제품/실제80 오류와 구분한다.

## 2026-10-10 최신 진행: 전체 진입점과 완료 표시

80건 검토 자료 준비를 유지하면서 일반 `expert_main` 전체 진입점의 합성 입력 OFF·재생 ON·최초 분석 ON을 검증했다. 최초 ON은 provider1회·native7회를 거쳐 원래 HOLD와 별도 결과를 보존했다. 대시보드의 완료 상태·부분집합·실패·저장 대기와 이력 건수 표시를 수리했다.

관련 Python 3파일은 **71 passed, 40 subtests passed in 10.17s**, **Node 84개 통과·실패 0개·skip 0개**다. 일반 CLI 검증과 이후 UI/API 변경의 시험 범위를 분리한다. [현재 검증·남은 개발](EXPERT_ENTRY_COMPLETION_REVIEW_20261010_KO.md)을 따른다. 아래 수치와 당시 미완료 설명은 이전 단계 기록이다.

후속으로 semantic NIL/CAL→actual readback·baseline 연결을 구현하고 합성 로컬 검증을 마쳤다. **271 passed, 9 subtests passed in 167.12s (0:02:47)**이며 [R4 연결 검증](R4_ACTUAL_BRIDGE_20261010_KO.md)에 범위와 한계를 기록했다. 적격 실제 자료의 전체 성공 경로, 실제80·새 브라우저·사람 판정·실자료 품질·R5 실측은 미완료다. Goal active·formal KPI NOT_ESTIMABLE·R7 보류를 유지한다.

## 이전 검증: 기존 회귀 수리와 80건 검토 준비

기존 rework 실패 33개는 이름 변경 대응표와 실제 JUnit을 대조해 모두 통과했다. 마지막 3개 파일 실행은 **494 passed, 55 subtests passed in 181.10s (0:03:01)**다. 앞선 9개 파일 실행의 **5 failed, 578 passed, 64 subtests passed in 572.95s (0:09:32)**에서 시험 의존 파일 누락 4건과 최종 후보 단계의 기대 불일치 1건을 확인하고 보완했다. 제품 소스는 두 실행 사이에 그대로이며, 앞선 나머지 6개 파일의 통과를 따로 보존한다. 서로 다른 실행 수치를 합산하지 않으며 전체 저장소 회귀나 전체 CLI 검증 완료로 해석하지 않는다. [현재 수리 기록](LEGACY_REWORK_REPAIR_20261010_KO.md)과 [최종 실행 검산](../../out/development_plan_20261010/r6_rework_phase4_reconciled.json)을 따른다.

원형 본문에 결속된 별칭은 비권한 후보로 보존하고, 일반 화자 발화는 명시적인 작성자 복귀 전까지 보류한다. URL·시각 예외, OCR 작가 검색, 추천 보류와 최종 설명 봉인을 검증했다. 후보 제목·URL 보존과 최종 공개 title/URL을 따로 확인하며, 검색 후보만으로 공개 권한을 만들지 않는다.

[80건 검토 자료](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)는 원문·저장 관측 112개와 참조를 연결했고 [독립 재판독](../../out/development_plan_20261010/r6_rework_actual80_preparation_readback_v1_KO.md)에서 원문·참조 52개 파일의 존재와 SHA 일치를 확인했다. 사람 정답 0건·학습 준비 0건·전 행 개발 노출·권한 UNKNOWN이며 후보 누락 3행, 미검토 이미지 25개는 남아 있다.

현재 상태는 **REWORK_LOCAL_VERIFIED_ACTUAL_PENDING**이다. 아래 자동 복구 수치와 33개 실패·NOT_PASS 표기는 이전 단계 이력이다. 실제80 모델 실행·새 브라우저는 자동 승인 검토의 `blocked by policy` 거절 이후 재시도하지 않았다. 실제 품질·사람 판정·적격 분할 자료·R5 실측·formal KPI는 미완료이며 formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다.

## 이전 자동 연결 단계: 일반 main 자동 복구의 로컬 검증 (2026-10-10)

일반 `expert_main`의 같은 호출 문맥을 원래 guard·commit·AUDIT·최종 저장 이후 제한된 복구로 연결하고, 별도 결과를 대시보드 live/history API와 표시까지 로컬 검증했다. 기본값은 OFF이며 ON에는 고정 정책·예산과 대시보드가 필요하다. 원래 결과·manifest·WAL은 보존하며 공개 적용·권한·중앙 DB 쓰기는 false다.

현재 상태는 **AUTOMATIC_NATIVE_LOCAL_VERIFIED_ACTUAL_AND_LEGACY_REWORK_PENDING**이다. [운영 계약](NATIVE_RECOVERY_AUTOMATION_20261010_KO.md)과 [실행별 검증·수리 기록](../../out/development_plan_20261010/r6_auto_reconciled_receipt.json)을 따른다. 검증은 합성 HTTP 응답으로 실제 전문가·guard·AST로 추출한 실제 main 함수 본문·원장·API·Node 표시를 통과한 범위다. 전체 CLI 기동과 실제 브라우저 통과를 뜻하지 않는다. 실행별 시험 수는 합산하지 않으며 마지막 수리 뒤 최초 전체 파일을 모두 다시 실행한 결과도 아니다.

최종 HOLD의 OCR 근거 누락은 새 `strict_evidence_v2` 검토 규칙으로 수리했고 기존 v1 영수증 판독은 보존했다. 실제80 모델 실행·새 브라우저·사람 정답·적격 실제 TRAIN/CAL/FROZEN 품질·R5 실측과 기존 rework 33개 실패는 남아 있다. 전체 회귀는 NOT_PASS, formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다. 아래 단계별 수치와 미완료 설명은 당시 이력이며 현재 범위는 이 절을 따른다.

## 이전 단계: 명시 native 복구 연결과 당시 남은 자동화

R6의 **명시 same-call native 복구 연결을 합성 응답·HTTP mock으로 로컬 검증했다**. 현재 검증 상태는 `PASS_NATIVE_EXISTING_REWORK_FAILURES_PENDING`이며 기존 rework 시험 실패는 미해결이다. `run_native_recovery`는 같은 분석 호출에서 보존한 pre-final 문맥을 원래 입력·저장 provider 근거에 결속하고, 실제 Decoder·Verifier·Synthesizer·Arbiter와 기존 native 공개 guard를 호출한다. 원래 결과·manifest·WAL을 덮어쓰지 않고 별도 scope의 새 publication WAL과 결과를 저장·재판독한다. guard 판정 기록은 공개 반영이 아니며 `public_apply`, `publication_authority`, `central_db_write`는 false다.

native 추가 LLM·검색·fetch는 하나의 영속 호출·byte·시간 예산을 공유하며 먼저 예약하고 전송한다. 완료 job만 저장 결과를 0회 호출로 재생하고, 미완료·불확실 요청은 재시작 후 재발송하지 않는다. upstream provider 수집은 별도 앞 단계로 합계에 표시하며, MCP 내부 원격 검색 횟수·취소·가격은 확정하지 않는다. 과거 actual80/32 저장 JSON을 살아 있는 native 문맥으로 복원하는 기능은 없다.

최초 Python 16개 파일의 원시 결과는 시험 893개 통과·32개 실패와 하위 시험 21개 통과다 (`32 failed, 893 passed, 21 subtests passed in 1228.60s (0:20:28)`, [최초 전체 수령증](../../out/development_plan_20261010/r6_native_final_receipt.json)). 합성 응답 fixture만 보정한 뒤 workflow 1개 파일의 시험 7개가 통과하고 실패는 1개, 하위 시험은 0개다 (`1 failed, 7 passed in 657.84s (0:10:57)`, [보정 후 수령증](../../out/development_plan_20261010/r6_native_repair_receipt.json)). 그 뒤 실제 fetch 응답의 identity 캐시를 복제하는 제품 코드를 수리하고 context·workflow 2개 파일을 재검증해 시험 67개와 하위 시험 0개가 통과했고 실패는 0개다 (`67 passed in 701.00s (0:11:41)`, [캐시 수리 후 수령증](../../out/development_plan_20261010/r6_native_capture_final_receipt.json)). **세 실행의 시험은 겹치므로 합산하지 않는다. 마지막 수리 뒤 전체 16파일을 다시 실행한 결과도 아니다.** [재조정 수령증](../../out/development_plan_20261010/r6_native_reconciled_receipt.json)은 새 native 경로의 실패가 수리됐음을 기록하며 최초 전체 실행을 PASS로 바꾸지 않는다.

기존 rework 시험은 전체 실행에서 31개가 실패했다. 동일한 빈 캐시·단일 파일 격리 조건의 이전 baseline과 현재 소스에서는 각각 33개 실패가 재현됐고, 33개의 예외 종류·정규화 메시지가 같았다. 비교상 남은 차이는 0개지만 시험 상태는 `FAILED`다 ([격리 비교 근거](../../out/development_plan_20261010/r6_native_isolated_rework_comparison_v1.json)). **실패 33건은 해결되지 않았으며 전체 회귀 통과나 모든 OFF 동작의 동등성을 뜻하지 않는다.** [API·검증 범위](../../out/development_plan_20261010/r6_native_api_KO.md), [현재 코드·캐시 수리 독립 검토](../../out/development_plan_20261010/r6_native_capture_cache_review.json)와 [I/O 독립 검토](../../out/development_plan_20261010/r6_native_io_closure_review.json)를 따른다. [fixture 수정 독립 검토](../../out/development_plan_20261010/r6_native_fixture_repair_review.json)는 앞선 수리 이력으로 보존한다. 이번에는 Node·브라우저 시험을 실행하지 않았다. 화면 소스는 이전 provider 단계의 [Node 66개 통과 기록](../../out/development_plan_20261010/r6_provider_node_receipt.json)과 같으며, 그 기록은 새 native 화면이나 브라우저 통과 증거가 아니다. 이전 probe 실패와 simulation/provider 시험도 별도 이력으로 보존한다.

[80건 검토 큐](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)는 그대로 보존했다. 입력 80행·저장 관측 112개·중복 게시물 32개이며, 사람 정답과 학습 준비는 모두 0건이다. 기존 WORK/NIL 참조를 사람 정답으로 승격하거나 새 독립 분모로 세지 않았다.

**일반 main의 자동 복구 스케줄과 native 결과의 대시보드 live/history 연결은 아직 미완료다.** 실제 외부 모델·검색 호출은 0회이며 실제 복구 품질·비용·formal KPI는 `NOT_ESTIMABLE`이다. P4 실제80 실행과 새 Chrome 검증은 기존 자동정책 차단을 재시도하지 않았다. 실제 자료·사람 판정·R4 학습/교정 품질·R5 실측도 남아 있다. R6 전체 완료로 처리하지 않으며 Goal은 active, R7은 보류다.

## 이전 단계: provider 근거 수집과 80건 검토 준비 (2026-10-10)

당시 R6 상태는 **PROVIDER_EVIDENCE_LOCAL_VERIFIED_NATIVE_GUARD_AND_ACTUAL_RECOVERY_PENDING**였다. 원본 HOLD·AUDIT에 결속한 명시 계획 → 영속 예약 → 단일 HTTP → 원시 응답 저장·독립 판독 → `expert_main`·대시보드 연결을 구현했다. 완료된 요청은 0회 전송으로 재생하고, 완료 여부가 불명확한 요청은 재발송하지 않는다. 최초 fresh source 검사부터 응답 저장·재판독까지 같은 시간 제한을 적용한다. 마지막 `REQUEST_FINALIZED` 자체의 저장은 이 시간 범위에서 제외한다. 저장 성공은 `PROVIDER_EVIDENCE_STORED`, 공개 guard는 `GUARD_NOT_EVALUATED`이며 일반 실행의 자동 복구는 아직 연결하지 않았다.

이전 provider 단계의 변경 영향 Python 23파일 `779 passed, 163 subtests passed in 654.67s (0:10:54)`, Node 66개 PASS다. 실제 파일 원장과 HTTP mock, 저장 결과의 API·Node 표시를 확인했다. 실제 외부 모델·검색 호출과 새 브라우저 검증은 0회다. [실행 계약·한계](../../out/development_plan_20261010/r6_provider_api_KO.md), [Python 검증](../../out/development_plan_20261010/r6_provider_final_receipt.json), [Node 검증](../../out/development_plan_20261010/r6_provider_node_receipt.json)을 따른다. 아래 이전 단계의 수치는 당시 증거이며 이번 수치와 합산하지 않는다.

[80건 검토 큐](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)를 준비했다. 원래 입력 순서 80행에 112관측·관측별 후보 기록 121개를 연결했고 중복 게시물 32개를 별도 표본으로 세지 않았다. WORK 2·NIL 6은 기존 모델 참조, UNJUDGED는 72건이다. 사람 정답·학습 준비는 모두 0건이며 전 행이 개발에 노출됐다. 후보 결손 3행과 미검토 이미지 21행을 검토 순서에 반영했지만 정답·역할·사용 권리를 채우지 않았다. [검산 수령증](../../out/development_plan_20261010/actual80_review_queue_v1/verification_receipt.json)에 원본 46개·이전 준비 파일 5개의 보존 근거를 남겼다.

당시 남은 범위는 P4 실제80·새 브라우저, 실제 corpus·사람 판정·TRAIN/CAL/FROZEN 품질, R5 실측, R6 native 공개 guard·자동 복구·실제 품질이었다. 현재 native 연결과 미완료 범위는 위 최신 기록을 따른다. 당시 R6 후속 계획은 [native guard 개발 메모](../../out/development_plan_20261010/r6_native_guard_next_steps_KO.md)를 따른다. 기존 자동 승인 차단을 재시도하지 않았으며 formal KPI는 `NOT_ESTIMABLE`, Goal은 active, R7은 보류다.

2026-10-10. R4 상태는 **GENERAL_INFERENCE_LOCAL_VERIFIED_BROWSER_AND_ACTUAL_DATA_PENDING**다. 일반 입력의 실제 R2 원문·후보 ID·작품/판본·출처 bytes를 고정 semantic NIL 모델 및 CAL 온도에 연결하고 expert_main 저장·API·대시보드 표시를 구현했다. 현재 원문·R2·모델 점수를 재생 검산하며, FROZEN 배정이나 정답을 만들지 않는다. 이번 로컬 회귀는 Python 38파일 `1440 passed, 42 subtests passed in 229.37s (0:03:49)`, Node 58개 PASS다. 실제 pipeline에서 저장한 live/history 자료를 Node 표시 시험으로 연결했다. 실제80 준비 묶음은 112관측/80고유행을 원문과 연결했으나 사람 정답0·학습 준비0이며 전 행이 개발 노출 자료다. 실제 TRAIN/CAL/FROZEN 품질, 새80 모델 실행, 새 화면의 브라우저 검증과 R6 실제 provider 복구는 남았다. 실제 모델 API·검색·source-backed 학습은 0회다. 실제80·Chrome의 자동 승인 검토가 blocked by policy로 차단한 실행은 재시도하지 않았다. formal KPI는 NOT_ESTIMABLE, Goal은 active다.

[승인 계획](EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md), [착수 전 읽기 조사](../../out/development_plan_20261010/r4_implementation_contract_KO.md)와 [최신 통합 기록](EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md)을 함께 따른다. 앱 Goal은 active이며 미완료된 실제 모델·자료 작업을 완료로 바꾸지 않는다.

## 초기 v1 구현과 당시 검증

| 범위 | 구현·검증한 내용 | 남은 조건 |
|---|---|---|
| 고정 후보 scorer | local manifest SHA, strict backend 허용 목록, finite score·동점 정렬·동일 ID 집합·크기·호출 격리 | 실제 모델/가중치·권리·학습 이력·자원 계약 |
| 실행 연결 | R2 조회 직후 expert 실행 전 원문·후보 고정, 한 번 score, OFF 무동작, 기존 모델·검색·공개 결과 비개입 | 실제 backend 연결과 별도 검증 |
| 저장·화면 | private receipt→행별 저장→live/history, 실패·미실행·부분 후보·미교정 구분 | 실제 실행 자료의 의미·품질 검토 |
| 학습 split | TRAIN/DEV/CALIBRATION/FROZEN_HOLDOUT의 선언된 positive/negative 노출·ID·역할·원문/provenance byte 검사 | 적격 실제 자료, 독립 판정과 노출 완전성 확인 |
| 기존 하네스 | 현재 모듈 지문 경로와 새 합성 graph, 원본 자료 변조 거절·기존 assertion 보존 | 과거 Golden18의 정상 재생을 복구한 것은 아님 |
| 학습·교정·평가 | 이번 구현에서 실행하지 않음 | 실제 optimizer·CAL fit·고정 모델 FROZEN 평가·사전 지표 정책 |

초기 v1 통합 회귀는 **Python 44개 파일의 시험 916개와 하위 시험 139개, Node 시험 25개 PASS**다. 이전 R3의 37파일·726개·하위132개·화면24개는 당시 기록이며 합산하지 않는다. 모델 호출·외부 socket 시도·시험 중 소스 변경은 모두0이었다. 경고1개는 기존 Windows 임시 폴더 정리의 WinError145이며 시험 실패는0이다. 이를 이유로 공용 Temp를 별도 삭제하지 않았다.

## 사용 설정

기본값은 OFF다. OFF에서는 scorer adapter를 불러오거나 manifest를 읽거나 score하지 않는다. SHADOW에는 명시적인 R2 `--candidate-retrieval SHADOW`가 필요하다. 설정 우선순위는 CLI→환경변수→기본값이며 실행 정책과 설정 출처를 기록한다.

| CLI | 환경변수 | 조건 |
|---|---|---|
| `--candidate-reranker OFF|SHADOW` | `EXPERT_CANDIDATE_RERANKER` | 기본 OFF |
| `--reranker-manifest` | `EXPERT_RERANKER_MANIFEST` | SHADOW에서 명시 local JSON 필요 |
| `--reranker-manifest-sha256` | `EXPERT_RERANKER_MANIFEST_SHA256` | 사전 고정 lowercase SHA-256 필요 |

이미 승인된 입력·실행에 붙이는 옵션 예시는 다음과 같다. 이 문서의 예시가 새 모델 실행 승인이나 실제 실행 이력을 뜻하지 않는다.

```text
--candidate-retrieval SHADOW
--candidate-corpus <고정-corpus.json>
--candidate-corpus-sha256 <corpus-byte-sha256>
--candidate-reranker SHADOW
--reranker-manifest <합성-scorer-manifest.json>
--reranker-manifest-sha256 <manifest-byte-sha256>
```

manifest schema는 `candidate_reranker_manifest_v1`이다. `backend=SYNTHETIC_FIXED_SCORES_V1`, `data_kind=SYNTHETIC_FIXTURE`, `feature_schema=candidate_reranker_features_v1`과 ID별 고정 score를 명시한다. 없는 후보 점수를0으로 만들거나 모델을 자동 다운로드하지 않는다. URL·UNC·원격 드라이브, dynamic import/pickle/실행 코드, 미구현 backend와 추가 weight 필드를 거절한다. 실제 학습 모델을 이 합성 schema에 넣어 실제 모델처럼 표시하면 안 된다. 상세 schema는 [adapter API](../../out/development_plan_20261010/r4_reranker_api_KO.md)에 있다.

`expert_main`은 scorer를 한 번 준비해 worker에 불변 객체로 공유한다. 로드 실패도 명시 unavailable scorer로 남기며 다른 모델로 대체하지 않는다. 현재 저부하 검증은 BelowNormal16384·단일 CPU mask2·numeric thread5종=1을 실제 프로세스에서 관측했다. 새 실제 검증런에는 대시보드를 연결하며 low-load 설정 자체를 paired 계측 적격성으로 간주하지 않는다.

## 원문·후보·점수 경계

pipeline 진입점에서 원래 title/body/comments와 raw_path를 캡처하고 R2 receipt의 query/post/corpus/scorer/config와 알려진 observation SHA를 검산한다. 그 뒤 expert 실행 전 `candidate_reranker_frozen_view_v1`을 만든다. final official title/URL, reference/gold/adjudication, baseline_selected를 query feature로 받지 않는다. 후보의 제목·URL은 고정된 선택 전 관측값이다.

현재 runtime namespace는 CORPUS_CANDIDATE이며 candidate_id는 R2의 corpus_candidate_id 그대로다. 제목 문자열로 CandidateOption의 cand_*를 만들지 않는다. 명시 대응이 없으므로 candidate_option_bridge_status=MISSING, candidate_set_fingerprint=null을 남긴다. 별도 CANDIDATE_OPTION 입력은 기존 CandidateOption 생성자의 canonical title/URL ID 결속을 검사한다. 전체 CandidateSet producer를 재생했다는 뜻은 아니다.

R2가 반환하는 점수는 유한한 양수여야 한다. positive_candidates와 반환/생략 counts를 대조하며 top_k 등으로 일부 후보가 빠졌으면 TRUNCATED로 남기고 재정렬하지 않는다. UNKNOWN·빈 후보·조회 오류·모델 불가를 NIL로 바꾸지 않는다. 점수 성공에서도 후보 추가/삭제가 없고 유한한 숫자만 허용하며 boolean은 거절한다. 점수 내림차순, 동점 ID 오름차순으로 정렬한다. runtime은 자체 SHA뿐 아니라 점수 타입·순위·frozen ID 순서·역할 관측·digest scope도 재검산한다.

역할은 PRIMARY/PREVIOUS/MENTIONED/COMPARISON/UNKNOWN을 원문별 raw_path·span·span SHA 관측으로 보존한다. 서로 다른 언급을 전역 역할 하나로 합치지 않는다. 실제 span 근거가 없는 R2 후보는 빈 역할 배열을 유지한다. 관측은 human gold나 역할 정답이 아니다.

상한은 manifest256KiB·score row256개, frozen view96KiB·후보20개, 원문12,000자·fragment128개, 후보별 역할32개·전체128개다. 입력 한도는 backend 호출 전에 검사하며 조용히 자르지 않는다. adapter receipt는48KiB, 저장 binding을 포함한 runtime receipt는64KiB다.

## 저장·공개 결과·대시보드

private `_candidate_reranker_shadow`는 `run_meta.candidate_reranker_shadow`로 저장하고 정책은 `candidate_reranker_policy`에 기록한다. 모든 receipt의 publication_authority/public_apply/central_db_write는 false다. 기존 모델·검색 호출, expert 문맥, 제목/URL 공개, 중앙 Slang DB·candidate ledger에 점수나 후보를 적용하지 않는다. publication의 stable payload와 decision config도 이 관측으로 바꾸지 않는다.

확률은 NOT_AVAILABLE_UNCALIBRATED, nil_probability와 selected_candidate_id는 null이다. 정상 합성 결과 상태는 SCORED_SYNTHETIC이며 actual_model_available=false다. receipt SHA는 latency_ms·자기 지문·storage binding을 제외한 canonical 본문으로 계산한다. 저장 시 scorer/manifest/feature/config·post와 기존 binding을 확인하고 run_id/input_index(1-based)/post_id/attempt_id/publication_scope_id를 현재 행에 묶는다. 다른 행·attempt·설정·SHA나 크기 한도 위반은 NOT_AVAILABLE로 보존한다.

source-only 조기 경로는 이전 receipt를 지우고 새 PIPELINE_NOT_EXECUTED를 기록한다. 재사용 output의 stale private 값도 제거한다. query·scorer 오류는 기존 분석에 전파하지 않는다. R2의 진짜 지문 없는 예외와, 제공된 알려진 정책·SHA가 모순인 경우를 구분해 기록한다.

화면은 저장된 producer 필드만 보여준다. 합성v3의 live/history에서 SCORED_SYNTHETIC, NOT_SCORED_GENERATION_TRUNCATED와 빈 순위, 미교정 확률을 구분했고 콘솔 경고·오류0을 확인했다. publication scope 미기록은 PARTIAL로 남았다. 큰 receipt는 목록/SSE로 보내지 않으며 과거 미저장 값을 추론하지 않는다. 확인용 서버의 실제 PID35684와 wrapper PID82804는 종료했고18769 포트가 열려 있지 않음을 확인했다. [live 화면](../../out/development_plan_20261010/r4_browser_final_live.png), [history 점수](../../out/development_plan_20261010/r4_browser_final_history_scored.png), [history 부분 후보](../../out/development_plan_20261010/r4_browser_final_history_partial.png)를 참고한다.

## 학습 split과 기존 calibration 연결

새 `reranker_training_split_v1`은 기존 calibration enum에 TRAIN을 몰래 추가하지 않는다. 선언된 positive뿐 아니라 negative의 source/content/lineage, candidate/corpus/work, edition·media, alias-family가 서로 다른 split을 넘는지 검사한다. 같은 corpus ID가 같은 split의 여러 행에서 알려진 다른 candidate/work/edition/media에 UNIQUE로 연결되는 모순도 INVALID다. MISSING/AMBIGUOUS/UNKNOWN·UNJUDGED를 임의 정답이나 NIL로 승격하지 않는다.

source span의 byte slice·text·SHA, label/role provenance의 scope·artifact SHA와 제공된 exact bytes를 대조한다. 같은 후보의 서로 다른 역할 언급은 보존한다. 알려진 모순은 INVALID, 자료 누락은 NOT_READY다. VALID는 **제공된 byte와 선언의 구조·결속이 맞다**는 뜻이다. 권리·작품·역할 판정의 진실성이나 선언된 학습 노출 목록의 완전성을 독립 입증하지 않는다. exposure_completeness=DECLARED_NOT_INDEPENDENTLY_VERIFIED를 유지한다.

기존 calibration bridge는 TRAIN을 제외한 assignment 원형과 외부 expected manifest SHA를 기존 validator로 검산한다. bridge가 없으면 ready_for_calibration_bridge=false다. bound라는 사실도 실제 CAL 학습이나 fit의 실행 증거가 아니다. [split API](../../out/development_plan_20261010/r4_split_api_KO.md)에 schema·한도·분모를 기록했다.

## 하네스·보존·검증 근거

기존 네 도구의 구형 구현 지문 경로11개를 실제 grounding/ledger 경로로 바로잡았다. 새 합성18행 graph는 현재 단계 builder와 기본 validator로 P0→P1→producer→P2, P1→readiness, P3를 재생한다. 과거 라벨·원본 ledger/RunSpec SHA를 덮지 않았다. 기존23개 publication/calibration 시험의 assertion 호출98개를 보존한 정적 독립 검토가 PASS다. 원본 ledger byte 불일치는 예상 거절로 남으며 과거 Golden18 정상 재생을 복구했다고 주장하지 않는다. 합성 graph도 실제 준비도 NO_GO와 확률null·runtime NOT_RUN을 유지한다.

| 근거 | 확인 범위 |
|---|---|
| [통합 수령증](../../out/development_plan_20261010/r4_validation_receipt.json) · [Python 로그](../../out/development_plan_20261010/r4_validation_tests.log) · [Node 로그](../../out/development_plan_20261010/r4_validation_node.log) | 44파일916개＋하위139개·Node25개 PASS, PID86872의 시작/종료 저부하 관측·소스 변경0·외부 socket0 |
| [adapter 후속 독립 검토](../../out/development_plan_20261010/r4_reranker_independent_final_review_receipt.json) | R2 양수·canonical ID·오류형 및 고정 후보 점수 계약 PASS |
| [runtime 후속 독립 검토](../../out/development_plan_20261010/r4_runtime_independent_final_review_receipt.json) | 실제 process·저장·OFF·실패 비간섭8개 묶음 PASS |
| [split 후속 독립 검토](../../out/development_plan_20261010/r4_split_independent_final_review_receipt.json) | 후속11개 검산과 전역 corpus UNIQUE 충돌 거절 PASS |
| [하네스 독립 검토](../../out/development_plan_20261010/r4_harness_independent_review_receipt.json) | 기본 검산·원본 거절·기존 assertion98개 보존, 정적 검토 PASS |
| [브라우저 수령증](../../out/development_plan_20261010/r4_browser_receipt.json) | 합성v3 live/history·TRUNCATED·빈 순위·콘솔0 |

초기 발견과 FAIL/PARTIAL 이력은 후속 PASS로 덮어쓰지 않았다. 원본 byte는 [root 백업](../../out/development_plan_20261010/r4_backup/root_files_receipt.json)과 각 담당자의 후속 백업에 있다. 원래233b worktree, 기존80/32 결과·연구 benchmark6개·중앙 Slang DB와 staged 상태의 최종 관측은 [보존 수령증](../../out/development_plan_20261010/r4_preservation_receipt.json)을 따른다. [전달 수령증](../../out/development_plan_20261010/R4_DELIVERY_RECEIPT.json)은 구현·검증·한계를 함께 모은다.

`/tests/*`에 가려진 R1~R4 신규 회귀시험12개와 `tests/candidate_shadow_graph_fixture.py`에 `.gitignore` 예외13개를 추가했다. 파일 포함 문제의 수리이며 stage·commit 완료를 뜻하지 않는다. out 검증자료는 기존 정책대로 로컬 근거다.

## 남은 작업

초기 학습 단계에서는 baseline·optimizer·원시 점수 평가기를 구현했다. 다음 문장은 당시 남은 범위이며, 이후 관계 관측과 의미 특징 소비 구현은 아래 후속 기록을 따른다. 적격 실제 자료의 권리·훈련 이력을 고정한 TRAIN/CAL/FROZEN 실행, PRIMARY/PREVIOUS/COMPARISON 관계 관측, 실제 자료의 NIL 학습·확률 교정과 품질 수용 판정은 남았다. 기존 calibration helper나 지정 temperature만으로 실제 학습·교정을 완료했다고 기록하지 않는다. 사전 지표 정책과 적격 정답·역할 자료가 없으므로 실제 MRR·NIL·risk·품질 개선은 NOT_ESTIMABLE이다.

P4 실제80 실행은 자동 승인 검토가 두 차례 차단한 뒤 재시도하지 않았다. R2/R3 실제 corpus·참조와 품질 평가도 남았다. [R5 운영 기록](PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md)의 저부하 v3와 [R6 운영 기록](BOUNDED_RECOVERY_EXECUTION_20261010_KO.md)의 합성 main 진입점·웹 연결은 구현됐다. R5 실측과 R6 전체 provider·실제 복구 품질은 미완료이며 R7 보류·Goal active를 유지한다.

## 학습 baseline v2 사용과 한계

기존 v1 고정 점수 fixture는 유지한다. v2 manifest는 `candidate_reranker_manifest_v2`, `PAIRWISE_LINEAR_V1`, 자료 종류, feature schema와 전체 모델 JSON을 담는다. 모델은 11개 원문·후보 어휘/역할 특징의 학습 가중치와 Unicode 정규화 계약·학습 config·원문/노출/provenance 지문을 검산한다. ID·정답·최종 선택·판정용 역할 라벨은 점수 특징이 아니다. `actual_model_available=true`는 학습 파라미터의 존재이며 `SYNTHETIC_FIXTURE`를 실제 자료로 바꾸지 않는다. 대시보드도 이 뜻으로 표시하고 모델 SHA·방식·품질 미검증을 함께 보여준다.

학습 baseline 최초 검증 당시 일반 R2→frozen view 연결은 후보 제목과 빈 alias·role 관측을 만들었다. 이후 제목의 원문 출현을 MENTIONED로 연결하는 작업을 진행했다. 당시 자동 별칭 연결과 PRIMARY/PREVIOUS/COMPARISON 관계 추론은 미완료였으며, 학습기에 역할 특징이 있다는 사실을 전체 역할 추론의 구현·품질 증거로 사용하지 않는다.

학습은 기존 네 분할의 노출 검산이 VALID일 때 TRAIN만 사용한다. query 전체 순서·후보 title/alias의 exact source bytes·PRE_SELECTION capture를 결속한다. capture와 판정 근거는 별도이며 선언된 capture 시점과 정답의 사실성을 독립 인증하지 않는다. NIL 행은 분모에 기록하되 pairwise 학습의 NIL head로 취급하지 않는다. 학습 가능한 쌍이 없으면 거절한다. 모델을 자동 다운로드하거나 corpus·정답·후보를 만들어 채우지 않는다.

`tools/run_candidate_reranker_training.py --bundle <명시 로컬 bundle> --bundle-sha256 <raw SHA256> --output-dir <새 폴더>`는 입력 파일의 SHA·경계·자원을 확인하고 새 `model_manifest.json`, `training_report.json`, `workflow_receipt.json`을 저장·재판독한다. 출력 폴더 재사용과 부분 산출물 덮어쓰기는 거절한다. 이 경로는 로컬 CPU 학습이며 모델·검색 검증런을 시작하는 명령이 아니다. 생성한 manifest와 원시 SHA를 기존 `expert_main --candidate-retrieval SHADOW --candidate-reranker SHADOW --reranker-manifest ... --reranker-manifest-sha256 ...` 설정으로 소비한다. 기본 OFF와 기존 공개 guard는 유지된다.

평가기는 `fit_calibration_thresholds`로 CAL에서만 원시 점수와 1·2위 margin의 임계값을 고정한다. `evaluate_frozen_scores`는 외부에서 고정한 정책 SHA와 같은 split/model 결속을 확인하고 FROZEN만 판독한다. 점수는 확률이 아니며 후보 하나·빈 후보는 NIL로 바뀌지 않는다. NIL 정책은 미지원으로 남고 ABSTAIN·UNAVAILABLE·candidate miss와 전체 분모를 보존한다. 실제 semantic 성능과 정식 KPI 승인 경로는 별도다.

API와 bundle의 정확한 필드·상한은 [학습 API](../../out/development_plan_20261010/r4_learned_api_KO.md), [학습 workflow](../../out/development_plan_20261010/r4_training_workflow_api_KO.md), [평가 API](../../out/development_plan_20261010/r4_score_evaluator_api_KO.md)를 따른다.

v2 baseline 당시 기능 단위 검증: 변경 영향 Python 11파일의 403개 시험·10개 하위 시험과 Node 38개를 통과했다. [Python 수령증](../../out/development_plan_20261010/r4_learned_final_receipt.json)과 [Node 수령증](../../out/development_plan_20261010/r4_learned_node_receipt.json)을 따른다. 초기916/139/25와 이전 R5·R6 수치를 합산하지 않는다.

학습 분할 결속 후속: 모델 내부 `training_binding.split_manifest_sha256`를 summary와 scored/unscored receipt의 `training_split_manifest_sha256`로 전달한다. 평가기는 현재 split manifest와 직접 대조하므로 같은 모델을 두고 TRAIN/FROZEN을 재배정한 새 분할을 거절한다. 최초396/10 PASS 뒤 이 경계의 반례를 추가했고 최종403/10 PASS다. 두 시험 수를 합산하지 않는다.

## 선택 전 제목 출현 관측 후속

일반 `expert_main`의 R2 조회 후 expert 호출 전 경로에 `candidate_reranker_roles.observe_preselection_roles`를 연결했다. 검산한 frozen view의 원문 fragment와 고정 후보 제목만 받아 정확한 출현을 MENTIONED로 남긴다. 원문·후보 ID·순서·제목·생성 상태는 보존한다. role span은 fragment별 Python 문자 좌표이며 `text_sha256`는 그 원문 조각의 UTF-8 SHA다. 학습 자료의 byte 좌표와 혼용하지 않는다.

표면 정규화·부분 단어·대소문자 보정·추정 별칭은 사용하지 않는다. 단어 문자(Unicode 영숫자·밑줄·결합/서식 문자)가 아닌 경계와 명시된 한글 조사 경계를 허용한다. 공백·개행·문장부호뿐 아니라 기호·이모지도 경계가 될 수 있다. 동일 제목이 여러 후보에 대응하거나 경계가 유효한 제목 span끼리 겹치면 모두 미결합으로 남긴다. 이 정책은 긴 제목 일부를 다른 작품으로 확정하지 않지만, 긴 제목 자체의 관측도 보류할 수 있다. `아생갤`이 고정 corpus의 제목이면 그대로 관측하며, 갤러리라는 표현을 현실 커뮤니티명으로 강제 분류하지 않는다. 전체 제목만 있는 후보에 약어를 임의 연결하지 않는다.

후보당 32개·전체 128개 관측, 원시 출현 탐색 4096개 상한을 넘으면 부분 결과를 반환하지 않는다. 실행 전 UNKNOWN/TRUNCATED·빈 후보·빈 원문은 기존 terminal을 유지한다. producer 오류는 점수화를 중단하지만 기존 expert 분석·검색·공개 결과에는 관여하지 않는다.

`preselection_role_producer`는 정책 SHA, 실행 상태, 사유, 집계와 역할 추가 후의 frozen view SHA를 receipt에 함께 봉인한다. OBSERVED는 결속된 제목 출현이 있다는 뜻이고, AMBIGUOUS는 출현이 있으나 전부 동명·겹침으로 미결합인 상태다. NO_MATCH는 결속된 출현이 없다는 뜻이며 작품 없음(NIL)이 아니다. 관측과 모호성이 함께 있으면 OBSERVED와 미결합 집계를 함께 남긴다. 미실행·오류의 입력 SHA와 집계는 null이며 0건 정상 관측으로 바꾸지 않는다. run policy의 `preselection_role_producer_policy`에도 같은 정책을 기록한다.

수동 frozen-view scorer API는 보존한다. metadata가 없는 기존 영수증을 exporter에 주면 원래 영수증부터 검산하고 NOT_EXECUTED / EXPLICIT_FROZEN_VIEW_PROVIDED를 붙인다. 이 경우 producer 입력 SHA는 null이고 원래 scorer의 입력 SHA는 유지한다. 학습 capture/view schema는 변경하지 않았다. 기존 capture SHA는 역할을 포함한 입력을 결속하지만, 새 producer 정책의 실행 시점까지 독립 인증하지는 않는다.

대시보드는 역할 관측 상태·사유·집계·정책 및 입력 SHA와 후보별 원문 위치를 표시한다. MENTIONED만 자동 관측한다는 한계도 함께 표시한다. 당시 PRIMARY/PREVIOUS/COMPARISON 관계 관측과 검증 자료의 별칭 연결은 미완료였으며 후속 관측 구현은 아래 기록을 따른다. 실제 자료의 품질 평가는 남아 있다.

기능 단위 검증은 Python 12파일의 **494개 시험·10개 하위 시험**, Node **39개** PASS다. [Python 수령증](../../out/development_plan_20261010/r4_roles_final_receipt.json)과 [화면 표시 시험](../../out/development_plan_20261010/r4_roles_node_final_receipt.json)을 따른다. Python 검증의 시작·종료 priority16384·affinity2·수치 스레드5종=1, 소스302개 지문 일치와 외부 socket 시도0을 확인했다. 기존 Windows 임시 디렉터리 정리 경고1개는 로그에 남겼으며 시험 실패는 없다. 이전 단계 시험 수와 합산하지 않는다.

독립 검토 후속: scorer가 receipt 상한으로 상세 관측을 생략할 때 LIMIT_EXCEEDED / RECEIPT_BYTE_LIMIT가 일반 ERROR로 바뀌던 경계를 수정했다. 완료된 producer의 집계·입력 SHA는 유지하고 큰 관측 배열은 다시 붙이지 않는다. 실제 adapter 제한 분기의 process→export 회귀를 추가했다. 초기493개 PASS 기록은 보존하며 최종494개 PASS와 합산하지 않는다.

실제 Chrome에서는 합성 corpus를 R2→runtime producer→scorer→export로 처리한 3행의 live/history 6화면을 확인했다. OBSERVED의 MENTIONED 원문 위치, 동명 후보 AMBIGUOUS, TRUNCATED의 NOT_EXECUTED가 API·저장 영수증과 같았다. 콘솔 오류·경고0, 안내 로그2였으며 서버·Chrome 종료와 포트 해제를 확인했다. 기존 합성 모델을 읽기 전용으로 재사용했고 화면 검증 중 새 학습·모델 API·검색은0회다. [화면 수령증](../../out/development_plan_20261010/r4_roles_browser_receipt.json), [화면 검증 기록](../../out/development_plan_20261010/r4_roles_browser_final_KO.md), [후속 독립 검토](../../out/development_plan_20261010/r4_roles_final_review.json), [원본 보존 검사](../../out/development_plan_20261010/r4_roles_preservation.json)를 따른다. P4 실제80의 자동 승인 차단과 전체 Goal active 상태는 유지한다.

## NIL head 학습과 event 연결 후속

`candidate_reranker_nil_learned`는 같은 TRAIN에서 학습한 pairwise 모델을 고정하고, 후보와 NIL의 공동 softmax 손실로 NIL head의 24개 선형 파라미터만 갱신한다. bias·후보 수·기존 11개 특징의 최대/평균을 사용한다. 원문 관측을 이용한 선형 baseline이며 신경망 의미 모델은 아니다. 명시된 CANDIDATE와 NIL TRAIN이 모두 필요하다. 후보 누락·미판정·검색 장애를 NIL 학습 정답으로 바꾸지 않으며 CAL/FROZEN 라벨은 optimizer에 사용하지 않는다. 학습 중 손실 계산에 쓰는 값과 사용자에게 제공하는 교정 확률은 구분한다.

기존 training bundle v1은 pairwise를 유지한다. bundle v2의 필수 `backend`를 `NIL_AUGMENTED_LINEAR_V1`으로 명시하면 `parameters.base`와 `parameters.nil_head`를 검산해 manifest v3를 저장한다. CLI 명령과 배타 저장·입력 원본 검산은 기존 계약을 따른다. `train_nil_head(base_model, ...)`로 이미 학습한 같은 TRAIN 모델을 고정해 head만 학습할 수도 있다. 새 모델은 base 모델 SHA와 TRAIN·source·evidence·노출 결속을 함께 검산한다. [NIL CLI 계약](../../out/development_plan_20261010/r4_nil_training_workflow_api_KO.md)에 정확한 필드를 기록했다.

일반 R2 → 제목 MENTIONED 관측 → scorer → export 경로는 고정 후보의 기존 점수를 그대로 유지하고 `nil_score`와 `event_logits`를 추가한다. event 배열은 순위순이 아니라 고정 입력 후보 순서이며 마지막만 `__NIL__`이다. `ranked_candidates`에는 실제 후보만 둔다. NIL 예약 ID·잘못된 순서·불리언/비유한 점수·모델 지문 불일치·확률 삽입을 거절한다. 미점수·오류·상한 상태에는 NIL 점수를 만들지 않는다. `nil_probability`와 선택은 null이고 공개 권한은 false다. 대시보드에는 이 한계와 raw 점수를 함께 표시한다.

`candidate_reranker_event_bridge.build_frozen_event_score`는 검산한 raw receipt·summary·원문 capture·명시 ID 대응·기존 candidate graph와 generation/retrieval 근거를 받아 FROZEN_HOLDOUT의 `EventScoreVector`만 만든다. corpus ID와 CandidateOption ID는 전체 후보의 일대일 대응이 있어야 하며, 기존 event 순서로 옮길 때도 후보/NIL 점수는 보존한다. TRAIN 포함 manifest SHA와 기존 calibration manifest SHA는 별도로 검산한다. [event 연결 API](../../out/development_plan_20261010/r4_nil_event_bridge_api_KO.md)에 원문과 graph를 연결하는 별도 evidence 바이트의 exact projection을 기록했다. 이 연결은 공급자가 선언한 관계를 검산하며 상류 사실성을 독립 입증하지 않는다.

이 NIL 후속 검증 당시에는 일반 R2 graph 자동 공급과 CAL temperature optimizer가 없었다. CAL optimizer의 후속 구현은 아래 최신 기록을 따른다. 기존 pairwise raw threshold 평가기는 v2 범위에 남으며 v3 NIL 확률 평가기로 승격하지 않는다. 순수 event 변환만으로 교정 artifact·fit receipt·확률·최종 판정을 만들지 않는다. 적격 실제 TRAIN/CAL/FROZEN, 전체 의미 역할과 검증된 별칭, NIL 확률 교정·품질 수용 판정은 계속 미완료다.

기능 단위 검증은 Python 14파일의 **603개 시험·10개 하위 시험**, Node **40개** PASS다. [Python 수령증](../../out/development_plan_20261010/r4_nil_initial_receipt.json), [표시 시험 수령증](../../out/development_plan_20261010/r4_nil_node_receipt.json)을 따른다. Python 시작·종료 priority16384·affinity2·수치 스레드5종=1, 소스306개 SHA 일치와 외부 socket 시도0을 확인했다. 기존 Windows 임시 디렉터리 정리의 WinError145 경고1개는 로그에 보존했다. 모든 수치는 이번 변경의 검증 범위이며 이전 단계와 합산하지 않는다. 실제 외부 LLM·검색 실행은0회, source-backed 학습은0회다. P4 실제80은 명시적 승인 후에도 자동 승인 검토에 차단되어 미시작이며 재시도하지 않았다. 전체 Goal은 active이고 R7은 보류다.

실제 Chrome에서는 새 합성 TRAIN bundle v2 → 학습 CLI → manifest v3 → R2 → 제목 관측 → scorer → export로 만든 3사례를 live/history 6화면에서 확인했다. NIL raw score·TRUNCATED의 null/빈 배열·모델 불가를 구분했고, 각 API는 저장 receipt와 같으며 manifest는 모두 BOUND였다. 소스17개 SHA 일치, 콘솔 오류·경고0을 확인하고 서버·Chrome 종료와 포트 해제를 검산했다. Chrome 전체 소켓은 계측하지 않았으므로 전역 외부 통신0을 주장하지 않는다. 최초 helper의 pytest 부재 실패는 산출물 생성 전이었고 원본 로그를 보존했다. [화면 수령증](../../out/development_plan_20261010/r4_nil_browser_receipt.json), [최종 화면 기록](../../out/development_plan_20261010/r4_nil_browser_final_KO.md), [독립 원본 보존 검사](../../out/development_plan_20261010/r4_nil_preservation.json)를 따른다. CLI/API 작성 시 계약 문서의 미실행 표기는 당시 이력이며 현재 기능 시험 결과는 위 수령증을 우선한다.

## CAL 온도 학습과 저장 근거 재검산

새 `candidate_reranker_calibration`은 후보 모델과 NIL head를 고정한 채 CAL 전체 후보+NIL 사건의 평균 NLL을 최소화하는 양의 온도 하나를 학습한다. 역온도 beta의 구간은 기본0.01~100, 기본 반복 상한80회다. 볼록 목적함수의 도함수를 이분 탐색하며 구간 끝 최적점·내부 수렴·평평한 손실의 항등 온도를 구분한다. 미수렴이나 비유한 점수는 성공 산출물로 만들지 않는다. CAL 손실 감소는 FROZEN 품질 개선이나 실측 KPI를 뜻하지 않는다. threshold와 모델 가중치는 갱신하지 않는다.

`build_calibration_fit_events`는 기존 FROZEN enum에 CAL을 넣지 않고 별도 `CalibrationFitEvent`를 만든다. 명시된 원문·capture·동일 모델·raw receipt·candidate graph·ID 대응을 검산한다. 외부 두 manifest의 CAL 전체 집합과 example_id 오름차순을 정확히 대조하므로 누락·중복·행 제거·분할 혼입을 허용하지 않는다. 각 행은 기존 후보 순서와 마지막 NIL을 유지한다. 정답은 manifest의 UNIQUE 후보 또는 명시 NIL이며 점수에서 추측하지 않는다. 기존 DEV/CAL 최소 표본·각 정답 부류·미해결 라벨 게이트를 유지한다. 최대256행·행당20후보+NIL, raw score 절댓값10,000, 학습 근거8MiB 제한이다. [자료 연결 계약](../../out/development_plan_20261010/r4_calibration_bridge_api_KO.md)을 참고한다.

fit receipt와 calibration artifact의 새 schema는 각각 `candidate_set_calibration_fit_receipt_v2`, `candidate_set_calibration_artifact_v2`다. 저장 근거에는 전체 CAL event, manifest·정책, 모델·원문 결속 지문, 학습 설정, 수렴 상태·온도·전후 NLL을 포함한다. 공용 `calibration_artifact_from_dict`와 기존 artifact validator는 자체 SHA뿐 아니라 내장·외부 결속과 결정적 수치 결과를 재검산한다. 온도나 수렴 결과를 바꾼 뒤 모든 SHA를 다시 계산해도 거절한다. 기존 v1 JSON 키·지문과 소비는 유지하며 v1에 실제 optimizer 실행 근거가 있다고 해석하지 않는다.

명시적 로컬 명령은 다음과 같다. bundle·모델·원문은 고정된 프로젝트 내부 상대 참조와 정확한 raw SHA/크기로 공급한다. 새 출력 폴더에만 저장한다.

```text
python tools/run_candidate_reranker_calibration.py --bundle <bundle.json> --bundle-sha256 <raw-sha256> --output-dir <새-출력-폴더>
```

CLI는 고정 모델로 모든 CAL 점수를 재생해 공급 receipt의 점수·모델·입력 지문과 대조한 뒤 학습한다. `calibration_artifact.json`, `fit_receipt.json`, `fit_report.json`을 저장하고 raw bytes와 typed 재판독을 확인한다. 최종 성공 수령증은 검산한 임시 수령증을 확정한 뒤에만 남긴다. 실패 증거를 보존하며 기존 출력은 덮지 않는다. [bundle 필드·저장 계약](../../out/development_plan_20261010/r4_calibration_workflow_api_KO.md)을 따른다. 일반 expert_main에 새 교정 옵션을 연결한 것은 아니다.

저장된 v2 artifact와 별도 FROZEN `EventScoreVector`를 기존 `build_calibration_shadow`에 넣어 후보+NIL 확률 질량 합1,000,000과 artifact 결속을 확인했다. 기존 base·모델을 변경하지 않고 `action_applied=false`, 공개 권한false를 유지한다. 이 시험은 합성 FROZEN 소비 검증이며 실제 FROZEN 품질 평가가 아니다. 원시 점수와 실제 source-backed 자료·주석·권리의 사실성은 외부 근거가 별도로 필요하다.

최종 회귀는 Python **22파일 833개 시험·21개 하위 시험 PASS**다. [최종 수령증](../../out/development_plan_20261010/r4_calibration_final_receipt.json)과 [별도 CLI 실행 수령증](../../out/development_plan_20261010/r4_calibration_cli_smoke_receipt.json)에 프로세스·저부하 자원·원본 불변·실행 결과를 기록했다. 최초22파일 실행은820개·하위21개 통과, 기존 Golden18 label_ledger raw SHA 불일치로 준비도 시험8개가 setup에서 오류였다. 원본을 바꾸지 않고 해당8개의 기존 assertion을 현재 합성18행 graph에 연결했으며 원본 거절 반례를 추가했다. [최초 실패 로그](../../out/development_plan_20261010/r4_calibration_initial_tests.log)를 보존했다. 최종 수령증 저장 후 재판독 실패 시 성공 파일이 남을 수 있던 정적 리뷰 지적도 임시 파일 검산 후 확정 방식으로 수정했다.

이번에는 화면 소스를 바꾸지 않았다. 이전 NIL 단계의 Python603개·하위10개, Node40개·Chrome6화면은 당시 증거이며 이번 숫자와 합산하지 않는다. 실제 외부 LLM·검색 호출과 source-backed 학습은0회다. 일반 R2 source/ID/graph 자동 공급·runtime 교정 저장/표시, 의미 역할·검증된 별칭, 실제 TRAIN/CAL/FROZEN·품질 수용은 미완료다. P4 실제80은 자동 승인 차단 뒤 재시도하지 않았으며 앱 Goal active·R7 보류를 유지한다.

[다음 일반 실행 연결 범위](../../out/development_plan_20261010/r4_calibration_runtime_next_scope_KO.md)는 선택 전 원문 capture 저장, 명시적 graph와 분할 배정 검산, 별도 교정 receipt 저장·표시 순으로 나눴다. runtime 정수 post ID와 학습 문자열 ID의 대응도 먼저 명시해야 한다. 현재 모든 일반 입력을 FROZEN으로 간주하거나 누락된 근거를 기본값으로 채우는 연결은 구현하지 않았다.

## expert_main의 명시 FROZEN 재관측·capture 저장

`--candidate-calibration SHADOW --calibration-bundle <로컬 bundle> --calibration-bundle-sha256 <raw SHA256>`를 추가했다. R2와 reranker도 SHADOW여야 한다. CLI가 환경 변수보다 우선하며 기본 OFF에서는 capture·bundle 파일을 읽거나 쓰지 않는다. 환경 변수는 `EXPERT_CANDIDATE_CALIBRATION`, `EXPERT_CALIBRATION_BUNDLE`, `EXPERT_CALIBRATION_BUNDLE_SHA256`다. 비교 측정의 연구 기능 OFF 조건도 유지한다.

bundle은 기존 CAL v2 artifact, 두 split manifest, 정책, source/evidence 파일 참조와 FROZEN 전체 행을 명시한다. 각 행은 runtime ID와 dataset ID의 타입까지 선언한다. 현재 원문 view의 두 post_id만 비교용 복사본에서 대응시킨 뒤, 나머지 원문·후보·순서·역할·생성 지문과 실제 점수가 고정 자료와 정확히 같아야 한다. 기존 FROZEN graph·split·scorer 재생·artifact 검산은 유지한다. TRAIN/CAL 행, 미배정 새 글, source·ID·모델 불일치에는 확률을 만들지 않는다. [정확한 bundle/API](../../out/development_plan_20261010/r4_runtime_calibration_api_KO.md)를 따른다.

선택 전 실제 R2→MENTIONED→scorer 호출에서 원문 frozen view, raw receipt, scorer summary와 R2 receipt를 호출별 깊은 복사로 보존한다. scorer는 추가 호출하지 않는다. 파싱된 fragment의 UTF-8 길이·SHA와 role 문자/byte 좌표를 재검산하며, 입력 JSONL 자체의 원시 byte 위치나 정답·권리 사실성을 추론하지 않는다. capture는 256KiB, 저장 artifact는 512KiB 상한이다.

행에는 작은 `candidate_reranker_capture` 참조를 저장하고 원문은 실행 출력 폴더의 `candidate_reranker_captures/<run 지문>/<artifact 지문>.json`에 보존한다. 현재 run/input_index/post/attempt/publication_scope 및 입력 snapshot SHA를 함께 결속한다. 임시 파일의 쓰기·fsync·재판독 후 기존 파일을 덮지 않는 rename으로 최종 경로에 저장한다. 같은 파일은 byte가 일치할 때만 재사용하며, 실패는 성공 참조로 표시하지 않는다. capture 저장은 학습 자료 준비 완료를 뜻하지 않는다.

별도 `candidate_calibration_shadow`는 capture 저장이 SAVED이고 관측 지문과 행 결속이 일치할 때만 CALIBRATED_SHADOW_BOUND다. 원래 raw receipt의 미교정 상태·확률 null은 그대로 보존한다. 결과 없는 조기 반환은 NOT_EXECUTED, 실행 중 교정 관측 누락은 NOT_AVAILABLE로 구분한다. private 관측은 호출별로 유지하고 성공·오류 양쪽 결과에 전달하며, 재사용 결과의 오래된 값을 제거한다. 공개 WAL의 안정 결과 지문에서 두 관측 필드를 제외하므로 공개 결과와 중앙 DB를 바꾸지 않는다.

live/history 공통 화면은 교정 정책, 저장된 정수 확률 질량·기준값, 명시 ID 대응과 capture 참조를 표시한다. 파일 참조를 임의로 열지 않고, 브라우저에서 softmax나 NIL 판정을 다시 계산하지 않는다. 누락·null·false를 구분하고 새 receipt의 run/scope 충돌은 manifest 결속 실패로 표시한다.

당시 원문 관계·별칭 관측은 미완료였으며 아래 후속 단계에서 추가했다. 당시 R6의 transport·durable journal·재시작 예산 연결은 미완료였으며 현재 상태는 위 최신 기록을 따른다. 최신 NIL 모델과 교정 결과의 순위·전체 terminal·FROZEN 평가 연결은 아래 후속 단계에서 구현했다. 기존 PAIRWISE_LINEAR_V1 전용 평가기는 그대로 유지한다. R2/R3 품질과 R5 paired 비용·품질에는 실제 고정 자료와 실행 근거가 더 필요하다.

당시 R4 상태는 **FROZEN_RUNTIME_CALIBRATION_LOCAL_VERIFIED_ACTUAL_DATA_AND_GENERAL_GRAPH_PENDING**였다. `expert_main`에 선택 전 원문 capture 저장과 명시적 FROZEN 재관측 교정을 연결하고 웹 대시보드의 실시간·이력 화면에 별도 표시했다. 저장된 CAL artifact와 명시 source/ID/graph를 검산한 행만 확률을 받는다. 일반 R2의 source/ID/graph 자동 공급, 새 입력의 추론 계약, PRIMARY/PREVIOUS/COMPARISON·별칭, 실제 TRAIN/CAL/FROZEN 품질 검증은 남았다. Python 28파일 1002개 시험·45개 하위 시험, Node 41개와 Chrome 6화면을 통과했다. 합성 자료의 로컬 검증이며 실제 모델 API·검색·source-backed 학습은0회다. formal KPI는 NOT_ESTIMABLE, Goal은 active다.

검증 근거: [묶음 회귀](../../out/development_plan_20261010/r4_runtime_calibration_final_receipt.json), [Node](../../out/development_plan_20261010/r4_runtime_calibration_node_receipt.json), [Chrome](../../out/development_plan_20261010/r4_runtime_calibration_browser_receipt.json). 실제80건은 사용자 승인 후에도 자동 승인 검토의 `blocked by policy`로 실행되지 않았다. 차단된 명령을 다시 시도하지 않았다. 전체 P4·R2~R6의 실제 자료/실측/의미 품질과 R7 보류 상태는 유지한다.

## NIL 순위·FROZEN 교정 평가와 로컬 보고서

기존 pairwise 평가 API는 그대로 두고 `candidate_reranker_nil_evaluation.evaluate_frozen_nil_scores`를 추가했다. 전체 FROZEN expected 행과 저장 관측의 순서·집합, TRAIN manifest와 고정 NIL scorer, 원문 capture·후보 ID 대응·점수를 먼저 검산한다. MRR은 후보 정답 행의 후보 순위로 계산하며 NIL을 후보 순위에 끼워 넣지 않는다. 성공 행의 조건부 지표와 전체 terminal을 포함한 운영 분모를 따로 기록한다.

ERROR·UNAVAILABLE·미실행·후보 누락·UNJUDGED를 정답 NIL로 바꾸거나 평가 목록에서 제거하지 않는다. 필요한 graph나 성공 관측이 부족하면 raw 처리 현황은 보존하고 정식 교정 평가는 NOT_EVALUABLE로 남긴다. NIL 최고점과 ASSERT_NIL 행동은 구분하며, 모든 행이 보류되면 selective risk의 0분모는 null이다.

교정에는 학습된 v2 artifact와 전체 CAL 학습 근거를 사용한다. 현재 model/base model/scorer/scorer summary/TRAIN manifest/CAL manifest/data_kind의 결속을 확인하고 기존 event bridge·calibration shadow·FROZEN evaluator를 재사용한다. FROZEN에서 온도나 임계값을 다시 맞추지 않는다. 합성 평가의 GO는 계약 검증이며 실제 자료의 성능·권리·정답 사실성을 입증하지 않는다. 이번 API·CLI에는 실제 readback과 baseline 연결을 아직 지원하지 않는다. SOURCE_BACKED 입력의 raw 현황과 검산 가능한 행별 교정 관측은 보존하되, 전체 정식 평가는 NOT_EVALUABLE로 남기고 실제 품질을 수용하지 않는다. 실제 품질 수용을 위해서는 기존 사전 등록 정책·독립 파일 readback·동일 행 baseline·구간 추정 조건을 별도로 연결해야 한다.

실행 명령은 `python tools/run_candidate_reranker_evaluation.py --bundle <bundle.json> --bundle-sha256 <raw SHA256> --output-dir <새 폴더>`다. bundle schema는 `candidate_reranker_evaluation_bundle_v1`이며 모델·CAL artifact·source/evidence 파일 참조는 bundle 폴더 안 상대 경로로 지정한다. 파일 참조는 path/sha256/bytes다. 나머지 입력은 두 manifest와 각 예상 SHA, 정책, 예상 scorer summary SHA, 전체 expected_rows/observations와 명시 frozen_rows다. 새 원문 graph나 ID 대응을 도구가 추론하지 않는다.

CLI는 병렬1에 해당하는 단일 프로세스·BelowNormal·CPU1·숫자 라이브러리 스레드1의 저부하 설정으로 고정한다. 성공 관측만 고정 모델로 재점수화해 확인하고, 원래 실패 관측을 재실행 성공으로 바꾸지 않는다. 새 학습·외부 모델 API·검색 호출은 없다. report를 임시 파일에 배타 저장·fsync·재판독한 뒤 기존 파일을 덮지 않는 rename으로 확정하고, 입력 파일을 다시 검산한 후 workflow_receipt.json을 최종 완료 표식으로 기록한다. 중간 파일만 있고 최종 수령증이 없으면 완료된 실행으로 사용하지 않는다.

이번 변경은 offline 평가 API와 보고서 CLI이며 웹 화면을 다시 바꾸지 않았다. 실제80건은 자동 승인 검토의 차단 후 재시도하지 않았고, P4·R2/R3/R5 실제 자료 평가와 R6 실제 복구 연결·재시작 예산 검증, R7 보류는 그대로 남는다.

검증: Python 18파일 710개·하위11개 PASS. [회귀 수령증](../../out/development_plan_20261010/r4_nil_evaluation_final_receipt.json)을 따른다.

## 명시 원문 관계·검증 자료의 별칭 관측과 실행 연결

`--candidate-semantics SHADOW`는 R2 조회 뒤 선택·전문가 호출 전에 실행한다. 기본값은 OFF이며 `--candidate-retrieval SHADOW`가 필요하다. 기존 reranker가 없어도 관측할 수 있다. 설정은 CLI가 환경변수 `EXPERT_CANDIDATE_SEMANTICS`보다 우선하며 manifest와 설정 화면에 실제 정책 지문·별칭 bundle 지문을 남긴다.

원문 작성자의 명시 리뷰·분석 대상은 PRIMARY, 명시 작가 전작 관계는 PREVIOUS, 방향이 있는 비교 관계는 COMPARISON으로 관측한다. PREVIOUS는 독자가 전에 읽은 작품이라는 뜻이 아니다. 좁은 명시 문법으로만 관계를 관측하므로 일반 자연어 이해가 끝났다는 뜻은 아니다. 후보명·원문·후보 ID/순서/생성 지문을 보존하고 출현·관계 근거의 Unicode/UTF-8 위치와 원문 SHA를 기록한다. 댓글, 인용, 전언, 조건문, 부정, 발화 라벨과 충돌은 MENTIONED 또는 미결합 사유로 남긴다. 여러 줄·본문 조각에 걸친 미종결 인용도 작성자 단언으로 승격하지 않는다. 최종 selection·ExpertSignals·최종 context projection은 관측 입력으로 역류시키지 않는다.

별칭은 `--semantic-alias-bundle <bundle.json> --semantic-alias-bundle-sha256 <원본 SHA256>`로 제공한다. 환경변수는 `EXPERT_SEMANTIC_ALIAS_BUNDLE`, `EXPERT_SEMANTIC_ALIAS_BUNDLE_SHA256`이다. bundle은 `candidate_semantics_alias_bundle_v1`이며 `alias_evidence`와 `evidence_files`를 포함한다. 정적 별칭 설정은 R3 manifest SHA·snapshot 파일 지문 맵·R2 corpus SHA를 지정하고, evidence_files는 SHA를 키로 한 bundle 내부 상대 path/sha256/bytes 참조다. 실행 게시글의 community/time/R2 receipt를 bundle에 미리 넣을 수 없다. 경로 이탈·링크·원격 참조·원문 변조는 거절한다. 필요한 원본 manifest·corpus·snapshot·payload·review/권리 자료가 모두 있어야 한다.

원본의 명시 별칭 관계와 review body, 후보 work/edition/media, community와 유효 시각·lineage·경쟁 의미를 검산한 UNIQUE binding만 연결한다. SOURCE_BACKED는 제공된 HUMAN_REVIEW 근거를 요구하고 합성 fixture는 별도 evidence grade로 표시한다. review에 HUMAN_REVIEW라고 쓰여 있다는 사실만으로 실제 검토자 신원이나 의미 정답을 인증하지 않는다. `actual_semantic_evidence_verified`와 `reviewer_identity_verified`는 false다. 모델 참고 의견·unknown 권한, 미기록 community/time, 판본 미결합을 추정으로 채우지 않는다. `아생갤`·`갤러리`를 일괄 현실 DC 커뮤니티로 분류하지 않는다.

행에는 `candidate_reranker_semantics`와 `candidate_reranker_semantics_capture`를 저장한다. 현재 입력과 현재 고정 R2를 독립 재관측하므로 같은 ID의 다른 원문·corpus 패키지 치환을 거절한다. 정상 관측은 원문·근거·정책·입력 snapshot SHA·회차 binding과 함께 새 capture 파일에 저장하고, 별칭 bundle 원본과 각 evidence 원본은 공통 archive에 보존한다. SHA·bytes를 재판독한 뒤에만 SAVED로 표시한다. `read_candidate_semantics_capture`는 원본 bundle 경로 없이 archive를 읽고 producer를 재생한다. 이는 저장물의 일관성 검사이며 원래 입력 파일·실제 실행·정답 사실성을 새로 인증하는 함수는 아니다.

저장 실패 시 관측은 보존하고 capture는 NOT_AVAILABLE이다. 미실행·미기록·실패는 성공 0건으로 바꾸지 않는다. 구형 scorer 지문을 확인할 수 없어도 정상 신규 관측을 지우지 않는다. 웹 화면 코드는 실시간과 이력 모두 역할·화자·원문·별칭 근거·정책·미결합 사유·capture 상태를 표시하도록 연결했으며 원본 JSON도 보존한다. 상세 카드가 표시 상한을 넘으면 축약 사실을 알린다. 당시 Python·Node 표시 시험은 통과했으나 Chrome 시작이 자동 승인 검토에서 차단되어 6화면 검증은 미실행이었다. 이후 [현재 IAB의 합성 저장자료 검증](../../out/development_plan_20261010/p4_reapproval_v1/semantics_browser_v1/REPORT_KO.md)에서 6화면·API 저장값 동등성·콘솔 오류/경고0을 확인했다. 이전 단계의 브라우저 PASS를 재사용한 것이 아니며 새 모델 소비 성공이나 실자료 품질은 별도다.

기존 v1 모델에는 새 의미 관측을 넣지 않는다. 이 경로는 `OBSERVED_NOT_CONSUMED`, `scorer_input_applied=false`, `calibration_input_applied=false`로 기록하며 기존 v1 점수·CAL 계약과 공개 결과/WAL은 유지한다. 새 v2 모델의 실제 소비는 아래 후속 구현 계약을 따른다. 실제 역할·별칭 품질, 실제 TRAIN/CAL/FROZEN, 일반 graph/새 입력 추론, P4 실제80과 R6 실제 복구는 여전히 미완료다. R7은 보류한다.

검증 근거: [묶음 회귀](../../out/development_plan_20261010/r4_semantics_final_receipt.json), [Node 표시 시험](../../out/development_plan_20261010/r4_semantics_node_receipt.json), [실시간·이력 브라우저](../../out/development_plan_20261010/r4_semantics_browser_receipt.json).

## 의미 특징을 학습·실행·교정에 소비하는 새 계약

기본 동작은 v1이다. 새 학습 bundle `candidate_reranker_training_bundle_v3`는 기존 v2 필드에 `semantic_feature_contract_sha256`을 추가하며 현재 공통 특징 계약과 같아야 한다. pairwise/NIL 모델과 feature schema는 각각 v2로 분기한다. backend 이름과 바깥 manifest 형식은 유지하되 model/feature의 정확한 조합만 허용한다. TRAIN의 의미 artifact 집합 지문을 base/head 내부에 결속하고 NIL은 같은 고정 base를 사용한다. 새 view를 구형 모델에 넣거나 새 모델에 구형 capture를 넣는 요청은 거절한다.

학습 capture `reranker_preselection_capture_v2`는 `semantic_input_sha256`으로 원본 의미 artifact를 참조한다. 이는 artifact 내부의 self 제외 지문과 별개다. 공통 검산자는 원문·고정 R2→producer 전체를 재생하고 파생 역할·alias·근거·정책을 대조한다. 정의 원문과 review 원문을 행 및 후보의 source 노출에 포함하고, 동일 lineage와 정규화 alias-family를 기존 전체 분할 검사로 확인한다. 독립적인 정답·검토자 신원·권리를 인증한다는 뜻은 아니다.

별칭이 없는 입력도 R2 전체 후보의 work/edition/media와 data_kind를 분할 선언에 직접 대조한다. 바깥 지문만 다시 계산한 다른 작품·판본·매체·자료 종류를 허용하지 않는다.

실행 시 새 모델은 `--candidate-semantics SHADOW` 관측에서 현재 post/R2와 독립 대조한 입력을 받는다. 점수 capture v2는 실제 호출의 의미 입력과 원본 별칭 bytes를 보존하고 재판독 시 다시 검산한다. `--candidate-calibration OFF`에서도 새 의미 모델의 capture를 저장한다. 저장 실패를 점수 성공이나 NIL 판단으로 바꾸지 않는다. 미할당 일반 게시글을 FROZEN으로 추정하지 않는다.

교정 결과를 저장할 때도 관측 시점과 같은 의미 입력 결속을 다시 검사한다. 원문과 점수가 같아도 별칭 적용 시점·공동체·원본 근거가 고정 FROZEN과 다르면 BOUND 저장을 거절한다.

전체 CAL은 새 모델로 재점수화하고 새 온도를 학습한다. 기존 CAL artifact를 새 모델에 재사용할 수 없다. 고정 FROZEN은 같은 모델/정책/명시 graph/원문을 검산하며 전체 terminal 분모와 NIL·미회수·UNJUDGED·오류를 보존한다. 평가 CLI도 원본 의미 artifact를 전달해 재점수화한 뒤 보고서를 저장·재판독한다. 실제 readback/baseline 미지원과 formal KPI의 NOT_ESTIMABLE 제한은 유지한다.

CAL 연결부의 `feature_schema_sha256`은 scorer와 똑같이 frozen view 계약과 learned feature 계약을 합친 지문을 검산한다. 학습 계약 단독 지문은 허용하지 않는다. 초기 통합 시험에서 이 계산 차이로 발생한 실패를 보존하고 PAIRWISE/NIL 양쪽의 정상·오류 지문을 회귀 시험으로 확인했다.

`candidate_reranker_semantics_runtime_v2`의 consumption은 입력 검산, backend 호출, 점수 생성, CAL 적용을 따로 기록한다. producer 원본의 NOT_CONSUMED_MODEL_POLICY_UNBOUND는 사후 변경하지 않는다. 화면은 실제 scorer 입력·특징 계약·관측·모델·점수 영수증 지문을 함께 표시하고 모순/미기록은 성공으로 보충하지 않는다. Python 및 Node 회귀와 실제 브라우저 검증은 별개이며 이번 Chrome 실행은 이전 정책 차단 이후 재시도하지 않았다.

근거: [통합 회귀](../../out/development_plan_20261010/r4_semantic_consumption_final_receipt.json), [화면 표시·테마](../../out/development_plan_20261010/r4_semantic_consumption_node_review_receipt.json), [공통 API](../../out/development_plan_20261010/r4_semantic_consumption_api_KO.md).


## 일반 입력 교정의 실행·저장·표시

`--candidate-inference SHADOW --inference-bundle <bundle.json> --inference-bundle-sha256 <raw-SHA>`를 기존 R2·고정 NIL 모델 옵션과 함께 사용한다. 기본 OFF이며 v2 의미 모델에는 의미 관측 SHADOW도 필요하다. 새 bundle은 명시된 source raw bytes·corpus·기존 CAL artifact를 묶으며 새 학습을 수행하지 않는다. 온도 수치 재생 검산과 새 온도 fit을 구분한다.

성공은 TEMPERATURE_APPLIED_BOUND_INFERENCE, 현재 고정 모델의 수치 검산, 저장 참조 SAVED를 함께 요구한다. 행의 candidate_reranker_inference/candidate_inference_capture와 manifest의 candidate_inference_policy를 보존한다. 화면은 현재 게시글·run/scope·CAL/model/원문 지문까지 대조한다. 후보가 비거나 잘렸거나 저장/검산에 실패하면 확률은 null이다. NIL 제안은 정답이나 공개 판정이 아니며 전체 웹 recall도 주장하지 않는다.

[정확한 API·bundle 구성·한계](../../out/development_plan_20261010/r4_general_inference_api_KO.md)와 [실제80 준비 보고서](../../out/development_plan_20261010/actual80_preparation_v1/report_ko.md)를 따른다. P4·실제 자료 품질·R6는 계속 미완료이며 Goal은 active다.
